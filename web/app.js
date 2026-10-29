/* PJe-Calc Studio — interface. Nenhum cálculo é feito aqui: os valores exibidos como resultado
 * vêm do relatório oficial e do .PJC gerados pelo PJe-Calc. */
"use strict";
(function () {
  // ============================================================================ utilidades
  function h(tag, attrs, ...filhos) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else if (k === "dataset") Object.assign(el.dataset, v);
      else if (v === true) el.setAttribute(k, "");
      else el.setAttribute(k, String(v));
    }
    for (const f of filhos.flat(Infinity)) {
      if (f === null || f === undefined || f === false) continue;
      el.appendChild(typeof f === "string" || typeof f === "number" ? document.createTextNode(String(f)) : f);
    }
    return el;
  }
  const $ = (s, r = document) => r.querySelector(s);
  // ícones de linha no estilo SF Symbols (24×24, traço herdado da cor do texto; ver .icone em estilo.css)
  const ICONES = {
    calculos: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
    modelos: "M8 8h12v12H8zM4 16V4h12",
    padroes: "M4 20 15 9M14 3.5l.9 1.9 1.9.9-1.9.9-.9 1.9-.9-1.9-1.9-.9 1.9-.9zM19.5 10l.5 1.1 1.1.5-1.1.5-.5 1.1-.5-1.1-1.1-.5 1.1-.5z",
    comparar: "M7 7h13M16 3l4 4-4 4M17 17H4M8 13l-4 4 4 4",
    config: "M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4",
    funcao: "M3 9 12 4l9 5M5 10v8M9.7 10v8M14.3 10v8M19 10v8M3 20h18",
    tabelas: "M4 5h16v14H4zM4 10h16M4 15h16M10 5v14",
    novo: "M12 5v14M5 12h14",
    relatorio: "M5 20V11M10 20V5M15 20v-6M20 20V9",
    buscar: "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM15.5 15.5l5 5",
    voltar: "M15 5l-7 7 7 7",
    versoes: "M12 7.5V12l3 2M4.2 12a7.8 7.8 0 1 0 2.3-5.5M4 3.5v3.5h3.5",
    baixar: "M12 4v11M7 10l5 5 5-5M5 20h14",
    colar: "M9 4h6v3H9zM9 5.5H6v15h12v-15h-3M9 12h6M9 16h4",
    assistente: "M4 5h16v11H10l-5 4v-4H4zM9 10.5h.01M12 10.5h.01M15 10.5h.01",
  };
  function icone(nome) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("class", "icone"); svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", ICONES[nome] || ICONES.funcao);
    svg.appendChild(p);
    return svg;
  }
  // replaceChildren converte null em texto "null"; este auxiliar descarta itens vazios
  const preencher = (el, ...n) => el.replaceChildren(...n.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false));
  const dobrar = (s) => String(s || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const quando = (iso) => { if (!iso) return "—"; const d = new Date(iso); return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); };
  const SITUACOES = { rascunho: "Rascunho", em_conferencia: "Em conferência", calculado: "Calculado", concluido: "Concluído" };
  let uid = 0; const novoId = (p) => `${p}-${++uid}`;

  function dataValida(s) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s || ""); if (!m) return false;
    const d = new Date(+m[3], +m[2] - 1, +m[1]); return d.getFullYear() === +m[3] && d.getMonth() === +m[2] - 1 && d.getDate() === +m[1];
  }
  function mascaraData(inp) {
    inp.addEventListener("input", () => {
      const dig = inp.value.replace(/\D/g, "").slice(0, 8);
      let s = dig; if (dig.length > 4) s = dig.slice(0, 2) + "/" + dig.slice(2, 4) + "/" + dig.slice(4); else if (dig.length > 2) s = dig.slice(0, 2) + "/" + dig.slice(2);
      if (inp.value !== s && !inp.value.endsWith("/")) inp.value = s;
    });
  }
  // Máscara por dígitos: o padrão usa "9" para cada dígito e copia os demais caracteres (".", "-", "/")
  // assim que o dígito seguinte é digitado. O cursor fica depois do mesmo dígito em que estava.
  // completar: ao digitar no fim, já mostra a pontuação seguinte ("529" -> "529.")
  function formatarPadrao(digitos, padrao, completar) {
    let s = "", i = 0, k = 0;
    for (; k < padrao.length && i < digitos.length; k++) s += padrao[k] === "9" ? digitos[i++] : padrao[k];
    if (completar && i > 0) while (k < padrao.length && padrao[k] !== "9") s += padrao[k++];
    return s;
  }
  function mascaraDigitos(inp, padraoDe, aoAlterar) {
    inp.addEventListener("input", (e) => {
      const pos = inp.selectionStart ?? inp.value.length;
      const antes = inp.value.slice(0, pos).replace(/\D/g, "").length;
      const padrao = padraoDe(inp.value.replace(/\D/g, ""));
      const max = padrao.replace(/[^9]/g, "").length;
      const noFim = pos >= inp.value.length;
      const digitando = noFim && (!e.inputType || e.inputType.startsWith("insert"));
      const s = formatarPadrao(inp.value.replace(/\D/g, "").slice(0, max), padrao, digitando);
      if (inp.value !== s) {
        inp.value = s;
        let p = 0, n = 0; while (p < s.length && n < antes) { if (/\d/.test(s[p])) n++; p++; }
        if (digitando) p = s.length;
        inp.setSelectionRange(p, p);
      }
      aoAlterar?.();
    });
  }
  // número único CNJ (Resolução 65/2008): NNNNNNN-DD.AAAA.J.TR.OOOO; J = 5 na Justiça do Trabalho
  const PADRAO_CNJ = "9999999-99.9999.9.99.9999";
  function digitoCnj(n, ano, j, tr, oooo) {
    return String(98n - (BigInt(n + ano + j + tr + oooo + "00") % 97n)).padStart(2, "0");
  }
  // procura um número de processo num texto (o PJe copia com ou sem pontuação, às vezes com o nome da classe)
  function extrairCnj(texto) {
    const t = String(texto || "");
    const m = /(\d{7})\s*-?\s*(\d{2})\s*\.?\s*(\d{4})\s*\.?\s*(\d)\s*\.?\s*(\d{2})\s*\.?\s*(\d{4})/.exec(t);
    if (m) return m.slice(1).join("");
    const d = t.replace(/\D/g, "");
    return d.length === 20 ? d : null;
  }
  // devolve null se o número for válido, ou o motivo em linguagem simples
  function problemaCnj(d) {
    if (!d) return null;
    if (d.length < 20) return `Faltam ${20 - d.length} dígito(s). O número do processo tem 20 dígitos, no formato 0001234-56.2024.5.08.0001.`;
    if (d[13] !== "5") return `Este número não é da Justiça do Trabalho: o dígito depois do ano deve ser 5 (aqui é ${d[13]}).`;
    const esperado = digitoCnj(d.slice(0, 7), d.slice(9, 13), d[13], d.slice(14, 16), d.slice(16, 20));
    if (esperado !== d.slice(7, 9)) return `O número não confere: os dois dígitos depois do traço deveriam ser ${esperado}, não ${d.slice(7, 9)}. Confira se algum número foi digitado errado.`;
    return null;
  }
  // documentos fiscais: CPF, CNPJ e CEI, com os dígitos verificadores da Receita Federal
  const PADROES_DOC = { CPF: "999.999.999-99", CNPJ: "99.999.999/9999-99", CEI: "99.999.99999/99" };
  const padraoDoc = (tipo, dig) => PADROES_DOC[tipo] || (dig.length > 11 ? PADROES_DOC.CNPJ : PADROES_DOC.CPF);
  function cpfValido(d) {
    if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
    for (const t of [9, 10]) {
      let s = 0; for (let i = 0; i < t; i++) s += +d[i] * (t + 1 - i);
      if ((s * 10 % 11) % 10 !== +d[t]) return false;
    }
    return true;
  }
  function cnpjValido(d) {
    if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
    for (const t of [12, 13]) {
      const pesos = t === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
      const r = pesos.reduce((s, p, i) => s + p * +d[i], 0) % 11;
      if ((r < 2 ? 0 : 11 - r) !== +d[t]) return false;
    }
    return true;
  }
  function problemaDoc(tipo, d) {
    if (!d) return null;
    if (tipo === "CPF") return d.length !== 11 ? `O CPF tem 11 dígitos; faltam ${Math.max(0, 11 - d.length)}.` : cpfValido(d) ? null : "Este CPF não existe: os dois últimos dígitos não conferem. Confira a digitação.";
    if (tipo === "CNPJ") return d.length !== 14 ? `O CNPJ tem 14 dígitos; faltam ${Math.max(0, 14 - d.length)}.` : cnpjValido(d) ? null : "Este CNPJ não existe: os dois últimos dígitos não conferem. Confira a digitação.";
    if (tipo === "CEI") return d.length !== 12 ? `O CEI tem 12 dígitos; faltam ${Math.max(0, 12 - d.length)}.` : null;
    return null;
  }
  function competencias(ini, fim) { // "MM/AAAA" inclusivo
    const out = []; let [m, a] = ini.split("/").map(Number); const [mf, af] = fim.split("/").map(Number);
    while (a < af || (a === af && m <= mf)) { out.push(String(m).padStart(2, "0") + "/" + a); m++; if (m > 12) { m = 1; a++; } if (out.length > 1200) break; }
    return out;
  }
  const chaveComp = (c) => { const [m, a] = c.split("/"); return +a * 100 + +m; };
  // número único do processo (NNNNNNN-DD.AAAA.5.TT.OOOO) a partir dos campos do rascunho; "" se não informado
  const numeroProcesso = (d) => d["processo.numero"]
    ? `${d["processo.numero"]}-${d["processo.digito"] || "??"}.${d["processo.ano"] || "????"}.5.${d["processo.regiao"] || "??"}.${d["processo.vara"] || "????"}` : "";

  // ============================================================================ API
  async function api(metodo, caminho, corpo, opcoes = {}) {
    const init = { method: metodo, headers: { "X-PJeCalc-Studio": "1" } };
    if (corpo instanceof ArrayBuffer || corpo instanceof Blob) { init.body = corpo; init.headers["Content-Type"] = "application/octet-stream"; }
    else if (corpo !== undefined) { init.body = JSON.stringify(corpo); init.headers["Content-Type"] = "application/json"; }
    let r;
    try { r = await fetch(caminho, init); } catch (e) { throw Object.assign(new Error("O servidor local da interface não respondeu. Verifique se o PJe-Calc Studio está em execução."), { rede: true }); }
    const dados = await r.json().catch(() => ({}));
    if (!r.ok && !opcoes.aceitar?.includes(r.status)) throw Object.assign(new Error(dados.erro || `Erro ${r.status}`), { status: r.status, dados });
    return dados;
  }

  // ============================================================================ estado e preferências
  const E = { config: {}, motor: null, opcoes: null, caso: null, estadoRes: null, conferencia: null, pendente: false,
    salvando: false, timer: null, criterios: null, ajudaOficial: null, municipios: {}, ultimaOperacao: null, ajudaAberta: null };
  const PREF = "pjstudio:pref";
  function prefs() { try { return JSON.parse(localStorage.getItem(PREF)) || {}; } catch { return {}; } }
  function salvarPref(p) { try { localStorage.setItem(PREF, JSON.stringify({ ...prefs(), ...p })); } catch { /* armazenamento indisponível */ } }
  function aplicarPrefs() {
    const p = prefs();
    if (p.tema && p.tema !== "auto") document.documentElement.dataset.theme = p.tema; else delete document.documentElement.dataset.theme;
    document.documentElement.style.fontSize = (p.fonte || 100) + "%";
    const modo = p.modo || "guiado";
    document.body.classList.toggle("modo-guiado", modo === "guiado");
    document.body.classList.toggle("modo-avancado", modo === "avancado");
    $("#modoGuiado").setAttribute("aria-pressed", String(modo === "guiado"));
    $("#modoAvancado").setAttribute("aria-pressed", String(modo === "avancado"));
  }
  const modoAvancado = () => (prefs().modo || "guiado") === "avancado";

  // ============================================================================ avisos (toast) e diálogos
  function avisar(texto, tipo = "info", ms = 6000) {
    const el = h("div", { class: "aviso " + tipo, role: tipo === "erro" ? "alert" : "status" }, texto);
    $("#avisos").appendChild(el);
    setTimeout(() => el.remove(), ms);
  }
  function dialogo({ titulo, corpo, botoes, aoAbrir, largo }) {
    return new Promise((resolve) => {
      const d = $("#dialogo");
      const idT = novoId("dlg");
      d.setAttribute("aria-labelledby", idT);
      d.style.maxWidth = largo ? "min(1100px, 96vw)" : "";
      const rodape = h("div", { class: "dlg-rodape" });
      (botoes || [{ texto: "Fechar", valor: null }]).forEach((b) =>
        rodape.appendChild(h("button", { type: "button", class: "botao " + (b.classe || ""), onclick: () => { d.close(); resolve(b.valor); } }, b.texto)));
      preencher(d, h("div", { class: "dlg-cab" }, h("h2", { id: idT, text: titulo })), h("div", { class: "dlg-corpo" }, corpo), rodape);
      // Esc ou fechamento sem botão: resolve como "cancelado" (a promessa ignora resoluções depois da primeira)
      d.onclose = () => resolve(null);
      d.oncancel = () => resolve(null);
      d.showModal();
      if (aoAbrir) aoAbrir(d);
      else (d.querySelector("input,select,textarea,button.primario") || d.querySelector("button"))?.focus();
    });
  }
  const confirmar = (titulo, texto, rotuloSim = "Confirmar", perigo = false) =>
    dialogo({ titulo, corpo: h("p", { text: texto }), botoes: [{ texto: "Cancelar", valor: false }, { texto: rotuloSim, valor: true, classe: perigo ? "perigo" : "primario" }] });

  // comCorrigir: dentro de um cálculo, cada erro, alerta ou informação ganha o botão "Corrigir" (ver corrigirPendencia)
  function listaMensagens(msgs, comCorrigir) {
    if (!msgs || !msgs.length) return h("p", { class: "sutil mini", text: "Sem mensagens do PJe-Calc." });
    return h("ul", { class: "lista-avisos" }, msgs.map((m) => h("li", {},
      h("span", { class: "marcador " + (m.severidade || m.nivel), text: { erro: "Erro", alerta: "Alerta", sucesso: "Sucesso", info: "Info", impeditivo: "Impeditivo" }[m.severidade || m.nivel] || m.severidade }),
      h("span", { text: m.texto }),
      comCorrigir && E.caso && (m.severidade || m.nivel) !== "sucesso" ? botaoCorrigir(destinoPendencia(m.texto, m.campo)) : null)));
  }
  function mostrarPassos(passos) {
    return h("ol", { class: "passos" }, (passos || []).map((p) => h("li", {},
      h("div", { class: "titulo" }, h("span", { class: "pill " + (p.ok ? "pill-ok" : "pill-erro"), text: p.ok ? "Concluído" : "Não concluído" }), p.rotulo),
      p.mensagens && p.mensagens.length ? h("div", { class: "mensagens" }, listaMensagens(p.mensagens, true)) : null)));
  }

  // ============================================================================ status do PJe-Calc
  async function atualizarStatus() {
    const pill = $("#statusMotor");
    try {
      const r = await api("GET", "/api/estado");
      E.config = r.config; E.motor = r.motor;
      const at = $("#statusAtualizacao");
      at.hidden = !r.atualizacao?.disponivel;
      if (r.atualizacao?.disponivel) { at.textContent = `Versão ${r.atualizacao.versao} disponível`; at.title = "Ver as novidades e atualizar (Configurações)"; }
      if (r.motor.acessivel) {
        pill.className = "pill " + (r.compativel ? "pill-ok" : "pill-alerta");
        pill.textContent = `PJe-Calc ${r.motor.versao || "?"} ${r.compativel ? "conectado" : "— versão não validada"}`;
        pill.title = `Build ${r.motor.build || "?"} em ${r.motor.url}`;
      } else {
        pill.className = "pill pill-erro"; pill.textContent = "PJe-Calc desconectado";
        pill.title = "Inicie o PJe-Calc pelo atalho oficial. Rascunhos continuam disponíveis offline.";
      }
      return r;
    } catch (e) {
      pill.className = "pill pill-erro"; pill.textContent = "Servidor local indisponível";
    }
  }

  // ============================================================================ roteamento
  function rota() {
    const [caminho, consulta] = (location.hash.slice(1) || "/").split("?");
    const partes = caminho.split("/").filter(Boolean);
    return { partes, q: Object.fromEntries(new URLSearchParams(consulta || "")) };
  }
  async function navegar() {
    if (E.pendente) await salvarAgora();
    fecharAjuda();
    const { partes, q } = rota();
    const main = $("#conteudo");
    const campoPedido = !!E.focoPendente;  // irParaCampo: a etapa foca o campo ao ser desenhada
    $("#barraAcoes").hidden = true;
    document.querySelector(".corpo").classList.remove("sem-lateral");
    try {
      if (partes[0] === "caso" && partes[1]) await telaCaso(partes[1], partes[2] || null, partes[3] || null);
      else if (partes[0] === "original") await telaOriginalGeral(partes[1] || "buscar");
      else if (partes[0] === "comparar") await telaComparar(q);
      else if (partes[0] === "modelos") await telaModelos();
      else if (partes[0] === "padroes") await telaPadroes();
      else if (partes[0] === "config") await telaConfig();
      else if (partes[0] === "claude") await telaClaude();
      else await telaPainel();
    } catch (e) {
      preencher(main, h("div", { class: "faixa erro", role: "alert" }, h("strong", { text: "Não foi possível abrir esta tela. " }), h("div", { text: e.message })));
    }
    E.focoPendente = null;
    const h1 = main.querySelector("h1");
    if (h1) document.title = h1.textContent + " — PJe-Calc Studio";
    if (campoPedido && main.contains(document.activeElement)) return;
    if (h1) { h1.tabIndex = -1; h1.focus({ preventScroll: true }); }
    window.scrollTo(0, 0);
  }

  function lateralGeral(atual) {
    document.querySelector(".corpo").classList.remove("sem-lateral");
    const item = (href, texto, chave, ic) => h("a", { href, "aria-current": atual === chave ? "page" : null }, icone(ic), h("span", { text: texto }));
    preencher($("#lateral"), 
      h("h2", { text: "Escritório" }),
      h("div", { class: "links" }, item("#/", "Cálculos", "painel", "calculos"), item("#/modelos", "Modelos de cálculo", "modelos", "modelos"),
        item("#/padroes", "Padrões do escritório", "padroes", "padroes"), item("#/comparar", "Comparar cenários", "comparar", "comparar"),
        item("#/claude", "Assistentes Claude e Codex", "claude", "assistente"),
        item("#/config", "Configurações", "config", "config")),
      h("h2", { text: "Funções do PJe-Calc" }),
      h("div", { class: "links" }, TELAS_GERAIS.filter((t) => t.grupo === "PJe-Calc").map((t) => item("#/original/" + t.id, t.titulo, "original:" + t.id,
        { externo: "novo", consolidado: "relatorio", buscar: "buscar" }[t.id]))),
      h("details", { class: "nav-original", open: String(atual || "").startsWith("original:t-") },
        h("summary", {}, `Tabelas do PJe-Calc (${TELAS_GERAIS.filter((t) => t.grupo === "Tabelas").length})`),
        h("div", { class: "links" }, TELAS_GERAIS.filter((t) => t.grupo === "Tabelas").map((t) => item("#/original/" + t.id, t.titulo, "original:" + t.id, "tabelas")))));
  }

  // ============================================================================ painel do escritório
  // estado de trabalho de um cálculo da lista (mesmos critérios do cabeçalho do cálculo)
  function estadoLista(c) {
    const ult = c.ultimaExecucao;
    if (ult && ult.revisaoEntradas === c.revisao) return { cls: "ok", t: "Calculado", sub: ult.liquido ? `líquido R$ ${ult.liquido}` : "" };
    if (ult) return { cls: "erro", t: "Resultado desatualizado", sub: "os dados mudaram depois do cálculo" };
    if (c.calculoPjecalc && c.pendenciasErro && c.gravadoRevisao === c.revisao) return { cls: "erro", t: "Pendências no PJe-Calc", sub: `${c.pendenciasErro} pendência(s) impedem calcular` };
    if (c.calculoPjecalc && c.gravadoRevisao !== c.revisao) return { cls: "alerta", t: "Alterações não enviadas", sub: `cálculo nº ${c.calculoPjecalc} no PJe-Calc` };
    if (c.calculoPjecalc) return { cls: "info", t: "Enviado, falta calcular", sub: `cálculo nº ${c.calculoPjecalc}` };
    return { cls: "neutro", t: "Rascunho", sub: "ainda não enviado ao PJe-Calc" };
  }
  const nomeEtapa = (id) => { const e = ETAPAS.find((x) => x.id === id) || ETAPAS[0]; const f = FASES.find((x) => x.id === e.fase); return `${f.titulo} › ${e.titulo}`; };
  function menuAcoes(rotulo, itens) {
    return h("details", { class: "menu" }, h("summary", { class: "botao pequeno", "aria-label": "Mais ações: " + rotulo }, "Mais ▾"),
      h("div", { class: "menu-lista", role: "menu" }, itens.filter(Boolean).map((i) => i.href
        ? h("a", { role: "menuitem", href: i.href, class: i.perigo ? "perigo" : null }, i.texto)
        : h("button", { type: "button", role: "menuitem", class: i.perigo ? "perigo" : null, onclick: (e) => { e.currentTarget.closest("details").open = false; i.f(); } }, i.texto))));
  }
  async function telaPainel() {
    lateralGeral("painel");
    const main = $("#conteudo");
    const filtros = { q: "", situacao: "", responsavel: "", etiqueta: "", favorito: "" };
    const lista = h("div", { "aria-live": "polite" });
    const buscar = h("input", { type: "search", id: "fBusca", placeholder: "Cliente, parte contrária, processo, etiqueta…", "aria-describedby": "fBuscaDica" });
    const sit = h("select", { id: "fSit" }, h("option", { value: "" }, "Todas"), Object.entries(SITUACOES).map(([v, t]) => h("option", { value: v }, t)));
    const resp = h("select", { id: "fResp" }, h("option", { value: "" }, "Todos"));
    const etq = h("select", { id: "fEtq" }, h("option", { value: "" }, "Todas"));
    const fav = h("input", { type: "checkbox", id: "fFav" });
    const denso = () => prefs().densidade === "compacta";
    const dens = h("div", { class: "grupo-botoes", role: "group", "aria-label": "Densidade da lista" },
      h("button", { type: "button", "aria-pressed": String(!denso()), onclick: () => { salvarPref({ densidade: "confortavel" }); telaPainel(); } }, "Confortável"),
      h("button", { type: "button", "aria-pressed": String(denso()), onclick: () => { salvarPref({ densidade: "compacta" }); telaPainel(); } }, "Compacta"));
    let todos = [];
    async function carregar() {
      const p = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
      const r = await api("GET", "/api/casos?" + p);
      desenhar(r.casos);
    }
    function desenhar(casos) {
      if (!casos.length) {
        preencher(lista, h("div", { class: "cartao" }, h("p", { text: todos.length ? "Nenhum cálculo corresponde à pesquisa e aos filtros. Limpe a pesquisa ou escolha “Todas” nos filtros." : "Você ainda não tem cálculos. Use “Novo cálculo” para começar, em branco ou a partir de um modelo, ou importe um arquivo .PJC." })));
        return;
      }
      const corpo = h("tbody");
      casos.forEach((c) => {
        const s = estadoLista(c);
        const href = `#/caso/${c.id}/${c.etapaAtual || "identificacao"}`;
        const titulo = c.titulo || "(sem título)";
        corpo.appendChild(h("tr", { class: "linha-caso" },
          h("td", { class: "col-estrela" }, h("button", { class: "botao leve estrela", "aria-pressed": String(!!c.favorito), "aria-label": (c.favorito ? "Remover dos favoritos: " : "Marcar como favorito: ") + titulo,
            onclick: async () => { await api("PUT", `/api/casos/${c.id}`, { favorito: !c.favorito }); carregar(); } }, c.favorito ? "★" : "☆")),
          h("td", {}, h("a", { class: "titulo-link", href }, titulo),
            h("div", { class: "sub", text: [[c.cliente, c.parteContraria].filter(Boolean).join(" × "), c.processo, c.cenarioDe ? "cenário alternativo" : ""].filter(Boolean).join(" · ") || "Partes ainda não informadas" }),
            (c.etiquetas || []).length ? h("div", { class: "chips sub" }, c.etiquetas.map((e) => h("span", { class: "etiqueta", text: e }))) : null),
          h("td", {}, h("span", { class: "situacao " + s.cls, text: s.t }), h("div", { class: "sub", text: s.sub }),
            c.situacao === "concluido" ? h("div", { class: "sub", text: "marcado como concluído" }) : null),
          h("td", { class: "mini" }, quando(c.atualizadoEm), h("div", { class: "sub", text: c.responsavel ? "por " + c.responsavel : "" })),
          h("td", { class: "col-acoes" }, h("div", { class: "acoes-linha" },
            h("a", { class: "botao pequeno", href, "aria-label": "Abrir " + titulo }, "Abrir"),
            menuAcoes(titulo, [
              c.ultimaExecucao ? { texto: "Ver resultado", href: `#/caso/${c.id}/resultado` } : null,
              { texto: "Duplicar como cenário", f: () => duplicar(c.id) },
              { texto: "Mover para a lixeira…", perigo: true, f: async () => {
                if (await confirmar("Mover para a lixeira", `Mover “${titulo}” para a lixeira deste computador? O cálculo gravado no PJe-Calc não é alterado, e a lixeira pode ser recuperada pela pasta de dados.`, "Mover para a lixeira", true)) {
                  const r = await api("DELETE", `/api/casos/${c.id}`); avisar(r.mensagem, "ok"); carregar(); } } }])))));
      });
      preencher(lista, h("div", { class: "tabela-rolagem" + (denso() ? " denso" : "") }, h("table", { class: "tabela tabela-casos" },
        h("caption", { class: "sr-only", text: `${casos.length} cálculo(s)` }),
        h("thead", {}, h("tr", {}, [["", "Favorito"], ["Cálculo"], ["Situação"], ["Atualizado"], ["", "Ações"]].map(([t, sr]) => h("th", { scope: "col" }, t, sr ? h("span", { class: "sr-only", text: sr }) : null)))),
        corpo)), h("p", { class: "mini sutil", text: `${casos.length} cálculo(s)` }));
    }
    const r0 = await api("GET", "/api/casos");
    todos = r0.casos;
    [...new Set(todos.map((c) => c.responsavel).filter(Boolean))].forEach((n) => resp.appendChild(h("option", { value: n }, n)));
    [...new Set(todos.flatMap((c) => c.etiquetas || []))].forEach((n) => etq.appendChild(h("option", { value: n }, n)));
    let t;
    buscar.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { filtros.q = buscar.value; carregar(); }, 250); });
    sit.addEventListener("change", () => { filtros.situacao = sit.value; carregar(); });
    resp.addEventListener("change", () => { filtros.responsavel = resp.value; carregar(); });
    etq.addEventListener("change", () => { filtros.etiqueta = etq.value; carregar(); });
    fav.addEventListener("change", () => { filtros.favorito = fav.checked ? "1" : ""; carregar(); });
    const ultimo = todos[0];
    const atencao = todos.filter((c) => ["erro", "alerta"].includes(estadoLista(c).cls)).slice(0, 6);
    preencher(main, h("div", { class: "area" },
      h("div", { class: "cabecalho-etapa" }, h("div", {}, h("h1", { text: "Cálculos" }),
        h("p", { class: "sutil", text: "Rascunhos e versões ficam neste computador. Os valores são sempre calculados pelo PJe-Calc instalado." })),
        h("div", { class: "acoes" }, h("button", { class: "botao", onclick: trazerDoPjecalc, title: "Liga ao Studio um cálculo que já existe no PJe-Calc, sem duplicá-lo" }, "Trazer do PJe-Calc"),
          h("button", { class: "botao", onclick: importarPjc }, "Importar arquivo .PJC"), h("button", { class: "botao primario", onclick: novoCalculo }, "Novo cálculo"))),
      ultimo ? (() => { const s = estadoLista(ultimo); return h("section", { class: "continuar", "aria-labelledby": "tContinuar" },
        h("div", {}, h("h2", { class: "eyebrow", id: "tContinuar", style: "margin:0", text: "Continuar de onde parei" }),
          h("p", { class: "titulo-caso", text: ultimo.titulo || "(sem título)" }),
          h("p", { class: "passo", style: "margin:0" }, "Você estava em ", h("strong", { text: nomeEtapa(ultimo.etapaAtual) }), ` · atualizado ${quando(ultimo.atualizadoEm)}`),
          h("p", { style: "margin:6px 0 0" }, h("span", { class: "situacao " + s.cls, text: s.t }), s.sub ? h("span", { class: "mini sutil", text: " " + s.sub }) : null)),
        h("div", { class: "acoes" }, h("a", { class: "botao primario", href: `#/caso/${ultimo.id}/${ultimo.etapaAtual || "identificacao"}` }, "Continuar"))); })() : null,
      atencao.length ? h("section", { class: "atencao", "aria-labelledby": "tAtencao" }, h("h2", { id: "tAtencao", text: `Precisam de atenção (${atencao.length})` }),
        h("ul", {}, atencao.map((c) => { const s = estadoLista(c); return h("li", {}, h("span", { class: "situacao " + s.cls, text: s.t }),
          h("a", { href: `#/caso/${c.id}/${s.cls === "erro" && c.ultimaExecucao ? "calculo" : c.pendenciasErro ? "conferencia" : "calculo"}` }, c.titulo || "(sem título)"),
          h("span", { class: "motivo", text: s.sub })); }))) : null,
      h("section", { "aria-labelledby": "tTodos" }, h("h2", { id: "tTodos", text: "Todos os cálculos" }),
        h("div", { class: "barra-lista", role: "search" },
          h("div", { class: "campo busca" }, h("label", { for: "fBusca", text: "Pesquisar" }), buscar,
            h("span", { id: "fBuscaDica", class: "sr-only", text: "Procura em título, cliente, parte contrária, processo, responsável, número no PJe-Calc e etiquetas." })),
          h("div", { class: "campo" }, h("label", { for: "fSit", text: "Situação do trabalho" }), sit),
          h("div", { class: "campo so-avancado" }, h("label", { for: "fResp", text: "Responsável" }), resp),
          h("div", { class: "campo so-avancado" }, h("label", { for: "fEtq", text: "Etiqueta" }), etq),
          h("label", { class: "marcacao", for: "fFav", style: "padding-bottom:8px" }, fav, "Só favoritos"),
          dens),
        lista)));
    desenhar(todos);
  }

  async function duplicar(id) {
    const r = await api("POST", `/api/casos/${id}/duplicar`, { cenario: true });
    avisar("Cenário criado. O cálculo original foi preservado.", "ok");
    location.hash = `#/caso/${r.caso.id}/identificacao`;
  }

  // nomes dos padrões do escritório, para mostrar o que um modelo (ou o escritório) aplica no primeiro envio
  const rotuloPadrao = (p) => `${p.nome} (${p.funcao || "PJe-Calc"})`;
  function avisoPadroes(ids, padroes, titulo) {
    const porId = Object.fromEntries(padroes.map((p) => [p.id, p]));
    const todos = [...new Set([...(ids || []), ...padroes.filter((p) => p.automatico).map((p) => p.id)])].filter((id) => porId[id]);
    return todos.length ? h("div", { class: "faixa info" }, h("strong", { text: titulo || "No primeiro envio ao PJe-Calc, o Studio também aplica:" }),
      h("ul", { class: "lista-simples mini" }, todos.map((id) => h("li", { text: rotuloPadrao(porId[id]) + (porId[id].automatico ? " · automático" : "") })))) : null;
  }
  async function novoCalculo() {
    const [r, rp] = await Promise.all([api("GET", "/api/modelos"), api("GET", "/api/padroes").catch(() => ({ padroes: [] }))]);
    const pref = E.config.modeloPadrao || null;
    const ehPadrao = (m) => !!pref && m.id === pref.id && m.origem === pref.origem;
    let escolhido = null;
    const titulo = h("input", { type: "text", id: "nTitulo", placeholder: "Ex.: Maria × Empresa — liquidação" });
    const lista = h("div", { role: "radiogroup", "aria-label": "Modelo inicial", class: "catalogo", style: "max-height:46vh" });
    const premissas = h("div", { class: "mini", "aria-live": "polite" });
    // o modelo padrão do escritório vem primeiro e já marcado: na maioria dos casos basta dar um título e criar
    const modelos = r.modelos.slice().sort((a, b) => (ehPadrao(b) - ehPadrao(a)) || String(a.categoria || "").localeCompare(String(b.categoria || "")));
    const opcoes = [{ id: "", nome: "Cálculo em branco", descricao: "Todos os parâmetros começam com os padrões do PJe-Calc.", origem: "inicial" }, ...modelos];
    const inicial = Math.max(0, opcoes.findIndex(ehPadrao));
    const mostrar = async (m) => {
      escolhido = m.id ? m : null;
      preencher(premissas, m.id ? null : avisoPadroes([], rp.padroes));
      if (!m.id) return;
      const det = await api("GET", `/api/modelos/${m.id}?origem=${m.origem}`);
      if (escolhido !== m) return;  // outra opção foi marcada enquanto as premissas carregavam
      const md = det.modelo;
      preencher(premissas, h("h3", { text: "Premissas do modelo " + md.nome + (md.versao ? ` (versão ${md.versao})` : "") }),
        md.suporte === "parcial" ? h("div", { class: "faixa alerta" }, h("strong", { text: "Suporte parcial:" }), h("div", { text: " parte dos parâmetros deve ser conferida ou ajustada no quadro de critérios ou nas funções do PJe-Calc." })) : null,
        h("ul", { class: "premissas" }, (md.premissas || []).map((p) => h("li", {}, p.confirmar ? h("span", { class: "marcador alerta", text: "Confirmar" }) : null, " ", p.texto))),
        avisoPadroes(md.padroes, rp.padroes),
        md.fontes ? h("p", { class: "sutil", text: "Fontes: " + md.fontes.join("; ") + (md.revisadoEm ? ` · revisado em ${md.revisadoEm.split("-").reverse().join("/")}` : "") }) : null);
    };
    opcoes.forEach((m, i) => {
      const id = novoId("mod");
      const rb = h("input", { type: "radio", name: "modelo", id, value: i, checked: i === inicial, "aria-labelledby": id + "-n", "aria-describedby": id + "-d" });
      rb.addEventListener("change", () => mostrar(m));
      lista.appendChild(h("label", { class: "marcacao cartao", for: id, style: "margin:0;padding:10px" }, rb,
        h("span", {}, h("strong", { id: id + "-n", text: m.nome }),
          m.categoria ? h("span", { class: "etiqueta", text: " " + m.categoria }) : null,
          m.origem === "escritorio" ? h("span", { class: "etiqueta", text: " escritório v" + m.versao }) : null,
          ehPadrao(m) ? h("span", { class: "pill pill-ok", text: "padrão do escritório" }) : null,
          h("div", { class: "mini sutil", id: id + "-d", text: m.descricao || "" }))));
    });
    mostrar(opcoes[inicial]);
    const ok = await dialogo({ titulo: "Novo cálculo", largo: true, corpo: h("div", {},
      h("div", { class: "campo" }, h("label", { for: "nTitulo", text: "Título interno (opcional)" }), titulo),
      h("h3", { text: "Ponto de partida" }), lista, premissas),
      aoAbrir: () => titulo.focus(),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Criar cálculo", valor: true, classe: "primario" }] });
    if (!ok) return;
    const corpo = { titulo: titulo.value || undefined };
    if (escolhido) corpo.modelo = { id: escolhido.id, origem: escolhido.origem, versao: escolhido.versao };
    const c = await api("POST", "/api/casos", corpo);
    location.hash = `#/caso/${c.caso.id}/identificacao`;
  }

  async function importarPjc() {
    const arq = h("input", { type: "file", id: "arqPjc", accept: ".pjc,.PJC" });
    const ok = await dialogo({ titulo: "Importar arquivo .PJC", corpo: h("div", {},
      h("p", { text: "O arquivo é importado pela tela oficial “Importar” do PJe-Calc (com as validações do programa). Em seguida, os dados gravados são lidos de volta para criar o cálculo nesta interface." }),
      h("div", { class: "faixa alerta" }, h("div", { text: "A importação cria um novo cálculo no PJe-Calc instalado. Dados regionais (feriados, pontos facultativos, pisos e vale-transporte) não acompanham o arquivo." })),
      h("div", { class: "campo" }, h("label", { for: "arqPjc", text: "Arquivo do PJe-Calc (.PJC)" }), arq)),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Importar no PJe-Calc", valor: true, classe: "primario" }] });
    if (!ok || !arq.files[0]) return;
    avisar("Importando no PJe-Calc…");
    const buf = await arq.files[0].arrayBuffer();
    try {
      const r = await api("POST", "/api/importar-pjc?nome=" + encodeURIComponent(arq.files[0].name), buf);
      if (!r.ok) { await dialogo({ titulo: "O PJe-Calc não importou o arquivo", corpo: mostrarPassos(r.passos) }); return; }
      await dialogo({ titulo: "Arquivo importado", corpo: mostrarPassos(r.passos) });
      location.hash = `#/caso/${r.caso}/identificacao`;
    } catch (e) { avisar(e.message, "erro", 10000); }
  }

  // ============================================================================ definição das etapas e campos
  const ETAPAS = [
    { id: "identificacao", fase: "caso", titulo: "Partes e processo", desc: "Quem são as partes, o número do processo e onde o trabalho era prestado." },
    { id: "contrato", fase: "caso", titulo: "Contrato", desc: "Datas do contrato, prescrição, remunerações e aviso prévio." },
    { id: "historico", fase: "dados", titulo: "Histórico salarial", desc: "Valores mensais que servem de base para as verbas." },
    { id: "jornada", fase: "dados", titulo: "Jornada", desc: "Carga horária mensal (divisor) e regra do sábado." },
    { id: "verbas", fase: "dados", titulo: "Verbas", desc: "Parcelas pedidas ou deferidas, com bases e quantidades mês a mês." },
    { id: "reflexos", fase: "dados", titulo: "Reflexos e FGTS", desc: "Repercussões de cada verba, incidências e FGTS." },
    { id: "atualizacao", fase: "dados", titulo: "Correção e juros", desc: "Data de liquidação, correção monetária e juros." },
    { id: "outros", fase: "dados", titulo: "Outros itens do cálculo", desc: "Férias, faltas, dano moral e multas, honorários, custas, INSS, imposto de renda e descontos: responda o que o documento do caso diz sobre cada um." },
    { id: "conferencia", fase: "conferencia", titulo: "Revisar tudo", desc: "Confira cada seção antes de enviar. Use “Alterar” para corrigir sem refazer o percurso." },
    { id: "calculo", fase: "conferencia", titulo: "Enviar e calcular", desc: "Envie os dados ao PJe-Calc e execute o cálculo oficial." },
    { id: "resultado", fase: "resultado", titulo: "Resultado", desc: "Valores apurados pelo PJe-Calc com os dados enviados." },
    { id: "exportacao", fase: "resultado", titulo: "Documentos", desc: "Relatório oficial, arquivo .PJC e planilha de conferência." },
  ];
  const FASES = [
    { id: "caso", titulo: "Caso" }, { id: "dados", titulo: "Dados e verbas" },
    { id: "conferencia", titulo: "Conferência" }, { id: "resultado", titulo: "Resultado" },
  ];
  // padrões observados na tela "Novo" do PJe-Calc 2.16.0 (exibidos quando o rascunho não define o campo)
  const PADROES = { "contrato.prescricaoQuinquenal": false, "contrato.prescricaoFgts": false, "contrato.regime": "INTEGRAL",
    "contrato.apuracaoAvisoPrevio": "APURACAO_CALCULADA", "contrato.projetaAvisoIndenizado": true, "contrato.limitarAvos": false,
    "contrato.zeraValorNegativo": false, "contrato.consideraFeriadoEstadual": true, "contrato.consideraFeriadoMunicipal": true,
    "jornada.cargaHorariaPadrao": "220,00", "jornada.sabadoDiaUtil": true };
  const op = (chave) => (E.opcoes?.opcoes?.[chave] || []);
  const GRUPOS = {
    identificacao: [
      { titulo: "Organização interna", nota: "Usado só nesta interface (painel, pesquisa e etiquetas). Não é enviado ao PJe-Calc.", campos: [
        { k: "meta.titulo", rotulo: "Título interno", tipo: "texto", dica: "Nome curto para localizar o cálculo." },
        { k: "meta.cliente", rotulo: "Cliente", tipo: "texto" },
        { k: "meta.parteContraria", rotulo: "Parte contrária", tipo: "texto" },
        { k: "meta.responsavel", rotulo: "Responsável", tipo: "texto" },
        { k: "meta.etiquetas", rotulo: "Etiquetas", tipo: "texto", dica: "Separe por vírgula. Ex.: urgente, recurso." },
        { k: "meta.observacoes", rotulo: "Observações internas", tipo: "area", largura: "inteiro" }] },
      { titulo: "Processo", especial: "cnj" },
      { titulo: "Reclamante", campos: [
        { k: "reclamante.nome", rotulo: "Nome", tipo: "texto", obrig: true, largura: "largo" },
        { k: "reclamante.tipoDocumentoFiscal", rotulo: "Documento fiscal", tipo: "lista", opcoes: "reclamante.tipoDocumentoFiscal", vazio: "Não informar" },
        { k: "reclamante.numeroDocumentoFiscal", rotulo: "Número do documento", tipo: "documento", tipoDe: "reclamante.tipoDocumentoFiscal" },
        { k: "reclamante.tipoDocumentoPrevidenciario", rotulo: "Documento previdenciário", tipo: "lista", opcoes: "reclamante.tipoDocumentoPrevidenciario", vazio: "Não informar", avancado: true },
        { k: "reclamante.numeroDocumentoPrevidenciario", rotulo: "Número (PIS/PASEP/NIT)", tipo: "texto", avancado: true }] },
      { titulo: "Reclamado", campos: [
        { k: "reclamado.nome", rotulo: "Nome", tipo: "texto", obrig: true, largura: "largo" },
        { k: "reclamado.tipoDocumentoFiscal", rotulo: "Documento fiscal", tipo: "lista", opcoes: "reclamado.tipoDocumentoFiscal", vazio: "Não informar" },
        { k: "reclamado.numeroDocumentoFiscal", rotulo: "Número do documento", tipo: "documento", tipoDe: "reclamado.tipoDocumentoFiscal" }] },
      { titulo: "Local da prestação de serviços", campos: [
        { k: "local.estado", rotulo: "Estado", tipo: "estado", obrig: true },
        { k: "local.municipio", rotulo: "Município", tipo: "municipio", obrig: true, largura: "largo" }] },
    ],
    contrato: [
      { titulo: "Datas", campos: [
        { k: "contrato.dataAdmissao", rotulo: "Admissão", tipo: "data", obrig: true },
        { k: "contrato.dataDemissao", rotulo: "Demissão", tipo: "data" },
        { k: "contrato.dataAjuizamento", rotulo: "Ajuizamento", tipo: "data", obrig: true },
        { k: "contrato.dataInicioCalculo", rotulo: "Início do cálculo", tipo: "data", avancado: true, dica: "Vazio: desde a admissão." },
        { k: "contrato.dataTerminoCalculo", rotulo: "Término do cálculo", tipo: "data", avancado: true, dica: "Vazio: até a demissão." }] },
      { titulo: "Prescrição", campos: [
        { k: "contrato.prescricaoQuinquenal", rotulo: "Aplicar prescrição quinquenal", tipo: "marca" },
        { k: "contrato.prescricaoFgts", rotulo: "Aplicar prescrição do FGTS", tipo: "marca" }] },
      { titulo: "Remuneração e regime", campos: [
        { k: "contrato.regime", rotulo: "Regime de trabalho", tipo: "lista", opcoes: "contrato.regime" },
        { k: "contrato.maiorRemuneracao", rotulo: "Maior remuneração (R$)", tipo: "moeda" },
        { k: "contrato.ultimaRemuneracao", rotulo: "Última remuneração (R$)", tipo: "moeda" }] },
      { titulo: "Aviso prévio", campos: [
        { k: "contrato.apuracaoAvisoPrevio", rotulo: "Prazo de aviso prévio", tipo: "lista", opcoes: "contrato.apuracaoAvisoPrevio" },
        { k: "contrato.prazoAvisoInformado", rotulo: "Prazo informado (dias)", tipo: "inteiro", seCampo: ["contrato.apuracaoAvisoPrevio", "APURACAO_INFORMADA"] },
        { k: "contrato.projetaAvisoIndenizado", rotulo: "Projetar aviso prévio indenizado", tipo: "marca" }] },
      { titulo: "Outros parâmetros do cálculo", avancado: true, campos: [
        { k: "contrato.limitarAvos", rotulo: "Limitar avos ao período do cálculo", tipo: "marca" },
        { k: "contrato.zeraValorNegativo", rotulo: "Zerar valor negativo (padrão)", tipo: "marca" },
        { k: "contrato.consideraFeriadoEstadual", rotulo: "Considerar feriados estaduais", tipo: "marca" },
        { k: "contrato.consideraFeriadoMunicipal", rotulo: "Considerar feriados municipais", tipo: "marca" },
        { k: "observacoes.comentarios", rotulo: "Comentários (gravados no PJe-Calc)", tipo: "area", largura: "inteiro" }] },
    ],
    jornada: [
      { titulo: "Carga horária", campos: [
        { k: "jornada.cargaHorariaPadrao", rotulo: "Carga horária mensal padrão (divisor)", tipo: "moeda", ajuda: "jornada.cargaHorariaPadrao" },
        { k: "jornada.sabadoDiaUtil", rotulo: "Sábado como dia útil", tipo: "marca" }] },
    ],
  };

  // ============================================================================ campos de formulário
  function obterValor(k) {
    const c = E.caso;
    if (k.startsWith("meta.")) { const m = k.slice(5); return m === "etiquetas" ? (c.etiquetas || []).join(", ") : c[m]; }
    const d = c.rascunho.dados || {};
    return k in d ? d[k] : undefined;
  }
  function definirValor(k, v) {
    const c = E.caso;
    if (k.startsWith("meta.")) {
      const m = k.slice(5);
      c[m] = m === "etiquetas" ? String(v).split(",").map((s) => s.trim()).filter(Boolean) : v;
    } else {
      c.rascunho.dados = c.rascunho.dados || {};
      if (v === "" || v === undefined) delete c.rascunho.dados[k]; else c.rascunho.dados[k] = v;
    }
    agendarSalvamento();
  }
  function errosDoCampo(k) {
    return (E.conferencia?.avisos || []).filter((a) => a.campo === k);
  }

  function campo(def, opcoesExtra = {}) {
    const id = "f-" + def.k.replace(/[^\w]/g, "_");
    const aj = window.AJUDA[def.ajuda || def.k];
    const valorAtual = opcoesExtra.valor !== undefined ? opcoesExtra.valor : obterValor(def.k);
    const padrao = PADROES[def.k];
    const salvar = opcoesExtra.aoAlterar || ((v) => definirValor(def.k, v));
    const idDica = id + "-dica", idErro = id + "-erro";
    const erros = opcoesExtra.erros || errosDoCampo(def.k);
    let entrada;
    const descr = [idDica, erros.length ? idErro : null].filter(Boolean).join(" ");
    const comum = { id, "aria-describedby": descr, "aria-invalid": erros.some((e) => e.nivel === "impeditivo") ? "true" : null, "aria-required": def.obrig ? "true" : null };
    if (def.tipo === "marca") {
      const marcado = valorAtual === undefined ? !!padrao : !!valorAtual;
      entrada = h("input", { type: "checkbox", ...comum, checked: marcado });
      entrada.addEventListener("change", () => salvar(entrada.checked));
      const lbl = h("label", { class: "marcacao", for: id }, entrada, h("span", {}, def.rotulo,
        valorAtual === undefined && padrao !== undefined ? h("span", { class: "sutil mini", text: " (padrão do PJe-Calc)" }) : null));
      return wrapCampo(def, lbl, null, aj, idDica, idErro, erros);
    }
    if (def.tipo === "lista" || def.tipo === "estado") {
      const ops = def.tipo === "estado" ? (E.opcoes?.estados || []).map((u) => ({ valor: u, rotulo: u })) : (Array.isArray(def.opcoes) ? def.opcoes : op(def.opcoes));
      const v = valorAtual === undefined ? (padrao ?? "") : valorAtual;
      entrada = h("select", comum, h("option", { value: "" }, def.vazio || (padrao !== undefined ? "Padrão do PJe-Calc" : "Selecione…")),
        ops.map((o) => h("option", { value: o.valor, selected: o.valor === v }, o.rotulo)));
      entrada.addEventListener("change", () => { salvar(entrada.value); if (def.tipo === "estado") { definirValor("local.municipio", ""); renderEtapa(); } else if (opcoesExtra.redesenhar !== false) renderEtapa(); });
    } else if (def.tipo === "municipio") {
      const uf = obterValor("local.estado");
      const lista = E.municipios[uf];
      if (uf && lista) {
        const dl = id + "-lista";
        entrada = h("input", { type: "text", list: dl, ...comum, value: valorAtual || "", autocomplete: "off" });
        entrada.addEventListener("change", () => {
          const ok = lista.find((m) => dobrar(m) === dobrar(entrada.value));
          if (ok) { entrada.value = ok; entrada.removeAttribute("aria-invalid"); } else if (entrada.value) entrada.setAttribute("aria-invalid", "true");
          salvar(ok || entrada.value);
        });
        return wrapCampo(def, h("label", { for: id }, def.rotulo, def.obrig ? h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" }) : null),
          h("div", {}, entrada, h("datalist", { id: dl }, lista.map((m) => h("option", { value: m })))), aj, idDica, idErro, erros,
          `${lista.length} municípios lidos do PJe-Calc para ${uf}.`);
      }
      entrada = h("input", { type: "text", ...comum, value: valorAtual || "", placeholder: uf ? "Carregando lista do PJe-Calc…" : "Escolha o estado primeiro" });
      entrada.addEventListener("change", () => salvar(entrada.value.toUpperCase()));
      if (uf && !lista && E.motor?.acessivel) carregarMunicipios(uf);
    } else if (def.tipo === "documento") {
      // CPF/CNPJ/CEI: pontos, barra e traço aparecem enquanto se digita; sem tipo escolhido, até 11 dígitos é CPF
      const tipoDoc = () => obterValor(def.tipoDe) || "";
      const dig0 = String(valorAtual || "").replace(/\D/g, "");
      entrada = h("input", { type: "text", ...comum, inputmode: "numeric", autocomplete: "off", value: dig0 ? formatarPadrao(dig0, padraoDoc(tipoDoc(), dig0)) : (valorAtual || ""),
        placeholder: tipoDoc() === "CNPJ" ? "00.000.000/0000-00" : tipoDoc() === "CEI" ? "00.000.00000/00" : "000.000.000-00" });
      mascaraDigitos(entrada, (dig) => padraoDoc(tipoDoc(), dig));
      entrada.addEventListener("change", () => {
        const dig = entrada.value.replace(/\D/g, "");
        let tipo = tipoDoc();
        // sem tipo escolhido: 11 dígitos válidos é CPF; 14 é CNPJ (e o tipo é escolhido sozinho)
        if (!tipo && dig && (dig.length === 11 || dig.length === 14)) { tipo = dig.length === 11 ? "CPF" : "CNPJ"; definirValor(def.tipoDe, tipo); }
        const prob = problemaDoc(tipo, dig);
        if (prob) { erroNoCampo(entrada, prob + " Este número ainda não foi salvo."); return; }
        erroNoCampo(entrada, null);
        salvar(dig ? formatarPadrao(dig, padraoDoc(tipo, dig)) : "");
        const sel = document.getElementById("f-" + def.tipoDe.replace(/[^\w]/g, "_"));
        if (sel && sel.value !== tipo) sel.value = tipo;
      });
    } else if (def.tipo === "area") {
      entrada = h("textarea", { ...comum }, valorAtual || "");
      entrada.addEventListener("input", () => salvar(entrada.value));
    } else {
      entrada = h("input", { type: "text", ...comum, value: valorAtual ?? "", inputmode: def.tipo === "moeda" || def.tipo === "inteiro" ? "decimal" : null,
        placeholder: def.tipo === "data" ? "DD/MM/AAAA" : def.tipo === "moeda" ? (padrao ? padrao + " (padrão)" : "0,00") : null, autocomplete: "off" });
      if (def.tipo === "data") mascaraData(entrada);
      entrada.addEventListener("input", () => { if (def.tipo !== "moeda" && def.tipo !== "data") salvar(entrada.value); });
      entrada.addEventListener("change", () => {
        let v = entrada.value.trim();
        if (def.tipo === "moeda" && v) { const n = window.normalizarValor(v); if (n === null) { erroNoCampo(entrada, `“${v}” não é um valor em reais. Digite com vírgula nos centavos, por exemplo 3.800,00. Este valor ainda não foi salvo.`); return; } v = n; entrada.value = n; }
        if (def.tipo === "data" && v && !dataValida(v)) { erroNoCampo(entrada, `“${v}” não é uma data válida. Use dia/mês/ano, com o ano em 4 dígitos, por exemplo 15/03/2021. Esta data ainda não foi salva.`); return; }
        if (def.tipo === "inteiro" && v && !/^\d+$/.test(v)) { erroNoCampo(entrada, `Use só números inteiros, por exemplo 45. Este valor ainda não foi salvo.`); return; }
        erroNoCampo(entrada, null);
        salvar(v);
      });
    }
    const label = h("label", { for: id }, def.rotulo, def.obrig ? h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" }) : null,
      def.obrig ? h("span", { class: "sr-only", text: " (obrigatório)" }) : aj?.obrigatorio === "nao" ? h("span", { class: "opcional", text: " (opcional)" }) : null);
    return wrapCampo(def, label, entrada, aj, idDica, idErro, erros);
  }

  function wrapCampo(def, label, entrada, aj, idDica, idErro, erros, dicaExtra) {
    const cab = h("div", { class: "rotulo" }, label, botaoAjuda(def.ajuda || def.k, def.rotulo),
      aj?.decisao ? h("span", { class: "decisao", title: "Escolha que depende do caso concreto e do título executivo", text: "decisão profissional" }) : null);
    const wrap = h("div", { class: "campo " + (def.largura || "") + (def.avancado ? " so-avancado" : ""), dataset: { campo: def.k } }, cab, entrada,
      h("span", { class: "dica", id: idDica, text: dicaExtra || def.dica || aj?.essencial || "" }),
      erros.length ? h("span", { class: "erro-campo", id: idErro, role: "alert" }, erros.map((e) => e.texto).join(" ")) : null);
    if (aj?.decisao && !def.k.startsWith("meta.")) wrap.appendChild(botaoFundamento(def.k, def.rotulo));
    return wrap;
  }

  function botaoFundamento(chave, rotulo) {
    const atual = (E.caso.rascunho.decisoes || []).find((d) => d.campo === chave);
    return h("button", { type: "button", class: "botao leve pequeno", style: "align-self:flex-start;padding-left:0",
      onclick: () => editarFundamento(chave, rotulo) }, atual ? "✎ Fundamento registrado" : "+ Registrar fundamento da escolha");
  }
  async function editarFundamento(chave, rotulo) {
    const lista = E.caso.rascunho.decisoes = E.caso.rascunho.decisoes || [];
    const atual = lista.find((d) => d.campo === chave) || { campo: chave, texto: "", trecho: "", documento: "" };
    const t = h("textarea", { id: "fdTexto" }, atual.texto), tr = h("textarea", { id: "fdTrecho" }, atual.trecho), doc = h("input", { type: "text", id: "fdDoc", value: atual.documento || "" });
    const ok = await dialogo({ titulo: "Fundamento: " + rotulo, corpo: h("div", { class: "grade" },
      h("div", { class: "campo inteiro" }, h("label", { for: "fdTexto", text: "Justificativa da escolha" }), t),
      h("div", { class: "campo inteiro" }, h("label", { for: "fdTrecho", text: "Trecho da decisão ou do documento" }), tr),
      h("div", { class: "campo inteiro" }, h("label", { for: "fdDoc", text: "Referência (ex.: sentença, ID 1234, fl. 5)" }), doc)),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Salvar fundamento", valor: true, classe: "primario" }] });
    if (!ok) return;
    const novo = { campo: chave, rotulo, texto: t.value, trecho: tr.value, documento: doc.value };
    const i = lista.findIndex((d) => d.campo === chave);
    if (i >= 0) lista[i] = novo; else lista.push(novo);
    agendarSalvamento(); renderEtapa();
  }

  async function carregarMunicipios(uf) {
    if (E.carregandoUf === uf) return;
    E.carregandoUf = uf;
    try { const r = await api("GET", "/api/municipios?estado=" + uf); E.municipios[uf] = r.municipios; if (E.etapa === "identificacao") renderEtapa(); }
    catch (e) { avisar("Não foi possível ler os municípios do PJe-Calc: " + e.message, "alerta"); }
    finally { E.carregandoUf = null; }
  }

  // Nada fica escondido: as opções menos usadas vão para "Mais opções", fechado no modo Guiado
  // (aberto no Avançado ou quando alguma delas já tem valor), com a quantidade e o motivo de normalmente não mexer.
  function maisOpcoes(campos, textoResumo) {
    if (!campos.length) return null;
    const preenchidas = campos.filter((c) => { const v = obterValor(c.k); return v !== undefined && v !== ""; }).length;
    return h("details", { class: "mais-opcoes", open: modoAvancado() || preenchidas ? true : null },
      h("summary", {}, `Mais ${campos.length} opç${campos.length > 1 ? "ões" : "ão"}`, h("span", { class: "sutil mini", text: preenchidas ? ` · ${preenchidas} preenchida(s)` : ` · ${textoResumo || "normalmente ficam como estão; abra se a sentença tratar disso"}` })),
      h("div", { class: "grade" }, campos.map((c) => campo({ ...c, avancado: false }))));
  }
  function grupoCampos(g) {
    const campos = (g.campos || []).filter((c) => !c.seCampo || (obterValor(c.seCampo[0]) ?? PADROES[c.seCampo[0]]) === c.seCampo[1]);
    const idt = "g-" + dobrar(g.titulo).replace(/\W/g, "");
    if (g.avancado) return h("section", { class: "cartao", "aria-labelledby": idt },
      h("h2", { id: idt, text: g.titulo }), g.nota ? h("p", { class: "sutil mini", text: g.nota }) : null,
      maisOpcoes(campos, "ajustes que o PJe-Calc já traz prontos; mude só se o documento do caso exigir"));
    return h("section", { class: "cartao", "aria-labelledby": idt },
      h("h2", { id: idt, text: g.titulo }), g.nota ? h("p", { class: "sutil mini", text: g.nota }) : null,
      h("div", { class: "grade" }, campos.filter((c) => !c.avancado).map((c) => campo(c))),
      maisOpcoes(campos.filter((c) => c.avancado)));
  }

  // ============================================================================ ajuda contextual
  // Botão "?" junto ao rótulo: abre por clique, toque ou teclado (Enter/Espaço; F1 no campo em foco).
  // No computador abre ao lado do formulário (sem cobrir campos); em telas estreitas, como folha inferior.
  function botaoAjuda(chave, rotulo, texto = "?") {
    if (!window.AJUDA[chave]) return null;
    // "Última remuneração (R$)" -> "última remuneração"; siglas no início (CNJ, FGTS) são mantidas
    const nome = rotulo.replace(/\s*\([^)]*\)\s*$/, "");
    const falado = /^[A-ZÀ-Ý]{2}/.test(nome) ? nome : nome.charAt(0).toLowerCase() + nome.slice(1);
    return h("button", { type: "button", class: "ajuda-btn", "aria-label": `Ajuda sobre ${falado}`, "aria-controls": "painelAjuda", "aria-expanded": "false",
      title: "Ajuda (F1)", dataset: { ajuda: chave }, onclick: (e) => abrirAjuda(chave, rotulo, e.currentTarget) }, texto);
  }
  function abrirAjuda(chave, rotulo, origem) {
    const a = window.AJUDA[chave];
    const painel = $("#painelAjuda");
    if (!a) return;
    if (E.ajudaOrigem && E.ajudaOrigem !== origem) E.ajudaOrigem.setAttribute("aria-expanded", "false");
    E.ajudaOrigem = origem || null;
    origem?.setAttribute("aria-expanded", "true");
    const nomeOficial = (window.AJUDA_OFICIAL_CAMPO || {})[chave] || CAMPO_OFICIAL[chave];
    const oficiais = (E.ajudaOficial || []).filter((o) => o.campo && (o.campo === nomeOficial || chave.endsWith("." + o.campo)));
    const idT = novoId("aj");
    painel.setAttribute("aria-labelledby", idT);
    painel.setAttribute("role", "region");
    const sec = (titulo, ...conteudo) => conteudo.some(Boolean) ? h("section", {}, h("h3", { text: titulo }), ...conteudo) : null;
    const exemplo = (ex) => ex ? h("div", { class: "exemplo" }, h("p", { text: ex.situacao }), h("p", { style: "margin:0" }, "Preencha: ", h("span", { class: "valor", text: ex.valor }))) : null;
    const obrig = a.obrigatorio === "sim" ? "Obrigatório" : a.obrigatorio === "nao" ? "Opcional" : a.obrigatorio || null;
    preencher(painel,
      h("div", { class: "ajuda-cab" }, h("div", { style: "flex:1;min-width:0" }, h("span", { class: "eyebrow", text: "Ajuda" }), h("h2", { id: idT, text: rotulo || chave })),
        h("button", { type: "button", class: "botao-icone", "aria-label": "Fechar ajuda", onclick: () => fecharAjuda(true) }, "×")),
      h("div", { class: "marcas" }, obrig ? h("span", { class: "pill " + (a.obrigatorio === "sim" ? "pill-alerta" : "pill-neutro"), text: obrig }) : null,
        a.decisao ? h("span", { class: "pill pill-info", text: "Depende de decisão profissional" }) : null),
      h("p", { class: "resposta", text: a.essencial }),
      sec("O que é", a.oQue ? h("p", { text: a.oQue }) : null),
      sec("Quando preencher", a.quando ? h("p", { text: a.quando }) : null),
      sec("Como preencher", a.como ? h("p", { text: a.como }) : null),
      sec("Exemplo preenchido", exemplo(a.exemplo)),
      a.outroExemplo ? h("details", {}, h("summary", {}, "Outro exemplo"), exemplo(a.outroExemplo)) : null,
      sec("Erro comum", a.erroComum ? h("p", { text: a.erroComum }) : null),
      a.vazio ? h("details", { open: true }, h("summary", {}, "Vazio, zero e “não se aplica”"), h("p", { text: a.vazio })) : null,
      a.automatico ? h("details", {}, h("summary", {}, "Valor automático"), h("p", { text: a.automatico })) : null,
      sec("Efeito no cálculo", a.efeito ? h("p", { text: a.efeito }) : null),
      a.textoOficialPronto ? sec("Ajuda oficial do PJe-Calc", h("p", { class: "oficial", text: a.textoOficialPronto })) : null,
      a.decisao ? h("p", { class: "mini sutil" }, "A escolha depende do caso concreto e do título executivo. ",
        h("span", { text: chave.startsWith("pj") ? "Anote o fundamento nas observações internas do cálculo (etapa Partes e processo)." : "Registre o fundamento no campo." })) : null,
      a.duvida ? h("div", { class: "duvida" }, h("strong", { text: "Ponto não confirmado nesta interface: " }), a.duvida) : null,
      (a.referencias?.length || oficiais.length || a.oficial) ? h("details", {}, h("summary", {}, "Referências"),
        a.oficial ? h("p", { class: "mini" }, "No PJe-Calc: ", h("strong", { text: a.oficial })) : null,
        oficiais.map((o) => h("div", { class: "oficial" }, h("strong", { class: "mini", text: "Ajuda oficial do PJe-Calc: " }), o.texto)),
        a.textoOficial && !oficiais.length ? h("p", { class: "mini sutil", text: "O PJe-Calc tem um texto de ajuda oficial para este campo. Informe a pasta de instalação em Configurações para exibi-lo aqui." }) : null,
        a.referencias?.length ? h("ul", { class: "lista-simples mini" }, a.referencias.map((f) => h("li", { text: f }))) : null,
        h("p", { class: "mini sutil", text: `Conteúdo revisado em ${window.AJUDA_REVISAO}. Referências “para conferência” não foram validadas por esta interface.` })) : null);
    painel.hidden = false;
    document.querySelector(".corpo").classList.add("com-ajuda");
    E.ajudaAberta = chave;
    // em tela estreita a ajuda ocupa a parte de baixo: mantém o campo visível no alto
    if (origem && matchMedia("(max-width: 960px)").matches) origem.closest(".campo, section, article")?.scrollIntoView({ block: "start" });
    const t = painel.querySelector("h2"); t.tabIndex = -1; t.focus({ preventScroll: true });
  }
  function fecharAjuda(devolverFoco) {
    const p = $("#painelAjuda");
    if (p.hidden) return;
    p.hidden = true; document.querySelector(".corpo").classList.remove("com-ajuda"); E.ajudaAberta = null;
    const o = E.ajudaOrigem; E.ajudaOrigem = null;
    if (o) { o.setAttribute("aria-expanded", "false"); if (devolverFoco && document.contains(o)) o.focus(); }
  }
  const CAMPO_OFICIAL = { "contrato.ultimaRemuneracao": "valorUltimaRemuneracao", "historico": "fgts", "atualizacao.aplicarJurosFasePreJudicial": "aplicarJurosFasePreJudicial",
    "atualizacao.baseDeJurosDasVerbas": "baseDeJurosDasVerbas", "base": "integralizarBase" };
  // mensagem de erro junto ao campo, ligada a ele por aria-describedby
  function erroNoCampo(entrada, texto) {
    const wrap = entrada.closest(".campo"); if (!wrap) return;
    const id = entrada.id + "-erro-local";
    let span = document.getElementById(id);
    if (!texto) { span?.remove(); entrada.removeAttribute("aria-invalid"); entrada.setAttribute("aria-describedby", (entrada.getAttribute("aria-describedby") || "").replace(id, "").trim()); return; }
    if (!span) { span = h("span", { class: "erro-campo", id, role: "alert" }); wrap.appendChild(span); }
    span.textContent = texto;
    entrada.setAttribute("aria-invalid", "true");
    if (!(entrada.getAttribute("aria-describedby") || "").includes(id)) entrada.setAttribute("aria-describedby", ((entrada.getAttribute("aria-describedby") || "") + " " + id).trim());
  }

  // ============================================================================ salvamento automático, revisões e recuperação
  // Cada edição incrementa E.versaoLocal. Um salvamento só marca "salvo" se nenhuma edição tiver ocorrido
  // enquanto a requisição estava em curso; caso contrário, salva de novo. A cópia local de recuperação só é
  // apagada quando o servidor confirmou exatamente o que está na tela.
  const chavePendente = (id) => "pjstudio:pendente:" + id;
  const meta = (c) => ({ titulo: c.titulo, cliente: c.cliente, parteContraria: c.parteContraria, processo: c.processo, responsavel: c.responsavel, etiquetas: c.etiquetas, observacoes: c.observacoes });
  function guardarCopiaLocal() {
    try { localStorage.setItem(chavePendente(E.caso.id), JSON.stringify({ revisaoBase: E.caso.revisao, em: new Date().toISOString(), caso: meta(E.caso), rascunho: E.caso.rascunho })); return true; }
    catch { return false; }
  }
  function agendarSalvamento() {
    if (!E.caso) return;
    E.versaoLocal = (E.versaoLocal || 0) + 1;
    E.pendente = true;
    E.copiaLocal = guardarCopiaLocal();
    atualizarBarra();
    clearTimeout(E.timer);
    if (!E.conflito) E.timer = setTimeout(() => salvarAgora(), 1200);
  }
  // Devolve true quando tudo o que está na tela foi persistido no servidor.
  async function salvarAgora() {
    if (!E.caso) return true;
    clearTimeout(E.timer);
    if (E.promessaSalvar) await E.promessaSalvar;  // espera a gravação em curso e depois confere o que sobrou
    if (!E.pendente) return true;
    if (E.conflito) return false;
    E.promessaSalvar = salvarUmaVez().finally(() => { E.promessaSalvar = null; });
    await E.promessaSalvar;
    if (E.pendente && !E.conflito && !E.erroSalvar) return salvarAgora();  // houve edição durante a gravação
    return !E.pendente;
  }
  async function salvarUmaVez() {
    const caso = E.caso, versao = E.versaoLocal || 0;
    E.salvando = true; atualizarBarra();
    const proc = numeroProcesso(caso.rascunho.dados || {}) || caso.processo;
    const corpo = JSON.parse(JSON.stringify({ revisaoBase: caso.revisao, rascunho: caso.rascunho, ...meta(caso), processo: proc }));
    try {
      const r = await api("PUT", `/api/casos/${caso.id}`, corpo);
      if (E.caso !== caso) return;  // o usuário já abriu outro cálculo
      // preserva o que foi digitado durante a requisição (rascunho e organização interna)
      const local = { rascunho: caso.rascunho, ...meta(caso) };
      E.caso = Object.assign(r.caso, local); E.estadoRes = r.estado;
      E.erroSalvar = null;
      if ((E.versaoLocal || 0) === versao) {
        E.pendente = false; E.ultimoSalvo = new Date();
        try { localStorage.removeItem(chavePendente(caso.id)); } catch { /* ok */ }
      } else {
        E.copiaLocal = guardarCopiaLocal();  // continua pendente: a cópia passa a apontar para a revisão nova
      }
      conferirDepois();
    } catch (e) {
      if (e.status === 409) { E.conflito = { revisaoServidor: e.dados?.revisaoAtual }; resolverConflito(); }
      else { E.erroSalvar = e.rede ? "o servidor local do Studio não respondeu" : e.message;
        avisar(`O rascunho não foi salvo: ${E.erroSalvar}. Suas alterações continuam nesta janela${E.copiaLocal ? " e numa cópia de recuperação neste computador" : ""}. Use “Tentar salvar de novo”.`, "erro", 12000); }
    } finally { E.salvando = false; atualizarBarra(); }
  }
  async function tentarSalvarDeNovo() { E.erroSalvar = null; const ok = await salvarAgora(); if (ok) avisar("Rascunho salvo.", "ok"); }

  // Conflito de revisão (o cálculo mudou em outra janela): nada é descartado sem escolha explícita.
  async function resolverConflito(p) {
    const local = p || { revisaoBase: E.caso.revisao, em: new Date().toISOString(), caso: meta(E.caso), rascunho: E.caso.rascunho };
    const id = E.caso.id;
    const atual = (await api("GET", `/api/casos/${id}`)).caso;
    const escolha = await dialogo({ titulo: "Este cálculo foi alterado em outra janela", corpo: h("div", {},
      h("p", { text: `As alterações feitas aqui (sobre a revisão ${local.revisaoBase}, em ${quando(local.em)}) não foram salvas, porque o cálculo já está na revisão ${atual.revisao}, salva em outra janela ou por outra pessoa.` }),
      h("p", { text: "Escolha o que fazer com as suas alterações. Enquanto você não decidir, elas ficam guardadas neste computador." }),
      h("ul", { class: "lista-simples" },
        h("li", {}, h("strong", { text: "Salvar como novo cálculo: " }), "mantém as duas versões; suas alterações vão para uma cópia."),
        h("li", {}, h("strong", { text: "Substituir pela minha versão: " }), `a revisão ${atual.revisao} da outra janela é substituída pela sua (ela continua no histórico de versões).`),
        h("li", {}, h("strong", { text: "Descartar as minhas: " }), "abre a versão mais recente e apaga a cópia guardada."))),
      botoes: [{ texto: "Decidir depois", valor: "depois" }, { texto: "Descartar as minhas", valor: "descartar", classe: "perigo" },
        { texto: "Substituir pela minha versão", valor: "substituir" }, { texto: "Salvar como novo cálculo", valor: "copia", classe: "primario" }] });
    try { localStorage.setItem(chavePendente(id), JSON.stringify(local)); } catch { /* ok */ }
    if (escolha === "copia") {
      const dup = (await api("POST", `/api/casos/${id}/duplicar`, { cenario: true })).caso;
      await api("PUT", `/api/casos/${dup.id}`, { revisaoBase: dup.revisao, rascunho: local.rascunho, ...local.caso, titulo: (local.caso.titulo || "Cálculo") + " (minhas alterações)" });
      try { localStorage.removeItem(chavePendente(id)); } catch { /* ok */ }
      E.conflito = null; E.pendente = false; E.caso = null;
      avisar("Suas alterações foram salvas num novo cálculo. O original ficou como estava na outra janela.", "ok", 9000);
      location.hash = `#/caso/${dup.id}/${E.etapa || "identificacao"}`;
    } else if (escolha === "substituir") {
      await api("PUT", `/api/casos/${id}`, { revisaoBase: atual.revisao, rascunho: local.rascunho, ...local.caso });
      try { localStorage.removeItem(chavePendente(id)); } catch { /* ok */ }
      E.conflito = null; E.pendente = false; E.caso = null; avisar("Sua versão foi salva.", "ok"); navegar();
    } else if (escolha === "descartar") {
      if (!(await confirmar("Descartar suas alterações", "As alterações desta janela serão apagadas definitivamente. Continuar?", "Descartar", true))) return resolverConflito(local);
      try { localStorage.removeItem(chavePendente(id)); } catch { /* ok */ }
      E.conflito = null; E.pendente = false; E.caso = null; navegar();
    } else {
      E.conflito = E.conflito || { revisaoServidor: atual.revisao };
      atualizarBarra();
    }
  }
  let tConf;
  function conferirDepois() {
    clearTimeout(tConf);
    tConf = setTimeout(async () => {
      if (!E.caso) return;
      try { E.conferencia = await api("GET", `/api/casos/${E.caso.id}/conferir`); desenharLateralCaso(); atualizarAvisosNaTela(); } catch { /* ignora */ }
    }, 400);
  }
  window.addEventListener("beforeunload", (e) => { if (E.pendente) { e.preventDefault(); e.returnValue = ""; } });

  async function verificarRecuperacao() {
    let p; try { p = JSON.parse(localStorage.getItem(chavePendente(E.caso.id))); } catch { p = null; }
    if (!p) return;
    // cópia feita sobre uma revisão que já não é a atual: nunca descartar em silêncio
    if (p.revisaoBase !== E.caso.revisao) { E.conflito = { revisaoServidor: E.caso.revisao }; return resolverConflito(p); }
    const sim = await dialogo({ titulo: "Recuperar alterações não salvas?", corpo: h("p", { text: `Há alterações feitas em ${quando(p.em)} que não chegaram a ser salvas (a janela foi fechada ou o servidor estava indisponível).` }),
      botoes: [{ texto: "Descartar alterações", valor: false, classe: "perigo" }, { texto: "Recuperar alterações", valor: true, classe: "primario" }] });
    if (sim) { E.caso.rascunho = p.rascunho; Object.assign(E.caso, p.caso); agendarSalvamento(); avisar("Alterações recuperadas.", "ok"); }
    else { const ok = await confirmar("Descartar alterações", "Descartar definitivamente as alterações não salvas?", "Descartar", true); if (ok) { try { localStorage.removeItem(chavePendente(E.caso.id)); } catch { /* ok */ } } else return verificarRecuperacao(); }
  }

  // ============================================================================ tela do cálculo
  async function telaCaso(id, etapa, sub) {
    if (!E.caso || E.caso.id !== id) {
      const r = await api("GET", `/api/casos/${id}`);
      E.caso = r.caso; E.estadoRes = r.estado; E.criterios = null; E.conferencia = null;
      E.pendente = false; E.conflito = null; E.erroSalvar = null; E.versaoLocal = 0; E.ultimoSalvo = null; E.assuntosCnj = null;
      await verificarRecuperacao();
      if (!E.caso) return;  // a recuperação abriu outro cálculo
      try { E.conferencia = await api("GET", `/api/casos/${id}/conferir`); } catch { /* segue */ }
    }
    E.etapa = etapa === "original" ? "original:" + (sub || "dados") : (etapa || E.caso.etapaAtual || "identificacao");
    if (E.etapa !== "historico-auditoria" && !E.etapa.startsWith("original:") && E.caso.etapaAtual !== E.etapa) {
      E.caso.etapaAtual = E.etapa;
      api("PUT", `/api/casos/${id}`, { etapaAtual: E.etapa }).catch(() => {});
    }
    E.sub = sub;
    desenharLateralCaso();
    await renderEtapa();
  }

  function contagemEtapa(et) {
    const av = (E.conferencia?.avisos || []).filter((a) => a.etapa === et);
    const oficiais = et === "conferencia" && E.conferencia?.pendenciasAtuais ? (E.conferencia.pendenciasPjecalc || []).filter((m) => m.severidade === "erro") : [];
    return { erros: av.filter((a) => a.nivel === "impeditivo").length + oficiais.length, alertas: av.filter((a) => a.nivel === "alerta").length };
  }
  // Estado real de cada etapa (nunca "concluída" só por ter sido visitada):
  //   ok = dados exigidos preenchidos e válidos · andamento = preenchida em parte · padrao = etapa opcional sem alteração
  //   vazio = nada informado · bloqueada = depende de uma etapa anterior · erro/alerta = conferência apontou problemas
  function estadoEtapa(et) {
    const r = E.caso.rascunho, d = r.dados || {}, est = E.estadoRes || {}, vinc = E.caso.pjecalc || {};
    const c = contagemEtapa(et);
    const temRes = !!est.ultimaExecucao, resOk = !!est.resultadoAtual && !E.pendente;
    const conta = (ks) => ks.filter((k) => d[k] !== undefined && d[k] !== "").length;
    let s;
    switch (et) {
      case "identificacao": { const n = conta(["reclamante.nome", "reclamado.nome", "local.estado", "local.municipio"]);
        s = n === 4 ? ["ok", "Partes e local informados"] : n ? ["andamento", `Faltam ${4 - n} de 4 campos obrigatórios`] : ["vazio", "Não iniciada"]; break; }
      case "contrato": { const n = conta(["contrato.dataAdmissao", "contrato.dataAjuizamento"]);
        s = n === 2 ? ["ok", "Datas principais informadas"] : n || conta(["contrato.dataDemissao", "contrato.ultimaRemuneracao"]) ? ["andamento", "Faltam admissão ou ajuizamento"] : ["vazio", "Não iniciada"]; break; }
      case "historico": { const hs = (r.historicos || []).filter((x) => (x.ocorrencias || []).length);
        s = hs.length ? ["ok", `${hs.length} histórico(s) com valores`] : d["contrato.ultimaRemuneracao"] ? ["ok", "Usa só a última remuneração do contrato"] : ["vazio", "Nenhum valor mensal informado"]; break; }
      case "jornada": s = d["jornada.cargaHorariaPadrao"] || d["jornada.sabadoDiaUtil"] !== undefined ? ["ok", "Carga horária definida"] : ["padrao", "Sem alteração: vale o padrão do PJe-Calc (220 h)"]; break;
      case "verbas": { const n = (r.verbas || []).length + (r.verbasManuais || []).filter((v) => v.descricao).length;
        s = n ? ["ok", `${n} verba(s)`] : ["vazio", "Nenhuma verba escolhida"]; break; }
      case "reflexos": { const alterou = Object.values(r.verbasConfig || {}).some((x) => Object.keys(x.reflexos || {}).length || Object.keys(x.alteracoes || {}).length) || Object.keys(r.fgts || {}).length;
        s = alterou ? ["ok", "Reflexos, incidências ou FGTS ajustados"] : vinc.calculoId ? ["padrao", "Sem alteração: valem as escolhas padrão do PJe-Calc"] : ["padrao", "Reflexos aparecem depois do primeiro envio; FGTS pode ser ajustado já"]; break; }
      case "atualizacao": { const at = r.atualizacao || {};
        s = (r.liquidacao || {}).data || Object.keys(at.valores || {}).length ? ["ok", "Data ou critérios definidos"] : ["padrao", "Sem alteração: o PJe-Calc sugere a data e mantém os critérios"]; break; }
      case "outros": { const resp = r.outrosItens || {}; const n = OUTROS_ITENS.filter((i) => resp[i.id]).length, faltam = OUTROS_ITENS.filter((i) => resp[i.id] === "sim").length;
        s = n === OUTROS_ITENS.length && !faltam ? ["ok", "Todos os itens respondidos"] : n ? ["andamento", `${OUTROS_ITENS.length - n} pergunta(s) sem resposta${faltam ? ` · ${faltam} a preencher` : ""}`] : ["vazio", "Nenhuma pergunta respondida"]; break; }
      case "conferencia": s = !vinc.calculoId ? ["andamento", "Revise antes do primeiro envio"] : est.gravadoAtual && !E.pendente ? ["ok", "Dados enviados conferidos"] : ["andamento", "Há alterações a revisar e enviar"]; break;
      case "calculo": s = resOk ? ["ok", "Resultado atualizado"] : temRes ? ["alerta", "Resultado desatualizado: calcule de novo"] : vinc.calculoId ? ["andamento", "Enviado; falta calcular"] : ["vazio", "Ainda não enviado"]; break;
      case "resultado": case "exportacao": s = resOk ? ["ok", et === "resultado" ? "Resultado atualizado" : "Documentos do resultado atual"] : temRes ? ["alerta", "Do resultado anterior (desatualizado)"] : ["bloqueada", "Disponível depois de calcular"]; break;
      default: s = ["vazio", ""];
    }
    if (c.erros) s = ["erro", `${c.erros} pendência(s) que impedem o envio`];
    else if (c.alertas && s[0] !== "vazio") s = [s[0] === "ok" ? "alerta" : s[0], `${s[1]} · ${c.alertas} alerta(s) para avaliar`];
    return { estado: s[0], texto: s[1], ...c };
  }
  const ROTULO_ESTADO = { ok: "pronta", andamento: "em andamento", padrao: "usa o padrão", vazio: "não iniciada", bloqueada: "aguardando etapa anterior", erro: "com pendências", alerta: "com alertas" };
  function etapaConcluida(et) { return estadoEtapa(et).estado === "ok"; }

  function desenharLateralCaso() {
    if (!E.caso) return;
    const fases = h("ol", { class: "fases", "aria-label": "Fases do cálculo" }, FASES.map((f, fi) => {
      const ets = ETAPAS.filter((e) => e.fase === f.id);
      return h("li", { class: "fase" }, h("h2", { class: "fase-titulo", id: "fase-" + f.id }, h("span", { class: "fase-num", "aria-hidden": "true", text: fi + 1 + "." }), f.titulo),
        h("ol", { class: "etapas", "aria-labelledby": "fase-" + f.id }, ets.map((e) => {
          const s = estadoEtapa(e.id);
          return h("li", { class: "etapa-" + s.estado }, h("a", { href: `#/caso/${E.caso.id}/${e.id}`, "aria-current": E.etapa === e.id ? "step" : null,
            title: s.texto, "aria-label": `${e.titulo}: ${ROTULO_ESTADO[s.estado]}${s.texto ? ". " + s.texto : ""}` },
            h("span", { class: "etapa-marca", "aria-hidden": "true", text: s.estado === "ok" ? "✓" : s.estado === "erro" ? "!" : "" }),
            h("span", { text: e.titulo }),
            s.erros ? h("span", { class: "etapa-contagem", "aria-hidden": "true", text: s.erros }) : s.alertas ? h("span", { class: "etapa-contagem alerta", "aria-hidden": "true", text: s.alertas }) : null));
        })));
    }));
    const leg = (cls, t) => h("li", { class: "etapa-" + cls }, h("span", { class: "etapa-marca", "aria-hidden": "true", text: cls === "ok" ? "✓" : cls === "erro" ? "!" : "" }), t);
    preencher($("#lateral"),
      h("a", { href: "#/", class: "voltar" }, icone("voltar"), "Todos os cálculos"),
      fases,
      h("ul", { class: "legenda-etapas", "aria-label": "Legenda" }, leg("ok", "pronta"), leg("andamento", "em andamento"), leg("padrao", "opcional, usa o padrão"), leg("erro", "com pendência")),
      h("h2", { text: "Funções do PJe-Calc" }), navOriginal(E.etapa),
      h("h2", { text: "Mais" }),
      h("div", { class: "links" },
        h("a", { href: `#/comparar?a=${E.caso.cenarioDe || E.caso.id}&b=${E.caso.id}` }, icone("comparar"), "Comparar cenários"),
        h("a", { href: `#/caso/${E.caso.id}/historico-auditoria`, "aria-current": E.etapa === "historico-auditoria" ? "page" : null }, icone("versoes"), "Versões e alterações"),
        h("button", { type: "button", class: "link-botao", onclick: aplicarPadroesNoCaso }, icone("padroes"), "Aplicar padrões do escritório"),
        h("button", { type: "button", class: "link-botao", onclick: salvarComoModelo }, icone("modelos"), E.caso.edicaoModelo ? "Salvar modelo" : "Salvar como modelo")));
  }

  // Quatro estados distintos e sempre visíveis: rascunho salvo · envio ao PJe-Calc · resultado
  function estadosTrabalho() {
    const est = E.estadoRes || {}, vinc = E.caso.pjecalc || {};
    const hora = (d) => d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    let rasc;
    if (E.conflito) rasc = { cls: "erro", rot: "Rascunho", t: "não salvo: o cálculo mudou em outra janela", acao: h("button", { type: "button", class: "botao leve pequeno", onclick: () => resolverConflito() }, "Resolver") };
    else if (E.erroSalvar) rasc = { cls: "erro", rot: "Rascunho", t: "não salvo (" + E.erroSalvar + ")", acao: h("button", { type: "button", class: "botao leve pequeno", onclick: tentarSalvarDeNovo }, "Tentar salvar de novo") };
    else if (E.salvando) rasc = { cls: "progresso", rot: "Rascunho", t: "salvando…" };
    else if (E.pendente) rasc = { cls: "alerta", rot: "Rascunho", t: "alterações ainda não salvas" };
    else rasc = { cls: "ok", rot: "Rascunho", t: E.ultimoSalvo ? "salvo às " + hora(E.ultimoSalvo) : "salvo" };
    const enviado = vinc.calculoId && est.gravadoAtual && !E.pendente;
    const pj = !vinc.calculoId ? { cls: "", rot: "PJe-Calc", t: "dados ainda não enviados" }
      : enviado ? { cls: "ok", rot: "PJe-Calc", t: `dados enviados (cálculo nº ${vinc.calculoId})` }
      : { cls: "alerta", rot: "PJe-Calc", t: `há alterações não enviadas (cálculo nº ${vinc.calculoId})` };
    const res = !est.ultimaExecucao ? { cls: "", rot: "Resultado", t: "ainda não calculado" }
      : est.resultadoAtual && !E.pendente && est.abertoNoOriginalDepois ? { cls: "alerta", rot: "Resultado", t: "pode estar desatualizado: algo foi salvo numa função do PJe-Calc depois do cálculo; se mudou algum valor, calcule de novo" }
      : est.resultadoAtual && !E.pendente ? { cls: "ok", rot: "Resultado", t: "atualizado" }
      : { cls: "erro", rot: "Resultado", t: "desatualizado: os dados mudaram depois do cálculo" };
    return [rasc, pj, res];
  }
  function atualizarBarra() {
    if (!E.caso || !location.hash.includes("/caso/")) return;
    const lista = $("#estadosCaso");
    if (lista) preencher(lista, estadosTrabalho().map((s) => h("li", { class: "estado-item " + s.cls }, h("span", { class: "ponto", "aria-hidden": "true" }), h("strong", { text: s.rot + ":" }), " " + s.t, s.acao || null)));
    const salvo = $("#salvoRodape");
    if (salvo) { const s = estadosTrabalho()[0]; salvo.className = "salvo" + (s.cls === "erro" ? " erro" : ""); preencher(salvo, h("span", { text: `Rascunho ${s.t}` }), s.acao ? s.acao.cloneNode(true) : null);
      const b = salvo.querySelector("button"); if (b) b.onclick = E.conflito ? () => resolverConflito() : tentarSalvarDeNovo; }
  }
  function cabecalhoCaso() {
    const d = E.caso.rascunho.dados || {};
    const partes = [d["reclamante.nome"], d["reclamado.nome"]].filter(Boolean).join(" × ");
    const proc = numeroProcesso(d) ? "Processo " + numeroProcesso(d) : "";
    const ed = E.caso.edicaoModelo;
    const faixaModelo = ed ? h("div", { class: "faixa info faixa-modelo" }, h("strong", { text: `Editando o modelo “${ed.nome}”${ed.categoria ? ` (${ed.categoria})` : ""}.` }),
      h("div", { text: "Preencha as etapas com o que se repete nesse tipo de trabalho. Partes, processo e documentos não entram no modelo." }),
      h("button", { type: "button", class: "botao pequeno primario", onclick: salvarComoModelo }, "Salvar modelo")) : null;
    return h("div", {}, faixaModelo, h("header", { class: "cabecalho-caso", "aria-label": ed ? "Modelo em edição" : "Cálculo aberto" },
      h("div", { class: "ident" }, h("p", { class: "titulo-caso", text: E.caso.titulo || "Cálculo sem título" }),
        h("p", { class: "partes", text: [partes || "Partes ainda não informadas", proc].filter(Boolean).join(" · ") })),
      h("div", { class: "acoes" },
        h("button", { type: "button", class: "botao", onclick: () => operar("gravar"), title: "Preenche as telas oficiais do PJe-Calc com os dados deste rascunho" }, "Enviar ao PJe-Calc"),
        h("button", { type: "button", class: "botao primario", onclick: () => operar("executar"), "aria-keyshortcuts": "Control+Enter", title: "Envia o que faltar e executa o cálculo oficial (Ctrl+Enter)" }, "Calcular")),
      h("ul", { class: "estados", id: "estadosCaso", "aria-label": "Situação do trabalho", "aria-live": "polite" })));
  }

  let renderSeq = 0;
  async function renderEtapa() {
    const seq = ++renderSeq;
    const main = $("#conteudo");
    const et = ETAPAS.find((e) => e.id === E.etapa);
    // Ao trocar de etapa, uma etapa que dependa do PJe-Calc (telas oficiais, por exemplo) pode levar segundos: o
    // clique responde na hora com "Carregando…" em vez de deixar a etapa anterior parada na tela. Redesenhar a
    // mesma etapa não troca o conteúdo (não tira o foco nem a rolagem).
    const desenho = `${E.caso?.id}/${E.etapa}`;
    const espera = desenho !== E.desenhada ? setTimeout(() => {
      if (seq !== renderSeq) return;
      E.desenhada = null;
      preencher(main, h("div", { class: "area" }, cabecalhoCaso(), h("p", { class: "carregando", role: "status", text: `Carregando ${et ? et.titulo : "a etapa"}…` })));
    }, 200) : null;
    let conteudo;
    try {
      if (E.etapa === "historico-auditoria") conteudo = await etapaAuditoria();
      else if (E.etapa.startsWith("original:")) conteudo = await etapaOriginal(E.etapa.slice(9));
      else conteudo = await ({ identificacao: etapaFormulario, contrato: etapaFormulario, jornada: etapaJornada, historico: etapaHistorico, verbas: etapaVerbas,
        reflexos: etapaReflexos, atualizacao: etapaAtualizacao, outros: etapaOutros, conferencia: etapaConferencia, calculo: etapaCalculo, resultado: etapaResultado, exportacao: etapaExportacao }[E.etapa] || etapaFormulario)();
    } catch (e) {
      // uma falha numa etapa não deixa a tela parada: mostra o motivo e permite tentar de novo
      console.error(e);
      conteudo = h("div", { class: "faixa erro", role: "alert" }, h("div", { text: `Não foi possível abrir esta etapa: ${e.message || e}` }),
        h("button", { type: "button", class: "botao pequeno", onclick: () => renderEtapa() }, "Tentar de novo"));
    } finally {
      clearTimeout(espera);
    }
    if (seq !== renderSeq) return;
    E.desenhada = desenho;
    const idx = ETAPAS.findIndex((e) => e.id === E.etapa);
    const fase = et ? FASES.find((f) => f.id === et.fase) : null;
    const daFase = et ? ETAPAS.filter((e) => e.fase === et.fase) : [];
    const ant = idx > 0 ? ETAPAS[idx - 1] : null, prox = idx >= 0 && idx < ETAPAS.length - 1 ? ETAPAS[idx + 1] : null;
    // ação principal da barra: avançar; na etapa de envio, calcular
    const principal = E.etapa === "calculo" ? h("button", { type: "button", class: "botao primario", onclick: () => operar("executar") }, "Calcular no PJe-Calc")
      : prox ? h("a", { class: "botao primario", href: `#/caso/${E.caso.id}/${prox.id}`, "aria-keyshortcuts": "Alt+ArrowRight" }, `Continuar: ${prox.titulo} →`) : null;
    const barra = idx >= 0 ? h("nav", { class: "continuidade", "aria-label": "Continuar o cálculo" },
      h("div", { class: "salvo", id: "salvoRodape", "aria-live": "polite" }),
      ant ? h("a", { class: "botao", href: `#/caso/${E.caso.id}/${ant.id}`, "aria-keyshortcuts": "Alt+ArrowLeft" }, `← ${ant.titulo}`) : null,
      principal) : null;
    const foco = document.activeElement?.id;
    preencher(main, h("div", { class: "area" + (E.etapa.startsWith("original:") ? " area-larga" : "") },
      cabecalhoCaso(),
      et ? h("div", { class: "cabecalho-etapa" }, h("div", {},
        h("p", { class: "eyebrow", text: `${FASES.indexOf(fase) + 1}. ${fase.titulo}${daFase.length > 1 ? ` · etapa ${daFase.indexOf(et) + 1} de ${daFase.length}` : ""}` }),
        h("h1", { text: et.titulo }), h("p", { class: "sutil", text: et.desc })), h("div", { class: "acoes" }, linkOriginalDaEtapa(et.id))) : null,
      conteudo, barra));
    // um campo pedido (Revisar tudo › Alterar, pesquisa) tem prioridade; senão, redesenhar não tira o foco do usuário
    if (!focarCampoPendente() && foco && document.getElementById(foco)) document.getElementById(foco).focus();
    aplicarCorrecao(main);
    atualizarBarra();
  }
  // Pede foco num campo de uma etapa: aplicado assim que a etapa for desenhada (sem esperas por tempo)
  function irParaCampo(etapa, campo) {
    E.focoPendente = campo || null;
    const destino = `#/caso/${E.caso.id}/${etapa}`;
    if (location.hash === destino) renderEtapa(); else location.hash = destino;
  }
  // ---------------------------------------------------------------------------- "Corrigir": da pendência para o lugar certo
  // As mensagens do PJe-Calc não dizem o campo; o destino é deduzido do texto (nome da verba citada, assunto).
  const REGRAS_PENDENCIA = [
    [/pensao alimenticia/, "reflexos", "Marque a incidência de pensão alimentícia em pelo menos uma verba (quadro Incidências de cada verba) ou no FGTS."],
    [/historico/, "historico", "Confira os meses e valores do histórico salarial citado."],
    [/correcao|juros|indice|atualizac/, "atualizacao", "Confira os critérios de correção monetária e juros."],
    [/liquidac/, "atualizacao", "Confira a data de liquidação."],
    [/admiss|demiss|ajuizamento|prescri|aviso previo|maior remunera|ultima remunera/, "contrato", "Confira as datas e valores do contrato."],
    [/reclamante|reclamad|numero do processo|municipio|cpf|cnpj/, "identificacao", "Confira os dados das partes e do processo."],
    [/carga horaria|cartao de ponto|jornada/, "jornada", "Confira a jornada e o cartão de ponto."],
    [/fgts/, "reflexos", "Confira os parâmetros do FGTS."],
    [/ferias/, "original/ferias", "Confira os períodos de férias na tela oficial do PJe-Calc."],
    [/falta/, "original/faltas", "Confira as faltas na tela oficial do PJe-Calc."],
    [/custas/, "original/custas", "Confira as custas na tela oficial do PJe-Calc."],
    [/honorario/, "original/honorarios", "Confira os honorários na tela oficial do PJe-Calc."],
    [/imposto de renda|irpf/, "original/irpf", "Confira o imposto de renda na tela oficial do PJe-Calc."],
    [/contribuicao social|inss/, "original/inss", "Confira a contribuição social na tela oficial do PJe-Calc."],
    [/seguro.desemprego/, "original/seguro-desemprego", "Confira o seguro-desemprego na tela oficial do PJe-Calc."],
    [/salario.familia/, "original/salario-familia", "Confira o salário-família na tela oficial do PJe-Calc."],
    [/previdencia privada/, "original/previdencia", "Confira a previdência privada na tela oficial do PJe-Calc."],
    [/multa|indeniza/, "original/multas", "Confira as multas e indenizações na tela oficial do PJe-Calc."],
  ];
  function destinoPendencia(texto, campo) {
    const t = dobrar(texto);
    const r = E.caso?.rascunho || {};
    // aviso da conferência do Studio: já sabe a etapa e o campo
    const aviso = (E.conferencia?.avisos || []).find((a) => a.texto === texto && a.etapa);
    if (aviso) return { texto, etapa: aviso.etapa, campo: aviso.campo };
    // verba citada pelo nome (a mais longa que aparece no texto: "HORAS EXTRAS 50%" antes de "HORAS EXTRAS")
    const nomes = [...(r.verbas || []), ...(r.verbasManuais || []).map((v) => v.descricao), ...(E.criterios?.verbas || []).map((v) => v.nome)].filter(Boolean);
    const verba = nomes.filter((n) => t.includes(dobrar(n))).sort((a, b) => b.length - a.length)[0];
    if (verba && !/pensao alimenticia/.test(t)) {
      if (/reflexo|incidencia/.test(t)) return { texto, etapa: "reflexos", verba, dica: "Confira os reflexos e as incidências desta verba." };
      if (/quantidade/.test(t)) return { texto, etapa: "verbas", verba, foco: 'input[id$="-qt"]', abrirOcorrencias: true,
        dica: "Informe quantas horas ou dias por mês (campo “Quantas … por mês?”), ou preencha a coluna Quantidade nas ocorrências mês a mês." };
      if (/ocorrencia|valor devido|valor pago/.test(t)) return { texto, etapa: "verbas", verba, abrirOcorrencias: true,
        dica: "Abra “Ocorrências mês a mês” desta verba e preencha a coluna Devido (ou Pago) dos meses devidos, conforme o documento do caso." };
      return { texto, etapa: "verbas", verba, dica: "Confira os parâmetros desta verba." };
    }
    const regra = REGRAS_PENDENCIA.find(([re]) => re.test(t));
    if (regra) return { texto, etapa: regra[1], campo: campo || null, dica: regra[2],
      destacar: /pensao alimenticia/.test(t) ? 'input[id$="pensaoAlimenticia"]' : null };
    return { texto, etapa: "original/liquidar", dica: "A tela Liquidar do PJe-Calc mostra esta pendência com mais detalhes." };
  }
  function botaoCorrigir(dest) {
    const nome = dest.etapa.startsWith("original/") ? "PJe-Calc: " + ((TELAS_ORIGINAIS || []).find((t) => t.id === dest.etapa.slice(9))?.titulo || "tela oficial")
      : (ETAPAS.find((e) => e.id === dest.etapa) || {}).titulo || dest.etapa;
    return h("button", { type: "button", class: "botao pequeno botao-corrigir", onclick: () => corrigirPendencia(dest), title: `Abre ${nome} e mostra onde corrigir` },
      "Corrigir", h("span", { class: "destino", text: dest.verba ? `${nome} › ${dest.verba}` : nome }));
  }
  function corrigirPendencia(dest) {
    E.correcao = { ...dest, rolado: false };
    if (dest.abrirOcorrencias && dest.verba) E.ocAberta = dest.verba;
    irParaCampo(dest.etapa, dest.campo || "__correcao");
  }
  // chamada a cada desenho da etapa: mantém a faixa "Pendência a corrigir" e destaca o lugar até o usuário sair dela
  function aplicarCorrecao(main) {
    const c = E.correcao;
    if (!c) return false;
    if (c.etapa !== E.etapa.replace(":", "/")) { E.correcao = null; return false; }
    const limpar = () => { E.correcao = null; faixa.remove(); main.querySelectorAll(".alvo-correcao").forEach((x) => x.classList.remove("alvo-correcao")); };
    const faixa = h("div", { class: "faixa alerta faixa-correcao", role: "status" },
      h("strong", { text: "Pendência a corrigir:" }),
      h("div", { style: "flex:1 1 320px" }, h("p", { style: "margin:0", text: c.texto }), c.dica ? h("p", { class: "mini", style: "margin:4px 0 0" }, h("strong", { text: "O que fazer: " }), c.dica) : null),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap" },
        h("a", { class: "botao pequeno", href: `#/caso/${E.caso.id}/conferencia` }, "← Voltar à revisão"),
        h("button", { type: "button", class: "botao leve pequeno", onclick: limpar }, "Fechar")));
    const cab = main.querySelector(".cabecalho-etapa");
    if (cab) cab.after(faixa); else main.querySelector(".area")?.prepend(faixa);
    let alvo = null;
    if (c.verba) alvo = [...main.querySelectorAll(".verba-cartao")].find((x) => dobrar(x.dataset.verba || x.getAttribute("aria-label")) === dobrar(c.verba));
    if (!alvo && c.campo) alvo = main.querySelector(`[data-campo="${CSS.escape(c.campo)}"]`) || (CHAVES_CNJ.includes(c.campo) ? main.querySelector("#cnj-numero")?.closest(".campo") : null);
    if (!alvo && c.destacar) {
      const marcas = [...main.querySelectorAll(c.destacar)].map((x) => x.closest("label") || x);
      marcas.slice(1).forEach((x) => x.classList.add("alvo-correcao"));
      alvo = marcas[0] || null;
    }
    if (!alvo) {
      // sem um lugar exato (ex.: incidências em várias verbas): mostra a faixa com a orientação
      if (!c.rolado) { c.rolado = true; faixa.tabIndex = -1; faixa.style.scrollMarginTop = "calc(var(--topo-h) + 8px)"; faixa.scrollIntoView({ block: "start" }); faixa.focus({ preventScroll: true }); }
      return false;
    }
    alvo.classList.add("alvo-correcao");
    if (c.rolado) return false;
    c.rolado = true;
    const foco = (c.foco && alvo.querySelector(c.foco)) || (c.abrirOcorrencias && alvo.querySelector("details.mais > summary")) || alvo.querySelector("input, select, textarea, button, summary");
    alvo.scrollIntoView({ block: "start" });
    foco?.focus({ preventScroll: true });
    return true;
  }
  function focarCampoPendente() {
    const campo = E.focoPendente;
    if (!campo) return false;
    E.focoPendente = null;
    const el = document.querySelector(`[data-campo="${CSS.escape(campo)}"] :is(input, select, textarea)`)
      || (CHAVES_CNJ.includes(campo) ? document.getElementById("cnj-numero") : null);
    if (!el) return false;
    el.scrollIntoView({ block: "center" });
    el.focus({ preventScroll: true });
    return true;
  }

  async function etapaFormulario() {
    const grupos = GRUPOS[E.etapa] || [];
    return h("div", {}, avisosDaEtapa(E.etapa), E.etapa === "identificacao" ? perguntaDocumento() : null, E.etapa === "contrato" ? perguntaDesligamento() : null,
      grupos.map((g) => g.especial === "cnj" ? grupoCnj() : grupoCampos(g)));
  }
  function avisosDaEtapa(et) {
    const caixa = h("div", { id: "avisosEtapa", dataset: { etapa: et }, "aria-live": "polite" });
    preencherAvisosEtapa(caixa, et);
    return caixa;
  }
  function preencherAvisosEtapa(caixa, et) {
    const av = (E.conferencia?.avisos || []).filter((a) => a.etapa === et && !a.campo?.startsWith("historicos."));
    preencher(caixa, av.length ? h("div", { class: "faixa " + (av.some((a) => a.nivel === "impeditivo") ? "erro" : "alerta") },
      h("strong", { text: "Conferência preventiva:" }), h("div", {}, h("ul", { style: "margin:0;padding-left:18px" }, av.map((a) => h("li", { text: a.texto }))))) : null);
  }
  // após cada salvamento: atualiza a faixa de avisos e as mensagens junto aos campos, sem redesenhar a etapa
  function atualizarAvisosNaTela() {
    const caixa = $("#avisosEtapa");
    if (caixa) preencherAvisosEtapa(caixa, caixa.dataset.etapa);
    document.querySelectorAll(".campo[data-campo]").forEach((el) => {
      const erros = errosDoCampo(el.dataset.campo);
      const entrada = el.querySelector("input:not([type=checkbox]), select, textarea");
      let span = el.querySelector(".erro-campo");
      if (!erros.length) { span?.remove(); entrada?.removeAttribute("aria-invalid"); return; }
      if (!span) {
        span = h("span", { class: "erro-campo", id: (entrada?.id || "x") + "-erro", role: "alert" });
        el.appendChild(span);
        if (entrada && !(entrada.getAttribute("aria-describedby") || "").includes(span.id))
          entrada.setAttribute("aria-describedby", ((entrada.getAttribute("aria-describedby") || "") + " " + span.id).trim());
      }
      span.textContent = erros.map((e) => e.texto).join(" ");
      if (entrada && erros.some((e) => e.nivel === "impeditivo")) entrada.setAttribute("aria-invalid", "true");
    });
  }
  // Número do processo num campo só, com máscara e botão "Colar" (o PJe copia o número com pontuação).
  // No rascunho continua dividido em número, dígito, ano, tribunal e vara, como a tela do PJe-Calc pede.
  const CHAVES_CNJ = ["processo.numero", "processo.digito", "processo.ano", "processo.regiao", "processo.vara"];
  function grupoCnj() {
    const d0 = E.caso.rascunho.dados || {};
    const atual = d0["processo.numero"] ? [d0["processo.numero"], d0["processo.digito"], d0["processo.ano"], "5", d0["processo.regiao"], d0["processo.vara"]].map((x) => x || "").join("") : "";
    const erros = CHAVES_CNJ.flatMap((k) => errosDoCampo(k));
    const inp = h("input", { type: "text", id: "cnj-numero", inputmode: "numeric", value: formatarPadrao(atual.replace(/\D/g, ""), PADRAO_CNJ), maxlength: PADRAO_CNJ.length,
      placeholder: "0001234-56.2024.5.08.0001", autocomplete: "off", spellcheck: "false", class: "entrada-cnj", "aria-describedby": "cnjDica cnjSituacao" });
    const situacao = h("p", { class: "situacao-campo", id: "cnjSituacao", "aria-live": "polite" });
    const mostrar = (texto, tipo) => { preencher(situacao, texto ? h("span", { class: tipo, text: (tipo === "ok" ? "✓ " : "") + texto }) : null); if (tipo === "erro") inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid"); };
    // grava só um número completo e válido; vazio apaga o número do rascunho
    const gravar = (final) => {
      const d = inp.value.replace(/\D/g, "");
      if (!d) { CHAVES_CNJ.forEach((k) => definirValor(k, "")); mostrar(null); return; }
      const prob = problemaCnj(d);
      if (prob) { if (final || d.length === 20) mostrar(prob + (final ? " O número ainda não foi salvo." : ""), "erro"); else mostrar(null); return; }
      [d.slice(0, 7), d.slice(7, 9), d.slice(9, 13), d.slice(14, 16), d.slice(16, 20)].forEach((v, i) => definirValor(CHAVES_CNJ[i], v));
      mostrar(`Número válido · Tribunal Regional do Trabalho da ${+d.slice(14, 16)}ª Região · vara ${d.slice(16, 20)}`, "ok");
    };
    mascaraDigitos(inp, () => PADRAO_CNJ, () => gravar(false));
    inp.addEventListener("change", () => gravar(true));
    // Ctrl+V com texto copiado do PJe (pode vir com a classe e as partes): fica só o número
    inp.addEventListener("paste", (e) => {
      const n = extrairCnj(e.clipboardData?.getData("text"));
      if (!n) return;
      e.preventDefault(); inp.value = formatarPadrao(n, PADRAO_CNJ); gravar(true);
    });
    const colar = async () => {
      let texto;
      try { texto = await navigator.clipboard.readText(); }
      catch { inp.focus(); mostrar("O navegador não deixou ler o que foi copiado. Clique no campo e use Ctrl+V.", "erro"); return; }
      const n = extrairCnj(texto);
      if (!n) { mostrar(`O que está copiado não é um número de processo${texto?.trim() ? ` (“${texto.trim().slice(0, 40)}${texto.trim().length > 40 ? "…" : ""}”)` : ""}. No PJe, copie o número do processo e tente de novo.`, "erro"); inp.focus(); return; }
      inp.value = formatarPadrao(n, PADRAO_CNJ); gravar(true); inp.focus();
    };
    if (atual.replace(/\D/g, "").length === 20) { const p = problemaCnj(atual); if (!p) mostrar("Número válido", "ok"); }
    return h("section", { class: "cartao", "aria-labelledby": "gProc" }, h("div", { class: "rotulo", style: "display:flex;gap:8px;align-items:center" },
      h("h2", { id: "gProc", text: "Processo", style: "margin:0" }), botaoAjuda("processo.numero", "Número do processo")),
      h("div", { class: "campo inteiro", dataset: { campo: "processo.numero" } },
        h("label", { for: "cnj-numero", text: "Número do processo" }),
        h("div", { class: "linha-cnj" }, inp,
          h("button", { type: "button", class: "botao", onclick: colar, title: "Cola o número copiado do PJe" }, icone("colar"), "Colar")),
        h("span", { class: "dica", id: "cnjDica", text: "Copie o número no PJe e clique em Colar, ou digite só os números: a pontuação aparece sozinha. Opcional em estimativas; necessário para anexar ao PJe." }),
        situacao),
      erros.length ? h("p", { class: "erro-campo", id: "cnjErro", role: "alert", text: erros.map((e) => e.texto).join(" ") }) : null,
      maisOpcoes([{ k: "processo.valorDaCausa", rotulo: "Valor da causa (R$)", tipo: "moeda" }, { k: "processo.autuadoEm", rotulo: "Autuado em", tipo: "data" }],
        "valor da causa e data de autuação, se quiser que constem do cálculo"));
  }

  async function etapaJornada() {
    return h("div", {}, avisosDaEtapa("jornada"), grupoCampos(GRUPOS.jornada[0]),
      h("section", { class: "cartao" }, h("h2", { text: "Cartão de ponto, exceções de carga horária e feriados locais" }),
        h("p", { text: "A apuração de jornada por cartão de ponto (marcações e geração das quantidades de horas extras e noturnas), as exceções de carga horária por período e os feriados locais são feitos nas telas oficiais do PJe-Calc, abertas aqui mesmo no cálculo certo. As quantidades resultantes são usadas pelo motor e aparecem no quadro de critérios e nas ocorrências do resultado." }),
        h("p", { class: "mini sutil", text: "Quantidades de horas extras, adicionais e demais verbas mês a mês também podem ser informadas na etapa Verbas (“Ocorrências mês a mês” de cada verba)." }),
        h("div", { class: "ferramentas" }, linkOriginal("cartao", "Cartão de Ponto"), linkOriginal("dados", "Exceções de carga horária (Dados do Cálculo)"),
          h("a", { class: "botao pequeno", href: "#/original/t-feriados" }, "Feriados e Pontos Facultativos"))));
  }
  // botão para uma função do PJe-Calc (desenhada pelo Studio), aberta neste cálculo
  const linkOriginal = (telaId, texto) => h("a", { class: "botao pequeno", href: `#/caso/${E.caso.id}/original/${telaId}` }, texto);

  // ---------------------------------------------------------------------------- histórico salarial
  async function etapaHistorico() {
    const r = E.caso.rascunho;
    r.historicos = r.historicos || [];
    const d = r.dados || {};
    const sel = E.histSel && r.historicos.find((x) => x.id === E.histSel) ? E.histSel : r.historicos[0]?.id;
    E.histSel = sel;
    const lista = h("div", { class: "chips", role: "tablist", "aria-label": "Históricos salariais" }, r.historicos.map((x) =>
      h("button", { class: "chip", role: "tab", "aria-selected": String(x.id === sel), "aria-pressed": String(x.id === sel), onclick: () => { E.histSel = x.id; renderEtapa(); } },
        `${x.nome || "(sem nome)"} · ${x.ocorrencias.length} comp.`)));
    const atual = r.historicos.find((x) => x.id === sel);
    const ur = d["contrato.ultimaRemuneracao"];
    return h("div", {},
      avisosDaEtapa("historico"),
      h("section", { class: "cartao" },
        h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, h("h2", { text: "Históricos", style: "margin:0" }),
          botaoAjuda("historico", "Histórico salarial"),
          h("button", { class: "botao primario", style: "margin-left:auto", onclick: adicionarHistorico }, "Adicionar histórico")),
        h("p", { class: "sutil mini", text: ur ? `O PJe-Calc também cria automaticamente o histórico “ÚLTIMA REMUNERAÇÃO” (${ur}) a partir da etapa Contrato.` : "Sem histórico próprio, o PJe-Calc usa apenas a “Última Remuneração” informada no Contrato." }),
        lista),
      atual ? editorHistorico(atual) : h("p", { class: "sutil", text: "Nenhum histórico cadastrado nesta interface." }));
  }
  async function adicionarHistorico() {
    const nome = h("input", { type: "text", id: "hNome", placeholder: "Ex.: SALARIO BASE, COMISSOES, SALARIO DEVIDO" });
    const fg = h("input", { type: "checkbox", id: "hFgts", checked: true }), cs = h("input", { type: "checkbox", id: "hInss", checked: true });
    const ok = await dialogo({ titulo: "Adicionar histórico salarial", corpo: h("div", { class: "grade" },
      h("div", { class: "campo inteiro" }, h("label", { for: "hNome", text: "Nome do histórico" }), nome, h("span", { class: "dica", text: "Use nomes distintos por natureza de valor. O nome aparece na fórmula das verbas." })),
      h("label", { class: "marcacao", for: "hFgts" }, fg, "Incidência de FGTS"), h("label", { class: "marcacao", for: "hInss" }, cs, "Incidência de contribuição social")),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Adicionar histórico", valor: true, classe: "primario" }] });
    if (!ok || !nome.value.trim()) return;
    const n = nome.value.trim().toUpperCase();
    if ((E.caso.rascunho.historicos || []).some((x) => x.nome === n)) { avisar("Já existe um histórico com esse nome.", "erro"); return; }
    const novo = { id: "h" + Date.now().toString(36), nome: n, fgts: fg.checked, inss: cs.checked, ocorrencias: [] };
    const d = E.caso.rascunho.dados || {};
    if (dataValida(d["contrato.dataAdmissao"]) && (dataValida(d["contrato.dataDemissao"]) || dataValida(d["contrato.dataTerminoCalculo"]))) {
      const fim = (d["contrato.dataTerminoCalculo"] || d["contrato.dataDemissao"]).slice(3), ini = (d["contrato.dataInicioCalculo"] || d["contrato.dataAdmissao"]).slice(3);
      novo.ocorrencias = competencias(ini, fim).map((c) => ({ competencia: c, valor: "", fgtsRecolhido: false, inssRecolhido: false }));
    }
    E.caso.rascunho.historicos.push(novo); E.histSel = novo.id; agendarSalvamento(); renderEtapa();
  }

  function lacunas(ocs) {
    if (ocs.length < 2) return [];
    const k = [...new Set(ocs.map((o) => chaveComp(o.competencia)))].sort((a, b) => a - b), out = [];
    for (let i = 1; i < k.length; i++) { let a = k[i - 1]; while (true) { let m = a % 100 + 1, y = Math.floor(a / 100); if (m > 12) { m = 1; y++; } a = y * 100 + m; if (a >= k[i]) break; out.push(String(m).padStart(2, "0") + "/" + y); if (out.length > 600) return out; } }
    return out;
  }
  function editorHistorico(hist) {
    const raiz = h("div", { id: "grade-" + hist.id, class: "tabela-rolagem", style: "max-height:56vh" });
    const resumo = h("p", { class: "mini", "aria-live": "polite" });
    const atualizarResumo = () => {
      const vaz = hist.ocorrencias.filter((o) => o.valor === "" || o.valor == null).length, desc = hist.ocorrencias.filter((o) => o.valor === "?").length;
      const inval = hist.ocorrencias.filter((o) => o.valor && o.valor !== "?" && window.normalizarValor(o.valor) === null).length;
      const gaps = lacunas(hist.ocorrencias), dup = hist.ocorrencias.length - new Set(hist.ocorrencias.map((o) => o.competencia)).size;
      preencher(resumo, h("strong", { text: `${hist.ocorrencias.length} competências` }),
        ` · ${vaz} não informada(s) · ${desc} desconhecida(s) · ${inval} inválida(s) · ${dup} duplicada(s) · ${gaps.length} lacuna(s)`,
        gaps.length ? h("span", { class: "negativo", text: ` (faltam: ${gaps.slice(0, 8).join(", ")}${gaps.length > 8 ? "…" : ""})` }) : null);
    };
    const pl = new window.Planilha(raiz, {
      rotuloTabela: "Ocorrências do histórico " + hist.nome,
      colunas: [{ chave: "competencia", titulo: "Competência", tipo: "texto", somenteLeitura: true }, { chave: "valor", titulo: "Valor (R$)", tipo: "moeda" },
        { chave: "fgtsRecolhido", titulo: "FGTS recolhido", tipo: "marca" }, { chave: "inssRecolhido", titulo: "Contrib. social recolhida", tipo: "marca" }],
      linhas: hist.ocorrencias, rotuloLinha: (i) => String(i + 1),
      aoAlterar: () => { agendarSalvamento(); atualizarResumo(); },
    });
    raiz.addEventListener("colado", (e) => avisar(`${e.detail.celulas} célula(s) coladas${e.detail.ignoradas ? `; ${e.detail.ignoradas} além do fim da tabela foram ignoradas` : ""}.`, "ok"));
    atualizarResumo();
    const d = E.caso.rascunho.dados || {};
    const gerar = async () => {
      if (!dataValida(d["contrato.dataAdmissao"])) { avisar("Informe a data de admissão na etapa Contrato.", "erro"); return; }
      const fimData = d["contrato.dataTerminoCalculo"] || d["contrato.dataDemissao"];
      if (!dataValida(fimData)) { avisar("Informe a data de demissão (ou o término do cálculo).", "erro"); return; }
      const novas = competencias((d["contrato.dataInicioCalculo"] || d["contrato.dataAdmissao"]).slice(3), fimData.slice(3));
      const atuais = new Map(hist.ocorrencias.map((o) => [o.competencia, o]));
      const faltam = novas.filter((c) => !atuais.has(c)).length;
      if (!faltam) { avisar("Todas as competências do período já existem.", "info"); return; }
      hist.ocorrencias = novas.map((c) => atuais.get(c) || { competencia: c, valor: "", fgtsRecolhido: false, inssRecolhido: false })
        .concat(hist.ocorrencias.filter((o) => !novas.includes(o.competencia)));
      hist.ocorrencias.sort((a, b) => chaveComp(a.competencia) - chaveComp(b.competencia));
      pl.definirLinhas(hist.ocorrencias); agendarSalvamento(); atualizarResumo(); avisar(`${faltam} competência(s) incluída(s).`, "ok");
    };
    const preencherSel = async () => {
      const inp = h("input", { type: "text", id: "valSel", placeholder: "1.234,56 ou ? (desconhecido)" });
      const ok = await dialogo({ titulo: "Repetir valor na seleção", corpo: h("div", { class: "campo" }, h("label", { for: "valSel", text: "Valor para as células selecionadas da coluna Valor" }), inp),
        botoes: [{ texto: "Cancelar", valor: false }, { texto: "Aplicar à seleção", valor: true, classe: "primario" }] });
      if (!ok) return;
      const n = inp.value.trim() === "?" ? "?" : window.normalizarValor(inp.value);
      if (n === null) { avisar("Valor inválido. Use 1.234,56.", "erro"); return; }
      const s = pl.selecao(); const alt = [];
      for (let l = s.l1; l <= s.l2; l++) alt.push([l, 1, n]);
      pl.gravar(alt); avisar(`Valor aplicado a ${alt.length} competência(s).`, "ok");
    };
    const competencia = async () => {
      const inp = h("input", { type: "text", id: "novaComp", placeholder: "MM/AAAA" });
      const ok = await dialogo({ titulo: "Incluir competência", corpo: h("div", { class: "campo" }, h("label", { for: "novaComp", text: "Competência" }), inp),
        botoes: [{ texto: "Cancelar", valor: false }, { texto: "Incluir", valor: true, classe: "primario" }] });
      if (!ok) return;
      if (!/^(0[1-9]|1[0-2])\/\d{4}$/.test(inp.value)) { avisar("Use o formato MM/AAAA.", "erro"); return; }
      if (hist.ocorrencias.some((o) => o.competencia === inp.value)) { avisar("Competência já existe.", "erro"); return; }
      hist.ocorrencias.push({ competencia: inp.value, valor: "", fgtsRecolhido: false, inssRecolhido: false });
      hist.ocorrencias.sort((a, b) => chaveComp(a.competencia) - chaveComp(b.competencia));
      pl.definirLinhas(hist.ocorrencias); agendarSalvamento(); atualizarResumo();
    };
    const removerSel = async () => {
      const s = pl.selecao(); const n = s.l2 - s.l1 + 1;
      if (!(await confirmar("Remover competências", `Remover ${n} competência(s) selecionada(s) deste histórico?`, "Remover", true))) return;
      hist.ocorrencias.splice(s.l1, n); pl.definirLinhas(hist.ocorrencias); agendarSalvamento(); atualizarResumo();
    };
    const fg = h("input", { type: "checkbox", id: "hf-" + hist.id, checked: !!hist.fgts }); fg.addEventListener("change", () => { hist.fgts = fg.checked; agendarSalvamento(); });
    const cs = h("input", { type: "checkbox", id: "hc-" + hist.id, checked: !!hist.inss }); cs.addEventListener("change", () => { hist.inss = cs.checked; agendarSalvamento(); });
    return h("section", { class: "cartao", "aria-labelledby": "ht-" + hist.id },
      h("div", { style: "display:flex;gap:12px;align-items:center;flex-wrap:wrap" }, h("h2", { id: "ht-" + hist.id, text: hist.nome, style: "margin:0" }),
        h("label", { class: "marcacao", for: fg.id }, fg, "Incidência de FGTS"), h("label", { class: "marcacao", for: cs.id }, cs, "Incidência de contribuição social"),
        h("button", { class: "botao perigo pequeno", style: "margin-left:auto", onclick: async () => {
          if (await confirmar("Excluir histórico", `Excluir o histórico ${hist.nome} do rascunho? Se já estiver gravado, será removido do PJe-Calc na próxima gravação.`, "Excluir histórico", true)) {
            E.caso.rascunho.historicos = E.caso.rascunho.historicos.filter((x) => x !== hist); agendarSalvamento(); renderEtapa(); } } }, "Excluir histórico")),
      h("div", { class: "ferramentas", role: "toolbar", "aria-label": "Ferramentas da tabela" },
        h("button", { class: "botao pequeno", onclick: gerar }, "Gerar competências do contrato"),
        h("button", { class: "botao pequeno", onclick: competencia }, "Incluir competência"),
        h("span", { class: "separador", "aria-hidden": "true" }),
        h("button", { class: "botao pequeno", onclick: preencherSel }, "Repetir valor na seleção"),
        h("button", { class: "botao pequeno", onclick: () => pl.repetirPrimeira(), "aria-keyshortcuts": "Control+D" }, "Repetir 1ª linha para baixo", teclas("Ctrl", "D")),
        h("button", { class: "botao pequeno", onclick: () => { const s = pl.selecao(); const alt = []; for (let l = s.l1; l <= s.l2; l++) alt.push([l, 2, "s"]); pl.gravar(alt); } }, "Marcar FGTS recolhido"),
        h("button", { class: "botao pequeno", onclick: removerSel }, "Remover selecionadas"),
        h("span", { class: "separador", "aria-hidden": "true" }),
        h("button", { class: "botao pequeno", onclick: () => importarTabela(hist, pl, atualizarResumo) }, "Importar CSV/Excel")),
      painelAtalhos(),
      resumo, raiz);
  }
  // ---------------------------------------------------------------------------- atalhos da tabela
  // teclas("Ctrl", "D") -> [Ctrl] + [D], desenhadas como teclas de teclado
  function teclas(...ks) {
    return h("span", { class: "combo", "aria-hidden": "true" }, ks.flatMap((k, i) => [i ? "+" : null, h("span", { class: "tecla", text: k })]));
  }
  const ATALHOS_PLANILHA = [
    { titulo: "Andar pela tabela", itens: [[["↑", "↓", "←", "→"], "Ir para a célula ao lado", "sep"], [["Shift", "↓"], "Selecionar várias linhas"],
      [["PgDn"], "Descer 15 linhas"], [["Ctrl", "A"], "Selecionar a tabela toda"]] },
    { titulo: "Preencher", itens: [[["0–9"], "Comece a digitar o valor"], [["Enter"], "Confirmar e ir para baixo"], [["Esc"], "Desistir do que digitou"],
      [["Delete"], "Apagar as células selecionadas"], [["Espaço"], "Marcar ou desmarcar FGTS / contribuição"]] },
    { titulo: "Copiar e repetir", itens: [[["Ctrl", "V"], "Colar colunas do Excel"], [["Ctrl", "C"], "Copiar as células selecionadas"],
      [["Ctrl", "D"], "Repetir a 1ª linha selecionada nas de baixo"]] },
  ];
  function painelAtalhos() {
    const p = prefs();
    const det = h("details", { class: "atalhos", open: p.atalhosFechados ? null : true },
      h("summary", {}, "Atalhos do teclado", h("span", { class: "sutil mini", text: "clique numa célula da tabela para usar" })),
      h("div", { class: "atalhos-grade" },
        ATALHOS_PLANILHA.map((g) => h("div", {}, h("h4", { text: g.titulo }),
          h("ul", {}, g.itens.map(([ks, txt, sep]) => h("li", {}, sep ? h("span", { class: "combo", "aria-hidden": "true" }, ks.map((k) => h("span", { class: "tecla", text: k }))) : teclas(...ks),
            h("span", { text: txt, "aria-label": `${ks.join(sep ? " " : " + ")}: ${txt}` })))))),
        h("div", {}, h("h4", { text: "O que digitar na coluna Valor" }),
          h("ul", {}, [["1.234,56", "o salário do mês"], ["0,00", "o mês teve salário zero"], ["?", "não sei o valor ainda (impede o envio)"], ["(vazio)", "não informado (impede o envio)"]]
            .map(([v, t]) => h("li", {}, h("span", { class: "valor-especial", text: v }), h("span", { text: t })))))));
    det.addEventListener("toggle", () => salvarPref({ atalhosFechados: !det.open }));
    return det;
  }

  async function importarTabela(hist, pl, atualizarResumo) {
    const arq = h("input", { type: "file", id: "arqTab", accept: ".csv,.txt,.xlsx,.xlsm" });
    const area = h("div", { "aria-live": "polite" });
    let dados = null, validas = [];  // linhas válidas da prévia atual, já sem o campo "erro"
    const mapa = { competencia: -1, valor: -1, fgts: -1, inss: -1 };
    let cabecalho = true;
    const desenharPrevia = () => {
      if (!dados) return;
      const ncol = Math.max(...dados.linhas.map((l) => l.length));
      const cols = Array.from({ length: ncol }, (_, i) => cabecalho ? (dados.linhas[0][i] || `Coluna ${i + 1}`) : `Coluna ${i + 1}`);
      const sel = (chave, rot) => { const id = "map-" + chave; const s = h("select", { id }, h("option", { value: -1 }, "— não usar —"), cols.map((c, i) => h("option", { value: i, selected: mapa[chave] === i }, c)));
        s.addEventListener("change", () => { mapa[chave] = +s.value; desenharPrevia(); }); return h("div", { class: "campo" }, h("label", { for: id, text: rot }), s); };
      const corpoLinhas = dados.linhas.slice(cabecalho ? 1 : 0);
      const conv = corpoLinhas.map((l) => validarLinha(l, mapa));
      const okN = conv.filter((c) => !c.erro).length;
      const cab = h("input", { type: "checkbox", id: "temCab", checked: cabecalho }); cab.addEventListener("change", () => { cabecalho = cab.checked; desenharPrevia(); });
      preencher(area, 
        h("label", { class: "marcacao", for: "temCab" }, cab, "A primeira linha é cabeçalho"),
        h("div", { class: "grade" }, sel("competencia", "Competência (MM/AAAA ou data)"), sel("valor", "Valor"), sel("fgts", "FGTS recolhido (S/N) — opcional"), sel("inss", "Contrib. social recolhida (S/N) — opcional")),
        h("p", { class: "mini", text: `Prévia: ${okN} linha(s) válida(s) de ${conv.length}. Linhas com erro não serão aplicadas.` }),
        h("div", { class: "tabela-rolagem", style: "max-height:36vh" }, h("table", { class: "tabela" },
          h("thead", {}, h("tr", {}, ["Linha", "Competência", "Valor", "FGTS rec.", "CS rec.", "Situação"].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, conv.slice(0, 300).map((c, i) => h("tr", {}, h("td", { text: i + 1 + (cabecalho ? 1 : 0) }), h("td", { text: c.competencia || "" }), h("td", { class: "num", text: c.valor ?? "" }),
            h("td", { text: c.fgtsRecolhido ? "S" : "N" }), h("td", { text: c.inssRecolhido ? "S" : "N" }), h("td", { class: c.erro ? "negativo" : "positivo", text: c.erro || "ok" })))))));
      validas = conv.filter((c) => !c.erro).map(({ erro, ...o }) => o);
    };
    arq.addEventListener("change", async () => {
      if (!arq.files[0]) return;
      try {
        dados = await api("POST", "/api/ler-planilha?nome=" + encodeURIComponent(arq.files[0].name), await arq.files[0].arrayBuffer());
        const cab = (dados.linhas[0] || []).map(dobrar);
        mapa.competencia = cab.findIndex((c) => /compet|mes|data|periodo/.test(c));
        mapa.valor = cab.findIndex((c) => /valor|salario|remunera/.test(c));
        mapa.fgts = cab.findIndex((c) => /fgts/.test(c) && /rec/.test(c));
        mapa.inss = cab.findIndex((c) => /(contribui|inss)/.test(c) && /rec/.test(c));
        if (mapa.competencia < 0) mapa.competencia = 0; if (mapa.valor < 0) mapa.valor = 1;
        desenharPrevia();
      } catch (e) { dados = null; validas = []; preencher(area, h("div", { class: "faixa erro", text: e.message })); }
    });
    const modo = h("select", { id: "modoImp" }, h("option", { value: "mesclar" }, "Mesclar: atualizar competências existentes e incluir novas"), h("option", { value: "substituir" }, "Substituir todas as competências do histórico"));
    const ok = await dialogo({ titulo: `Importar planilha para ${hist.nome}`, largo: true, corpo: h("div", {},
      h("p", { text: "Formatos aceitos: CSV (separado por ponto e vírgula, vírgula ou tabulação) e Excel .xlsx. Datas e valores no padrão brasileiro. Nada é gravado antes da sua confirmação." }),
      h("div", { class: "campo" }, h("label", { for: "arqTab", text: "Arquivo" }), arq), h("div", { class: "campo" }, h("label", { for: "modoImp", text: "Como aplicar" }), modo), area),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Aplicar linhas válidas", valor: true, classe: "primario" }] });
    if (!ok || !validas.length) return;
    if (modo.value === "substituir") hist.ocorrencias.splice(0, hist.ocorrencias.length);
    const idx = new Map(hist.ocorrencias.map((o) => [o.competencia, o]));
    validas.forEach((v) => { const o = idx.get(v.competencia); if (o) Object.assign(o, v); else hist.ocorrencias.push(v); });
    hist.ocorrencias.sort((a, b) => chaveComp(a.competencia) - chaveComp(b.competencia));
    pl.definirLinhas(hist.ocorrencias); agendarSalvamento(); atualizarResumo();
    avisar(`${validas.length} competência(s) importada(s) para o rascunho. Confira antes de gravar no PJe-Calc.`, "ok");
  }
  function validarLinha(l, mapa) {
    const bruto = (i) => (i >= 0 ? (l[i] ?? "") : "");
    let comp = String(bruto(mapa.competencia)).trim(), erro = null;
    let m = /^(\d{1,2})\/(\d{4})$/.exec(comp) || /^\d{1,2}\/(\d{1,2})\/(\d{4})$/.exec(comp);
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(comp)) { const p = comp.split("/"); comp = p[1].padStart(2, "0") + "/" + p[2]; }
    else if (m) comp = m[1].padStart(2, "0") + "/" + m[2];
    else if (/^\d{4}-\d{2}(-\d{2})?$/.test(comp)) comp = comp.slice(5, 7) + "/" + comp.slice(0, 4);
    if (!/^(0[1-9]|1[0-2])\/\d{4}$/.test(comp)) erro = "competência inválida";
    const vb = String(bruto(mapa.valor)).trim();
    const valor = vb === "?" ? "?" : vb === "" ? "" : window.normalizarValor(vb);
    if (valor === null) erro = erro || "valor inválido";
    if (valor === "") erro = erro || "valor vazio";
    const fg = mapa.fgts >= 0 ? window.lerMarcacao(bruto(mapa.fgts)) : false, cs = mapa.inss >= 0 ? window.lerMarcacao(bruto(mapa.inss)) : false;
    if (fg === null || cs === null) erro = erro || "marcação S/N inválida";
    return { competencia: comp, valor: valor ?? vb, fgtsRecolhido: !!fg, inssRecolhido: !!cs, erro };
  }

  // ---------------------------------------------------------------------------- verbas
  async function etapaVerbas() {
    const r = E.caso.rascunho;
    r.verbas = r.verbas || []; r.verbasConfig = r.verbasConfig || {};
    const { crit: criterios, lendo } = criteriosSemEsperar();  // sem leitura do motor, a etapa funciona igual
    const filtro = h("input", { type: "search", id: "fVerba", placeholder: "Filtrar verbas (ex.: horas, férias, adicional)" });
    const cat = h("div", { class: "catalogo", role: "group", "aria-label": "Catálogo de verbas do lançamento expresso" });
    const desenharCat = () => {
      const f = dobrar(filtro.value);
      preencher(cat, ...(E.opcoes?.expressas || []).filter((v) => !f || dobrar(v).includes(f)).map((v) => {
        const id = "vx-" + dobrar(v).replace(/\W/g, "");
        const cb = h("input", { type: "checkbox", id, checked: r.verbas.includes(v) });
        cb.addEventListener("change", () => {
          if (cb.checked) { if (!r.verbas.includes(v)) r.verbas.push(v); } else { r.verbas = r.verbas.filter((x) => x !== v); }
          agendarSalvamento(); desenharSel(); desenharPerguntas();
        });
        return h("label", { class: "marcacao", for: id }, cb, v);
      }));
    };
    filtro.addEventListener("input", desenharCat);
    const selec = h("div");
    const nomesHist = () => [...(r.historicos || []).map((x) => x.nome), ...(r.dados?.["contrato.ultimaRemuneracao"] ? ["ÚLTIMA REMUNERAÇÃO"] : [])];
    const desenharSel = () => {
      if (!r.verbas.length) { preencher(selec, h("p", { class: "sutil", text: `Nenhuma verba escolhida ainda. Responda as perguntas acima ou marque no catálogo as verbas que ${doc().o} ${doc().manda}.` })); return; }
      preencher(selec, ...r.verbas.map((v) => {
        const cfg = r.verbasConfig[v] = r.verbasConfig[v] || {};
        const idb = "vb-" + dobrar(v).replace(/\W/g, "");
        // parâmetros que o PJe-Calc montou para a verba (conhecidos depois do primeiro envio)
        const lida = criterios?.verbas?.find((x) => dobrar(x.nome) === dobrar(v));
        const just = h("textarea", { id: idb + "-j", rows: 2 }, cfg.justificativa || ""); just.addEventListener("input", () => { cfg.justificativa = just.value; agendarSalvamento(); });
        const tre = h("textarea", { id: idb + "-t", rows: 2 }, cfg.trecho || ""); tre.addEventListener("input", () => { cfg.trecho = tre.value; agendarSalvamento(); });
        return h("article", { class: "verba-cartao", "aria-label": v, dataset: { verba: v } },
          h("header", {}, h("h3", { text: v }), h("button", { class: "botao leve pequeno", style: "margin-left:auto", onclick: () => { r.verbas = r.verbas.filter((x) => x !== v); agendarSalvamento(); desenharCat(); desenharSel(); desenharPerguntas(); } }, "Remover verba")),
          contaDaVerba(v, cfg, lida),
          escolhaDaBase(v, cfg, lida, idb, desenharSel),
          quantidadeDaVerba(v, cfg, lida, idb),
          editorOcorrencias(v, cfg),
          h("details", { class: "mais" }, h("summary", {}, "Fundamento (justificativa e trecho da decisão)"),
            h("div", { class: "grade" }, h("div", { class: "campo" }, h("label", { for: just.id, text: "Justificativa" }), just), h("div", { class: "campo" }, h("label", { for: tre.id, text: "Trecho da decisão ou documento" }), tre))));
      }));
    };
    // perguntas guiadas: redesenhadas junto com o catálogo e as verbas escolhidas
    const blocoPerguntas = h("div");
    const desenharPerguntas = () => preencher(blocoPerguntas, perguntasVerbas(() => { desenharPerguntas(); desenharCat(); desenharSel(); }));
    desenharCat(); desenharSel(); desenharPerguntas();
    r.verbasManuais = r.verbasManuais || [];
    const assuntos = r.verbasManuais.length ? assuntosSemEsperar() : null;
    const manuais = h("div", {}, r.verbasManuais.length ? r.verbasManuais.map((v, i) => cartaoVerbaManual(v, i, nomesHist(), assuntos, () => {
      r.verbasManuais = r.verbasManuais.filter((x) => x !== v); if (v.descricao) delete r.verbasConfig[v.descricao]; agendarSalvamento(); renderEtapa();
    })) : h("p", { class: "sutil", text: "Nenhuma verba manual." }));
    const todas = [...r.verbas, ...r.verbasManuais.filter((v) => v.parametros?.tipoDeVerba !== "REFLEXO").map((v) => v.descricao).filter(Boolean)];
    const dup = todas.filter((v, i) => todas.indexOf(v) !== i);
    return h("div", {}, avisosDaEtapa("verbas"),
      lendo ? avisoLendoCriterios() : null,
      dup.length ? h("div", { class: "faixa erro" }, h("strong", { text: "Verbas duplicadas: " }), h("div", { text: dup.join(", ") })) : null,
      guiaVerbas(),
      blocoPerguntas,
      h("section", { class: "cartao" }, h("div", { style: "display:flex;gap:8px;align-items:center" }, h("span", { class: "passo-num", text: "2" }), h("h2", { text: "Catálogo completo de verbas", style: "margin:0" }),
        botaoAjuda("verbas", "Verbas")),
        h("p", { class: "mini sutil", text: `Todas as verbas do PJe-Calc ${E.opcoes?.versaoCatalogo || ""}. As marcadas pelas perguntas aparecem aqui também; marque o que mais ${doc().o} ${doc().manda}. Não achou? Use o lançamento manual, no fim da página.` }),
        h("div", { class: "campo", style: "margin-bottom:8px" }, h("label", { for: "fVerba", text: "Procurar verba" }), filtro), cat),
      h("section", { class: "cartao" }, h("div", { style: "display:flex;gap:8px;align-items:center" }, h("span", { class: "passo-num", text: "3" }), h("h2", { text: `Diga como cada verba é calculada (${r.verbas.length})`, style: "margin:0" })),
        h("p", { class: "mini sutil", text: "Para cada verba: confira a conta que o PJe-Calc monta, escolha sobre qual salário ela é calculada e, se for o caso, informe a quantidade de horas ou dias." }),
        selec),
      h("section", { class: "cartao" }, h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, h("h2", { text: `Lançamento manual (${r.verbasManuais.length})`, style: "margin:0" }),
          h("button", { class: "botao primario", style: "margin-left:auto", onclick: () => { r.verbasManuais.push(verbaManualNova()); agendarSalvamento(); renderEtapa(); } }, "Adicionar verba manual")),
        h("p", { class: "mini sutil", text: "Equivale ao botão “Manual” da tela Verbas do PJe-Calc: a verba é criada nessa tela, com estes parâmetros, ao gravar. Alterar uma verba manual já gravada a recria no PJe-Calc." }),
        manuais));
  }

  // ---------------------------------------------------------------------------- verbas explicadas para quem não é especialista
  // As bases que o PJe-Calc oferece (campo "Base de Cálculo" da tela Parâmetros da Verba), em linguagem simples
  const BASES_EXPLICADAS = [
    { valor: "HISTORICO_SALARIAL", rotulo: "Histórico salarial", curto: "Os salários mês a mês da etapa Histórico salarial.", texto: "Os salários de cada mês, cadastrados na etapa Histórico salarial (por exemplo SALÁRIO BASE ou COMISSÕES). Use quando o salário mudou durante o contrato. Inclui a ÚLTIMA REMUNERAÇÃO, que o PJe-Calc cria sozinho." },
    { valor: "MAIOR_REMUNERACAO", rotulo: "Maior remuneração", curto: "O maior salário, informado no Contrato, em todos os meses.", texto: "O maior salário que o trabalhador recebeu, informado na etapa Contrato. O PJe-Calc usa esse valor em todos os meses. É a base habitual de verbas da rescisão, como férias e aviso prévio." },
    { valor: "SALARIO_MINIMO", rotulo: "Salário mínimo", curto: "O mínimo nacional de cada mês, pela tabela oficial do PJe-Calc.", texto: "O salário mínimo nacional de cada mês. O PJe-Calc já tem a tabela oficial: não é preciso cadastrar nada. Usado, por exemplo, no adicional de insalubridade." },
    { valor: "SALARIO_DA_CATEGORIA", rotulo: "Piso salarial", curto: "O piso da categoria, da tabela de pisos do PJe-Calc.", texto: "O piso da categoria, previsto em convenção ou acordo coletivo, cadastrado na tabela de pisos salariais do PJe-Calc." },
  ];
  const valorParam = (lida, id) => lida?.campos?.find((c) => c.id === id);
  const rotuloParam = (lida, id) => { const c = valorParam(lida, id); if (!c) return null; return (c.opcoes || []).find((o) => o.valor === c.valor)?.rotulo || c.valor; };
  const numeroBr = (s) => { const n = parseFloat(String(s || "").replace(/\./g, "").replace(",", ".")); return Number.isFinite(n) ? n : null; };
  const fmtBr = (n, casas = 2) => n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  function resumoHistorico(nome) {
    const r = E.caso.rascunho, d = r.dados || {};
    if (dobrar(nome) === dobrar("ÚLTIMA REMUNERAÇÃO")) return d["contrato.ultimaRemuneracao"] ? `R$ ${d["contrato.ultimaRemuneracao"]} em todos os meses (informado no Contrato)` : "valor informado no Contrato";
    const x = (r.historicos || []).find((y) => y.nome === nome);
    const vals = (x?.ocorrencias || []).map((o) => numeroBr(o.valor)).filter((n) => n !== null);
    if (!x?.ocorrencias?.length) return "sem meses cadastrados";
    const min = Math.min(...vals), max = Math.max(...vals);
    return `${x.ocorrencias.length} mês(es)` + (vals.length ? ` · ${min === max ? "R$ " + fmtBr(min) : `de R$ ${fmtBr(min)} a R$ ${fmtBr(max)}`}` : " · ainda sem valores");
  }
  // "parece" salário mínimo: histórico criado à mão com esse nome (a base própria é melhor: usa a tabela oficial)
  const ehNomeSalarioMinimo = (n) => /salario\s*minimo/.test(dobrar(n));

  function guiaVerbas() {
    const r = E.caso.rascunho;
    const histMinimo = (r.historicos || []).filter((x) => ehNomeSalarioMinimo(x.nome)).map((x) => x.nome);
    const det = h("details", { class: "guia-verbas cartao", open: prefs().guiaVerbasFechado ? null : true },
      h("summary", {}, h("h2", { text: "Como funcionam as verbas", style: "margin:0;display:inline" }), h("span", { class: "sutil mini", text: " · leia uma vez; depois pode fechar" })),
      h("p", { text: "Cada verba é paga mês a mês. O PJe-Calc calcula o valor de cada mês com esta conta:" }),
      h("div", { class: "conta", "aria-label": "Valor do mês = base dividida pelo divisor, vezes o multiplicador, vezes a quantidade" },
        termoConta("Base", "o salário usado na conta"), h("span", { class: "op", text: "÷" }),
        termoConta("Divisor", "em quantas partes o salário é dividido (ex.: 220 horas do mês)"), h("span", { class: "op", text: "×" }),
        termoConta("Multiplicador", "o acréscimo (ex.: 1,5 = hora com 50% a mais)"), h("span", { class: "op", text: "×" }),
        termoConta("Quantidade", "quantas horas, dias ou avos no mês"), h("span", { class: "op", text: "=" }),
        termoConta("Valor do mês", "", "resultado")),
      h("p", { class: "exemplo" }, h("strong", { text: "Exemplo, horas extras 50%: " }), "salário de R$ 2.200,00 ÷ 220 horas × 1,5 × 10 horas extras no mês = ", h("strong", { text: "R$ 150,00" }), "."),
      h("h3", { text: "Sobre qual salário? As bases possíveis" }),
      h("dl", { class: "bases-explicadas" }, BASES_EXPLICADAS.map((b) => h("div", {}, h("dt", { text: b.rotulo }), h("dd", { text: b.texto }))),
        h("div", {}, h("dt", { text: "Última remuneração" }), h("dd", { text: "O último salário, informado na etapa Contrato. O PJe-Calc cria sozinho um histórico chamado ÚLTIMA REMUNERAÇÃO com esse valor em todos os meses. Serve quando o salário foi sempre o mesmo ou não se sabe como ele mudou." }))),
      h("p", { class: "mini sutil", text: `Na dúvida, mantenha o que o PJe-Calc já escolheu para a verba: ele segue a lei para cada tipo de verba. Mude só quando ${doc().o} indicar outra base.` }));
    det.addEventListener("toggle", () => salvarPref({ guiaVerbasFechado: !det.open }));
    return h("div", {}, det, histMinimo.length ? h("div", { class: "faixa alerta" }, h("strong", { text: "Salário mínimo não precisa de histórico." }),
      h("div", { text: `Você cadastrou o histórico ${histMinimo.join(", ")}. Se ${doc().o} indica o salário mínimo como base, escolha a base “Salário mínimo” em cada verba, mais abaixo: o PJe-Calc usa a tabela oficial, com o valor certo de cada mês. Um histórico digitado à mão pode ficar com valores errados.` })) : null);
  }
  const termoConta = (nome, texto, classe) => h("div", { class: "termo " + (classe || "") }, h("strong", { text: nome }), texto ? h("span", { text: texto }) : null);

  // a conta que o PJe-Calc montou para a verba, termo a termo e em português
  function contaDaVerba(v, cfg, lida) {
    if (!lida) return h("div", { class: "faixa info" }, h("div", { text: E.caso.pjecalc?.calculoId
      ? "Esta verba ainda não está no PJe-Calc. Depois do próximo envio, aparece aqui a conta que ele monta para ela."
      : "Depois do primeiro envio ao PJe-Calc, aparece aqui a conta que ele monta para esta verba (base, divisor, multiplicador e quantidade)." }));
    if (!lida.formula) return h("div", { class: "faixa alerta" }, h("strong", { text: "Esta verba não tem conta: o valor é informado." }),
      h("div", { text: "Informe o valor devido de cada mês em “Ocorrências mês a mês”, logo abaixo, na coluna Devido. Sem nenhum valor, o PJe-Calc não consegue calcular a verba." }));
    const d = E.caso.rascunho.dados || {};
    const tipoBase = cfg.alteracoes?.tipoDaBaseTabelada || valorParam(lida, "tipoDaBaseTabelada")?.valor;
    const base = cfg.alteracoes?.tipoDaBaseTabelada ? BASES_EXPLICADAS.find((b) => b.valor === tipoBase)?.rotulo : rotuloParam(lida, "tipoDaBaseTabelada");
    const hist = tipoBase === "HISTORICO_SALARIAL" ? [...new Set([...(lida.bases || []), ...(cfg.bases || [])])] : [];
    const tipoDiv = valorParam(lida, "tipoDeDivisor")?.valor;
    const divisor = tipoDiv === "OUTRO_VALOR" ? (valorParam(lida, "outroValorDoDivisor")?.valor || "—")
      : tipoDiv === "CARGA_HORARIA" ? `carga horária (${d["jornada.cargaHorariaPadrao"] || "220,00"} h)` : rotuloParam(lida, "tipoDeDivisor") || "—";
    const mult = numeroBr(valorParam(lida, "outroValorDoMultiplicador")?.valor);
    const multTxt = mult === null ? "—" : fmtBr(mult, mult % 1 ? 4 : 0).replace(/0+$/, "").replace(/,$/, "");
    const multSent = mult === null || mult === 1 ? "sem acréscimo" : mult > 1 ? `${fmtBr((mult - 1) * 100, (mult - 1) * 100 % 1 ? 2 : 0)}% a mais` : `${fmtBr(mult * 100, 0)}% do valor`;
    const tipoQt = valorParam(lida, "tipoDaQuantidade")?.valor;
    const qtInf = cfg.alteracoes?.valorInformadoDaQuantidade ?? valorParam(lida, "valorInformadoDaQuantidade")?.valor;
    const qtN = numeroBr(qtInf) || 0;
    const qt = tipoQt === "INFORMADA" ? `${fmtBr(qtN, qtN % 1 ? 2 : 0)} por mês` : rotuloParam(lida, "tipoDaQuantidade") || "—";
    const qtZero = tipoQt === "INFORMADA" && !numeroBr(qtInf) && !(cfg.ocorrencias || []).some((o) => numeroBr(o.quantidade));
    return h("div", { class: "conta-verba" },
      h("p", { class: "mini sutil", style: "margin:0 0 6px", text: "Como o PJe-Calc calcula esta verba, mês a mês:" }),
      h("div", { class: "conta compacta" },
        termoConta("Base", [base, hist.length ? hist.join(" + ") : null].filter(Boolean).join(": ")), h("span", { class: "op", text: "÷" }),
        termoConta("Divisor", divisor), h("span", { class: "op", text: "×" }),
        termoConta("Multiplicador", `${multTxt} (${multSent})`), h("span", { class: "op", text: "×" }),
        termoConta("Quantidade", tipoQt === "AVOS" ? "avos (meses trabalhados ÷ 12)" : qt, qtZero ? "falta" : "")),
      qtZero ? h("p", { class: "erro-campo", style: "margin-top:6px", text: "A quantidade está zerada, então esta verba vai dar R$ 0,00. Informe abaixo quantas horas ou dias por mês, ou preencha a coluna Quantidade nas ocorrências mês a mês." }) : null);
  }

  // escolha da base: tipo de base (alteração da tela Parâmetros da Verba) e, se for histórico, quais históricos
  function escolhaDaBase(v, cfg, lida, idb, redesenhar) {
    const r = E.caso.rascunho;
    cfg.alteracoes = cfg.alteracoes || {};
    const campoBase = valorParam(lida, "tipoDaBaseTabelada");
    if (lida && !campoBase) return null;  // verba sem base (valor informado, reflexos…)
    const doPjecalc = campoBase?.valor || null;
    const escolhida = cfg.alteracoes.tipoDaBaseTabelada || doPjecalc;
    const opcoes = BASES_EXPLICADAS.filter((b) => !campoBase?.opcoes?.length || campoBase.opcoes.some((o) => o.valor === b.valor));
    const nome = "base-" + idb;
    const escolher = (valor) => {
      if (!valor || valor === doPjecalc) delete cfg.alteracoes.tipoDaBaseTabelada; else cfg.alteracoes.tipoDaBaseTabelada = valor;
      if (valor && valor !== "HISTORICO_SALARIAL") cfg.bases = [];
      agendarSalvamento(); redesenhar();
    };
    const radios = h("div", { class: "opcoes-base", role: "radiogroup", "aria-labelledby": idb },
      lida ? null : h("label", { class: "opcao-base" + (!escolhida ? " escolhida" : "") },
        h("input", { type: "radio", name: nome, checked: !escolhida, onchange: () => escolher("") }),
        h("span", {}, h("strong", { text: "Deixar o PJe-Calc escolher" }), h("span", { class: "mini sutil", text: "Ele usa a base prevista para esta verba. Depois do envio, você vê aqui qual foi." }))),
      opcoes.map((b) => h("label", { class: "opcao-base" + (escolhida === b.valor ? " escolhida" : "") },
        h("input", { type: "radio", name: nome, value: b.valor, checked: escolhida === b.valor, onchange: () => escolher(b.valor) }),
        h("span", {}, h("strong", {}, b.rotulo, b.valor === doPjecalc ? h("span", { class: "etiqueta-padrao", text: "escolha do PJe-Calc" }) : null),
          h("span", { class: "mini sutil", text: b.curto })))));
    // históricos que entram na base (só quando a base é o histórico salarial)
    let historicos = null;
    if (escolhida === "HISTORICO_SALARIAL" || !escolhida) {
      const jaNaBase = lida?.bases || [];
      const nomes = [...new Set([...(r.historicos || []).map((x) => x.nome), ...(r.dados?.["contrato.ultimaRemuneracao"] ? ["ÚLTIMA REMUNERAÇÃO"] : []), ...jaNaBase])];
      historicos = h("div", { class: "historicos-base" },
        h("p", { class: "mini", style: "margin:8px 0 4px;font-weight:600", text: "Quais salários do histórico entram na conta?" }),
        nomes.length ? h("ul", {}, nomes.map((n) => {
          const id = idb + "-h-" + dobrar(n).replace(/\W/g, "");
          const fixo = jaNaBase.some((b) => dobrar(b) === dobrar(n));
          const cb = h("input", { type: "checkbox", id, checked: fixo || (cfg.bases || []).includes(n), disabled: fixo });
          cb.addEventListener("change", () => { cfg.bases = (cfg.bases || []).filter((x) => x !== n); if (cb.checked) cfg.bases.push(n); agendarSalvamento(); });
          return h("li", {}, h("label", { class: "marcacao", for: id }, cb, h("span", {}, h("strong", { text: n }), " — ", h("span", { class: "sutil", text: resumoHistorico(n) }),
            fixo ? h("span", { class: "mini sutil", text: " (já está na base no PJe-Calc)" }) : null,
            ehNomeSalarioMinimo(n) ? h("span", { class: "mini negativo", text: " · para salário mínimo, prefira a base “Salário mínimo” acima" }) : null)));
        })) : h("p", { class: "mini sutil" }, "Nenhum histórico cadastrado. ", h("a", { href: `#/caso/${E.caso.id}/historico` }, "Cadastre os salários na etapa Histórico salarial"), " ou informe a última remuneração no Contrato."),
        nomes.length > 1 ? h("p", { class: "mini sutil", text: "Marcar mais de um soma os valores (ex.: SALÁRIO BASE + COMISSÕES)." }) : null);
    }
    return h("div", { class: "bloco-verba" },
      h("div", { class: "rotulo", id: idb, style: "font-weight:600" }, "Sobre qual salário esta verba é calculada?", botaoAjuda("base", "Base de cálculo"),
        h("span", { class: "decisao", text: "decisão profissional" })),
      radios, historicos);
  }

  // quantidade padrão do mês (horas, dias) quando o PJe-Calc espera uma quantidade informada
  function quantidadeDaVerba(v, cfg, lida, idb) {
    if (valorParam(lida, "tipoDaQuantidade")?.valor !== "INFORMADA") return null;
    cfg.alteracoes = cfg.alteracoes || {};
    const doPjecalc = valorParam(lida, "valorInformadoDaQuantidade")?.valor || "";
    const id = idb + "-qt";
    const unidade = /hora|noturn|interval|sobreaviso|prontid/.test(dobrar(v)) ? "horas" : /dia|domingo|feriado|repouso/.test(dobrar(v)) ? "dias" : "unidades";
    const inp = h("input", { type: "text", id, inputmode: "decimal", autocomplete: "off", value: cfg.alteracoes.valorInformadoDaQuantidade ?? doPjecalc, placeholder: "Ex.: 10", style: "max-width:140px" });
    const erro = h("span", { class: "erro-campo", hidden: true });
    inp.addEventListener("change", () => {
      const n = window.normalizarNumero(inp.value, 4);
      if (n === null || (n && numeroBr(n) < 0)) { erro.hidden = false; erro.textContent = "Use só números, com vírgula para fração. Ex.: 10 ou 7,5."; return; }
      erro.hidden = true;
      if (!n || n === doPjecalc) delete cfg.alteracoes.valorInformadoDaQuantidade; else cfg.alteracoes.valorInformadoDaQuantidade = n;
      inp.value = n; agendarSalvamento(); renderEtapa();
    });
    return h("div", { class: "bloco-verba campo" },
      h("label", { for: id, style: "font-weight:600" }, `Quantas ${unidade} por mês?`),
      h("div", { style: "display:flex;gap:8px;align-items:center" }, inp, h("span", { class: "sutil", text: unidade })),
      h("span", { class: "dica", text: "Esse número vale para todos os meses. Se muda de um mês para outro, deixe aqui o mais comum e corrija os outros meses em “Ocorrências mês a mês”, logo abaixo." }),
      erro);
  }

  // ---------------------------------------------------------------------------- ocorrências da verba (mês a mês)
  // Mesma grade da tela "Ocorrências da Verba" do PJe-Calc. Célula vazia = mantém o que o PJe-Calc gerou.
  const COLS_OCORRENCIA = [
    { chave: "competencia", titulo: "Competência", tipo: "texto", somenteLeitura: true },
    { chave: "quantidade", titulo: "Quantidade", tipo: "numero", casas: 4, vazio: "padrão do PJe-Calc" },
    { chave: "devido", titulo: "Devido (R$)", tipo: "moeda", vazio: "padrão do PJe-Calc" },
    { chave: "pago", titulo: "Pago (R$)", tipo: "moeda", vazio: "padrão do PJe-Calc" },
    { chave: "ativo", titulo: "Ativa", tipo: "marca" },
  ];
  const COLS_OCORRENCIA_AVANCADAS = [
    { chave: "divisor", titulo: "Divisor", tipo: "numero", casas: 4, vazio: "padrão do PJe-Calc" },
    { chave: "multiplicador", titulo: "Multiplicador", tipo: "numero", casas: 8, vazio: "padrão do PJe-Calc" },
  ];
  const COLS_OCORRENCIA_MOTOR = [{ chave: "_quantidadeMotor", titulo: "Qtd. no PJe-Calc", tipo: "texto", somenteLeitura: true },
    { chave: "_devidoMotor", titulo: "Devido no PJe-Calc", tipo: "texto", somenteLeitura: true }];
  const ocorrenciaVazia = (c) => ({ competencia: c, quantidade: "", devido: "", pago: "", ativo: true, divisor: "", multiplicador: "" });
  const ocorrenciaInformada = (o) => ["quantidade", "devido", "pago", "divisor", "multiplicador"].some((k) => o[k] !== "" && o[k] != null) || o.ativo === false;
  function periodoDoCalculo() {
    const d = E.caso.rascunho.dados || {};
    const ini = d["contrato.dataInicioCalculo"] || d["contrato.dataAdmissao"], fim = d["contrato.dataTerminoCalculo"] || d["contrato.dataDemissao"];
    return dataValida(ini) && dataValida(fim) ? competencias(ini.slice(3), fim.slice(3)) : null;
  }
  function editorOcorrencias(nome, cfg) {
    cfg.ocorrencias = cfg.ocorrencias || [];
    const raiz = h("div", { id: "oc-" + dobrar(nome).replace(/\W/g, ""), class: "tabela-rolagem", style: "max-height:44vh" });
    const resumo = h("p", { class: "mini", "aria-live": "polite" });
    const sumario = h("summary", {});
    const atualizar = () => {
      const inf = cfg.ocorrencias.filter(ocorrenciaInformada).length;
      const inval = cfg.ocorrencias.filter((o) => ["quantidade", "divisor"].some((k) => o[k] && window.normalizarNumero(o[k], 4) === null)
        || (o.multiplicador && window.normalizarNumero(o.multiplicador, 8) === null) || [o.devido, o.pago].some((v) => v && window.normalizarValor(v) === null)).length;
      preencher(resumo, h("strong", { text: `${inf} de ${cfg.ocorrencias.length} competência(s) alterada(s)` }), inval ? h("span", { class: "negativo", text: ` · ${inval} com valor inválido` }) : null);
      preencher(sumario, `Ocorrências mês a mês — ${inf ? inf + " competência(s) alterada(s)" : "padrão do PJe-Calc"}`);
    };
    const temMotor = cfg.ocorrencias.some((o) => o._quantidadeMotor !== undefined);
    const pl = new window.Planilha(raiz, {
      rotuloTabela: "Ocorrências da verba " + nome,
      colunas: [...COLS_OCORRENCIA, ...COLS_OCORRENCIA_AVANCADAS, ...(temMotor ? COLS_OCORRENCIA_MOTOR : [])],
      linhas: cfg.ocorrencias, classeLinha: (o) => (ocorrenciaInformada(o) ? "alterada" : ""),
      aoAlterar: () => { agendarSalvamento(); atualizar(); },
    });
    raiz.addEventListener("colado", (e) => avisar(`${e.detail.celulas} célula(s) coladas${e.detail.ignoradas ? `; ${e.detail.ignoradas} além do fim da tabela foram ignoradas` : ""}.`, "ok"));
    const gerar = () => {
      const comps = periodoDoCalculo();
      if (!comps) { avisar("Informe admissão e demissão (ou início e término do cálculo) na etapa Contrato.", "erro"); return; }
      const atuais = new Map(cfg.ocorrencias.map((o) => [o.competencia, o]));
      cfg.ocorrencias = comps.map((c) => atuais.get(c) || ocorrenciaVazia(c));
      E.ocAberta = nome; agendarSalvamento(); renderEtapa();
    };
    const carregar = async () => {
      try {
        const r = await api("GET", `/api/casos/${E.caso.id}/ocorrencias?verba=${encodeURIComponent(nome)}`);
        const atuais = new Map(cfg.ocorrencias.map((o) => [o.competencia, o]));
        const antes = cfg.ocorrencias.map((o) => o.competencia).join();
        cfg.ocorrencias = r.ocorrencias.map((m) => {
          const o = atuais.get(m.competencia) || ocorrenciaVazia(m.competencia);
          // referência de leitura: propriedades não enumeráveis não entram no rascunho salvo (nem geram revisão)
          for (const [k, x] of [["_quantidadeMotor", m.quantidade ?? ""], ["_devidoMotor", m.devido ?? ""]])
            Object.defineProperty(o, k, { value: x, enumerable: false, writable: true, configurable: true });
          return o;
        });
        E.ocAberta = nome;
        if (cfg.ocorrencias.map((o) => o.competencia).join() !== antes) agendarSalvamento();
        renderEtapa();
        avisar(`${r.ocorrencias.length} competência(s) lidas do PJe-Calc (gravação da revisão ${r.lidoNaRevisao}). Os valores do PJe-Calc aparecem nas colunas de referência.`, "ok");
      } catch (e) { avisar(e.message, "erro"); }
    };
    const limpar = () => {
      cfg.ocorrencias.forEach((o) => Object.assign(o, { quantidade: "", devido: "", pago: "", divisor: "", multiplicador: "", ativo: true }));
      pl.definirLinhas(cfg.ocorrencias); agendarSalvamento(); atualizar();
    };
    const det = h("details", { class: "mais", open: E.ocAberta === nome }, sumario,
      h("p", { class: "mini sutil" }, "Célula vazia mantém o que o PJe-Calc calcular. Quantidade em horas ou dias, conforme a fórmula da verba; “Devido” substitui o valor calculado do mês; desmarque “Ativa” para excluir o mês. Aceita colar colunas de planilhas (Ctrl+V). ",
        botaoAjuda("ocorrencias", "Ocorrências mês a mês")),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin:6px 0" },
        h("button", { type: "button", class: "botao pequeno", onclick: gerar }, cfg.ocorrencias.length ? "Completar competências do período" : "Gerar competências do período"),
        E.caso.pjecalc?.calculoId ? h("button", { type: "button", class: "botao pequeno", onclick: carregar }, "Carregar do PJe-Calc") : null,
        cfg.ocorrencias.length ? h("button", { type: "button", class: "botao leve pequeno", onclick: limpar }, "Limpar alterações") : null),
      cfg.ocorrencias.length ? raiz : h("p", { class: "mini sutil", text: "Gere as competências do período do cálculo ou carregue as geradas pelo PJe-Calc (após a primeira gravação)." }),
      resumo);
    det.addEventListener("toggle", () => { if (det.open) E.ocAberta = nome; else if (E.ocAberta === nome) E.ocAberta = null; });
    atualizar();
    return det;
  }

  // ---------------------------------------------------------------------------- verbas do lançamento manual
  const OPC_MANUAL = {
    valor: [{ valor: "CALCULADO", rotulo: "Calculado (base ÷ divisor × multiplicador × quantidade)" }, { valor: "INFORMADO", rotulo: "Informado (valor devido mês a mês)" }],
    tipoVariacaoDaParcela: [{ valor: "FIXA", rotulo: "Fixa" }, { valor: "VARIAVEL", rotulo: "Variável" }],
    caracteristicaVerba: [{ valor: "COMUM", rotulo: "Comum" }, { valor: "DECIMO_TERCEIRO_SALARIO", rotulo: "13º salário" }, { valor: "AVISO_PREVIO", rotulo: "Aviso prévio" }, { valor: "FERIAS", rotulo: "Férias" }],
    ocorrenciaPagto: [{ valor: "MENSAL", rotulo: "Mensal" }, { valor: "DEZEMBRO", rotulo: "Dezembro" }, { valor: "DESLIGAMENTO", rotulo: "Desligamento" }, { valor: "PERIODO_AQUISITIVO", rotulo: "Período aquisitivo" }],
    tipoDaBaseTabelada: [{ valor: "HISTORICO_SALARIAL", rotulo: "Histórico salarial" }, { valor: "MAIOR_REMUNERACAO", rotulo: "Maior remuneração" }, { valor: "SALARIO_MINIMO", rotulo: "Salário mínimo" }, { valor: "SALARIO_DA_CATEGORIA", rotulo: "Piso salarial" }],
    tipoDeDivisor: [{ valor: "OUTRO_VALOR", rotulo: "Informado" }, { valor: "CARGA_HORARIA", rotulo: "Carga horária" }, { valor: "DIAS_UTEIS", rotulo: "Dias úteis" }],
    tipoDeVerba: [{ valor: "PRINCIPAL", rotulo: "Principal" }, { valor: "REFLEXO", rotulo: "Reflexo de outra verba" }],
    // opções exibidas pelo PJe-Calc 2.16.0; as médias só existem para 13º, férias e aviso prévio
    comportamentoDoReflexo: [{ valor: "VALOR_MENSAL", rotulo: "Valor mensal" }, { valor: "MEDIA_PELO_VALOR", rotulo: "Média pelo valor absoluto" },
      { valor: "MEDIA_PELO_VALOR_CORRIGIDO", rotulo: "Média pelo valor corrigido" }, { valor: "MEDIA_PELA_QUANTIDADE", rotulo: "Média pela quantidade" }],
    tratamentoFracaoReflexo: [{ valor: "MANTER", rotulo: "Manter" }, { valor: "INTEGRALIZAR", rotulo: "Integralizar" },
      { valor: "DESPREZAR", rotulo: "Desprezar (só médias)" }, { valor: "DESPREZAR_MENOR_QUE_15_DIAS", rotulo: "Desprezar menor que 15 dias (só médias)" }],
  };
  function verbaManualNova() {
    return { id: "vm" + Date.now().toString(36), descricao: "", assuntoCnj: "", bases: [],
      parametros: { tipoDeVerba: "PRINCIPAL", valor: "CALCULADO", caracteristicaVerba: "COMUM", ocorrenciaPagto: "MENSAL", tipoDaBaseTabelada: "HISTORICO_SALARIAL",
        tipoDeDivisor: "OUTRO_VALOR", outroValorDoDivisor: "", outroValorDoMultiplicador: "", tipoDaQuantidade: "INFORMADA", valorInformadoDaQuantidade: "",
        irpf: true, inss: true, fgts: true } };
  }
  async function carregarAssuntosCnj() {
    if (E.assuntosCnj || !E.caso.pjecalc?.calculoId) return E.assuntosCnj || null;
    try { E.assuntosCnj = (await api("GET", `/api/casos/${E.caso.id}/assuntos-cnj`)).assuntos; } catch { E.assuntosCnj = null; }
    return E.assuntosCnj;
  }
  // A tabela de assuntos CNJ vem do PJe-Calc (que pode estar ocupado): a etapa abre sem ela e é redesenhada
  // quando ela chega. Uma tentativa por cálculo aberto; sem a tabela, o campo aceita o assunto digitado.
  function assuntosSemEsperar() {
    if (E.assuntosCnj || !E.caso.pjecalc?.calculoId || E.assuntosTentado === E.caso.id) return E.assuntosCnj || null;
    E.assuntosTentado = E.caso.id;
    const caso = E.caso.id;
    carregarAssuntosCnj().then((a) => { if (a && E.caso?.id === caso && E.etapa === "verbas") renderEtapa(); });
    return null;
  }
  function cartaoVerbaManual(v, i, nomesHist, assuntos, aoRemover) {
    const r = E.caso.rascunho;
    const p = v.parametros = v.parametros || {};
    const pre = `vm.${v.id}.`;
    const AJ = { irpf: "manual.incidencias", inss: "manual.incidencias", fgts: "manual.incidencias", tipoDeDivisor: "divisor" };
    const par = (k, rotulo, tipo, opcoes, extra = {}) => campo({ k: pre + k, rotulo, tipo, opcoes, vazio: "Selecione…", ajuda: AJ[k] || "manual." + k, ...extra },
      { valor: p[k], erros: [], redesenhar: false,
        aoAlterar: (x) => { p[k] = x; agendarSalvamento(); if (tipo === "lista") renderEtapa(); } });
    const nome = h("input", { type: "text", id: pre + "nome", value: v.descricao || "", maxlength: 50, placeholder: "Ex.: ADICIONAL DE PERMANÊNCIA", autocomplete: "off" });
    nome.addEventListener("change", () => {
      const novo = nome.value.trim().toUpperCase(), antigo = (v.descricao || "").trim().toUpperCase();
      if (antigo && r.verbasConfig[antigo] && novo && !r.verbasConfig[novo]) { r.verbasConfig[novo] = r.verbasConfig[antigo]; delete r.verbasConfig[antigo]; }
      v.descricao = novo; agendarSalvamento(); renderEtapa();
    });
    const dl = pre + "assuntos";
    const assunto = h("input", { type: "text", id: pre + "cnj", value: v.assuntoCnj || "", list: assuntos ? dl : null, placeholder: "Código CNJ (ex.: 2086 - Horas Extras)", autocomplete: "off" });
    assunto.addEventListener("change", () => {
      const cod = assunto.value.split("-")[0].trim();
      const achado = (assuntos || []).find((a) => a.codigo === cod);
      v.assuntoCnj = achado ? `${achado.codigo} - ${achado.nome}` : assunto.value.trim();
      assunto.value = v.assuntoCnj; agendarSalvamento();
    });
    const calculado = p.valor !== "INFORMADO";
    const bases = p.tipoDaBaseTabelada === "HISTORICO_SALARIAL" ? h("div", { class: "campo inteiro" },
      h("div", { class: "rotulo", text: "Históricos que compõem a base" }),
      h("div", { class: "chips", role: "group", "aria-label": "Históricos da base" }, nomesHist.length ? nomesHist.map((n) => {
        const id = pre + "b-" + dobrar(n).replace(/\W/g, "");
        const cb = h("input", { type: "checkbox", id, checked: (v.bases || []).includes(n) });
        cb.addEventListener("change", () => { v.bases = (v.bases || []).filter((x) => x !== n); if (cb.checked) v.bases.push(n); agendarSalvamento(); });
        return h("label", { class: "marcacao", for: id }, cb, n);
      }) : h("span", { class: "mini sutil", text: "Cadastre históricos para escolher a base." }))) : null;
    const reflexo = p.tipoDeVerba === "REFLEXO";
    // verbas que podem servir de principal/base: expressas e manuais principais (exceto esta)
    const outras = [...(r.verbas || []), ...(r.verbasManuais || []).filter((x) => x !== v && x.parametros?.tipoDeVerba !== "REFLEXO").map((x) => x.descricao).filter(Boolean)];
    const meta = (k, rotulo, opcoes, extra = {}) => campo({ k: pre + k, rotulo, tipo: "lista", opcoes, vazio: "Selecione…", ajuda: "manual." + k, ...extra },
      { valor: v[k], erros: [], redesenhar: false, aoAlterar: (x) => { v[k] = x; agendarSalvamento(); renderEtapa(); } });
    const basesVerbas = !reflexo && calculado ? h("div", { class: "campo inteiro" },
      h("div", { class: "rotulo" }, "Outras verbas que compõem a base", h("span", { class: "opcional", text: " (opcional)" }), botaoAjuda("manual.basesVerbas", "Outras verbas na base")),
      h("div", { class: "chips", role: "group", "aria-label": "Verbas da base" }, outras.length ? outras.map((n) => {
        const id = pre + "bv-" + dobrar(n).replace(/\W/g, "");
        const atual = (v.basesVerbas || []).find((b) => b.verba === n);
        const cb = h("input", { type: "checkbox", id, checked: !!atual });
        cb.addEventListener("change", () => {
          v.basesVerbas = (v.basesVerbas || []).filter((b) => b.verba !== n);
          if (cb.checked) v.basesVerbas.push({ verba: n, integralizar: "SIM" });
          agendarSalvamento(); renderEtapa();
        });
        const integ = atual ? h("select", { "aria-label": `Integralizar ${n}`, onchange: (e) => { atual.integralizar = e.target.value; agendarSalvamento(); } },
          h("option", { value: "SIM", selected: atual.integralizar !== "NAO" }, "integralizar"), h("option", { value: "NAO", selected: atual.integralizar === "NAO" }, "não integralizar")) : null;
        return h("span", { class: "marcacao" }, h("label", { for: id }, cb, n), integ);
      }) : h("span", { class: "mini sutil", text: "Inclua outras verbas para usá-las como base." }))) : null;
    const titulo = v.descricao ? (reflexo && v.principal ? `${v.descricao} SOBRE ${v.principal}` : v.descricao) : `Verba manual ${i + 1} (sem nome)`;
    const cfg = v.descricao && !reflexo ? (r.verbasConfig[v.descricao] = r.verbasConfig[v.descricao] || {}) : null;
    return h("article", { class: "verba-cartao", "aria-label": titulo, dataset: { verba: v.descricao || "" } },
      h("header", {}, h("h3", { text: titulo }), h("span", { class: "decisao", text: reflexo ? "reflexo lançado manualmente" : "lançamento manual" }),
        h("button", { class: "botao leve pequeno", style: "margin-left:auto", onclick: aoRemover }, reflexo ? "Retirar reflexo" : "Remover verba")),
      h("div", { class: "grade" },
        h("div", { class: "campo" }, h("div", { class: "rotulo" }, h("label", { for: nome.id }, "Nome", h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" })), botaoAjuda("manual.descricao", "Nome da verba")), nome,
          h("span", { class: "dica", text: window.AJUDA["manual.descricao"].essencial })),
        h("div", { class: "campo" }, h("div", { class: "rotulo" }, h("label", { for: assunto.id }, "Assunto CNJ", h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" })), botaoAjuda("manual.assuntoCnj", "Assunto CNJ")), assunto,
          assuntos ? h("datalist", { id: dl }, assuntos.map((a) => h("option", { value: `${a.codigo} - ${a.nome}` }))) : null,
          h("span", { class: "dica", text: assuntos ? `${assuntos.length} assuntos da tabela do PJe-Calc.` : "Grave o cálculo uma vez para escolher na tabela oficial; até lá, informe o código." })),
        par("tipoDeVerba", "Tipo", "lista", OPC_MANUAL.tipoDeVerba),
        reflexo ? meta("principal", "Verba principal (base do reflexo) *", outras.map((n) => ({ valor: n, rotulo: n }))) : null,
        reflexo ? meta("comportamentoDoReflexo", "Comportamento do reflexo", OPC_MANUAL.comportamentoDoReflexo) : null,
        reflexo ? meta("tratamentoFracaoReflexo", "Tratamento da fração de mês", OPC_MANUAL.tratamentoFracaoReflexo) : null,
        par("valor", "Valor", "lista", OPC_MANUAL.valor),
        par("caracteristicaVerba", "Característica", "lista", OPC_MANUAL.caracteristicaVerba),
        par("ocorrenciaPagto", "Ocorrência de pagamento", "lista", OPC_MANUAL.ocorrenciaPagto),
        par("tipoVariacaoDaParcela", "Parcela", "lista", OPC_MANUAL.tipoVariacaoDaParcela, { avancado: true }),
        par("irpf", "Incidência de imposto de renda", "marca"), par("inss", "Incidência de contribuição social", "marca"), par("fgts", "Incidência de FGTS", "marca"),
        calculado && !reflexo ? par("tipoDaBaseTabelada", "Base de cálculo", "lista", OPC_MANUAL.tipoDaBaseTabelada) : null,
        calculado && !reflexo ? bases : null,
        basesVerbas,
        calculado ? par("tipoDeDivisor", "Divisor", "lista", OPC_MANUAL.tipoDeDivisor) : null,
        calculado && p.tipoDeDivisor === "OUTRO_VALOR" ? par("outroValorDoDivisor", "Valor do divisor", "texto") : null,
        calculado ? par("outroValorDoMultiplicador", "Multiplicador", "texto") : null,
        calculado ? par("valorInformadoDaQuantidade", "Quantidade padrão do mês", "texto") : null),
      calculado || reflexo ? null : h("p", { class: "mini", text: "Valor informado: preencha a coluna “Devido” nas ocorrências mês a mês." }),
      reflexo ? h("p", { class: "mini sutil", text: "O PJe-Calc não exclui reflexos: retirar este reflexo do rascunho o desativa na verba principal. Alterações são gravadas pela ação “Parametrizar”, seguidas de “Regerar” das ocorrências do reflexo. As ocorrências mês a mês de reflexos continuam na interface original." })
        : cfg ? editorOcorrencias(v.descricao, cfg) : h("p", { class: "mini sutil", text: "Dê um nome à verba para editar as ocorrências mês a mês." }));
  }

  // ---------------------------------------------------------------------------- reflexos, incidências e FGTS
  async function carregarCriterios(forcar) {
    if (!E.caso.pjecalc?.calculoId) return null;
    if (E.criterios && !forcar && E.criteriosDe === E.caso.id && E.criterios.lidoNaRevisao === E.caso.pjecalc.gravadoRevisao) return E.criterios;
    const caso = E.caso.id;
    E.erroCriterios = null;
    const lido = await api("GET", `/api/casos/${caso}/criterios${forcar ? "?forcar=1" : ""}`);
    if (E.caso?.id !== caso) return null;  // o usuário abriu outro cálculo durante a leitura
    E.criterios = lido; E.criteriosDe = caso;
    return lido;
  }
  // Critérios sem travar a etapa: ler do PJe-Calc leva vários segundos. Com uma leitura válida em memória,
  // devolve na hora; senão dispara a leitura (uma por vez), devolve o que houver e redesenha a etapa quando
  // ela chega. Um erro fica guardado até "Ler novamente", para não repetir a leitura a cada redesenho.
  function criteriosSemEsperar() {
    const vinc = E.caso.pjecalc || {};
    if (!vinc.calculoId) return { crit: null };
    const caso = E.caso.id, chave = `${caso}:${vinc.gravadoRevisao}`;
    const crit = E.criteriosDe === caso ? E.criterios : null;
    // lida para esta gravação (ou já tentada nela: não relê em laço se a revisão local e a do servidor divergirem)
    if (crit && (crit.lidoNaRevisao === vinc.gravadoRevisao || E.criteriosChave === chave)) return { crit };
    if (E.erroCriterios?.chave === chave) return { crit, erro: E.erroCriterios.mensagem };
    if (E.lendoCriterios !== chave) {
      E.lendoCriterios = chave;
      carregarCriterios()
        .then((lido) => { if (lido) E.criteriosChave = chave; })
        .catch((e) => { if (E.caso?.id === caso) E.erroCriterios = { chave, mensagem: e.message }; })
        .finally(() => {
          if (E.lendoCriterios === chave) E.lendoCriterios = null;
          if (E.caso?.id === caso && ETAPAS_COM_CRITERIOS.includes(E.etapa)) renderEtapa();
        });
    }
    return { crit, lendo: true };
  }
  const ETAPAS_COM_CRITERIOS = ["verbas", "reflexos", "atualizacao", "conferencia"];
  const avisoLendoCriterios = () => h("div", { class: "faixa info lendo", role: "status" },
    h("div", { text: "Lendo do PJe-Calc o que está gravado para este cálculo… A tela já pode ser usada e se completa sozinha em alguns segundos." }));
  async function etapaReflexos() {
    const r = E.caso.rascunho;
    r.fgts = r.fgts || {};
    const fg = (k, rot, tipo, opc) => campo({ k: "fgts." + k, rotulo: rot, tipo, opcoes: opc },
      { valor: r.fgts[k], aoAlterar: (v) => { if (v === "" || v === undefined) delete r.fgts[k]; else r.fgts[k] = v; agendarSalvamento(); if (k === "multa") renderEtapa(); }, erros: [] });
    const blocoFgts = h("section", { class: "cartao" }, h("h2", { text: "FGTS" }),
      h("p", { class: "mini sutil", text: "Campos não alterados mantêm o padrão do PJe-Calc." }),
      h("div", { class: "grade" }, fg("tipoDeVerba", "Destino do FGTS", "lista", "fgts.tipoDeVerba"), fg("comporPrincipal", "Compor principal", "lista", "fgts.comporPrincipal"),
        fg("multa", "Multa do FGTS", "marca"),
        r.fgts.multa ? fg("multaDoFgts", "Percentual da multa", "lista", "fgts.multaDoFgts") : null,
        r.fgts.multa ? h("div", { class: "so-avancado", style: "display:contents" }, fg("tipoDoValorDaMulta", "Valor da multa", "lista", "fgts.tipoDoValorDaMulta"), fg("incidenciaDoFgts", "Incidência da multa", "lista", "fgts.incidenciaDoFgts"),
          fg("excluirAvisoDaMulta", "Excluir da base da multa o FGTS sobre aviso prévio", "marca"), fg("multaDoArtigo467", "Multa do art. 467 da CLT sobre o FGTS", "marca")) : null,
        h("div", { class: "so-avancado", style: "display:contents" }, fg("multa10", "Contribuição social 10%", "marca"), fg("contribuiçãoSocial", "Contribuição social 0,5%", "marca"))));
    let blocoReflexos;
    const vinc = E.caso.pjecalc || {};
    if (!vinc.calculoId) {
      blocoReflexos = h("section", { class: "cartao" }, h("h2", { text: "Reflexos e incidências por verba" }),
        h("p", { text: "Os reflexos disponíveis e as incidências padrão de cada verba são definidos pelo PJe-Calc. Grave o cálculo para carregá-los diretamente do motor." }),
        h("button", { class: "botao primario", onclick: async () => { await operar("gravar"); renderEtapa(); } }, "Gravar no PJe-Calc e carregar reflexos"));
    } else {
      const { crit, erro, lendo } = criteriosSemEsperar();
      const reler = async (ev) => {
        ev.currentTarget.disabled = true;
        try { await carregarCriterios(true); } catch (e) { avisar(e.message, "erro"); }
        renderEtapa();
      };
      blocoReflexos = h("section", { class: "cartao" }, h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, h("h2", { text: "Reflexos e incidências por verba", style: "margin:0" }),
        botaoAjuda("reflexos", "Reflexos"), h("span", { class: "mini sutil", text: "Incidências" }), botaoAjuda("incidencias", "Incidências"),
        h("button", { class: "botao pequeno", style: "margin-left:auto", disabled: !!lendo, onclick: reler }, "Ler novamente do PJe-Calc")),
        lendo ? avisoLendoCriterios() : null,
        erro ? h("div", { class: "faixa erro", text: erro }) : null,
        crit && crit.lidoNaRevisao !== E.caso.revisao ? h("div", { class: "faixa alerta" }, h("div", { text: `Lido do PJe-Calc na revisão ${crit.lidoNaRevisao}. Verbas incluídas depois aparecerão após a próxima gravação.` })) : null,
        crit ? crit.verbas.map((v) => cartaoReflexos(v)) : null);
    }
    return h("div", {}, avisosDaEtapa("reflexos"), blocoReflexos, blocoFgts);
  }
  function cartaoReflexos(v) {
    const r = E.caso.rascunho;
    const cfg = r.verbasConfig[v.nome] = r.verbasConfig[v.nome] || {};
    cfg.reflexos = cfg.reflexos || {};
    cfg.alteracoes = cfg.alteracoes || {};
    const val = (id) => v.campos.find((c) => c.id === id);
    const inc = ["irpf", "inss", "fgts", "previdenciaPrivada", "pensaoAlimenticia"].map((id) => {
      const c = val(id); if (!c) return null;
      const atual = id in cfg.alteracoes ? cfg.alteracoes[id] : c.valor;
      const cid = "inc-" + dobrar(v.nome).replace(/\W/g, "") + id;
      const cb = h("input", { type: "checkbox", id: cid, checked: !!atual, disabled: !c.editavel });
      cb.addEventListener("change", () => { if (cb.checked === c.valor) delete cfg.alteracoes[id]; else cfg.alteracoes[id] = cb.checked; agendarSalvamento(); });
      return h("label", { class: "marcacao", for: cid }, cb, c.rotulo.replace("Incidência: ", ""), id in cfg.alteracoes ? h("span", { class: "decisao", text: "alterado" }) : null);
    });
    const refl = (v.reflexos || []).map((rf) => {
      const atual = rf.nome in cfg.reflexos ? cfg.reflexos[rf.nome] : rf.ativo;
      const cid = "rf-" + dobrar(v.nome + rf.nome).replace(/\W/g, "").slice(0, 60);
      const cb = h("input", { type: "checkbox", id: cid, checked: !!atual });
      cb.addEventListener("change", () => { if (cb.checked === !!rf.ativo) delete cfg.reflexos[rf.nome]; else cfg.reflexos[rf.nome] = cb.checked; agendarSalvamento(); });
      return h("label", { class: "marcacao", for: cid }, cb, rf.nome);
    });
    return h("article", { class: "verba-cartao", "aria-label": v.nome, dataset: { verba: v.nome } },
      h("header", {}, h("h3", { text: v.nome })),
      v.formula ? h("p", { class: "mini" }, "Fórmula montada pelo PJe-Calc: ", h("code", { class: "formula", text: v.formula })) : null,
      h("div", { class: "grade" }, h("div", {}, h("strong", { class: "mini", text: "Incidências" }), h("div", {}, inc)),
        h("div", {}, h("strong", { class: "mini", text: "Reflexos disponíveis" }), refl.length ? h("div", {}, refl) : h("p", { class: "mini sutil", text: "O PJe-Calc não oferece reflexos para esta verba." }))));
  }

  // ---------------------------------------------------------------------------- critérios de atualização
  async function etapaAtualizacao() {
    const r = E.caso.rascunho;
    r.liquidacao = r.liquidacao || {}; r.atualizacao = r.atualizacao || { valores: {}, jurosCombinados: null, indicesCombinados: null };
    const at = r.atualizacao; at.valores = at.valores || {};
    const liq = (k, rot, tipo, opc) => campo({ k: "liquidacao." + k, rotulo: rot, tipo, opcoes: opc }, { valor: r.liquidacao[k], aoAlterar: (v) => { r.liquidacao[k] = v; agendarSalvamento(); }, erros: [] });
    const leitura = criteriosSemEsperar();
    const atuais = leitura.crit?.atualizacao || null, erroLeitura = leitura.erro || null, lendoAtualizacao = !!leitura.lendo;
    // Cada critério aparece já com o valor gravado no PJe-Calc; o que for mudado aqui vai para at.valores
    // (só as diferenças) e é gravado na tela Correção, Juros e Multa no próximo envio.
    const doPjecalc = (k) => atuais?.campos?.find((c) => c.id === k);
    const alterado = (k) => k in at.valores;
    const atualDe = (k) => (alterado(k) ? at.valores[k] : doPjecalc(k)?.valor);
    const mudar = (k, v) => {
      const orig = doPjecalc(k)?.valor;
      if (v === "" || v === undefined || (orig !== undefined && v === orig)) delete at.valores[k]; else at.valores[k] = v;
      agendarSalvamento(); renderEtapa();
    };
    const etiquetaAlt = (k) => alterado(k) ? h("span", { class: "decisao", text: doPjecalc(k) ? "alterado aqui" : "definido aqui" }) : null;
    const av = (k, rot, tipo, opcKey) => {
      const id = "at-" + k, c = doPjecalc(k);
      const explica = window.AJUDA["atualizacao." + k]?.essencial;
      if (tipo === "marca") {
        const cb = h("input", { type: "checkbox", id, checked: !!atualDe(k) });
        cb.addEventListener("change", () => mudar(k, cb.checked));
        return h("div", { class: "campo" }, h("div", { class: "rotulo" }, h("label", { class: "marcacao", for: id }, cb, h("span", {}, rot, etiquetaAlt(k))), botaoAjuda("atualizacao." + k, rot)),
          explica ? h("span", { class: "dica", text: explica }) : null);
      }
      const ops = c?.opcoes?.length ? c.opcoes : op(opcKey || "atualizacao." + k);
      const v = atualDe(k) ?? "";
      const sel = h("select", { id }, h("option", { value: "" }, c ? "—" : "Padrão do PJe-Calc"), ops.map((o) => h("option", { value: o.valor, selected: o.valor === v }, o.rotulo)));
      sel.addEventListener("change", () => mudar(k, sel.value));
      return h("div", { class: "campo" }, h("div", { class: "rotulo" }, h("label", { for: id, text: rot }), botaoAjuda("atualizacao." + k, rot), etiquetaAlt(k)), sel,
        explica ? h("span", { class: "dica", text: explica }) : null,
        alterado(k) && c ? h("span", { class: "dica", text: `No PJe-Calc está: ${(c.opcoes || []).find((o) => o.valor === c.valor)?.rotulo || c.valor || "—"}` }) : null);
    };
    // combinações (outro índice / outra tabela de juros a partir de uma data): a lista do PJe-Calc vira a do rascunho na primeira mudança
    const combos = (chave, rotulo, opcoesKey) => {
      const lista = at[chave] || atuais?.[chave] || [];
      const editar = (fn) => { at[chave] = clone(lista); fn(at[chave]); agendarSalvamento(); renderEtapa(); };
      const corpo = h("tbody", {}, lista.length ? lista.map((c, i) => h("tr", {}, h("td", { text: c.tabela }), h("td", { text: c.aPartirDe }),
        h("td", {}, h("button", { class: "botao pequeno perigo", onclick: () => editar((l) => l.splice(i, 1)) }, "Remover"))))
        : h("tr", {}, h("td", { colspan: 3, class: "sutil", text: "Nenhuma combinação." })));
      const sel = h("select", { id: "nc-" + chave }, op(opcoesKey).map((o) => h("option", { value: o.rotulo }, o.rotulo)));
      const dt = h("input", { type: "text", id: "nd-" + chave, placeholder: "DD/MM/AAAA" }); mascaraData(dt);
      return h("div", { class: "inteiro" }, h("h3", {}, rotulo, at[chave] ? h("span", { class: "decisao", text: "alterado aqui" }) : null),
        h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, h("th", { text: "Tabela" }), h("th", { text: "A partir de" }), h("th", { text: "" }))), corpo),
        h("div", { class: "ferramentas" }, h("label", { for: sel.id, class: "mini", text: "Tabela" }), sel, h("label", { for: dt.id, class: "mini", text: "A partir de" }), dt,
          h("button", { class: "botao pequeno", onclick: () => { if (!dataValida(dt.value)) { avisar("Data inválida. Use DD/MM/AAAA.", "erro"); return; } editar((l) => l.push({ tabela: sel.value, aPartirDe: dt.value })); } }, "Adicionar combinação")));
    };
    const nAlt = Object.keys(at.valores).length + (at.jurosCombinados ? 1 : 0) + (at.indicesCombinados ? 1 : 0);
    const desfazer = async () => {
      if (!(await confirmar("Desfazer alterações", "Voltar todos os critérios de correção e juros para o que está gravado no PJe-Calc?", "Desfazer"))) return;
      r.atualizacao = { valores: {}, jurosCombinados: null, indicesCombinados: null }; agendarSalvamento(); renderEtapa();
    };
    const grupoAt = (titulo, ...itens) => h("div", { class: "inteiro grupo-atualizacao" }, h("h3", { text: titulo }), h("div", { class: "grade" }, itens));
    return h("div", {},
      h("section", { class: "cartao" }, h("h2", { text: "Liquidação" }), h("div", { class: "grade" },
        liq("data", "Data de liquidação", "data"), liq("indicesAcumulados", "Acumular índices de correção", "lista", "liquidacao.indicesAcumulados")),
        h("p", { class: "mini sutil", text: "Vazio: o PJe-Calc sugere o último dia do mês corrente e a época própria padrão." })),
      h("section", { class: "cartao" }, h("h2", { text: "Correção monetária e juros" }),
        h("div", { class: "faixa info" }, h("strong", { text: "Decisão do usuário." }), h("div", { text: " Os critérios dependem do título executivo e da tese vinculante aplicável (ADC 58/59 do STF; Lei nº 14.905/2024). A interface não sugere uma combinação: ela transcreve exatamente o que você definir para a tela oficial." })),
        lendoAtualizacao ? avisoLendoCriterios() : null,
        erroLeitura ? h("div", { class: "faixa alerta" }, h("div", { text: `Não foi possível ler os critérios gravados no PJe-Calc (${erroLeitura}). Você ainda pode defini-los aqui.` })) : null,
        h("div", { class: "faixa " + (nAlt ? "alerta" : "ok"), style: "align-items:center" },
          h("div", { text: nAlt ? `${nAlt} critério(s) mudado(s) aqui. Serão gravados no PJe-Calc no próximo envio.`
            : atuais ? "Os campos mostram o que está gravado hoje no PJe-Calc. Mude o que precisar: só o que você mudar será enviado."
            : "Ainda não enviado ao PJe-Calc. Campos em “Padrão do PJe-Calc” ficam com a escolha dele; defina os que o documento do caso indicar." }),
          nAlt ? h("button", { class: "botao pequeno", onclick: desfazer }, atuais ? "Voltar ao que está no PJe-Calc" : "Limpar o que defini") : null),
        h("div", { class: "grade" },
          grupoAt("Correção monetária",
            av("indiceTrabalhista", "Índice de correção", "lista"),
            av("combinarOutroIndice", "Trocar de índice a partir de uma data (combinar)", "marca"),
            atualDe("combinarOutroIndice") ? combos("indicesCombinados", "Índices combinados", "atualizacao.outroIndiceTrabalhista") : null,
            av("ignorarTaxaNegativa", "Ignorar taxa negativa", "marca"),
            av("indiceDeCorrecaoDoFGTS", "Correção do FGTS", "lista")),
          grupoAt("Juros",
            av("juros", "Tabela de juros", "lista"),
            av("combinarOutroJuros", "Trocar de tabela de juros a partir de uma data (combinar)", "marca"),
            atualDe("combinarOutroJuros") ? combos("jurosCombinados", "Tabelas de juros combinadas", "atualizacao.outroJuros") : null,
            av("aplicarJurosFasePreJudicial", "Aplicar juros na fase pré-judicial", "marca"),
            av("baseDeJurosDasVerbas", "Base de juros das verbas", "lista")),
          h("details", { class: "inteiro mais", open: ["correcaoDasCustas", "jurosDeCustas", "correcaoLei11941", "correcaoTrabalhistaDosSalariosDevidosDoINSS", "jurosTrabalhistasDosSalariosDevidosDoINSS",
            "correcaoPrevidenciariaDosSalariosDevidosDoINSS", "jurosPrevidenciariosDosSalariosDevidosDoINSS", "aplicarMultaDosSalariosDevidosDoINSS"].some(alterado) || null },
            h("summary", {}, "Custas e contribuição social"),
            grupoAt("Custas", av("correcaoDasCustas", "Corrigir as custas", "marca"), av("jurosDeCustas", "Juros sobre as custas", "marca")),
            grupoAt("Contribuição social",
              av("correcaoLei11941", "Aplicar a Lei nº 11.941/2009", "marca"),
              av("correcaoTrabalhistaDosSalariosDevidosDoINSS", "Salários devidos: correção trabalhista", "marca"),
              av("jurosTrabalhistasDosSalariosDevidosDoINSS", "Salários devidos: juros trabalhistas", "marca"),
              av("correcaoPrevidenciariaDosSalariosDevidosDoINSS", "Salários devidos: correção previdenciária", "marca"),
              av("jurosPrevidenciariosDosSalariosDevidosDoINSS", "Salários devidos: juros previdenciários", "marca"),
              av("aplicarMultaDosSalariosDevidosDoINSS", "Salários devidos: multa previdenciária", "marca"))))));
  }

  // ---------------------------------------------------------------------------- perguntas guiadas
  // O cálculo pode partir de uma petição inicial (estimativa dos pedidos), de uma decisão (liquidação),
  // de um acordo ou de outro documento. Os textos das perguntas se ajustam ao documento escolhido.
  const DOCUMENTOS = [
    { id: "inicial", rotulo: "Petição inicial", texto: "Estimar o valor dos pedidos, antes da sentença (por exemplo, para o valor da causa).",
      O: "A petição inicial", o: "a petição inicial", no: "na petição inicial", manda: "pede", de: "da petição inicial" },
    { id: "sentenca", rotulo: "Sentença ou acórdão", texto: "Liquidar o que a decisão mandou pagar.",
      O: "A decisão", o: "a decisão", no: "na decisão", manda: "manda pagar", de: "da decisão" },
    { id: "acordo", rotulo: "Acordo", texto: "Calcular ou conferir os valores de um acordo entre as partes.",
      O: "O acordo", o: "o acordo", no: "no acordo", manda: "prevê", de: "do acordo" },
    { id: "outro", rotulo: "Outro documento", texto: "Contestação, impugnação, cálculo de conferência ou outra situação.",
      O: "O documento", o: "o documento", no: "no documento", manda: "prevê", de: "do documento" },
  ];
  const doc = () => DOCUMENTOS.find((x) => x.id === E.caso?.rascunho?.documentoBase) || DOCUMENTOS[3];

  // Cartão de pergunta, usado em todas as perguntas guiadas: título, pergunta, explicação, respostas e,
  // conforme a resposta, um complemento (botão, lista de verbas…). chave = data-campo (alvo de "Corrigir").
  function cartaoPergunta({ chave, titulo, pergunta, explica, respostas, atual, aoResponder, situacao, extra }) {
    const nome = "pq-" + chave.replace(/\W/g, "_");
    const sit = situacao || (atual ? ["ok", (respostas.find(([v]) => v === atual) || [])[1] || "respondida"] : ["neutro", "sem resposta"]);
    return h("article", { class: "item-sentenca " + (atual ? "respondido-" + (sit[0] === "alerta" ? "sim" : "ok") : "sem-resposta"), dataset: { campo: chave } },
      h("div", { class: "item-cab" }, h("h3", { text: titulo }), h("span", { class: "situacao " + sit[0], text: sit[1] })),
      h("p", { class: "pergunta", text: pergunta }),
      explica ? h("p", { class: "mini sutil", text: explica }) : null,
      h("div", { class: "respostas", role: "radiogroup", "aria-label": pergunta },
        respostas.map(([v, rot, dica]) => h("label", { class: "resposta" + (atual === v ? " escolhida" : ""), title: dica || null },
          h("input", { type: "radio", name: nome, value: v, checked: atual === v, onchange: () => aoResponder(v) }), rot))),
      extra || null);
  }
  const responderECarregar = (fn) => (v) => { fn(v); agendarSalvamento(); renderEtapa(); };

  // ---------------------------------------------------------------------------- 1) documento de base
  function perguntaDocumento() {
    const r = E.caso.rascunho;
    const d = DOCUMENTOS.find((x) => x.id === r.documentoBase);
    return h("section", { class: "cartao" }, h("h2", { text: "Ponto de partida" }),
      cartaoPergunta({ chave: "documentoBase", titulo: "Documento de base", pergunta: "Este cálculo é feito a partir de quê?",
        explica: "Todas as perguntas dos próximos passos se ajustam a esta resposta: elas vão falar do que a petição pede, do que a decisão manda pagar ou do que o acordo prevê.",
        respostas: DOCUMENTOS.map((x) => [x.id, x.rotulo, x.texto]), atual: r.documentoBase,
        aoResponder: responderECarregar((v) => { r.documentoBase = v; }),
        extra: d ? h("p", { class: "mini", style: "margin:8px 0 0" }, h("strong", { text: d.rotulo + ": " }), d.texto) : null }));
  }

  // ---------------------------------------------------------------------------- 2) como o contrato terminou
  // Em regra, o que cada forma de término dá direito (CLT; Súmulas 14, 171 e 261 do TST). São sugestões
  // para conferir com o documento: nada é marcado sem o usuário confirmar na etapa Verbas.
  const DESLIGAMENTOS = [
    { id: "sem_justa_causa", rotulo: "Dispensa sem justa causa", verbas: ["SALDO DE SALÁRIO", "AVISO PRÉVIO", "13º SALÁRIO", "FÉRIAS + 1/3"], fgts: true,
      texto: "Em regra: saldo de salário, aviso prévio, 13º proporcional, férias vencidas e proporcionais com 1/3, multa de 40% do FGTS e guias do seguro-desemprego." },
    { id: "rescisao_indireta", rotulo: "Rescisão indireta", verbas: ["SALDO DE SALÁRIO", "AVISO PRÉVIO", "13º SALÁRIO", "FÉRIAS + 1/3"], fgts: true,
      texto: "Falta grave do empregador (art. 483 da CLT). Em regra, as mesmas verbas da dispensa sem justa causa, inclusive a multa de 40% do FGTS." },
    { id: "pedido_demissao", rotulo: "Pedido de demissão", verbas: ["SALDO DE SALÁRIO", "13º SALÁRIO", "FÉRIAS + 1/3"], fgts: false,
      texto: "Em regra: saldo de salário, 13º proporcional e férias vencidas e proporcionais com 1/3 (Súmula 261 do TST). Sem aviso prévio indenizado e sem multa do FGTS." },
    { id: "justa_causa", rotulo: "Justa causa", verbas: ["SALDO DE SALÁRIO", "FÉRIAS + 1/3"], fgts: false,
      texto: "Em regra: só saldo de salário e férias vencidas com 1/3 (Súmula 171 do TST). Se a justa causa foi revertida no processo, escolha “Dispensa sem justa causa”." },
    { id: "culpa_reciproca", rotulo: "Culpa recíproca", verbas: ["SALDO DE SALÁRIO", "AVISO PRÉVIO", "13º SALÁRIO", "FÉRIAS + 1/3"], fgts: true,
      texto: "Em regra: metade do aviso prévio, do 13º e das férias proporcionais, e multa do FGTS de 20% (Súmula 14 do TST). Ajuste a metade no multiplicador de cada verba." },
    { id: "prazo_determinado", rotulo: "Fim do contrato por prazo determinado", verbas: ["SALDO DE SALÁRIO", "13º SALÁRIO", "FÉRIAS + 1/3"], fgts: false,
      texto: "Contrato com data para acabar (experiência, temporário) que terminou no prazo. Em regra: saldo de salário, 13º e férias proporcionais com 1/3, sem aviso prévio." },
    { id: "em_vigor", rotulo: "Contrato ainda em vigor", verbas: [], fgts: false,
      texto: "O trabalhador continua na empresa: não há verbas de rescisão. O cálculo vai só até a data de término do cálculo." },
  ];
  function perguntaDesligamento() {
    const r = E.caso.rascunho;
    const dl = DESLIGAMENTOS.find((x) => x.id === r.desligamento);
    const d = doc();
    return h("section", { class: "cartao" }, h("h2", { text: "Fim do contrato" }),
      cartaoPergunta({ chave: "desligamento", titulo: "Como o contrato terminou", pergunta: `Segundo ${d.o}, como o contrato de trabalho terminou?`,
        explica: "A forma de término define quais verbas da rescisão são devidas. Com a resposta, a etapa Verbas já sugere as verbas certas.",
        respostas: DESLIGAMENTOS.map((x) => [x.id, x.rotulo]), atual: r.desligamento,
        aoResponder: responderECarregar((v) => { r.desligamento = v; }),
        extra: dl ? h("div", { class: "faixa info", style: "margin:10px 0 0" }, h("div", {}, h("strong", { text: dl.rotulo + ". " }), dl.texto,
          dl.verbas.length ? h("p", { class: "mini", style: "margin:6px 0 0" }, "Na etapa Verbas, a pergunta sobre a rescisão já vem com estas verbas sugeridas: ", h("strong", { text: dl.verbas.join(", ") }), ".") : null)) : null }));
  }

  // ---------------------------------------------------------------------------- 3) perguntas para escolher as verbas
  // Cada pergunta leva a verbas do lançamento expresso; "Sim" mostra as verbas para marcar (as sugeridas já vêm marcadas).
  // Os ids são os mesmos de PERGUNTAS_VERBAS em ponte/conferencia.py.
  const PERGUNTAS_VERBAS = [
    { id: "rescisao", grupo: "Fim do contrato", titulo: "Verbas da rescisão", pergunta: (d) => `${d.O} ${d.manda} verbas da rescisão (o que o trabalhador deveria ter recebido ao sair)?`,
      explica: "Saldo de salário são os dias trabalhados no último mês; aviso prévio, o período de aviso não dado; 13º e férias, as partes proporcionais ao tempo trabalhado. A multa do art. 477 é devida quando a rescisão foi paga com atraso.",
      verbas: ["SALDO DE SALÁRIO", "AVISO PRÉVIO", "13º SALÁRIO", "FÉRIAS + 1/3", "MULTA DO ARTIGO 477 DA CLT"],
      sugeridas: () => DESLIGAMENTOS.find((x) => x.id === E.caso.rascunho.desligamento)?.verbas || ["SALDO DE SALÁRIO", "13º SALÁRIO", "FÉRIAS + 1/3"] },
    { id: "horas_extras", grupo: "Jornada", titulo: "Horas extras", pergunta: (d) => `${d.O} ${d.manda} horas extras?`,
      explica: "Horas além da jornada. 50% nos dias normais; 100% em domingos e feriados (ou o que a convenção coletiva fixar). Use “Adicional de horas extras” quando as horas já foram pagas de forma simples e falta só o acréscimo.",
      verbas: ["HORAS EXTRAS 50%", "HORAS EXTRAS 100%", "ADICIONAL DE HORAS EXTRAS 50%"], sugeridas: () => ["HORAS EXTRAS 50%"] },
    { id: "intervalos", grupo: "Jornada", titulo: "Intervalos", pergunta: (d) => `${d.O} ${d.manda} intervalo para almoço/descanso não concedido, ou descanso menor que 11 horas entre um dia e outro?`,
      explica: "Intrajornada é a pausa durante o dia (em regra, 1 hora para quem trabalha mais de 6 horas). Interjornadas são as 11 horas de descanso entre o fim de um dia e o início do outro.",
      verbas: ["INTERVALO INTRAJORNADA", "INTERVALO INTERJORNADAS"], sugeridas: () => ["INTERVALO INTRAJORNADA"] },
    { id: "noturno", grupo: "Jornada", titulo: "Trabalho noturno", pergunta: (d) => `${d.O} ${d.manda} adicional noturno?`,
      explica: "Trabalho entre 22h e 5h (trabalhador urbano) vale 20% a mais.", verbas: ["ADICIONAL NOTURNO 20%"], sugeridas: () => ["ADICIONAL NOTURNO 20%"] },
    { id: "descansos", grupo: "Jornada", titulo: "Domingos, feriados e repouso", pergunta: (d) => `${d.O} ${d.manda} feriados trabalhados em dobro ou repouso semanal remunerado?`,
      explica: "Feriado trabalhado sem folga compensatória é pago em dobro. O repouso semanal remunerado (RSR/DSR) é o dia de descanso pago da semana.",
      verbas: ["FERIADO EM DOBRO", "REPOUSO SEMANAL REMUNERADO"], sugeridas: () => [] },
    { id: "sobreaviso", grupo: "Jornada", titulo: "Sobreaviso e deslocamento", pergunta: (d) => `${d.O} ${d.manda} horas de sobreaviso ou de deslocamento (in itinere)?`,
      explica: "Sobreaviso: tempo de espera à disposição da empresa, fora do local de trabalho. In itinere: tempo de deslocamento até o trabalho, em situações anteriores à Reforma Trabalhista (11/2017).",
      verbas: ["ADICIONAL DE SOBREAVISO", "HORAS IN ITINERE"], sugeridas: () => [] },
    { id: "insalubridade", grupo: "Adicionais", titulo: "Insalubridade", pergunta: (d) => `${d.O} ${d.manda} adicional de insalubridade?`,
      explica: "Trabalho com agentes nocivos à saúde. O grau (mínimo 10%, médio 20%, máximo 40%) vem do laudo pericial ou da decisão. Escolha só um grau por período; a base costuma ser o salário mínimo.",
      verbas: ["ADICIONAL DE INSALUBRIDADE 10%", "ADICIONAL DE INSALUBRIDADE 20%", "ADICIONAL DE INSALUBRIDADE 40%"], sugeridas: () => ["ADICIONAL DE INSALUBRIDADE 20%"] },
    { id: "periculosidade", grupo: "Adicionais", titulo: "Periculosidade e risco", pergunta: (d) => `${d.O} ${d.manda} adicional de periculosidade ou de risco?`,
      explica: "Periculosidade: 30% sobre o salário-base, para trabalho com inflamáveis, explosivos, energia elétrica, segurança ou motocicleta. Não se acumula com insalubridade: escolha um.",
      verbas: ["ADICIONAL DE PERICULOSIDADE 30%", "ADICIONAL DE RISCO 40%"], sugeridas: () => ["ADICIONAL DE PERICULOSIDADE 30%"] },
    { id: "transferencia", grupo: "Adicionais", titulo: "Transferência", pergunta: (d) => `${d.O} ${d.manda} adicional de transferência?`,
      explica: "25% enquanto durar a transferência provisória para outra cidade.", verbas: ["ADICIONAL DE TRANSFERÊNCIA 25%"], sugeridas: () => ["ADICIONAL DE TRANSFERÊNCIA 25%"] },
    { id: "salario", grupo: "Salário", titulo: "Salário não pago ou pago a menor", pergunta: (d) => `${d.O} ${d.manda} salários atrasados ou diferenças de salário?`,
      explica: "Salário retido: meses não pagos. Diferença salarial: quando o salário pago foi menor que o devido (piso da categoria, equiparação, desvio de função, reajuste).",
      verbas: ["SALÁRIO RETIDO", "DIFERENÇA SALARIAL"], sugeridas: () => [] },
    { id: "variaveis", grupo: "Salário", titulo: "Comissões, prêmios e gratificações", pergunta: (d) => `${d.O} ${d.manda} comissões, prêmios, gratificações ou participação nos lucros?`,
      explica: "Parcelas variáveis ou adicionais ao salário que não foram pagas ou foram pagas a menor.",
      verbas: ["COMISSÃO", "PRÊMIO PRODUÇÃO", "GRATIFICAÇÃO DE FUNÇÃO", "GRATIFICAÇÃO POR TEMPO DE SERVIÇO", "PARTICIPAÇÃO NOS LUCROS OU RESULTADOS - PLR", "GORJETA"], sugeridas: () => [] },
    { id: "beneficios", grupo: "Salário", titulo: "Benefícios", pergunta: (d) => `${d.O} ${d.manda} vale-transporte, vale-alimentação ou cesta básica?`,
      explica: "Benefícios previstos em lei ou na convenção coletiva que não foram fornecidos.",
      verbas: ["VALE TRANSPORTE", "TÍQUETE-ALIMENTAÇÃO", "CESTA BÁSICA"], sugeridas: () => [] },
    { id: "devolucoes", grupo: "Salário", titulo: "Descontos e despesas", pergunta: (d) => `${d.O} ${d.manda} devolução de descontos indevidos ou reembolso de despesas?`,
      explica: "Valores descontados do salário sem autorização, ou gastos do trabalhador que a empresa deveria ter pago.",
      verbas: ["DEVOLUÇÃO DE DESCONTOS INDEVIDOS", "RESTITUIÇÃO / INDENIZAÇÃO DE DESPESA"], sugeridas: () => [] },
    { id: "estabilidade", grupo: "Indenizações", titulo: "Estabilidade e outras indenizações", pergunta: (d) => `${d.O} ${d.manda} indenização por estabilidade, salário-maternidade, abono do PIS ou indenização adicional?`,
      explica: "Estabilidade (gestante, acidente, CIPA): salários do período em que o trabalhador não podia ser dispensado. Indenização adicional: dispensa nos 30 dias antes da data-base. Abono do PIS: quando a empresa não informou o trabalhador. Dano moral e outros valores fixos ficam em “Outros itens do cálculo”.",
      verbas: ["SALÁRIO MATERNIDADE", "INDENIZAÇÃO ADICIONAL", "INDENIZAÇÃO PIS - ABONO SALARIAL"], sugeridas: () => [] },
  ];
  // nome exatamente como no catálogo do PJe-Calc (as perguntas citam as verbas sem depender de acento/caixa)
  const verbaDoCatalogo = (n) => (E.opcoes?.expressas || []).find((v) => dobrar(v) === dobrar(n)) || null;
  function perguntasVerbas(aoMudar) {
    const r = E.caso.rascunho;
    r.perguntasVerbas = r.perguntasVerbas || {};
    const resp = r.perguntasVerbas, d = doc();
    const sem = PERGUNTAS_VERBAS.filter((p) => !resp[p.id]).length;
    const cartao = (p) => {
      const nomes = p.verbas.map(verbaDoCatalogo).filter(Boolean);
      const marcadas = nomes.filter((n) => r.verbas.includes(n));
      const responder = (v) => {
        resp[p.id] = v;
        // "Sim" marca as sugeridas (se nenhuma verba da pergunta estiver marcada ainda); "Não" não desmarca nada sozinho
        if (v === "sim" && !marcadas.length) p.sugeridas().map(verbaDoCatalogo).filter(Boolean).forEach((n) => { if (!r.verbas.includes(n)) r.verbas.push(n); });
        agendarSalvamento(); aoMudar();
      };
      const lista = resp[p.id] === "sim" ? h("div", { class: "verbas-da-pergunta" },
        h("p", { class: "mini", style: "margin:8px 0 4px;font-weight:600", text: "Marque as verbas que se aplicam:" }),
        h("div", { class: "chips" }, nomes.map((n) => {
          const id = "pv-" + p.id + "-" + dobrar(n).replace(/\W/g, "");
          const cb = h("input", { type: "checkbox", id, checked: r.verbas.includes(n) });
          cb.addEventListener("change", () => { if (cb.checked) { if (!r.verbas.includes(n)) r.verbas.push(n); } else r.verbas = r.verbas.filter((x) => x !== n); agendarSalvamento(); aoMudar(); });
          return h("label", { class: "marcacao", for: id }, cb, n);
        })),
        !marcadas.length ? h("p", { class: "erro-campo", text: "Nenhuma verba marcada: marque pelo menos uma, ou responda “Não”." }) : null)
        : resp[p.id] === "nao" && marcadas.length ? h("p", { class: "mini negativo", style: "margin-top:8px", text: `Atenção: ${marcadas.join(", ")} continua(m) marcada(s) no catálogo. Desmarque abaixo se não se aplica(m).` }) : null;
      return cartaoPergunta({ chave: "perguntasVerbas." + p.id, titulo: p.titulo, pergunta: p.pergunta(d), explica: p.explica,
        respostas: [["sim", "Sim"], ["nao", "Não"]], atual: resp[p.id], aoResponder: responder,
        situacao: resp[p.id] === "sim" ? (marcadas.length ? ["ok", `${marcadas.length} verba(s)`] : ["alerta", "marque as verbas"]) : resp[p.id] === "nao" ? ["ok", "não"] : null,
        extra: lista });
    };
    const grupos = [...new Set(PERGUNTAS_VERBAS.map((p) => p.grupo))];
    return h("section", { class: "cartao" },
      h("div", { style: "display:flex;gap:8px;align-items:center" }, h("span", { class: "passo-num", text: "1" }), h("h2", { text: `O que ${d.o} ${d.manda}?`, style: "margin:0" })),
      h("p", { class: "mini sutil", text: `Responda Sim ou Não a cada pergunta${sem ? ` (faltam ${sem} de ${PERGUNTAS_VERBAS.length})` : ""}. Cada “Sim” marca as verbas certas do catálogo do PJe-Calc. Se ${d.o} trouxer algo que não está nas perguntas, procure no catálogo completo, logo abaixo.` }),
      !E.caso.rascunho.desligamento ? h("div", { class: "faixa alerta" }, h("div", {}, "Dica: responda primeiro ", h("a", { href: `#/caso/${E.caso.id}/contrato` }, "como o contrato terminou (etapa Contrato)"), ": assim a pergunta da rescisão já sugere as verbas certas.")) : null,
      grupos.map((g) => h("div", {}, h("h3", { class: "grupo-perguntas", text: g }), h("div", { class: "itens-sentenca" }, PERGUNTAS_VERBAS.filter((p) => p.grupo === g).map(cartao)))));
  }

  // ---------------------------------------------------------------------------- 4) outros itens do cálculo
  // Itens que o PJe-Calc calcula em telas próprias (abertas aqui, no cálculo certo). Para que nada seja esquecido,
  // cada um é uma pergunta: "não se aplica", "sim, preencher" ou "já preenchido". A lista de ids é a mesma de
  // OUTROS_ITENS em ponte/conferencia.py, que cobra as perguntas sem resposta em "Revisar tudo".
  const OUTROS_ITENS = [
    { id: "ferias", grupo: "Contrato e jornada", nome: "Férias", pergunta: (d) => `${d.O} ${d.manda} férias, ou o trabalhador tirou férias durante o contrato?`,
      explica: () => "Na tela Férias ficam os períodos aquisitivos e as férias que o trabalhador já tirou (gozadas), vendeu (abono) ou deve receber em dobro. Conferir isso evita pagar férias já tiradas ou deixar de pagar as que não foram." },
    { id: "faltas", grupo: "Contrato e jornada", nome: "Faltas", pergunta: (d) => `Houve faltas a considerar, segundo ${d.o}?`,
      explica: () => "Faltas sem justificativa reduzem férias e 13º salário e podem descontar dias das verbas. Informe as datas das faltas, justificadas ou não." },
    { id: "cartao", grupo: "Contrato e jornada", nome: "Cartão de ponto", pergunta: (d) => `As horas extras, o adicional noturno ou os intervalos vêm dos horários de entrada e saída (cartão de ponto ou jornada descrita ${d.no})?`,
      explica: (d) => `O cartão de ponto apura as horas mês a mês a partir dos horários. Se ${d.o} já traz uma quantidade de horas por mês, basta informá-la na verba (etapa Verbas) e responder “Não se aplica” aqui.` },
    { id: "multas", grupo: "Valores fixos", nome: "Dano moral, multas e indenizações", pergunta: (d) => `${d.O} ${d.manda} algum valor fixo, como dano moral, dano material, dano estético ou multa da convenção coletiva?`,
      explica: () => "Valores fixos (que não são calculados mês a mês) entram na tela Multas e Indenizações, com o valor e a data a partir da qual são corrigidos. A multa do art. 477 da CLT entra como verba, na etapa Verbas." },
    { id: "seguro-desemprego", grupo: "Valores fixos", nome: "Seguro-desemprego", pergunta: (d) => `${d.O} ${d.manda} indenização no lugar do seguro-desemprego (porque as guias não foram entregues)?`,
      explica: () => "O PJe-Calc calcula o número de parcelas e o valor pela tabela oficial do seguro-desemprego." },
    { id: "salario-familia", grupo: "Valores fixos", nome: "Salário-família", pergunta: (d) => `${d.O} ${d.manda} salário-família?`,
      explica: () => "Benefício por filho de até 14 anos, pago a quem ganha até o limite da tabela. Informe o número de filhos por período." },
    { id: "honorarios", grupo: "Despesas do processo", nome: "Honorários", pergunta: (d) => d.id === "inicial" ? "A petição inicial pede honorários de advogado (sucumbência)?" : `${d.O} ${d.id === "sentenca" ? "fixou" : "prevê"} honorários de advogado (sucumbência) ou de perito?`,
      explica: (d) => d.id === "inicial" ? "Na petição, honorários costumam ser pedidos entre 5% e 15% da condenação (art. 791-A da CLT). Inclua se quiser que a estimativa já mostre esse valor."
        : "Informe quem paga, o percentual (honorários de advogado ficam entre 5% e 15%, art. 791-A da CLT) ou o valor fixo, e sobre o que incidem." },
    { id: "custas", grupo: "Despesas do processo", nome: "Custas processuais", pergunta: (d) => d.id === "inicial" ? "Quer incluir uma estimativa das custas?" : `${d.O} ${d.id === "sentenca" ? "fixou" : "prevê"} custas?`,
      explica: (d) => d.id === "inicial" ? "As custas são fixadas pelo juiz só na sentença. Numa estimativa, dá para incluir o valor provável: em regra, 2% sobre o valor da condenação (art. 789 da CLT)."
        : "Quase toda decisão fixa custas: na Justiça do Trabalho, em regra, 2% sobre o valor da condenação, pagas por quem perdeu (art. 789 da CLT). Confira quem paga e a base." },
    { id: "inss", grupo: "Descontos e tributos", nome: "Contribuição previdenciária (INSS)", pergunta: (d) => `Confira a contribuição ao INSS: ${d.o} diz algo sobre ela?`,
      explica: (d) => `Sobre as verbas de natureza salarial incide INSS do trabalhador (descontado do crédito) e do empregador. A tela Contribuição Social define como o PJe-Calc apura. Mesmo que ${d.o} não diga nada específico, vale abrir e conferir.` },
    { id: "irpf", grupo: "Descontos e tributos", nome: "Imposto de renda", pergunta: (d) => `Confira o imposto de renda: ${d.o} diz algo sobre ele, ou o trabalhador tem dependentes?`,
      explica: () => "O imposto de renda é descontado do crédito do trabalhador. Na tela Imposto de Renda ficam o número de dependentes e as deduções." },
    { id: "pensao", grupo: "Descontos e tributos", nome: "Pensão alimentícia", pergunta: () => "O trabalhador paga pensão alimentícia que deve ser descontada do crédito?",
      explica: () => "Informe o percentual da pensão. Além disso, marque a incidência de pensão nas verbas (etapa Reflexos e FGTS)." },
    { id: "previdencia", grupo: "Descontos e tributos", nome: "Previdência privada", pergunta: () => "Há desconto de previdência privada a fazer?",
      explica: () => "Informe o percentual descontado, se o trabalhador tinha previdência complementar pela empresa." },
  ];
  const RESPOSTAS_OUTROS = [["nao", "Não se aplica"], ["sim", "Sim, preciso preencher"], ["feito", "Já preenchi"]];
  async function etapaOutros() {
    const r = E.caso.rascunho;
    r.outrosItens = r.outrosItens || {};
    const resp = r.outrosItens, d = doc();
    const sem = OUTROS_ITENS.filter((i) => !resp[i.id]).length, pend = OUTROS_ITENS.filter((i) => resp[i.id] === "sim").length;
    const enviado = !!E.caso.pjecalc?.calculoId;
    const cartao = (i) => {
      const atual = resp[i.id] || "";
      return cartaoPergunta({ chave: "outros." + i.id, titulo: i.nome, pergunta: i.pergunta(d), explica: i.explica(d), respostas: RESPOSTAS_OUTROS, atual,
        aoResponder: responderECarregar((v) => { resp[i.id] = v; }),
        situacao: atual === "sim" ? ["alerta", "a preencher"] : atual === "feito" ? ["ok", "preenchido"] : atual === "nao" ? ["ok", "não se aplica"] : null,
        extra: atual === "sim" || atual === "feito" ? h("div", { class: "acao-item" },
          h("a", { class: "botao " + (atual === "sim" ? "primario" : ""), href: `#/caso/${E.caso.id}/original/${i.id}` }, atual === "sim" ? `Preencher ${i.nome} no PJe-Calc →` : `Abrir ${i.nome} de novo`),
          enviado ? null : h("span", { class: "mini sutil", text: "A tela abre depois do primeiro envio ao PJe-Calc (ela grava direto no cálculo de lá)." })) : null });
    };
    const grupos = [...new Set(OUTROS_ITENS.map((i) => i.grupo))];
    return h("div", {}, avisosDaEtapa("outros"),
      E.caso.rascunho.documentoBase ? null : perguntaDocumento(),
      h("div", { class: "faixa " + (sem || pend ? "info" : "ok") },
        h("strong", { text: sem || pend ? "Para não esquecer nada:" : "Tudo respondido." }),
        h("div", { text: sem || pend
          ? `responda cada pergunta com o que diz ${d.o}. ${sem ? `Faltam ${sem} de ${OUTROS_ITENS.length}.` : ""} ${pend ? `${pend} item(ns) marcado(s) para preencher.` : ""} Na dúvida, escolha “Sim” e abra a tela: ela explica cada campo.`
          : "Os itens que se aplicam ao caso estão preenchidos. Continue para revisar tudo." })),
      grupos.map((g) => h("section", { class: "cartao" }, h("h2", { text: g }), h("div", { class: "itens-sentenca" }, OUTROS_ITENS.filter((i) => i.grupo === g).map(cartao)))));
  }

  // ---------------------------------------------------------------------------- conferência ("revise antes de enviar")
  const rotOp = (chave, v) => (op(chave).find((o) => o.valor === v) || {}).rotulo || v;
  async function etapaConferencia() {
    E.conferencia = await api("GET", `/api/casos/${E.caso.id}/conferir`);
    desenharLateralCaso();
    const r = E.caso.rascunho, d = r.dados || {};
    const av = E.conferencia.avisos;
    const imp = av.filter((a) => a.nivel === "impeditivo"), ale = av.filter((a) => a.nivel === "alerta");
    const nomeEt = (id) => (ETAPAS.find((e) => e.id === id) || {}).titulo || id;
    const listaAv = (itens, nivel) => h("ul", { class: "lista-avisos" }, itens.map((a) => h("li", {},
      h("span", { class: "marcador " + nivel, text: nivel === "impeditivo" ? "Impede o envio" : "Avaliar" }), h("span", { text: a.texto }),
      botaoCorrigir({ texto: a.texto, etapa: a.etapa, campo: a.campo }))));
    // linha do resumo: rótulo, valor (vazio explícito) e "Alterar" que leva ao campo
    const vazio = (t) => h("span", { class: "vazio", text: t });
    const linha = (rot, valor, etapa, campo) => h("div", {}, h("dt", { text: rot }), h("dd", {}, valor === undefined || valor === null || valor === "" ? vazio("Não informado") : valor),
      h("dd", { class: "acao" }, h("a", { href: `#/caso/${E.caso.id}/${etapa}`, "aria-label": `Alterar ${rot.toLowerCase()}`, onclick: (ev) => { ev.preventDefault(); irParaCampo(etapa, campo); } }, "Alterar")));
    const secao = (etapa, ...linhas) => { const s = estadoEtapa(etapa); return h("section", { "aria-labelledby": "rs-" + etapa },
      h("div", { class: "resumo-secao" }, h("h2", { id: "rs-" + etapa, text: nomeEt(etapa) }),
        h("span", { class: "situacao " + ({ ok: "ok", erro: "erro", alerta: "alerta", andamento: "alerta", padrao: "neutro", vazio: "neutro" }[s.estado] || "neutro"), text: s.texto })),
      h("dl", { class: "resumo-lista" }, linhas.filter(Boolean))); };
    const sn = (k) => { const v = d[k] !== undefined ? d[k] : PADROES[k]; return v === undefined ? undefined : (v ? "Sim" : "Não") + (d[k] === undefined ? " (padrão do PJe-Calc)" : ""); };
    const doc = (p) => d[p + ".numeroDocumentoFiscal"] ? `${d[p + ".tipoDocumentoFiscal"] || "Documento"} ${d[p + ".numeroDocumentoFiscal"]}` : "";
    const proc = numeroProcesso(d) || vazio("Não informado (opcional em estimativas; necessário para anexar ao PJe)");
    const hist = (r.historicos || []).map((x) => { const oc = x.ocorrencias || []; const semValor = oc.filter((o) => o.valor === "" || o.valor == null).length;
      return linha(x.nome || "Histórico sem nome", oc.length ? `${oc[0].competencia} a ${oc[oc.length - 1].competencia} · ${oc.length} mês(es)${semValor ? ` · ${semValor} sem valor` : ""}` : vazio("Sem competências"), "historico"); });
    const verbas = [...(r.verbas || []).map((v) => ({ nome: v, tipo: "catálogo" })), ...(r.verbasManuais || []).filter((v) => v.descricao).map((v) => ({ nome: v.descricao + (v.parametros?.tipoDeVerba === "REFLEXO" && v.principal ? " sobre " + v.principal : ""), tipo: v.parametros?.tipoDeVerba === "REFLEXO" ? "reflexo manual" : "manual" }))];
    const altOc = (n) => ((r.verbasConfig || {})[n]?.ocorrencias || []).filter((o) => ["quantidade", "devido", "pago", "divisor", "multiplicador"].some((k) => o[k]) || o.ativo === false).length;
    const at = r.atualizacao || {}, liq = r.liquidacao || {};
    const reflexosAlt = Object.entries(r.verbasConfig || {}).flatMap(([v, c]) => Object.entries(c.reflexos || {}).map(([nome, ativo]) => `${ativo ? "Ativar" : "Desativar"}: ${nome}`));
    const of = E.conferencia.pendenciasPjecalc || [];
    let quadro = null;
    if (E.caso.pjecalc?.calculoId) {
      const { crit, erro, lendo } = criteriosSemEsperar();
      quadro = crit ? quadroCriterios(crit) : lendo ? avisoLendoCriterios()
        : erro ? h("div", { class: "faixa erro", text: "Não foi possível ler os critérios do PJe-Calc: " + erro }) : null;
    }
    return h("div", {},
      imp.length ? h("div", { class: "faixa erro", role: "alert" }, h("strong", { text: `${imp.length} item(ns) impedem o envio ao PJe-Calc.` }), h("div", { text: "Corrija-os pelo link de cada item; o restante do que você preencheu continua salvo." }))
        : h("div", { class: "faixa ok" }, h("strong", { text: "Nada impede o envio." }), h("div", { text: ale.length ? `Há ${ale.length} alerta(s) para avaliar antes de calcular.` : "Revise as seções abaixo e continue para enviar e calcular." })),
      imp.length ? h("section", { class: "cartao" }, h("h2", { text: "Para corrigir antes de enviar" }), listaAv(imp, "impeditivo")) : null,
      ale.length ? h("section", { class: "cartao" }, h("h2", { text: "Para avaliar" }), h("p", { class: "sutil", text: "Não impedem o envio, mas podem indicar um preenchimento incompleto ou uma escolha que depende do caso." }), listaAv(ale, "alerta")) : null,
      h("div", { class: "cartao" },
        secao("identificacao",
          linha("Documento de base", (DOCUMENTOS.find((x) => x.id === r.documentoBase) || {}).rotulo, "identificacao", "documentoBase"),
          linha("Reclamante", [d["reclamante.nome"], doc("reclamante")].filter(Boolean).join(" · "), "identificacao", "reclamante.nome"),
          linha("Reclamado", [d["reclamado.nome"], doc("reclamado")].filter(Boolean).join(" · "), "identificacao", "reclamado.nome"),
          linha("Processo", proc, "identificacao", "processo.numero"),
          linha("Local da prestação", [d["local.municipio"], d["local.estado"]].filter(Boolean).join(" / "), "identificacao", "local.estado")),
        secao("contrato",
          linha("Fim do contrato", (DESLIGAMENTOS.find((x) => x.id === r.desligamento) || {}).rotulo, "contrato", "desligamento"),
          linha("Admissão", d["contrato.dataAdmissao"], "contrato", "contrato.dataAdmissao"),
          linha("Demissão", d["contrato.dataDemissao"] || vazio("Não informada (contrato em vigor ou não se aplica)"), "contrato", "contrato.dataDemissao"),
          linha("Ajuizamento", d["contrato.dataAjuizamento"], "contrato", "contrato.dataAjuizamento"),
          d["contrato.dataInicioCalculo"] || d["contrato.dataTerminoCalculo"] ? linha("Período do cálculo", `${d["contrato.dataInicioCalculo"] || "admissão"} a ${d["contrato.dataTerminoCalculo"] || "demissão"}`, "contrato", "contrato.dataInicioCalculo") : null,
          linha("Prescrição quinquenal", sn("contrato.prescricaoQuinquenal"), "contrato", "contrato.prescricaoQuinquenal"),
          linha("Maior remuneração", d["contrato.maiorRemuneracao"] ? "R$ " + d["contrato.maiorRemuneracao"] : "", "contrato", "contrato.maiorRemuneracao"),
          linha("Última remuneração", d["contrato.ultimaRemuneracao"] ? "R$ " + d["contrato.ultimaRemuneracao"] : "", "contrato", "contrato.ultimaRemuneracao"),
          linha("Aviso prévio", d["contrato.apuracaoAvisoPrevio"] ? rotOp("contrato.apuracaoAvisoPrevio", d["contrato.apuracaoAvisoPrevio"]) + (d["contrato.prazoAvisoInformado"] ? ` (${d["contrato.prazoAvisoInformado"]} dias)` : "") : vazio("Padrão do PJe-Calc (calculado)"), "contrato", "contrato.apuracaoAvisoPrevio")),
        secao("historico", ...(hist.length ? hist : [linha("Histórico salarial", d["contrato.ultimaRemuneracao"] ? `Nenhum histórico próprio; o PJe-Calc usa a última remuneração (R$ ${d["contrato.ultimaRemuneracao"]}) em todo o período` : "", "historico")])),
        secao("jornada",
          linha("Carga horária mensal", d["jornada.cargaHorariaPadrao"] || vazio("Padrão do PJe-Calc (220,00)"), "jornada", "jornada.cargaHorariaPadrao"),
          linha("Sábado como dia útil", sn("jornada.sabadoDiaUtil"), "jornada", "jornada.sabadoDiaUtil")),
        secao("verbas", ...(verbas.length ? verbas.map((v) => linha(v.nome, [v.tipo, altOc(v.nome) ? `${altOc(v.nome)} mês(es) com quantidade ou valor informado` : "valores mensais calculados pelo PJe-Calc"].join(" · "), "verbas")) : [linha("Verbas", "", "verbas")])),
        secao("reflexos",
          linha("Reflexos e incidências", reflexosAlt.length ? reflexosAlt.join("; ") : vazio(E.caso.pjecalc?.calculoId ? "Sem alteração: valem as escolhas padrão do PJe-Calc" : "Disponíveis depois do primeiro envio"), "reflexos"),
          linha("FGTS", Object.keys(r.fgts || {}).length ? Object.entries(r.fgts).map(([k, v]) => `${k}: ${v === true ? "sim" : v === false ? "não" : rotOp("fgts." + k, v)}`).join("; ") : vazio("Sem alteração: padrão do PJe-Calc"), "reflexos")),
        secao("atualizacao",
          linha("Data de liquidação", liq.data || vazio("Sugerida pelo PJe-Calc (último dia do mês corrente)"), "atualizacao"),
          linha("Correção e juros", Object.keys(at.valores || {}).length ? `${rotOp("atualizacao.indiceTrabalhista", at.valores.indiceTrabalhista) || "índice não escolhido"}${at.valores.juros ? " · juros: " + rotOp("atualizacao.juros", at.valores.juros) : ""}` : vazio("Mantém os critérios já gravados no PJe-Calc"), "atualizacao")),
        secao("outros", ...OUTROS_ITENS.map((i) => { const v = (r.outrosItens || {})[i.id];
          return linha(i.nome, v === "nao" ? "Não se aplica" : v === "feito" ? "Preenchido no PJe-Calc" : v === "sim" ? h("span", { class: "negativo", text: "Falta preencher no PJe-Calc" }) : vazio("Sem resposta"), "outros", "outros." + i.id); }))),
      h("section", { class: "cartao" }, h("h2", { text: "Pendências apuradas pelo PJe-Calc" }),
        E.caso.pjecalc?.calculoId ? (E.conferencia.pendenciasAtuais ? listaMensagens(of, true) : h("div", {}, h("div", { class: "faixa alerta" }, h("div", { text: "Estas pendências são do último envio. O rascunho mudou depois disso: envie de novo para atualizá-las." })), listaMensagens(of, true)))
          : h("p", { class: "sutil", text: "O PJe-Calc só aponta as pendências dele depois do primeiro envio." }),
        h("button", { class: "botao", onclick: async () => { await operar("gravar"); renderEtapa(); } }, "Enviar ao PJe-Calc e atualizar pendências")),
      h("section", { class: "cartao" }, h("h2", { text: "Critérios de cada verba (lidos do PJe-Calc)" }),
        h("p", { class: "sutil", text: "Base, divisor, multiplicador, reflexos e a fórmula montada pelo próprio PJe-Calc, ao lado do fundamento que você registrou." }),
        quadro || h("p", { class: "sutil", text: "Disponível depois do primeiro envio ao PJe-Calc." })),
      decisoesGerais());
  }
  function quadroCriterios(c) {
    if (!c) return null;
    const r = E.caso.rascunho;
    const val = (v, id) => { const x = v.campos.find((k) => k.id === id); if (!x) return "—"; if (typeof x.valor === "boolean") return x.valor ? "Sim" : "Não"; return (x.opcoes || []).find((o) => o.valor === x.valor)?.rotulo || x.valor || "—"; };
    const inc = (v) => ["irpf", "inss", "fgts"].filter((id) => v.campos.find((k) => k.id === id)?.valor).map((id) => ({ irpf: "IRPF", inss: "CS", fgts: "FGTS" }[id])).join(", ") || "nenhuma";
    return h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Verba", "Período", "Base", "Divisor", "Multiplicador", "Quantidade", "Reflexos ativos", "Incidências", "Fórmula (PJe-Calc)", "Fundamento"].map((t) => h("th", { scope: "col", text: t })))),
      h("tbody", {}, c.verbas.map((v) => { const cfg = r.verbasConfig?.[v.nome] || {};
        return h("tr", {}, h("th", { scope: "row", text: v.nome }), h("td", { text: `${val(v, "periodoInicialInputDate")} a ${val(v, "periodoFinalInputDate")}` }),
          h("td", { text: [val(v, "tipoDaBaseTabelada"), (v.bases || []).join(" + ")].filter((x) => x && x !== "—").join(": ") }),
          h("td", { class: "num", text: val(v, "outroValorDoDivisor") }), h("td", { class: "num", text: val(v, "outroValorDoMultiplicador") }), h("td", { text: val(v, "tipoDaQuantidade") }),
          h("td", { text: (v.reflexos || []).filter((x) => x.ativo).map((x) => x.nome).join("; ") || "nenhum" }), h("td", { text: inc(v) }),
          h("td", {}, v.formula ? h("code", { class: "formula", text: v.formula }) : "—"),
          h("td", { class: "mini", text: [cfg.justificativa, cfg.trecho ? `“${cfg.trecho}”` : ""].filter(Boolean).join(" — ") || "não registrado" })); }))));
  }
  function decisoesGerais() {
    const d = E.caso.rascunho.decisoes || [];
    return h("section", { class: "cartao" }, h("h2", { text: "Fundamentos registrados para escolhas do caso concreto" }),
      d.length ? h("ul", { class: "lista-avisos" }, d.map((x) => h("li", {}, h("span", { class: "marcador info", text: "Decisão" }),
        h("span", {}, h("strong", { text: (x.rotulo || x.campo) + ": " }), x.texto || "", x.trecho ? h("div", { class: "mini sutil", text: `“${x.trecho}” ${x.documento ? "— " + x.documento : ""}` }) : null)))) : h("p", { class: "sutil", text: "Nenhum fundamento registrado. Use “Registrar fundamento da escolha” nos campos marcados como decisão do usuário." }));
  }

  // ---------------------------------------------------------------------------- operações com o PJe-Calc
  async function operar(tipo) {
    if (!E.caso) return;
    if (E.pendente && !(await salvarAgora())) {
      // nunca enviar ao PJe-Calc uma versão diferente da que está na tela
      avisar("Nada foi enviado ao PJe-Calc: o rascunho desta janela ainda não está salvo. Resolva o aviso de salvamento e tente de novo.", "erro", 12000);
      return;
    }
    const rot = tipo === "gravar" ? "Enviando ao PJe-Calc" : "Calculando no PJe-Calc";
    const d = $("#dialogo");
    preencher(d, h("div", { class: "dlg-cab" }, h("h2", { text: rot + "…" })), h("div", { class: "dlg-corpo" },
      h("p", { role: "status", text: "As telas do PJe-Calc estão sendo preenchidas e validadas pelo próprio programa. Isto pode levar de alguns segundos a poucos minutos; não feche esta janela nem o PJe-Calc." })));
    d.showModal();
    let r;
    try { r = await api("POST", `/api/casos/${E.caso.id}/${tipo}`); }
    catch (e) {
      d.close();
      avisar(e.message, "erro", 12000); return;
    }
    d.close();
    E.ultimaOperacao = { tipo, ...r, em: new Date().toISOString() };
    if (r.caso) { E.caso = r.caso; E.estadoRes = r.estado; E.criterios = null; }
    try { E.conferencia = await api("GET", `/api/casos/${E.caso.id}/conferir`); } catch { /* ok */ }
    desenharLateralCaso(); atualizarBarra();
    if (r.etapa === "conferencia") {
      await dialogo({ titulo: "Há itens que impedem o envio", corpo: h("div", {}, h("p", { text: "Nada foi enviado ao PJe-Calc. Corrija os itens abaixo; a etapa Revisar tudo leva direto a cada campo." }), listaMensagens(r.avisos)),
        botoes: [{ texto: "Ir para Revisar tudo", valor: true, classe: "primario" }] });
      location.hash = `#/caso/${E.caso.id}/conferencia`; return;
    }
    const titulo = r.ok ? (tipo === "gravar" ? "Dados enviados ao PJe-Calc" : "Cálculo feito pelo PJe-Calc") : (tipo === "gravar" ? "O PJe-Calc não aceitou todos os dados" : "O cálculo não foi feito");
    const ir = await dialogo({ titulo, largo: true, corpo: h("div", {},
      r.ok && tipo === "executar" ? h("div", { class: "faixa ok" }, h("div", { text: `Calculado pelo PJe-Calc ${r.execucao?.versaoMotor || ""}. O relatório oficial e o arquivo .PJC foram guardados.` })) : null,
      !r.ok && r.etapa === "pendencias" ? h("div", { class: "faixa erro" }, h("div", { text: "O PJe-Calc apontou pendências do tipo “Erro”, que impedem calcular. Veja cada mensagem abaixo; em geral elas indicam a etapa a corrigir (por exemplo, a base de uma verba). Depois de corrigir, use “Calcular” de novo." })) : null,
      mostrarPassos(r.passos)),
      botoes: r.ok && tipo === "executar" ? [{ texto: "Fechar", valor: false }, { texto: "Ver o resultado", valor: true, classe: "primario" }] : [{ texto: "Fechar", valor: false }] });
    if (ir) location.hash = `#/caso/${E.caso.id}/resultado`;
    else renderEtapa();
  }

  async function etapaCalculo() {
    const est = E.estadoRes || {}, vinc = E.caso.pjecalc || {};
    const u = E.ultimaOperacao;
    return h("div", {},
      !E.motor?.acessivel ? h("div", { class: "faixa erro", role: "alert" }, h("strong", { text: "PJe-Calc desconectado." }), h("div", { text: " Inicie o PJe-Calc pelo atalho oficial e aguarde a tela inicial. O rascunho continua salvo nesta interface." })) : null,
      h("section", { class: "cartao" }, h("h2", { text: "Situação" }),
        h("dl", { class: "resumo-lista" },
          h("div", {}, h("dt", { text: "Rascunho" }), h("dd", { text: `Revisão ${E.caso.revisao}${E.pendente ? ", com alterações ainda não salvas" : ", salvo neste computador"}` }), h("dd", {})),
          h("div", {}, h("dt", { text: "PJe-Calc" }), h("dd", { text: vinc.calculoId ? `Cálculo nº ${vinc.calculoId}: recebeu a revisão ${vinc.gravadoRevisao} em ${quando(vinc.gravadoEm)}${est.gravadoAtual && !E.pendente ? " (igual ao rascunho)" : " — há alterações ainda não enviadas"}` : "Nada enviado ainda" }), h("dd", {})),
          h("div", {}, h("dt", { text: "Resultado" }), h("dd", { text: est.ultimaExecucao ? (est.resultadoAtual && !E.pendente ? "Atualizado" : "Desatualizado: os dados mudaram depois do último cálculo") : "Ainda não calculado" }), h("dd", {})),
          h("div", {}, h("dt", { text: "PJe-Calc em uso" }), h("dd", { text: E.motor?.acessivel ? `${E.motor.versao} (build ${E.motor.build})` : "Não está respondendo" }), h("dd", {})))),
      h("section", { class: "cartao" }, h("h2", { text: "O que cada botão faz" }),
        h("dl", { class: "resumo-lista" },
          h("div", {}, h("dt", { text: "Enviar ao PJe-Calc" }), h("dd", { text: "Preenche as telas oficiais do PJe-Calc com este rascunho. O PJe-Calc valida cada tela e devolve as mensagens dele. Não calcula." }), h("dd", { class: "acao" }, h("button", { class: "botao pequeno", onclick: () => operar("gravar") }, "Enviar"))),
          h("div", {}, h("dt", { text: "Calcular" }), h("dd", { text: "Envia o que faltar, liquida no PJe-Calc e guarda o relatório oficial (PDF e HTML) e o arquivo .PJC." }), h("dd", { class: "acao" }, h("button", { class: "botao pequeno primario", onclick: () => operar("executar") }, "Calcular"))))),
      cartaoPadroes(),
      u ? h("section", { class: "cartao" }, h("h2", { text: `Última operação: ${u.tipo === "gravar" ? "envio" : "cálculo"} (${quando(u.em)})` }), mostrarPassos(u.passos)) : null);
  }
  // padrões do modelo/escritório: os que faltam aplicar (no próximo envio) e os já aplicados neste cálculo
  function cartaoPadroes() {
    const apl = E.caso.pjecalc?.padroesAplicados || {};
    const faltam = (E.caso.padroesPendentes || []).filter((id) => !apl[id]);
    return h("section", { class: "cartao" }, h("h2", { text: "Padrões do escritório" }),
      faltam.length ? h("p", { text: `${faltam.length} padrão(ões) do modelo ou do escritório entram no PJe-Calc logo depois do próximo envio.` }) : null,
      Object.keys(apl).length ? h("ul", { class: "lista-simples mini" }, Object.values(apl).map((a) => h("li", { class: a.ok ? null : "negativo",
        text: `${a.nome}: aplicado em ${quando(a.em)}${a.ok ? "" : " (com erro: veja a última operação)"}` })))
        : faltam.length ? null : h("p", { class: "sutil", text: "Nenhum padrão aplicado neste cálculo." }),
      h("button", { class: "botao pequeno", onclick: aplicarPadroesNoCaso }, "Aplicar padrões…"));
  }

  // ---------------------------------------------------------------------------- resultado
  async function etapaResultado() {
    const ex = E.caso.execucoes || [];
    if (!ex.length) return h("div", { class: "cartao" }, h("h2", { text: "Ainda não há resultado" }),
      h("p", { text: "O resultado aparece aqui depois que o PJe-Calc calcular. “Calcular” envia o que faltar e executa o cálculo oficial." }),
      h("button", { class: "botao primario", onclick: () => operar("executar") }, "Calcular no PJe-Calc"));
    const eid = E.sub || ex[ex.length - 1].id;
    const r = await api("GET", `/api/casos/${E.caso.id}/execucoes/${eid}`);
    const e = r.execucao, rel = r.resultado.relatorio || {}, pjc = r.resultado.pjc || { verbas: [] };
    const atual = e.revisaoEntradas === E.caso.revisao && !E.pendente;
    const cd = (d) => (rel.creditos_descontos || []).find((x) => dobrar(x.descricao) === dobrar(d))?.valor;
    const db = (d) => (rel.debitos_reclamado || []).find((x) => dobrar(x.descricao) === dobrar(d))?.valor;
    const base = `/api/casos/${E.caso.id}/execucoes/${eid}`;
    // valores sempre transcritos do relatório oficial; "—" quando o relatório não traz a linha
    const kpi = (rot, v, fonte, destaque) => h("div", { class: "kpi" + (destaque ? " destaque" : "") }, h("div", { class: "rotulo", text: rot }),
      h("div", { class: "valor", text: v ? "R$ " + v : "—" }), h("div", { class: "fonte", text: fonte }));
    const abas = ["Resumo", "Por verba e mês", "Critérios do cálculo", "Documentos oficiais"];
    let aba = 0;
    const painel = h("div", { role: "tabpanel", id: "painelRes", tabindex: 0 });
    const barra = h("div", { class: "abas", role: "tablist", "aria-label": "Visões do resultado" });
    const documentos = () => h("div", { class: "documentos" },
      e.arquivos.relatorioPdf ? h("div", { class: "documento" }, h("span", { class: "tipo", text: "Oficial · PDF" }), h("strong", { text: "Relatório do cálculo" }),
        h("span", { class: "mini sutil", text: "Gerado pelo PJe-Calc; é o documento que vai para o processo." }), h("a", { class: "botao pequeno primario", href: `${base}/arquivo/relatorio.pdf?baixar=1` }, "Baixar PDF")) : null,
      e.arquivos.pjc ? h("div", { class: "documento" }, h("span", { class: "tipo", text: "Oficial · .PJC" }), h("strong", { text: "Arquivo do cálculo" }),
        h("span", { class: "mini sutil", text: "Abre no PJe-Calc de qualquer pessoa; é o que se anexa ao PJe." }), h("a", { class: "botao pequeno", href: `${base}/arquivo/calculo.pjc` }, "Baixar .PJC")) : null,
      e.arquivos.relatorio ? h("div", { class: "documento" }, h("span", { class: "tipo", text: "Oficial · HTML" }), h("strong", { text: "Relatório para leitura na tela" }),
        h("span", { class: "mini sutil", text: "O mesmo relatório, para abrir no navegador." }), h("a", { class: "botao pequeno", href: `${base}/arquivo/relatorio.html`, target: "_blank", rel: "noopener" }, "Abrir em nova janela")) : null,
      h("div", { class: "documento" }, h("span", { class: "tipo", text: "Conferência · não oficial" }), h("strong", { text: "Planilha CSV" }),
        h("span", { class: "mini sutil", text: "Transcreve os valores oficiais para conferência em planilha." }), h("a", { class: "botao pequeno", href: `${base}/planilha.csv` }, "Baixar CSV")));
    const desenhar = () => {
      preencher(barra, ...abas.map((t, i) => h("button", { role: "tab", id: "tab" + i, "aria-selected": String(i === aba), "aria-controls": "painelRes", tabindex: i === aba ? 0 : -1,
        onclick: () => { aba = i; desenhar(); }, onkeydown: (ev) => { if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") { aba = (aba + (ev.key === "ArrowRight" ? 1 : abas.length - 1)) % abas.length; desenhar(); barra.children[aba].focus(); } } }, t)));
      painel.setAttribute("aria-labelledby", "tab" + aba);
      if (aba === 0) preencher(painel,
        h("div", { class: "kpis" }, kpi("Líquido devido ao reclamante", cd("Líquido Devido ao Reclamante"), "O que o reclamante recebe, já com os descontos", true),
          kpi("Bruto devido ao reclamante", cd("Bruto Devido ao Reclamante"), "Antes dos descontos"),
          kpi("Descontos do reclamante", cd("Total de Descontos"), "Contribuição social, IR e outros"),
          kpi("Total devido pelo reclamado", db("Total Devido pelo Reclamado") || (rel.debitos_reclamado || []).find((x) => /total devido/i.test(x.descricao || ""))?.valor, "Inclui encargos e outros credores")),
        h("h2", { text: "Detalhamento por verba" }),
        h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" }, h("caption", { class: "sr-only", text: "Valor corrigido, juros e total de cada verba" }),
          h("thead", {}, h("tr", {}, ["Verba", "Valor corrigido", "Juros", "Total"].map((t, i) => h("th", { scope: "col", class: i ? "num" : null, text: t })))),
          h("tbody", {}, (rel.verbas || []).map((v) => h("tr", {}, h("th", { scope: "row", text: v.descricao }), h("td", { class: "num", text: v.corrigido }), h("td", { class: "num", text: v.juros }), h("td", { class: "num", text: v.total })))),
          rel.total_bruto ? h("tfoot", {}, h("tr", {}, h("td", { text: "Total" }), h("td", { class: "num", text: rel.total_bruto.corrigido }), h("td", { class: "num", text: rel.total_bruto.juros }), h("td", { class: "num", text: rel.total_bruto.total }))) : null)),
        rel.percentual_tributavel ? h("p", { class: "mini sutil", text: "Percentual de parcelas remuneratórias e tributáveis: " + rel.percentual_tributavel }) : null,
        h("div", { class: "grade", style: "margin-top:16px" },
          h("div", {}, h("h2", { text: "Créditos e descontos do reclamante" }), tabelaSimples(rel.creditos_descontos)),
          h("div", {}, h("h2", { text: "Débitos do reclamado por credor" }), tabelaSimples(rel.debitos_reclamado))));
      else if (aba === 1) preencher(painel, h("p", { class: "mini sutil", text: "Valores de cada mês calculados pelo PJe-Calc, lidos do arquivo .PJC exportado (números como gravados pelo programa)." }),
        ...pjc.verbas.map((v) => h("details", { class: "verba-cartao" }, h("summary", {}, h("strong", { text: v.descricao }), ` — ${v.ocorrencias.length} mês(es)`),
          h("div", { class: "tabela-rolagem", style: "max-height:50vh;margin-top:8px" }, h("table", { class: "tabela compacta" },
            h("thead", {}, h("tr", {}, ["Início", "Fim", "Base", "Divisor", "Multiplicador", "Quantidade", "Dobra", "Devido", "Pago", "Índice acumulado"].map((t, i) => h("th", { scope: "col", class: i > 1 ? "num" : null, text: t })))),
            h("tbody", {}, v.ocorrencias.map((o) => h("tr", {}, h("td", { text: o.dataInicial }), h("td", { text: o.dataFinal }),
              ...["base", "divisor", "multiplicador", "quantidade", "dobra", "devido", "pago", "indiceAcumulado"].map((k) => h("td", { class: "num", text: o[k] == null ? "" : String(o[k]).replace(".", ",") }))))))))));
      else if (aba === 2) preencher(painel, h("p", { class: "mini sutil", text: "Critérios e fundamentação transcritos do relatório oficial." }), h("ol", {}, (rel.criterios || []).map((c) => h("li", { text: c.texto }))));
      else preencher(painel, documentos(),
        h("h2", { text: "Relatório oficial" }), h("p", { class: "mini sutil", text: "Exibido sem alterações e isolado desta interface." }),
        h("iframe", { class: "relatorio", src: `${base}/arquivo/relatorio.html`, title: "Relatório oficial do PJe-Calc", sandbox: "" }));
    };
    desenhar();
    const rod = e.rodape || {};
    const seletor = ex.length > 1 ? (() => { const s = h("select", { id: "selExec", "aria-label": "Escolher o cálculo exibido" }, ex.slice().reverse().map((x) => h("option", { value: x.id, selected: x.id === eid }, `${quando(x.em)} · revisão ${x.revisaoEntradas}`)));
      s.addEventListener("change", () => { location.hash = `#/caso/${E.caso.id}/resultado/${s.value}`; }); return h("div", { class: "campo", style: "max-width:320px" }, h("label", { for: "selExec", text: "Cálculo exibido" }), s); })() : null;
    return h("div", {},
      atual ? h("div", { class: "faixa ok" }, h("strong", { text: "Resultado atualizado." }), h("div", { text: "Calculado pelo PJe-Calc com os dados que estão no rascunho agora." }))
        : h("div", { class: "faixa erro", role: "alert" }, h("strong", { text: "Resultado desatualizado." }),
          h("div", { text: `Os dados mudaram depois deste cálculo (ele usou a revisão ${e.revisaoEntradas}; o rascunho está na ${E.caso.revisao}${E.pendente ? ", com alterações ainda não salvas" : ""}). Os valores abaixo não refletem as alterações.` }),
          h("button", { class: "botao pequeno", onclick: () => operar("executar") }, "Calcular de novo")),
      h("p", { class: "mini sutil", text: `Cálculo nº ${e.calculoId} · PJe-Calc ${rod.versao || e.versaoMotor || "?"} · liquidado em ${rod.data || "?"} às ${rod.hora || "?"}${rod.usuario && rod.usuario !== "offline" ? " por " + rod.usuario : ""}` }),
      seletor, barra, painel,
      h("details", { class: "mais" }, h("summary", {}, "Integridade dos arquivos"),
        h("p", { class: "mini" }, "SHA-256 do .PJC: ", h("code", { text: e.sha256Pjc || "—" })),
        h("p", { class: "mini", text: `Hash da liquidação: ${e.hashLiquidacao || "—"} · build do PJe-Calc: ${e.buildMotor || "—"}` })));
  }
  function tabelaSimples(itens) {
    return h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" }, h("tbody", {}, (itens || []).map((x) => h("tr", {}, h("td", { text: x.descricao || "" }), h("td", { class: "num", text: x.valor || "" }))))));
  }

  // ---------------------------------------------------------------------------- exportação
  async function etapaExportacao() {
    const ex = (E.caso.execucoes || []).slice().reverse();
    const vinc = E.caso.pjecalc || {};
    const linhas = ex.map((e) => { const base = `/api/casos/${E.caso.id}/execucoes/${e.id}`;
      return h("tr", {}, h("td", {}, quando(e.em), h("div", { class: "mini sutil", text: `rev. ${e.revisaoEntradas}${e.revisaoEntradas === E.caso.revisao ? " (atual)" : " (desatualizada)"}` })),
        h("td", { text: `PJe-Calc ${e.versaoMotor || "?"}` }),
        h("td", {}, h("div", { class: "chips" },
          e.arquivos.pjc ? h("a", { class: "botao pequeno primario", href: `${base}/arquivo/calculo.pjc` }, "Exportar arquivo .PJC") : null,
          e.arquivos.relatorioPdf ? h("a", { class: "botao pequeno", href: `${base}/arquivo/relatorio.pdf?baixar=1` }, "Relatório oficial (PDF)") : null,
          e.arquivos.relatorio ? h("a", { class: "botao pequeno", href: `${base}/arquivo/relatorio.html?baixar=1` }, "Relatório oficial (HTML)") : null,
          h("a", { class: "botao pequeno", href: `${base}/planilha.csv` }, "Planilha de conferência (CSV)"),
          h("a", { class: "botao pequeno", href: `${base}/resumo-complementar`, target: "_blank", rel: "noopener" }, "Resumo complementar (não oficial)")))); });
    return h("div", {},
      h("section", { class: "cartao" }, h("h2", { text: "Arquivos gerados pelo PJe-Calc" }),
        ex.length ? h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Execução", "Motor", "Arquivos"].map((t) => h("th", { scope: "col", text: t })))), h("tbody", {}, linhas)))
          : h("p", { text: "Execute o cálculo para gerar o .PJC e os relatórios oficiais." }),
        h("ul", { class: "mini sutil" }, h("li", { text: "O .PJC e os relatórios são exatamente os arquivos emitidos pelo PJe-Calc (integridade registrada por SHA-256)." }),
          h("li", { text: "A planilha CSV e o resumo complementar transcrevem os resultados oficiais para conferência e não substituem a memória de cálculo." }))),
      h("section", { class: "cartao" }, h("h2", { text: "Outros relatórios" }),
        vinc.calculoId ? h("p", { text: `O cálculo está gravado no PJe-Calc como nº ${vinc.calculoId}. Os demais relatórios e opções de impressão ficam na função “Imprimir” do PJe-Calc, aberta aqui mesmo neste cálculo.` })
          : h("p", { text: "O cálculo ainda não foi enviado ao PJe-Calc." }),
        vinc.calculoId ? h("div", { class: "ferramentas" }, linkOriginal("imprimir", "Imprimir (todas as opções)"), linkOriginal("exportar", "Exportar")) : null),
      h("section", { class: "cartao" }, h("h2", { text: "Situação do trabalho" }),
        h("p", { class: "mini sutil", text: "“Concluído” registra a revisão do escritório. Não representa homologação judicial nem aprovação oficial." }),
        (() => { const s = h("select", { id: "sitCaso" }, Object.entries(SITUACOES).map(([v, t]) => h("option", { value: v, selected: E.caso.situacao === v }, t)));
          s.addEventListener("change", async () => { const r = await api("PUT", `/api/casos/${E.caso.id}`, { situacao: s.value }); E.caso.situacao = r.caso.situacao; desenharLateralCaso(); avisar("Situação atualizada.", "ok"); });
          return h("div", { class: "campo", style: "max-width:320px" }, h("label", { for: "sitCaso", text: "Situação" }), s); })(),
        h("div", { class: "ferramentas", style: "margin-top:12px" },
          h("button", { class: "botao", onclick: () => duplicar(E.caso.id) }, "Duplicar como cenário alternativo"),
          h("button", { class: "botao", onclick: salvarComoModelo }, "Salvar como modelo do escritório"))));
  }

  // ---------------------------------------------------------------------------- versões e auditoria
  async function etapaAuditoria() {
    const r = await api("GET", `/api/casos/${E.caso.id}/auditoria`);
    const ROT = { criacao: "Criação", edicao: "Edição do rascunho", metadados: "Organização", gravacao_pjecalc: "Gravação no PJe-Calc", execucao_pjecalc: "Execução no PJe-Calc", importacao_pjc: "Importação de .PJC" };
    return h("div", {}, h("h1", { text: "Versões e alterações" }),
      h("p", { class: "sutil", text: "Registro de quem alterou, quando e o quê. Cada edição do rascunho cria uma revisão recuperável." }),
      h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Quando", "Quem", "Ação", "Revisão", "Alterações"].map((t) => h("th", { scope: "col", text: t })))),
        h("tbody", {}, r.eventos.map((ev) => h("tr", {}, h("td", { class: "mini", text: quando(ev.em) }), h("td", { text: ev.autor }), h("td", { text: ROT[ev.acao] || ev.acao }), h("td", { class: "num", text: ev.revisao }),
          h("td", { class: "mini" }, ev.alteracoes.length ? h("details", {}, h("summary", {}, `${ev.alteracoes.length} campo(s)`),
            h("ul", {}, ev.alteracoes.slice(0, 80).map((a) => h("li", {}, h("code", { text: a.campo }), `: ${fmt(a.de)} → ${fmt(a.para)}`)))) : "—")))))));
  }
  const fmt = (v) => v === undefined || v === null ? "(vazio)" : typeof v === "object" ? JSON.stringify(v).slice(0, 80) : String(v);

  // ============================================================================ funções do PJe-Calc
  // Toda função do PJe-Calc continua disponível: as telas que o Studio não reproduz (ou reproduz em parte)
  // são abertas aqui mesmo, na interface oficial, com o cálculo e o item de menu certos já abertos.
  // O servidor do Studio repassa /pjecalc/* ao PJe-Calc local (mesma origem), sem interpretar nada.
  const TELAS_ORIGINAIS = [
    { id: "dados", li: "li_calculo_dados_do_calculo", grupo: "Cálculo", titulo: "Dados do Cálculo (completa)", desc: "Todos os campos, inclusive advogados, exceções de carga horária e de sábado e pontos facultativos.", studio: "identificacao" },
    { id: "faltas", li: "li_calculo_faltas", grupo: "Cálculo", titulo: "Faltas", desc: "Faltas justificadas e não justificadas, com reflexo em férias, 13º e bases." },
    { id: "ferias", li: "li_calculo_ferias", grupo: "Cálculo", titulo: "Férias", desc: "Períodos aquisitivos, gozo, dobra e abono; férias coletivas." },
    { id: "historico", li: "li_calculo_historico_salarial", grupo: "Cálculo", titulo: "Histórico Salarial (completa)", desc: "Grade de ocorrências, proporcionalização e demais opções do histórico.", studio: "historico" },
    { id: "verbas", li: "li_calculo_verbas", grupo: "Cálculo", titulo: "Verbas (completa)", desc: "Todos os parâmetros, ocorrências de reflexos e regeração de ocorrências.", studio: "verbas" },
    { id: "cartao", li: "li_calculo_cartao_ponto", grupo: "Cálculo", titulo: "Cartão de Ponto", desc: "Marcações, jornadas, apuração de horas extras, noturnas e intervalos." },
    { id: "salario-familia", li: "li_calculo_salario_familia", grupo: "Cálculo", titulo: "Salário-família", desc: "Apuração do salário-família." },
    { id: "seguro-desemprego", li: "li_calculo_seguro_desemprego", grupo: "Cálculo", titulo: "Seguro-desemprego", desc: "Indenização substitutiva do seguro-desemprego." },
    { id: "fgts", li: "li_calculo_fgts", grupo: "Cálculo", titulo: "FGTS (completa)", desc: "Ocorrências do FGTS, depósitos e demais opções.", studio: "reflexos" },
    { id: "inss", li: "li_calculo_inss", grupo: "Cálculo", titulo: "Contribuição Social", desc: "Segurado e empregador, alíquotas, salários pagos e ocorrências." },
    { id: "previdencia", li: "li_calculo_previdencia_privada", grupo: "Cálculo", titulo: "Previdência Privada", desc: "Descontos de previdência privada." },
    { id: "pensao", li: "li_calculo_pensao_alimenticia", grupo: "Cálculo", titulo: "Pensão Alimentícia", desc: "Descontos de pensão alimentícia." },
    { id: "irpf", li: "li_calculo_irpf", grupo: "Cálculo", titulo: "Imposto de Renda", desc: "Apuração, deduções, dependentes e regime de caixa." },
    { id: "multas", li: "li_calculo_multas_e_indenizacoes", grupo: "Cálculo", titulo: "Multas e Indenizações", desc: "Multas e indenizações fixadas na decisão." },
    { id: "honorarios", li: "li_calculo_honorarios", grupo: "Cálculo", titulo: "Honorários", desc: "Honorários advocatícios e periciais." },
    { id: "custas", li: "li_calculo_custas_judiciais", grupo: "Cálculo", titulo: "Custas Judiciais", desc: "Custas de conhecimento e liquidação, autos e armazenamento." },
    { id: "correcao", li: "li_calculo_correcao_juros_multa", grupo: "Cálculo", titulo: "Correção, Juros e Multa (completa)", desc: "Todas as abas, inclusive multa e contribuição social.", studio: "atualizacao" },
    { id: "liquidar", li: "li_operacoes_liquidar", grupo: "Operações", titulo: "Liquidar", desc: "Tela oficial de liquidação e pendências.", studio: "calculo" },
    { id: "imprimir", li: "li_calculo_relatorios", grupo: "Operações", titulo: "Imprimir (todas as opções)", desc: "Todos os relatórios e opções de impressão.", studio: "exportacao" },
    { id: "exportar", li: "li_operacoes_exportar", grupo: "Operações", titulo: "Exportar", desc: "Exportação oficial do arquivo .PJC." },
    { id: "pagamento", li: "li_pagamento_dados_do_pagamento", grupo: "Atualização de pagamentos", titulo: "Dados do Pagamento", desc: "Pagamentos realizados no processo, para atualização do saldo." },
    { id: "pag-pensao", li: "li_pagamento_pensao_alimenticia", grupo: "Atualização de pagamentos", titulo: "Pensão Alimentícia (atualização)" },
    { id: "pag-multas", li: "li_pagamento_multas_e_indenizacoes", grupo: "Atualização de pagamentos", titulo: "Multas e Indenizações (atualização)" },
    { id: "pag-honorarios", li: "li_pagamento_honorarios", grupo: "Atualização de pagamentos", titulo: "Honorários (atualização)" },
    { id: "pag-custas", li: "li_pagamento_custas_judiciais", grupo: "Atualização de pagamentos", titulo: "Custas Judiciais (atualização)" },
    { id: "liquidar-atualizacao", li: "li_operacoes_liquidar_pagamento", grupo: "Atualização de pagamentos", titulo: "Liquidar Atualização" },
    { id: "imprimir-atualizacao", li: "li_operacoes_imprimir_pagamento", grupo: "Atualização de pagamentos", titulo: "Imprimir Atualização" },
  ];
  // funções que não dependem de um cálculo aberto
  const TELAS_GERAIS = [
    { id: "externo", li: "li_calculo_externo_novo", grupo: "PJe-Calc", titulo: "Novo Cálculo Externo", desc: "Atualização de cálculo feito fora do PJe-Calc." },
    { id: "consolidado", li: "li_processo_relatorio", grupo: "PJe-Calc", titulo: "Relatório Consolidado", desc: "Relatório consolidado de cálculos de um processo." },
    { id: "buscar", li: "li_calculo_buscar", grupo: "PJe-Calc", titulo: "Buscar cálculos no PJe-Calc", desc: "Todos os cálculos do PJe-Calc, inclusive os feitos fora do Studio." },
    { id: "t-salario-minimo", li: "li_tabelas_salario_minimo", grupo: "Tabelas", titulo: "Salário Mínimo" },
    { id: "t-pisos", li: "li_tabelas_salario_categoria", grupo: "Tabelas", titulo: "Pisos Salariais" },
    { id: "t-salario-familia", li: "li_tabelas_salario_familia", grupo: "Tabelas", titulo: "Salário-família" },
    { id: "t-seguro", li: "li_tabelas_seguro_desemprego", grupo: "Tabelas", titulo: "Seguro-desemprego" },
    { id: "t-vale", li: "li_tabelas_vale_transporte", grupo: "Tabelas", titulo: "Vale-transporte" },
    { id: "t-feriados", li: "li_tabelas_feriado", grupo: "Tabelas", titulo: "Feriados e Pontos Facultativos" },
    { id: "t-verbas", li: "li_tabelas_verbas", grupo: "Tabelas", titulo: "Verbas" },
    { id: "t-inss", li: "li_tabelas_inss", grupo: "Tabelas", titulo: "Contribuição Social" },
    { id: "t-irpf", li: "li_tabela_irpf", grupo: "Tabelas", titulo: "Imposto de Renda" },
    { id: "t-custas", li: "li_tabelas_parametros_custas", grupo: "Tabelas", titulo: "Custas Judiciais" },
    { id: "t-correcao", li: "li_tabelas_indices_gerais", grupo: "Tabelas", titulo: "Correção Monetária" },
    { id: "t-juros", li: "li_tabelas_juros", grupo: "Tabelas", titulo: "Juros de Mora" },
    { id: "t-atualizar", li: "li_tabelas_sincronizar", grupo: "Tabelas", titulo: "Atualização de Tabelas e Índices", desc: "Baixa as tabelas e índices oficiais mais recentes." },
  ];
  // Cada tela do PJe-Calc é lida pelo servidor (ponte/tela.py) e desenhada aqui com o visual do Studio: grupos,
  // abas, campos, tabelas e botões. Valores digitados e botões voltam para a mesma tela oficial, numa sessão
  // própria do PJe-Calc: validação, gravação e cálculo continuam sendo do PJe-Calc.
  const BOTAO_PRINCIPAL = /^(salvar|confirmar|liquidar|imprimir|exportar|gerar|regerar|calcular|importar|buscar|pesquisar|atualizar)\b/i;
  const BOTAO_PERIGO = /^(excluir|remover|apagar)\b/i;
  const TEXTOS_REPETIDOS = /^(c[áa]lculo|processo):/i;  // resumo "Dados do Cálculo" que o cabeçalho do Studio já mostra

  // ---------------------------------------------------------------------------- ajuda das funções do PJe-Calc
  // Todo campo ganha a mesma ajuda das etapas do Studio (painel lateral, F1). Ordem de preferência: texto próprio
  // (web/ajuda-pjecalc.js), a ajuda já escrita para o mesmo campo nas etapas do Studio (aliases), o texto de ajuda
  // oficial que o PJe-Calc mostra na tela e, por fim, o que a própria tela informa (formato, opções, obrigatoriedade).
  const sufixoCampo = (nome) => nome.split(":").pop().replace(/InputDate$/, "");
  function comoPreencher(c) {
    const r = (c.rotulo || "").toLowerCase();
    if (c.tipo === "data") return /compet/.test(r) ? "Mês e ano (MM/AAAA) ou a data completa (DD/MM/AAAA), conforme o campo aceitar." : "Digite a data no formato DD/MM/AAAA. As barras aparecem sozinhas.";
    if (c.tipo === "lista" || c.tipo === "radio") {
      const ops = (c.opcoes || []).map((o) => o.rotulo).filter((x) => x && x !== "Selecione…");
      return ops.length ? `Opções do PJe-Calc: ${ops.slice(0, 12).join("; ")}${ops.length > 12 ? "…" : ""}.` : null;
    }
    if (c.tipo === "marca") return "Marque para aplicar; deixe desmarcado para não aplicar.";
    if (c.tipo === "arquivo") return "Escolha um arquivo CSV no formato do modelo do PJe-Calc (link do arquivo de exemplo na mesma seção).";
    if (/al[ií]quota|%|percent/.test(r)) return "Percentual com vírgula nos decimais, sem o símbolo %. Ex.: 15 ou 12,5.";
    if (/valor/.test(r)) return "Valor em reais no formato 1.234,56. Não digite “R$”.";
    if (/^(qtd|quantidade)|qtde/.test(r)) return "Número inteiro.";
    return null;
  }
  function ajudaDoCampo(c, tela, grupo) {
    const A = window.AJUDA_PJECALC || { campos: {}, aliases: {} };
    const suf = sufixoCampo(c.nome), chave = `pj:${tela.li}:${suf}`;
    const alias = A.aliases[`${tela.li}|${suf}`];
    const proprio = A.campos[`${tela.li}|${suf}`] || A.campos[suf] || {};
    const base = (alias && window.AJUDA[alias]) || {};
    const rot = c.rotulo || grupo || "este campo";
    const essencial = c.ajuda ? c.ajuda.split(/(?<=\.)\s/)[0]
      : c.tipo === "marca" ? `Marque para aplicar “${rot}” neste cálculo.` : c.tipo === "lista" || c.tipo === "radio" ? `Escolha a opção de “${rot}”.` : `Informe: ${rot}.`;
    window.AJUDA[chave] = { essencial, como: comoPreencher(c), ...base, ...proprio,
      obrigatorio: c.obrigatorio ? "sim" : (proprio.obrigatorio || base.obrigatorio || null),
      textoOficialPronto: c.ajuda || null, oficial: [tela.titulo.replace(/ \(completa\)$/, ""), grupo, c.rotulo].filter(Boolean).join(" › ") };
    return chave;
  }
  function ajudaDaTela(tela) {
    const t = (window.AJUDA_PJECALC?.telas || {})[tela.li] || {};
    const chave = "pjtela:" + tela.li;
    window.AJUDA[chave] = { essencial: t.essencial || tela.desc || `Função ${tela.titulo} do PJe-Calc.`, ...t,
      como: [t.como, "Para não preencher de novo nos próximos cálculos, use “Padrões” › “Salvar como padrão”: depois é um clique, ou automático em todo cálculo novo."].filter(Boolean).join(" "),
      oficial: `PJe-Calc › ${tela.grupo} › ${tela.titulo.replace(/ \(completa\)$/, "")}` };
    return chave;
  }

  function visaoTela(tela, casoId) {
    const raiz = h("div", { class: "tela-pj", "aria-busy": "true" });
    const situacao = h("p", { class: "mini sutil tela-pj-status", role: "status", "aria-live": "polite", text: "Abrindo a tela no PJe-Calc…" });
    const corpo = h("div", { class: "tela-pj-corpo" });
    let token = null, desc = null, ocupado = false, abaAtiva = {}, baixado = null;
    const valores = {};  // digitado e ainda não enviado (vai junto com o próximo botão ou evento)
    // o que a pessoa preencheu e acionou nesta tela desde que ela abriu: vira um padrão em "Salvar como padrão"
    let gravacao = [], padroesTela = [], registroPadrao = null;
    const gravarCampo = (c, valor) => {
      const ultimaAcao = gravacao.map((p) => p.tipo).lastIndexOf("acao");
      gravacao = gravacao.filter((p, i) => !(p.tipo === "campo" && p.nome === c.nome && i > ultimaAcao));
      const opcao = (c.opcoes || []).find((o) => o.valor === valor);  // o que a pessoa viu na lista (não o código interno)
      gravacao.push({ tipo: "campo", nome: c.nome, rotulo: c.rotulo || "", valor, valorRotulo: opcao ? opcao.rotulo : undefined, evento: !!c.evento, campoTipo: c.tipo });
    };

    const esperar = (texto) => { ocupado = true; raiz.setAttribute("aria-busy", "true"); raiz.classList.add("ocupada"); situacao.className = "mini sutil tela-pj-status"; situacao.textContent = texto; };
    const pronto = () => { ocupado = false; raiz.setAttribute("aria-busy", "false"); raiz.classList.remove("ocupada"); };
    const falhou = (e) => { pronto(); situacao.className = "erro-campo tela-pj-status"; situacao.textContent = e.message; };

    async function executar(texto, fn) {
      if (ocupado) return;
      const foco = document.activeElement && raiz.contains(document.activeElement) ? document.activeElement.dataset.nome : null;
      esperar(texto);
      try {
        const r = await fn();
        desc = r.tela;
        for (const k of Object.keys(valores)) delete valores[k];  // a sessão do PJe-Calc já recebeu tudo
        pronto();
        desenhar(foco);
      } catch (e) { falhou(e); }
    }
    async function abrir() {
      if (token) api("DELETE", `/api/telas/${token}`).catch(() => {});
      token = null;
      await executar("Abrindo a tela no PJe-Calc…", async () => {
        const r = await api("POST", "/api/telas", { caso: casoId || undefined, menu: tela.li });
        token = r.token;
        gravacao = []; registroPadrao = null;
        return r;
      });
      carregarPadroes();
    }
    async function carregarPadroes() {
      try { padroesTela = (await api("GET", "/api/padroes?menu=" + encodeURIComponent(tela.li))).padroes; } catch { padroesTela = []; }
      desenharBarra();
    }
    const alterar = (nome) => executar("Atualizando no PJe-Calc…", () => api("POST", `/api/telas/${token}/alterar`, { valores: { ...valores }, evento: nome }));
    const acionar = async (acao, linha) => {
      // exclusões sempre pedem confirmação no Studio, mesmo quando a tela oficial não pede
      const pergunta = acao.confirmar || (BOTAO_PERIGO.test(acao.texto) ? `${acao.texto}${linha ? ` “${linha}”` : " este registro"} no PJe-Calc? Esta ação grava no cálculo e não pode ser desfeita pelo Studio.` : null);
      if (pergunta && !(await confirmar(acao.texto, pergunta, acao.texto, BOTAO_PERIGO.test(acao.texto)))) return;
      // botões de linha (Excluir, Alterar de um registro) e trocas de página valem só para este caso: não entram no padrão
      if (!linha && !acao.id.startsWith("pag:")) gravacao.push({ tipo: "acao", id: acao.id, texto: acao.texto });
      registroPadrao = null;
      await executar(`${acao.texto}: aguardando o PJe-Calc…`, () => api("POST", `/api/telas/${token}/acao`, { acao: acao.id, valores: { ...valores } }));
      if (casoId && !acao.navegacao) { E.estadoRes = { ...(E.estadoRes || {}), abertoNoOriginalDepois: !!(E.estadoRes || {}).ultimaExecucao }; atualizarBarra(); }
    };
    const enviarArquivo = (c, arquivo) => executar(`Enviando ${arquivo.name} ao PJe-Calc…`, async () =>
      api("POST", `/api/telas/${token}/arquivo?campo=${encodeURIComponent(c.nome)}&nome=${encodeURIComponent(arquivo.name)}`, await arquivo.arrayBuffer()));

    // ------------------------------------------------------------------ desenho
    function controle(c, compacto, tituloGrupo) {
      const id = "tp-" + c.nome.replace(/[^\w]/g, "_");
      const comum = { id, disabled: c.desabilitado, dataset: { nome: c.nome }, "aria-required": c.obrigatorio ? "true" : null };
      const mudou = (v) => { valores[c.nome] = v; if (!compacto) gravarCampo(c, v); if (c.evento) alterar(c.nome); };
      const rotuloTexto = c.rotulo || (compacto ? "" : "Campo sem nome no PJe-Calc");
      const rotulo = (alvo) => h("label", { for: alvo }, rotuloTexto, c.obrigatorio ? h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" }) : null,
        c.obrigatorio ? h("span", { class: "sr-only", text: " (obrigatório)" }) : null);
      const ajuda = compacto ? null : botaoAjuda(ajudaDoCampo(c, tela, tituloGrupo), rotuloTexto || tituloGrupo || "Campo");
      const embrulhar = (...filhos) => compacto ? h("div", { class: "tela-pj-celula-campo" }, ...filhos)
        : h("div", { class: "campo" + (c.tipo === "area" ? " inteiro" : ""), dataset: { nome: c.nome } }, ...filhos);
      if (c.tipo === "marca") {
        const cb = h("input", { type: "checkbox", ...comum, checked: !!c.valor && c.valor !== "false" });
        cb.addEventListener("change", () => mudou(cb.checked));
        return embrulhar(h("div", { class: "rotulo" }, h("label", { class: "marcacao", for: id }, cb, h("span", { text: rotuloTexto || "Marcar" })), ajuda));
      }
      if (c.tipo === "radio") {
        const grupo = h("fieldset", { class: "tela-pj-radios", disabled: c.desabilitado },
          // rótulo igual ao título do grupo: não repete na tela (continua para leitores de tela)
          rotuloTexto ? h("legend", { class: rotuloTexto === tituloGrupo ? "sr-only" : null }, rotuloTexto, c.obrigatorio ? h("span", { class: "obrigatorio", "aria-hidden": "true", text: " *" }) : null,
            rotuloTexto === tituloGrupo ? null : ajuda) : null,
          (c.opcoes || []).map((o, i) => {
            const rid = `${id}-${i}`;
            const rb = h("input", { type: "radio", name: id, id: rid, value: o.valor, checked: o.valor === c.valor, dataset: { nome: c.nome } });
            rb.addEventListener("change", () => { if (rb.checked) mudou(o.valor); });
            return h("label", { class: "marcacao", for: rid }, rb, h("span", { text: o.rotulo }));
          }));
        // título do grupo igual ao rótulo: a legenda fica só para leitores de tela e o "?" vai logo abaixo
        return embrulhar(grupo, rotuloTexto === tituloGrupo || !rotuloTexto ? ajuda : null);
      }
      let entrada;
      if (c.tipo === "lista") {
        entrada = h("select", comum, (c.opcoes || []).map((o) => h("option", { value: o.valor, selected: o.valor === c.valor }, o.rotulo || "—")));
        entrada.addEventListener("change", () => mudou(entrada.value));
      } else if (c.tipo === "area") {
        entrada = h("textarea", comum, c.valor || "");
        entrada.addEventListener("input", () => { valores[c.nome] = entrada.value; });
        entrada.addEventListener("change", () => { gravarCampo(c, entrada.value); if (c.evento) alterar(c.nome); });
      } else if (c.tipo === "arquivo") {
        entrada = h("input", { type: "file", id, disabled: c.desabilitado || !token, dataset: { nome: c.nome } });
        entrada.addEventListener("change", () => { if (entrada.files[0]) enviarArquivo(c, entrada.files[0]); });
      } else {
        entrada = h("input", { type: c.tipo === "senha" ? "password" : "text", ...comum, value: c.valor ?? "", autocomplete: "off",
          placeholder: c.tipo === "data" ? "DD/MM/AAAA" : null, inputmode: c.tipo === "data" ? "numeric" : null, "aria-label": compacto ? (c.rotulo || "Valor") : null });
        if (c.tipo === "data") mascaraData(entrada);
        entrada.addEventListener("input", () => { valores[c.nome] = entrada.value; });
        entrada.addEventListener("change", () => {
          if (c.tipo === "data" && entrada.value && !dataValida(entrada.value)) { erroNoCampo(entrada, `“${entrada.value}” não é uma data válida. Use dia/mês/ano, por exemplo 15/03/2021.`); return; }
          if (c.tipo === "data") erroNoCampo(entrada, null);
          valores[c.nome] = entrada.value;
          if (!compacto) gravarCampo(c, entrada.value);
          if (c.evento) alterar(c.nome);
        });
      }
      if (c.erro) { entrada.setAttribute("aria-invalid", "true"); entrada.setAttribute("aria-describedby", id + "-erro"); }
      const erro = c.erro ? h("span", { class: "erro-campo", id: id + "-erro", text: c.erro }) : null;
      if (compacto) return embrulhar(entrada, erro);
      return embrulhar(h("div", { class: "rotulo" }, rotulo(id), ajuda), entrada, erro);
    }
    function botao(a, pequeno, linha) {
      const cls = "botao" + (pequeno ? " pequeno" : "") + (BOTAO_PERIGO.test(a.texto) ? " perigo" : BOTAO_PRINCIPAL.test(a.texto) && !pequeno ? " primario" : "");
      return h("button", { type: "button", class: cls, title: a.dica && a.dica !== a.texto ? a.dica : null,
        "aria-label": linha ? `${a.texto}: ${linha}` : null, onclick: () => acionar(a, linha) }, a.texto);
    }
    function tabela(t) {
      const linhas = t.linhas || [];
      if (!linhas.length) return h("p", { class: "mini sutil tela-pj-vazia", text: "Nenhum registro." });
      const ncol = Math.max(t.colunas.length, ...linhas.map((l) => l.celulas.length));
      const cab = Array.from({ length: ncol }, (_, i) => t.colunas[i] || "");
      // a coluna de ações do PJe-Calc (ícones) vai para o fim, como no restante do Studio
      const soAcoes = cab.map((_, i) => linhas.every((l) => !(l.celulas[i]?.texto) && !(l.celulas[i]?.campos || []).length));
      const ordem = [...cab.keys()].filter((i) => !soAcoes[i]).concat([...cab.keys()].filter((i) => soAcoes[i]));
      return h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela compacta" },
        h("thead", {}, h("tr", {}, ordem.map((i) => h("th", { scope: "col", class: soAcoes[i] ? "col-acoes" : null }, soAcoes[i] ? h("span", { class: "sr-only", text: cab[i] || "Ações" }) : cab[i])))),
        h("tbody", {}, linhas.map((l) => {
          // descrição da linha (para leitores de tela e para a confirmação de exclusão)
          const resumo = l.celulas.map((c) => c.texto).filter(Boolean).slice(0, 3).join(" · ");
          return h("tr", {}, ordem.map((i) => {
            const cel = l.celulas[i] || { texto: "", campos: [], acoes: [] };
            return h("td", { class: soAcoes[i] ? "col-acoes" : /^-?[\d.]+,\d+$/.test(cel.texto) ? "num" : null },
              cel.texto ? h("span", { text: cel.texto }) : null,
              cel.campos.map((c) => controle(c, true)),
              cel.acoes.length ? h("div", { class: "acoes-linha" }, cel.acoes.map((a) => botao(a, true, resumo))) : null);
          }));
        }))));
    }
    // itens de um grupo: campos seguidos viram uma grade; botões seguidos, uma barra
    function itens(lista, nivel, tituloGrupo) {
      const saida = [];
      let grade = null, barra = null;
      const fechar = () => { grade = null; barra = null; };
      for (let i = 0; i < lista.length; i++) {
        const it = lista[i];
        if (it.t === "grupo" && it.aba) {
          const abas = [];
          while (i < lista.length && lista[i].t === "grupo" && lista[i].aba) abas.push(lista[i++]);
          i--; fechar();
          saida.push(abasDe(abas, nivel));
        } else if (it.t === "grupo") {
          fechar();
          if (it.titulo === "Dados do Cálculo" && it.itens.every((x) => x.t === "texto" && TEXTOS_REPETIDOS.test(x.texto))) continue;
          saida.push(grupo(it, nivel + 1));
        } else if (it.t === "campo") {
          barra = null;
          if (!grade) { grade = h("div", { class: "grade" }); saida.push(grade); }
          grade.appendChild(controle(it, false, tituloGrupo));
        } else if (it.t === "acao") {
          grade = null;
          if (!barra) { barra = h("div", { class: "ferramentas" }); saida.push(barra); }
          barra.appendChild(botao(it));
        } else if (it.t === "link") {
          grade = null;
          if (!barra) { barra = h("div", { class: "ferramentas" }); saida.push(barra); }
          barra.appendChild(h("a", { class: "botao leve pequeno", href: it.href, download: "" }, it.texto));
        } else if (it.t === "tabela") {
          fechar();
          saida.push(tabela(it));
        } else if (it.t === "abas") {  // abas trocadas pelo PJe-Calc: cada troca é uma requisição
          fechar();
          saida.push(h("div", { class: "abas", role: "tablist" }, it.abas.map((a) => h("button", { type: "button", role: "tab", "aria-selected": String(a.ativa),
            onclick: () => { if (!a.ativa) acionar({ id: "aba:" + a.id, texto: a.titulo, navegacao: true }); } }, a.titulo))));
        } else if (it.t === "paginas") {
          fechar();
          if (it.paginas.filter((p) => /^\d+$/.test(p.texto)).length > 1) saida.push(h("nav", { class: "paginacao", "aria-label": "Páginas da tabela" }, it.paginas.map((p) =>
            h("button", { type: "button", class: "botao pequeno" + (p.atual ? " primario" : ""), "aria-current": p.atual ? "page" : null, disabled: p.desabilitado || p.atual,
              onclick: () => acionar({ id: `pag:${it.id}:${p.pagina}`, texto: "Página " + p.texto, navegacao: true }) }, p.texto))));
        } else {
          fechar();
          if (TEXTOS_REPETIDOS.test(it.texto) && nivel === 0) continue;
          saida.push(h("p", { class: "tela-pj-texto", text: it.texto }));
        }
      }
      return saida;
    }
    function grupo(g, nivel) {
      const conteudo = itens(g.itens, nivel, g.titulo);
      if (!conteudo.length) return null;
      if (nivel <= 1) return h("section", { class: "cartao tela-pj-grupo" }, g.titulo ? h("h2", { text: g.titulo }) : null, conteudo);
      return h("fieldset", { class: "tela-pj-subgrupo" }, g.titulo ? h("legend", { text: g.titulo }) : null, conteudo);
    }
    function abasDe(abas, nivel) {
      const chave = abas.map((a) => a.titulo).join("|");
      const atual = Math.min(abaAtiva[chave] || 0, abas.length - 1);
      const base = novoId("aba");
      const barra = h("div", { class: "abas", role: "tablist" });
      const paineis = abas.map((a, i) => h("div", { role: "tabpanel", id: `${base}-p${i}`, "aria-labelledby": `${base}-t${i}`, hidden: i !== atual, class: "tela-pj-aba" }, itens(a.itens, nivel + 1)));
      const ir = (i, focar) => {
        abaAtiva[chave] = i;
        [...barra.children].forEach((b, j) => { b.setAttribute("aria-selected", String(i === j)); b.tabIndex = i === j ? 0 : -1; });
        paineis.forEach((p, j) => { p.hidden = i !== j; });
        if (focar) barra.children[i].focus();
      };
      abas.forEach((a, i) => barra.appendChild(h("button", { type: "button", role: "tab", id: `${base}-t${i}`, "aria-controls": `${base}-p${i}`, "aria-selected": String(i === atual), tabindex: i === atual ? 0 : -1,
        onclick: () => ir(i), onkeydown: (ev) => { if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") { ev.preventDefault(); ir((i + (ev.key === "ArrowRight" ? 1 : abas.length - 1)) % abas.length, true); } } }, a.titulo)));
      return h("div", { class: "tela-pj-abas" }, barra, paineis);
    }
    function desenhar(focoNome) {
      if (!desc) return;
      const erros = desc.mensagens.filter((m) => m.severidade === "erro").length;
      situacao.className = "mini sutil tela-pj-status";
      situacao.textContent = (desc.titulo ? desc.titulo.replace(/\s*>\s*/g, " › ") : tela.titulo) + (desc.calculo ? ` · cálculo nº ${desc.calculo}` : "");
      preencher(corpo,
        registroPadrao ? h("div", { class: "faixa " + (registroPadrao.ok ? "ok" : "erro"), role: registroPadrao.ok ? "status" : "alert" },
          h("strong", { text: registroPadrao.ok ? `Padrão “${registroPadrao.nome}” aplicado.` : `O padrão “${registroPadrao.nome}” parou:` }),
          h("details", { open: !registroPadrao.ok }, h("summary", {}, "O que foi feito"),
            h("ul", { class: "lista-simples mini" }, registroPadrao.registro.map((x) => h("li", { class: x.ok ? null : "negativo", text: x.texto }))))) : null,
        desc.mensagens.length ? h("div", { class: "faixa " + (erros ? "erro" : desc.mensagens.some((m) => m.severidade === "sucesso") ? "ok" : "info"), role: erros ? "alert" : "status" },
          h("strong", { text: erros ? "O PJe-Calc não aceitou:" : "PJe-Calc:" }), h("div", {}, listaMensagens(desc.mensagens))) : null,
        desc.arquivo ? h("div", { class: "faixa ok" }, h("strong", { text: "Arquivo gerado pelo PJe-Calc:" }), h("div", { text: `${desc.arquivo.nome} (${Math.max(1, Math.round(desc.arquivo.bytes / 1024))} KB)` }),
          h("a", { class: "botao pequeno primario", href: `/api/telas/${token}/download`, download: desc.arquivo.nome }, "Baixar de novo")) : null,
        itens(desc.itens, 0));
      // como no PJe-Calc, o arquivo gerado (relatório, .PJC) começa a baixar sozinho
      if (desc.arquivo && desc.arquivo !== baixado) { baixado = desc.arquivo; h("a", { href: `/api/telas/${token}/download`, download: desc.arquivo.nome }).click(); }
      if (focoNome) corpo.querySelector(`[data-nome="${CSS.escape(focoNome)}"]:is(input, select, textarea)`)?.focus();
    }

    // ------------------------------------------------------------------ padrões do escritório (ponte/padroes.py)
    function acharCampo(nome, lista = desc?.itens || []) {
      for (const i of lista) {
        if (i.t === "campo" && i.nome === nome) return i;
        if (i.t === "grupo") { const r = acharCampo(nome, i.itens); if (r) return r; }
      }
      return null;
    }
    function passoLegivel(p) {
      if (p.tipo === "acao") return `Botão “${p.texto}”`;
      const c = acharCampo(p.nome);
      let v = p.valorRotulo || (c && (c.opcoes || []).length ? ((c.opcoes.find((o) => o.valor === p.valor) || {}).rotulo || p.valor) : p.valor);
      v = v === true ? "marcado" : v === false ? "desmarcado" : v === "" || v == null ? "(vazio)" : v;
      return `${p.rotulo || "Campo"}: ${v}`;
    }
    async function aplicarPadrao(p) {
      const botoes = p.passos.filter((x) => x.tipo === "acao").map((x) => `“${x.texto}”`);
      if (botoes.length && !(await confirmar(`Aplicar “${p.nome}”`, `O padrão preenche esta tela e aciona ${botoes.join(", ")} no PJe-Calc${casoId ? " deste cálculo" : ""}. Continuar?`, "Aplicar padrão"))) return;
      await executar(`Aplicando o padrão “${p.nome}”…`, async () => {
        const r = await api("POST", `/api/telas/${token}/padroes/${p.id}`);
        registroPadrao = { nome: p.nome, ok: r.ok, registro: r.registro };
        gravacao = p.passos.map((x) => ({ ...x }));  // dá para ajustar e salvar como outro padrão
        return r;
      });
      if (casoId && botoes.length) { E.estadoRes = { ...(E.estadoRes || {}), abertoNoOriginalDepois: !!(E.estadoRes || {}).ultimaExecucao }; atualizarBarra(); }
    }
    async function salvarPadrao() {
      if (!gravacao.length) { avisar("Preencha os campos desta tela (e, se quiser, use o botão Salvar dela) antes de guardar o padrão.", "info", 8000); return; }
      const funcao = tela.titulo.replace(/ \(completa\)$/, "");
      // datas costumam ser do caso concreto: começam desmarcadas
      const marcas = gravacao.map((p, i) => h("input", { type: "checkbox", id: "pp-" + i, checked: !(p.tipo === "campo" && p.campoTipo === "data") }));
      const nome = h("input", { type: "text", id: "ppNome", value: `${funcao} — padrão do escritório` });
      const descr = h("textarea", { id: "ppDesc", rows: 2 });
      const auto = h("input", { type: "checkbox", id: "ppAuto" });
      const ok = await dialogo({ titulo: "Salvar como padrão", largo: true, corpo: h("div", {},
        h("p", { text: `O padrão repete este preenchimento na função “${funcao}” de outros cálculos, em um clique. O PJe-Calc valida e grava como se você tivesse digitado.` }),
        h("div", { class: "grade" }, h("div", { class: "campo" }, h("label", { for: "ppNome", text: "Nome do padrão" }), nome),
          h("div", { class: "campo" }, h("label", { for: "ppDesc", text: "Descrição (opcional)" }), descr)),
        h("h3", { text: "O que o padrão repete" }),
        h("p", { class: "mini sutil", text: "Desmarque o que é só deste caso (datas, nomes, valores pontuais). Sem o botão final (por exemplo, Salvar), o padrão apenas preenche a tela para você conferir e salvar." }),
        h("ul", { class: "padrao-passos" }, gravacao.map((p, i) => h("li", {}, h("label", { class: "marcacao", for: "pp-" + i }, marcas[i], h("span", { text: passoLegivel(p) }))))),
        casoId ? h("label", { class: "marcacao", for: "ppAuto" }, auto, h("span", { text: "Aplicar automaticamente em todo cálculo novo (logo depois do primeiro envio ao PJe-Calc)" })) : null),
        botoes: [{ texto: "Cancelar", valor: false }, { texto: "Salvar padrão", valor: true, classe: "primario" }] });
      if (!ok) return;
      const passos = gravacao.filter((_, i) => marcas[i].checked).map(({ campoTipo, ...p }) => p);
      try {
        const r = await api("POST", "/api/padroes", { nome: nome.value, descricao: descr.value, menu: tela.li, funcao, passos, automatico: auto.checked });
        avisar(`Padrão “${r.padrao.nome}” salvo. Use “Aplicar padrão” nesta função de qualquer cálculo${auto.checked ? "; ele também entra sozinho em todo cálculo novo" : ""}.`, "ok", 9000);
        carregarPadroes();
      } catch (e) { avisar(e.message, "erro", 9000); }
    }
    const acoesBarra = h("div", { class: "acoes" });
    function desenharBarra() {
      preencher(acoesBarra,
        padroesTela.length ? h("details", { class: "menu" }, h("summary", { class: "botao pequeno primario", "aria-label": "Aplicar um padrão do escritório nesta tela" }, `Aplicar padrão (${padroesTela.length}) ▾`),
          h("div", { class: "menu-lista", role: "menu" }, padroesTela.map((p) => h("button", { type: "button", role: "menuitem", title: p.descricao || null,
            onclick: (e) => { e.currentTarget.closest("details").open = false; aplicarPadrao(p); } }, p.nome + (p.automatico ? " · automático" : ""))))) : null,
        h("button", { type: "button", class: "botao pequeno", onclick: salvarPadrao, title: "Guarda o que você preencheu nesta tela para repetir em outros cálculos" }, "Salvar como padrão"),
        h("button", { type: "button", class: "botao pequeno leve", onclick: abrir, title: "Lê a tela de novo no PJe-Calc (descarta o que não foi salvo)" }, "Recarregar"));
    }

    desenharBarra();
    abrir();
    preencher(raiz, h("div", { class: "tela-pj-barra" }, situacao, acoesBarra), corpo);
    return raiz;
  }
  async function etapaOriginal(telaId) {
    const tela = TELAS_ORIGINAIS.find((t) => t.id === telaId);
    if (!tela) return h("p", { text: "Tela do PJe-Calc desconhecida." });
    const vinc = E.caso.pjecalc || {};
    const cab = cabecalhoFuncao(tela);
    if (!vinc.calculoId) return h("div", {}, cab, h("div", { class: "cartao" }, h("h2", { text: "Envie o cálculo ao PJe-Calc primeiro" }),
      h("p", { text: "Esta função grava diretamente no cálculo do PJe-Calc. Envie o cálculo uma vez (o Studio cria o cálculo lá) e volte aqui." }),
      h("button", { class: "botao primario", onclick: async () => { await operar("gravar"); renderEtapa(); } }, "Enviar ao PJe-Calc")));
    // aberta pela etapa "Outros itens do cálculo": ao terminar, marcar como preenchido e voltar
    const item = OUTROS_ITENS.find((i) => i.id === telaId);
    const resp = E.caso.rascunho.outrosItens || {};
    const voltaOutros = item && resp[telaId] ? h("div", { class: "faixa " + (resp[telaId] === "feito" ? "ok" : "info"), style: "align-items:center" },
      h("div", { text: resp[telaId] === "feito" ? `${item.nome}: marcado como preenchido.` : `Preencha ${item.nome} aqui e clique em Salvar nesta tela. Depois, volte:` }),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-left:auto" },
        resp[telaId] === "sim" ? h("button", { type: "button", class: "botao primario pequeno", onclick: () => {
          E.caso.rascunho.outrosItens[telaId] = "feito"; agendarSalvamento(); location.hash = `#/caso/${E.caso.id}/outros`; } }, "Já preenchi: voltar à lista") : null,
        h("a", { class: "botao pequeno", href: `#/caso/${E.caso.id}/outros` }, "← Outros itens do cálculo"))) : null;
    return h("div", {}, cab, voltaOutros,
      h("p", { class: "mini sutil" }, "O que você salvar aqui é validado e gravado pelo próprio PJe-Calc no cálculo nº ", h("strong", { text: vinc.calculoId }),
        ". Depois de alterar algo, use “Calcular” para gerar um resultado novo." + (tela.studio ? " Os campos preenchidos nas etapas do Studio prevalecem quando ele enviar de novo." : "")),
      visaoTela(tela, E.caso.id));
  }
  async function telaOriginalGeral(telaId) {
    lateralGeral("original:" + telaId);
    const tela = TELAS_GERAIS.find((t) => t.id === telaId) || TELAS_GERAIS[0];
    preencher($("#conteudo"), h("div", { class: "area" },
      cabecalhoFuncao(tela),
      visaoTela(tela, null)));
  }
  function cabecalhoFuncao(tela) {
    const chave = ajudaDaTela(tela);
    return h("div", { class: "cabecalho-etapa" }, h("div", {}, h("p", { class: "eyebrow", text: `Funções do PJe-Calc · ${tela.grupo}` }),
      h("div", { class: "titulo-com-ajuda" }, h("h1", { text: tela.titulo }), botaoAjuda(chave, tela.titulo.replace(/ \(completa\)$/, ""), "?")),
      h("p", { class: "sutil", text: window.AJUDA[chave].essencial })));
  }
  // lista de telas originais na navegação do cálculo
  function navOriginal(atual) {
    const grupos = [...new Set(TELAS_ORIGINAIS.map((t) => t.grupo))];
    const aberta = atual?.startsWith("original:");
    return h("details", { class: "nav-original", open: aberta },
      h("summary", {}, `Todas as funções do PJe-Calc (${TELAS_ORIGINAIS.length})`),
      grupos.map((g) => h("div", {}, h("p", { class: "fase-titulo", text: g }),
        h("ul", { class: "etapas" }, TELAS_ORIGINAIS.filter((t) => t.grupo === g).map((t) => h("li", {},
          h("a", { href: `#/caso/${E.caso.id}/original/${t.id}`, "aria-current": atual === "original:" + t.id ? "page" : null, title: t.desc || "" },
            h("span", { class: "etapa-marca original", "aria-hidden": "true", text: "›" }), h("span", { text: t.titulo }))))))));
  }
  // atalho, no cabeçalho de uma etapa do Studio, para a função equivalente do PJe-Calc (todos os campos)
  const ORIGINAL_DA_ETAPA = { identificacao: "dados", contrato: "dados", historico: "historico", jornada: "dados", verbas: "verbas",
    reflexos: "verbas", atualizacao: "correcao", conferencia: "liquidar", calculo: "liquidar", resultado: "imprimir", exportacao: "imprimir" };
  function linkOriginalDaEtapa(et) {
    const t = TELAS_ORIGINAIS.find((x) => x.id === ORIGINAL_DA_ETAPA[et]);
    return t && E.caso ? h("a", { class: "botao pequeno leve", href: `#/caso/${E.caso.id}/original/${t.id}`, title: "Todos os campos desta função do PJe-Calc" }, `Todos os campos do PJe-Calc`) : null;
  }

  // ---------------------------------------------------------------------------- trazer cálculo existente do PJe-Calc
  async function trazerDoPjecalc() {
    const corpo = h("div", {});
    const lista = h("div", {}, h("p", { role: "status", text: "Lendo os cálculos do PJe-Calc…" }));
    const busca = h("input", { id: "trazerBusca", type: "search", placeholder: "nº do cálculo ou nome do reclamante" });
    const carregar = async () => {
      const t = busca.value.trim();
      preencher(lista, h("p", { role: "status", text: t ? `Procurando “${t}” no PJe-Calc…` : "Lendo os cálculos do PJe-Calc…" }));
      try { await mostrar(await api("GET", "/api/pjecalc/calculos" + (t ? (/^\d+$/.test(t) ? "?calculo=" : "?reclamante=") + encodeURIComponent(t) : ""))); }
      catch (e) { preencher(lista, h("div", { class: "faixa erro" }, h("div", { text: "Não foi possível ler os cálculos do PJe-Calc: " + e.message }))); }
    };
    preencher(corpo,
      h("p", { text: "Liga ao Studio um cálculo que já existe no PJe-Calc, sem copiá-lo nem duplicá-lo. O Studio lê os dados do cálculo, os históricos e a lista de verbas; tudo o mais (faltas, férias, cartão de ponto, contribuição social, IR, honorários, custas…) continua no PJe-Calc e pode ser usado pelas telas originais dentro do Studio." }),
      h("form", { class: "filtros", onsubmit: (ev) => { ev.preventDefault(); carregar(); } },
        h("div", { class: "campo" }, h("label", { for: "trazerBusca", text: "Procurar no PJe-Calc" }), busca),
        h("button", { class: "botao", type: "submit" }, "Procurar")),
      h("p", { class: "mini sutil", text: "Sem busca, o PJe-Calc mostra só os cálculos mais recentes." }),
      lista);
    const p = dialogo({ titulo: "Trazer um cálculo do PJe-Calc", largo: true, corpo, botoes: [{ texto: "Fechar", valor: null }] });
    const mostrar = async (r) => {
      preencher(lista,
        r.calculos.length ? h("div", { class: "tabela-rolagem", style: "max-height:50vh" }, h("table", { class: "tabela" },
          h("thead", {}, h("tr", {}, ["Nº", "Processo", "Reclamante", "Reclamado", ""].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, r.calculos.map((c) => h("tr", {}, h("td", { class: "num", text: c.calculo }), h("td", { text: c.processo || "—" }), h("td", { text: c.reclamante || "—" }), h("td", { text: c.reclamado || "—" }),
            h("td", {}, c.studio ? h("a", { href: `#/caso/${c.studio.id}/identificacao`, onclick: () => $("#dialogo").close() }, "Já está no Studio")
              : h("button", { class: "botao pequeno primario", onclick: async (ev) => {
                ev.currentTarget.disabled = true; ev.currentTarget.textContent = "Trazendo…";
                try { const t = await api("POST", `/api/pjecalc/calculos/${c.calculo}/trazer`, {});
                  if (!t.ok) { avisar(t.erro || "O PJe-Calc não abriu o cálculo.", "erro", 10000); return; }
                  $("#dialogo").close();
                  avisar(`Cálculo nº ${c.calculo} ligado ao Studio (${t.historicos} histórico(s), ${t.verbas} verba(s)).${(t.avisos || []).map((a) => " " + a).join("")}`, t.avisos?.length ? "alerta" : "ok", t.avisos?.length ? 20000 : 8000);
                  location.hash = `#/caso/${t.caso}/identificacao`;
                } catch (e) { avisar(e.message, "erro", 10000); } } }, "Trazer")))))))
          : h("p", { class: "sutil", text: "Nenhum cálculo encontrado no PJe-Calc." }));
    };
    carregar();
    return p;
  }

  // ============================================================================ comparar cenários
  async function telaComparar(q) {
    lateralGeral("comparar");
    const casos = (await api("GET", "/api/casos")).casos;
    const sa = h("select", { id: "cmpA" }, casos.map((c) => h("option", { value: c.id, selected: c.id === q.a }, c.titulo)));
    const sb = h("select", { id: "cmpB" }, casos.map((c) => h("option", { value: c.id, selected: c.id === q.b }, c.titulo)));
    const ir = () => { location.hash = `#/comparar?a=${sa.value}&b=${sb.value}`; };
    const cab = h("div", {}, h("h1", { text: "Comparar cenários" }), h("p", { class: "sutil", text: "Cada cenário é processado pelo PJe-Calc. A comparação mostra as diferenças nas entradas e nos resultados oficiais." }),
      h("div", { class: "filtros" }, h("div", { class: "campo" }, h("label", { for: "cmpA", text: "Cenário A" }), sa), h("div", { class: "campo" }, h("label", { for: "cmpB", text: "Cenário B" }), sb), h("button", { class: "botao primario", onclick: ir }, "Comparar")));
    if (!q.a || !q.b) { preencher($("#conteudo"), cab); return; }
    const r = await api("GET", `/api/comparar?a=${q.a}&b=${q.b}`);
    const secao = (tit, linhas) => h("section", { class: "cartao" }, h("h2", { text: tit }), linhas.length ? h("div", { class: "tabela-rolagem" }, h("table", { class: "tabela" },
      h("thead", {}, h("tr", {}, ["Descrição", "A", "B", "Diferença (B − A)"].map((t, i) => h("th", { scope: "col", class: i ? "num" : null, text: t })))),
      h("tbody", {}, linhas.map((l) => h("tr", {}, h("td", { text: l.descricao }), h("td", { class: "num", text: l.a || "—" }), h("td", { class: "num", text: l.b || "—" }),
        h("td", { class: "num " + (l.diferenca && !/^-?0(,0+)?$/.test(l.diferenca) ? (l.diferenca.startsWith("-") ? "negativo" : "positivo") : ""), text: l.diferenca || "—" })))))) : h("p", { text: "Sem diferenças." }));
    preencher($("#conteudo"), cab,
      r.motor ? h("section", { class: "cartao" }, h("h2", { text: "Motor e tabelas" }),
        (r.motor.versaoDiferente || r.motor.tabelasDiferentes) ? h("div", { class: "faixa alerta" }, h("div", { text: `${r.motor.versaoDiferente ? "Versões do PJe-Calc diferentes. " : ""}${r.motor.tabelasDiferentes ? "Referência das tabelas auxiliares diferente entre as execuções." : ""}` })) : h("p", { class: "positivo", text: "Mesma versão do motor e mesma referência de tabelas." }),
        h("p", { class: "mini", text: `A: PJe-Calc ${r.motor.a.versaoMotor} em ${quando(r.motor.a.em)} (rev. ${r.motor.a.revisaoEntradas}) · B: PJe-Calc ${r.motor.b.versaoMotor} em ${quando(r.motor.b.em)} (rev. ${r.motor.b.revisaoEntradas})` }),
        r.desatualizado && (r.desatualizado.a || r.desatualizado.b) ? h("div", { class: "faixa erro" }, h("div", { text: "Ao menos um cenário tem resultado desatualizado em relação às entradas atuais." })) : null) : h("div", { class: "faixa info" }, h("div", { text: r.motivo })),
      h("section", { class: "cartao" }, h("h2", { text: `Entradas alteradas (${r.entradas.length})` }), r.entradas.length ? h("div", { class: "tabela-rolagem", style: "max-height:40vh" }, h("table", { class: "tabela" },
        h("thead", {}, h("tr", {}, ["Campo", "A", "B"].map((t) => h("th", { scope: "col", text: t })))),
        h("tbody", {}, r.entradas.map((x) => h("tr", {}, h("td", {}, h("code", { text: x.campo })), h("td", { text: fmt(x.de) }), h("td", { text: fmt(x.para) })))))) : h("p", { text: "Entradas idênticas." })),
      r.resultados ? [secao("Resumo por verba (total)", r.resultados.verbas), secao("Créditos e descontos do reclamante", r.resultados.creditos_descontos), secao("Débitos do reclamado por credor", r.resultados.debitos_reclamado),
        h("section", { class: "cartao" }, h("h2", { text: `Diferenças por verba e competência (${r.resultados.ocorrencias.length})` }),
          r.resultados.ocorrencias.length ? h("div", { class: "tabela-rolagem", style: "max-height:50vh" }, h("table", { class: "tabela" }, h("thead", {}, h("tr", {}, ["Verba", "Competência", "Campo", "A", "B"].map((t) => h("th", { scope: "col", text: t })))),
            h("tbody", {}, r.resultados.ocorrencias.slice(0, 1500).map((o) => h("tr", {}, h("td", { text: o.verba || o.campo }), h("td", { text: o.competencia || "—" }), h("td", { text: o.campo || o.nivel }), h("td", { class: "num", text: fmt(o.a) }), h("td", { class: "num", text: fmt(o.b) })))))) : h("p", { text: "Nenhuma diferença nas ocorrências." }))] : null);
  }

  // ============================================================================ modelos e padrões do escritório
  // Modelo = ponto de partida de um cálculo (etapas do Studio + padrões das funções do PJe-Calc). É editado como um
  // cálculo comum (mesmas etapas e formulários) e guardado em versões, sem dados pessoais.
  const CATEGORIAS_MODELO = ["Liquidação de sentença", "Execução", "Atualização de cálculo", "Petição inicial", "Acordo", "Rescisórias", "Outros"];
  async function telaModelos() {
    lateralGeral("modelos");
    const [r, rp] = await Promise.all([api("GET", "/api/modelos"), api("GET", "/api/padroes").catch(() => ({ padroes: [] }))]);
    const pref = E.config.modeloPadrao || null;
    const ehPadrao = (m) => !!pref && m.id === pref.id && m.origem === pref.origem;
    const porId = Object.fromEntries(rp.padroes.map((p) => [p.id, p]));
    const grupos = {};
    r.modelos.forEach((m) => { const g = m.categoria || "Outros"; (grupos[g] = grupos[g] || []).push(m); });
    const ordem = [...CATEGORIAS_MODELO.filter((c) => grupos[c]), ...Object.keys(grupos).filter((c) => !CATEGORIAS_MODELO.includes(c))];
    const cartao = (m) => h("article", { class: "cartao modelo-cartao" },
      h("div", { class: "modelo-cab" }, h("h3", { text: m.nome }),
        m.origem === "escritorio" ? h("span", { class: "etiqueta", text: `do escritório · v${m.versao}${m.autor ? " · " + m.autor : ""}` }) : h("span", { class: "etiqueta", text: "modelo inicial" }),
        m.suporte ? h("span", { class: "pill " + (m.suporte === "completo" ? "pill-ok" : "pill-alerta"), text: m.suporte === "completo" ? "suporte completo" : "suporte parcial" }) : null,
        ehPadrao(m) ? h("span", { class: "pill pill-ok", text: "padrão do escritório" }) : null),
      h("p", { class: "mini", text: m.descricao || "" }),
      (m.padroes || []).length ? h("p", { class: "mini sutil", text: "Aplica no PJe-Calc: " + m.padroes.map((id) => porId[id] ? rotuloPadrao(porId[id]) : "(padrão excluído)").join("; ") }) : null,
      h("div", { class: "ferramentas" },
        h("button", { class: "botao primario pequeno", onclick: async () => { const c = await api("POST", "/api/casos", { modelo: { id: m.id, origem: m.origem } }); location.hash = `#/caso/${c.caso.id}/identificacao`; } }, "Usar modelo"),
        h("button", { class: "botao pequeno", onclick: () => editarModelo(m), title: m.origem === "escritorio" ? "Abre o modelo nas etapas do Studio" : "Cria um modelo do escritório a partir deste" }, m.origem === "escritorio" ? "Editar" : "Personalizar"),
        h("button", { class: "botao pequeno leve", onclick: () => verModelo(m) }, "Ver premissas"),
        h("button", { class: "botao pequeno leve", onclick: () => definirModeloPadrao(ehPadrao(m) ? null : m),
          title: "O modelo padrão já vem marcado em “Novo cálculo”" }, ehPadrao(m) ? "Deixar de ser o padrão" : "Usar como padrão em “Novo cálculo”")));
    preencher($("#conteudo"), h("div", { class: "area" },
      h("div", { class: "cabecalho-etapa" }, h("div", {}, h("h1", { text: "Modelos de cálculo" }),
        h("p", { class: "sutil", text: "Um modelo deixa prontos os parâmetros e verbas de um tipo de trabalho (liquidação de sentença, execução, atualização…) e pode aplicar padrões do escritório nas funções do PJe-Calc (honorários, custas, imposto de renda…). Assim cada cálculo novo começa quase pronto." })),
        h("div", { class: "acoes" }, h("a", { class: "botao", href: "#/padroes" }, "Padrões do escritório"), h("button", { class: "botao primario", onclick: novoModelo }, "Novo modelo"))),
      ordem.map((g) => h("section", {}, h("h2", { text: g }), grupos[g].map(cartao)))));
  }
  async function verModelo(m) {
    const r = await api("GET", `/api/modelos/${m.id}?origem=${m.origem}`);
    const md = r.modelo;
    const rp = await api("GET", "/api/padroes").catch(() => ({ padroes: [] }));
    await dialogo({ titulo: md.nome, largo: true, corpo: h("div", {}, h("p", { text: md.descricao || "" }),
      h("h3", { text: "Premissas" }), h("ul", { class: "premissas" }, (md.premissas || []).map((p) => h("li", {}, p.confirmar ? h("span", { class: "marcador alerta", text: "Confirmar" }) : null, " ", p.texto))),
      md.rascunho?.verbas?.length ? h("p", {}, h("strong", { text: "Verbas: " }), md.rascunho.verbas.join(", ")) : null,
      avisoPadroes(md.padroes, rp.padroes.filter((p) => (md.padroes || []).includes(p.id)), "Padrões aplicados no PJe-Calc:"),
      md.fontes ? h("p", { class: "mini sutil", text: "Fontes: " + md.fontes.join("; ") }) : null,
      r.historico?.length ? h("div", {}, h("h3", { text: "Histórico de versões" }), h("ul", {}, r.historico.map((v) => h("li", { text: `v${v.versao} — ${quando(v.em)} — ${v.autor}${v.nota ? ": " + v.nota : ""}` })))) : null) });
  }
  async function definirModeloPadrao(m) {
    const valor = m ? { id: m.id, origem: m.origem, nome: m.nome } : null;
    await api("PUT", "/api/config", { modeloPadrao: valor });
    E.config.modeloPadrao = valor;
    avisar(m ? `“${m.nome}” agora vem marcado em “Novo cálculo”.` : "Nenhum modelo vem marcado em “Novo cálculo”.", "ok");
    telaModelos();
  }
  async function editarModelo(m) {
    const r = await api("POST", "/api/modelos/editar", { modelo: { id: m.id, origem: m.origem } });
    avisar(m.origem === "escritorio" ? "Modelo aberto para edição. Ajuste as etapas e use “Salvar modelo” no alto." : "Cópia do modelo criada para o escritório. Ajuste as etapas e use “Salvar modelo” no alto.", "ok", 9000);
    location.hash = `#/caso/${r.caso.id}/identificacao`;
  }
  async function novoModelo() {
    const [rc, rm] = await Promise.all([api("GET", "/api/casos"), api("GET", "/api/modelos")]);
    const nome = h("input", { type: "text", id: "nmNome", placeholder: "Ex.: Liquidação de sentença — padrão do escritório" });
    const cat = h("select", { id: "nmCat" }, CATEGORIAS_MODELO.map((c) => h("option", { value: c }, c)));
    const casos = rc.casos.filter((c) => !c.modeloEmEdicao);
    const selCaso = h("select", { id: "nmCaso", "aria-label": "Cálculo de origem" }, casos.map((c) => h("option", { value: c.id }, c.titulo || "(sem título)")));
    const selModelo = h("select", { id: "nmModelo", "aria-label": "Modelo de origem" }, rm.modelos.map((m, i) => h("option", { value: i }, `${m.nome}${m.origem === "escritorio" ? " (escritório)" : ""}`)));
    const base = (v, rot, extra) => { const id = "nmB-" + v; const rb = h("input", { type: "radio", name: "nmBase", id, value: v, checked: v === "branco" });
      return h("div", { class: "marcacao" }, rb, h("div", {}, h("label", { for: id, text: rot }), extra || null)); };
    const ok = await dialogo({ titulo: "Novo modelo", largo: true, corpo: h("div", {},
      h("p", { text: "O modelo abre nas mesmas etapas de um cálculo. Preencha o que se repete nesse tipo de trabalho (verbas, critérios de correção e juros, FGTS, liquidação…) e use “Salvar modelo”. Partes, processo e documentos nunca entram no modelo." }),
      h("div", { class: "grade" }, h("div", { class: "campo" }, h("label", { for: "nmNome", text: "Nome do modelo" }), nome), h("div", { class: "campo" }, h("label", { for: "nmCat", text: "Tipo de trabalho" }), cat)),
      h("h3", { text: "Começar de" }),
      h("div", { class: "pilha" }, base("branco", "Em branco"), casos.length ? base("caso", "Um cálculo do escritório (copia verbas e critérios, sem dados pessoais)", selCaso) : null,
        base("modelo", "Outro modelo", selModelo))),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Criar e editar o modelo", valor: true, classe: "primario" }] });
    if (!ok) return;
    const escolha = document.querySelector('input[name="nmBase"]:checked')?.value || "branco";
    const corpo = { nome: nome.value, categoria: cat.value };
    if (escolha === "caso") corpo.caso = selCaso.value;
    if (escolha === "modelo") { const m = rm.modelos[+selModelo.value]; corpo.modelo = { id: m.id, origem: m.origem }; }
    const r = await api("POST", "/api/modelos/editar", corpo);
    location.hash = `#/caso/${r.caso.id}/identificacao`;
  }
  // Salvar o cálculo aberto como modelo (ou como nova versão do modelo em edição)
  async function salvarComoModelo() {
    const ed = E.caso.edicaoModelo || null;
    const [r0, rp] = await Promise.all([api("GET", "/api/modelos"), api("GET", "/api/padroes").catch(() => ({ padroes: [] }))]);
    const existentes = r0.modelos.filter((m) => m.origem === "escritorio");
    const alvo = h("select", { id: "mAlvo" }, h("option", { value: "" }, "Novo modelo"),
      existentes.map((m) => h("option", { value: m.id, selected: ed?.id === m.id }, `Nova versão de: ${m.nome} (v${m.versao})`)));
    const nome = h("input", { type: "text", id: "mNome", value: ed?.nome || "" });
    const cat = h("select", { id: "mCat" }, CATEGORIAS_MODELO.map((c) => h("option", { value: c, selected: (ed?.categoria || "Liquidação de sentença") === c }, c)));
    const desc = h("textarea", { id: "mDesc", rows: 2 }, ed?.descricao || "");
    const prem = h("textarea", { id: "mPrem", rows: 4, placeholder: "Uma premissa por linha. Ex.: Correção pela TUACDT e juros conforme Lei 14.905/2024." }, (ed?.premissas || []).map((p) => p.texto).join("\n"));
    const nota = h("input", { type: "text", id: "mNota", placeholder: "Ex.: incluída multa de 40%" });
    const marcados = new Set(ed?.padroes || []);
    const cbs = rp.padroes.map((p) => h("input", { type: "checkbox", id: "mp-" + p.id, value: p.id, checked: marcados.has(p.id) }));
    alvo.addEventListener("change", () => {  // nova versão: traz nome, tipo, descrição e padrões do modelo escolhido
      const m = existentes.find((x) => x.id === alvo.value); if (!m) return;
      nome.value = m.nome; desc.value = m.descricao || ""; if (m.categoria) cat.value = m.categoria;
      prem.value = (m.premissas || []).map((p) => p.texto).join("\n");
      cbs.forEach((cb) => { cb.checked = (m.padroes || []).includes(cb.value); });
    });
    const ok = await dialogo({ titulo: ed ? "Salvar modelo" : "Salvar como modelo do escritório", largo: true, corpo: h("div", { class: "grade" },
      h("div", { class: "faixa info inteiro" }, h("div", { text: "Os dados pessoais do caso (processo, partes, documentos, observações e trechos de decisões) não entram no modelo." })),
      h("div", { class: "campo" }, h("label", { for: "mAlvo", text: "Destino" }), alvo),
      h("div", { class: "campo" }, h("label", { for: "mCat", text: "Tipo de trabalho" }), cat),
      h("div", { class: "campo inteiro" }, h("label", { for: "mNome", text: "Nome do modelo" }), nome),
      h("div", { class: "campo inteiro" }, h("label", { for: "mDesc", text: "Descrição" }), desc),
      h("div", { class: "campo inteiro" }, h("label", { for: "mPrem", text: "Premissas (o que quem usar o modelo deve conferir)" }), prem),
      h("div", { class: "campo inteiro" }, h("div", { class: "rotulo", text: "Padrões do escritório que o modelo aplica no PJe-Calc (no primeiro envio)" }),
        rp.padroes.length ? h("div", { class: "chips" }, rp.padroes.map((p, i) => h("label", { class: "marcacao", for: cbs[i].id }, cbs[i], h("span", { text: rotuloPadrao(p) }))))
          : h("p", { class: "mini sutil", text: "Nenhum padrão ainda. Para criar: abra uma função do PJe-Calc (ex.: Honorários), preencha e use “Salvar como padrão”." })),
      h("div", { class: "campo inteiro" }, h("label", { for: "mNota", text: "Nota desta versão (opcional)" }), nota)),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Salvar modelo", valor: true, classe: "primario" }] });
    if (!ok) return;
    try {
      const r = await api("POST", "/api/modelos", { casoId: E.caso.id, id: alvo.value || undefined, nome: nome.value, categoria: cat.value, descricao: desc.value, nota: nota.value,
        premissas: prem.value.split("\n").map((t) => t.trim()).filter(Boolean).map((t) => ({ texto: t })), padroes: cbs.filter((cb) => cb.checked).map((cb) => cb.value) });
      if (ed) E.caso.edicaoModelo = { ...ed, id: r.modelo.id, nome: r.modelo.nome, categoria: r.modelo.categoria, descricao: r.modelo.descricao, premissas: r.modelo.premissas, padroes: r.modelo.padroes };
      avisar(`Modelo “${r.modelo.nome}” salvo (versão ${r.modelo.versao}).`, "ok");
      if (ed) renderEtapa();
    } catch (e) { avisar(e.message, "erro", 9000); }
  }

  // Padrões do escritório: lista, nome, aplicação automática e exclusão
  async function telaPadroes() {
    lateralGeral("padroes");
    const r = await api("GET", "/api/padroes");
    const grupos = {};
    r.padroes.forEach((p) => { (grupos[p.funcao || p.menu] = grupos[p.funcao || p.menu] || []).push(p); });
    const cartao = (p) => {
      const auto = h("input", { type: "checkbox", id: "pa-" + p.id, checked: !!p.automatico });
      auto.addEventListener("change", async () => { await api("PUT", `/api/padroes/${p.id}`, { automatico: auto.checked });
        avisar(auto.checked ? `“${p.nome}” será aplicado em todo cálculo novo.` : `“${p.nome}” deixa de ser automático.`, "ok"); });
      return h("article", { class: "cartao" },
        h("div", { class: "modelo-cab" }, h("h3", { text: p.nome }), p.automatico ? h("span", { class: "pill pill-ok", text: "automático" }) : null,
          h("span", { class: "mini sutil", text: `${p.autor || ""} · ${quando(p.em)}` })),
        p.descricao ? h("p", { class: "mini", text: p.descricao }) : null,
        h("details", {}, h("summary", {}, `${p.passos.length} passo(s) repetido(s)`),
          h("ol", { class: "lista-simples mini" }, p.passos.map((x) => h("li", { text: x.tipo === "acao" ? `Botão “${x.texto}”` : `${x.rotulo || x.nome}: ${x.valor === true ? "marcado" : x.valor === false ? "desmarcado" : x.valorRotulo || x.valor}` })))),
        h("label", { class: "marcacao", for: auto.id }, auto, h("span", { text: "Aplicar automaticamente em todo cálculo novo (no primeiro envio ao PJe-Calc)" })),
        h("div", { class: "ferramentas" },
          h("button", { class: "botao pequeno", onclick: async () => {
            const n = h("input", { type: "text", id: "prNome", value: p.nome }), d = h("textarea", { id: "prDesc", rows: 2 }, p.descricao || "");
            if (!(await dialogo({ titulo: "Renomear padrão", corpo: h("div", {}, h("div", { class: "campo" }, h("label", { for: "prNome", text: "Nome" }), n), h("div", { class: "campo" }, h("label", { for: "prDesc", text: "Descrição" }), d)),
              botoes: [{ texto: "Cancelar", valor: false }, { texto: "Salvar", valor: true, classe: "primario" }] }))) return;
            await api("PUT", `/api/padroes/${p.id}`, { nome: n.value, descricao: d.value }); telaPadroes(); } }, "Renomear"),
          h("button", { class: "botao pequeno perigo", onclick: async () => {
            if (!(await confirmar("Excluir padrão", `Excluir “${p.nome}”? Ele sai dos modelos que o usam. O que já foi aplicado nos cálculos continua no PJe-Calc.`, "Excluir", true))) return;
            await api("DELETE", `/api/padroes/${p.id}`); avisar("Padrão movido para a lixeira local.", "ok"); telaPadroes(); } }, "Excluir")));
    };
    preencher($("#conteudo"), h("div", { class: "area" },
      h("div", { class: "cabecalho-etapa" }, h("div", {}, h("h1", { text: "Padrões do escritório" }),
        h("p", { class: "sutil", text: "Um padrão guarda o preenchimento de uma função do PJe-Calc (honorários de sucumbência, custas, imposto de renda, contribuição social, correção e juros…) para repetir em outros cálculos com um clique. Também pode entrar sozinho em todo cálculo novo ou fazer parte de um modelo." })),
        h("div", { class: "acoes" }, h("a", { class: "botao", href: "#/modelos" }, "Modelos de cálculo"))),
      !r.padroes.length ? h("div", { class: "cartao" }, h("h2", { text: "Como criar um padrão" }),
        h("ol", {}, h("li", { text: "Abra um cálculo enviado ao PJe-Calc e, em “Funções do PJe-Calc”, a função desejada (por exemplo, Honorários)." }),
          h("li", { text: "Preencha como o escritório costuma fazer e, se quiser que o padrão grave sozinho, clique no botão Salvar da tela." }),
          h("li", { text: "Use “Salvar como padrão”, dê um nome e desmarque o que é só daquele caso (datas, nomes)." }),
          h("li", { text: "Nos próximos cálculos: “Aplicar padrão” na mesma função, “Aplicar padrões” no menu do cálculo, automático em todo cálculo novo, ou dentro de um modelo." }))) : null,
      Object.entries(grupos).map(([g, ps]) => h("section", {}, h("h2", { text: g }), ps.map(cartao)))));
  }
  // aplica padrões escolhidos ao cálculo aberto (cada um na sua função do PJe-Calc)
  async function aplicarPadroesNoCaso() {
    if (!E.caso.pjecalc?.calculoId) { avisar("Envie o cálculo ao PJe-Calc uma vez antes de aplicar padrões.", "alerta", 8000); return; }
    const rp = await api("GET", "/api/padroes");
    if (!rp.padroes.length) { avisar("Ainda não há padrões. Abra uma função do PJe-Calc, preencha e use “Salvar como padrão”.", "info", 9000); return; }
    const aplicados = E.caso.pjecalc.padroesAplicados || {};
    const cbs = rp.padroes.map((p) => h("input", { type: "checkbox", id: "ap-" + p.id, value: p.id }));
    const ok = await dialogo({ titulo: "Aplicar padrões do escritório", largo: true, corpo: h("div", {},
      h("p", { text: "Cada padrão abre a sua função no PJe-Calc deste cálculo e repete o preenchimento; o PJe-Calc valida e grava." }),
      h("ul", { class: "padrao-passos" }, rp.padroes.map((p, i) => h("li", {}, h("label", { class: "marcacao", for: cbs[i].id }, cbs[i],
        h("span", {}, h("strong", { text: p.nome }), ` — ${p.funcao || p.menu}`,
          aplicados[p.id] ? h("span", { class: "mini " + (aplicados[p.id].ok ? "sutil" : "negativo"), text: ` (já aplicado em ${quando(aplicados[p.id].em)}${aplicados[p.id].ok ? "" : ", com erro"}; aplicar de novo pode criar um registro repetido)` }) : null))))) ),
      botoes: [{ texto: "Cancelar", valor: false }, { texto: "Aplicar", valor: true, classe: "primario" }] });
    const ids = cbs.filter((cb) => cb.checked).map((cb) => cb.value);
    if (!ok || !ids.length) return;
    const d = $("#dialogo");
    preencher(d, h("div", { class: "dlg-cab" }, h("h2", { text: "Aplicando padrões…" })), h("div", { class: "dlg-corpo" }, h("p", { role: "status", text: "O PJe-Calc está recebendo os padrões. Não feche esta janela." })));
    d.showModal();
    try {
      const r = await api("POST", `/api/casos/${E.caso.id}/padroes`, { padroes: ids });
      d.close();
      E.caso = r.caso; E.estadoRes = r.estado;
      await dialogo({ titulo: r.ok ? "Padrões aplicados" : "Nem todos os padrões foram aplicados", largo: true, corpo: mostrarPassos(r.passos) });
      renderEtapa();
    } catch (e) { d.close(); avisar(e.message, "erro", 10000); }
  }

  // ============================================================================ configurações, diagnóstico e backups
  async function telaConfig() {
    lateralGeral("config");
    const cfg = (await api("GET", "/api/estado")).config;
    const campoCfg = (k, rot, dica, tipo = "text") => { const id = "cfg-" + k; const inp = h("input", { type: tipo, id, value: cfg[k] || "" });
      return { inp, el: h("div", { class: "campo" }, h("label", { for: id, text: rot }), inp, dica ? h("span", { class: "dica", text: dica }) : null) }; };
    const u = campoCfg("usuario", "Seu nome (registro de alterações)", "Aparece na trilha de auditoria de cada cálculo.");
    const url = campoCfg("urlPjecalc", "Endereço do PJe-Calc local", "Padrão: http://127.0.0.1:9257/pjecalc/ (porta definida pelo PJe-Calc).");
    const pasta = campoCfg("pastaInstalacao", "Pasta de instalação do PJe-Calc", "Ex.: C:\\PJeCalc ou a pasta extraída do instalador. Usada no diagnóstico e para ler os textos de ajuda oficiais.");
    const esc = campoCfg("nomeEscritorio", "Nome do escritório (documentos complementares)");
    const logo = h("input", { type: "file", id: "cfgLogo", accept: "image/png,image/jpeg,image/svg+xml" });
    const diag = h("div", { "aria-live": "polite" }, h("p", { class: "sutil", text: "Clique em “Executar diagnóstico”." }));
    const bks = h("div");
    const salvar = async () => {
      const novo = { usuario: u.inp.value, urlPjecalc: url.inp.value, pastaInstalacao: pasta.inp.value, nomeEscritorio: esc.inp.value };
      if (logo.files[0]) { if (logo.files[0].size > 400000) { avisar("Logotipo muito grande (máx. 400 KB).", "erro"); return; } novo.logoEscritorio = await new Promise((ok) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.readAsDataURL(logo.files[0]); }); }
      try { await api("PUT", "/api/config", novo); avisar("Configurações salvas.", "ok"); E.ajudaOficial = null; carregarAjudaOficial(); atualizarStatus(); } catch (e) { avisar(e.message, "erro"); }
    };
    const rodarDiag = async () => {
      preencher(diag, h("p", { text: "Verificando…" }));
      const r = await api("GET", "/api/diagnostico");
      const m = r.motor, i = r.instalacao;
      preencher(diag, listaMensagens(r.avisos.map((a) => ({ severidade: a.nivel === "impeditivo" ? "erro" : "alerta", texto: a.texto }))),
        h("table", { class: "tabela" }, h("tbody", {},
          h("tr", {}, h("th", { scope: "row", text: "PJe-Calc acessível" }), h("td", { text: m.acessivel ? "Sim" : "Não" })),
          h("tr", {}, h("th", { scope: "row", text: "Versão / build" }), h("td", { text: `${m.versao || "—"} / ${m.build || "—"}` })),
          h("tr", {}, h("th", { scope: "row", text: "Interface (PJe-Calc Studio)" }), h("td", { text: r.app })),
          h("tr", {}, h("th", { scope: "row", text: "Pasta de dados desta interface" }), h("td", {}, h("code", { text: r.dados }))),
          h("tr", {}, h("th", { scope: "row", text: "Pasta de instalação" }), h("td", { text: i.pasta || "não informada" })),
          i.arquivos ? h("tr", {}, h("th", { scope: "row", text: "Arquivos essenciais" }), h("td", { text: Object.entries(i.arquivos).map(([k, v]) => `${v ? "✓" : "✗"} ${k}`).join(" · ") })) : null,
          i.bancoBytes ? h("tr", {}, h("th", { scope: "row", text: "Banco de dados do PJe-Calc" }), h("td", { text: `${(i.bancoBytes / 1048576).toFixed(1)} MB (nunca gravado diretamente por esta interface)` })) : null,
          i.ajudaOficial !== undefined ? h("tr", {}, h("th", { scope: "row", text: "Textos de ajuda oficiais" }), h("td", { text: `${i.ajudaOficial} encontrados` })) : null)),
        r.tabelasTexto ? h("details", { class: "mais" }, h("summary", {}, "Referência das tabelas auxiliares (página Versão das Tabelas)"), h("p", { class: "mini", text: r.tabelasTexto })) : null);
    };
    const carregarBackups = async () => {
      const r = await api("GET", "/api/backups");
      preencher(bks, r.backups.length ? h("table", { class: "tabela" }, h("tbody", {}, r.backups.map((b) => h("tr", {}, h("td", { text: b.arquivo }), h("td", { class: "mini", text: quando(b.em) }), h("td", { class: "num mini", text: (b.bytes / 1024).toFixed(0) + " KB" }),
        h("td", {}, h("div", { class: "chips" },
          h("button", { class: "botao pequeno", onclick: async () => { const v = await api("POST", `/api/backups/${b.arquivo}/verificar`); avisar(v.ok ? `Backup íntegro (${v.arquivos} arquivos).` : "Backup com problemas: " + (v.divergentes || []).join(", "), v.ok ? "ok" : "erro"); } }, "Verificar"),
          h("button", { class: "botao pequeno perigo", onclick: async () => { if (await confirmar("Restaurar backup", `Restaurar ${b.arquivo}? O estado atual será guardado em um novo backup antes da restauração.`, "Restaurar", true)) {
            const v = await api("POST", `/api/backups/${b.arquivo}/restaurar`); avisar(v.ok ? `Restaurado. Backup anterior: ${v.backupAnterior}.` : v.motivo, v.ok ? "ok" : "erro"); carregarBackups(); } } }, "Restaurar"))))))) : h("p", { class: "sutil", text: "Nenhuma cópia de segurança." }));
    };
    preencher($("#conteudo"), h("h1", { text: "Configurações e diagnóstico" }),
      await cartaoAtualizacoes(),
      h("section", { class: "cartao" }, h("h2", { text: "Preferências" }), h("div", { class: "grade" }, u.el, url.el, pasta.el, esc.el,
        h("div", { class: "campo" }, h("label", { for: "cfgLogo", text: "Logotipo (documentos complementares)" }), logo)), h("button", { class: "botao primario", style: "margin-top:12px", onclick: salvar }, "Salvar configurações")),
      h("section", { class: "cartao" }, h("h2", { text: "Diagnóstico da instalação" }), h("button", { class: "botao", onclick: rodarDiag }, "Executar diagnóstico"), diag),
      h("section", { class: "cartao" }, h("h2", { text: "Cópias de segurança desta interface" }),
        h("p", { class: "mini sutil", text: "Incluem rascunhos, revisões, execuções e modelos. Para os cálculos gravados no PJe-Calc, use também “Salvar Tudo” no ícone do PJe-Calc na bandeja do Windows antes de atualizar o programa." }),
        h("button", { class: "botao", onclick: async () => { const r = await api("POST", "/api/backups", { motivo: "manual" }); avisar(`Backup ${r.arquivo} criado e ${r.verificado ? "verificado" : "COM FALHA na verificação"}.`, r.verificado ? "ok" : "erro"); carregarBackups(); } }, "Criar cópia de segurança agora"), bks),
      h("section", { class: "cartao" }, h("h2", { text: "Atalhos de teclado" }), tabelaAtalhos()));
    carregarBackups();
  }
  // ============================================================================ assistente Claude (conector MCP)
  async function telaClaude() {
    lateralGeral("claude");
    const st = await api("GET", "/api/claude");
    const comandoCodex = st.comandoCodex || st.comandoClaudeCode.replace(/^claude mcp add pjecalc-studio/, "codex mcp add pjecalc_studio");
    const exemplo = "Crie um cálculo para o Fulano a partir desta sentença (anexada), preencha o que ela traz e me mostre o que ficou em dúvida antes de enviar ao PJe-Calc.";
    const copiar = async (texto, rotulo) => {
      try { await navigator.clipboard.writeText(texto); avisar(`${rotulo} copiado.`, "ok"); } catch { avisar("Não foi possível copiar: selecione o texto e use Ctrl+C.", "erro"); }
    };
    const instalar = async () => {
      try { const r = await api("POST", "/api/claude/instalar-desktop"); avisar(r.mensagem, "ok", 10000); telaClaude(); }
      catch (e) { avisar(e.message, "erro", 12000); }
    };
    const conectar = async () => { const r = await api("POST", "/api/claude/conectar"); avisar(r.mensagem, "ok"); telaClaude(); };
    const novaChave = async () => {
      if (!(await confirmar("Gerar nova chave", "Gerar uma chave nova para o assistente? Programas que tinham a chave antiga perdem o acesso. O Claude Desktop, o Claude Code e o Codex leem a chave nova sozinhos.", "Gerar nova chave"))) return;
      const r = await api("POST", "/api/claude/nova-chave"); avisar(r.mensagem, "ok"); telaClaude();
    };
    const passo = (n, titulo, ...corpo) => h("li", { class: "passo-claude" }, h("span", { class: "passo-num", text: String(n) }), h("div", {}, h("strong", { text: titulo }), ...corpo));
    preencher($("#conteudo"), h("div", { class: "area" },
      h("h1", { text: "Assistentes Claude e Codex" }),
      h("p", { class: "sutil", text: "Conecte o Claude ou o Codex a este Studio: você conversa com o assistente, e ele prepara o cálculo aqui, pelas mesmas regras e conferências desta tela. Quem calcula continua sendo o PJe-Calc." }),
      h("section", { class: "cartao" }, h("h2", { text: "Como funciona" }),
        h("ul", { class: "lista-simples" },
          h("li", { text: "Use a sua própria conta do Claude ou do Codex. O Studio não pede nem guarda senha ou chave de IA." }),
          h("li", { text: `Cada assistente ganha as mesmas ${st.ferramentas} ferramentas e opera tudo sozinho: as etapas do Studio e todas as telas do PJe-Calc (férias, faltas, cartão de ponto, honorários, custas, multas, INSS, IR, pagamentos, tabelas...), até o resultado oficial.` }),
          h("li", {}, h("strong", { text: "Fiel ao documento: " }), "lança o que a petição, a decisão ou o acordo determinam; quando o documento é omisso, usa o padrão do PJe-Calc e avisa; pergunta só o que for indispensável."),
          h("li", { text: "As permissões de cada ação seguem as configurações do assistente escolhido." }),
          h("li", { text: "O Studio precisa estar aberto enquanto você usa o Claude ou o Codex. Para calcular, mantenha também o PJe-Calc aberto." }))),
      h("section", { class: "cartao" }, h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, h("h2", { text: "Claude Desktop", style: "margin:0" }),
          h("span", { class: "situacao " + (st.claudeDesktop ? "ok" : "neutro"), text: st.claudeDesktop ? "instalado neste computador" : "não encontrado neste computador" })),
        h("ol", { class: "passos-claude" },
          st.claudeDesktop ? null : passo(1, "Instale o Claude Desktop", h("p", { class: "mini" }, "Baixe em ", h("a", { href: "https://claude.ai/download", target: "_blank", rel: "noopener" }, "claude.ai/download"), " e entre com a sua conta.")),
          passo(st.claudeDesktop ? 1 : 2, "Instale a extensão do Studio",
            h("p", { class: "mini sutil", text: "Abre a janela de instalação do próprio Claude Desktop, que mostra o que a extensão faz e pede a sua confirmação." }),
            h("div", { class: "ferramentas" },
              st.windows ? h("button", { type: "button", class: "botao primario", onclick: instalar }, icone("baixar"), "Instalar no Claude Desktop") : null,
              h("a", { class: "botao", href: "/api/claude/extensao.mcpb", download: "PJeCalcStudio.mcpb" }, "Baixar a extensão (.mcpb)")),
            h("p", { class: "mini sutil", text: "Se a janela não abrir: baixe o arquivo e arraste-o para a janela do Claude Desktop (ou Configurações › Extensões › Configurações avançadas › Instalar extensão)." })),
          passo(st.claudeDesktop ? 2 : 3, "Peça na conversa", h("p", { class: "mini" }, "Por exemplo: ", h("em", { text: "“" + exemplo + "”" })),
            h("button", { type: "button", class: "botao leve pequeno", onclick: () => copiar(exemplo, "Exemplo") }, "Copiar exemplo")))),
      h("section", { class: "cartao" }, h("h2", { text: "Claude Code" }),
        h("p", { class: "mini sutil", text: "Para quem usa o Claude Code (no terminal ou no aplicativo): rode este comando uma vez." }),
        h("div", { class: "linha-cnj", style: "max-width:none" }, h("input", { type: "text", readonly: true, value: st.comandoClaudeCode, class: "entrada-cnj", "aria-label": "Comando para o Claude Code", style: "font-size:.8125rem" }),
          h("button", { type: "button", class: "botao", onclick: () => copiar(st.comandoClaudeCode, "Comando") }, icone("colar"), "Copiar"))),
      h("section", { class: "cartao" }, h("h2", { text: "Codex" }),
        h("p", { class: "mini sutil", text: "Para usar no Codex: com o comando codex disponível no terminal, rode este comando uma vez. Depois, feche e abra o Codex para carregar as ferramentas." }),
        h("div", { class: "linha-cnj", style: "max-width:none" }, h("input", { type: "text", readonly: true, value: comandoCodex, class: "entrada-cnj", "aria-label": "Comando para o Codex", style: "font-size:.8125rem" }),
          h("button", { type: "button", class: "botao", onclick: () => copiar(comandoCodex, "Comando do Codex") }, icone("colar"), "Copiar")),
        h("p", { class: "mini sutil", text: "Claude e Codex podem ficar configurados ao mesmo tempo. Os dois acessam as mesmas ferramentas e os mesmos cálculos do Studio." }),
        h("p", { class: "mini sutil", text: "Para operações demoradas, ajuste tool_timeout_sec = 900 na seção [mcp_servers.pjecalc_studio] do arquivo de configuração do Codex." })),
      h("section", { class: "cartao" }, h("h2", { text: "Conexão" }),
        st.conexaoAtual ? h("div", { class: "faixa ok" }, h("strong", { text: "Pronto." }), h("div", { text: "Claude e Codex encontram este Studio pelo arquivo de conexão enquanto ele estiver aberto." }))
          : h("div", { class: "faixa alerta", style: "align-items:center" }, h("div", { text: "O arquivo de conexão dos assistentes aponta para outro Studio deste computador (ou para nenhum)." }),
            h("button", { type: "button", class: "botao pequeno", onclick: conectar }, "Conectar os assistentes a este Studio")),
        h("table", { class: "tabela" }, h("tbody", {},
          h("tr", {}, h("th", { scope: "row", text: "Endereço local" }), h("td", {}, h("code", { text: st.endpoint }))),
          h("tr", {}, h("th", { scope: "row", text: "Arquivo de conexão" }), h("td", {}, h("code", { text: st.conexao }))),
          h("tr", {}, h("th", { scope: "row", text: "Proteção" }), h("td", { text: "Só aceita conexões deste computador, com a chave do assistente; sites abertos no navegador não conseguem usá-lo." })))),
        h("button", { type: "button", class: "botao leve pequeno", style: "margin-top:8px", onclick: novaChave }, "Gerar nova chave")),
      h("section", { class: "cartao" }, h("h2", { text: "Sigilo dos dados" }),
        h("div", { class: "faixa alerta" }, h("div", {},
          h("p", { style: "margin:0", text: "Ao usar um assistente, os dados dos cálculos que ele ler (nomes, documentos, salários e trechos de decisões) são enviados ao fornecedor pela sua conta: Anthropic no Claude ou OpenAI no Codex." }),
          h("p", { class: "mini", style: "margin:6px 0 0", text: "Confira se isso está de acordo com o sigilo dos seus clientes. Para testar, use cálculos com dados fictícios." }))))));
  }
  // ---------------------------------------------------------------------------- atualizações
  async function cartaoAtualizacoes() {
    let at = await api("GET", "/api/atualizacao");
    const caixa = h("div", { "aria-live": "polite" });
    const desenhar = () => preencher(caixa,
      h("p", {}, "Versão instalada: ", h("strong", { text: at.versaoAtual }), at.instalado ? "" : " (rodando pelo código-fonte: atualize pelo instalador novo)"),
      at.disponivel ? h("div", { class: "faixa ok" }, h("div", {}, h("strong", { text: `Versão ${at.versao} disponível` }),
          at.tamanho ? h("span", { class: "mini sutil", text: ` · ${(at.tamanho / 1048576).toFixed(0)} MB` }) : null,
          (at.notas || []).length ? h("ul", { class: "lista-simples" }, at.notas.map((n) => h("li", { text: n }))) : null,
          h("p", { class: "mini", style: "margin:6px 0 0", text: "Os seus cálculos ficam onde estão: a atualização troca só os arquivos do programa." })))
        : h("p", { class: "sutil", text: at.erro || "O Studio está atualizado. Ele procura versões novas sozinho, quando abre e a cada 12 horas." }),
      h("div", { class: "ferramentas" },
        h("button", { type: "button", class: "botao", onclick: verificar }, "Procurar atualização agora"),
        at.podeInstalar ? h("button", { type: "button", class: "botao primario", onclick: atualizar }, `Atualizar para ${at.versao}`) : null));
    const verificar = async () => {
      try { at = await api("POST", "/api/atualizacao/verificar"); avisar(at.disponivel ? `Versão ${at.versao} disponível.` : "O Studio está atualizado.", "ok"); }
      catch (e) { avisar(e.message, "erro"); at = await api("GET", "/api/atualizacao"); }
      desenhar();
    };
    const atualizar = async () => {
      if (!(await confirmar("Atualizar o PJe-Calc Studio", `Instalar a versão ${at.versao}? O Studio fecha por alguns segundos e abre de novo; esta página recarrega sozinha. Os seus cálculos não são alterados.`, "Atualizar agora"))) return;
      if (E.pendente && !(await salvarAgora())) { avisar("Salve o rascunho antes de atualizar.", "erro"); return; }
      let r;
      try { r = await api("POST", "/api/atualizacao/instalar"); } catch (e) { avisar(e.message, "erro", 12000); return; }
      const d = $("#dialogo");
      preencher(d, h("div", { class: "dlg-cab" }, h("h2", { text: `Atualizando para a versão ${r.versao}…` })),
        h("div", { class: "dlg-corpo" }, h("p", { role: "status", text: "Baixado e conferido. O Studio está sendo atualizado e vai abrir de novo; não feche esta página." })));
      d.showModal();
      const inicio = Date.now();
      const esperar = async () => {
        try { const e = await api("GET", "/api/estado"); if (e.app === r.versao) { location.reload(); return; } } catch { /* reiniciando */ }
        if (Date.now() - inicio > 180000) { d.close(); avisar("A atualização está demorando. Se o Studio não abrir sozinho, abra pelo atalho PJe-Calc Studio.", "alerta", 20000); return; }
        setTimeout(esperar, 2000);
      };
      setTimeout(esperar, 4000);
    };
    desenhar();
    return h("section", { class: "cartao" }, h("h2", { text: "Atualizações" }), caixa);
  }
  function tabelaAtalhos() {
    return h("table", { class: "tabela" }, h("tbody", {}, [["Ctrl + K", "Pesquisar funções e campos"], ["Ctrl + S", "Salvar o rascunho imediatamente"], ["Alt + → / Alt + ←", "Próxima / etapa anterior"],
      ["Ctrl + Enter", "Calcular (com um cálculo aberto)"], ["F1", "Ajuda do campo em foco"], ["Esc", "Fechar painel de ajuda ou diálogo"], ["Na tabela: setas, Shift+setas, Enter, Espaço, Ctrl+C, Ctrl+V, Ctrl+D", "Navegar, selecionar, editar, marcar, copiar, colar, repetir"]]
      .map(([k, d]) => h("tr", {}, h("th", { scope: "row" }, h("kbd", { text: k })), h("td", { text: d })))));
  }

  // ============================================================================ paleta de comandos
  function abrirPaleta() {
    const d = $("#paleta");
    const inp = h("input", { type: "search", "aria-label": "Pesquisar", placeholder: "Digite uma função, etapa ou campo…", role: "combobox", "aria-expanded": "true", "aria-controls": "paletaLista", "aria-autocomplete": "list" });
    const ul = h("ul", { id: "paletaLista", role: "listbox" });
    const itens = [
      { t: "Painel de cálculos", tipo: "tela", f: () => (location.hash = "#/") }, { t: "Novo cálculo", tipo: "ação", f: novoCalculo }, { t: "Importar arquivo .PJC", tipo: "ação", f: importarPjc },
      { t: "Modelos de cálculo", tipo: "tela", f: () => (location.hash = "#/modelos") }, { t: "Novo modelo", tipo: "ação", f: novoModelo },
      { t: "Padrões do escritório", tipo: "tela", f: () => (location.hash = "#/padroes") }, { t: "Comparar cenários", tipo: "tela", f: () => (location.hash = "#/comparar") },
      { t: "Configurações e diagnóstico", tipo: "tela", f: () => (location.hash = "#/config") },
      { t: "Trazer cálculo do PJe-Calc", tipo: "ação", f: trazerDoPjecalc },
      ...TELAS_GERAIS.map((t) => ({ t: (t.grupo === "Tabelas" ? "Tabela: " : "") + t.titulo, tipo: "função do PJe-Calc", f: () => (location.hash = "#/original/" + t.id) })), { t: "Atalhos de teclado", tipo: "ajuda", f: () => dialogo({ titulo: "Atalhos de teclado", corpo: tabelaAtalhos() }) },
    ];
    if (E.caso && location.hash.includes("/caso/")) {
      ETAPAS.forEach((e, i) => itens.push({ t: `${i + 1}. ${e.titulo}`, tipo: "etapa", f: () => (location.hash = `#/caso/${E.caso.id}/${e.id}`) }));
      TELAS_ORIGINAIS.forEach((t) => itens.push({ t: t.titulo, tipo: "função do PJe-Calc", f: () => (location.hash = `#/caso/${E.caso.id}/original/${t.id}`) }));
      itens.push({ t: "Enviar ao PJe-Calc", tipo: "ação", f: () => operar("gravar") }, { t: "Calcular", tipo: "ação", f: () => operar("executar") },
        { t: "Revisar tudo", tipo: "etapa", f: () => (location.hash = `#/caso/${E.caso.id}/conferencia`) }, { t: "Documentos e arquivo .PJC", tipo: "etapa", f: () => (location.hash = `#/caso/${E.caso.id}/exportacao`) },
        { t: "Versões e alterações", tipo: "tela", f: () => (location.hash = `#/caso/${E.caso.id}/historico-auditoria`) },
        { t: "Duplicar como cenário alternativo", tipo: "ação", f: () => duplicar(E.caso.id) },
        { t: "Aplicar padrões do escritório", tipo: "ação", f: aplicarPadroesNoCaso }, { t: E.caso.edicaoModelo ? "Salvar modelo" : "Salvar como modelo", tipo: "ação", f: salvarComoModelo });
      Object.entries(GRUPOS).forEach(([et, gs]) => gs.forEach((g) => (g.campos || []).forEach((c) => itens.push({ t: c.rotulo, tipo: "campo · " + (ETAPAS.find((x) => x.id === et)?.titulo || et),
        f: () => irParaCampo(et, c.k) }))));
    }
    const rotuloAjuda = (k, a) => Object.values(GRUPOS).flat().flatMap((g) => g.campos || []).find((x) => (x.ajuda || x.k) === k)?.rotulo || (a.oficial ? a.oficial.split("›").pop().trim() : k);
    Object.entries(window.AJUDA).forEach(([k, a]) => { const t = rotuloAjuda(k, a); itens.push({ t: "Ajuda: " + t, tipo: "explicação", f: () => abrirAjuda(k, t) }); });
    let sel = 0, vis = [];
    const desenhar = () => {
      const q = dobrar(inp.value);
      vis = itens.filter((i) => !q || q.split(/\s+/).every((p) => dobrar(i.t + " " + i.tipo).includes(p))).slice(0, 40);
      sel = Math.min(sel, Math.max(0, vis.length - 1));
      preencher(ul, ...vis.map((i, n) => h("li", { role: "option", id: "po" + n, "aria-selected": String(n === sel), onclick: () => { d.close(); i.f(); } }, i.t, h("span", { class: "tipo", text: i.tipo }))));
      inp.setAttribute("aria-activedescendant", vis.length ? "po" + sel : "");
    };
    inp.addEventListener("input", () => { sel = 0; desenhar(); });
    inp.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(sel + 1, vis.length - 1); desenhar(); ul.children[sel]?.scrollIntoView({ block: "nearest" }); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(sel - 1, 0); desenhar(); ul.children[sel]?.scrollIntoView({ block: "nearest" }); }
      else if (e.key === "Enter" && vis[sel]) { e.preventDefault(); d.close(); vis[sel].f(); }
    });
    preencher(d, inp, ul);
    d.showModal(); desenhar(); inp.focus();
  }

  async function carregarAjudaOficial() {
    try { const r = await api("GET", "/api/ajuda-oficial"); E.ajudaOficial = r.itens || []; } catch { E.ajudaOficial = []; }
  }

  // ============================================================================ inicialização
  async function iniciar() {
    aplicarPrefs();
    $("#modoGuiado").onclick = () => { salvarPref({ modo: "guiado" }); aplicarPrefs(); if (E.caso && location.hash.includes("/caso/")) renderEtapa(); };
    $("#modoAvancado").onclick = () => { salvarPref({ modo: "avancado" }); aplicarPrefs(); if (E.caso && location.hash.includes("/caso/")) renderEtapa(); };
    $("#fonteMais").onclick = () => { salvarPref({ fonte: Math.min(150, (prefs().fonte || 100) + 10) }); aplicarPrefs(); avisar(`Fonte em ${prefs().fonte}%`); };
    $("#fonteMenos").onclick = () => { salvarPref({ fonte: Math.max(80, (prefs().fonte || 100) - 10) }); aplicarPrefs(); avisar(`Fonte em ${prefs().fonte}%`); };
    $("#tema").onclick = () => {
      const escuroAtual = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      salvarPref({ tema: escuroAtual ? "light" : "dark" }); aplicarPrefs();
    };
    $("#abrirPaleta").onclick = abrirPaleta;
    // menus "Mais ações": fecham ao clicar fora ou com Escape (o foco volta ao botão)
    document.addEventListener("click", (e) => document.querySelectorAll("details.menu[open]").forEach((m) => { if (!m.contains(e.target)) m.open = false; }));
    document.addEventListener("keydown", (e) => {
      const m = e.key === "Escape" && document.activeElement?.closest?.("details.menu[open]");
      if (m) { e.stopPropagation(); m.open = false; m.querySelector("summary").focus(); }
    }, true);
    document.addEventListener("keydown", (e) => {
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && (e.key === "k" || e.key === "K")) { e.preventDefault(); abrirPaleta(); }
      else if (ctrl && (e.key === "s" || e.key === "S")) { e.preventDefault(); if (E.pendente) salvarAgora().then(() => avisar("Rascunho salvo.", "ok")); else avisar("Nada a salvar: o rascunho já está salvo.", "info"); }
      else if (e.altKey && (e.key === "ArrowRight" || e.key === "ArrowLeft") && E.caso && location.hash.includes("/caso/")) {
        const i = ETAPAS.findIndex((x) => x.id === E.etapa); const j = i + (e.key === "ArrowRight" ? 1 : -1);
        if (i >= 0 && ETAPAS[j]) { e.preventDefault(); location.hash = `#/caso/${E.caso.id}/${ETAPAS[j].id}`; }
      } else if (ctrl && e.key === "Enter" && E.caso && location.hash.includes("/caso/")) { e.preventDefault(); operar("executar"); }
      else if (e.key === "F1") { const b = document.activeElement?.closest?.("[data-campo], .campo, section, article")?.querySelector(".ajuda-btn"); if (b) { e.preventDefault(); b.click(); } }
      else if (e.key === "Escape" && !$("#painelAjuda").hidden && !document.querySelector("dialog[open]")) { e.preventDefault(); fecharAjuda(true); }
    });
    window.addEventListener("hashchange", navegar);
    try { E.opcoes = await api("GET", "/api/opcoes"); } catch (e) { avisar(e.message, "erro", 12000); }
    const st = await atualizarStatus();
    setInterval(atualizarStatus, 30000);
    carregarAjudaOficial();
    await navegar();
    if (st && !st.config.usuario) {
      const nome = h("input", { type: "text", id: "nomeUsuario" });
      const ok = await dialogo({ titulo: "Bem-vindo ao PJe-Calc Studio", corpo: h("div", {},
        h("p", { text: "Esta interface organiza o preenchimento e opera o PJe-Calc instalado neste computador. Os cálculos continuam sendo feitos pelo motor original do PJe-Calc." }),
        h("div", { class: "campo" }, h("label", { for: "nomeUsuario", text: "Seu nome (para o registro de alterações)" }), nome)),
        botoes: [{ texto: "Agora não", valor: false }, { texto: "Salvar nome", valor: true, classe: "primario" }] });
      if (ok && nome.value.trim()) { await api("PUT", "/api/config", { usuario: nome.value.trim() }); E.config.usuario = nome.value.trim(); }
    }
  }
  iniciar();
})();
