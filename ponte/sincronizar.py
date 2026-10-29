"""Leva o rascunho da nova interface para o PJe-Calc e executa o cálculo no motor original.

Regras:
  * toda gravação passa pelas telas e validações do PJe-Calc (ver ponte/pjecalc.py);
  * cada passo devolve as mensagens oficiais; a primeira falha impeditiva interrompe a sequência;
  * o caso registra a revisão do rascunho efetivamente gravada e a revisão usada em cada execução,
    o que permite sinalizar resultados desatualizados.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import datetime

from . import catalogo, padroes
from .armazenamento import Armazenamento, agora, rascunho_vazio
from .jsf import JsfError, fold
from .pjecalc import PJeCalc, Resultado
from .relatorio import ler_pjc, ler_relatorio, historicos_do_pjc
from .tela import SessaoTela

motor_lock = threading.Lock()  # o PJe-Calc Cidadão é monousuário: uma operação por vez


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _historico_hash(h: dict) -> str:
    return _hash({"fgts": bool(h.get("fgts")), "inss": bool(h.get("inss")), "ocorrencias": h.get("ocorrencias", [])})


def _falha_conexao(url: str, diag: dict) -> dict:
    return {"rotulo": "Conectar ao PJe-Calc", "ok": False, "operacao": "conectar", "dados": diag,
            "mensagens": [{"severidade": "erro", "campo": None,
                           "texto": f"PJe-Calc não respondeu em {url}. Inicie o PJe-Calc e tente novamente."}]}


CAMPOS_SO_CALCULADO = ("tipoDaBaseTabelada", "baseHistoricos", "proporcionalizaHistorico", "baseVerbaDeCalculo",
                       "integralizarBase", "tipoDeDivisor", "outroValorDoDivisor", "outroValorDoMultiplicador",
                       "tipoDaQuantidade", "valorInformadoDaQuantidade")
CAMPOS_OCORRENCIA = ("ativo", "divisor", "multiplicador", "quantidade", "dobra", "devido", "pago")


def ocorrencias_informadas(ocorrencias: list[dict]) -> list[dict]:
    """Só o que o usuário informou: célula vazia mantém o valor gerado pelo PJe-Calc.

    Colunas de referência lidas do motor (prefixo "_") não são enviadas. "ativo" segue sempre que presente,
    para que remarcar um mês desativado numa gravação anterior o reative (mês já ativo não é alterado).
    """
    saida = []
    for o in ocorrencias or []:
        if not o.get("competencia"):
            continue
        item = {k: o[k] for k in CAMPOS_OCORRENCIA if k in o and o[k] not in (None, "")}
        if item:
            saida.append({"competencia": o["competencia"], **item})
    return saida


def e_reflexo_manual(v: dict) -> bool:
    return (v.get("parametros") or {}).get("tipoDeVerba") == "REFLEXO"


def nome_reflexo_manual(v: dict) -> str:
    """Nome completo que o PJe-Calc dá ao reflexo: "<nome> SOBRE <verba principal>"."""
    return f"{v['descricao'].strip().upper()} SOBRE {(v.get('principal') or '').strip().upper()}"


def _verba_manual_hash(v: dict) -> str:
    return _hash(spec_verba_manual(v))


def spec_verba_manual(v: dict) -> dict:
    """Verba manual do rascunho -> campos da tela "Manual" (ids de PARAMETROS_VERBA, ver ponte/pjecalc.py).

    v: {"descricao", "assuntoCnj", "parametros": {id: valor}, "bases": [históricos]}.
    """
    spec = {k: x for k, x in (v.get("parametros") or {}).items() if x not in (None, "")}
    informado = spec.get("valor") == "INFORMADO"
    if informado:  # a tela oculta base, divisor, multiplicador e quantidade quando o valor é informado
        spec = {k: x for k, x in spec.items() if k not in CAMPOS_SO_CALCULADO}
    spec["descricao"] = v["descricao"].strip().upper()
    if v.get("assuntoCnj"):
        spec["assuntoCnj"] = str(v["assuntoCnj"]).split("-")[0].strip()
    if e_reflexo_manual(v):  # a base do reflexo é a própria verba principal
        spec = {k: x for k, x in spec.items() if k not in ("tipoDaBaseTabelada", "integralizarBase")}
        spec["principal"] = (v.get("principal") or "").strip().upper()
        for k in ("comportamentoDoReflexo", "periodoMediaReflexo", "tratamentoFracaoReflexo"):
            if v.get(k):
                spec[k] = v[k]
        return spec
    if v.get("bases") and not informado:
        spec["bases"] = [b.strip().upper() for b in v["bases"] if b.strip()]
    bv = [{"verba": b["verba"].strip().upper(), "integralizar": b.get("integralizar") or "SIM"}
          for b in v.get("basesVerbas") or [] if (b.get("verba") or "").strip()]
    if bv and not informado:
        spec["basesVerbas"] = bv
    return spec


def gravar(caso: dict, url: str, armaz: Armazenamento, autor: str) -> dict:
    """Grava o rascunho no PJe-Calc. Retorna {"ok", "passos": [Resultado...], "calculoId"}.

    O vínculo com o cálculo do PJe-Calc (número e estado já sincronizado) é salvo mesmo quando a
    gravação para no meio, para que uma nova tentativa continue no mesmo cálculo em vez de duplicá-lo.
    """
    antes = json.dumps(caso.get("pjecalc") or {}, sort_keys=True)
    try:
        r = _gravar(caso, url, armaz, autor)
        # padrões do modelo/escritório ainda não aplicados neste cálculo: entram logo depois do primeiro envio
        pendentes = [p for p in caso.get("padroesPendentes") or []
                     if p not in ((caso.get("pjecalc") or {}).get("padroesAplicados") or {})]
        if r["ok"] and pendentes:
            ap = aplicar_padroes(armaz.obter(caso["id"]), pendentes, url, armaz, autor)
            r["passos"] += ap["passos"]
            r["ok"] = r["ok"] and ap["ok"]
        return r
    finally:
        vinc = caso.get("pjecalc") or {}
        if vinc.get("calculoId") and json.dumps(vinc, sort_keys=True) != antes and vinc.get("gravadoRevisao") != caso["revisao"]:
            armaz.salvar_interno(caso, autor, "gravacao_pjecalc_incompleta",
                                 [{"campo": "pjecalc.calculoId", "de": None, "para": vinc["calculoId"]}])


def _gravar(caso: dict, url: str, armaz: Armazenamento, autor: str) -> dict:
    r = caso["rascunho"]
    vinc = caso.setdefault("pjecalc", {})
    passos: list[dict] = []

    def registrar(res: Resultado, rotulo: str) -> bool:
        passos.append({"rotulo": rotulo, **res.to_dict()})
        return res.ok

    with motor_lock:
        m = PJeCalc(url)
        diag = m.diagnostico(tabelas=False)
        if not diag.get("acessivel"):
            return {"ok": False, "passos": [_falha_conexao(url, diag)]}
        # 1. Dados do cálculo (cria ou atualiza)
        if vinc.get("calculoId"):
            aberto = m.abrir_calculo(vinc["calculoId"])
            if not aberto.ok:
                registrar(aberto, f"Abrir cálculo nº {vinc['calculoId']} no PJe-Calc")
                return {"ok": False, "passos": passos}
            res = m.salvar_dados(r.get("dados", {}))
            rot = f"Gravar Dados do Cálculo (nº {vinc['calculoId']})"
        else:
            res = m.novo_calculo(r.get("dados", {}))
            rot = "Criar cálculo no PJe-Calc"
        if not registrar(res, rot):
            return {"ok": False, "passos": passos}
        vinc["calculoId"] = m.calculo_id
        vinc["url"] = url
        vinc["versao"] = diag.get("versao")

        # 2. Históricos salariais (CSV oficial por histórico; reenviados apenas se mudaram)
        estado = vinc.setdefault("historicos", {})
        no_motor = {fold(h["nome"]) for h in m.listar_historicos()}
        nomes_rascunho = set()
        for h in r.get("historicos", []):
            nome = (h.get("nome") or "").strip().upper()
            if not nome:
                continue
            nomes_rascunho.add(fold(nome))
            hh = _historico_hash(h)
            if fold(nome) in no_motor and estado.get(nome) == hh:
                continue
            # histórico já existente é atualizado no lugar ("Alterar" + CSV oficial): excluir e recriar quebraria o
            # vínculo com as verbas que o usam como base, e o PJe-Calc recusa excluir histórico vinculado
            if fold(nome) in no_motor:
                res = m.alterar_historico_ocorrencias(nome, h.get("ocorrencias", []), h.get("fgts"), h.get("inss"))
                rot = f"Atualizar histórico salarial {nome} ({len(h.get('ocorrencias', []))} competências)"
            else:
                res = m.incluir_historico_ocorrencias(nome, h.get("ocorrencias", []), h.get("fgts"), h.get("inss"))
                rot = f"Histórico salarial {nome} ({len(h.get('ocorrencias', []))} competências)"
            if not registrar(res, rot):
                return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
            estado[nome] = hh
        for nome in list(estado):  # removidos do rascunho depois de gravados
            if fold(nome) not in nomes_rascunho and fold(nome) in no_motor:
                registrar(m.excluir_historico(nome), f"Remover histórico {nome}")
                estado.pop(nome, None)

        # 3. Verbas (lançamento expresso), exclusões e parâmetros
        no_motor_v = {fold(v["nome"]): v for v in m.listar_verbas()}
        desejadas = [v for v in r.get("verbas", []) if v]
        faltantes = [v for v in desejadas if fold(v) not in no_motor_v]
        if faltantes:
            if not registrar(m.incluir_verbas_expressas(faltantes), "Incluir verbas: " + ", ".join(faltantes)):
                return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
        gravadas = set(vinc.get("verbasGravadas", []))
        for nome_f, v in no_motor_v.items():
            if nome_f not in {fold(x) for x in desejadas} and nome_f in {fold(x) for x in gravadas}:
                registrar(m.excluir_verba(v["nome"]), f"Remover verba {v['nome']}")
        vinc["verbasGravadas"] = desejadas
        estado_v = vinc.setdefault("verbasConfig", {})

        # 3a. Verbas manuais (lançamento "Manual"): incluídas, substituídas quando mudam, removidas se saírem do rascunho
        estado_m = vinc.setdefault("verbasManuais", {})
        no_motor_v = {fold(v["nome"]): v for v in m.listar_verbas()}
        todas_manuais = [v for v in r.get("verbasManuais", []) if (v.get("descricao") or "").strip()]
        manuais = [v for v in todas_manuais if not e_reflexo_manual(v)]
        nomes_manuais = {fold(v["descricao"].strip()) for v in manuais}
        for nome in list(estado_m):
            if fold(nome) not in nomes_manuais and fold(nome) in no_motor_v:
                registrar(m.excluir_verba(nome), f"Remover verba manual {nome}")
            if fold(nome) not in nomes_manuais:
                estado_m.pop(nome, None)
        for v in manuais:
            nome = v["descricao"].strip().upper()
            hm = _verba_manual_hash(v)
            if fold(nome) in no_motor_v and estado_m.get(nome) == hm:
                continue
            if fold(nome) in no_motor_v:
                if fold(nome) not in {fold(x) for x in estado_m}:
                    registrar(Resultado(False, "incluir_verba_manual", [{"severidade": "erro", "campo": None, "texto":
                              f"Já existe no cálculo uma verba chamada {nome}, que não foi lançada por esta interface."}]),
                              f"Verba manual {nome}")
                    return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                if not registrar(m.excluir_verba(nome), f"Substituir verba manual {nome} (exclusão da versão anterior)"):
                    return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
            if not registrar(m.incluir_verba_manual(spec_verba_manual(v)), f"Incluir verba manual {nome}"):
                return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
            estado_m[nome] = hm
            for k in [k for k in estado_v if fold(k.split("#")[0]) == fold(nome)]:
                estado_v.pop(k)  # verba recriada: reflexos, parâmetros e ocorrências precisam ser regravados
            estado_r = vinc.setdefault("reflexosManuais", {})
            for k in [k for k, x in estado_r.items() if fold(x["principal"]) == fold(nome)]:
                estado_r.pop(k)  # os reflexos da verba excluída foram junto com ela

        # 3b. Reflexos lançados manualmente: criados sob a verba principal, alterados por "Parametrizar" e,
        # como o PJe-Calc não exclui reflexos, desativados quando saem do rascunho
        estado_r = vinc.setdefault("reflexosManuais", {})
        reflexos = [v for v in todas_manuais if e_reflexo_manual(v)]
        motor_r = {fold(r["nome"]): (v["nome"], r) for v in m.listar_verbas() for r in v["reflexos"]}
        desejados = {fold(nome_reflexo_manual(v)) for v in reflexos}
        for nome in list(estado_r):
            if fold(nome) in desejados:
                continue
            principal, atual = motor_r.get(fold(nome), (estado_r[nome]["principal"], None))
            if atual and atual["ativo"]:
                registrar(m.definir_reflexos(principal, {atual["nome"]: False}), f"Desativar reflexo manual {nome}")
            estado_r.pop(nome)
        for v in reflexos:
            nome = nome_reflexo_manual(v)
            principal = v["principal"].strip().upper()
            hr = _verba_manual_hash(v)
            existente = motor_r.get(fold(nome))
            if existente and existente[1]["ativo"] and (estado_r.get(nome) or {}).get("hash") == hr:
                continue
            if existente and nome not in estado_r:
                registrar(Resultado(False, "incluir_verba_manual", [{"severidade": "erro", "campo": None, "texto":
                          f"Já existe no cálculo o reflexo {nome}, que não foi lançado por esta interface."}]),
                          f"Reflexo manual {nome}")
                return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
            if existente:
                res = m.alterar_reflexo_manual(existente[0], existente[1]["nome"], spec_verba_manual(v))
                rot = f"Alterar reflexo manual {nome}"
                if res.ok:  # parâmetros novos só valem para as ocorrências depois de regeradas
                    registrar(res, rot)
                    res, rot = m.regerar_ocorrencias(existente[0], existente[1]["nome"]), f"Regerar ocorrências de {nome}"
            elif fold(principal) not in {fold(x["nome"]) for x in m.listar_verbas()}:
                res = Resultado(False, "incluir_verba_manual", [{"severidade": "erro", "campo": None, "texto":
                                f"A verba principal {principal} do reflexo {v['descricao']} não está no cálculo."}])
                rot = f"Incluir reflexo manual {nome}"
            else:
                res = m.incluir_verba_manual(spec_verba_manual(v))
                rot = f"Incluir reflexo manual {nome}"
            if not registrar(res, rot):
                return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
            estado_r[nome] = {"principal": principal, "hash": hr}

        cfgs = r.get("verbasConfig", {})
        if cfgs:
            atuais = {fold(v["nome"]): v for v in m.listar_verbas()}
            for nome, cfg in cfgs.items():
                alvo = atuais.get(fold(nome))
                if not alvo:
                    continue
                if cfg.get("reflexos"):
                    hr = _hash(cfg["reflexos"])
                    if estado_v.get(nome + "#reflexos") != hr:
                        if not registrar(m.definir_reflexos(nome, cfg["reflexos"]), f"Reflexos da verba {nome}"):
                            return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                        estado_v[nome + "#reflexos"] = hr
                hv = _hash({"alteracoes": cfg.get("alteracoes", {}), "bases": cfg.get("bases", [])})
                if estado_v.get(nome) != hv:
                    atual = m.parametros_verba(alvo["linha"])
                    ja = {fold(b) for b in atual.get("bases", [])}
                    novas = [b for b in cfg.get("bases", []) if fold(b) not in ja]
                    if cfg.get("alteracoes") or novas:
                        if not registrar(m.alterar_verba(alvo["linha"], cfg.get("alteracoes", {}), novas),
                                         f"Parâmetros da verba {nome}"):
                            return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                        # sem regerar, o PJe-Calc mantém as ocorrências calculadas com os parâmetros anteriores
                        if not registrar(m.regerar_ocorrencias(alvo["nome"]), f"Regerar ocorrências de {nome}"):
                            return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                        estado_v.pop(nome + "#ocorrencias", None)  # parâmetros novos podem regerar as ocorrências
                    estado_v[nome] = hv
                # ocorrências mês a mês: depois dos parâmetros, que definem o período e os termos padrão
                ocs = ocorrencias_informadas(cfg.get("ocorrencias", []))
                if ocs:
                    ho = _hash(ocs)
                    if estado_v.get(nome + "#ocorrencias") != ho:
                        linha = next((v["linha"] for v in m.listar_verbas() if fold(v["nome"]) == fold(nome)), alvo["linha"])
                        if not registrar(m.gravar_ocorrencias(linha, ocs),
                                         f"Ocorrências da verba {nome} ({len(ocs)} competências)"):
                            return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                        estado_v[nome + "#ocorrencias"] = ho

        # 4. FGTS e critérios de atualização (somente se o usuário definiu algo)
        if r.get("fgts"):
            hf = _hash(r["fgts"])
            if vinc.get("fgtsHash") != hf:
                if not registrar(m.gravar_fgts(r["fgts"]), "FGTS"):
                    return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                vinc["fgtsHash"] = hf
        at = r.get("atualizacao") or {}
        if at.get("valores") or at.get("jurosCombinados") is not None or at.get("indicesCombinados") is not None:
            ha = _hash(at)
            if vinc.get("atualizacaoHash") != ha:
                if not registrar(m.gravar_atualizacao(at.get("valores", {}), at.get("jurosCombinados"),
                                                      at.get("indicesCombinados")), "Correção, Juros e Multa"):
                    return {"ok": False, "passos": passos, "calculoId": vinc["calculoId"]}
                vinc["atualizacaoHash"] = ha

        # 5. Pendências apuradas pelo PJe-Calc
        pend = m.pendencias()
        passos.append({"rotulo": "Pendências apuradas pelo PJe-Calc", **pend.to_dict()})
        vinc["gravadoRevisao"] = caso["revisao"]
        vinc["gravadoEm"] = agora()
        vinc["pendencias"] = pend.mensagens
        vinc["dadosPadraoLiquidacao"] = pend.dados
    armaz.salvar_interno(caso, autor, "gravacao_pjecalc",
                         [{"campo": "pjecalc.gravadoRevisao", "de": None, "para": caso["revisao"]}])
    return {"ok": True, "passos": passos, "calculoId": vinc["calculoId"], "pendencias": pend.mensagens}


def aplicar_padroes(caso: dict, ids: list[str], url: str, armaz: Armazenamento, autor: str) -> dict:
    """Aplica padrões do escritório (ponte/padroes.py) ao cálculo do PJe-Calc ligado ao caso.

    Cada padrão abre a sua tela numa sessão própria e repete o preenchimento gravado; o PJe-Calc valida e grava.
    O caso registra o que foi aplicado (com data e resultado) para não repetir sem querer: aplicar de novo um
    padrão que cria registros (ex.: honorários) criaria um segundo registro.
    """
    vinc = caso.get("pjecalc") or {}
    if not vinc.get("calculoId"):
        return {"ok": False, "passos": [{"rotulo": "Aplicar padrões", "ok": False, "operacao": "padroes", "dados": {},
                                        "mensagens": [{"severidade": "erro", "campo": None,
                                                       "texto": "Envie o cálculo ao PJe-Calc antes de aplicar padrões."}]}]}
    passos, aplicados = [], {}
    with motor_lock:
        for pid in ids:
            try:
                padrao = armaz.obter_padrao(pid)
            except KeyError:
                passos.append({"rotulo": f"Padrão {pid}", "ok": False, "operacao": "padrao", "dados": {},
                               "mensagens": [{"severidade": "erro", "campo": None, "texto": "Padrão não encontrado (excluído?)."}]})
                continue
            rotulo = f"Padrão “{padrao['nome']}” ({padrao.get('funcao') or padrao['menu']})"
            try:
                sessao = SessaoTela(url, vinc["calculoId"], padrao["menu"])
                sessao.abrir()
                r = padroes.aplicar(sessao, padrao["passos"])
            except (JsfError, OSError) as e:
                r = {"ok": False, "registro": [{"ok": False, "texto": str(e)}], "tela": {"mensagens": []}}
            msgs = [{"severidade": "sucesso" if x["ok"] else "erro", "campo": None, "texto": x["texto"]} for x in r["registro"]]
            msgs += [m for m in r["tela"]["mensagens"] if m["severidade"] in ("erro", "alerta")]
            passos.append({"rotulo": rotulo, "ok": r["ok"], "operacao": "padrao", "mensagens": msgs, "dados": {"padrao": pid}})
            aplicados[pid] = {"em": agora(), "ok": r["ok"], "nome": padrao["nome"]}
    caso = armaz.obter(caso["id"])
    caso.setdefault("pjecalc", {}).setdefault("padroesAplicados", {}).update(aplicados)
    caso["pjecalc"]["abertoNoOriginalEm"] = agora()  # o PJe-Calc mudou fora das etapas do Studio
    armaz.salvar_interno(caso, autor, "padroes_pjecalc", [{"campo": "pjecalc.padroesAplicados", "de": None, "para": list(aplicados)}])
    return {"ok": all(p["ok"] for p in passos), "passos": passos}


def executar(caso: dict, url: str, armaz: Armazenamento, autor: str) -> dict:
    """Liquida no PJe-Calc, gera o relatório oficial (HTML) e exporta o .PJC, registrando a execução."""
    vinc = caso.get("pjecalc") or {}
    if not vinc.get("calculoId") or vinc.get("gravadoRevisao") != caso["revisao"]:
        g = gravar(caso, url, armaz, autor)
        if not g["ok"]:
            return {"ok": False, "etapa": "gravar", **g}
        caso = armaz.obter(caso["id"])
        vinc = caso["pjecalc"]
    passos = []
    liq = caso["rascunho"].get("liquidacao", {})
    with motor_lock:
        m = PJeCalc(url)
        diag = m.diagnostico()  # com a referência das tabelas: fica registrada na execução
        if not diag.get("acessivel"):
            return {"ok": False, "etapa": "conectar", "passos": [_falha_conexao(url, diag)]}
        aberto = m.abrir_calculo(vinc["calculoId"])
        if not aberto.ok:
            return {"ok": False, "passos": [{"rotulo": "Abrir cálculo", **aberto.to_dict()}]}
        pend = m.pendencias()
        passos.append({"rotulo": "Pendências apuradas pelo PJe-Calc", **pend.to_dict()})
        if not pend.ok:
            return {"ok": False, "etapa": "pendencias", "passos": passos}
        res = m.liquidar(liq.get("data") or None, liq.get("indicesAcumulados") or None)
        passos.append({"rotulo": "Liquidar (motor do PJe-Calc)", **res.to_dict()})
        if not res.ok:
            return {"ok": False, "etapa": "liquidar", "passos": passos}
        rr, corpo_rel, _ = m.relatorio("HTML")
        passos.append({"rotulo": "Relatório oficial (HTML)", **rr.to_dict()})
        rp, corpo_pdf, _ = m.relatorio("PDF")
        passos.append({"rotulo": "Relatório oficial (PDF)", **rp.to_dict()})
        re_, corpo_pjc, nome_pjc = m.exportar()
        passos.append({"rotulo": "Exportar .PJC", **re_.to_dict()})
    # dois cálculos no mesmo segundo não podem gravar na mesma pasta
    eid = datetime.now().strftime("e%Y%m%d%H%M%S") + "_" + secrets.token_hex(2)
    pasta = armaz.pasta_execucao(caso["id"], eid)
    arquivos = {}
    if corpo_rel:
        with open(os.path.join(pasta, "relatorio.html"), "wb") as fh:
            fh.write(corpo_rel)
        arquivos["relatorio"] = "relatorio.html"
    if corpo_pdf:
        with open(os.path.join(pasta, "relatorio.pdf"), "wb") as fh:
            fh.write(corpo_pdf)
        arquivos["relatorioPdf"] = "relatorio.pdf"
    if corpo_pjc:
        with open(os.path.join(pasta, "calculo.pjc"), "wb") as fh:
            fh.write(corpo_pjc)
        arquivos["pjc"] = "calculo.pjc"
        arquivos["pjcNomeOriginal"] = nome_pjc
    resultado = ler_relatorio(corpo_rel) if corpo_rel else {}
    pjc = ler_pjc(corpo_pjc) if corpo_pjc else {"meta": {}, "verbas": []}
    with open(os.path.join(pasta, "resultado.json"), "w", encoding="utf-8") as fh:
        json.dump({"relatorio": resultado, "pjc": pjc}, fh, ensure_ascii=False, indent=1)
    liquido = next((c["valor"] for c in resultado.get("creditos_descontos", [])
                    if fold(c.get("descricao") or "") == fold("Líquido Devido ao Reclamante")), None)
    execucao = {
        "id": eid, "em": agora(), "autor": autor, "revisaoEntradas": caso["revisao"],
        "calculoId": vinc["calculoId"], "versaoMotor": diag.get("versao"), "buildMotor": diag.get("build"),
        "tabelas": diag.get("tabelas"), "rodape": resultado.get("rodape"),
        "parametrosLiquidacao": res.dados, "hashLiquidacao": pjc["meta"].get("hashCodeLiquidacao"),
        "sha256Pjc": hashlib.sha256(corpo_pjc).hexdigest() if corpo_pjc else None,
        "arquivos": arquivos, "liquido": liquido, "mensagens": list(passos),
    }
    caso = armaz.obter(caso["id"])
    caso.setdefault("execucoes", []).append(execucao)
    if caso.get("situacao") in ("rascunho", "em_conferencia"):
        caso["situacao"] = "calculado"
    armaz.salvar_interno(caso, autor, "execucao_pjecalc",
                         [{"campo": "execucao", "de": None, "para": eid}])
    return {"ok": True, "execucao": execucao, "passos": passos}


def importar_pjc(conteudo: bytes, nome: str, url: str, armaz: Armazenamento, autor: str) -> dict:
    """Importa um .PJC pela tela oficial e cria um caso local com os dados lidos de volta do PJe-Calc."""
    with motor_lock:
        m = PJeCalc(url)
        res = m.importar(conteudo, nome)
        if not res.ok:
            return {"ok": False, "passos": [{"rotulo": "Importar .PJC no PJe-Calc", **res.to_dict()}]}
        dados = m.ler_dados()
        verbas = [v["nome"] for v in m.listar_verbas()]
        historicos_motor = [h["nome"] for h in m.listar_historicos()]
    historicos = [h for h in historicos_do_pjc(conteudo) if not _e_ultima_remuneracao(h["nome"])]
    caso = _criar_caso_ligado(armaz, autor, url, res.dados["calculo_id"], dados, historicos, verbas, historicos_motor,
                              titulo_padrao="Cálculo importado", origem={"tipo": "importado", "arquivo": nome},
                              acao="importacao_pjc", alteracao={"campo": "origem", "de": None, "para": nome})
    return {"ok": True, "caso": caso["id"], "passos": [{"rotulo": "Importar .PJC no PJe-Calc", **res.to_dict()}]}


def _e_ultima_remuneracao(nome: str) -> bool:
    """Histórico gerado automaticamente pelo PJe-Calc a partir da "Última Remuneração" do contrato."""
    return fold(nome) == fold("ÚLTIMA REMUNERAÇÃO")


def _criar_caso_ligado(armaz: Armazenamento, autor: str, url: str, calculo_id: str, dados: dict, historicos: list[dict],
                       verbas: list[str], historicos_motor: list[str], *, titulo_padrao: str, origem: dict, acao: str,
                       alteracao: dict, extra_vinculo: dict | None = None) -> dict:
    """Cria no Studio um cálculo já ligado a um cálculo do PJe-Calc, com o que foi lido de volta das telas oficiais.

    O vínculo nasce "gravado" na revisão inicial: o Studio só reenvia ao PJe-Calc o que for alterado nele depois.
    Só as verbas do lançamento expresso entram na lista de verbas do Studio; as lançadas manualmente no PJe-Calc
    continuam lá (o Studio não as conhece por inteiro e nunca as exclui) e são devolvidas em "verbasSoNoPjecalc".
    """
    expressas = {fold(v) for v in catalogo.VERBAS_EXPRESSAS}
    so_no_pjecalc = [v for v in verbas if fold(v) not in expressas]
    verbas = [v for v in verbas if fold(v) in expressas]
    dados = {k: (v.get("rotulo") if isinstance(v, dict) else v) for k, v in dados.items() if k != "id"}
    dados = {k: v for k, v in dados.items() if v not in (None, "")}
    historicos = [{"id": "h" + _hash(h["nome"])[:6], "nome": h["nome"], "fgts": bool(h.get("fgts")),
                   "inss": bool(h.get("inss")), "ocorrencias": h["ocorrencias"]} for h in historicos]
    rasc = rascunho_vazio()
    rasc["dados"], rasc["historicos"], rasc["verbas"] = dados, historicos, verbas
    reclamante, reclamado = dados.get("reclamante.nome") or "", dados.get("reclamado.nome") or ""
    caso = armaz.criar({
        "titulo": f"{reclamante or titulo_padrao} × {reclamado}".strip(" ×"),
        "cliente": reclamante, "parteContraria": reclamado, "rascunho": rasc, "origem": origem,
    }, autor)
    caso["pjecalc"] = {"calculoId": str(calculo_id), "url": url, "gravadoRevisao": caso["revisao"], "gravadoEm": agora(),
                       "verbasGravadas": verbas, "historicos": {h["nome"]: _historico_hash(h) for h in historicos},
                       "historicosDoMotor": historicos_motor, "verbasSoNoPjecalc": so_no_pjecalc, **(extra_vinculo or {})}
    return armaz.salvar_interno(caso, autor, acao, [alteracao])


def trazer_do_pjecalc(numero: str, url: str, armaz: Armazenamento, autor: str) -> dict:
    """Cria um cálculo no Studio ligado a um cálculo que já existe no PJe-Calc (sem importar nem duplicar).

    Lê pelas telas oficiais os Dados do Cálculo, as verbas e os históricos salariais mês a mês. Tudo o mais
    (faltas, férias, cartão de ponto, contribuição social, IR, honorários, custas, ocorrências editadas…)
    continua no PJe-Calc e não é alterado: o Studio só reenvia o que for modificado nele.
    """
    for c in armaz.listar():
        if str(c.get("calculoPjecalc") or "") == str(numero):
            return {"ok": False, "caso": c["id"], "erro": f"O cálculo nº {numero} já está ligado a “{c.get('titulo')}”."}
    with motor_lock:
        m = PJeCalc(url)
        aberto = m.abrir_calculo(numero)
        if not aberto.ok:
            return {"ok": False, "passos": [{"rotulo": f"Abrir cálculo nº {numero} no PJe-Calc", **aberto.to_dict()}]}
        dados = m.ler_dados()
        verbas = [v["nome"] for v in m.listar_verbas()]
        nomes_hist = [h["nome"] for h in m.listar_historicos()]
        historicos, avisos, vistos = [], [], set()
        for nome in nomes_hist:
            if _e_ultima_remuneracao(nome):
                continue
            if fold(nome) in vistos:
                # o Studio identifica históricos pelo nome; o PJe-Calc aceita nomes repetidos
                avisos.append(f"O PJe-Calc tem mais de um histórico salarial chamado “{nome}”. O Studio trouxe o primeiro; "
                              "os outros continuam no PJe-Calc (tela original “Histórico Salarial”) e o Studio não os altera.")
                continue
            vistos.add(fold(nome))
            h = m.ler_historico(nome)
            if not h:
                continue
            ocs = [{"competencia": o["competencia"], "valor": o["valor"], "fgtsRecolhido": bool(o.get("fgtsRecolhido")),
                    "inssRecolhido": bool(o.get("inssRecolhido"))} for o in h["ocorrencias"]]
            historicos.append({"nome": nome, "fgts": h.get("fgts"), "inss": h.get("inss"), "ocorrencias": ocs})
    caso = _criar_caso_ligado(armaz, autor, url, numero, dados, historicos, verbas, nomes_hist,
                              titulo_padrao="Cálculo do PJe-Calc", origem={"tipo": "pjecalc", "calculo": str(numero)},
                              acao="ligado_ao_pjecalc",
                              alteracao={"campo": "pjecalc.calculoId", "de": None, "para": str(numero)},
                              extra_vinculo={"trazidoDoPjecalc": True})
    for v in caso["pjecalc"]["verbasSoNoPjecalc"]:
        avisos.append(f"A verba “{v}” foi lançada manualmente no PJe-Calc: ela continua no cálculo e o Studio não a altera, "
                      "mas não é copiada em cenários duplicados.")
    return {"ok": True, "caso": caso["id"], "historicos": len(historicos), "verbas": len(caso["rascunho"]["verbas"]), "avisos": avisos}


def expandir(inicio: str, fim: str, valor: str) -> list[dict]:
    """Competências MM/AAAA de inicio a fim (inclusive) com o mesmo valor."""
    mi, ai = int(inicio[:2]), int(inicio[3:])
    mf, af = int(fim[:2]), int(fim[3:])
    saida = []
    while (ai, mi) <= (af, mf):
        saida.append({"competencia": f"{mi:02d}/{ai}", "valor": valor, "fgtsRecolhido": False, "inssRecolhido": False})
        mi += 1
        if mi > 12:
            mi, ai = 1, ai + 1
    return saida
