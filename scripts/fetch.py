"""
fetch.py — Coletor de séries do SGS/BACEN.

Lê `config.yml`, consulta a API pública do Banco Central (SGS) e mantém, para
cada série, a SÉRIE TEMPORAL acumulada em `data/<codigo>_history.json` —
lista de {data, valor} por data de referência do BACEN. O Git versiona esses
arquivos: cada commit é um ponto no tempo.

Arquivos gerados em data/ (e espelhados em docs/data/ para o GitHub Pages):
  - data/<codigo>_history.json  -> série temporal [{data, valor}, ...] ordenada.
  - data/<codigo>.json          -> último ponto bruto (+ codigo, nome).
  - data/series.json            -> manifesto (codigo, nome, valor_atual, ...).

Quando o valor de um ponto NOVO difere do anterior, uma linha é anexada ao
CHANGELOG.md e — se houver — uma frase-resumo em PT-BR (grátis, local).

A coleta busca os ÚLTIMOS N pontos (cobre execuções perdidas) e funde por data,
sem duplicar. A carga inicial de 2 anos é feita por scripts/backfill.py.

A API do SGS é pública (sem autenticação). Falha de uma série não derruba o job.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"  # espelho servido pelo GitHub Pages
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

TIMEOUT = 30   # segundos por requisição
ULTIMOS = 8    # quantos últimos pontos buscar por execução (cobre dias perdidos)


# --------------------------------------------------------------------------- #
# Helpers reutilizados também por backfill.py
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_json(path: Path, payload) -> None:
    """Escreve JSON estável (UTF-8, indentado, newline final) p/ git diff limpo."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _chave_data(s: str):
    """'dd/mm/aaaa' -> (aaaa, mm, dd) para ordenação cronológica."""
    try:
        d, m, a = str(s).split("/")
        return (int(a), int(m), int(d))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def fetch_pontos(base_url: str, codigo, *, ultimos=None,
                 data_inicial=None, data_final=None) -> list[dict]:
    """
    Busca pontos da API do SGS e devolve [{data, valor}, ...].
    - ultimos=N         -> /dados/ultimos/N
    - data_inicial/final -> /dados?dataInicial=&dataFinal=  (intervalo histórico)
    """
    base = base_url.format(codigo=codigo)
    if ultimos:
        url = f"{base}/ultimos/{ultimos}?formato=json"
    else:
        url = f"{base}?formato=json&dataInicial={data_inicial}&dataFinal={data_final}"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    dados = resp.json()
    if not isinstance(dados, list):
        raise ValueError("resposta em formato inesperado")
    pontos = [{"data": p["data"], "valor": p["valor"]}
              for p in dados if "data" in p and "valor" in p]
    if not pontos:
        raise ValueError("resposta vazia")
    return pontos


def merge_history(existing: list[dict], novos: list[dict]) -> list[dict]:
    """Funde por data (novos sobrescrevem revisões), remove duplicatas, ordena."""
    por_data = {p["data"]: {"data": p["data"], "valor": p["valor"]} for p in existing}
    for p in novos:
        por_data[p["data"]] = {"data": p["data"], "valor": p["valor"]}
    return sorted(por_data.values(), key=lambda p: _chave_data(p["data"]))


def data_ultima_mudanca(history: list[dict]):
    """Data de referência do ponto mais recente cujo valor diferiu do anterior."""
    ultima = history[0]["data"] if history else None
    for i in range(1, len(history)):
        if str(history[i]["valor"]) != str(history[i - 1]["valor"]):
            ultima = history[i]["data"]
    return ultima


def manifest_entry(codigo, nome: str, history: list[dict]) -> dict:
    ultimo = history[-1] if history else {}
    return {
        "codigo": codigo,
        "nome": nome,
        "valor_atual": ultimo.get("valor"),
        "data_referencia": ultimo.get("data"),
        "ultima_mudanca": data_ultima_mudanca(history),
        "pontos": len(history),
    }


def write_series_files(codigo, nome: str, history: list[dict]) -> None:
    """Persiste o histórico (data/ + espelho docs/data/) e o último ponto bruto."""
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DATA_DIR / f"{codigo}_history.json", history)
    write_json(DOCS_DATA_DIR / f"{codigo}_history.json", history)
    ultimo = history[-1] if history else {}
    write_json(DATA_DIR / f"{codigo}.json",
               {**ultimo, "codigo": codigo, "nome": nome})


def write_manifest(manifesto: list[dict]) -> None:
    write_json(DATA_DIR / "series.json", manifesto)
    write_json(DOCS_DATA_DIR / "series.json", manifesto)


