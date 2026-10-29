"""Testes que não dependem do PJe-Calc em execução.  Uso: py -I tests/test_unidades.py [relatorio.html]"""
import io
import os
import sys
import tempfile
import threading
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ponte import armazenamento, conferencia, planilha, sincronizar  # noqa: E402
from ponte.jsf import fold, parse, table  # noqa: E402
from ponte.pjecalc import classificar  # noqa: E402
from ponte.sincronizar import expandir  # noqa: E402

RELATORIO = sys.argv.pop(1) if len(sys.argv) > 1 else None


class Conferencia(unittest.TestCase):
    def test_digito_cnj(self):
        # validado pelo próprio PJe-Calc (aceitou 0000123-74.2025.5.08.0001 e 0000456-23.2025.5.08.0002)
        self.assertEqual(conferencia.digito_cnj("0000123", "2025", "5", "08", "0001"), "74")
        self.assertEqual(conferencia.digito_cnj("0000456", "2025", "5", "08", "0002"), "23")

    def test_documentos(self):
        self.assertTrue(conferencia.cpf_valido("529.982.247-25"))
        self.assertFalse(conferencia.cpf_valido("529.982.247-24"))
        self.assertTrue(conferencia.cnpj_valido("11.222.333/0001-81"))
        self.assertFalse(conferencia.cnpj_valido("11.222.333/0001-80"))

    def base(self):
        return {"dados": {"reclamante.nome": "A", "reclamado.nome": "B", "local.estado": "PA", "local.municipio": "BELEM",
                          "contrato.dataAdmissao": "01/02/2022", "contrato.dataDemissao": "31/01/2025",
                          "contrato.dataAjuizamento": "10/03/2025"},
                "historicos": [{"nome": "SALARIO", "ocorrencias": [{"competencia": c["competencia"], "valor": "1.000,00"}
                                                                   for c in expandir("02/2022", "01/2025", "")]}],
                "verbas": ["SALDO DE SALÁRIO"],
                "outrosItens": {iid: "nao" for iid, _ in conferencia.OUTROS_ITENS},
                "perguntasVerbas": {pid: "nao" for pid, _ in conferencia.PERGUNTAS_VERBAS},
                "documentoBase": "sentenca", "desligamento": "sem_justa_causa"}

    def test_sem_avisos(self):
        self.assertEqual(conferencia.conferir(self.base()), [])

    def test_outros_itens_sem_resposta_ou_a_preencher(self):
        r = self.base()
        del r["outrosItens"]["custas"], r["outrosItens"]["honorarios"]
        r["outrosItens"]["multas"] = "sim"
        av = [a for a in conferencia.conferir(r) if a["etapa"] == "outros"]
        self.assertEqual(len(av), 2)
        self.assertTrue(all(a["nivel"] == "alerta" for a in av))  # não impedem o envio: as telas exigem o cálculo no PJe-Calc
        self.assertIn("Faltam 2 de 12", av[0]["texto"])
        self.assertIn("Honorários", av[0]["texto"])
        self.assertEqual(av[1]["campo"], "outros.multas")
        r["outrosItens"]["multas"] = "feito"
        r["outrosItens"].update(custas="nao", honorarios="feito")
        self.assertEqual(conferencia.conferir(r), [])

    def test_perguntas_guiadas_sem_resposta(self):
        r = self.base()
        r["documentoBase"] = r["desligamento"] = ""
        del r["perguntasVerbas"]["horas_extras"]
        av = {a["campo"]: a for a in conferencia.conferir(r)}
        self.assertEqual(set(av), {"documentoBase", "desligamento", "perguntasVerbas"})
        self.assertEqual(av["desligamento"]["etapa"], "contrato")
        self.assertIn("Faltam 1 de 14", av["perguntasVerbas"]["texto"])
        self.assertIn("Horas extras", av["perguntasVerbas"]["texto"])

    def test_modelo_e_copia_nao_levam_respostas_de_outros_itens(self):
        r = self.base()
        r["outrosItens"]["custas"] = "feito"
        self.assertEqual(armazenamento.sem_dados_pessoais(r)["outrosItens"], {})
        # o documento de base é do tipo de trabalho (fica no modelo); o término do contrato e as respostas são do caso
        m = armazenamento.sem_dados_pessoais(r)
        self.assertEqual((m["documentoBase"], m["desligamento"], m["perguntasVerbas"]), ("sentenca", "", {}))

    def test_valores_e_datas_invalidos_nao_derrubam_a_conferencia(self):
        # antes, "abc" na maior remuneração lançava ValueError e a API respondia 500 (envio bloqueado)
        r = self.base()
        r["dados"].update({"contrato.maiorRemuneracao": "abc", "contrato.ultimaRemuneracao": "1234.56",
                           "contrato.dataDemissao": "31/02/2025", "processo.valorDaCausa": "10,0,0",
                           "contrato.prazoAvisoInformado": "30 dias"})
        r["liquidacao"] = {"data": "2025-01-01"}
        campos = {a["campo"] for a in conferencia.conferir(r) if a["nivel"] == "impeditivo"}
        self.assertTrue({"contrato.maiorRemuneracao", "contrato.ultimaRemuneracao", "contrato.dataDemissao",
                         "processo.valorDaCausa", "contrato.prazoAvisoInformado", "liquidacao.data"} <= campos)
        # uma data inválida não esconde as verificações das outras
        self.assertNotIn("contrato.dataAdmissao", campos)

    def test_valor_br(self):
        self.assertEqual(conferencia.valor_br("3.800,00"), 3800.0)
        self.assertEqual(conferencia.valor_br("3800,5"), 3800.5)
        self.assertIsNone(conferencia.valor_br(" "))
        for ruim in ("1234.56", "1.23,00", "abc"):
            with self.assertRaises(ValueError):
                conferencia.valor_br(ruim)

    def test_vazio_zero_desconhecido(self):
        r = self.base()
        ocs = r["historicos"][0]["ocorrencias"]
        ocs[0]["valor"] = ""
        ocs[1]["valor"] = "0,00"
        ocs[2]["valor"] = "?"
        textos = [a["texto"] for a in conferencia.conferir(r)]
        self.assertTrue(any("sem valor" in t for t in textos))
        self.assertTrue(any("desconhecidas" in t for t in textos))
        self.assertFalse(any("04/2022" in t and "sem valor" in t for t in textos))  # zero é valor válido

    def test_lacuna_e_duplicidade(self):
        r = self.base()
        ocs = r["historicos"][0]["ocorrencias"]
        del ocs[5]
        ocs.append(dict(ocs[0]))
        niveis = {(a["nivel"], a["texto"].split(":")[1].strip()[:9]) for a in conferencia.conferir(r)}
        self.assertIn(("alerta", "lacuna de"), niveis)
        self.assertIn(("impeditivo", "competênc"), niveis)

    def test_prescricao_quinquenal(self):
        r = self.base()
        r["dados"]["contrato.prescricaoQuinquenal"] = True
        self.assertTrue(any(a["campo"] == "contrato.prescricaoQuinquenal" for a in conferencia.conferir(r)))

    def test_datas(self):
        r = self.base()
        r["dados"]["contrato.dataDemissao"] = "01/01/2021"
        self.assertTrue(any(a["campo"] == "contrato.dataDemissao" and a["nivel"] == "impeditivo" for a in conferencia.conferir(r)))


