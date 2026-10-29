"""Telas do PJe-Calc com o visual do Studio.

Cada tela oficial (Faltas, Férias, Honorários, Tabelas…) é aberta numa sessão própria do PJe-Calc, lida e
descrita como dados — grupos, abas, campos, tabelas e ações —, que a interface do Studio desenha com o seu
próprio visual. Cada valor digitado e cada botão acionado voltam por esta sessão para a mesma tela oficial:
quem valida, grava e calcula continua sendo o PJe-Calc. Nada é gravado no banco nem reimplementado.

Descrição devolvida por SessaoTela.descrever():
  {"titulo", "url", "mensagens": [...], "itens": [item...], "arquivo": {...} | None}
  item = {"t": "grupo", "titulo", "aba": bool, "itens": [...]}
       | {"t": "campo", "nome", "tipo": texto|data|lista|radio|marca|area|arquivo|senha, "rotulo", "valor",
          "opcoes": [{"valor", "rotulo"}], "desabilitado": bool, "evento": bool}
       | {"t": "texto", "texto"}
       | {"t": "tabela", "id", "colunas": [str], "linhas": [{"celulas": [{"texto", "campos", "acoes"}]}]}
       | {"t": "acao", "id", "texto", "confirmar": str | None}
       | {"t": "link", "texto", "href"}
"""
from __future__ import annotations

import html
import re
import secrets
import threading
import time
from html.parser import HTMLParser

from .jsf import Field, JsfError, Page, fold
from .pjecalc import PJeCalc, classificar

_ESTILO_OCULTO = re.compile(r"display\s*:\s*none", re.I)
_CONFIRMAR = re.compile(r"confirm\(\s*'((?:[^'\\]|\\.)*)'")
_VAZIOS = {"", ":", "*", "-", "|", "»", ">"}
_SEM_FECHAMENTO = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}


def _limpo(s: str) -> str:
    return " ".join(html.unescape(s or "").split())


