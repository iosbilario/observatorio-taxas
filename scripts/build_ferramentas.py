#!/usr/bin/env python3
"""
build_ferramentas.py — Comparador (/comparador/) e Simulador de CDI (/simulador-cdi/).

As duas páginas são estáticas. O cálculo interativo roda no navegador
(docs/calculos.js + docs/comparador.js / docs/simulador-cdi.js), lendo os
JSON de docs/data/. Este script escreve o HTML com tudo o que precisa existir
sem JavaScript: título, explicação, metodologia, fontes, perguntas e
respostas e um resultado de exemplo calculado aqui, a partir de data/:

  - comparador: CDI (4391), Selic (4390) e IPCA (433) acumulados nos últimos
    12 meses fechados comuns às três séries, com a tabela mês a mês;
  - simulador: R$ 1.000 a 90%, 100%, 110% e 120% do CDI nos últimos 12 meses
    com taxa DI diária (4389), bruto e líquido de CDB (IR e IOF).

Metodologia: desenvolvimento/METODOLOGIA-FERRAMENTAS.md. O sitemap é escrito
por render_index.py, que roda depois deste script.

    python scripts/build_ferramentas.py
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_correcao import CSS, faq_html, faq_ld  # noqa: E402
from build_indicadores import EXTRA_CSS, completos, load_history  # noqa: E402
from build_pages import FAVICON, WEBSITE_ID, fmt_num, goatcounter_beacon, jsonld_script, migalhas  # noqa: E402

DOCS = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
URL_COMP = f"{BASE_URL}/comparador/"
URL_SIM = f"{BASE_URL}/simulador-cdi/"
REGRAS_CONFERIDAS = "13/11/2026"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CSP = ("default-src 'self'; base-uri 'self'; object-src 'none'; "
       "img-src 'self' data: https://observatoriotaxas.goatcounter.com; style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; script-src 'self' https://gc.zgo.at; "
       "connect-src 'self' https://observatoriotaxas.goatcounter.com; frame-src 'self'")

FERR_CSS = """
.ctrl{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:10px}
.ctrl fieldset{border:1px solid var(--linha);border-radius:8px;margin:0;padding:.5rem .8rem .7rem}
.ctrl legend{font-family:"IBM Plex Mono",monospace;font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;color:var(--papel-45);padding:0 .3rem}
.ctrl fieldset label{display:inline-flex;align-items:center;gap:.4rem;margin:.3rem .9rem .1rem 0;text-transform:none;letter-spacing:0;font-family:"Archivo",sans-serif;font-size:.92rem;color:var(--papel)}
.ctrl input[type=checkbox],.ctrl input[type=radio]{width:auto;accent-color:var(--carimbo)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:.6rem 0 0}
.chips button{width:auto;margin:0;padding:.42rem .8rem;background:transparent;color:var(--papel-70);border:1px solid var(--linha);font-size:.8rem;border-radius:999px}
.chips button[aria-pressed=true]{background:var(--carimbo);color:var(--cofre);border-color:var(--carimbo)}
.acoes{display:flex;flex-wrap:wrap;gap:8px;margin-top:.8rem}
.acoes button{width:auto;margin:0;background:transparent;color:var(--papel);border:1px solid var(--linha);font-size:.82rem}
.resultado{font-size:1.06rem}
.resultado b{color:var(--carimbo);font-family:"IBM Plex Mono",monospace}
.aviso{color:var(--papel-45);font-size:.84rem}
.erro{color:var(--queda)}
.num{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.rolagem{overflow-x:auto}
.rolagem table{min-width:520px}
.rolagem th,.rolagem td{white-space:nowrap;overflow-wrap:normal}
.legenda{display:flex;flex-wrap:wrap;gap:14px;font-size:.84rem;color:var(--papel-70);margin:.4rem 0 0}
.legenda i{display:inline-block;width:18px;height:0;border-top:3px solid;vertical-align:middle;margin-right:6px}
svg.grafico{width:100%;height:auto;display:block}
.alta{color:var(--alta)}.queda{color:var(--queda)}
"""


# ------------------------------------------------------------------ cálculo
def mes_iso(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def mes_txt(m: str) -> str:
    a, n = m.split("-")
    return f"{MESES[int(n) - 1]} de {a}"


def mes_curto(m: str) -> str:
    a, n = m.split("-")
    return f"{MESES_ABREV[int(n) - 1]}/{a}"


def mensal_fechado(codigo: int) -> dict[str, float]:
    pts, _ = completos(codigo, load_history(codigo))
    return {mes_iso(p["dt"]): p["valor"] for p in pts}


def meses_ate(fim: str, n: int) -> list[str]:
    a, m = map(int, fim.split("-"))
    out = []
    for _ in range(n):
        out.append(f"{a}-{m:02d}")
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return out[::-1]


def acumular(taxas: list[float]) -> float:
    f = 1.0
    for t in taxas:
        f *= 1 + t / 100
    return f


def comparador_padrao() -> dict:
    series = {"cdi": mensal_fechado(4391), "selic": mensal_fechado(4390), "ipca": mensal_fechado(433)}
    fim = min(max(s) for s in series.values())
    meses = meses_ate(fim, 12)
    linhas, fat = [], {k: 1.0 for k in series}
    for m in meses:
        lin = {"mes": m}
        for k, s in series.items():
            fat[k] *= 1 + s[m] / 100
            lin[k] = s[m]
            lin["f_" + k] = fat[k]
        linhas.append(lin)
    # Mesmos meses com as taxas diárias (Selic 1178 e CDI 4389), para mostrar a
    # diferença que o arredondamento a 2 casas das séries mensais esconde.
    diaria = {}
    for k, cod in (("cdi", 4389), ("selic", 1178)):
        f = 1.0
        for p in load_history(cod):
            if meses[0] <= mes_iso(p["dt"]) <= meses[-1]:
                f *= (1 + p["valor"] / 100) ** (1 / 252)
        diaria[k] = (f - 1) * 100
    return {"de": meses[0], "ate": meses[-1], "linhas": linhas,
            "pct": {k: (fat[k] - 1) * 100 for k in series}, "diaria": diaria,
            "fechado": {k: max(s) for k, s in series.items()}}


IOF = [0, 96, 93, 90, 86, 83, 80, 76, 73, 70, 66, 63, 60, 56, 53, 50, 46, 43, 40, 36,
       33, 30, 26, 23, 20, 16, 13, 10, 6, 3]


def aliquota_ir(dias: int) -> float:
    return 22.5 if dias <= 180 else 20.0 if dias <= 360 else 17.5 if dias <= 720 else 15.0


def centavos(x: float) -> float:
    return round(x + (1e-9 if x >= 0 else -1e-9), 2)


def soma_meses(d: date, n: int) -> date:
    a, m = d.year, d.month - 1 + n
    a += m // 12
    m = m % 12 + 1
    ultimo = (date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(a, m, min(d.day, ultimo))


def simulacao_padrao() -> dict:
    di = load_history(4389)
    ultimo = di[-1]["dt"].date()
    fim = ultimo + timedelta(days=1)
    inicio = soma_meses(fim, -12)
    dias = (fim - inicio).days
    janela = [p for p in di if inicio <= p["dt"].date() < fim]
    cenarios = []
    for pct in (90, 100, 110, 120):
        saldo = 1000.0
        for p in janela:
            saldo *= 1 + pct / 100 * ((1 + p["valor"] / 100) ** (1 / 252) - 1)
        rend = saldo - 1000
        iof = centavos(rend * (IOF[dias] if dias < 30 else 0) / 100)
        ir = centavos((rend - iof) * aliquota_ir(dias) / 100)
        cenarios.append({"pct": pct, "bruto": saldo, "rend": rend, "ir": ir, "iof": iof,
                         "liquido": 1000 + rend - iof - ir})
    fdi = 1.0
    for p in janela:
        fdi *= (1 + p["valor"] / 100) ** (1 / 252)
    ipca = mensal_fechado(433)
    meses = []
    m = date(inicio.year, inicio.month, 1)
    while (m.year, m.month) < (fim.year, fim.month):
        meses.append(f"{m.year}-{m.month:02d}")
        m = soma_meses(m, 1)
    inflacao = None
    if all(x in ipca for x in meses):
        inflacao = {"de": meses[0], "ate": meses[-1], "pct": (acumular([ipca[x] for x in meses]) - 1) * 100}
    return {"inicio": inicio, "fim": fim, "ultimo": ultimo, "dias": dias, "dias_uteis": len(janela),
            "cdi_pct": (fdi - 1) * 100, "cenarios": cenarios, "aliquota_ir": aliquota_ir(dias),
            "inflacao": inflacao}


# ------------------------------------------------------------------ HTML
def e(s: str) -> str:
    return html.escape(str(s), quote=True)


def pct(v: float, casas: int = 2) -> str:
    return f"{fmt_num(v, casas)}%"


def reais(v: float) -> str:
    return f"R$ {fmt_num(v, 2)}"


def dbr(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def head(title: str, desc: str, canonical: str, jsonld: str, crumb: str, scripts: list[str]) -> str:
    tags = "\n".join(f'<script src="/{s}" defer></script>' for s in scripts)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="{CSP}"/>
<meta name="referrer" content="strict-origin-when-cross-origin"/>
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}"/>
<meta name="robots" content="index, follow, max-snippet:-1"/>
<meta name="theme-color" content="#0E1210"/>
<link rel="canonical" href="{canonical}"/>
{FAVICON}
<meta property="og:type" content="website"/>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:site_name" content="Observatório de Taxas"/>
<meta property="og:title" content="{e(title)}"/>
<meta property="og:description" content="{e(desc)}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{BASE_URL}/og-image.png"/>
{jsonld}
<style>{CSS}{EXTRA_CSS}{FERR_CSS}</style>
{tags}
{goatcounter_beacon()}
</head>
<body><a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
<!-- nav:start -->
<!-- nav:end -->
<div class="wrap">
{crumb}
<main id="conteudo">
"""


RODAPE = """
</main>
<footer>Dados: CDI calculado pela B3; Selic e taxa DI publicadas pelo Banco Central do Brasil; IPCA produzido pelo
IBGE. O Observatório obtém as séries na <a href="https://www3.bcb.gov.br/sgspub/">API pública do SGS</a> do Banco
Central e não altera os valores. Simulações e comparações são informativas, não são recomendação de investimento e
podem diferir de aplicações reais por custos, impostos e características de cada produto.
</footer>
</div></body></html>
"""


def app_ld(nome: str, url: str, desc: str) -> dict:
    return {"@context": "https://schema.org", "@type": "WebApplication", "name": nome, "url": url,
            "description": desc, "applicationCategory": "FinanceApplication", "operatingSystem": "Navegador web",
            "inLanguage": "pt-BR", "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "BRL"},
            "publisher": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"},
            "isPartOf": {"@id": WEBSITE_ID}}


def fontes_html() -> str:
    return """<section class="card" aria-labelledby="fontes-t"><h2 id="fontes-t">Fontes oficiais</h2>
<ul>
<li><a href="/indicadores/cdi/">CDI (taxa DI) anualizado</a>, série 4389 do SGS (B3), diária: <a href="/data/4389_history.json">JSON</a></li>
<li><a href="/indicadores/cdi-acumulado-no-mes/">CDI acumulado no mês</a>, série 4391 (B3): <a href="/data/4391_history.json">JSON</a></li>
<li><a href="/indicadores/selic-acumulada-no-mes/">Selic acumulada no mês</a>, série 4390 (Banco Central): <a href="/data/4390_history.json">JSON</a></li>
<li><a href="/indicadores/selic-efetiva/">Selic efetiva anualizada</a>, série 1178 (Banco Central): <a href="/data/1178_history.json">JSON</a></li>
<li><a href="/indicadores/ipca/">IPCA, variação mensal</a>, série 433 (IBGE): <a href="/data/433_history.json">JSON</a></li>
<li>Conferência: <a href="/indicadores/ipca-12-meses/">IPCA acumulado em 12 meses</a>, série 13522 (IBGE)</li>
<li>Metodologia completa: <a href="https://github.com/iosbilario/observatorio-taxas/blob/main/desenvolvimento/METODOLOGIA-FERRAMENTAS.md">METODOLOGIA-FERRAMENTAS.md</a></li>
</ul></section>"""


def pagina_comparador(c: dict) -> str:
    title = "Selic, CDI e IPCA: compare juros e inflação no Brasil"
    desc = (f"Compare Selic, CDI e IPCA acumulados em qualquer período. De {mes_curto(c['de'])} a {mes_curto(c['ate'])}: "
            f"CDI {pct(c['pct']['cdi'])}, Selic {pct(c['pct']['selic'])}, IPCA {pct(c['pct']['ipca'])}. "
            "Dados oficiais, gráfico, tabela e metodologia.")
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Comparador", URL_COMP)])
    p, d = c["pct"], c["diaria"]
    frase = (f"De {mes_txt(c['de'])} a {mes_txt(c['ate'])} (12 meses), o CDI acumulou <b>{pct(p['cdi'])}</b>, "
             f"a Selic acumulou <b>{pct(p['selic'])}</b> e o IPCA acumulou <b>{pct(p['ipca'])}</b>.")
    perguntas = [
        ("CDI rende mais que o IPCA?",
         f"Depende do período. De {mes_txt(c['de'])} a {mes_txt(c['ate'])}, o CDI acumulou {pct(p['cdi'])} e o IPCA, "
         f"{pct(p['ipca'])}. Em outros períodos a relação pode ser diferente; o comparador mostra cada um. O IPCA mede "
         "a variação de preços ao consumidor e não é uma aplicação: a comparação indica se a taxa de referência ficou "
         "acima ou abaixo da inflação, não o resultado de um investimento real."),
        ("Qual a diferença entre CDI e Selic?",
         "A Selic é a taxa dos empréstimos de um dia entre instituições com lastro em títulos públicos; a meta Selic é "
         "definida pelo Copom e a Selic efetiva é a taxa praticada no dia. O CDI (taxa DI) é a taxa média dos "
         "empréstimos de um dia entre instituições sem lastro em títulos, calculada pela B3. Na prática, o CDI anda "
         "muito perto da Selic efetiva, e as duas ficam um pouco abaixo da meta. "
         + (f"Com as taxas diárias, de {mes_txt(c['de'])} a {mes_txt(c['ate'])}, a Selic efetiva e o CDI acumularam o "
            f"mesmo: {pct(d['cdi'], 4)}." if round(d["cdi"], 4) == round(d["selic"], 4) else
            f"Com as taxas diárias, de {mes_txt(c['de'])} a {mes_txt(c['ate'])}, a Selic efetiva acumulou "
            f"{pct(d['selic'], 4)} e o CDI, {pct(d['cdi'], 4)}.")
         + " A meta Selic não entra na conta: é uma meta anual, não uma taxa acumulada."),
        ("Como comparar CDI e inflação?",
         "Acumule as duas no mesmo período, pelas competências mensais, e calcule a taxa real: "
         "(1 + CDI acumulado) ÷ (1 + IPCA acumulado) − 1. Se for positiva, a taxa de referência ficou acima da inflação "
         "no período."),
        ("O que significa CDI acumulado?",
         "É o produto das taxas de cada período: fator = (1 + taxa₁ ÷ 100) × (1 + taxa₂ ÷ 100) × …, e o acumulado é "
         "(fator − 1) × 100. Não é a soma das taxas mensais."),
        ("Por que não usar a meta Selic ou o IPCA de 12 meses?",
         "A meta Selic é uma taxa anual definida pelo Copom, não a taxa efetivamente acumulada em cada mês. O IPCA de 12 "
         "meses já é um acumulado; compô-lo de novo contaria a inflação mais de uma vez. O comparador usa a Selic e o "
         "CDI acumulados no mês e a variação mensal do IPCA."),
    ]
    jsonld = (jsonld_script(app_ld("Comparador Selic, CDI e IPCA", URL_COMP, desc)) + "\n"
              + faq_ld(URL_COMP, title, crumb_ld, perguntas) + "\n"
              + jsonld_script({"@context": "https://schema.org", **crumb_ld}))
    linhas = "".join(
        f'<tr><td>{mes_curto(l["mes"])}</td><td class="num">{pct(l["selic"])}</td><td class="num">{pct(l["cdi"])}</td>'
        f'<td class="num">{pct(l["ipca"])}</td><td class="num">{fmt_num(l["f_selic"], 6)}</td>'
        f'<td class="num">{fmt_num(l["f_cdi"], 6)}</td><td class="num">{fmt_num(l["f_ipca"], 6)}</td></tr>'
        for l in c["linhas"])
    dados = e(json.dumps({"de": c["de"], "ate": c["ate"], "fechado": c["fechado"]}, separators=(",", ":")))
    corpo = f"""<article id="comparador" data-padrao="{dados}">
<h1>Selic, CDI e IPCA: compare juros e inflação no Brasil</h1>
<p class="lead">Compare a evolução dos indicadores econômicos em períodos equivalentes, com dados oficiais, metodologia
transparente e histórico verificável.</p>
<section class="card" aria-labelledby="ctrl-t"><h2 id="ctrl-t">Período e indicadores</h2>
<form id="form-comp" class="ctrl" novalidate>
<div><label for="de">Mês inicial</label><input id="de" name="de" type="month" value="{c['de']}" min="2015-01" max="{c['ate']}"/></div>
<div><label for="ate">Mês final</label><input id="ate" name="ate" type="month" value="{c['ate']}" min="2015-01" max="{c['ate']}"/></div>
<fieldset><legend>Indicadores</legend>
<label><input type="checkbox" name="i" value="cdi" checked/> CDI</label>
<label><input type="checkbox" name="i" value="selic" checked/> Selic</label>
<label><input type="checkbox" name="i" value="ipca" checked/> IPCA</label></fieldset>
<fieldset><legend>Mostrar</legend>
<label><input type="radio" name="ver" value="pct" checked/> % acumulado</label>
<label><input type="radio" name="ver" value="reais"/> R$ 1.000 corrigidos</label></fieldset>
</form>
<div class="chips" role="group" aria-label="Períodos rápidos">
<button type="button" data-meses="12" aria-pressed="true">12 meses</button><button type="button" data-meses="24" aria-pressed="false">24 meses</button>
<button type="button" data-meses="36" aria-pressed="false">36 meses</button><button type="button" data-meses="60" aria-pressed="false">60 meses</button></div>
<div class="acoes"><button type="button" id="copiar">Copiar link desta comparação</button></div>
<noscript><p class="aviso">Os controles precisam de JavaScript. Sem ele, a página mostra os últimos 12 meses fechados, abaixo.</p></noscript>
</section>
<section class="card" aria-labelledby="res-t"><h2 id="res-t">Resultado</h2>
<p class="resultado" id="resultado" aria-live="polite">{frase}</p>
<p class="aviso">Esses números são calculados a partir das séries oficiais e podem diferir do desempenho de
investimentos reais devido a custos, impostos e características dos produtos. Selic e CDI são taxas de referência,
não aplicações disponíveis diretamente ao investidor; o IPCA mede a variação de preços.</p>
</section>
<section class="card" aria-labelledby="graf-t"><h2 id="graf-t">Gráfico</h2>
<div id="grafico" role="img" aria-label="Evolução acumulada de CDI, Selic e IPCA no período; os mesmos valores estão na tabela abaixo.">
<p class="aviso">O gráfico é desenhado com JavaScript. Os valores estão na tabela abaixo.</p></div>
<div class="legenda" id="legenda"></div>
</section>
<section class="card" aria-labelledby="tab-t"><h2 id="tab-t">Mês a mês</h2>
<div class="rolagem"><table id="tabela"><caption class="aviso" style="caption-side:bottom;text-align:left;padding-top:.6rem">Taxa de cada competência em % e fator acumulado desde o mês inicial.</caption>
<thead><tr><th scope="col">Mês</th><th scope="col">Selic</th><th scope="col">CDI</th><th scope="col">IPCA</th>
<th scope="col">Fator Selic</th><th scope="col">Fator CDI</th><th scope="col">Fator IPCA</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
<p class="aviso">Fontes: Selic acumulada no mês (SGS 4390, Banco Central), CDI acumulado no mês (SGS 4391, B3) e
IPCA (SGS 433, IBGE). As séries mensais têm 2 casas decimais; por isso o acumulado pode diferir em centésimos do
calculado com taxas diárias ou com números-índice. O mês corrente, ainda incompleto, não entra.</p>
</section>
<!-- anuncio:comparador:inicio --><!-- anuncio:comparador:fim -->
<section class="card" aria-labelledby="met-t"><h2 id="met-t">Metodologia</h2>
<p>Para cada indicador escolhido, o comparador multiplica os fatores das competências do mês inicial ao mês final,
inclusive: <span class="num">fator = Π (1 + taxa do mês ÷ 100)</span> e <span class="num">variação = (fator − 1) × 100</span>.
A composição vale porque as três séries têm a mesma natureza: taxa ou variação que vale para o próprio mês.</p>
<ul>
<li><b>Selic</b>: Selic acumulada no mês (SGS 4390), não a meta Selic, que é uma taxa anual de política monetária.</li>
<li><b>CDI</b>: CDI acumulado no mês (SGS 4391), não a taxa DI anualizada apresentada como se fosse mensal.</li>
<li><b>IPCA</b>: variação mensal (SGS 433). O IPCA de 12 meses (SGS 13522) serve só de conferência.</li>
</ul>
<p>Em “R$ 1.000 corrigidos”, cada linha mostra R$ 1.000 multiplicados pelo fator do indicador. Para o IPCA, o
número representa quanto custaria, no fim do período, o que custava R$ 1.000 no início; não é rendimento.</p>
</section>
{faq_html(perguntas)}
{fontes_html()}
<section class="card" aria-labelledby="rel-t"><h2 id="rel-t">Veja também</h2>
<p><a class="pill" href="/simulador-cdi/">Simulador de rendimento do CDI</a><a class="pill" href="/correcao/ipca/">Correção monetária pelo IPCA</a>
<a class="pill" href="/indicadores/">Todos os indicadores</a><a class="pill" href="/var.html">VAR da Economia</a></p></section>
</article>"""
    return head(title + " | Observatório de Taxas" if len(title) < 50 else title, desc, URL_COMP, jsonld, crumb_html,
                ["calculos.js", "comparador.js"]) + corpo + RODAPE


def pagina_simulador(s: dict) -> str:
    title = "Quanto rende 100% do CDI? Simulador de CDB e CDI"
    c100 = next(x for x in s["cenarios"] if x["pct"] == 100)
    c110 = next(x for x in s["cenarios"] if x["pct"] == 110)
    periodo = f"{dbr(s['inicio'])} a {dbr(s['fim'])}"
    desc = (f"Simule quanto rende R$ 1.000 a 100% do CDI: {reais(c100['bruto'])} brutos em 12 meses ({periodo}). "
            "Compare 90%, 110% e 120% do CDI, veja IR e IOF do CDB e a memória de cálculo dia a dia.")
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Simulador de CDI", URL_SIM)])
    infl = s["inflacao"]
    perguntas = [
        ("Quanto rende R$ 1.000 a 100% do CDI?",
         f"De {periodo} ({s['dias_uteis']} dias úteis), R$ 1.000 a 100% do CDI chegaram a {reais(c100['bruto'])} "
         f"brutos, rendimento de {pct(c100['rend'] / 10)}. Num CDB, o IR de {fmt_num(s['aliquota_ir'], 1)}% sobre o "
         f"rendimento deixaria {reais(c100['liquido'])}. Os valores vêm da taxa DI diária publicada e não consideram "
         "custos nem o risco do emissor."),
        ("Como calcular 110% do CDI?",
         "Aplique o percentual à taxa de cada dia útil, antes de compor: fator do dia = 1 + 1,10 × ((1 + DI ÷ 100)^(1/252) − 1). "
         f"Multiplicar o rendimento total de 100% por 1,10 dá um resultado diferente. No mesmo período, 110% do CDI "
         f"renderam {pct(c110['rend'] / 10)}, e não 1,10 × {pct(c100['rend'] / 10)} = {pct(1.1 * c100['rend'] / 10)}."),
        ("Qual a diferença entre rendimento bruto e líquido?",
         "O bruto é o saldo antes dos impostos. No CDB, pessoa física paga IR sobre o rendimento pela tabela "
         "regressiva (22,5% até 180 dias, 20% de 181 a 360, 17,5% de 361 a 720 e 15% acima de 720 dias) e IOF sobre o "
         "rendimento em resgates com menos de 30 dias."),
        ("LCI e LCA rendem o mesmo que um CDB?",
         "Não necessariamente. LCI e LCA são isentas de IR para pessoa física, mas têm prazos mínimos de carência e "
         "regras próprias. O simulador calcula o líquido só para CDB; para outros produtos, mostra o valor bruto."),
        ("CDI rende mais que a inflação?",
         (f"No período simulado, o CDI acumulou {pct(s['cdi_pct'])} e o IPCA de {mes_txt(infl['de'])} a "
          f"{mes_txt(infl['ate'])}, {pct(infl['pct'])}. " if infl else "")
         + "A taxa real é (1 + rendimento) ÷ (1 + inflação) − 1. O resultado varia conforme o período."),
    ]
    jsonld = (jsonld_script(app_ld("Simulador de rendimento do CDI", URL_SIM, desc)) + "\n"
              + faq_ld(URL_SIM, title, crumb_ld, perguntas) + "\n"
              + jsonld_script({"@context": "https://schema.org", **crumb_ld}))
    cen = "".join(
        f'<tr><td>{x["pct"]}% do CDI</td><td class="num">{reais(x["bruto"])}</td><td class="num">{reais(x["rend"])}</td>'
        f'<td class="num">{reais(x["ir"] + x["iof"])}</td><td class="num">{reais(x["liquido"])}</td></tr>'
        for x in s["cenarios"])
    dados = e(json.dumps({"ultimo": s["ultimo"].isoformat()}, separators=(",", ":")))
    hoje_max = s["fim"].isoformat()
    corpo = f"""<article id="simulador" data-padrao="{dados}">
<h1>Quanto rende 100% do CDI?</h1>
<p class="lead">Simule o rendimento de aplicações indexadas ao CDI, compare percentuais e confira a memória de cálculo.</p>
<section class="card" aria-labelledby="ctrl-t"><h2 id="ctrl-t">Simulação</h2>
<form id="form-sim" class="ctrl" novalidate>
<div><label for="valor">Valor inicial (R$)</label><input id="valor" name="valor" type="text" inputmode="decimal" value="1.000,00" autocomplete="off"/>
<div class="chips" role="group" aria-label="Valores sugeridos"><button type="button" data-valor="1000" aria-pressed="true">R$ 1.000</button><button type="button" data-valor="5000" aria-pressed="false">R$ 5.000</button><button type="button" data-valor="10000" aria-pressed="false">R$ 10.000</button></div></div>
<div><label for="percentual">Percentual do CDI (%)</label><input id="percentual" name="percentual" type="text" inputmode="decimal" value="100" autocomplete="off"/>
<div class="chips" role="group" aria-label="Percentuais sugeridos"><button type="button" data-percentual="90" aria-pressed="false">90%</button><button type="button" data-percentual="100" aria-pressed="true">100%</button><button type="button" data-percentual="110" aria-pressed="false">110%</button><button type="button" data-percentual="120" aria-pressed="false">120%</button></div></div>
<div><label for="de">Data da aplicação</label><input id="de" name="de" type="date" value="{s['inicio'].isoformat()}" min="2015-01-02" max="{hoje_max}"/></div>
<div><label for="ate">Data do resgate</label><input id="ate" name="ate" type="date" value="{s['fim'].isoformat()}" min="2015-01-03" max="{hoje_max}"/>
<div class="chips" role="group" aria-label="Períodos rápidos"><button type="button" data-periodo="6m" aria-pressed="false">6 meses</button><button type="button" data-periodo="12m" aria-pressed="true">12 meses</button><button type="button" data-periodo="24m" aria-pressed="false">24 meses</button><button type="button" data-periodo="36m" aria-pressed="false">36 meses</button><button type="button" data-periodo="60m" aria-pressed="false">60 meses</button></div></div>
<fieldset><legend>Resultado</legend>
<label><input type="radio" name="modo" value="liquido" checked/> Líquido (CDB, pessoa física)</label>
<label><input type="radio" name="modo" value="bruto"/> Bruto (sem impostos)</label></fieldset>
</form>
<div class="acoes"><button type="button" id="copiar">Copiar link desta simulação</button><button type="button" id="csv">Baixar memória de cálculo (CSV)</button></div>
<noscript><p class="aviso">A simulação precisa de JavaScript. Sem ele, a página mostra o exemplo dos últimos 12 meses, abaixo.</p></noscript>
</section>
<section class="card" aria-labelledby="res-t"><h2 id="res-t">Resultado</h2>
<div id="resultado" aria-live="polite">
<p class="resultado">R$ 1.000,00 a 100% do CDI, de {periodo}: <b>{reais(c100['bruto'])}</b> brutos e
<b>{reais(c100['liquido'])}</b> líquidos num CDB (IR de {fmt_num(s['aliquota_ir'], 1)}% sobre o rendimento).</p>
<div class="rolagem"><table><thead><tr><th scope="col">Percentual</th><th scope="col">Valor bruto</th><th scope="col">Rendimento bruto</th>
<th scope="col">IR + IOF (CDB)</th><th scope="col">Valor líquido</th></tr></thead><tbody>{cen}</tbody></table></div>
</div>
<p class="aviso">Simulação informativa com a taxa DI diária publicada. Não considera custos, risco do emissor,
garantia do FGC nem regras específicas de cada produto e não é recomendação de investimento.</p>
</section>
<section class="card" aria-labelledby="mem-t"><h2 id="mem-t">Memória de cálculo</h2>
<p class="aviso" id="mem-resumo">Um dia útil por linha: taxa DI do dia, percentual aplicado, fator, saldo anterior, rendimento e saldo.
A tabela completa aparece aqui com JavaScript e pode ser baixada em CSV.</p>
<div class="rolagem" id="memoria"></div>
</section>
<!-- anuncio:simulador:inicio --><!-- anuncio:simulador:fim -->
<section class="card" aria-labelledby="met-t"><h2 id="met-t">Metodologia</h2>
<p>O simulador usa a taxa DI diária (CDI anualizado, base 252, SGS 4389). Para cada dia útil entre a data da aplicação
(inclusive) e a do resgate (exclusive):</p>
<p class="num">fator do dia = 1 + (percentual ÷ 100) × ((1 + DI ÷ 100)^(1/252) − 1)</p>
<p>O saldo é o valor inicial multiplicado pelos fatores de todos os dias. O percentual é aplicado à taxa de cada dia
antes da composição; dias sem taxa publicada (fins de semana e feriados) não rendem e não são estimados.</p>
<p><b>Tributos do CDB (pessoa física)</b>, regras conferidas em {REGRAS_CONFERIDAS}: IR sobre o rendimento pela tabela
regressiva da Lei 11.033/2004, art. 1º (22,5% até 180 dias corridos, 20% de 181 a 360, 17,5% de 361 a 720, 15% acima
de 720); IOF sobre o rendimento em resgates com menos de 30 dias, pela tabela do Decreto 6.306/2007 (96% no 1º dia
até 3% no 29º). O IR incide sobre o rendimento menos o IOF. Cada tributo é arredondado para centavos.</p>
<p><b>Inflação e poder de compra</b>: IPCA (SGS 433) das competências do mês da aplicação ao mês anterior ao do resgate.
É uma aproximação: aplicações no meio do mês contam o mês inteiro. Sem IPCA publicado para algum desses meses, a
taxa real não é exibida.</p>
<p><b>Arredondamento</b>: o cálculo usa todas as casas e arredonda só o que é exibido. Extratos bancários podem diferir
em centavos, porque as instituições truncam fatores diários conforme regras próprias.</p>
</section>
{faq_html(perguntas)}
{fontes_html()}
<section class="card" aria-labelledby="rel-t"><h2 id="rel-t">Veja também</h2>
<p><a class="pill" href="/comparador/">Comparador Selic, CDI e IPCA</a><a class="pill" href="/indicadores/cdi/">CDI hoje</a>
<a class="pill" href="/indicadores/poupanca/">Rendimento da poupança</a><a class="pill" href="/indicadores/">Todos os indicadores</a></p></section>
</article>"""
    return head(title, desc, URL_SIM, jsonld, crumb_html, ["calculos.js", "simulador-cdi.js"]) + corpo + RODAPE


def main() -> None:
    c = comparador_padrao()
    s = simulacao_padrao()
    for slug, texto in (("comparador", pagina_comparador(c)), ("simulador-cdi", pagina_simulador(s))):
        out = DOCS / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(texto, encoding="utf-8")
    print(f"Comparador ({c['de']}..{c['ate']}) e simulador ({s['inicio']}..{s['fim']}) gerados.")


if __name__ == "__main__":
    main()