class Planilhas(unittest.TestCase):
    def test_csv(self):
        r = planilha.ler("Competência;Valor\r\n03/2024;3.300,00\r\n".encode("cp1252"), "x.csv")
        self.assertEqual(r["linhas"][1], ["03/2024", "3.300,00"])

    def test_xlsx(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                                          '<sheets><sheet name="Plan1"/></sheets></workbook>')
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                                               '<si><t>Competência</t></si><si><t>Valor</t></si><si><t>03/2024</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                       '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                       '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>3300.5</v></c></row></sheetData></worksheet>')
        r = planilha.ler(buf.getvalue(), "x.xlsx")
        self.assertEqual(r["linhas"], [["Competência", "Valor"], ["03/2024", "3300,5"]])


class Jsf(unittest.TestCase):
    def test_parse_formulario(self):
        p = parse('<form id="formulario" action="/x"><input type="text" name="formulario:a" value="1"/>'
                  '<select name="formulario:s"><option value="1">UM</option><option value="2" selected="selected">DOIS</option></select>'
                  '<input type="radio" name="formulario:r" value="X" checked="checked"/><input type="radio" name="formulario:r" value="Y"/>'
                  '<input type="button" id="formulario:salvar" value="Salvar" onclick="A4J.AJAX.Submit(\'formulario\',event,{})"/></form>')
        f = p.forms["formulario"]
        self.assertEqual([x.name for x in f["fields"]], ["formulario:a", "formulario:s", "formulario:r", "formulario:r"])
        self.assertEqual(f["fields"][1].value, "2")
        self.assertEqual(f["actions"][0].text, "Salvar")

    def test_tabela_e_fold(self):
        cab, linhas = table('<table id="t"><thead><tr><th>A</th></tr></thead><tbody><tr><td>x<table><tr><td>in</td></tr></table></td></tr></tbody></table>', "t")
        self.assertEqual(cab, ["A"])
        self.assertEqual(len(linhas), 1)
        self.assertEqual(fold("  Belém  do PARÁ "), "belem do para")

    def test_classificar(self):
        m = classificar([{"class": "rich-messages-marker", "text": "Erro."}, {"class": "rich-messages-label", "text": "Falhou."},
                         {"class": "rich-messages-marker", "text": "Sucesso."}, {"class": "rich-messages-label", "text": "Operação realizada com sucesso."}])
        self.assertEqual([x["severidade"] for x in m], ["erro", "sucesso"])


