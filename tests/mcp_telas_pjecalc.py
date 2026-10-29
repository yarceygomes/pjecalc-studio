"""Teste das ferramentas de telas do assistente contra um PJe-Calc e um Studio abertos, SEM salvar nada:
abre telas, lê, troca de aba, inicia um lançamento novo e preenche campos, e fecha a tela sem salvar.

Uso:  py -I tests/mcp_telas_pjecalc.py <arquivo de conexão do Studio> <id de um cálculo já enviado ao PJe-Calc>
"""
import json
import sys
import urllib.request

with open(sys.argv[1], encoding="utf-8") as fh:
    conexao = json.load(fh)
CASO = sys.argv[2]
n = 0


def chamar(nome, **args):
    global n
    n += 1
    req = urllib.request.Request(conexao["url"], method="POST", headers={"Authorization": "Bearer " + conexao["chave"], "Content-Type": "application/json"},
                                 data=json.dumps({"jsonrpc": "2.0", "id": n, "method": "tools/call", "params": {"name": nome, "arguments": args}}).encode())
    with urllib.request.urlopen(req, timeout=600) as r:
        res = json.loads(r.read())["result"]
    texto = res["content"][0]["text"]
    assert not res["isError"], f"{nome}: {texto}"
    return json.loads(texto)


telas = chamar("telas_pjecalc")["telas"]
print(len(telas), "telas disponíveis")

# 1) tabela auxiliar (sem cálculo): salário mínimo
r = chamar("abrir_tela", tela="t-salario-minimo")
t = r["tela"]
linhas = sum(len(x["linhas"]) for x in t.get("tabelas", []))
print(f"Salário Mínimo: {linhas} linha(s) de tabela, {len(t.get('acoes', []))} ação(ões); ex.: {t['tabelas'][0]['linhas'][:1] if t.get('tabelas') else '-'}")
assert linhas > 0
chamar("fechar_tela", token=r["token"])

# 2) telas de cálculo: lê cada uma e mostra o que o Claude recebe
for tela in ("honorarios", "ferias", "faltas", "multas", "custas", "inss", "irpf", "cartao", "dados"):
    r = chamar("abrir_tela", tela=tela, id=CASO)
    t = r["tela"]
    print(f"{t['titulo']!r}: {len(t.get('campos', []))} campos, {len(t.get('acoes', []))} ações, {len(t.get('abas', []))} abas, "
          f"{len(t.get('tabelas', []))} tabelas; ações: {', '.join(a['texto'] or a['id'] for a in t.get('acoes', [])[:8])}")
    if tela == "dados" and t.get("abas"):
        outra = next(a for a in t["abas"] if not a["ativa"])
        t2 = chamar("acionar_tela", token=r["token"], acao=outra["acao"])["tela"]
        ativa = next((a["titulo"] for a in t2.get("abas", []) if a["ativa"]), None)
        print(f"   troca de aba para {outra['titulo']!r}: ativa agora {ativa!r}, {len(t2.get('campos', []))} campos")
        assert ativa == outra["titulo"]
    if tela == "honorarios":
        novo = next((a for a in t.get("acoes", []) if (a["texto"] or "").strip().lower() in ("novo", "incluir")), None)
        if novo:
            t2 = chamar("acionar_tela", token=r["token"], acao=novo["id"])["tela"]
            editaveis = [c for c in t2.get("campos", []) if not c.get("desabilitado") and c["tipo"] in ("lista", "radio", "texto")]
            print(f"   'Novo' abriu o formulário: {len(t2.get('campos', []))} campos; ex.: " +
                  "; ".join(f"{c.get('rotulo')} [{c['tipo']}{', evento' if c.get('evento') else ''}]" for c in editaveis[:6]))
            lista = next((c for c in editaveis if c["tipo"] in ("lista", "radio") and c.get("opcoes")), None)
            if lista:
                valor = lista["opcoes"][-1].split("=")[0]
                t3 = chamar("preencher_tela", token=r["token"], valores={lista["nome"]: valor})["tela"]
                lido = next(c for c in t3["campos"] if c["nome"] == lista["nome"])["valor"]
                print(f"   preencheu {lista.get('rotulo')!r} = {valor!r}: tela devolveu {lido!r}")
                assert str(lido) == valor
    chamar("fechar_tela", token=r["token"])  # sem salvar
print("OK: telas do PJe-Calc operadas pelo assistente (nada salvo)")
