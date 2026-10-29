"""Documentos complementares gerados a partir dos resultados oficiais (nunca os substituem)."""
from __future__ import annotations

import csv
import html
import io

AVISO = ("Documento complementar para conferência. Os valores foram transcritos do relatório oficial e do "
         "arquivo .PJC gerados pelo PJe-Calc; não substituem a memória de cálculo oficial.")


def planilha_csv(caso: dict, execucao: dict, resultado: dict) -> bytes:
    """CSV (separador ';', UTF-8 com BOM) com resumo e ocorrências por verba e competência."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    rod = execucao.get("rodape") or {}
    w.writerow([AVISO])
    w.writerow(["Cálculo PJe-Calc nº", execucao.get("calculoId"), "Versão do motor", execucao.get("versaoMotor"),
                "Liquidado em", f"{rod.get('data', '')} {rod.get('hora', '')}".strip(),
                "Revisão das entradas", execucao.get("revisaoEntradas"), "SHA-256 do .PJC", execucao.get("sha256Pjc")])
    w.writerow([])
    rel = resultado.get("relatorio", {})
    w.writerow(["RESUMO DO CÁLCULO (relatório oficial)"])
    w.writerow(["Descrição", "Valor Corrigido", "Juros", "Total"])
    for v in rel.get("verbas", []):
        w.writerow([v["descricao"], v.get("corrigido"), v.get("juros"), v.get("total")])
    if rel.get("total_bruto"):
        t = rel["total_bruto"]
        w.writerow(["Total", t.get("corrigido"), t.get("juros"), t.get("total")])
    w.writerow([])
    w.writerow(["CRÉDITOS E DESCONTOS DO RECLAMANTE"])
    for c in rel.get("creditos_descontos", []):
        w.writerow([c.get("descricao"), c.get("valor")])
    w.writerow([])
    w.writerow(["DÉBITOS DO RECLAMADO POR CREDOR"])
    for c in rel.get("debitos_reclamado", []):
        w.writerow([c.get("descricao"), c.get("valor")])
    w.writerow([])
    w.writerow(["OCORRÊNCIAS POR VERBA E COMPETÊNCIA (arquivo .PJC)"])
    w.writerow(["Verba", "Início", "Fim", "Base", "Divisor", "Multiplicador", "Quantidade", "Dobra", "Devido", "Pago",
                "Índice acumulado"])
    for v in resultado.get("pjc", {}).get("verbas", []):
        for o in v.get("ocorrencias", []):
            w.writerow([v["descricao"], o.get("dataInicial"), o.get("dataFinal"),
                        *(_br(o.get(k)) for k in ("base", "divisor", "multiplicador", "quantidade")),
                        o.get("dobra"), _br(o.get("devido")), _br(o.get("pago")), _br(o.get("indiceAcumulado"))])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _br(v):
    """Número do XML ('1234.5') em notação brasileira sem arredondar ('1234,5')."""
    if v is None:
        return ""
    return str(v).replace(".", ",")


def resumo_complementar(caso: dict, execucao: dict, resultado: dict, cfg: dict) -> str:
    rel = resultado.get("relatorio", {})
    rod = execucao.get("rodape") or {}
    e = html.escape

    def linhas(itens, cols):
        return "".join("<tr>" + "".join(f"<td{' class=n' if i else ''}>{e(str(it.get(c) or ''))}</td>"
                                         for i, c in enumerate(cols)) + "</tr>" for it in itens)

    logo = cfg.get("logoEscritorio") or ""
    logo_html = f'<img src="{e(logo)}" alt="Logotipo do escritório" class="logo">' if logo.startswith("data:image/") else ""
    criterios = "".join(f"<li>{e(c['texto'])}</li>" for c in rel.get("criterios", []))
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Resumo complementar — cálculo {e(str(execucao.get('calculoId')))}</title>
<style>
body{{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;color:#1d2433;max-width:820px;margin:24px auto;padding:0 16px}}
header{{display:flex;gap:16px;align-items:center;border-bottom:2px solid #1d2433;padding-bottom:8px}}
.logo{{max-height:56px}} h1{{font-size:20px;margin:0}} h2{{font-size:15px;margin-top:22px}}
.aviso{{border:2px solid #9a3412;background:#fff7ed;color:#7c2d12;padding:10px 12px;margin:14px 0;font-weight:600}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #d6dae3;padding:4px 6px;text-align:left}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}} footer{{margin-top:24px;font-size:12px;color:#4b5565}}
@media print{{.aviso{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<header>{logo_html}<div><h1>{e(cfg.get('nomeEscritorio') or 'Resumo de cálculo')}</h1>
<div>{e(caso.get('titulo') or '')}</div></div></header>
<div class="aviso">DOCUMENTO COMPLEMENTAR — NÃO É O RELATÓRIO OFICIAL DO PJe-Calc. {e(AVISO)}</div>
<p>Processo: {e(rel.get('cabecalho', {}).get('Processo', ''))} · Cálculo PJe-Calc nº {e(str(execucao.get('calculoId')))}</p>
<h2>Resumo (transcrito do relatório oficial)</h2>
<table><tr><th>Descrição</th><th>Valor corrigido</th><th>Juros</th><th>Total</th></tr>
{linhas(rel.get('verbas', []), ['descricao', 'corrigido', 'juros', 'total'])}
{linhas([{'descricao': 'Total', **(rel.get('total_bruto') or {})}], ['descricao', 'corrigido', 'juros', 'total'])}</table>
<h2>Créditos e descontos do reclamante</h2>
<table>{linhas(rel.get('creditos_descontos', []), ['descricao', 'valor'])}</table>
<h2>Débitos do reclamado por credor</h2>
<table>{linhas(rel.get('debitos_reclamado', []), ['descricao', 'valor'])}</table>
<h2>Critérios informados pelo PJe-Calc</h2><ol>{criterios}</ol>
<footer>Fonte: PJe-Calc Cidadão {e(str(execucao.get('versaoMotor') or ''))}, liquidado por {e(rod.get('usuario', ''))} em
{e(rod.get('data', ''))} às {e(rod.get('hora', ''))}. Revisão das entradas: {e(str(execucao.get('revisaoEntradas')))}.
Integridade do .PJC (SHA-256): {e(str(execucao.get('sha256Pjc') or ''))}.</footer>
</body></html>"""