class _Leitor(HTMLParser):
    """Percorre a área de conteúdo (div#contentPrincipal) da página e monta a árvore de itens."""

    def __init__(self, abas: dict[str, str]):
        super().__init__(convert_charrefs=True)
        self.abas = abas  # id do painel da aba -> título
        self.raiz = {"t": "grupo", "titulo": None, "aba": False, "itens": []}
        self.titulo = ""
        self.ativo = False
        self.pilha: list[dict] = []  # elementos abertos: {"tag", "oculto", "grupo", "tabela", "titulo"}
        self.grupos = [self.raiz]
        self.texto: list[str] = []
        self.legenda: list[str] | None = None
        self.rotulo: dict | None = None  # <label> em leitura: {"for", "partes"}
        self.rotulos: dict[str, str] = {}
        self.rotulo_pendente: str | None = None
        self.select: dict | None = None
        self.opcao: list | None = None
        self.textarea: dict | None = None
        self.link: dict | None = None
        self.em_script = 0
        self.em_titulo = 0
        self.tabelas: list[dict] = []  # tabelas de dados (rich-table) abertas
        self.ocultos = 0
        self.ignorados = 0  # cabeçalhos de aba (viram as abas do Studio)
        self.dica: dict | None = None  # rich:toolTip em leitura: {"id", "partes"}
        self.dicas: dict[str, str] = {}  # id do tooltip -> texto
        self.paginacao: dict | None = None  # rich:datascroller em leitura
        self.pagina: dict | None = None  # botão de página (célula) em leitura

    # -------------------------------------------------------------------- auxiliares
    @property
    def destino(self) -> list:
        """Lista onde entram os itens agora: a célula da tabela aberta ou o grupo atual."""
        if self.tabelas and self.tabelas[-1]["celula"] is not None:
            return self.tabelas[-1]["celula"]["itens"]
        return self.grupos[-1]["itens"]

    def _descarregar_texto(self):
        t = _limpo(" ".join(self.texto))
        self.texto = []
        if t in _VAZIOS or self.ocultos:
            return
        if self.tabelas and self.tabelas[-1]["celula"] is not None:
            cel = self.tabelas[-1]["celula"]
            cel["texto"] = (cel["texto"] + " " + t).strip()
        elif not self.tabelas:
            self.destino.append({"t": "texto", "texto": t})

    def _campo(self, item: dict):
        self._descarregar_texto()
        if self.rotulo_pendente and not item.get("rotulo"):
            item["rotulo"] = self.rotulo_pendente
        self.rotulo_pendente = None
        self.destino.append(item)

    # -------------------------------------------------------------------- eventos do parser
    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if not self.ativo:
            if a.get("id") == "contentPrincipal":
                self.ativo = True
            return
        if tag in ("script", "style"):
            self.em_script += 1
            return
        if self.em_script:
            return
        cls = a.get("class", "")
        if "textoTitulo" in cls:
            self.em_titulo += 1
        el = {"tag": tag, "oculto": False, "grupo": False, "tabela": False, "ignorar": False, "dica": False, "paginacao": False}
        if tag not in _SEM_FECHAMENTO:
            if "rich-tabhdr-side-cell" in cls or "rich-tab-header" in cls:
                el["ignorar"] = True
                self.ignorados += 1
            elif "rich-tool-tip" in cls and self.dica is None:
                el["dica"] = True
                self.dica = {"id": a.get("id"), "partes": []}
        if self.ignorados or self.dica is not None:
            if tag not in _SEM_FECHAMENTO:
                self.pilha.append(el)
            return
        if self.paginacao is not None:  # rich:datascroller: só interessam os botões de página
            self._pagina(tag, a, cls, el)
            return
        if tag == "div" and "rich-datascr" in cls.split() and a.get("id"):
            self._descarregar_texto()
            self.paginacao = {"t": "paginas", "id": a["id"], "paginas": []}
            self.destino.append(self.paginacao)
            el["paginacao"] = True
            self.pilha.append(el)
            return
        # painel de aba: as abas trocadas no navegador vêm todas na página (as inativas com display:none) e viram
        # abas do Studio; as trocadas no servidor só trazem a ativa e viram uma barra de abas que aciona o PJe-Calc
        aba = self.abas.get(a.get("id")) if a.get("role") == "tabpanel" else None
        vazio = tag in _SEM_FECHAMENTO
        if _ESTILO_OCULTO.search(a.get("style", "")) and not aba and not vazio:
            el["oculto"] = True
            self.ocultos += 1
        if tag in ("div", "p", "br", "tr", "td", "th", "li", "fieldset", "table", "legend", "ul", "h1", "h2", "h3"):
            self._descarregar_texto()
        if aba:
            if aba["servidor"]:
                self.destino.append({"t": "abas", "abas": [{"id": k, "titulo": v["titulo"], "ativa": k == a["id"]}
                                                           for k, v in self.abas.items() if v["painel"] == aba["painel"]]})
                g = {"t": "grupo", "titulo": None, "aba": False, "itens": []}
            else:
                g = {"t": "grupo", "titulo": aba["titulo"], "aba": True, "itens": []}
            self.destino.append(g)
            self.grupos.append(g)
            el["grupo"] = True
        elif tag == "fieldset" or "rich-panel" in cls.split():
            g = {"t": "grupo", "titulo": None, "aba": False, "itens": []}
            if not self.ocultos:
                self.destino.append(g)
            self.grupos.append(g)
            el["grupo"] = True
        elif tag == "legend" or "rich-panel-header" in cls.split():
            self.legenda = []
        if tag == "table" and "rich-table" in cls.split():
            if self.tabelas and self.tabelas[-1]["celula"] is not None:
                self.tabelas[-1]["aninhadas"] += 1  # tabela dentro de célula: conteúdo vai para a célula
            else:
                tb = {"t": "tabela", "id": a.get("id"), "colunas": [], "linhas": [], "linha": None, "celula": None,
                      "cabecalho": False, "aninhadas": 0}
                if not self.ocultos:
                    self.destino.append(tb)
                self.tabelas.append(tb)
                el["tabela"] = True
        elif self.tabelas and not self.tabelas[-1]["aninhadas"]:
            tb = self.tabelas[-1]
            if tag == "thead":
                tb["cabecalho"] = True
            elif tag == "tr":
                tb["linha"] = {"celulas": []} if not tb["cabecalho"] else None
            elif tag in ("td", "th"):
                if tb["cabecalho"] or tag == "th" and tb["linha"] is None:
                    tb["celula"] = {"texto": "", "itens": [], "cab": True}
                elif tb["linha"] is not None:
                    tb["celula"] = {"texto": "", "itens": []}
        if tag == "label":
            self.rotulo = {"for": a.get("for"), "partes": []}
        elif tag == "input":
            self._input(a)
        elif tag == "select" and a.get("name"):
            self.select = {"t": "campo", "nome": a["name"], "tipo": "lista", "rotulo": None, "opcoes": [],
                           "id": a.get("id")}
        elif tag == "option" and self.select is not None:
            self.opcao = [a.get("value"), []]
        elif tag == "textarea" and a.get("name"):
            self.textarea = {"t": "campo", "nome": a["name"], "tipo": "area", "rotulo": None, "id": a.get("id")}
        elif tag == "a":
            self._descarregar_texto()
            self.link = {"id": a.get("id"), "onclick": a.get("onclick", ""), "href": a.get("href", ""),
                         "titulo": a.get("title", ""), "partes": []}
        elif tag == "img" and self.link is not None and not self.link["titulo"]:
            self.link["titulo"] = a.get("title") or a.get("alt") or ""
        if not vazio:
            self.pilha.append(el)

    def _pagina(self, tag: str, a: dict, cls: str, el: dict):
        if tag == "td":
            alvo = re.search(r"'page':\s*'([^']+)'", a.get("onclick", ""))
            atual = "rich-datascr-act" in cls
            self.pagina = {"pagina": alvo.group(1) if alvo else None, "atual": atual, "partes": [],
                           "desabilitado": "dsbld" in cls or not (alvo or atual)}
        elif tag == "img" and self.pagina is not None:
            self.pagina["partes"].append(a.get("title") or a.get("alt") or "")
        if tag not in _SEM_FECHAMENTO:
            self.pilha.append(el)

    def _input(self, a: dict):
        tipo = a.get("type", "text").lower()
        if self.ocultos or tipo == "hidden":
            return
        if tipo in ("submit", "button", "image", "reset"):
            texto = a.get("value") or a.get("title") or a.get("alt") or ""
            ident = a.get("id") or a.get("name")
            if ident and texto and tipo != "reset":
                self._descarregar_texto()
                self.destino.append({"t": "acao", "id": ident, "texto": _limpo(texto),
                                     "confirmar": _confirmacao(a.get("onclick", ""))})
            return
        if not a.get("name"):
            return
        nome = a["name"]
        if tipo == "radio":
            for item in reversed(self.destino):
                if item.get("t") == "campo" and item["nome"] == nome:
                    item["opcoes"].append({"valor": a.get("value", ""), "id": a.get("id")})
                    return
            self._campo({"t": "campo", "nome": nome, "tipo": "radio", "rotulo": None, "id": a.get("id"),
                         "opcoes": [{"valor": a.get("value", ""), "id": a.get("id")}]})
            return
        tipos = {"checkbox": "marca", "file": "arquivo", "password": "senha"}
        t = "data" if nome.endswith("InputDate") else tipos.get(tipo, "texto")
        self._campo({"t": "campo", "nome": nome, "tipo": t, "rotulo": None, "id": a.get("id")})

    def handle_endtag(self, tag):
        if not self.ativo:
            return
        if tag in ("script", "style"):
            self.em_script = max(0, self.em_script - 1)
            return
        if self.em_script:
            return
        if self.paginacao is not None:
            if tag == "td" and self.pagina is not None:
                pg, self.pagina = self.pagina, None
                texto = _limpo(" ".join(pg.pop("partes")))
                if texto:
                    self.paginacao["paginas"].append({"texto": texto, **pg})
            while self.pilha and any(el["tag"] == tag for el in self.pilha):
                el = self.pilha.pop()
                if el["paginacao"]:
                    self.paginacao = None
                if el["tag"] == tag:
                    break
            return
        if tag == "label" and self.rotulo is not None:
            texto = _limpo(" ".join(self.rotulo["partes"])).rstrip(":").strip()
            if self.rotulo["for"]:
                self.rotulos[self.rotulo["for"]] = texto
                # caixa de marcação seguida do próprio rótulo (às vezes com "for" apontando outro campo)
                ultimo = self.destino[-1] if self.destino else None
                if ultimo and ultimo.get("t") == "campo" and ultimo["tipo"] == "marca" and "rotulo_seguinte" not in ultimo:
                    ultimo["rotulo_seguinte"] = texto
            elif texto:
                self.rotulo_pendente = texto
            self.rotulo = None
        elif tag == "option" and self.opcao is not None and self.select is not None:
            valor, partes = self.opcao
            rot = _limpo(" ".join(partes))
            self.select["opcoes"].append({"valor": rot if valor is None else valor, "rotulo": rot})
            self.opcao = None
        elif tag == "select" and self.select is not None:
            if not self.ocultos:
                self._campo(self.select)
            self.select = None
        elif tag == "textarea" and self.textarea is not None:
            if not self.ocultos:
                self._campo(self.textarea)
            self.textarea = None
        elif tag == "a" and self.link is not None:
            self._fechar_link()
        if tag == "legend" and self.legenda is not None:
            self._titulo_grupo()
        if tag in ("div", "p", "td", "th", "tr", "li", "fieldset", "table"):
            self._descarregar_texto()
        # desempilha até o elemento correspondente (o HTML gerado pode omitir fechamentos); fechamento sem
        # abertura (ex.: <br />, <input />, que o HTMLParser também entrega como fechamento) é ignorado
        while self.pilha and any(el["tag"] == tag for el in self.pilha):
            el = self.pilha.pop()
            if el["ignorar"]:
                self.ignorados -= 1
            if el["dica"] and self.dica is not None:
                if self.dica["id"]:
                    self.dicas[self.dica["id"]] = _limpo(" ".join(self.dica["partes"]))
                self.dica = None
            if el["oculto"]:
                self.ocultos -= 1
            if el["grupo"] and len(self.grupos) > 1:
                self.grupos.pop()
            if el["tabela"]:
                tb = self.tabelas.pop()
                for k in ("linha", "celula", "cabecalho", "aninhadas"):
                    tb.pop(k, None)
            if el["tag"] in ("td", "th") and self.tabelas and not self.tabelas[-1]["aninhadas"]:
                self._fechar_celula()
            if el["tag"] == "tr" and self.tabelas and not self.tabelas[-1]["aninhadas"]:
                tb = self.tabelas[-1]
                if tb["linha"] is not None and tb["linha"]["celulas"]:
                    tb["linhas"].append(tb["linha"])
                tb["linha"] = None
            if el["tag"] == "thead" and self.tabelas:
                self.tabelas[-1]["cabecalho"] = False
            if el["tag"] == "table" and self.tabelas and self.tabelas[-1]["aninhadas"] and not el["tabela"]:
                self.tabelas[-1]["aninhadas"] -= 1
            if el["tag"] == tag:
                break
        if tag == "div" and self.legenda is not None:
            self._titulo_grupo()
        if self.em_titulo and tag == "span":
            self.em_titulo -= 1

    def _titulo_grupo(self):
        titulo = _limpo(" ".join(self.legenda or [])).rstrip("*").rstrip(": ").strip()
        self.legenda = None
        if titulo and self.grupos[-1] is not self.raiz and not self.grupos[-1]["titulo"]:
            self.grupos[-1]["titulo"] = titulo

    def _fechar_celula(self):
        tb = self.tabelas[-1]
        cel = tb["celula"]
        if cel is None:
            return
        self._descarregar_texto()
        tb["celula"] = None
        if cel.pop("cab", False):
            tb["colunas"].append(cel["texto"])
        elif tb["linha"] is not None:
            tb["linha"]["celulas"].append({"texto": cel["texto"],
                                           "campos": [i for i in cel["itens"] if i["t"] == "campo"],
                                           "acoes": [i for i in cel["itens"] if i["t"] == "acao"]})

    def _fechar_link(self):
        lk, self.link = self.link, None
        texto = _limpo(" ".join(lk["partes"])) or _limpo(lk["titulo"])
        if self.ocultos or not texto:
            return
        clica = "A4J.AJAX.Submit" in lk["onclick"] or "jsfcljs" in lk["onclick"]
        if clica and lk["id"]:
            self.destino.append({"t": "acao", "id": lk["id"], "texto": texto, "dica": _limpo(lk["titulo"]) or None,
                                 "confirmar": _confirmacao(lk["onclick"])})
        elif lk["href"] and not lk["href"].startswith(("#", "javascript")) and not lk["onclick"]:
            self.destino.append({"t": "link", "texto": texto, "href": lk["href"]})

    def handle_data(self, data):
        if not self.ativo or self.em_script:
            return
        if self.em_titulo:
            self.titulo += data
            return
        if self.dica is not None:
            self.dica["partes"].append(data)
            return
        if self.paginacao is not None:
            if self.pagina is not None:
                self.pagina["partes"].append(data)
            return
        if self.ignorados:
            return
        if self.opcao is not None:
            self.opcao[1].append(data)
            return
        if self.textarea is not None:
            return
        if self.link is not None:
            self.link["partes"].append(data)
            return
        if self.rotulo is not None:
            self.rotulo["partes"].append(data)
            return
        if self.legenda is not None:
            self.legenda.append(data)
            return
        if self.tabelas and self.tabelas[-1]["celula"] is None:
            return  # texto solto entre células (espaços)
        self.texto.append(data)


