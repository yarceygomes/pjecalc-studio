"""Teste do início automático do PJe-Calc (ponte/motor.py), sem o PJe-Calc real: instalações falsas numa pasta
temporária e, no lugar do Java, um servidor HTTP que demora a subir, como o Tomcat do PJe-Calc.

Uso:  py -I tests/motor_fluxo.py
"""
import os
import socket
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from ponte import motor  # noqa: E402

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # o Windows pode segurar o log do processo recém-encerrado


def instalacao(pasta, porta=9257, banco_idade=None):
    """Monta uma pasta com a cara do PJe-Calc: bin/pjecalc.jar, tomcat/conf/server.xml e o banco em .dados/."""
    for p in ("bin", os.path.join("tomcat", "conf"), ".dados"):
        os.makedirs(os.path.join(pasta, p), exist_ok=True)
    open(os.path.join(pasta, "bin", "pjecalc.jar"), "wb").close()
    with open(os.path.join(pasta, "tomcat", "conf", "server.xml"), "w", encoding="utf-8") as fh:
        fh.write(f'<Server><Connector port="{porta}" address="127.0.0.1" protocol="HTTP/1.1" />'
                 '<Connector port="9258" address="127.0.0.1" protocol="AJP/1.3" /></Server>')
    if banco_idade is not None:
        banco = os.path.join(pasta, ".dados", "pjecalc.h2.db")
        open(banco, "wb").close()
        t = time.time() - banco_idade
        os.utime(banco, (t, t))
    return pasta


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# 1) reconhecer uma instalação e ler a porta do Tomcat
casa = os.path.join(tmp.name, "casa")
velha = instalacao(os.path.join(casa, "Downloads", "pjecalc-windows64-2.15.0"), banco_idade=86400 * 30)
nova = instalacao(os.path.join(casa, "Downloads", "pjecalc-windows64-2.16.0"), banco_idade=60)
instalacao(os.path.join(casa, "AppData", "PJeCalcStudio", "sandbox", "pjecalc-windows64-2.16.0"), banco_idade=1)  # caixa de testes
assert motor.e_instalacao(nova) and not motor.e_instalacao(os.path.join(casa, "Downloads"))
assert motor.porta_http(nova) == 9257 and motor.porta_http(casa) is None
print("instalação e porta: ok")

# 2) localizar sozinho: a mais usada primeiro, ignorando a caixa de testes do Studio
motor._raizes_de_busca = lambda: [casa, os.path.join(casa, "Downloads")]
achadas = motor.localizar_instalacoes()
assert achadas == [nova, velha], achadas
print("localização automática (a mais usada primeiro, sem a caixa de testes): ok")

# 3) a linha de comando é a do iniciador oficial, sem tela de abertura nem navegador
cmd = motor.comando(nova)
assert "org.apache.catalina.startup.Bootstrap" in cmd and "-Xmx2048m" in cmd and not any("splash" in c for c in cmd)
assert f"-Dcaminho.instalacao={nova}" in cmd
assert motor.comando(nova, "stop")[-1] == "stop"  # desligamento normal do Tomcat (o banco fecha direito)
print("linha de comando: ok")

# 4) recusas claras: sem instalação, porta diferente da configurada, PJe-Calc que não é local
m = motor.Motor(os.path.join(tmp.name, "dados"))
p = porta_livre()
url = f"http://127.0.0.1:{p}/pjecalc/"
assert m.iniciar(url, None)["situacao"] == "sem_instalacao"
assert "porta 9257" in m.iniciar(url, nova)["mensagem"]
assert m.iniciar("http://exemplo.com:9257/pjecalc/", nova)["situacao"] == "erro"
try:
    m.garantir(url, None, timeout=2)
    raise AssertionError("deveria falhar sem instalação")
except motor.ErroMotor as e:
    assert "Não encontrei a instalação" in str(e)
print("recusas (sem instalação, porta errada, não local): ok")

# 5) ciclo completo: inicia, acompanha a subida (2 s de espera, como o Tomcat) e fica pronto
inst = instalacao(os.path.join(tmp.name, "real"), porta=p, banco_idade=10)
servidor_falso = ("import http.server, sys, time; time.sleep(2); "
                  f"http.server.HTTPServer(('127.0.0.1', {p}), http.server.SimpleHTTPRequestHandler).serve_forever()")
motor.comando = lambda pasta: [sys.executable, "-I", "-c", servidor_falso]
inicio = m.iniciar(url, inst)
assert inicio["situacao"] == "iniciando" and inicio["pasta"] == inst, inicio
assert m.iniciar(url, inst)["situacao"] == "iniciando"  # uma segunda chamada não inicia outro processo
pronto = m.esperar(url, timeout=30)
assert pronto["situacao"] == "pronto", pronto
m.garantir(url, inst)  # já pronto: volta na hora
assert os.path.exists(m.log)
print("ciclo iniciar, esperar, pronto: ok")
m.proc.kill()
m.proc.wait()

# 6) processo que fecha logo depois de iniciar (PJe-Calc já aberto por outro atalho): erro explicado
m2 = motor.Motor(os.path.join(tmp.name, "dados2"))
p2 = porta_livre()
inst2 = instalacao(os.path.join(tmp.name, "quebrada"), porta=p2, banco_idade=10)
motor.comando = lambda pasta: [sys.executable, "-I", "-c", "raise SystemExit(1)"]
m2.iniciar(f"http://127.0.0.1:{p2}/pjecalc/", inst2)
e = m2.esperar(f"http://127.0.0.1:{p2}/pjecalc/", timeout=20)
assert e["situacao"] == "erro" and "fechou logo depois de iniciar" in e["mensagem"], e
print("PJe-Calc que fecha ao iniciar: erro explicado")

tmp.cleanup()
print("OK: início automático do PJe-Calc conferido")
