"""PJe-Calc Studio — servidor local da nova interface.

Executa somente em 127.0.0.1. Serve a interface (pasta web/) e uma API JSON que:
  * guarda rascunhos, revisões e auditoria localmente (ponte/armazenamento.py);
  * opera o PJe-Calc instalado por meio da interface original (ponte/pjecalc.py), sem gravar no banco.

Uso:  py -I servidor.py [--porta 8765] [--dados ./dados] [--pjecalc http://127.0.0.1:9257/pjecalc/] [--sem-navegador]
"""
from __future__ import annotations

import argparse
import hmac
import http.client
import io
import json
import mimetypes
import os
import re
import secrets
import sys
import tempfile
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from ponte import assistente, catalogo, conferencia, exportacao, padroes, planilha, sincronizar  # noqa: E402
from ponte.ajuda_oficial import extrair, localizar_webapp, versao_instalada  # noqa: E402
from ponte.armazenamento import (Armazenamento, ConflitoRevisao, agora, dentro_de, diferencas, rascunho_vazio,  # noqa: E402
                                 sem_dados_pessoais)
from ponte.jsf import JsfError, fold  # noqa: E402
from ponte.atualizacao import Atualizador, ErroAtualizacao  # noqa: E402
from ponte.pjecalc import PJeCalc  # noqa: E402
from ponte.relatorio import comparar_pjc, decimal_br, ler_pjc, ler_relatorio, moeda_br  # noqa: E402
from ponte.tela import SessaoTela, Sessoes  # noqa: E402

VERSAO_APP = "0.2.0"
VERSOES_TESTADAS = ["2.16.0"]
WEB = os.path.join(RAIZ, "web")
ARMAZ: Armazenamento
PORTA = 8765
LIMITE_CORPO = 60 * 1024 * 1024


class ErroApi(Exception):
    def __init__(self, status: int, mensagem: str, extra: dict | None = None):
        super().__init__(mensagem)
        self.status, self.mensagem, self.extra = status, mensagem, extra or {}


def _autor() -> str:
    return ARMAZ.config().get("usuario") or "usuário local"


def _url() -> str:
    return ARMAZ.config().get("urlPjecalc") or "http://127.0.0.1:9257/pjecalc/"


def _execucao(caso: dict, eid: str) -> dict:
    for e in caso.get("execucoes", []):
        if e["id"] == eid:
            return e
    raise ErroApi(404, "Execução não encontrada.")


def _resultado(cid: str, eid: str) -> dict:
    """Resultado extraído dos arquivos oficiais guardados na execução (relidos a cada consulta:
    os arquivos do PJe-Calc são a fonte de verdade; o JSON é só um cache derivado)."""
    pasta = ARMAZ.pasta_execucao(cid, eid)
    rel, pjc = os.path.join(pasta, "relatorio.html"), os.path.join(pasta, "calculo.pjc")
    if os.path.exists(rel) or os.path.exists(pjc):
        out = {"relatorio": {}, "pjc": {"meta": {}, "verbas": []}}
        if os.path.exists(rel):
            with open(rel, "rb") as fh:
                out["relatorio"] = ler_relatorio(fh.read())
        if os.path.exists(pjc):
            with open(pjc, "rb") as fh:
                out["pjc"] = ler_pjc(fh.read())
        return out
    raise ErroApi(404, "Resultado não encontrado.")


def _estado_resultado(caso: dict) -> dict:
    """Situação do resultado em relação às entradas atuais (para o aviso de "desatualizado")."""
    ult = caso["execucoes"][-1] if caso.get("execucoes") else None
    vinc = caso.get("pjecalc") or {}
    aberto = vinc.get("abertoNoOriginalEm")
    return {
        "revisao": caso["revisao"],
        "gravadoRevisao": vinc.get("gravadoRevisao"),
        "gravadoAtual": vinc.get("gravadoRevisao") == caso["revisao"],
        "ultimaExecucao": ult["id"] if ult else None,
        "resultadoAtual": bool(ult) and ult["revisaoEntradas"] == caso["revisao"],
        # o cálculo foi aberto na interface original depois do último resultado: algo pode ter mudado lá
        "abertoNoOriginalDepois": bool(aberto) and (not ult or aberto > ult["em"]),
        "abertoNoOriginalEm": aberto,
    }


# ------------------------------------------------------------------------------------------- rotas
# ---------------------------------------------------------------------------------------------
def _tarefas_periodicas() -> None:
    """Ao abrir e a cada 12 horas, em silêncio: procura versão nova no GitHub (sem internet, nada muda)."""
    _atualizador().verificar_em_silencio()
    t = threading.Timer(12 * 3600, _tarefas_periodicas)
    t.daemon = True
    t.start()


# ---------------------------------------------------------------------------------------------
# Atualização automática (ponte/atualizacao.py): só na versão instalada; os cálculos ficam fora da pasta do programa.
_ATUALIZADOR: list[Atualizador] = []


def _atualizador() -> Atualizador:
    if not _ATUALIZADOR:
        _ATUALIZADOR.append(Atualizador(RAIZ, VERSAO_APP))
    return _ATUALIZADOR[0]


def rota_atualizacao(_h, _q, _b):
    return _atualizador().estado()


def rota_atualizacao_verificar(_h, _q, _b):
    try:
        return _atualizador().verificar()
    except ErroAtualizacao as e:
        raise ErroApi(400, str(e)) from None


def rota_atualizacao_instalar(_h, _q, _b):
    """Inicia o instalador em silêncio e encerra o Studio para os arquivos poderem ser trocados; o instalador o reabre."""
    try:
        nova = _atualizador().instalar()
    except ErroAtualizacao as e:
        raise ErroApi(400, str(e)) from None
    threading.Timer(1.5, lambda: os._exit(0)).start()  # dá tempo de a resposta chegar à tela
    return {"ok": True, "versao": nova, "mensagem": f"Atualizando para a versão {nova}. O Studio fecha e abre de novo sozinho."}


def rota_estado(_h, _q, _b):
    cfg = ARMAZ.config()
    diag = PJeCalc(_url(), timeout=5).diagnostico(tabelas=False)
    return {"app": VERSAO_APP, "config": {k: v for k, v in cfg.items() if k != "logoEscritorio"},
            "temLogo": bool(cfg.get("logoEscritorio")), "motor": diag,
            "compativel": diag.get("versao") in VERSOES_TESTADAS if diag.get("versao") else None,
            "versoesTestadas": VERSOES_TESTADAS, "atualizacao": _atualizador().estado()}


