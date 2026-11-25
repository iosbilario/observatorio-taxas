/* mudancas.js — Última verificação na página /mudancas/.

   A página é estática e completa sem este script. Ele só acrescenta a hora da
   última execução bem-sucedida do monitor (GitHub Actions, API pública, um
   pedido por visita) para separar "última verificação" de "última mudança":
   uma coleta sem dado novo não publica nada, então só a API sabe que ela rodou.
   Se a API não responder (limite de 60 pedidos por hora por IP, rede), a
   frase fixa do HTML continua. */
(function () {
  "use strict";
  var el = document.querySelector("[data-verificacao]");
  if (!el || !window.fetch) return;
  var repo = el.getAttribute("data-repo");
  var publicado = el.getAttribute("data-publicado");
  var fmt = function (d) {
    return d.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit",
      year: "numeric", hour: "2-digit", minute: "2-digit" }).replace(",", " às") + " (horário de Brasília)";
  };
  fetch("https://api.github.com/repos/" + repo + "/actions/workflows/monitor.yml/runs?status=success&per_page=1",
        { headers: { Accept: "application/vnd.github+json" } })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (j) {
      var run = j.workflow_runs && j.workflow_runs[0];
      if (!run) return;
      var ini = new Date(run.run_started_at || run.created_at), fim = new Date(run.updated_at);
      var txt = "<b>Última verificação:</b> " + fmt(fim) + ", pela coleta automática no GitHub Actions. ";
      if (publicado) {
        var pub = new Date(publicado);
        txt += pub >= ini && pub <= fim
          ? "Foi essa coleta que publicou as mudanças desta página."
          : pub > fim
            ? "A publicação abaixo é mais recente que essa verificação."
            : "Ela não encontrou dado novo: as mudanças abaixo continuam sendo as da última publicação.";
      }
      el.innerHTML = txt;
    })
    .catch(function () { /* fica a frase fixa do HTML */ });
})();
