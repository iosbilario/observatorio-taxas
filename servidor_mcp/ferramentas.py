"""
ferramentas.py — As quatro operações do MCP, como funções puras.

Toda resposta traz procedência (produtor e distribuidor), licença, unidade e
versão dos dados. Erros viram ErroConsulta, com código, mensagem e sugestão.

Os cálculos usam as MESMAS funções do site:
  - build_correcao.fator_periodo: correção entre dois meses (calculadora /correcao/);
  - build_pages.acumulado: acumulado composto (páginas /reajuste/), usado como
    conferência do mesmo produto.
"""

from __future__ import annotations

import calendar
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_correcao import fator_periodo  # noqa: E402
from build_pages import MESES, acumulado  # noqa: E402

from . import catalogo as cat  # noqa: E402
from .dados import Dados, FonteIndisponivel  # noqa: E402

MAX_PONTOS = 500
MAX_VALOR = 1e12
AVISO_ATUALIZACAO = ("Dados coletados do SGS a cada 6 horas e publicados pelo Observatório; não são em tempo real. "
                     "A data de divulgação oficial não é registrada; a data de referência é a do SGS.")


class ErroConsulta(Exception):
    def __init__(self, codigo: str, mensagem: str, **detalhes):
        self.dados = {"erro": codigo, "mensagem": mensagem, **detalhes}
        super().__init__(json.dumps(self.dados, ensure_ascii=False))


# ------------------------------------------------------------------ util
def _data(s: str, campo: str, fim: bool = False) -> date:
    s = (s or "").strip()
    try:
        if len(s) == 7:
            a, m = int(s[:4]), int(s[5:7])
            if s[4] != "-":
                raise ValueError
            return date(a, m, calendar.monthrange(a, m)[1] if fim else 1)
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return date.fromisoformat(s)
    except ValueError:
        pass
    raise ErroConsulta("data_invalida", f"{campo} deve estar no formato AAAA-MM-DD ou AAAA-MM; recebido {s!r}.",
                       exemplo="2026-07 ou 2026-07-01")


def _periodo(ini: str, fim: str) -> tuple[date, date]:
    d0, d1 = _data(ini, "data_inicial"), _data(fim, "data_final", fim=True)
    if d0 > d1:
        raise ErroConsulta("periodo_invertido", "data_inicial é posterior a data_final.")
    if d0.year < 1990 or d1.year > 2100:
        raise ErroConsulta("periodo_fora_do_alcance", "Use datas entre 1990 e 2100.")
    return d0, d1


def _serie(indicador: str | int) -> int:
    cod = cat.resolver(indicador)
    if cod is None:
        raise ErroConsulta("indicador_desconhecido", f"Indicador {indicador!r} não existe no Observatório.",
                           indicadores_disponiveis=[{"codigo_sgs": x["codigo_sgs"], "apelidos": x["apelidos"]}
                                                    for x in cat.lista_publica() if x["situacao"].startswith("exposta")])
    if not cat.exposta(cod):
        m = cat.SERIES[cod]
        raise ErroConsulta("indicador_suspenso", f"{m['nome']} não está disponível por esta integração.",
                           motivo=cat.licenca(cod)["motivo"], produtor=m["produtor"],
                           onde_consultar=[m["produtor"]["url"], cat.SGS_API.format(codigo=cod)])
    return cod


def _historico(d: Dados, cod: int) -> list[dict]:
    try:
        pts, _ = d.historico(cod)
    except FonteIndisponivel as e:
        raise ErroConsulta("fonte_indisponivel", "Os dados do Observatório não puderam ser lidos agora. Tente de novo.",
                           detalhe=str(e)) from e
    if not pts:
        raise ErroConsulta("serie_vazia", f"A série {cod} não tem pontos publicados.")
    return pts


def _procedencia(cod: int) -> dict:
    m = cat.SERIES[cod]
    return {"produtor": m["produtor"], "distribuidor": cat.DISTRIBUIDOR, "codigo_sgs": cod,
            "fonte_url": cat.SGS_API.format(codigo=cod), "licenca": cat.licenca(cod)}


def _url_observatorio(cod: int, pts: list[dict], i: int) -> str:
    m = cat.SERIES[cod]
    if m.get("chave_reajuste") and i >= 11:
        dt = pts[i]["dt"]
        return f"{cat.SITE}/reajuste/{m['chave_reajuste']}-{quote(MESES[dt.month - 1])}-{dt.year}/"
    if m.get("ancora"):
        return f"{cat.SITE}/{m['ancora']}"
    return f"{cat.SITE}/data/{cod}_history.json"


def _ponto(p: dict) -> dict:
    return {"data_referencia": p["dt"].isoformat(), "valor": p["valor"], "valor_publicado": p["valor_publicado"]}


def _cobertura(pts: list[dict]) -> dict:
    return {"inicio": pts[0]["dt"].isoformat(), "fim": pts[-1]["dt"].isoformat(), "observacoes": len(pts)}


