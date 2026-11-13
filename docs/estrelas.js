/* Contador de estrelas do repositório no header (partials/nav.html).

   Lê data/github.json, que o robô (scripts/fetch_github.py, no monitor.yml)
   grava a partir da API do GitHub. O navegador do visitante só fala com este
   site: nenhuma requisição vai para o GitHub, então a CSP (connect-src 'self')
   e a política de privacidade não mudam. Sem JavaScript, o link aparece sem o
   número. */
(function () {
  var script = document.currentScript;
  var src = script && script.src;
  function iniciar() {
  var alvo = document.querySelector("[data-estrelas]");
  if (!alvo || !src || !window.fetch) return;
  fetch(new URL("data/github.json", src), { cache: "no-cache" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (!d || typeof d.estrelas !== "number" || d.estrelas < 0) return;
      var n = d.estrelas;
      alvo.textContent = n.toLocaleString("pt-BR");
      alvo.hidden = false;
      var link = alvo.closest("a");
      if (link) link.setAttribute("aria-label",
        "Código no GitHub, " + n + (n === 1 ? " estrela" : " estrelas"));
    })
    .catch(function () {});
  }
  // Com anúncios ligados, adsense.py carrega este arquivo dinamicamente no
  // <head>, antes de o corpo existir: espera o DOM nesse caso.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
