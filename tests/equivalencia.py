"""Prova de equivalência entre dois cálculos do PJe-Calc.

Uso: py -I tests/equivalencia.py <referencia.pjc> <nova_interface.pjc> [referencia.html] [nova_interface.html]

  referencia.pjc      exportado de um cálculo preenchido MANUALMENTE na interface original
  nova_interface.pjc  exportado pelo fluxo da nova interface, com os mesmos dados
  *.html              (opcional) relatórios oficiais em HTML ("Imprimir" › HTML) de cada um

Compara versão do sistema, data de liquidação, critério de índices, cada verba e cada ocorrência
(base, divisor, multiplicador, quantidade, devido, pago, índice acumulado) e, se informados os
relatórios, o resumo, os créditos/descontos e os débitos do reclamado. Termina com código 0
somente se não houver nenhuma divergência.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte.relatorio import comparar_pjc, ler_pjc, ler_relatorio, historicos_do_pjc  # noqa: E402


def ler(p):
    with open(p, "rb") as fh:
        return fh.read()


ref, novo = ler(sys.argv[1]), ler(sys.argv[2])
a, b = ler_pjc(ref), ler_pjc(novo)
divergencias = comparar_pjc(a, b)
ha = {h["nome"]: h["ocorrencias"] for h in historicos_do_pjc(ref)}
hb = {h["nome"]: h["ocorrencias"] for h in historicos_do_pjc(novo)}
if ha != hb:
    divergencias.append({"nivel": "historico", "a": sorted(ha), "b": sorted(hb)})
print(f"Versão: {a['meta']['versaoDoSistema']} × {b['meta']['versaoDoSistema']}")
print(f"Verbas: {len(a['verbas'])} × {len(b['verbas'])}; ocorrências: "
      f"{sum(len(v['ocorrencias']) for v in a['verbas'])} × {sum(len(v['ocorrencias']) for v in b['verbas'])}")
if len(sys.argv) > 4:
    ra, rb = ler_relatorio(ler(sys.argv[3])), ler_relatorio(ler(sys.argv[4]))
    for secao in ("verbas", "total_bruto", "creditos_descontos", "debitos_reclamado", "criterios"):
        if ra.get(secao) != rb.get(secao):
            divergencias.append({"nivel": "relatorio", "secao": secao, "a": ra.get(secao), "b": rb.get(secao)})
for d in divergencias:
    print("DIVERGÊNCIA:", d)
print("RESULTADO:", "EQUIVALENTES" if not divergencias else f"{len(divergencias)} divergência(s)")
sys.exit(0 if not divergencias else 1)