def _confirmacao(onclick: str) -> str | None:
    m = _CONFIRMAR.search(onclick or "")
    return _limpo(m.group(1).replace("\\'", "'").replace("\\n", " ")) if m else None


def _abas(dom: str) -> dict[str, dict]:
    """Abas do RichFaces: id do painel da aba -> {"titulo", "servidor", "painel"}.

    "servidor": a troca de aba envia o formulário (switchType="server"), e só a aba ativa vem na página.
    "painel": o rich:tabPanel que reúne as abas irmãs."""
    rotulos = {}
    for m in re.finditer(r"<td\b([^>]*\bclass=\"rich-tab-header[^>]*)>(.*?)</td>", dom, re.S):
        ident = re.search(r'\bid="([^"]+)_lbl"', m.group(1))
        if ident:
            rotulos[ident.group(1)] = _limpo(re.sub(r"<[^>]+>", " ", m.group(2)))
    abas = {}
    for m in re.finditer(r'<table[^>]*\bid="([^"]+)_shifted"[^>]*role="tab"[^>]*>', dom):
        clique = re.search(r'onclick="([^"]*)"', m.group(0))
        clique = html.unescape(clique.group(1)) if clique else ""
        painel = re.search(r"onTabChange\(event,\s*'([^']+)'", clique)
        abas[m.group(1)] = {"titulo": rotulos.get(m.group(1), ""), "servidor": "_server_submit" in clique,
                            "painel": painel.group(1) if painel else None}
    return abas


