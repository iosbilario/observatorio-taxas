"""
backfill.py — Carga inicial do histórico (executar uma vez, ou quando quiser
reforçar a janela). Puxa N anos de cada série do SGS/BACEN (N = anos_historico
do config.yml, padrão 2) e funde com o que já existe em data/<codigo>_history.json.

NÃO mexe no CHANGELOG.md — backfill é silencioso (não gera "eventos" para os
500+ pontos históricos). A partir daí, scripts/fetch.py mantém a série em dia
e registra apenas as mudanças novas.

Uso:
    python scripts/backfill.py            # usa anos_historico do config
    python scripts/backfill.py 5          # força 5 anos
"""

from __future__ import annotations

import sys
from datetime import date

import fetch as F  # mesmo diretório (scripts/) está no sys.path


def main() -> None:
    config = F.load_config()
    base_url = config["base_url"]
    series = config.get("series", [])
    anos = int(sys.argv[1]) if len(sys.argv) > 1 else int(config.get("anos_historico", 2))

    hoje = date.today()
    try:
        inicio = hoje.replace(year=hoje.year - anos)
    except ValueError:  # 29/02
        inicio = hoje.replace(year=hoje.year - anos, day=28)
    di, df = inicio.strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y")
    print(f"Backfill de {anos} ano(s): {di} a {df}")

    manifesto: list[dict] = []
    ok = falhas = 0
    for item in series:
        codigo = item["codigo"]
        nome = item.get("nome", str(codigo))
        try:
            pontos = F.fetch_pontos(base_url, codigo, data_inicial=di, data_final=df)
        except Exception as exc:
            falhas += 1
            print(f"[ERRO] série {codigo} ({nome}): {exc}", file=sys.stderr)
            continue

        existing = F.read_json(F.DATA_DIR / f"{codigo}_history.json", [])
        merged = F.merge_history(existing, pontos)
        F.write_series_files(codigo, nome, merged)
        manifesto.append(F.manifest_entry(codigo, nome, merged))
        ok += 1
        print(f"[OK] {nome}: {len(merged)} pontos "
              f"({merged[0]['data']} … {merged[-1]['data']})")

    if manifesto:
        F.write_manifest(manifesto)
    print(f"\nResumo: {ok} série(s) OK, {falhas} falha(s).")


if __name__ == "__main__":
    main()
