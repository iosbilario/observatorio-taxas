/* catalogo.js — "Indicadores por tema" na página inicial.

   O HTML (scripts/catalogo_home.py) já traz todos os temas e todas as fichas:
   sem JavaScript, a lista de temas é de âncoras e os painéis ficam um embaixo
   do outro. Este script só melhora a escolha, sem recarregar:

   - desktop (≥ 760 px): abas (padrão ARIA tabs, ativação automática). Setas,
     Home e End movem o foco e escolhem o tema; o foco fica na aba.
   - celular: seções expansíveis (botão com aria-expanded logo acima do
     conteúdo, que aparece embaixo dele).

   Endereço: #catalogo-<tema> (ex.: /#catalogo-cambio) abre o tema e leva ao
   catálogo. Cada troca feita pela pessoa cria uma entrada no histórico
   (history.pushState); Voltar e Avançar restauram o tema daquela entrada sem
   rolar a página, e voltar até a entrada sem fragmento restaura o tema
   inicial. Outros fragmentos da página (#selic etc.) não são tocados. */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-catalogo]");
  if (!raiz) return;
  var abasEl = Array.prototype.slice.call(raiz.querySelectorAll(".cat-tema"));
  var paineis = Array.prototype.slice.call(raiz.querySelectorAll(".cat-painel"));
  var ids = paineis.map(function (p) { return p.getAttribute("data-tema"); });
  var largo = window.matchMedia("(min-width: 760px)");
  var ativo = raiz.getAttribute("data-inicial");
  if (ids.indexOf(ativo) < 0) ativo = ids[0];
  var botoes = [];

  function temaDoHash() {
    var m = /^#catalogo-([a-z0-9-]+)$/.exec(location.hash);
    return m && ids.indexOf(m[1]) >= 0 ? m[1] : null;
  }

  // Cabeçalho de cada painel vira botão (usado no modo celular).
  paineis.forEach(function (p) {
    var h = p.querySelector(".cat-painel-cab"), corpo = p.querySelector(".cat-corpo");
    var b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-controls", corpo.id);
    while (h.firstChild) b.appendChild(h.firstChild);
    h.appendChild(b);
    b.addEventListener("click", function () {
      var abrir = b.getAttribute("aria-expanded") !== "true";
      definirSanfona(p.getAttribute("data-tema"), abrir);
      if (abrir) marcarHash(p.getAttribute("data-tema"));
      else desmarcarHash(p.getAttribute("data-tema"));
    });
    botoes.push(b);
  });

  function marcarHash(id) {
    var h = "#catalogo-" + id;
    if (location.hash !== h && history.pushState) history.pushState({ catalogo: id }, "", h);
  }

  // Fechar o tema que está no endereço tira o fragmento, também com uma entrada
  // no histórico: ao recarregar, a página não reabre o tema que a pessoa fechou,
  // e Voltar reabre esse tema.
  function desmarcarHash(id) {
    if (location.hash === "#catalogo-" + id && history.pushState)
      history.pushState({ catalogo: null }, "", location.pathname + location.search);
  }

  function definirSanfona(id, abrir) {
    paineis.forEach(function (p, i) {
      if (p.getAttribute("data-tema") !== id) return;
      botoes[i].setAttribute("aria-expanded", abrir ? "true" : "false");
      p.querySelector(".cat-corpo").hidden = !abrir;
    });
    if (abrir) ativo = id;
    else if (ativo === id) ativo = null;
  }

  function selecionar(id, focar) {
    ativo = id;
    abasEl.forEach(function (a) {
      var sim = a.getAttribute("data-tema") === id;
      a.setAttribute("aria-selected", sim ? "true" : "false");
      a.tabIndex = sim ? 0 : -1;
      if (sim && focar) a.focus();
    });
    paineis.forEach(function (p) { p.hidden = p.getAttribute("data-tema") !== id; });
  }

  function modoAbas() {
    raiz.classList.add("abas"); raiz.classList.remove("sanfona");
    var lista = raiz.querySelector(".cat-temas");
    lista.setAttribute("role", "tablist");
    lista.setAttribute("aria-label", "Temas");
    Array.prototype.forEach.call(lista.children, function (li) { li.setAttribute("role", "presentation"); });
    abasEl.forEach(function (a) {
      var id = a.getAttribute("data-tema");
      a.setAttribute("role", "tab");
      a.id = "catalogo-aba-" + id;
      a.setAttribute("aria-controls", "catalogo-" + id);
    });
    paineis.forEach(function (p) {
      p.setAttribute("role", "tabpanel");
      p.setAttribute("aria-labelledby", "catalogo-aba-" + p.getAttribute("data-tema"));
      p.tabIndex = -1;
      p.querySelector(".cat-corpo").hidden = false;
    });
    selecionar(ativo || raiz.getAttribute("data-inicial") || ids[0], false);
  }

  function modoSanfona() {
    raiz.classList.add("sanfona"); raiz.classList.remove("abas");
    var lista = raiz.querySelector(".cat-temas");
    lista.removeAttribute("role");
    abasEl.forEach(function (a) { a.removeAttribute("role"); a.removeAttribute("aria-selected"); a.removeAttribute("tabindex"); });
    paineis.forEach(function (p, i) {
      p.hidden = false;
      p.removeAttribute("role");
      p.removeAttribute("tabindex");
      p.setAttribute("aria-labelledby", p.querySelector(".cat-painel-cab").id);
      var abrir = p.getAttribute("data-tema") === ativo;
      botoes[i].setAttribute("aria-expanded", abrir ? "true" : "false");
      p.querySelector(".cat-corpo").hidden = !abrir;
    });
  }

  function aplicarModo() { if (largo.matches) modoAbas(); else modoSanfona(); }

  abasEl.forEach(function (a, i) {
    a.addEventListener("click", function (ev) {
      if (!raiz.classList.contains("abas")) return;
      ev.preventDefault();
      selecionar(a.getAttribute("data-tema"), true);
      marcarHash(a.getAttribute("data-tema"));
    });
    a.addEventListener("keydown", function (ev) {
      if (!raiz.classList.contains("abas")) return;
      var n = abasEl.length, j = null;
      if (ev.key === "ArrowDown" || ev.key === "ArrowRight") j = (i + 1) % n;
      else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") j = (i - 1 + n) % n;
      else if (ev.key === "Home") j = 0;
      else if (ev.key === "End") j = n - 1;
      else if (ev.key === " ") j = i;
      if (j === null) return;
      ev.preventDefault();
      var id = abasEl[j].getAttribute("data-tema");
      selecionar(id, true);
      marcarHash(id);
    });
  });

  function irParaHash(rolar) {
    // Entrada criada ao fechar um tema no celular: tudo fechado.
    if (!location.hash && history.state && history.state.catalogo === null && !raiz.classList.contains("abas")) {
      ativo = null; modoSanfona(); return;
    }
    var id = temaDoHash();
    if (!id && !location.hash) id = raiz.getAttribute("data-inicial");   // de volta à entrada sem fragmento
    if (!id || ids.indexOf(id) < 0) return;
    if (raiz.classList.contains("abas")) selecionar(id, false);
    else { ativo = id; modoSanfona(); }
    if (!rolar) return;
    // Depois do salto nativo do navegador para o painel: no desktop, mostra a
    // seção inteira (título e temas); no celular, o tema aberto.
    setTimeout(function () {
      var alvo = raiz.classList.contains("abas") ? (document.getElementById("catalogo") || raiz)
                                                 : document.getElementById("catalogo-" + id);
      alvo.scrollIntoView();
    }, 0);
  }

  var inicial = temaDoHash();
  if (inicial) ativo = inicial;
  aplicarModo();
  if (inicial) irParaHash(true);
  // Voltar/Avançar: popstate restaura sem rolar. Um hashchange que não veio do
  // histórico (link para #catalogo-<tema>) escolhe o tema e rola até ele.
  var doHistorico = false;
  window.addEventListener("popstate", function () { doHistorico = true; irParaHash(false); setTimeout(function () { doHistorico = false; }, 0); });
  window.addEventListener("hashchange", function () { if (!doHistorico) irParaHash(true); });
  if (largo.addEventListener) largo.addEventListener("change", aplicarModo);
  else if (largo.addListener) largo.addListener(aplicarModo);
})();
