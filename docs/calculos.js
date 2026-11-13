/* calculos.js — Núcleo de cálculo do Comparador e do Simulador de CDI.

   Funções puras, sem acesso ao DOM, usadas por comparador.js e
   simulador-cdi.js no navegador e pelos testes (node) em
   tests/test_ferramentas_js.py. Metodologia em desenvolvimento/METODOLOGIA-FERRAMENTAS.md.

   Séries (data/<codigo>_history.json, [{data: "dd/mm/aaaa", valor: "..."}]):
     4389  CDI (taxa DI) anualizada, base 252, um ponto por dia útil (B3 via SGS)
     4391  CDI acumulado no mês, % (B3 via SGS)
     4390  Selic acumulada no mês, % (BCB)
     433   IPCA, variação mensal, % (IBGE via SGS)
   A Meta Selic (432) e o IPCA em 12 meses (13522) NÃO entram em cálculo:
   a primeira é uma meta, não uma taxa acumulável; a segunda já é acumulada. */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.ObsCalc = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ------------------------------------------------------------- datas
  var RE_DIA = /^(\d{4})-(\d{2})-(\d{2})$/;
  var RE_MES = /^(\d{4})-(\d{2})$/;

  function isoDeSgs(d) {            // "dd/mm/aaaa" -> "aaaa-mm-dd"
    var p = String(d).split("/");
    return p[2] + "-" + p[1] + "-" + p[0];
  }
  function diaValido(s) {
    var m = RE_DIA.exec(s || "");
    if (!m) return false;
    var dt = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return dt.getUTCFullYear() === +m[1] && dt.getUTCMonth() === +m[2] - 1 && dt.getUTCDate() === +m[3];
  }
  function mesValido(s) {
    var m = RE_MES.exec(s || "");
    return !!m && +m[2] >= 1 && +m[2] <= 12 && +m[1] >= 1990 && +m[1] <= 2100;
  }
  function msDia(s) { var m = RE_DIA.exec(s); return Date.UTC(+m[1], +m[2] - 1, +m[3]); }
  function diasCorridos(a, b) { return Math.round((msDia(b) - msDia(a)) / 86400000); }
  function somaDias(s, n) {
    var d = new Date(msDia(s) + n * 86400000);
    return d.toISOString().slice(0, 10);
  }
  function somaMeses(s, n) {          // mesmo dia do mês; dia inexistente vai para o último dia
    var m = RE_DIA.exec(s), a = +m[1], mes = +m[2] - 1 + n, dia = +m[3];
    a += Math.floor(mes / 12); mes = ((mes % 12) + 12) % 12;
    var ultimo = new Date(Date.UTC(a, mes + 1, 0)).getUTCDate();
    return new Date(Date.UTC(a, mes, Math.min(dia, ultimo))).toISOString().slice(0, 10);
  }
  function mesDe(s) { return s.slice(0, 7); }
  function proximoMes(m) {
    var a = +m.slice(0, 4), n = +m.slice(5, 7);
    return n === 12 ? (a + 1) + "-01" : a + "-" + (n < 9 ? "0" : "") + (n + 1);
  }
  function mesesEntre(de, ate) {      // inclusive
    var out = [], m = de, guarda = 0;
    while (m <= ate && guarda++ < 2000) { out.push(m); m = proximoMes(m); }
    return out;
  }
  function somaMesesMes(m, n) { return somaMeses(m + "-01", n).slice(0, 7); }

  // ------------------------------------------------------------- séries
  function historico(json) {         // -> [{d: "aaaa-mm-dd", v: Number}] em ordem
    var out = [];
    for (var i = 0; i < json.length; i++) {
      var v = parseFloat(String(json[i].valor).replace(",", "."));
      if (isFinite(v)) out.push({ d: isoDeSgs(json[i].data), v: v });
    }
    out.sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : 0; });
    return out;
  }
  function porMes(hist) {             // série mensal -> {"aaaa-mm": v}
    var m = {};
    for (var i = 0; i < hist.length; i++) m[mesDe(hist[i].d)] = hist[i].v;
    return m;
  }

  // ------------------------------------------------------------- composição
  // Fator = Π (1 + taxa/100); variação = (fator − 1) × 100. Só para séries
  // cuja taxa vale para o próprio período (acumulados no mês, variação mensal).
  function compor(taxas) {
    var f = 1;
    for (var i = 0; i < taxas.length; i++) f *= 1 + taxas[i] / 100;
    return { fator: f, pct: (f - 1) * 100 };
  }

  /* Comparador: competências de `de` a `ate`, inclusive.
     mapas = {cdi: {...}, selic: {...}, ipca: {...}} (só os escolhidos).
     Erro se faltar a competência em alguma série escolhida. */
  function comparar(mapas, de, ate) {
    if (!mesValido(de) || !mesValido(ate)) return { erro: "Período inválido." };
    if (de > ate) return { erro: "O mês inicial deve ser anterior ou igual ao final." };
    var meses = mesesEntre(de, ate), chaves = Object.keys(mapas);
    if (!chaves.length) return { erro: "Escolha ao menos um indicador." };
    var fat = {}, linhas = [];
    chaves.forEach(function (k) { fat[k] = 1; });
    for (var i = 0; i < meses.length; i++) {
      var l = { mes: meses[i], taxas: {}, fatores: {} };
      for (var j = 0; j < chaves.length; j++) {
        var k = chaves[j], v = mapas[k][meses[i]];
        if (typeof v !== "number") return { erro: "Sem dado de " + k.toUpperCase() + " para " + meses[i] + "." , falta: { serie: k, mes: meses[i] } };
        fat[k] *= 1 + v / 100;
        l.taxas[k] = v; l.fatores[k] = fat[k];
      }
      linhas.push(l);
    }
    var res = {};
    chaves.forEach(function (k) { res[k] = { fator: fat[k], pct: (fat[k] - 1) * 100 }; });
    return { meses: meses.length, linhas: linhas, resultado: res };
  }

  // ------------------------------------------------------------- CDI diário
  /* Rendimento a p% do CDI entre a data de aplicação (inclusive) e a de
     resgate (exclusive): cada dia útil d com taxa DI anual t rende
       fator_DI(d) = (1 + t/100)^(1/252)
       fator(d)    = 1 + (p/100) × (fator_DI(d) − 1)
     e o saldo é composto dia a dia. O percentual é aplicado à taxa de cada
     dia ANTES da composição. Dias sem observação não existem (não há
     interpolação). */
  function simularCDI(diario, inicio, fim, percentual, valor) {
    if (!diaValido(inicio) || !diaValido(fim)) return { erro: "Datas inválidas." };
    if (fim <= inicio) return { erro: "A data de resgate deve ser posterior à de aplicação." };
    if (!(percentual > 0 && percentual <= 300)) return { erro: "Percentual do CDI deve estar entre 0,01% e 300%." };
    if (!(valor > 0 && valor <= 1e12)) return { erro: "Valor inicial inválido." };
    if (!diario.length) return { erro: "Série do CDI indisponível." };
    var primeiro = diario[0].d, ultimo = diario[diario.length - 1].d;
    if (inicio < primeiro) return { erro: "A série do CDI começa em " + primeiro + "." };
    var limite = somaDias(ultimo, 1);
    if (fim > limite) return { erro: "Ainda não há taxa DI publicada depois de " + ultimo + ".", ultimo: ultimo };
    var saldo = valor, linhas = [], p = percentual / 100;
    for (var i = 0; i < diario.length; i++) {
      var o = diario[i];
      if (o.d < inicio) continue;
      if (o.d >= fim) break;
      var fdi = Math.pow(1 + o.v / 100, 1 / 252);
      var f = 1 + p * (fdi - 1);
      var antes = saldo;
      saldo = antes * f;
      linhas.push({ data: o.d, taxa: o.v, fatorDI: fdi, fator: f, saldoAnterior: antes, rendimento: saldo - antes, saldo: saldo });
    }
    var fdiTotal = 1;
    for (var k = 0; k < linhas.length; k++) fdiTotal *= linhas[k].fatorDI;
    return {
      inicio: inicio, fim: fim, diasCorridos: diasCorridos(inicio, fim), diasUteis: linhas.length,
      percentual: percentual, valor: valor, valorBruto: saldo, rendimentoBruto: saldo - valor,
      cdiAcumuladoPct: (fdiTotal - 1) * 100, rentabilidadeBrutaPct: (saldo / valor - 1) * 100,
      linhas: linhas, ultimoDado: ultimo,
    };
  }

  // ------------------------------------------------------------- tributos (CDB, pessoa física)
  // IR: Lei 11.033/2004, art. 1º (tabela regressiva por dias corridos).
  // IOF: Decreto 6.306/2007, art. 32 e anexo (resgate em menos de 30 dias).
  var IOF_TABELA = [0, 96, 93, 90, 86, 83, 80, 76, 73, 70, 66, 63, 60, 56, 53, 50, 46, 43, 40, 36,
                    33, 30, 26, 23, 20, 16, 13, 10, 6, 3];               // índice = dias corridos
  function aliquotaIR(dias) {
    if (dias <= 180) return 22.5;
    if (dias <= 360) return 20;
    if (dias <= 720) return 17.5;
    return 15;
  }
  function aliquotaIOF(dias) { return dias >= 1 && dias < 30 ? IOF_TABELA[dias] : 0; }
  function centavos(x) {            // arredondamento comercial para centavos
    return Math.round((x + (x >= 0 ? 1e-9 : -1e-9)) * 100) / 100;
  }
  /* IOF incide sobre o rendimento; o IR, sobre o rendimento menos o IOF.
     Sem rendimento positivo, não há imposto. */
  function tributosCDB(rendimento, dias) {
    var base = Math.max(0, rendimento);
    var aIOF = aliquotaIOF(dias), iof = centavos(base * aIOF / 100);
    var aIR = aliquotaIR(dias), ir = centavos((base - iof) * aIR / 100);
    return { aliquotaIOF: aIOF, iof: iof, aliquotaIR: aIR, ir: ir, total: centavos(iof + ir) };
  }

  // ------------------------------------------------------------- inflação
  /* IPCA dos meses de competência do mês da aplicação ao mês anterior ao do
     resgate. Aproximação: aplicações no meio do mês contam o mês inteiro.
     Sem algum desses meses publicado, devolve null (não se estima). */
  function inflacaoPeriodo(ipcaMes, inicio, fim) {
    var de = mesDe(inicio), ate = somaMesesMes(mesDe(fim), -1);
    if (ate < de) return { erro: "Período menor que um mês de competência do IPCA." };
    var meses = mesesEntre(de, ate), taxas = [];
    for (var i = 0; i < meses.length; i++) {
      if (typeof ipcaMes[meses[i]] !== "number") return { erro: "IPCA de " + meses[i] + " ainda não publicado.", falta: meses[i] };
      taxas.push(ipcaMes[meses[i]]);
    }
    var c = compor(taxas);
    return { de: de, ate: ate, meses: meses.length, fator: c.fator, pct: c.pct };
  }
  function rentabilidadeReal(nominalPct, inflacaoPct) {
    return ((1 + nominalPct / 100) / (1 + inflacaoPct / 100) - 1) * 100;
  }

  // ------------------------------------------------------------- formatação e CSV
  function br(x, casas) {
    var s = Math.abs(x).toFixed(casas).split(".");
    s[0] = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (x < 0 && +Math.abs(x).toFixed(casas) !== 0 ? "-" : "") + s.join(",");
  }
  function csvCelula(v) {
    var s = String(v);
    if (/^[=+\-@\t\r]/.test(s) && !/^-?\d/.test(s)) s = "'" + s;    // evita fórmula no Excel
    return /[;"\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function csv(cabecalho, linhas) {
    var out = [cabecalho.map(csvCelula).join(";")];
    for (var i = 0; i < linhas.length; i++) out.push(linhas[i].map(csvCelula).join(";"));
    return "\ufeff" + out.join("\r\n") + "\r\n";
  }
  function csvSimulacao(r) {
    var cab = ["Data", "Taxa DI (% a.a.)", "Percentual do CDI (%)", "Fator do dia", "Saldo anterior (R$)",
               "Rendimento (R$)", "Saldo (R$)"];
    var lin = r.linhas.map(function (l) {
      return [l.data, br(l.taxa, 2), br(r.percentual, 2), br(l.fator, 10), br(l.saldoAnterior, 2),
              br(l.rendimento, 2), br(l.saldo, 2)];
    });
    return csv(cab, lin);
  }

  // ------------------------------------------------------------- parâmetros de URL
  // Lista fechada de chaves e formatos: nada do que vem na URL é executado
  // ou inserido como HTML.
  var PERIODOS = { "6m": 6, "12m": 12, "24m": 24, "36m": 36, "60m": 60 };
  function numero(s, min, max) {
    if (!/^\d{1,13}([.,]\d{1,2})?$/.test(s || "")) return null;
    var v = parseFloat(String(s).replace(",", "."));
    return v >= min && v <= max ? v : null;
  }
  function lerParamsSimulador(qs) {
    var p = {}, v;
    if ((v = numero(qs.get("valor"), 0.01, 1e9)) !== null) p.valor = v;
    if ((v = numero(qs.get("percentual"), 0.01, 300)) !== null) p.percentual = v;
    if (PERIODOS[qs.get("periodo")]) p.periodo = qs.get("periodo");
    if (diaValido(qs.get("de")) && diaValido(qs.get("ate"))) { p.de = qs.get("de"); p.ate = qs.get("ate"); delete p.periodo; }
    if (qs.get("modo") === "bruto" || qs.get("modo") === "liquido") p.modo = qs.get("modo");
    return p;
  }
  var INDICADORES = ["cdi", "selic", "ipca"];
  function lerParamsComparador(qs) {
    var p = {};
    if (mesValido(qs.get("de")) && mesValido(qs.get("ate")) && qs.get("de") <= qs.get("ate")) {
      p.de = qs.get("de"); p.ate = qs.get("ate");
    }
    var n = qs.get("meses");
    if (n === "12" || n === "24" || n === "36" || n === "60") p.meses = +n;
    var i = (qs.get("i") || "").split(",").filter(function (x) { return INDICADORES.indexOf(x) >= 0; });
    if (i.length) p.indicadores = INDICADORES.filter(function (x) { return i.indexOf(x) >= 0; });
    if (qs.get("ver") === "reais" || qs.get("ver") === "pct") p.ver = qs.get("ver");
    return p;
  }
  function periodoParaDatas(periodo, ultimoDado) {
    var fim = somaDias(ultimoDado, 1);
    return { inicio: somaMeses(fim, -PERIODOS[periodo]), fim: fim };
  }

  return {
    isoDeSgs: isoDeSgs, diaValido: diaValido, mesValido: mesValido, diasCorridos: diasCorridos,
    somaDias: somaDias, somaMeses: somaMeses, somaMesesMes: somaMesesMes, mesesEntre: mesesEntre,
    historico: historico, porMes: porMes, compor: compor, comparar: comparar,
    simularCDI: simularCDI, aliquotaIR: aliquotaIR, aliquotaIOF: aliquotaIOF, tributosCDB: tributosCDB,
    centavos: centavos, inflacaoPeriodo: inflacaoPeriodo, rentabilidadeReal: rentabilidadeReal,
    br: br, csv: csv, csvSimulacao: csvSimulacao, lerParamsSimulador: lerParamsSimulador,
    lerParamsComparador: lerParamsComparador, periodoParaDatas: periodoParaDatas, PERIODOS: PERIODOS,
    INDICADORES: INDICADORES,
  };
});
