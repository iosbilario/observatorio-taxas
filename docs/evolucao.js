/* evolucao.js — "Ver evolução desde o início do contrato" e "Comparar com outro índice".

   Reconstrói os reajustes anuais de um contrato: em cada aniversário, o valor
   anterior × o fator do acumulado de 12 meses do índice, com a MESMA conta do
   demonstrativo (docs/demonstrativo.js, ObsDemo.calcula: fator com 10 casas e
   centavos com meio centavo para cima). O valor reajustado vira a base do
   aniversário seguinte. Na comparação, cada índice evolui do seu próprio saldo.

   Regra de referência = defasagem: com 1 (o costume), o aniversário de
   novembro de 2024 usa o acumulado de novembro de 2023 a outubro de 2024.

   Privacidade: o valor fica no navegador. Não entra na URL, em requisições nem
   em métricas; a passagem vinda do demonstrativo usa sessionStorage (só esta
   aba). As séries são os JSON públicos do site, os mesmos para qualquer pessoa.

   Funções puras exportadas para os testes (node). */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica(require("./demonstrativo.js"));
  else raiz.ObsEvol = fabrica(raiz.ObsDemo);
})(typeof self !== "undefined" ? self : this, function (Demo) {
  "use strict";
  var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
               "outubro", "novembro", "dezembro"];
  var INDICES = { ipca: [433, "IPCA"], igpm: [189, "IGP-M"], inpc: [188, "INPC"], igpdi: [190, "IGP-DI"] };
  var REGRAS = { "1": "acumulado de 12 meses até o mês anterior ao aniversário",
                 "2": "acumulado de 12 meses até dois meses antes do aniversário",
                 "0": "acumulado de 12 meses até o mês do aniversário" };
  var CHAVE_SESSAO = "obs-evolucao";

  function soma(ym, n) {
    var t = +ym.slice(0, 4) * 12 + (+ym.slice(5, 7) - 1) + n;
    var m = t % 12 + 1;
    return Math.floor(t / 12) + "-" + (m < 10 ? "0" : "") + m;
  }
  function mesTxt(ym) { return MESES[+ym.slice(5, 7) - 1] + " de " + ym.slice(0, 4); }
  function porMes(hist) {
    var m = {};
    (hist || []).forEach(function (p) { var d = String(p.data).split("/"); m[d[2] + "-" + d[1]] = Number(String(p.valor).replace(",", ".")); });
    return m;
  }

  function aniversarios(inicio, defasagem, corte) {
    var out = [];
    for (var k = 1; k < 200; k++) {
      var aniv = soma(inicio, 12 * k);
      if (aniv > corte) break;
      var fim = soma(aniv, -defasagem);
      out.push({ n: k, aniversario: aniv, janela: [soma(fim, -11), fim] });
    }
    return out;
  }

  // Evolução a partir de `base` (número). Para no primeiro aniversário sem as 12 competências.
  function evolucao(mapa, base, inicio, defasagem, corte) {
    var anivs = aniversarios(inicio, defasagem, corte), linhas = [], saldo = base, parada = null;
    var meses = Object.keys(mapa).sort(), primeiro = meses[0], ultimo = meses[meses.length - 1];
    for (var i = 0; i < anivs.length; i++) {
      var a = anivs[i], comps = [], faltam = [], f = 1;
      for (var k = 0; k < 12; k++) {
        var ym = soma(a.janela[0], k);
        if (typeof mapa[ym] !== "number" || !isFinite(mapa[ym])) faltam.push(ym);
        else { comps.push({ ym: ym, v: mapa[ym] }); f *= 1 + mapa[ym] / 100; }
      }
      if (faltam.length) {
        parada = { n: a.n, aniversario: a.aniversario, janela: a.janela, faltam: faltam,
                   motivo: faltam[0] < primeiro ? "antes_da_cobertura" : faltam[faltam.length - 1] > ultimo ? "ainda_nao_divulgado" : "lacuna",
                   primeiro: primeiro, ultimo: ultimo };
        break;
      }
      var r = Demo.calcula(saldo, f);
      linhas.push({ n: a.n, aniversario: a.aniversario, janela: a.janela, competencias: comps,
                    acumulado: (f - 1) * 100, fator: f, fatorTxt: Demo.fatorTxt(f),
                    antes: r.valor, novo: r.novo, diferenca: r.diferenca });
      saldo = r.novo;
    }
    return { linhas: linhas, parada: parada, aniversarios: anivs.length, base: base, saldo: saldo };
  }

  // Dois índices, mesma base e mesmas competências; cada um com o seu saldo.
  // Diferença só nos aniversários em que os dois foram calculados.
  function comparar(mapaA, mapaB, base, inicio, defasagem, corte) {
    var a = evolucao(mapaA, base, inicio, defasagem, corte), b = evolucao(mapaB, base, inicio, defasagem, corte);
    var n = Math.min(a.linhas.length, b.linhas.length), linhas = [];
    for (var i = 0; i < n; i++) {
      var x = a.linhas[i], y = b.linhas[i];
      linhas.push({ n: x.n, aniversario: x.aniversario, janela: x.janela, a: x, b: y,
                    diferenca: Math.round((y.novo - x.novo) * 100) / 100 });
    }
    return { linhas: linhas, a: a, b: b, conferidoAte: n ? linhas[n - 1].aniversario : null };
  }

  function brl(x) { return Demo.brl(x); }
  function pct(x) { return Demo.pctTxt(x); }

  function texto(nome, regra, r) {
    var l = ["Evolução do contrato pelo " + nome + " (" + REGRAS[regra] + ")", "Valor inicial: " + brl(r.base)];
    r.linhas.forEach(function (x) {
      l.push(mesTxt(x.aniversario) + ": " + mesTxt(x.janela[0]) + " a " + mesTxt(x.janela[1]) + ", acumulado " + pct(x.acumulado) +
             ", fator " + x.fatorTxt + ", de " + brl(x.antes) + " para " + brl(x.novo) + " (" + (x.diferenca < 0 ? "−" : "+") + " " + brl(x.diferenca) + ")");
    });
    if (r.parada) l.push("Interrompido em " + mesTxt(r.parada.aniversario) + ": falta " + r.parada.faltam.map(mesTxt).join(", ") + ".");
    l.push("Conta: valor anterior × fator de 10 casas, arredondado ao centavo; o resultado é a base do ano seguinte.");
    l.push("Fonte: séries do SGS/Banco Central. Calculado pelo Observatório de Taxas: https://observatoriodetaxas.tec.br/reajuste/evolucao/");
    return l.join("\n");
  }

  // ------------------------------------------------------------------ DOM
  function iniciar() {
    var form = document.getElementById("evol-form");
    if (!form) return;
    var E = form.elements, out = document.getElementById("evol-res"), cmp = document.getElementById("evol-cmp");
    var exemplo = document.getElementById("evol-exemplo"), cen = document.getElementById("cenario"), dados = {};
    var q = new URLSearchParams(location.search);
    ["indice", "regra"].forEach(function (k) { if (q.get(k) && E[k].querySelector('option[value="' + q.get(k) + '"]')) E[k].value = q.get(k); });
    function ymCampos(prefixo, ym) { if (/^\d{4}-\d{2}$/.test(ym || "")) { E[prefixo + "_mes"].value = ym.slice(5); E[prefixo + "_ano"].value = ym.slice(0, 4); } }
    ymCampos("inicio", q.get("inicio")); ymCampos("corte", q.get("corte"));
    var passou = null;
    try { passou = JSON.parse(sessionStorage.getItem(CHAVE_SESSAO) || "null"); } catch (e) { passou = null; }
    if (passou && passou.valor) E.valor.value = Demo.br(passou.valor, 2);
    if (q.get("cenario") && cen.querySelector('option[value="' + q.get("cenario") + '"]')) cen.value = q.get("cenario");

    function ym(prefixo) { return E[prefixo + "_ano"].value + "-" + E[prefixo + "_mes"].value; }
    function atualizaExemplo() {
      var ini = ym("inicio"), d = +E.regra.value, a = aniversarios(ini, d, "9999-12")[0];
      exemplo.textContent = "Com esta regra, um contrato iniciado em " + mesTxt(ini) + " tem o primeiro reajuste em " +
        mesTxt(a.aniversario) + ", pelo acumulado de " + mesTxt(a.janela[0]) + " a " + mesTxt(a.janela[1]) +
        ". O seguinte usa " + mesTxt(soma(a.janela[0], 12)) + " a " + mesTxt(soma(a.janela[1], 12)) + ".";
    }
    ["inicio_mes", "inicio_ano", "regra"].forEach(function (k) { E[k].addEventListener("change", atualizaExemplo); });
    atualizaExemplo();

    function serie(chave) {
      if (dados[chave]) return Promise.resolve(dados[chave]);
      return fetch("../../data/" + INDICES[chave][0] + "_history.json").then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (h) { dados[chave] = porMes(h); return dados[chave]; });
    }
    function el(t, txt, cls) { var e = document.createElement(t); if (txt != null) e.textContent = txt; if (cls) e.className = cls; return e; }
    function tabela(cab, linhas, rotulo) {
      var w = el("div", null, "tabela-rolagem"); w.setAttribute("role", "region"); w.setAttribute("aria-label", rotulo); w.tabIndex = 0;
      var t = el("table"), tr = el("tr"), th = el("thead"), tb = el("tbody");
      cab.forEach(function (c) { var h = el("th", c); h.scope = "col"; tr.appendChild(h); }); th.appendChild(tr); t.appendChild(th);
      linhas.forEach(function (l) { var r = el("tr"); l.forEach(function (c) { r.appendChild(c instanceof Node ? (function () { var td = el("td"); td.appendChild(c); return td; })() : el("td", c)); }); tb.appendChild(r); });
      t.appendChild(tb); w.appendChild(t); return w;
    }
    function avisoParada(p, nome) {
      if (!p) return null;
      var txt = p.motivo === "antes_da_cobertura" ? "A série do " + nome + " no Observatório começa em " + mesTxt(p.primeiro) + "; o aniversário de " +
        mesTxt(p.aniversario) + " precisaria de " + mesTxt(p.faltam[0]) + "." :
        p.motivo === "ainda_nao_divulgado" ? "O aniversário de " + mesTxt(p.aniversario) + " precisa de " + p.faltam.map(mesTxt).join(", ") +
        ", ainda sem dado no Observatório (último mês: " + mesTxt(p.ultimo) + ")." :
        "Falta a competência " + p.faltam.map(mesTxt).join(", ") + " do " + nome + ". O cálculo para em " + mesTxt(p.aniversario) +
        ", porque a base dos anos seguintes ficaria indeterminada.";
      var a = el("p", txt, "aviso"); a.setAttribute("role", "status"); return a;
    }
    function calcular(ev) {
      if (ev) ev.preventDefault();
      var v = Demo.parseValor(E.valor.value), ini = ym("inicio"), corte = ym("corte"), regra = E.regra.value, chave = E.indice.value;
      out.textContent = ""; cmp.hidden = true;
      if (v === null) { out.appendChild(el("p", "Informe o valor inicial entre R$ 0,01 e " + Demo.brl(Demo.VALOR_MAX) + ".", "aviso")); return; }
      if (corte < ini) { out.appendChild(el("p", "A data de corte deve ser depois do início do contrato.", "aviso")); return; }
      history.replaceState(null, "", location.pathname + "?indice=" + chave + "&inicio=" + ini + "&regra=" + regra + "&corte=" + corte);
      serie(chave).then(function (mapa) {
        var nome = INDICES[chave][1], r = evolucao(mapa, v, ini, +regra, corte);
        if (!r.aniversarios) { out.appendChild(el("p", "O primeiro aniversário (" + mesTxt(soma(ini, 12)) + ") ainda não foi alcançado na data de corte.", "aviso")); return; }
        out.appendChild(el("h2", "Evolução pelo " + nome));
        out.appendChild(el("p", "Regra: " + REGRAS[regra] + ". Em cada aniversário: valor anterior × fator do acumulado (10 casas), " +
          "arredondado ao centavo, com meio centavo para cima. O valor arredondado é a base do aniversário seguinte."));
        var ls = r.linhas.map(function (x) {
          var det = el("details"); det.appendChild(el("summary", "Memória"));
          det.appendChild(tabela(["Competência", "Variação"], x.competencias.map(function (c) { return [mesTxt(c.ym), pct(c.v)]; }), "Competências de " + mesTxt(x.aniversario)));
          det.appendChild(el("p", Demo.brl(x.antes) + " × " + x.fatorTxt + " = " + Demo.brl(x.novo) + " (arredondado ao centavo). Base de " +
            mesTxt(soma(x.aniversario, 12)) + ": " + Demo.brl(x.novo) + "." + (x.acumulado < 0 ? " Acumulado negativo: confira no contrato se a redução se aplica." : ""), "mut"));
          return [mesTxt(x.aniversario), mesTxt(x.janela[0]) + " a " + mesTxt(x.janela[1]), pct(x.acumulado), x.fatorTxt,
                  Demo.brl(x.antes), (x.diferenca < 0 ? "− " : "+ ") + Demo.brl(x.diferenca), Demo.brl(x.novo), det];
        });
        if (ls.length) out.appendChild(tabela(["Aniversário", "Competências", "Acumulado", "Fator", "Antes", "Diferença", "Novo valor", "Memória"], ls, "Reajustes anuais"));
        var p = avisoParada(r.parada, nome); if (p) out.appendChild(p);
        if (r.linhas.length) {
          out.appendChild(el("p", "Valor em " + mesTxt(r.linhas[r.linhas.length - 1].aniversario) + ": " + Demo.brl(r.saldo) + "."));
          var bt = el("button", "Copiar demonstrativo"); bt.type = "button";
          var st = el("p", null, "mut"); st.setAttribute("role", "status");
          var cx = el("textarea"); cx.hidden = true; cx.readOnly = true; cx.rows = 8; cx.setAttribute("aria-label", "Texto do demonstrativo");
          bt.addEventListener("click", function () { Demo.copiar(texto(nome, regra, r), bt, st, cx); });
          out.appendChild(bt); out.appendChild(st); out.appendChild(cx);
          cmp.hidden = false;
          if (q.get("comparar") === "1") { q.delete("comparar"); compararAgora(); }
        }
      }).catch(function () { out.appendChild(el("p", "Não foi possível carregar a série do índice agora.", "aviso")); });
    }
    function compararAgora(ev) {
      if (ev) ev.preventDefault();
      var v = Demo.parseValor(E.valor.value), ini = ym("inicio"), corte = ym("corte"), regra = +E.regra.value;
      var ka = E.indice.value, kb = cen.value, res = document.getElementById("evol-cmp-res");
      res.textContent = "";
      if (v === null) return;
      Promise.all([serie(ka), serie(kb)]).then(function (m) {
        var c = comparar(m[0], m[1], v, ini, regra, corte), na = INDICES[ka][1], nb = INDICES[kb][1];
        res.appendChild(el("p", "Índice do contrato: " + na + ". Cenário: " + nb + ". Os dois partem de " + Demo.brl(v) +
          " e usam as mesmas competências em cada aniversário; cada um segue do seu próprio saldo."));
        if (c.linhas.length) {
          res.appendChild(tabela(["Aniversário", "Competências", na + " (acumulado · fator)", nb + " (acumulado · fator)", na, nb, "Diferença (" + nb + " − " + na + ")"],
            c.linhas.map(function (l) {
              return [mesTxt(l.aniversario), mesTxt(l.janela[0]) + " a " + mesTxt(l.janela[1]), pct(l.a.acumulado) + " · " + l.a.fatorTxt,
                      pct(l.b.acumulado) + " · " + l.b.fatorTxt, Demo.brl(l.a.novo), Demo.brl(l.b.novo),
                      (l.diferenca < 0 ? "− " : l.diferenca > 0 ? "+ " : "") + Demo.brl(l.diferenca)];
            }), "Comparação entre índices"));
          var u = c.linhas[c.linhas.length - 1], d = u.diferenca;
          res.appendChild(el("p", d === 0 ? "Em " + mesTxt(u.aniversario) + ", os dois cenários chegam ao mesmo valor, " + Demo.brl(u.a.novo) + "." :
            "Em " + mesTxt(u.aniversario) + ", o cenário pelo " + nb + " fica " + Demo.brl(d) + (d > 0 ? " acima" : " abaixo") +
            " do valor pelo " + na + " (" + Demo.brl(u.b.novo) + " contra " + Demo.brl(u.a.novo) + ")."));
        }
        [[c.a, na], [c.b, nb]].forEach(function (x) { var p = avisoParada(x[0].parada, x[1]); if (p) res.appendChild(p); });
        if ((c.a.parada || c.b.parada) && c.linhas.length) res.appendChild(el("p", "A diferença foi conferida até " + mesTxt(c.conferidoAte) + "; depois disso os períodos não são iguais e não há diferença a mostrar.", "mut"));
        if (!c.linhas.length) res.appendChild(el("p", "Sem aniversário calculado pelos dois índices: não há diferença a mostrar.", "aviso"));
      });
    }
    form.addEventListener("submit", calcular);
    document.getElementById("evol-cmp-form").addEventListener("submit", compararAgora);
    if (passou && passou.valor && q.get("inicio")) calcular();
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar); else iniciar();
  }
  return { soma: soma, porMes: porMes, aniversarios: aniversarios, evolucao: evolucao, comparar: comparar, texto: texto,
           INDICES: INDICES, REGRAS: REGRAS, CHAVE_SESSAO: CHAVE_SESSAO };
});
