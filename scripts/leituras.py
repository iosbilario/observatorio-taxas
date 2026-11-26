"""
leituras.py — Leituras de uma divulgação, calculadas só com os dados do Observatório.

Funções puras: recebem pontos [{"dt": datetime, "valor": float}] (o formato de
build_pages.load_history) e devolvem um dicionário com os números, a tabela que
permite refazer a conta e o texto. Não leem arquivo nem rede, para os testes
usarem dados pequenos e controlados.

As contas guardam a precisão de float até o fim; só a exibição arredonda
(fmt_num). A explicação é sempre ARITMÉTICA (como a janela de meses mudou); a
nota econômica deixa claro o que exigiria outros dados.

Cada leitura leva o nome da regra que a produziu (REGRA_*). Quando a regra
mudar, troque o nome: as leituras já arquivadas em data/publicacoes.json
guardam o resultado da regra antiga e continuam reproduzíveis.
"""

from __future__ import annotations

from datetime import datetime

from build_pages import _pp, acumulado, fmt_num, frase_troca_da_janela, mes_ano

REGRA_MENSAL = "leitura-mensal-v1"

NOTA_ECONOMICA = {
    433: ("Essa explicação é aritmética: mostra como a troca de meses move a janela de 12 meses. Ela não diz quais "
          "preços pressionaram a inflação. Atribuir o movimento a alimentos, combustíveis ou serviços exigiria os "
          "dados de grupos e itens do IPCA, publicados pelo IBGE e não coletados pelo Observatório."),
}


def ym(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def dt_ym(s: str) -> datetime:
    return datetime(int(s[:4]), int(s[5:7]), 1)


def soma_mes(s: str, n: int) -> str:
    t = int(s[:4]) * 12 + int(s[5:7]) - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def mes_txt(s: str) -> str:
    return mes_ano(dt_ym(s))


def por_mes(pts: list[dict]) -> dict[str, float]:
    return {ym(p["dt"]): p["valor"] for p in pts}


def pct(v: float) -> str:
    return f"{fmt_num(v)}%"


def _direcao(novo: float, antigo: float) -> str | None:
    if abs(novo - antigo) < 0.005:
        return None
    return "acelerou" if novo > antigo else "desacelerou"


def leitura_mensal(codigo: int, nome: str, pts: list[dict], ref: str | None = None) -> dict:
    """Leitura de uma competência de um índice de variação mensal.

    Compara a taxa do mês com a do mês anterior e o acumulado de 12 meses com o
    do mês anterior, e explica a mudança do acumulado pela troca de meses: a
    janela atual (ref-11 … ref) e a anterior (ref-12 … ref-1) só diferem pelo
    mês que entrou (ref) e pelo que saiu (ref-12). Se faltar alguma das 13
    competências, nomeia a lacuna e não calcula o acumulado que dependeria dela.
    """
    m = por_mes(pts)
    ref = ref or max(m)
    ant, saiu = soma_mes(ref, -1), soma_mes(ref, -12)
    janela = [soma_mes(ref, -k) for k in range(11, -1, -1)]
    janela_ant = [soma_mes(ref, -k) for k in range(12, 0, -1)]
    necessarias = [saiu] + janela
    lacunas = [c for c in necessarias if c not in m]

    def ac_de(js: list[str]) -> float | None:
        return acumulado([{"valor": m[c]} for c in js]) if all(c in m for c in js) else None

    ac, ac_ant = ac_de(janela), ac_de(janela_ant)
    mensal, mensal_ant, saiu_v = m.get(ref), m.get(ant), m.get(saiu)
    frases: list[str] = []
    dir_mensal = None
    if mensal is not None and mensal_ant is not None:
        dir_mensal = _direcao(mensal, mensal_ant)
        if dir_mensal is None:
            frases.append(f"A taxa mensal do {nome} ficou praticamente estável: {pct(mensal_ant)} em "
                          f"{mes_txt(ant)} e {pct(mensal)} em {mes_txt(ref)}.")
        else:
            frases.append(f"A taxa mensal do {nome} {dir_mensal} de {pct(mensal_ant)} em {mes_txt(ant)} para "
                          f"{pct(mensal)} em {mes_txt(ref)}, uma diferença de {_pp(mensal - mensal_ant)}.")
    sobe = None
    if ac is not None and ac_ant is not None:
        frase, sobe = frase_troca_da_janela(ac, ac_ant, dt_ym(ref), mensal, saiu_v)
        frases.append(frase)
        mensal_cai = dir_mensal == "desacelerou"
        if (mensal_cai and sobe) or (dir_mensal == "acelerou" and sobe is False):
            compara = "menor" if mensal_cai else "maior"
            contra = "maior" if mensal_cai else "menor"
            frases.append(f"Os dois movimentos não se contradizem. A taxa mensal compara {mes_txt(ref)} com "
                          f"{mes_txt(ant)}. O acumulado não depende de {mes_txt(ant)}, que está nas duas janelas: "
                          f"ele só muda pelo mês que entrou ({mes_txt(ref)}, {pct(mensal)}) e pelo que saiu "
                          f"({mes_txt(saiu)}, {pct(saiu_v)}). Como {pct(mensal)} é {compara} que {pct(mensal_ant)} "
                          f"e {contra} que {pct(saiu_v)}, a taxa mensal "
                          f"{'desacelera' if mensal_cai else 'acelera'} e o acumulado "
                          f"{'sobe' if sobe else 'cai'} ao mesmo tempo.")
    if lacunas:
        frases.append("Faltam no histórico do Observatório as competências de "
                      + ", ".join(mes_txt(c) for c in lacunas)
                      + ". Sem elas, o acumulado de 12 meses que dependeria delas não é calculado, para não "
                        "apresentar uma conta parcial como se cobrisse 12 meses.")

    linhas = []
    for c in necessarias:
        papel = "entrou na janela" if c == ref else "saiu da janela" if c == saiu else ""
        linhas.append({"competencia": c, "valor": m.get(c), "janela_atual": c in janela,
                       "janela_anterior": c in janela_ant, "papel": papel})

    if mensal is None:
        titulo = f"{nome} de {mes_txt(ref)}: competência ausente no histórico"
    else:
        partes = [f"{nome} de {mes_txt(ref)}: taxa mensal de {pct(mensal)}"]
        if dir_mensal:
            partes[0] = (f"{nome} de {mes_txt(ref)}: taxa mensal "
                         f"{'desacelera' if dir_mensal == 'desacelerou' else 'acelera'} para {pct(mensal)}")
        if ac is not None:
            verbo = "fica estável em" if sobe is None else "sobe para" if sobe else "cai para"
            if ac_ant is None:
                verbo = "em"
            partes.append(f"acumulado em 12 meses {verbo} {pct(ac)}")
        titulo = " e ".join(partes)

    return {
        "regra": REGRA_MENSAL, "codigo": codigo, "nome": nome, "competencia": ref,
        "anterior": ant, "saiu": saiu, "mensal": mensal, "mensal_anterior": mensal_ant, "saiu_valor": saiu_v,
        "acumulado_12m": ac, "acumulado_12m_anterior": ac_ant,
        "diferenca_pp": (ac - ac_ant) if ac is not None and ac_ant is not None else None,
        "janela": [janela[0], janela[-1]], "janela_anterior": [janela_ant[0], janela_ant[-1]],
        "lacunas": lacunas, "frases": frases, "nota": NOTA_ECONOMICA.get(codigo, ""),
        "titulo": titulo, "linhas": linhas,
        "entradas": {c: m[c] for c in necessarias if c in m},
    }
