#!/usr/bin/env python3
"""
build_indicadores.py — Vitrine de indicadores: /indicadores/ e uma página por série.

Para cada série de config.yml, gera docs/indicadores/<slug>/index.html com:
  - a resposta primeiro: valor atual, unidade, data de referência e produtor,
    numa frase que um buscador ou um assistente de IA pode citar como está;
  - o que o indicador mede e para que serve;
  - números de contexto calculados a partir de data/ (acumulado em 12 meses
    para variações mensais; mudança desde a observação anterior e em 12 meses
    para níveis, taxas, cotações e estoques);
  - tabela das últimas observações (fim de cada mês, nas séries diárias);
  - ficha técnica (produtor, série SGS, unidade, periodicidade, licença);
  - perguntas e respostas visíveis + FAQPage, Dataset e BreadcrumbList em JSON-LD;
  - gráfico (iframe do /embed.html, carregado sob demanda) e links para os dados.

E o hub docs/indicadores/index.html, com todas as séries agrupadas numa tabela
estática. Tudo legível sem JavaScript. Sem data/hora da coleta no conteúdo: a
página só muda quando o dado da própria série muda, o que mantém o lastmod do
sitemap honesto.

Metadados de cada série (nome, produtor, unidade, periodicidade, natureza,
licença) vêm de servidor_mcp/catalogo.py, a mesma fonte do servidor MCP. Este
arquivo acrescenta só o que é da página: slug, formatação e textos.

O sitemap é escrito por render_index.py, que roda depois deste script.

    python scripts/build_indicadores.py
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_correcao import CSS, faq_html, faq_ld  # noqa: E402
from build_pages import (FAVICON, INDICES as REAJUSTE, WEBSITE_ID, acumulado, fmt_num,  # noqa: E402
                         goatcounter_beacon, jsonld_script, migalhas, slug_mes)
from servidor_mcp import catalogo as cat  # noqa: E402

DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
OUT_DIR = DOCS_DIR / "indicadores"
BASE_URL = "https://observatoriodetaxas.tec.br"
HUB_URL = f"{BASE_URL}/indicadores/"
LICENCA_DADOS_URL = "https://github.com/iosbilario/observatorio-taxas/blob/main/LICENSE-DADOS.md"
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Acumulados no mês cujo último ponto pode ser o mês corrente, ainda parcial.
# Parcial = a série diária correspondente já tem dias nesse mesmo mês.
PARCIAL_SE = {4390: 1178, 4391: 4389}

# Séries que o VAR aceita (docs/var.html) e que têm reajuste/correção.
NO_VAR = {433, 13522, 189, 432, 1, 24369, 25, 4390, 4391, 7478, 256, 20714, 21082, 4513}
REAJUSTE_POR_CODIGO = {v["codigo"]: k for k, v in REAJUSTE.items()}

# slug, título curto, casas, prefixo, sufixo, o que é, para que serve, outros nomes.
PAGINAS: dict[int, dict] = {
    432: dict(slug="meta-selic", curto="Taxa Selic (meta)", casas=2, suf="% a.a.",
              o_que="A meta da taxa Selic é a taxa básica de juros da economia brasileira, definida pelo Comitê de "
                    "Política Monetária (Copom) do Banco Central em reuniões realizadas a cada seis semanas, aproximadamente.",
              uso="É a referência para os juros de empréstimos, financiamentos e aplicações de renda fixa, e o principal "
                  "instrumento do Banco Central para controlar a inflação.",
              outros=["taxa Selic hoje", "juros básicos", "taxa básica de juros", "decisão do Copom"]),
    1178: dict(slug="selic-efetiva", curto="Selic efetiva (anualizada)", casas=2, suf="% a.a.",
               o_que="Taxa média das operações compromissadas de um dia com títulos públicos federais registradas no "
                     "sistema Selic, expressa em % ao ano na base de 252 dias úteis. Fica próxima da meta definida pelo Copom.",
               uso="Mostra a taxa praticada no mercado em cada dia útil e é a base da remuneração de títulos como o Tesouro Selic.",
               outros=["Selic over", "Selic diária", "taxa Selic efetiva"]),
    4390: dict(slug="selic-acumulada-no-mes", curto="Selic acumulada no mês", casas=2, suf="%",
               o_que="Taxa Selic efetiva acumulada em cada mês, em %.",
               uso="É usada na atualização de tributos federais pagos em atraso e de restituições do Imposto de Renda, "
                   "entre outros cálculos.",
               outros=["Selic mensal", "Selic do mês"]),
    226: dict(slug="tr", curto="TR (Taxa Referencial)", casas=4, suf="%",
              o_que="Taxa calculada pelo Banco Central a partir dos juros de títulos públicos federais. Cada valor vale "
                    "para o período de um mês que começa na data de referência.",
              uso="Compõe a remuneração da poupança e do FGTS e corrige contratos do Sistema Financeiro da Habitação.",
              outros=["Taxa Referencial hoje", "TR do mês"]),
    25: dict(slug="poupanca-regra-antiga", curto="Poupança (depósitos até 03/05/2012)", casas=4, suf="%",
             o_que="Rentabilidade dos depósitos de poupança feitos até 03/05/2012, pela regra antiga: 0,5% ao mês "
                   "mais a TR. Cada valor vale para o período de um mês que começa na data de referência.",
             uso="Vale para os saldos depositados até aquela data.",
             outros=["poupança antiga", "rendimento da poupança antiga"]),
    195: dict(slug="poupanca", curto="Rendimento da poupança", casas=4, suf="%",
              o_que="Rentabilidade dos depósitos de poupança feitos a partir de 04/05/2012. Pela regra atual, quando a "
                    "meta Selic está acima de 8,5% ao ano, a poupança rende 0,5% ao mês mais a TR; com a meta Selic em "
                    "8,5% ou menos, rende 70% da Selic mais a TR. Cada valor vale para o período de um mês que começa "
                    "na data de referência.",
              uso="Mostra quanto rende a poupança no mês, para comparar com outras aplicações.",
              outros=["rendimento da poupança hoje", "quanto rende a poupança", "poupança regra nova"]),
    4389: dict(slug="cdi", curto="CDI (taxa DI)", casas=2, suf="% a.a.",
               o_que="Taxa média dos empréstimos de um dia entre instituições financeiras (taxa DI), calculada pela B3, "
                     "em % ao ano na base de 252 dias úteis.",
               uso="É a referência da renda fixa: CDBs, LCIs, LCAs e fundos costumam render um percentual do CDI.",
               outros=["CDI hoje", "taxa DI", "taxa CDI"]),
    4391: dict(slug="cdi-acumulado-no-mes", curto="CDI acumulado no mês", casas=2, suf="%",
               o_que="Taxa DI acumulada em cada mês, em %, calculada pela B3.",
               uso="Permite calcular quanto uma aplicação que rende 100% do CDI teria rendido em cada mês.",
               outros=["CDI mensal", "CDI do mês"]),
    256: dict(slug="tjlp", curto="TJLP", casas=2, suf="% a.a.",
              o_que="Taxa de Juros de Longo Prazo, fixada pelo Conselho Monetário Nacional e divulgada pelo Banco "
                    "Central, em % ao ano.",
              uso="Corrige contratos de financiamento do BNDES firmados antes de 2018 e parte dos recursos do FAT. "
                  "Os contratos novos do BNDES usam a TLP.",
              outros=["Taxa de Juros de Longo Prazo", "TJLP hoje"]),
    433: dict(slug="ipca", curto="IPCA (inflação oficial)", casas=2, suf="%",
              o_que="Índice Nacional de Preços ao Consumidor Amplo, a inflação oficial do Brasil, calculada pelo IBGE "
                    "para famílias com renda de 1 a 40 salários mínimos.",
              uso="É a referência do sistema de metas de inflação e corrige contratos, títulos públicos (Tesouro IPCA+) "
                  "e valores em geral.",
              outros=["inflação do mês", "IPCA hoje", "inflação oficial"]),
    13522: dict(slug="ipca-12-meses", curto="IPCA acumulado em 12 meses", casas=2, suf="%",
                o_que="Variação do IPCA nos últimos 12 meses, calculada pelo IBGE.",
                uso="É o número comparado com a meta de inflação definida pelo Conselho Monetário Nacional.",
                outros=["inflação em 12 meses", "inflação acumulada", "IPCA anual"]),
    188: dict(slug="inpc", curto="INPC", casas=2, suf="%",
              o_que="Índice Nacional de Preços ao Consumidor, calculado pelo IBGE para famílias com renda de 1 a 5 "
                    "salários mínimos.",
              uso="Corrige salários em negociações coletivas e os benefícios do INSS acima do salário mínimo.",
              outros=["INPC hoje", "inflação das famílias de menor renda"]),
    189: dict(slug="igp-m", curto="IGP-M", casas=2, suf="%",
              o_que="Índice Geral de Preços – Mercado, calculado pela FGV IBRE. Combina preços ao produtor, ao "
                    "consumidor e da construção civil.",
              uso="É o índice tradicional de reajuste de contratos de aluguel e de algumas tarifas.",
              outros=["IGP-M hoje", "índice do aluguel", "inflação do aluguel"]),
    190: dict(slug="igp-di", curto="IGP-DI", casas=2, suf="%",
              o_que="Índice Geral de Preços – Disponibilidade Interna, calculado pela FGV IBRE com a mesma composição "
                    "do IGP-M, mas com preços coletados no mês de referência inteiro.",
              uso="Corrige contratos públicos e de fornecimento e é usado em séries históricas de preços.",
              outros=["IGP-DI hoje"]),
    7478: dict(slug="ipca-15", curto="IPCA-15 (prévia da inflação)", casas=2, suf="%",
               o_que="Prévia da inflação oficial, calculada pelo IBGE com a mesma metodologia do IPCA, mas com preços "
                     "coletados da metade do mês anterior até a metade do mês de referência.",
               uso="Antecipa a tendência do IPCA do mês.",
               outros=["prévia da inflação", "IPCA-15 hoje"]),
    1: dict(slug="dolar", curto="Dólar", casas=4, pref="R$ ",
            o_que="Taxa de câmbio do dólar americano em reais, na ponta de venda, divulgada pelo Banco Central em cada "
                  "dia útil (PTAX).",
            uso="É a referência oficial para contratos em dólar, declarações e conversões.",
            outros=["cotação do dólar hoje", "dólar PTAX", "dólar oficial"]),
    10813: dict(slug="dolar-compra", curto="Dólar (compra)", casas=4, pref="R$ ",
                o_que="Taxa de câmbio do dólar americano em reais, na ponta de compra, divulgada pelo Banco Central em "
                      "cada dia útil (PTAX).",
                uso="Complementa a taxa de venda; a diferença entre as duas é o spread da PTAX.",
                outros=["dólar compra PTAX"]),
    21619: dict(slug="euro", curto="Euro", casas=4, pref="R$ ",
                o_que="Taxa de câmbio do euro em reais, na ponta de venda, divulgada pelo Banco Central em cada dia útil.",
                uso="É a referência oficial para conversões e contratos em euro.",
                outros=["cotação do euro hoje", "euro PTAX"]),
    24363: dict(slug="ibc-br", curto="IBC-Br (prévia do PIB)", casas=2,
                o_que="Índice de Atividade Econômica do Banco Central, número-índice mensal que acompanha a atividade "
                      "da economia (série sem ajuste sazonal).",
                uso="É usado como sinal antecipado do PIB, que o IBGE divulga a cada trimestre.",
                outros=["prévia do PIB", "atividade econômica"]),
    24369: dict(slug="desemprego", curto="Taxa de desemprego", casas=1, suf="%",
                o_que="Taxa de desocupação medida pelo IBGE na PNAD Contínua, em % da força de trabalho, para "
                      "trimestres móveis.",
                uso="É o principal indicador do mercado de trabalho no Brasil.",
                outros=["desemprego hoje", "taxa de desocupação", "PNAD Contínua"]),
    20539: dict(slug="saldo-de-credito", curto="Saldo do crédito", casas=0, pref="R$ ", suf=" milhões",
                o_que="Saldo, no fim de cada mês, das operações de crédito do Sistema Financeiro Nacional, com recursos "
                      "livres e direcionados, para pessoas físicas e jurídicas, em R$ milhões.",
                uso="Mede o tamanho do crédito na economia.",
                outros=["carteira de crédito", "volume de crédito"]),
    20714: dict(slug="juros-do-credito", curto="Juros médios do crédito", casas=2, suf="% a.a.",
                o_que="Taxa média de juros das novas operações de crédito contratadas no mês no Sistema Financeiro "
                      "Nacional, ponderada pelo valor das operações, em % ao ano.",
                uso="Mostra quanto custa, em média, tomar crédito no país.",
                outros=["taxa média de juros", "juros dos empréstimos"]),
    21082: dict(slug="inadimplencia", curto="Inadimplência do crédito", casas=2, suf="%",
                o_que="Percentual da carteira de crédito do Sistema Financeiro Nacional com pelo menos uma parcela em "
                      "atraso há mais de 90 dias.",
                uso="Mede o risco de calote nas operações de crédito.",
                outros=["inadimplência hoje", "calote", "atraso acima de 90 dias"]),
    13621: dict(slug="reservas-internacionais", curto="Reservas internacionais", casas=0, pref="US$ ", suf=" milhões",
                o_que="Estoque de reservas internacionais do Brasil no conceito caixa, em US$ milhões, administrado "
                      "pelo Banco Central.",
                uso="Protege o país contra choques externos; o Banco Central as usa em intervenções no câmbio.",
                outros=["reservas do Brasil", "reservas cambiais"]),
    4513: dict(slug="divida-liquida", curto="Dívida líquida do setor público", casas=2, suf="% do PIB",
               o_que="Dívida líquida do setor público consolidado (governos federal, estaduais e municipais, Banco "
                     "Central e empresas estatais), em % do PIB.",
               uso="É um dos principais indicadores da situação fiscal do país.",
               outros=["dívida pública", "DLSP"]),
}

EXTRA_CSS = """
.lead{font-size:1.12rem;color:var(--papel)}
.lead b{color:var(--carimbo)}
main{overflow-wrap:anywhere}
.rolagem{overflow-x:auto}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr));gap:10px;margin:1rem 0}
.kpi{border:1px solid var(--linha);border-radius:10px;padding:.8rem 1rem}
.kpi span{display:block;font-family:"IBM Plex Mono",monospace;font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;color:var(--papel-45)}
.kpi b{font-family:"Fraunces",Georgia,serif;font-size:1.25rem;font-variant-numeric:tabular-nums}
dl.ficha{display:grid;grid-template-columns:minmax(140px,30%) 1fr;gap:.4rem 1rem;margin:0}
dl.ficha dt{font-family:"IBM Plex Mono",monospace;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--papel-45);padding-top:.2rem}
dl.ficha dd{margin:0}
.grafico iframe{width:100%;height:320px;border:0;border-radius:8px;background:var(--campo)}
.tabela-hub td:nth-child(2){white-space:nowrap}
.tabela-hub th,.tabela-hub td{text-align:left}
.tabela-hub td.num{text-align:right}
h2.grupo{margin-top:1.6rem}
@media(max-width:520px){dl.ficha{grid-template-columns:1fr}}
"""

CSP = ("default-src 'self'; base-uri 'self'; object-src 'none'; "
       "img-src 'self' data: https://observatoriotaxas.goatcounter.com; style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; script-src 'self' https://gc.zgo.at; "
       "connect-src 'self' https://observatoriotaxas.goatcounter.com; frame-src 'self'")


# --------------------------------------------------------------------------- dados
def parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


def load_history(codigo: int) -> list[dict]:
    path = DATA_DIR / f"{codigo}_history.json"
    if not path.exists():
        return []
    pts = [{"dt": parse_date(p["data"]), "valor": float(p["valor"]), "bruto": p["valor"]}
           for p in json.loads(path.read_text(encoding="utf-8"))]
    pts.sort(key=lambda p: p["dt"])
    return pts


def series_config() -> list[dict]:
    return yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["series"]


def mensal(codigo: int) -> bool:
    return cat.SERIES[codigo]["periodicidade"].startswith("mensal")


def fim_de_cada_mes(pts: list[dict]) -> list[dict]:
    """Última observação de cada mês (séries diárias)."""
    por_mes: dict = {}
    for p in pts:
        por_mes[(p["dt"].year, p["dt"].month)] = p
    return [por_mes[k] for k in sorted(por_mes)]


def ultima_mudanca(pts: list[dict]) -> tuple[dict, dict] | None:
    """(ponto anterior, ponto novo) da mudança de valor mais recente."""
    for i in range(len(pts) - 1, 0, -1):
        if pts[i]["valor"] != pts[i - 1]["valor"]:
            return pts[i - 1], pts[i]
    return None


def ponto_ha_um_ano(pts: list[dict]) -> dict | None:
    ref = pts[-1]["dt"]
    alvo = ref.replace(year=ref.year - 1)
    antes = [p for p in pts if p["dt"] <= alvo]
    return antes[-1] if antes else None


# ------------------------------------------------------------------- formatação
def valor(codigo: int, v: float) -> str:
    p = PAGINAS[codigo]
    return f"{p.get('pref', '')}{fmt_num(v, p['casas'])}{p.get('suf', '')}"


def data_ref(codigo: int, dt: datetime) -> str:
    return f"{MESES[dt.month - 1]} de {dt.year}" if mensal(codigo) else dt.strftime("%d/%m/%Y")


def em_pontos_percentuais(codigo: int) -> bool:
    return cat.SERIES[codigo]["natureza"] not in ("cotacao", "estoque", "indice")


def variacao(codigo: int, de: float, ate: float) -> str:
    if em_pontos_percentuais(codigo):
        d = ate - de
        sinal = "+" if d > 0 else ("−" if d < 0 else "")
        return f"{sinal}{fmt_num(abs(d), 2)} p.p."
    if de == 0:
        return "—"
    d = (ate / de - 1) * 100
    sinal = "+" if d > 0 else ("−" if d < 0 else "")
    return f"{sinal}{fmt_num(abs(d), 2)}%"


def titulo_curto(base: str, sufixos: list[str], limite: int = 70) -> str:
    """O maior título que cabe no limite (buscadores cortam títulos longos)."""
    for s in sufixos:
        if len(base + s) <= limite:
            return base + s
    return base[:limite]


def url_pagina(codigo: int) -> str:
    return f"{HUB_URL}{PAGINAS[codigo]['slug']}/"


def e(s: str) -> str:
    return html.escape(s, quote=True)


# ---------------------------------------------------------------------- páginas
def head(title: str, desc: str, canonical: str, jsonld: str, crumb: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="{CSP}"/>
<meta name="referrer" content="strict-origin-when-cross-origin"/>
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}"/>
<meta name="robots" content="index, follow, max-snippet:-1"/>
<meta name="theme-color" content="#0E1210"/>
<link rel="canonical" href="{canonical}"/>
{FAVICON}
<meta property="og:type" content="website"/>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:site_name" content="Observatório de Taxas"/>
<meta property="og:title" content="{e(title)}"/>
<meta property="og:description" content="{e(desc)}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="{BASE_URL}/og-image.png"/>
{jsonld}
<style>{CSS}{EXTRA_CSS}</style>
{goatcounter_beacon()}
</head>
<body><a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
<!-- nav:start -->
<!-- nav:end -->
<div class="wrap">
{crumb}
<main id="conteudo">
"""


