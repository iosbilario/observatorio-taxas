// Alternância claro/escuro: respeita o sistema na primeira visita e lembra a escolha.
(function () {
  var raiz = document.documentElement;
  var claro = raiz.getAttribute("data-claro") || "light";
  var salvo = null;
  try { salvo = localStorage.getItem("tema"); } catch (e) {}
  var escuro = salvo ? salvo === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  raiz.setAttribute("data-theme", escuro ? "dark" : claro);
  document.addEventListener("DOMContentLoaded", function () {
    var b = document.querySelector(".tema");
    if (!b) return;
    function rotulo() {
      var e = raiz.getAttribute("data-theme") === "dark";
      b.setAttribute("aria-label", e ? "Mudar para o modo claro" : "Mudar para o modo escuro");
      b.innerHTML = e
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
    }
    rotulo();
    b.addEventListener("click", function () {
      var e = raiz.getAttribute("data-theme") === "dark";
      raiz.setAttribute("data-theme", e ? claro : "dark");
      try { localStorage.setItem("tema", e ? "light" : "dark"); } catch (x) {}
      rotulo();
    });
  });
})();
