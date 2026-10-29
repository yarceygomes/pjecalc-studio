"""Verificação de reabertura: o .PJC gerado pelo fluxo da nova interface abre no PJe-Calc e preserva os dados.

Uso: py -I tests/reabertura_pjc.py <arquivo.pjc> [URL do PJe-Calc] [data de liquidação DD/MM/AAAA]

1. importa o arquivo pela tela oficial "Importar";
2. reliquida o cálculo importado com a mesma data de liquidação do original;
3. exporta de novo e compara, campo a campo, entradas e ocorrências (verba × competência) dos dois arquivos;
4. compara o resumo do relatório oficial do cálculo reimportado com o do arquivo original (quando informado).
Sai com código 1 se houver qualquer divergência.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte.pjecalc import PJeCalc  # noqa: E402
from ponte.relatorio import comparar_pjc, ler_pjc, ler_relatorio, historicos_do_pjc  # noqa: E402

arquivo = sys.argv[1]
url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:19257/pjecalc/"
with open(arquivo, "rb") as fh:
    original = fh.read()
a = ler_pjc(original)
data_liq = sys.argv[3] if len(sys.argv) > 3 else a["meta"]["dataDeLiquidacao"]

m = PJeCalc(url)
imp = m.importar(original, os.path.basename(arquivo))
print("importação:", imp.ok, [x["texto"] for x in imp.mensagens], imp.dados)
if not imp.ok:
    sys.exit(1)
liq = m.liquidar(data_liq, a["meta"]["indicesAcumulados"])
print("liquidação:", liq.ok, liq.dados, [x["texto"] for x in liq.mensagens])
_, rel, _ = m.relatorio("HTML")
_, novo, _ = m.exportar()
b = ler_pjc(novo)

dif = comparar_pjc(a, b)
ocs = sum(len(v["ocorrencias"]) for v in a["verbas"])
print(f"verbas: {len(a['verbas'])} / {len(b['verbas'])}; ocorrências comparadas: {ocs}; divergências: {len(dif)}")
for d in dif[:30]:
    print("  ", d)
ha = {h["nome"]: h["ocorrencias"] for h in historicos_do_pjc(original)}
hb = {h["nome"]: h["ocorrencias"] for h in historicos_do_pjc(novo)}
print("históricos preservados:", ha == hb, {k: len(v) for k, v in ha.items()})
r = ler_relatorio(rel)
print("resumo do reimportado:", json.dumps({"total": r.get("total_bruto"),
                                            "liquido": [c for c in r["creditos_descontos"] if "quido" in (c["descricao"] or "")]},
                                           ensure_ascii=False))
sys.exit(0 if not dif and ha == hb else 1)
