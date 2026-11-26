/* 404.js — Endereço inexistente. Se for de uma análise citada (/divulgacoes/…),
   diz que aquela versão não está disponível e dá um link SEPARADO para a visão
   atual do indicador. Nunca redireciona sozinho para outra versão.
   Sem JavaScript, a página já lista as visões atuais. */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.Obs404 = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var FICHAS = { ipca: ["IPCA", "/indicadores/ipca/#leitura"], cdi: ["CDI", "/indicadores/cdi/#leitura"],
                 dolar: ["dólar PTAX", "/indicadores/dolar/#leitura"] };

  function alvo(caminho) {
    var m = /^\/divulgacoes\/([a-z]+)\/([^/]+)\//.exec(caminho || "");
    if (!m) return null;
    var f = FICHAS[m[1]];
    return { serie: m[1], periodo: m[2], nome: f ? f[0] : null, atual: f ? f[1] : "/divulgacoes/" };
  }

  if (typeof document !== "undefined") {
    var a = alvo(location.pathname), el = document.getElementById("versao-indisponivel");
    if (a && el) {
      el.hidden = false;
      el.querySelector("[data-periodo]").textContent = a.periodo;
      var link = el.querySelector("[data-atual]");
      link.href = a.atual;
      link.textContent = a.nome ? "Ver a leitura atual do " + a.nome : "Ver as divulgações disponíveis";
    }
  }
  return { alvo: alvo };
});