# ------------------------------------------------------------------ ferramentas
def get_latest_indicator(d: Dados, indicador: str) -> dict:
    cod = _serie(indicador)
    pts = _historico(d, cod)
    m, ult = cat.SERIES[cod], pts[-1]
    return {
        "indicador": m["nome"], "codigo_sgs": cod, "valor": ult["valor"], "valor_publicado": ult["valor_publicado"],
        "unidade": m["unidade"], "natureza": m["natureza"], "periodicidade": m["periodicidade"],
        "data_referencia": ult["dt"].isoformat(),
        "competencia": ult["dt"].strftime("%Y-%m") if m["periodicidade"].startswith("mensal") else None,
        "data_divulgacao": None, "data_ultima_coleta": d.meta().get("gerado_em"),
        "url_observatorio": _url_observatorio(cod, pts, len(pts) - 1),
        **_procedencia(cod), "versao_dados": d.versao(cod), "aviso": AVISO_ATUALIZACAO,
    }


def get_indicator_history(d: Dados, indicador: str, data_inicial: str, data_final: str) -> dict:
    cod = _serie(indicador)
    d0, d1 = _periodo(data_inicial, data_final)
    pts = _historico(d, cod)
    sel = [p for p in pts if d0 <= p["dt"] <= d1]
    if not sel:
        raise ErroConsulta("periodo_sem_dados", "Não há pontos publicados no período pedido.",
                           disponivel=_cobertura(pts))
    pagina, resto = sel[:MAX_PONTOS], sel[MAX_PONTOS:]
    m = cat.SERIES[cod]
    return {
        "indicador": m["nome"], "codigo_sgs": cod, "unidade": m["unidade"], "natureza": m["natureza"],
        "periodicidade": m["periodicidade"],
        "periodo_pedido": {"inicio": d0.isoformat(), "fim": d1.isoformat()},
        "periodo_retornado": _cobertura(pagina), "disponivel_na_serie": _cobertura(pts),
        "observacoes": len(pagina), "observacoes_no_periodo": len(sel),
        "pontos": [_ponto(p) for p in pagina],
        "paginacao": ({"limite_por_chamada": MAX_PONTOS, "proxima_data_inicial": resto[0]["dt"].isoformat()}
                      if resto else None),
        **_procedencia(cod), "versao_dados": d.versao(cod), "aviso": AVISO_ATUALIZACAO,
    }


def calculate_adjustment(d: Dados, valor: float, indice: str, data_inicial: str, data_final: str) -> dict:
    if not (isinstance(valor, (int, float)) and 0 < valor <= MAX_VALOR):
        raise ErroConsulta("valor_invalido", f"valor deve ser maior que 0 e no máximo {MAX_VALOR:.0f}.")
    cod = _serie(indice)
    m = cat.SERIES[cod]
    if m["natureza"] != "variacao_mensal":
        aceitos = [c for c, x in cat.SERIES.items() if x["natureza"] == "variacao_mensal" and cat.exposta(c)]
        raise ErroConsulta("indice_nao_aplicavel",
                           f"{m['nome']} não é uma variação mensal; reajuste e correção usam índices mensais.",
                           indices_aceitos=aceitos)
    d0, d1 = _data(data_inicial, "data_inicial"), _data(data_final, "data_final")
    pts = _historico(d, cod)
    meses = {(p["dt"].year, p["dt"].month): i for i, p in enumerate(pts)}
    i0, i1 = meses.get((d0.year, d0.month)), meses.get((d1.year, d1.month))
    if i0 is None or i1 is None:
        raise ErroConsulta("periodo_sem_dados", "Mês inicial ou final sem variação publicada.",
                           disponivel=_cobertura(pts))
    if i1 <= i0:
        raise ErroConsulta("periodo_invertido", "O mês final deve ser posterior ao inicial.")

    fator = fator_periodo(pts, i0, i1)                     # mesma função da calculadora do site
    aplicados = pts[i0 + 1: i1 + 1]
    assert abs(fator - (1 + acumulado(aplicados) / 100)) < 1e-12
    memoria, f = [], 1.0
    for p in aplicados:
        f *= 1 + p["valor"] / 100
        memoria.append({"competencia": p["dt"].strftime("%Y-%m"), "variacao_pct": p["valor"],
                        "fator_acumulado": f})
    taxa = (fator - 1) * 100
    final = valor * fator
    return {
        "valor_original": valor, "indice": m["nome"], "codigo_sgs": cod,
        "periodo": {"mes_inicial": pts[i0]["dt"].strftime("%Y-%m"), "mes_final": pts[i1]["dt"].strftime("%Y-%m"),
                    "meses_aplicados": len(aplicados),
                    "regra": "aplica as variações dos meses posteriores ao mês inicial até o mês final, inclusive"},
        "taxa_acumulada_pct": taxa, "fator": fator, "valor_final": final,
        "arredondado": {"taxa_acumulada_pct": f"{taxa:.2f}", "fator": f"{fator:.6f}", "valor_final": f"{final:.2f}",
                        "regra": "exibição com 2 casas (taxa e valor) e 6 casas (fator), como no site"},
        "formula": "fator = Π (1 + variação_mensal/100) dos meses aplicados; valor_final = valor_original × fator",
        "memoria_de_calculo": memoria,
        "equivalencia_no_site": {
            "correcao": f"{cat.SITE}/correcao/{m.get('chave_reajuste', '')}/" if m.get("chave_reajuste") else None,
            "reajuste_12_meses": (_url_observatorio(cod, pts, i1) if m.get("chave_reajuste") and i1 - i0 == 12
                                  else None)},
        "observacoes": (["Acumulado negativo: o efeito em contratos depende da cláusula de reajuste."]
                        if taxa < 0 else []),
        "codigo_do_calculo": "https://github.com/iosbilario/observatorio-taxas/blob/main/scripts/build_correcao.py",
        **_procedencia(cod), "versao_dados": d.versao(cod), "aviso": AVISO_ATUALIZACAO,
    }


