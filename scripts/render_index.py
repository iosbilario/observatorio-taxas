"""
render_index.py — Assa dados no HTML da landing (docs/index.html).

Lê docs/data/series.json + os history.json e injeta, entre marcadores no
index.html, blocos ESTÁTICOS (funcionam sem JavaScript):

  <!-- boletim:inicio -->   linha de carimbo (hora + commit) + os 5 números do dia
  <!-- var:inicio -->       recibo do VAR (IPCA 2019-2022 vs 2023-hoje), com veredito
  <!-- rebobinar:inicio -->  fita de 6 meses + a manchete do mês atual

Também regenera docs/sitemap.xml com todas as páginas (topo + reajuste + correção).

Roda DEPOIS do fetch no cron. O JS da página hidrata por cima (sparklines,
calculadora), mas todos os números aparecem no HTML cru. Idempotente, só stdlib.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
INDEX = ROOT / "docs" / "index.html"
SITEMAP = ROOT / "docs" / "sitemap.xml"
BASE_URL = "https://observatoriodetaxas.tec.br"
REPO_URL = "https://github.com/iosbilario/observatorio-taxas"

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESC = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Os 5 números do dia (ordem = ordem de exibição).
BOLETIM = [
    {"cod": 432,   "anchor": "selic",      "h2": "Taxa Selic hoje",              "rot": "Meta Selic",      "suf": "% a.a.", "casas": 2},
    {"cod": 13522, "anchor": "ipca",       "h2": "IPCA acumulado 12 meses hoje", "rot": "IPCA 12 meses",   "suf": "%",      "casas": 2},
    {"cod": 1,     "anchor": "dolar",      "h2": "Cotação do dólar hoje",        "rot": "Dólar (venda)",   "pref": "R$ ",  "casas": 4},
    {"cod": 189,   "anchor": "igpm",       "h2": "IGP-M no mês hoje",            "rot": "IGP-M no mês",    "suf": "%",      "casas": 2},
    {"cod": 24369, "anchor": "desemprego", "h2": "Taxa de desemprego hoje",      "rot": "Desemprego",      "suf": "%",      "casas": 1},
]
# Indicadores de nível para eleger a manchete do Rebobinar (z-score do movimento).
# Mesmo conjunto do rebobinar.html, para a manchete assada bater com a da página.
NIVEL = {432: "a Selic", 13522: "a inflação em 12 meses", 1: "o dólar",
         21619: "o euro", 24369: "o desemprego"}


# --------------------------------------------------------------------------- #
def parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


def load_history(cod: int) -> list[dict]:
    p = DATA_DIR / f"{cod}_history.json"
    if not p.exists():
        return []
    pts = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for x in pts:
        try:
            out.append({"dt": parse_date(x["data"]), "v": float(str(x["valor"]).replace(",", ".")), "data": x["data"]})
        except (ValueError, KeyError):
            continue
    out.sort(key=lambda p: p["dt"])
    return out


def fmt_num(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mensal_ultimo(pts: list[dict]) -> list[tuple[str, float]]:
    """[(aaaa-mm, último valor do mês), ...] em ordem cronológica."""
    porm: dict[str, float] = {}
    for p in pts:
        porm[p["dt"].strftime("%Y-%m")] = p["v"]
    return sorted(porm.items())


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]


def _meta_dt() -> datetime:
    meta = DATA_DIR / "meta.json"
    if meta.exists():
        try:
            iso = json.loads(meta.read_text(encoding="utf-8")).get("gerado_em", "")
            return datetime.fromisoformat(iso)
        except Exception:
            pass
    return datetime.now()


def hora_coleta() -> str:
    return _meta_dt().strftime("%H:%M")


def data_extenso() -> str:
    d = _meta_dt()
    return f"{cap(DIAS[d.weekday()])}, {d.day} de {MESC[d.month - 1]} de {d.year}"


# --------------------------------------------------------------------------- #
def bloco_boletim() -> str:
    hora, sha = hora_coleta(), git_sha()
    data_el = f'<p class="masthead-data" id="hoje">{esc(data_extenso())}</p>'
    carimbo = (f'<p class="carimbo-linha">coletado às {esc(hora)} · '
               + (f'commit <a href="{REPO_URL}/commits/main">{esc(sha)}</a> · ' if sha else "")
               + 'fonte SGS/BACEN</p>')
    carimbo = data_el + "\n" + carimbo

    cards = []
    for b in BOLETIM:
        pts = load_history(b["cod"])
        if not pts:
            continue
        ml = mensal_ultimo(pts)
        cur = pts[-1]["v"]
        ref = pts[-1]["dt"]
        prev = ml[-2][1] if len(ml) >= 2 else None
        pref, suf, dec = b.get("pref", ""), b.get("suf", ""), b["casas"]
        valor = pref + fmt_num(cur, dec)

        if prev is not None:
            d = cur - prev
            cls = "up" if d > 1e-9 else "down" if d < -1e-9 else "flat"
            seta = "▲" if cls == "up" else "▼" if cls == "down" else "■"
            unidade = ("R$ " + fmt_num(abs(d), dec)) if pref else (fmt_num(abs(d), dec) + " p.p.")
            delta = f'{seta} {"+" if d > 0 else "-" if d < 0 else ""}{unidade} no mês'
        else:
            cls, delta = "flat", "sem base de comparação"

        cards.append(
            f'<article class="num" id="{b["anchor"]}">'
            f'<h2 class="num-tag">{esc(b["h2"])}</h2>'
            f'<p class="num-rot">{esc(b["rot"])}</p>'
            f'<p class="num-val"><span class="v">{esc(valor)}</span>'
            + (f'<span class="suf">{esc(suf)}</span>' if suf else "")
            + f'</p>'
            f'<p class="num-delta {cls}">{esc(delta)}</p>'
            f'<p class="num-ref">ref. {ref.strftime("%d/%m/%Y")}</p>'
            f'<div class="spark" data-cod="{b["cod"]}" data-casas="{dec}" aria-hidden="true"></div>'
            f'</article>'
        )
    return carimbo + '\n<div class="boletim">\n' + "\n".join(cards) + "\n</div>"


def acumulado(pts: list[dict], a: str, z: str) -> tuple[float, int]:
    """Acumulado composto das variações mensais entre aaaa-mm a e z (inclusive)."""
    fator, n = 1.0, 0
    for p in pts:
        ym = p["dt"].strftime("%Y-%m")
        if a <= ym <= z:
            fator *= 1 + p["v"] / 100.0
            n += 1
    return (fator - 1.0) * 100.0, n


def bloco_var() -> str:
    pts = load_history(433)  # IPCA variação mensal
    if not pts:
        return ""
    ult = pts[-1]["dt"].strftime("%Y-%m")
    a1, a2, b1, b2 = "2019-01", "2022-12", "2023-01", ult
    ac_a, _ = acumulado(pts, a1, a2)
    ac_b, _ = acumulado(pts, b1, b2)
    conf = ac_a > ac_b
    vered = "CONFERE" if conf else "NÃO CONFERE"
    vcls = "ok" if conf else "no"

    def rot(ym):
        y, m = ym.split("-")
        return f"{MES[int(m) - 1]}/{y}"

    claim = (f"O IPCA acumulado entre {rot(a1)} e {rot(a2)} foi maior "
             f"do que entre {rot(b1)} e {rot(b2)}.")
    perma = (f"var.html?s=433&op=acum&a1={a1}&a2={a2}&b1={b1}&b2={b2}&cmp=maior")

    return (
        '<div class="recibo-mini">'
        '<p class="rc-h">RECIBO · VAR DA ECONOMIA</p>'
        f'<p class="rc-claim">{esc(claim)}</p>'
        f'<div class="rc-row"><span>{esc(rot(a1))} a {esc(rot(a2))}</span><b>{fmt_num(ac_a)}%</b></div>'
        f'<div class="rc-row"><span>{esc(rot(b1))} a {esc(rot(b2))}</span><b>{fmt_num(ac_b)}%</b></div>'
        f'<p class="rc-vered {vcls}">{vered}</p>'
        '</div>'
        f'<a class="btn-link" href="{perma}">Abrir e auditar este recibo no VAR →</a>'
    )


def _ym_num(ym: str) -> int:
    y, m = ym.split("-"); return int(y) * 12 + int(m) - 1


def _ym_from(n: int) -> str:
    return f"{n // 12}-{n % 12 + 1:02d}"


def _asof(ml: list[tuple[str, float]], alvo: str):
    """Valor as-of fim do mês alvo (carrega o último conhecido; None se não há)."""
    val = None
    for ym, v in ml:
        if ym <= alvo:
            val = v
        else:
            break
    return val


def bloco_rebobinar() -> str:
    series_ml = {}
    ultimo_mes = ""
    for cod in NIVEL:
        ml = mensal_ultimo(load_history(cod))
        if len(ml) >= 3:
            series_ml[cod] = ml
            ultimo_mes = max(ultimo_mes, ml[-1][0])
    if not series_ml:
        return ""

    prev_mes = _ym_from(_ym_num(ultimo_mes) - 1)
    # Manchete: maior |z| no MESMO mês de referência (as-of, com carry-forward).
    # Série defasada tem delta 0 no mês corrente e não vira manchete.
    melhor = None  # (absz, cod, delta)
    for cod, ml in series_ml.items():
        # Desvio sobre os ~24 meses recentes (mesma janela do rebobinar.html),
        # senão a volatilidade de 2015+ encolhe o z e some com a manchete.
        ml_rec = ml[-25:]
        vals = [v for _, v in ml_rec]
        deltas = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
        if not deltas:
            continue
        mean = sum(deltas) / len(deltas)
        std = math.sqrt(sum((d - mean) ** 2 for d in deltas) / len(deltas))
        cur, prv = _asof(ml, ultimo_mes), _asof(ml, prev_mes)
        if cur is None or prv is None:
            continue
        dlast = cur - prv
        z = 0.0 if std < 1e-9 else dlast / std
        if melhor is None or abs(z) > melhor[0]:
            melhor = (abs(z), cod, dlast)
    if melhor is None:
        return ""

    _, cod, dlast = melhor
    ind = NIVEL[cod]
    y, m = ultimo_mes.split("-")
    mesCap = f"{cap(MESC[int(m) - 1])} de {y}"
    quieto = melhor[0] < 0.4
    direc = "flat" if quieto else ("up" if dlast > 1e-9 else "down" if dlast < -1e-9 else "flat")
    # Templates (sorteio determinístico pelo mês). Sem travessão, sem "ciclo",
    # e sem "de {ind}" (evita a contração "de o"/"de a").
    TPL = {
        "up": ["{mes}: {ind} rouba a cena", "{Ind} não deu trégua em {mes}", "{Ind} ditou o rumo de {mes}"],
        "down": ["{Ind} finalmente cede", "{mes}: {ind} perde força", "{Ind} recuou e marcou {mes}"],
        "flat": ["{mes}: um mês de poucas surpresas", "Poucos números se mexeram em {mes}"],
    }
    lst = TPL[direc]
    h = 2166136261
    for ch in ultimo_mes:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    tpl = lst[h % len(lst)]
    manch = tpl.replace("{mes}", mesCap).replace("{Ind}", cap(ind)).replace("{ind}", ind)

    # Fita: os 6 meses de calendário terminando no mês de referência.
    base = _ym_num(ultimo_mes)
    meses6 = [_ym_from(base - i) for i in range(5, -1, -1)]
    nos = "".join(
        f'<span class="no-mini{" ativo" if i == len(meses6) - 1 else ""}"></span>'
        for i in range(len(meses6))
    )
    r0 = meses6[0].split("-"); r1 = meses6[-1].split("-")
    faixa = f"{MES[int(r0[1]) - 1]}/{r0[0][2:]} … {MES[int(r1[1]) - 1]}/{r1[0][2:]}"

    return (
        f'<div class="fita-mini" aria-hidden="true"><span class="fio-mini"></span>{nos}</div>'
        f'<p class="fita-meses">{esc(faixa)}</p>'
        f'<p class="manchete-mes">{esc(manch)}</p>'
        f'<a class="btn-link" href="rebobinar.html">Rebobinar mês a mês →</a>'
    )


# --------------------------------------------------------------------------- #
def inject(html: str, nome: str, conteudo: str) -> str:
    pat = re.compile(rf"(<!-- {nome}:inicio -->).*?(<!-- {nome}:fim -->)", re.S)
    if not pat.search(html):
        raise SystemExit(f"marcador '{nome}' não encontrado em index.html")
    return pat.sub(lambda m: m.group(1) + "\n" + conteudo + "\n" + m.group(2), html)


def rebuild_sitemap() -> int:
    hoje = datetime.now().strftime("%Y-%m-%d")
    docs = ROOT / "docs"
    urls = [f"{BASE_URL}/", f"{BASE_URL}/rebobinar.html",
            f"{BASE_URL}/var.html", f"{BASE_URL}/retransmissora.html",
            f"{BASE_URL}/reajuste/", f"{BASE_URL}/correcao/"]
    for sub in ("reajuste", "correcao"):
        for idx in sorted((docs / sub).glob("*/index.html")):
            urls.append(f"{BASE_URL}/{sub}/{idx.parent.name}/")
    vistos, unicas = set(), []
    for u in urls:
        if u not in vistos:
            vistos.add(u); unicas.append(u)
    body = "".join(
        f"  <url><loc>{u}</loc><lastmod>{hoje}</lastmod><changefreq>daily</changefreq></url>\n"
        for u in unicas
    )
    SITEMAP.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n",
        encoding="utf-8",
    )
    return len(unicas)


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    html = inject(html, "boletim", bloco_boletim())
    html = inject(html, "var", bloco_var())
    html = inject(html, "rebobinar", bloco_rebobinar())
    INDEX.write_text(html, encoding="utf-8")
    n = rebuild_sitemap()
    print(f"index.html: boletim + VAR + rebobinar assados. sitemap.xml: {n} URLs.")


if __name__ == "__main__":
    main()