def rota_diagnostico(_h, _q, _b):
    cfg = ARMAZ.config()
    diag = PJeCalc(_url(), timeout=15).diagnostico()
    inst = {"pasta": cfg.get("pastaInstalacao") or None}
    if inst["pasta"]:
        try:
            webapp = localizar_webapp(inst["pasta"])
            inst["webapp"] = webapp
            inst["versaoArquivos"] = versao_instalada(webapp)
            raiz = inst["pasta"]
            inst["arquivos"] = {nome: os.path.exists(os.path.join(raiz, *nome.split("/"))) for nome in (
                "bin/pjecalc.jar", "bin/jre/bin/java.exe", "tomcat/conf/server.xml", ".dados/pjecalc.h2.db",
                "iniciarPjeCalc.bat")}
            banco = os.path.join(raiz, ".dados", "pjecalc.h2.db")
            if os.path.exists(banco):
                inst["bancoBytes"] = os.path.getsize(banco)
            inst["ajudaOficial"] = len(extrair(webapp))
        except Exception as e:  # noqa: BLE001
            inst["erro"] = str(e)
    avisos = []
    if not diag.get("acessivel"):
        avisos.append({"nivel": "impeditivo", "texto": f"O PJe-Calc não respondeu em {_url()}. Inicie-o pelo atalho "
                       "oficial (iniciarPjeCalc.bat) e aguarde a abertura da tela inicial."})
    elif diag.get("versao") not in VERSOES_TESTADAS:
        avisos.append({"nivel": "alerta", "texto": f"Versão {diag.get('versao')} do PJe-Calc ainda não foi validada com esta "
                       f"interface (validadas: {', '.join(VERSOES_TESTADAS)}). Rode o roteiro de equivalência antes do uso."})
    if inst.get("versaoArquivos") and diag.get("versao") and inst["versaoArquivos"] != diag["versao"]:
        avisos.append({"nivel": "alerta", "texto": "A pasta de instalação informada não corresponde ao PJe-Calc em execução."})
    tab = diag.get("tabelas") or ""
    return {"motor": diag, "instalacao": inst, "avisos": avisos, "app": VERSAO_APP, "dados": ARMAZ.pasta,
            "backups": ARMAZ.listar_backups()[:5], "tabelasTexto": tab}


def rota_config(_h, _q, b):
    permitidos = {"urlPjecalc", "usuario", "pastaInstalacao", "tema", "fonte", "modo", "logoEscritorio", "nomeEscritorio",
                  "modeloPadrao"}
    novo = {k: v for k, v in (b or {}).items() if k in permitidos}
    if "urlPjecalc" in novo:
        u = urllib.parse.urlparse(novo["urlPjecalc"])
        if u.hostname not in ("127.0.0.1", "localhost") or u.scheme != "http":
            raise ErroApi(400, "Por segurança, a interface só opera um PJe-Calc local (http://127.0.0.1:<porta>/pjecalc/).")
        if not novo["urlPjecalc"].endswith("/"):
            novo["urlPjecalc"] += "/"
    if "logoEscritorio" in novo and novo["logoEscritorio"] and not str(novo["logoEscritorio"]).startswith("data:image/"):
        raise ErroApi(400, "Logotipo inválido.")
    cfg = ARMAZ.salvar_config(novo)
    return {k: v for k, v in cfg.items() if k != "logoEscritorio"}


def rota_casos(_h, q, _b):
    itens = ARMAZ.listar()
    texto = (q.get("q") or "").lower()
    if texto:
        itens = [c for c in itens if texto in " ".join(str(c.get(k) or "") for k in
                                                         ("titulo", "cliente", "parteContraria", "processo", "responsavel",
                                                          "calculoPjecalc")).lower()
                 or any(texto in (e or "").lower() for e in c.get("etiquetas", []))]
    for chave in ("situacao", "responsavel"):
        if q.get(chave):
            itens = [c for c in itens if (c.get(chave) or "") == q[chave]]
    if q.get("etiqueta"):
        itens = [c for c in itens if q["etiqueta"] in c.get("etiquetas", [])]
    if q.get("favorito") == "1":
        itens = [c for c in itens if c.get("favorito")]
    return {"casos": itens}


def _obter_modelo(mod: dict) -> dict:
    if mod.get("origem") == "escritorio":
        return ARMAZ.obter_modelo(mod["id"], mod.get("versao"))
    m = next((x for x in _modelos_iniciais() if x["id"] == mod.get("id")), None)
    if not m:
        raise ErroApi(404, "Modelo não encontrado.")
    return m


def _padroes_automaticos() -> list[str]:
    """Padrões marcados para entrar em todo cálculo novo (ex.: honorários do escritório)."""
    return [p["id"] for p in ARMAZ.listar_padroes() if p.get("automatico")]


def rota_criar(_h, _q, b):
    b = b or {}
    rasc = rascunho_vazio()
    origem = {"tipo": "novo"}
    padroes_modelo: list[str] = []
    if b.get("modelo"):
        m = _obter_modelo(b["modelo"])
        for k, v in (m.get("rascunho") or {}).items():
            rasc[k] = json.loads(json.dumps(v))
        origem = {"tipo": "modelo", "modelo": m["id"], "versao": m.get("versao"), "nome": m.get("nome")}
        padroes_modelo = list(m.get("padroes") or [])
    pendentes = list(dict.fromkeys(padroes_modelo + _padroes_automaticos()))
    dados = {k: b.get(k) for k in ("titulo", "cliente", "parteContraria", "processo", "responsavel", "etiquetas") if b.get(k)}
    caso = ARMAZ.criar({**dados, "rascunho": rasc, "origem": origem, "padroesPendentes": pendentes}, _autor())
    return {"caso": caso, "estado": _estado_resultado(caso)}


def rota_caso(_h, _q, _b, cid):
    caso = ARMAZ.obter(cid)
    return {"caso": caso, "estado": _estado_resultado(caso)}


def rota_atualizar(_h, _q, b, cid):
    try:
        caso = ARMAZ.atualizar(cid, b or {}, _autor(), (b or {}).get("revisaoBase"))
    except ConflitoRevisao as e:
        raise ErroApi(409, str(e), {"revisaoAtual": e.revisao_atual})
    return {"caso": caso, "estado": _estado_resultado(caso)}


def rota_excluir(_h, _q, _b, cid):
    ARMAZ.excluir(cid)
    return {"ok": True, "mensagem": "Cálculo movido para a lixeira local (pasta dados/lixeira). O cálculo no PJe-Calc não foi alterado."}


def rota_duplicar(_h, _q, b, cid):
    novo = ARMAZ.duplicar(cid, _autor(), como_cenario=(b or {}).get("cenario", True), padroes_extras=_padroes_automaticos())
    return {"caso": novo, "estado": _estado_resultado(novo)}


def rota_conferir(_h, _q, _b, cid):
    caso = ARMAZ.obter(cid)
    avisos = conferencia.conferir(caso["rascunho"])
    vinc = caso.get("pjecalc") or {}
    oficiais = vinc.get("pendencias") or []
    return {"avisos": avisos, "pendenciasPjecalc": oficiais,
            "pendenciasAtuais": vinc.get("gravadoRevisao") == caso["revisao"], "estado": _estado_resultado(caso)}


def rota_gravar(_h, _q, _b, cid):
    caso = ARMAZ.obter(cid)
    bloqueios = [a for a in conferencia.conferir(caso["rascunho"]) if a["nivel"] == "impeditivo"]
    if bloqueios:
        return {"ok": False, "etapa": "conferencia", "avisos": bloqueios, "passos": []}
    r = sincronizar.gravar(caso, _url(), ARMAZ, _autor())
    caso = ARMAZ.obter(cid)
    return {**r, "caso": caso, "estado": _estado_resultado(caso)}


def rota_executar(_h, _q, _b, cid):
    caso = ARMAZ.obter(cid)
    bloqueios = [a for a in conferencia.conferir(caso["rascunho"]) if a["nivel"] == "impeditivo"]
    if bloqueios:
        return {"ok": False, "etapa": "conferencia", "avisos": bloqueios, "passos": []}
    r = sincronizar.executar(caso, _url(), ARMAZ, _autor())
    caso = ARMAZ.obter(cid)
    return {**r, "caso": caso, "estado": _estado_resultado(caso)}


def rota_auditoria(_h, _q, _b, cid):
    return {"eventos": ARMAZ.auditoria(cid)[::-1]}


