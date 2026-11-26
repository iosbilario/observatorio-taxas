/* sobre.js — Botões "Copiar referência" da página Sobre.
   Sem JavaScript os botões ficam escondidos e as referências continuam
   na página como texto selecionável. Se o navegador recusar a cópia,
   o texto da referência fica selecionado para Ctrl+C ou ⌘+C, no mesmo
   padrão do demonstrativo. */
(function () {
  "use strict";
  function seleciona(el) {
    var r = document.createRange();
    r.selectNodeContents(el);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }
  function copiar(botao) {
    var alvo = document.getElementById(botao.getAttribute("data-copiar"));
    var status = botao.nextElementSibling;
    if (!alvo) return;
    var txt = alvo.textContent.replace(/\s+/g, " ").trim();
    var feito = false;
    function ok() {
      if (feito) return; feito = true;
      status.textContent = "Referência copiada.";
      botao.textContent = "Copiado ✓";
      setTimeout(function () { botao.textContent = "Copiar referência"; }, 2500);
    }
    function manual() {
      if (feito) return; feito = true;
      seleciona(alvo);
      status.textContent = "Não deu para copiar automaticamente. O texto está selecionado: copie com Ctrl+C ou ⌘+C.";
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(ok, manual);
        setTimeout(manual, 1500);
      } else manual();
    } catch (e) { manual(); }
  }
  document.querySelectorAll("[data-copiar]").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () { copiar(b); });
  });
})();
