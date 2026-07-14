"""
build_correcao.py — Gerador de calculadora de correção monetária entre datas.

Lê os históricos mensais já coletados por fetch.py (data/<codigo>_history.json)
e gera, em docs/correcao/, uma calculadora estática que corrige um valor entre
DUAS datas quaisquer (não apenas a janela fixa de 12 meses da reajuste), por
índice de inflação:

  - hub docs/correcao/index.html (escolhe índice + mês inicial + mês final);
  - uma página por índice (docs/correcao/<indice>/) com a calculadora já
    pré-filtrada, explicação de uso e FAQ (JSON-LD) para SEO;
  - fator de correção, percentual acumulado e memória do período;
  - links cruzados com as páginas de reajuste.

A série mensal completa de cada índice é embutida no HTML (poucos KB), então a
página é 100% estática e não faz fetch. Idempotente, só stdlib.

IMPORTANTE (ordem no workflow): rode DEPOIS de build_pages.py. Este script
FUNDE suas URLs ao docs/sitemap.xml já existente (não sobrescreve), preservando
as URLs de reajuste geradas antes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
OUT_DIR = DOCS_DIR / "correcao"

BASE_URL = "https://iosbilario.github.io/observatorio-taxas"


def goatcounter_beacon() -> str:
    """Beacon do GoatCounter a partir de `goatcounter_code` em config.yml.

    Devolve "" (nada injetado) se o código não estiver configurado ou se o
    config não puder ser lido — nunca quebra a geração das páginas.
    """
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        code = str(cfg.get("goatcounter_code", "")).strip()
    except Exception:
        return ""
    if not code:
        return ""
    return (f'<script data-goatcounter="https://{code}.goatcounter.com/count" '
            f'async src="https://gc.zgo.at/count.js"></script>')


GOATCOUNTER_BEACON = goatcounter_beacon()

# Índices de inflação usados em correção monetária / atualização de valores.
INDICES = {
    "ipca": {"codigo": 433, "nome": "IPCA",
             "uso": "atualização de valores em geral, condenações judiciais recentes e contratos de serviços"},
    "igpm": {"codigo": 189, "nome": "IGP-M",
             "uso": "contratos de aluguel e reajustes atrelados ao índice do mercado imobiliário"},
    "inpc": {"codigo": 188, "nome": "INPC",
             "uso": "correção de salários, pensões e benefícios ligados à renda das famílias"},
    "igpdi": {"codigo": 190, "nome": "IGP-DI",
              "uso": "contratos públicos, de fornecimento e correções administrativas"},
}

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

CSS = """
:root{--bg:#0b1120;--card:#0f172a;--line:#1e293b;--tx:#e2e8f0;--mut:#94a3b8;--ac:#38bdf8;--ok:#4ade80;--warn:#fbbf24}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--ac);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:1.5rem;line-height:1.3;margin:.5em 0}.crumb{color:var(--mut);font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin:16px 0}
.big{font-size:2.2rem;font-weight:700;color:var(--ac)}.big.neg{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}thead th{color:var(--mut);font-weight:600}
input,select{background:#0b1526;border:1px solid var(--line);border-radius:8px;color:var(--tx);padding:10px 12px;font-size:1rem;width:100%}
label{display:block;margin:12px 0 4px;color:var(--mut);font-size:.85rem}
button{background:var(--ac);color:#04121f;border:0;border-radius:8px;padding:12px 18px;font-size:1rem;font-weight:700;cursor:pointer;margin-top:14px;width:100%}
.res{margin-top:14px;font-size:1.15rem}.res b{color:var(--ok)}
.mut{color:var(--mut);font-size:.85rem}.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pill{display:inline-block;background:#0b1526;border:1px solid var(--line);border-radius:999px;padding:4px 12px;margin:3px;font-size:.85rem}
footer{margin-top:32px;color:var(--mut);font-size:.8rem}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
"""


def parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


def load_history(codigo: int) -> list[dict]:
    path = DATA_DIR / f"{codigo}_history.json"
    if not path.exists():
        return []
    pts = json.loads(path.read_text(encoding="utf-8"))
    pts = [{"dt": parse_date(p["data"]), "valor": float(p["valor"])} for p in pts]
    pts.sort(key=lambda p: p["dt"])
    return pts


def fmt_num(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_ano(dt: datetime) -> str:
    return f"{MESES[dt.month - 1]} de {dt.year}"


def fator_periodo(pts: list[dict], i0: int, i1: int) -> float:
    """Fator de correção aplicando as variações dos meses (i0+1 .. i1)."""
    fator = 1.0
    for k in range(i0 + 1, i1 + 1):
        fator *= 1.0 + pts[k]["valor"] / 100.0
    return fator


def serie_js(pts: list[dict]) -> list[dict]:
    """Série compacta embutida no HTML: rótulo + variação mensal."""
    return [{"label": mes_ano(p["dt"]).capitalize(), "v": p["valor"]} for p in pts]


def head(title: str, desc: str, canonical: str, jsonld: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'self'; object-src 'none'; img-src 'self' data: https://observatoriotaxas.goatcounter.com; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://gc.zgo.at; connect-src 'self' https://observatoriotaxas.goatcounter.com"/>
<meta name="referrer" content="strict-origin-when-cross-origin"/>
<script>if (top !== self) {{ try {{ top.location = self.location; }} catch (e) {{ document.documentElement.style.display = "none"; }} }}</script>
<title>{title}</title>
<meta name="description" content="{desc}"/>
<meta name="robots" content="index, follow"/>
<meta name="theme-color" content="#0b1120"/>
<link rel="canonical" href="{canonical}"/>
<meta property="og:type" content="website"/>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:site_name" content="Observatório de Taxas"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{desc}"/>
<meta property="og:url" content="{canonical}"/>
{jsonld}
<style>{CSS}</style>
{GOATCOUNTER_BEACON}
</head>
<body><div class="wrap">
<p class="crumb"><a href="{BASE_URL}/">Observatório de Taxas</a> › <a href="{BASE_URL}/correcao/">Correção monetária</a></p>
"""


FOOTER = f"""
<footer>Fonte primária: API pública do SGS/Banco Central do Brasil. Série histórica versionada e auditável no
<a href="https://github.com/iosbilario/observatorio-taxas">GitHub</a>. Conteúdo informativo; confira o índice e a
convenção de correção previstos no seu contrato ou decisão. Projeto <a href="{BASE_URL}/">Observatório de Taxas</a>, LBP Tecnologia.</footer>
</div></body></html>
"""


# JavaScript da calculadora. Placeholders __SERIES_JSON__ / __DEFAULT_KEY__ são
# substituídos por texto (evita colisão com o '%' literal do JS).
CALC_JS = """
<script>
const SERIES = __SERIES_JSON__;
const DEFAULT_KEY = __DEFAULT_KEY__;
function opt(sel,i,txt){var o=document.createElement('option');o.value=i;o.textContent=txt;sel.appendChild(o);}
function fillMeses(){
  var key = idxKey();
  var pts = SERIES[key].pts;
  var de = document.getElementById('de'), ate = document.getElementById('ate');
  var deVal = de.value, ateVal = ate.value;
  de.innerHTML=''; ate.innerHTML='';
  for(var i=0;i<pts.length;i++){opt(de,i,pts[i].label);opt(ate,i,pts[i].label);}
  // padrões: de = 12 meses antes do fim; ate = último mês disponível
  var last = pts.length-1, start = Math.max(0,last-12);
  de.value = (deVal!==''&&deVal<pts.length)?deVal:start;
  ate.value = (ateVal!==''&&ateVal<pts.length)?ateVal:last;
}
function idxKey(){
  var s=document.getElementById('indice');
  return s?s.value:DEFAULT_KEY;
}
function calc(){
  var key=idxKey(), pts=SERIES[key].pts;
  var i0=parseInt(document.getElementById('de').value,10);
  var i1=parseInt(document.getElementById('ate').value,10);
  var v=parseFloat((document.getElementById('valor').value||'').replace('.','').replace(',','.'));
  var res=document.getElementById('res');
  if(isNaN(v)){res.textContent='Informe o valor a corrigir.';return;}
  if(i1<=i0){res.textContent='O mês final deve ser posterior ao inicial.';return;}
  var fator=1.0;
  for(var k=i0+1;k<=i1;k++){fator*=1+pts[k].v/100;}
  var novo=v*fator, ac=(fator-1)*100;
  var f6=fator.toLocaleString('pt-BR',{minimumFractionDigits:6,maximumFractionDigits:6});
  res.innerHTML='Valor corrigido: <b>R$ '+novo.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+'</b>'
    +'<br><span class="mut">'+SERIES[key].nome+' acumulado no período: '+ac.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+'%'
    +' · fator '+f6+' · de '+pts[i0].label+' a '+pts[i1].label+'</span>';
}
document.addEventListener('DOMContentLoaded',function(){
  fillMeses();
  var is=document.getElementById('indice');
  if(is){is.addEventListener('change',fillMeses);}
});
</script>
"""


def calc_card(default_key: str, com_seletor: bool) -> str:
    seletor = ""
    if com_seletor:
        opts = "".join(
            f'<option value="{k}">{info["nome"]}</option>' for k, info in INDICES.items()
        )
        seletor = f'<label>Índice</label><select id="indice">{opts}</select>'
    return f"""
<div class="card">
<h2>Calcule a correção</h2>
{seletor}
<label>Valor a corrigir (R$)</label>
<input id="valor" type="text" inputmode="decimal" placeholder="1.000,00"/>
<div class="grid">
<div><label>Do mês</label><select id="de"></select></div>
<div><label>Até o mês</label><select id="ate"></select></div>
</div>
<button onclick="calc()">Corrigir valor</button>
<p class="res" id="res"></p>
<p class="mut">A correção aplica, de forma composta, a variação mensal do índice dos meses posteriores ao inicial até o final.</p>
</div>"""


def build_index_page(key: str, info: dict, pts: list[dict]) -> tuple[str, str]:
    slug = key
    url = f"{BASE_URL}/correcao/{slug}/"
    nome = info["nome"]

    last = len(pts) - 1
    start = max(0, last - 12)
    fator = fator_periodo(pts, start, last)
    ac = (fator - 1.0) * 100.0
    ref_ini, ref_fim = mes_ano(pts[start]["dt"]), mes_ano(pts[last]["dt"])
    exemplo = 1000.0 * fator

    title = f"Correção monetária pelo {nome}: atualize valores entre datas"
    desc = (f"Calculadora de correção monetária pelo {nome}: atualize um valor entre duas datas com "
            f"dados oficiais do Banco Central (SGS). Nos 12 meses até {ref_fim}, o {nome} acumulou "
            f"{fmt_num(ac)}% (fator {fmt_num(fator, 6)}).")

    faq = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question",
             "name": f"Como corrigir um valor pelo {nome} entre duas datas?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": f"Multiplique o valor pelo fator de correção do período, que é o produto composto das variações mensais do {nome} entre o mês inicial e o final. Use a calculadora acima com dados do Banco Central (SGS)."}},
            {"@type": "Question",
             "name": f"Quanto o {nome} acumulou nos 12 meses até {ref_fim}?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": f"De {ref_ini} a {ref_fim}, o {nome} acumulou {fmt_num(ac)}% (fator {fmt_num(fator, 6)}). Exemplo: R$ 1.000,00 corrigidos passam a R$ {fmt_num(exemplo)}."}},
        ],
    }, ensure_ascii=False)

    js = (CALC_JS
          .replace("__SERIES_JSON__", json.dumps({key: {"nome": nome, "pts": serie_js(pts)}}, ensure_ascii=False))
          .replace("__DEFAULT_KEY__", json.dumps(key)))

    outros = "".join(
        f'<a class="pill" href="{BASE_URL}/correcao/{k}/">{i["nome"]}</a>'
        for k, i in INDICES.items() if k != key
    )

    html = head(title, desc, url, f'<script type="application/ld+json">{faq}</script>') + f"""
<h1>Correção monetária pelo {nome}</h1>
<div class="card">
<p class="mut">{nome} acumulado nos 12 meses até {ref_fim}</p>
<p class="big">{fmt_num(ac)}%</p>
<p>Fator: <b>{fmt_num(fator, 6)}</b> · Exemplo: R$ 1.000,00 → <b>R$ {fmt_num(exemplo)}</b></p>
<p class="mut">Índice tipicamente usado em {info['uso']}.</p>
</div>
{calc_card(key, com_seletor=False)}
<div class="card"><h2>Precisa reajustar um contrato de 12 meses?</h2>
<p class="mut">Para o reajuste anual fechado (aluguel, mensalidades), veja a
<a href="{BASE_URL}/reajuste/">calculadora de reajuste</a>. Esta página corrige entre datas livres.</p></div>
<div class="card"><h2>Outros índices</h2>{outros}</div>
{js}
""" + FOOTER
    return f"correcao/{slug}/index.html", html


