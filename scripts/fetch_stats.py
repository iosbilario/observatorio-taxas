"""
fetch_stats.py — Coletor de estatísticas de acesso (GoatCounter).

Fecha o ciclo do observatório também para o VOLUME DE ACESSO, no mesmo espírito
zero-custo do resto do projeto: o beacon do GoatCounter (injetado nas páginas por
build_pages.py / build_correcao.py e no docs/index.html) registra os acessos; este
robô puxa os números agregados da API pública do GoatCounter e os grava em
`data/stats.json` (espelhado em `docs/data/stats.json`, que é o que o GitHub Pages
serve). O painel `docs/admin/index.html` só lê esse JSON — nada roda no servidor.

Fontes de configuração:
  - `goatcounter_code` em config.yml  -> monta a URL da API.
  - variável de ambiente GOATCOUNTER_TOKEN -> autenticação (Bearer).

Nunca derruba o job:
  - sem token (secret não configurado) -> avisa e sai com código 0;
  - erro de rede / API fora do ar       -> avisa e sai com código 0 SEM
    sobrescrever um stats.json anterior válido.

API (OpenAPI em https://<code>.goatcounter.com/api.json):
  GET /api/v0/stats/total -> {total, stats:[{day, daily}, ...]}   (visitantes)
  GET /api/v0/stats/hits  -> {hits:[{path, count}, ...], more}     (por página)
  GET /api/v0/stats/{page} -> {stats:[{name, count}, ...], more}  (page = toprefs,
      browsers, systems, sizes, locations: origem, navegador, sistema, tela, país)

O que o painel mostra a mais (desde a v1.10.0):
  - comparação dos últimos 30 dias com os 30 anteriores;
  - acessos por hora nas últimas 48 h e média por hora do dia (pico);
  - "última hora registrada": a última hora cheia antes da coleta. Não é
    "online agora": a API agrupa por hora e a coleta roda a cada 6 h;
  - origem dos acessos, navegador, sistema, tamanho de tela e país (top 10);
  - acessos por seção do site (todas as seções, não só reajuste e correção).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"  # espelho servido pelo GitHub Pages

TIMEOUT = 30          # segundos por requisição
HITS_LIMIT = 200      # teto da API por chamada; cobre todas as páginas do site
DIAS_JANELA = 30      # janela "recente" e da série diária

# "All-time": o SaaS do GoatCounter recusa (404) janelas muito largas em
# /stats/total. Tentamos estas janelas (em dias) da maior para a menor e usamos
# a PRIMEIRA que a API aceitar — para um site novo, a maior já responde.
JANELAS_ALL_TIME = (3650, 365, 90, 35)

# Brasil sem horário de verão desde 2019 -> offset fixo, sem depender de tzdata.
BRT = timezone(timedelta(hours=-3))

# Prefixos de slug -> nome de exibição do índice (reajuste e correção).
IDX_NOMES = {"ipca": "IPCA", "igpm": "IGP-M", "inpc": "INPC", "igpdi": "IGP-DI"}

TOP_DETALHE = 10      # itens por lista de origem, navegador, sistema, tela, país
DETALHES = {"origens": "toprefs", "navegadores": "browsers", "sistemas": "systems",
            "telas": "sizes", "paises": "locations"}

# Seções do site pelo começo do path (depois da base). A ordem importa: a
# primeira que casar vence ("reajuste/evolucao" antes de "reajuste").
SECOES = [
    ("Evolução do contrato", ("reajuste/evolucao",)),
    ("Reajuste", ("reajuste",)),
    ("Correção", ("correcao",)),
    ("Indicadores", ("indicadores",)),
    ("Comparador", ("comparador",)),
    ("Simulador de CDI", ("simulador-cdi",)),
    ("VAR da Economia", ("var.html",)),
    ("Divulgações", ("divulgacoes", "feed.xml")),
    ("Calendário", ("calendario",)),
    ("O que mudou", ("mudancas",)),
    ("Versão histórica", ("historico",)),
    ("Guias", ("guias",)),
    ("Rebobinar", ("rebobinar.html",)),
    ("Embeds", ("embed.html", "retransmissora.html")),
    ("MCP", ("mcp",)),
    ("Institucional", ("sobre", "apoie", "privacidade", "termos")),
    ("Admin", ("admin",)),
]


# --------------------------------------------------------------------------- #
# Config / IO
# --------------------------------------------------------------------------- #
def load_code() -> str:
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return str(cfg.get("goatcounter_code", "")).strip()
    except Exception as exc:  # noqa: BLE001 — config ilegível não deve quebrar o job
        print(f"[aviso] não consegui ler config.yml: {exc}", file=sys.stderr)
        return ""


def write_json(path: Path, payload) -> None:
    """JSON estável (UTF-8, indentado, chaves ordenadas) p/ git diff limpo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Cliente da API do GoatCounter
