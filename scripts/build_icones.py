#!/usr/bin/env python3
"""
build_icones.py — Ícones do site em arquivos com URL própria.

Até aqui o favicon ia embutido em cada página como data:image/svg+xml. O
navegador mostra esse ícone na aba, mas o Google não: para aparecer ao lado do
resultado da busca, o ícone precisa de uma URL própria que o Googlebot consiga
baixar, quadrado e com lado múltiplo de 48 px
(https://developers.google.com/search/docs/appearance/favicon-in-search).

Gera em docs/, a partir do mesmo desenho do logo (quadrado escuro arredondado
e a linha dourada):

  favicon.svg           vetor, para navegadores modernos
  favicon.ico           16, 32 e 48 px, para /favicon.ico e navegadores antigos
  icon-192.png          192 px (4 × 48), o que o Google prefere
  icon-512.png          512 px, para o manifest (atalho no Android)
  apple-touch-icon.png  180 px, fundo cheio (o iOS arredonda sozinho)
  site.webmanifest      nome, cores e ícones

As tags <link> entram em todas as páginas por sync_nav.py. Rode só quando o
desenho mudar; os arquivos são versionados.

    python scripts/build_icones.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

DOCS = Path(__file__).resolve().parent.parent / "docs"
FUNDO = "#0E1210"
OURO = "#D9B54A"
PONTOS = [(4, 22), (12, 14), (18, 18), (28, 6)]   # viewBox 0 0 32 32

SVG = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
       f'<rect width="32" height="32" rx="6" fill="{FUNDO}"/>'
       f'<polyline points="{" ".join(f"{x},{y}" for x, y in PONTOS)}" fill="none" stroke="{OURO}" '
       f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>\n')


def desenha(lado: int, arredondado: bool = True) -> Image.Image:
    """Desenha em 8× e reduz (antisserrilhado)."""
    k = lado * 8 / 32
    img = Image.new("RGBA", (lado * 8, lado * 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if arredondado:
        d.rounded_rectangle([0, 0, lado * 8 - 1, lado * 8 - 1], radius=round(6 * k), fill=FUNDO)
    else:
        d.rectangle([0, 0, lado * 8, lado * 8], fill=FUNDO)
    pts = [(x * k, y * k) for x, y in PONTOS]
    w = round(3 * k)
    d.line(pts, fill=OURO, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[-1]):                      # pontas arredondadas
        d.ellipse([x - r, y - r, x + r, y + r], fill=OURO)
    return img.resize((lado, lado), Image.LANCZOS)


def main() -> None:
    (DOCS / "favicon.svg").write_text(SVG, encoding="utf-8")
    desenha(48).save(DOCS / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    desenha(192).save(DOCS / "icon-192.png", optimize=True)
    desenha(512).save(DOCS / "icon-512.png", optimize=True)
    desenha(180, arredondado=False).convert("RGB").save(DOCS / "apple-touch-icon.png", optimize=True)
    manifest = {
        "name": "Observatório de Taxas",
        "short_name": "Observatório",
        "start_url": "/",
        "display": "browser",
        "background_color": FUNDO,
        "theme_color": FUNDO,
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    (DOCS / "site.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ícones: favicon.svg, favicon.ico, icon-192.png, icon-512.png, apple-touch-icon.png, site.webmanifest")


if __name__ == "__main__":
    main()