def rodape(produtores: str) -> str:
    return f"""
</main>
<footer>Dados: {produtores}. O Observatório obtém as séries na <a href="https://www3.bcb.gov.br/sgspub/">API pública do SGS</a>
do Banco Central do Brasil e não altera os valores. Série histórica versionada e auditável no
<a href="https://github.com/iosbilario/observatorio-taxas">GitHub</a>. Conteúdo informativo, sem caráter de recomendação financeira.
</footer>
</div></body></html>
"""


def mes_parcial(codigo: int, pts: list[dict]) -> bool:
    diaria = PARCIAL_SE.get(codigo)
    if not diaria or not pts:
        return False
    d = load_history(diaria)
    return bool(d) and (d[-1]["dt"].year, d[-1]["dt"].month) == (pts[-1]["dt"].year, pts[-1]["dt"].month)


def completos(codigo: int, pts: list[dict]) -> tuple[list[dict], dict | None]:
    """Separa o mês corrente ainda parcial (se houver) dos meses fechados."""
    if mes_parcial(codigo, pts) and len(pts) > 1:
        return pts[:-1], pts[-1]
    return pts, None


def contexto(codigo: int, pts: list[dict]) -> tuple[list[tuple[str, str]], list[str]]:
    """KPIs (rótulo, valor) e frases de contexto, conforme a natureza da série."""
    m = cat.SERIES[codigo]
    ult = pts[-1]
    kpis = [("Valor atual", valor(codigo, ult["valor"])), ("Referência", data_ref(codigo, ult["dt"]))]
    frases: list[str] = []
    if m["natureza"] == "variacao_mensal" and mensal(codigo) and len(pts) >= 12:
        ac12 = acumulado(pts[-12:])
        kpis.append(("Acumulado em 12 meses", f"{fmt_num(ac12, 2)}%"))
        do_ano = [p for p in pts if p["dt"].year == ult["dt"].year]
        ac_ano = acumulado(do_ano)
        kpis.append((f"Acumulado em {ult['dt'].year}", f"{fmt_num(ac_ano, 2)}%"))
        frases.append(f"Nos 12 meses até {data_ref(codigo, ult['dt'])}, a variação acumulada foi de "
                      f"{fmt_num(ac12, 2)}% (produto de 1 + variação mensal ÷ 100, menos 1). Em {ult['dt'].year}, "
                      f"até {MESES[ult['dt'].month - 1]}, o acumulado é de {fmt_num(ac_ano, 2)}%.")
    else:
        mud = ultima_mudanca(pts)
        if mud:
            ant, nov = mud
            kpis.append(("Última mudança", data_ref(codigo, nov["dt"])))
            frases.append(f"A última mudança foi em {data_ref(codigo, nov['dt'])}: de {valor(codigo, ant['valor'])} "
                          f"para {valor(codigo, nov['valor'])} ({variacao(codigo, ant['valor'], nov['valor'])}).")
        um_ano = ponto_ha_um_ano(pts)
        if um_ano:
            kpis.append(("Em 12 meses", variacao(codigo, um_ano["valor"], ult["valor"])))
            frases.append(f"Há um ano, em {data_ref(codigo, um_ano['dt'])}, o valor era {valor(codigo, um_ano['valor'])} "
                          f"({variacao(codigo, um_ano['valor'], ult['valor'])} até agora).")
        janela = [p for p in pts if p["dt"] > ult["dt"].replace(year=ult["dt"].year - 1)]
        if len(janela) > 2:
            mx = max(janela, key=lambda p: p["valor"])
            mn = min(janela, key=lambda p: p["valor"])
            frases.append(f"Nos últimos 12 meses, o maior valor foi {valor(codigo, mx['valor'])} "
                          f"({data_ref(codigo, mx['dt'])}) e o menor, {valor(codigo, mn['valor'])} "
                          f"({data_ref(codigo, mn['dt'])}).")
    return kpis, frases