class Ocorrencias(unittest.TestCase):
    def pagina(self):
        from ponte.jsf import Page
        linha = ('<input type="checkbox" name="formulario:listagem:{i}:ativo" checked="checked"/>'
                 '<input type="text" name="formulario:listagem:{i}:j_id153" value="01/{m}/2023" disabled="disabled"/>'
                 '<input type="text" name="formulario:listagem:{i}:j_id156" value="28/{m}/2023" disabled="disabled"/>'
                 '<input type="text" name="formulario:listagem:{i}:termoDiv" value="220,0000"/>'
                 '<input type="text" name="formulario:listagem:{i}:termoQuant" value="{q}"/>'
                 '<input type="text" name="formulario:listagem:{i}:valorDevido" value=""/>'
                 '<input type="text" name="formulario:listagem:{i}:valorPago" value="0,00"/>')
        html = ('<form id="formulario" action="/x"><input type="text" name="formulario:quantidade" value=""/>'
                + linha.format(i=0, m="02", q="0,0000") + linha.format(i=1, m="03", q="12,5000") + "</form>")
        return Page(None, "http://x/pjecalc/pages/calculo/parametrizar-ocorrencia.jsf", html)

    def test_grade(self):
        from ponte.pjecalc import _ocorrencias_da_pagina
        ocs = _ocorrencias_da_pagina(self.pagina())
        self.assertEqual([o["competencia"] for o in ocs], ["02/2023", "03/2023"])
        self.assertEqual(ocs[1]["quantidade"], "12,5000")
        self.assertTrue(ocs[0]["ativo"])
        self.assertEqual(ocs[0]["dataFinal"], "28/02/2023")
        self.assertNotIn("multiplicador", ocs[0])  # célula ausente na página não vira valor

    def test_informadas(self):
        from ponte.sincronizar import ocorrencias_informadas
        r = ocorrencias_informadas([
            {"competencia": "02/2023", "quantidade": "10,0000", "devido": "", "pago": "", "ativo": True, "_quantidadeMotor": "0,0000"},
            {"competencia": "03/2023", "quantidade": "", "devido": "", "pago": ""},
            {"competencia": "04/2023", "quantidade": "", "ativo": False}, {"quantidade": "1"}])
        self.assertEqual(r, [{"competencia": "02/2023", "ativo": True, "quantidade": "10,0000"},
                             {"competencia": "04/2023", "ativo": False}])

    def test_spec_manual(self):
        from ponte.sincronizar import spec_verba_manual
        s = spec_verba_manual({"descricao": " adicional x ", "assuntoCnj": "2086 - Horas Extras", "bases": ["salario base", " "],
                               "parametros": {"valor": "CALCULADO", "outroValorDoDivisor": "220", "outroValorDoMultiplicador": ""}})
        self.assertEqual(s, {"valor": "CALCULADO", "outroValorDoDivisor": "220", "descricao": "ADICIONAL X",
                             "assuntoCnj": "2086", "bases": ["SALARIO BASE"]})
        # valor informado: campos do modo calculado (padrões da interface) não vão para a tela
        s = spec_verba_manual({"descricao": "X", "bases": ["SALARIO BASE"], "parametros": {
            "valor": "INFORMADO", "tipoDaBaseTabelada": "HISTORICO_SALARIAL", "tipoDeDivisor": "OUTRO_VALOR", "fgts": False}})
        self.assertEqual(s, {"valor": "INFORMADO", "fgts": False, "descricao": "X"})

    def test_spec_reflexo_manual(self):
        from ponte.sincronizar import e_reflexo_manual, nome_reflexo_manual, spec_verba_manual
        v = {"descricao": "integração em plr", "principal": "horas extras 50%", "assuntoCnj": "2086",
             "comportamentoDoReflexo": "VALOR_MENSAL", "tratamentoFracaoReflexo": "MANTER",
             "parametros": {"tipoDeVerba": "REFLEXO", "valor": "CALCULADO", "tipoDaBaseTabelada": "HISTORICO_SALARIAL",
                            "outroValorDoMultiplicador": "1"}}
        self.assertTrue(e_reflexo_manual(v))
        self.assertEqual(nome_reflexo_manual(v), "INTEGRAÇÃO EM PLR SOBRE HORAS EXTRAS 50%")
        self.assertEqual(spec_verba_manual(v), {"tipoDeVerba": "REFLEXO", "valor": "CALCULADO", "outroValorDoMultiplicador": "1",
                                                "descricao": "INTEGRAÇÃO EM PLR", "assuntoCnj": "2086",
                                                "principal": "HORAS EXTRAS 50%", "comportamentoDoReflexo": "VALOR_MENSAL",
                                                "tratamentoFracaoReflexo": "MANTER"})
        r = Conferencia.base(None)
        r["verbasManuais"] = [dict(v, assuntoCnj="2086"), {**v, "principal": ""},
                              {"descricao": "ADIC", "assuntoCnj": "1", "basesVerbas": [{"verba": "ADIC"}, {"verba": "NAO EXISTE"}],
                               "parametros": {"valor": "INFORMADO"}}]
        textos = " | ".join(a["texto"] for a in conferencia.conferir(r))
        for trecho in ("HORAS EXTRAS 50% não está entre", "escolha a verba principal", "base de si mesma", "NAO EXISTE, usada como base"):
            self.assertIn(trecho, textos)

    def test_assuntos_cnj(self):
        from ponte.pjecalc import _assuntos_cnj
        html = ('<td id="formularioModalCNJ:arv:864::_defaultNodeFace:text"><span>864 - Direito do Trabalho</span></td>'
                '<td id="formularioModalCNJ:arv:864:1658:2086::_defaultNodeFace:text"><div><span>2086 - Horas Extras</span></div></td>')
        self.assertEqual(_assuntos_cnj(html)[1], {"codigo": "2086", "nome": "Horas Extras", "caminho": ["864", "1658", "2086"]})

    def test_conferencia_manual(self):
        r = Conferencia.base(None)
        r["verbasManuais"] = [{"descricao": "SALDO DE SALÁRIO", "parametros": {"tipoDaBaseTabelada": "HISTORICO_SALARIAL"}}]
        r["verbasConfig"] = {"SALDO DE SALÁRIO": {"ocorrencias": [{"competencia": "13/2023"}, {"competencia": "02/2023", "quantidade": "1,2,3"}]}}
        textos = " | ".join(a["texto"] for a in conferencia.conferir(r))
        for trecho in ("mais de uma vez", "Assunto CNJ", "sem nenhum histórico", "competência inválida", "formato inválido"):
            self.assertIn(trecho, textos)

    def test_pjc_principal_aninhada(self):
        # o XStream serializa a verba principal dentro do primeiro reflexo; no nível de cima fica só a referência
        from ponte.relatorio import ler_pjc
        oc = "<ocorrencias><list><OcorrenciaDeVerba><dataInicial>1675220400000</dataInicial><quantidade>10.00</quantidade></OcorrenciaDeVerba></list></ocorrencias>"
        xml = (f"<Calculo><verbas><set><Reflexo><id>2</id><nome>13º SOBRE HE</nome><descricao>13º</descricao><ocorrencias/>"
               f"<verbaPrincipal><Calculada><id>1</id><nome>HORAS EXTRAS 50%</nome>{oc}</Calculada></verbaPrincipal></Reflexo>"
               f"<internalRef reference='../Reflexo/verbaPrincipal/Calculada'/></set></verbas></Calculo>")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("calculo.xml", xml)
        v = {x["descricao"]: x for x in ler_pjc(buf.getvalue())["verbas"]}
        self.assertEqual(set(v), {"13º SOBRE HE", "HORAS EXTRAS 50%"})
        self.assertEqual(v["HORAS EXTRAS 50%"]["ocorrencias"][0]["quantidade"], "10")


