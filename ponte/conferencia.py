"""Conferência preventiva dos dados de entrada (antes de enviá-los ao PJe-Calc).

Estas verificações apenas apontam inconsistências de preenchimento. Elas não calculam
verbas e não substituem as validações do PJe-Calc, que continuam sendo a palavra final
(as mensagens do motor são sempre exibidas ao usuário).

Cada aviso: {"nivel": "impeditivo"|"alerta", "campo": <chave>, "etapa": <etapa>, "texto": ...}
"""
from __future__ import annotations

import re
from datetime import date

from .catalogo import VERBAS_EXPRESSAS
from .jsf import fold


def digito_cnj(numero: str, ano: str, justica: str, tribunal: str, origem: str) -> str:
    """Dígito verificador do número único (Resolução CNJ nº 65/2008, módulo 97 - ISO 7064)."""
    base = f"{int(numero):07d}{int(ano):04d}{int(justica):01d}{int(tribunal):02d}{int(origem):04d}"
    return f"{98 - (int(base) * 100) % 97:02d}"


def cpf_valido(cpf: str) -> bool:
    d = re.sub(r"\D", "", cpf or "")
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def cnpj_valido(cnpj: str) -> bool:
    d = re.sub(r"\D", "", cnpj or "")
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        p = pesos if n == 12 else [6] + pesos
        s = sum(int(d[i]) * p[i] for i in range(n))
        r = s % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


def data_br(s: str | None) -> date | None:
    if not s:
        return None
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s.strip())
    if not m:
        raise ValueError(s)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def competencia(s: str) -> tuple[int, int]:
    m = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{4})", (s or "").strip())
    if not m:
        raise ValueError(s)
    return int(m.group(2)), int(m.group(1))


VALOR_BR = re.compile(r"-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?")


def valor_br(s) -> float | None:
    """Converte '1.234,56' em número. Vazio -> None (diferente de zero). Formato inválido -> ValueError."""
    if s is None or (isinstance(s, str) and not s.strip()):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = s.strip()
    if not VALOR_BR.fullmatch(t):
        raise ValueError(s)
    return float(t.replace(".", "").replace(",", "."))


def _aviso(nivel, campo, etapa, texto):
    return {"nivel": nivel, "campo": campo, "etapa": etapa, "texto": texto}