def descrever_pagina(p: Page) -> dict:
    """Descreve a página atual (p.dom) para a interface do Studio, com os valores atuais de p.fields."""
    leitor = _Leitor(_abas(p.dom))
    leitor.feed(p.dom)
    leitor.close()
    rotulos = {**p.labels, **leitor.rotulos}
    # textos de ajuda oficiais: new ToolTip("<id do tooltip>", "<campo>Help") liga o texto ao campo
    ajuda = {alvo.removesuffix("Help"): leitor.dicas[tid]
             for tid, alvo in re.findall(r'new ToolTip\("([^"]+)",\s*"([^"]+)"', p.dom)
             if alvo.endswith("Help") and leitor.dicas.get(tid)}
    # erro de validação de um campo: <a id="<campo>Erro" class="linkErro"> com a rich:message dentro
    erros = {}
    for m in re.finditer(r'<a id="([^"]+)Erro"[^>]*class="linkErro"', p.dom):
        trecho = p.dom[m.end():m.end() + 1500]
        t = re.search(r'class="rich-message-label">([^<]+)<', trecho)
        if t and _limpo(t.group(1)):
            erros[m.group(1)] = _limpo(t.group(1))

    def rotulo_de(ident: str | None, nome: str) -> str | None:
        for chave in (ident, nome, (ident or "").removesuffix("InputDate"), nome.removesuffix("InputDate")):
            if chave and chave in rotulos:
                return rotulos[chave]
        sufixo = nome.split(":")[-1].removesuffix("InputDate")
        return next((v for k, v in rotulos.items() if k.split(":")[-1] == sufixo), None)

    def completar(itens: list, titulo_grupo: str | None = None) -> list:
        saida = []
        unico = sum(1 for i in itens if i["t"] == "campo") == 1
        for item in itens:
            if item["t"] == "grupo":
                item["itens"] = completar(item["itens"], item["titulo"])
                if item["itens"]:
                    saida.append(item)
                continue
            if item["t"] == "tabela":
                for ln in item["linhas"]:
                    for cel in ln["celulas"]:
                        cel["campos"] = [c for c in (_valores(p, c, rotulo_de) for c in cel["campos"]) if c]
                if item["linhas"] or item["colunas"]:
                    saida.append(item)
                continue
            if (item["t"] == "texto" and saida and saida[-1]["t"] == "campo" and saida[-1]["tipo"] == "marca"
                    and not saida[-1].get("rotulo") and len(item["texto"]) <= 60):
                saida[-1]["rotulo"] = item["texto"]  # caixa de marcação seguida de um texto simples (sem <label>)
                _obrigatorio(saida[-1])
                continue
            if item["t"] == "campo":
                seguinte = item.get("rotulo_seguinte")
                item = _valores(p, item, rotulo_de)
                if not item:
                    continue
                if item["tipo"] == "marca" and seguinte and (not item["rotulo"] or item["rotulo"] == titulo_grupo):
                    item["rotulo"] = seguinte
                # rótulo escrito como texto logo antes do campo (h:outputText em vez de <label>)
                if not item.get("rotulo") and saida and saida[-1]["t"] == "texto" and len(saida[-1]["texto"]) <= 60:
                    item["rotulo"] = saida.pop()["texto"].rstrip(":").strip()
                if not item.get("rotulo") and unico and titulo_grupo:
                    item["rotulo"] = titulo_grupo  # campo único do grupo: a legenda é o rótulo (ex.: rádios)
                _obrigatorio(item)
                item["ajuda"] = ajuda.get(item["nome"].removesuffix("InputDate"))
                item["erro"] = erros.get(item["nome"].removesuffix("InputDate"))
            saida.append(item)
        return saida

    itens = completar(leitor.raiz["itens"])
    titulo = _limpo(leitor.titulo)
    return {"titulo": titulo, "itens": itens, "mensagens": classificar(p.messages)}


