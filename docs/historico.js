/* historico.js — "Consultar versão histórica": o que o Observatório tinha
   registrado de uma série até o fim de um dia (horário de Brasília).

   Índice: /data/versoes/<codigo>.json (scripts/versoes_series.py), com os
   commits da main que mudaram data/<codigo>_history.json e a data de cada um.
   A consulta baixa só o índice da série, o arquivo dela no commit escolhido
   (raw.githubusercontent.com) e a versão atual (/data/<codigo>_history.json).
   Se a versão antiga não carregar, a página diz isso e não troca pela atual.

   Funções puras exportadas para os testes (node). */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.ObsHist = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var REPO = "iosbilario/observatorio-taxas";
  var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
               "outubro", "novembro", "dezembro"];

  // Fim do dia `dataISO` (aaaa-mm-dd) em Brasília (UTC−3, sem horário de verão desde 2019), em ms UTC.
  function corte(dataISO) {
    var p = dataISO.split("-").map(Number);
    return Date.UTC(p[0], p[1] - 1, p[2], 23, 59, 59, 999) + 3 * 3600 * 1000;
  }

  // Última versão registrada até o corte. Antes da primeira: {versao: null, primeira}.
  function escolher(versoes, dataISO) {
    var c = corte(dataISO), achada = null;
    for (var i = 0; i < versoes.length; i++) {
      if (Date.parse(versoes[i].registrado_em) <= c) achada = versoes[i];
    }
    return { versao: achada, primeira: versoes[0] || null, antesDaCobertura: !achada };
  }

  function chave(d) { var p = d.split("/"); return p[2] + "-" + p[1] + "-" + p[0]; }

  // Compara pela data de referência de cada observação.
  function comparar(antigo, atual) {
    var a = {}, b = {}, todas = {};
    antigo.forEach(function (o) { a[o.data] = String(o.valor); todas[o.data] = 1; });
    atual.forEach(function (o) { b[o.data] = String(o.valor); todas[o.data] = 1; });
    return Object.keys(todas).sort(function (x, y) { return chave(x) < chave(y) ? -1 : 1; }).map(function (d) {
      var s = !(d in a) ? "entrou_depois" : !(d in b) ? "deixou" : Number(a[d]) === Number(b[d]) ? "igual" : "alterado";
      return { data: d, antes: d in a ? Number(a[d]) : null, agora: d in b ? Number(b[d]) : null, situacao: s };
    });
  }

  function resumo(linhas) {
    var r = { igual: 0, alterado: 0, entrou_depois: 0, deixou: 0 };
    linhas.forEach(function (l) { r[l.situacao]++; });
    return r;
  }

  function urlRaw(sha, arquivo) { return "https://raw.githubusercontent.com/" + REPO + "/" + sha + "/" + arquivo; }

  // ------------------------------------------------------------------ DOM
  var SIT = { igual: "igual", alterado: "alterado depois", entrou_depois: "entrou depois", deixou: "deixou de constar" };

  function br(x, casas) {
    return x.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  }
  function quando(iso) {
    return new Date(iso).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit",
      year: "numeric", hour: "2-digit", minute: "2-digit" }).replace(",", " às");
  }
  function iniciar() {
    var form = document.getElementById("hist-form");
    if (!form) return;
    var out = document.getElementById("hist-res"), sel = form.elements.serie, inp = form.elements.data;
    var q = new URLSearchParams(location.search);
    if (q.get("serie")) sel.value = q.get("serie");
    if (/^\d{4}-\d{2}-\d{2}$/.test(q.get("data") || "")) inp.value = q.get("data");

    function lerJson(u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }); }
    function el(t, txt, cls) { var e = document.createElement(t); if (txt != null) e.textContent = txt; if (cls) e.className = cls; return e; }

    function consultar(empurrar) {
      var cod = sel.value, dia = inp.value;
      if (!cod || !/^\d{4}-\d{2}-\d{2}$/.test(dia)) { out.textContent = "Escolha a série e a data."; return; }
      var url = location.pathname + "?serie=" + encodeURIComponent(cod) + "&data=" + dia;
      if (empurrar) history.pushState(null, "", url);
      out.textContent = "Consultando…";
      lerJson("../data/versoes/" + cod + ".json").then(function (idx) {
        var esc = escolher(idx.versoes, dia), fmt = function (v) { return v === null ? "—" : idx.pref + br(v, idx.casas) + idx.suf; };
        var ref = function (d) { var p = d.split("/"); return idx.mensal ? MESES[+p[1] - 1] + " de " + p[2] : d; };
        out.textContent = "";
        if (esc.antesDaCobertura) {
          var p = el("p"); p.className = "aviso";
          p.textContent = "Não há versão registrada de " + idx.nome + " até o fim de " + dia.split("-").reverse().join("/") +
            ". A primeira versão preservada é de " + quando(esc.primeira.registrado_em) + " (horário de Brasília). " +
            "Os dados antigos que ela traz foram carregados de uma vez, então não mostram como o site estava antes disso.";
          var a = el("a", "Consultar a primeira data disponível");
          a.href = location.pathname + "?serie=" + cod + "&data=" + esc.primeira.registrado_em.slice(0, 10);
          out.appendChild(p); out.appendChild(a);
          return;
        }
        return Promise.all([
          lerJson(urlRaw(esc.versao.sha, idx.arquivo)).catch(function () { return null; }),
          lerJson("../data/" + cod + "_history.json"), lerJson("../data/versao.json").catch(function () { return {}; }),
        ]).then(function (r) {
          var cab = el("div", null, "card");
          cab.appendChild(el("p", "Versão consultada: commit dos dados " + esc.versao.sha.slice(0, 7) + ", registrado pelo " +
            "Observatório em " + quando(esc.versao.registrado_em) + " (horário de Brasília), a última até o fim de " +
            dia.split("-").reverse().join("/") + "."));
          cab.appendChild(el("p", "Comparada com: versão atual do site" + (r[2].sha ? ", dados do commit " + r[2].sha.slice(0, 7) : "") + "."));
          cab.appendChild(el("p", "O commit dos dados é o que gravou " + idx.arquivo + ". As páginas HTML podem ter sido " +
            "refeitas em commits posteriores sem mudar esses dados. A primeira coluna é a data de referência de cada observação.", "mut"));
          var lk = el("a", "Link desta consulta"); lk.href = location.href; cab.appendChild(lk);
          out.appendChild(cab);
          if (!r[0]) {
            var av = el("p", "A versão " + esc.versao.sha.slice(0, 7) + " não carregou agora (raw.githubusercontent.com não " +
              "respondeu). O Observatório não a substitui pela versão atual. Tente de novo mais tarde.", "aviso");
            av.setAttribute("role", "alert"); out.appendChild(av);
            var fa = el("a", "Ver a ficha atual de " + idx.nome); fa.href = "../indicadores/" + idx.slug + "/"; out.appendChild(fa);
            return;
          }
          var linhas = comparar(r[0], r[1]), rs = resumo(linhas);
          out.appendChild(el("p", rs.igual + " iguais, " + rs.alterado + " alteradas depois, " + rs.entrou_depois +
            " entraram depois" + (rs.deixou ? ", " + rs.deixou + " deixaram de constar" : "") + "."));
          var difs = linhas.filter(function (l) { return l.situacao !== "igual"; });
          var iguais = linhas.filter(function (l) { return l.situacao === "igual"; });
          function tabela(lista, titulo) {
            var w = el("div", null, "tabela-rolagem"); w.setAttribute("role", "region"); w.setAttribute("aria-label", titulo); w.tabIndex = 0;
            var t = el("table"), th = el("thead"), tr = el("tr");
            ["Referência", "Na versão consultada", "Atual", "Situação"].forEach(function (c) { var h = el("th", c); h.scope = "col"; tr.appendChild(h); });
            th.appendChild(tr); t.appendChild(th);
            var tb = el("tbody");
            lista.forEach(function (l) { var r2 = el("tr"); [ref(l.data), fmt(l.antes), fmt(l.agora), SIT[l.situacao]].forEach(function (c) { r2.appendChild(el("td", c)); }); tb.appendChild(r2); });
            t.appendChild(tb); w.appendChild(t); return w;
          }
          if (difs.length) { out.appendChild(el("h2", "O que mudou desde então")); out.appendChild(tabela(difs.slice(-400), "Observações diferentes")); }
          else out.appendChild(el("p", "Nenhuma observação mudou, entrou ou saiu desde a versão consultada."));
          if (iguais.length) {
            var det = el("details"), s = el("summary", "Mostrar as últimas " + Math.min(iguais.length, 60) + " observações iguais");
            det.appendChild(s); det.appendChild(tabela(iguais.slice(-60), "Observações iguais")); out.appendChild(det);
          }
        });
      }).catch(function () { out.textContent = "Não foi possível ler o índice de versões desta série agora."; });
    }
    form.addEventListener("submit", function (ev) { ev.preventDefault(); consultar(true); });
    window.addEventListener("popstate", function () {
      var q2 = new URLSearchParams(location.search);
      if (q2.get("serie")) { sel.value = q2.get("serie"); inp.value = q2.get("data") || ""; consultar(false); }
    });
    if (q.get("serie") && inp.value) consultar(false);
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
  }
  return { corte: corte, escolher: escolher, comparar: comparar, resumo: resumo, urlRaw: urlRaw };
});
