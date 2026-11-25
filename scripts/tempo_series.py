"""
tempo_series.py — O que a data de cada série quer dizer, em texto.

O SGS devolve toda observação com uma data dd/mm/aaaa, mas ela significa
coisas diferentes conforme a série:

  mensal         01/10/2026 = competência outubro de 2026 (IPCA, IGP-M...)
  trimestre      01/09/2026 = trimestre móvel até setembro de 2026 (PNAD)
  cotação        25/11/2026 = cotação PTAX daquele dia (dólar, euro)
  taxa diária    24/11/2026 = taxa daquele dia útil (Selic efetiva, CDI)
  período        24/11/2026 = rendimento do período de 1 mês que começa
                 nesse dia (poupança e TR: a data é o "aniversário")
  posição        24/11/2026 = posição no fim daquele dia (reservas)
  meta Selic     a série 432 traz, dia a dia, a meta em vigor (vem até com
                 datas futuras, até a próxima reunião do Copom, que o
                 fetch.py corta). Por isso "em vigor desde" é o primeiro dia
                 com o valor atual na própria série, e a última observação é
                 outra data, mostrada à parte.

A hora da coleta não entra aqui: é do carimbo da página (meta.json).
Usado por render_index.py (capa) e build_mudancas.py (/mudancas/).
"""

from __future__ import annotations

from datetime import datetime

MESC = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

NATUREZA = {
    432: "meta",
    1: "cotacao", 10813: "cotacao", 21619: "cotacao",
    1178: "taxa_dia", 4389: "taxa_dia",
    195: "periodo", 25: "periodo", 226: "periodo",
    13621: "posicao",
    24369: "trimestre",
}


def natureza(cod: int) -> str:
    return NATUREZA.get(int(cod), "mensal")


def _dt(d) -> datetime:
    return d if isinstance(d, datetime) else datetime.strptime(str(d), "%d/%m/%Y")


def mes_extenso(d) -> str:
    d = _dt(d)
    return f"{MESC[d.month - 1]} de {d.year}"


def referencia(cod: int, data) -> str:
    """O que a data de uma observação significa, em poucas palavras.
    Ex.: 'competência outubro de 2026', 'cotação de 25/11/2026'."""
    d, n = _dt(data), natureza(cod)
    dia = d.strftime("%d/%m/%Y")
    if n == "mensal":
        return f"competência {mes_extenso(d)}"
    if n == "trimestre":
        return f"trimestre móvel até {mes_extenso(d)}"
    if n == "cotacao":
        return f"cotação de {dia}"
    if n == "taxa_dia":
        return f"taxa do dia {dia}"
    if n == "periodo":
        return f"período de 1 mês iniciado em {dia}"
    if n == "posicao":
        return f"posição em {dia}"
    return f"dia {dia}"   # meta Selic: uma observação diária


def vigencia_meta(pts: list[dict]) -> tuple[datetime, float | None]:
    """(primeiro dia com o valor atual, valor anterior) numa série de pontos
    {dt, v} em ordem cronológica, como a 432."""
    cur = pts[-1]["v"]
    desde = pts[-1]["dt"]
    for p in reversed(pts):
        if p["v"] != cur:
            break
        desde = p["dt"]
    antes = next((p["v"] for p in reversed(pts) if p["dt"] < desde), None)
    return desde, antes


def rotulo_card(cod: int, pts: list[dict]) -> str:
    """Linha de tempo dos cards da capa. Na meta Selic, a vigência e a última
    observação são datas diferentes e saem as duas."""
    ult = pts[-1]["dt"]
    if natureza(cod) == "meta":
        desde, _ = vigencia_meta(pts)
        return f"em vigor desde {desde.strftime('%d/%m/%Y')} · última observação {ult.strftime('%d/%m/%Y')}"
    return referencia(cod, ult)
