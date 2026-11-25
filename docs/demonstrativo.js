/* demonstrativo.js — Resultado da calculadora de reajuste e "Copiar demonstrativo".

   Usado pelas páginas de mês em /reajuste/<indice>-<mes>-<ano>/ (gerador
   scripts/build_pages.py) e pela calculadora de reajuste da página inicial.
   As funções de texto e de cálculo são puras e testadas em node
   (tests/test_demonstrativo.py); as de DOM ficam no fim do arquivo.

   Privacidade: o valor do contrato fica só na tela e no texto copiado. O link
   de conferência leva índice, mês de referência e a versão dos dados (o commit,
   ?dados=<sha>), nunca o valor. O destinatário abre o link, vê o fator usado e
   digita o valor para conferir os centavos.

   Precisão: o fator aparece com 10 casas e o cálculo usa exatamente esse
   fator exibido (ver calcula). Com qualquer valor até R$ 10.000.000,00 (o
   máximo aceito), valor × fator exibido fica a menos de R$ 0,0005 de
   valor × fator completo, e o resultado é reproduzível à mão a partir do texto. */
(function (raiz, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else raiz.ObsDemo = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CASAS_FATOR = 10;
  var VALOR_MAX = 10000000;
  var ORIGEM = "https://observatoriodetaxas.tec.br";
  var REPO = "iosbilario/observatorio-taxas";
  var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
               "agosto", "setembro", "outubro", "novembro", "dezembro"];

  function br(x, casas) {
    return x.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  }
  function brl(x) { return "R$ " + br(Math.abs(x), 2); }
  function fatorTxt(f) { return br(Math.round(f * ESCALA) / ESCALA, CASAS_FATOR); }
  function pctTxt(p) { return br(p, 2).replace(/^-/, "−") + "%"; }

  // "2.000,00", "2000,5", "2000.50", "2.000" -> número; null se inválido ou fora da faixa.
  function parseValor(s) {
    s = String(s == null ? "" : s).trim().replace(/^R\$\s*/, "");
    if (!s) return null;
    if (s.indexOf(",") >= 0) s = s.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
    if (!/^\d+(\.\d+)?$/.test(s)) return null;
    var v = Number(s);
    return v > 0 && v <= VALOR_MAX ? v : null;
  }

  function mesTxt(ym) { var p = ym.split("-"); return MESES[+p[1] - 1] + " de " + p[0]; }
  function somaMeses(ym, n) {
    var p = ym.split("-").map(Number), t = p[0] * 12 + p[1] - 1 + n;
    var m = t % 12 + 1; return Math.floor(t / 12) + "-" + (m < 10 ? "0" : "") + m;
  }

  // Reajuste anual: valor × fator EXIBIDO (10 casas), em centavos e inteiros
  // exatos (BigInt), arredondando meio centavo para cima. Assim quem recebe o
  // demonstrativo reproduz os centavos com o próprio fator do texto.
  var ESCALA = Math.pow(10, CASAS_FATOR);
  function calcula(valor, fator) {
    var fInt = BigInt(Math.round(fator * ESCALA));
    var cent = BigInt(Math.round(valor * 100));
    var esc = BigInt(ESCALA);
    var novoCent = (cent * fInt + esc / BigInt(2)) / esc;
    var novo = Number(novoCent) / 100, v = Number(cent) / 100;
    return { valor: v, fator: Number(fInt) / ESCALA, novo: novo, diferenca: Number(novoCent - cent) / 100 };
  }

  function linkConferencia(chave, refYm, sha) {
    var p = refYm.split("-");
    var url = ORIGEM + "/reajuste/" + chave + "-" + MESES[+p[1] - 1] + "-" + p[0] + "/";
    return /^[0-9a-f]{40}$/.test(sha || "") ? url + "?dados=" + sha : url;
  }

  // Texto curto, pronto para WhatsApp ou e-mail.
  function texto(d) {
    var r = calcula(d.valor, d.fator);
    var ini = somaMeses(d.refYm, -11);
    var sinal = r.diferenca > 0 ? "+" : r.diferenca < 0 ? "−" : "";
    var linhas = [
      "Reajuste pelo " + d.indice + " (acumulado em 12 meses)",
      "Valor original: " + brl(r.valor),
      "Período: " + mesTxt(ini) + " a " + mesTxt(d.refYm) + " (12 meses)",
      "Acumulado: " + pctTxt((d.fator - 1) * 100),
      "Fator: " + fatorTxt(d.fator),
      "Valor reajustado: " + brl(r.novo),
      "Diferença: " + sinal + (sinal ? " " : "") + brl(r.diferenca),
    ];
    if (r.diferenca < 0) linhas.push("Acumulado negativo: confira no contrato se a redução se aplica.");
    linhas.push("Confira o índice, o período e o fator: " + d.link);
    linhas.push("Fonte: " + d.produtor + ", via SGS/Banco Central. Calculado pelo Observatório de Taxas. Conteúdo informativo.");
    return linhas.join("\n");
  }

  // Fator do acumulado de 12 meses até refYm numa versão dos dados.
  async function fatorNaVersao(lerJson, sha, codigo, refYm) {
    var arr;
    try { arr = await lerJson("https://raw.githubusercontent.com/" + REPO + "/" + sha + "/docs/data/" + codigo + "_history.json"); }
    catch (e) { return { ok: false, motivo: "versao_indisponivel" }; }
    var porMes = {};
    (arr || []).forEach(function (p) { var d = String(p.data).split("/"); porMes[d[2] + "-" + d[1]] = parseFloat(String(p.valor).replace(",", ".")); });
    var f = 1;
    for (var i = -11; i <= 0; i++) {
      var v = porMes[somaMeses(refYm, i)];
      if (!isFinite(v)) return { ok: false, motivo: "competencia_indisponivel" };
      f *= 1 + v / 100;
    }
    return { ok: true, fator: f };
  }

  // ------------------------------------------------------------------ DOM
  // Copia o texto; sem área de transferência, mostra o texto selecionável.
  function copiar(txt, botao, status, caixa) {
    var feito = false;
    function ok() {
      if (feito) return; feito = true;
      status.textContent = "Demonstrativo copiado. Cole no WhatsApp ou no e-mail.";
      botao.textContent = "Copiado ✓";
      caixa.hidden = true;
      setTimeout(function () { botao.textContent = "Copiar demonstrativo"; }, 2500);
    }
    function manual() {
      if (feito) return; feito = true;
      caixa.hidden = false; caixa.value = txt; caixa.focus(); caixa.select();
      status.textContent = "Não deu para copiar automaticamente. O texto está selecionado abaixo: copie com Ctrl+C ou ⌘+C.";
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(ok, manual);
        // Alguns navegadores deixam a promessa pendente quando a permissão não vem.
        setTimeout(manual, 1500);
      } else manual();
    } catch (e) { manual(); }
  }

  async function lerJson(url) {
    var r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function versaoAtual(base) {
    try { var v = await lerJson(base + "data/versao.json"); return /^[0-9a-f]{40}$/.test(v.sha || "") ? v.sha : null; }
    catch (e) { return null; }
  }

  // Monta resultado + botão de cópia num bloco [data-demonstrativo].
  // data-chave, data-ref (aaaa-mm), data-indice, data-produtor, data-fator,
  // data-codigo e data-base (caminho até a raiz do site).
  function montaBlocoResultado(raizEl) {
    var res = raizEl.querySelector("[data-demo-res]");
    var botao = raizEl.querySelector("[data-demo-copiar]");
    var status = raizEl.querySelector("[data-demo-status]");
    var caixa = raizEl.querySelector("[data-demo-texto]");
    return function mostra(d) {
      var r = calcula(d.valor, d.fator);
      var dif = r.diferenca;
      res.innerHTML = "Novo valor: <b>" + brl(r.novo) + "</b> (" + (dif < 0 ? "redução" : "aumento") + " de " + brl(dif) + ")" +
        "<br><span class=\"mut\">Fator " + fatorTxt(d.fator) + " · acumulado " + pctTxt((d.fator - 1) * 100) + "</span>";
      var txt = texto(d);
      botao.hidden = false; caixa.hidden = true; status.textContent = "";
      botao.onclick = function () { copiar(txt, botao, status, caixa); };
    };
  }

  function iniciaPaginaDoMes() {
    var form = document.querySelector("form[data-demonstrativo]");
    if (!form) return;
    var ds = form.dataset, area = form.parentNode;
    var fatorPagina = Number(ds.fator), fator = fatorPagina;
    var mostra = montaBlocoResultado(area);
    var conf = area.querySelector("[data-demo-conferencia]");
    var sha = null;
    var pedido = new URLSearchParams(location.search).get("dados");
    var pronto = (async function () {
      var atual = await versaoAtual(ds.base);
      if (pedido && /^[0-9a-f]{40}$/.test(pedido)) {
        var r = await fatorNaVersao(lerJson, pedido, ds.codigo, ds.ref);
        conf.hidden = false;
        if (r.ok) {
          fator = r.fator; sha = pedido;
          var igual = Math.abs(r.fator - fatorPagina) < 1e-12;
          conf.innerHTML = "<b>Conferência de um demonstrativo.</b> Dados do commit " + pedido.slice(0, 7) +
            ": fator <b>" + fatorTxt(r.fator) + "</b> (" + pctTxt((r.fator - 1) * 100) + ")." +
            (igual ? " É o mesmo fator desta página." :
              " Os dados foram revisados depois: o fator atual desta página é " + fatorTxt(fatorPagina) + ".") +
            " Digite o valor original para conferir o resultado.";
        } else {
          conf.innerHTML = "<b>Não foi possível carregar a versão dos dados do demonstrativo (commit " + pedido.slice(0, 7) + ").</b> " +
            (r.motivo === "competencia_indisponivel" ? "Essa versão não tem os 12 meses até " + mesTxt(ds.ref) + ". " : "") +
            "O cálculo abaixo usa o fator atual desta página, " + fatorTxt(fatorPagina) + ".";
          sha = atual;
        }
      } else sha = atual;
    })();
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      await pronto;
      var v = parseValor(form.querySelector("input").value);
      var res = area.querySelector("[data-demo-res]");
      if (v === null) {
        res.textContent = "Informe um valor entre R$ 0,01 e " + brl(VALOR_MAX) + ".";
        area.querySelector("[data-demo-copiar]").hidden = true;
        return;
      }
      mostra({ valor: v, fator: fator, indice: ds.indice, refYm: ds.ref, produtor: ds.produtor,
               link: linkConferencia(ds.chave, ds.ref, sha) });
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciaPaginaDoMes);
    else iniciaPaginaDoMes();
  }

  return {
    CASAS_FATOR: CASAS_FATOR, VALOR_MAX: VALOR_MAX, br: br, brl: brl, fatorTxt: fatorTxt, pctTxt: pctTxt,
    parseValor: parseValor, mesTxt: mesTxt, somaMeses: somaMeses, calcula: calcula,
    linkConferencia: linkConferencia, texto: texto, fatorNaVersao: fatorNaVersao,
    montaBlocoResultado: montaBlocoResultado, versaoAtual: versaoAtual, copiar: copiar,
  };
});
