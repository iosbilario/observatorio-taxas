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


# ── o que uma mudança registrada quer dizer ───────────────────────────────
#
# Usada por /mudancas/, pelas fichas e pelos títulos das divulgações. A
# classificação depende só do código, da data da observação e da hora da coleta
# (gravada em mudancas.json), nunca do dia em que a página é gerada: uma página
# refeita em dezembro descreve novembro como ele era na coleta.

from datetime import date, timedelta, timezone as _tz

BRT = _tz(timedelta(hours=-3))

# Acumulados do mês que crescem dia a dia (a série diária correspondente soma
# os dias úteis do mês): enquanto o mês não termina, o valor muda a cada coleta.
ACUMULA_NO_MES = {4390: 1178, 4391: 4389}
# Depois do fim do mês, a taxa do último dia útil ainda pode sair no dia útil
# seguinte. Nesse intervalo não há como afirmar se o período estava fechado.
FOLGA_FECHAMENTO = 5

TIPOS = {
    "nova": ("Nova observação", "A competência apareceu pela primeira vez no histórico observado."),
    "andamento": ("Atualização de período em andamento",
                  "O período ainda estava aberto na coleta: a série acumula os dias úteis do mês, e o valor muda "
                  "até o último deles."),
    "encerrado": ("Alteração em período encerrado",
                  "Uma observação de período já encerrado voltou da fonte com valor diferente. O SGS não informa o "
                  "motivo, e o Observatório não o deduz."),
    "alterado": ("Valor alterado", "Os dados disponíveis não bastam para dizer se o período ainda estava aberto."),
}


def _ultimo_dia_do_mes(d: date) -> date:
    prox = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return prox - timedelta(days=1)


def fim_do_periodo(cod: int, dt) -> date:
    """Último dia a que a observação se refere, pela convenção da série."""
    d = _dt(dt).date()
    n = natureza(cod)
    if n in ("mensal", "trimestre"):
        return _ultimo_dia_do_mes(d)
    if n == "periodo":                                   # 1 mês a partir da data
        m = d.month % 12 + 1
        a = d.year + (d.month == 12)
        return date(a, m, min(d.day, _ultimo_dia_do_mes(date(a, m, 1)).day)) - timedelta(days=1)
    return d                                             # cotação, taxa do dia, posição, meta do dia


def dia_da_coleta(quando_iso: str) -> date:
    return datetime.fromisoformat(quando_iso.replace("Z", "+00:00")).astimezone(BRT).date()


def classificar(tipo: str, cod: int, data, quando_iso: str) -> str:
    """'nova', 'andamento', 'encerrado' ou 'alterado' (ver TIPOS).

    tipo: "nova" (data que não existia) ou "revisao" (data que já existia com
    outro valor), como em mudancas.json."""
    if tipo == "nova":
        return "nova"
    fim = fim_do_periodo(cod, data)
    dia = dia_da_coleta(quando_iso)
    if int(cod) in ACUMULA_NO_MES:
        if dia <= fim:
            return "andamento"
        if dia <= fim + timedelta(days=FOLGA_FECHAMENTO):
            return "alterado"
        return "encerrado"
    return "encerrado" if dia > fim else "alterado"


def rotulo_tipo(chave: str) -> str:
    return TIPOS[chave][0]


def explicacao_tipo(chave: str) -> str:
    return TIPOS[chave][1]
