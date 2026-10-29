"""Cliente HTTP para a interface JSF 1.2 / RichFaces 3.3 (Ajax4jsf) do PJe-Calc.

Opera a interface original exatamente como um navegador: lê os formulários, envia os
mesmos campos, dispara os eventos A4J declarados nos atributos ``onchange``/``onclick``
e aciona os botões. Nenhuma regra de cálculo ou validação é reproduzida aqui: todas as
gravações passam pelos apresentadores e validadores do próprio PJe-Calc.
"""
from __future__ import annotations

import html
import http.cookiejar
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from html.parser import HTMLParser

ENCODING = "iso-8859-1"  # o PJe-Calc força ISO-8859-1 (web.xml / components.xml)

_A4J_RE = re.compile(r"A4J\.AJAX\.Submit\('([^']+)',\s*event,\s*\{(.*)\}\s*\)", re.S)
_PARAMS_RE = re.compile(r"'parameters':\{([^}]*)\}")
_KV_RE = re.compile(r"'([^']*)':'([^']*)'")
_CONTAINER_RE = re.compile(r"'containerId':'([^']*)'")
_JSFCLJS_RE = re.compile(r"jsfcljs\(document\.getElementById\('([^']+)'\),\{([^}]*)\}")


class JsfError(RuntimeError):
    pass


@dataclass
class Field:
    name: str
    tag: str
    type: str = "text"
    id: str | None = None
    value: str = ""
    checked: bool = False
    disabled: bool = False
    options: list[tuple[str, str]] = field(default_factory=list)  # (valor, rótulo)
    onchange: str | None = None
    onclick: str | None = None
    label: str | None = None
    onblur: str | None = None


@dataclass
class Action:
    """Elemento acionável (botão ou link) com seu manipulador de evento."""
    id: str | None
    name: str | None
    text: str
    onclick: str | None
    tag: str
    type: str | None = None


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: dict[str, dict] = {}
        self.form: str | None = None
        self.select: Field | None = None
        self.option: list | None = None
        self.textarea: Field | None = None
        self.link: dict | None = None
        self.labels: dict[str, str] = {}
        self.label_for: str | None = None
        self.label_text: list[str] = []
        self.messages: list[dict] = []
        self.msg_stack: list[dict | None] = []
        self.ajax_meta: dict[str, str] = {}
        self.span_stack: list[list] = []
        self.in_script = False
        self.texts: dict[str, str] = {}  # id de <span> -> texto (rótulos de listas e grades)

    def _fields(self):
        return self.forms[self.form]["fields"] if self.form else None

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if tag in ("script", "style"):
            self.in_script = True
            return
        if tag == "meta" and a.get("name"):
            self.ajax_meta[a["name"]] = a.get("content", "")
        if tag == "form":
            fid = a.get("id") or a.get("name") or f"form{len(self.forms)}"
            self.forms[fid] = {"action": a.get("action"), "enctype": a.get("enctype"), "fields": [], "actions": []}
            self.form = fid
            return
        if tag == "label" and a.get("for"):
            self.label_for, self.label_text = a["for"], []
        cls = a.get("class", "")
        if tag in ("span", "td"):
            self.span_stack.append([a.get("id"), [], tag])
        if tag in ("span", "div", "li", "dt", "td"):
            if any(c in cls for c in ("rich-message", "rich-messages", "msgErro", "msgAlerta", "msgInfo",
                                      "validacaoErro", "validacaoAlerta", "validacaoSucesso", "mensagem")):
                self.msg_stack.append({"class": cls, "id": a.get("id"), "text": []})
            else:
                self.msg_stack.append(None)
        if self.form is None:
            return
        fields = self._fields()
        if tag == "input":
            t = a.get("type", "text").lower()
            if t in ("submit", "button", "image"):
                self.forms[self.form]["actions"].append(
                    Action(a.get("id"), a.get("name"), a.get("value", ""), a.get("onclick"), tag, t))
                return
            if not a.get("name"):
                return
            fields.append(Field(name=a["name"], tag=tag, type=t, id=a.get("id"), value=a.get("value", ""),
                                checked="checked" in a, disabled="disabled" in a,
                                onchange=a.get("onchange"), onclick=a.get("onclick"), onblur=a.get("onblur")))
        elif tag == "select" and a.get("name"):
            self.select = Field(name=a["name"], tag=tag, type="select", id=a.get("id"),
                                disabled="disabled" in a, onchange=a.get("onchange"), onclick=a.get("onclick"))
            self.select.value = None  # definido pela opção selecionada
            fields.append(self.select)
        elif tag == "option" and self.select is not None:
            self.option = [a.get("value"), [], "selected" in a]
        elif tag == "textarea" and a.get("name"):
            self.textarea = Field(name=a["name"], tag=tag, type="textarea", id=a.get("id"),
                                  disabled="disabled" in a, onchange=a.get("onchange"))
            fields.append(self.textarea)
        elif tag == "a" and a.get("onclick"):
            self.link = {"id": a.get("id"), "onclick": a.get("onclick"), "text": [], "title": a.get("title", "")}

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script = False
            return
        if tag == "form":
            self.form = None
        elif tag == "option" and self.option is not None and self.select is not None:
            val, txt, sel = self.option
            label = "".join(txt).strip()
            if val is None:
                val = label
            self.select.options.append((val, label))
            if sel or self.select.value is None:
                if sel or not self.select.options[:-1]:
                    self.select.value = val
            self.option = None
        elif tag == "select":
            if self.select is not None and self.select.value is None:
                self.select.value = ""
            self.select = None
        elif tag == "textarea":
            self.textarea = None
        elif tag == "a" and self.link is not None:
            if self.form:
                text = " ".join("".join(self.link["text"]).split()) or self.link["title"]
                self.forms[self.form]["actions"].append(Action(self.link["id"], None, text, self.link["onclick"], "a"))
            self.link = None
        elif tag == "label" and self.label_for:
            self.labels[self.label_for] = " ".join("".join(self.label_text).split())
            self.label_for = None
        if tag in ("span", "td") and self.span_stack:
            # desempilha até o elemento correspondente (HTML gerado pode omitir fechamentos)
            while self.span_stack:
                sid, parts, t = self.span_stack.pop()
                if sid:
                    self.texts[sid] = " ".join("".join(parts).split())
                if t == tag:
                    break
        if tag in ("span", "div", "li", "dt", "td") and self.msg_stack:
            m = self.msg_stack.pop()
            if m is not None:
                text = " ".join("".join(m["text"]).split())
                if text:
                    self.messages.append({"class": m["class"], "id": m["id"], "text": text})

    def handle_data(self, data):
        if self.in_script:
            return
        if self.option is not None:
            self.option[1].append(data)
        if self.textarea is not None:
            self.textarea.value += data
        if self.link is not None:
            self.link["text"].append(data)
        if self.label_for:
            self.label_text.append(data)
        for m in self.msg_stack:
            if m is not None:
                m["text"].append(data)
        for s in self.span_stack:
            s[1].append(data)


