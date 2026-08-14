/* =========================================================================
   Radar de Recomendação — motor compartilhado das quatro páginas.
   Sem framework, sem build, sem storage: estado só em memória.
   ========================================================================= */
"use strict";

var Radar = (function () {

  var BASE = "data";

  var MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun",
                   "jul", "ago", "set", "out", "nov", "dez"];
  var MES_LONGO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                   "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

  // ---------------------------------------------------------------- básicos

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function escRegex(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function semAcento(s) {
    return String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function normal(s) {
    return semAcento(String(s)).toLowerCase().trim();
  }

  function fmtDataCurta(iso) {
    var p = String(iso).split("-");
    if (p.length !== 3) return String(iso);
    return p[2] + " " + MES_CURTO[Number(p[1]) - 1] + " " + p[0];
  }

  function fmtDataLonga(iso) {
    var p = String(iso).split("-");
    if (p.length !== 3) return String(iso);
    return Number(p[2]) + " de " + MES_LONGO[Number(p[1]) - 1] + " de " + p[0];
  }

  function fmtHora(iso) {
    var m = String(iso).match(/T(\d{2}):(\d{2})/);
    return m ? m[1] + "h" + m[2] : "";
  }

  function umaCasa(n) {
    return n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function qs(chave) {
    var m = new RegExp("[?&]" + chave + "=([^&#]*)").exec(window.location.search);
    return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
  }

  // ------------------------------------------------------------------ dados
  //
  // Os JSONs em data/ são o contrato com o coletor (ver README.md). Em
  // produção eles chegam por fetch(). Aberta via file://, a página tem origem
  // opaca e o navegador bloqueia o fetch de arquivo local — nesse caso caímos
  // no bundle.js, que é um espelho derivado dos mesmos JSONs.

  var bundlePromessa = null;

  function carregarBundle() {
    if (bundlePromessa) return bundlePromessa;
    bundlePromessa = new Promise(function (resolve, reject) {
      if (window.__RADAR_BUNDLE__) { resolve(window.__RADAR_BUNDLE__); return; }
      var s = document.createElement("script");
      s.src = BASE + "/bundle.js";
      s.onload = function () {
        if (window.__RADAR_BUNDLE__) resolve(window.__RADAR_BUNDLE__);
        else reject(new Error("bundle carregado, mas vazio"));
      };
      s.onerror = function () { reject(new Error("não consegui carregar os dados")); };
      document.head.appendChild(s);
    });
    return bundlePromessa;
  }

  function pegar(rel, doBundle) {
    return fetch(BASE + "/" + rel, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error(rel + " " + r.status);
        return r.json();
      })
      .catch(function () {
        return carregarBundle().then(function (b) {
          var v = doBundle(b);
          if (!v) throw new Error("dados ausentes: " + rel);
          return v;
        });
      });
  }

  var Dados = {
    indice: function () {
      return pegar("index.json", function (b) { return b.index; });
    },
    busca: function () {
      return pegar("busca.json", function (b) { return b.busca; });
    },
    sonda: function (slug) {
      return pegar("sondas/" + slug + ".json", function (b) { return b.sondas[slug]; });
    },
    recibo: function (id) {
      return pegar("recibos/" + id + ".json", function (b) { return b.recibos[id]; });
    }
  };

  // ------------------------------------------------------- derivações
  //
  // Nada disso é armazenado: veredito, share, posição média e delta saem
  // sempre das execuções cruas. É o que torna cada número reproduzível a
  // partir dos JSONs públicos.

  function rodadasOrdenadas(sonda) {
    return (sonda.rodadas || []).slice().sort(function (a, b) { return b.numero - a.numero; });
  }

  function acharRodada(sonda, numero) {
    var rs = rodadasOrdenadas(sonda);
    if (!rs.length) return null;
    if (numero == null) return rs[0];
    for (var i = 0; i < rs.length; i++) if (rs[i].numero === Number(numero)) return rs[i];
    return rs[0];
  }

  /** Placar de uma rodada: uma linha por estabelecimento citado, ordenada. */
  function apurar(rodada, estabelecimentos) {
    var total = rodada.execucoes.length;
    var por = {};

    rodada.execucoes.forEach(function (ex, idx) {
      var vistos = {};
      ex.citados.forEach(function (c) {
        var s = c.estabelecimento;
        if (!por[s]) por[s] = { slug: s, mencoes: 0, posicoes: [], execucoes: [] };
        if (vistos[s]) return;           // uma execução conta no máximo uma vez
        vistos[s] = true;
        por[s].mencoes += 1;
        por[s].posicoes.push(c.posicao);
        por[s].execucoes.push({
          ordem: idx + 1, id: ex.id, prompt_idx: ex.prompt_idx,
          repeticao: ex.repeticao, posicao: c.posicao, recibo: ex.recibo
        });
      });
    });

    var linhas = Object.keys(por).map(function (s) {
      var d = por[s];
      var meta = (estabelecimentos && estabelecimentos[s]) || {};
      var soma = d.posicoes.reduce(function (a, b) { return a + b; }, 0);
      return {
        slug: s,
        nome: meta.nome || s,
        aliases: meta.aliases || [],
        mencoes: d.mencoes,
        total: total,
        share: total ? d.mencoes / total : 0,
        posicaoMedia: d.posicoes.length ? soma / d.posicoes.length : null,
        execucoes: d.execucoes
      };
    });

    linhas.sort(function (a, b) {
      if (b.mencoes !== a.mencoes) return b.mencoes - a.mencoes;
      return (a.posicaoMedia || 99) - (b.posicaoMedia || 99);
    });
    linhas.forEach(function (l, i) { l.posicao = i + 1; });
    return { total: total, linhas: linhas };
  }

  /** Mapa slug -> menções, para comparar rodadas. */
  function mencoesPorSlug(rodada) {
    var m = {};
    if (!rodada) return m;
    rodada.execucoes.forEach(function (ex) {
      var vistos = {};
      ex.citados.forEach(function (c) {
        if (vistos[c.estabelecimento]) return;
        vistos[c.estabelecimento] = true;
        m[c.estabelecimento] = (m[c.estabelecimento] || 0) + 1;
      });
    });
    return m;
  }

  /** entrou / saiu / subiu / caiu / estável, contra a rodada anterior. */
  function delta(atual, anterior) {
    if (anterior == null) return { tipo: "novo", diff: 0, rotulo: "primeira rodada" };
    var d = atual - anterior;
    if (anterior === 0 && atual > 0) return { tipo: "entrou", diff: d, rotulo: "entrou" };
    if (anterior > 0 && atual === 0) return { tipo: "saiu", diff: d, rotulo: "saiu" };
    if (d > 0) return { tipo: "subiu", diff: d, rotulo: "subiu " + d };
    if (d < 0) return { tipo: "caiu", diff: d, rotulo: "caiu " + Math.abs(d) };
    return { tipo: "igual", diff: 0, rotulo: "estável" };
  }

  // ------------------------------------------------------------- destaque
  //
  // Marca nome e apelidos na resposta bruta. O casamento ignora acento e
  // caixa, mas o texto exibido continua sendo o texto cru — por isso o mapa
  // de índices entre a versão normalizada e a original.

  function destacar(texto, termos) {
    var alvos = (termos || []).filter(Boolean).slice().sort(function (a, b) {
      return b.length - a.length;
    });
    if (!alvos.length) return esc(texto);

    var norm = "";
    var mapa = [];
    for (var i = 0; i < texto.length; i++) {
      var conv = semAcento(texto[i]).toLowerCase();
      for (var k = 0; k < conv.length; k++) { norm += conv[k]; mapa.push(i); }
    }
    mapa.push(texto.length);

    var re = new RegExp(alvos.map(function (t) { return escRegex(normal(t)); }).join("|"), "g");
    var saida = "";
    var cursor = 0;
    var m;
    while ((m = re.exec(norm)) !== null) {
      if (m[0].length === 0) { re.lastIndex++; continue; }
      var ini = mapa[m.index];
      var fim = mapa[m.index + m[0].length];
      if (ini < cursor) continue;
      saida += esc(texto.slice(cursor, ini));
      saida += "<mark>" + esc(texto.slice(ini, fim)) + "</mark>";
      cursor = fim;
    }
    saida += esc(texto.slice(cursor));
    return saida;
  }

  // ------------------------------------------------------------------ blips
  //
  // A assinatura do produto: um quadradinho por execução da rodada. Aceso =
  // citado naquela execução, e clicável, porque abre o recibo. Apagado = não
  // citado, e inerte. O <span> apagado fica fora da árvore de acessibilidade
  // (o grupo já anuncia "citado em N de M"); só os acesos são navegáveis.

  function blipsHTML(linha, classeExtra) {
    var porOrdem = {};
    linha.execucoes.forEach(function (e) { porOrdem[e.ordem] = e; });

    var partes = [];
    for (var i = 1; i <= linha.total; i++) {
      var e = porOrdem[i];
      if (!e) {
        partes.push('<span class="blip" aria-hidden="true"></span>');
        continue;
      }
      var rot = "execução " + i + ", prompt " + (e.prompt_idx + 1) +
                ", citado na posição " + e.posicao + ", abrir recibo";
      partes.push(
        '<button type="button" class="blip" data-recibo="' + esc(e.id) + '"' +
        ' data-estab="' + esc(linha.slug) + '" aria-label="' + esc(rot) + '"></button>'
      );
    }

    var resumo = linha.nome + ": citado em " + linha.mencoes + " de " + linha.total + " execuções";
    // --n dimensiona a barra para caber numa fileira só; no mobile o CSS
    // solta esse mínimo e deixa quebrar em duas.
    return '<div class="blips' + (classeExtra ? " " + classeExtra : "") + '"' +
           ' role="group" style="--n:' + linha.total + '"' +
           ' aria-label="' + esc(resumo) + '">' + partes.join("") + "</div>";
  }

  /** Liga a delegação de clique dos blips e da lista de recibos. */
  function ligarRecibos(raiz, estabelecimentos) {
    raiz.addEventListener("click", function (ev) {
      var alvo = ev.target.closest("[data-recibo]");
      if (!alvo) return;
      var slug = alvo.getAttribute("data-estab");
      var meta = estabelecimentos[slug] || {};
      var termos = [meta.nome].concat(meta.aliases || []);
      abrirRecibo(alvo.getAttribute("data-recibo"), termos, alvo);
    });
  }

  // ----------------------------------------------------------- painel recibo

  var dlg = null;

  function garantirDialogo() {
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.className = "recibo";
    dlg.setAttribute("aria-labelledby", "recibo-titulo");
    dlg.innerHTML = '<div class="recibo-corpo" id="recibo-corpo"></div>';
    document.body.appendChild(dlg);
    dlg.addEventListener("click", function (ev) {
      if (ev.target === dlg) dlg.close();     // clique no backdrop
      if (ev.target.closest(".recibo-fechar")) dlg.close();
    });
    return dlg;
  }

  function abrirRecibo(id, termos, origem) {
    var d = garantirDialogo();
    var corpo = d.querySelector(".recibo-corpo");
    corpo.innerHTML = '<p class="recibo-nota">Abrindo recibo ' + esc(id) + '…</p>';
    if (!d.open) d.showModal();

    d.addEventListener("close", function devolveFoco() {
      d.removeEventListener("close", devolveFoco);
      if (origem && origem.focus) origem.focus();
    });

    Dados.recibo(id).then(function (r) {
      corpo.innerHTML =
        '<div class="recibo-topo">' +
          '<h2 id="recibo-titulo">Recibo · ' + esc(r.id) + '</h2>' +
          '<button type="button" class="recibo-fechar">fechar</button>' +
        '</div>' +
        '<dl class="recibo-meta">' +
          '<div><dt>Quando</dt><dd>' + esc(fmtDataLonga(String(r.quando).slice(0, 10))) +
            ", " + esc(fmtHora(r.quando)) + '</dd></div>' +
          '<div><dt>Modelo</dt><dd>' + esc(r.modelo) + '</dd></div>' +
          '<div><dt>Pergunta</dt><dd>' + esc(r.prompt) + '</dd></div>' +
        '</dl>' +
        '<div class="recibo-resposta">' + destacar(r.resposta_bruta, termos) + '</div>' +
        fontesHTML(r.fontes_citadas) +
        (r.demonstracao
          ? '<p class="recibo-nota">Rodada de demonstração: esta resposta foi ' +
            'gerada para a fixture do produto, não coletada de um modelo real. ' +
            'Os endereços em exemplo.invalid são deliberadamente inválidos.</p>'
          : "");
      var fechar = corpo.querySelector(".recibo-fechar");
      if (fechar) fechar.focus();
    }).catch(function (e) {
      corpo.innerHTML =
        '<div class="recibo-topo"><h2 id="recibo-titulo">Recibo indisponível</h2>' +
        '<button type="button" class="recibo-fechar">fechar</button></div>' +
        '<p class="recibo-nota">' + esc(e.message) + "</p>";
    });
  }

  function fontesHTML(fontes) {
    if (!fontes || !fontes.length) return "";
    return '<div class="recibo-fontes"><p>Fontes citadas na resposta</p><ul>' +
      fontes.map(function (f) {
        if (typeof f === "string") return "<li>" + esc(f) + "</li>";
        return '<li><a href="' + esc(f.url) + '" target="_blank" rel="noopener noreferrer nofollow">' +
               esc(f.titulo || f.url) + "</a></li>";
      }).join("") + "</ul></div>";
  }

  // ---------------------------------------------------------------- gráfico
  //
  // SVG à mão em vez de Chart.js: as páginas públicas deste site não carregam
  // CDN (a CSP é script-src 'self') e precisam funcionar abertas do disco.

  function grafico(alvo, sonda, quantos) {
    var rs = rodadasOrdenadas(sonda).slice().reverse();   // cronológico
    if (rs.length < 2) { alvo.hidden = true; return; }

    var atual = apurar(rs[rs.length - 1], sonda.estabelecimentos);
    var top = atual.linhas.slice(0, quantos || 5);
    var mapas = rs.map(mencoesPorSlug);
    var totais = rs.map(function (r) { return r.execucoes.length; });

    var W = 760, H = 240, ml = 42, mr = 150, mt = 16, mb = 30;
    var iw = W - ml - mr, ih = H - mt - mb;
    var maxShare = 1;

    function x(i) { return ml + (rs.length === 1 ? iw / 2 : (i / (rs.length - 1)) * iw); }
    function y(v) { return mt + ih - (v / maxShare) * ih; }

    var cores = ["var(--fosforo)", "var(--eco)", "#9AA4B0", "#6E7885", "#525C68"];
    var svg = [];

    svg.push('<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' +
      esc("Evolução do share de menções dos " + top.length +
          " primeiros ao longo de " + rs.length + " rodadas") + '">');

    [0, 0.5, 1].forEach(function (v) {
      svg.push('<line class="eixo" x1="' + ml + '" y1="' + y(v) + '" x2="' + (ml + iw) +
               '" y2="' + y(v) + '" />');
      svg.push('<text x="' + (ml - 8) + '" y="' + (y(v) + 4) + '" text-anchor="end">' +
               Math.round(v * 100) + "%</text>");
    });

    rs.forEach(function (r, i) {
      svg.push('<text x="' + x(i) + '" y="' + (H - 8) + '" text-anchor="middle">R' +
               r.numero + "</text>");
    });

    top.forEach(function (l, k) {
      var pts = rs.map(function (r, i) {
        var v = (mapas[i][l.slug] || 0) / (totais[i] || 1);
        return { x: x(i), y: y(v), v: v };
      });
      var d = pts.map(function (p, i) {
        return (i ? "L" : "M") + p.x.toFixed(1) + " " + p.y.toFixed(1);
      }).join(" ");
      svg.push('<path class="serie" d="' + d + '" stroke="' + cores[k % cores.length] + '" />');
      var ult = pts[pts.length - 1];
      svg.push('<circle class="marca-pt" cx="' + ult.x.toFixed(1) + '" cy="' + ult.y.toFixed(1) +
               '" r="3" fill="' + cores[k % cores.length] + '" />');
      var curto = l.nome.length > 20 ? l.nome.slice(0, 19) + "…" : l.nome;
      svg.push('<text x="' + (ult.x + 10) + '" y="' + (ult.y + 4) + '" fill="' +
               cores[k % cores.length] + '">' + esc(curto) + "</text>");
    });

    svg.push("</svg>");
    alvo.innerHTML = svg.join("");
  }

  // ------------------------------------------------------- captura de e-mail

  function ligarAlerta(form) {
    if (!form) return;
    var campo = form.querySelector('input[type="email"]');
    var aviso = form.parentNode.querySelector(".aviso");

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var valor = (campo.value || "").trim();
      var valido = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(valor);

      if (!valido) {
        aviso.textContent = "Endereço inválido. Confira e tente de novo.";
        aviso.className = "aviso erro";
        campo.focus();
        return;
      }

      // ---------------------------------------------------------------
      // AQUI ENTRA O ENDPOINT REAL de captura de e-mail. Enquanto ele não
      // existe, a confirmação é só em memória: nada sai do navegador e
      // nada é persistido (sem localStorage, por decisão de projeto).
      // ---------------------------------------------------------------
      aviso.textContent = "Anotado: " + valor + ". Você recebe o placar quando a " +
                          "próxima rodada for apurada.";
      aviso.className = "aviso ok";
      campo.value = "";
      campo.disabled = true;
      form.querySelector("button").disabled = true;
    });
  }

  // ---------------------------------------------------------------- rodapé

  function anoRodape() {
    var el = document.getElementById("ano");
    if (el) el.textContent = new Date().getFullYear();
  }

  function erroNa(el, msg) {
    if (!el) return;
    el.hidden = false;
    el.className = "estado estado--erro";
    el.textContent = msg;
  }

  return {
    esc: esc, normal: normal, semAcento: semAcento,
    fmtDataCurta: fmtDataCurta, fmtDataLonga: fmtDataLonga, umaCasa: umaCasa,
    qs: qs,
    Dados: Dados,
    rodadasOrdenadas: rodadasOrdenadas, acharRodada: acharRodada,
    apurar: apurar, mencoesPorSlug: mencoesPorSlug, delta: delta,
    destacar: destacar, blipsHTML: blipsHTML, ligarRecibos: ligarRecibos,
    abrirRecibo: abrirRecibo, grafico: grafico,
    ligarAlerta: ligarAlerta, anoRodape: anoRodape, erroNa: erroNa
  };
})();

document.addEventListener("DOMContentLoaded", Radar.anoRodape);
