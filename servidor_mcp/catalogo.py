"""
catalogo.py — Metadados de cada série exposta pelo MCP.

Uma entrada por código SGS de config.yml. Para cada série: produtor (quem
calcula o indicador), distribuidor (o SGS do Banco Central), unidade,
periodicidade, natureza (o que o número representa) e situação de
licenciamento.

Licenciamento (ver LICENSE-DADOS.md e servidor_mcp/README.md):
  - séries do Banco Central: ODbL 1.0, publicadas no Portal de Dados Abertos
    do BCB -> expostas;
  - séries do IBGE e da FGV IBRE: sem autorização clara de redistribuição
    automatizada -> SUSPENSAS por padrão. Só são expostas se a variável de
    ambiente OBS_MCP_LIBERAR_RESTRITAS=1 estiver definida, depois de o
    proprietário confirmar os termos com o produtor.
"""

from __future__ import annotations

import os
import re
import unicodedata

SITE = "https://observatoriodetaxas.tec.br"
SGS_API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
SGS_PORTAL = "https://www3.bcb.gov.br/sgspub/"

BCB = {"sigla": "BCB", "nome": "Banco Central do Brasil", "url": "https://www.bcb.gov.br/"}
IBGE = {"sigla": "IBGE", "nome": "Instituto Brasileiro de Geografia e Estatística",
        "url": "https://www.ibge.gov.br/"}
FGV = {"sigla": "FGV IBRE", "nome": "Instituto Brasileiro de Economia da Fundação Getulio Vargas",
       "url": "https://portalibre.fgv.br/igp"}
DISTRIBUIDOR = {"nome": "SGS — Sistema Gerenciador de Séries Temporais do Banco Central do Brasil",
                "url": SGS_PORTAL}

LIC_ODBL = {"situacao": "exposta", "licenca": "ODbL 1.0",
            "licenca_url": "https://opendatacommons.org/licenses/odbl/1-0/",
            "atribuicao": "Fonte: Banco Central do Brasil (SGS). Dados via Observatório de Taxas."}
LIC_RESTRITA = {"situacao": "suspensa",
                "licenca": "termos do produtor (não relicenciada)",
                "licenca_url": "https://github.com/iosbilario/observatorio-taxas/blob/main/LICENSE-DADOS.md",
                "motivo": ("Redistribuição automatizada ainda não confirmada com o produtor. "
                           "A série continua disponível no site do produtor e no Observatório.")}

