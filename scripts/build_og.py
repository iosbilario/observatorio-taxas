"""
build_og.py — Gera docs/og-image.png automaticamente a cada coleta.

O card social também "se reescreve sozinho": desenha, sobre a identidade da
marca (sala-cofre + carimbo dourado, Fraunces/IBM Plex Mono), os números do dia
(Selic, IPCA 12 meses, Dólar) lidos de docs/data, com a data da coleta.

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

# Paleta da marca (idêntica ao index.html).
COFRE = (14, 18, 16)          # #0E1210
PAPEL = (233, 230, 220)       # #E9E6DC
PAPEL_70 = (183, 181, 173)    # papel a 70%
PAPEL_45 = (135, 134, 128)    # papel a 45%
CARIMBO = (217, 181, 74)      # #D9B54A
ALTA = (63, 214, 143)         # #3FD68F
QUEDA = (228, 87, 79)         # #E4574F
LINHA = (46, 47, 44)          # linha sutil

W, H = 1200, 630
PAD = 72

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Os 3 números do card (mesmos destaques do boletim da landing).
CARDS = [
    {"cod": 432, "rot": "Meta Selic", "suf": "%", "casas": 2},
    {"cod": 13522, "rot": "IPCA 12 meses", "suf": "%", "casas": 2},
    {"cod": 1, "rot": "Dólar", "pref": "R$ ", "casas": 4},
]

FR = str(FONTS / "Fraunces-variable.ttf")
MONO_M = str(FONTS / "IBMPlexMono-Medium.ttf")
MONO_R = str(FONTS / "IBMPlexMono-Regular.ttf")


def fraunces(size: int, wght: int = 600):
    """Fraunces no peso pedido, com opsz no máximo (display) e sem soft/wonk."""
    f = ImageFont.truetype(FR, size)
    try:
        vals = []
        for ax in f.get_variation_axes():
            nm = ax["name"]
            nm = nm.decode() if isinstance(nm, (bytes, bytearray)) else nm
            low = nm.lower()
            if "opt" in low or low == "opsz":
                vals.append(144)
            elif "weight" in low or low == "wght":
                vals.append(wght)
            elif "soft" in low or "wonk" in low:
                vals.append(0)
            else:
                vals.append(ax.get("default", 0))
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
    img = Image.new("RGB", (W, H), COFRE)
    d = ImageDraw.Draw(img)

    # Brilho dourado sutil no canto (eco do admin), desenhado por retângulos leves.
    glow = Image.new("RGB", (W, H), COFRE)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -320, 520, 260], fill=(24, 26, 20))
    img = Image.blend(img, glow, 0.5)
    d = ImageDraw.Draw(img)

    f_kicker = ImageFont.truetype(MONO_M, 20)
    f_title = fraunces(88, 700)
    f_sub = ImageFont.truetype(MONO_R, 24)
    f_rot = ImageFont.truetype(MONO_M, 22)
    f_val = fraunces(66, 600)
    f_suf = ImageFont.truetype(MONO_M, 26)
    f_delta = ImageFont.truetype(MONO_M, 22)
    f_stamp = ImageFont.truetype(MONO_R, 22)

    # Kicker + título + subtítulo.
    draw_text(d, (PAD, 64), "A PRIMEIRA PÁGINA QUE SE REESCREVE SOZINHA", f_kicker, CARIMBO, ls=4)
    d.text((PAD - 2, 96), "Observatório de Taxas", font=f_title, fill=PAPEL)
    d.text((PAD, 214), "Os números do dia da economia brasileira · direto do SGS/BACEN",
           font=f_sub, fill=PAPEL_70)

    # Régua dupla (eco do masthead).
    d.line([(PAD, 262), (W - PAD, 262)], fill=LINHA, width=2)
    d.line([(PAD, 267), (W - PAD, 267)], fill=LINHA, width=1)

    # Três números, em colunas.
    col_w = (W - 2 * PAD) / 3
    top = 312
    for i, c in enumerate(CARDS):
        s = series.get(c["cod"], {})
        x = PAD + i * col_w
        # rótulo
        draw_text(d, (x, top), c["rot"].upper(), f_rot, PAPEL_45, ls=2)
        # valor
        try:
            val = float(str(s.get("valor_atual", "")).replace(",", "."))
            vtxt = c.get("pref", "") + fmt_num(val, c["casas"])
        except (ValueError, TypeError):
            vtxt = "—"
        d.text((x - 2, top + 34), vtxt, font=f_val, fill=PAPEL)
        vw = d.textlength(vtxt, font=f_val)
        if c.get("suf"):
            d.text((x + vw + 12, top + 64), c["suf"], font=f_suf, fill=PAPEL_45)
        # delta no mês — seta desenhada (a fonte mono não traz ▲▼■).
        dy = top + 128
        dl = delta_mes(load_history(c["cod"]))
        if dl is None:
            d.text((x, dy), "sem base de comparação", font=f_delta, fill=PAPEL_45)
        elif abs(dl) < 1e-9:
            d.rectangle([x, dy + 4, x + 13, dy + 17], fill=PAPEL_45)
            d.text((x + 24, dy), "estável no mês", font=f_delta, fill=PAPEL_45)
        else:
            up = dl > 0
            col = ALTA if up else QUEDA
            if up:
                d.polygon([(x, dy + 17), (x + 13, dy + 17), (x + 6.5, dy + 2)], fill=col)
            else:
                d.polygon([(x, dy + 2), (x + 13, dy + 2), (x + 6.5, dy + 17)], fill=col)
            unidade = ("R$ " + fmt_num(abs(dl), c["casas"])) if c.get("pref") else (fmt_num(abs(dl), c["casas"]) + " p.p.")
            txt = ("+" if up else "-") + unidade + " no mês"
            d.text((x + 24, dy), txt, font=f_delta, fill=col)

    # Rodapé: carimbo de coleta + selo dourado (mesma linha da landing).
    dt = meta_dt()
    stamp = f"coletado em {dt.day:02d}/{dt.month:02d}/{dt.year} · fonte SGS / Banco Central do Brasil"
    d.text((PAD, H - PAD - 8), stamp, font=f_stamp, fill=PAPEL_45)

    # Marca: mini gráfico dourado (eco do favicon), canto inferior direito.
    pts = [(W - PAD - 132, H - PAD + 4), (W - PAD - 96, H - PAD - 28),
           (W - PAD - 60, H - PAD - 12), (W - PAD - 8, H - PAD - 56)]
    d.line(pts, fill=CARIMBO, width=4, joint="curve")
    d.ellipse([pts[-1][0] - 6, pts[-1][1] - 6, pts[-1][0] + 6, pts[-1][1] + 6], fill=CARIMBO)

    img.save(OUT, "PNG", optimize=True)
    print(f"og-image.png gerado: {W}x{H} ({OUT.stat().st_size // 1024} KB).")


if __name__ == "__main__":
    main()