def rota_revisao(_h, _q, _b, cid, n):
    return {"rascunho": ARMAZ.revisao(cid, int(n))}


def rota_resultado(_h, _q, _b, cid, eid):
    caso = ARMAZ.obter(cid)
    return {"execucao": _execucao(caso, eid), "resultado": _resultado(cid, eid), "estado": _estado_resultado(caso)}


def rota_arquivo(h, q, _b, cid, eid, nome):
    caso = ARMAZ.obter(cid)
    ex = _execucao(caso, eid)
    if nome not in ("relatorio.html", "relatorio.pdf", "calculo.pjc"):
        raise ErroApi(404, "Arquivo desconhecido.")
    caminho = os.path.join(ARMAZ.pasta_execucao(cid, eid), nome)
    if not os.path.exists(caminho):
        raise ErroApi(404, "Arquivo não gerado nesta execução.")
    with open(caminho, "rb") as fh:
        corpo = fh.read()
    tipos = {"relatorio.html": "text/html; charset=utf-8", "relatorio.pdf": "application/pdf",
             "calculo.pjc": "application/zip"}
    baixar = q.get("baixar") == "1" or nome == "calculo.pjc"
    nome_saida = ex["arquivos"].get("pjcNomeOriginal") if nome == "calculo.pjc" else f"pjecalc_{ex['calculoId']}_{nome}"
    return Binario(corpo, tipos[nome], nome_saida if baixar else None, sandbox=nome.endswith(".html"))


def rota_planilha(_h, _q, _b, cid, eid):
    caso = ARMAZ.obter(cid)
    ex = _execucao(caso, eid)
    corpo = exportacao.planilha_csv(caso, ex, _resultado(cid, eid))
    return Binario(corpo, "text/csv; charset=utf-8", f"conferencia_calculo_{ex['calculoId']}_{eid}.csv")


def rota_resumo_complementar(_h, _q, _b, cid, eid):
    caso = ARMAZ.obter(cid)
    ex = _execucao(caso, eid)
    corpo = exportacao.resumo_complementar(caso, ex, _resultado(cid, eid), ARMAZ.config()).encode("utf-8")
    return Binario(corpo, "text/html; charset=utf-8", None, sandbox=True)


# Quadro de critérios por cálculo. Ler do PJe-Calc abre o painel de cada verba (vários segundos, com o PJe-Calc
# ocupado para o resto do Studio); o quadro só muda com uma nova gravação ou com um botão acionado numa tela
# oficial do cálculo, que entram na chave. ?forcar=1 lê de novo.
_criterios: dict[str, tuple] = {}


def rota_parametros_verbas(_h, q, _b, cid):
    """Quadro de critérios lido do PJe-Calc: parâmetros e fórmula de cada verba gravada."""
    caso = ARMAZ.obter(cid)
    vinc = caso.get("pjecalc") or {}
    if not vinc.get("calculoId"):
        raise ErroApi(409, "Grave o cálculo no PJe-Calc para ler os critérios aplicados pelo motor.")
    chave = (_url(), vinc["calculoId"], vinc.get("gravadoRevisao"), vinc.get("abertoNoOriginalEm"))
    with sincronizar.motor_lock:
        guardado = _criterios.get(cid)
        if guardado and guardado[0] == chave and q.get("forcar") != "1":
            lido = guardado[1]
        else:
            m = PJeCalc(_url())
            r = m.abrir_calculo(vinc["calculoId"])
            if not r.ok:
                raise ErroApi(502, "Não foi possível abrir o cálculo no PJe-Calc.", r.to_dict())
            verbas = m.listar_verbas()
            lido = {"verbas": [m.parametros_verba(v["linha"]) | {"reflexos": v["reflexos"]} for v in verbas],
                    "fgts": m.ler_fgts(), "atualizacao": m.ler_atualizacao()}
            _criterios[cid] = (chave, lido)
    return {**lido, "lidoNaRevisao": vinc.get("gravadoRevisao"), "revisaoAtual": caso["revisao"]}


def _abrir_vinculado(caso: dict) -> PJeCalc:
    vinc = caso.get("pjecalc") or {}
    if not vinc.get("calculoId"):
        raise ErroApi(409, "Grave o cálculo no PJe-Calc para ler os dados gerados pelo motor.")
    m = PJeCalc(_url())
    r = m.abrir_calculo(vinc["calculoId"])
    if not r.ok:
        raise ErroApi(502, "Não foi possível abrir o cálculo no PJe-Calc.", r.to_dict())
    return m


def rota_ocorrencias_verba(_h, q, _b, cid):
    """Grade "Ocorrências da Verba" gerada pelo PJe-Calc para a verba informada (somente leitura)."""
    caso = ARMAZ.obter(cid)
    nome = q.get("verba") or ""
    with sincronizar.motor_lock:
        m = _abrir_vinculado(caso)
        alvo = next((v for v in m.listar_verbas() if fold(v["nome"]) == fold(nome)), None)
        if not alvo:
            raise ErroApi(404, f"Verba '{nome}' não encontrada no cálculo gravado. Grave o cálculo e tente novamente.")
        dados = m.ler_ocorrencias(alvo["linha"])
    return {"verba": alvo["nome"], "ocorrencias": dados["ocorrencias"],
            "lidoNaRevisao": (caso.get("pjecalc") or {}).get("gravadoRevisao"), "revisaoAtual": caso["revisao"]}


# Leituras do PJe-Calc que não mudam enquanto a mesma instalação está em execução. Preenchidas sob
# sincronizar.motor_lock (duas requisições simultâneas não leem nem gravam a mesma chave duas vezes).
_cache: dict[str, object] = {}


def _em_cache(chave: str, ler):
    with sincronizar.motor_lock:
        if chave in _cache:
            return _cache[chave]
        valor = ler()
        if valor:  # lista vazia (tela ainda sem dados) é relida na próxima consulta
            _cache[chave] = valor
        return valor


def rota_assuntos_cnj(_h, _q, _b, cid):
    """Tabela de assuntos CNJ do modal oficial (só aparece com um cálculo aberto na tela Verbas)."""
    caso = ARMAZ.obter(cid)
    return {"assuntos": _em_cache("assuntos:" + _url(), lambda: _abrir_vinculado(caso).assuntos_cnj())}


# ------------------------------------------------------------------ telas do PJe-Calc no visual do Studio
SESSOES_TELA = Sessoes()
MENU_RE = re.compile(r"li_[a-z_]+")


def _operar_tela(fn):
    """Executa uma operação numa tela oficial; erros do PJe-Calc viram mensagens para a interface."""
    with sincronizar.motor_lock:
        try:
            return fn()
        except JsfError as e:
            raise ErroApi(502, f"O PJe-Calc não concluiu a operação: {e}") from None
        except OSError as e:
            raise ErroApi(502, f"O PJe-Calc não respondeu em {_url()}. Abra o PJe-Calc e tente de novo. ({e})") from None


def rota_abrir_tela(_h, _q, b):
    b = b or {}
    menu = str(b.get("menu") or "")
    if not MENU_RE.fullmatch(menu):
        raise ErroApi(400, "Tela desconhecida.")
    calculo = None
    if b.get("caso"):
        calculo = (ARMAZ.obter(b["caso"]).get("pjecalc") or {}).get("calculoId")
        if not calculo:
            raise ErroApi(409, "Envie o cálculo ao PJe-Calc uma vez antes de abrir esta tela.")
    sessao = SessaoTela(_url(), calculo, menu)
    sessao.caso = b.get("caso")
    descricao = _operar_tela(sessao.abrir)
    SESSOES_TELA.nova(sessao)
    return {"token": sessao.token, "tela": descricao}


