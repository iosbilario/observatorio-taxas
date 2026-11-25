#!/usr/bin/env python3
"""
versao_dados.py — Publica docs/data/versao.json: o commit dos dados do site.

O VAR (docs/var.html) carrega as séries de um commit e grava esse commit no
recibo. Para a primeira visita funcionar sem consultar a API do GitHub, o site
publica aqui qual commit gravou os dados que ele está servindo:

    {"sha": "<40 hex>", "curto": "<7 hex>", "data": "<data ISO do commit>"}

O commit é o último que alterou data/ ou docs/data/ (fora este próprio
arquivo). Um commit não sabe o próprio hash, por isso o monitor.yml roda este
script DEPOIS de commitar a coleta e commita o resultado à parte: os JSON de
docs/data/ no commit novo são idênticos aos do commit gravado em versao.json.

Também atualiza o carimbo e o recibo de exemplo da página inicial
(render_index.py lê este arquivo), para que o hash mostrado na capa e o do
link do recibo sejam o mesmo dos dados.

    python scripts/versao_dados.py            # grava docs/data/versao.json
    python scripts/versao_dados.py --mostrar  # só imprime
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAIDA = ROOT / "docs" / "data" / "versao.json"


def commit_dos_dados(raiz: Path = ROOT) -> tuple[str, str] | None:
    """(sha, data ISO) do último commit que mudou data/ ou docs/data/, sem
    contar versao.json. None fora de um repositório Git."""
    r = subprocess.run(
        ["git", "log", "-1", "--format=%H%x09%cI", "--", "data", "docs/data",
         ":(exclude)docs/data/versao.json"],
        cwd=raiz, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    sha, data = r.stdout.strip().split("\t")
    return sha, data


def conteudo(sha: str, data: str) -> str:
    return json.dumps({"sha": sha, "curto": sha[:7], "data": data}, ensure_ascii=False, indent=1) + "\n"


def grava(raiz: Path = ROOT) -> bool:
    achado = commit_dos_dados(raiz)
    if not achado:
        print("versao_dados: nenhum commit de dados no histórico disponível; versao.json mantido.")
        return False
    texto = conteudo(*achado)
    saida = raiz / "docs" / "data" / "versao.json"
    if saida.exists() and saida.read_text(encoding="utf-8") == texto:
        print(f"versao_dados: já em dia ({achado[0][:7]}).")
        return False
    saida.write_text(texto, encoding="utf-8")
    print(f"versao_dados: docs/data/versao.json -> {achado[0][:7]} ({achado[1]}).")
    return True


if __name__ == "__main__":
    if "--mostrar" in sys.argv:
        print(commit_dos_dados())
    else:
        grava()