def conferir(rascunho: dict) -> list[dict]:
    """Verifica o rascunho da nova interface. Não altera nada."""
    d = rascunho.get("dados", {})
    avisos: list[dict] = []

    def obrig(campo, etapa, rotulo):
        if not str(d.get(campo) or "").strip():
            avisos.append(_aviso("impeditivo", campo, etapa, f"{rotulo} é obrigatório no PJe-Calc."))

    obrig("reclamante.nome", "identificacao", "Nome do reclamante")
    obrig("reclamado.nome", "identificacao", "Nome do reclamado")
    obrig("local.estado", "identificacao", "Estado")
    obrig("local.municipio", "identificacao", "Município")
    obrig("contrato.dataAdmissao", "contrato", "Data de admissão")
    obrig("contrato.dataAjuizamento", "contrato", "Data de ajuizamento")

    # número do processo (dígito verificador CNJ)
    partes = [d.get(k) for k in ("processo.numero", "processo.digito", "processo.ano", "processo.regiao", "processo.vara")]
    if any(partes) and all(partes):
        try:
            esperado = digito_cnj(partes[0], partes[2], "5", partes[3], partes[4])
            if esperado != f"{int(partes[1]):02d}":
                avisos.append(_aviso("impeditivo", "processo.digito", "identificacao",
                                     f"Dígito verificador não confere com o número informado (esperado {esperado}, "
                                     "pela Resolução CNJ 65/2008). O PJe-Calc recusará a gravação."))
        except ValueError:
            avisos.append(_aviso("impeditivo", "processo.numero", "identificacao", "Número do processo contém caracteres inválidos."))
    elif any(partes):
        avisos.append(_aviso("alerta", "processo.numero", "identificacao",
                             "Número do processo incompleto. Sem ele, o cálculo não poderá ser anexado ao PJe."))

    for papel in ("reclamante", "reclamado"):
        tipo, num = d.get(f"{papel}.tipoDocumentoFiscal"), d.get(f"{papel}.numeroDocumentoFiscal")
        if num and tipo == "CPF" and not cpf_valido(num):
            avisos.append(_aviso("impeditivo", f"{papel}.numeroDocumentoFiscal", "identificacao", "CPF inválido."))
        if num and tipo == "CNPJ" and not cnpj_valido(num):
            avisos.append(_aviso("impeditivo", f"{papel}.numeroDocumentoFiscal", "identificacao", "CNPJ inválido."))
        if num and not tipo:
            avisos.append(_aviso("impeditivo", f"{papel}.tipoDocumentoFiscal", "identificacao", "Informe o tipo do documento fiscal."))

    # datas do contrato
    # cada data é lida separadamente: uma data inválida aponta o próprio campo e não esconde as demais verificações
    def data(campo, etapa, rotulo):
        try:
            return data_br(d.get(campo))
        except ValueError:
            avisos.append(_aviso("impeditivo", campo, etapa, f"{rotulo}: “{d.get(campo)}” não é uma data válida. Use DD/MM/AAAA."))
            return None

    def valor(campo, etapa, rotulo):
        try:
            return valor_br(d.get(campo))
        except ValueError:
            avisos.append(_aviso("impeditivo", campo, etapa,
                                 f"{rotulo}: “{d.get(campo)}” não é um valor válido. Use vírgula nos centavos, por exemplo 3.800,00."))
            return None

    adm = data("contrato.dataAdmissao", "contrato", "Admissão")
    dem = data("contrato.dataDemissao", "contrato", "Demissão")
    aju = data("contrato.dataAjuizamento", "contrato", "Ajuizamento")
    ini = data("contrato.dataInicioCalculo", "contrato", "Início do cálculo")
    fim = data("contrato.dataTerminoCalculo", "contrato", "Término do cálculo")
    data("processo.autuadoEm", "identificacao", "Autuado em")
    valor("processo.valorDaCausa", "identificacao", "Valor da causa")
    valor("jornada.cargaHorariaPadrao", "jornada", "Carga horária mensal")
    prazo = str(d.get("contrato.prazoAvisoInformado") or "").strip()
    if prazo and not prazo.isdigit():
        avisos.append(_aviso("impeditivo", "contrato.prazoAvisoInformado", "contrato", "Prazo do aviso prévio: use só números inteiros (dias)."))
    liq = (rascunho.get("liquidacao") or {}).get("data")
    if liq:
        try:
            data_br(liq)
        except ValueError:
            avisos.append(_aviso("impeditivo", "liquidacao.data", "atualizacao", f"Data de liquidação “{liq}” inválida. Use DD/MM/AAAA."))
    if adm and dem and dem < adm:
        avisos.append(_aviso("impeditivo", "contrato.dataDemissao", "contrato", "Demissão anterior à admissão."))
    if dem and aju and aju < dem:
        avisos.append(_aviso("alerta", "contrato.dataAjuizamento", "contrato",
                             "Ajuizamento anterior à demissão: confirme se a ação foi proposta durante o contrato."))
    if ini and fim and fim < ini:
        avisos.append(_aviso("impeditivo", "contrato.dataTerminoCalculo", "contrato", "Término do cálculo anterior ao início."))
    if d.get("contrato.prescricaoQuinquenal") and adm and aju and (aju.year - adm.year) * 12 + aju.month - adm.month < 60:
        avisos.append(_aviso("impeditivo", "contrato.prescricaoQuinquenal", "contrato",
                             "O PJe-Calc não admite prescrição quinquenal quando admissão e ajuizamento distam menos de cinco anos."))
    if aju and dem and (aju.year - dem.year) * 12 + aju.month - dem.month > 24:
        avisos.append(_aviso("alerta", "contrato.dataAjuizamento", "contrato",
                             "Ajuizamento mais de dois anos após a demissão: avalie a prescrição bienal (art. 7º, XXIX, CF). "
                             "Decisão do usuário."))
    mr = valor("contrato.maiorRemuneracao", "contrato", "Maior remuneração")
    ur = valor("contrato.ultimaRemuneracao", "contrato", "Última remuneração")
    if mr is not None and ur is not None and ur > mr:
        avisos.append(_aviso("alerta", "contrato.maiorRemuneracao", "contrato", "Última remuneração maior que a maior remuneração."))
    if dem is None and d.get("contrato.apuracaoAvisoPrevio") not in (None, "", "NAO_APURAR"):
        avisos.append(_aviso("alerta", "contrato.apuracaoAvisoPrevio", "contrato",
                             "Aviso prévio configurado sem data de demissão."))

    # histórico salarial (uma ocorrência por competência): formato, vazio × zero × desconhecido,
    # duplicidades, lacunas e meses fora do período do contrato
    hist = rascunho.get("historicos", [])
    fim_periodo = fim or dem
    vistos_nomes = set()
    for i, h in enumerate(hist):
        rot = (h.get("nome") or "").strip().upper() or f"histórico {i + 1}"
        if rot in vistos_nomes:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico", f"Há dois históricos chamados '{rot}'."))
        vistos_nomes.add(rot)
        if rot == "ÚLTIMA REMUNERAÇÃO":
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico",
                                 "O nome 'ÚLTIMA REMUNERAÇÃO' é reservado ao histórico criado pelo próprio PJe-Calc."))
        ocs = h.get("ocorrencias") or []
        if not ocs:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico", f"{rot}: nenhuma competência informada."))
            continue
        comps, invalidas, vazias, desconhecidas, valores_ruins = [], [], [], [], []
        for o in ocs:
            try:
                comps.append(competencia(o.get("competencia")))
            except ValueError:
                invalidas.append(str(o.get("competencia")))
                continue
            v = o.get("valor")
            if v is None or str(v).strip() == "":
                vazias.append(o["competencia"])
            elif str(v).strip() == "?":
                desconhecidas.append(o["competencia"])
            else:
                try:
                    valor_br(v)
                except ValueError:
                    valores_ruins.append(o["competencia"])

        def _lista(xs):
            return ", ".join(xs[:6]) + ("…" if len(xs) > 6 else "")
        if invalidas:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico", f"{rot}: competência inválida ({_lista(invalidas)}). Use MM/AAAA."))
        if vazias:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico",
                                 f"{rot}: {len(vazias)} competência(s) sem valor ({_lista(vazias)}). Vazio não é zero: informe 0,00 se for o caso."))
        if desconhecidas:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico",
                                 f"{rot}: {len(desconhecidas)} competência(s) marcadas como desconhecidas ({_lista(desconhecidas)})."))
        if valores_ruins:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico", f"{rot}: valor em formato inválido ({_lista(valores_ruins)})."))
        dup = sorted({c for c in comps if comps.count(c) > 1})
        if dup:
            avisos.append(_aviso("impeditivo", f"historicos.{i}", "historico",
                                 f"{rot}: competências repetidas ({_lista([f'{m:02d}/{a}' for a, m in dup])})."))
        unicas = sorted(set(comps))
        faltando = []
        for (a1, m1), (a2, m2) in zip(unicas, unicas[1:]):
            a, m = a1, m1
            while True:
                m += 1
                if m > 12:
                    a, m = a + 1, 1
                if (a, m) >= (a2, m2):
                    break
                faltando.append(f"{m:02d}/{a}")
        if faltando:
            avisos.append(_aviso("alerta", f"historicos.{i}", "historico",
                                 f"{rot}: lacuna de {len(faltando)} competência(s) ({_lista(faltando)})."))
        if adm and unicas and unicas[0] < (adm.year, adm.month):
            avisos.append(_aviso("alerta", f"historicos.{i}", "historico", f"{rot}: há competências anteriores à admissão."))
        if fim_periodo and unicas and unicas[-1] > (fim_periodo.year, fim_periodo.month):
            avisos.append(_aviso("alerta", f"historicos.{i}", "historico", f"{rot}: há competências posteriores ao fim do período do cálculo."))

    # verbas: duplicidades (expressas e manuais compartilham a mesma lista no PJe-Calc)
    manuais = rascunho.get("verbasManuais") or []
    e_reflexo = lambda v: (v.get("parametros") or {}).get("tipoDeVerba") == "REFLEXO"  # noqa: E731
    verbas = [v.strip().upper() for v in rascunho.get("verbas", [])] + \
             [(v.get("descricao") or "").strip().upper() for v in manuais if not e_reflexo(v)]
    reflexos = [f"{(v.get('descricao') or '').strip().upper()} SOBRE {(v.get('principal') or '').strip().upper()}"
                for v in manuais if e_reflexo(v)]
    for v in sorted({x for x in reflexos if reflexos.count(x) > 1}):
        avisos.append(_aviso("impeditivo", "verbas", "verbas", f"Reflexo '{v}' lançado mais de uma vez."))
    for v in sorted({v for v in verbas if v and verbas.count(v) > 1}):
        avisos.append(_aviso("impeditivo", "verbas", "verbas", f"Verba '{v}' incluída mais de uma vez."))
    expressas = {fold(v) for v in VERBAS_EXPRESSAS}
    for v in rascunho.get("verbas", []):
        if fold(v) not in expressas:
            avisos.append(_aviso("impeditivo", "verbas", "verbas", f"A verba '{v}' não está no lançamento expresso do PJe-Calc: "
                                 "retire-a da lista e inclua-a como verba manual (lançamento manual, mais abaixo na etapa Verbas)."))
    if not [v for v in verbas if v]:
        avisos.append(_aviso("alerta", "verbas", "verbas", "Nenhuma verba selecionada: o cálculo não terá parcelas."))
    for i, v in enumerate(manuais):
        rot = (v.get("descricao") or "").strip().upper()
        if not rot:
            avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas", f"Verba manual {i + 1} sem nome."))
            continue
        if not v.get("assuntoCnj"):
            avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas", f"{rot}: informe o Assunto CNJ (exigido pelo PJe-Calc)."))
        par = v.get("parametros") or {}
        if e_reflexo(v):
            principal = (v.get("principal") or "").strip().upper()
            if not principal:
                avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas", f"{rot}: escolha a verba principal do reflexo."))
            elif principal not in verbas:
                avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas",
                                     f"{rot}: a verba principal {principal} não está entre as verbas do cálculo."))
            continue
        for b in v.get("basesVerbas") or []:
            nb = (b.get("verba") or "").strip().upper()
            if nb == rot:
                avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas", f"{rot}: a verba não pode ser base de si mesma."))
            elif nb and nb not in verbas:
                avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas",
                                     f"{rot}: a verba {nb}, usada como base, não está entre as verbas do cálculo."))
        if par.get("valor") != "INFORMADO" and par.get("tipoDaBaseTabelada") == "HISTORICO_SALARIAL" and not v.get("bases"):
            avisos.append(_aviso("impeditivo", f"verbasManuais.{i}", "verbas",
                                 f"{rot}: base Histórico Salarial sem nenhum histórico selecionado."))
    # ocorrências mês a mês informadas por verba
    for nome, cfg in (rascunho.get("verbasConfig") or {}).items():
        ocs = cfg.get("ocorrencias") or []
        invalidas, ruins, comps = [], [], []
        for o in ocs:
            try:
                comps.append(competencia(o.get("competencia")))
            except ValueError:
                invalidas.append(str(o.get("competencia")))
                continue
            for chave in ("divisor", "multiplicador", "quantidade", "devido", "pago"):
                x = o.get(chave)
                if x not in (None, "") and not re.fullmatch(r"-?[\d.]*\d(,\d+)?", str(x).strip()):
                    ruins.append(f"{o['competencia']} ({chave})")
        if invalidas:
            avisos.append(_aviso("impeditivo", f"verbasConfig.{nome}", "verbas",
                                 f"{nome}: competência inválida nas ocorrências ({', '.join(invalidas[:6])}). Use MM/AAAA."))
        if ruins:
            avisos.append(_aviso("impeditivo", f"verbasConfig.{nome}", "verbas",
                                 f"{nome}: valor em formato inválido nas ocorrências ({', '.join(ruins[:6])})."))
        dup = sorted({c for c in comps if comps.count(c) > 1})
        if dup:
            avisos.append(_aviso("impeditivo", f"verbasConfig.{nome}", "verbas",
                                 f"{nome}: competências repetidas nas ocorrências ({', '.join(f'{m:02d}/{a}' for a, m in dup)})."))
    # perguntas guiadas: documento de base, término do contrato e perguntas para escolher as verbas
    if not rascunho.get("documentoBase"):
        avisos.append(_aviso("alerta", "documentoBase", "identificacao",
                             "Diga se o cálculo parte de uma petição inicial, de uma decisão, de um acordo ou de outro documento "
                             "(etapa Partes e processo): as perguntas das outras etapas se ajustam a isso."))
    if not rascunho.get("desligamento"):
        avisos.append(_aviso("alerta", "desligamento", "contrato",
                             "Responda como o contrato terminou (etapa Contrato): é o que define as verbas da rescisão."))
    resp_verbas = rascunho.get("perguntasVerbas") or {}
    sem_verbas = [nome for pid, nome in PERGUNTAS_VERBAS if not resp_verbas.get(pid)]
    if sem_verbas:
        avisos.append(_aviso("alerta", "perguntasVerbas", "verbas",
                             f"Faltam {len(sem_verbas)} de {len(PERGUNTAS_VERBAS)} perguntas sobre verbas ({', '.join(sem_verbas)}). "
                             "Responda Sim ou Não a cada uma, para nenhuma verba ficar de fora."))
    # outros itens do cálculo (telas próprias do PJe-Calc): nenhum pode ficar sem resposta
    respostas = rascunho.get("outrosItens") or {}
    sem_resposta = [nome for iid, nome in OUTROS_ITENS if not respostas.get(iid)]
    if sem_resposta:
        avisos.append(_aviso("alerta", "outros", "outros",
                             f"Faltam {len(sem_resposta)} de {len(OUTROS_ITENS)} perguntas sobre outros itens do cálculo "
                             f"({', '.join(sem_resposta)}). Responda cada uma, nem que seja “Não se aplica”, para nada ficar de fora."))
    for iid, nome in OUTROS_ITENS:
        if respostas.get(iid) == "sim":
            avisos.append(_aviso("alerta", f"outros.{iid}", "outros",
                                 f"{nome}: marcado como necessário, mas ainda não preenchido no PJe-Calc."))
    return avisos


