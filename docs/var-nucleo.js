/* var-nucleo.js — Núcleo do VAR da Economia: versão dos dados, carga e cálculo.

   Funções puras (sem DOM), usadas por var.html no navegador e pelos testes
   em node (tests/test_var_versao.py).

   Versão dos dados. O robô de coleta publica docs/data/versao.json com o
   commit que gravou os dados que o site está servindo (scripts/versao_dados.py).
   Todo recibo carrega as séries DAQUELE commit, em
   raw.githubusercontent.com/<repo>/<sha>/docs/data/, e grava o mesmo sha no
   link. Assim o commit do recibo é, por construção, o dos dados usados no
   cálculo, e um link aberto meses depois refaz a conta com os mesmos números,
   mesmo que o produtor tenha revisado algum mês.

   O link fixa os DADOS. A regra de cálculo é a do código servido hoje
   (metrica, abaixo); ela não muda de versão para versão desde a v1.4.0, mas o
   recibo não guarda uma cópia dela. */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.ObsVar = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var RE_SHA = /^[0-9a-f]{7,40}$/;

  function dataToYm(s) { var p = String(s).split("/"); return p[2] + "-" + p[1]; }
  function ymNum(ym) { var p = ym.split("-").map(Number); return p[0] * 12 + (p[1] - 1); }
  function ymFromNum(n) { var y = Math.floor(n / 12), m = (n % 12) + 1; return y + "-" + (m < 10 ? "0" : "") + m; }
  function num(v) { return parseFloat(String(v).replace(",", ".")); }
  function shaValido(s) { return RE_SHA.test(s || ""); }

  // Meses de calendário entre p1 e p2, inclusive (a duração do intervalo).
  function mesesEntre(p1, p2) { return Math.abs(ymNum(p2) - ymNum(p1)) + 1; }

  function serieDeJson(arr) {
    return (arr || []).map(function (p) { return { ym: dataToYm(p.data), v: num(p.valor) }; })
      .filter(function (p) { return isFinite(p.v); })
      .sort(function (a, b) { return ymNum(a.ym) - ymNum(b.ym); });
  }

  // Dois intervalos seguidos de mesma duração, o segundo terminando em `fim`.
  function intervaloComparavel(fim, meses) {
    var b2 = ymNum(fim), b1 = b2 - meses + 1, a2 = b1 - 1, a1 = a2 - meses + 1;
    return { a1: ymFromNum(a1), a2: ymFromNum(a2), b1: ymFromNum(b1), b2: ymFromNum(b2) };
  }

  // Métrica de um período. `meses` é a duração do intervalo; `obs`, quantos
  // meses dele têm dado na série (menor que `meses` quando falta competência;
  // séries diárias contam o mês uma vez só).
  function metrica(pts, nat, op, p1, p2) {
    var lo = Math.min(ymNum(p1), ymNum(p2)), hi = Math.max(ymNum(p1), ymNum(p2));
    var sel = pts.filter(function (p) { var n = ymNum(p.ym); return n >= lo && n <= hi; });
    var comp = {}; sel.forEach(function (p) { comp[p.ym] = 1; });
    var base = { meses: hi - lo + 1, obs: Object.keys(comp).length };
    if (!sel.length) return Object.assign({ ok: false }, base);
    var vals = sel.map(function (p) { return p.v; });
    if (op === "acum") {
      var f = 1; vals.forEach(function (v) { f *= 1 + v / 100; });
      return Object.assign({ ok: true, tipo: "pct", metric: (f - 1) * 100 }, base);
    }
    if (op === "media") {
      var m = vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
      return Object.assign({ ok: true, tipo: nat === "cambio" ? "cotacao" : "nivel", metric: m }, base);
    }
    var a = vals[0], z = vals[vals.length - 1];
    if (nat === "cambio") return Object.assign({ ok: true, tipo: "pct", metric: (z / a - 1) * 100, de: a, ate: z }, base);
    return Object.assign({ ok: true, tipo: "delta", metric: z - a, de: a, ate: z }, base);
  }

  // "48 meses" ou "48 meses, 47 com dado" (quando falta competência na série).
  function duracaoTxt(r) {
    var t = r.meses + (r.meses === 1 ? " mês" : " meses");
    if (r.obs !== r.meses) t += ", " + r.obs + " com dado";
    return t;
  }

  function urlDados(repo, sha) { return "https://raw.githubusercontent.com/" + repo + "/" + sha + "/docs/data/"; }

  async function carregaSeries(lerJson, base, cods) {
    var dados = {};
    await Promise.all(cods.map(async function (cod) {
      try { dados[cod] = serieDeJson(await lerJson(base + cod + "_history.json")); }
      catch (e) { dados[cod] = []; }
    }));
    return dados;
  }
  function temDado(dados, cods) { return cods.some(function (c) { return dados[c] && dados[c].length; }); }

  async function versaoPublicada(lerJson, localBase) {
    try {
      var v = await lerJson(localBase + "versao.json");
      return v && shaValido(v.sha) ? v.sha : null;
    } catch (e) { return null; }
  }

  // Decide de onde vêm os dados do recibo.
  //   shaPedido (link com ?sha=): só aquela versão. Se ela não carregar, devolve
  //     erro "versao_indisponivel" e NADA de dados: quem chama mostra o aviso e
  //     oferece consultar os dados atuais. Nunca troca de versão sozinho.
  //   sem sha: a versão publicada em versao.json; se o GitHub não responder,
  //     os dados do próprio site, marcados como "ao_vivo" (recibo sem commit).
  async function carregaRecibo(o) {
    if (o.shaPedido) {
      var d = await carregaSeries(o.lerJson, urlDados(o.repo, o.shaPedido), o.cods);
      if (!temDado(d, o.cods)) return { erro: "versao_indisponivel", sha: o.shaPedido };
      return { dados: d, sha: o.shaPedido, modo: "fixado" };
    }
    var sha = await versaoPublicada(o.lerJson, o.localBase);
    if (sha) {
      var dv = await carregaSeries(o.lerJson, urlDados(o.repo, sha), o.cods);
      if (temDado(dv, o.cods)) return { dados: dv, sha: sha, modo: "versionado" };
    }
    var dl = await carregaSeries(o.lerJson, o.localBase, o.cods);
    if (!temDado(dl, o.cods)) return { erro: "sem_dados" };
    return { dados: dl, sha: null, modo: "ao_vivo" };
  }

  return {
    dataToYm: dataToYm, ymNum: ymNum, ymFromNum: ymFromNum, shaValido: shaValido,
    mesesEntre: mesesEntre, serieDeJson: serieDeJson, intervaloComparavel: intervaloComparavel,
    metrica: metrica, duracaoTxt: duracaoTxt, urlDados: urlDados, carregaSeries: carregaSeries,
    versaoPublicada: versaoPublicada, carregaRecibo: carregaRecibo,
  };
});
