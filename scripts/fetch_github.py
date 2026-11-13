#!/usr/bin/env python3
"""
fetch_github.py — Número de estrelas do repositório para o header do site.

Consulta a API do GitHub (GET /repos/<repo>) e grava `data/github.json`,
espelhado em `docs/data/github.json`, que é o que o GitHub Pages serve. O
script `docs/estrelas.js` lê esse arquivo no navegador; o visitante nunca
fala com o GitHub.

Só reescreve os arquivos quando o número muda, para não gerar commit a cada
execução do monitor.yml.

Nunca derruba o job: erro de rede, limite da API ou resposta inesperada só
geram um aviso, e o arquivo anterior fica como está.

Ambiente (opcional): GITHUB_TOKEN autentica a chamada (limite maior). No
Actions, o monitor.yml passa o token do próprio workflow, só de leitura aqui.

    python scripts/fetch_github.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "iosbilario/observatorio-taxas"
SAIDAS = [ROOT / "data" / "github.json", ROOT / "docs" / "data" / "github.json"]
LIMITE_BYTES = 512 * 1024


def consulta(repo: str = REPO, token: str | None = None, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "observatorio-taxas-monitor",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(LIMITE_BYTES))


def extrai_estrelas(resposta: dict) -> int:
    n = resposta.get("stargazers_count")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError(f"stargazers_count inválido: {n!r}")
    return n


def registro(estrelas: int, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    return {
        "repositorio": f"https://github.com/{REPO}",
        "estrelas": estrelas,
        "atualizado_em": agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fonte": "API do GitHub (GET /repos), coletada por scripts/fetch_github.py",
    }


def estrelas_gravadas(caminho: Path) -> int | None:
    try:
        return json.loads(caminho.read_text(encoding="utf-8")).get("estrelas")
    except (OSError, ValueError, AttributeError):
        return None


def grava_se_mudou(estrelas: int, saidas: list[Path] = SAIDAS) -> bool:
    if all(estrelas_gravadas(p) == estrelas for p in saidas):
        return False
    texto = json.dumps(registro(estrelas), ensure_ascii=False, indent=2) + "\n"
    for p in saidas:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")
    return True


def main() -> int:
    try:
        n = extrai_estrelas(consulta(token=os.environ.get("GITHUB_TOKEN") or None))
    except Exception as e:  # noqa: BLE001 — nunca derruba o monitor
        print(f"[fetch_github] aviso: não consegui ler as estrelas ({type(e).__name__}: {e}); mantendo o arquivo anterior.")
        return 0
    mudou = grava_se_mudou(n)
    print(f"[fetch_github] {n} estrela(s); {'atualizado' if mudou else 'sem mudança'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
