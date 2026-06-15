"""
fetch.py — Coletor de séries do SGS/BACEN.

Objetivo
--------
Ler `config.yml`, consultar cada série configurada na API de dados abertos do
Banco Central (SGS) e gravar/atualizar snapshots JSON dentro de `data/`. Esses
snapshots, versionados pelo Git, formam o "banco de dados temporal" do
observatório: cada commit é um ponto no tempo.

Arquivos gerados em data/
-------------------------
  - data/<codigo>.json          -> último snapshot bruto normalizado da série.
  - data/<codigo>_history.json  -> histórico acumulado: lista de
                                    {data_coleta, valor}. Só recebe um novo
                                    ponto quando o valor muda em relação ao
                                    último registrado (o "diff" que vira evento).
  - data/series.json            -> manifesto (codigo, nome, valor_atual, ...).

Para que o GitHub Pages (servindo a pasta /docs) consiga ler os dados, os
arquivos que a página consome (series.json e cada <codigo>_history.json) são
espelhados em docs/data/. O store canônico continua sendo data/ na raiz.

Quando um valor muda, uma linha é anexada ao CHANGELOG.md (alerta do MVP):
  [timestamp] <nome>: <valor_antigo> -> <valor_novo>

A API do SGS é pública e não exige autenticação. Falhas de rede em UMA série
são registradas e não derrubam a coleta das demais.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

# Caminhos âncora — resolvidos a partir da raiz do repositório (pai de scripts/).
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"  # espelho servido pelo GitHub Pages
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

TIMEOUT = 30  # segundos por requisição


def load_config() -> dict:
    """Carrega config.yml -> base_url + lista de séries."""
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_json(path: Path, payload) -> None:
    """Escreve JSON estável (UTF-8, indentado, newline final) p/ git diff limpo."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fmt_num(valor) -> str:
    """Formata um número no padrão PT-BR (vírgula decimal), sem zeros à toa."""
    try:
        x = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return str(valor)
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def frase_mudanca(nome: str, valor_antigo, valor_novo) -> str:
    """
    Resumo em PT-BR 100% GRÁTIS e local (sem API, sem chave, sem custo).
    Compara os números e descreve a direção. É o padrão do observatório.
    Ex.: "Meta Selic (% a.a.): subiu de 13,75 para 14,50."
    """
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


# Estado da camada de IA OPCIONAL E PAGA (diff_summary.py / API da Anthropic):
#   None -> não testado   True -> ativa   False -> indisponível/desligada.
# Por padrão fica DESLIGADA: só é tentada se ANTHROPIC_API_KEY estiver definida.
# Sem ela, usamos frase_mudanca() (grátis) — o projeto permanece NoCost.
_summary_enabled = None


def try_summary(diff_text: str):
    """
    Upgrade OPCIONAL: frase via API da Anthropic (paga). Só tenta se houver
    ANTHROPIC_API_KEY no ambiente; caso contrário devolve None em silêncio para
    cair no resumo grátis. Qualquer falha (chave, pacote, saldo, rede) é
    capturada e nunca interrompe a coleta.
    """
    global _summary_enabled
    if _summary_enabled is False:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _summary_enabled = False  # camada paga não configurada -> silencioso
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


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def fetch_serie(base_url: str, codigo) -> dict:
    """
    Consulta a API do SGS para um código e devolve o ponto normalizado:
    {"data": "dd/mm/aaaa", "valor": "x"}. Levanta exceção em falha de rede/HTTP.

    Formato da resposta do SGS (validado): [{"data": "dd/mm/aaaa", "valor": "x"}]
    """
    url = base_url.format(codigo=codigo)
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    dados = resp.json()
    if not isinstance(dados, list) or not dados:
        raise ValueError("resposta vazia ou em formato inesperado")
    ponto = dados[-1]  # /ultimos/1 retorna 1 item; -1 é robusto p/ N itens
    if "data" not in ponto or "valor" not in ponto:
        raise ValueError(f"ponto sem campos esperados: {ponto!r}")
    return {"data": ponto["data"], "valor": ponto["valor"]}


