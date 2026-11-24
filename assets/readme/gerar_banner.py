"""
gerar_banner.py — Gera os banners do README, claro e escuro.

  assets/readme/banner.svg         modo claro (padrão)
  assets/readme/banner-escuro.svg  modo escuro (README com <picture>)

As cores são as do tema do site (tokens do Refy Design, docs/refy/tokens.css,
e docs/tema.css). O texto vira contorno (path) a partir das fontes do site
(IBM Plex Serif, Source Sans 3, IBM Plex Mono), porque o GitHub não carrega
fontes dentro de SVG. A linha do gráfico é a série real do IPCA acumulado em
12 meses (SGS 13522, produzida pelo IBGE), lida de data/13522_history.json.

Ferramenta de manutenção, fora do pipeline do site. Exige fonttools:

    pip install fonttools
    python assets/readme/gerar_banner.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[2]
PASTA = Path(__file__).resolve().parent

# fundo, borda/linhas, título, texto, texto fraco, destaque
TEMAS = {
    "banner.svg": dict(fundo="#FFFFFF", linha="#D9DEDD", titulo="#111113", texto="#3E3E44",
                       fraco="#68676D", destaque="#1B5FAB"),
    "banner-escuro.svg": dict(fundo="#12161B", linha="#2E3844", titulo="#E8EDF2", texto="#C6D0DA",
                              fraco="#ADBDCC", destaque="#8AB8EE"),
}
W, H = 1280, 440


def fonte(caminho: Path, eixos: dict | None = None) -> TTFont:
    f = TTFont(str(caminho))
    if eixos and "fvar" in f:
        f = instantiateVariableFont(f, eixos)
    return f


def texto(f: TTFont, s: str, x: float, y: float, tam: float, cor: str,
          opac: float = 1.0, espaco: float = 0.0) -> tuple[str, float]:
    """Path SVG do texto `s` com a linha de base em (x, y). Devolve (svg, largura)."""
    gs, cmap, hmtx = f.getGlyphSet(), f.getBestCmap(), f["hmtx"]
    upm = f["head"].unitsPerEm
    k = tam / upm
    partes, cx = [], 0.0
    for ch in s:
        nome = cmap.get(ord(ch))
        if nome is None:
            nome = cmap.get(ord(" "))
        pen = SVGPathPen(gs, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
        gs[nome].draw(TransformPen(pen, (k, 0, 0, -k, x + cx, y)))
        d = pen.getCommands()
        if d:
            partes.append(d)
        cx += hmtx[nome][0] * k + espaco
    op = f' fill-opacity="{opac}"' if opac < 1 else ""
    return f'<path fill="{cor}"{op} d="{" ".join(partes)}"/>', cx - espaco


def serie_ipca() -> tuple[str, str, str]:
    pts = json.loads((ROOT / "data" / "13522_history.json").read_text(encoding="utf-8"))
    vals = [float(p["valor"]) for p in pts]
    x0, x1, y0, y1 = 64, W - 64, 318, 392
    lo, hi = min(vals), max(vals)
    xy = [(x0 + i * (x1 - x0) / (len(vals) - 1), y1 - (v - lo) / (hi - lo) * (y1 - y0))
          for i, v in enumerate(vals)]
    poly = " ".join(f"{a:.1f},{b:.1f}" for a, b in xy)
    ini, fim = pts[0]["data"][3:], pts[-1]["data"][3:]
    return poly, f"{xy[-1][0]:.1f},{xy[-1][1]:.1f}", f"{ini} a {fim}"


def main() -> None:
    serif = fonte(ROOT / "assets/fonts/IBMPlexSerif-Regular.ttf")
    sans = fonte(ROOT / "assets/fonts/SourceSans3[wght].ttf", {"wght": 400})
    mono = fonte(ROOT / "assets/fonts/IBMPlexMono-Regular.ttf")
    poly, ultimo, periodo = serie_ipca()

    for nome, c in TEMAS.items():
        el = []
        el.append(texto(mono, "OBSERVATORIODETAXAS.TEC.BR", 64, 74, 13, c["destaque"], espaco=3.2)[0])
        tit, tw = texto(serif, "Observatório de Taxas", 62, 148, 68, c["titulo"])
        el.append(tit)
        el.append(texto(serif, ".", 62 + tw, 148, 68, c["destaque"])[0])
        el.append(texto(serif, "Os números mudam. O histórico fica.", 64, 198, 32, c["texto"])[0])
        el.append(texto(sans, "Indicadores econômicos brasileiros, séries históricas versionadas e", 64, 242, 20, c["fraco"])[0])
        el.append(texto(sans, "ferramentas gratuitas para consulta, comparação e cálculo.", 64, 268, 20, c["fraco"])[0])
        el.append(texto(mono, f"IPCA ACUMULADO EM 12 MESES · IBGE, VIA SGS/BCB · {periodo}", 64, 420, 11,
                        c["fraco"], espaco=1.2)[0])
        x, y = ultimo.split(",")
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Observatório de Taxas</title>
<desc id="d">Os números mudam. O histórico fica. Indicadores econômicos brasileiros, séries históricas versionadas e ferramentas gratuitas. Ao fundo, a linha do IPCA acumulado em 12 meses ({periodo}).</desc>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{c['fundo']}" stroke="{c['linha']}"/>
<line x1="64" y1="300" x2="{W - 64}" y2="300" stroke="{c['linha']}"/>
<line x1="64" y1="398" x2="{W - 64}" y2="398" stroke="{c['linha']}"/>
<polyline points="{poly}" fill="none" stroke="{c['destaque']}" stroke-width="1.6" stroke-linejoin="round"/>
<circle cx="{x}" cy="{y}" r="4" fill="{c['destaque']}"/>
{chr(10).join(el)}
</svg>
"""
        saida = PASTA / nome
        saida.write_text(svg, encoding="utf-8")
        print(f"{saida.relative_to(ROOT)}: {len(svg.encode()) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
