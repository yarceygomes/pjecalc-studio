"""Teste da atualização automática pelas Releases do GitHub: um "GitHub" local que responde como a API
(releases/latest) e serve um instalador falso. Não acessa a internet nem executa nenhum instalador de verdade.

Uso:  py -I tests/atualizacao_fluxo.py
"""
import functools
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from ponte.atualizacao import INSTALADOR, Atualizador, ErroAtualizacao, versao_tupla  # noqa: E402

tmp = tempfile.TemporaryDirectory()
site = os.path.join(tmp.name, "site")
os.makedirs(site)

# instalador falso e "GitHub" local
instalador = os.path.join(site, INSTALADOR)
with open(instalador, "wb") as fh:
    fh.write(os.urandom(300_000))
with open(instalador, "rb") as fh:
    SOMA = hashlib.sha256(fh.read()).hexdigest()
with open(instalador + ".sha256", "w", encoding="ascii") as fh:
    fh.write(f"{SOMA}  {INSTALADOR}\n")
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=site))
srv.RequestHandlerClass.log_message = lambda *a: None
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}"


def publicar(tag="v0.2.0", nome="latest.json", digest=True, sha_arquivo=True, url=None, extra=None):
    """Grava uma resposta no formato de GET /repos/{dono}/{repo}/releases/latest e devolve o endereço dela."""
    ativos = [{"name": INSTALADOR, "size": os.path.getsize(instalador), "browser_download_url": url or f"{BASE}/{INSTALADOR}",
               **({"digest": "sha256:" + (digest if isinstance(digest, str) else SOMA)} if digest else {})}]
    if sha_arquivo:
        ativos.append({"name": INSTALADOR + ".sha256", "size": 80, "browser_download_url": f"{BASE}/{INSTALADOR}.sha256"})
    rel = {"tag_name": tag, "draft": False, "prerelease": False, "published_at": "2026-10-29T00:00:00Z",
           "html_url": "https://github.com/exemplo/pjecalc-studio/releases/tag/" + tag,
           "body": "## Novidades\n- Novidade A\n- Correção B\n", "assets": ativos, **(extra or {})}
    with open(os.path.join(site, nome), "w", encoding="utf-8") as fh:
        json.dump(rel, fh)
    return f"{BASE}/{nome}"


def falha(fn, trecho):
    try:
        fn()
    except ErroAtualizacao as e:
        assert trecho in str(e), f"esperava “{trecho}”, veio “{e}”"
        return
    raise AssertionError(f"deveria falhar com “{trecho}”")


raiz_fonte, raiz_instalada = os.path.join(tmp.name, "fonte"), os.path.join(tmp.name, "instalado")
os.makedirs(raiz_fonte)
os.makedirs(raiz_instalada)
with open(os.path.join(raiz_instalada, "instalacao.json"), "w") as fh:
    json.dump({"canal": "estavel", "versao": "0.1.0"}, fh)

assert versao_tupla("0.10.0") > versao_tupla("0.9.9") > versao_tupla("0.9") and versao_tupla("v1.2.0") == (1, 2, 0)

# 1) versão nova: detectada, com as notas da release
e = Atualizador(raiz_instalada, "0.1.0", url=publicar()).verificar()
assert e["disponivel"] and e["versao"] == "0.2.0" and e["notas"] == ["Novidades", "Novidade A", "Correção B"] and e["podeInstalar"] == (os.name == "nt"), e
print("versão nova detectada: ok")

# 2) já atualizado / versão mais antiga publicada: nada a fazer
assert not Atualizador(raiz_instalada, "0.2.0", url=publicar()).verificar()["disponivel"]
assert not Atualizador(raiz_instalada, "0.3.0", url=publicar()).verificar()["disponivel"]
print("sem versão nova: ok")

# 3) SHA-256 pelo arquivo .sha256 quando a API não traz o "digest"
at = Atualizador(raiz_instalada, "0.1.0", url=publicar(digest=False, nome="sem-digest.json"))
at.verificar()
assert at.ultima["sha256"] == SOMA
print("SHA-256 pelo arquivo .sha256: ok")

# 4) releases incompletas ou fora do padrão: ignoradas
falha(lambda: Atualizador(raiz_instalada, "0.1.0", url=publicar(digest=False, sha_arquivo=False, nome="sem-sha.json")).verificar(), "SHA-256")
falha(lambda: Atualizador(raiz_instalada, "0.1.0", url=publicar(nome="rascunho.json", extra={"draft": True})).verificar(), "não tem o instalador")
falha(lambda: Atualizador(raiz_instalada, "0.1.0", url=publicar(nome="http.json", url="http://site.com/x.exe")).verificar(), "não tem o instalador")
falha(lambda: Atualizador(raiz_instalada, "0.1.0", url="http://site-externo.com/latest.json").verificar(), "inválido")
falha(lambda: Atualizador(raiz_instalada, "0.1.0", url="https://api.github.com/repos/SEU-USUARIO/repositorio/releases/latest").verificar(), "não configuradas")  # marcador que publicar-no-github.ps1 não troca
print("release incompleta, rascunho, sem HTTPS ou repositório não definido: recusado")

# 5) repositório ainda sem nenhuma versão publicada (404): sem erro, sem versão nova
vazio = Atualizador(raiz_instalada, "0.1.0", url=f"{BASE}/nao-existe.json")
assert not vazio.verificar()["disponivel"] and vazio.estado()["erro"] is None
print("repositório sem versões: ok")

# 6) download corrompido (SHA-256 não confere): descartado
ruim = Atualizador(raiz_instalada, "0.1.0", url=publicar(digest="0" * 64, nome="sha-errado.json"))
ruim.verificar()
falha(ruim.baixar, "não confere")
assert not os.path.exists(os.path.join(tempfile.gettempdir(), "PJeCalcStudio-0.2.0.exe.parcial"))
print("download corrompido: descartado")

# 7) instalação: só na versão instalada; comando silencioso que reabre o Studio
fonte = Atualizador(raiz_fonte, "0.1.0", url=publicar())
fonte.verificar()
assert not fonte.estado()["podeInstalar"]
falha(lambda: fonte.instalar(executar=lambda c: None), "só na versão instalada")
comandos = []
at = Atualizador(raiz_instalada, "0.1.0", url=publicar())
at.verificar()
assert at.instalar(executar=comandos.append) == "0.2.0"
exe = comandos[0][0]
with open(exe, "rb") as a, open(instalador, "rb") as b:
    assert a.read() == b.read()
assert comandos[0][1:] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/ATUALIZACAO"]
os.remove(exe)
print("instalação silenciosa: ok")

# 8) sem internet: em silêncio, sem quebrar nada
offline = Atualizador(raiz_instalada, "0.1.0", url="http://127.0.0.1:9/latest.json")
offline.verificar_em_silencio()
assert not offline.estado()["disponivel"] and "Não foi possível verificar" in offline.estado()["erro"]
print("sem internet: ok")

srv.shutdown()
srv.server_close()
tmp.cleanup()
print("OK: atualização automática conferida")
