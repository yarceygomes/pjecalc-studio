"""Exploração interativa da interface original via ponte JSF (uso em desenvolvimento)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte.jsf import JsfClient  # noqa: E402

BASE = os.environ.get("PJECALC_URL", "http://127.0.0.1:19257/pjecalc/")


def dump(page, only_enabled=False):
    for name, group in page.fields.items():
        f = group[0]
        if only_enabled and f.disabled:
            continue
        extra = ""
        if f.type == "select":
            extra = f" opts={f.options[:8]}{'...' if len(f.options) > 8 else ''}"
        if f.type == "radio":
            extra = f" radios={[g.value for g in group]}"
        print(f"  {f.type:9s} {name} = {page.get(name)!r} {'DIS' if f.disabled else ''} [{f.label or ''}]{extra}")
    print("  ACTIONS:", [(a.id, a.text) for a in page.actions if (a.text or a.id) and 'j_id38' not in (a.id or '')][:80])


def save_html(page, name):
    out = os.path.join(os.environ.get("TEMP", "."), "pjstudio-html")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
        fh.write(page.last_response)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "novo"
    c = JsfClient(BASE)
    p = c.open("pages/principal.jsf")
    p.click("Novo")
    print("novo:", p.url)
    p.set("reclamanteNome", "Maria Teste da Silva")
    p.set("reclamadoNome", "Empresa Exemplo Ltda")
    p.set("estado", "PA")
    print("municipios:", p.options("municipio")[:5], len(p.options("municipio")))
    p.set("municipio", "BELÉM")
    p.set("dataAdmissaoInputDate", "01/02/2022")
    p.set("dataDemissaoInputDate", "31/01/2025")
    p.set("dataAjuizamentoInputDate", "10/03/2025")
    p.set("valorMaiorRemuneracao", "3.000,00")
    p.set("valorUltimaRemuneracao", "3.000,00")
    p.click("salvar")
    save_html(p, "salvar.xml")
    print("mensagens:", p.errors())
    print("id:", p.get("idCalculo") if p.has("idCalculo") else None, "url:", p.url)
    for seq in sys.argv[2:] or [step]:
        for menu in seq.split(">"):
            p.click(menu)
        print("\n=====", seq, p.url, p.errors())
        save_html(p, seq.replace(" ", "_").replace(">", "__") + ".html")
        dump(p, only_enabled=True)