def _registrar_alteracao(sessao: SessaoTela):
    """Botão acionado numa tela de um cálculo: o resultado anterior pode não refletir mais o que está no PJe-Calc."""
    if sessao.caso:
        caso = ARMAZ.obter(sessao.caso)
        caso.setdefault("pjecalc", {})["abertoNoOriginalEm"] = agora()
        ARMAZ.salvar_interno(caso, _autor(), "tela_pjecalc", [{"campo": "telaPjecalc", "de": None, "para": sessao.menu}])


def rota_tela_alterar(_h, _q, b, token):
    s, b = SESSOES_TELA.obter(token), b or {}
    return {"tela": _operar_tela(lambda: s.alterar(b.get("valores") or {}, b.get("evento")))}


def rota_tela_acao(_h, _q, b, token):
    s, b = SESSOES_TELA.obter(token), b or {}
    if not b.get("acao"):
        raise ErroApi(400, "Ação não informada.")
    tela = _operar_tela(lambda: s.acionar(str(b["acao"]), b.get("valores") or {}))
    if not str(b["acao"]).startswith(("aba:", "pag:")):  # trocar de aba ou de página não altera o cálculo
        _registrar_alteracao(s)
    return {"tela": tela}


def rota_tela_upload(_h, q, corpo, token):
    s = SESSOES_TELA.obter(token)
    if not q.get("campo"):
        raise ErroApi(400, "Campo do arquivo não informado.")
    return {"tela": _operar_tela(lambda: s.enviar_arquivo(q["campo"], q.get("nome") or "arquivo", corpo, {}))}


def rota_tela_download(_h, _q, _b, token):
    s = SESSOES_TELA.obter(token)
    if s.arquivo is None:
        raise ErroApi(404, "Nenhum arquivo gerado por esta tela.")
    return Binario(s.arquivo["corpo"], s.arquivo["tipo"], s.arquivo["nome"])


# ------------------------------------------------------------------ padrões do escritório (ponte/padroes.py)
def rota_padroes(_h, q, _b):
    return {"padroes": ARMAZ.listar_padroes(q.get("menu"))}


def rota_salvar_padrao(_h, _q, b, pid=None):
    b = b or {}
    dados = {}
    if "nome" in b or not pid:
        if not (b.get("nome") or "").strip():
            raise ErroApi(400, "Dê um nome ao padrão.")
        dados["nome"] = b["nome"].strip()
    for k in ("descricao", "funcao"):
        if k in b:
            dados[k] = str(b[k] or "")
    if "automatico" in b:
        dados["automatico"] = bool(b["automatico"])
    if "passos" in b or not pid:
        passos = padroes.validar_passos(b.get("passos"))
        if not passos:
            raise ErroApi(400, "O padrão não tem nenhum campo ou botão para repetir.")
        dados["passos"] = passos
    if not pid:
        if not MENU_RE.fullmatch(str(b.get("menu") or "")):
            raise ErroApi(400, "Função do PJe-Calc desconhecida.")
        dados["menu"] = b["menu"]
    return {"padrao": ARMAZ.salvar_padrao(dados, _autor(), pid)}


def rota_excluir_padrao(_h, _q, _b, pid):
    ARMAZ.excluir_padrao(pid)
    return {"ok": True}


def rota_tela_aplicar_padrao(_h, _q, _b, token, pid):
    """Aplica um padrão na tela já aberta: a pessoa vê o resultado e pode ajustar antes de salvar."""
    s, padrao = SESSOES_TELA.obter(token), ARMAZ.obter_padrao(pid)
    if padrao["menu"] != s.menu:
        raise ErroApi(400, "Este padrão é de outra função do PJe-Calc.")
    r = _operar_tela(lambda: padroes.aplicar(s, padrao["passos"]))
    if s.caso and any(p["tipo"] == "acao" for p in padrao["passos"]):
        _registrar_alteracao(s)
    return r


def rota_aplicar_padroes_caso(_h, _q, b, cid):
    ids = [str(i) for i in (b or {}).get("padroes") or []]
    if not ids:
        raise ErroApi(400, "Escolha ao menos um padrão.")
    r = sincronizar.aplicar_padroes(ARMAZ.obter(cid), ids, _url(), ARMAZ, _autor())
    caso = ARMAZ.obter(cid)
    return {**r, "caso": caso, "estado": _estado_resultado(caso)}


def rota_tela_fechar(_h, _q, _b, token):
    SESSOES_TELA.fechar(token)
    return {"ok": True}


def rota_calculos_do_pjecalc(_h, q, _b):
    """Cálculos existentes no PJe-Calc (tela Buscar), indicando os que já estão ligados a um cálculo do Studio.

    Sem filtro, o PJe-Calc devolve só a primeira página; ?calculo=, ?reclamante= e ?numero= (processo) filtram
    pela própria busca dele."""
    ligados = {}
    for c in ARMAZ.listar():
        if c.get("calculoPjecalc"):
            ligados[str(c["calculoPjecalc"])] = {"id": c["id"], "titulo": c.get("titulo")}
    filtros = {k: q[k].strip() for k in ("calculo", "reclamante", "numero") if (q.get(k) or "").strip()}
    with sincronizar.motor_lock:
        itens = PJeCalc(_url()).listar_calculos(filtros)
    for i in itens:
        i["studio"] = ligados.get(str(i.get("calculo")))
    return {"calculos": itens}


def rota_trazer_do_pjecalc(_h, _q, b, numero):
    """Liga um cálculo que já existe no PJe-Calc a um novo cálculo do Studio, sem duplicá-lo no PJe-Calc."""
    return sincronizar.trazer_do_pjecalc(numero, _url(), ARMAZ, _autor())


def rota_importar_pjc(h, q, corpo):
    nome = q.get("nome") or "calculo.pjc"
    if not corpo or corpo[:2] != b"PK":
        raise ErroApi(400, "O arquivo não parece um .PJC válido (esperado um pacote ZIP gerado pelo PJe-Calc).")
    return sincronizar.importar_pjc(corpo, nome, _url(), ARMAZ, _autor())


