"""Assistente Claude: ferramentas MCP do PJe-Calc Studio.

Deixa o Claude (Claude Desktop ou Claude Code) operar o Studio pelas mesmas regras da interface: ler e criar
cálculos, responder as perguntas guiadas, preencher campos, verbas, históricos e critérios, conferir, enviar ao
PJe-Calc e ler o resultado. Nenhum valor é calculado aqui: quem calcula é o PJe-Calc.

O servidor do Studio atende o protocolo em POST /mcp (protegido por chave); as pontes locais (extensão do Claude
Desktop em extensao/ e mcp_studio.py) só repassam as mensagens entre o Claude e esse endereço.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
import traceback
import urllib.parse
from datetime import date

from . import catalogo, conferencia
from .pjecalc import CAMPOS_ATUALIZACAO, CAMPOS_FGTS

VERSOES_PROTOCOLO = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

# Respostas das perguntas guiadas; os ids são os de DOCUMENTOS e DESLIGAMENTOS em web/app.js
DOCUMENTOS = {"inicial": "Petição inicial", "sentenca": "Sentença ou acórdão", "acordo": "Acordo", "outro": "Outro documento"}
DESLIGAMENTOS = {"sem_justa_causa": "Dispensa sem justa causa", "rescisao_indireta": "Rescisão indireta",
                 "pedido_demissao": "Pedido de demissão", "justa_causa": "Justa causa", "culpa_reciproca": "Culpa recíproca",
                 "prazo_determinado": "Fim do contrato por prazo determinado", "em_vigor": "Contrato ainda em vigor"}
BASES = {"HISTORICO_SALARIAL": "Histórico salarial", "MAIOR_REMUNERACAO": "Maior remuneração",
         "SALARIO_MINIMO": "Salário mínimo", "SALARIO_DA_CATEGORIA": "Piso salarial"}

# Campos do formulário (mesmas chaves das etapas do Studio): tipo e, para listas, a chave das opções em catalogo.OPCOES
CAMPOS = {
    "reclamante.nome": "texto", "reclamante.tipoDocumentoFiscal": "lista", "reclamante.numeroDocumentoFiscal": "documento",
    "reclamante.tipoDocumentoPrevidenciario": "lista", "reclamante.numeroDocumentoPrevidenciario": "texto",
    "reclamado.nome": "texto", "reclamado.tipoDocumentoFiscal": "lista", "reclamado.numeroDocumentoFiscal": "documento",
    "local.estado": "estado", "local.municipio": "municipio",
    "processo.numeroCompleto": "cnj", "processo.valorDaCausa": "moeda", "processo.autuadoEm": "data",
    "contrato.dataAdmissao": "data", "contrato.dataDemissao": "data", "contrato.dataAjuizamento": "data",
    "contrato.dataInicioCalculo": "data", "contrato.dataTerminoCalculo": "data",
    "contrato.prescricaoQuinquenal": "marca", "contrato.prescricaoFgts": "marca", "contrato.regime": "lista",
    "contrato.maiorRemuneracao": "moeda", "contrato.ultimaRemuneracao": "moeda",
    "contrato.apuracaoAvisoPrevio": "lista", "contrato.prazoAvisoInformado": "inteiro", "contrato.projetaAvisoIndenizado": "marca",
    "contrato.limitarAvos": "marca", "contrato.zeraValorNegativo": "marca",
    "contrato.consideraFeriadoEstadual": "marca", "contrato.consideraFeriadoMunicipal": "marca",
    "observacoes.comentarios": "texto", "jornada.cargaHorariaPadrao": "moeda", "jornada.sabadoDiaUtil": "marca",
}
META = ("titulo", "cliente", "parteContraria", "processo", "responsavel", "observacoes")

INSTRUCOES = """Você opera o PJe-Calc Studio e, por ele, TODO o PJe-Calc (o programa oficial de cálculos da Justiça do Trabalho). Faça o cálculo inteiro você mesmo, do documento ao resultado oficial. Quem calcula os valores é sempre o PJe-Calc: você preenche e confere, nunca calcula nem inventa valores.

FIDELIDADE AO DOCUMENTO (petição inicial, sentença, acórdão, acordo, ata ou texto do usuário)
- Leia o documento inteiro antes de começar e monte uma lista de tudo o que ele determina: partes e processo, datas (admissão, demissão, ajuizamento, período), salários e sua evolução, forma de término do contrato, cada verba (com período, base, quantidade, percentual, reflexos), prescrição, compensações e deduções, correção monetária e juros, FGTS e multa, dano moral e outros valores fixos, multas, honorários (percentual, base, quem paga), custas, contribuição social, imposto de renda, pensão, justiça gratuita, limites e ressalvas.
- Cada item da lista tem de entrar no cálculo exatamente como está no documento: mesma data, mesmo valor, mesmo percentual, mesmo período, mesma base. Não arredonde, não "melhore", não complete por conta própria.
- Documento omisso: se o PJe-Calc tem um padrão legal para o ponto (ex.: divisor 220, adicional de 50%, alíquotas oficiais, índices das tabelas oficiais), use o padrão e registre que usou. Pergunte ao usuário SÓ quando o dado é indispensável, não está no documento e não tem padrão (ex.: salário não informado, data de admissão ausente, critério de correção que a decisão manda "definir na liquidação"). Junte todas as dúvidas numa pergunta só, no começo, e continue o resto enquanto isso.
- Documento contraditório ou ilegível em um ponto: pergunte só sobre esse ponto, citando o trecho.
- Registre o trecho do documento que fundamenta cada escolha que depende do caso (configurar_verba: justificativa e trecho).

FAÇA VOCÊ MESMO, NÃO PEÇA AO USUÁRIO
- Nunca peça ao usuário para preencher telas, clicar botões, abrir o Studio em outra aba ou conferir algo que você mesmo pode conferir. O usuário só precisa deixar o PJe-Calc e o PJe-Calc Studio abertos.
- Etapas principais: ferramentas do Studio (criar_calculo, responder_perguntas, preencher_campos, definir_historico, definir_verbas, configurar_verba, definir_correcao, definir_fgts).
- Todo o resto do PJe-Calc (Faltas, Férias, Cartão de Ponto, Multas e Indenizações, Honorários, Custas, Contribuição Social, Imposto de Renda, Pensão, Previdência Privada, Seguro-desemprego, Salário-família, Dados do Cálculo completos, Verbas completas, FGTS completo, Correção completa, Pagamentos, Liquidar, Imprimir, Exportar, Tabelas): telas_pjecalc, abrir_tela, preencher_tela, acionar_tela. Leia a tela, preencha os campos, use a ação de salvar/confirmar da tela e leia as mensagens; se o PJe-Calc apontar erro, corrija e salve de novo. Depois marque o item correspondente em responder_perguntas (outrosItens: "feito" ou "nao").
- As telas de um cálculo só abrem depois do primeiro envio: chame enviar_ao_pjecalc antes, sem pedir licença ao usuário.

