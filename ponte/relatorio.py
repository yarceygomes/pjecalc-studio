"""Leitura dos resultados produzidos pelo PJe-Calc.

Duas fontes, ambas geradas pelo motor original:
  * o relatório oficial em HTML (tela "Imprimir", formato HTML) — resumo, créditos e descontos,
    débitos do reclamado, critérios e fundamentação legal, rodapé com versão e data da liquidação;
  * o arquivo .PJC exportado — valores por verba e por competência (ocorrências).

Nada aqui recalcula valores: os números são transcritos como texto, exatamente como o PJe-Calc os
emitiu, e convertidos para Decimal apenas para comparação entre cenários.
"""
from __future__ import annotations

import html as _html
import re
import zipfile
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

NUM = re.compile(r"^\(?-?[\d.]+,\d{2,}\)?$")


def decimal_br(s: str | None) -> Decimal | None:
    if s is None:
        return None
    t = s.strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(".", "").replace(",", ".")
    try:
        v = Decimal(t)
    except InvalidOperation:
        return None
    return -v if neg else v


def decodificar_relatorio(corpo: bytes) -> str:
    """O HTML do Jasper declara UTF-8 no <meta>, embora o cabeçalho HTTP diga ISO-8859-1."""
    head = corpo[:2000].decode("ascii", "ignore").lower()
    if "charset=utf-8" in head:
        return corpo.decode("utf-8", "replace")
    try:
        return corpo.decode("utf-8")
    except UnicodeDecodeError:
        return corpo.decode("iso-8859-1")


