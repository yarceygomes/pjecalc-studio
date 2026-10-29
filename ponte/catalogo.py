"""Opções oficiais exibidas pela nova interface.

Os valores abaixo foram lidos das telas do PJe-Calc Cidadão 2.16.0 (build 25/06/2026) durante a
investigação de integração e são servidos por /api/opcoes. Exceções lidas na hora da instalação em uso:
municípios (/api/municipios), assuntos CNJ (/api/casos/<id>/assuntos-cnj) e os parâmetros de cada verba
gravada (quadro de critérios). Em outra versão do PJe-Calc, uma opção que não exista mais é recusada pela
própria tela oficial no envio, e a mensagem dela é exibida.
"""

VERSAO_CATALOGO = "2.16.0"

VERBAS_EXPRESSAS = [
    "13º SALÁRIO", "FÉRIAS + 1/3", "VALE TRANSPORTE", "ABONO PECUNIÁRIO", "GORJETA", "VALOR PAGO - NÃO TRIBUTÁVEL",
    "ACORDO (MERA LIBERALIDADE)", "GRATIFICAÇÃO DE FUNÇÃO", "VALOR PAGO - TRIBUTÁVEL", "ACORDO (MULTA)",
    "GRATIFICAÇÃO POR TEMPO DE SERVIÇO", "ACORDO (VERBAS INDENIZATÓRIAS)", "HORAS EXTRAS 100%",
    "ACORDO (VERBAS REMUNERATÓRIAS)", "HORAS EXTRAS 50%", "ADICIONAL DE HORAS EXTRAS 50%", "HORAS IN ITINERE",
    "ADICIONAL DE INSALUBRIDADE 10%", "INDENIZAÇÃO ADICIONAL", "ADICIONAL DE INSALUBRIDADE 20%",
    "INDENIZAÇÃO PIS - ABONO SALARIAL", "ADICIONAL DE INSALUBRIDADE 40%", "INDENIZAÇÃO POR DANO ESTÉTICO",
    "ADICIONAL DE PERICULOSIDADE 30%", "INDENIZAÇÃO POR DANO MATERIAL", "ADICIONAL DE PRODUTIVIDADE 30%",
    "INDENIZAÇÃO POR DANO MORAL", "ADICIONAL DE RISCO 40%", "INTERVALO INTERJORNADAS", "ADICIONAL DE SOBREAVISO",
    "INTERVALO INTRAJORNADA", "ADICIONAL DE TRANSFERÊNCIA 25%", "MULTA CONVENCIONAL", "ADICIONAL NOTURNO 20%",
    "MULTA DO ARTIGO 477 DA CLT", "AJUDA DE CUSTO", "PARTICIPAÇÃO NOS LUCROS OU RESULTADOS - PLR", "AVISO PRÉVIO",
    "PRÊMIO PRODUÇÃO", "CESTA BÁSICA", "REPOUSO SEMANAL REMUNERADO", "COMISSÃO", "RESTITUIÇÃO / INDENIZAÇÃO DE DESPESA",
    "DEVOLUÇÃO DE DESCONTOS INDEVIDOS", "SALDO DE EMPREITADA", "DIFERENÇA SALARIAL", "SALDO DE SALÁRIO",
    "DIÁRIAS - INTEGRAÇÃO AO SALÁRIO", "SALÁRIO MATERNIDADE", "DIÁRIAS - PAGAMENTO", "SALÁRIO RETIDO",
    "FERIADO EM DOBRO", "TÍQUETE-ALIMENTAÇÃO",
]

ESTADOS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
           "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]


def _op(*pares):
    return [{"valor": v, "rotulo": r} for v, r in pares]