PERCURSO
1. Leia o documento e faça a lista do que ele determina. Pergunte as omissões indispensáveis de uma vez.
2. criar_calculo (ou listar_calculos/ler_calculo para continuar um existente); responder_perguntas (documentoBase, desligamento).
3. preencher_campos (guia_de_campos mostra as chaves); definir_historico; perguntas de verbas, definir_verbas e configurar_verba de cada verba; definir_correcao; definir_fgts.
4. conferir; enviar_ao_pjecalc; ler_criterios para ver a fórmula que o PJe-Calc montou para cada verba e corrigir o que não bater com o documento.
5. Telas do PJe-Calc para tudo o que o documento determina e as etapas do Studio não cobrem (lista acima); responder_perguntas (outrosItens) para os 12 itens.
6. calcular; se houver pendências, corrija (pela ferramenta do Studio ou pela tela) e calcule de novo; ler_resultado.
7. Confira o resultado com o documento: quando ele traz valores (valor da condenação, do acordo, de cada pedido, custas), compare e explique qualquer diferença.
8. Relatório final ao usuário: o que foi lançado e de onde veio, padrões do PJe-Calc usados por omissão do documento, diferenças encontradas e dúvidas que restaram. Seja breve; dados do caso são sigilosos, não os repita além do necessário."""


class ErroStudio(Exception):
    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


# ============================================================================ acesso ao Studio
# As ferramentas usam as mesmas rotas da interface. O servidor do Studio injeta, com configurar(), a função
# que despacha cada rota em processo; assim valem as mesmas regras e a mesma conferência da interface.
_despachar = None
VERSAO = "0"


def configurar(despachar, versao: str) -> None:
    """despachar(metodo, caminho, corpo) -> dict; levanta ErroStudio(mensagem, status) em erro."""
    global _despachar, VERSAO
    _despachar, VERSAO = despachar, versao


def chamar(metodo: str, caminho: str, corpo=None, timeout: float = 30):
    if _despachar is None:
        raise ErroStudio("Assistente não configurado no servidor do Studio.")
    return _despachar(metodo, caminho, corpo)


def obter(cid: str) -> dict:
    return chamar("GET", f"/api/casos/{_id(cid)}")["caso"]


def editar(cid: str, alterar) -> dict:
    """Lê o caso, aplica alterar(caso) e grava com controle de revisão (repete uma vez se outra janela salvou antes)."""
    for tentativa in range(2):
        caso = obter(cid)
        alterar(caso)
        corpo = {"revisaoBase": caso["revisao"], "rascunho": caso["rascunho"], **{k: caso.get(k) for k in META + ("etiquetas",)}}
        try:
            return chamar("PUT", f"/api/casos/{caso['id']}", corpo)["caso"]
        except ErroStudio as e:
            if tentativa or e.status != 409:  # 409: outra janela salvou antes; relê e aplica de novo
                raise
    raise ErroStudio("Não foi possível salvar.")


def _id(cid) -> str:
    cid = str(cid or "").strip()
    if not re.fullmatch(r"[a-z0-9_]+", cid):
        raise ErroStudio("Identificador de cálculo inválido. Use o id devolvido por listar_calculos.")
    return cid


# ============================================================================ validação (mesmas regras da interface)
def _fold(s) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c)).lower().strip()


def data_br(v) -> str:
    s = str(v).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s) or re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        raise ErroStudio(f"“{v}” não é uma data. Use DD/MM/AAAA.")
    d, mth, a = (m.group(3), m.group(2), m.group(1)) if "-" in s else m.groups()
    try:
        date(int(a), int(mth), int(d))
    except ValueError:
        raise ErroStudio(f"“{v}” não é uma data válida.") from None
    return f"{int(d):02d}/{int(mth):02d}/{a}"


def competencia(v) -> str:
    s = str(v).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", s) or re.fullmatch(r"(\d{4})-(\d{2})", s)
    if not m:
        raise ErroStudio(f"Competência “{v}” inválida. Use MM/AAAA.")
    mes, ano = (m.group(2), m.group(1)) if "-" in s else m.groups()
    if not 1 <= int(mes) <= 12:
        raise ErroStudio(f"Competência “{v}” inválida.")
    return f"{int(mes):02d}/{ano}"


def _numero(v, casas: int) -> float:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace("R$", "").strip()
    if re.fullmatch(r"-?\d+\.\d+", s) and "," not in s and len(s.split(".")[1]) != 3:
        return float(s)  # 1234.56 (ponto decimal)
    try:
        n = conferencia.valor_br(s)
    except ValueError:
        n = None
    if n is None:
        raise ErroStudio(f"“{v}” não é um número. Use vírgula nos decimais, por exemplo 3.800,00.")
    return n


def moeda(v) -> str:
    if str(v).strip() == "?":
        return "?"
    n = _numero(v, 2)
    s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if n < 0 else "") + s


def numero(v, casas: int = 4) -> str:
    n = _numero(v, casas)
    return f"{n:.{casas}f}".replace(".", ",")


def documento(tipo: str, v) -> tuple[str, str]:
    dig = re.sub(r"\D", "", str(v))
    tipo = tipo or ("CPF" if len(dig) == 11 else "CNPJ" if len(dig) == 14 else "")
    if tipo == "CPF":
        if not conferencia.cpf_valido(dig):
            raise ErroStudio(f"CPF {v} inválido (os dígitos verificadores não conferem).")
        return tipo, f"{dig[:3]}.{dig[3:6]}.{dig[6:9]}-{dig[9:]}"
    if tipo == "CNPJ":
        if not conferencia.cnpj_valido(dig):
            raise ErroStudio(f"CNPJ {v} inválido (os dígitos verificadores não conferem).")
        return tipo, f"{dig[:2]}.{dig[2:5]}.{dig[5:8]}/{dig[8:12]}-{dig[12:]}"
    if tipo == "CEI" and len(dig) == 12:
        return tipo, f"{dig[:2]}.{dig[2:5]}.{dig[5:10]}/{dig[10:]}"
    raise ErroStudio(f"Documento {v}: informe 11 dígitos (CPF), 14 (CNPJ) ou 12 (CEI).")


def cnj(v) -> dict:
    d = re.sub(r"\D", "", str(v))
    if len(d) != 20:
        raise ErroStudio(f"Número de processo “{v}” incompleto: são 20 dígitos (0001234-56.2024.5.08.0001).")
    if d[13] != "5":
        raise ErroStudio("Este número não é da Justiça do Trabalho (o dígito depois do ano deve ser 5).")
    esperado = conferencia.digito_cnj(d[:7], d[9:13], "5", d[14:16], d[16:])
    if esperado != d[7:9]:
        raise ErroStudio(f"Número de processo não confere: o dígito verificador deveria ser {esperado}, não {d[7:9]}. Confira a digitação.")
    return {"processo.numero": d[:7], "processo.digito": d[7:9], "processo.ano": d[9:13], "processo.regiao": d[14:16], "processo.vara": d[16:]}


def opcao(chave: str, v) -> str:
    ops = catalogo.OPCOES.get(chave) or []
    for o in ops:
        if str(v) == o["valor"] or _fold(v) == _fold(o["rotulo"]):
            return o["valor"]
    raise ErroStudio(f"“{v}” não é uma opção de {chave}. Opções: " + "; ".join(f"{o['valor']} ({o['rotulo']})" for o in ops))


def verba_do_catalogo(nome: str) -> str:
    for v in catalogo.VERBAS_EXPRESSAS:
        if _fold(v) == _fold(nome):
            return v
    proximas = [v for v in catalogo.VERBAS_EXPRESSAS if all(p in _fold(v) for p in _fold(nome).split())][:6]
    raise ErroStudio(f"“{nome}” não está no catálogo de verbas do PJe-Calc." + (f" Parecidas: {', '.join(proximas)}." if proximas else
                     " Use guia_de_campos (secao 'verbas') para ver a lista; verbas fora do catálogo são lançadas na interface (lançamento manual)."))


# ============================================================================ resumo de um cálculo
def resumo(caso: dict, completo: bool = False) -> dict:
    r = caso.get("rascunho") or {}
    hist = [{"nome": h.get("nome"), "meses": len(h.get("ocorrencias") or []),
             "de": (h.get("ocorrencias") or [{}])[0].get("competencia"), "ate": (h.get("ocorrencias") or [{}])[-1].get("competencia"),
             "semValor": sum(1 for o in h.get("ocorrencias") or [] if o.get("valor") in ("", None)),
             "fgts": h.get("fgts"), "inss": h.get("inss")} for h in r.get("historicos") or []]
    cfgs = {}
    for nome, c in (r.get("verbasConfig") or {}).items():
        x = {k: c[k] for k in ("bases", "alteracoes", "justificativa", "trecho", "reflexos") if c.get(k)}
        ocs = [o for o in c.get("ocorrencias") or [] if any(o.get(k) not in ("", None) for k in ("quantidade", "devido", "pago")) or o.get("ativo") is False]
        if ocs:
            x["ocorrenciasInformadas"] = ocs if completo else len(ocs)
        if x:
            cfgs[nome] = x
    out = {
        "id": caso["id"], "titulo": caso.get("titulo"), "situacao": caso.get("situacao"), "revisao": caso.get("revisao"),
        "pjecalc": {k: (caso.get("pjecalc") or {}).get(k) for k in ("calculoId", "gravadoRevisao")},
        "documentoBase": r.get("documentoBase") or None, "desligamento": r.get("desligamento") or None,
        "dados": r.get("dados") or {}, "historicos": hist if not completo else r.get("historicos") or [],
        "verbas": r.get("verbas") or [], "verbasManuais": [v.get("descricao") for v in r.get("verbasManuais") or []],
        "verbasConfig": cfgs, "perguntasVerbas": r.get("perguntasVerbas") or {}, "outrosItens": r.get("outrosItens") or {},
        "fgts": r.get("fgts") or {}, "atualizacao": r.get("atualizacao") or {}, "liquidacao": r.get("liquidacao") or {},
        "execucoes": [{"id": e.get("id"), "em": e.get("em"), "ok": e.get("ok")} for e in (caso.get("execucoes") or [])[-3:]],
    }
    return out


# ============================================================================ ferramentas
def f_estado(_a):
    return chamar("GET", "/api/estado")


def f_listar(a):
    q = ("?q=" + urllib.parse.quote(a["busca"])) if a.get("busca") else ""
    casos = chamar("GET", "/api/casos" + q)["casos"]
    return [{k: c.get(k) for k in ("id", "titulo", "cliente", "processo", "situacao", "atualizadoEm", "calculoPjecalc")} for c in casos]


def f_criar(a):
    corpo = {k: a[k] for k in ("titulo", "cliente", "parteContraria", "processo", "responsavel") if a.get(k)}
    if a.get("modelo"):
        corpo["modelo"] = {"id": a["modelo"], "origem": a.get("modelo_origem", "escritorio")}
    caso = chamar("POST", "/api/casos", corpo)["caso"]
    return {"id": caso["id"], "titulo": caso["titulo"], "mensagem": "Cálculo criado. Próximo passo: responder_perguntas (documentoBase e desligamento)."}


def f_ler(a):
    return resumo(obter(a["id"]), bool(a.get("completo")))


def f_guia(a):
    secao = a.get("secao") or "campos"
    if secao == "campos":
        return {"campos": {k: ({"tipo": t, "opcoes": [f"{o['valor']} ({o['rotulo']})" for o in catalogo.OPCOES.get(k, [])]} if t == "lista" else {"tipo": t})
                           for k, t in CAMPOS.items()},
                "metadados": list(META), "estados": catalogo.ESTADOS,
                "notas": {"processo.numeroCompleto": "número CNJ inteiro; é dividido e validado (dígito verificador, Justiça do Trabalho).",
                          "documento": "CPF/CNPJ com ou sem pontuação; o tipo é escolhido sozinho se não informado.",
                          "moeda": "3.800,00 ou 3800.00", "marca": "true/false", "data": "DD/MM/AAAA"}}
    if secao == "perguntas":
        return {"documentoBase": DOCUMENTOS, "desligamento": DESLIGAMENTOS,
                "perguntasVerbas (sim/nao)": dict(conferencia.PERGUNTAS_VERBAS),
                "outrosItens (nao = não se aplica / sim = precisa preencher no PJe-Calc / feito = já preenchido)": dict(conferencia.OUTROS_ITENS)}
    if secao == "verbas":
        return {"catalogo": catalogo.VERBAS_EXPRESSAS, "bases": BASES}
    if secao == "correcao":
        return {"correcao": {cid: {"rotulo": rot, "tipo": tipo, **({"opcoes": [f"{o['valor']} ({o['rotulo']})" for o in catalogo.OPCOES["atualizacao." + cid]]}
                                                                   if "atualizacao." + cid in catalogo.OPCOES else {})} for cid, rot, tipo in CAMPOS_ATUALIZACAO},
                "combinacoes": {"indices": [o["rotulo"] for o in catalogo.OPCOES.get("atualizacao.outroIndiceTrabalhista", [])],
                                "juros": [o["rotulo"] for o in catalogo.OPCOES.get("atualizacao.outroJuros", [])]},
                "fgts": {cid: {"rotulo": rot, "tipo": tipo, **({"opcoes": [f"{o['valor']} ({o['rotulo']})" for o in catalogo.OPCOES["fgts." + cid]]}
                                                              if "fgts." + cid in catalogo.OPCOES else {})} for cid, rot, tipo in CAMPOS_FGTS}}
    raise ErroStudio("secao deve ser campos, perguntas, verbas ou correcao.")


def f_responder(a):
    erros = []

    def alterar(caso):
        r = caso["rascunho"]
        if a.get("documentoBase") is not None:
            if a["documentoBase"] not in DOCUMENTOS:
                erros.append(f"documentoBase deve ser um de {list(DOCUMENTOS)}.")
            else:
                r["documentoBase"] = a["documentoBase"]
        if a.get("desligamento") is not None:
            if a["desligamento"] not in DESLIGAMENTOS:
                erros.append(f"desligamento deve ser um de {list(DESLIGAMENTOS)}.")
            else:
                r["desligamento"] = a["desligamento"]
        for chave, validos, respostas in (("perguntasVerbas", dict(conferencia.PERGUNTAS_VERBAS), ("sim", "nao")),
                                          ("outrosItens", dict(conferencia.OUTROS_ITENS), ("nao", "sim", "feito"))):
            for pid, v in (a.get(chave) or {}).items():
                if pid not in validos:
                    erros.append(f"{chave}: “{pid}” não existe. Válidos: {', '.join(validos)}.")
                elif v not in respostas:
                    erros.append(f"{chave}.{pid}: resposta deve ser {'/'.join(respostas)}.")
                else:
                    r.setdefault(chave, {})[pid] = v
        if erros:
            raise ErroStudio(" ".join(erros))
    caso = editar(a["id"], alterar)
    r = caso["rascunho"]
    faltam = [n for p, n in conferencia.PERGUNTAS_VERBAS if not (r.get("perguntasVerbas") or {}).get(p)]
    faltam_o = [n for p, n in conferencia.OUTROS_ITENS if not (r.get("outrosItens") or {}).get(p)]
    return {"salvo": True, "perguntasDeVerbasSemResposta": faltam, "outrosItensSemResposta": faltam_o,
            "lembrete": "Uma resposta 'sim' em perguntasVerbas não marca verbas sozinha: use definir_verbas."}


def f_preencher(a):
    campos = a.get("campos") or {}
    if not campos:
        raise ErroStudio("Informe campos: {chave: valor}. Veja guia_de_campos.")
    feitos = {}

    def alterar(caso):
        d = caso["rascunho"].setdefault("dados", {})
        for k, v in campos.items():
            if k.startswith("meta."):
                m = k[5:]
                if m not in META:
                    raise ErroStudio(f"Metadado “{k}” desconhecido. Válidos: {', '.join('meta.' + x for x in META)}.")
                caso[m] = str(v)
                feitos[k] = caso[m]
                continue
            tipo = CAMPOS.get(k)
            if not tipo:
                raise ErroStudio(f"Campo “{k}” desconhecido. Use guia_de_campos para ver as chaves.")
            if v in ("", None):
                if tipo == "cnj":
                    for c in cnj_chaves():
                        d.pop(c, None)
                else:
                    d.pop(k, None)
                feitos[k] = "(apagado)"
                continue
            if tipo == "data":
                d[k] = data_br(v)
            elif tipo == "moeda":
                d[k] = moeda(v)
            elif tipo == "inteiro":
                if not re.fullmatch(r"\d+", str(v).strip()):
                    raise ErroStudio(f"{k}: use um número inteiro.")
                d[k] = str(v).strip()
            elif tipo == "marca":
                d[k] = v if isinstance(v, bool) else str(v).strip().lower() in ("true", "sim", "s", "1", "yes")
            elif tipo == "lista":
                d[k] = opcao(k, v)
            elif tipo == "estado":
                if str(v).upper() not in catalogo.ESTADOS:
                    raise ErroStudio(f"Estado “{v}” inválido. Use a sigla (PA, SP...).")
                d[k] = str(v).upper()
            elif tipo == "municipio":
                d[k] = str(v).strip().upper()
            elif tipo == "documento":
                papel = k.split(".")[0]
                tipo_doc = campos.get(f"{papel}.tipoDocumentoFiscal") or d.get(f"{papel}.tipoDocumentoFiscal") or ""
                t, num = documento(str(tipo_doc).strip().upper(), v)
                d[f"{papel}.tipoDocumentoFiscal"] = t
                d[k] = num
            elif tipo == "cnj":
                d.update(cnj(v))
            else:
                d[k] = str(v).strip()
            feitos[k] = d.get(k, "ok")
    editar(a["id"], alterar)
    return {"salvo": feitos}


def cnj_chaves():
    return ("processo.numero", "processo.digito", "processo.ano", "processo.regiao", "processo.vara")


def f_verbas(a):
    adicionar = [verba_do_catalogo(n) for n in a.get("adicionar") or []]
    remover = [verba_do_catalogo(n) for n in a.get("remover") or []]

    def alterar(caso):
        vs = caso["rascunho"].setdefault("verbas", [])
        for n in adicionar:
            if n not in vs:
                vs.append(n)
        caso["rascunho"]["verbas"] = [v for v in vs if v not in remover]
    caso = editar(a["id"], alterar)
    return {"verbas": caso["rascunho"]["verbas"]}


def f_configurar_verba(a):
    nome = verba_do_catalogo(a["verba"])
    msgs = []

    def alterar(caso):
        r = caso["rascunho"]
        if nome not in (r.get("verbas") or []):
            raise ErroStudio(f"{nome} não está entre as verbas do cálculo. Use definir_verbas antes.")
        cfg = r.setdefault("verbasConfig", {}).setdefault(nome, {})
        alt = cfg.setdefault("alteracoes", {})
        if a.get("base"):
            if a["base"] not in BASES:
                raise ErroStudio(f"base deve ser uma de {list(BASES)}.")
            alt["tipoDaBaseTabelada"] = a["base"]
            if a["base"] != "HISTORICO_SALARIAL":
                cfg["bases"] = []
        if a.get("historicos") is not None:
            # comparação sem acentos e sem caixa; grava a grafia do histórico existente
            existentes = {_fold(h.get("nome")): (h.get("nome") or "").upper() for h in r.get("historicos") or []}
            existentes[_fold("ÚLTIMA REMUNERAÇÃO")] = "ÚLTIMA REMUNERAÇÃO"
            desconhecidos = [str(h) for h in a["historicos"] if _fold(h) not in existentes]
            if desconhecidos:
                raise ErroStudio(f"Históricos inexistentes: {', '.join(desconhecidos)}. Existentes: {', '.join(existentes.values())}. "
                                 "Crie com definir_historico.")
            cfg["bases"] = [existentes[_fold(h)] for h in a["historicos"]]
        if a.get("quantidade_por_mes") is not None:
            alt["valorInformadoDaQuantidade"] = numero(a["quantidade_por_mes"], 4)
        for k in ("justificativa", "trecho"):
            if a.get(k) is not None:
                cfg[k] = str(a[k])
        if a.get("ocorrencias"):
            ocs = {o["competencia"]: o for o in cfg.setdefault("ocorrencias", [])}
            for o in a["ocorrencias"]:
                c = competencia(o["competencia"])
                atual = ocs.get(c) or {"competencia": c, "quantidade": "", "devido": "", "pago": "", "ativo": True, "divisor": "", "multiplicador": ""}
                if "quantidade" in o:
                    atual["quantidade"] = numero(o["quantidade"], 4) if o["quantidade"] not in ("", None) else ""
                for k in ("devido", "pago"):
                    if k in o:
                        atual[k] = moeda(o[k]) if o[k] not in ("", None) else ""
                if "ativo" in o:
                    atual["ativo"] = bool(o["ativo"])
                ocs[c] = atual
            cfg["ocorrencias"] = sorted(ocs.values(), key=lambda x: (int(x["competencia"][3:]), int(x["competencia"][:2])))
            msgs.append(f"{len(a['ocorrencias'])} competência(s) informada(s); as demais seguem o que o PJe-Calc gerar.")
        if not alt:
            cfg.pop("alteracoes", None)
    caso = editar(a["id"], alterar)
    cfg = caso["rascunho"]["verbasConfig"][nome]
    return {"verba": nome, "config": {k: (len(v) if k == "ocorrencias" else v) for k, v in cfg.items()}, "avisos": msgs}


def f_historico(a):
    nome = str(a["nome"]).strip().upper()
    if not nome:
        raise ErroStudio("Informe o nome do histórico (ex.: SALARIO BASE).")
    novas = []
    if a.get("valores"):
        novas = [{"competencia": competencia(o["competencia"]), "valor": moeda(o["valor"])} for o in a["valores"]]
    elif a.get("de") and a.get("ate") and a.get("valor") is not None:
        ini, fim = competencia(a["de"]), competencia(a["ate"])
        m, y = int(ini[:2]), int(ini[3:])
        while (y, m) <= (int(fim[3:]), int(fim[:2])):
            novas.append({"competencia": f"{m:02d}/{y}", "valor": moeda(a["valor"])})
            m, y = (1, y + 1) if m == 12 else (m + 1, y)
            if len(novas) > 1200:
                raise ErroStudio("Período longo demais.")
    else:
        raise ErroStudio("Informe valores [{competencia, valor}] ou de, ate e valor.")

    def alterar(caso):
        hs = caso["rascunho"].setdefault("historicos", [])
        h = next((x for x in hs if (x.get("nome") or "").upper() == nome), None)
        if not h:
            h = {"id": "h" + secrets.token_hex(4), "nome": nome, "fgts": True, "inss": True, "ocorrencias": []}
            hs.append(h)
        for k in ("fgts", "inss"):
            if a.get(k) is not None:
                h[k] = bool(a[k])
        ocs = {} if a.get("substituir") else {o["competencia"]: o for o in h["ocorrencias"]}
        for o in novas:
            atual = ocs.get(o["competencia"]) or {"competencia": o["competencia"], "fgtsRecolhido": False, "inssRecolhido": False}
            atual["valor"] = o["valor"]
            ocs[o["competencia"]] = atual
        h["ocorrencias"] = sorted(ocs.values(), key=lambda x: (int(x["competencia"][3:]), int(x["competencia"][:2])))
    caso = editar(a["id"], alterar)
    # o histórico pode ter sido criado na interface com outra grafia (ex.: "Salário base")
    h = next(x for x in caso["rascunho"]["historicos"] if (x.get("nome") or "").upper() == nome)
    ocs = h.get("ocorrencias") or [{}]
    return {"historico": h["nome"], "meses": len(h.get("ocorrencias") or []), "de": ocs[0].get("competencia"), "ate": ocs[-1].get("competencia")}


def f_correcao(a):
    ids = {cid: tipo for cid, _, tipo in CAMPOS_ATUALIZACAO}

    def combos(lista, chave):
        rotulos = [o["rotulo"] for o in catalogo.OPCOES.get(chave, [])]
        out = []
        for c in lista:
            tab = next((r for r in rotulos if _fold(r) == _fold(c.get("tabela"))), None)
            if not tab:
                raise ErroStudio(f"Tabela “{c.get('tabela')}” inválida. Opções: {', '.join(rotulos)}.")
            out.append({"tabela": tab, "aPartirDe": data_br(c.get("aPartirDe"))})
        return out

    def alterar(caso):
        r = caso["rascunho"]
        at = r.setdefault("atualizacao", {"valores": {}, "jurosCombinados": None, "indicesCombinados": None})
        at.setdefault("valores", {})
        for k, v in (a.get("valores") or {}).items():
            if k not in ids:
                raise ErroStudio(f"Critério “{k}” desconhecido. Use guia_de_campos secao=correcao.")
            if v in ("", None):
                at["valores"].pop(k, None)
            elif ids[k] == "marca":
                at["valores"][k] = bool(v)
            else:
                at["valores"][k] = opcao("atualizacao." + k, v) if "atualizacao." + k in catalogo.OPCOES else str(v)
        if a.get("indices_combinados") is not None:
            at["indicesCombinados"] = combos(a["indices_combinados"], "atualizacao.outroIndiceTrabalhista")
        if a.get("juros_combinados") is not None:
            at["jurosCombinados"] = combos(a["juros_combinados"], "atualizacao.outroJuros")
        liq = r.setdefault("liquidacao", {})
        if a.get("data_liquidacao"):
            liq["data"] = data_br(a["data_liquidacao"])
    caso = editar(a["id"], alterar)
    return {"atualizacao": caso["rascunho"]["atualizacao"], "liquidacao": caso["rascunho"].get("liquidacao")}


def f_fgts(a):
    ids = {cid: tipo for cid, _, tipo in CAMPOS_FGTS}

    def alterar(caso):
        fg = caso["rascunho"].setdefault("fgts", {})
        for k, v in (a.get("valores") or {}).items():
            if k not in ids:
                raise ErroStudio(f"Campo de FGTS “{k}” desconhecido. Use guia_de_campos secao=correcao (parte fgts).")
            if v in ("", None):
                fg.pop(k, None)
            elif ids[k] == "marca":
                fg[k] = bool(v)
            else:
                fg[k] = opcao("fgts." + k, v) if "fgts." + k in catalogo.OPCOES else str(v)
    caso = editar(a["id"], alterar)
    return {"fgts": caso["rascunho"]["fgts"]}


def f_conferir(a):
    r = chamar("GET", f"/api/casos/{_id(a['id'])}/conferir")
    imp = [x for x in r["avisos"] if x["nivel"] == "impeditivo"]
    return {"podeEnviar": not imp, "impedemOEnvio": imp, "alertas": [x for x in r["avisos"] if x["nivel"] != "impeditivo"],
            "pendenciasDoPjecalc": r.get("pendenciasPjecalc"), "pendenciasAtualizadas": r.get("pendenciasAtuais")}


def _operar(a, acao):
    r = chamar("POST", f"/api/casos/{_id(a['id'])}/{acao}", {}, timeout=600)
    passos = [{"passo": p.get("rotulo"), "ok": p.get("ok"), "mensagens": [m.get("texto") for m in p.get("mensagens") or []]} for p in r.get("passos") or []]
    return {"ok": r.get("ok"), "calculoNoPjecalc": r.get("calculoId"), "passos": passos,
            "impedimentos": r.get("avisos"), "pendencias": r.get("pendencias"), "estado": r.get("estado")}


def f_enviar(a):
    return _operar(a, "gravar")


def f_calcular(a):
    return _operar(a, "executar")


def f_resultado(a):
    caso = obter(a["id"])
    exs = caso.get("execucoes") or []
    if not exs:
        raise ErroStudio("Este cálculo ainda não foi calculado. Use calcular (com a confirmação do usuário).")
    eid = str(a.get("execucao") or exs[-1]["id"]).strip()
    if eid not in {e.get("id") for e in exs}:
        raise ErroStudio(f"Execução “{eid}” não existe neste cálculo. Execuções: {', '.join(str(e.get('id')) for e in exs[-10:])}.")
    r = chamar("GET", f"/api/casos/{caso['id']}/execucoes/{eid}")
    texto = json.dumps(r.get("resultado"), ensure_ascii=False)
    return {"execucao": r.get("execucao"), "estado": r.get("estado"),
            "resultado": r.get("resultado") if len(texto) < 60000 else texto[:60000] + "… (cortado)"}


def f_criterios(a):
    r = chamar("GET", f"/api/casos/{_id(a['id'])}/criterios", timeout=120)
    def val(v, cid):
        c = next((x for x in v.get("campos") or [] if x["id"] == cid), None)
        return None if not c else next((o["rotulo"] for o in c.get("opcoes") or [] if o["valor"] == c["valor"]), c["valor"])
    return {"lidoNaRevisao": r.get("lidoNaRevisao"),
            "verbas": [{"nome": v["nome"], "formula": v.get("formula"), "base": val(v, "tipoDaBaseTabelada"), "historicos": v.get("bases"),
                        "divisor": val(v, "tipoDeDivisor"), "valorDivisor": val(v, "outroValorDoDivisor"),
                        "multiplicador": val(v, "outroValorDoMultiplicador"), "quantidade": val(v, "tipoDaQuantidade"),
                        "quantidadeInformada": val(v, "valorInformadoDaQuantidade"),
                        "reflexosAtivos": [x["nome"] for x in v.get("reflexos") or [] if x.get("ativo")]} for v in r.get("verbas") or []],
            "atualizacao": r.get("atualizacao")}


# ============================================================================ telas oficiais do PJe-Calc
# Mesmo mecanismo de "Todas as funções do PJe-Calc" no Studio (ponte/tela.py): a tela é aberta numa sessão
# própria do PJe-Calc, lida como dados, e cada valor e clique volta para a tela oficial, que valida e grava.
# (id, item de menu do PJe-Calc, grupo, título, descrição, precisa de um cálculo aberto)
TELAS = [
    ("dados", "li_calculo_dados_do_calculo", "Cálculo", "Dados do Cálculo (completa)", "Todos os campos, inclusive advogados, exceções de carga horária e de sábado e pontos facultativos.", True),
    ("faltas", "li_calculo_faltas", "Cálculo", "Faltas", "Faltas justificadas e não justificadas, com reflexo em férias, 13º e bases.", True),
    ("ferias", "li_calculo_ferias", "Cálculo", "Férias", "Períodos aquisitivos, gozo, dobra e abono; férias coletivas.", True),
    ("historico", "li_calculo_historico_salarial", "Cálculo", "Histórico Salarial (completa)", "Grade de ocorrências, proporcionalização e demais opções do histórico.", True),
    ("verbas", "li_calculo_verbas", "Cálculo", "Verbas (completa)", "Todos os parâmetros, ocorrências de reflexos e regeração de ocorrências.", True),
    ("cartao", "li_calculo_cartao_ponto", "Cálculo", "Cartão de Ponto", "Marcações, jornadas, apuração de horas extras, noturnas e intervalos.", True),
    ("salario-familia", "li_calculo_salario_familia", "Cálculo", "Salário-família", "Apuração do salário-família.", True),
    ("seguro-desemprego", "li_calculo_seguro_desemprego", "Cálculo", "Seguro-desemprego", "Indenização substitutiva do seguro-desemprego.", True),
    ("fgts", "li_calculo_fgts", "Cálculo", "FGTS (completa)", "Ocorrências do FGTS, depósitos e demais opções.", True),
    ("inss", "li_calculo_inss", "Cálculo", "Contribuição Social", "Segurado e empregador, alíquotas, salários pagos e ocorrências.", True),
    ("previdencia", "li_calculo_previdencia_privada", "Cálculo", "Previdência Privada", "Descontos de previdência privada.", True),
    ("pensao", "li_calculo_pensao_alimenticia", "Cálculo", "Pensão Alimentícia", "Descontos de pensão alimentícia.", True),
    ("irpf", "li_calculo_irpf", "Cálculo", "Imposto de Renda", "Apuração, deduções, dependentes e regime de caixa.", True),
    ("multas", "li_calculo_multas_e_indenizacoes", "Cálculo", "Multas e Indenizações", "Dano moral, dano material, multas e indenizações de valor fixo.", True),
    ("honorarios", "li_calculo_honorarios", "Cálculo", "Honorários", "Honorários advocatícios e periciais.", True),
    ("custas", "li_calculo_custas_judiciais", "Cálculo", "Custas Judiciais", "Custas de conhecimento e liquidação, autos e armazenamento.", True),
    ("correcao", "li_calculo_correcao_juros_multa", "Cálculo", "Correção, Juros e Multa (completa)", "Todas as abas, inclusive multa e contribuição social.", True),
    ("liquidar", "li_operacoes_liquidar", "Operações", "Liquidar", "Tela oficial de liquidação e pendências.", True),
    ("imprimir", "li_calculo_relatorios", "Operações", "Imprimir (todas as opções)", "Todos os relatórios e opções de impressão.", True),
    ("exportar", "li_operacoes_exportar", "Operações", "Exportar", "Exportação oficial do arquivo .PJC.", True),
    ("pagamento", "li_pagamento_dados_do_pagamento", "Atualização de pagamentos", "Dados do Pagamento", "Pagamentos realizados no processo, para atualização do saldo.", True),
    ("pag-pensao", "li_pagamento_pensao_alimenticia", "Atualização de pagamentos", "Pensão Alimentícia (atualização)", "", True),
    ("pag-multas", "li_pagamento_multas_e_indenizacoes", "Atualização de pagamentos", "Multas e Indenizações (atualização)", "", True),
    ("pag-honorarios", "li_pagamento_honorarios", "Atualização de pagamentos", "Honorários (atualização)", "", True),
    ("pag-custas", "li_pagamento_custas_judiciais", "Atualização de pagamentos", "Custas Judiciais (atualização)", "", True),
    ("liquidar-atualizacao", "li_operacoes_liquidar_pagamento", "Atualização de pagamentos", "Liquidar Atualização", "", True),
    ("imprimir-atualizacao", "li_operacoes_imprimir_pagamento", "Atualização de pagamentos", "Imprimir Atualização", "", True),
    ("externo", "li_calculo_externo_novo", "PJe-Calc", "Novo Cálculo Externo", "Atualização de cálculo feito fora do PJe-Calc.", False),
    ("consolidado", "li_processo_relatorio", "PJe-Calc", "Relatório Consolidado", "Relatório consolidado de cálculos de um processo.", False),
    ("buscar", "li_calculo_buscar", "PJe-Calc", "Buscar cálculos no PJe-Calc", "Todos os cálculos do PJe-Calc, inclusive os feitos fora do Studio.", False),
    ("t-salario-minimo", "li_tabelas_salario_minimo", "Tabelas", "Salário Mínimo", "", False),
    ("t-pisos", "li_tabelas_salario_categoria", "Tabelas", "Pisos Salariais", "Pisos da categoria (base SALARIO_DA_CATEGORIA).", False),
    ("t-salario-familia", "li_tabelas_salario_familia", "Tabelas", "Salário-família", "", False),
    ("t-seguro", "li_tabelas_seguro_desemprego", "Tabelas", "Seguro-desemprego", "", False),
    ("t-vale", "li_tabelas_vale_transporte", "Tabelas", "Vale-transporte", "", False),
    ("t-feriados", "li_tabelas_feriado", "Tabelas", "Feriados e Pontos Facultativos", "", False),
    ("t-verbas", "li_tabelas_verbas", "Tabelas", "Verbas", "Modelos de verbas do PJe-Calc.", False),
    ("t-inss", "li_tabelas_inss", "Tabelas", "Contribuição Social", "", False),
    ("t-irpf", "li_tabela_irpf", "Tabelas", "Imposto de Renda", "", False),
    ("t-custas", "li_tabelas_parametros_custas", "Tabelas", "Custas Judiciais", "", False),
    ("t-correcao", "li_tabelas_indices_gerais", "Tabelas", "Correção Monetária", "", False),
    ("t-juros", "li_tabelas_juros", "Tabelas", "Juros de Mora", "", False),
]
TELA_POR_ID = {t[0]: t for t in TELAS}
LIMITE_LINHAS = 80  # linhas de tabela por resposta; o restante vem pelas ações de página ("pag:...")


def _texto_curto(t, n: int = 240):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[:n] + "…"


def resumir_tela(d: dict) -> dict:
    """Descrição da tela (ponte/tela.py) em formato compacto para o Claude: campos, ações, abas, tabelas e mensagens."""
    out = {"titulo": d.get("titulo"), "mensagens": [{"tipo": m.get("severidade"), "texto": m.get("texto")} for m in d.get("mensagens") or []],
           "campos": [], "acoes": [], "abas": [], "tabelas": [], "textos": []}
    if d.get("arquivo"):
        out["arquivoGerado"] = d["arquivo"]

    def campo(c, grupo, linha=None):
        x = {"nome": c["nome"], "rotulo": c.get("rotulo"), "tipo": c.get("tipo"), "valor": c.get("valor")}
        if grupo:
            x["grupo"] = grupo
        if linha is not None:
            x["linha"] = linha
        for k in ("obrigatorio", "desabilitado", "evento"):
            if c.get(k):
                x[k] = True
        if c.get("opcoes"):
            ops = [f"{o['valor']}={o['rotulo']}" if o["valor"] != o["rotulo"] else str(o["valor"]) for o in c["opcoes"]]
            x["opcoes"] = ops[:120] + ([f"… mais {len(ops) - 120}"] if len(ops) > 120 else [])
        if c.get("ajuda"):
            x["ajuda"] = _texto_curto(c["ajuda"], 300)
        if c.get("erro"):
            x["erro"] = c["erro"]
        return x

    def acao(a, grupo, linha=None):
        x = {"id": a["id"], "texto": a.get("texto") or a.get("titulo")}
        if grupo:
            x["grupo"] = grupo
        if linha is not None:
            x["linha"] = linha
        if a.get("confirmar"):
            x["confirmacaoDaTela"] = a["confirmar"]
        return x

    def percorrer(itens, grupo):
        for it in itens:
            t = it.get("t")
            if t == "grupo":
                percorrer(it["itens"], " › ".join(x for x in (grupo, it.get("titulo")) if x))
            elif t == "campo":
                out["campos"].append(campo(it, grupo))
            elif t == "acao":
                out["acoes"].append(acao(it, grupo))
            elif t == "abas":
                out["abas"] += [{"acao": "aba:" + a["id"], "titulo": a.get("titulo"), "ativa": bool(a.get("ativa"))} for a in it.get("abas") or []]
            elif t == "paginacao":
                paginas = [p for p in it.get("paginas") or [] if str(p.get("texto", "")).isdigit()]
                if len(paginas) > 1:
                    out["acoes"].append({"id": None, "texto": "Páginas da tabela", "grupo": grupo,
                                         "paginas": {p["texto"]: f"pag:{it['id']}:{p['pagina']}" for p in paginas}})
            elif t == "tabela":
                tab = {"id": it.get("id"), "grupo": grupo, "colunas": it.get("colunas") or [], "linhas": []}
                for i, ln in enumerate(it.get("linhas") or []):
                    if i >= LIMITE_LINHAS:
                        tab["linhasOmitidas"] = len(it["linhas"]) - LIMITE_LINHAS
                        break
                    tab["linhas"].append([_texto_curto(c.get("texto"), 120) for c in ln.get("celulas") or []])
                    for c in ln.get("celulas") or []:
                        out["campos"] += [campo(x, grupo, i) for x in c.get("campos") or []]
                        out["acoes"] += [acao(x, grupo, i) for x in c.get("acoes") or []]
                out["tabelas"].append(tab)
            elif t == "texto":
                if it.get("texto") and len(out["textos"]) < 40:
                    out["textos"].append(_texto_curto(it["texto"]))
            elif t == "link":
                out["textos"].append(_texto_curto(f"{it.get('texto')} ({it.get('href')})"))
    percorrer(d.get("itens") or [], None)
    return {k: v for k, v in out.items() if v not in ([], None)}


def f_telas(_a):
    return {"telas": [{"tela": t[0], "titulo": t[3], "grupo": t[2], "descricao": t[4], "precisaDeCalculo": t[5]} for t in TELAS],
            "como": "abrir_tela(tela, id do cálculo) devolve um token e a tela; preencher_tela muda campos; acionar_tela clica "
                    "em botões, abas, páginas e ações de linha; feche com fechar_tela."}


def f_abrir_tela(a):
    t = TELA_POR_ID.get(a.get("tela"))
    if not t:
        raise ErroStudio(f"Tela “{a.get('tela')}” não existe. Use telas_pjecalc para ver os ids.")
    corpo = {"menu": t[1]}
    if t[5]:
        if not a.get("id"):
            raise ErroStudio(f"A tela {t[3]} é de um cálculo: informe o id do cálculo (listar_calculos).")
        corpo["caso"] = _id(a["id"])
    try:
        r = chamar("POST", "/api/telas", corpo)
    except ErroStudio as e:
        if e.status == 409:
            raise ErroStudio("Este cálculo ainda não está no PJe-Calc. Chame enviar_ao_pjecalc e abra a tela de novo.", 409) from None
        raise
    return {"token": r["token"], "tela": resumir_tela(r["tela"])}


def _valores_tela(valores) -> dict:
    if not isinstance(valores, dict) or not valores:
        raise ErroStudio("Informe valores: {nome do campo: valor}, com os nomes de campos que abrir_tela devolveu.")
    return {str(k): ("true" if v is True else "false" if v is False else "" if v is None else str(v)) for k, v in valores.items()}


def _token(a) -> str:
    token = str(a.get("token") or "").strip()
    if not re.fullmatch(r"[\w-]+", token):
        raise ErroStudio("Token de tela inválido. Use o token devolvido por abrir_tela.")
    return token


def _tela(metodo: str, token: str, sufixo: str = "", corpo=None) -> dict:
    """Chama a rota da tela aberta; token desconhecido vira uma orientação em vez de "Registro não encontrado"."""
    try:
        return chamar(metodo, f"/api/telas/{token}{sufixo}", corpo)
    except ErroStudio as e:
        if e.status == 404:
            raise ErroStudio("Esta tela não está mais aberta (foi fechada, substituída por outras telas abertas ou ficou "
                             "mais de 1 hora parada). Abra de novo com abrir_tela; o que não foi salvo nela se perdeu.", 404) from None
        raise


def _percorrer_campos(d: dict):
    """Todos os campos da tela (inclusive os de linhas de tabela)."""
    def coletar(itens):
        for it in itens:
            if it.get("t") == "grupo":
                yield from coletar(it.get("itens") or [])
            elif it.get("t") == "campo":
                yield it
            elif it.get("t") == "tabela":
                for ln in it.get("linhas") or []:
                    for c in ln.get("celulas") or []:
                        yield from c.get("campos") or []
    return coletar(d.get("itens") or [])


def _nomes(d: dict) -> set:
    return {c["nome"] for c in _percorrer_campos(d)}


def _com_evento(d: dict) -> set:
    return {c["nome"] for c in _percorrer_campos(d) if c.get("evento")}


def f_preencher_tela(a):
    """Campos com "evento" (recarregam parte da tela e podem fazer surgir campos novos) vão primeiro, um a um, na
    ordem dada; depois os comuns, todos juntos, conferidos com a tela já recarregada."""
    token = _token(a)
    valores = _valores_tela(a.get("valores"))
    tela = _tela("POST", token, "/alterar", {"valores": {}})["tela"]
    restantes = dict(valores)
    for _ in range(len(valores)):
        eventos = _com_evento(tela)
        k = next((k for k in restantes if k in eventos), None)
        if k is None:
            break
        tela = _tela("POST", token, "/alterar", {"valores": {k: restantes.pop(k)}, "evento": k})["tela"]
    desconhecidos = [k for k in restantes if k not in _nomes(tela)]
    if desconhecidos:
        aplicados = [k for k in valores if k not in restantes]
        raise ErroStudio(f"Campos que não existem nesta tela agora: {', '.join(desconhecidos)}. Leia a tela (ler_tela) e use os nomes dela; "
                         "alguns campos só aparecem depois de escolher uma opção ou trocar de aba."
                         + (f" Já aplicados (sem salvar): {', '.join(aplicados)}." if aplicados else ""))
    if restantes:
        tela = _tela("POST", token, "/alterar", {"valores": restantes})["tela"]
    return {"tela": resumir_tela(tela), "lembrete": "Os valores só ficam gravados no PJe-Calc depois da ação de salvar/confirmar da tela (acionar_tela)."}


def f_acionar_tela(a):
    token, acao = _token(a), str(a.get("acao") or "").strip()
    if not acao:
        raise ErroStudio("Informe a ação: o id de um botão, de uma ação de linha, de uma aba (aba:...) ou de uma página (pag:...).")
    corpo = {"acao": acao}
    if a.get("valores"):
        corpo["valores"] = _valores_tela(a["valores"])
    return {"tela": resumir_tela(_tela("POST", token, "/acao", corpo)["tela"])}


def f_ler_tela(a):
    return {"tela": resumir_tela(_tela("POST", _token(a), "/alterar", {"valores": {}})["tela"])}


def f_fechar_tela(a):
    _tela("DELETE", _token(a))
    return {"ok": True}


ID = {"id": {"type": "string", "description": "id do cálculo (de listar_calculos)"}}
LEITURA = {"readOnlyHint": True, "openWorldHint": False}
ESCRITA = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
COMBINACAO = {"type": "object", "properties": {"tabela": {"type": "string"}, "aPartirDe": {"type": "string", "description": "DD/MM/AAAA"}},
              "required": ["tabela", "aPartirDe"]}
FERRAMENTAS = [
    ("estado_studio", "Situação do Studio e da conexão com o PJe-Calc (versão, se está aberto).", {}, [], f_estado, LEITURA),
    ("listar_calculos", "Lista os cálculos do Studio (id, título, processo, situação). Filtra por texto em título, cliente, processo e etiquetas.",
     {"busca": {"type": "string"}}, [], f_listar, LEITURA),
    ("criar_calculo", "Cria um cálculo novo (rascunho local). Opcionalmente a partir de um modelo do escritório.",
     {"titulo": {"type": "string"}, "cliente": {"type": "string"}, "parteContraria": {"type": "string"}, "processo": {"type": "string"},
      "responsavel": {"type": "string"}, "modelo": {"type": "string", "description": "id de um modelo (opcional)"},
      "modelo_origem": {"type": "string", "description": "origem do modelo (padrão: escritorio)"}}, ["titulo"], f_criar, {**ESCRITA, "idempotentHint": False}),
    ("ler_calculo", "Lê um cálculo: perguntas respondidas, campos, históricos, verbas e suas configurações, critérios e execuções. completo=true traz os valores mês a mês.",
     {**ID, "completo": {"type": "boolean"}}, ["id"], f_ler, LEITURA),
    ("guia_de_campos", "Referência para preencher: secao=campos (chaves, tipos e opções), perguntas (ids e respostas válidas), verbas (catálogo do PJe-Calc e bases) ou correcao (critérios de correção, juros e FGTS).",
     {"secao": {"type": "string", "enum": ["campos", "perguntas", "verbas", "correcao"]}}, [], f_guia, LEITURA),
    ("responder_perguntas", "Responde as perguntas guiadas: documentoBase, desligamento (como o contrato terminou), perguntasVerbas {id: sim|nao} e outrosItens {id: nao|sim|feito}. Responda 'nao' só quando o documento não tratar do item.",
     {**ID, "documentoBase": {"type": "string", "enum": list(DOCUMENTOS)}, "desligamento": {"type": "string", "enum": list(DESLIGAMENTOS)},
      "perguntasVerbas": {"type": "object", "additionalProperties": {"type": "string", "enum": ["sim", "nao"]}},
      "outrosItens": {"type": "object", "additionalProperties": {"type": "string", "enum": ["nao", "sim", "feito"]}}},
     ["id"], f_responder, ESCRITA),
    ("preencher_campos", "Preenche campos do formulário com validação (datas, valores, CPF/CNPJ, número CNJ em processo.numeroCompleto). Valor vazio apaga. Metadados internos: meta.titulo, meta.cliente...",
     {**ID, "campos": {"type": "object", "description": "{chave: valor}, chaves de guia_de_campos"}}, ["id", "campos"], f_preencher, ESCRITA),
    ("definir_verbas", "Adiciona ou remove verbas do catálogo do PJe-Calc (nomes conferidos com o catálogo oficial).",
     {**ID, "adicionar": {"type": "array", "items": {"type": "string"}}, "remover": {"type": "array", "items": {"type": "string"}}},
     ["id"], f_verbas, ESCRITA),
    ("configurar_verba", "Configura uma verba já incluída: base (HISTORICO_SALARIAL, MAIOR_REMUNERACAO, SALARIO_MINIMO, SALARIO_DA_CATEGORIA), historicos que compõem a base, quantidade_por_mes (horas/dias), ocorrencias mês a mês [{competencia, quantidade?, devido?, pago?, ativo?}] e o fundamento (justificativa, trecho do documento).",
     {**ID, "verba": {"type": "string"}, "base": {"type": "string", "enum": list(BASES)}, "historicos": {"type": "array", "items": {"type": "string"}},
      "quantidade_por_mes": {"type": ["number", "string"]}, "justificativa": {"type": "string"}, "trecho": {"type": "string"},
      "ocorrencias": {"type": "array", "items": {"type": "object", "properties": {"competencia": {"type": "string"}, "quantidade": {"type": ["number", "string"]},
                                                                                  "devido": {"type": ["number", "string"]}, "pago": {"type": ["number", "string"]}, "ativo": {"type": "boolean"}},
                                                 "required": ["competencia"]}}},
     ["id", "verba"], f_configurar_verba, ESCRITA),
    ("definir_historico", "Cria ou atualiza um histórico salarial: valores [{competencia MM/AAAA, valor}] ou um período (de, ate) com o mesmo valor. substituir=true apaga os meses anteriores.",
     {**ID, "nome": {"type": "string"}, "valores": {"type": "array", "items": {"type": "object", "properties": {"competencia": {"type": "string"}, "valor": {"type": ["number", "string"]}},
                                                                                  "required": ["competencia", "valor"]}},
      "de": {"type": "string"}, "ate": {"type": "string"}, "valor": {"type": ["number", "string"]},
      "fgts": {"type": "boolean"}, "inss": {"type": "boolean"}, "substituir": {"type": "boolean"}},
     ["id", "nome"], f_historico, ESCRITA),
    ("definir_correcao", "Define critérios de correção monetária e juros (ids de guia_de_campos secao=correcao), combinações a partir de uma data e a data de liquidação. Só o que for informado é enviado; o resto fica como está no PJe-Calc.",
     {**ID, "valores": {"type": "object"}, "data_liquidacao": {"type": "string"},
      "indices_combinados": {"type": "array", "items": COMBINACAO}, "juros_combinados": {"type": "array", "items": COMBINACAO}},
     ["id"], f_correcao, ESCRITA),
    ("definir_fgts", "Define parâmetros do FGTS (multa de 40% ou 20%, destino, incidências). Ids em guia_de_campos secao=correcao (parte fgts).",
     {**ID, "valores": {"type": "object"}}, ["id", "valores"], f_fgts, ESCRITA),
    ("conferir", "Conferência do Studio (o mesmo 'Revisar tudo'): o que impede o envio, alertas e as pendências apontadas pelo PJe-Calc no último envio.",
     ID, ["id"], f_conferir, LEITURA),
    ("enviar_ao_pjecalc", "Grava no PJe-Calc tudo o que foi preenchido no Studio (cria o cálculo lá no primeiro envio). Necessário antes de abrir as telas do cálculo.",
     ID, ["id"], f_enviar,
     {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}),
    ("calcular", "Envia o que faltar e executa o cálculo oficial no PJe-Calc (Liquidar), guardando o relatório e o .PJC. Devolve as pendências se houver.",
     ID, ["id"], f_calcular,
     {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}),
    ("ler_resultado", "Resultado oficial da última execução (ou de execucao=id): totais, verbas, descontos, lidos do relatório e do .PJC do PJe-Calc.",
     {**ID, "execucao": {"type": "string"}}, ["id"], f_resultado, LEITURA),
    ("ler_criterios", "Lê do PJe-Calc a conta montada para cada verba (fórmula, base, divisor, multiplicador, quantidade, reflexos) e os critérios de correção gravados. Disponível depois do primeiro envio.",
     ID, ["id"], f_criterios, LEITURA),
]
TOKEN = {"token": {"type": "string", "description": "token devolvido por abrir_tela"}}
FERRAMENTAS += [
    ("telas_pjecalc", "Lista todas as telas do PJe-Calc que você pode abrir e operar (Faltas, Férias, Cartão de Ponto, Multas e Indenizações, Honorários, Custas, Contribuição Social, IR, Pensão, Pagamentos, Liquidar, Imprimir, Tabelas...).",
     {}, [], f_telas, LEITURA),
    ("abrir_tela", "Abre uma tela oficial do PJe-Calc (id de telas_pjecalc) e a devolve como dados: campos (nome, rótulo, tipo, valor, opções, obrigatório, ajuda oficial, erro), ações (botões e ações de linha), abas, tabelas e mensagens. Telas de cálculo pedem o id do cálculo, já enviado ao PJe-Calc.",
     {"tela": {"type": "string"}, **ID}, ["tela"], f_abrir_tela, {**ESCRITA, "idempotentHint": False}),
    ("preencher_tela", "Preenche campos da tela aberta: valores {nome do campo: valor} (listas: o valor da opção; marcas: true/false; datas DD/MM/AAAA; valores 1.234,56). Campos com evento recarregam a tela (podem aparecer campos novos). Não grava: use a ação de salvar da tela depois.",
     {**TOKEN, "valores": {"type": "object"}}, ["token", "valores"], f_preencher_tela, ESCRITA),
    ("acionar_tela", "Clica numa ação da tela: botão (Salvar, Incluir, Novo, Alterar, Excluir, Gerar...), ação de uma linha de tabela, aba (aba:...) ou página (pag:...). Pode levar valores para preencher antes do clique. Devolve a tela atualizada e as mensagens do PJe-Calc.",
     {**TOKEN, "acao": {"type": "string"}, "valores": {"type": "object"}}, ["token", "acao"], f_acionar_tela,
     {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}),
    ("ler_tela", "Lê de novo a tela aberta (estado atual, mensagens e erros de validação).", TOKEN, ["token"], f_ler_tela, LEITURA),
    ("fechar_tela", "Fecha a tela aberta (o que não foi salvo nela é descartado).", TOKEN, ["token"], f_fechar_tela, ESCRITA),
]
POR_NOME = {f[0]: f for f in FERRAMENTAS}


def lista_ferramentas():
    return [{"name": n, "description": d, "annotations": anot,
             "inputSchema": {"type": "object", "properties": props, "required": req}} for n, d, props, req, _, anot in FERRAMENTAS]


# ============================================================================ conferência dos argumentos
# Os argumentos de cada chamada são conferidos com o inputSchema da ferramenta antes de executar: tipo, enum,
# obrigatórios e parâmetros desconhecidos, com mensagens que dizem ao Claude o que corrigir (em vez de uma falha
# interna ou de um dado ignorado em silêncio). null vale como "não informado". Textos "true"/"sim"... em campos
# true/false e enums com outra grafia ("não" por "nao") são aceitos e normalizados.
NOME_TIPO = {"string": "texto", "number": "número", "integer": "número inteiro", "boolean": "true/false",
             "object": "objeto {…}", "array": "lista […]"}
TEXTO_BOOL = {"true": True, "sim": True, "s": True, "1": True, "false": False, "nao": False, "n": False, "0": False}


def _tipo_ok(v, tipo: str) -> bool:
    if tipo in ("number", "integer"):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and (tipo == "number" or float(v).is_integer())
    return isinstance(v, {"string": str, "boolean": bool, "object": dict, "array": list}[tipo])


def validar(v, esq: dict, onde: str, erros: list):
    """Confere v com o esquema esq; acrescenta os problemas em erros e devolve o valor normalizado."""
    if v is None:
        return v
    tipos = esq.get("type")
    tipos = [tipos] if isinstance(tipos, str) else tipos or []
    if tipos and not any(_tipo_ok(v, t) for t in tipos):
        if "boolean" in tipos and isinstance(v, str) and _fold(v) in TEXTO_BOOL:
            v = TEXTO_BOOL[_fold(v)]
        else:
            erros.append(f"{onde}: esperado {' ou '.join(NOME_TIPO.get(t, t) for t in tipos)}, veio {json.dumps(v, ensure_ascii=False)[:80]}.")
            return v
    if "enum" in esq and v not in esq["enum"]:
        igual = next((e for e in esq["enum"] if _fold(e) == _fold(v)), None)
        if igual is None:
            erros.append(f"{onde}: “{v}” não é válido. Use um de: {', '.join(map(str, esq['enum']))}.")
            return v
        v = igual
    if isinstance(v, dict):
        props, extra = esq.get("properties"), esq.get("additionalProperties")
        faltam = [k for k in esq.get("required") or [] if v.get(k) is None]
        if faltam:
            erros.append(f"{onde or 'argumentos'}: falta{'m' if len(faltam) > 1 else ''} {', '.join(faltam)}.")
        for k in list(v):
            filho = f"{onde}.{k}" if onde else k
            if props and k in props:
                v[k] = validar(v[k], props[k], filho, erros)
            elif isinstance(extra, dict):
                v[k] = validar(v[k], extra, filho, erros)
            elif props and extra is not True:
                erros.append(f"{filho}: parâmetro desconhecido. Válidos: {', '.join(props)}.")
    elif isinstance(v, list) and isinstance(esq.get("items"), dict):
        for i in range(len(v)):
            v[i] = validar(v[i], esq["items"], f"{onde}[{i}]", erros)
    return v


# ============================================================================ protocolo MCP (JSON-RPC 2.0)
def responder(msg) -> dict | None:
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Mensagem JSON-RPC inválida (esperado um objeto)."}}
    metodo, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notificação (initialized, cancelled...): sem resposta
        return None
    if metodo == "initialize":
        pedida = (msg.get("params") or {}).get("protocolVersion")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": pedida if pedida in VERSOES_PROTOCOLO else VERSOES_PROTOCOLO[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "pjecalc-studio", "title": "PJe-Calc Studio", "version": VERSAO},
            "instructions": INSTRUCOES}}
    if metodo == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if metodo == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": lista_ferramentas()}}
    if metodo == "tools/call":
        p = msg.get("params") or {}
        f = POR_NOME.get(p.get("name"))
        if not f:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Ferramenta desconhecida: {p.get('name')}"}}
        args = p.get("arguments")
        args = {} if args is None else args
        try:
            if not isinstance(args, dict):
                raise ErroStudio("Os argumentos devem ser um objeto JSON {parâmetro: valor}.")
            erros = []
            args = validar(args, {"type": "object", "properties": f[2], "required": f[3]}, "", erros)
            if erros:
                raise ErroStudio("Argumentos inválidos para " + f[0] + ": " + " ".join(erros[:10])
                                 + (f" (e mais {len(erros) - 10})" if len(erros) > 10 else ""))
            # JSON compacto: menos texto para o Claude ler, mesmo conteúdo
            texto, erro = json.dumps(f[4](args), ensure_ascii=False, separators=(",", ":"), default=str), False
        except ErroStudio as e:
            texto, erro = str(e), True
        except Exception as e:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            texto, erro = f"Falha interna do conector: {type(e).__name__}: {e}", True
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": texto}], "isError": erro}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Método não suportado: {metodo}"}}