def parse(text: str) -> _FormParser:
    p = _FormParser()
    p.feed(text)
    p.close()
    for form in p.forms.values():
        for f in form["fields"]:
            if f.id and f.id in p.labels:
                f.label = p.labels[f.id]
    return p


class Page:
    """Estado de uma página JSF (um formulário principal) mantido entre requisições."""

    def __init__(self, client: "JsfClient", url: str, text: str, form_id: str = "formulario"):
        self.client = client
        self.url = url
        self.form_id = form_id
        self.last_response = text
        self.messages: list[dict] = []
        self.arquivo: Response | None = None  # última resposta de submit() que foi um arquivo
        self._load(text)

    # ------------------------------------------------------------------ leitura
    def _load(self, text: str):
        p = parse(text)
        if self.form_id not in p.forms:
            raise JsfError(f"Formulário '{self.form_id}' não encontrado em {self.url}")
        form = p.forms[self.form_id]
        self.action = urllib.parse.urljoin(self.url, form["action"])
        self.enctype = form["enctype"]
        self.fields: dict[str, list[Field]] = {}
        for f in form["fields"]:
            self.fields.setdefault(f.name, []).append(f)
        self.actions: list[Action] = form["actions"]
        self.messages = p.messages
        self.texts = p.texts
        self.labels = p.labels  # id do campo/opção -> texto do <label for>
        self.text = text
        self.dom = text  # página completa, atualizada a cada resposta A4J (ver _merge)

    def _merge(self, text: str):
        """Incorpora um trecho de resposta A4J (regiões re-renderizadas)."""
        # como o navegador: cada região listada em Ajax-Update-Ids substitui o elemento de mesmo id
        ids = re.search(r'<meta name="Ajax-Update-Ids" content="([^"]*)"', text)
        for rid in (ids.group(1).split(",") if ids else []):
            novo = outer_html(text, rid.strip())
            if novo is not None:
                self.dom = substituir_elemento(self.dom, rid.strip(), novo)
        p = parse(text)
        self.messages = p.messages
        self.texts.update(p.texts)
        self.labels.update(p.labels)
        for form in p.forms.values():
            self._merge_fields(form)
        # respostas A4J nem sempre trazem o <form>; procurar campos soltos
        loose = _FormParser()
        loose.form = "_"
        loose.forms["_"] = {"action": None, "enctype": None, "fields": [], "actions": []}
        loose.feed(text)
        self._merge_fields(loose.forms["_"])

    def _merge_fields(self, form):
        seen: set[str] = set()
        for f in form["fields"]:
            if f.name == "javax.faces.ViewState":
                self.fields[f.name] = [f]
                continue
            if f.name not in seen:
                self.fields[f.name] = []
                seen.add(f.name)
            self.fields[f.name].append(f)
        # ações re-renderizadas têm prioridade (ordem atual do DOM); as demais permanecem
        fresh = [a for a in form["actions"] if a.id or a.text]
        ids = {a.id for a in fresh if a.id}
        self.actions = fresh + [a for a in self.actions if not (a.id and a.id in ids)]

    def field(self, name: str) -> Field:
        key = name if name in self.fields else f"{self.form_id}:{name}"
        if key not in self.fields:
            raise JsfError(f"Campo '{name}' não existe na página {self.url}")
        return self.fields[key][0]

    def has(self, name: str) -> bool:
        return name in self.fields or f"{self.form_id}:{name}" in self.fields

    def get(self, name: str):
        key = name if name in self.fields else f"{self.form_id}:{name}"
        group = self.fields[key]
        if group[0].type == "radio":
            return next((f.value for f in group if f.checked), None)
        if group[0].type == "checkbox":
            return group[0].checked
        return group[0].value

    def options(self, name: str) -> list[tuple[str, str]]:
        return self.field(name).options

    # ------------------------------------------------------------------ escrita
    def set(self, name: str, value, fire: bool = True):
        """Define o valor e, se houver, dispara o evento A4J associado (onchange/onclick)."""
        key = name if name in self.fields else f"{self.form_id}:{name}"
        group = self.fields.get(key)
        if not group:
            raise JsfError(f"Campo '{name}' não existe na página {self.url}")
        f0 = group[0]
        handler = None
        if f0.type == "radio":
            target = next((f for f in group if f.value == str(value)), None)
            if target is None:
                raise JsfError(f"Opção '{value}' inexistente para '{name}': {[f.value for f in group]}")
            for f in group:
                f.checked = f is target
            handler = target.onclick or target.onchange
        elif f0.type == "checkbox":
            f0.checked = bool(value)
            handler = f0.onclick or f0.onchange
        elif f0.type == "select":
            values = [v for v, _ in f0.options]
            labels = {fold(lbl): v for v, lbl in f0.options}
            val = str(value)
            if val not in values:
                if fold(val) in labels:
                    val = labels[fold(val)]
                else:
                    raise JsfError(f"Opção '{value}' inexistente para '{name}': {f0.options[:20]}")
            f0.value = val
            handler = f0.onchange
        else:
            f0.value = "" if value is None else str(value)
            # campos desabilitados só no navegador (habilitados por JavaScript ao marcar a opção
            # correspondente) seguem para o servidor, que decide se os aceita
            f0.disabled = False
            handler = f0.onchange
        if fire and handler and "A4J.AJAX.Submit" in handler:
            self.ajax(handler)
        return self

    def blur(self, name: str):
        """Dispara o evento A4J de saída do campo (a4j:support event="onblur"), se houver."""
        f = self.field(name)
        if f.onblur and "A4J.AJAX.Submit" in f.onblur:
            self.ajax(f.onblur)
        return self

    def payload(self, extra: dict | None = None, upper: bool = False) -> list[tuple[str, str]]:
        data: list[tuple[str, str]] = []
        for name, group in self.fields.items():
            for f in group:
                if f.disabled:
                    continue
                if f.type in ("radio", "checkbox"):
                    if f.checked:
                        data.append((name, f.value or "on"))
                elif f.type == "file":
                    continue
                else:
                    v = f.value or ""
                    if upper and f.type in ("text", "textarea") and not name.endswith("InputDate"):
                        v = v.upper()  # reproduz allToUpperCase() da página original
                    data.append((name, v))
        for k, v in (extra or {}).items():
            data.append((k, v))
        return data

    # ------------------------------------------------------------------ eventos
    def ajax(self, handler: str, upper: bool | None = None):
        m = _A4J_RE.search(handler)
        if not m:
            raise JsfError(f"Manipulador A4J não reconhecido: {handler[:200]}")
        form_id, opts = m.group(1), m.group(2)
        params = dict(_KV_RE.findall(_PARAMS_RE.search(opts).group(1))) if _PARAMS_RE.search(opts) else {}
        container = _CONTAINER_RE.search(opts)
        extra = {"AJAXREQUEST": container.group(1) if container else "_viewRoot", **params}
        if upper is None:
            upper = "allToUpperCase()" in handler
        resp = self.client.post(self.action, self.payload(extra, upper=upper), ajax=True)
        self._after(resp)
        return self

    def ajax_parametros(self, params: dict, container: str = "_viewRoot"):
        """Requisição A4J montada por um componente via script (ex.: páginas do rich:datascroller)."""
        resp = self.client.post(self.action, self.payload({"AJAXREQUEST": container, **params}), ajax=True)
        self._after(resp)
        return self

    def submit(self, extra: dict):
        """Envio convencional (h:commandButton / h:commandLink sem A4J).

        Se a resposta for um arquivo (relatório, .PJC), a página continua como estava e o arquivo fica em
        self.arquivo."""
        resp = self.client.post(self.action, self.payload(extra))
        self.arquivo = None
        tipo = (resp.headers.get("Content-Type") or "").lower()
        if "html" not in tipo and "xml" not in tipo:
            self.arquivo = resp
            return self
        self._after(resp, full=True)
        return self

    def upload(self, component_id: str, filename: str, content: bytes):
        """Envia um arquivo por um rich:fileUpload (mesma requisição que o componente faz no navegador)."""
        comp = component_id if component_id.startswith(self.form_id + ":") else f"{self.form_id}:{component_id}"
        url = (self.action + ("&" if "?" in self.action else "?") +
               urllib.parse.urlencode({"_richfaces_upload_uid": str(uuid.uuid4()), comp: comp,
                                       "_richfaces_upload_file_indicator": "true", "AJAXREQUEST": "_viewRoot"}))
        resp = self.client.post_multipart(url, self.payload(), [(comp + ":file", filename, content)])
        self._merge(resp.text)
        return self

    def download(self, component_id: str) -> "Response":
        """Aciona um h:commandLink que devolve arquivo (PDF, .PJC) sem alterar o estado da página."""
        cid = component_id if component_id.startswith(self.form_id + ":") else f"{self.form_id}:{component_id}"
        return self.client.post(self.action, self.payload({cid: cid}))

    def _after(self, resp: "Response", full: bool = False):
        self.last_response = resp.text
        meta = parse(resp.text).ajax_meta
        if meta.get("Ajax-Response") == "redirect" and meta.get("Location"):
            nxt = self.client.get(urllib.parse.urljoin(self.url, meta["Location"]))
            self.url = nxt.url
            self.last_response = nxt.text
            self._load(nxt.text)
        elif full or resp.url != self.url and not resp.ajax:
            self.url = resp.url
            self._load(resp.text)
        else:
            self._merge(resp.text)

    def click(self, text_or_id: str):
        """Aciona botão/link pelo id (sem prefixo do formulário) ou texto visível."""
        act = self.find_action(text_or_id)
        if act.onclick and "A4J.AJAX.Submit" in act.onclick:
            return self.ajax(act.onclick)
        if act.onclick and "jsfcljs" in act.onclick:
            m = _JSFCLJS_RE.search(act.onclick)
            return self.submit(dict(_KV_RE.findall(m.group(2))))
        if act.name:
            return self.submit({act.name: act.text})
        raise JsfError(f"Não sei acionar '{text_or_id}': {act}")

    def find_action(self, text_or_id: str) -> Action:
        full = f"{self.form_id}:{text_or_id}"
        for a in self.actions:
            if a.id in (text_or_id, full) or a.name in (text_or_id, full):
                return a
        norm = fold(text_or_id)
        for a in self.actions:
            if fold(a.text) == norm:
                return a
        raise JsfError(f"Ação '{text_or_id}' não encontrada. Disponíveis: "
                       f"{[(a.id, a.text) for a in self.actions][:60]}")

    def errors(self) -> list[str]:
        return [m["text"] for m in self.messages]