OPCOES = {
    "contrato.regime": _op(("INTERMITENTE", "Trabalho Intermitente"), ("INTEGRAL", "Tempo Integral"),
                           ("PARCIAL", "Tempo Parcial")),
    "contrato.apuracaoAvisoPrevio": _op(("NAO_APURAR", "Não apurar"), ("APURACAO_CALCULADA", "Calculado"),
                                        ("APURACAO_INFORMADA", "Informado")),
    "reclamante.tipoDocumentoFiscal": _op(("CPF", "CPF"), ("CNPJ", "CNPJ"), ("CEI", "CEI")),
    "reclamante.tipoDocumentoPrevidenciario": _op(("PIS", "PIS"), ("PASEP", "PASEP"), ("NIT", "NIT")),
    "reclamado.tipoDocumentoFiscal": _op(("CPF", "CPF"), ("CNPJ", "CNPJ"), ("CEI", "CEI")),
    "liquidacao.indicesAcumulados": _op(
        ("MES_SUBSEQUENTE_AO_VENCIMENTO", "A partir do mês subsequente ao vencimento das verbas"),
        ("MES_DO_VENCIMENTO", "A partir do mês do vencimento das verbas"),
        ("MES_SUBSEQUENTE_E_MES_DO_VENCIMENTO", "Mês subsequente e mês do vencimento (conforme a verba)")),
    "fgts.tipoDeVerba": _op(("PAGAR", "Pagar"), ("DEPOSITAR", "Depositar")),
    "fgts.comporPrincipal": _op(("SIM", "Sim"), ("NAO", "Não")),
    "fgts.multaDoFgts": _op(("VINTE_POR_CENTO", "20%"), ("QUARENTA_POR_CENTO", "40%")),
    "fgts.tipoDoValorDaMulta": _op(("CALCULADA", "Calculado"), ("INFORMADA", "Informado")),
    # quando o código interno não foi observado, o valor é o próprio rótulo oficial (a ponte seleciona pelo rótulo)
    "fgts.incidenciaDoFgts": _op(("SOBRE_O_TOTAL_DEVIDO", "Sobre devido"),
                                 ("Sobre saldo e/ou saque", "Sobre saldo e/ou saque"),
                                 ("Sobre diferença", "Sobre diferença"),
                                 ("Sobre devido + saldo e/ou saque", "Sobre devido + saldo e/ou saque"),
                                 ("Sobre devido - saldo e/ou saque", "Sobre devido - saldo e/ou saque")),
    "atualizacao.indiceTrabalhista": _op(
        ("TUACDT", "Tabela Única de Atualização e Conversão de Débitos Trabalhistas"),
        ("TABELA_DEVEDOR_FAZENDA", "Devedor Fazenda Pública"), ("TABELA_INDEBITO_TRIBUTARIO", "Repetição de Indébito Tributário"),
        ("TABELA_UNICA_JT_MENSAL", "Tabela JT Mensal"), ("TABELA_UNICA_JT_DIARIO", "Tabela JT Diária"), ("TR", "TR"),
        ("IGPM", "IGP-M"), ("INPC", "INPC"), ("IPC", "IPC"), ("IPCA", "IPCA"), ("IPCAE", "IPCA-E"), ("IPCAETR", "IPCA-E/TR")),
    "atualizacao.outroIndiceTrabalhista": _op(
        ("TUACDT", "Tabela Única de Atualização e Conversão de Débitos Trabalhistas"),
        ("TABELA_DEVEDOR_FAZENDA", "Devedor Fazenda Pública"), ("TABELA_INDEBITO_TRIBUTARIO", "Repetição de Indébito Tributário"),
        ("TABELA_UNICA_JT_MENSAL", "Tabela JT Mensal"), ("TABELA_UNICA_JT_DIARIO", "Tabela JT Diária"), ("TR", "TR"),
        ("IGPM", "IGP-M"), ("INPC", "INPC"), ("IPC", "IPC"), ("IPCA", "IPCA"), ("IPCAE", "IPCA-E"), ("IPCAETR", "IPCA-E/TR"),
        ("SELIC", "SELIC (Receita Federal)")),
    "atualizacao.juros": _op(*[(r, r) for r in (
        "Juros Padrão", "Juros Caderneta de Poupança", "Juros Fazenda Pública", "Juros Simples 0,5% a.m.",
        "Juros Simples 1,0% a.m.", "Juros Simples 0,0333333% a.d.", "Juros Simples 2,0% a.a. (0,1666666% a.m.)",
        "SELIC (Receita Federal)", "SELIC Simples", "SELIC Composta", "TRD Juros Simples", "TRD Juros Compostos")]),
    "atualizacao.outroJuros": _op(*[(r, r) for r in (
        "Juros Padrão", "Juros Caderneta de Poupança", "Juros Fazenda Pública", "Juros Simples 0,5% a.m.",
        "Juros Simples 1,0% a.m.", "Juros Simples 0,0333333% a.d.", "Juros Simples 2,0% a.a. (0,1666666% a.m.)",
        "SELIC (Receita Federal)", "SELIC Simples", "SELIC Composta", "TRD Juros Simples", "Sem Juros")]),
    "atualizacao.baseDeJurosDasVerbas": _op(("Verbas", "Verbas"), ("VERBA_INSS", "Verba (-) Contribuição Social"),
                                            ("Verba (-) Contribuição Social (-) Previdência Privada",
                                             "Verba (-) Contribuição Social (-) Previdência Privada")),
    "atualizacao.indiceDeCorrecaoDoFGTS": _op(("UTILIZAR_INDICE_TRABALHISTA", "Utilizar índice trabalhista"),
                                              ("UTILIZAR_INDICE_JAM", "Utilizar índice JAM"),
                                              ("UTILIZAR_INDICE_JAM_E_TRABALHISTA", "Utilizar índice JAM e índice trabalhista")),
}