def compare_indicators(d: Dados, indicadores: list[str], data_inicial: str, data_final: str) -> dict:
    if not isinstance(indicadores, list) or len(indicadores) != 2:
        raise ErroConsulta("parametro_invalido", "Informe exatamente dois indicadores.")
    cods = [_serie(x) for x in indicadores]
    if cods[0] == cods[1]:
        raise ErroConsulta("parametro_invalido", "Os dois indicadores são a mesma série.")
    d0, d1 = _periodo(data_inicial, data_final)
    series = []
    for cod in cods:
        pts = _historico(d, cod)
        sel = [p for p in pts if d0 <= p["dt"] <= d1]
        if not sel:
            raise ErroConsulta("periodo_sem_dados", f"Série {cod} sem pontos no período.", disponivel=_cobertura(pts))
        m = cat.SERIES[cod]
        resumo = {"primeiro": _ponto(sel[0]), "ultimo": _ponto(sel[-1]),
                  "minimo": min(p["valor"] for p in sel), "maximo": max(p["valor"] for p in sel)}
        if m["natureza"] == "variacao_mensal":
            resumo["acumulado_composto_pct"] = acumulado(sel)
        series.append({"indicador": m["nome"], "codigo_sgs": cod, "unidade": m["unidade"], "natureza": m["natureza"],
                       "periodicidade": m["periodicidade"], "cobertura_no_periodo": _cobertura(sel),
                       "resumo": resumo, **_procedencia(cod), "_sel": sel})

    a, b = series
    mesma_base = a["natureza"] == b["natureza"] and a["unidade"] == b["unidade"] and \
        a["periodicidade"].split()[0] == b["periodicidade"].split()[0]
    datas_a = {p["dt"]: p for p in a["_sel"]}
    comuns = [(p, datas_a[p["dt"]]) for p in b["_sel"] if p["dt"] in datas_a]
    resultado: dict = {"comparavel_diretamente": mesma_base}
    if mesma_base:
        lim = comuns[:MAX_PONTOS]
        resultado["pontos_alinhados"] = [{"data_referencia": pb["dt"].isoformat(), "a": pa["valor"], "b": pb["valor"],
                                          "diferenca_a_menos_b": pa["valor"] - pb["valor"]} for pb, pa in lim]
        resultado["pontos_alinhados_total"] = len(comuns)
        resultado["truncado"] = len(comuns) > MAX_PONTOS
        if a["natureza"] == "variacao_mensal":
            ra, rb = a["resumo"]["acumulado_composto_pct"], b["resumo"]["acumulado_composto_pct"]
            resultado["acumulados_no_periodo"] = {"a_pct": ra, "b_pct": rb, "diferenca_pp": ra - rb}
        metodo = ("Mesma natureza, unidade e periodicidade: comparação ponto a ponto nas datas comuns"
                  + ("; para variações mensais, também o acumulado composto de cada série no período." if
                     a["natureza"] == "variacao_mensal" else "."))
    else:
        metodo = (f"Não comparáveis ponto a ponto: {a['indicador']} é {a['natureza']} em {a['unidade']} "
                  f"({a['periodicidade']}) e {b['indicador']} é {b['natureza']} em {b['unidade']} "
                  f"({b['periodicidade']}). Cada série é resumida separadamente, sem subtrair valores.")
    for s in series:
        s.pop("_sel")
    return {"periodo_pedido": {"inicio": d0.isoformat(), "fim": d1.isoformat()}, "series": series,
            "metodologia": metodo, "diferencas_de_cobertura": {
                "a": series[0]["cobertura_no_periodo"], "b": series[1]["cobertura_no_periodo"],
                "datas_em_comum": len(comuns)},
            **resultado, "versao_dados": d.versao(), "aviso": AVISO_ATUALIZACAO}


def list_indicators() -> dict:
    return {"indicadores": cat.lista_publica(), "aviso": AVISO_ATUALIZACAO}