def rota_ler_planilha(h, q, corpo):
    try:
        return planilha.ler(corpo, q.get("nome") or "dados.csv")
    except ValueError as e:
        raise ErroApi(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise ErroApi(400, f"Não foi possível ler a planilha: {e}")


def _comparar_resultados(ra: dict, rb: dict) -> dict:
    def mapa(itens, chave="total"):
        return {i["descricao"]: i.get(chave) or i.get("valor") for i in itens if i.get("descricao")}
    saida = {}
    for secao, chave in (("verbas", "total"), ("creditos_descontos", "valor"), ("debitos_reclamado", "valor")):
        a, b = mapa(ra["relatorio"].get(secao, []), chave), mapa(rb["relatorio"].get(secao, []), chave)
        linhas = []
        for nome in list(dict.fromkeys(list(a) + list(b))):
            da, db = decimal_br(a.get(nome)), decimal_br(b.get(nome))
            linhas.append({"descricao": nome, "a": a.get(nome), "b": b.get(nome),
                           "diferenca": (moeda_br(str(db - da)) if da is not None and db is not None else None)})
        saida[secao] = linhas
    saida["ocorrencias"] = comparar_pjc(ra["pjc"], rb["pjc"])
    return saida


def rota_comparar(_h, q, _b):
    if not q.get("a") or not q.get("b"):
        raise ErroApi(400, "Escolha os dois cenários a comparar.")
    a, b = ARMAZ.obter(q["a"]), ARMAZ.obter(q["b"])
    entradas = diferencas(a["rascunho"], b["rascunho"])
    res = {"entradas": entradas, "a": {"id": a["id"], "titulo": a["titulo"], "revisao": a["revisao"]},
           "b": {"id": b["id"], "titulo": b["titulo"], "revisao": b["revisao"]}}
    ea = a["execucoes"][-1] if a.get("execucoes") else None
    eb = b["execucoes"][-1] if b.get("execucoes") else None
    if ea and eb:
        res["motor"] = {"a": {k: ea.get(k) for k in ("versaoMotor", "buildMotor", "em", "revisaoEntradas", "rodape")},
                        "b": {k: eb.get(k) for k in ("versaoMotor", "buildMotor", "em", "revisaoEntradas", "rodape")},
                        "versaoDiferente": ea.get("versaoMotor") != eb.get("versaoMotor"),
                        "tabelasDiferentes": (ea.get("tabelas") or "") != (eb.get("tabelas") or "")}
        res["resultados"] = _comparar_resultados(_resultado(a["id"], ea["id"]), _resultado(b["id"], eb["id"]))
        res["desatualizado"] = {"a": ea["revisaoEntradas"] != a["revisao"], "b": eb["revisaoEntradas"] != b["revisao"]}
    else:
        res["resultados"] = None
        res["motivo"] = "Execute os dois cenários no PJe-Calc para comparar resultados."
    return res


def _modelos_iniciais() -> list[dict]:
    with open(os.path.join(WEB, "modelos-iniciais.json"), encoding="utf-8") as fh:
        return json.load(fh)


def rota_modelos(_h, _q, _b):
    iniciais = [{**{k: m.get(k) for k in ("id", "nome", "descricao", "premissas", "versao", "revisadoEm", "fontes",
                                           "categoria", "suporte")}, "origem": "inicial"} for m in _modelos_iniciais()]
    return {"modelos": iniciais + ARMAZ.listar_modelos()}


def rota_modelo(_h, q, _b, mid):
    if q.get("origem") == "escritorio":
        return {"modelo": ARMAZ.obter_modelo(mid, q.get("versao")), "historico": ARMAZ.historico_modelo(mid)}
    m = next((x for x in _modelos_iniciais() if x["id"] == mid), None)
    if not m:
        raise ErroApi(404, "Modelo não encontrado.")
    return {"modelo": m, "historico": []}


CATEGORIAS_MODELO = ("Liquidação de sentença", "Execução", "Atualização de cálculo", "Petição inicial", "Acordo",
                      "Rescisórias", "Outros")


def rota_salvar_modelo(_h, _q, b):
    """Grava uma versão de um modelo do escritório (a partir do rascunho de um cálculo, sem dados pessoais)."""
    b = b or {}
    caso = ARMAZ.obter(b["casoId"]) if b.get("casoId") else None
    if caso:
        b["rascunho"] = caso["rascunho"]
    if not (b.get("nome") or "").strip():
        raise ErroApi(400, "Informe o nome do modelo.")
    if b.get("categoria") and b["categoria"] not in CATEGORIAS_MODELO:
        raise ErroApi(400, "Categoria de modelo desconhecida.")
    existentes = {p["id"] for p in ARMAZ.listar_padroes()}
    b["padroes"] = [p for p in b.get("padroes") or [] if p in existentes]
    mid = b.get("id") or ((caso or {}).get("edicaoModelo") or {}).get("id")
    reg = ARMAZ.salvar_modelo({k: b.get(k) for k in ("nome", "descricao", "premissas", "nota", "rascunho", "categoria", "padroes")},
                              _autor(), mid)
    if caso and caso.get("edicaoModelo") is not None:  # próximas gravações do mesmo cálculo viram novas versões
        caso["edicaoModelo"] = {**caso["edicaoModelo"], "id": reg["id"], "nome": reg["nome"], "categoria": reg.get("categoria"),
                                "padroes": reg["padroes"], "descricao": reg.get("descricao")}
        ARMAZ.salvar_interno(caso, _autor(), "modelo_salvo", [{"campo": "modelo", "de": None, "para": reg["id"]}])
    return {"modelo": reg}


def rota_editar_modelo(_h, _q, b):
    """Abre um modelo para edição como um cálculo do Studio (todas as etapas, mesmos formulários).

    {"modelo": {"id", "origem"}} edita um modelo do escritório (ou cria um novo a partir de um modelo inicial);
    {"caso": id} cria um modelo a partir de um cálculo existente; sem nenhum dos dois, um modelo em branco.
    Dados pessoais (partes, processo, documentos) nunca entram no modelo (ver armazenamento.sem_dados_pessoais).
    """
    b = b or {}
    rasc, info = rascunho_vazio(), {"id": None, "nome": (b.get("nome") or "").strip() or "Novo modelo",
                                    "categoria": b.get("categoria") or "Liquidação de sentença", "descricao": "", "padroes": []}
    if b.get("modelo"):
        m = _obter_modelo(b["modelo"])
        rasc.update(json.loads(json.dumps(m.get("rascunho") or {})))
        info.update({"nome": m["nome"] if b["modelo"].get("origem") == "escritorio" else f"{m['nome']} (do escritório)",
                     "categoria": m.get("categoria") if m.get("categoria") in CATEGORIAS_MODELO else info["categoria"],
                     "descricao": m.get("descricao") or "", "premissas": m.get("premissas") or [],
                     "padroes": list(m.get("padroes") or []),
                     "id": m["id"] if b["modelo"].get("origem") == "escritorio" else None})
    elif b.get("caso"):
        rasc.update(sem_dados_pessoais(ARMAZ.obter(b["caso"])["rascunho"]))
    caso = ARMAZ.criar({"titulo": f"Modelo: {info['nome']}", "etiquetas": ["modelo"], "rascunho": rasc,
                        "origem": {"tipo": "edicao_modelo", "modelo": info["id"]}, "edicaoModelo": info}, _autor())
    return {"caso": caso, "estado": _estado_resultado(caso)}


def rota_opcoes(_h, _q, _b):
    return {"versaoCatalogo": catalogo.VERSAO_CATALOGO, "expressas": catalogo.VERBAS_EXPRESSAS,
            "estados": catalogo.ESTADOS, "opcoes": catalogo.OPCOES}


def rota_municipios(_h, q, _b):
    uf = (q.get("estado") or "").upper()
    if uf not in catalogo.ESTADOS:
        raise ErroApi(400, "UF inválida.")
    lista = _em_cache(f"municipios:{_url()}:{uf}", lambda: PJeCalc(_url(), timeout=60).municipios(uf))
    return {"estado": uf, "municipios": lista}


def rota_ajuda_oficial(_h, _q, _b):
    pasta = ARMAZ.config().get("pastaInstalacao")
    if not pasta:
        return {"itens": [], "motivo": "Informe a pasta de instalação do PJe-Calc em Configurações para exibir os textos de ajuda oficiais."}
    try:
        return {"itens": _em_cache("ajuda:" + pasta, lambda: extrair(localizar_webapp(pasta)))}
    except OSError as e:
        return {"itens": [], "motivo": str(e)}


def rota_backups(_h, _q, _b):
    return {"backups": ARMAZ.listar_backups()}


def rota_criar_backup(_h, _q, b):
    return ARMAZ.criar_backup((b or {}).get("motivo") or "manual")


def rota_verificar_backup(_h, _q, _b, nome):
    return ARMAZ.verificar_backup(nome)


def rota_restaurar_backup(_h, _q, _b, nome):
    return ARMAZ.restaurar_backup(nome)


# ---------------------------------------------------------------------------------------------
# Assistente Claude (MCP). O protocolo é atendido aqui, em POST /mcp, protegido por uma chave guardada na
# pasta de dados; as pontes locais (extensão do Claude Desktop e mcp_studio.py) leem o endereço e a chave
# do arquivo de conexão que o Studio escreve ao iniciar e só repassam as mensagens.
EXTENSAO = os.path.join(RAIZ, "extensao")


def _chave_assistente(nova: bool = False) -> str:
    caminho = os.path.join(ARMAZ.pasta, "assistente.json")
    try:
        with open(caminho, encoding="utf-8") as fh:
            chave = "" if nova else json.load(fh).get("chave", "")
    except (OSError, ValueError):
        chave = ""
    if len(chave) < 32:
        chave = secrets.token_urlsafe(32)
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump({"chave": chave}, fh)
    return chave


def _arquivo_conexao() -> str:
    return os.environ.get("PJECALC_STUDIO_CONEXAO") or os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PJeCalcStudio", "conexao.json")


def _escrever_conexao() -> None:
    """Endereço, chave e lista de ferramentas para as pontes (a lista permite ao Claude conhecê-las com o Studio fechado)."""
    destino = _arquivo_conexao()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"url": f"http://127.0.0.1:{PORTA}/mcp", "chave": _chave_assistente(), "versao": VERSAO_APP,
                   "instrucoes": assistente.INSTRUCOES, "ferramentas": assistente.lista_ferramentas(), "atualizadoEm": agora()},
                  fh, ensure_ascii=False)
    os.replace(tmp, destino)


