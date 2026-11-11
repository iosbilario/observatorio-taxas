"""
fontes.py — Procedência dos índices de preços usados em reajuste e correção.

O Observatório coleta TODOS os números na API pública do SGS (Sistema
Gerenciador de Séries Temporais) do Banco Central do Brasil. O SGS, porém,
REDISTRIBUI índices que outros órgãos produzem: IPCA e INPC são do IBGE;
IGP-M e IGP-DI são da FGV IBRE. As páginas devem dizer as duas coisas
(quem produz e de onde o Observatório tirou o dado), sem atribuir ao BACEN a
autoria de um índice que ele não calcula.

Fonte única para build_pages.py, build_correcao.py e os testes.
"""

from __future__ import annotations

IBGE = {
    "sigla": "IBGE",
    "do": "do IBGE",
    "pelo": "pelo IBGE",
    "nome": "Instituto Brasileiro de Geografia e Estatística (IBGE)",
}
FGV_IBRE = {
    "sigla": "FGV IBRE",
    "do": "da FGV IBRE",
    "pelo": "pela FGV IBRE",
    "nome": "Instituto Brasileiro de Economia da Fundação Getulio Vargas (FGV IBRE)",
    "url": "https://portalibre.fgv.br/igp",
}

# codigo SGS -> procedência e conceito da série.
FONTES: dict[int, dict] = {
    433: {
        "sigla": "IPCA",
        "nome_completo": "Índice Nacional de Preços ao Consumidor Amplo",
        "produtor": IBGE,
        "produtor_url": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html",
    },
    188: {
        "sigla": "INPC",
        "nome_completo": "Índice Nacional de Preços ao Consumidor",
        "produtor": IBGE,
        "produtor_url": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9258-indice-nacional-de-precos-ao-consumidor.html",
    },
    189: {
        "sigla": "IGP-M",
        "nome_completo": "Índice Geral de Preços – Mercado",
        "produtor": FGV_IBRE,
        "produtor_url": FGV_IBRE["url"],
    },
    190: {
        "sigla": "IGP-DI",
        "nome_completo": "Índice Geral de Preços – Disponibilidade Interna",
        "produtor": FGV_IBRE,
        "produtor_url": FGV_IBRE["url"],
    },
}

UNIDADE_MENSAL = "variação percentual no mês (%)"
SGSPUB_URL = "https://www3.bcb.gov.br/sgspub/"

# Rodapé comum às páginas geradas (reajuste e correção).
LINHA_PROCEDENCIA = (
    "Dados: IPCA e INPC produzidos pelo IBGE; IGP-M e IGP-DI produzidos pela FGV IBRE. "
    'O Observatório obtém as séries na <a href="' + SGSPUB_URL + '">API pública do SGS</a> '
    "do Banco Central do Brasil, que as redistribui, e calcula acumulados e fatores a partir "
    "das variações mensais publicadas."
)


def sgs_api_url(codigo: int) -> str:
    """URL pública da série no SGS (JSON), conferível por qualquer pessoa."""
    return f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