TELA_EXEMPLO = """<html><body><form id="formulario" name="formulario" action="/pjecalc/pages/calculo/falta.jsf">
<div id="menu"><input type="text" name="formulario:menuBusca" /></div>
<div id="contentPrincipal"><div id="barraTitulo"><span class="textoTitulo">C&aacute;lculo &gt; Faltas</span></div>
<fieldset><legend>Dados do C&aacute;lculo</legend><span>C&aacute;lculo: 41</span></fieldset>
<fieldset><legend><b>Nova Falta</b></legend>
 <label for="formulario:inicio">Data Inicial *</label><br /><span id="formulario:inicioPopup">
 <input id="formulario:inicioInputDate" name="formulario:inicioInputDate" type="text" value="" />
 <input id="formulario:inicioInputCurrentDate" name="formulario:inicioInputCurrentDate" style="display:none" type="hidden" value="10/2026" /></span>
 <div id="formulario:inicioScript" style="display: none;"><script>new Calendar('x', {'a':1});</script></div>
 <input id="formulario:justificada" type="checkbox" name="formulario:justificada" onchange="A4J.AJAX.Submit('formulario',event,{'parameters':{'x':'x'} } )" /><label for="formulario:outroCampo">Justificada</label>
 <legend>x</legend>
 <select id="formulario:tipo" name="formulario:tipo"><option value="org.jboss.seam.ui.NoSelectionConverter.noSelectionValue"></option><option value="A">Tipo A</option></select>
 <span class="rich-tool-tip" id="formulario:t1"><span>Escolha o tipo da falta conforme o documento.</span></span><span id="formulario:tipoHelp"></span>
 <script>new ToolTip("formulario:t1","formulario:tipoHelp",{});</script>
 <input type="submit" id="formulario:salvar" name="formulario:salvar" value="Salvar" />
</fieldset>
<table class="rich-table" id="formulario:listagem"><thead><tr><th>A&ccedil;&atilde;o</th><th>In&iacute;cio</th></tr></thead>
<tbody><tr><td><a id="formulario:listagem:0:excluir" href="#" title="Excluir" onclick="A4J.AJAX.Submit('formulario',event,{'parameters':{'formulario:listagem:0:excluir':'formulario:listagem:0:excluir'} } );return false;"><img src="x.gif" /></a></td><td>10/03/2023</td></tr></tbody></table>
<div class="rich-datascr" id="formulario:pag"><table><tr><td class="rich-datascr-act">1</td><td class="rich-datascr-inact" onclick="Event.fire(this, 'rich:datascroller:onscroll', {'page': '2'});">2</td></tr></table></div>
<table><tr><td class="rich-tab-header" id="formulario:abaA_lbl">Aba A</td></tr></table>
<table id="formulario:abaA_shifted" role="tab" onclick="RichFaces.switchTab('formulario:p','formulario:abaA','abaA');"></table>
<table id="formulario:abaB_shifted" role="tab" onclick="RichFaces.switchTab('formulario:p','formulario:abaB','abaB');"></table>
<table><tr><td class="rich-tab-header" id="formulario:abaB_lbl">Aba B</td></tr></table>
<table><tr><td role="tabpanel" id="formulario:abaA"><input type="text" name="formulario:campoA" id="formulario:campoA" /></td>
<td role="tabpanel" id="formulario:abaB" style="display: none;"><input type="text" name="formulario:campoB" id="formulario:campoB" /></td></tr></table>
</div>
<input type="hidden" name="javax.faces.ViewState" value="j_id1" />
</form></body></html>"""


