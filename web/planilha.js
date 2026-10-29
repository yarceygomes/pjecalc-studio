/* Tabela editável com navegação por teclado, seleção retangular, copiar/colar de planilhas.
 *
 * Teclas: setas (mover), Shift+setas (selecionar), Enter/F2 (editar ou confirmar e descer), Tab (direita),
 * Esc (cancelar), Delete (limpar), Espaço (alternar marcação), Ctrl+C / Ctrl+V (copiar/colar TSV),
 * Ctrl+D (repetir o valor da primeira linha da seleção nas demais).
 *
 * Valores: "" = não informado (vazio), "0,00" = zero, "?" = desconhecido. Os três são exibidos de forma distinta.
 */
"use strict";
(function () {
  const MOEDA = /^-?\d{1,3}(\.\d{3})*(,\d{1,2})?$|^-?\d+(,\d{1,2})?$/;

  function normalizarValor(txt) {
    let t = String(txt == null ? "" : txt).trim().replace(/^R\$\s*/i, "");
    if (t === "" || t === "?") return t;
    if (/^-?\d+\.\d{1,2}$/.test(t) && !t.includes(",")) t = t.replace(".", ","); // 1234.56 vindo de planilha
    if (/^-?\d+(\.\d{3})+$/.test(t)) return null; // ambíguo (1.234 ou 1,234?) — pede revisão
    if (!MOEDA.test(t)) return null;
    const neg = t.startsWith("-");
    let [int, dec = ""] = t.replace("-", "").replace(/\./g, "").split(",");
    dec = (dec + "00").slice(0, 2);
    int = String(parseInt(int, 10));
    int = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (neg ? "-" : "") + int + "," + dec;
  }

  /* Número com casas decimais fixas (quantidade, divisor, multiplicador): "12,5" -> "12,5000" com casas = 4. */
  function normalizarNumero(txt, casas = 4) {
    let t = String(txt == null ? "" : txt).trim();
    if (t === "") return t;
    if (/^-?\d+\.\d+$/.test(t) && !t.includes(",")) t = t.replace(".", ","); // 12.5 vindo de planilha
    if (!/^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$/.test(t)) return null;
    const neg = t.startsWith("-");
    let [int, dec = ""] = t.replace("-", "").replace(/\./g, "").split(",");
    if (dec.length > casas) return null; // o PJe-Calc não aceita mais casas do que exibe
    return (neg ? "-" : "") + String(parseInt(int, 10)) + (casas ? "," + (dec + "0".repeat(casas)).slice(0, casas) : "");
  }

  function lerMarcacao(txt) {
    const t = String(txt == null ? "" : txt).trim().toLowerCase();
    if (["s", "sim", "x", "1", "true", "verdadeiro", "✓"].includes(t)) return true;
    if (["n", "não", "nao", "0", "false", "falso", ""].includes(t)) return false;
    return null;
  }

  class Planilha {
    /* colunas: [{chave, titulo, tipo: "texto"|"moeda"|"numero"|"marca", casas, somenteLeitura, vazio: "significado da célula vazia"}] */
    constructor(raiz, { colunas, linhas, aoAlterar, rotuloLinha, rotuloTabela, classeLinha }) {
      this.raiz = raiz;
      this.colunas = colunas;
      this.linhas = linhas;
      this.aoAlterar = aoAlterar || (() => {});
      this.rotuloLinha = rotuloLinha || ((i) => String(i + 1));
      this.classeLinha = classeLinha || (() => "");
      this.ativa = { l: 0, c: this.primeiraEditavel() };
      this.ancora = null;
      this.editor = null;
      this.tabela = document.createElement("table");
      this.tabela.className = "planilha";
      this.tabela.setAttribute("role", "grid");
      this.tabela.setAttribute("aria-label", rotuloTabela || "Tabela editável");
      this.tabela.tabIndex = 0;
      raiz.replaceChildren(this.tabela);
      this.tabela.addEventListener("keydown", (e) => this.tecla(e));
      this.tabela.addEventListener("mousedown", (e) => this.mouse(e));
      this.tabela.addEventListener("dblclick", (e) => { const td = e.target.closest("td.cel"); if (td) this.editar(); });
      this.tabela.addEventListener("paste", (e) => this.colar(e));
      this.tabela.addEventListener("copy", (e) => this.copiar(e));
      this.desenhar();
    }
    primeiraEditavel() { const i = this.colunas.findIndex((c) => !c.somenteLeitura); return i < 0 ? 0 : i; }
    definirLinhas(linhas) { this.linhas = linhas; this.ativa.l = Math.min(this.ativa.l, Math.max(0, linhas.length - 1)); this.desenhar(); }

    selecao() {
      const a = this.ancora || this.ativa, b = this.ativa;
      return { l1: Math.min(a.l, b.l), l2: Math.max(a.l, b.l), c1: Math.min(a.c, b.c), c2: Math.max(a.c, b.c) };
    }

    desenhar() {
      const t = this.tabela;
      t.replaceChildren();
      const thead = t.createTHead();
      const trh = thead.insertRow();
      const th0 = document.createElement("th"); th0.textContent = "#"; th0.scope = "col"; trh.appendChild(th0);
      this.colunas.forEach((c) => { const th = document.createElement("th"); th.scope = "col"; th.textContent = c.titulo; trh.appendChild(th); });
      const tb = t.createTBody();
      const s = this.selecao();
      this.linhas.forEach((ln, i) => {
        const tr = tb.insertRow();
        tr.setAttribute("role", "row");
        const extra = this.classeLinha(ln, i);
        const rot = tr.insertCell(); rot.className = "rot" + (extra ? " " + extra : ""); rot.textContent = this.rotuloLinha(i, ln);
        this.colunas.forEach((c, j) => {
          const td = tr.insertCell();
          td.className = "cel";
          td.dataset.l = i; td.dataset.c = j;
          td.setAttribute("role", "gridcell");
          const v = ln[c.chave];
          if (c.tipo === "marca") {
            td.textContent = v ? "✓ sim" : "não";
            td.setAttribute("aria-checked", v ? "true" : "false");
          } else {
            td.textContent = v === "?" ? "desconhecido" : (v ?? "");
            if (c.tipo === "moeda" || c.tipo === "numero") td.classList.add("num");
            if (v === "" || v == null) {
              if (c.vazio) { td.classList.add("padrao"); td.setAttribute("aria-label", c.vazio); } // vazio com significado próprio
              else { if (!c.somenteLeitura) td.classList.add("vazio"); td.setAttribute("aria-label", "não informado"); }
            }
            if (v === "?") td.classList.add("desconhecido");
            if (c.tipo === "moeda" && v && v !== "?" && normalizarValor(v) === null) td.classList.add("invalido");
            if (c.tipo === "numero" && v && normalizarNumero(v, c.casas) === null) td.classList.add("invalido");
          }
          if (c.somenteLeitura) td.setAttribute("aria-readonly", "true");
          if (i >= s.l1 && i <= s.l2 && j >= s.c1 && j <= s.c2) { td.classList.add("sel"); td.setAttribute("aria-selected", "true"); }
          if (i === this.ativa.l && j === this.ativa.c) { td.classList.add("ativa"); td.id = this.idAtiva(); }
        });
      });
      t.setAttribute("aria-activedescendant", this.idAtiva());
      t.setAttribute("aria-rowcount", String(this.linhas.length + 1));
    }
    idAtiva() { return (this.raiz.id || "pl") + "-ativa"; }
    celula(l, c) { return this.tabela.querySelector(`td.cel[data-l="${l}"][data-c="${c}"]`); }
    rolarAtiva() { const td = this.celula(this.ativa.l, this.ativa.c); if (td) td.scrollIntoView({ block: "nearest", inline: "nearest" }); }

    mover(dl, dc, estender) {
      if (estender && !this.ancora) this.ancora = { ...this.ativa };
      if (!estender) this.ancora = null;
      this.ativa.l = Math.max(0, Math.min(this.linhas.length - 1, this.ativa.l + dl));
      this.ativa.c = Math.max(0, Math.min(this.colunas.length - 1, this.ativa.c + dc));
      this.desenhar(); this.rolarAtiva();
    }

    mouse(e) {
      const td = e.target.closest("td.cel");
      if (!td) return;
      if (this.editor) this.confirmar();
      const l = +td.dataset.l, c = +td.dataset.c;
      if (e.shiftKey) { if (!this.ancora) this.ancora = { ...this.ativa }; } else this.ancora = { l, c };
      this.ativa = { l, c };
      this.desenhar();
      this.tabela.focus();
      const mover = (ev) => {
        const alvo = document.elementFromPoint(ev.clientX, ev.clientY)?.closest?.("td.cel");
        if (alvo && this.tabela.contains(alvo)) { this.ativa = { l: +alvo.dataset.l, c: +alvo.dataset.c }; this.desenhar(); }
      };
      const soltar = () => { document.removeEventListener("mousemove", mover); document.removeEventListener("mouseup", soltar); };
      document.addEventListener("mousemove", mover); document.addEventListener("mouseup", soltar);
    }

    tecla(e) {
      if (this.editor) return; // o editor trata as próprias teclas
      const k = e.key, ctrl = e.ctrlKey || e.metaKey;
      const col = this.colunas[this.ativa.c];
      if (k === "ArrowDown") { e.preventDefault(); this.mover(1, 0, e.shiftKey); }
      else if (k === "ArrowUp") { e.preventDefault(); this.mover(-1, 0, e.shiftKey); }
      else if (k === "ArrowRight") { e.preventDefault(); this.mover(0, 1, e.shiftKey); }
      else if (k === "ArrowLeft") { e.preventDefault(); this.mover(0, -1, e.shiftKey); }
      else if (k === "Home") { e.preventDefault(); this.ativa.c = 0; if (ctrl) this.ativa.l = 0; this.ancora = null; this.desenhar(); this.rolarAtiva(); }
      else if (k === "End") { e.preventDefault(); this.ativa.c = this.colunas.length - 1; if (ctrl) this.ativa.l = this.linhas.length - 1; this.ancora = null; this.desenhar(); this.rolarAtiva(); }
      else if (k === "PageDown") { e.preventDefault(); this.mover(15, 0, e.shiftKey); }
      else if (k === "PageUp") { e.preventDefault(); this.mover(-15, 0, e.shiftKey); }
      else if (k === "Tab") { if (this.ativa.c < this.colunas.length - 1 && !e.shiftKey || this.ativa.c > 0 && e.shiftKey) { e.preventDefault(); this.mover(0, e.shiftKey ? -1 : 1, false); } }
      else if (k === "Enter" || k === "F2") { e.preventDefault(); if (col.tipo === "marca") this.alternar(); else this.editar(); }
      else if (k === " " && col.tipo === "marca") { e.preventDefault(); this.alternar(); }
      else if (k === "Delete" || k === "Backspace") { e.preventDefault(); this.preencher(""); }
      else if (ctrl && (k === "d" || k === "D")) { e.preventDefault(); this.repetirPrimeira(); }
      else if (ctrl && (k === "a" || k === "A")) { e.preventDefault(); this.ancora = { l: 0, c: 0 }; this.ativa = { l: this.linhas.length - 1, c: this.colunas.length - 1 }; this.desenhar(); }
      else if (!ctrl && !e.altKey && k.length === 1 && col.tipo !== "marca") { e.preventDefault(); this.editar(k); }
    }

    editar(inicial) {
      const col = this.colunas[this.ativa.c];
      if (col.somenteLeitura) return;
      const td = this.celula(this.ativa.l, this.ativa.c);
      const inp = document.createElement("input");
      inp.className = "editor";
      inp.setAttribute("aria-label", `${col.titulo}, linha ${this.rotuloLinha(this.ativa.l, this.linhas[this.ativa.l])}`);
      const atual = this.linhas[this.ativa.l][col.chave];
      inp.value = inicial !== undefined ? inicial : (atual ?? "");
      td.replaceChildren(inp);
      this.editor = inp;
      inp.focus();
      if (inicial === undefined) inp.select();
      inp.addEventListener("keydown", (e) => {
        // as teclas do editor não podem chegar ao manipulador da tabela (reabriria o editor na linha seguinte)
        if (["Enter", "Tab", "Escape", "ArrowDown", "ArrowUp"].includes(e.key)) e.stopPropagation();
        if (e.key === "Enter") { e.preventDefault(); this.confirmar(); this.mover(1, 0, false); this.tabela.focus(); }
        else if (e.key === "Tab") { e.preventDefault(); this.confirmar(); this.mover(0, e.shiftKey ? -1 : 1, false); this.tabela.focus(); }
        else if (e.key === "Escape") { e.preventDefault(); this.editor = null; this.desenhar(); this.tabela.focus(); }
        else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); this.confirmar(); this.mover(e.key === "ArrowDown" ? 1 : -1, 0, false); this.tabela.focus(); }
      });
      inp.addEventListener("blur", () => { if (this.editor === inp) { this.confirmar(); } });
    }

    confirmar() {
      if (!this.editor) return;
      const v = this.editor.value;
      this.editor = null;
      this.gravar([[this.ativa.l, this.ativa.c, v]]);
    }

    converter(col, v) {
      if (col.tipo === "marca") { const b = lerMarcacao(v); return b === null ? undefined : b; }
      if (col.tipo === "moeda") { const n = normalizarValor(v); return n === null ? String(v).trim() : n; }
      if (col.tipo === "numero") { const n = normalizarNumero(v, col.casas); return n === null ? String(v).trim() : n; }
      return String(v).trim();
    }

    gravar(alteracoes) {
      const mudou = [];
      for (const [l, c, v] of alteracoes) {
        const col = this.colunas[c];
        if (!col || col.somenteLeitura || !this.linhas[l]) continue;
        const novo = this.converter(col, v);
        if (novo === undefined) continue;
        if (this.linhas[l][col.chave] !== novo) { this.linhas[l][col.chave] = novo; mudou.push([l, col.chave]); }
      }
      this.desenhar();
      if (mudou.length) this.aoAlterar(mudou);
    }

    preencher(valor) {
      const s = this.selecao(), alt = [];
      for (let l = s.l1; l <= s.l2; l++) for (let c = s.c1; c <= s.c2; c++) alt.push([l, c, this.colunas[c].tipo === "marca" ? (valor ? "s" : "n") : valor]);
      this.gravar(alt);
    }
    alternar() {
      const s = this.selecao(), col = this.colunas[this.ativa.c];
      const novo = !this.linhas[this.ativa.l][col.chave];
      const alt = [];
      for (let l = s.l1; l <= s.l2; l++) for (let c = s.c1; c <= s.c2; c++) if (this.colunas[c].tipo === "marca") alt.push([l, c, novo ? "s" : "n"]);
      this.gravar(alt);
    }
    repetirPrimeira() {
      const s = this.selecao(), alt = [];
      for (let c = s.c1; c <= s.c2; c++) {
        const col = this.colunas[c], v = this.linhas[s.l1][col.chave];
        for (let l = s.l1 + 1; l <= s.l2; l++) alt.push([l, c, col.tipo === "marca" ? (v ? "s" : "n") : v]);
      }
      this.gravar(alt);
    }

    copiar(e) {
      const s = this.selecao(), linhas = [];
      for (let l = s.l1; l <= s.l2; l++) {
        const cel = [];
        for (let c = s.c1; c <= s.c2; c++) { const col = this.colunas[c], v = this.linhas[l][col.chave]; cel.push(col.tipo === "marca" ? (v ? "S" : "N") : (v ?? "")); }
        linhas.push(cel.join("\t"));
      }
      e.clipboardData.setData("text/plain", linhas.join("\r\n"));
      e.preventDefault();
    }

    colar(e) {
      if (this.editor) return;
      const texto = e.clipboardData.getData("text/plain");
      if (!texto) return;
      e.preventDefault();
      const linhas = texto.replace(/\r/g, "").split("\n").filter((x, i, a) => !(i === a.length - 1 && x === ""));
      const alt = [];
      linhas.forEach((ln, i) => ln.split("\t").forEach((v, j) => alt.push([this.ativa.l + i, this.ativa.c + j, v])));
      const fora = alt.filter(([l]) => l >= this.linhas.length).length;
      this.gravar(alt);
      this.raiz.dispatchEvent(new CustomEvent("colado", { detail: { celulas: alt.length, ignoradas: fora } }));
    }
  }

  window.Planilha = Planilha;
  window.normalizarValor = normalizarValor;
  window.lerMarcacao = lerMarcacao;
  window.normalizarNumero = normalizarNumero;
})();