@dataclass
class Response:
    url: str
    status: int
    text: str
    headers: dict
    body: bytes
    ajax: bool = False


class JsfClient:
    def __init__(self, base_url: str, timeout: float = 300):
        self.base = base_url.rstrip("/") + "/"
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.timeout = timeout

    def url(self, path: str) -> str:
        return urllib.parse.urljoin(self.base, path.lstrip("/"))

    def _do(self, req: urllib.request.Request, ajax=False) -> Response:
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                body = r.read()
                ctype = r.headers.get("Content-Type", "")
                enc = ENCODING
                if "charset=" in ctype.lower():
                    enc = ctype.lower().split("charset=")[1].split(";")[0].strip()
                text = body.decode(enc, "replace") if ("text" in ctype or "xml" in ctype or "html" in ctype) else ""
                return Response(r.geturl(), r.status, text, dict(r.headers), body, ajax)
        except urllib.error.HTTPError as e:
            body = e.read()
            raise JsfError(f"HTTP {e.code} em {req.full_url}: {body[:300]!r}") from e

    def get(self, path: str) -> Response:
        return self._do(urllib.request.Request(self.url(path), headers={"User-Agent": "PJeCalcStudio/0.1"}))

    def post(self, url: str, data: list[tuple[str, str]], ajax=False) -> Response:
        body = urllib.parse.urlencode(data, encoding=ENCODING).encode("ascii")
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=" + ENCODING,
                   "User-Agent": "PJeCalcStudio/0.1"}
        return self._do(urllib.request.Request(url, data=body, headers=headers), ajax=ajax)

    def post_multipart(self, url: str, data: list[tuple[str, str]], files: list[tuple[str, str, bytes]],
                       extra_headers: dict | None = None) -> Response:
        boundary = "----PJeCalcStudio7d1f0a"
        parts = []
        for k, v in data:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode(ENCODING)
                         + v.encode(ENCODING, "replace") + b"\r\n")
        for k, filename, content in files:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{filename}\"\r\n"
                         f"Content-Type: application/octet-stream\r\n\r\n".encode(ENCODING) + content + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "PJeCalcStudio/0.1"}
        headers.update(extra_headers or {})
        return self._do(urllib.request.Request(url, data=body, headers=headers))

    def open(self, path: str, form_id: str = "formulario") -> Page:
        r = self.get(path)
        return Page(self, r.url, r.text, form_id)