class Tela(unittest.TestCase):
    """Leitura de uma tela do PJe-Calc para o visual do Studio (ponte/tela.py), sem PJe-Calc em execução."""

    def setUp(self):
        from ponte.jsf import Page
        from ponte.tela import descrever_pagina
        self.desc = descrever_pagina(Page(None, "http://127.0.0.1:9257/pjecalc/pages/calculo/falta.jsf", TELA_EXEMPLO))

    def itens(self, tipo, itens=None):
        saida = []
        for i in self.desc["itens"] if itens is None else itens:
            if i["t"] == tipo:
                saida.append(i)
            if i["t"] == "grupo":
                saida += self.itens(tipo, i["itens"])
        return saida

    def test_titulo_grupos_e_campos(self):
        self.assertEqual(self.desc["titulo"], "Cálculo > Faltas")
        self.assertEqual([g["titulo"] for g in self.itens("grupo") if not g["aba"]], ["Dados do Cálculo", "Nova Falta"])
        campos = {c["nome"]: c for c in self.itens("campo")}
        self.assertNotIn("formulario:menuBusca", campos)  # menu do PJe-Calc fica fora (o Studio tem o seu)
        data = campos["formulario:inicioInputDate"]
        # campo depois do calendário (com input oculto e script) continua visível; "*" vira obrigatório
        self.assertEqual((data["tipo"], data["rotulo"], data["obrigatorio"]), ("data", "Data Inicial", True))
        marca = campos["formulario:justificada"]
        self.assertEqual((marca["rotulo"], marca["evento"]), ("Justificada", True))  # rótulo logo após, "for" errado
        tipo = campos["formulario:tipo"]
        self.assertEqual(tipo["opcoes"][0], {"valor": "", "rotulo": "Selecione…"})  # sem seleção do Seam
        self.assertEqual(tipo["ajuda"], "Escolha o tipo da falta conforme o documento.")
        self.assertEqual([a["texto"] for a in self.itens("acao")], ["Salvar"])

    def test_tabela_paginas_e_abas(self):
        tb = self.itens("tabela")[0]
        self.assertEqual(tb["colunas"], ["Ação", "Início"])
        self.assertEqual(tb["linhas"][0]["celulas"][0]["acoes"][0]["id"], "formulario:listagem:0:excluir")
        self.assertEqual(tb["linhas"][0]["celulas"][1]["texto"], "10/03/2023")
        pg = self.itens("paginas")[0]
        self.assertEqual([(p["texto"], p["pagina"], p["atual"]) for p in pg["paginas"]], [("1", None, True), ("2", "2", False)])
        # abas trocadas no navegador: as duas aparecem (a inativa vinha com display:none)
        abas = [g for g in self.itens("grupo") if g["aba"]]
        self.assertEqual([(a["titulo"], a["itens"][0]["nome"]) for a in abas], [("Aba A", "formulario:campoA"), ("Aba B", "formulario:campoB")])

    def test_resposta_ajax_atualiza_a_pagina(self):
        from ponte.jsf import Page, outer_html, substituir_elemento
        p = Page(None, "http://x/pjecalc/a.jsf", TELA_EXEMPLO)
        novo = '<table class="rich-table" id="formulario:listagem"><tbody><tr><td>01/01/2024</td></tr></tbody></table>'
        p._merge('<html><body>' + novo + '<meta name="Ajax-Update-Ids" content="formulario:listagem" /></body></html>')
        self.assertEqual(outer_html(p.dom, "formulario:listagem"), novo)
        self.assertIn('id="formulario:pag"', p.dom)  # o restante da página fica
        self.assertEqual(substituir_elemento("<a><b id=\"x\"><b>1</b></b><i/></a>", "x", "<b id=\"x\">2</b>"), '<a><b id="x">2</b><i/></a>')


