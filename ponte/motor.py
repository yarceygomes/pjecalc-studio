"""Início automático do PJe-Calc Cidadão instalado no computador.

O Studio inicia o PJe-Calc sozinho quando precisa dele (ao abrir e antes de enviar, calcular ou abrir uma tela
oficial), sem a tela de abertura e sem abrir o navegador: sobe o Tomcat interno da instalação com os mesmos
parâmetros de JVM do iniciarPjeCalc.bat oficial (tools/iniciar-instancia-teste.ps1 usa a mesma linha). O PJe-Calc
continua sendo o oficial, com o banco e as tabelas da instalação; nada dele é alterado.

A pasta de instalação vem das Configurações ou é localizada sozinha (a que tem bin/pjecalc.jar e tomcat/, nas
pastas onde o PJe-Calc costuma ser extraído). O processo do PJe-Calc continua rodando se o Studio fechar.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MARCADORES = (("bin", "pjecalc.jar"), ("tomcat", "conf", "server.xml"))
# mesmos parâmetros de JVM do iniciarPjeCalc.bat oficial (2.16.0)
PARAMETROS_JVM = ["-Duser.timezone=GMT-3", "-Dfile.encoding=ISO-8859-1",
                  "-Dseguranca.pjecalc.tokenServicos=pW4jZ4g9VM5MCy6FnB5pEfQe",
                  "-Dseguranca.pjekz.servico.contexto=https://pje.trtXX.jus.br/pje-seguranca",
                  "-Xms1024m", "-Xmx2048m", "-XX:MaxPermSize=512m"]
ESPERA_PADRAO = 240  # segundos; a primeira subida do PJe-Calc costuma levar de 30 s a 2 min


def e_instalacao(pasta: str) -> bool:
    return bool(pasta) and all(os.path.exists(os.path.join(pasta, *m)) for m in MARCADORES)


def _raizes_de_busca() -> list[str]:
    casa = os.path.expanduser("~")
    raizes = [casa, os.path.join(casa, "Downloads"), os.path.join(casa, "Desktop"), os.path.join(casa, "Documents"),
              os.path.join(casa, "OneDrive", "Desktop"), os.path.join(casa, "OneDrive", "Documentos"),
              os.path.join(casa, "OneDrive", "Documents"), os.path.join(casa, "Documentos")]
    for var in ("SystemDrive", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        v = os.environ.get(var)
        if v:
            raizes.append(v + ("\\" if v.endswith(":") else ""))
    if os.environ.get("LOCALAPPDATA"):
        raizes.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs"))
    vistos, saida = set(), []
    for r in raizes:
        k = os.path.normcase(os.path.abspath(r))
        if k not in vistos and os.path.isdir(r):
            vistos.add(k)
            saida.append(r)
    return saida


def localizar_instalacoes(profundidade: int = 2) -> list[str]:
    """Pastas do PJe-Calc encontradas, a mais usada primeiro (banco alterado por último). Ignora a caixa de testes do Studio."""
    achadas = {}

    def visitar(pasta: str, nivel: int):
        if e_instalacao(pasta):
            achadas[os.path.normcase(os.path.abspath(pasta))] = pasta
            return
        if nivel >= profundidade:
            return
        try:
            filhas = [e.path for e in os.scandir(pasta) if e.is_dir(follow_symlinks=False)]
        except OSError:
            return
        for f in filhas:
            nome = os.path.basename(f).lower()
            if nome.startswith((".", "$")) or nome in ("windows", "appdata", "node_modules", "python") or "pjecalcstudio" in nome:
                continue
            visitar(f, nivel + 1)

    for r in _raizes_de_busca():
        visitar(r, 0)

    def uso(p):
        banco = os.path.join(p, ".dados", "pjecalc.h2.db")
        return os.path.getmtime(banco) if os.path.exists(banco) else 0
    return sorted(achadas.values(), key=uso, reverse=True)


def porta_http(pasta: str) -> int | None:
    """Porta HTTP configurada no Tomcat da instalação (9257 no PJe-Calc Cidadão)."""
    try:
        with open(os.path.join(pasta, "tomcat", "conf", "server.xml"), encoding="utf-8", errors="replace") as fh:
            xml = fh.read()
    except OSError:
        return None
    m = re.search(r'<Connector\s+port="(\d+)"[^>]*protocol="HTTP/1\.1"', xml)
    return int(m.group(1)) if m else None


def comando(pasta: str, acao: str = "start") -> list[str]:
    """Linha do Tomcat do PJe-Calc; acao="stop" pede o desligamento normal (o banco fecha direito)."""
    jre = os.path.join(pasta, "bin", "jre", "bin")
    java = os.path.join(jre, "javaw.exe") if os.path.exists(os.path.join(jre, "javaw.exe")) else os.path.join(jre, "java.exe")
    tomcat = os.path.join(pasta, "tomcat")
    return [java, *PARAMETROS_JVM, f"-Dcaminho.instalacao={pasta}", f"-Dcatalina.home={tomcat}", f"-Dcatalina.base={tomcat}",
            "-cp", os.path.join(pasta, "bin", "lib", "*"), "org.apache.catalina.startup.Bootstrap", acao]


def responde(url: str, timeout: float = 3) -> bool:
    try:
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
        with abrir(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


class ErroMotor(Exception):
    pass


class Motor:
    """Um PJe-Calc por Studio: inicia uma vez, acompanha a subida e informa a situação para a interface."""

    def __init__(self, pasta_log: str):
        self.log = os.path.join(pasta_log, "pjecalc-inicio.log")
        self.trava = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.situacao = "parado"  # parado | iniciando | pronto | erro | sem_instalacao
        self.mensagem = ""
        self.pasta = None
        self.desde = None

    def estado(self) -> dict:
        return {"situacao": self.situacao, "mensagem": self.mensagem, "pasta": self.pasta,
                "segundos": round(time.monotonic() - self.desde) if self.desde and self.situacao == "iniciando" else None}

    def _local(self, url: str) -> bool:
        return urllib.parse.urlparse(url).hostname in ("127.0.0.1", "localhost")

    def iniciar(self, url: str, pasta: str | None) -> dict:
        """Inicia o PJe-Calc se ele não estiver respondendo; não espera a subida terminar."""
        with self.trava:
            if responde(url):
                self.situacao, self.mensagem = "pronto", ""
                return self.estado()
            if self.proc and self.proc.poll() is None:
                return self.estado()  # já está subindo
            if not self._local(url):
                self.situacao, self.mensagem = "erro", "O início automático só funciona com um PJe-Calc neste computador."
                return self.estado()
            if not pasta or not e_instalacao(pasta):
                self.situacao = "sem_instalacao"
                self.mensagem = ("Não encontrei a instalação do PJe-Calc neste computador. Informe a pasta em Configurações "
                                 "(a que tem o iniciarPjeCalc.bat) ou abra o PJe-Calc pelo atalho oficial.")
                return self.estado()
            porta = porta_http(pasta)
            porta_url = urllib.parse.urlparse(url).port or 80
            if porta and porta != porta_url:
                self.situacao = "erro"
                self.mensagem = (f"A instalação em {pasta} usa a porta {porta}, mas o Studio está configurado para a porta "
                                 f"{porta_url}. Ajuste o endereço do PJe-Calc em Configurações.")
                return self.estado()
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as fh:
                fh.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} iniciando o PJe-Calc em {pasta}\n")
            saida = open(self.log, "ab")  # noqa: SIM115 — fica com o processo do PJe-Calc
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:
                self.proc = subprocess.Popen(comando(pasta), cwd=pasta, stdin=subprocess.DEVNULL, stdout=saida, stderr=saida,
                                             creationflags=flags, close_fds=True)
            except OSError as e:
                self.situacao, self.mensagem = "erro", f"Não foi possível iniciar o PJe-Calc ({e})."
                return self.estado()
            finally:
                saida.close()
            self.situacao, self.mensagem, self.pasta, self.desde = "iniciando", "Iniciando o PJe-Calc…", pasta, time.monotonic()
            return self.estado()

    def esperar(self, url: str, timeout: float = ESPERA_PADRAO) -> dict:
        """Espera o PJe-Calc responder; atualiza a situação (pronto ou erro)."""
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            if responde(url):
                self.situacao, self.mensagem = "pronto", ""
                return self.estado()
            if self.proc is not None and self.proc.poll() is not None:
                self.situacao = "erro"
                self.mensagem = ("O PJe-Calc fechou logo depois de iniciar. Ele pode já estar aberto por outro atalho, ou a "
                                 f"instalação pode estar com problema (detalhes em {self.log}).")
                return self.estado()
            time.sleep(1.5)
        self.situacao = "erro"
        self.mensagem = f"O PJe-Calc não respondeu depois de {int(timeout)} s. Tente de novo ou abra pelo atalho oficial."
        return self.estado()

    def encerrar(self, url: str, pasta: str | None, timeout: float = 60) -> dict:
        """Desliga o PJe-Calc pelo comando oficial do Tomcat (stop), como o "Sair" do ícone da bandeja."""
        if not responde(url):
            self.situacao, self.mensagem = "parado", ""
            return self.estado()
        if not pasta or not e_instalacao(pasta):
            raise ErroMotor("Não encontrei a pasta de instalação do PJe-Calc para encerrá-lo. Feche-o pelo ícone da bandeja.")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(comando(pasta, "stop"), cwd=pasta, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=flags, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ErroMotor(f"Não foi possível encerrar o PJe-Calc ({e}).") from None
        fim = time.monotonic() + timeout
        while time.monotonic() < fim and responde(url):
            time.sleep(1)
        if responde(url):
            raise ErroMotor("O PJe-Calc não fechou. Ele pode ter sido aberto pelo atalho oficial: feche-o pelo ícone da bandeja.")
        self.situacao, self.mensagem, self.proc = "parado", "", None
        return self.estado()

    def garantir(self, url: str, pasta: str | None, timeout: float = ESPERA_PADRAO) -> None:
        """Deixa o PJe-Calc pronto para uso, iniciando e esperando se preciso; levanta ErroMotor se não der."""
        if responde(url):
            self.situacao, self.mensagem = "pronto", ""
            return
        e = self.iniciar(url, pasta)
        if e["situacao"] == "iniciando":
            e = self.esperar(url, timeout)
        if e["situacao"] != "pronto":
            raise ErroMotor(e["mensagem"] or "O PJe-Calc não está disponível.")
