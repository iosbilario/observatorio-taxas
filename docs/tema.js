// tema.js — Modo claro e escuro do site (ver tema.css).
// Carregado no <head>, sem defer, para aplicar a escolha salva antes da
// primeira pintura. O <html> já vem com data-theme="light"; aqui só se
// troca para "dark" se a pessoa escolheu. Depois, mostra e liga o botão
// de tema do header (que nasce `hidden` no partials/nav.html).
(function () {
  "use strict";
  var raiz = document.documentElement;
  var salvo = null;
  try { salvo = localStorage.getItem("tema"); } catch (e) { /* modo privado */ }
  if (salvo === "dark" || salvo === "light") raiz.setAttribute("data-theme", salvo);

  document.addEventListener("DOMContentLoaded", function () {
    var botao = document.querySelector("[data-tema-botao]");
    if (!botao) return;
    function rotulo() {
      var escuro = raiz.getAttribute("data-theme") === "dark";
      botao.setAttribute("aria-label", escuro ? "Mudar para o modo claro" : "Mudar para o modo escuro");
      botao.setAttribute("aria-pressed", String(escuro));
    }
    botao.hidden = false;
    rotulo();
    botao.addEventListener("click", function () {
      var escuro = raiz.getAttribute("data-theme") !== "dark";
      raiz.setAttribute("data-theme", escuro ? "dark" : "light");
      try { localStorage.setItem("tema", escuro ? "dark" : "light"); } catch (e) { /* modo privado */ }
      rotulo();
      document.dispatchEvent(new Event("tema"));
    });
  });
})();
