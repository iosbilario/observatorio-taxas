"""
render_index.py — Assa dados no HTML da landing (docs/index.html).

Lê docs/data/series.json + os history.json e injeta, entre marcadores no
index.html, blocos ESTÁTICOS (funcionam sem JavaScript):

  <!-- carimbo:inicio -->   data, hora da coleta e commit
  <!-- boletim:inicio -->   as 5 perguntas do dia, com resposta, valor e direcionador
  <!-- mais:inicio -->      grade com mais 12 indicadores
  <!-- var:inicio -->       recibo do VAR (IPCA 2019-2022 vs 2023-hoje), com veredito
  <!-- rebobinar:inicio -->  fita de 6 meses + a manchete do mês atual

Também regenera docs/sitemap.xml com todas as páginas (topo + reajuste + correção).

Roda DEPOIS do fetch no cron. O JS da página hidrata por cima (sparklines,
calculadora), mas todos os números aparecem no HTML cru. Idempotente, só stdlib.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
INDEX = ROOT / "docs" / "index.html"
SITEMAP = ROOT / "docs" / "sitemap.xml"
LASTMOD_STATE = ROOT / "data" / "sitemap_lastmod.json"
BASE_URL = "https://observatoriodetaxas.tec.br"
REPO_URL = "https://github.com/iosbilario/observatorio-taxas"

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESC = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# As 5 perguntas do dia (ordem = ordem de exibição).
BOLETIM = [
    {"cod": 432, "anchor": "selic", "pergunta": "Qual é a Selic hoje?", "rot": "Meta Selic", "suf": "% a.a.",
     "casas": 2, "link": "indicadores/meta-selic/", "link_txt": "Histórico da Selic"},
    {"cod": 13522, "anchor": "ipca", "pergunta": "Qual é a inflação acumulada em 12 meses?", "rot": "IPCA 12 meses",
     "suf": "%", "casas": 2, "link": "indicadores/ipca-12-meses/", "link_txt": "IPCA mês a mês"},
    {"cod": 1, "anchor": "dolar", "pergunta": "Quanto está o dólar hoje?", "rot": "Dólar (venda)", "pref": "R$ ",
     "casas": 4, "link": "indicadores/dolar/", "link_txt": "Histórico do dólar"},
    {"cod": 189, "anchor": "igpm", "pergunta": "Quanto vai subir o aluguel?", "rot": "IGP-M no mês", "suf": "%",
     "casas": 2, "link": "reajuste/igpm-{mes}/", "link_txt": "Calcular o meu reajuste"},
    {"cod": 24369, "anchor": "desemprego", "pergunta": "Qual é a taxa de desemprego?", "rot": "Desemprego",
     "suf": "%", "casas": 1, "link": "indicadores/desemprego/", "link_txt": "Série completa"},
]

# Mais indicadores (grade abaixo das perguntas). slug = página em /indicadores/.
MAIS = [
    {"cod": 1178, "slug": "selic-efetiva", "rot": "Selic efetiva", "suf": "% a.a.", "casas": 2},
    {"cod": 4389, "slug": "cdi", "rot": "CDI", "suf": "% a.a.", "casas": 2},
    {"cod": 195, "slug": "poupanca", "rot": "Poupança no mês", "suf": "%", "casas": 4},
    {"cod": 226, "slug": "tr", "rot": "TR no mês", "suf": "%", "casas": 4},
    {"cod": 433, "slug": "ipca", "rot": "IPCA no mês", "suf": "%", "casas": 2},
    {"cod": 188, "slug": "inpc", "rot": "INPC no mês", "suf": "%", "casas": 2},
    {"cod": 190, "slug": "igp-di", "rot": "IGP-DI no mês", "suf": "%", "casas": 2},
    {"cod": 21619, "slug": "euro", "rot": "Euro (venda)", "pref": "R$ ", "casas": 4},
    {"cod": 20714, "slug": "juros-do-credito", "rot": "Juros do crédito", "suf": "% a.a.", "casas": 2},
    {"cod": 21082, "slug": "inadimplencia", "rot": "Inadimplência", "suf": "%", "casas": 2},
    {"cod": 24363, "slug": "ibc-br", "rot": "IBC-Br (prévia do PIB)", "casas": 2, "du": " pontos"},
    {"cod": 4513, "slug": "divida-liquida", "rot": "Dívida líquida", "suf": "% do PIB", "casas": 2},
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
def _delta(pts: list[dict], dec: int, pref: str, unidade_delta: str = " p.p.") -> tuple[str, str]:
    """Direcionador do mês: (classe, texto). Compara o último valor com o último
    do mês anterior. ▲ subiu, ▼ caiu, ■ igual."""
    ml = mensal_ultimo(pts)
    if len(ml) < 2:
        return "flat", "sem base de comparação"
    d = pts[-1]["v"] - ml[-2][1]
    if abs(d) < 0.5 * 10 ** -dec:
        d = 0.0
    cls = "up" if d > 0 else "down" if d < 0 else "flat"
    seta = "▲" if cls == "up" else "▼" if cls == "down" else "■"
    unidade = ("R$ " + fmt_num(abs(d), dec)) if pref == "R$ " else (fmt_num(abs(d), dec) + unidade_delta)
    return cls, f'{seta} {"+" if d > 0 else "-" if d < 0 else ""}{unidade} no mês'


def _mes(dt: datetime) -> str:
    return f"{MESC[dt.month - 1]} de {dt.year}"


def bloco_carimbo() -> str:
    """Linha acima do título: data, hora da coleta e commit."""
    hora, sha = hora_coleta(), git_sha()
    return (f'<p class="carimbo-linha"><span id="hoje">{esc(data_extenso())}</span> · coletado às {esc(hora)} · '
            + (f'commit <a href="{REPO_URL}/commits/main">{esc(sha)}</a> · ' if sha else "")
            + 'fonte SGS/BACEN</p>')


def _frase(b: dict, pts: list[dict]) -> str:
    """Resposta em uma frase, montada com os números da série."""
    cur, ref = pts[-1]["v"], pts[-1]["dt"]
    v = fmt_num(cur, b["casas"])
    if b["cod"] == 432:
        desde = pts[-1]["dt"]
        for p in reversed(pts):
            if p["v"] != cur:
                break
            desde = p["dt"]
        antes = next((p["v"] for p in reversed(pts) if p["dt"] < desde), None)
        txt = f"A Meta Selic está em <b>{v}% ao ano</b> desde {desde.strftime('%d/%m/%Y')}"
        if antes is not None:
            txt += f", quando passou de {fmt_num(antes, 2)}% para {v}%"
        return txt + ", por decisão do Copom."
    if b["cod"] == 13522:
        return (f"O IPCA acumulou <b>{v}%</b> nos 12 meses até {_mes(ref)}, pela série 13522 do Banco Central. "
                "O índice é do IBGE.")
    if b["cod"] == 1:
        return (f"O dólar PTAX de venda ficou em <b>R$ {v}</b> em {ref.strftime('%d/%m/%Y')}. "
                "É a taxa de referência do Banco Central, calculada todo dia útil.")
    if b["cod"] == 189:
        fator = 1.0
        for p in pts[-12:]:
            fator *= 1 + p["v"] / 100
        ac = (fator - 1) * 100
        return (f"O IGP-M variou <b>{v}%</b> em {_mes(ref)} e acumula {fmt_num(ac, 2)}% em 12 meses. "
                f"Um aluguel de R$ 2.000,00 reajustado por ele vai a R$ {fmt_num(2000 * fator, 2)}.")
    if b["cod"] == 24369:
        return (f"A desocupação ficou em <b>{v}%</b> no trimestre móvel até {_mes(ref)}, "
                "segundo a PNAD Contínua do IBGE.")
    return f"<b>{v}</b>"


def bloco_boletim() -> str:
    """As cinco perguntas do dia: pergunta, resposta em uma frase, valor,
    direcionador do mês, data de referência e minigráfico."""
    itens = []
    for b in BOLETIM:
        pts = load_history(b["cod"])
        if not pts:
            continue
        pref, suf, dec = b.get("pref", ""), b.get("suf", ""), b["casas"]
        cls, delta = _delta(pts, dec, pref)
        ref = pts[-1]["dt"]
        link = b["link"].replace("{mes}", f"{MESC[ref.month - 1]}-{ref.year}")
        itens.append(
            f'<article class="resp" id="{b["anchor"]}">'
            f'<div class="resp-texto"><h2>{esc(b["pergunta"])}</h2>'
            f'<p>{_frase(b, pts)} <a class="resp-link" href="{link}">{esc(b["link_txt"])} →</a></p></div>'
            f'<div class="resp-lado"><p class="resp-rot">{esc(b["rot"])}</p>'
            f'<p class="resp-val"><span class="v">{esc(pref + fmt_num(pts[-1]["v"], dec))}</span>'
            + (f'<span class="suf">{esc(suf)}</span>' if suf else "")
            + f'</p><p class="num-delta {cls}">{esc(delta)}</p>'
            f'<p class="num-ref">ref. {ref.strftime("%d/%m/%Y")}</p>'
            f'<div class="spark" data-cod="{b["cod"]}" data-casas="{dec}" aria-hidden="true"></div></div>'
            f'</article>'
        )
    return '<div class="respostas">\n' + "\n".join(itens) + "\n</div>"


def bloco_mais() -> str:
    """Mais indicadores: valor atual, direcionador e link para a página da série."""
    cards = []
    for m in MAIS:
        pts = load_history(m["cod"])
        if not pts:
            continue
        pref, suf, dec = m.get("pref", ""), m.get("suf", ""), m["casas"]
        cls, delta = _delta(pts, dec, pref, m.get("du", " p.p."))
        cards.append(
            f'<a class="mais-card" href="indicadores/{m["slug"]}/">'
            f'<span class="mais-rot">{esc(m["rot"])}</span>'
            f'<span class="mais-val">{esc(pref + fmt_num(pts[-1]["v"], dec))}'
            + (f'<small>{esc(suf)}</small>' if suf else "")
            + f'</span><span class="num-delta {cls}">{esc(delta)}</span>'
            f'<span class="num-ref">ref. {pts[-1]["dt"].strftime("%d/%m/%Y")}</span></a>'
        )
    return '<div class="mais-grade">\n' + "\n".join(cards) + "\n</div>"


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


def _hoje_brt() -> str:
    """Data de hoje em Brasília (o cron roda em UTC; o site fala em BRT)."""
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")


# Partes do HTML que mudam sem mudar o conteúdo (o hash do commit no carimbo
# do boletim muda a cada commit do robô, mesmo sem dado novo).
_RUIDO = [re.compile(r'commit <a href="[^"]*">[0-9a-f]{6,40}</a>')]


def impressao_digital(arquivo: Path) -> str:
    """Impressão digital de um arquivo de docs/ (ver impressao_digital_html)."""
    return impressao_digital_html(arquivo.read_text(encoding="utf-8"))


def impressao_digital_html(html: str) -> str:
    """Hash do que importa para quem lê a página: <title>, meta description e
    o conteúdo principal. Fica de fora o que não é conteúdo (CSS, CSP, header
    replicado, beacon), para que o lastmod só mude quando a página muda.
    O rodapé replicado de partials/rodape.html também fica de fora.
    Também usada por indexnow.py para conferir, no site publicado, que a
    versão no ar é a mesma do estado (deploy confirmado).

    Conteúdo principal = trecho entre <!-- conteudo:inicio --> e
    <!-- conteudo:fim --> quando existe (páginas de mês: o bloco de navegação
    "últimos 12 meses", que muda em TODAS as páginas do índice a cada mês
    novo, fica fora dele e não conta como mudança da página); senão, o
    <body> sem header replicado, scripts e estilos."""
    partes = []
    for pat in (r"<title>.*?</title>", r'<meta name="description"[^>]*>'):
        m = re.search(pat, html, re.S)
        partes.append(m.group(0) if m else "")
    corpo = re.search(r"<!-- conteudo:inicio -->.*?<!-- conteudo:fim -->", html, re.S)
    if corpo:
        partes.append(corpo.group(0))
    else:
        # Sem marcadores: o <body> inteiro menos header replicado, scripts e
        # estilos. (Na landing o boletim do dia fica FORA do <main>.)
        m = re.search(r"<body\b.*</body>", html, re.S)
        b = m.group(0) if m else html
        b = re.sub(r"<!-- nav:start -->.*?<!-- nav:end -->", "", b, flags=re.S)
        b = re.sub(r"<!-- rodape:start -->.*?<!-- rodape:end -->\n?", "", b, flags=re.S)
        b = re.sub(r"<(script|style)\b.*?</\1>", "", b, flags=re.S)
        partes.append(b)
    texto = "\n".join(partes)
    for r in _RUIDO:
        texto = r.sub("", texto)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _data_git(arquivo: Path) -> str | None:
    """Data do último commit do arquivo, SE o arquivo não mudou desde então.
    Só usada para semear o estado na primeira execução."""
    try:
        rel = arquivo.relative_to(ROOT).as_posix()
        limpo = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT,
                               capture_output=True, timeout=10).returncode == 0
        if not limpo:
            return None
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT,
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def _arquivo_da_url(url: str) -> Path:
    caminho = url[len(BASE_URL) + 1:]
    return ROOT / "docs" / (caminho + "index.html" if caminho.endswith("/") or caminho == "" else caminho)


def rebuild_sitemap() -> int:
    """Único escritor de docs/sitemap.xml.

    lastmod por URL = última data em que a impressão digital do conteúdo
    mudou, guardada em data/sitemap_lastmod.json (versionado junto com os
    dados). Antes, todas as URLs recebiam a data do dia a cada coleta, o que
    tornava o lastmod inútil para os buscadores e gerava commit diário.
    """
    hoje = _hoje_brt()
    docs = ROOT / "docs"
    # O Radar está fora: as páginas existem em docs/radar/, mas não são
    # divulgadas enquanto o coletor não estiver no ar.
    urls = [f"{BASE_URL}/", f"{BASE_URL}/rebobinar.html",
            f"{BASE_URL}/var.html", f"{BASE_URL}/retransmissora.html",
            f"{BASE_URL}/reajuste/", f"{BASE_URL}/correcao/", f"{BASE_URL}/apoie/", f"{BASE_URL}/sobre/", f"{BASE_URL}/privacidade/", f"{BASE_URL}/termos/", f"{BASE_URL}/mcp/", f"{BASE_URL}/indicadores/", f"{BASE_URL}/comparador/", f"{BASE_URL}/simulador-cdi/", f"{BASE_URL}/guias/"]
    for sub in ("reajuste", "correcao", "indicadores", "guias"):
        for idx in sorted((docs / sub).glob("*/index.html")):
            urls.append(f"{BASE_URL}/{sub}/{idx.parent.name}/")
    vistos, unicas = set(), []
    for u in urls:
        if u not in vistos and _arquivo_da_url(u).is_file():
            vistos.add(u); unicas.append(u)

    estado: dict = {}
    if LASTMOD_STATE.exists():
        try:
            estado = json.loads(LASTMOD_STATE.read_text(encoding="utf-8"))
        except ValueError:
            estado = {}
    semear = not estado
    novo: dict = {}
    for u in unicas:
        arq = _arquivo_da_url(u)
        h = impressao_digital(arq)
        ant = estado.get(u)
        if ant and ant.get("hash") == h:
            novo[u] = ant
        else:
            data = (_data_git(arq) if semear else None) or hoje
            novo[u] = {"hash": h, "lastmod": data}

    texto_estado = json.dumps(novo, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if not LASTMOD_STATE.exists() or LASTMOD_STATE.read_text(encoding="utf-8") != texto_estado:
        LASTMOD_STATE.write_text(texto_estado, encoding="utf-8")

    body = "".join(
        # loc percent-encoded (protocolo de sitemaps exige URL escapada; as
        # páginas de "março" têm "ç" no caminho). É a MESMA URL, só escapada.
        f"  <url><loc>{quote(u, safe=':/')}</loc><lastmod>{novo[u]['lastmod']}</lastmod></url>\n"
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
    html = inject(html, "carimbo", bloco_carimbo())
    html = inject(html, "boletim", bloco_boletim())
    html = inject(html, "mais", bloco_mais())
    html = inject(html, "var", bloco_var())
    html = inject(html, "rebobinar", bloco_rebobinar())
    INDEX.write_text(html, encoding="utf-8")
    n = rebuild_sitemap()
    print(f"index.html: carimbo + perguntas + mais indicadores + VAR + rebobinar assados. sitemap.xml: {n} URLs.")


if __name__ == "__main__":
    main()
