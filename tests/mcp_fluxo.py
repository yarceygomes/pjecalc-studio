"""Teste do assistente Claude (MCP), sem o PJe-Calc e sem tocar nos dados do usuário.

Sobe um Studio próprio (pasta e arquivo de conexão temporários) e conversa com ele como o Claude faria:
pela ponte Python (mcp_studio.py, Claude Code) e pela extensão do Claude Desktop (extensao/server/index.js,
se o Node estiver instalado). Confere também a proteção do endereço /mcp e o pacote .mcpb.

Uso:  py -I tests/mcp_fluxo.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import servidor  # noqa: E402
from ponte import armazenamento  # noqa: E402

tmp = tempfile.TemporaryDirectory()
servidor.ARMAZ = armazenamento.Armazenamento(os.path.join(tmp.name, "dados"))
servidor.ARMAZ.salvar_config({"urlPjecalc": "http://127.0.0.1:9/pjecalc/"})  # porta sem serviço
srv = servidor.Servidor(("127.0.0.1", 0), servidor.Handler)
servidor.PORTA = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
CONEXAO = os.path.join(tmp.name, "conexao.json")
os.environ["PJECALC_STUDIO_CONEXAO"] = CONEXAO
servidor._escrever_conexao()
with open(CONEXAO, encoding="utf-8") as fh:
    conexao = json.load(fh)
URL = conexao["url"]
from ponte import assistente  # noqa: E402
N = len(assistente.lista_ferramentas())

# formato compacto de uma tela (descrição como a de ponte/tela.py)
_t = assistente.resumir_tela({"titulo": "Cálculo > Honorários", "mensagens": [{"severidade": "erro", "texto": "Campo obrigatório"}], "itens": [
    {"t": "abas", "abas": [{"id": "abaA", "titulo": "Dados", "ativa": True}, {"id": "abaB", "titulo": "Ocorrências", "ativa": False}]},
    {"t": "grupo", "titulo": "Honorário", "aba": False, "itens": [
        {"t": "campo", "nome": "formulario:tipo", "tipo": "lista", "rotulo": "Tipo", "valor": "", "evento": True, "obrigatorio": True,
         "opcoes": [{"valor": "", "rotulo": "Selecione…"}, {"valor": "ADVOCATICIOS", "rotulo": "Advocatícios"}]},
        {"t": "acao", "id": "formulario:salvar", "texto": "Salvar", "confirmar": None}]},
    {"t": "tabela", "id": "formulario:lista", "colunas": ["Descrição", ""], "linhas": [{"celulas": [
        {"texto": "Honorários 15%", "campos": [], "acoes": []}, {"texto": "", "campos": [], "acoes": [{"id": "formulario:lista:0:excluir", "texto": "Excluir", "confirmar": "Excluir?"}]}]}]},
    {"t": "paginacao", "id": "formulario:pag", "paginas": [{"texto": "1", "pagina": "1"}, {"texto": "2", "pagina": "2"}]}]})
assert _t["abas"][1] == {"acao": "aba:abaB", "titulo": "Ocorrências", "ativa": False}
assert _t["campos"][0]["opcoes"] == ["=Selecione…", "ADVOCATICIOS=Advocatícios"] and _t["campos"][0]["evento"] and _t["campos"][0]["grupo"] == "Honorário"
assert _t["acoes"][1] == {"id": "formulario:lista:0:excluir", "texto": "Excluir", "linha": 0, "confirmacaoDaTela": "Excluir?"}
assert _t["acoes"][2]["paginas"] == {"1": "pag:formulario:pag:1", "2": "pag:formulario:pag:2"} and _t["tabelas"][0]["linhas"] == [["Honorários 15%", ""]]
print("resumo de tela: ok")


def http(metodo, url, corpo=None, cab=None):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo, headers=cab or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ---------------------------------------------------------------- proteção do endereço /mcp
ini = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
chave = {"Authorization": "Bearer " + conexao["chave"], "Content-Type": "application/json"}
assert http("POST", URL, ini, {"Content-Type": "application/json"})[0] == 401, "sem chave deveria recusar"
assert http("POST", URL, ini, {"Authorization": "Bearer errada", "Content-Type": "application/json"})[0] == 401
assert http("POST", URL, ini, {**chave, "Origin": "https://site-qualquer.com"})[0] == 403, "origem de site deveria recusar"
assert http("GET", URL, None, chave)[0] == 405
st, corpo = http("POST", URL, ini, chave)
assert st == 200 and json.loads(corpo)["result"]["serverInfo"]["name"] == "pjecalc-studio"
assert http("POST", URL, {"jsonrpc": "2.0", "method": "notifications/initialized"}, chave)[0] == 202
st, corpo = http("POST", URL, [1, {**ini, "params": {"protocolVersion": "2025-11-25"}}], chave)  # lote com item inválido
lote = json.loads(corpo)
assert st == 200 and lote[0]["error"]["code"] == -32600 and lote[1]["result"]["protocolVersion"] == "2025-11-25", lote
print("proteção do /mcp: ok")

# ---------------------------------------------------------------- pacote .mcpb e tela
st, pacote = http("GET", URL.replace("/mcp", "/api/claude/extensao.mcpb"))
with zipfile.ZipFile(io.BytesIO(pacote)) as z:
    man = json.loads(z.read("manifest.json"))
    assert sorted(z.namelist()) == ["manifest.json", "server/index.js"], z.namelist()
assert man["manifest_version"] == "0.3" and man["version"] == servidor.VERSAO_APP and len(man["tools"]) == N
assert man["server"]["mcp_config"]["args"] == ["${__dirname}/server/index.js"]
info = json.loads(http("GET", URL.replace("/mcp", "/api/claude"))[1])
assert info["conexaoAtual"] and info["ferramentas"] == N and "mcp_studio.py" in info["comandoClaudeCode"]
print("pacote .mcpb e /api/claude: ok")


# ---------------------------------------------------------------- conversa pelas pontes
class Ponte:
    def __init__(self, cmd):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=os.environ.copy())
        self.n = 0

    def rpc(self, metodo, params=None, notificacao=False):
        msg = {"jsonrpc": "2.0", "method": metodo, "params": params or {}}
        if not notificacao:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write(json.dumps(msg).encode() + b"\n")
        self.p.stdin.flush()
        return None if notificacao else json.loads(self.p.stdout.readline())

    def chamar(self, _ferramenta, **args):
        r = self.rpc("tools/call", {"name": _ferramenta, "arguments": args})["result"]
        texto = r["content"][0]["text"]
        return r["isError"], (texto if r["isError"] else json.loads(texto))

    def ok(self, _ferramenta, **args):
        erro, r = self.chamar(_ferramenta, **args)
        assert not erro, f"{_ferramenta}: {r}"
        return r

    def falha(self, _ferramenta, trecho, **args):
        erro, r = self.chamar(_ferramenta, **args)
        assert erro and trecho in r, f"{_ferramenta} deveria falhar com “{trecho}”: {r}"

    def fechar(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


def fluxo(ponte: Ponte, nome: str):
    r = ponte.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "teste", "version": "1"}})["result"]
    assert r["serverInfo"]["name"] == "pjecalc-studio" and "PJe-Calc" in r["instructions"]
    ponte.rpc("notifications/initialized", notificacao=True)
    assert len(ponte.rpc("tools/list")["result"]["tools"]) == N
    cid = ponte.ok("criar_calculo", titulo=f"TESTE {nome}")["id"]
    ponte.ok("responder_perguntas", id=cid, documentoBase="sentenca", desligamento="sem_justa_causa",
             perguntasVerbas={"rescisao": "sim", "horas_extras": "sim"}, outrosItens={"custas": "sim", "faltas": "nao"})
    ponte.falha("responder_perguntas", "não existe", id=cid, perguntasVerbas={"inventada": "sim"})
    s = ponte.ok("preencher_campos", id=cid, campos={
        "reclamante.nome": "FULANO DE TAL", "reclamante.numeroDocumentoFiscal": "52998224725", "reclamado.nome": "EMPRESA X LTDA",
        "reclamado.numeroDocumentoFiscal": "11222333000181", "local.estado": "pa", "local.municipio": "Belém",
        "processo.numeroCompleto": "0000123-74.2025.5.08.0001", "contrato.dataAdmissao": "2022-02-01", "contrato.dataDemissao": "31/01/2025",
        "contrato.dataAjuizamento": "10/03/2025", "contrato.ultimaRemuneracao": "3800", "contrato.regime": "Tempo Integral", "meta.cliente": "FULANO"})["salvo"]
    assert s["reclamante.numeroDocumentoFiscal"] == "529.982.247-25" and s["contrato.ultimaRemuneracao"] == "3.800,00", s
    ponte.falha("preencher_campos", "dígito verificador deveria ser 74", id=cid, campos={"processo.numeroCompleto": "0000123-75.2025.5.08.0001"})
    ponte.falha("preencher_campos", "CPF", id=cid, campos={"reclamante.numeroDocumentoFiscal": "529.982.247-24"})
    ponte.falha("preencher_campos", "não é uma data válida", id=cid, campos={"contrato.dataDemissao": "31/02/2025"})
    ponte.falha("preencher_campos", "desconhecido", id=cid, campos={"contrato.inventado": "x"})
    ponte.ok("definir_historico", id=cid, nome="salario base", de="02/2022", ate="01/2025", valor="3.500,00")
    v = ponte.ok("definir_verbas", id=cid, adicionar=["saldo de salario", "AVISO PRÉVIO", "horas extras 50%"])["verbas"]
    assert v == ["SALDO DE SALÁRIO", "AVISO PRÉVIO", "HORAS EXTRAS 50%"], v
    ponte.falha("definir_verbas", "não está no catálogo", id=cid, adicionar=["VERBA QUE NAO EXISTE"])
    c = ponte.ok("configurar_verba", id=cid, verba="horas extras 50%", base="HISTORICO_SALARIAL", historicos=["SALARIO BASE"], quantidade_por_mes=10,
                 trecho="condeno ao pagamento de 10 horas extras mensais", ocorrencias=[{"competencia": "12/2024", "quantidade": "20"}])["config"]
    assert c["alteracoes"] == {"tipoDaBaseTabelada": "HISTORICO_SALARIAL", "valorInformadoDaQuantidade": "10,0000"} and c["ocorrencias"] == 1, c
    ponte.falha("configurar_verba", "não está entre as verbas", id=cid, verba="13º SALÁRIO", base="MAIOR_REMUNERACAO")
    a = ponte.ok("definir_correcao", id=cid, valores={"indiceTrabalhista": "IPCA-E", "juros": "SELIC Simples"}, data_liquidacao="30/09/2026")
    assert a["atualizacao"]["valores"] == {"indiceTrabalhista": "IPCAE", "juros": "SELIC Simples"}, a
    ponte.ok("definir_fgts", id=cid, valores={"multa": True})
    # telas do PJe-Calc (sem PJe-Calc aqui: só as validações; a operação real está em mcp_telas_pjecalc.py)
    assert len(ponte.ok("telas_pjecalc")["telas"]) == len(assistente.TELAS)
    ponte.falha("abrir_tela", "não existe", tela="inventada")
    ponte.falha("abrir_tela", "informe o id do cálculo", tela="ferias")
    ponte.falha("abrir_tela", "ainda não está no PJe-Calc", tela="ferias", id=cid)
    conf = ponte.ok("conferir", id=cid)
    assert conf["podeEnviar"] and any("outros itens" in x["texto"] for x in conf["alertas"]), conf
    lido = ponte.ok("ler_calculo", id=cid)
    assert lido["documentoBase"] == "sentenca" and lido["dados"]["processo.vara"] == "0001" and lido["historicos"][0]["meses"] == 36, lido
    assert any(x["id"] == cid for x in ponte.ok("listar_calculos", busca=f"TESTE {nome}"))
    ponte.falha("ler_resultado", "ainda não foi calculado", id=cid)
    # conferência dos argumentos pelo esquema: mensagens claras em vez de falha interna ou dado ignorado
    ponte.falha("ler_calculo", "falta id", completo=True)
    ponte.falha("ler_calculo", "id: esperado texto", id=123)
    ponte.falha("criar_calculo", "parâmetro desconhecido", titulo="X", inventado=1)
    ponte.falha("definir_correcao", "falta aPartirDe", id=cid, juros_combinados=[{"tabela": "SELIC Simples"}])
    ponte.falha("configurar_verba", "ocorrencias[0]: falta competencia", id=cid, verba="horas extras 50%", ocorrencias=[{"quantidade": 1}])
    ponte.falha("responder_perguntas", "não é válido", id=cid, desligamento="demitido")
    assert isinstance(ponte.ok("ler_calculo", id=cid, completo="true")["historicos"][0]["ocorrencias"], list)  # "true" vira true
    ponte.ok("responder_perguntas", id=cid, outrosItens={"faltas": "não"})  # "não" vira "nao"
    c = ponte.ok("configurar_verba", id=cid, verba="horas extras 50%", historicos=["Salário Base"])["config"]
    assert c["bases"] == ["SALARIO BASE"], c  # sem acento e sem caixa, gravado com a grafia do histórico
    ponte.falha("ler_tela", "Token de tela inválido", token="a/b")
    ponte.falha("ler_tela", "não está mais aberta", token="token_inexistente")
    print(f"fluxo completo pela {nome}: ok")


p = Ponte([sys.executable, "-I", os.path.join(RAIZ, "mcp_studio.py")])
fluxo(p, "ponte Python")
p.fechar()

node = shutil.which("node")
if node:
    p = Ponte([node, os.path.join(RAIZ, "extensao", "server", "index.js")])
    fluxo(p, "extensão do Claude Desktop (Node)")
    p.fechar()
else:
    print("Node não encontrado: extensão do Claude Desktop não testada")

# ---------------------------------------------------------------- Studio fechado e chave trocada
srv.shutdown()
srv.server_close()
for cmd in ([sys.executable, "-I", os.path.join(RAIZ, "mcp_studio.py")],) + (([node, os.path.join(RAIZ, "extensao", "server", "index.js")],) if node else ()):
    p = Ponte(cmd)
    assert p.rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]["serverInfo"]["name"] == "pjecalc-studio"
    assert len(p.rpc("tools/list")["result"]["tools"]) == N, "com o Studio fechado, a lista vem do arquivo de conexão"
    p.falha("listar_calculos", "não está aberto")
    p.fechar()
os.remove(CONEXAO)
p = Ponte([sys.executable, "-I", os.path.join(RAIZ, "mcp_studio.py")])
assert p.rpc("initialize", {})["result"]["serverInfo"]["name"] == "pjecalc-studio"
p.falha("listar_calculos", "não está aberto")
p.fechar()
print("Studio fechado / sem conexão: ok")
tmp.cleanup()
print("OK: assistente Claude conferido")
