"""Atualização automática do PJe-Calc Studio instalado, pelas Releases do GitHub.

Cada versão publicada no GitHub (tools/publicar-versao.ps1 cria a tag; .github/workflows/release.yml gera o
instalador) traz o instalador PJeCalcStudio-Instalador.exe e o SHA-256 dele. O Studio consulta a última release,
baixa o instalador por HTTPS, confere o SHA-256 e o executa em modo silencioso; o instalador troca os arquivos do
programa (os cálculos ficam fora da pasta do programa) e reabre o Studio.

Só vale para a versão instalada (arquivo instalacao.json, gravado pelo instalador): rodando pelo código-fonte,
o Studio só informa que há versão nova.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

# Repositório do projeto no GitHub ("usuario/repositorio"). tools/publicar-no-github.ps1 troca o marcador.
REPOSITORIO = "yarceygomes/pjecalc-studio"
URL_ATUALIZACOES = os.environ.get("PJECALC_STUDIO_ATUALIZACOES") or f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
INSTALADOR = "PJeCalcStudio-Instalador.exe"
LIMITE_INSTALADOR = 400 * 1024 * 1024


class ErroAtualizacao(Exception):
    pass


def versao_tupla(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("vV").split("."))
    except ValueError:
        return (0,)


def _endereco_permitido(url: str) -> bool:
    """Instalador e consulta só por HTTPS (HTTP só na própria máquina, para testes)."""
    u = urllib.parse.urlparse(url)
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost"))


def _notas(corpo: str) -> list[str]:
    """Texto da release (Markdown) em itens curtos para a tela de atualização."""
    itens = [re.sub(r"^[-*+]\s+|^#+\s*", "", x.strip()).replace("**", "") for x in (corpo or "").splitlines()]
    # a linha "Para instalar..." da página da release é para quem ainda não tem o Studio
    return [x for x in itens if x and not x.startswith("Para instalar")][:12]


class Atualizador:
    def __init__(self, raiz: str, versao_atual: str, url: str | None = None):
        self.raiz = raiz
        self.versao = versao_atual
        self.url = url or URL_ATUALIZACOES
        self.ultima: dict | None = None  # última release conferida
        self.erro: str | None = None
        self.baixado: str | None = None
        self.trava = threading.Lock()

    @property
    def instalado(self) -> bool:
        return os.path.exists(os.path.join(self.raiz, "instalacao.json"))

    def estado(self) -> dict:
        m = self.ultima or {}
        nova = bool(m) and versao_tupla(m.get("versao")) > versao_tupla(self.versao)
        return {"versaoAtual": self.versao, "instalado": self.instalado, "disponivel": nova,
                "versao": m.get("versao") if nova else None, "notas": m.get("notas") if nova else None,
                "tamanho": m.get("tamanho") if nova else None, "publicadaEm": m.get("publicadaEm") if nova else None,
                "erro": self.erro, "podeInstalar": nova and self.instalado and os.name == "nt"}

    def _ler(self, url: str, limite: int, timeout: float) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": f"PJeCalcStudio/{self.versao}", "Accept": "application/vnd.github+json",
                                                   "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(limite)

    def verificar(self, timeout: float = 15) -> dict:
        if "SEU-USUARIO" in self.url:
            self.erro = "Atualizações automáticas ainda não configuradas (repositório do GitHub não definido)."
            raise ErroAtualizacao(self.erro)
        if not _endereco_permitido(self.url):
            raise ErroAtualizacao("Endereço de atualizações inválido.")
        try:
            rel = json.loads(self._ler(self.url, 4 * 1024 * 1024, timeout).decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 404: o repositório ainda não tem nenhuma versão publicada
            self.erro = None if e.code == 404 else f"O GitHub recusou a consulta de atualizações (HTTP {e.code}). O Studio tenta de novo sozinho."
            if e.code == 404:
                self.ultima = None
                return self.estado()
            raise ErroAtualizacao(self.erro) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            self.erro = "Não foi possível verificar atualizações agora (sem internet ou GitHub fora do ar). O Studio tenta de novo sozinho."
            raise ErroAtualizacao(self.erro) from None
        ativos = {a.get("name"): a for a in (rel or {}).get("assets") or [] if isinstance(a, dict)}
        exe = ativos.get(INSTALADOR)
        versao = str((rel or {}).get("tag_name") or "").lstrip("vV")
        if (rel or {}).get("draft") or (rel or {}).get("prerelease") or not exe or versao_tupla(versao) == (0,) \
                or not _endereco_permitido(exe.get("browser_download_url", "")):
            self.erro = "A última versão publicada no GitHub ainda não tem o instalador."
            raise ErroAtualizacao(self.erro)
        sha = str(exe.get("digest") or "").removeprefix("sha256:")
        if len(sha) != 64 and (INSTALADOR + ".sha256") in ativos:  # arquivo .sha256 publicado junto com o instalador
            try:
                sha = self._ler(ativos[INSTALADOR + ".sha256"]["browser_download_url"], 4096, timeout).decode("ascii", "replace").split()[0]
            except (urllib.error.URLError, TimeoutError, OSError, IndexError):
                sha = ""
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            self.erro = "A última versão publicada não traz o SHA-256 do instalador e foi ignorada."
            raise ErroAtualizacao(self.erro)
        self.ultima = {"versao": versao, "url": exe["browser_download_url"], "sha256": sha.lower(), "tamanho": exe.get("size"),
                       "notas": _notas(rel.get("body")), "publicadaEm": rel.get("published_at"), "pagina": rel.get("html_url")}
        self.erro = None
        return self.estado()

    def verificar_em_silencio(self) -> None:
        try:
            self.verificar()
        except ErroAtualizacao:
            pass

    def baixar(self, timeout: float = 600) -> str:
        """Baixa o instalador da versão nova e confere o SHA-256 do manifesto assinado."""
        m = self.ultima
        if not m or versao_tupla(m["versao"]) <= versao_tupla(self.versao):
            raise ErroAtualizacao("Não há versão nova para baixar.")
        destino = os.path.join(tempfile.gettempdir(), f"PJeCalcStudio-{m['versao']}.exe")
        with self.trava:
            soma, total = hashlib.sha256(), 0
            try:
                with urllib.request.urlopen(urllib.request.Request(m["url"], headers={"User-Agent": f"PJeCalcStudio/{self.versao}"}), timeout=timeout) as r, \
                        open(destino + ".parcial", "wb") as fh:
                    while bloco := r.read(1024 * 1024):
                        total += len(bloco)
                        if total > LIMITE_INSTALADOR:
                            raise ErroAtualizacao("Instalador maior que o esperado.")
                        soma.update(bloco)
                        fh.write(bloco)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise ErroAtualizacao(f"Falha ao baixar a atualização ({getattr(e, 'reason', e)}). Tente de novo mais tarde.") from None
            if soma.hexdigest() != m["sha256"].lower():
                os.remove(destino + ".parcial")
                raise ErroAtualizacao("O instalador baixado não confere com o SHA-256 publicado e foi descartado.")
            os.replace(destino + ".parcial", destino)
        self.baixado = destino
        return destino

    def instalar(self, executar=None) -> str:
        """Baixa (se preciso) e inicia o instalador em modo silencioso; quem chama encerra o Studio em seguida."""
        if not self.instalado:
            raise ErroAtualizacao("Atualização automática só na versão instalada. Baixe o instalador novo na página do projeto no GitHub.")
        if os.name != "nt" and executar is None:
            raise ErroAtualizacao("Atualização automática só no Windows.")
        exe = self.baixado if self.baixado and os.path.exists(self.baixado) else self.baixar()
        cmd = [exe, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/ATUALIZACAO"]
        if executar:
            executar(cmd)
        else:
            subprocess.Popen(cmd, close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        return self.ultima["versao"]
