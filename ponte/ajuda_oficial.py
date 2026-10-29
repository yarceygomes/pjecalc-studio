"""Extrai os textos de ajuda (tooltips) das telas da instalação local do PJe-Calc.

Os textos são lidos dos arquivos .xhtml da versão instalada, sem modificá-los, para que a
nova interface exiba a explicação oficial junto ao campo correspondente — sempre identificada
como "Texto de ajuda do PJe-Calc <versão>".

Uso: py -I -m ponte.ajuda_oficial <pasta da instalação> <saida.json>
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

_TOOLTIP = re.compile(r"<rich:toolTip\b([^>]*)>(.*?)</rich:toolTip>", re.S)
_LABEL = re.compile(r'<h:outputLabel[^>]*?(?:value="([^"]*)"[^>]*?for="([^"]+)"|for="([^"]+)"[^>]*?value="([^"]*)")')
_INPUT = re.compile(r'<(?:h:inputText|h:selectOneMenu|h:selectOneRadio|h:selectBooleanCheckbox|rich:calendar|'
                    r'h:inputTextarea|h:selectManyCheckbox)\b[^>]*?\bid="([^"]+)"')


def _limpar(texto: str) -> str:
    t = re.sub(r"<[^>]+>", " ", texto)
    return " ".join(html.unescape(t).split())


def extrair(webapp: str) -> list[dict]:
    saida = []
    for raiz, _, arquivos in os.walk(os.path.join(webapp, "pages")):
        for nome in arquivos:
            if not nome.endswith(".xhtml"):
                continue
            caminho = os.path.join(raiz, nome)
            with open(caminho, encoding="iso-8859-1") as fh:
                fonte = fh.read()
            pagina = os.path.relpath(caminho, webapp).replace("\\", "/")
            for m in _TOOLTIP.finditer(fonte):
                corpo = m.group(2)
                if "rich:message" in corpo or "#{" in corpo:
                    continue  # tooltips de validação (mensagens dinâmicas), não são ajuda
                texto = _limpar(corpo)
                if len(texto) < 15:
                    continue
                antes = fonte[max(0, m.start() - 2500):m.start()]
                rotulos = list(_LABEL.finditer(antes))
                entradas = list(_INPUT.finditer(antes))
                campo = rotulo = None
                if rotulos:
                    r = rotulos[-1]
                    rotulo = _limpar(r.group(1) or r.group(4) or "")
                    campo = r.group(2) or r.group(3)
                if entradas and (not rotulos or entradas[-1].start() > rotulos[-1].start()):
                    campo = entradas[-1].group(1)
                # convenção das telas: o ícone de ajuda tem id "<campo>Help"
                alvo = re.search(r'for="([^"]+)Help"', m.group(1))
                if alvo and re.search(rf'\bid="{re.escape(alvo.group(1))}"', fonte):
                    if campo != alvo.group(1):
                        campo, rotulo = alvo.group(1), None
                saida.append({"pagina": pagina, "campo": campo, "rotulo": rotulo, "texto": texto})
    return saida


def localizar_webapp(instalacao: str) -> str:
    for cand in (os.path.join(instalacao, "tomcat", "webapps", "pjecalc"), instalacao):
        if os.path.isdir(os.path.join(cand, "pages")):
            return cand
    raise FileNotFoundError("Pasta 'tomcat/webapps/pjecalc' não encontrada em " + instalacao)


def versao_instalada(webapp: str) -> str | None:
    """Versão declarada em versao.html da aplicação instalada (a mesma página que o PJe-Calc serve)."""
    vf = os.path.join(webapp, "versao.html")
    if not os.path.exists(vf):
        return None
    with open(vf, encoding="utf-8", errors="replace") as fh:
        m = re.search(r"Versao:\s*([\d.]+)", fh.read())
    return m.group(1) if m else None


if __name__ == "__main__":
    webapp = localizar_webapp(sys.argv[1])
    itens = extrair(webapp)
    versao = versao_instalada(webapp)
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump({"versao": versao, "itens": itens}, fh, ensure_ascii=False, indent=1)
    print(f"{len(itens)} textos de ajuda extraídos (versão {versao})")
