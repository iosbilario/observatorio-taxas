"""
build_og.py — Gera docs/og-image.png automaticamente a cada coleta.

O card social também "se reescreve sozinho": desenha, na identidade do site
(modo claro com os tokens do Refy, título em IBM Plex Serif, números em
Manrope), os números do dia (Selic, IPCA 12 meses, Dólar) lidos de docs/data,
com o direcionador do mês (▲ ▼ ■) e a data da coleta.

1200×630 (proporção padrão de og:image). Sem dependência de rede: usa as fontes
embutidas em assets/fonts/ (OFL) e o Pillow. Roda no cron depois de render_index.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "docs" / "og-image.png"

# Cores do modo claro (docs/refy/tokens.css + docs/tema.css).
FUNDO = (255, 255, 255)
SUPERFICIE = (247, 247, 247)
TINTA_1 = (17, 17, 19)        # --ink-1
TINTA_2 = (62, 62, 68)        # --ink-2
TINTA_3 = (104, 103, 109)     # --ink-3
LINHA = (217, 222, 221)       # --line
DESTAQUE = (27, 95, 171)      # #1b5fab
SOBE = (10, 125, 79)          # #0a7d4f
CAI = (179, 38, 30)           # #b3261e
LOGO_FUNDO = (22, 27, 24)     # #161B18 (o mesmo do ícone do menu)
LOGO_LINHA = (217, 181, 74)   # #D9B54A

W, H = 1200, 630
PAD = 72

# Os 3 números do card (mesmos destaques da página inicial).
CARDS = [
    {"cod": 432, "rot": "Meta Selic", "suf": "% a.a.", "casas": 2},
    {"cod": 13522, "rot": "IPCA 12 meses", "suf": "%", "casas": 2},
    {"cod": 1, "rot": "Dólar (venda)", "pref": "R$ ", "casas": 4},
]

SERIF = str(FONTS / "IBMPlexSerif-Regular.ttf")
MANROPE = str(FONTS / "Manrope[wght].ttf")
SANS = str(FONTS / "SourceSans3[wght].ttf")
MONO_M = str(FONTS / "IBMPlexMono-Medium.ttf")
MONO_R = str(FONTS / "IBMPlexMono-Regular.ttf")


def variavel(caminho: str, size: int, wght: int):
    """Fonte variável no peso pedido (eixo wght)."""
    f = ImageFont.truetype(caminho, size)
    try:
        vals = []
        for ax in f.get_variation_axes():
            nm = ax["name"]
            nm = (nm.decode() if isinstance(nm, (bytes, bytearray)) else nm).lower()
            vals.append(wght if ("weight" in nm or nm == "wght") else ax.get("default", 0))
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    return f


def parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


def fmt_num(v: float, dec: int) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load_series() -> dict:
    try:
        arr = json.loads((DATA_DIR / "series.json").read_text(encoding="utf-8"))
        return {int(s["codigo"]): s for s in arr}
    except Exception:
        return {}


def load_history(cod: int) -> list[dict]:
    p = DATA_DIR / f"{cod}_history.json"
    if not p.exists():
        return []
    out = []
    for x in json.loads(p.read_text(encoding="utf-8")):
        try:
            out.append({"dt": parse_date(x["data"]), "v": float(str(x["valor"]).replace(",", "."))})
        except (ValueError, KeyError):
            continue
    out.sort(key=lambda p: p["dt"])
    return out


def delta_mes(hist: list[dict]) -> float | None:
    """Variação do último valor vs. o fechamento do mês anterior."""
    if len(hist) < 2:
        return None
    porm: dict[str, float] = {}
    for p in hist:
        porm[p["dt"].strftime("%Y-%m")] = p["v"]
    chaves = sorted(porm)
    if len(chaves) < 2:
        return None
    return porm[chaves[-1]] - porm[chaves[-2]]


def meta_dt() -> datetime:
    meta = DATA_DIR / "meta.json"
    if meta.exists():
        try:
            return datetime.fromisoformat(json.loads(meta.read_text(encoding="utf-8")).get("gerado_em", ""))
        except Exception:
            pass
    return datetime.now()


def draw_text(d, xy, text, font, fill, ls=0, anchor="la"):
    """Desenha texto; com ls>0 aplica tracking (letter-spacing) manual."""
    if ls <= 0:
        d.text(xy, text, font=font, fill=fill, anchor=anchor)
        return
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor="la")
        x += d.textlength(ch, font=font) + ls


def main() -> None:
    series = load_series()
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)

    f_marca = ImageFont.truetype(MONO_M, 22)
    f_data = ImageFont.truetype(MONO_R, 22)
    f_title = ImageFont.truetype(SERIF, 76)
    f_sub = variavel(SANS, 30, 400)
    f_rot = ImageFont.truetype(MONO_M, 20)
    f_val = variavel(MANROPE, 62, 800)
    f_suf = ImageFont.truetype(MONO_R, 24)
    f_delta = ImageFont.truetype(MONO_M, 21)
    f_rodape = ImageFont.truetype(MONO_R, 21)

    # Faixa de topo: ícone + nome, e a data da coleta à direita.
    d.rounded_rectangle([PAD, 52, PAD + 44, 96], radius=10, fill=LOGO_FUNDO)
    d.line([(PAD + 9, 85), (PAD + 19, 75), (PAD + 28, 80), (PAD + 37, 63)], fill=LOGO_LINHA, width=4, joint="curve")
    draw_text(d, (PAD + 60, 62), "OBSERVATÓRIO DE TAXAS", f_marca, TINTA_1, ls=3)
    dt = meta_dt()
    data = f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    d.text((W - PAD, 64), data, font=f_data, fill=TINTA_3, anchor="ra")

    # Título com o ponto na cor de destaque, como na página inicial.
    titulo = "Indicadores do Brasil, hoje"
    d.text((PAD - 4, 134), titulo, font=f_title, fill=TINTA_1)
    tw = d.textlength(titulo, font=f_title)
    d.text((PAD - 4 + tw, 134), ".", font=f_title, fill=DESTAQUE)
    d.text((PAD, 238), "Direto do Banco Central, com a fonte de cada número.", font=f_sub, fill=TINTA_2)

    # Três números, em cartões.
    gap = 20
    col_w = (W - 2 * PAD - 2 * gap) / 3
    top, alt = 312, 214
    for i, c in enumerate(CARDS):
        s = series.get(c["cod"], {})
        x0 = PAD + i * (col_w + gap)
        d.rounded_rectangle([x0, top, x0 + col_w, top + alt], radius=14, fill=SUPERFICIE, outline=LINHA, width=2)
        x = x0 + 26
        draw_text(d, (x, top + 26), c["rot"].upper(), f_rot, TINTA_3, ls=2)
        try:
            val = float(str(s.get("valor_atual", "")).replace(",", "."))
            vtxt = c.get("pref", "") + fmt_num(val, c["casas"])
        except (ValueError, TypeError):
            vtxt = "—"
        d.text((x - 2, top + 60), vtxt, font=f_val, fill=TINTA_1)
        if c.get("suf"):
            vw = d.textlength(vtxt, font=f_val)
            d.text((x + vw + 10, top + 92), c["suf"], font=f_suf, fill=TINTA_3)
        # Direcionador do mês, desenhado (a fonte mono não traz ▲▼■).
        dy = top + 156
        dl = delta_mes(load_history(c["cod"]))
        if dl is not None and abs(dl) < 0.5 * 10 ** -c["casas"]:
            dl = 0.0
        if dl is None:
            d.text((x, dy), "sem base de comparação", font=f_delta, fill=TINTA_3)
            continue
        cor = SOBE if dl > 0 else CAI if dl < 0 else TINTA_3
        if dl > 0:
            d.polygon([(x, dy + 17), (x + 14, dy + 17), (x + 7, dy + 3)], fill=cor)
        elif dl < 0:
            d.polygon([(x, dy + 3), (x + 14, dy + 3), (x + 7, dy + 17)], fill=cor)
        else:
            d.rectangle([x + 1, dy + 4, x + 13, dy + 16], fill=cor)
        unidade = ("R$ " + fmt_num(abs(dl), c["casas"])) if c.get("pref") else (fmt_num(abs(dl), c["casas"]) + " p.p.")
        sinal = "+" if dl > 0 else "-" if dl < 0 else ""
        d.text((x + 24, dy), f"{sinal}{unidade} no mês", font=f_delta, fill=cor)

    # Rodapé: endereço e fonte.
    d.line([(PAD, H - 66), (W - PAD, H - 66)], fill=LINHA, width=2)
    d.text((PAD, H - 50), "observatoriodetaxas.tec.br", font=f_rodape, fill=DESTAQUE)
    d.text((W - PAD, H - 50), "fonte: SGS / Banco Central do Brasil", font=f_rodape, fill=TINTA_3, anchor="ra")

    img.save(OUT, "PNG", optimize=True)
    versiona_og()
    print(f"og-image.png gerado: {W}x{H} ({OUT.stat().st_size // 1024} KB).")


def versiona_og() -> None:
    """Põe ?v=<hash da imagem> no og:image e no twitter:image da página
    inicial. WhatsApp, LinkedIn e afins guardam a imagem pela URL: com a URL
    nova, eles baixam o card novo em vez de mostrar o antigo do cache."""
    import hashlib
    import re
    v = hashlib.sha256(OUT.read_bytes()).hexdigest()[:10]
    index = ROOT / "docs" / "index.html"
    html = index.read_text(encoding="utf-8")
    novo = re.sub(r'(content="https://observatoriodetaxas\.tec\.br/og-image\.png)(?:\?v=[0-9a-f]+)?"',
                  rf'\g<1>?v={v}"', html)
    if novo != html:
        index.write_text(novo, encoding="utf-8")


if __name__ == "__main__":
    main()
