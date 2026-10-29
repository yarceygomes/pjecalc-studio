"""Padrões do escritório para as funções do PJe-Calc (honorários, custas, imposto de renda, correção…).

Um padrão é o preenchimento de uma tela do PJe-Calc gravado pelo usuário no Studio: a sequência de campos
alterados e de botões acionados (ex.: Honorários › Novo › Tipo, Devedor, Alíquota 15%, Base Bruto, Credor ›
Salvar). Aplicar o padrão em outro cálculo repete a sequência na mesma tela oficial, que valida e grava como
se a pessoa tivesse digitado. Nenhum valor é gravado por fora do PJe-Calc.

Passo:  {"tipo": "campo", "nome", "rotulo", "valor", "valorRotulo" (o texto da opção escolhida), "evento": bool}
      | {"tipo": "acao", "id", "texto"}
"""
from __future__ import annotations

from .jsf import fold
from .tela import SessaoTela

TIPOS_PASSO = ("campo", "acao")


def validar_passos(passos) -> list[dict]:
    """Normaliza os passos recebidos da interface (só o necessário para repetir; nada executável)."""
    saida = []
    for p in passos or []:
        if not isinstance(p, dict) or p.get("tipo") not in TIPOS_PASSO:
            continue
        if p["tipo"] == "campo" and p.get("nome"):
            saida.append({"tipo": "campo", "nome": str(p["nome"]), "rotulo": str(p.get("rotulo") or ""),
                          "valor": p.get("valor") if isinstance(p.get("valor"), (str, bool, int, float)) else "",
                          "evento": bool(p.get("evento")),
                          **({"valorRotulo": str(p["valorRotulo"])} if isinstance(p.get("valorRotulo"), str) else {})})
        elif p["tipo"] == "acao" and (p.get("id") or p.get("texto")):
            saida.append({"tipo": "acao", "id": str(p.get("id") or ""), "texto": str(p.get("texto") or "")})
    return saida


def _percorrer(itens: list, dentro_tabela: bool = False):
    for i in itens:
        yield i, dentro_tabela
        if i["t"] == "grupo":
            yield from _percorrer(i["itens"], dentro_tabela)
        elif i["t"] == "tabela":
            for ln in i["linhas"]:
                for cel in ln["celulas"]:
                    yield from _percorrer(cel["campos"] + cel["acoes"], True)


def _resolver_campo(sessao: SessaoTela, desc: dict, passo: dict) -> str | None:
    if passo["nome"] in sessao.page.fields:
        return passo["nome"]
    # o id mudou (ex.: outra versão do PJe-Calc): procura pelo rótulo, fora das tabelas
    alvo = fold(passo["rotulo"])
    if alvo:
        for i, em_tabela in _percorrer(desc["itens"]):
            if i["t"] == "campo" and not em_tabela and fold(i.get("rotulo") or "") == alvo:
                return i["nome"]
    return None


def _resolver_acao(sessao: SessaoTela, desc: dict, passo: dict) -> str | None:
    ids = {a.id for a in sessao.page.actions if a.id}
    if passo["id"] in ids or passo["id"].startswith("aba:"):
        return passo["id"]
    alvo = fold(passo["texto"])
    for i, em_tabela in _percorrer(desc["itens"]):
        if i["t"] == "acao" and not em_tabela and fold(i["texto"]) == alvo:
            return i["id"]
    return None


def aplicar(sessao: SessaoTela, passos: list[dict]) -> dict:
    """Repete os passos na tela aberta. Devolve {"tela": descrição final, "registro": [...], "ok": bool}.

    Os campos são enviados junto com o próximo botão (como no navegador); campo com evento A4J dispara o
    evento na hora, porque ele costuma habilitar ou mostrar os campos seguintes. Um passo que não pode ser
    repetido (campo ou botão que não existe mais) interrompe a aplicação antes de qualquer botão seguinte.
    """
    desc = sessao.descrever()
    pendentes: dict = {}
    registro: list[dict] = []
    for passo in validar_passos(passos):
        if passo["tipo"] == "campo":
            nome = _resolver_campo(sessao, desc, passo)
            if not nome:
                registro.append({"ok": False, "texto": f"Campo “{passo['rotulo'] or passo['nome']}” não está na tela."})
                return {"tela": desc, "registro": registro, "ok": False}
            pendentes[nome] = passo["valor"]
            if passo["evento"]:
                desc = sessao.alterar(dict(pendentes), nome)
                pendentes = {}
            registro.append({"ok": True, "texto": f"{passo['rotulo'] or nome}: {passo.get('valorRotulo') or _mostrar(passo['valor'])}"})
            continue
        acao = _resolver_acao(sessao, desc, passo)
        if not acao:
            registro.append({"ok": False, "texto": f"Botão “{passo['texto']}” não está na tela."})
            return {"tela": desc, "registro": registro, "ok": False}
        desc = sessao.acionar(acao, dict(pendentes))
        pendentes = {}
        erros = [m["texto"] for m in desc["mensagens"] if m["severidade"] == "erro"]
        registro.append({"ok": not erros, "texto": f"Botão {passo['texto']}" + (f": {'; '.join(erros)}" if erros else "")})
        if erros:
            return {"tela": desc, "registro": registro, "ok": False}
    if pendentes:  # padrão sem botão final: os valores ficam na tela para a pessoa conferir e salvar
        sessao.preencher(pendentes)
        desc = sessao.descrever()
    return {"tela": desc, "registro": registro, "ok": True}


def _mostrar(valor) -> str:
    if valor is True:
        return "marcado"
    if valor is False:
        return "desmarcado"
    return str(valor) if valor not in (None, "") else "(vazio)"
