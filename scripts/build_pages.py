"""
build_pages.py — Gerador de páginas programáticas de reajuste contratual.

Lê os históricos mensais já coletados por fetch.py (data/<codigo>_history.json)
e gera, em docs/reajuste/, uma página estática por índice+mês com:

  - acumulado 12 meses (composto) e fator de reajuste;
  - memória de cálculo (tabela dos 12 meses, com fonte BACEN/SGS);
  - calculadora embutida (valor atual -> valor reajustado);
  - JSON-LD (FAQPage) para SEO;
  - links cruzados entre índices e meses.

Também gera o hub docs/reajuste/index.html (calculadora geral) e reescreve
docs/sitemap.xml com todas as URLs.

Idempotente e sem dependência externa além do stdlib. Roda depois do fetch
no workflow (ver .github/workflows/monitor.yml).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
OUT_DIR = DOCS_DIR / "reajuste"

BASE_URL = "https://observatoriodetaxas.tec.br"


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

# Formulário de captura de e-mail ("me avise quando o índice sair").
# Deixe vazio para ocultar o bloco. Ex.: "https://formsubmit.co/SEU_ID"
EMAIL_FORM_ACTION = ""

# Índices usados em reajuste de contratos (aluguel, serviços, mensalidades).
INDICES = {
    "ipca": {"codigo": 433, "nome": "IPCA", "uso": "contratos de serviços, mensalidades e aluguéis mais recentes"},
    "igpm": {"codigo": 189, "nome": "IGP-M", "uso": "contratos de aluguel (índice historicamente padrão do mercado imobiliário)"},
    "inpc": {"codigo": 188, "nome": "INPC", "uso": "dissídios, pensões e contratos atrelados à renda de famílias de menor faixa"},
    "igpdi": {"codigo": 190, "nome": "IGP-DI", "uso": "contratos públicos e de fornecimento"},
}

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]

# Identidade visual do site: sala-cofre (#0E1210), papel-moeda (#E9E6DC), carimbo
# dourado (#D9B54A); Fraunces (serifa de display), Archivo (texto), IBM Plex Mono
# (rótulos). Mesmos tokens de docs/index.html — a página de reajuste é uma
# extensão da landing, não um painel à parte.
CSS = """
/* fontes self-hosted (subset latin, SIL OFL) — ver /fonts/LICENSE.txt */
@font-face{font-family:'Fraunces';font-style:normal;font-weight:500 700;font-display:swap;src:url(/fonts/fraunces.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:'Archivo';font-style:normal;font-weight:400 600;font-display:swap;src:url(/fonts/archivo.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:400;font-display:swap;src:url(/fonts/ibmplexmono-400.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:500;font-display:swap;src:url(/fonts/ibmplexmono-500.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:600;font-display:swap;src:url(/fonts/ibmplexmono-600.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
:root{--cofre:#0E1210;--papel:#E9E6DC;--carimbo:#D9B54A;--alta:#3FD68F;--queda:#E4574F;--neutro:#5A625D;--papel-70:rgba(233,230,220,.70);--papel-45:rgba(233,230,220,.55);--linha:rgba(233,230,220,.14);--campo:#0d1210;--maxw:860px;color-scheme:dark}
*{box-sizing:border-box}
/* Foco visível e consistente (WCAG 2.4.7) + link "pular para o conteúdo" */
:focus-visible{outline:2px solid var(--carimbo);outline-offset:2px}
.skip-link{position:absolute;left:-9999px;top:0;z-index:100;font-family:"IBM Plex Mono",monospace;font-size:.82rem;font-weight:600;color:var(--cofre);background:var(--carimbo);padding:.6rem 1rem;border-radius:0 0 8px 0;text-decoration:none;border-bottom:0}
.skip-link:focus{left:0;outline:2px solid var(--papel);outline-offset:-4px}
body{margin:0;background:var(--cofre);color:var(--papel);font-family:"Archivo",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:var(--maxw);margin:0 auto;padding:24px clamp(1rem,4vw,2rem) 64px}
a{color:var(--carimbo);text-decoration:none;border-bottom:1px solid rgba(217,181,74,.4)}a:hover{border-bottom-color:var(--carimbo)}
::selection{background:rgba(217,181,74,.28)}
.crumb{font-family:"IBM Plex Mono",monospace;color:var(--papel-45);font-size:.78rem;letter-spacing:.02em;border-bottom:0}
.crumb a{color:var(--papel-70);border-bottom:0}.crumb a:hover{color:var(--papel)}
h1{font-family:"Fraunces",Georgia,serif;font-optical-sizing:auto;font-weight:600;font-size:clamp(1.7rem,4.6vw,2.4rem);line-height:1.08;letter-spacing:-.015em;margin:.5em 0 .35em}
h2{font-family:"Fraunces",Georgia,serif;font-weight:600;font-size:1.2rem;letter-spacing:-.01em;margin:0 0 .7rem}
.card{background:rgba(233,230,220,.02);border:1px solid var(--linha);border-radius:10px;padding:1.1rem 1.2rem 1.3rem;margin:1rem 0}
.big{font-family:"Fraunces",Georgia,serif;font-weight:700;font-size:clamp(2rem,5.5vw,2.7rem);color:var(--carimbo);letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1}.big.neg{color:var(--queda)}
table{width:100%;border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--linha)}
th:first-child,td:first-child{text-align:left}
thead th{color:var(--papel-45);font-weight:600;font-family:"IBM Plex Mono",monospace;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase}
tfoot th{color:var(--papel);border-bottom:0;padding-top:12px}
input,select{background:var(--campo);border:1px solid var(--linha);border-radius:8px;color:var(--papel);padding:.6rem .7rem;font:inherit;font-size:1rem;width:100%}
input:focus-visible,select:focus-visible{outline:2px solid var(--carimbo);outline-offset:1px}
label{display:block;margin:12px 0 4px;color:var(--papel-45);font-family:"IBM Plex Mono",monospace;font-size:.64rem;letter-spacing:.1em;text-transform:uppercase}
button{font-family:"IBM Plex Mono",monospace;background:var(--carimbo);color:var(--cofre);border:0;border-radius:8px;padding:.72rem 1rem;font-size:.95rem;font-weight:600;letter-spacing:.02em;cursor:pointer;margin-top:14px;width:100%;transition:filter .15s}
button:hover{filter:brightness(1.06)}
button:focus-visible{outline:2px solid var(--papel);outline-offset:2px}
.res{margin-top:14px;font-size:1.1rem;color:var(--papel-70)}.res b{color:var(--papel);font-family:"Fraunces",Georgia,serif;font-weight:700}
.mut{color:var(--papel-45);font-size:.84rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pill{display:inline-block;background:transparent;border:1px solid var(--linha);border-radius:999px;padding:5px 13px;margin:3px;font-size:.8rem;font-family:"IBM Plex Mono",monospace;color:var(--papel-70)}
a.pill{border-bottom:1px solid var(--linha)}a.pill:hover{border-color:rgba(217,181,74,.5);color:var(--papel)}
footer{margin-top:32px;color:var(--papel-45);font-size:.8rem;border-top:1px solid var(--linha);padding-top:1.2rem}
footer a{color:var(--papel-70)}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
/* --- hub e navegação de meses (menos paredão de links, mais destino) --- */
a.destaque{display:block;border:1px solid rgba(217,181,74,.35);background:rgba(217,181,74,.05);border-radius:10px;padding:.8rem 1rem;margin:.3rem 0 .9rem;border-bottom:1px solid rgba(217,181,74,.35)}
a.destaque:hover{border-color:var(--carimbo)}
.destaque .d-num{display:block;font-family:"Fraunces",Georgia,serif;font-weight:700;font-size:1.55rem;letter-spacing:-.02em;color:var(--carimbo);font-variant-numeric:tabular-nums;line-height:1.15}
.destaque .d-num.neg{color:var(--queda)}
.destaque .d-leg{display:block;color:var(--papel-70);font-size:.84rem;margin-top:2px}
.grupo-rot{font-family:"IBM Plex Mono",monospace;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--papel-45);margin:.9rem 0 .25rem}
.pills{margin:.2rem 0}
.pill.mini{padding:3px 9px;font-size:.72rem;margin:2px}
.pill[aria-current="page"]{border-color:var(--carimbo);color:var(--carimbo);cursor:default}
details.meses{margin-top:.55rem}
details.meses summary{cursor:pointer;font-family:"IBM Plex Mono",monospace;font-size:.76rem;color:var(--papel-70);padding:.4rem .1rem;list-style:none}
details.meses summary::-webkit-details-marker{display:none}
details.meses summary::before{content:"▸ ";color:var(--carimbo)}
details.meses[open] summary::before{content:"▾ "}
details.meses summary:hover{color:var(--papel)}
.ano-grp{display:flex;align-items:baseline;gap:4px;flex-wrap:wrap;margin:.3rem 0}
.ano-grp .ano{font-family:"IBM Plex Mono",monospace;font-size:.74rem;color:var(--papel-45);min-width:3.4ch}
.ir-form{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;align-items:end}
.ir-form button{width:auto;margin-top:0;padding:.62rem 1.1rem}
@media(max-width:640px){.ir-form{grid-template-columns:1fr}.ir-form button{width:100%}}
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


def acumulado(janela: list[dict]) -> float:
    """Acumulado composto (%) de uma janela de variações mensais (%)."""
    fator = 1.0
    for p in janela:
        fator *= 1.0 + p["valor"] / 100.0
    return (fator - 1.0) * 100.0


def fmt_num(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_ano(dt: datetime) -> str:
    return f"{MESES[dt.month - 1]} de {dt.year}"


def slug_mes(dt: datetime) -> str:
    return f"{MESES[dt.month - 1]}-{dt.year}"


def head(title: str, desc: str, canonical: str, jsonld: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'self'; object-src 'none'; img-src 'self' data: https://observatoriotaxas.goatcounter.com; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self' 'unsafe-inline' https://gc.zgo.at; connect-src 'self' https://observatoriotaxas.goatcounter.com"/>
<meta name="referrer" content="strict-origin-when-cross-origin"/>
<script>if (top !== self) {{ try {{ top.location = self.location; }} catch (e) {{ document.documentElement.style.display = "none"; }} }}</script>
<title>{title}</title>
<meta name="description" content="{desc}"/>
<meta name="robots" content="index, follow"/>
<meta name="theme-color" content="#0E1210"/>
<link rel="canonical" href="{canonical}"/>
<meta property="og:type" content="article"/>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:site_name" content="Observatório de Taxas"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{desc}"/>
<meta property="og:url" content="{canonical}"/>
{jsonld}
<style>{CSS}</style>
{GOATCOUNTER_BEACON}
</head>
<body><a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
<!-- nav:start -->
<!-- nav:end -->
<div class="wrap">
<nav class="crumb" aria-label="Você está em"><a href="{BASE_URL}/">Observatório de Taxas</a> › <a href="{BASE_URL}/reajuste/">Reajuste de contratos</a></nav>
<main id="conteudo">
"""


FOOTER = f"""
</main>
<footer>Fonte primária: API pública do SGS/Banco Central do Brasil. Série histórica versionada e auditável no
<a href="https://github.com/iosbilario/observatorio-taxas">GitHub</a>. Conteúdo informativo; confira o índice e a
convenção de defasagem previstos no seu contrato. Projeto <a href="{BASE_URL}/">Observatório de Taxas</a>, LBP Tecnologia.</footer>
</div></body></html>
"""


def email_block() -> str:
    if not EMAIL_FORM_ACTION:
        return ""
    return f"""
<div class="card">
<h2>Me avise quando o índice do mês sair</h2>
<form action="{EMAIL_FORM_ACTION}" method="POST">
<label for="email-alerta">Seu e-mail</label><input id="email-alerta" type="email" name="email" required placeholder="voce@exemplo.com"/>
<button type="submit">Quero o alerta mensal</button>
</form>
<p class="mut">Um e-mail por mês, quando o BACEN publica. Sem spam.</p>
</div>"""


def _pill(slug: str, rotulo: str, titulo: str, base: str = "",
          atual: bool = False, mini: bool = False) -> str:
    """Link-pílula. `base` é o prefixo relativo até /reajuste/ ("" no hub,
    "../" numa página de mês) — links relativos funcionam no Pages, no
    localhost e via file://, e pesam menos que a URL absoluta."""
    cls = "pill mini" if mini else "pill"
    if atual:
        return f'<span class="{cls}" aria-current="page">{rotulo}</span>'
    return f'<a class="{cls}" href="{base}{slug}/" title="{titulo}">{rotulo}</a>'


def _paginas_do_indice(paginas: dict, key: str) -> list[tuple[str, dict]]:
    return sorted(((s, p) for s, p in paginas.items() if p["key"] == key),
                  key=lambda kv: kv[1]["dt"])


def bloco_meses(key: str, nome: str, paginas: dict, base: str = "",
                slug_atual: str = None) -> str:
    """Navegação de meses de UM índice: últimos 12 como pills + <details>
    com todos os anos (agrupados, um pill curto por mês). Substitui o antigo
    paredão de um link por página — os links continuam todos no DOM (SEO),
    mas colapsados e legíveis."""
    ordenadas = _paginas_do_indice(paginas, key)
    if not ordenadas:
        return ""

    recentes = [kv for kv in ordenadas if kv[0] != slug_atual][-12:][::-1]
    pills = "".join(
        _pill(s, f"{MES_CURTO[p['dt'].month - 1]}/{p['dt'].year}",
              f"{nome} · {p['ref']}", base)
        for s, p in recentes
    )

    por_ano: dict[int, list] = {}
    for s, p in ordenadas:
        por_ano.setdefault(p["dt"].year, []).append((s, p))
    linhas = "".join(
        '<p class="ano-grp"><span class="ano">' + str(ano) + "</span>"
        + "".join(_pill(s, MES_CURTO[p["dt"].month - 1],
                        f"{nome} · {MES_CURTO[p['dt'].month - 1]}/{ano}", base,
                        atual=(s == slug_atual), mini=True)
                  for s, p in por_ano[ano])
        + "</p>"
        for ano in sorted(por_ano, reverse=True)
    )
    ini, fim = ordenadas[0][1]["dt"].year, ordenadas[-1][1]["dt"].year
    return (
        f'<p class="grupo-rot">Últimos 12 meses</p><p class="pills">{pills}</p>'
        f'<details class="meses"><summary>Todos os meses ({ini}–{fim})</summary>'
        f"{linhas}</details>"
    )


def build_month_page(key: str, info: dict, janela: list[dict], todas_paginas: dict) -> tuple[str, str]:
    """Gera a página de um índice+mês. Retorna (caminho relativo, html)."""
    ref = janela[-1]["dt"]
    slug = f"{key}-{slug_mes(ref)}"
    url = f"{BASE_URL}/reajuste/{slug}/"
    ac = acumulado(janela)
    fator = 1.0 + ac / 100.0
    nome, ref_txt = info["nome"], mes_ano(ref)

    title = f"Reajuste {nome} {ref_txt}: acumulado 12 meses de {fmt_num(ac)}%"
    desc = (f"{nome} acumulado em 12 meses até {ref_txt}: {fmt_num(ac)}% "
            f"(fator {fmt_num(fator, 6)}). Calculadora de reajuste de aluguel e contratos "
            f"com memória de cálculo e dados oficiais do BACEN.")

    linhas = "".join(
        f"<tr><td>{mes_ano(p['dt']).capitalize()}</td><td>{fmt_num(p['valor'])}%</td></tr>"
        for p in janela
    )

    exemplo = 2000.0 * fator
    faq = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question",
             "name": f"Qual o {nome} acumulado de 12 meses até {ref_txt}?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": f"O {nome} acumulado nos 12 meses encerrados em {ref_txt} é de {fmt_num(ac)}%, segundo dados do Banco Central do Brasil (SGS)."}},
            {"@type": "Question",
             "name": f"Como calcular o reajuste de aluguel pelo {nome} em {ref_txt}?",
             "acceptedAnswer": {"@type": "Answer",
                                "text": f"Multiplique o valor atual pelo fator {fmt_num(fator, 6)}. Exemplo: um aluguel de R$ 2.000,00 passa a R$ {fmt_num(exemplo)}."}},
        ],
    }, ensure_ascii=False)

    # Navegação enxuta: o mesmo mês nos outros índices + os meses do próprio
    # índice (12 recentes visíveis, resto agrupado por ano num <details>).
    mesmo_mes = "".join(
        _pill(s2, todas_paginas[s2]["nome"], f"{todas_paginas[s2]['nome']} · {ref_txt}", "../")
        for k2 in INDICES if k2 != key
        and (s2 := f"{k2}-{slug_mes(ref)}") in todas_paginas
    )
    outros = (
        (f'<p class="grupo-rot">{ref_txt.capitalize()} em outros índices</p>'
         f'<p class="pills">{mesmo_mes}</p>' if mesmo_mes else "")
        + bloco_meses(key, nome, todas_paginas, "../", slug_atual=slug)
    )

    neg = " neg" if ac < 0 else ""
    aviso_neg = ("<p class='mut'>Acumulado negativo: na maioria dos contratos de aluguel o valor "
                 "não é reduzido, apenas mantido. Verifique a cláusula do seu contrato.</p>" if ac < 0 else "")

    html = head(title, desc, url, f'<script type="application/ld+json">{faq}</script>') + f"""
<h1>Reajuste pelo {nome}: {ref_txt}</h1>
<div class="card">
<p class="mut">{nome} acumulado 12 meses (até {ref_txt})</p>
<p class="big{neg}">{fmt_num(ac)}%</p>
<p>Fator de reajuste: <b>{fmt_num(fator, 6)}</b> · Exemplo: aluguel de R$ 2.000,00 → <b>R$ {fmt_num(exemplo)}</b></p>
{aviso_neg}
<p class="mut">Índice tipicamente usado em {info['uso']}.</p>
</div>

<div class="card">
<h2>Calcule o seu reajuste</h2>
<form onsubmit="calc();return false">
<label for="valor">Valor atual do contrato (R$)</label>
<input id="valor" type="number" inputmode="decimal" step="0.01" placeholder="2000,00"/>
<button type="submit">Calcular reajuste</button>
</form>
<p class="res" id="res" aria-live="polite"></p>
</div>

<div class="card">
<h2>Memória de cálculo (12 meses)</h2>
<table><thead><tr><th scope="col">Mês</th><th scope="col">{nome} mensal</th></tr></thead>
<tbody>{linhas}</tbody>
<tfoot><tr><th scope="row">Acumulado composto</th><th>{fmt_num(ac)}%</th></tr></tfoot></table>
<p class="mut">Acumulado = produto de (1 + variação mensal), não a soma simples. Dados: SGS/BACEN, série {info['codigo']}.</p>
</div>
{email_block()}
<div class="card"><h2>Outros índices e meses</h2>{outros}</div>
<script>
const FATOR={fator!r};
function calc(){{
  const v=parseFloat(document.getElementById('valor').value.replace(',','.'));
  if(!v){{document.getElementById('res').textContent='Informe o valor atual.';return;}}
  const n=v*FATOR;
  document.getElementById('res').innerHTML='Novo valor: <b>R$ '+n.toLocaleString('pt-BR',{{minimumFractionDigits:2,maximumFractionDigits:2}})+'</b> (aumento de R$ '+(n-v).toLocaleString('pt-BR',{{minimumFractionDigits:2,maximumFractionDigits:2}})+')';
}}
</script>
""" + FOOTER
    return f"reajuste/{slug}/index.html", html


def _mapa_meses_js(paginas: dict) -> str:
    """{indice: {ano: [meses...]}} para o seletor 'vá direto ao mês'."""
    mapa: dict[str, dict[str, list[int]]] = {}
    for _, p in paginas.items():
        mapa.setdefault(p["key"], {}).setdefault(str(p["dt"].year), []).append(p["dt"].month)
    for k in mapa:
        for a in mapa[k]:
            mapa[k][a] = sorted(mapa[k][a])
    return json.dumps(mapa, ensure_ascii=False, sort_keys=True)


def build_hub(paginas: dict, resumo: dict) -> str:
    url = f"{BASE_URL}/reajuste/"
    title = "Calculadora de reajuste de contrato: IPCA, IGP-M, INPC e IGP-DI"
    desc = ("Calcule o reajuste anual do seu aluguel ou contrato pelo IPCA, IGP-M, INPC ou IGP-DI, "
            "com acumulado de 12 meses, memória de cálculo e dados oficiais do Banco Central.")

    opcoes_indice = "".join(
        f'<option value="{key}">{info["nome"]}</option>' for key, info in INDICES.items()
    )
    seletor = f"""
<div class="card">
<h2>Vá direto ao mês do seu contrato</h2>
<p class="mut">Escolha o índice e o mês de aniversário do contrato: a página do mês traz
o acumulado de 12 meses, o fator e a calculadora daquela referência.</p>
<form class="ir-form" id="ir-form">
<div><label for="ir-indice">Índice</label><select id="ir-indice">{opcoes_indice}</select></div>
<div><label for="ir-mes">Mês do reajuste</label><select id="ir-mes"></select></div>
<button type="submit">Abrir o mês</button>
</form>
</div>"""

    cards = ""
    for key, info in INDICES.items():
        r = resumo.get(key)
        if not r:
            continue
        neg = " neg" if r["ac"] < 0 else ""
        cards += f"""
<div class="card">
<h2>{info["nome"]}</h2>
<p class="mut">Usado em {info["uso"]}.</p>
<a class="destaque" href="{r["slug"]}/">
<span class="d-num{neg}">{fmt_num(r["ac"])}%</span>
<span class="d-leg">acumulado 12 meses até {r["refTxt"]} · fator {fmt_num(r["fator"], 6)} — abrir cálculo completo →</span>
</a>
{bloco_meses(key, info["nome"], paginas)}
</div>"""

    html = head(title, desc, url) + f"""
<h1>Reajuste de contratos e aluguel</h1>
<p>Acumulado de 12 meses, fator de reajuste e calculadora para cada índice, mês a mês, com dados
oficiais do BACEN coletados automaticamente e <a href="https://github.com/iosbilario/observatorio-taxas">versionados em aberto</a>.</p>
<p class="mut">Precisa corrigir um valor entre duas datas, e não reajustar um contrato?
Use a <a href="{BASE_URL}/correcao/">correção monetária</a>.</p>
{seletor}
{email_block()}
{cards}
<script>
"use strict";
(function () {{
  var MESES = {json.dumps(MESES, ensure_ascii=False)};
  var PAG = {_mapa_meses_js(paginas)};
  var selI = document.getElementById("ir-indice");
  var selM = document.getElementById("ir-mes");
  function popula() {{
    var anos = PAG[selI.value] || {{}};
    selM.innerHTML = "";
    Object.keys(anos).sort().reverse().forEach(function (ano) {{
      anos[ano].slice().reverse().forEach(function (m) {{
        var o = document.createElement("option");
        o.value = selI.value + "-" + MESES[m - 1] + "-" + ano;
        o.textContent = MESES[m - 1] + " de " + ano;
        selM.appendChild(o);
      }});
    }});
  }}
  selI.addEventListener("change", popula);
  document.getElementById("ir-form").addEventListener("submit", function (ev) {{
    ev.preventDefault();
    if (selM.value) window.location.href = selM.value + "/";
  }});
  popula();
}})();
</script>
""" + FOOTER
    return html


def rebuild_sitemap(paths: list[str]) -> None:
    hoje = datetime.now().strftime("%Y-%m-%d")
    urls = [f"{BASE_URL}/", f"{BASE_URL}/reajuste/"] + [
        f"{BASE_URL}/{p.rsplit('/index.html', 1)[0]}/" for p in paths
    ]
    body = "".join(
        f"  <url><loc>{u}</loc><lastmod>{hoje}</lastmod><changefreq>daily</changefreq></url>\n"
        for u in urls
    )
    (DOCS_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1ª passada: descobrir todas as janelas de 12 meses disponíveis por índice.
    janelas: dict[str, list[list[dict]]] = {}
    paginas: dict[str, dict] = {}  # slug -> {nome, ref} p/ cross-links
    for key, info in INDICES.items():
        hist = load_history(info["codigo"])
        janelas[key] = []
        for fim in range(11, len(hist)):
            j = hist[fim - 11 : fim + 1]
            janelas[key].append(j)
            ref = j[-1]["dt"]
            paginas[f"{key}-{slug_mes(ref)}"] = {
                "nome": info["nome"], "ref": mes_ano(ref), "key": key, "dt": ref,
            }

    # Resumo do mês mais recente de cada índice, para o destaque do hub.
    resumo: dict[str, dict] = {}
    for key, info in INDICES.items():
        if janelas[key]:
            j = janelas[key][-1]
            ac = acumulado(j)
            ref = j[-1]["dt"]
            resumo[key] = {"slug": f"{key}-{slug_mes(ref)}", "ac": ac,
                           "fator": 1.0 + ac / 100.0, "refTxt": mes_ano(ref)}

    # 2ª passada: gerar páginas.
    paths: list[str] = []
    for key, info in INDICES.items():
        for j in janelas[key]:
            rel, html = build_month_page(key, info, j, paginas)
            out = DOCS_DIR / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            paths.append(rel)

    (OUT_DIR / "index.html").write_text(build_hub(paginas, resumo), encoding="utf-8")
    rebuild_sitemap(paths)
    print(f"Geradas {len(paths)} páginas de reajuste + hub + sitemap.")


if __name__ == "__main__":
    main()
