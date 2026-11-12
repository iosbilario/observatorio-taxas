"""
gerar_banner.py — Gera assets/readme/banner.svg (banner do README).

O texto vira contorno (path) a partir das fontes do próprio site (Fraunces,
Archivo, IBM Plex Mono), porque o GitHub não carrega fontes dentro de SVG. A
linha do gráfico é a série real do IPCA acumulado em 12 meses (SGS 13522,
produzida pelo IBGE), lida de data/13522_history.json.

Ferramenta de manutenção, fora do pipeline do site. Exige fonttools e brotli:

    pip install fonttools brotli
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
SAIDA = Path(__file__).resolve().parent / "banner.svg"

COFRE, PAPEL, CARIMBO = "#0E1210", "#E9E6DC", "#D9B54A"
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
    fr_t = fonte(ROOT / "assets/fonts/Fraunces-variable.ttf", {"wght": 600, "opsz": 144, "SOFT": 0, "WONK": 0})
    fr_s = fonte(ROOT / "assets/fonts/Fraunces-variable.ttf", {"wght": 500, "opsz": 72, "SOFT": 0, "WONK": 0})
    arq = fonte(ROOT / "docs/fonts/archivo.woff2", {"wght": 400})
    mono = fonte(ROOT / "assets/fonts/IBMPlexMono-Regular.ttf")

    poly, ultimo, periodo = serie_ipca()
    el = []
    el.append(texto(mono, "OBSERVATORIODETAXAS.TEC.BR", 64, 74, 13, CARIMBO, espaco=3.2)[0])
    el.append(texto(fr_t, "Observatório de Taxas", 62, 146, 64, PAPEL)[0])
    el.append(texto(fr_s, "Os números mudam. O histórico fica.", 64, 196, 32, CARIMBO)[0])
    el.append(texto(arq, "Indicadores econômicos brasileiros, séries históricas versionadas e", 64, 240, 19, PAPEL, 0.72)[0])
    el.append(texto(arq, "ferramentas gratuitas para consulta, comparação e cálculo.", 64, 266, 19, PAPEL, 0.72)[0])
    legenda, lw = texto(mono, f"IPCA ACUMULADO EM 12 MESES · IBGE, VIA SGS/BCB · {periodo}", 64, 420, 11, PAPEL, 0.55, espaco=1.2)
    el.append(legenda)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Observatório de Taxas</title>
<desc id="d">Os números mudam. O histórico fica. Indicadores econômicos brasileiros, séries históricas versionadas e ferramentas gratuitas. Ao fundo, a linha do IPCA acumulado em 12 meses ({periodo}).</desc>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{COFRE}" stroke="{PAPEL}" stroke-opacity="0.14"/>
<line x1="64" y1="300" x2="{W - 64}" y2="300" stroke="{PAPEL}" stroke-opacity="0.14"/>
<line x1="64" y1="304" x2="{W - 64}" y2="304" stroke="{PAPEL}" stroke-opacity="0.14"/>
<line x1="64" y1="398" x2="{W - 64}" y2="398" stroke="{PAPEL}" stroke-opacity="0.14"/>
<polyline points="{poly}" fill="none" stroke="{PAPEL}" stroke-opacity="0.55" stroke-width="1.4" stroke-linejoin="round"/>
<circle cx="{ultimo.split(',')[0]}" cy="{ultimo.split(',')[1]}" r="4" fill="{CARIMBO}"/>
{chr(10).join(el)}
</svg>
"""
    SAIDA.write_text(svg, encoding="utf-8")
    print(f"{SAIDA.relative_to(ROOT)}: {len(svg.encode()) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
