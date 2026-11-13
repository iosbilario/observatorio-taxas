/* simulador-cdi.js — Interface do Simulador de rendimento do CDI (/simulador-cdi/).
   Cálculo em calculos.js. Parâmetros de URL validados por lerParamsSimulador;
   texto inserido com textContent. */
(function () {
  "use strict";
  function pronto(fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); }
  pronto(function () {
    var C = window.ObsCalc, raiz = document.getElementById("simulador");
    if (!C || !raiz || !window.fetch) return;
    var $ = function (id) { return document.getElementById(id); };
    var form = $("form-sim"), diario = [], ipca = {}, ultimo = null, atual = null;

    function el(tag, txt, cls) { var e = document.createElement(tag); if (txt != null) e.textContent = txt; if (cls) e.className = cls; return e; }
    function dbr(s) { return s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4); }
    function mesCurto(m) { var n = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]; return n[+m.slice(5) - 1] + "/" + m.slice(0, 4); }
    function num(s) {
      s = String(s || "").trim().replace(/^R\$\s*/, "");
      if (!/^\d{1,3}(\.\d{3})*(,\d{1,2})?$|^\d+([.,]\d{1,2})?$/.test(s)) return NaN;
      if (/,/.test(s)) s = s.replace(/\./g, "").replace(",", ".");
      else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
      return parseFloat(s);
    }
    function reais(x) { return "R$ " + C.br(x, 2); }

    function estado() {
      return { valor: num($("valor").value), percentual: num($("percentual").value), de: $("de").value, ate: $("ate").value,
               modo: form.querySelector("input[name=modo]:checked").value };
    }
    function aplicar(p) {
      if (p.valor) $("valor").value = C.br(p.valor, 2);
      if (p.percentual) $("percentual").value = C.br(p.percentual, p.percentual % 1 ? 2 : 0);
      if (p.periodo && ultimo) { var d = C.periodoParaDatas(p.periodo, ultimo); $("de").value = d.inicio; $("ate").value = d.fim; }
      if (p.de) { $("de").value = p.de; $("ate").value = p.ate; }
      if (p.modo) form.querySelector("input[name=modo][value=" + p.modo + "]").checked = true;
    }
    function periodoAtual(st) {
      var ks = Object.keys(C.PERIODOS);
      for (var i = 0; i < ks.length; i++) { var d = C.periodoParaDatas(ks[i], ultimo); if (d.inicio === st.de && d.fim === st.ate) return ks[i]; }
      return null;
    }
    function chips(st) {
      var per = periodoAtual(st);
      [["data-valor", st.valor], ["data-percentual", st.percentual], ["data-periodo", per]].forEach(function (par) {
        Array.prototype.forEach.call(document.querySelectorAll("[" + par[0] + "]"), function (b) {
          var v = b.getAttribute(par[0]); b.setAttribute("aria-pressed", String(par[0] === "data-periodo" ? v === par[1] : +v === par[1]));
        });
      });
      return per;
    }
    function url(st, per) {
      var q = new URLSearchParams();
      q.set("valor", String(st.valor)); q.set("percentual", String(st.percentual));
      if (per) q.set("periodo", per); else { q.set("de", st.de); q.set("ate", st.ate); }
      if (st.modo === "bruto") q.set("modo", "bruto");
      return location.pathname + "?" + q.toString();
    }
    function linha(dl, rot, val, cls) { dl.appendChild(el("dt", rot)); dl.appendChild(el("dd", val, cls)); }

    function render() {
      var st = estado(), box = $("resultado");
      box.textContent = "";
      var r = C.simularCDI(diario, st.de, st.ate, st.percentual, st.valor);
      if (isNaN(st.valor)) r = { erro: "Informe o valor inicial, por exemplo 1.000,00." };
      else if (isNaN(st.percentual)) r = { erro: "Informe o percentual do CDI, por exemplo 110." };
      if (r.erro) { box.appendChild(el("p", r.erro, "resultado erro")); $("memoria").textContent = ""; atual = null; return; }
      atual = r;
      var tr = st.modo === "liquido" ? C.tributosCDB(r.rendimentoBruto, r.diasCorridos) : null;
      var final = r.valorBruto - (tr ? tr.total : 0);
      var liquido = final - st.valor;
      var p = el("p", null, "resultado");
      p.appendChild(document.createTextNode(reais(st.valor) + " a " + C.br(st.percentual, st.percentual % 1 ? 2 : 0) + "% do CDI, de " + dbr(r.inicio) + " a " + dbr(r.fim) + ": "));
      p.appendChild(el("b", reais(final)));
      p.appendChild(document.createTextNode(tr ? " líquidos num CDB." : " brutos."));
      box.appendChild(p);
      var dl = el("dl", null, "ficha");
      linha(dl, "Valor aplicado", reais(st.valor));
      linha(dl, "Período", dbr(r.inicio) + " a " + dbr(r.fim) + " (" + r.diasCorridos + " dias corridos, " + r.diasUteis + " dias úteis com taxa DI)");
      linha(dl, "CDI acumulado", C.br(r.cdiAcumuladoPct, 4) + "%");
      linha(dl, "Percentual contratado", C.br(st.percentual, 2) + "% do CDI");
      linha(dl, "Rendimento bruto", reais(r.rendimentoBruto) + " (" + C.br(r.rentabilidadeBrutaPct, 4) + "%)");
      if (tr) {
        linha(dl, "IOF", reais(tr.iof) + " (" + C.br(tr.aliquotaIOF, 0) + "% do rendimento)");
        linha(dl, "IR", reais(tr.ir) + " (" + C.br(tr.aliquotaIR, 1) + "% do rendimento menos IOF)");
        linha(dl, "Rendimento líquido estimado", reais(liquido));
      } else {
        linha(dl, "Tributos", "não calculados no modo bruto");
      }
      linha(dl, "Valor final", reais(final));
      var nominal = (final / st.valor - 1) * 100;
      linha(dl, "Rentabilidade nominal", C.br(nominal, 4) + "%" + (tr ? " (líquida)" : " (bruta)"));
      var inf = C.inflacaoPeriodo(ipca, r.inicio, r.fim);
      if (inf.erro) {
        linha(dl, "Inflação (IPCA)", "não calculada: " + inf.erro);
      } else {
        linha(dl, "Inflação (IPCA)", C.br(inf.pct, 2) + "% (" + mesCurto(inf.de) + " a " + mesCurto(inf.ate) + ", aproximação por meses inteiros)");
        var real = C.rentabilidadeReal(nominal, inf.pct);
        linha(dl, "Rentabilidade real", C.br(real, 2) + "%", real >= 0 ? "alta" : "queda");
        linha(dl, "Poder de compra aproximado", reais(final / inf.fator) + " em valores do início do período");
      }
      box.appendChild(dl);
      if (r.fim > ultimo) box.appendChild(el("p", "O período vai até a última taxa DI publicada, de " + dbr(ultimo) + ".", "aviso"));
      memoria(r);
      history.replaceState(null, "", url(st, chips(st)));
    }

    function memoria(r) {
      var m = $("memoria"); m.textContent = "";
      $("mem-resumo").textContent = r.linhas.length + " dias úteis. Primeiros e últimos 10 abaixo; o CSV traz todos.";
      var t = el("table"), th = el("thead"), tr = el("tr");
      ["Data", "Taxa DI (% a.a.)", "% do CDI", "Fator do dia", "Saldo anterior", "Rendimento", "Saldo"].forEach(function (c) { var h = el("th", c); h.setAttribute("scope", "col"); tr.appendChild(h); });
      th.appendChild(tr); t.appendChild(th);
      var tb = el("tbody"), ls = r.linhas, mostrar = ls.length <= 20 ? ls : ls.slice(0, 10).concat([null]).concat(ls.slice(-10));
      mostrar.forEach(function (l) {
        var row = el("tr");
        if (!l) { var c = el("td", "… " + (ls.length - 20) + " dias no CSV …", "aviso"); c.colSpan = 7; row.appendChild(c); tb.appendChild(row); return; }
        [dbr(l.data), C.br(l.taxa, 2), C.br(r.percentual, 2) + "%", C.br(l.fator, 10), C.br(l.saldoAnterior, 2), C.br(l.rendimento, 2), C.br(l.saldo, 2)]
          .forEach(function (v, i) { row.appendChild(el("td", v, i ? "num" : null)); });
        tb.appendChild(row);
      });
      t.appendChild(tb); m.appendChild(t);
    }

    Promise.all([
      fetch("/data/4389_history.json").then(function (r) { if (!r.ok) throw new Error("cdi"); return r.json(); }),
      fetch("/data/433_history.json").then(function (r) { if (!r.ok) throw new Error("ipca"); return r.json(); }),
    ]).then(function (js) {
      diario = C.historico(js[0]); ipca = C.porMes(C.historico(js[1]));
      ultimo = diario[diario.length - 1].d;
      $("de").max = ultimo; $("ate").max = C.somaDias(ultimo, 1);
      aplicar(C.lerParamsSimulador(new URLSearchParams(location.search)));
      form.addEventListener("change", render);
      form.addEventListener("submit", function (ev) { ev.preventDefault(); render(); });
      ["valor", "percentual"].forEach(function (k) {
        Array.prototype.forEach.call(document.querySelectorAll("[data-" + k + "]"), function (b) {
          b.addEventListener("click", function () { var o = {}; o[k] = +b.getAttribute("data-" + k); aplicar(o); render(); });
        });
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-periodo]"), function (b) {
        b.addEventListener("click", function () { aplicar({ periodo: b.getAttribute("data-periodo") }); render(); });
      });
      $("copiar").addEventListener("click", function () {
        var st = estado(), u = location.origin + url(st, periodoAtual(st));
        (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function () { $("copiar").textContent = "Link copiado"; },
          function () { window.prompt("Copie o link:", u); });
      });
      $("csv").addEventListener("click", function () {
        if (!atual) return;
        var blob = new Blob([C.csvSimulacao(atual)], { type: "text/csv;charset=utf-8" });
        var a = document.createElement("a"); a.href = URL.createObjectURL(blob);
        a.download = "simulacao-cdi-" + atual.inicio + "-a-" + atual.fim + ".csv";
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
      });
      render();
    }).catch(function () { $("resultado").appendChild(el("p", "Não foi possível carregar a série do CDI agora. O exemplo acima segue válido.", "aviso")); });
  });
})();
