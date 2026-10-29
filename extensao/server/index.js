// PJe-Calc Studio — extensão do Claude Desktop (ponte MCP).
// Repassa as mensagens MCP (JSON-RPC por stdio) ao Studio aberto neste computador, em POST /mcp. O endereço e a
// chave vêm do arquivo de conexão que o Studio escreve ao iniciar; as ferramentas e as regras ficam no Studio.
// Com o Studio fechado, responde o início da conversa e a lista de ferramentas (guardada no arquivo de conexão)
// e, em cada uso, pede para abrir o Studio. Sem dependências: só o Node que vem com o Claude Desktop.
"use strict";
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const readline = require("readline");

const VERSOES = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];
const ARQUIVO = process.env.PJECALC_STUDIO_CONEXAO
  || path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "PJeCalcStudio", "conexao.json");
const FECHADO = "O PJe-Calc Studio não está aberto neste computador. Peça ao usuário para abrir o PJe-Calc Studio "
  + "(e o PJe-Calc, se for enviar ou calcular) e tente de novo.";
const DEMOROU = "O PJe-Calc Studio não respondeu em 15 minutos. A operação pode ter terminado no Studio: confira com "
  + "ler_calculo ou conferir antes de repetir.";
const PRAZO = 15 * 60 * 1000;  // calcular e enviar ao PJe-Calc podem levar vários minutos

function lerConexao() {
  try { return JSON.parse(fs.readFileSync(ARQUIVO, "utf8")); } catch { return null; }
}

// resposta local quando o Studio não atende (fechado, ainda não instalado ou chave trocada)
function local(msg, motivo, c) {
  const ok = (result) => ({ jsonrpc: "2.0", id: msg.id, result });
  switch (msg.method) {
    case "initialize": {
      const pedida = msg.params && msg.params.protocolVersion;
      return ok({ protocolVersion: VERSOES.includes(pedida) ? pedida : VERSOES[0], capabilities: { tools: { listChanged: false } },
        serverInfo: { name: "pjecalc-studio", title: "PJe-Calc Studio", version: (c && c.versao) || "0" },
        instructions: (c && c.instrucoes) || "Ferramentas do PJe-Calc Studio. " + FECHADO });
    }
    case "ping": return ok({});
    case "tools/list": return ok({ tools: (c && c.ferramentas) || [] });
    case "tools/call": return ok({ content: [{ type: "text", text: motivo }], isError: true });
    default: return { jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: motivo } };
  }
}

// POST pelo módulo http (e não fetch): o fetch do Node corta a espera da resposta em 5 minutos, menos que um
// cálculo grande; e o Studio é sempre local, sem proxy.
function postar(url, corpo, chave) {
  return new Promise((resolve, reject) => {
    const dados = Buffer.from(corpo, "utf8");
    const req = http.request(url, { method: "POST", headers: { "Content-Type": "application/json", "Content-Length": dados.length,
      Accept: "application/json, text/event-stream", Authorization: "Bearer " + chave } }, (r) => {
      const partes = [];
      r.on("data", (p) => partes.push(p));
      r.on("end", () => resolve({ status: r.statusCode, corpo: Buffer.concat(partes).toString("utf8") }));
      r.on("error", reject);
    });
    req.setTimeout(PRAZO, () => req.destroy(Object.assign(new Error("prazo"), { code: "PRAZO" })));
    req.on("error", reject);
    req.end(dados);
  });
}

async function encaminhar(msg) {
  if (!msg || typeof msg !== "object" || Array.isArray(msg))
    return { jsonrpc: "2.0", id: null, error: { code: -32600, message: "Mensagem JSON-RPC inválida (esperado um objeto)." } };
  const notificacao = msg.id === undefined;
  const c = lerConexao();  // relido a cada mensagem: o Studio pode ter sido aberto ou reiniciado depois do Claude
  if (!c || !c.url || !c.chave) return notificacao ? null : local(msg, FECHADO, c);
  let r;
  try {
    r = await postar(c.url, JSON.stringify(msg), c.chave);
  } catch (e) {
    return notificacao ? null : local(msg, e && e.code === "PRAZO" ? DEMOROU : FECHADO, c);
  }
  if (r.status === 202 || notificacao) return null;
  if (r.status === 401) return local(msg, "O PJe-Calc Studio recusou a chave do assistente. Peça ao usuário para fechar e abrir o Studio de novo.", c);
  try { return JSON.parse(r.corpo); } catch { return local(msg, `O PJe-Calc Studio respondeu HTTP ${r.status}.`, c); }
}

const saida = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");
let fila = Promise.resolve();  // mantém a ordem das respostas
readline.createInterface({ input: process.stdin }).on("line", (linha) => {
  if (!linha.trim()) return;
  let msg;
  try { msg = JSON.parse(linha); } catch { saida({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "JSON inválido." } }); return; }
  fila = fila.then(async () => {
    const lista = Array.isArray(msg) ? msg : [msg];
    let resp;
    try {
      resp = (await Promise.all(lista.map(encaminhar))).filter(Boolean);
    } catch (e) {  // a ponte nunca cai: uma falha vira resposta, e o Claude segue conectado
      resp = lista.filter((m) => m && m.id !== undefined)
        .map((m) => local(m, "Falha na ponte do PJe-Calc Studio: " + (e && e.message), lerConexao()));
    }
    if (resp.length) saida(Array.isArray(msg) ? resp : resp[0]);
  });
});