def append_changelog(linhas: list[str]) -> None:
    """Anexa linhas de evento ao CHANGELOG.md (cria com cabeçalho se ausente)."""
    if not linhas:
        return
    cabecalho = ""
    if not CHANGELOG_PATH.exists():
        cabecalho = "# CHANGELOG — Observatório de Taxas\n\n"
    with CHANGELOG_PATH.open("a", encoding="utf-8") as fh:
        if cabecalho:
            fh.write(cabecalho)
        for linha in linhas:
            fh.write(linha + "\n")


def main() -> None:
    config = load_config()
    base_url = config["base_url"]
    series = config.get("series", [])

    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    agora = datetime.now(timezone.utc).astimezone()
    data_coleta = agora.isoformat(timespec="seconds")
    timestamp = agora.strftime("%Y-%m-%d %H:%M:%S %z")

    eventos: list[str] = []
    manifesto: list[dict] = []
    ok = 0
    falhas = 0

    # Manifesto anterior, indexado por código. Em caso de falha de uma série,
    # preservamos sua última entrada conhecida — assim um soluço de rede não
    # remove o indicador do series.json (evita commit "flapping" e a série
    # sumindo da página até a próxima coleta).
    prev_manifesto = {
        s["codigo"]: s for s in read_json(DATA_DIR / "series.json", [])
    }

    for item in series:
        codigo = item["codigo"]
        nome = item.get("nome", str(codigo))
        try:
            ponto = fetch_serie(base_url, codigo)
        except Exception as exc:  # rede, HTTP, JSON, formato — não derruba o job
            falhas += 1
            print(f"[ERRO] série {codigo} ({nome}): {exc}", file=sys.stderr)
            # Preserva a entrada anterior no manifesto, se houver, para não
            # remover o indicador por causa de uma falha transitória.
            if codigo in prev_manifesto:
                manifesto.append(prev_manifesto[codigo])
            continue

        valor_novo = ponto["valor"]

        # Snapshot bruto do último valor.
        snapshot_path = DATA_DIR / f"{codigo}.json"
        write_json(snapshot_path, {**ponto, "codigo": codigo, "nome": nome})

        # Histórico acumulado: anexa só se o valor mudou vs último registrado.
        history_path = DATA_DIR / f"{codigo}_history.json"
        history = read_json(history_path, [])
        valor_antigo = history[-1]["valor"] if history else None

        mudou = valor_antigo is None or str(valor_antigo) != str(valor_novo)
        if mudou:
            history.append({
                "data_coleta": data_coleta,
                "valor": valor_novo,
                "data_referencia": ponto["data"],
            })
            write_json(history_path, history)
            if valor_antigo is not None:
                eventos.append(
                    f"[{timestamp}] {nome}: {valor_antigo} -> {valor_novo}"
                )
                # Frase em PT-BR: grátis (local) por padrão; usa IA só se houver
                # ANTHROPIC_API_KEY configurada. Sempre presente, sem custo.
                frase = (try_summary(f"{nome}: {valor_antigo} -> {valor_novo}")
                         or frase_mudanca(nome, valor_antigo, valor_novo))
                eventos.append(f"    ↳ {frase}")
                print(f"[MUDOU] {nome}: {valor_antigo} -> {valor_novo}")
            else:
                print(f"[NOVO] {nome}: {valor_novo} (primeiro registro)")
        else:
            print(f"[OK] {nome}: {valor_novo} (sem mudança)")

        # Espelho para o GitHub Pages (sempre, para manter docs/data em sincronia).
        write_json(DOCS_DATA_DIR / f"{codigo}_history.json", history)

        # ultima_mudanca = quando o valor mudou pela última vez (último ponto do
        # histórico). Estável entre coletas sem mudança -> git diff vazio ->
        # nenhum commit ruído a cada 6h. NÃO usar o timestamp da coleta atual aqui.
        manifesto.append({
            "codigo": codigo,
            "nome": nome,
            "valor_atual": valor_novo,
            "data_referencia": ponto["data"],
            "ultima_mudanca": history[-1]["data_coleta"],
        })
        ok += 1

    # Manifesto p/ a página estática saber quais séries existem e seus nomes.
    write_json(DATA_DIR / "series.json", manifesto)
    write_json(DOCS_DATA_DIR / "series.json", manifesto)  # espelho p/ Pages
    append_changelog(eventos)

    print(
        f"\nResumo: {ok} série(s) OK, {falhas} falha(s), "
        f"{len(eventos)} mudança(s) registrada(s)."
    )


if __name__ == "__main__":
    main()