def _sem_selecao(valor) -> bool:
    return isinstance(valor, str) and valor.startswith("org.jboss.seam.ui.NoSelectionConverter")


def _obrigatorio(item: dict):
    """O PJe-Calc marca campos obrigatórios com "*" no rótulo: vira um atributo e sai do texto."""
    rot = (item.get("rotulo") or "").strip(" |")  # "|" separa campos lado a lado em algumas telas
    item["obrigatorio"] = item.get("obrigatorio") or rot.endswith("*")
    item["rotulo"] = rot.rstrip("*").rstrip(": |").strip() or None


def _valores(p: Page, item: dict, rotulo_de) -> dict | None:
    """Completa o campo com valor, opções e estado lidos do formulário (inclui o que já foi digitado)."""
    nome = item["nome"]
    grupo: list[Field] = p.fields.get(nome) or []
    if not grupo and item["tipo"] != "arquivo":
        return None
    f0 = grupo[0] if grupo else None
    saida = {"t": "campo", "nome": nome, "tipo": item["tipo"], "rotulo": item.get("rotulo") or rotulo_de(item.get("id"), nome),
             "desabilitado": bool(f0 and all(f.disabled for f in grupo)), "evento": False}
    if f0:
        saida["evento"] = any("A4J.AJAX.Submit" in (f.onchange or "") + (f.onclick or "") + (f.onblur or "") for f in grupo)
        saida["valor"] = p.get(nome)
    if item["tipo"] == "lista" and f0:
        # a opção "sem seleção" do Seam (valor org.jboss…) vira "" para a interface; _para_pagina faz o caminho inverso
        saida["opcoes"] = [{"valor": "" if _sem_selecao(v) else v, "rotulo": r or ("Selecione…" if _sem_selecao(v) or not v else r)}
                           for v, r in f0.options]
        if _sem_selecao(saida["valor"]):
            saida["valor"] = ""
        if saida["valor"] not in [o["valor"] for o in saida["opcoes"]]:
            saida["opcoes"].insert(0, {"valor": saida["valor"] or "", "rotulo": "Selecione…"})
    elif item["tipo"] == "radio":
        saida["opcoes"] = [{"valor": o["valor"], "rotulo": p.labels.get(o["id"] or "") or rotulo_de(o["id"], o["id"] or "") or o["valor"]}
                           for o in item["opcoes"]]
        if saida["rotulo"] and saida["rotulo"] in [o["rotulo"] for o in saida["opcoes"]]:
            saida["rotulo"] = rotulo_de(nome, nome) if rotulo_de(nome, nome) not in [o["rotulo"] for o in saida["opcoes"]] else None
    return saida