def build_hub(series_all: dict) -> str:
    url = f"{BASE_URL}/correcao/"
    title = "Calculadora de correção monetária entre datas: IPCA, IGP-M, INPC e IGP-DI"
    desc = ("Corrija (atualize) um valor entre duas datas pelo IPCA, IGP-M, INPC ou IGP-DI, com fator de "
            "correção, percentual acumulado e dados oficiais do Banco Central. Gratuito e sem cadastro.")

    js = (CALC_JS
          .replace("__SERIES_JSON__", json.dumps(series_all, ensure_ascii=False))
          .replace("__DEFAULT_KEY__", json.dumps(next(iter(INDICES)))))

    cards = "".join(
        f'<a class="pill" href="{BASE_URL}/correcao/{k}/">{i["nome"]}</a>' for k, i in INDICES.items()
    )

    faq = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question",
             "name": "O que é correção monetária?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "É a atualização de um valor ao longo do tempo pela variação de um índice de preços (como IPCA ou IGP-M), preservando o poder de compra entre a data original e a data atual."}},
            {"@type": "Question",
             "name": "Qual índice devo usar para corrigir um valor?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": "Depende do contrato ou da decisão: IPCA para atualização geral e muitas condenações judiciais, IGP-M em aluguéis, INPC para verbas ligadas a salário, e IGP-DI em contratos públicos e de fornecimento."}},
        ],
    }, ensure_ascii=False)

    html = head(title, desc, url, f'<script type="application/ld+json">{faq}</script>') + f"""
<h1>Correção monetária entre datas</h1>
<p>Atualize qualquer valor entre duas datas por um índice de inflação oficial, com fator de correção e
percentual acumulado. Dados coletados automaticamente do BACEN e
<a href="https://github.com/iosbilario/observatorio-taxas">versionados em aberto</a>.</p>
{calc_card(next(iter(INDICES)), com_seletor=True)}
<div class="card"><h2>Páginas por índice</h2>{cards}</div>
<div class="card"><h2>Reajuste anual de contrato</h2>
<p class="mut">Para o reajuste fechado de 12 meses (aluguel, mensalidades), use a
<a href="{BASE_URL}/reajuste/">calculadora de reajuste</a>.</p></div>
{js}
""" + FOOTER
    return html


