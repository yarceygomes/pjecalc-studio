"""Leitura de planilhas .xlsx e .csv para a importação de tabelas (somente biblioteca padrão).

Devolve as células como texto, sem interpretar valores: a associação de colunas, a conversão
de formatos brasileiros e a validação acontecem na prévia exibida ao usuário.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col(ref: str) -> int:
    letras = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n - 1


def ler_xlsx(conteudo: bytes, aba: int = 0) -> dict:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        compartilhadas = []
        if "xl/sharedStrings.xml" in z.namelist():
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz.findall("m:si", NS):
                compartilhadas.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        abas = [s.get("name") for s in wb.findall("m:sheets/m:sheet", NS)]
        # formatos de data: estilos cujo numFmtId é de data (14-22) ou personalizado com d/m/y
        datas = set()
        if "xl/styles.xml" in z.namelist():
            st = ET.fromstring(z.read("xl/styles.xml"))
            fmts = {int(f.get("numFmtId")): f.get("formatCode", "") for f in st.findall("m:numFmts/m:numFmt", NS)}
            for i, xf in enumerate(st.findall("m:cellXfs/m:xf", NS)):
                fid = int(xf.get("numFmtId", "0"))
                if 14 <= fid <= 22 or re.search(r"[dy]", fmts.get(fid, ""), re.I) and "[" not in fmts.get(fid, "["):
                    datas.add(i)
        nomes = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        nomes.sort(key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
        planilha = ET.fromstring(z.read(nomes[aba]))
    linhas: list[list[str]] = []
    for row in planilha.findall("m:sheetData/m:row", NS):
        valores: dict[int, str] = {}
        for c in row.findall("m:c", NS):
            ref, tipo, estilo = c.get("r"), c.get("t"), int(c.get("s", "0"))
            v = c.find("m:v", NS)
            if tipo == "s" and v is not None:
                texto = compartilhadas[int(v.text)]
            elif tipo == "inlineStr":
                texto = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
            elif v is not None and v.text is not None:
                texto = v.text
                if estilo in datas and re.fullmatch(r"\d+(\.\d+)?", texto):
                    d = date(1899, 12, 30) + timedelta(days=float(texto))
                    texto = d.strftime("%d/%m/%Y")
                elif re.fullmatch(r"-?\d+\.\d+|-?\d+", texto) and tipo != "str":
                    texto = texto.replace(".", ",")  # mantém o número sem arredondar, em notação brasileira
            else:
                texto = ""
            valores[_col(ref)] = texto
        if valores:
            largura = max(valores) + 1
            linhas.append([valores.get(i, "") for i in range(largura)])
    return {"abas": abas, "linhas": linhas}


def ler_csv(conteudo: bytes) -> dict:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    amostra = texto[:4096]
    sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    if amostra.count("\t") > max(amostra.count(";"), amostra.count(",")):
        sep = "\t"
    linhas = [ln for ln in csv.reader(io.StringIO(texto), delimiter=sep)]
    return {"abas": ["CSV"], "linhas": [ln for ln in linhas if any(c.strip() for c in ln)], "separador": sep}


def ler(conteudo: bytes, nome: str) -> dict:
    if nome.lower().endswith((".xlsx", ".xlsm")):
        return ler_xlsx(conteudo)
    if nome.lower().endswith(".xls"):
        raise ValueError("Formato .xls (Excel 97-2003) não suportado: salve a planilha como .xlsx ou .csv.")
    return ler_csv(conteudo)
