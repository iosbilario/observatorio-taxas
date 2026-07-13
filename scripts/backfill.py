"""
backfill.py — Carga histórica profunda (executar uma vez, ou quando quiser
reforçar a janela). Puxa cada série do SGS/BACEN DESDE 01/01/2015 (ou de um ano
informado) e funde com o que já existe em data/<codigo>_history.json.

A API do SGS limita cada requisição a ~10 anos para séries diárias. Por isso a
coleta é feita em JANELAS (ver WINDOW_DAYS) e fundida por data — o merge já
deduplica. Pontos com data futura (ex.: vigência da Meta Selic até o próximo
COPOM) são descartados, igual ao scripts/fetch.py.

Séries diárias muito longas podem deixar o JSON grande demais para o site
estático. Se um history passar de MAX_KB, seu alcance é reduzido para 2019 e o
fato é registrado em docs/llms.txt.

NÃO mexe no CHANGELOG.md — backfill é silencioso. A partir daí, scripts/fetch.py
mantém a série em dia e registra apenas as mudanças novas.

Uso:
    python scripts/backfill.py            # desde 01/01/2015
    python scripts/backfill.py 2019       # desde 01/01/2019
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone

import fetch as F  # mesmo diretório (scripts/) está no sys.path

INICIO_PADRAO = date(2015, 1, 1)
WINDOW_DAYS = 1800          # ~5 anos: bem sob o limite do SGS, resposta mais leve
TENTATIVAS = 3             # retries por janela (a API do SGS oscila com timeout/502)
MAX_KB = 300               # acima disso, série diária é reduzida para 2019
CORTE_REDUZIDO = date(2019, 1, 1)
LLMS_PATH = F.ROOT / "docs" / "llms.txt"


def janelas(inicio: date, fim: date):
    """Gera pares (dataInicial, dataFinal) cobrindo [inicio, fim] em fatias."""
    ini = inicio
    while ini <= fim:
        fim_janela = min(ini + timedelta(days=WINDOW_DAYS), fim)
        yield ini, fim_janela
        ini = fim_janela + timedelta(days=1)


def fetch_intervalo(base_url: str, codigo, inicio: date, fim: date) -> list[dict]:
    """Busca [inicio, fim] em janelas e funde por data (última revisão vence)."""
    por_data: dict = {}
    for di, df in janelas(inicio, fim):
        pts = None
        for tent in range(1, TENTATIVAS + 1):
            try:
                pts = F.fetch_pontos(base_url, codigo,
                                     data_inicial=di.strftime("%d/%m/%Y"),
                                     data_final=df.strftime("%d/%m/%Y"))
                break
            except Exception as exc:  # timeout/502 são comuns; tenta de novo
                if tent == TENTATIVAS:
                    print(f"[aviso] série {codigo}: janela {di:%d/%m/%Y}..{df:%d/%m/%Y} "
                          f"falhou após {TENTATIVAS} tentativas: {exc}", file=sys.stderr)
                else:
                    time.sleep(2 * tent)
        if not pts:
            continue
        for p in pts:
            por_data[p["data"]] = {"data": p["data"], "valor": p["valor"]}
    return list(por_data.values())


def registra_reduzidas(nomes: list[str]) -> None:
    """Anota no llms.txt quais séries diárias tiveram o alcance reduzido a 2019."""
    if not nomes or not LLMS_PATH.exists():
        return
    marca = "## Cobertura temporal"
    txt = LLMS_PATH.read_text(encoding="utf-8")
    bloco = (f"{marca}\n\n"
             "As séries começam em 01/01/2015, exceto as diárias abaixo, reduzidas a "
             "01/01/2019 para manter os arquivos estáticos leves:\n"
             + "".join(f"- {n}\n" for n in nomes))
    if marca in txt:
        # substitui o bloco existente (até a próxima seção ## ou fim)
        import re
        txt = re.sub(rf"{re.escape(marca)}.*?(?=\n## |\Z)", bloco.rstrip() + "\n",
                     txt, flags=re.S)
    else:
        txt = txt.rstrip() + "\n\n" + bloco
    LLMS_PATH.write_text(txt, encoding="utf-8")


def main() -> None:
    config = F.load_config()
    base_url = config["base_url"]
    series = config.get("series", [])

    inicio = INICIO_PADRAO
    if len(sys.argv) > 1:
        inicio = date(int(sys.argv[1]), 1, 1)

    hoje = datetime.now(timezone.utc).astimezone(F.BRT).date()
    corte_hoje = (hoje.year, hoje.month, hoje.day)   # descarta datas futuras
    print(f"Backfill desde {inicio:%d/%m/%Y} até {hoje:%d/%m/%Y} "
          f"(janelas de {WINDOW_DAYS} dias).")

    manifesto: list[dict] = []
    reduzidas: list[str] = []
    ok = falhas = 0
    for item in series:
        codigo = item["codigo"]
        nome = item.get("nome", str(codigo))
        try:
            pontos = fetch_intervalo(base_url, codigo, inicio, hoje)
        except Exception as exc:
            falhas += 1
            print(f"[ERRO] série {codigo} ({nome}): {exc}", file=sys.stderr)
            if F.read_json(F.DATA_DIR / f"{codigo}_history.json", None) is None:
                continue

        existing = F.read_json(F.DATA_DIR / f"{codigo}_history.json", [])
        merged = [p for p in F.merge_history(existing, pontos)
                  if F._chave_data(p["data"]) <= corte_hoje]

        # Reduz o alcance de séries diárias grandes demais para o site estático.
        payload = json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if len(payload.encode("utf-8")) > MAX_KB * 1024:
            merged = [p for p in merged
                      if F._chave_data(p["data"]) >= (CORTE_REDUZIDO.year, 1, 1)]
            reduzidas.append(nome)
            print(f"[reduzida] {nome}: > {MAX_KB} KB, alcance cortado para "
                  f"{CORTE_REDUZIDO:%Y}.")

        if not merged:
            print(f"[ERRO] série {codigo} ({nome}): sem pontos.", file=sys.stderr)
            falhas += 1
            continue

        F.write_series_files(codigo, nome, merged)
        manifesto.append(F.manifest_entry(codigo, nome, merged, item.get("grupo")))
        ok += 1
        print(f"[OK] {nome}: {len(merged)} pontos "
              f"({merged[0]['data']} … {merged[-1]['data']})")

    if manifesto:
        F.write_manifest(manifesto)
    registra_reduzidas(reduzidas)
    print(f"\nResumo: {ok} série(s) OK, {falhas} falha(s), "
          f"{len(reduzidas)} reduzida(s).")


if __name__ == "__main__":
    main()