class _TableParser(HTMLParser):
    def __init__(self, table_id: str):
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.depth = 0  # profundidade de <table> dentro da tabela-alvo
        self.rows: list[list[str]] = []
        self.header: list[str] = []
        self.cell: list[str] | None = None
        self.row: list[str] | None = None
        self.in_head = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if self.depth == 0 and a.get("id") == self.table_id:
                self.depth = 1
            elif self.depth:
                self.depth += 1
            return
        if self.depth != 1:
            if self.depth > 1 and self.cell is not None and tag == "br":
                self.cell.append(" ")
            return
        if tag == "thead":
            self.in_head = True
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
            return
        if self.depth != 1:
            return
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.in_head:
                self.header.extend(self.row)
            else:
                self.rows.append(self.row)
            self.row = None
        elif tag == "thead":
            self.in_head = False

    def handle_data(self, data):
        if self.depth >= 1 and self.cell is not None:
            self.cell.append(data)


def table(text: str, table_id: str) -> tuple[list[str], list[list[str]]]:
    """Extrai cabeçalho e linhas (texto das células) de uma tabela pelo id."""
    tp = _TableParser(table_id)
    tp.feed(text)
    tp.close()
    return tp.header, tp.rows


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w:-]*)([^>]*?)(/?)>", re.S)


