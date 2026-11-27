/* admin.js — Observatório de Acessos (/admin/).

   Lê só /data/stats.json, gravado por scripts/fetch_stats.py a cada coleta, e
   desenha tudo com SVG e CSS do próprio site: sem biblioteca externa, cores
   pelas variáveis do tema (claro e escuro). Campos que um stats.json antigo
   ainda não tem aparecem como "a partir da próxima coleta". */
(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;
  var NS = "http://www.w3.org/2000/svg";
  var IDX = ["IPCA", "IGP-M", "INPC", "IGP-DI"];

  function fmt(n) { return Number(n || 0).toLocaleString("pt-BR"); }
  function pct(n) { return n.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%"; }
  function el(tag, txt, cls) { var e = document.createElement(tag); if (txt != null) e.textContent = txt; if (cls) e.className = cls; return e; }
  function svg(tag, at) { var e = document.createElementNS(NS, tag); for (var k in at) e.setAttribute(k, at[k]); return e; }
  function diaMes(iso) { var p = String(iso).slice(0, 10).split("-"); return p[2] + "/" + p[1]; }
  function caminho(p) {
    var s = String(p || "/").replace(/^\/observatorio-taxas/, "");
    return s === "" || s === "/" ? "/ (página inicial)" : s;
  }
  function card(titulo, nota) {
    var c = el("section", null, "card"); c.appendChild(el("h2", titulo));
    if (nota) c.appendChild(el("p", nota, "mut"));
    return c;
  }
  function semDados(c) { c.appendChild(el("p", "Disponível a partir da próxima coleta.", "vazio")); return c; }

  // Barras verticais: valores [{rotulo, n}], com rótulos esparsos no eixo.
  function barras(pontos, opc) {
    opc = opc || {};
    var W = 720, H = 200, M = { l: 36, r: 8, t: 10, b: 24 };
    var mx = Math.max.apply(null, pontos.map(function (p) { return p.n; }).concat([1]));
    var g = svg("svg", { viewBox: "0 0 " + W + " " + H, class: "grafico", role: "img", "aria-label": opc.rotulo || "" });
    [0, mx / 2, mx].forEach(function (v) {
      var y = M.t + (H - M.t - M.b) * (1 - v / mx);
      g.appendChild(svg("line", { x1: M.l, x2: W - M.r, y1: y, y2: y, class: "linha-g" }));
      var t = svg("text", { x: M.l - 6, y: y + 4, "text-anchor": "end" }); t.textContent = fmt(Math.round(v)); g.appendChild(t);
    });
    var bw = (W - M.l - M.r) / pontos.length;
    var media = pontos.reduce(function (a, p) { return a + p.n; }, 0) / (pontos.length || 1);
    pontos.forEach(function (p, i) {
      var h = (H - M.t - M.b) * p.n / mx, x = M.l + i * bw;
      var r = svg("rect", { x: (x + bw * 0.15).toFixed(1), y: (H - M.b - h).toFixed(1), width: (bw * 0.7).toFixed(1), height: Math.max(h, p.n ? 1 : 0).toFixed(1),
                            class: "barra" + (opc.destaque != null && i !== opc.destaque ? " fraca" : "") });
      var tt = svg("title", {}); tt.textContent = p.rotulo + ": " + fmt(p.n); r.appendChild(tt); g.appendChild(r);
      if (opc.cada && i % opc.cada === 0) {
        var t = svg("text", { x: (x + bw / 2).toFixed(1), y: H - 6, "text-anchor": "middle" }); t.textContent = p.curto || p.rotulo; g.appendChild(t);
      }
    });
    // Linha vermelha pontilhada com a média do período, por cima das barras.
    if (pontos.length) {
      var ym = (M.t + (H - M.t - M.b) * (1 - media / mx)).toFixed(1);
      var lm = svg("line", { x1: M.l, x2: W - M.r, y1: ym, y2: ym, class: "media" });
      var tm = svg("title", {}); tm.textContent = "Média: " + fmtMedia(media); lm.appendChild(tm); g.appendChild(lm);
      var rt = svg("text", { x: W - M.r, y: (ym - 5).toFixed(1), "text-anchor": "end", class: "media-t" }); rt.textContent = "média " + fmtMedia(media); g.appendChild(rt);
    }
    var fig = el("div"); fig.appendChild(g);
    var lg = el("p", null, "legenda-media"); lg.appendChild(el("i")); lg.appendChild(document.createTextNode((opc.media || "Média do período") + ": " + fmtMedia(media)));
    fig.appendChild(lg);
    return fig;
  }
  function fmtMedia(n) { return n.toLocaleString("pt-BR", { maximumFractionDigits: 1 }); }

  // Lista com barra proporcional: [{nome, acessos}].
  // total = denominador do percentual; escala = valor que enche a barra.
  function listaBarras(itens, total, escala) {
    var ul = el("ul", null, "lista-barras");
    var mx = escala || Math.max.apply(null, itens.map(function (i) { return i.acessos; }).concat([1]));
    itens.forEach(function (i) {
      var li = el("li"); li.appendChild(el("span", i.nome, "nome"));
      li.appendChild(el("span", fmt(i.acessos) + (total ? " · " + pct(100 * i.acessos / total) : ""), "n"));
      var tr = el("span", null, "trilho"), b = el("i"); b.style.width = (100 * i.acessos / mx).toFixed(1) + "%"; tr.appendChild(b);
      li.appendChild(tr); ul.appendChild(li);
    });
    return ul;
  }

  function kpi(k, v, d, dcls) {
    var c = el("div", null, "kpi"); c.appendChild(el("div", k, "k")); c.appendChild(el("div", v, "v"));
    if (d) c.appendChild(el("div", d, "d" + (dcls ? " " + dcls : ""))); return c;
  }

  function render(s) {
    app.textContent = "";
    var t = s.totais || {}, m30 = t.ultimos_30d || {}, ant = t["30d_anteriores"] || {}, tudo = t.all_time || {};
    var velhos = s.blocos_da_coleta_anterior || [];
    if (velhos.length) app.appendChild(el("p", "Nesta coleta a API do GoatCounter não respondeu a " + velhos.length +
      (velhos.length === 1 ? " bloco" : " blocos") + " (" + velhos.join(", ") + "); eles mostram os números da coleta anterior.", "aviso"));
    if (s.gerado_em_fmt) document.getElementById("coleta").textContent =
      "Última coleta: " + s.gerado_em_fmt + " (horário de Brasília). Dados agregados do GoatCounter, coletados a cada 6 horas pelo mesmo robô das séries.";

    // Números principais
    var k = el("div", null, "kpis");
    var varTxt = null, varCls = null;
    if (ant.visitantes) {
      var v = 100 * (m30.visitantes - ant.visitantes) / ant.visitantes;
      varTxt = (v >= 0 ? "▲ +" : "▼ −") + pct(Math.abs(v)) + " ante os 30 dias anteriores"; varCls = v >= 0 ? "sobe" : "cai";
    } else varTxt = "comparação a partir da próxima coleta";
    k.appendChild(kpi("Visitantes em 30 dias", fmt(m30.visitantes), varTxt, varCls));
    k.appendChild(kpi("Visitas a páginas em 30 dias", fmt(m30.acessos), "visitantes somados página a página"));
    var uh = s.ultima_hora;
    k.appendChild(kpi("Última hora registrada", uh ? fmt(uh.acessos) : "—",
      uh ? "visitantes das " + uh.hora.slice(11, 13) + "h às " + uh.hora.slice(11, 13) + "h59 de " + diaMes(uh.hora) : "a partir da próxima coleta"));
    k.appendChild(kpi("Visitantes desde o início", fmt(tudo.visitantes), fmt(tudo.acessos) + " visitas a páginas"));
    app.appendChild(k);

    // Últimas 48 horas
    var c48 = card("Últimas 48 horas", "Visitantes por hora até a última hora cheia antes da coleta. Não é \u201conline agora\u201d: o GoatCounter agrupa por hora e a coleta roda a cada 6 horas.");
    var h48 = s.ultimas_48h || [];
    if (h48.length) c48.appendChild(barras(h48.map(function (p) { return { rotulo: diaMes(p.hora) + " " + p.hora.slice(11, 13) + "h", curto: p.hora.slice(11, 13) + "h", n: p.acessos }; }),
      { cada: 6, rotulo: "Visitantes por hora nas últimas 48 horas", media: "Média por hora nas 48 horas" }));
    else semDados(c48);
    app.appendChild(c48);

    // Por dia
    var cd = card("Por dia, nos últimos 30 dias");
    var sd = s.serie_diaria || [];
    if (sd.length) {
      var soma = sd.reduce(function (a, p) { return a + p.acessos; }, 0), melhor = sd.reduce(function (a, p) { return p.acessos > a.acessos ? p : a; }, sd[0]);
      cd.appendChild(el("p", "Média de " + fmt(Math.round(soma / sd.length)) + " visitantes por dia. Maior dia: " + diaMes(melhor.data) + ", com " + fmt(melhor.acessos) + ".", "mut"));
      cd.appendChild(barras(sd.map(function (p) { return { rotulo: diaMes(p.data), n: p.acessos }; }), { cada: 5, rotulo: "Visitantes por dia nos últimos 30 dias", media: "Média por dia nos 30 dias" }));
    } else semDados(cd);
    app.appendChild(cd);

    // Horário de pico
    var cp = card("Horário de pico");
    var mh = s.media_por_hora_do_dia || [];
    if (mh.length === 24 && mh.some(function (x) { return x > 0; })) {
      var pico = mh.indexOf(Math.max.apply(null, mh));
      cp.appendChild(el("p", "Em média, o horário com mais visitantes é das " + pico + "h às " + pico + "h59 (horário de Brasília), com " +
        mh[pico].toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " por hora.", "mut"));
      cp.appendChild(barras(mh.map(function (n, h) { return { rotulo: h + "h", n: n }; }), { cada: 3, destaque: pico, rotulo: "Média de visitantes por hora do dia", media: "Média das 24 horas" }));
    } else semDados(cp);
    app.appendChild(cp);

    // Seções e páginas
    var duas = el("div", null, "duas");
    var cs = card("Por seção do site", "Visitas a páginas nos últimos 30 dias.");
    if ((s.secoes_30d || []).length) cs.appendChild(listaBarras(s.secoes_30d.map(function (x) { return { nome: x.secao, acessos: x.acessos }; }), m30.acessos));
    else semDados(cs);
    duas.appendChild(cs);
    var ct = card("Páginas mais vistas", "Últimos 30 dias.");
    var top = s.top_paginas_30d || s.top_paginas || [];
    if (top.length) ct.appendChild(listaBarras(top.slice(0, 10).map(function (h) { return { nome: caminho(h.path), acessos: h.count }; })));
    else semDados(ct);
    duas.appendChild(ct);
    app.appendChild(duas);

    // Funis: página de entrada → convite → ferramenta → cálculo, todos na
    // mesma janela (desde o início da medição dos eventos).
    var fu = s.funis, fs = fu ? (fu.caminhos || []) : (s.funis_30d || []);
    var desde = fu && fu.desde ? diaMes(fu.desde) + "/" + fu.desde.slice(0, 4) : null;
    var cf = card("Da consulta à ferramenta", (desde ? "Visitantes de cada etapa desde " + desde + ", quando começou a medição dos cliques e cálculos: visitas, cliques e cálculos na mesma janela. "
                                                     : "Visitantes de cada etapa nos últimos 30 dias. ") +
      "Cada etapa é contada separadamente por página ou evento, então não é taxa de conversão: quem calcula pode ter chegado à ferramenta por outro caminho.");
    if (fs.length) {
      var df = el("div", null, "duas");
      fs.forEach(function (f) {
        var bloco = el("div"); bloco.appendChild(el("h3", f.nome));
        var ol = el("ol", null, "funil");
        f.etapas.forEach(function (e) {
          var li = el("li"); li.appendChild(el("span", e.rotulo, "nome")); li.appendChild(el("span", fmt(e.visitantes), "n"));
          if (e.tipo === "evento") li.className = "evento";
          ol.appendChild(li);
        });
        bloco.appendChild(ol); df.appendChild(bloco);
      });
      cf.appendChild(df);
      if (!fu) cf.appendChild(el("p", "Formato antigo do stats.json: visitas de 30 dias e eventos desde a medição, em janelas diferentes.", "aviso"));
      else if (!fu.completo) cf.appendChild(el("p", "A API devolveu só parte das páginas da janela; etapas com poucas visitas podem aparecer abaixo do real.", "aviso"));
    } else semDados(cf);
    app.appendChild(cf);

    // Origem dos acessos: de fora, sem origem e dentro do site, separados.
    var o = s.origens_30d, co = card("De onde vêm");
    if (o && o.totais) {
      var den = o.denominador || 0, tt = o.totais;
      co.appendChild(el("p", "Percentuais sobre os " + fmt(den) + " visitantes dos últimos 30 dias.", "mut"));
      co.appendChild(listaBarras([{ nome: "Vieram de outros sites e buscas", acessos: tt.externo },
                                  { nome: "Acesso direto ou sem origem", acessos: tt.direto },
                                  { nome: "Navegação dentro do Observatório", acessos: tt.interno }], den, den));
      co.appendChild(el("h3", "Sites e buscas"));
      var ext = (o.externas || []).slice();
      if (o.completo && o.outros_externos > 0) ext.push({ nome: "Outros sites", acessos: o.outros_externos });
      if (ext.length) co.appendChild(listaBarras(ext, den, ext[0].acessos));
      else co.appendChild(el("p", "Nenhum visitante de outros sites no período.", "vazio"));
      if (!o.completo) co.appendChild(el("p", "A API devolveu só parte das origens; os totais acima podem estar abaixo do real e \u201cOutros\u201d não é mostrado.", "aviso"));
    } else {
      var antigos = (s.detalhes_30d || {}).origens || [];
      if (antigos.length) { co.appendChild(el("p", "Ranking sem separar navegação interna (formato antigo do stats.json).", "aviso")); co.appendChild(listaBarras(antigos)); }
      else semDados(co);
    }

    // Aparelhos e lugares, sobre o total de visitantes da janela
    var det = s.detalhes_30d || {}, den30 = m30.visitantes || 0;
    var blocos = [["paises", "Países"], ["telas", "Tamanho de tela"], ["navegadores", "Navegadores"], ["sistemas", "Sistemas"],
                  ["campanhas", "Campanhas (utm_campaign)"]];
    var d2 = el("div", null, "duas");
    d2.appendChild(co);
    blocos.forEach(function (b) {
      var c = card(b[1], den30 ? "Percentuais sobre os " + fmt(den30) + " visitantes dos 30 dias. Mostra os 10 primeiros." : null);
      var itens = det[b[0]] || [];
      if (itens.length) c.appendChild(listaBarras(itens, den30));
      else semDados(c);
      d2.appendChild(c);
    });
    app.appendChild(d2);

    // Reajuste e correção por índice (desde o início)
    var g = s.grupos || {}, cr = card("Reajuste e correção por índice", "Visitas a páginas desde o início da contagem.");
    var tb = el("table"), th = el("thead"), tr = el("tr");
    ["Recurso", "Visitas"].forEach(function (x) { var h = el("th", x); h.scope = "col"; tr.appendChild(h); });
    th.appendChild(tr); tb.appendChild(th);
    var bd = el("tbody");
    ["Reajuste", "Correção"].forEach(function (nome) {
      var gr = g[nome] || { acessos: 0, sub: {} };
      var r = el("tr"); r.appendChild(el("td", nome)); r.appendChild(el("td", fmt(gr.acessos))); bd.appendChild(r);
      IDX.forEach(function (i) {
        if (!gr.sub || !(i in gr.sub)) return;
        var rs = el("tr", null, "sub"); rs.appendChild(el("td", i)); rs.appendChild(el("td", fmt(gr.sub[i]))); bd.appendChild(rs);
      });
    });
    tb.appendChild(bd); cr.appendChild(tb); app.appendChild(cr);
  }

  fetch("../data/stats.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (s) {
      var tem = s && s.totais && ((s.totais.all_time || {}).visitantes || (s.serie_diaria || []).length);
      if (!tem) { app.textContent = ""; app.appendChild(el("p", "Ainda coletando: volte depois da primeira execução do robô.", "vazio")); return; }
      render(s);
    })
    .catch(function () { app.textContent = ""; app.appendChild(el("p", "Não foi possível ler stats.json agora.", "vazio")); });
})();