def merge_sitemap(novas: list[str]) -> None:
    """Funde as novas URLs ao sitemap existente (não sobrescreve o de reajuste)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    sitemap = DOCS_DIR / "sitemap.xml"
    existentes: list[str] = []
    if sitemap.exists():
        existentes = re.findall(r"<loc>(.*?)</loc>", sitemap.read_text(encoding="utf-8"))
    urls: list[str] = []
    for u in existentes + novas:
        if u not in urls:
            urls.append(u)
    body = "".join(
        f"  <url><loc>{u}</loc><lastmod>{hoje}</lastmod><changefreq>daily</changefreq></url>\n"
        for u in urls
    )
    sitemap.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    series_all: dict = {}
    paths: list[str] = []
    for key, info in INDICES.items():
        pts = load_history(info["codigo"])
        if len(pts) < 2:
            continue
        series_all[key] = {"nome": info["nome"], "pts": serie_js(pts)}
        rel, html = build_index_page(key, info, pts)
        out = DOCS_DIR / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        paths.append(rel)

    (OUT_DIR / "index.html").write_text(build_hub(series_all), encoding="utf-8")

    novas = [f"{BASE_URL}/correcao/"] + [
        f"{BASE_URL}/{p.rsplit('/index.html', 1)[0]}/" for p in paths
    ]
    merge_sitemap(novas)
    print(f"Geradas {len(paths)} páginas de correção + hub; sitemap fundido ({len(novas)} URLs novas).")


if __name__ == "__main__":
    main()
