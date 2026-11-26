"""
catalogo_home.py — "Indicadores por tema" da página inicial.

Quais séries entram, em que tema e com que nome, unidade, casas e link vêm das
MESMAS fontes da vitrine /indicadores/: config.yml (código e grupo) e
build_indicadores.PAGINAS (a série tem ficha pública). Não existe uma segunda
lista das séries aqui. Uma série nova com grupo e ficha entra sozinha, no tema
do seu grupo; um grupo novo vira um tema novo, no fim.

TEMAS é só a parte editorial: ordem, título, endereço (#catalogo-<id>) e o
indicador de referência de cada tema. ACOES liga um tema a uma ferramenta.

Cada série vira uma linha com o último valor (só meses fechados, como na
ficha), a referência temporal no vocabulário do site (tempo_series), a
variação contra uma base dita por extenso e um minigráfico SVG dos últimos 12
meses até a última observação, desenhado aqui no build com datas reais.

    python scripts/render_index.py     # o bloco entra entre <!-- mais:inicio --> e <!-- mais:fim -->
"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime

import build_indicadores as BI
from build_pages import fmt_num
from servidor_mcp import catalogo as cat
from tempo_series import referencia, rotulo_card

# (grupo em config.yml, id do endereço, título, código de referência, rótulo
# curto da referência no resumo do tema: "IPCA em 12 meses · 4,63%")
TEMAS = [
    ("Inflação", "inflacao", "Inflação", 13522, "IPCA em 12 meses"),
    ("Juros", "juros", "Juros e poupança", 432, "Meta Selic"),
    ("Câmbio", "cambio", "Câmbio", 1, "Dólar PTAX de venda"),
    ("Crédito", "credito", "Crédito", 21082, "Inadimplência"),
    ("Atividade & Emprego", "atividade", "Atividade e emprego", 24369, "Desemprego"),
    ("Setor externo e fiscal", "externo", "Setor externo e fiscal", 13621, "Reservas internacionais"),
]
# Nome da linha quando o da ficha é ambíguo lado a lado no catálogo.
NOMES = {1: "Dólar PTAX de venda", 10813: "Dólar PTAX de compra"}
ACOES = {"inflacao": ("correcao/", "Corrigir um valor pela inflação"),
         "juros": ("comparador/", "Comparar Selic, CDI e IPCA")}
TEMA_INICIAL = "inflacao"
JANELA_TXT = "Minigráficos: 12 meses de cada série, até a última observação dela, cada um na própria escala."
MAX_PONTOS = 48          # séries diárias são simplificadas para o HTML não crescer demais


def e(s) -> str:
    return html.escape(str(s), quote=True)


def _slug(txt: str) -> str:
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _diaria(codigo: int) -> bool:
    return not BI.mensal(codigo)


# ── uma série ─────────────────────────────────────────────────────────────

def base_de_comparacao(codigo: int, pts: list[dict]) -> dict | None:
    """Mensal: o mês anterior. Diária: a última observação de até um mês antes."""
    if len(pts) < 2:
        return None
    if not _diaria(codigo):
        return pts[-2]
    ult = pts[-1]["dt"]
    m = ult.month - 1 or 12
    a = ult.year - (1 if ult.month == 1 else 0)
    d = min(ult.day, [31, 29 if a % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    alvo = ult.replace(year=a, month=m, day=d)
    antes = [p for p in pts if p["dt"] <= alvo]
    return antes[-1] if antes else pts[0]


def rotulo_base(codigo: int, p: dict) -> str:
    """A base no mesmo vocabulário da referência: competência, trimestre
    móvel, cotação, taxa do dia, período iniciado ou posição."""
    return referencia(codigo, p["dt"])


def janela_12m(pts: list[dict]) -> list[dict]:
    ult = pts[-1]["dt"]
    inicio = ult.replace(year=ult.year - 1)
    return [p for p in pts if p["dt"] > inicio]


def simplifica(pts: list[dict], maximo: int = MAX_PONTOS) -> list[dict]:
    """No máximo `maximo` pontos: um a cada k, mais o primeiro, o último e os
    extremos (o maior e o menor). Nunca cria ponto."""
    if len(pts) <= maximo:
        return pts
    k = -(-len(pts) // maximo)
    manter = set(range(0, len(pts), k)) | {0, len(pts) - 1}
    manter.add(max(range(len(pts)), key=lambda i: pts[i]["valor"]))
    manter.add(min(range(len(pts)), key=lambda i: pts[i]["valor"]))
    return [pts[i] for i in sorted(manter)]


def lacuna(codigo: int, a: datetime, b: datetime) -> bool:
    """Intervalo maior que o esperado pela periodicidade (sem dado no meio)."""
    if _diaria(codigo):
        return (b - a).days > 10
    return (b.year * 12 + b.month) - (a.year * 12 + a.month) > 1


def minigrafico(codigo: int, pts: list[dict], w: int = 112, h: int = 30) -> str:
    """SVG da janela de 12 meses: eixo x com as datas reais (do início da janela
    à última observação), escala própria, linha quebrada nas lacunas. Série
    constante = linha horizontal; um ponto = um ponto."""
    jan = janela_12m(pts)
    if not jan:
        return ""
    ult = jan[-1]["dt"]
    x0 = ult.replace(year=ult.year - 1)
    total = (ult - x0).total_seconds() or 1
    vs = [p["valor"] for p in jan]
    lo, hi = min(vs), max(vs)
    pad = 3

    def x(dt):
        return pad + (dt - x0).total_seconds() / total * (w - 2 * pad)

    def y(v):
        return h / 2 if hi == lo else pad + (hi - v) / (hi - lo) * (h - 2 * pad)

    jan_s = simplifica(jan)
    if len(jan_s) == 1:
        p = jan_s[0]
        corpo = f'<circle cx="{x(p["dt"]):.1f}" cy="{y(p["valor"]):.1f}" r="2"/>'
    else:
        partes, ant = [], None
        for p in jan_s:
            cmd = "M" if ant is None or lacuna(codigo, ant["dt"], p["dt"]) else "L"
            partes.append(f'{cmd}{x(p["dt"]):.1f} {y(p["valor"]):.1f}')
            ant = p
        p = jan_s[-1]
        corpo = (f'<path d="{" ".join(partes)}"/>'
                 f'<circle cx="{x(p["dt"]):.1f}" cy="{y(p["valor"]):.1f}" r="2"/>')
    return (f'<svg class="cat-spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true" '
            f'focusable="false">{corpo}</svg>')


def linha(codigo: int, pts: list[dict]) -> dict:
    """Dados de uma linha do catálogo (pts = histórico da série)."""
    fechados, _ = BI.completos(codigo, pts)
    p = BI.PAGINAS[codigo]
    d = {"codigo": codigo, "nome": NOMES.get(codigo, p["curto"]), "unidade": cat.SERIES[codigo]["unidade"],
         "url": f"indicadores/{p['slug']}/", "valor": None, "ref": "", "variacao": None, "svg": ""}
    if not fechados:
        return d
    ult = fechados[-1]
    d["valor"] = BI.valor(codigo, ult["valor"])
    d["ref"] = rotulo_card(codigo, [{"dt": q["dt"], "v": q["valor"]} for q in fechados])
    base = base_de_comparacao(codigo, fechados)
    if base is not None:
        dif = ult["valor"] - base["valor"]
        d["variacao"] = {"texto": BI.variacao(codigo, base["valor"], ult["valor"]),
                         "sentido": "alta" if dif > 0 else "queda" if dif < 0 else "estável",
                         "base": rotulo_base(codigo, base)}
    d["svg"] = minigrafico(codigo, fechados)
    return d


# ── temas ─────────────────────────────────────────────────────────────────

def temas(series: list[dict], historicos: dict[int, list[dict]]) -> list[dict]:
    """series = itens de config.yml ({codigo, grupo}); só entram as que têm
    ficha (PAGINAS) e histórico, como na vitrine /indicadores/."""
    por_grupo: dict[str, list[int]] = {}
    for it in series:
        c = it["codigo"]
        if c in BI.PAGINAS and historicos.get(c):
            por_grupo.setdefault(it.get("grupo", "Outros"), []).append(c)
    conf = {g: (i, t, r, rc) for g, i, t, r, rc in TEMAS}
    ordem = [g for g, *_ in TEMAS if g in por_grupo] + [g for g in por_grupo if g not in conf]
    saida = []
    for g in ordem:
        ident, titulo, ref, rotulo = conf.get(g, (_slug(g), g, None, None))
        codigos = por_grupo[g]
        linhas = [linha(c, historicos[c]) for c in codigos]
        refc = ref if ref in codigos else codigos[0]
        refli = next(li for li in linhas if li["codigo"] == refc)
        saida.append({"grupo": g, "id": ident, "titulo": titulo, "linhas": linhas, "n": len(linhas),
                      "referencia": refli, "rotulo_ref": rotulo if ref in codigos else refli["nome"],
                      "acao": ACOES.get(ident)})
    return saida


SETA = {"alta": "▲", "queda": "▼", "estável": "■"}


def _cab(t: dict) -> str:
    r = t["referencia"]
    return (f'<span class="cat-tema-nome">{e(t["titulo"])}</span>'
            f'<span class="cat-tema-n">{t["n"]} {"série" if t["n"] == 1 else "séries"}</span>'
            f'<span class="cat-tema-ref">{e(t["rotulo_ref"])} · <b>{e(r["valor"] or "—")}</b></span>')


def _linha_html(li: dict) -> str:
    v = li["variacao"]
    if v:
        var = (f'<span class="cat-var"><span aria-hidden="true">{SETA[v["sentido"]]}</span> '
               f'<span class="cat-var-n">{e(v["texto"])}</span> <span class="cat-var-base">'
               f'{e(v["sentido"])} · base: {e(v["base"])}</span></span>')
    else:
        var = '<span class="cat-var"><span class="cat-var-base">sem base de comparação</span></span>'
    return (f'<li><a class="cat-linha" href="{e(li["url"])}">'
            f'<span class="cat-nome">{e(li["nome"])}<small>{e(li["unidade"])} · {e(li["ref"])}</small></span>'
            f'{li["svg"]}<span class="cat-valor">{e(li["valor"] or "—")}</span>{var}</a></li>')


def bloco(ts: list[dict]) -> str:
    """HTML do catálogo. Sem JavaScript: a lista de temas é de âncoras e todos
    os painéis ficam visíveis, um embaixo do outro. docs/catalogo.js transforma
    em abas (desktop) ou seções expansíveis (celular)."""
    nav = "".join(f'<li><a class="cat-tema" href="#catalogo-{t["id"]}" data-tema="{t["id"]}">{_cab(t)}</a></li>'
                  for t in ts)
    paineis = []
    for t in ts:
        acao = (f'<p class="cat-acao"><a href="{e(t["acao"][0])}">{e(t["acao"][1])} →</a></p>' if t["acao"] else "")
        paineis.append(
            f'<section class="cat-painel" id="catalogo-{t["id"]}" data-tema="{t["id"]}" '
            f'aria-labelledby="catalogo-{t["id"]}-t">'
            f'<h3 class="cat-painel-cab" id="catalogo-{t["id"]}-t">{_cab(t)}</h3>'
            f'<div class="cat-corpo" id="catalogo-{t["id"]}-corpo"><ul class="cat-linhas">'
            + "".join(_linha_html(li) for li in t["linhas"]) + f"</ul>{acao}</div></section>")
    n = sum(t["n"] for t in ts)
    return (f'<div class="cat" data-catalogo data-inicial="{TEMA_INICIAL}">'
            f'<p class="cat-janela">{e(JANELA_TXT)} {n} séries em {len(ts)} temas.</p>'
            f'<nav class="cat-nav" aria-label="Temas"><ul class="cat-temas">{nav}</ul></nav>'
            f'<div class="cat-paineis">{"".join(paineis)}</div></div>')


def gerar() -> str:
    series = BI.series_config()
    hist = {it["codigo"]: BI.load_history(it["codigo"]) for it in series}
    ts = temas(series, hist)
    return bloco(ts)