# --------------------------------------------------------------------------- #
def rfc3339(dt: datetime) -> str:
    """Timestamp arredondado à hora, como a API pede (start/end)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")


# /stats/sizes traz o nome vazio e só o id da faixa de largura.
TELAS = {"phone": "Celular", "largephone": "Celular grande", "tablet": "Tablet",
         "desktop": "Computador", "desktophd": "Computador (tela grande)", "unknown": "Desconhecido"}
# /stats/locations traz o nome do país em inglês.
PAISES = {"Brazil": "Brasil", "United States": "Estados Unidos", "Portugal": "Portugal", "Spain": "Espanha",
          "Argentina": "Argentina", "Germany": "Alemanha", "France": "França", "United Kingdom": "Reino Unido",
          "Canada": "Canadá", "Mexico": "México", "Netherlands": "Países Baixos", "Italy": "Itália",
          "Ireland": "Irlanda", "Japan": "Japão", "China": "China", "India": "Índia", "Chile": "Chile",
          "Colombia": "Colômbia", "Uruguay": "Uruguai", "Paraguay": "Paraguai", "Peru": "Peru",
          "Switzerland": "Suíça", "Belgium": "Bélgica", "Singapore": "Singapura", "Australia": "Austrália",
          "Russia": "Rússia", "Sweden": "Suécia", "Finland": "Finlândia", "Poland": "Polônia",
          "Turkey": "Turquia", "Türkiye": "Turquia", "United Arab Emirates": "Emirados Árabes Unidos",
          "Austria": "Áustria", "Norway": "Noruega", "Denmark": "Dinamarca", "Greece": "Grécia",
          "Czechia": "Tchéquia", "Czech Republic": "Tchéquia", "Hungary": "Hungria", "Romania": "Romênia",
          "Ukraine": "Ucrânia", "Israel": "Israel", "Saudi Arabia": "Arábia Saudita", "South Africa": "África do Sul",
          "Angola": "Angola", "Mozambique": "Moçambique", "Cape Verde": "Cabo Verde", "Cabo Verde": "Cabo Verde",
          "Bolivia": "Bolívia", "Venezuela": "Venezuela", "Ecuador": "Equador", "Panama": "Panamá",
          "Costa Rica": "Costa Rica", "Dominican Republic": "República Dominicana", "Cuba": "Cuba",
          "Guatemala": "Guatemala", "New Zealand": "Nova Zelândia", "South Korea": "Coreia do Sul",
          "Korea, Republic of": "Coreia do Sul", "Hong Kong": "Hong Kong", "Taiwan": "Taiwan",
          "Indonesia": "Indonésia", "Philippines": "Filipinas", "Vietnam": "Vietnã", "Thailand": "Tailândia",
          "Malaysia": "Malásia", "Pakistan": "Paquistão", "Bangladesh": "Bangladesh", "Egypt": "Egito",
          "Nigeria": "Nigéria", "Morocco": "Marrocos", "Luxembourg": "Luxemburgo",
          "(unknown)": "Desconhecido", "": "Desconhecido"}


def nome_detalhe(pagina: str, s: dict) -> str:
    """Nome legível de um item de /stats/{pagina}, em português."""
    nome = (s.get("name") or "").strip()
    if pagina == "sizes":
        return TELAS.get(str(s.get("id") or "").strip(), nome or "Desconhecido")
    if pagina == "locations":
        return PAISES.get(nome, nome)
    if pagina == "toprefs" and not nome:
        return "Acesso direto ou sem origem"
    return nome or "Desconhecido"


# Origem dos acessos: o painel separa quem veio de fora, quem chegou sem
# referência (link digitado, app, favorito) e a navegação dentro do próprio site.
DOMINIO_PROPRIO = "observatoriodetaxas.tec.br"
LIMITE_ORIGENS = 100   # pede mais que o top 10 para classificar e fechar o total

# Funis medidos com eventos do GoatCounter (desde 27/11/2026): página de
# entrada, clique no convite, página da ferramenta e cálculo feito pela pessoa.
EVENTOS_DESDE = "2026-11-27"
FUNIS = [
    {"id": "cdi", "nome": "CDI → simulador", "etapas": [
        ("pagina", "indicadores/cdi", "Visitantes da página do CDI"),
        ("evento", "cta-simulador-cdi", "Clicaram em \u201cSimule quanto R$ 1.000 rende\u201d"),
        ("pagina", "simulador-cdi", "Visitantes do simulador"),
        ("evento", "calculo-simulador-cdi", "Fizeram um cálculo no simulador"),
    ]},
    {"id": "igpm", "nome": "IGP-M → reajuste", "etapas": [
        ("pagina", "indicadores/igp-m", "Visitantes da página do IGP-M"),
        ("evento", "cta-reajuste-igpm", "Clicaram em \u201cCalcule o reajuste do aluguel\u201d"),
        ("prefixo", "reajuste/igpm-", "Visitantes das páginas de reajuste pelo IGP-M"),
        ("evento", "calculo-reajuste-igpm", "Calcularam um reajuste pelo IGP-M"),
    ]},
]


def tipo_origem(nome: str) -> str:
    n = (nome or "").strip().lower()
    if not n:
        return "direto"
    if n == DOMINIO_PROPRIO or n.startswith(DOMINIO_PROPRIO + "/") or n.endswith("." + DOMINIO_PROPRIO):
        return "interno"
    return "externo"


def resume_origens(itens: list[dict], completo: bool, visitantes: int) -> dict:
    """Origens separadas em externo, direto e interno, com o denominador explícito.

    itens = [{nome, acessos}] cru de /stats/toprefs (nome vazio = sem referência).
    'outros_externos' só é calculado quando a API devolveu a lista inteira
    (completo), porque só então a soma fecha.
    """
    soma = {"externo": 0, "direto": 0, "interno": 0}
    externas = []
    for i in itens:
        k = tipo_origem(i["nome"])
        soma[k] += i["acessos"]
        if k == "externo":
            externas.append(i)
    top = sorted(externas, key=lambda i: -i["acessos"])[:TOP_DETALHE]
    return {
        "denominador": visitantes,
        "completo": completo,
        "totais": soma,
        "externas": top,
        "outros_externos": soma["externo"] - sum(i["acessos"] for i in top) if completo else None,
    }


def norm_path(path: str) -> str:
    p = (path or "").split("?")[0].split("#")[0].lower().strip("/")
    if p.startswith("observatorio-taxas"):
        p = p[len("observatorio-taxas"):].strip("/")
    return p[:-len("/index.html")] if p.endswith("/index.html") else p


def funis(paginas: list[dict], eventos: list[dict]) -> list[dict]:
    """Contagem de cada etapa dos funis. São visitantes por página ou por
    evento, contados separadamente: não é uma taxa de conversão exata."""
    por_pagina: dict[str, int] = {}
    for h in paginas:
        k = norm_path(h["path"])
        por_pagina[k] = por_pagina.get(k, 0) + h["count"]
    por_evento = {h["path"].strip("/"): h["count"] for h in eventos}
    saida = []
    for f in FUNIS:
        etapas = []
        for tipo, chave, rotulo in f["etapas"]:
            if tipo == "pagina":
                n = por_pagina.get(chave, 0)
            elif tipo == "prefixo":
                n = sum(v for k, v in por_pagina.items() if k.startswith(chave))
            else:
                n = por_evento.get(chave, 0)
            etapas.append({"tipo": tipo, "chave": chave, "rotulo": rotulo, "visitantes": n})
        saida.append({"id": f["id"], "nome": f["nome"], "etapas": etapas})
    return saida


class GoatCounter:
    def __init__(self, code: str, token: str):
        self.base = f"https://{code}.goatcounter.com/api/v0"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        self.houve_sucesso = False  # ao menos uma chamada 200? (evita clobber)

    def _get(self, endpoint: str, params: dict) -> dict:
        resp = self.session.get(f"{self.base}{endpoint}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        self.houve_sucesso = True
        return data if isinstance(data, dict) else {}

    def total(self, start: str, end: str) -> tuple[bool, int, list[dict]]:
        """(ok, visitantes no período, série diária [{data, acessos}, ...]).

        ok=False se a chamada não retornou 200 — o chamador usa isso para tentar
        janelas menores no 'all-time' (o SaaS 404a janelas muito largas).
        """
        try:
            data = self._get("/stats/total", {"start": start, "end": end})
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] /stats/total ({start}..{end}) falhou: {exc}", file=sys.stderr)
            return False, 0, []
        total = int(data.get("total") or 0)
        diaria = [
            {"data": s.get("day"), "acessos": int(s.get("daily") or 0),
             "por_hora": [int(x or 0) for x in (s.get("hourly") or [])][:24]}
            for s in (data.get("stats") or []) if s.get("day")
        ]
        return True, total, diaria

    def detalhe(self, pagina: str, start: str, end: str) -> list[dict]:
        """Top de /stats/{pagina} (browsers, sizes...): [{nome, acessos}, ...]."""
        itens, _ = self.detalhe_cru(pagina, start, end, TOP_DETALHE)
        return [{"nome": nome_detalhe(pagina, s), "acessos": int(s.get("count") or 0)} for s in itens][:TOP_DETALHE]

    def detalhe_cru(self, pagina: str, start: str, end: str, limite: int) -> tuple[list[dict], bool | None]:
        """(itens crus de /stats/{pagina}, completo?). completo=None se falhou."""
        try:
            data = self._get(f"/stats/{pagina}", {"start": start, "end": end, "limit": limite})
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] /stats/{pagina} falhou: {exc}", file=sys.stderr)
            return [], None
        return list(data.get("stats") or []), not data.get("more")

    def hits(self, start: str, end: str) -> list[dict]:
        """Páginas do período: [{path, count}, ...] (até HITS_LIMIT)."""
        try:
            data = self._get("/stats/hits",
                             {"start": start, "end": end, "limit": HITS_LIMIT})
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] /stats/hits falhou: {exc}", file=sys.stderr)
            return []
        if data.get("more"):
            print(f"[aviso] mais de {HITS_LIMIT} páginas distintas; a cauda longa "
                  "foi truncada (não afeta grupos nem o Top 15).", file=sys.stderr)
        return [
            {"path": h.get("path") or "", "count": int(h.get("count") or 0), "event": bool(h.get("event"))}
            for h in (data.get("hits") or [])
        ]


# --------------------------------------------------------------------------- #
# Agregação por recurso
# --------------------------------------------------------------------------- #
def _seg_apos(path: str, marcador: str) -> str:
    """Primeiro segmento após '<marcador>' no path (ex.: 'ipca-junho-2026')."""
    i = path.find(marcador)
    if i == -1:
        return ""
    resto = path[i + len(marcador):].strip("/")
    return resto.split("/")[0] if resto else ""


def classificar(path: str) -> tuple[str | None, str | None]:
    """Mapeia um path para (grupo, índice). grupo None = fora dos grupos nomeados.

    Tolerante ao prefixo de base do GitHub Pages (/observatorio-taxas/...),
    a querystrings e a variações com/sem barra final.
    """
    p = (path or "").split("?")[0].split("#")[0].lower()
    if "/reajuste/" in p or p.endswith("/reajuste"):
        return "Reajuste", IDX_NOMES.get(_seg_apos(p, "/reajuste/").split("-")[0])
    if "/correcao/" in p or p.endswith("/correcao"):
        return "Correção", IDX_NOMES.get(_seg_apos(p, "/correcao/"))
    if "/admin/" in p or p.endswith("/admin"):
        return "Admin", None
    # Raiz do site (com ou sem o prefixo do repositório) -> Home.
    segs = [s for s in p.split("/") if s and s != "index.html"]
    if segs and segs[0] == "observatorio-taxas":
        segs = segs[1:]
    if not segs:
        return "Home", None
    return None, None  # conta no total/top, mas fora dos grupos nomeados


def secao(path: str) -> str:
    """Seção do site de um path (Home, Reajuste, Indicadores...; 'Outras')."""
    p = (path or "").split("?")[0].split("#")[0].lower().strip("/")
    if p.startswith("observatorio-taxas"):
        p = p[len("observatorio-taxas"):].strip("/")
    if p in ("", "index.html"):
        return "Home"
    for nome, prefixos in SECOES:
        if any(p == x or p.startswith(x + "/") or p.startswith(x + "?") for x in prefixos):
            return nome
    return "Outras"


def agrega_secoes(hits: list[dict]) -> list[dict]:
    """[{secao, acessos}] em ordem decrescente, só as que tiveram acesso."""
    soma: dict[str, int] = {}
    for h in hits:
        s = secao(h["path"])
        soma[s] = soma.get(s, 0) + h["count"]
    return [{"secao": s, "acessos": n} for s, n in sorted(soma.items(), key=lambda x: (-x[1], x[0])) if n]


def por_hora(serie: list[dict], agora_brt: datetime) -> tuple[list[dict], dict | None, list[float]]:
    """(últimas 48 h, última hora cheia, média por hora do dia nos dias da série).

    As horas vêm de /stats/total, no fuso do site (America/Sao_Paulo). A hora
    em andamento na coleta fica de fora: ainda não está completa.
    """
    horas = []
    for d in serie:
        for h, n in enumerate(d.get("por_hora") or []):
            horas.append((f"{d['data']}T{h:02d}:00", n))
    corte = agora_brt.strftime("%Y-%m-%dT%H:00")
    cheias = [(k, n) for k, n in horas if k < corte]
    ult48 = [{"hora": k, "acessos": n} for k, n in cheias[-48:]]
    ultima = {"hora": cheias[-1][0], "acessos": cheias[-1][1]} if cheias else None
    dias = [d for d in serie if len(d.get("por_hora") or []) == 24]
    media = [round(sum(d["por_hora"][h] for d in dias) / len(dias), 2) if dias else 0.0 for h in range(24)]
    return ult48, ultima, media


def agrega_grupos(hits: list[dict]) -> dict:
    grupos = {
        "Home": {"acessos": 0, "sub": {}},
        "Reajuste": {"acessos": 0, "sub": {n: 0 for n in IDX_NOMES.values()}},
        "Correção": {"acessos": 0, "sub": {n: 0 for n in IDX_NOMES.values()}},
        "Admin": {"acessos": 0, "sub": {}},
    }
    for h in hits:
        grupo, idx = classificar(h["path"])
        if grupo is None:
            continue
        grupos[grupo]["acessos"] += h["count"]
        if idx:
            grupos[grupo]["sub"][idx] += h["count"]
    return grupos


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def main() -> None:
    token = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    if not token:
        print("[info] GOATCOUNTER_TOKEN não definido — pulando coleta de acessos "
              "(configure o secret para ativar o painel /admin/).")
        return  # exit 0: não pode quebrar o job de quem não configurou o secret

    code = load_code()
    if not code:
        print("[info] goatcounter_code vazio em config.yml — nada a coletar.")
        return

    agora = datetime.now(timezone.utc)
    fim = rfc3339(agora)
    ini_30d = rfc3339(agora - timedelta(days=DIAS_JANELA))

    gc = GoatCounter(code, token)

    # All-time: acha a MAIOR janela que a API aceita (candidatos decrescentes).
    # A janela encontrada vira também o start dos hits all-time, p/ coerência.
    ini_tudo, vis_tudo = None, 0
    for dias in JANELAS_ALL_TIME:
        cand = rfc3339(agora - timedelta(days=dias))
        ok, total_v, _ = gc.total(cand, fim)
        if ok:
            ini_tudo, vis_tudo = cand, total_v
            break
    if ini_tudo is None:                 # nenhuma janela grande passou -> 30 dias
        ini_tudo = ini_30d
        _, vis_tudo, _ = gc.total(ini_tudo, fim)

    _, vis_30d, serie_diaria = gc.total(ini_30d, fim)
    ini_60d = rfc3339(agora - timedelta(days=2 * DIAS_JANELA))
    _, vis_30d_ant, _ = gc.total(ini_60d, ini_30d)
    hits_tudo = gc.hits(ini_tudo, fim)
    hits_30d = gc.hits(ini_30d, fim)
    detalhes = {chave: gc.detalhe(pagina, ini_30d, fim) for chave, pagina in DETALHES.items() if chave != "origens"}
    refs, refs_completo = gc.detalhe_cru("toprefs", ini_30d, fim, LIMITE_ORIGENS)
    origens = [{"nome": (s.get("name") or "").strip(), "acessos": int(s.get("count") or 0)} for s in refs]
    detalhes["origens"] = [{"nome": nome_detalhe("toprefs", {"name": o["nome"]}), "acessos": o["acessos"]}
                           for o in origens[:TOP_DETALHE]]
    # Eventos (cliques e cálculos) chegam em /stats/hits com event=true: saem das
    # contagens de páginas e vão só para os funis.
    eventos_30d = [h for h in hits_30d if h.get("event")]
    hits_tudo = [h for h in hits_tudo if not h.get("event")]
    hits_30d = [h for h in hits_30d if not h.get("event")]

    if not gc.houve_sucesso:
        # API inteira indisponível: não sobrescreve um stats.json anterior bom.
        print("[aviso] API do GoatCounter indisponível — mantendo stats.json anterior "
              "(se houver) e saindo sem erro.", file=sys.stderr)
        return

    pv_tudo = sum(h["count"] for h in hits_tudo)
    pv_30d = sum(h["count"] for h in hits_30d)
    top = sorted(hits_tudo, key=lambda h: h["count"], reverse=True)[:15]

    agora_brt = agora.astimezone(BRT)
    ult48, ultima_hora, media_hora = por_hora(serie_diaria, agora_brt)
    stats = {
        "gerado_em": agora_brt.isoformat(timespec="seconds"),
        "gerado_em_fmt": agora_brt.strftime("%d/%m/%Y às %H:%M"),
        "timezone": "America/Sao_Paulo (UTC-3)",
        "site": code,
        # "acessos" = soma de visitantes por página (page-level); "visitantes" =
        # visitantes únicos do período (a API do GoatCounter conta por visitante).
        "totais": {
            "all_time": {"acessos": pv_tudo, "visitantes": vis_tudo},
            "ultimos_30d": {"acessos": pv_30d, "visitantes": vis_30d},
            "30d_anteriores": {"visitantes": vis_30d_ant},
        },
        "grupos": agrega_grupos(hits_tudo),
        "secoes_30d": agrega_secoes(hits_30d),
        "top_paginas": top,
        "top_paginas_30d": sorted(hits_30d, key=lambda h: h["count"], reverse=True)[:15],
        "serie_diaria": [{"data": d["data"], "acessos": d["acessos"]} for d in serie_diaria],
        "ultimas_48h": ult48,
        "ultima_hora": ultima_hora,
        "media_por_hora_do_dia": media_hora,
        "detalhes_30d": detalhes,
        "origens_30d": resume_origens(origens, bool(refs_completo), vis_30d) if refs_completo is not None else None,
        "funis_30d": funis(hits_30d, eventos_30d),
        "eventos_desde": EVENTOS_DESDE,
    }

    write_json(DATA_DIR / "stats.json", stats)
    write_json(DOCS_DATA_DIR / "stats.json", stats)
    print(f"stats.json gravado: {pv_tudo} acessos all-time, {vis_tudo} visitantes, "
          f"{len(top)} páginas no Top, série de {len(serie_diaria)} dia(s).")


if __name__ == "__main__":
    main()
