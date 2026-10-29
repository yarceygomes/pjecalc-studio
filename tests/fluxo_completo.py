"""Teste de integração do fluxo mínimo contra uma instância do PJe-Calc.

Uso: py -I tests/fluxo_completo.py [URL] [pasta_saida]
Cria um cálculo fictício, inclui histórico salarial e verbas, liquida, gera o relatório
oficial em HTML, exporta o .PJC e reabre o cálculo para conferir os dados gravados.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte.pjecalc import PJeCalc  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19257/pjecalc/"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "."), "pjstudio-saida")
os.makedirs(OUT, exist_ok=True)

from ponte.conferencia import digito_cnj  # noqa: E402

DADOS = {
    "processo.numero": "0000123", "processo.digito": digito_cnj("0000123", "2025", "5", "08", "0001"),
    "processo.ano": "2025",
    "processo.regiao": "08", "processo.vara": "0001",
    "reclamante.nome": "Pessoa Reclamante Ficticia",
    "reclamante.tipoDocumentoFiscal": "CPF", "reclamante.numeroDocumentoFiscal": "529.982.247-25",
    "reclamado.nome": "Empresa Ficticia Ltda",
    "reclamado.tipoDocumentoFiscal": "CNPJ", "reclamado.numeroDocumentoFiscal": "11.222.333/0001-81",
    "local.estado": "PA", "local.municipio": "BELEM",
    "contrato.dataAdmissao": "01/02/2022", "contrato.dataDemissao": "31/01/2025",
    "contrato.dataAjuizamento": "10/03/2025",
    "contrato.maiorRemuneracao": "3.000,00", "contrato.ultimaRemuneracao": "3.000,00",
}


def show(r):
    print(f"[{'OK' if r.ok else 'FALHA'}] {r.operacao}: {json.dumps(r.mensagens, ensure_ascii=False)} {r.dados}")
    return r


calc = PJeCalc(URL)
print("diagnóstico:", {k: v for k, v in calc.diagnostico().items() if k != "tabelas"})
# 1) validação original: contrato < 5 anos não admite prescrição quinquenal -> o PJe-Calc deve recusar
r = show(calc.novo_calculo({**DADOS, "contrato.prescricaoQuinquenal": True}))
print("   mensagens brutas:", [(m.get("class"), m["text"][:60]) for m in calc.page.messages])
assert not r.ok and any(m["severidade"] == "erro" for m in r.mensagens), "a recusa do PJe-Calc deveria ser erro"
# 2) gravação válida
r = show(calc.novo_calculo(DADOS))
assert r.ok, "falha ao criar cálculo"
show(calc.incluir_historico({"nome": "SALARIO BASE", "competenciaInicial": "02/2022", "competenciaFinal": "01/2025",
                             "valor": "3.000,00", "fgts": True, "inss": True}))
print("históricos:", calc.listar_historicos())
show(calc.incluir_verbas_expressas(["SALDO DE SALÁRIO", "AVISO PRÉVIO", "13º SALÁRIO", "FÉRIAS + 1/3"]))
print("verbas:", calc.listar_verbas())
# com dois históricos (SALARIO BASE + ÚLTIMA REMUNERAÇÃO, gerado a partir do contrato) o PJe-Calc pede a base das
# verbas que usam histórico; escolhe SALARIO BASE para as que ele apontar, como a etapa Verbas faz
pend = show(calc.pendencias())
faltam = {m.get("verba") for m in pend.mensagens if "Falta selecionar pelo menos um Histórico Salarial" in m["texto"]}
for v in calc.listar_verbas():
    if v["nome"] in faltam:
        show(calc.alterar_verba(v["linha"], {}, ["SALARIO BASE"]))
        show(calc.regerar_ocorrencias(v["nome"]))
assert show(calc.pendencias()).ok, "pendências de erro depois de escolher as bases"
assert show(calc.liquidar()).ok, "liquidação recusada"
r, corpo, ctype = calc.relatorio("HTML")
show(r)
with open(os.path.join(OUT, "relatorio.html"), "wb") as fh:
    fh.write(corpo)
print("relatório:", ctype, len(corpo))
r, corpo, nome = calc.exportar()
show(r)
with open(os.path.join(OUT, "exportado.pjc"), "wb") as fh:
    fh.write(corpo)
cid = calc.calculo_id
reaberto = PJeCalc(URL)
show(reaberto.abrir_calculo(cid))
d = reaberto.ler_dados()
def _norm(x):
    s = str(x).upper()
    return (s.lstrip("0") or "0") if s.isdigit() else s  # o PJe-Calc devolve "123" para "0000123"


diverg = {k: (v, d.get(k)) for k, v in DADOS.items() if not isinstance(d.get(k), dict) and _norm(d.get(k)) != _norm(v)}
print("divergências após reabrir:", diverg)
assert not diverg, "dados diferentes depois de reabrir"
print("\nRESULTADO: OK")