# Itens calculados em telas próprias do PJe-Calc; os ids são os de OUTROS_ITENS em web/app.js
OUTROS_ITENS = [
    ("ferias", "Férias"), ("faltas", "Faltas"), ("cartao", "Cartão de ponto"),
    ("multas", "Dano moral, multas e indenizações"), ("seguro-desemprego", "Seguro-desemprego"),
    ("salario-familia", "Salário-família"), ("honorarios", "Honorários"), ("custas", "Custas processuais"),
    ("inss", "Contribuição previdenciária (INSS)"), ("irpf", "Imposto de renda"),
    ("pensao", "Pensão alimentícia"), ("previdencia", "Previdência privada"),
]

# Perguntas para escolher as verbas; os ids são os de PERGUNTAS_VERBAS em web/app.js
PERGUNTAS_VERBAS = [
    ("rescisao", "Verbas da rescisão"), ("horas_extras", "Horas extras"), ("intervalos", "Intervalos"),
    ("noturno", "Trabalho noturno"), ("descansos", "Domingos, feriados e repouso"), ("sobreaviso", "Sobreaviso e deslocamento"),
    ("insalubridade", "Insalubridade"), ("periculosidade", "Periculosidade e risco"), ("transferencia", "Transferência"),
    ("salario", "Salário não pago ou pago a menor"), ("variaveis", "Comissões, prêmios e gratificações"),
    ("beneficios", "Benefícios"), ("devolucoes", "Descontos e despesas"), ("estabilidade", "Estabilidade e outras indenizações"),
]