class _Grade(HTMLParser):
    """Converte as tabelas do Jasper em linhas de (coluna_inicial, texto)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas: list[list[tuple[int, str]]] = []
        self.linha: list[tuple[int, str]] | None = None
        self.col = 0
        self.cel: list[str] | None = None
        self.cel_col = 0
        self.span = 1
        self.rspan = 1
        self.in_style = False
        self.ocupadas: dict[int, int] = {}  # coluna -> linhas restantes ocupadas por rowspan
        self.ocupadas_linha: set[int] = set()
        self.base = 0  # deslocamento de coluna de uma tabela aninhada (coluna da célula externa)
        self.pilha: list[tuple] = []

    def _pular_ocupadas(self):
        while self.col in self.ocupadas_linha:
            self.col += 1

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("style", "script"):
            self.in_style = True
        elif tag == "table":
            if self.cel is not None:  # tabela dentro de uma célula: guarda o estado externo
                self.pilha.append((self.linha, self.col, self.cel, self.cel_col, self.span, self.rspan,
                                   self.ocupadas, self.ocupadas_linha, self.base))
                self.base = self.cel_col
                self.linha, self.cel = None, None
            self.ocupadas = {}
        elif tag == "tr":
            self.linha, self.col = [], 0
            self.ocupadas_linha = {c for c, n in self.ocupadas.items() if n > 0}
        elif tag == "td" and self.linha is not None:
            self._pular_ocupadas()
            self.cel, self.cel_col = [], self.col
            try:
                self.span = int(a.get("colspan") or 1)
                self.rspan = int(a.get("rowspan") or 1)
            except ValueError:
                self.span, self.rspan = 1, 1
        elif tag == "br" and self.cel is not None:
            self.cel.append(" ")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.in_style = False
        elif tag == "table" and self.pilha:
            (self.linha, self.col, self.cel, self.cel_col, self.span, self.rspan,
             self.ocupadas, self.ocupadas_linha, self.base) = self.pilha.pop()
        elif tag == "td" and self.cel is not None and self.linha is not None:
            texto = " ".join("".join(self.cel).split())
            if texto:
                self.linha.append((self.base + self.cel_col, texto))
            if self.rspan > 1:
                for c in range(self.cel_col, self.cel_col + self.span):
                    self.ocupadas[c] = self.rspan  # decrementado ao fim de cada linha
            self.col += self.span
            self.cel = None
        elif tag == "tr" and self.linha is not None:
            if self.linha:
                self.linhas.append(self.linha)
            self.ocupadas = {c: n - 1 for c, n in self.ocupadas.items() if n - 1 > 0}
            self.linha = None

    def handle_data(self, data):
        if self.cel is not None and not self.in_style:
            self.cel.append(data)


def _coluna(cols: list[tuple[int, str]], pos: int) -> str:
    """Cabeçalho cuja coluna inicial é a mais próxima (à esquerda, preferencialmente) da célula."""
    candidatos = [c for c in cols if c[0] <= pos] or cols
    return max(candidatos, key=lambda c: c[0])[1] if candidatos is not cols else min(cols, key=lambda c: abs(c[0] - pos))[1]


def ler_relatorio(corpo: bytes) -> dict:
    texto_html = decodificar_relatorio(corpo)
    g = _Grade()
    g.feed(texto_html)
    linhas = g.linhas
    res: dict = {"verbas": [], "total_bruto": None, "creditos_descontos": [], "debitos_reclamado": [],
                 "criterios": [], "percentual_tributavel": None, "rodape": None, "cabecalho": {}}

    i = 0
    while i < len(linhas):
        ln = linhas[i]
        textos = [t for _, t in ln]
        if "Descrição do Bruto Devido ao Reclamante" in textos:
            cab = ln
            i += 1
            while i < len(linhas):
                row = linhas[i]
                tx = [t for _, t in row]
                if any(t.startswith("Percentual de Parcelas") for t in tx) or "Descrição de Créditos e Descontos do Reclamante" in tx:
                    break
                if tx == ["Total"]:
                    i += 1
                    continue
                reg = {}
                for pos, t in row:
                    reg[_coluna(cab, pos)] = t
                desc = reg.get("Descrição do Bruto Devido ao Reclamante")
                vals = {k: v for k, v in reg.items() if k != "Descrição do Bruto Devido ao Reclamante"}
                item = {"corrigido": vals.get("Valor Corrigido"), "juros": vals.get("Juros"), "total": vals.get("Total")}
                if desc and not NUM.match(desc):
                    res["verbas"].append({"descricao": desc, **item})
                elif any(item.values()):
                    if desc and NUM.match(desc):  # linha de totais sem descrição: valores deslocados
                        nums = [t for _, t in row if NUM.match(t)]
                        item = dict(zip(("corrigido", "juros", "total"), nums))
                    res["total_bruto"] = item
                i += 1
            continue
        if "Descrição de Créditos e Descontos do Reclamante" in textos:
            cab = ln
            esq = [c for c in cab if c[0] < next(p for p, t in cab if t.startswith("Descrição de Débitos"))]
            dir_inicio = next(p for p, t in cab if t.startswith("Descrição de Débitos"))
            i += 1
            while i < len(linhas):
                row = linhas[i]
                tx = [t for _, t in row]
                if not row or any(t.startswith("Critério de Cálculo") for t in tx) or any(t.startswith("Cálculo liquidado por") for t in tx):
                    break
                lado_e = [(p, t) for p, t in row if p < dir_inicio]
                lado_d = [(p, t) for p, t in row if p >= dir_inicio]
                for lado, destino in ((lado_e, "creditos_descontos"), (lado_d, "debitos_reclamado")):
                    desc = next((t for _, t in lado if not NUM.match(t)), None)
                    val = next((t for _, t in lado if NUM.match(t)), None)
                    if desc or val:
                        res[destino].append({"descricao": desc, "valor": val})
                i += 1
            del esq
            continue
        for t in textos:
            if t.startswith("Percentual de Parcelas Remuneratórias"):
                res["percentual_tributavel"] = t.split(":", 1)[-1].strip()
            m = re.match(r"Cálculo liquidado por (.+?) na versão ([\d.]+) em (\d{2}/\d{2}/\d{4}) às (\d{2}:\d{2}:\d{2})", t)
            if m and not res["rodape"]:
                res["rodape"] = {"usuario": m.group(1), "versao": m.group(2), "data": m.group(3), "hora": m.group(4)}
        i += 1

    # critérios e fundamentação legal: itens numerados após o título
    plano = [t for ln in linhas for _, t in ln]
    if "Critério de Cálculo e Fundamentação Legal" in plano:
        k = plano.index("Critério de Cálculo e Fundamentação Legal") + 1
        atual = None
        while k < len(plano):
            t = plano[k]
            if t in ("Dados do Cálculo",):
                break
            if re.fullmatch(r"\d+\.", t):
                atual = {"numero": int(t[:-1]), "texto": ""}
                res["criterios"].append(atual)
            elif atual is not None and not t.startswith("Cálculo liquidado por") and not t.startswith("Pág.") \
                    and not re.fullmatch(r"\d+", t) and t not in ("Processo:", "Cálculo:", "PLANILHA DE CÁLCULO",
                                                                  "Reclamante:", "Reclamado:", "Período do Cálculo:",
                                                                  "Data Ajuizamento:", "Data Liquidação:") \
                    and not res["cabecalho"].get("_skip"):
                if not atual["texto"]:
                    atual["texto"] = t
            k += 1
    for chave in ("Processo:", "Cálculo:", "Reclamante:", "Reclamado:", "Data Ajuizamento:"):
        if chave in plano:
            j = plano.index(chave)
            prox = plano[j + 1] if j + 1 < len(plano) else ""
            res["cabecalho"][chave.rstrip(":")] = "" if prox.endswith(":") else prox
    return res


# ---------------------------------------------------------------------------------------------- PJC
TZ_PJECALC = timezone(timedelta(hours=-3))  # o PJe-Calc roda com -Duser.timezone=GMT-3


def _txt(el, tag):
    x = el.find(tag)
    return None if x is None or x.text in (None, "null") else x.text


def _num(el, tag):
    """Valor numérico do .PJC sem os zeros à direita da escala interna (3300.000…0 -> 3300)."""
    v = _txt(el, tag)
    if v is None:
        return None
    try:
        d = Decimal(v).normalize()
        return format(d, "f")
    except InvalidOperation:
        return v


def _data_ms(v: str | None) -> str | None:
    if not v:
        return None
    try:
        return datetime.fromtimestamp(int(v) / 1000, TZ_PJECALC).strftime("%d/%m/%Y")
    except (ValueError, OverflowError):
        return v


def ler_pjc(conteudo: bytes) -> dict:
    """Extrai do .PJC os metadados e as ocorrências por verba/competência calculadas pelo motor."""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        nome = z.namelist()[0]
        raiz = ET.fromstring(z.read(nome))
    meta = {
        "arquivo_interno": nome,
        "id": _txt(raiz, "id"),
        "versaoDoSistema": _txt(raiz, "versaoDoSistema"),
        "hashCodeLiquidacao": _txt(raiz, "hashCodeLiquidacao"),
        "dataDeLiquidacao": _data_ms(_txt(raiz, "dataDeLiquidacao")),
        "dataCriacao": _data_ms(_txt(raiz, "dataCriacao")),
        "indicesAcumulados": _txt(raiz, "indicesAcumulados"),
        "hashCalculoCorreto": _txt(raiz, "hashCalculoCorreto"),
    }
    verbas = []
    cont = raiz.find("verbas")
    if cont is not None:
        vistos = set()
        # a verba principal pode vir serializada dentro do primeiro reflexo que a referencia
        # (<verbaPrincipal>), e só como <internalRef> no nível de cima: percorre a árvore toda
        for v in cont.iter():
            if v.find("ocorrencias") is None:
                continue
            chave = (v.tag, _txt(v, "id"))
            if chave in vistos:
                continue
            vistos.add(chave)
            desc = _txt(v, "nome") or _txt(v, "descricao")  # nome completo: distingue reflexos de verbas diferentes
            if desc is None:
                continue
            desc = " ".join(desc.split())  # o PJe-Calc remove espaços finais ao importar
            ocs = []
            lista = v.find("ocorrencias")
            if lista is not None:
                for l in lista:
                    for o in l.findall("OcorrenciaDeVerba"):
                        ocs.append({
                            "dataInicial": _data_ms(_txt(o, "dataInicial")),
                            "dataFinal": _data_ms(_txt(o, "dataFinal")),
                            "ativo": _txt(o, "ativo"),
                            "base": _num(o, "base"), "divisor": _num(o, "divisor"),
                            "multiplicador": _num(o, "multiplicador"), "quantidade": _num(o, "quantidade"),
                            "dobra": _txt(o, "dobra"), "devido": _num(o, "devido"), "pago": _num(o, "pago"),
                            "indiceAcumulado": _num(o, "indiceAcumulado"),
                        })
            verbas.append({"tipo": v.tag, "descricao": desc, "ocorrencias": ocs})
    return {"meta": meta, "verbas": verbas}


def historicos_do_pjc(conteudo: bytes) -> list[dict]:
    """Históricos salariais do .PJC agrupados em faixas contínuas de mesmo valor (para a tabela editável)."""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        raiz = ET.fromstring(z.read(z.namelist()[0]))
    saida = []
    cont = raiz.find("historicosSalariais")
    for h in (cont.iter("HistoricoSalarial") if cont is not None else []):
        nome = _txt(h, "nome")
        if not nome:
            continue  # referências internas (<internalRef>) também usam a tag HistoricoSalarial
        ocs, mensais = [], []
        for o in h.iter("OcorrenciaDoHistoricoSalarial"):
            d = _txt(o, "dataOcorrencia")
            if d:
                dt = datetime.fromtimestamp(int(d) / 1000, TZ_PJECALC)
                ocs.append(((dt.year, dt.month), _txt(o, "valor")))
                mensais.append({"_k": (dt.year, dt.month), "competencia": f"{dt.month:02d}/{dt.year}",
                                "valor": moeda_br(_txt(o, "valor")),
                                "fgtsRecolhido": _txt(o, "recolhidoFGTS") == "true",
                                "inssRecolhido": _txt(o, "recolhidoINSS") == "true"})
        ocs.sort()
        mensais.sort(key=lambda x: x["_k"])
        for x in mensais:
            del x["_k"]
        faixas = []
        for (ano, mes), valor in ocs:
            v = (valor or "").replace(".", ",")
            if faixas and faixas[-1]["valor"] == v and _seguinte(faixas[-1]["_fim"]) == (ano, mes):
                faixas[-1]["_fim"] = (ano, mes)
            else:
                faixas.append({"_ini": (ano, mes), "_fim": (ano, mes), "valor": v})
        for f in faixas:
            f["competenciaInicial"] = f"{f['_ini'][1]:02d}/{f['_ini'][0]}"
            f["competenciaFinal"] = f"{f['_fim'][1]:02d}/{f['_fim'][0]}"
            del f["_ini"], f["_fim"]
        saida.append({"nome": nome, "fgts": _txt(h, "incidenciaFGTS") == "true",
                      "inss": _txt(h, "incidenciaINSS") == "true", "faixas": faixas, "ocorrencias": mensais})
    return saida


def moeda_br(v: str | None) -> str:
    """'3000.00' (XML) -> '3.000,00' (formato brasileiro, como digitado na tela)."""
    if v is None:
        return ""
    try:
        d = Decimal(v)
    except InvalidOperation:
        return v
    inteiro, _, frac = f"{d:.2f}".partition(".")
    neg = inteiro.startswith("-")
    inteiro = inteiro.lstrip("-")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return ("-" if neg else "") + ".".join(grupos or ["0"]) + "," + frac


def _seguinte(am: tuple[int, int]) -> tuple[int, int]:
    return (am[0] + 1, 1) if am[1] == 12 else (am[0], am[1] + 1)


def comparar_pjc(a: dict, b: dict) -> list[dict]:
    """Compara dois PJCs lidos por ler_pjc: entradas e valores por verba e competência."""
    dif = []
    for k in ("versaoDoSistema", "dataDeLiquidacao", "indicesAcumulados"):
        if a["meta"].get(k) != b["meta"].get(k):
            dif.append({"nivel": "meta", "campo": k, "a": a["meta"].get(k), "b": b["meta"].get(k)})
    va = {v["descricao"]: v for v in a["verbas"]}
    vb = {v["descricao"]: v for v in b["verbas"]}
    for nome in sorted(set(va) | set(vb)):
        if nome not in va or nome not in vb:
            dif.append({"nivel": "verba", "verba": nome, "a": nome in va, "b": nome in vb})
            continue
        oa = {o["dataInicial"]: o for o in va[nome]["ocorrencias"]}
        ob = {o["dataInicial"]: o for o in vb[nome]["ocorrencias"]}
        for comp in sorted(set(oa) | set(ob), key=lambda s: (s or "")[6:] + (s or "")[3:5] + (s or "")[:2]):
            x, y = oa.get(comp, {}), ob.get(comp, {})
            for campo in ("base", "divisor", "multiplicador", "quantidade", "devido", "pago", "indiceAcumulado"):
                if x.get(campo) != y.get(campo):
                    dif.append({"nivel": "ocorrencia", "verba": nome, "competencia": comp, "campo": campo,
                                "a": x.get(campo), "b": y.get(campo)})
    return dif