# --------------------------------------------------------------------------- #
# Resumo em PT-BR: grátis (local) por padrão; IA (paga) só se ANTHROPIC_API_KEY.
# --------------------------------------------------------------------------- #
def _fmt_num(valor) -> str:
    try:
        x = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return str(valor)
    return f"{x:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def frase_mudanca(nome: str, valor_antigo, valor_novo) -> str:
    """Resumo PT-BR 100% grátis e local (sem API/chave/custo)."""
    try:
        a = float(str(valor_antigo).replace(",", "."))
        b = float(str(valor_novo).replace(",", "."))
    except (TypeError, ValueError):
        return f"{nome}: {valor_antigo} -> {valor_novo}"
    if b > a:
        return f"{nome}: subiu de {_fmt_num(a)} para {_fmt_num(b)}."
    if b < a:
        return f"{nome}: caiu de {_fmt_num(a)} para {_fmt_num(b)}."
    return f"{nome}: manteve-se em {_fmt_num(b)}."


_summary_enabled = None  # None=não testado | True=ativa | False=desligada


def try_summary(diff_text: str):
    """Upgrade OPCIONAL via API da Anthropic (paga). Só tenta se houver chave."""
    global _summary_enabled
    if _summary_enabled is False:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _summary_enabled = False
        return None
    try:
        from diff_summary import summarize_change
        frase = summarize_change(diff_text)
        _summary_enabled = True
        return frase
    except Exception as exc:
        if _summary_enabled is None:
            print(f"[info] resumo via IA indisponível ({exc}); usando resumo grátis.",
                  file=sys.stderr)
        _summary_enabled = False
        return None


def append_changelog(linhas: list[str]) -> None:
    if not linhas:
        return
    cabecalho = "" if CHANGELOG_PATH.exists() else "# CHANGELOG — Observatório de Taxas\n\n"
    with CHANGELOG_PATH.open("a", encoding="utf-8") as fh:
        if cabecalho:
            fh.write(cabecalho)
        for linha in linhas:
            fh.write(linha + "\n")


# --------------------------------------------------------------------------- #
# Coleta periódica
# --------------------------------------------------------------------------- #
def main() -> None:
    config = load_config()
    base_url = config["base_url"]
    series = config.get("series", [])

    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    eventos: list[str] = []
    manifesto: list[dict] = []
    ok = falhas = 0

    # Manifesto anterior — preserva entrada em caso de falha transitória da série.
    prev_manifesto = {s["codigo"]: s for s in read_json(DATA_DIR / "series.json", [])}

    for item in series:
        codigo = item["codigo"]
        nome = item.get("nome", str(codigo))
        try:
            novos = fetch_pontos(base_url, codigo, ultimos=ULTIMOS)
        except Exception as exc:
            falhas += 1
            print(f"[ERRO] série {codigo} ({nome}): {exc}", file=sys.stderr)
            if codigo in prev_manifesto:
                manifesto.append(prev_manifesto[codigo])
            continue

        history_path = DATA_DIR / f"{codigo}_history.json"
        existing = read_json(history_path, [])
        datas_antigas = {p["data"] for p in existing}
        merged = merge_history(existing, novos)
        pos = {p["data"]: i for i, p in enumerate(merged)}

        # Eventos: pontos novos cujo valor difere do ponto anterior na série.
        novas_datas = sorted((p["data"] for p in novos if p["data"] not in datas_antigas),
                             key=_chave_data)
        for nd in novas_datas:
            i = pos[nd]
            antigo = merged[i - 1]["valor"] if i > 0 else None
            novo = merged[i]["valor"]
            if antigo is not None and str(antigo) != str(novo):
                eventos.append(f"[{timestamp}] {nome}: {antigo} -> {novo}")
                frase = (try_summary(f"{nome}: {antigo} -> {novo}")
                         or frase_mudanca(nome, antigo, novo))
                eventos.append(f"    ↳ {frase}")
                print(f"[MUDOU] {nome}: {antigo} -> {novo} (ref. {nd})")

        write_series_files(codigo, nome, merged)
        manifesto.append(manifest_entry(codigo, nome, merged))
        ok += 1
        if not novas_datas:
            print(f"[OK] {nome}: {merged[-1]['valor']} (sem ponto novo)")
        elif not any(e.startswith(f"[{timestamp}] {nome}:") for e in eventos):
            print(f"[OK] {nome}: {len(novas_datas)} ponto(s) novo(s), sem mudança de valor")

    write_manifest(manifesto)
    append_changelog(eventos)
    print(f"\nResumo: {ok} série(s) OK, {falhas} falha(s), "
          f"{len([e for e in eventos if not e.startswith('    ')])} mudança(s).")


if __name__ == "__main__":
    main()
