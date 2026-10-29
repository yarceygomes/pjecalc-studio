"""Operações de alto nível sobre a instalação local do PJe-Calc Cidadão.

Cada operação percorre as mesmas telas e aciona os mesmos botões da interface original.
O resultado de cada operação traz as mensagens devolvidas pelo PJe-Calc, para que a nova
interface informe com fidelidade o que foi efetivamente gravado.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass, field

from .jsf import JsfClient, JsfError, Page, fold, table
from .jsf import unescape as _unesc

URL_PADRAO = "http://127.0.0.1:9257/pjecalc/"

# Campos da tela "Dados do Cálculo" (calculo.xhtml), na ordem em que devem ser enviados.
# chave da nova interface -> (id do componente JSF, tipo)
CAMPOS_CALCULO: list[tuple[str, str, str]] = [
    ("processo.numero", "numero", "texto"),
    ("processo.digito", "digito", "texto"),
    ("processo.ano", "ano", "texto"),
    ("processo.regiao", "regiao", "texto"),
    ("processo.vara", "vara", "texto"),
    ("processo.valorDaCausa", "valorDaCausa", "valor"),
    ("processo.autuadoEm", "autuadoEm", "data"),
    ("reclamante.nome", "reclamanteNome", "texto"),
    ("reclamante.tipoDocumentoFiscal", "documentoFiscalReclamante", "opcao"),
    ("reclamante.numeroDocumentoFiscal", "reclamanteNumeroDocumentoFiscal", "texto"),
    ("reclamante.tipoDocumentoPrevidenciario", "reclamanteTipoDocumentoPrevidenciario", "opcao"),
    ("reclamante.numeroDocumentoPrevidenciario", "reclamanteNumeroDocumentoPrevidenciario", "texto"),
    ("reclamado.nome", "reclamadoNome", "texto"),
    ("reclamado.tipoDocumentoFiscal", "tipoDocumentoFiscalReclamado", "opcao"),
    ("reclamado.numeroDocumentoFiscal", "reclamadoNumeroDocumentoFiscal", "texto"),
    ("local.estado", "estado", "lista"),
    ("local.municipio", "municipio", "lista"),
    ("contrato.dataAdmissao", "dataAdmissaoInputDate", "data"),
    ("contrato.dataDemissao", "dataDemissaoInputDate", "data"),
    ("contrato.dataAjuizamento", "dataAjuizamentoInputDate", "data"),
    ("contrato.dataInicioCalculo", "dataInicioCalculoInputDate", "data"),
    ("contrato.dataTerminoCalculo", "dataTerminoCalculoInputDate", "data"),
    ("contrato.prescricaoQuinquenal", "prescricaoQuinquenal", "marca"),
    ("contrato.prescricaoFgts", "prescricaoFgts", "marca"),
    ("contrato.regime", "tipoDaBaseTabelada", "lista"),
    ("contrato.maiorRemuneracao", "valorMaiorRemuneracao", "valor"),
    ("contrato.ultimaRemuneracao", "valorUltimaRemuneracao", "valor"),
    ("contrato.apuracaoAvisoPrevio", "apuracaoPrazoDoAvisoPrevio", "lista"),
    ("contrato.prazoAvisoInformado", "prazoAvisoInformado", "texto"),
    ("contrato.projetaAvisoIndenizado", "projetaAvisoIndenizado", "marca"),
    ("contrato.limitarAvos", "limitarAvos", "marca"),
    ("contrato.zeraValorNegativo", "zeraValorNegativo", "marca"),
    ("contrato.consideraFeriadoEstadual", "consideraFeriadoEstadual", "marca"),
    ("contrato.consideraFeriadoMunicipal", "consideraFeriadoMunicipal", "marca"),
    ("jornada.cargaHorariaPadrao", "valorCargaHorariaPadrao", "valor"),
    ("jornada.sabadoDiaUtil", "sabadoDiaUtil", "marca"),
    ("observacoes.comentarios", "comentarios", "texto"),
]

SUCESSO = ("operacao realizada com sucesso", "sucesso")


@dataclass
class Resultado:
    """Resultado de uma operação, com as mensagens do próprio PJe-Calc."""
    ok: bool
    operacao: str
    mensagens: list[dict] = field(default_factory=list)
    dados: dict = field(default_factory=dict)

    def to_dict(self):
        return {"ok": self.ok, "operacao": self.operacao, "mensagens": self.mensagens, "dados": self.dados}


MARCADORES = {"erro.": "erro", "alerta.": "alerta", "sucesso.": "sucesso"}  # facetas de mensagem.xhtml


def classificar(mensagens: list[dict]) -> list[dict]:
    """Converte as mensagens da página em avisos com severidade.

    A severidade vem do marcador que o próprio PJe-Calc imprime antes de cada mensagem global
    ("Erro.", "Alerta.", "Sucesso." em pages/comum/mensagem.xhtml). Mensagens de campo
    (rich:message) são erros de validação do componente indicado.
    """
    vistos, saida = set(), []
    atual = None
    for m in mensagens:
        texto = m["text"].strip()
        t = fold(texto)
        if t in MARCADORES:
            atual = MARCADORES[t]
            continue
        for marcador, sev in MARCADORES.items():  # marcador e texto na mesma célula
            if t.startswith(marcador + " "):
                atual, texto, t = sev, texto[len(marcador):].strip(), t[len(marcador):].strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        cls = (m.get("class") or "").lower()
        cid = m.get("id") or ""
        global_ = "rich-messages" in cls
        if global_ and atual:
            sev = atual
        elif not global_ and (cid or "rich-message" in cls):
            sev = "erro"  # rich:message (e seus rótulos/marcadores) vinculada a um campo = falha de validação
        elif "errors" in cls or "error" in cls or "erro" in cls:
            sev = "erro"
        elif any(s in t for s in SUCESSO):
            sev = "sucesso"
        else:
            sev = "info"
        saida.append({"severidade": sev, "texto": texto, "campo": _campo(cid)})
    return saida


def _campo(component_id: str | None) -> str | None:
    if not component_id:
        return None
    alvo = component_id.split(":")[-1]
    for chave, cid, _ in CAMPOS_CALCULO:
        if cid == alvo or alvo.startswith(cid):
            return chave
    return None


def _ok(msgs: list[dict]) -> bool:
    return not any(m["severidade"] == "erro" for m in msgs) and any(m["severidade"] == "sucesso" for m in msgs)


class PJeCalc:
    """Sessão de trabalho com uma instalação local do PJe-Calc (um usuário, um cálculo aberto por vez)."""

    def __init__(self, url: str = URL_PADRAO, timeout: float = 600):
        self.url = url
        self.client = JsfClient(url, timeout=timeout)
        self.page: Page | None = None
        self.calculo_id: str | None = None

    # ------------------------------------------------------------------ diagnóstico
    def diagnostico(self, tabelas: bool = True) -> dict:
        """Versão e build do PJe-Calc em execução; com tabelas=True, também a referência das tabelas auxiliares
        (uma requisição a mais: o indicador de status da interface, consultado a cada 30 s, não precisa dela)."""
        info = {"url": self.url, "acessivel": False}
        try:
            r = self.client.get("versao.html")
            info["acessivel"] = r.status == 200
            m = re.search(r"Versao:\s*([\d.]+)", r.text)
            b = re.search(r"Build:\s*([^<]+)", r.text)
            info["versao"] = m.group(1) if m else None
            info["build"] = b.group(1).strip() if b else None
        except Exception as e:  # noqa: BLE001 - diagnóstico deve relatar qualquer falha
            info["erro"] = str(e)
            return info
        if not tabelas:
            return info
        try:
            r = self.client.get("versao-tabelas.jsf")
            info["tabelas"] = _texto_simples(r.text)[:2000]
        except Exception as e:  # noqa: BLE001
            info["tabelas_erro"] = str(e)
        return info

    # ------------------------------------------------------------------ navegação
    def _inicio(self, acao: str | None = None) -> Page:
        """Abre a tela inicial e, opcionalmente, aciona uma de suas opções.

        Com um cálculo aberto, o menu lateral troca "Novo/Buscar/Importar" pelos itens do
        cálculo; os atalhos da tela inicial ("Criar Novo Cálculo" etc.) continuam disponíveis.
        """
        self.page = self.client.open("pages/principal.jsf")
        if acao:
            alternativas = {"Novo": "Criar Novo Cálculo", "Buscar": "Buscar Cálculo", "Importar": "Importar Cálculo"}
            try:
                self.page.click(acao)
            except JsfError:
                self.page.click(alternativas[acao])
        return self.page

    def tela_inicial(self) -> Page:
        """Tela inicial, sem cálculo aberto (menu com Novo, Buscar, Importar e as Tabelas)."""
        return self._inicio()

    def _menu(self, item: str) -> Page:
        if self.page is None:
            raise JsfError("Nenhum cálculo aberto nesta sessão.")
        self.page.click(item)
        return self.page

    def municipios(self, uf: str) -> list[str]:
        """Municípios que o PJe-Calc oferece para a UF (somente leitura: a tela "Novo" é abandonada sem "Salvar")."""
        p = self._inicio("Novo")
        p.set("estado", uf)
        self.page = None
        return [r for v, r in p.options("municipio") if not v.startswith("org.jboss")]

    def novo_calculo(self, dados: dict) -> Resultado:
        self._inicio("Novo")
        return self._gravar_dados(dados, "novo_calculo")

    def abrir_calculo(self, calculo_id: str | int) -> Resultado:
        p = self._inicio("Buscar")
        p.set("numeroCalculoBusca", str(calculo_id))
        p.click("buscar")
        _, linhas = table(p.last_response, "formulario:listagem")
        if not linhas:
            return Resultado(False, "abrir_calculo", [{"severidade": "erro", "texto": f"Cálculo {calculo_id} não encontrado.", "campo": None}])
        p.click("formulario:listagem:0:" + self._acao_linha(p, 0, "Abrir"))
        self.calculo_id = str(calculo_id)
        return Resultado(True, "abrir_calculo", [], {"calculo": self.ler_dados()})

    @staticmethod
    def _acao_linha(p: Page, linha: int, titulo: str) -> str:
        prefixo = f"formulario:listagem:{linha}:"
        for a in p.actions:
            if (a.id or "").startswith(prefixo) and fold(a.text) == fold(titulo):
                return a.id[len(prefixo):]
        raise JsfError(f"Ação '{titulo}' não encontrada na linha {linha}.")

    def listar_calculos(self, filtros: dict | None = None) -> list[dict]:
        p = self._inicio("Buscar")
        mapa = {"reclamante": "reclamanteBusca", "reclamado": "reclamadoBusca", "numero": "numeroProcessoBusca",
                "calculo": "numeroCalculoBusca"}
        for k, v in (filtros or {}).items():
            if k in mapa and v:
                p.set(mapa[k], v)
        p.click("buscar")
        cab, linhas = table(p.last_response, "formulario:listagem")
        saida = []
        for ln in linhas:
            if len(ln) >= 6:
                saida.append({"processo": ln[1], "calculo": ln[2], "tipo": ln[3], "reclamante": ln[4], "reclamado": ln[5]})
        self.page = None
        return saida

    # ------------------------------------------------------------------ dados do cálculo
    def ler_dados(self) -> dict:
        p = self._menu("Dados do Cálculo")
        dados = {"id": p.get("idCalculo") if p.has("idCalculo") else None}
        for chave, cid, tipo in CAMPOS_CALCULO:
            if not p.has(cid):
                continue
            valor = p.get(cid)
            if tipo == "lista":
                rotulos = dict(p.options(cid))
                valor = {"valor": valor, "rotulo": rotulos.get(valor, "")}
            dados[chave] = valor
        return dados

    def salvar_dados(self, dados: dict) -> Resultado:
        self._menu("Dados do Cálculo")
        return self._gravar_dados(dados, "salvar_dados")

    def _gravar_dados(self, dados: dict, operacao: str) -> Resultado:
        p = self.page
        for chave, cid, tipo in CAMPOS_CALCULO:
            if chave not in dados or not p.has(cid):
                continue
            valor = dados[chave]
            if tipo == "lista" and isinstance(valor, dict):
                valor = valor.get("rotulo") or valor.get("valor")
            if tipo == "opcao" and not valor:
                continue
            p.set(cid, valor)
        p.click("salvar")
        msgs = classificar(p.messages)
        ok = _ok(msgs)
        if ok and p.has("idCalculo"):
            self.calculo_id = p.get("idCalculo")
        return Resultado(ok, operacao, msgs, {"calculo_id": self.calculo_id})

    # ------------------------------------------------------------------ histórico salarial
    def listar_historicos(self) -> list[dict]:
        p = self._menu("Histórico Salarial")
        _, linhas = table(p.last_response, "formulario:listagem")
        return [{"nome": ln[1] if len(ln) > 1 else ln[0]} for ln in linhas if ln and any(ln)]

    def ler_historico(self, nome: str) -> dict | None:
        """Lê um histórico salarial pela ação "Visualizar" da tela (somente leitura; sai por "Voltar").

        Devolve {"nome", "fgts", "inss", "ocorrencias": [{"competencia", "valor", "fgtsRecolhido", "inssRecolhido"}]}
        ou None se o histórico não existe. As caixas de incidência/recolhimento só aparecem quando o histórico
        tem a incidência correspondente; ausência de coluna = None (não aplicável), nunca False.
        """
        p = self._menu("Histórico Salarial")
        _, linhas = table(p.last_response, "formulario:listagem")
        for i, ln in enumerate(linhas):
            if len(ln) > 1 and fold(ln[1]) == fold(nome):
                acao = next((a.id for a in p.actions if (a.id or "").startswith(f"formulario:listagem:{i}:")
                             and fold(a.text) == "visualizar"), None)
                if not acao:
                    raise JsfError(f"Ação Visualizar não encontrada para o histórico '{nome}'.")
                p.click(acao)
                ocs = []
                for k in sorted({int(m.group(1)) for n in p.fields if (m := re.fullmatch(r"formulario:listagemMC:(\d+):valor", n))}):
                    pre = f"formulario:listagemMC:{k}:"
                    flag = lambda suf: p.get(pre + suf) if p.has(pre + suf) else None  # noqa: E731
                    ocs.append({"competencia": p.texts.get(pre + "data", ""), "valor": p.get(pre + "valor"),
                                "fgtsRecolhido": flag("recolhidoFGTS"), "inssRecolhido": flag("recolhidoINSS")})
                dados = {"nome": nome, "fgts": bool(p.get("fgts")) if p.has("fgts") else None,
                         "inss": bool(p.get("inss")) if p.has("inss") else None, "ocorrencias": ocs}
                p.click("voltar")
                return dados
        return None

    def excluir_historico(self, nome: str) -> Resultado:
        p = self._menu("Histórico Salarial")
        _, linhas = table(p.last_response, "formulario:listagem")
        for i, ln in enumerate(linhas):
            if len(ln) > 1 and fold(ln[1]) == fold(nome):
                p.click(f"formulario:listagem:{i}:excluirHistorico")  # abre o registro em modo de exclusão
                msgs = classificar(p.messages)
                if 'id="formulario:excluir"' in p.last_response:
                    p.click("formulario:excluir")  # botão "Excluir" do registro (confirmação)
                    msgs += classificar(p.messages)
                return Resultado(_ok(msgs), "excluir_historico", msgs, {"nome": nome})
        return Resultado(False, "excluir_historico",
                         [{"severidade": "erro", "texto": f"Histórico '{nome}' não encontrado no PJe-Calc.", "campo": None}])

    def excluir_verba(self, nome: str) -> Resultado:
        p = self._menu("Verbas")
        for v in _verbas_da_pagina(p):
            if fold(v["nome"]) == fold(nome):
                p.click(f"formulario:listagem:{v['linha']}:" + self._acao_linha(p, v["linha"], "Excluir"))
                msgs = classificar(p.messages)
                if 'id="formulario:excluir"' in p.last_response:
                    p.click("formulario:excluir")
                    msgs += classificar(p.messages)
                return Resultado(_ok(msgs), "excluir_verba", msgs, {"nome": nome})
        return Resultado(False, "excluir_verba",
                         [{"severidade": "erro", "texto": f"Verba '{nome}' não encontrada no PJe-Calc.", "campo": None}])

    @staticmethod
    def _upload(p: Page, componente: str, nome_arquivo: str, conteudo: bytes) -> list[dict]:
        p.upload(componente, nome_arquivo, conteudo)
        return classificar(p.messages)

    @staticmethod
    def csv_historico(ocorrencias: list[dict], fgts: bool, inss: bool) -> bytes:
        """Arquivo no leiaute oficial (templateHistoricoSalarial/ExemploHistoricoSalarial.csv)."""
        linhas = ['"MES_ANO";"VALOR";"FGTS";"FGTS_REC.";"CONTRIBUICAO_SOCIAL";"CONTRIBUICAO_SOCIAL_REC."']
        sn = lambda b: "S" if b else "N"  # noqa: E731
        for o in ocorrencias:
            linhas.append(f'"{o["competencia"]}";"{o["valor"]}";"{sn(fgts)}";"{sn(o.get("fgtsRecolhido"))}";'
                          f'"{sn(inss)}";"{sn(o.get("inssRecolhido"))}"')
        return ("\r\n".join(linhas) + "\r\n").encode("iso-8859-1")

    def incluir_historico_ocorrencias(self, nome: str, ocorrencias: list[dict], fgts: bool, inss: bool) -> Resultado:
        """Cria um histórico e importa suas ocorrências mês a mês pelo CSV oficial da própria tela."""
        if not ocorrencias:
            return Resultado(False, "incluir_historico", [{"severidade": "erro", "campo": None,
                                                           "texto": f"Histórico '{nome}' sem ocorrências."}])
        p = self._menu("Histórico Salarial")
        p.click("incluir")
        p.set("nome", nome)
        return self._importar_no_historico(p, nome, ocorrencias, fgts, inss, "incluir_historico")

    def alterar_historico_ocorrencias(self, nome: str, ocorrencias: list[dict], fgts: bool, inss: bool) -> Resultado:
        """Substitui os valores mês a mês de um histórico existente pela ação "Alterar" + CSV oficial.

        O PJe-Calc não deixa excluir um histórico que é base de verba ("Registro possui vínculo"); a importação
        no modo Alterar troca as competências e mantém o vínculo com as verbas (verificado no 2.16.0).
        """
        if not ocorrencias:
            return Resultado(False, "alterar_historico", [{"severidade": "erro", "campo": None,
                                                           "texto": f"Histórico '{nome}' sem ocorrências."}])
        p = self._menu("Histórico Salarial")
        _, linhas = table(p.last_response, "formulario:listagem")
        i = next((i for i, ln in enumerate(linhas) if len(ln) > 1 and fold(ln[1]) == fold(nome)), None)
        acao = None if i is None else next((a.id for a in p.actions if (a.id or "").startswith(f"formulario:listagem:{i}:")
                                            and fold(a.text) == "alterar"), None)
        if not acao:
            return Resultado(False, "alterar_historico", [{"severidade": "erro", "campo": None,
                             "texto": f"Histórico '{nome}' não encontrado no PJe-Calc para alteração."}])
        p.click(acao)
        return self._importar_no_historico(p, nome, ocorrencias, fgts, inss, "alterar_historico")

    def _importar_no_historico(self, p: Page, nome: str, ocorrencias: list[dict], fgts: bool, inss: bool, operacao: str) -> Resultado:
        p.set("fgts", bool(fgts))
        p.set("inss", bool(inss))
        msgs = self._upload(p, "arquivo", "historico.csv", self.csv_historico(ocorrencias, fgts, inss))
        confirmar = next((a for a in p.actions if fold(a.text) == "confirmar" and a.id and "Importacao" not in a.id), None)
        if confirmar is None:
            return Resultado(False, operacao, msgs + [{"severidade": "erro", "campo": None,
                             "texto": "Botão Confirmar da importação de histórico não encontrado."}])
        p.click(confirmar.id)
        msgs += classificar(p.messages)
        if any(m["severidade"] == "erro" for m in msgs):
            p.click("cancelar")
            return Resultado(False, operacao, msgs, {"nome": nome})
        p.click("salvar")
        msgs += classificar(p.messages)
        return Resultado(_ok(msgs), operacao, msgs, {"nome": nome, "ocorrencias": len(ocorrencias)})

    def incluir_historico(self, h: dict) -> Resultado:
        """h: nome, competenciaInicial (MM/AAAA), competenciaFinal, valor, fgts, inss, variavel."""
        p = self._menu("Histórico Salarial")
        p.click("incluir")
        p.set("nome", h["nome"])
        p.set("tipoVariacaoDaParcela", "VARIAVEL" if h.get("variavel") else "FIXA")
        p.set("fgts", bool(h.get("fgts")))
        p.set("inss", bool(h.get("inss")))
        p.set("competenciaInicialInputDate", h["competenciaInicial"])
        p.set("competenciaFinalInputDate", h["competenciaFinal"])
        p.set("tipoValor", "INFORMADO")
        p.set("valorParaBaseDeCalculo", h["valor"])
        p.click("cmdGerarOcorrencias")
        gerar = classificar(p.messages)
        p.click("salvar")
        msgs = gerar + classificar(p.messages)
        return Resultado(_ok(msgs), "incluir_historico", msgs)

    # ------------------------------------------------------------------ verbas
    def verbas_expressas_disponiveis(self) -> list[str]:
        p = self._menu("Verbas")
        p.click("Expresso")
        nomes = [rotulo for _, rotulo in self._expressas(p)]
        self._menu("Verbas")
        return nomes

    @staticmethod
    def _expressas(p: Page) -> list[tuple[str, str]]:
        saida = []
        for name in p.fields:
            if name.endswith(":selecionada"):
                sid = name.replace(":selecionada", ":nome")
                saida.append((name, p.texts.get(sid, "")))
        return saida

    def incluir_verbas_expressas(self, nomes: list[str]) -> Resultado:
        p = self._menu("Verbas")
        p.click("Expresso")
        disponiveis = self._expressas(p)
        alvo = {fold(n) for n in nomes}
        marcadas, ausentes = [], set(alvo)
        for campo, rotulo in disponiveis:
            if fold(rotulo) in alvo:
                p.set(campo, True)
                marcadas.append(rotulo)
                ausentes.discard(fold(rotulo))
        if ausentes:
            p.click("cancelar")
            return Resultado(False, "incluir_verbas_expressas",
                             [{"severidade": "erro", "texto": "Verbas não disponíveis no lançamento expresso: "
                               + ", ".join(sorted(ausentes)), "campo": None}])
        p.click("salvar")
        msgs = classificar(p.messages)
        return Resultado(_ok(msgs), "incluir_verbas_expressas", msgs, {"incluidas": marcadas})

    def listar_verbas(self) -> list[dict]:
        p = self._menu("Verbas")
        return _verbas_da_pagina(p)

    def definir_reflexos(self, nome_verba: str, reflexos: dict[str, bool]) -> Resultado:
        """Marca/desmarca reflexos de uma verba principal (caixa "ativo" da tela Verbas)."""
        p = self._menu("Verbas")
        verba = next((v for v in _verbas_da_pagina(p) if fold(v["nome"]) == fold(nome_verba)), None)
        if not verba:
            return Resultado(False, "definir_reflexos", [{"severidade": "erro", "campo": None,
                                                         "texto": f"Verba '{nome_verba}' não encontrada no PJe-Calc."}])
        msgs, alterados, ausentes = [], [], []
        alvo = {fold(k): v for k, v in reflexos.items()}
        for r in verba["reflexos"]:
            if fold(r["nome"]) in alvo and bool(r["ativo"]) != alvo[fold(r["nome"])]:
                p.set(f"formulario:listagem:{verba['linha']}:listaReflexo:{r['indice']}:ativo", alvo[fold(r["nome"])])
                msgs += classificar(p.messages)
                alterados.append(r["nome"])
        conhecidos = {fold(r["nome"]) for r in verba["reflexos"]}
        ausentes = [k for k in reflexos if fold(k) not in conhecidos]
        if ausentes:
            msgs.append({"severidade": "erro", "campo": None,
                         "texto": "Reflexos não disponíveis para esta verba: " + ", ".join(ausentes)})
        # confere o estado gravado relendo a tela
        p = self._menu("Verbas")
        verba2 = next((v for v in _verbas_da_pagina(p) if fold(v["nome"]) == fold(nome_verba)), verba)
        divergentes = [r["nome"] for r in verba2["reflexos"]
                       if fold(r["nome"]) in alvo and bool(r["ativo"]) != alvo[fold(r["nome"])]]
        if divergentes:
            msgs.append({"severidade": "erro", "campo": None,
                         "texto": "O PJe-Calc não confirmou a alteração dos reflexos: " + ", ".join(divergentes)})
        ok = not divergentes and not ausentes and not any(m["severidade"] == "erro" for m in msgs)
        return Resultado(ok, "definir_reflexos", msgs, {"alterados": alterados, "reflexos": verba2["reflexos"]})

    def parametros_verba(self, linha: int) -> dict:
        """Lê o painel "Parâmetros da Verba" (todos os critérios, inclusive os não editáveis)."""
        p = self._menu("Verbas")
        verbas = _verbas_da_pagina(p)
        p.click(f"formulario:listagem:{linha}:" + self._acao_linha(p, linha, "Parâmetros da Verba"))
        campos = []
        for cid, rotulo, tipo in PARAMETROS_VERBA:
            if not p.has(cid):
                continue
            f = p.field(cid)
            grupo = p.fields[f.name]
            opcoes = f.options if tipo == "lista" else ([(g.value, g.value) for g in grupo] if f.type == "radio" else [])
            campos.append({"id": cid, "rotulo": rotulo, "tipo": tipo, "valor": p.get(cid),
                           "opcoes": [{"valor": v, "rotulo": r} for v, r in opcoes if not v.startswith("org.jboss")],
                           "editavel": not all(g.disabled for g in grupo)})
        _, linhas = table(p.last_response, "formulario:listagemHistoricosDaVerba")
        bases = [b for b in (next((c for c in ln if c), "") for ln in linhas) if b]
        formula = re.search(r'id="formulario:formulaVerba"[^>]*>([^<]*)<', p.last_response)
        nome = verbas[linha]["nome"] if linha < len(verbas) else p.get("descricao")
        p.click("cancelar")
        return {"linha": linha, "nome": nome, "campos": campos, "bases": bases or [],
                "formula": _unesc(formula.group(1)).strip() if formula else None}

    def alterar_verba(self, linha: int, alteracoes: dict, adicionar_bases: list[str] | None = None) -> Resultado:
        """Altera parâmetros de uma verba pela própria tela do PJe-Calc e salva."""
        p = self._menu("Verbas")
        p.click(f"formulario:listagem:{linha}:" + self._acao_linha(p, linha, "Parâmetros da Verba"))
        for cid, valor in alteracoes.items():
            p.set(cid, valor)
        msgs: list[dict] = []
        if adicionar_bases and not p.has("baseHistoricos"):
            base = dict(p.options("tipoDaBaseTabelada")).get(p.get("tipoDaBaseTabelada"), "") if p.has("tipoDaBaseTabelada") else ""
            p.click("cancelar")
            return Resultado(False, "alterar_verba", [{"severidade": "erro", "campo": None,
                             "texto": "Esta verba não admite histórico salarial como base"
                                      + (f" (base atual: {base})." if base else ".")}], {"linha": linha})
        for nome in adicionar_bases or []:
            p.set("baseHistoricos", nome)
            p.click("incluirBaseHistorico")
            msgs += classificar(p.messages)
        p.click("salvar")
        msgs += classificar(p.messages)
        return Resultado(_ok(msgs), "alterar_verba", msgs, {"linha": linha})

    def incluir_verba_manual(self, spec: dict) -> Resultado:
        """Inclui uma verba pelo lançamento "Manual" da tela Verbas e salva.

        spec: ids do painel de parâmetros (mesmos de PARAMETROS_VERBA, ex. "descricao", "valor",
        "tipoDaBaseTabelada", "outroValorDoDivisor") e, opcionalmente:
          "assuntoCnj": código CNJ; "bases": [históricos salariais];
          "basesVerbas": [{"verba": nome, "integralizar": "SIM"|"NAO"}] (verba como base de outra);
          "principal": nome da verba principal, quando tipoDeVerba = "REFLEXO" (vira a base do reflexo);
          "comportamentoDoReflexo", "periodoMediaReflexo", "tratamentoFracaoReflexo" (só para reflexos).
        Os campos são enviados na ordem da tela, porque cada escolha habilita ou oculta os seguintes.
        """
        p = self._menu("Verbas")
        assunto, erro = self._assunto(p, spec)
        if erro:
            return erro
        p.click("incluir")  # botão "Manual"
        if spec.get("tipoDeVerba"):
            p.set("tipoDeVerba", spec["tipoDeVerba"])  # Principal/Reflexa reorganiza o restante do painel
        return self._preencher_e_salvar(p, spec, assunto, nova=True, operacao="incluir_verba_manual")

    def alterar_reflexo_manual(self, principal: str, nome_completo: str, spec: dict) -> Resultado:
        """Altera um reflexo pela ação "Parametrizar" da tela Verbas (reativando-o, se estiver desativado)."""
        p = self._menu("Verbas")
        assunto, erro = self._assunto(p, spec)
        if erro:
            return erro
        verba = next((v for v in _verbas_da_pagina(p) if fold(v["nome"]) == fold(principal)), None)
        reflexo = next((r for r in (verba or {}).get("reflexos", []) if fold(r["nome"]) == fold(nome_completo)), None)
        if not reflexo:
            return Resultado(False, "alterar_reflexo_manual", [{"severidade": "erro", "campo": None, "texto":
                             f"Reflexo '{nome_completo}' não encontrado sob a verba {principal}."}])
        msgs: list[dict] = []
        pre = f"formulario:listagem:{verba['linha']}:listaReflexo:{reflexo['indice']}:"
        if not reflexo["ativo"]:
            p.set(pre + "ativo", True)
            msgs += classificar(p.messages)
        acao = next((a.id for a in p.actions if (a.id or "").startswith(pre) and fold(a.text) == "parametrizar"), None)
        if not acao:
            return Resultado(False, "alterar_reflexo_manual", msgs + [{"severidade": "erro", "campo": None, "texto":
                             f"Ação Parametrizar não disponível para o reflexo '{nome_completo}'."}])
        p.click(acao)
        spec = {k: x for k, x in spec.items() if k not in ("tipoDeVerba", "principal", "bases", "basesVerbas")}
        res = self._preencher_e_salvar(p, spec, assunto, nova=False, operacao="alterar_reflexo_manual")
        return Resultado(res.ok, res.operacao, msgs + res.mensagens, res.dados)

    def _assunto(self, p: Page, spec: dict) -> tuple[dict | None, Resultado | None]:
        if not spec.get("assuntoCnj"):
            return None, None
        codigo = str(spec["assuntoCnj"]).split("-")[0].strip()
        assunto = next((a for a in _assuntos_cnj(p.last_response) if a["codigo"] == codigo), None)
        if assunto is None:
            return None, Resultado(False, "incluir_verba_manual", [{"severidade": "erro", "campo": "assuntoCnj", "texto":
                                   f"Assunto CNJ {codigo} não consta da tabela de assuntos do PJe-Calc."}])
        return assunto, None

    def _preencher_e_salvar(self, p: Page, spec: dict, assunto: dict | None, nova: bool, operacao: str) -> Resultado:
        msgs: list[dict] = []

        def falhar(texto: str) -> Resultado:
            p.click("cancelar")  # não deixa o formulário pela metade na conversa do PJe-Calc
            return Resultado(False, operacao, msgs + [{"severidade": "erro", "campo": None, "texto": texto}])
        extras = {"bases", "assuntoCnj", "basesVerbas", "principal", "comportamentoDoReflexo",
                  "periodoMediaReflexo", "tratamentoFracaoReflexo"}
        desconhecidos = [k for k in spec if k not in extras and k not in {c for c, _, _ in PARAMETROS_VERBA}]
        ausentes = []
        for cid, _, _ in PARAMETROS_VERBA:
            if cid in spec and cid not in ("baseHistoricos", "tipoDeVerba"):
                if not p.has(cid):
                    ausentes.append(cid)
                    continue
                p.set(cid, spec[cid])
                p.blur(cid)  # o Nome só chega ao registro pelo evento de saída do campo
        if ausentes or desconhecidos:
            return falhar("Campos não disponíveis no lançamento manual: " + ", ".join(ausentes + desconhecidos))
        for nome in spec.get("bases") or []:
            if not p.has("baseHistoricos"):
                return falhar("Escolha a base de cálculo Histórico Salarial para adicionar históricos à verba.")
            p.set("baseHistoricos", nome)
            p.click("incluirBaseHistorico")
            msgs += classificar(p.messages)
        bases_verbas = list(spec.get("basesVerbas") or [])
        if spec.get("principal") and nova:
            bases_verbas.insert(0, {"verba": spec["principal"]})
        for b in bases_verbas:  # "Verba *" + "Adicionar Base"
            try:
                p.set("baseVerbaDeCalculo", b["verba"])
            except JsfError:
                return falhar(f"Verba '{b['verba']}' não está disponível como base no PJe-Calc.")
            if b.get("integralizar") and p.has("integralizarBase"):
                p.set("integralizarBase", b["integralizar"])
            p.click("incluirItemProp")
            msgs += classificar(p.messages)
        if spec.get("comportamentoDoReflexo"):
            if not p.has("comportamentoDoReflexo"):
                return falhar("Comportamento do reflexo indisponível: informe a verba principal do reflexo.")
            try:
                p.set("comportamentoDoReflexo", spec["comportamentoDoReflexo"])
            except JsfError:
                opcoes = [f.value for f in p.fields["formulario:comportamentoDoReflexo"]]
                return falhar(f"Comportamento {spec['comportamentoDoReflexo']} não é aceito pelo PJe-Calc para esta "
                              f"característica (opções: {', '.join(opcoes)}).")
        for chave in ("periodoMediaReflexo", "tratamentoFracaoReflexo"):
            if spec.get(chave):
                campo = _select_por_opcao(p, OPCOES_REFLEXO[chave], spec[chave])
                if not campo:
                    return falhar(f"Opção {spec[chave]} indisponível para {chave} nesta configuração do reflexo.")
                p.set(campo, spec[chave])
        if assunto:
            # o modal "Selecionar Assunto CNJ" apenas copia o código e o rótulo do nó escolhido para estes campos;
            # preenchidos por último porque as re-renderizações do painel os limpam
            p.set("codigoAssuntosCnj", assunto["codigo"], fire=False)
            p.set("assuntosCnj", f"{assunto['codigo']} - {assunto['nome']}", fire=False)
        nome_completo = p.get("nome") if p.has("nome") else None
        p.click("salvar")
        msgs += classificar(p.messages)
        ok = _ok(msgs)
        if not ok and any(a.id == "formulario:cancelar" for a in p.actions):
            p.click("cancelar")
        return Resultado(ok, operacao, msgs, {"nome": spec.get("descricao"), "nomeCompleto": nome_completo})

    def regerar_ocorrencias(self, principal: str, reflexo: str | None = None, manter_alteracoes: bool = True) -> Resultado:
        """Botão "Regerar" da tela Verbas para uma verba principal (ou um de seus reflexos).

        Depois de alterar parâmetros, o PJe-Calc mantém as ocorrências já geradas ("O parâmetro ... foi alterado
        após a geração das ocorrências") até que sejam regeradas. O padrão é "Manter alterações realizadas nas
        ocorrências": os parâmetros novos são aplicados e as células editadas à mão — inclusive na interface
        original do PJe-Calc — são preservadas (verificado no 2.16.0: multiplicador novo aplicado, quantidades e
        valor pago editados mantidos). "Sobrescrever" (manter_alteracoes=False) apagaria essas edições.
        """
        p = self._menu("Verbas")
        verba = next((v for v in _verbas_da_pagina(p) if fold(v["nome"]) == fold(principal)), None)
        if not verba:
            return Resultado(False, "regerar_ocorrencias", [{"severidade": "erro", "campo": None,
                             "texto": f"Verba '{principal}' não encontrada no PJe-Calc."}])
        if reflexo:
            r = next((x for x in verba["reflexos"] if fold(x["nome"]) == fold(reflexo)), None)
            pre = f"formulario:listagem:{verba['linha']}:listaReflexo:{r['indice'] if r else -1}:"
            marca = next((n for n, g in p.fields.items() if n.startswith(pre) and g[0].type == "checkbox"
                          and not n.endswith(":ativo")), None)
        else:
            marca = f"formulario:listagem:{verba['linha']}:verbaSelecionada"
        if not marca or not p.has(marca):
            return Resultado(False, "regerar_ocorrencias", [{"severidade": "erro", "campo": None,
                             "texto": f"Não foi possível selecionar '{reflexo or principal}' para regerar (reflexo inativo?)."}])
        p.set(marca, True)
        p.set("tipoRegeracao", "true" if manter_alteracoes else "false")
        p.set("manterAlteracoes", "true" if manter_alteracoes else "false", fire=False)  # o onclick do rádio faz isto
        p.click("regerarOcorrencias")
        msgs = classificar(p.messages)
        return Resultado(_ok(msgs), "regerar_ocorrencias", msgs, {"verba": reflexo or principal})

    def assuntos_cnj(self) -> list[dict]:
        """Tabela de assuntos CNJ do modal "Selecionar Assunto CNJ" da tela Verbas."""
        p = self._menu("Verbas")
        return _assuntos_cnj(p.last_response)

    # ------------------------------------------------------------------ ocorrências da verba
    def _abrir_ocorrencias(self, linha: int) -> Page:
        p = self._menu("Verbas")
        p.click(f"formulario:listagem:{linha}:" + self._acao_linha(p, linha, "Ocorrências da Verba"))
        return p

    def ler_ocorrencias(self, linha: int) -> dict:
        """Lê a grade "Ocorrências da Verba" (parametrizar-ocorrencia.xhtml) da verba principal da linha."""
        p = self._abrir_ocorrencias(linha)
        dados = {"linha": linha, "ocorrencias": _ocorrencias_da_pagina(p)}
        p.click("cancelar")
        return dados

    def gravar_ocorrencias(self, linha: int, ocorrencias: list[dict]) -> Resultado:
        """Altera ocorrências mês a mês e salva pela própria tela.

        ocorrencias: [{"competencia": "MM/AAAA", e qualquer de "ativo", "divisor", "multiplicador",
        "quantidade", "dobra", "devido", "pago"}]. Cada valor é digitado na célula correspondente e o
        evento de saída do campo é disparado, como no navegador (o PJe-Calc usa esse evento para
        abandonar a quantidade/valor integral e passar a usar o valor informado).
        """
        p = self._abrir_ocorrencias(linha)
        atuais = {o["competencia"]: o for o in _ocorrencias_da_pagina(p)}
        msgs: list[dict] = []
        ausentes = [o["competencia"] for o in ocorrencias if o.get("competencia") not in atuais]
        if ausentes:
            p.click("cancelar")
            return Resultado(False, "gravar_ocorrencias", [{"severidade": "erro", "campo": None, "texto":
                             "Competências fora do período da verba: " + ", ".join(ausentes)}], {"linha": linha})
        for o in ocorrencias:
            atual = atuais[o["competencia"]]
            pre = f"listagem:{atual['indice']}:"
            if "ativo" in o and bool(o["ativo"]) != atual["ativo"]:
                p.set(pre + "ativo", bool(o["ativo"]))  # reabilita/desabilita as demais células
            for chave, campo in OCORRENCIA_CAMPOS:
                if chave not in o or chave == "ativo" or not p.has(pre + campo):
                    continue
                if p.field(pre + campo).type == "checkbox":
                    p.set(pre + campo, bool(o[chave]))
                    continue
                if str(o[chave]) == str(atual.get(chave)):
                    continue
                p.set(pre + campo, o[chave])
                p.blur(pre + campo)
            msgs += classificar(p.messages)
        p.set("isAlteracaoEmLote", "true")  # o onclick do Salvar faz isto no navegador
        p.click("salvar")
        msgs += classificar(p.messages)
        ok = _ok(msgs)
        if not ok and any(a.id == "formulario:cancelar" for a in p.actions):
            p.click("cancelar")
        return Resultado(ok, "gravar_ocorrencias", msgs, {"linha": linha, "alteradas": len(ocorrencias)})

    # ------------------------------------------------------------------ telas de parâmetros (FGTS, atualização)
    @staticmethod
    def _ler_campos(p: Page, especificacao: list[tuple[str, str, str]]) -> list[dict]:
        campos = []
        for cid, rotulo, tipo in especificacao:
            if not p.has(cid):
                continue
            f = p.field(cid)
            grupo = p.fields[f.name]
            if f.type == "select":
                opcoes = [{"valor": v, "rotulo": r} for v, r in f.options if not v.startswith("org.jboss")]
            elif f.type == "radio":
                opcoes = [{"valor": g.value, "rotulo": p.labels.get(g.id or "", g.value)} for g in grupo]
            else:
                opcoes = []
            valor = p.get(cid)
            if isinstance(valor, str) and valor.startswith("org.jboss"):
                valor = ""
            campos.append({"id": cid, "rotulo": rotulo, "tipo": tipo, "valor": valor, "opcoes": opcoes,
                           "editavel": not all(g.disabled for g in grupo)})
        return campos

    def ler_fgts(self) -> dict:
        p = self._menu("FGTS")
        return {"campos": self._ler_campos(p, CAMPOS_FGTS)}

    def gravar_fgts(self, valores: dict) -> Resultado:
        p = self._menu("FGTS")
        for cid, _, _ in CAMPOS_FGTS:  # ordem da tela: a marcação da multa habilita os demais campos
            if cid in valores:
                p.set(cid, valores[cid])
        p.click("salvar")
        msgs = classificar(p.messages)
        return Resultado(_ok(msgs), "gravar_fgts", msgs)

    def ler_atualizacao(self) -> dict:
        p = self._menu("Correção, Juros e Multa")
        return {"campos": self._ler_campos(p, CAMPOS_ATUALIZACAO),
                "indicesCombinados": _linhas_span(p.last_response, "formulario:listagemIndicesCombinados"),
                "jurosCombinados": _linhas_span(p.last_response, "formulario:listagemJurosCombinados")}

    def gravar_atualizacao(self, valores: dict, juros_combinados: list[dict] | None = None,
                           indices_combinados: list[dict] | None = None) -> Resultado:
        """Grava a tela Correção, Juros e Multa. Combinações: [{"tabela": rótulo, "aPartirDe": "DD/MM/AAAA"}]."""
        p = self._menu("Correção, Juros e Multa")
        for cid, _, _ in CAMPOS_ATUALIZACAO:
            if cid in valores:
                p.set(cid, valores[cid])
        msgs: list[dict] = []
        for chave, combos, campo, data, botao in (
                ("juros", juros_combinados, "outroJuros", "apartirDeOutroJurosInputDate", "addOutroJuros"),
                ("indices", indices_combinados, "outroIndiceTrabalhista", "apartirDeOutroIndiceInputDate", "addOutroIndice")):
            if combos is None:
                continue
            span = "formulario:listagemJurosCombinados" if chave == "juros" else "formulario:listagemIndicesCombinados"
            tid = _tabela_no_span(p.text, span)
            # remove as combinações existentes: a cada exclusão as linhas são renumeradas a partir de 0
            for _ in range(len(_linhas_span(p.text, span)) if tid else 0):
                p.click(f"{tid}:0:excluirDep")
                msgs += classificar(p.messages)
            for c in combos:
                if not p.has(campo):
                    msgs.append({"severidade": "erro", "campo": campo, "texto":
                                 "Marque a opção de combinação antes de informar a tabela adicional."})
                    break
                p.set(campo, c["tabela"])
                p.set(data, c["aPartirDe"])
                p.click(botao)
                msgs += classificar(p.messages)
        p.click("salvar")
        msgs += classificar(p.messages)
        return Resultado(_ok(msgs), "gravar_atualizacao", msgs)

    # ------------------------------------------------------------------ liquidação, relatório, exportação
    def pendencias(self) -> Resultado:
        """Pendências apuradas pelo próprio PJe-Calc (tela Liquidar), com a verba citada quando houver."""
        p = self._menu("Liquidar")
        msgs = classificar(p.messages)
        for m in msgs:
            v = re.search(r"\bVerba\s+(.+?)\.?$", m["texto"])
            if v:
                m["verba"] = v.group(1).strip()
        return Resultado(not any(m["severidade"] == "erro" for m in msgs), "pendencias", msgs,
                         {"dataDeLiquidacao": p.get("dataDeLiquidacaoInputDate"),
                          "indicesAcumulados": p.get("indicesAcumulados")})

    def liquidar(self, data_liquidacao: str | None = None, indices_acumulados: str | None = None) -> Resultado:
        p = self._menu("Liquidar")
        if data_liquidacao:
            p.set("dataDeLiquidacaoInputDate", data_liquidacao)
        if indices_acumulados:
            p.set("indicesAcumulados", indices_acumulados)
        params = {"dataDeLiquidacao": p.get("dataDeLiquidacaoInputDate"), "indicesAcumulados": p.get("indicesAcumulados")}
        p.click("liquidar")
        msgs = classificar(p.messages)
        return Resultado(_ok(msgs), "liquidar", msgs, params)

    def relatorio(self, formato: str = "HTML") -> tuple[Resultado, bytes, str]:
        p = self._menu("Imprimir")
        p.set("formatoSaida", formato)
        p.click("imprimirConsolidado")
        msgs = classificar(p.messages)
        if "linkDownloadConsolidado" not in p.last_response:
            return Resultado(False, "relatorio", msgs or [{"severidade": "erro", "texto": "O PJe-Calc não gerou o relatório.", "campo": None}]), b"", ""
        r = p.download("linkDownloadConsolidado")
        return Resultado(True, "relatorio", msgs), r.body, r.headers.get("Content-Type", "")

    def exportar(self) -> tuple[Resultado, bytes, str]:
        p = self._menu("Exportar")
        p.click("exportar")
        msgs = classificar(p.messages)
        if "linkDownloadArquivo" not in p.last_response:
            return Resultado(False, "exportar", msgs or [{"severidade": "erro", "texto": "O PJe-Calc não disponibilizou o arquivo.", "campo": None}]), b"", ""
        r = p.download("linkDownloadArquivo")
        nome = _nome_arquivo(r.headers) or f"calculo_{self.calculo_id}.pjc"
        return Resultado(True, "exportar", msgs, {"arquivo": nome, "bytes": len(r.body)}), r.body, nome

    def importar(self, conteudo: bytes, nome_arquivo: str) -> Resultado:
        """Importa um .PJC pela tela oficial "Importar" (upload do RichFaces + botão Confirmar)."""
        p = self._inicio("Importar")
        msgs = self._upload(p, "arquivo", nome_arquivo, conteudo)
        p.click("confirmarImportacao")
        msgs += classificar(p.messages)
        ok = _ok(msgs) or (not any(m["severidade"] == "erro" for m in msgs) and "calculo.jsf" in p.url)
        novo = p.get("idCalculo") if p.has("idCalculo") else None
        if novo:
            self.calculo_id = novo
        return Resultado(ok and bool(novo), "importar", msgs, {"calculo_id": novo, "pagina": p.url})


def _nome_arquivo(headers: dict) -> str | None:
    cd = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    m = re.search(r'filename="?([^";]+)', cd)
    return urllib.parse.unquote(m.group(1)) if m else None


def _texto_simples(html_text: str) -> str:
    t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", html_text)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(html.unescape(t).split())


def _verbas_da_pagina(p: Page) -> list[dict]:
    """Verbas principais e reflexos da tela Verbas (verba-calculo.xhtml), na ordem exibida."""
    verbas: dict[int, dict] = {}
    for cid, texto in p.texts.items():
        m = re.fullmatch(r"formulario:listagem:(\d+):j_id\d+", cid)
        # células da linha: seleção (vazia), ações (vazia), nome, destinações ("Exibir")
        if m and texto and texto not in ("Exibir", "Ocultar"):
            verbas.setdefault(int(m.group(1)), {"linha": int(m.group(1)), "nome": texto, "reflexos": []})
    for cid, texto in p.texts.items():
        m = re.fullmatch(r"formulario:listagem:(\d+):listaReflexo:(\d+):j_id\d+", cid)
        if m and texto and int(m.group(1)) in verbas:
            ativo_id = f"formulario:listagem:{m.group(1)}:listaReflexo:{m.group(2)}:ativo"
            ref = verbas[int(m.group(1))]["reflexos"]
            if not any(r["indice"] == int(m.group(2)) for r in ref):
                ref.append({"indice": int(m.group(2)), "nome": texto,
                            "ativo": p.get(ativo_id) if p.has(ativo_id) else None})
    return [verbas[k] for k in sorted(verbas)]


# Células editáveis de cada linha da grade de ocorrências: chave da nova interface -> sufixo do id
OCORRENCIA_CAMPOS = [
    ("ativo", "ativo"), ("divisor", "termoDiv"), ("multiplicador", "termoMult"), ("quantidade", "termoQuant"),
    ("dobra", "dobra"), ("devido", "valorDevido"), ("pago", "valorPago"),
]


# Listas sem id estável no painel de reflexo (h:selectOneMenu sem id): reconhecidas pelas opções
OPCOES_REFLEXO = {
    "periodoMediaReflexo": {"ANO_CIVIL", "PERIODO_AQUISITIVO", "ULTIMOS_12_MESES", "ULTIMOS_DOZE_MESES"},
    "tratamentoFracaoReflexo": {"MANTER", "INTEGRALIZAR", "DESPREZAR", "DESPREZAR_MENOR_QUE_15_DIAS"},
}


def _select_por_opcao(p: Page, conhecidas: set[str], valor: str) -> str | None:
    for nome, grupo in p.fields.items():
        f = grupo[0]
        valores = {v for v, _ in f.options}
        if f.type == "select" and not f.disabled and valores & conhecidas and valor in valores:
            return nome
    return None


def _assuntos_cnj(html_text: str) -> list[dict]:
    """Nós da árvore formularioModalCNJ:arv (o id de cada nó é o caminho de códigos CNJ)."""
    saida = []
    for caminho, corpo in re.findall(r'id="formularioModalCNJ:arv:([\d:]+)::_defaultNodeFace:text"[^>]*>(.*?)</td>',
                                     html_text, re.S):
        texto = " ".join(_unesc(re.sub(r"<[^>]+>", " ", corpo)).split())
        codigo, _, nome = texto.partition(" - ")
        saida.append({"codigo": codigo.strip(), "nome": nome.strip(), "caminho": caminho.split(":")})
    return saida


def _ocorrencias_da_pagina(p: Page) -> list[dict]:
    """Linhas da grade principal "formulario:listagem" de parametrizar-ocorrencia.xhtml."""
    linhas: dict[int, dict] = {}
    for name, group in p.fields.items():
        m = re.fullmatch(r"formulario:listagem:(\d+):(\w+)", name)
        if not m:
            continue
        i, suf = int(m.group(1)), m.group(2)
        ln = linhas.setdefault(i, {"indice": i, "datas": []})
        if re.fullmatch(r"j_id\d+", suf):  # Data Inicial e Data Final (somente leitura)
            ln["datas"].append(group[0].value)
            continue
        for chave, campo in OCORRENCIA_CAMPOS:
            if suf == campo:
                ln[chave] = p.get(name)
                ln.setdefault("editavel", {})[chave] = not group[0].disabled
    saida = []
    for i in sorted(linhas):
        ln = linhas[i]
        datas = ln.pop("datas")
        if not datas:
            continue
        ln["dataInicial"], ln["dataFinal"] = datas[0], datas[-1]
        ln["competencia"] = datas[0][3:]  # dd/MM/aaaa -> MM/aaaa
        saida.append(ln)
    return saida


def _tabela_no_span(html_text: str, span_id: str) -> str | None:
    """Id da tabela renderizada dentro de <span id=span_id> (ex.: listagem de combinações)."""
    i = html_text.find(f'id="{span_id}"')
    if i < 0:
        return None
    m = re.match(r'[^>]*>\s*<table[^>]*id="([^"]+)"', html_text[i:i + 600])
    return m.group(1) if m else None


def _linhas_span(html_text: str, span_id: str) -> list[dict]:
    """Linhas (Índice/Tabela, A partir de) das combinações listadas dentro de um <span id=...>."""
    tid = _tabela_no_span(html_text, span_id)
    if not tid:
        return []
    _, linhas = table(html_text, tid)
    return [{"tabela": ln[1], "aPartirDe": ln[2]} for ln in linhas if len(ln) >= 3]


# Tela FGTS (fgts.xhtml), na ordem da tela
CAMPOS_FGTS = [
    ("tipoDeVerba", "Destino do FGTS", "opcao"),
    ("comporPrincipal", "Compor Principal", "opcao"),
    ("aliquota", "Alíquota", "opcao"),
    ("multa", "Multa", "marca"),
    ("tipoDoValorDaMulta", "Valor da Multa", "opcao"),
    ("multaDoFgts", "Percentual da Multa", "opcao"),
    ("incidenciaDoFgts", "Incidência", "lista"),
    ("excluirAvisoDaMulta", "Excluir da Base da Multa o valor de FGTS sobre Aviso Prévio", "marca"),
    ("multaDoArtigo467", "Multa do artigo 467 da CLT", "marca"),
    ("multa10", "Contribuição Social 10%", "marca"),
    ("contribuiçãoSocial", "Contribuição Social 0,5%", "marca"),
    ("incidenciaPensaoAlimenticia", "Pensão Alimentícia sobre FGTS", "marca"),
    ("deduzirDoFGTS", "Deduzir do FGTS", "marca"),
]

# Tela Correção, Juros e Multa (parametros-atualizacao.xhtml) — aba Dados Gerais
CAMPOS_ATUALIZACAO = [
    ("indiceTrabalhista", "Índice Trabalhista", "lista"),
    ("combinarOutroIndice", "Combinar com Outro Índice", "marca"),
    ("ignorarTaxaNegativa", "Ignorar Taxa Negativa para Índice(s) selecionado(s)", "marca"),
    ("aplicarJurosFasePreJudicial", "Aplicar Juros na Fase Pré-Judicial", "marca"),
    ("juros", "Tabela de Juros", "lista"),
    ("combinarOutroJuros", "Combinar com Outra Tabela de Juros", "marca"),
    ("baseDeJurosDasVerbas", "Bases de Juros", "lista"),
    ("indiceDeCorrecaoDoFGTS", "Índice de Correção do FGTS", "opcao"),
    ("correcaoDasCustas", "Custas: Correção", "marca"),
    ("jurosDeCustas", "Custas: Juros", "marca"),
    ("correcaoLei11941", "Contribuição Social: Lei nº 11.941/2009", "marca"),
    ("correcaoTrabalhistaDosSalariosDevidosDoINSS", "Contribuição Social (salários devidos): Correção trabalhista", "marca"),
    ("jurosTrabalhistasDosSalariosDevidosDoINSS", "Contribuição Social (salários devidos): Juros trabalhistas", "marca"),
    ("correcaoPrevidenciariaDosSalariosDevidosDoINSS", "Contribuição Social (salários devidos): Correção previdenciária", "marca"),
    ("jurosPrevidenciariosDosSalariosDevidosDoINSS", "Contribuição Social (salários devidos): Juros previdenciários", "marca"),
    ("aplicarMultaDosSalariosDevidosDoINSS", "Contribuição Social (salários devidos): Multa previdenciária", "marca"),
]

# Painel "Parâmetros da Verba" (verba-calculo.xhtml): id do componente, rótulo oficial, tipo
PARAMETROS_VERBA = [
    ("descricao", "Descrição", "texto"),
    ("assuntosCnj", "Assunto CNJ", "texto"),
    ("tipoVariacaoDaParcela", "Parcela", "opcao"),
    ("valor", "Valor", "opcao"),
    ("irpf", "Incidência: Imposto de Renda", "marca"),
    ("inss", "Incidência: Contribuição Social", "marca"),
    ("fgts", "Incidência: FGTS", "marca"),
    ("previdenciaPrivada", "Incidência: Previdência Privada", "marca"),
    ("pensaoAlimenticia", "Incidência: Pensão Alimentícia", "marca"),
    ("caracteristicaVerba", "Característica", "opcao"),
    ("ocorrenciaPagto", "Ocorrência de Pagamento", "opcao"),
    ("ocorrenciaAjuizamento", "Juros a partir do Ajuizamento", "opcao"),
    ("tipoDeVerba", "Tipo", "opcao"),
    ("geraReflexo", "Gera Reflexo", "opcao"),
    ("gerarPrincipal", "Gera Principal", "opcao"),
    ("comporPrincipal", "Compor Principal", "opcao"),
    ("zeraValorNegativo", "Zerar Valor Negativo", "marca"),
    ("periodoInicialInputDate", "Período: início", "data"),
    ("periodoFinalInputDate", "Período: fim", "data"),
    ("dobraValorDevido", "Dobrar Valor Devido", "marca"),
    ("tipoDaBaseTabelada", "Base de Cálculo", "lista"),
    ("baseHistoricos", "Histórico Salarial a adicionar à base", "lista"),
    ("proporcionalizaHistorico", "Proporcionalizar", "lista"),
    ("baseVerbaDeCalculo", "Verba como base", "lista"),
    ("integralizarBase", "Integralizar", "lista"),
    ("tipoDeDivisor", "Divisor", "opcao"),
    ("outroValorDoDivisor", "Divisor: valor", "valor"),
    ("outroValorDoMultiplicador", "Multiplicador", "valor"),
    ("tipoDaQuantidade", "Quantidade", "opcao"),
    ("valorInformadoDaQuantidade", "Quantidade: valor informado", "valor"),
    ("tipoDoValorPago", "Valor Pago", "opcao"),
    ("valorInformadoPago", "Valor Pago: valor informado", "valor"),
    ("comentarios", "Comentários", "texto"),
]
