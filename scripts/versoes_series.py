#!/usr/bin/env python3
"""
versoes_series.py — Índice das versões preservadas de cada série (consulta por data).

Para cada série com ficha, grava docs/data/versoes/<codigo>.json com a lista dos
commits da main que mudaram data/<codigo>_history.json, em ordem: o SHA e a
data do commit (quando o Observatório REGISTROU aquela versão; não há
evidência de quando o GitHub Pages publicou). O navegador (docs/historico.js)
escolhe a última versão até o fim do dia pedido, em Brasília, e baixa só o
arquivo daquela série naquele commit em raw.githubusercontent.com. Nada de
histórico Git inteiro no navegador, nem cópia das séries por dia: o Git já
guarda cada versão.

Histórico de primeiro pai (--first-parent): um dado que chegou por pull request
conta a partir do merge na main, não da data do commit na branch.

Precisa do histórico completo do repositório (o monitor.yml faz checkout com
fetch-depth: 0). Sem histórico, não grava nada: o índice commitado continua.
docs/data/versoes/index.json resume a primeira versão de cada série.

    python scripts/versoes_series.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_indicadores as BI  # noqa: E402

SAIDA = ROOT / "docs" / "data" / "versoes"


def versoes(codigo: int, raiz: Path = ROOT, ref: str = "HEAD") -> list[dict]:
    r = subprocess.run(["git", "log", "--first-parent", "--format=%H%x09%cI", ref, "--",
                        f"data/{codigo}_history.json"], cwd=raiz, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    linhas = [l.split("\t") for l in r.stdout.strip().splitlines() if l.strip()]
    return [{"sha": sha, "registrado_em": quando} for sha, quando in reversed(linhas)]


def historico_completo(raiz: Path = ROOT) -> bool:
    r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=raiz, capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "false"


def main() -> None:
    if not historico_completo():
        print("versoes_series: clone raso (sem histórico completo); índice mantido como está.")
        return
    SAIDA.mkdir(parents=True, exist_ok=True)
    resumo = []
    for it in BI.series_config():
        c = it["codigo"]
        if c not in BI.PAGINAS:
            continue
        p = BI.PAGINAS[c]
        vs = versoes(c)
        if not vs:
            continue
        dados = {"codigo": c, "nome": p["curto"], "slug": p["slug"], "casas": p["casas"], "pref": p.get("pref", ""),
                 "suf": p.get("suf", ""), "mensal": BI.mensal(c),
                 "arquivo": f"data/{c}_history.json", "versoes": vs}
        (SAIDA / f"{c}.json").write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n",
                                         encoding="utf-8")
        resumo.append({"codigo": c, "nome": p["curto"], "primeira": vs[0]["registrado_em"], "versoes": len(vs)})
    (SAIDA / "index.json").write_text(json.dumps({"series": resumo}, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    print(f"versoes_series: {len(resumo)} séries.")


if __name__ == "__main__":
    main()