class _TelaFalsa:
    """Imita SessaoTela: uma tela com Novo → formulário (Devedor com evento, Alíquota) → Salvar."""

    def __init__(self):
        from ponte.jsf import Action
        self.estado, self.chamadas = "lista", []
        self.page = type("P", (), {})()
        self.page.actions = [Action("formulario:incluir", None, "Novo", "A4J.AJAX.Submit", "input")]
        self.page.fields = {}

    def descrever(self):
        if self.estado == "lista":
            return {"itens": [{"t": "acao", "id": "formulario:incluir", "texto": "Novo"}], "mensagens": []}
        return {"mensagens": [], "itens": [{"t": "grupo", "titulo": "Dados", "aba": False, "itens": [
            {"t": "campo", "nome": "formulario:devedorNovo", "rotulo": "Devedor", "tipo": "radio"},
            {"t": "campo", "nome": "formulario:aliquota", "rotulo": "Alíquota (%)", "tipo": "texto"},
            {"t": "acao", "id": "formulario:salvar", "texto": "Salvar"}]}]}

    def alterar(self, valores, evento):
        self.chamadas.append(("alterar", dict(valores), evento))
        return self.descrever()

    def acionar(self, acao, valores):
        self.chamadas.append(("acionar", acao, dict(valores)))
        if acao == "formulario:incluir":
            self.estado = "form"
            self.page.fields = {"formulario:devedorNovo": [None], "formulario:aliquota": [None]}
        return self.descrever()

    def preencher(self, valores):
        self.chamadas.append(("preencher", dict(valores)))


class Padroes(unittest.TestCase):
    PASSOS = [{"tipo": "acao", "id": "formulario:idAntigo", "texto": "Novo"},
              {"tipo": "campo", "nome": "formulario:devedorAntigo", "rotulo": "Devedor", "valor": "RECLAMADO", "evento": True,
               "valorRotulo": "Reclamado"},
              {"tipo": "campo", "nome": "formulario:aliquota", "rotulo": "Alíquota (%)", "valor": "15,00", "evento": False},
              {"tipo": "acao", "id": "formulario:salvar", "texto": "Salvar"}]

    def test_repete_e_acha_por_rotulo_e_texto(self):
        from ponte import padroes
        tela = _TelaFalsa()
        r = padroes.aplicar(tela, self.PASSOS)
        self.assertTrue(r["ok"])
        # ids antigos: o botão é achado pelo texto e o campo pelo rótulo; o evento do Devedor dispara na hora
        self.assertEqual(tela.chamadas, [("acionar", "formulario:incluir", {}),
                                         ("alterar", {"formulario:devedorNovo": "RECLAMADO"}, "formulario:devedorNovo"),
                                         ("acionar", "formulario:salvar", {"formulario:aliquota": "15,00"})])
        self.assertIn("Devedor: Reclamado", [x["texto"] for x in r["registro"]])

    def test_para_antes_do_botao_se_campo_sumiu(self):
        from ponte import padroes
        passos = [p for p in self.PASSOS] + []
        passos.insert(3, {"tipo": "campo", "nome": "formulario:naoExiste", "rotulo": "Campo removido", "valor": "x"})
        tela = _TelaFalsa()
        r = padroes.aplicar(tela, passos)
        self.assertFalse(r["ok"])
        self.assertNotIn("formulario:salvar", [c[1] for c in tela.chamadas if c[0] == "acionar"])  # nada salvo pela metade

    def test_validar_passos_descarta_o_desconhecido(self):
        from ponte import padroes
        v = padroes.validar_passos([{"tipo": "script", "x": 1}, {"tipo": "campo", "nome": "a", "valor": {"obj": 1}},
                                    {"tipo": "acao", "texto": "Salvar"}])
        self.assertEqual(v, [{"tipo": "campo", "nome": "a", "rotulo": "", "valor": "", "evento": False},
                             {"tipo": "acao", "id": "", "texto": "Salvar"}])


class Armazenamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.armaz = armazenamento.Armazenamento(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dentro_de(self):
        base = os.path.join(self.tmp.name, "dados")
        self.assertTrue(armazenamento.dentro_de(base, os.path.join(base, "casos", "x.json")))
        self.assertFalse(armazenamento.dentro_de(base, base + "2"))  # startswith aceitaria
        self.assertFalse(armazenamento.dentro_de(base, os.path.join(base, "..", "fora")))

    def test_caso_ligado_ao_pjecalc(self):
        # mesmo caminho para "Importar .PJC" e "Trazer do PJe-Calc": vínculo nasce gravado na revisão inicial
        hist = [{"nome": "SALARIO", "fgts": 1, "inss": None, "ocorrencias": [{"competencia": "01/2024", "valor": "1.000,00"}]}]
        caso = sincronizar._criar_caso_ligado(
            self.armaz, "teste", "http://127.0.0.1:9257/pjecalc/", 41,
            {"id": "41", "reclamante.nome": "MARIA", "reclamado.nome": "", "local.estado": {"valor": "PA", "rotulo": "PA"}},
            hist, ["SALDO DE SALÁRIO"], ["SALARIO", "ÚLTIMA REMUNERAÇÃO"], titulo_padrao="Cálculo", origem={"tipo": "teste"},
            acao="teste", alteracao={"campo": "x", "de": None, "para": 1})
        self.assertEqual(caso["titulo"], "MARIA")
        self.assertEqual(caso["rascunho"]["dados"], {"reclamante.nome": "MARIA", "local.estado": "PA"})
        self.assertEqual(caso["pjecalc"]["calculoId"], "41")
        self.assertEqual(caso["pjecalc"]["gravadoRevisao"], caso["revisao"])
        h = caso["rascunho"]["historicos"][0]
        self.assertEqual((h["fgts"], h["inss"]), (True, False))
        # o hash guardado é o do histórico do rascunho: enviar sem alterar não reenvia nada
        self.assertEqual(caso["pjecalc"]["historicos"]["SALARIO"], sincronizar._historico_hash(h))
        self.assertEqual(self.armaz.listar()[0]["calculoPjecalc"], "41")

    def test_caso_ligado_so_traz_verbas_expressas(self):
        # verba lançada manualmente no PJe-Calc não entra na lista de expressas (antes o envio falhava em cópias)
        caso = sincronizar._criar_caso_ligado(
            self.armaz, "teste", "http://127.0.0.1:9257/pjecalc/", 7, {}, [], ["HORAS EXTRAS 50%", "ADICIONAL DO ESCRITORIO"], [],
            titulo_padrao="Cálculo", origem={"tipo": "teste"}, acao="teste", alteracao={"campo": "x", "de": None, "para": 1})
        self.assertEqual(caso["rascunho"]["verbas"], ["HORAS EXTRAS 50%"])
        self.assertEqual(caso["pjecalc"]["verbasGravadas"], ["HORAS EXTRAS 50%"])  # a manual nunca é excluída pelo Studio
        self.assertEqual(caso["pjecalc"]["verbasSoNoPjecalc"], ["ADICIONAL DO ESCRITORIO"])

    def test_padroes_e_duplicacao(self):
        p = self.armaz.salvar_padrao({"nome": "Honorários 15%", "menu": "li_calculo_honorarios", "passos": [{"tipo": "acao", "id": "", "texto": "Novo"}]}, "teste")
        self.assertEqual([x["id"] for x in self.armaz.listar_padroes("li_calculo_honorarios")], [p["id"]])
        self.assertEqual(self.armaz.listar_padroes("li_calculo_custas_judiciais"), [])
        rascunho = {**armazenamento.rascunho_vazio(), "outrosItens": {"custas": "feito", "faltas": "nao"}}
        orig = self.armaz.criar({"titulo": "A", "padroesPendentes": [p["id"]], "rascunho": rascunho}, "teste")
        orig["pjecalc"] = {"calculoId": "9", "padroesAplicados": {"pOutro_1": {"ok": True}}}
        self.armaz.salvar_interno(orig, "teste", "teste")
        dup = self.armaz.duplicar(orig["id"], "teste", padroes_extras=["pAuto_1"])
        # a cópia vira um cálculo novo no PJe-Calc: os padrões do original (pendentes e aplicados) e os automáticos voltam
        self.assertEqual(dup["padroesPendentes"], [p["id"], "pOutro_1", "pAuto_1"])
        # e o que foi preenchido nas telas do PJe-Calc precisa ser preenchido de novo na cópia
        self.assertEqual(dup["rascunho"]["outrosItens"], {"custas": "sim", "faltas": "nao"})
        self.armaz.excluir_padrao(p["id"])
        self.assertEqual(self.armaz.listar_padroes(), [])
        with self.assertRaises(ValueError):
            self.armaz.obter_padrao("../config")


class Servidor(unittest.TestCase):
    """API e arquivos estáticos sem o PJe-Calc (porta livre escolhida pelo sistema)."""

    @classmethod
    def setUpClass(cls):
        import servidor
        cls.tmp = tempfile.TemporaryDirectory()
        servidor.ARMAZ = armazenamento.Armazenamento(cls.tmp.name)
        servidor.ARMAZ.salvar_config({"urlPjecalc": "http://127.0.0.1:9/pjecalc/"})  # porta sem serviço
        cls.srv = servidor.Servidor(("127.0.0.1", 0), servidor.Handler)
        servidor.PORTA = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def pedir(self, metodo, caminho, corpo=None, cabecalhos=None):
        import http.client
        import json
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=10)
        cab = {"X-PJeCalc-Studio": "1", **(cabecalhos or {})}
        c.request(metodo, caminho, body=corpo, headers=cab)
        r = c.getresponse()
        dados = r.read()
        c.close()
        try:
            return r.status, json.loads(dados)
        except ValueError:
            return r.status, dados

    def test_json_invalido_e_400(self):
        st, r = self.pedir("POST", "/api/casos", b"{nao e json", {"Content-Type": "application/json"})
        self.assertEqual(st, 400)
        self.assertIn("JSON", r["erro"])

    def test_comparar_sem_parametros_e_400(self):
        self.assertEqual(self.pedir("GET", "/api/comparar")[0], 400)

    def test_situacao_invalida_e_400(self):
        import json
        st, r = self.pedir("POST", "/api/casos", b"{}")
        self.assertEqual(st, 200)
        cid = r["caso"]["id"]
        st, _ = self.pedir("PUT", f"/api/casos/{cid}", json.dumps({"situacao": "xyz"}).encode())
        self.assertEqual(st, 400)
        st, r = self.pedir("GET", f"/api/casos/{cid}/conferir")
        self.assertEqual(st, 200)
        self.assertTrue(r["avisos"])

    def test_estatico_nao_sai_da_pasta_web(self):
        st, corpo = self.pedir("GET", "/%2e%2e/servidor.py")
        self.assertEqual(st, 200)
        self.assertIn(b"<!doctype html>", corpo)  # cai na aplicação (index.html), nunca no código do servidor

    def test_padroes_e_modelos_pela_api(self):
        import json
        st, r = self.pedir("POST", "/api/padroes", json.dumps({"nome": "Custas 2%", "menu": "li_calculo_custas_judiciais", "automatico": True,
                                                               "passos": [{"tipo": "acao", "texto": "Salvar"}]}).encode())
        self.assertEqual(st, 200)
        pid = r["padrao"]["id"]
        self.assertEqual(self.pedir("POST", "/api/padroes", json.dumps({"nome": "x", "menu": "../x", "passos": [{"tipo": "acao", "texto": "a"}]}).encode())[0], 400)
        # cálculo novo recebe o padrão automático; modelo do escritório guarda tipo de trabalho e padrões
        st, r = self.pedir("POST", "/api/casos", json.dumps({"titulo": "Novo"}).encode())
        self.assertEqual(r["caso"]["padroesPendentes"], [pid])
        st, ed = self.pedir("POST", "/api/modelos/editar", json.dumps({"nome": "Execução padrão", "categoria": "Execução"}).encode())
        self.assertEqual(ed["caso"]["edicaoModelo"]["categoria"], "Execução")
        st, m = self.pedir("POST", "/api/modelos", json.dumps({"casoId": ed["caso"]["id"], "nome": "Execução padrão", "categoria": "Execução",
                                                               "padroes": [pid, "pInexistente_1"]}).encode())
        self.assertEqual((st, m["modelo"]["padroes"], m["modelo"]["versao"]), (200, [pid], 1))
        st, m2 = self.pedir("POST", "/api/modelos", json.dumps({"casoId": ed["caso"]["id"], "nome": "Execução padrão", "categoria": "Execução"}).encode())
        self.assertEqual((m2["modelo"]["id"], m2["modelo"]["versao"]), (m["modelo"]["id"], 2))  # mesmo modelo, nova versão
        self.assertEqual(self.pedir("PUT", f"/api/padroes/{pid}", json.dumps({"automatico": False}).encode())[1]["padrao"]["automatico"], False)
        self.assertEqual(self.pedir("DELETE", f"/api/padroes/{pid}")[0], 200)

    def test_estado_sem_pjecalc(self):
        st, r = self.pedir("GET", "/api/estado")
        self.assertEqual(st, 200)
        self.assertFalse(r["motor"]["acessivel"])


@unittest.skipUnless(RELATORIO, "informe um relatório oficial em HTML para testar a extração")
class Relatorio(unittest.TestCase):
    def test_resumo(self):
        from ponte.relatorio import decimal_br, ler_relatorio
        with open(RELATORIO, "rb") as fh:
            r = ler_relatorio(fh.read())
        soma = sum(decimal_br(v["total"]) for v in r["verbas"])
        self.assertEqual(soma, decimal_br(r["total_bruto"]["total"]))  # coerência interna do próprio relatório
        self.assertTrue(r["rodape"]["versao"])
        self.assertTrue(any("quido" in (c["descricao"] or "") for c in r["creditos_descontos"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
