"""Armazenamento local dos cálculos da nova interface (rascunhos, revisões, execuções, auditoria).

Tudo fica em arquivos JSON numa pasta local (padrão: ./dados). Nada é enviado para fora da máquina.

  dados/
    casos/<id>/caso.json            estado atual (rascunho + vínculo com o PJe-Calc + execuções)
    casos/<id>/revisoes/000012.json cópia do rascunho em cada revisão
    casos/<id>/auditoria.jsonl      quem alterou, quando e o quê
    casos/<id>/execucoes/<eid>/     relatorio.html, calculo.pjc, resultado.json (gerados pelo PJe-Calc)
    modelos/<id>/v0001.json         modelos do escritório, com histórico de versões
    padroes/<id>.json               padrões do escritório para as funções do PJe-Calc (ver ponte/padroes.py)
    config.json                     preferências (URL do PJe-Calc, nome do usuário, etc.)
    backups/                        cópias de segurança (.zip + manifesto de hashes)
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import time
import zipfile
from datetime import datetime

SITUACOES = ("rascunho", "em_conferencia", "calculado", "concluido")
_lock = threading.RLock()


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def dentro_de(pasta: str, caminho: str) -> bool:
    """caminho fica dentro de pasta? (startswith aceitaria "dados2" como se estivesse dentro de "dados")"""
    pasta, caminho = os.path.abspath(pasta), os.path.abspath(caminho)
    try:
        return os.path.commonpath([pasta, caminho]) == pasta
    except ValueError:  # unidades diferentes no Windows
        return False


def _repetir(fn, tentativas: int = 20):
    """No Windows, antivírus/indexador podem segurar um arquivo por instantes (PermissionError)."""
    for i in range(tentativas):
        try:
            return fn()
        except PermissionError:
            if i == tentativas - 1:
                raise
            time.sleep(0.05 * (i + 1))


def _escrever_json(caminho: str, obj) -> None:
    with _lock:
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
        _repetir(lambda: os.replace(tmp, caminho))  # gravação atômica: nunca deixa um caso.json pela metade


def _ler_json(caminho: str, padrao=None):
    with _lock:  # leituras e escritas serializadas: os.replace falha se o arquivo estiver aberto
        if not os.path.exists(caminho):
            return padrao

        def ler():
            with open(caminho, encoding="utf-8") as fh:
                return json.load(fh)
        return _repetir(ler)


def achatar(obj, prefixo="") -> dict:
    """{'a': {'b': 1}} -> {'a.b': 1}; listas viram 'a[0].b'."""
    saida = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            saida.update(achatar(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            saida.update(achatar(v, f"{prefixo}[{i}]"))
        if not obj:
            saida[prefixo] = []
    else:
        saida[prefixo] = obj
    return saida


def diferencas(a: dict, b: dict) -> list[dict]:
    fa, fb = achatar(a or {}), achatar(b or {})
    out = []
    for k in sorted(set(fa) | set(fb)):
        if fa.get(k) != fb.get(k):
            out.append({"campo": k, "de": fa.get(k), "para": fb.get(k)})
    return out


def rascunho_vazio() -> dict:
    return {
        "dados": {},
        "historicos": [],
        "verbas": [],
        "verbasConfig": {},
        "verbasManuais": [],
        "fgts": {},
        "atualizacao": {"valores": {}, "jurosCombinados": None, "indicesCombinados": None},
        "liquidacao": {"data": "", "indicesAcumulados": ""},
        "decisoes": [],
        "outrosItens": {},
        "perguntasVerbas": {},
        "documentoBase": "",
        "desligamento": "",
    }


# Campos com dados pessoais do caso: removidos ao transformar um cálculo em modelo
CAMPOS_PESSOAIS = ("processo.", "reclamante.", "reclamado.", "observacoes.")


def sem_dados_pessoais(rascunho: dict) -> dict:
    r = copy.deepcopy(rascunho)
    r["dados"] = {k: v for k, v in r.get("dados", {}).items() if not k.startswith(CAMPOS_PESSOAIS)}
    for d in r.get("decisoes", []):
        d["trecho"] = ""  # trechos de decisões citam o caso concreto
    # respostas sobre outros itens do cálculo valem para um caso só; cada caso novo responde de novo
    r["outrosItens"] = {}
    r["perguntasVerbas"] = {}
    r["desligamento"] = ""
    return r


class Armazenamento:
    def __init__(self, pasta: str):
        self.pasta = os.path.abspath(pasta)
        for sub in ("casos", "modelos", "padroes", "backups"):
            os.makedirs(os.path.join(self.pasta, sub), exist_ok=True)

    # ------------------------------------------------------------------ configuração
    def config(self) -> dict:
        padrao = {"urlPjecalc": "http://127.0.0.1:9257/pjecalc/", "usuario": "", "pastaInstalacao": "",
                  "tema": "auto", "fonte": 100, "modo": "guiado", "logoEscritorio": "", "nomeEscritorio": ""}
        cfg = _ler_json(os.path.join(self.pasta, "config.json"), {})
        return {**padrao, **(cfg or {})}

    def salvar_config(self, novo: dict) -> dict:
        with _lock:
            cfg = {**self.config(), **novo}
            _escrever_json(os.path.join(self.pasta, "config.json"), cfg)
            return cfg

    # ------------------------------------------------------------------ casos
    def _dir(self, cid: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", cid or ""):
            raise ValueError("identificador inválido")
        return os.path.join(self.pasta, "casos", cid)

    def listar(self) -> list[dict]:
        saida = []
        base = os.path.join(self.pasta, "casos")
        for cid in os.listdir(base):
            c = _ler_json(os.path.join(base, cid, "caso.json"))
            if not c:
                continue
            ult = c["execucoes"][-1] if c.get("execucoes") else None
            saida.append({
                "id": c["id"], "titulo": c.get("titulo"), "cliente": c.get("cliente"),
                "parteContraria": c.get("parteContraria"), "processo": c.get("processo"),
                "responsavel": c.get("responsavel"), "situacao": c.get("situacao"),
                "etiquetas": c.get("etiquetas", []), "favorito": c.get("favorito", False),
                "atualizadoEm": c.get("atualizadoEm"), "etapaAtual": c.get("etapaAtual"),
                "revisao": c.get("revisao"), "cenarioDe": c.get("cenarioDe"),
                "modeloEmEdicao": (c.get("edicaoModelo") or {}).get("nome"),
                "calculoPjecalc": (c.get("pjecalc") or {}).get("calculoId"),
                "gravadoRevisao": (c.get("pjecalc") or {}).get("gravadoRevisao"),
                # pendências do tipo "Erro" apuradas pelo PJe-Calc na última gravação (impedem calcular)
                "pendenciasErro": sum(1 for m in (c.get("pjecalc") or {}).get("pendencias") or [] if m.get("severidade") == "erro"),
                "ultimaExecucao": {"em": ult["em"], "revisaoEntradas": ult["revisaoEntradas"],
                                   "liquido": ult.get("liquido")} if ult else None,
            })
        saida.sort(key=lambda x: x.get("atualizadoEm") or "", reverse=True)
        return saida

    def obter(self, cid: str) -> dict:
        c = _ler_json(os.path.join(self._dir(cid), "caso.json"))
        if c is None:
            raise KeyError(cid)
        return c

    def criar(self, dados: dict, autor: str) -> dict:
        with _lock:
            cid = datetime.now().strftime("c%Y%m%d%H%M%S") + "_" + secrets.token_hex(2)
            os.makedirs(os.path.join(self._dir(cid), "revisoes"), exist_ok=True)
            caso = {
                "id": cid, "titulo": dados.get("titulo") or "Novo cálculo", "cliente": dados.get("cliente", ""),
                "parteContraria": dados.get("parteContraria", ""), "processo": dados.get("processo", ""),
                "responsavel": dados.get("responsavel") or autor, "situacao": "rascunho",
                "etiquetas": dados.get("etiquetas", []), "favorito": False, "observacoes": "",
                "origem": dados.get("origem") or {"tipo": "novo"}, "cenarioDe": dados.get("cenarioDe"),
                "revisao": 1, "etapaAtual": "identificacao",
                "rascunho": dados.get("rascunho") or rascunho_vazio(),
                "pjecalc": dados.get("pjecalc") or {}, "execucoes": [],
                "padroesPendentes": list(dados.get("padroesPendentes") or []),  # aplicados no primeiro envio
                "edicaoModelo": dados.get("edicaoModelo"),  # cálculo usado para editar um modelo do escritório
                "criadoEm": agora(), "atualizadoEm": agora(), "autor": autor,
            }
            self._persistir(caso, autor, "criacao", [])
            return caso

    def _persistir(self, caso: dict, autor: str, acao: str, alteracoes: list[dict]) -> None:
        d = self._dir(caso["id"])
        os.makedirs(os.path.join(d, "revisoes"), exist_ok=True)
        _escrever_json(os.path.join(d, "caso.json"), caso)
        _escrever_json(os.path.join(d, "revisoes", f"{caso['revisao']:06d}.json"), caso["rascunho"])
        with open(os.path.join(d, "auditoria.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"em": agora(), "autor": autor, "acao": acao, "revisao": caso["revisao"],
                                 "alteracoes": alteracoes}, ensure_ascii=False) + "\n")

    def atualizar(self, cid: str, mudancas: dict, autor: str, revisao_base: int | None = None) -> dict:
        """Aplica mudanças do usuário. Mudança no rascunho cria nova revisão (e torna o resultado desatualizado)."""
        with _lock:
            caso = self.obter(cid)
            if revisao_base is not None and revisao_base != caso["revisao"]:
                raise ConflitoRevisao(caso["revisao"])
            alteracoes = []
            meta = ("titulo", "cliente", "parteContraria", "processo", "responsavel", "situacao", "etiquetas",
                    "favorito", "observacoes", "etapaAtual")
            for k in meta:
                if k in mudancas and mudancas[k] != caso.get(k):
                    if k == "situacao" and mudancas[k] not in SITUACOES:
                        raise ValueError("situação inválida")
                    if k != "etapaAtual":
                        alteracoes.append({"campo": k, "de": caso.get(k), "para": mudancas[k]})
                    caso[k] = mudancas[k]
            acao = "metadados"
            if "rascunho" in mudancas:
                dif = diferencas(caso["rascunho"], mudancas["rascunho"])
                if dif:
                    caso["rascunho"] = mudancas["rascunho"]
                    caso["revisao"] += 1
                    alteracoes += [{**x, "campo": "rascunho." + x["campo"]} for x in dif]
                    acao = "edicao"
                    if caso.get("situacao") in ("calculado", "concluido"):
                        alteracoes.append({"campo": "situacao", "de": caso["situacao"], "para": "em_conferencia"})
                        caso["situacao"] = "em_conferencia"  # resultado anterior deixou de refletir as entradas
            if not alteracoes and "etapaAtual" not in mudancas:
                return caso
            caso["atualizadoEm"] = agora()
            if alteracoes:
                self._persistir(caso, autor, acao, alteracoes)
            else:
                _escrever_json(os.path.join(self._dir(cid), "caso.json"), caso)
            return caso

    def salvar_interno(self, caso: dict, autor: str, acao: str, alteracoes: list[dict] | None = None) -> dict:
        """Grava estado produzido pela integração (vínculo com o PJe-Calc, execuções) sem nova revisão.

        Somente esses campos são levados ao registro atual: edições do rascunho feitas enquanto o
        PJe-Calc trabalhava são preservadas.
        """
        with _lock:
            atual = self.obter(caso["id"])
            for k in ("pjecalc", "execucoes", "situacao", "edicaoModelo", "padroesPendentes"):
                if k in caso:
                    atual[k] = caso[k]
            caso = atual
            caso["atualizadoEm"] = agora()
            _escrever_json(os.path.join(self._dir(caso["id"]), "caso.json"), caso)
            with open(os.path.join(self._dir(caso["id"]), "auditoria.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"em": agora(), "autor": autor, "acao": acao, "revisao": caso["revisao"],
                                     "alteracoes": alteracoes or []}, ensure_ascii=False) + "\n")
            return caso

    def auditoria(self, cid: str) -> list[dict]:
        p = os.path.join(self._dir(cid), "auditoria.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def revisao(self, cid: str, n: int) -> dict:
        r = _ler_json(os.path.join(self._dir(cid), "revisoes", f"{int(n):06d}.json"))
        if r is None:
            raise KeyError(n)
        return r

    def duplicar(self, cid: str, autor: str, como_cenario: bool = True, padroes_extras: list[str] | None = None) -> dict:
        """Cópia do cálculo; no PJe-Calc ela vira um cálculo novo, então os padrões do original voltam a ser aplicados."""
        orig = self.obter(cid)
        padroes = list(orig.get("padroesPendentes") or []) + list(((orig.get("pjecalc") or {}).get("padroesAplicados") or {}))
        rascunho = copy.deepcopy(orig["rascunho"])
        # o que foi preenchido nas telas do PJe-Calc ficou no cálculo original: na cópia, volta a "preencher"
        rascunho["outrosItens"] = {k: ("sim" if v == "feito" else v) for k, v in (rascunho.get("outrosItens") or {}).items()}
        novo = self.criar({
            "titulo": (orig.get("titulo") or "") + (" — cenário alternativo" if como_cenario else " (cópia)"),
            "cliente": orig.get("cliente"), "parteContraria": orig.get("parteContraria"),
            "processo": orig.get("processo"), "responsavel": orig.get("responsavel"),
            "etiquetas": list(orig.get("etiquetas", [])), "rascunho": rascunho,
            "origem": {"tipo": "duplicado", "de": cid, "revisao": orig["revisao"]},
            "cenarioDe": cid if como_cenario else None,
            "padroesPendentes": list(dict.fromkeys(padroes + list(padroes_extras or []))),
        }, autor)
        return novo

    def excluir(self, cid: str) -> None:
        """Move o caso para a lixeira local (recuperável), nunca apaga definitivamente."""
        with _lock:
            lixeira = os.path.join(self.pasta, "lixeira")
            os.makedirs(lixeira, exist_ok=True)
            shutil.move(self._dir(cid), os.path.join(lixeira, cid + "_" + datetime.now().strftime("%Y%m%d%H%M%S")))

    def pasta_execucao(self, cid: str, eid: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", eid):
            raise ValueError("execução inválida")
        p = os.path.join(self._dir(cid), "execucoes", eid)
        os.makedirs(p, exist_ok=True)
        return p

    # ------------------------------------------------------------------ modelos do escritório
    def listar_modelos(self) -> list[dict]:
        base = os.path.join(self.pasta, "modelos")
        saida = []
        for mid in sorted(os.listdir(base)):
            versoes = sorted(f for f in os.listdir(os.path.join(base, mid)) if f.endswith(".json"))
            if versoes:
                atual = _ler_json(os.path.join(base, mid, versoes[-1]))
                saida.append({**{k: atual.get(k) for k in ("id", "nome", "descricao", "versao", "autor", "em", "premissas", "categoria", "padroes")},
                              "versoes": len(versoes), "origem": "escritorio"})
        return saida

    def obter_modelo(self, mid: str, versao: int | None = None) -> dict:
        base = os.path.join(self.pasta, "modelos", mid)
        versoes = sorted(f for f in os.listdir(base) if f.endswith(".json"))
        if versao:
            return _ler_json(os.path.join(base, f"v{int(versao):04d}.json"))
        return _ler_json(os.path.join(base, versoes[-1]))

    def historico_modelo(self, mid: str) -> list[dict]:
        base = os.path.join(self.pasta, "modelos", mid)
        return [{k: m.get(k) for k in ("versao", "autor", "em", "nota")}
                for m in (_ler_json(os.path.join(base, f)) for f in sorted(os.listdir(base)) if f.endswith(".json"))]

    def salvar_modelo(self, modelo: dict, autor: str, mid: str | None = None) -> dict:
        with _lock:
            if not mid:
                mid = "m" + datetime.now().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(2)
            base = os.path.join(self.pasta, "modelos", mid)
            os.makedirs(base, exist_ok=True)
            versao = len([f for f in os.listdir(base) if f.endswith(".json")]) + 1
            reg = {**modelo, "id": mid, "versao": versao, "autor": autor, "em": agora(),
                   "rascunho": sem_dados_pessoais(modelo.get("rascunho") or rascunho_vazio())}
            _escrever_json(os.path.join(base, f"v{versao:04d}.json"), reg)
            return reg

    # ------------------------------------------------------------------ padrões das funções do PJe-Calc
    # dados/padroes/<id>.json: {id, nome, descricao, menu, funcao, passos, automatico, autor, em}
    def _padrao(self, pid: str) -> str:
        if not re.fullmatch(r"p[0-9a-z_]+", pid or ""):
            raise ValueError("padrão inválido")
        return os.path.join(self.pasta, "padroes", pid + ".json")

    def listar_padroes(self, menu: str | None = None) -> list[dict]:
        base = os.path.join(self.pasta, "padroes")
        if not os.path.isdir(base):
            return []
        itens = [_ler_json(os.path.join(base, f)) for f in sorted(os.listdir(base)) if f.endswith(".json")]
        itens = [p for p in itens if p and (not menu or p.get("menu") == menu)]
        return sorted(itens, key=lambda p: (p.get("funcao") or "", p.get("nome") or ""))

    def obter_padrao(self, pid: str) -> dict:
        p = _ler_json(self._padrao(pid))
        if p is None:
            raise KeyError(pid)
        return p

    def salvar_padrao(self, dados: dict, autor: str, pid: str | None = None) -> dict:
        with _lock:
            os.makedirs(os.path.join(self.pasta, "padroes"), exist_ok=True)
            atual = self.obter_padrao(pid) if pid else {}
            reg = {**atual, **dados, "id": pid or ("p" + datetime.now().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(2)),
                   "autor": autor, "em": agora()}
            _escrever_json(self._padrao(reg["id"]), reg)
            return reg

    def excluir_padrao(self, pid: str) -> None:
        """Vai para a lixeira local (recuperável), como os cálculos."""
        with _lock:
            origem = self._padrao(pid)
            if not os.path.exists(origem):
                raise KeyError(pid)
            lixeira = os.path.join(self.pasta, "lixeira", "padroes")
            os.makedirs(lixeira, exist_ok=True)
            shutil.move(origem, os.path.join(lixeira, f"{pid}_{datetime.now():%Y%m%d%H%M%S}.json"))

    # ------------------------------------------------------------------ cópias de segurança
    def criar_backup(self, motivo: str = "manual") -> dict:
        with _lock:
            nome = datetime.now().strftime("backup_%Y%m%d_%H%M%S") + ".zip"
            destino = os.path.join(self.pasta, "backups", nome)
            manifesto = {}
            with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
                for sub in ("casos", "modelos", "padroes"):
                    for raiz, _, arqs in os.walk(os.path.join(self.pasta, sub)):
                        for a in arqs:
                            p = os.path.join(raiz, a)
                            rel = os.path.relpath(p, self.pasta).replace("\\", "/")
                            with open(p, "rb") as fh:
                                conteudo = fh.read()
                            manifesto[rel] = hashlib.sha256(conteudo).hexdigest()
                            z.writestr(rel, conteudo)
                cfg = os.path.join(self.pasta, "config.json")
                if os.path.exists(cfg):
                    z.write(cfg, "config.json")
                z.writestr("manifesto.json", json.dumps({"criadoEm": agora(), "motivo": motivo, "arquivos": manifesto},
                                                         ensure_ascii=False, indent=1))
            verif = self.verificar_backup(nome)
            return {"arquivo": nome, "arquivos": len(manifesto), "verificado": verif["ok"], "motivo": motivo}

    def listar_backups(self) -> list[dict]:
        base = os.path.join(self.pasta, "backups")
        return [{"arquivo": f, "bytes": os.path.getsize(os.path.join(base, f)),
                 "em": datetime.fromtimestamp(os.path.getmtime(os.path.join(base, f))).isoformat(timespec="seconds")}
                for f in sorted(os.listdir(base), reverse=True) if f.endswith(".zip")]

    def verificar_backup(self, nome: str) -> dict:
        if not re.fullmatch(r"backup_[\d_]+\.zip", nome):
            raise ValueError("nome de backup inválido")
        caminho = os.path.join(self.pasta, "backups", nome)
        with zipfile.ZipFile(caminho) as z:
            ruim = z.testzip()
            man = json.loads(z.read("manifesto.json"))
            divergentes = [rel for rel, h in man["arquivos"].items()
                           if hashlib.sha256(z.read(rel)).hexdigest() != h]
        return {"ok": ruim is None and not divergentes, "corrompido": ruim, "divergentes": divergentes,
                "arquivos": len(man["arquivos"]), "criadoEm": man.get("criadoEm")}

    def restaurar_backup(self, nome: str) -> dict:
        """Restaura somente após verificar o pacote; o estado atual é preservado em outro backup antes."""
        verif = self.verificar_backup(nome)
        if not verif["ok"]:
            return {"ok": False, "motivo": "backup não passou na verificação", **verif}
        antes = self.criar_backup("antes da restauração de " + nome)
        with _lock:
            for sub in ("casos", "modelos", "padroes"):
                alvo = os.path.join(self.pasta, sub)
                shutil.rmtree(alvo, ignore_errors=True)
                os.makedirs(alvo, exist_ok=True)
            with zipfile.ZipFile(os.path.join(self.pasta, "backups", nome)) as z:
                for rel in json.loads(z.read("manifesto.json"))["arquivos"]:
                    destino = os.path.normpath(os.path.join(self.pasta, rel))
                    if not dentro_de(self.pasta, destino):
                        continue
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    with open(destino, "wb") as fh:
                        fh.write(z.read(rel))
        return {"ok": True, "restaurado": nome, "backupAnterior": antes["arquivo"], "arquivos": verif["arquivos"]}


class ConflitoRevisao(Exception):
    def __init__(self, revisao_atual: int):
        super().__init__(f"O cálculo foi alterado em outra janela (revisão atual {revisao_atual}).")
        self.revisao_atual = revisao_atual
