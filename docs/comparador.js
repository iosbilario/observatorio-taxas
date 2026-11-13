/* comparador.js — Interface do Comparador Selic, CDI e IPCA (/comparador/).
   Cálculo em calculos.js. Tudo o que vem da URL passa por lerParamsComparador
   (lista fechada); o texto é inserido com textContent, nunca como HTML. */
(function () {
  "use strict";
  function pronto(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }
  pronto(function () {
    var C = window.ObsCalc, raiz = document.getElementById("comparador");
    if (!C || !raiz || !window.fetch) return;
    var padrao = JSON.parse(raiz.getAttribute("data-padrao"));
    var CODIGO = { cdi: 4391, selic: 4390, ipca: 433 };
    var NOME = { cdi: "CDI", selic: "Selic", ipca: "IPCA" };
    var COR = { cdi: "#D9B54A", selic: "#E9E6DC", ipca: "#8FB3D9" };
    var $ = function (id) { return document.getElementById(id); };
    var form = $("form-comp"), mapas = {};
    var ultimoComum = [padrao.fechado.cdi, padrao.fechado.selic, padrao.fechado.ipca].sort()[0];

    function el(tag, txt, cls) { var e = document.createElement(tag); if (txt != null) e.textContent = txt; if (cls) e.className = cls; return e; }
    function mesCurto(m) { var n = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]; return n[+m.slice(5) - 1] + "/" + m.slice(0, 4); }
    function mesLongo(m) { var n = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]; return n[+m.slice(5) - 1] + " de " + m.slice(0, 4); }

    function estado() {
      var ind = Array.prototype.filter.call(form.querySelectorAll("input[name=i]"), function (x) { return x.checked; })
        .map(function (x) { return x.value; });
      return { de: $("de").value, ate: $("ate").value, indicadores: ind,
               ver: form.querySelector("input[name=ver]:checked").value };
    }
    function aplicar(p) {
      if (p.meses) { p.ate = ultimoComum; p.de = C.somaMesesMes(ultimoComum, -(p.meses - 1)); }
      if (p.de) $("de").value = p.de;
      if (p.ate) $("ate").value = p.ate;
      if (p.indicadores) Array.prototype.forEach.call(form.querySelectorAll("input[name=i]"), function (x) { x.checked = p.indicadores.indexOf(x.value) >= 0; });
      if (p.ver) form.querySelector("input[name=ver][value=" + p.ver + "]").checked = true;
    }
    function marcarChips(st) {
      var n = C.mesesEntre(st.de, st.ate).length;
      Array.prototype.forEach.call(document.querySelectorAll("[data-meses]"), function (b) {
        b.setAttribute("aria-pressed", String(st.ate === ultimoComum && +b.getAttribute("data-meses") === n));
      });
    }
    function url(st) {
      var q = new URLSearchParams();
      q.set("de", st.de); q.set("ate", st.ate); q.set("i", st.indicadores.join(","));
      if (st.ver === "reais") q.set("ver", "reais");
      return location.pathname + "?" + q.toString();
    }

    function grafico(res, st) {
      var g = $("grafico"), leg = $("legenda");
      g.textContent = ""; leg.textContent = "";
      var W = 720, H = 300, M = { l: 56, r: 16, t: 12, b: 28 };
      var linhas = res.linhas, ks = st.indicadores, base = st.ver === "reais" ? 1000 : null;
      function y(f) { return base ? base * f : (f - 1) * 100; }
      var vals = [base ? base : 0];
      linhas.forEach(function (l) { ks.forEach(function (k) { vals.push(y(l.fatores[k])); }); });
      var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
      if (mx === mn) mx = mn + 1;
      var NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("class", "grafico"); svg.setAttribute("aria-hidden", "true");
      function px(i) { return M.l + (linhas.length < 2 ? 0 : i * (W - M.l - M.r) / (linhas.length - 1)); }
      function py(v) { return M.t + (mx - v) * (H - M.t - M.b) / (mx - mn); }
      function t(x, yy, s, anc) { var e = document.createElementNS(NS, "text"); e.setAttribute("x", x); e.setAttribute("y", yy); e.setAttribute("fill", "rgba(233,230,220,.55)"); e.setAttribute("font-size", "11"); e.setAttribute("font-family", "IBM Plex Mono, monospace"); if (anc) e.setAttribute("text-anchor", anc); e.textContent = s; svg.appendChild(e); }
      [mn, (mn + mx) / 2, mx].forEach(function (v) {
        var ln = document.createElementNS(NS, "line");
        ln.setAttribute("x1", M.l); ln.setAttribute("x2", W - M.r); ln.setAttribute("y1", py(v)); ln.setAttribute("y2", py(v));
        ln.setAttribute("stroke", "rgba(233,230,220,.14)"); svg.appendChild(ln);
        t(M.l - 6, py(v) + 4, base ? "R$ " + C.br(v, 0) : C.br(v, 1) + "%", "end");
      });
      t(M.l, H - 8, mesCurto(linhas[0].mes)); t(W - M.r, H - 8, mesCurto(linhas[linhas.length - 1].mes), "end");
      ks.forEach(function (k) {
        var d = linhas.map(function (l, i) { return (i ? "L" : "M") + px(i).toFixed(1) + " " + py(y(l.fatores[k])).toFixed(1); }).join(" ");
        var p = document.createElementNS(NS, "path");
        p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", COR[k]); p.setAttribute("stroke-width", "2.2");
        if (k === "ipca") p.setAttribute("stroke-dasharray", "6 4");
        svg.appendChild(p);
        var item = el("span"); var i = el("i"); i.style.borderTopColor = COR[k]; if (k === "ipca") i.style.borderTopStyle = "dashed";
        item.appendChild(i); item.appendChild(document.createTextNode(NOME[k] + (k === "ipca" ? " (preços)" : "")));
        leg.appendChild(item);
      });
      g.appendChild(svg);
      var ult = linhas[linhas.length - 1];
      g.setAttribute("aria-label", "Acumulado de " + mesCurto(linhas[0].mes) + " a " + mesCurto(ult.mes) + ": " +
        ks.map(function (k) { return NOME[k] + " " + C.br((ult.fatores[k] - 1) * 100, 2) + "%"; }).join(", ") + ". Valores mês a mês na tabela.");
    }

    function tabela(res, st) {
      var tb = $("tabela"), ks = st.indicadores, reais = st.ver === "reais";
      var thead = tb.querySelector("thead"), tbody = tb.querySelector("tbody");
      thead.textContent = ""; tbody.textContent = "";
      var tr = el("tr"); tr.appendChild(el("th", "Mês"));
      ks.forEach(function (k) { tr.appendChild(el("th", NOME[k])); });
      ks.forEach(function (k) { tr.appendChild(el("th", reais ? NOME[k] + " (R$ 1.000)" : "Fator " + NOME[k])); });
      Array.prototype.forEach.call(tr.children, function (th) { th.setAttribute("scope", "col"); });
      thead.appendChild(tr);
      res.linhas.forEach(function (l) {
        var r = el("tr"); r.appendChild(el("td", mesCurto(l.mes)));
        ks.forEach(function (k) { r.appendChild(el("td", C.br(l.taxas[k], 2) + "%", "num")); });
        ks.forEach(function (k) { r.appendChild(el("td", reais ? "R$ " + C.br(1000 * l.fatores[k], 2) : C.br(l.fatores[k], 6), "num")); });
        tbody.appendChild(r);
      });
    }

    function frase(res, st) {
      var p = $("resultado"); p.textContent = "";
      var n = res.meses;
      p.appendChild(document.createTextNode("De " + mesLongo(st.de) + " a " + mesLongo(st.ate) + " (" + n + (n === 1 ? " mês" : " meses") + "), "));
      st.indicadores.forEach(function (k, i) {
        if (i) p.appendChild(document.createTextNode(i === st.indicadores.length - 1 ? " e " : ", "));
        p.appendChild(document.createTextNode((k === "ipca" ? "o IPCA" : k === "cdi" ? "o CDI" : "a Selic") + " acumulou "));
        p.appendChild(el("b", C.br(res.resultado[k].pct, 2) + "%"));
        if (st.ver === "reais") p.appendChild(document.createTextNode(" (R$ 1.000 → R$ " + C.br(1000 * res.resultado[k].fator, 2) + ")"));
      });
      p.appendChild(document.createTextNode("."));
      if (res.resultado.cdi && res.resultado.ipca) {
        var real = C.rentabilidadeReal(res.resultado.cdi.pct, res.resultado.ipca.pct);
        p.appendChild(document.createTextNode(" Descontada a inflação, o CDI variou " + C.br(real, 2) + "% no período."));
      }
    }

    function render() {
      var st = estado();
      if (!st.indicadores.length) { $("resultado").textContent = "Escolha ao menos um indicador."; return; }
      if (st.ate > ultimoComum) { st.ate = ultimoComum; $("ate").value = ultimoComum; }
      var m = {}; st.indicadores.forEach(function (k) { m[k] = mapas[k]; });
      var res = C.comparar(m, st.de, st.ate);
      if (res.erro) { $("resultado").textContent = res.erro; $("resultado").className = "resultado erro"; return; }
      $("resultado").className = "resultado";
      frase(res, st); grafico(res, st); tabela(res, st); marcarChips(st);
      history.replaceState(null, "", url(st));
    }

    Promise.all(["cdi", "selic", "ipca"].map(function (k) {
      return fetch("/data/" + CODIGO[k] + "_history.json").then(function (r) { if (!r.ok) throw new Error(k); return r.json(); })
        .then(function (j) { mapas[k] = C.porMes(C.historico(j)); });
    })).then(function () {
      ["cdi", "selic"].forEach(function (k) { Object.keys(mapas[k]).forEach(function (m) { if (m > padrao.fechado[k]) delete mapas[k][m]; }); });
      $("de").max = ultimoComum; $("ate").max = ultimoComum;
      aplicar(C.lerParamsComparador(new URLSearchParams(location.search)));
      form.addEventListener("change", render);
      form.addEventListener("submit", function (ev) { ev.preventDefault(); render(); });
      Array.prototype.forEach.call(document.querySelectorAll("[data-meses]"), function (b) {
        b.addEventListener("click", function () { aplicar({ meses: +b.getAttribute("data-meses") }); render(); });
      });
      $("copiar").addEventListener("click", function () {
        var u = location.origin + url(estado());
        (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function () { $("copiar").textContent = "Link copiado"; },
          function () { window.prompt("Copie o link:", u); });
      });
      render();
    }).catch(function () { $("resultado").textContent = "Não foi possível carregar as séries agora. Os números de exemplo seguem na tabela."; });
  });
})();
