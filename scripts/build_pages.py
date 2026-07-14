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
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'self'; object-src 'none'; img-src 'self' data: https://observatoriotaxas.goatcounter.com; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://gc.zgo.at; connect-src 'self' https://observatoriotaxas.goatcounter.com"/>
<meta name="referrer" content="strict-origin-when-cross-origin"/>
<script>if (top !== self) {{ try {{ top.location = self.location; }} catch (e) {{ document.documentElement.style.display = "none"; }} }}</script>
<title>{title}</title>
<meta name="description" content="{desc}"/>
<meta name="robots" content="index, follow"/>
<meta name="theme-color" content="#0b1120"/>
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
<body><div class="wrap">
<p class="crumb"><a href="{BASE_URL}/">Observatório de Taxas</a> › <a href="{BASE_URL}/reajuste/">Reajuste de contratos</a></p>
"""


FOOTER = f"""
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
<label>Seu e-mail</label><input type="email" name="email" required placeholder="voce@exemplo.com"/>
<button type="submit">Quero o alerta mensal</button>
</form>
<p class="mut">Um e-mail por mês, quando o BACEN publica. Sem spam.</p>
</div>"""


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

    outros = "".join(
        f'<a class="pill" href="{BASE_URL}/reajuste/{s}/">{p["nome"]} {p["ref"]}</a>'
        for s, p in todas_paginas.items() if s != slug
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
<label>Valor atual do contrato (R$)</label>
<input id="valor" type="number" inputmode="decimal" step="0.01" placeholder="2000,00"/>
<button onclick="calc()">Calcular reajuste</button>
<p class="res" id="res"></p>
</div>

<div class="card">
<h2>Memória de cálculo (12 meses)</h2>
<table><thead><tr><th>Mês</th><th>{nome} mensal</th></tr></thead>
<tbody>{linhas}</tbody>
<tfoot><tr><th>Acumulado composto</th><th>{fmt_num(ac)}%</th></tr></tfoot></table>
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


def build_hub(paginas: dict) -> str:
    url = f"{BASE_URL}/reajuste/"
    title = "Calculadora de reajuste de contrato: IPCA, IGP-M, INPC e IGP-DI"
    desc = ("Calcule o reajuste anual do seu aluguel ou contrato pelo IPCA, IGP-M, INPC ou IGP-DI, "
            "com acumulado de 12 meses, memória de cálculo e dados oficiais do Banco Central.")
    cards = ""
    for key, info in INDICES.items():
        links = "".join(
            f'<a class="pill" href="{BASE_URL}/reajuste/{s}/">{p["ref"]}</a>'
            for s, p in paginas.items() if s.startswith(key + "-")
        )
        cards += f'<div class="card"><h2>{info["nome"]}</h2><p class="mut">Usado em {info["uso"]}.</p>{links}</div>'

    html = head(title, desc, url) + f"""
<h1>Reajuste de contratos e aluguel</h1>
<p>Acumulado de 12 meses, fator de reajuste e calculadora para cada índice, mês a mês, com dados
oficiais do BACEN coletados automaticamente e <a href="https://github.com/iosbilario/observatorio-taxas">versionados em aberto</a>.</p>
{email_block()}
{cards}
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
            paginas[f"{key}-{slug_mes(ref)}"] = {"nome": info["nome"], "ref": mes_ano(ref)}

    # 2ª passada: gerar páginas.
    paths: list[str] = []
    for key, info in INDICES.items():
        for j in janelas[key]:
            rel, html = build_month_page(key, info, j, paginas)
            out = DOCS_DIR / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            paths.append(rel)

    (OUT_DIR / "index.html").write_text(build_hub(paginas), encoding="utf-8")
    rebuild_sitemap(paths)
    print(f"Geradas {len(paths)} páginas de reajuste + hub + sitemap.")


if __name__ == "__main__":
    main()