# natureza:
#   variacao_mensal  -> % no mês; acumula por composição (reajuste/correção)
#   acumulado_12m    -> % acumulado em 12 meses (já composto pelo produtor)
#   taxa_anual       -> % ao ano (nível de taxa)
#   taxa_periodo     -> % no período que começa na data de referência
#   cotacao          -> R$ por unidade de moeda estrangeira
#   indice           -> número-índice
#   taxa_nivel       -> % de uma população (nível)
SERIES: dict[int, dict] = {
    432: dict(nome="Meta Selic", unidade="% a.a.", periodicidade="diária (pontos nas datas publicadas pelo SGS)",
              natureza="taxa_anual", produtor=BCB, apelidos=["selic", "meta-selic", "selic-meta"], ancora="#selic"),
    1178: dict(nome="Selic anualizada (base 252)", unidade="% a.a.", periodicidade="diária (dias úteis)",
               natureza="taxa_anual", produtor=BCB, apelidos=["selic-efetiva", "selic-anualizada", "selic-diaria"]),
    4390: dict(nome="Selic acumulada no mês", unidade="% no mês", periodicidade="mensal",
               natureza="variacao_mensal", produtor=BCB, apelidos=["selic-mensal", "selic-mes", "selic-acumulada"]),
    226: dict(nome="TR — Taxa Referencial", unidade="% no período", periodicidade="diária (período iniciado na data)",
              natureza="taxa_periodo", produtor=BCB, apelidos=["tr", "taxa-referencial"]),
    25: dict(nome="Poupança (depósitos até 03/05/2012) — rentabilidade", unidade="% no período",
             periodicidade="diária (período iniciado na data)", natureza="taxa_periodo", produtor=BCB,
             apelidos=["poupanca", "poupanca-antiga"]),
    433: dict(nome="IPCA — variação mensal", unidade="% no mês", periodicidade="mensal",
              natureza="variacao_mensal", produtor=IBGE, apelidos=["ipca", "ipca-mensal"], chave_reajuste="ipca"),
    13522: dict(nome="IPCA — acumulado em 12 meses", unidade="% em 12 meses", periodicidade="mensal",
                natureza="acumulado_12m", produtor=IBGE, apelidos=["ipca-12m", "ipca-12-meses"], ancora="#ipca"),
    188: dict(nome="INPC — variação mensal", unidade="% no mês", periodicidade="mensal",
              natureza="variacao_mensal", produtor=IBGE, apelidos=["inpc"], chave_reajuste="inpc"),
    189: dict(nome="IGP-M — variação mensal", unidade="% no mês", periodicidade="mensal",
              natureza="variacao_mensal", produtor=FGV, apelidos=["igpm", "igp-m"], chave_reajuste="igpm"),
    190: dict(nome="IGP-DI — variação mensal", unidade="% no mês", periodicidade="mensal",
              natureza="variacao_mensal", produtor=FGV, apelidos=["igpdi", "igp-di"], chave_reajuste="igpdi"),
    1: dict(nome="Dólar (USD/BRL) — venda", unidade="R$ por US$", periodicidade="diária (dias úteis)",
            natureza="cotacao", produtor=BCB, apelidos=["dolar", "usd", "dolar-venda"], ancora="#dolar"),
    10813: dict(nome="Dólar (USD/BRL) — compra", unidade="R$ por US$", periodicidade="diária (dias úteis)",
                natureza="cotacao", produtor=BCB, apelidos=["dolar-compra", "usd-compra"]),
    21619: dict(nome="Euro (EUR/BRL) — venda", unidade="R$ por €", periodicidade="diária (dias úteis)",
                natureza="cotacao", produtor=BCB, apelidos=["euro", "eur"]),
    24363: dict(nome="IBC-Br — índice de atividade econômica", unidade="número-índice", periodicidade="mensal",
                natureza="indice", produtor=BCB, apelidos=["ibc-br", "ibcbr"]),
    24369: dict(nome="Taxa de desocupação (PNAD Contínua)", unidade="% da força de trabalho",
                periodicidade="mensal (trimestre móvel)", natureza="taxa_nivel", produtor=IBGE,
                apelidos=["desemprego", "desocupacao", "pnad"], ancora="#desemprego"),
}


def restritas_liberadas() -> bool:
    return os.environ.get("OBS_MCP_LIBERAR_RESTRITAS", "") == "1"


def licenca(codigo: int) -> dict:
    if SERIES[codigo]["produtor"] is BCB:
        return dict(LIC_ODBL)
    if restritas_liberadas():
        return {**LIC_RESTRITA, "situacao": "exposta (liberada pelo operador)",
                "atribuicao": f"Fonte: {SERIES[codigo]['produtor']['sigla']}, via SGS/Banco Central do Brasil."}
    return dict(LIC_RESTRITA)


def exposta(codigo: int) -> bool:
    return licenca(codigo)["situacao"].startswith("exposta")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[\s_]+", "-", s)


APELIDOS = {_norm(a): cod for cod, m in SERIES.items() for a in m["apelidos"]}


def resolver(indicador: str | int) -> int | None:
    """Código SGS a partir de código numérico ou apelido. None se desconhecido."""
    s = _norm(str(indicador)).removeprefix("sgs-")
    if s.isdigit() and int(s) in SERIES:
        return int(s)
    return APELIDOS.get(s)


def lista_publica() -> list[dict]:
    return [{"codigo_sgs": c, "nome": m["nome"], "apelidos": m["apelidos"], "unidade": m["unidade"],
             "periodicidade": m["periodicidade"], "produtor": m["produtor"]["sigla"],
             "situacao": licenca(c)["situacao"]} for c, m in SERIES.items()]
