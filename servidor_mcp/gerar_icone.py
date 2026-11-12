"""
gerar_icone.py — Ícones da integração na identidade do Observatório.

Mesmo desenho do favicon do site: fundo sala-cofre (#0E1210), linha de série
temporal em dourado (#D9B54A). Gera PNGs quadrados para o pacote do ChatGPT,
para o diretório do Claude e para a página /mcp/.

    python servidor_mcp/gerar_icone.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
COFRE, CARIMBO, PAPEL = (14, 18, 16), (217, 181, 74), (233, 230, 220)
SAIDAS = [
    (ROOT / "servidor_mcp/plugin-openai/assets/logo.png", 512, True),
    (ROOT / "servidor_mcp/plugin-openai/assets/icon.png", 256, True),
    (ROOT / "docs/mcp/icone.png", 512, True),
]


def desenhar(tam: int, cantos: bool) -> Image.Image:
    esc = 4                                            # supersampling
    s = tam * esc
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.19) if cantos else 0, fill=COFRE)
    k = s / 32
    pontos = [(4 * k, 22 * k), (12 * k, 14 * k), (18 * k, 18 * k), (28 * k, 6 * k)]
    d.line([(4 * k, 26 * k), (28 * k, 26 * k)], fill=tuple(round(c * 0.24 + b * 0.76) for c, b in zip(PAPEL, COFRE)), width=max(1, int(0.6 * k)))
    d.line(pontos, fill=CARIMBO, width=int(3 * k), joint="curve")
    r = 1.5 * k
    for x, y in (pontos[0], pontos[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=CARIMBO)
    return im.resize((tam, tam), Image.LANCZOS)


def main() -> None:
    for caminho, tam, cantos in SAIDAS:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        desenhar(tam, cantos).save(caminho, optimize=True)
        print(f"{caminho.relative_to(ROOT)}: {tam}x{tam}")


if __name__ == "__main__":
    main()
