"""Integração (Fase 2): ocorrências mês a mês e verbas do lançamento manual, pelo caminho completo da interface.

Uso: py -I tests/ocorrencias_verbas_manuais.py [URL do PJe-Calc] [pasta de saída]

Caso: horas extras 50% (expressa) com quantidades mensais; uma verba manual calculada sobre o histórico
salarial; uma verba manual de valor informado mês a mês. O rascunho é gravado e executado por
ponte/sincronizar.py (as mesmas funções usadas pelo servidor). Confere:
  1. liquidação sem pendências do tipo erro;
  2. quantidades e valores devidos no .PJC iguais aos informados;
  3. nova gravação sem mudanças não reenvia nada (hash por item);
  4. alterar uma competência reenvia só as ocorrências daquela verba.
O .PJC exportado fica na pasta de saída para tests/reabertura_pjc.py.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte import sincronizar  # noqa: E402
from ponte.armazenamento import Armazenamento, rascunho_vazio  # noqa: E402
from ponte.pjecalc import PJeCalc  # noqa: E402
from ponte.relatorio import ler_pjc  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19257/pjecalc/"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "."), "pjstudio-saida")
os.makedirs(OUT, exist_ok=True)

COMPS = ["02/2023", "03/2023", "04/2023", "05/2023", "06/2023", "07/2023"]
QTD_HE = {"02/2023": "10,0000", "03/2023": "12,5000", "04/2023": "8,0000", "05/2023": "15,0000", "07/2023": "5,2500"}
DEVIDO_INFORMADO = {"02/2023": "150,00", "03/2023": "150,00", "05/2023": "210,35"}

r = rascunho_vazio()
r["dados"] = {
    "reclamante.nome": "Pessoa Ficticia Horas Extras", "reclamado.nome": "Empresa Ficticia Ltda",
    "local.estado": "PA", "local.municipio": "BELEM",
    "contrato.dataAdmissao": "01/02/2023", "contrato.dataDemissao": "31/07/2023", "contrato.dataAjuizamento": "10/09/2023",
    "contrato.maiorRemuneracao": "3.000,00", "contrato.ultimaRemuneracao": "3.000,00",
}
r["historicos"] = [{"id": "h1", "nome": "SALARIO BASE", "fgts": True, "inss": True,
                    "ocorrencias": sincronizar.expandir("02/2023", "07/2023", "3.000,00")}]
r["verbas"] = ["HORAS EXTRAS 50%"]


def linhas(valores: dict, chave: str) -> list[dict]:
    # como a Planilha da interface guarda: todas as competências, células vazias onde nada foi informado
    return [{"competencia": c, "quantidade": "", "devido": "", "pago": "", "ativo": True, "divisor": "", "multiplicador": "",
             chave: valores.get(c, "")} for c in COMPS]


r["verbasConfig"] = {
    "HORAS EXTRAS 50%": {"bases": ["SALARIO BASE"], "ocorrencias": linhas(QTD_HE, "quantidade")},
    "GRATIFICACAO INFORMADA TESTE": {"ocorrencias": linhas(DEVIDO_INFORMADO, "devido")},
}
r["verbasManuais"] = [
    {"id": "vm1", "descricao": "ADICIONAL MANUAL TESTE", "assuntoCnj": "2086 - Horas Extras", "bases": ["SALARIO BASE"],
     "parametros": {"valor": "CALCULADO", "caracteristicaVerba": "COMUM", "ocorrenciaPagto": "MENSAL",
                    "tipoDaBaseTabelada": "HISTORICO_SALARIAL", "tipoDeDivisor": "OUTRO_VALOR", "outroValorDoDivisor": "220",
                    "outroValorDoMultiplicador": "0,4", "tipoDaQuantidade": "INFORMADA", "valorInformadoDaQuantidade": "20",
                    "irpf": True, "inss": True, "fgts": True}},
    {"id": "vm2", "descricao": "GRATIFICACAO INFORMADA TESTE", "assuntoCnj": "2086",
     "parametros": {"valor": "INFORMADO", "caracteristicaVerba": "COMUM", "ocorrenciaPagto": "MENSAL",
                    "irpf": True, "inss": True, "fgts": False}},
    # verba principal cuja base é outra verba (10% das horas extras do mês)
    {"id": "vm3", "descricao": "ADICIONAL SOBRE HE TESTE", "assuntoCnj": "2086",
     "basesVerbas": [{"verba": "HORAS EXTRAS 50%", "integralizar": "NAO"}],
     "parametros": {"valor": "CALCULADO", "caracteristicaVerba": "COMUM", "ocorrenciaPagto": "MENSAL",
                    "tipoDeDivisor": "OUTRO_VALOR", "outroValorDoDivisor": "1", "outroValorDoMultiplicador": "0,1",
                    "tipoDaQuantidade": "INFORMADA", "valorInformadoDaQuantidade": "1", "irpf": True, "inss": True, "fgts": True}},
    # reflexos lançados manualmente
    {"id": "vr1", "descricao": "13O REFLEXO TESTE", "assuntoCnj": "2086", "principal": "ADICIONAL MANUAL TESTE",
     "comportamentoDoReflexo": "MEDIA_PELO_VALOR", "tratamentoFracaoReflexo": "MANTER",
     "parametros": {"tipoDeVerba": "REFLEXO", "valor": "CALCULADO", "caracteristicaVerba": "DECIMO_TERCEIRO_SALARIO",
                    "ocorrenciaPagto": "DEZEMBRO", "tipoDeDivisor": "OUTRO_VALOR", "outroValorDoDivisor": "12",
                    "outroValorDoMultiplicador": "1", "tipoDaQuantidade": "INFORMADA", "valorInformadoDaQuantidade": "1",
                    "irpf": True, "inss": True, "fgts": True}},
    {"id": "vr2", "descricao": "INTEGRACAO TESTE", "assuntoCnj": "2086", "principal": "HORAS EXTRAS 50%",
     "comportamentoDoReflexo": "VALOR_MENSAL", "tratamentoFracaoReflexo": "MANTER",
     "parametros": {"tipoDeVerba": "REFLEXO", "valor": "CALCULADO", "caracteristicaVerba": "COMUM",
                    "ocorrenciaPagto": "MENSAL", "tipoDeDivisor": "OUTRO_VALOR", "outroValorDoDivisor": "6",
                    "outroValorDoMultiplicador": "1", "tipoDaQuantidade": "INFORMADA", "valorInformadoDaQuantidade": "1",
                    "irpf": True, "inss": True, "fgts": True}},
]

pasta = tempfile.mkdtemp(prefix="pjstudio-teste-")
falhas = []


def confere(cond, texto):
    print(("  ok   " if cond else "  FALHA ") + texto)
    if not cond:
        falhas.append(texto)


def passos(res):
    for p in res.get("passos", []):
        print(f"  [{'OK' if p.get('ok') else '--'}] {p['rotulo']}: {[m['texto'] for m in p.get('mensagens', [])][:3]}")
    return [p["rotulo"] for p in res.get("passos", [])]


try:
    armaz = Armazenamento(pasta)
    caso = armaz.criar({"titulo": "Fase 2 - ocorrências e verbas manuais", "rascunho": r}, "teste")

    print("1) gravar e executar")
    g = sincronizar.gravar(caso, URL, armaz, "teste")
    passos(g)
    confere(g["ok"], "gravação no PJe-Calc")
    ex = sincronizar.executar(armaz.obter(caso["id"]), URL, armaz, "teste")
    passos(ex)
    caso = armaz.obter(caso["id"])
    pend = caso["pjecalc"].get("pendencias", [])
    confere(ex["ok"], "execução (liquidação, relatório e .PJC) concluída")
    confere(not [m for m in pend if m["severidade"] == "erro"], f"sem pendências do tipo erro: {[m['texto'] for m in pend]}")

    eid = ex["execucao"]["id"]
    with open(os.path.join(armaz.pasta_execucao(caso["id"], eid), "calculo.pjc"), "rb") as fh:
        corpo = fh.read()
    destino = os.path.join(OUT, "ocorrencias_verbas_manuais.pjc")
    with open(destino, "wb") as fh:
        fh.write(corpo)
    pjc = {v["descricao"]: v for v in ler_pjc(corpo)["verbas"]}
    num = lambda s: s.replace(".", "").replace(",", ".")  # noqa: E731 - "12,5000" -> "12.5000"

    def por_comp(verba, campo):
        return {o["dataInicial"][3:]: o[campo] for o in pjc.get(verba, {}).get("ocorrencias", [])}
    he = por_comp("HORAS EXTRAS 50%", "quantidade")
    confere(all(float(he.get(c) or 0) == float(num(q)) for c, q in QTD_HE.items()) and float(he.get("06/2023") or 0) == 0,
            f"quantidades de HE 50% no .PJC: {he}")
    gi = por_comp("GRATIFICACAO INFORMADA TESTE", "devido")
    confere(all(float(gi.get(c) or 0) == float(num(v)) for c, v in DEVIDO_INFORMADO.items()), f"devido informado no .PJC: {gi}")
    confere(set(pjc) >= {"ADICIONAL SOBRE HE TESTE", "13O REFLEXO TESTE SOBRE ADICIONAL MANUAL TESTE",
                         "INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%"}, "verba com verba como base e reflexos manuais no .PJC")
    he_dev = por_comp("HORAS EXTRAS 50%", "devido")
    ad = por_comp("ADICIONAL SOBRE HE TESTE", "devido")
    confere(all(abs(float(ad.get(c) or 0) - round(float(he_dev[c]) * 0.1, 2)) <= 0.01 for c in he_dev),
            f"ADICIONAL SOBRE HE = 10% de HE 50% por mês: {ad} / {he_dev}")
    integ = por_comp("INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%", "devido")
    confere(all(abs(float(integ.get(c) or 0) - round(float(he_dev[c]) / 6, 2)) <= 0.01 for c in he_dev),
            f"reflexo manual mensal = HE 50% / 6: {integ}")
    am = por_comp("ADICIONAL MANUAL TESTE", "quantidade")
    confere(len(am) == 6 and all(float(x) == 20 for x in am.values()), f"verba manual calculada no .PJC: {am}")
    print("   líquido:", ex["execucao"].get("liquido"))

    print("2) nova gravação sem mudanças")
    g = sincronizar.gravar(armaz.obter(caso["id"]), URL, armaz, "teste")
    rot = passos(g)
    confere(g["ok"] and not any(x.startswith(("Ocorrências", "Incluir", "Substituir", "Parâmetros", "Alterar", "Desativar")) for x in rot),
            "nada reenviado quando o rascunho não mudou")

    print("3) alterar uma competência de HE 50%")
    caso = armaz.obter(caso["id"])
    r2 = json.loads(json.dumps(caso["rascunho"]))
    next(o for o in r2["verbasConfig"]["HORAS EXTRAS 50%"]["ocorrencias"] if o["competencia"] == "06/2023")["quantidade"] = "3,0000"
    caso = armaz.atualizar(caso["id"], {"rascunho": r2}, "teste")
    g = sincronizar.gravar(caso, URL, armaz, "teste")
    rot = passos(g)
    confere(g["ok"] and [x for x in rot if x.startswith("Ocorrências")] == ["Ocorrências da verba HORAS EXTRAS 50% (6 competências)"]
            and not any(x.startswith(("Incluir verba manual", "Substituir")) for x in rot),
            "somente as ocorrências de HE 50% foram reenviadas")

    print("4) alterar um reflexo manual (Parametrizar) e retirar o outro do rascunho (desativação)")
    caso = armaz.obter(caso["id"])
    r3 = json.loads(json.dumps(caso["rascunho"]))
    next(v for v in r3["verbasManuais"] if v["id"] == "vr2")["parametros"]["outroValorDoDivisor"] = "5"
    r3["verbasManuais"] = [v for v in r3["verbasManuais"] if v["id"] != "vr1"]
    caso = armaz.atualizar(caso["id"], {"rascunho": r3}, "teste")
    g = sincronizar.gravar(caso, URL, armaz, "teste")
    rot = passos(g)
    confere(g["ok"] and "Alterar reflexo manual INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%" in rot
            and "Desativar reflexo manual 13O REFLEXO TESTE SOBRE ADICIONAL MANUAL TESTE" in rot
            and not any(x.startswith(("Incluir", "Substituir")) for x in rot), "reflexo alterado e reflexo retirado")
    m = PJeCalc(URL)
    m.abrir_calculo(caso["pjecalc"]["calculoId"])
    verbas = m.listar_verbas()
    refl = {x["nome"]: x["ativo"] for v in verbas for x in v["reflexos"]}
    confere(refl.get("13O REFLEXO TESTE SOBRE ADICIONAL MANUAL TESTE") is False
            and refl.get("INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%") is True, f"estado dos reflexos no PJe-Calc: {refl}")
    he = next(v for v in verbas if v["nome"] == "HORAS EXTRAS 50%")
    rr = next(x for x in he["reflexos"] if x["nome"].startswith("INTEGRACAO"))
    pre = f"formulario:listagem:{he['linha']}:listaReflexo:{rr['indice']}:"
    pg = m.page
    pg.click(next(a.id for a in pg.actions if (a.id or "").startswith(pre) and a.text == "Parametrizar"))
    confere(pg.get("outroValorDoDivisor").startswith("5"), f"divisor do reflexo relido no PJe-Calc: {pg.get('outroValorDoDivisor')}")
    pg.click("cancelar")
    confere("Regerar ocorrências de INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%" in rot, "ocorrências do reflexo regeradas")

    print("5) alterar o multiplicador de HE 50% (parâmetros + regerar + reaplicar quantidades)")
    caso = armaz.obter(caso["id"])
    r4 = json.loads(json.dumps(caso["rascunho"]))
    r4["verbasConfig"]["HORAS EXTRAS 50%"]["alteracoes"] = {"outroValorDoMultiplicador": "1,6"}
    caso = armaz.atualizar(caso["id"], {"rascunho": r4}, "teste")
    g = sincronizar.gravar(caso, URL, armaz, "teste")
    rot = passos(g)
    confere(g["ok"] and [x for x in rot if x.startswith(("Parâmetros", "Regerar", "Ocorrências"))] == [
        "Parâmetros da verba HORAS EXTRAS 50%", "Regerar ocorrências de HORAS EXTRAS 50%",
        "Ocorrências da verba HORAS EXTRAS 50% (6 competências)"], "parâmetros, regeração e ocorrências, nessa ordem")
    ex = sincronizar.executar(armaz.obter(caso["id"]), URL, armaz, "teste")
    caso = armaz.obter(caso["id"])
    with open(os.path.join(armaz.pasta_execucao(caso["id"], ex["execucao"]["id"]), "calculo.pjc"), "rb") as fh:
        corpo = fh.read()
    with open(destino, "wb") as fh:
        fh.write(corpo)
    pjc = {v["descricao"]: v for v in ler_pjc(corpo)["verbas"]}
    qtd = por_comp("HORAS EXTRAS 50%", "quantidade")
    dev = por_comp("HORAS EXTRAS 50%", "devido")
    mult = por_comp("HORAS EXTRAS 50%", "multiplicador")
    confere(ex["ok"] and all(float(mult[c]) == 1.6 for c in mult), f"multiplicador novo nas ocorrências: {mult}")
    confere(float(qtd["02/2023"]) == 10 and float(qtd["06/2023"]) == 3 and float(qtd["07/2023"]) == 5.25,
            f"quantidades informadas reaplicadas após regerar: {qtd}")
    confere(abs(float(dev["02/2023"]) - round(3000 / 220 * 1.6 * 10, 2)) <= 0.01, f"devido de 02/2023 com o multiplicador novo: {dev}")
    integ = por_comp("INTEGRACAO TESTE SOBRE HORAS EXTRAS 50%", "devido")
    confere(all(abs(float(integ.get(c) or 0) - round(float(dev[c]) / 5, 2)) <= 0.01 for c in dev),
            f"reflexo manual alterado = HE 50% / 5: {integ}")
    print(f"\n.PJC para reabertura: {destino}")
finally:
    shutil.rmtree(pasta, ignore_errors=True)

print("\nRESULTADO:", "OK" if not falhas else f"{len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