def _faixa_elemento(text: str, elem_id: str) -> tuple[int, int] | None:
    """Início e fim (exclusivo) do elemento com o id dado, contando o aninhamento de tags de mesmo nome."""
    m = re.search(r'<([a-zA-Z][\w:-]*)\b[^>]*\bid="%s"' % re.escape(elem_id), text)
    if not m:
        return None
    tag, inicio, prof = m.group(1).lower(), m.start(), 0
    if tag in _VOID:
        return inicio, text.index(">", m.end()) + 1
    for t in _TAG_RE.finditer(text, inicio):
        if t.group(2).lower() != tag or t.group(4):
            continue
        prof += -1 if t.group(1) else 1
        if prof == 0:
            return inicio, t.end()
    return None


def outer_html(text: str, elem_id: str) -> str | None:
    faixa = _faixa_elemento(text, elem_id)
    return text[faixa[0]:faixa[1]] if faixa else None


def substituir_elemento(text: str, elem_id: str, novo: str) -> str:
    faixa = _faixa_elemento(text, elem_id)
    return text[:faixa[0]] + novo + text[faixa[1]:] if faixa else text


def unescape(s: str) -> str:
    return html.unescape(s)


def fold(s: str) -> str:
    """Normaliza texto para comparação: sem acentos, minúsculo, espaços simples."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())
