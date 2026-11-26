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


# ── CDI contra a inflação ─────────────────────────────────────────────────

REGRA_CDI = "leitura-cdi-ipca-v1"
BASE_URL = "https://observatoriodetaxas.tec.br"


def _compor(taxas: list[float]) -> float:
    f = 1.0
    for t in taxas:
        f *= 1 + t / 100
    return (f - 1) * 100


def leitura_cdi(cdi_mes: list[dict], ipca: list[dict], cdi_dia: list[dict], fim: str | None = None,
                meses: int = 12) -> dict:
    """Quanto o CDI acumulou em `meses` competências fechadas e quanto ficou
    acima ou abaixo do IPCA nas MESMAS competências.

    CDI: série mensal 4391 (acumulado no mês). O mês corrente está aberto
    quando a taxa diária (4389) já tem dias nele, e fica de fora. Taxa real:
    (1 + CDI) ÷ (1 + IPCA) − 1, a fórmula do comparador e do simulador
    (docs/calculos.js, rentabilidadeReal)."""
    c, i = por_mes(cdi_mes), por_mes(ipca)
    aberto = None
    if cdi_mes and cdi_dia and ym(cdi_mes[-1]["dt"]) == ym(cdi_dia[-1]["dt"]):
        aberto = ym(cdi_mes[-1]["dt"])
        c = {k: x for k, x in c.items() if k != aberto}
    comuns = sorted(set(c) & set(i))
    fim = fim or (comuns[-1] if comuns else None)
    if fim is None:
        raise ValueError("sem competência comum entre CDI e IPCA")
    janela = [soma_mes(fim, -k) for k in range(meses - 1, -1, -1)]
    lacunas = [(m, s) for m in janela for s, d in (("CDI", c), ("IPCA", i)) if m not in d]
    ini = janela[0]
    frases: list[str] = []
    cdi_ac = ipca_ac = real = None
    if not lacunas:
        cdi_ac, ipca_ac = _compor([c[m] for m in janela]), _compor([i[m] for m in janela])
        real = ((1 + cdi_ac / 100) / (1 + ipca_ac / 100) - 1) * 100
        lado = "acima" if real > 0 else "abaixo"
        frases.append(f"De {mes_txt(ini)} a {mes_txt(fim)} ({meses} competências fechadas), o CDI acumulou "
                      f"{pct(cdi_ac)} e o IPCA, {pct(ipca_ac)}.")
        frases.append(f"Descontada a inflação, o CDI ficou {fmt_num(abs(real))}% {lado} do IPCA no período "
                      f"(taxa real = (1 + CDI) ÷ (1 + IPCA) − 1). A diferença simples entre os acumulados seria "
                      f"{_pp(cdi_ac - ipca_ac)}, que não é a taxa real.")
    else:
        frases.append("Faltam competências para comparar os mesmos 12 meses: "
                      + ", ".join(f"{s} de {mes_txt(m)}" for m, s in lacunas)
                      + ". Sem elas, o acumulado e a taxa real não são calculados.")
    if aberto:
        frases.append(f"{mes_txt(aberto).capitalize()} ainda está em andamento na série mensal do CDI e não entra "
                      "na conta.")
    dia = cdi_dia[-1] if cdi_dia else None
    nota = ("Duas séries diferentes: a conta usa o CDI acumulado em cada mês (SGS 4391), que é o quanto rendeu "
            "100% do CDI naquele mês. A taxa DI diária anualizada (SGS 4389)")
    nota += (f", hoje em {pct(dia['valor'])} ao ano na data de {dia['dt']:%d/%m/%Y}," if dia else "")
    nota += (" é a taxa de um dia útil expressa em base de 252 dias úteis por ano, não o que se acumulou no "
             "período. Os índices não descontam imposto de renda nem custos de uma aplicação real.")
    proximo = soma_mes(fim, 1)
    links = {
        "comparador": f"{BASE_URL}/comparador/?de={ini}&ate={fim}&i=cdi,ipca&ver=pct",
        "simulador": f"{BASE_URL}/simulador-cdi/?valor=1000&percentual=100&de={ini}-01&ate={proximo}-01&modo=bruto",
        "simulador_de": f"{ini}-01", "simulador_ate": f"{proximo}-01",
    }
    linhas = [[mes_txt(m), c.get(m), i.get(m)] for m in janela]
    titulo = (f"CDI de {mes_txt(ini)} a {mes_txt(fim)}: {pct(cdi_ac)} no período, "
              f"{fmt_num(abs(real))}% {'acima' if real > 0 else 'abaixo'} da inflação" if real is not None else
              f"CDI até {mes_txt(fim)}: competências ausentes para comparar com o IPCA")
    return {
        "regra": REGRA_CDI, "codigo": 4391, "nome": "CDI", "competencia": fim, "inicio": ini, "fim": fim,
        "meses": meses, "mes_aberto": aberto, "cdi_acumulado": cdi_ac, "ipca_acumulado": ipca_ac,
        "taxa_real": real, "cdi_diario": ({"data": f"{dia['dt']:%Y-%m-%d}", "valor": dia["valor"]} if dia else None),
        "lacunas": [f"{s} {m}" for m, s in lacunas], "frases": frases, "nota": nota, "titulo": titulo,
        "links": links,
        "kpis": [["Período", f"{mes_txt(ini)} a {mes_txt(fim)}"], ["CDI acumulado", v_pct(cdi_ac)],
                 ["IPCA acumulado", v_pct(ipca_ac)], ["Acima ou abaixo da inflação (real)", v_pct(real, sinal=True)]],
        "tabela": {"cab": ["Competência", "CDI no mês (%)", "IPCA no mês (%)"], "linhas": linhas},
        "entradas": {**{f"cdi:{m}": c[m] for m in janela if m in c}, **{f"ipca:{m}": i[m] for m in janela if m in i}},
    }


