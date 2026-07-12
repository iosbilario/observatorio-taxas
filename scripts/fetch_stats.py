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
INICIO_TUDO = "2020-01-01T00:00:00Z"  # "all-time": a API limita à disponibilidade

# Brasil sem horário de verão desde 2019 -> offset fixo, sem depender de tzdata.
BRT = timezone(timedelta(hours=-3))

# Prefixos de slug -> nome de exibição do índice (reajuste e correção).
IDX_NOMES = {"ipca": "IPCA", "igpm": "IGP-M", "inpc": "INPC", "igpdi": "IGP-DI"}


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

    def total(self, start: str, end: str) -> tuple[int, list[dict]]:
        """(visitantes no período, série diária [{data, acessos}, ...])."""
        try:
            data = self._get("/stats/total", {"start": start, "end": end})
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] /stats/total falhou: {exc}", file=sys.stderr)
            return 0, []
        total = int(data.get("total") or 0)
        diaria = [
            {"data": s.get("day"), "acessos": int(s.get("daily") or 0)}
            for s in (data.get("stats") or []) if s.get("day")
        ]
        return total, diaria

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
            {"path": h.get("path") or "", "count": int(h.get("count") or 0)}
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
    vis_tudo, _ = gc.total(INICIO_TUDO, fim)
    vis_30d, serie_diaria = gc.total(ini_30d, fim)
    hits_tudo = gc.hits(INICIO_TUDO, fim)
    hits_30d = gc.hits(ini_30d, fim)

    if not gc.houve_sucesso:
        # API inteira indisponível: não sobrescreve um stats.json anterior bom.
        print("[aviso] API do GoatCounter indisponível — mantendo stats.json anterior "
              "(se houver) e saindo sem erro.", file=sys.stderr)
        return

    pv_tudo = sum(h["count"] for h in hits_tudo)
    pv_30d = sum(h["count"] for h in hits_30d)
    top = sorted(hits_tudo, key=lambda h: h["count"], reverse=True)[:15]

    agora_brt = agora.astimezone(BRT)
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
        },
        "grupos": agrega_grupos(hits_tudo),
        "top_paginas": top,
        "serie_diaria": serie_diaria,
    }

    write_json(DATA_DIR / "stats.json", stats)
    write_json(DOCS_DATA_DIR / "stats.json", stats)
    print(f"stats.json gravado: {pv_tudo} acessos all-time, {vis_tudo} visitantes, "
          f"{len(top)} páginas no Top, série de {len(serie_diaria)} dia(s).")


if __name__ == "__main__":
    main()
