"""PJe-Calc Studio — ponte MCP para o Claude Code (e para configurar o Claude Desktop à mão).

Repassa as mensagens MCP (JSON-RPC por stdio, uma por linha) ao Studio aberto neste computador, em POST /mcp.
O endereço e a chave vêm do arquivo de conexão que o Studio escreve ao iniciar; as ferramentas e as regras ficam
no Studio (ponte/assistente.py). Com o Studio fechado, responde o início da conversa e a lista de ferramentas e,
em cada uso, pede para abrir o Studio. É a mesma lógica da extensão do Claude Desktop (extensao/server/index.js).

Uso:  claude mcp add pjecalc-studio -- py -3 -I <pasta do Studio>\\mcp_studio.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request

VERSOES = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
ARQUIVO = os.environ.get("PJECALC_STUDIO_CONEXAO") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PJeCalcStudio", "conexao.json")
FECHADO = ("O PJe-Calc Studio não está aberto neste computador. Peça ao usuário para abrir o PJe-Calc Studio "
           "(e o PJe-Calc, se for enviar ou calcular) e tente de novo.")
DEMOROU = ("O PJe-Calc Studio não respondeu em 15 minutos. A operação pode ter terminado no Studio: confira com "
           "ler_calculo ou conferir antes de repetir.")
PRAZO = 900  # segundos; calcular e enviar ao PJe-Calc podem levar vários minutos
# Sem proxy: o Studio é sempre local, e um proxy do sistema (variáveis HTTP_PROXY ou configuração do Windows)
# desviaria o 127.0.0.1 e faria o Studio parecer fechado.
ABRIR = urllib.request.build_opener(urllib.request.ProxyHandler({})).open


def ler_conexao() -> dict | None:
    try:
        with open(ARQUIVO, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def local(msg: dict, motivo: str, c: dict | None) -> dict:
    """Resposta local quando o Studio não atende (fechado, ainda não instalado ou chave trocada)."""
    def ok(result):
        return {"jsonrpc": "2.0", "id": msg.get("id"), "result": result}
    metodo = msg.get("method")
    if metodo == "initialize":
        pedida = (msg.get("params") or {}).get("protocolVersion")
        return ok({"protocolVersion": pedida if pedida in VERSOES else VERSOES[0], "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "pjecalc-studio", "title": "PJe-Calc Studio", "version": (c or {}).get("versao") or "0"},
                   "instructions": (c or {}).get("instrucoes") or "Ferramentas do PJe-Calc Studio. " + FECHADO})
    if metodo == "ping":
        return ok({})
    if metodo == "tools/list":
        return ok({"tools": (c or {}).get("ferramentas") or []})
    if metodo == "tools/call":
        return ok({"content": [{"type": "text", "text": motivo}], "isError": True})
    return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32601, "message": motivo}}


def encaminhar(msg) -> dict | None:
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Mensagem JSON-RPC inválida (esperado um objeto)."}}
    try:
        return _encaminhar(msg)
    except Exception as e:  # noqa: BLE001 — a ponte nunca cai: uma falha vira resposta, e o Claude segue conectado
        print(f"pjecalc-studio: {type(e).__name__}: {e}", file=sys.stderr)
        return None if "id" not in msg else local(msg, f"Falha na ponte do PJe-Calc Studio: {type(e).__name__}: {e}", ler_conexao())


def _encaminhar(msg: dict) -> dict | None:
    c = ler_conexao()  # relido a cada mensagem: o Studio pode ter sido aberto ou reiniciado depois do Claude
    notificacao = "id" not in msg
    if not c or not c.get("url") or not c.get("chave"):
        return None if notificacao else local(msg, FECHADO, c)
    req = urllib.request.Request(c["url"], data=json.dumps(msg).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Authorization": "Bearer " + c["chave"]})
    try:
        with ABRIR(req, timeout=PRAZO) as r:
            corpo = r.read()
            if r.status == 202 or notificacao:
                return None
    except urllib.error.HTTPError as e:
        if notificacao:
            return None
        if e.code == 401:
            return local(msg, "O PJe-Calc Studio recusou a chave do assistente. Peça ao usuário para fechar e abrir o Studio de novo.", c)
        return local(msg, f"O PJe-Calc Studio respondeu HTTP {e.code}.", c)
    except (TimeoutError, socket.timeout):
        return None if notificacao else local(msg, DEMOROU, c)
    except urllib.error.URLError as e:
        if notificacao:
            return None
        return local(msg, DEMOROU if isinstance(e.reason, (TimeoutError, socket.timeout)) else FECHADO, c)
    except (ConnectionError, OSError):
        return None if notificacao else local(msg, FECHADO, c)
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return local(msg, "O PJe-Calc Studio deu uma resposta inválida. Peça ao usuário para fechar e abrir o Studio de novo.", c)


def main() -> None:
    saida = sys.stdout.buffer
    for linha in sys.stdin.buffer:
        if not linha.strip():
            continue
        try:
            msg = json.loads(linha.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido."}}
        else:
            if isinstance(msg, list):
                resp = [x for x in (encaminhar(m) for m in msg) if x] or None
            else:
                resp = encaminhar(msg)
        if resp:
            saida.write(json.dumps(resp, ensure_ascii=False).encode("utf-8") + b"\n")
            saida.flush()


if __name__ == "__main__":
    main()