def _conexao_aponta_para_mim(caminho: str) -> bool:
    try:
        with open(caminho, encoding="utf-8") as fh:
            c = json.load(fh)
        return c.get("url") == f"http://127.0.0.1:{PORTA}/mcp" and c.get("chave") == _chave_assistente()
    except (OSError, ValueError):
        return False


def _despachar_interno(metodo: str, caminho: str, corpo=None):
    """Chama uma rota da API em processo, com as mesmas regras da interface (usado pelas ferramentas do assistente)."""
    url = urllib.parse.urlparse(caminho)
    q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
    for m_rota, padrao, fn in ROTAS:
        m = re.fullmatch(padrao, url.path)
        if m_rota != metodo or not m or fn in BINARIAS:
            continue
        try:
            return fn(None, q, corpo, *m.groups())
        except ErroApi as e:
            raise assistente.ErroStudio(e.mensagem, e.status) from None
        except KeyError:
            raise assistente.ErroStudio("Registro não encontrado.", 404) from None
        except ValueError as e:
            raise assistente.ErroStudio(f"Dados inválidos: {e}", 400) from None
    raise assistente.ErroStudio("Rota inexistente.", 404)


def _pacote_extensao() -> bytes:
    """Extensão do Claude Desktop (.mcpb): a pasta extensao/ compactada, com a versão do Studio no manifesto."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _, arqs in os.walk(EXTENSAO):
            for a in sorted(arqs):
                caminho = os.path.join(raiz, a)
                rel = os.path.relpath(caminho, EXTENSAO).replace(os.sep, "/")
                if rel == "manifest.json":
                    with open(caminho, encoding="utf-8") as fh:
                        man = json.load(fh)
                    man["version"] = VERSAO_APP
                    man["tools"] = [{"name": t["name"], "description": t["description"]} for t in assistente.lista_ferramentas()]
                    z.writestr(rel, json.dumps(man, ensure_ascii=False, indent=2))
                else:
                    z.write(caminho, rel)
    return buf.getvalue()


def _claude_desktop_instalado() -> bool:
    local = os.environ.get("LOCALAPPDATA", "")
    locais = [os.path.join(local, "AnthropicClaude"), os.path.join(os.environ.get("APPDATA", ""), "Claude")]
    pacotes = os.path.join(local, "Packages")
    if local and os.path.isdir(pacotes):
        locais += [os.path.join(pacotes, d) for d in os.listdir(pacotes) if d.startswith("Claude_")]
    return any(os.path.isdir(x) for x in locais if x)


def _comando_python() -> list[str]:
    portatil = os.path.join(RAIZ, "python", "python.exe")
    return [portatil, "-I"] if os.path.exists(portatil) else ["py", "-3", "-I"]


def rota_claude(_h, _q, _b):
    conexao = _arquivo_conexao()
    cmd = " ".join(f'"{x}"' if " " in x else x for x in _comando_python() + [os.path.join(RAIZ, "mcp_studio.py")])
    return {"endpoint": f"http://127.0.0.1:{PORTA}/mcp", "ferramentas": len(assistente.lista_ferramentas()),
            "conexao": conexao, "conexaoAtual": _conexao_aponta_para_mim(conexao),
            "claudeDesktop": _claude_desktop_instalado(), "windows": os.name == "nt",
            "comandoClaudeCode": f"claude mcp add pjecalc-studio -- {cmd}",
            "comandoCodex": f"codex mcp add pjecalc_studio -- {cmd}"}


def rota_claude_extensao(_h, _q, _b):
    return Binario(_pacote_extensao(), "application/zip", "PJeCalcStudio.mcpb")


def rota_claude_instalar(_h, _q, _b):
    """Abre a extensão no Claude Desktop (a janela de instalação dele pede a confirmação do usuário)."""
    if os.name != "nt":
        raise ErroApi(400, "A instalação automática é só para Windows. Baixe a extensão e dê dois cliques nela.")
    _escrever_conexao()
    destino = os.path.join(tempfile.gettempdir(), "PJeCalcStudio.mcpb")
    with open(destino, "wb") as fh:
        fh.write(_pacote_extensao())
    try:
        os.startfile(destino)  # abre com o programa associado ao .mcpb (Claude Desktop)
    except OSError as e:
        raise ErroApi(409, "O Windows não sabe abrir arquivos .mcpb: o Claude Desktop está instalado e atualizado? "
                      f"Baixe a extensão e arraste o arquivo para a janela do Claude. ({e})") from None
    return {"ok": True, "mensagem": "A janela de instalação do Claude Desktop foi aberta. Confirme a instalação nela."}


def rota_claude_conectar(_h, _q, _b):
    """Faz o Claude falar com este Studio (útil quando há mais de um Studio aberto no computador)."""
    _escrever_conexao()
    return {"ok": True, "mensagem": "O Claude agora fala com este Studio."}


def rota_claude_nova_chave(_h, _q, _b):
    _chave_assistente(nova=True)
    _escrever_conexao()
    return {"ok": True, "mensagem": "Chave nova criada. Quem tinha a chave antiga perde o acesso; a extensão instalada lê a nova sozinha."}


ROTAS = [
    ("GET", r"/api/estado", rota_estado),
    ("GET", r"/api/diagnostico", rota_diagnostico),
    ("PUT", r"/api/config", rota_config),
    ("GET", r"/api/casos", rota_casos),
    ("POST", r"/api/casos", rota_criar),
    ("GET", r"/api/casos/([a-z0-9_]+)", rota_caso),
    ("PUT", r"/api/casos/([a-z0-9_]+)", rota_atualizar),
    ("DELETE", r"/api/casos/([a-z0-9_]+)", rota_excluir),
    ("POST", r"/api/casos/([a-z0-9_]+)/duplicar", rota_duplicar),
    ("GET", r"/api/casos/([a-z0-9_]+)/conferir", rota_conferir),
    ("POST", r"/api/casos/([a-z0-9_]+)/gravar", rota_gravar),
    ("POST", r"/api/casos/([a-z0-9_]+)/executar", rota_executar),
    ("GET", r"/api/casos/([a-z0-9_]+)/auditoria", rota_auditoria),
    ("GET", r"/api/casos/([a-z0-9_]+)/revisoes/(\d+)", rota_revisao),
    ("GET", r"/api/casos/([a-z0-9_]+)/criterios", rota_parametros_verbas),
    ("GET", r"/api/casos/([a-z0-9_]+)/ocorrencias", rota_ocorrencias_verba),
    ("GET", r"/api/casos/([a-z0-9_]+)/assuntos-cnj", rota_assuntos_cnj),
    ("GET", r"/api/pjecalc/calculos", rota_calculos_do_pjecalc),
    ("POST", r"/api/pjecalc/calculos/(\d+)/trazer", rota_trazer_do_pjecalc),
    ("GET", r"/api/casos/([a-z0-9_]+)/execucoes/([a-z0-9_]+)", rota_resultado),
    ("GET", r"/api/casos/([a-z0-9_]+)/execucoes/([a-z0-9_]+)/arquivo/([a-z.]+)", rota_arquivo),
    ("GET", r"/api/casos/([a-z0-9_]+)/execucoes/([a-z0-9_]+)/planilha\.csv", rota_planilha),
    ("GET", r"/api/casos/([a-z0-9_]+)/execucoes/([a-z0-9_]+)/resumo-complementar", rota_resumo_complementar),
    ("POST", r"/api/telas", rota_abrir_tela),
    ("POST", r"/api/telas/([\w-]+)/alterar", rota_tela_alterar),
    ("POST", r"/api/telas/([\w-]+)/acao", rota_tela_acao),
    ("POST", r"/api/telas/([\w-]+)/arquivo", rota_tela_upload),
    ("GET", r"/api/telas/([\w-]+)/download", rota_tela_download),
    ("DELETE", r"/api/telas/([\w-]+)", rota_tela_fechar),
    ("POST", r"/api/telas/([\w-]+)/padroes/(p[0-9a-z_]+)", rota_tela_aplicar_padrao),
    ("GET", r"/api/padroes", rota_padroes),
    ("POST", r"/api/padroes", rota_salvar_padrao),
    ("PUT", r"/api/padroes/(p[0-9a-z_]+)", rota_salvar_padrao),
    ("DELETE", r"/api/padroes/(p[0-9a-z_]+)", rota_excluir_padrao),
    ("POST", r"/api/casos/([a-z0-9_]+)/padroes", rota_aplicar_padroes_caso),
    ("POST", r"/api/modelos/editar", rota_editar_modelo),
    ("POST", r"/api/importar-pjc", rota_importar_pjc),
    ("POST", r"/api/ler-planilha", rota_ler_planilha),
    ("GET", r"/api/comparar", rota_comparar),
    ("GET", r"/api/modelos", rota_modelos),
    ("POST", r"/api/modelos", rota_salvar_modelo),
    ("GET", r"/api/modelos/([a-z0-9_\-]+)", rota_modelo),
    ("GET", r"/api/opcoes", rota_opcoes),
    ("GET", r"/api/municipios", rota_municipios),
    ("GET", r"/api/ajuda-oficial", rota_ajuda_oficial),
    ("GET", r"/api/backups", rota_backups),
    ("POST", r"/api/backups", rota_criar_backup),
    ("POST", r"/api/backups/(backup_[\d_]+\.zip)/verificar", rota_verificar_backup),
    ("POST", r"/api/backups/(backup_[\d_]+\.zip)/restaurar", rota_restaurar_backup),
    ("GET", r"/api/atualizacao", rota_atualizacao),
    ("POST", r"/api/atualizacao/verificar", rota_atualizacao_verificar),
    ("POST", r"/api/atualizacao/instalar", rota_atualizacao_instalar),
    ("GET", r"/api/claude", rota_claude),
    ("GET", r"/api/claude/extensao\.mcpb", rota_claude_extensao),
    ("POST", r"/api/claude/instalar-desktop", rota_claude_instalar),
    ("POST", r"/api/claude/conectar", rota_claude_conectar),
    ("POST", r"/api/claude/nova-chave", rota_claude_nova_chave),
]
BINARIAS = {rota_importar_pjc, rota_ler_planilha, rota_tela_upload}
assistente.configurar(_despachar_interno, VERSAO_APP)


class Servidor(ThreadingHTTPServer):
    # HTTPServer liga SO_REUSEADDR; no Windows isso deixa uma segunda cópia do Studio ocupar a mesma porta em
    # silêncio (o navegador continua falando com a primeira). Sem ele, a segunda cópia falha com "porta ocupada".
    allow_reuse_address = os.name != "nt"

    def handle_error(self, request, client_address):
        # o navegador fechou a conexão antes da resposta (trocou de tela, recarregou): não é falha do Studio
        if isinstance(sys.exc_info()[1], (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class Binario:
    def __init__(self, corpo: bytes, tipo: str, nome_download: str | None, sandbox: bool = False):
        self.corpo, self.tipo, self.nome, self.sandbox = corpo, tipo, nome_download, sandbox


class Handler(BaseHTTPRequestHandler):
    server_version = "PJeCalcStudio/" + VERSAO_APP

    def log_message(self, fmt, *args):  # registros técnicos sem dados pessoais (somente método, rota e status)
        rota = urllib.parse.urlparse(self.path).path
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.command} {rota} {args[1] if len(args) > 1 else ''}\n")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{PORTA}", f"localhost:{PORTA}")

    def _enviar(self, status: int, corpo: bytes, tipo: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, status: int, obj):
        self._enviar(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _ler_corpo(self) -> bytes:
        try:
            tam = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ErroApi(400, "Cabeçalho Content-Length inválido.") from None
        if tam < 0:
            raise ErroApi(400, "Cabeçalho Content-Length inválido.")
        if tam > LIMITE_CORPO:
            raise ErroApi(413, "Arquivo grande demais.")
        return self.rfile.read(tam) if tam else b""

    def _api(self):
        if not self._host_ok():
            return self._json(403, {"erro": "Host não permitido."})
        if self.command != "GET" and self.headers.get("X-PJeCalc-Studio") != "1":
            return self._json(403, {"erro": "Requisição sem o cabeçalho da aplicação."})
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        for metodo, padrao, fn in ROTAS:
            if metodo != self.command:
                continue
            m = re.fullmatch(padrao, url.path)
            if not m:
                continue
            try:
                bruto = self._ler_corpo()
                if fn in BINARIAS:
                    r = fn(self, q, bruto, *m.groups())
                else:
                    try:
                        corpo = json.loads(bruto.decode("utf-8")) if bruto else None
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        raise ErroApi(400, "Corpo da requisição não é um JSON válido.") from None
                    r = fn(self, q, corpo, *m.groups())
            except ErroApi as e:
                return self._json(e.status, {"erro": e.mensagem, **e.extra})
            except KeyError:
                return self._json(404, {"erro": "Registro não encontrado."})
            except ValueError as e:  # identificador, situação ou nome de arquivo recusado pelo armazenamento
                return self._json(400, {"erro": f"Dados inválidos: {e}"})
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                return self._json(500, {"erro": f"Falha interna: {type(e).__name__}: {e}"})
            if isinstance(r, Binario):
                extra = {}
                if r.nome:
                    extra["Content-Disposition"] = "attachment; filename*=UTF-8''" + urllib.parse.quote(r.nome)
                if r.sandbox:  # relatório oficial exibido sem scripts, isolado da aplicação
                    extra["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src data: 'self'; style-src 'unsafe-inline'"
                return self._enviar(200, r.corpo, r.tipo, extra)
            return self._json(200, r)
        return self._json(404, {"erro": "Rota inexistente."})

    def _estatico(self):
        if not self._host_ok():
            return self._enviar(403, b"Host nao permitido", "text/plain")
        caminho = urllib.parse.urlparse(self.path).path
        if caminho in ("/", ""):
            caminho = "/index.html"
        alvo = os.path.normpath(os.path.join(WEB, urllib.parse.unquote(caminho).lstrip("/")))
        if not dentro_de(WEB, alvo) or not os.path.isfile(alvo):
            alvo = os.path.join(WEB, "index.html")  # SPA: rotas internas carregam a aplicação
        tipo = mimetypes.guess_type(alvo)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        with open(alvo, "rb") as fh:
            corpo = fh.read()
        self._enviar(200, corpo, tipo, {
            "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                       "frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'"})

    # ---------------------------------------------------------------------------------------------
    # Arquivos estáticos do PJe-Calc (ex.: modelos de CSV "clique aqui para baixar um exemplo" das telas),
    # repassados sem alteração ao PJe-Calc local configurado; nada é interpretado nem gravado pelo Studio.
    def _original(self):
        if not self._host_ok():
            return self._enviar(403, b"Host nao permitido", "text/plain")
        destino = urllib.parse.urlparse(_url())
        caminho_base = destino.path.rstrip("/")  # normalmente /pjecalc
        if not (self.path == caminho_base or self.path.startswith(caminho_base + "/")):
            return self._enviar(404, b"", "text/plain")
        try:
            corpo = self._ler_corpo() or None
        except ErroApi as e:
            return self._enviar(e.status, e.mensagem.encode("utf-8"), "text/plain; charset=utf-8")
        cab = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "connection", "keep-alive", "proxy-connection", "te", "upgrade", "accept-encoding")}
        try:
            conn = http.client.HTTPConnection(destino.hostname, destino.port or 80, timeout=900)
            conn.request(self.command, self.path, body=corpo, headers=cab)
            resp = conn.getresponse()
            dados = resp.read()
        except OSError as e:
            msg = ("O PJe-Calc não respondeu em " + _url() + ". Abra o PJe-Calc pelo atalho oficial e tente de novo. (" + str(e) + ")")
            return self._enviar(502, msg.encode("utf-8"), "text/plain; charset=utf-8")
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            kl = k.lower()
            if kl in ("connection", "keep-alive", "transfer-encoding", "content-length", "x-frame-options"):
                continue
            if kl == "location":  # redirecionamentos absolutos voltam para a origem do Studio
                u = urllib.parse.urlparse(v)
                if u.netloc and u.hostname in ("127.0.0.1", "localhost") and u.port == destino.port:
                    v = urllib.parse.urlunparse(("", "", u.path, u.params, u.query, u.fragment))
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(dados)
        conn.close()

    def _mcp(self):
        """MCP (Streamable HTTP, respostas em JSON): só da própria máquina, com a chave do assistente e sem origem de site."""
        if not self._host_ok():
            return self._json(403, {"erro": "Host não permitido."})
        origem = self.headers.get("Origin")
        if origem and origem not in (f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}"):
            return self._json(403, {"erro": "Origem não permitida."})
        dado = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(dado.encode(), _chave_assistente().encode()):
            return self._json(401, {"erro": "Chave do assistente ausente ou inválida."})
        if self.command != "POST":
            return self._enviar(405, b"", "text/plain", {"Allow": "POST"})
        try:
            msg = json.loads(self._ler_corpo().decode("utf-8"))
        except (ErroApi, UnicodeDecodeError, ValueError):
            return self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido."}})
        resp = [r for r in map(assistente.responder, msg) if r] if isinstance(msg, list) else assistente.responder(msg)
        if not resp:  # só notificações
            return self._enviar(202, b"", "text/plain")
        return self._json(200, resp)

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path == "/mcp":
            return self._mcp()
        if self.path.startswith("/api/"):
            return self._api()
        if self.path.startswith(urllib.parse.urlparse(_url()).path.rstrip("/") + "/"):
            return self._original()
        return self._estatico()

    do_HEAD = do_GET

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path == "/mcp":
            return self._mcp()
        if self.path.startswith(urllib.parse.urlparse(_url()).path.rstrip("/") + "/"):
            return self._original()
        return self._api()

    def do_PUT(self):
        return self._api()

    def do_DELETE(self):
        return self._api()


def main():
    global ARMAZ, PORTA
    ap = argparse.ArgumentParser(description="PJe-Calc Studio — interface local para o PJe-Calc Cidadão")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--dados", default=os.environ.get("PJECALC_STUDIO_DADOS") or os.path.join(RAIZ, "dados"))
    ap.add_argument("--pjecalc", default=None, help="URL do PJe-Calc local (padrão: configuração salva)")
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args()
    PORTA = a.porta
    ARMAZ = Armazenamento(a.dados)
    if sys.stderr is None or sys.stdout is None:  # versão instalada (pythonw, sem janela): mensagens vão para um arquivo
        caminho_log = os.path.join(ARMAZ.pasta, "studio.log")
        if os.path.exists(caminho_log) and os.path.getsize(caminho_log) > 5 * 1024 * 1024:
            os.replace(caminho_log, caminho_log + ".anterior")  # guarda só o arquivo anterior
        log = open(caminho_log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    if a.pjecalc:
        ARMAZ.salvar_config({"urlPjecalc": a.pjecalc if a.pjecalc.endswith("/") else a.pjecalc + "/"})
    url = f"http://127.0.0.1:{PORTA}/"
    try:
        srv = Servidor(("127.0.0.1", PORTA), Handler)
    except OSError:
        if _studio_em_execucao(url):  # dois cliques no iniciar.bat com o Studio já aberto: só abre o navegador
            print(f"O PJe-Calc Studio já está em execução em {url}; abrindo o navegador.", flush=True)
            if not a.sem_navegador:
                webbrowser.open(url)
            return 0
        print(f"A porta {PORTA} está ocupada por outro programa. Feche-o ou use --porta <outra porta>.", file=sys.stderr)
        return 1
    print(f"PJe-Calc Studio {VERSAO_APP} em {url}  (dados: {ARMAZ.pasta}; PJe-Calc: {_url()})", flush=True)
    threading.Thread(target=_tarefas_periodicas, daemon=True).start()  # silencioso; sem internet, segue no prazo offline
    try:
        _escrever_conexao()  # para o Claude encontrar este Studio (Assistente Claude)
    except OSError as e:
        print(f"Aviso: não foi possível gravar a conexão do assistente Claude ({e}).", file=sys.stderr)
    if not a.sem_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def _studio_em_execucao(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "api/opcoes", timeout=3) as r:
            return "versaoCatalogo" in json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    sys.exit(main())