# ======================================================================== sessões
class SessaoTela:
    """Uma tela oficial aberta para o Studio: sessão própria do PJe-Calc (cookies e conversa JSF)."""

    def __init__(self, url: str, calculo_id: str | None, menu: str):
        self.token = secrets.token_urlsafe(12)
        self.url, self.calculo_id, self.menu = url, calculo_id, menu
        self.m = PJeCalc(url, timeout=600)
        self.lock = threading.Lock()
        self.usada = time.monotonic()
        self.arquivo = None
        self.caso: str | None = None  # cálculo do Studio ligado (para avisar que o resultado pode mudar)

    def abrir(self) -> dict:
        if self.calculo_id:
            r = self.m.abrir_calculo(self.calculo_id)
            if not r.ok:
                raise JsfError("; ".join(x["texto"] for x in r.mensagens) or f"Cálculo {self.calculo_id} não encontrado.")
            p = self.m.page
        else:
            p = self.m.tela_inicial()
        if self.menu and self.menu != "li_tela_inicial":
            ancora = re.search(r'<li[^>]*id="%s"[^>]*>\s*<a[^>]*id="([^"]+)"' % re.escape(self.menu), p.dom)
            if not ancora:
                raise JsfError("Esta função não está no menu do PJe-Calc instalado.")
            p.click(ancora.group(1))
        return self.descrever()

    @property
    def page(self) -> Page:
        return self.m.page

    def descrever(self) -> dict:
        d = descrever_pagina(self.page)
        d["calculo"] = self.calculo_id
        if self.arquivo is not None:
            d["arquivo"] = {"nome": self.arquivo["nome"], "tipo": self.arquivo["tipo"], "bytes": len(self.arquivo["corpo"])}
        return d

    def _para_pagina(self, nome: str, valor):
        """Valor da interface -> valor do formulário ("" numa lista = a opção "sem seleção" do PJe-Calc)."""
        f = self.page.fields[nome][0]
        if f.type == "select" and valor in ("", None):
            vazio = next((v for v, _ in f.options if _sem_selecao(v) or v == ""), None)
            return vazio if vazio is not None else f.value  # lista sem opção vazia: fica como está
        return valor

    def preencher(self, valores: dict):
        """Valores digitados na interface: entram no formulário sem disparar eventos (o envio leva todos)."""
        for nome, valor in (valores or {}).items():
            if nome in self.page.fields:
                self.page.set(nome, self._para_pagina(nome, valor), fire=False)

    def alterar(self, valores: dict, evento: str | None) -> dict:
        """Campo com evento A4J (ex.: escolher um estado carrega os municípios): dispara como o navegador."""
        self.arquivo = None
        self.preencher({k: v for k, v in valores.items() if k != evento})
        if evento and evento in self.page.fields:
            f = self.page.fields[evento][0]
            self.page.set(evento, self._para_pagina(evento, valores.get(evento)), fire=True)
            if f.onblur and "A4J.AJAX.Submit" in f.onblur:
                self.page.blur(evento)
        return self.descrever()

    def acionar(self, acao: str, valores: dict) -> dict:
        self.arquivo = None
        self.preencher(valores)
        p = self.page
        p.arquivo = None
        if acao.startswith("aba:"):  # aba trocada no servidor (_JSFFormSubmit com "<aba>_server_submit")
            aba = acao[4:]
            p.submit({f"{p.form_id}:_idcl": aba, f"{aba}_server_submit": f"{aba}_server_submit"})
        elif acao.startswith("pag:"):  # página de um rich:datascroller
            scroller, pagina = acao[4:].rsplit(":", 1)
            p.ajax_parametros({scroller: pagina, "ajaxSingle": scroller})
        else:
            p.click(acao)
            # relatórios e exportação: a resposta traz um <script> que envia o formulário na hora (jsfcljs) para
            # baixar o arquivo; o navegador faria isso sozinho, então a sessão faz o mesmo
            automatico = _ENVIO_AUTOMATICO.search(_scripts(p.last_response))
            if automatico and p.arquivo is None:
                p.submit(dict(re.findall(r"'([^']*)':'([^']*)'", automatico.group(1))))
        if p.arquivo is not None:
            tipo = (p.arquivo.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
            self.arquivo = {"corpo": p.arquivo.body, "tipo": tipo, "nome": _nome_arquivo(p.arquivo.headers, tipo, self.calculo_id)}
        return self.descrever()

    def enviar_arquivo(self, campo: str, nome: str, conteudo: bytes, valores: dict) -> dict:
        self.arquivo = None
        self.preencher(valores)
        componente = campo.removesuffix(":file")
        self.page.upload(componente, nome, conteudo)
        return self.descrever()


_ENVIO_AUTOMATICO = re.compile(r"jsfcljs\(document\.getElementById\('[^']+'\),\{([^}]*)\}")


def _scripts(texto: str) -> str:
    """Conteúdo dos <script> da resposta (fora dos atributos onclick, que só rodam com um clique)."""
    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", texto, re.S))


def _nome_arquivo(headers: dict, tipo: str, calculo: str | None) -> str:
    cd = next((v for k, v in headers.items() if k.lower() == "content-disposition"), "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd, re.I)
    if m:
        return m.group(1).strip()
    sufixo = f"_{calculo}" if calculo else ""
    if "pdf" in tipo:
        return f"relatorio_pjecalc{sufixo}.pdf"
    if "zip" in tipo:
        return f"calculo_pjecalc{sufixo}.pjc"
    return f"arquivo_pjecalc{sufixo}"


class Sessoes:
    """Sessões de tela abertas (no máximo `limite`; as paradas há mais de `validade` segundos são descartadas)."""

    def __init__(self, limite: int = 8, validade: float = 3600):
        self.itens: dict[str, SessaoTela] = {}
        self.limite, self.validade = limite, validade
        self.lock = threading.Lock()

    def nova(self, sessao: SessaoTela) -> SessaoTela:
        with self.lock:
            agora = time.monotonic()
            for t in [t for t, s in self.itens.items() if agora - s.usada > self.validade]:
                del self.itens[t]
            while len(self.itens) >= self.limite:
                del self.itens[min(self.itens, key=lambda t: self.itens[t].usada)]
            self.itens[sessao.token] = sessao
            return sessao

    def obter(self, token: str) -> SessaoTela:
        with self.lock:
            s = self.itens.get(token)
            if s is None:
                raise KeyError(token)
            s.usada = time.monotonic()
            return s

    def fechar(self, token: str):
        with self.lock:
            self.itens.pop(token, None)


__all__ = ["SessaoTela", "Sessoes", "descrever_pagina", "fold"]