def v_pct(x: float | None, sinal: bool = False) -> str:
    if x is None:
        return "—"
    s = ("+" if x > 0 else "−" if x < 0 else "") if sinal else ("−" if x < 0 else "")
    return f"{s}{fmt_num(abs(x))}%"


# ── Dólar PTAX ────────────────────────────────────────────────────────────

REGRA_PTAX = "leitura-ptax-semanal-v1"
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _semana(d) -> str:
    a, s, _ = d.isocalendar()
    return f"{a}-W{s:02d}"


def _segunda(semana: str):
    from datetime import date
    return date.fromisocalendar(int(semana[:4]), int(semana[6:]), 1)


def _var(novo: float, antigo: float) -> tuple[float, float]:
    return novo - antigo, (novo / antigo - 1) * 100


def _reais(x: float, sinal: bool = False) -> str:
    s = ("+" if x > 0 else "−" if x < 0 else "") if sinal else ""
    return f"{s}R$ {fmt_num(abs(x), 4)}"


def leitura_ptax(pts: list[dict], hoje, semana: str | None = None) -> dict:
    """Dólar PTAX de venda: variação contra a observação anterior e fechamento
    semanal.

    Semana = segunda a domingo (ISO). Uma semana está ENCERRADA quando `hoje`
    já chegou ao sábado dela: depois da sexta não sai PTAX. O fechamento é a
    última cotação disponível da semana (numa sexta de feriado, a de quinta)
    contra a última da semana anterior. A semana de `hoje`, ainda aberta, só
    entra como resultado PARCIAL. `hoje` vem da data da versão dos dados, para
    a leitura ser a mesma sempre que as entradas forem as mesmas."""
    from datetime import timedelta
    limite = hoje if not semana else min(hoje, _segunda(semana) + timedelta(days=6))
    obs = [(p["dt"].date(), p["valor"]) for p in pts if p["dt"].date() <= limite]
    por_sem: dict[str, list] = {}
    for d, x in obs:
        por_sem.setdefault(_semana(d), []).append((d, x))
    fechadas = sorted(s for s in por_sem if _segunda(s) + timedelta(days=5) <= hoje)
    sem = semana or (fechadas[-1] if fechadas else None)
    frases: list[str] = []
    kpis: list[list[str]] = []
    diaria = None
    if len(obs) >= 2:
        (d0, x0), (d1, x1) = obs[-2], obs[-1]
        dr, dp = _var(x1, x0)
        diaria = {"data": f"{d1:%Y-%m-%d}", "valor": x1, "data_anterior": f"{d0:%Y-%m-%d}", "valor_anterior": x0,
                  "variacao_reais": dr, "variacao_pct": dp}
        frases.append(f"Na cotação de {d1:%d/%m/%Y}, a PTAX de venda ficou em R$ {fmt_num(x1, 4)}, "
                      f"{_reais(dr, True)} ({v_pct(dp, True)}) em relação à observação anterior, de {d0:%d/%m/%Y} "
                      f"(R$ {fmt_num(x0, 4)}).")
        kpis += [["Última cotação", f"R$ {fmt_num(x1, 4)} em {d1:%d/%m/%Y}"],
                 ["Contra a observação anterior", f"{_reais(dr, True)} ({v_pct(dp, True)}) desde {d0:%d/%m/%Y}"]]
    fech = None
    entradas = {}
    if sem:
        anterior = _semana(_segunda(sem) - timedelta(days=7))
        dW, xW = por_sem[sem][-1]
        seg = _segunda(sem)
        sexta = seg + timedelta(days=4)
        if anterior in por_sem:
            dA, xA = por_sem[anterior][-1]
            dr, dp = _var(xW, xA)
            fech = {"semana": sem, "data": f"{dW:%Y-%m-%d}", "valor": xW, "semana_anterior": anterior,
                    "data_anterior": f"{dA:%Y-%m-%d}", "valor_anterior": xA, "variacao_reais": dr, "variacao_pct": dp}
            sentido = "subiu" if dr > 0 else "caiu" if dr < 0 else "ficou estável"
            frases.append(f"Na semana de {seg:%d/%m} a {sexta:%d/%m/%Y}, o dólar {sentido}: a última cotação, de "
                          f"{DIAS[dW.weekday()]} {dW:%d/%m/%Y}, foi R$ {fmt_num(xW, 4)}, {_reais(dr, True)} "
                          f"({v_pct(dp, True)}) contra a última da semana anterior, de {DIAS[dA.weekday()]} "
                          f"{dA:%d/%m/%Y} (R$ {fmt_num(xA, 4)}).")
            entradas = {f"{dW:%Y-%m-%d}": xW, f"{dA:%Y-%m-%d}": xA}
            kpis.append(["Fechamento da semana", f"R$ {fmt_num(xW, 4)} em {dW:%d/%m/%Y}"])
            kpis.append(["Contra a semana anterior", f"{_reais(dr, True)} ({v_pct(dp, True)}) desde {dA:%d/%m/%Y}"])
        else:
            frases.append(f"A semana de {seg:%d/%m} a {sexta:%d/%m/%Y} fechou em R$ {fmt_num(xW, 4)} "
                          f"({dW:%d/%m/%Y}), mas a semana anterior não tem cotação no histórico: sem base de "
                          "comparação para o fechamento semanal.")
            entradas = {f"{dW:%Y-%m-%d}": xW}
        if dW != sexta:
            frases.append(f"Não houve PTAX na sexta-feira, {sexta:%d/%m/%Y}; o fechamento usa a última cotação "
                          f"disponível da semana, de {DIAS[dW.weekday()]} {dW:%d/%m/%Y}.")
    else:
        frases.append("Ainda não há uma semana encerrada com cotações no histórico.")
    parcial = None
    aberta = _semana(hoje)
    if not semana and aberta in por_sem and aberta not in fechadas and fech:
        dP, xP = por_sem[aberta][-1]
        dr, dp = _var(xP, fech["valor"])
        parcial = {"semana": aberta, "data": f"{dP:%Y-%m-%d}", "valor": xP, "variacao_reais": dr, "variacao_pct": dp}
        frases.append(f"Resultado parcial da semana em andamento: até {dP:%d/%m/%Y}, R$ {fmt_num(xP, 4)}, "
                      f"{_reais(dr, True)} ({v_pct(dp, True)}) contra o fechamento da semana anterior. O resultado "
                      "da semana só fica definido depois da última cotação dela.")
        kpis.append(["Semana em andamento (parcial)", f"{_reais(dr, True)} ({v_pct(dp, True)}) até {dP:%d/%m/%Y}"])
    linhas = []
    if sem:
        anterior = _semana(_segunda(sem) - timedelta(days=7))
        for s_ in (anterior, sem):
            for d, x in por_sem.get(s_, []):
                linhas.append([f"{DIAS[d.weekday()]} {d:%d/%m/%Y}", "anterior" if s_ == anterior else "encerrada",
                               fmt_num(x, 4)])
    if fech:
        seg = _segunda(sem)
        titulo = (f"Dólar PTAX na semana de {seg:%d/%m} a {seg + timedelta(days=4):%d/%m/%Y}: "
                  f"R$ {fmt_num(fech['valor'], 4)}, {v_pct(fech['variacao_pct'], True)} na semana")
    elif sem:
        titulo = f"Dólar PTAX na semana {sem}: sem base de comparação"
    else:
        titulo = "Dólar PTAX: sem semana encerrada"
    return {
        "regra": REGRA_PTAX, "codigo": 1, "nome": "Dólar PTAX (venda)", "competencia": sem, "hoje": f"{hoje:%Y-%m-%d}",
        "diaria": diaria, "fechamento": fech, "parcial": parcial, "frases": frases,
        "nota": ("A PTAX é a taxa de referência calculada pelo Banco Central em cada dia útil. Variação em reais = "
                 "cotação nova − cotação de comparação; em percentual = cotação nova ÷ cotação de comparação − 1. "
                 "A explicação mostra só o movimento da cotação: atribuí-lo a juros, fluxo ou notícias exigiria "
                 "outros dados."),
        "titulo": titulo, "kpis": kpis,
        "tabela": {"cab": ["Dia", "Semana", "PTAX de venda (R$)"], "linhas": linhas},
        "entradas": entradas,
    }