def tabela(codigo: int, pts: list[dict]) -> str:
    base = pts if mensal(codigo) else fim_de_cada_mes(pts)
    linhas = base[-12:][::-1]
    titulo = "Últimos 12 meses" if mensal(codigo) else "Último valor de cada mês (12 meses)"
    corpo = "".join(f"<tr><td>{data_ref(codigo, p['dt']) if mensal(codigo) else p['dt'].strftime('%d/%m/%Y')}</td>"
                    f"<td>{valor(codigo, p['valor'])}</td></tr>" for p in linhas)
    return (f'<section class="card" aria-labelledby="tab-t"><h2 id="tab-t">{titulo}</h2>'
            f'<table><thead><tr><th scope="col">Referência</th><th scope="col">Valor</th></tr></thead>'
            f"<tbody>{corpo}</tbody></table>"
            f'<p class="mut">Histórico completo desde {pts[0]["dt"].strftime("%d/%m/%Y")} em '
            f'<a href="{BASE_URL}/data/{codigo}_history.json">{codigo}_history.json</a>.</p></section>')


def licenca_url(codigo: int) -> str:
    return ODBL_URL if cat.SERIES[codigo]["produtor"] is cat.BCB else LICENCA_DADOS_URL


def pagina(codigo: int, pts: list[dict], grupo: str) -> str:
    m = cat.SERIES[codigo]
    p = PAGINAS[codigo]
    prod = m["produtor"]
    pts, parcial = completos(codigo, pts)
    ult = pts[-1]
    url = url_pagina(codigo)
    v_txt = valor(codigo, ult["valor"])
    ref_txt = data_ref(codigo, ult["dt"])
    nome_curto = p["curto"]

    title = titulo_curto(f"{nome_curto} hoje: {v_txt}", [f" ({ref_txt}) | Observatório de Taxas",
                                                         f" ({ref_txt})", " | Observatório de Taxas", ""])
    desc = (f"{m['nome']}: {v_txt} na referência de {ref_txt}, segundo o {prod['nome']} (série SGS {codigo}). "
            f"O que é, histórico desde {pts[0]['dt'].year}, últimos 12 meses, gráfico e dados abertos em JSON.")
    resposta = (f"{m['nome']}: <b>{v_txt}</b>, referência {ref_txt}. Fonte: {prod['nome']} ({prod['sigla']}), "
                f"série {codigo} do SGS do Banco Central.")
    resposta_txt = (f"{m['nome']}: {v_txt}, referência {ref_txt}. Fonte: {prod['nome']} ({prod['sigla']}), "
                    f"série {codigo} do SGS do Banco Central.")
    kpis, frases = contexto(codigo, pts)

    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Indicadores", HUB_URL),
                                     (nome_curto, url)])
    perguntas = [
        (f"Qual é o valor de {m['nome']} hoje?",
         f"O último valor publicado é {v_txt}, com referência em {ref_txt}. O dado é do {prod['nome']} e vem da "
         f"série {codigo} do SGS do Banco Central."),
        (f"O que é {m['nome']}?", f"{p['o_que']} {p['uso']}"),
        (f"Quem calcula {m['nome']}?",
         f"{prod['nome']} ({prod['sigla']}). O Banco Central distribui a série no SGS com o código {codigo}, "
         "e o Observatório de Taxas coleta os valores a cada 6 horas, sem alterá-los."),
        ("Com que frequência o dado é atualizado?",
         f"A periodicidade da série é {m['periodicidade']}. O Observatório confere o SGS a cada 6 horas e "
         "atualiza esta página quando sai um valor novo ou revisado."),
        ("Onde baixar a série histórica?",
         f"Em {BASE_URL}/data/{codigo}_history.json (JSON aberto, desde {pts[0]['dt'].strftime('%d/%m/%Y')}) "
         f"ou direto na API do SGS: {cat.SGS_API.format(codigo=codigo)}."),
    ]
    if frases:
        perguntas.insert(1, ("Como o valor mudou recentemente?", " ".join(frases)))

    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "@id": f"{url}#dataset", "name": f"{m['nome']} — série histórica (SGS {codigo})",
        "description": f"{p['o_que']} {p['uso']} Série {codigo} do SGS do Banco Central, coletada e versionada "
                       f"pelo Observatório de Taxas desde {pts[0]['dt'].strftime('%d/%m/%Y')}.",
        "url": url, "inLanguage": "pt-BR", "isAccessibleForFree": True,
        "keywords": [m["nome"], nome_curto, *p["outros"], f"SGS {codigo}", grupo],
        "creator": {"@type": "Organization", "name": prod["nome"], "url": prod["url"]},
        "publisher": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"},
        "license": licenca_url(codigo),
        "temporalCoverage": f"{pts[0]['dt']:%Y-%m-%d}/{ult['dt']:%Y-%m-%d}",
        "dateModified": f"{ult['dt']:%Y-%m-%d}",
        "variableMeasured": {"@type": "PropertyValue", "name": m["nome"], "unitText": m["unidade"],
                             "value": ult["valor"]},
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": f"{BASE_URL}/data/{codigo}_history.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": cat.SGS_API.format(codigo=codigo)},
        ],
        "isPartOf": {"@id": WEBSITE_ID},
    }
    jsonld = (jsonld_script(dataset) + "\n" + faq_ld(url, title, crumb_ld, perguntas) + "\n"
              + jsonld_script({"@context": "https://schema.org", **crumb_ld}))

    kpi_html = "".join(f'<div class="kpi"><span>{e(r)}</span><b>{e(v)}</b></div>' for r, v in kpis)
    lic = ("ODbL 1.0, com atribuição ao Banco Central do Brasil" if prod is cat.BCB
           else f"termos do produtor ({prod['sigla']}); o Observatório não relicencia a série")
    relacionados = [f'<a class="pill" href="{BASE_URL}/embed.html?s={codigo}">Gráfico para incorporar</a>',
                    f'<a class="pill" href="{BASE_URL}/retransmissora.html">Retransmissora</a>']
    if codigo in NO_VAR:
        relacionados.insert(0, f'<a class="pill" href="{BASE_URL}/var.html?s={codigo}">Conferir uma afirmação (VAR)</a>')
    if codigo in REAJUSTE_POR_CODIGO and mensal(codigo):
        k = REAJUSTE_POR_CODIGO[codigo]
        relacionados.insert(0, f'<a class="pill" href="{BASE_URL}/correcao/{k}/">Correção monetária pelo {REAJUSTE[k]["nome"]}</a>')
        relacionados.insert(0, f'<a class="pill" href="{BASE_URL}/reajuste/{k}-{slug_mes(ult["dt"])}/">'
                               f'Reajuste pelo {REAJUSTE[k]["nome"]} ({MESES[ult["dt"].month - 1]})</a>')
    outros_nomes = ", ".join(p["outros"])
    nota_parcial = ""
    if parcial:
        nota_parcial = (f'<p class="mut">{MESES[parcial["dt"].month - 1].capitalize()} de {parcial["dt"].year} ainda está '
                        f'em andamento: {valor(codigo, parcial["valor"])} acumulado até a última coleta. Os números '
                        f'abaixo usam só meses fechados.</p>\n')

    corpo = f"""<article>
<h1>{e(nome_curto)} hoje</h1>
<p class="lead">{resposta}</p>
{nota_parcial}<div class="kpis">{kpi_html}</div>
{"".join(f"<p>{e(f)}</p>" for f in frases)}
<section class="card" aria-labelledby="oque-t"><h2 id="oque-t">O que é</h2>
<p>{e(p['o_que'])}</p><p>{e(p['uso'])}</p>
<p class="mut">Também procurado como: {e(outros_nomes)}.</p></section>
<section class="card grafico" aria-labelledby="graf-t"><h2 id="graf-t">Gráfico</h2>
<iframe src="/embed.html?s={codigo}&amp;tema=escuro&amp;h=320" title="{e(m['nome'])}: gráfico dos últimos 24 meses" loading="lazy"></iframe>
</section>
{tabela(codigo, pts)}
<section class="card" aria-labelledby="ficha-t"><h2 id="ficha-t">Ficha técnica</h2>
<dl class="ficha">
<dt>Indicador</dt><dd>{e(m['nome'])}</dd>
<dt>Produzido por</dt><dd><a href="{prod['url']}">{e(prod['nome'])}</a></dd>
<dt>Obtido em</dt><dd>SGS do Banco Central do Brasil, <a href="{cat.SGS_API.format(codigo=codigo)}">série {codigo}</a></dd>
<dt>Unidade</dt><dd>{e(m['unidade'])}</dd>
<dt>Periodicidade</dt><dd>{e(m['periodicidade'])}</dd>
<dt>Grupo</dt><dd>{e(grupo)}</dd>
<dt>Histórico</dt><dd>{pts[0]['dt']:%d/%m/%Y} a {ult['dt']:%d/%m/%Y} ({len(pts)} observações)</dd>
<dt>Licença dos dados</dt><dd>{e(lic)} (<a href="{licenca_url(codigo)}">termos</a>)</dd>
<dt>Como citar</dt><dd>{e(resposta_txt)} Dados via Observatório de Taxas ({url}).</dd>
</dl></section>
{faq_html(perguntas)}
<section class="card" aria-labelledby="rel-t"><h2 id="rel-t">Ferramentas e dados</h2>
<p>{"".join(relacionados)}<a class="pill" href="{BASE_URL}/data/{codigo}_history.json">Série em JSON</a><a class="pill" href="{HUB_URL}">Todos os indicadores</a></p>
</section>
</article>"""
    produtores = f"{m['nome']} produzido por {prod['nome']} ({prod['sigla']})"
    return head(title, desc, url, jsonld, crumb_html) + corpo + rodape(produtores)


def hub(linhas: list[dict]) -> str:
    title = "Indicadores econômicos do Brasil hoje | Observatório de Taxas"
    desc = (f"Os {len(linhas)} indicadores acompanhados pelo Observatório de Taxas, com valor atual, data de referência "
            "e produtor: juros, inflação, câmbio, atividade, crédito, setor externo e fiscal. Dados oficiais do SGS do "
            "Banco Central, atualizados a cada 6 horas.")
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Indicadores", HUB_URL)])
    lista = {
        "@context": "https://schema.org", "@type": "ItemList", "name": "Indicadores econômicos do Brasil",
        "url": HUB_URL, "numberOfItems": len(linhas),
        "itemListElement": [{"@type": "ListItem", "position": i, "url": l["url"], "name": l["nome"]}
                            for i, l in enumerate(linhas, 1)],
    }
    catalogo = {
        "@context": "https://schema.org", "@type": "DataCatalog", "@id": f"{HUB_URL}#catalogo",
        "name": "Observatório de Taxas — indicadores econômicos do Brasil", "url": HUB_URL, "inLanguage": "pt-BR",
        "publisher": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"},
        "dataset": [{"@id": f"{l['url']}#dataset"} for l in linhas],
    }
    jsonld = (jsonld_script(lista) + "\n" + jsonld_script(catalogo) + "\n"
              + jsonld_script({"@context": "https://schema.org", **crumb_ld}))
    blocos, grupo_atual = [], None
    for l in linhas:
        if l["grupo"] != grupo_atual:
            if grupo_atual is not None:
                blocos.append("</tbody></table></div>")
            grupo_atual = l["grupo"]
            gid = "g-" + "".join(c if c.isalnum() else "-" for c in grupo_atual.lower())
            blocos.append(f'<h2 class="grupo" id="{gid}">{e(grupo_atual)}</h2>'
                          '<div class="rolagem"><table class="tabela-hub"><thead><tr><th scope="col">Indicador</th>'
                          '<th scope="col">Valor</th><th scope="col">Referência</th><th scope="col">Produtor</th>'
                          '<th scope="col">SGS</th></tr></thead><tbody>')
        blocos.append(f'<tr><td><a href="{l["url"]}">{e(l["curto"])}</a></td><td class="num">{e(l["valor"])}</td>'
                      f'<td>{e(l["ref"])}</td><td>{e(l["produtor"])}</td><td>{l["codigo"]}</td></tr>')
    blocos.append("</tbody></table></div>")
    corpo = f"""<article>
<h1>Indicadores econômicos do Brasil hoje</h1>
<p class="lead">Os {len(linhas)} indicadores acompanhados pelo Observatório de Taxas, com o último valor publicado,
a data de referência e quem produz cada número. Todos vêm da API pública do SGS do Banco Central do Brasil e são
conferidos a cada 6 horas.</p>
<p class="mut">Cada indicador tem uma página com o que ele mede, os últimos 12 meses, gráfico, ficha técnica e a
série completa em JSON. A lista em formato de máquina está em <a href="{BASE_URL}/data/series.json">series.json</a>,
e assistentes de IA podem consultar as séries do Banco Central pelo <a href="{BASE_URL}/mcp/">servidor MCP</a>.</p>
{"".join(blocos)}
</article>"""
    return head(title, desc, HUB_URL, jsonld, crumb_html) + corpo + rodape(
        "IPCA, IPCA-15, INPC e desocupação produzidos pelo IBGE; IGP-M e IGP-DI pela FGV IBRE; CDI pela B3; "
        "as demais séries pelo Banco Central do Brasil")


def main() -> None:
    linhas = []
    gerados = 0
    for item in series_config():
        cod = item["codigo"]
        if cod not in PAGINAS:
            raise SystemExit(f"série {cod} sem entrada em PAGINAS (scripts/build_indicadores.py)")
        pts = load_history(cod)
        fechados, _ = completos(cod, pts)
        if not pts:
            print(f"[aviso] série {cod} sem histórico; página não gerada.")
            continue
        out = OUT_DIR / PAGINAS[cod]["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(pagina(cod, pts, item.get("grupo", "Outros")), encoding="utf-8")
        gerados += 1
        linhas.append({"codigo": cod, "url": url_pagina(cod), "nome": cat.SERIES[cod]["nome"],
                       "curto": PAGINAS[cod]["curto"], "grupo": item.get("grupo", "Outros"),
                       "valor": valor(cod, fechados[-1]["valor"]), "ref": data_ref(cod, fechados[-1]["dt"]),
                       "produtor": cat.SERIES[cod]["produtor"]["sigla"]})
    (OUT_DIR / "index.html").write_text(hub(linhas), encoding="utf-8")
    print(f"Geradas {gerados} páginas de indicador + hub em docs/indicadores/.")


if __name__ == "__main__":
    main()
