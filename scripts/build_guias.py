#!/usr/bin/env python3
"""
build_guias.py — Guias editoriais em /guias/.

Seis guias escritos para quem usa os números do site (reajuste de aluguel,
diferenças entre os índices de inflação, cálculo do acumulado, dólar PTAX,
Selic e correção monetária) e o hub /guias/. O texto é fixo; os números de
exemplo saem de data/ a cada execução, então os guias acompanham a coleta e
nunca mostram um valor velho.

Os guias são HTML estático, sem JavaScript. O sitemap é escrito por
render_index.py, que roda depois deste script; o menu e o rodapé entram por
sync_nav.py.

    python scripts/build_guias.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_correcao import faq_html, faq_ld  # noqa: E402
from build_ferramentas import e, head  # noqa: E402
from build_indicadores import completos, load_history  # noqa: E402
from build_pages import acumulado, aplica_fator, fator_txt, fmt_num, jsonld_script, mes_ano, migalhas  # noqa: E402

DOCS = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
URL_HUB = f"{BASE_URL}/guias/"

GUIA_CSS = """
.guia p{color:var(--papel-70);line-height:1.65;margin:0 0 .9rem}
.guia p b{color:var(--papel)}
.guia h2{margin-top:1.6rem}
.guia ol,.guia ul{color:var(--papel-70);line-height:1.6;padding-left:1.3rem;margin:0 0 1rem}
.guia li{margin:.3rem 0}
.guia .nota{font-size:.86rem;color:var(--papel-45)}
.lista-guias a{display:block;border:1px solid var(--linha);border-radius:10px;padding:.9rem 1rem;margin:.6rem 0;border-bottom:1px solid var(--linha)}
.lista-guias a:hover{border-color:color-mix(in srgb,var(--carimbo) 50%,transparent)}
.lista-guias b{display:block;color:var(--papel);font-family:"Fraunces",Georgia,serif;font-size:1.05rem}
.lista-guias span{display:block;color:var(--papel-70);font-size:.9rem;margin-top:.2rem}
"""

INDICES = (("IPCA", 433, "IBGE"), ("INPC", 188, "IBGE"), ("IGP-M", 189, "FGV IBRE"), ("IGP-DI", 190, "FGV IBRE"))


def pct(v: float, casas: int = 2) -> str:
    return f"{fmt_num(v, casas)}%"


def reais(v: float) -> str:
    return f"R$ {fmt_num(v, 2)}"


def dia(d) -> str:
    return d.strftime("%d/%m/%Y")


# ── números de data/ ──────────────────────────────────────────────────────

def indice(codigo: int) -> dict:
    """Último mês, variação do mês e acumulado de 12 meses de um índice mensal."""
    pts, _ = completos(codigo, load_history(codigo))
    janela = pts[-12:]
    return {"ref": janela[-1]["dt"], "ini": janela[0]["dt"], "mensal": janela[-1]["valor"],
            "ac": acumulado(janela), "janela": janela}


def meta_selic() -> dict:
    pts = load_history(432)
    atual = pts[-1]["valor"]
    desde = pts[-1]["dt"]
    for p in reversed(pts):
        if p["valor"] != atual:
            break
        desde = p["dt"]
    anterior = next((p["valor"] for p in reversed(pts) if p["dt"] < desde), None)
    return {"valor": atual, "desde": desde, "anterior": anterior, "ref": pts[-1]["dt"]}


def selic_mes() -> dict:
    pts, _ = completos(4390, load_history(4390))
    janela = pts[-12:]
    return {"ref": janela[-1]["dt"], "ini": janela[0]["dt"], "mensal": janela[-1]["valor"],
            "ac": acumulado(janela)}


def ptax() -> dict:
    venda, compra = load_history(1), load_history(10813)
    ult = venda[-1]
    ano = [p for p in venda if p["dt"].year == ult["dt"].year]
    mx = max(ano, key=lambda p: p["valor"])
    mn = min(ano, key=lambda p: p["valor"])
    comp = next((p for p in reversed(compra) if p["dt"] == ult["dt"]), compra[-1])
    return {"venda": ult["valor"], "compra": comp["valor"], "dt": ult["dt"], "max": mx, "min": mn,
            "inicio_ano": ano[0], "dias_ano": len(ano)}


# ── página ────────────────────────────────────────────────────────────────

RODAPE = """
</main>
<footer>Guias informativos do Observatório de Taxas. Os números de exemplo vêm das séries do
<a href="https://www3.bcb.gov.br/sgspub/">SGS do Banco Central</a> e são atualizados a cada coleta. IPCA e INPC são
produzidos pelo IBGE; IGP-M e IGP-DI pela FGV IBRE. Não é recomendação financeira nem orientação jurídica: confira o
índice e a regra previstos no seu contrato.
</footer>
</div></body></html>
"""


def pagina(slug: str, titulo: str, h1: str, desc: str, corpo: str, perguntas: list[tuple[str, str]],
           atualizado: date) -> str:
    url = f"{URL_HUB}{slug}/"
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Guias", URL_HUB), (h1, url)])
    artigo = {
        "@context": "https://schema.org", "@type": "Article", "headline": h1, "description": desc,
        "url": url, "inLanguage": "pt-BR", "dateModified": atualizado.isoformat(),
        "author": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"},
        "publisher": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"},
        "isPartOf": {"@id": f"{BASE_URL}/#website"},
    }
    jsonld = (jsonld_script(artigo) + "\n" + faq_ld(url, titulo, crumb_ld, perguntas) + "\n"
              + jsonld_script({"@context": "https://schema.org", **crumb_ld}))
    return (head(titulo, desc, url, jsonld, crumb_html, []).replace("</style>", GUIA_CSS + "</style>", 1)
            + f"""
<article class="guia">
<header>
<h1>{e(h1)}</h1>
<p class="mut">Números de exemplo atualizados em <time datetime="{atualizado.isoformat()}">{dia(atualizado)}</time>
com as séries do Banco Central.</p>
</header>
{corpo}
{faq_html(perguntas)}
<p class="mut"><a href="../">Todos os guias</a></p>
</article>
""" + RODAPE)


# ── guias ─────────────────────────────────────────────────────────────────

def guia_aluguel(ix: dict) -> tuple:
    g, i = ix["IGP-M"], ix["IPCA"]
    novo_g, novo_i = aplica_fator(2000, 1 + g["ac"] / 100), aplica_fator(2000, 1 + i["ac"] / 100)
    ref = mes_ano(g["ref"])
    corpo = f"""
<p class="resposta">Para reajustar um aluguel, multiplique o valor atual por (1 + acumulado do índice em 12 meses
÷ 100). Com o IGP-M acumulado até {ref}, de <b>{pct(g['ac'])}</b>, um aluguel de R$ 2.000,00 passa a
<b>{reais(novo_g)}</b>.</p>

<h2>1. Ache o índice e a data no contrato</h2>
<p>O índice de reajuste é escolhido pelas partes e fica escrito no contrato. O IGP-M foi por muitos anos o mais
comum em aluguel residencial, e desde 2021 muitos contratos novos passaram a usar o IPCA. O reajuste é anual: a
lei que trata da correção de contratos (Lei 10.192/2001) não permite reajuste com periodicidade menor que um ano.
Anote o índice e o mês de aniversário do contrato.</p>

<h2>2. Pegue o acumulado de 12 meses certo</h2>
<p>O acumulado usado é o dos 12 meses mais recentes já divulgados na data do aniversário. Como o índice de um mês
sai no fim daquele mês ou no começo do seguinte, o costume é usar o acumulado até o mês anterior ao aniversário.
Um contrato que faz aniversário em {mes_seguinte(g['ref'])} usa, em geral, o acumulado até {ref}. Se o contrato
disser outra coisa, vale o contrato.</p>

<h2>3. Faça a conta</h2>
<ol>
<li>Transforme o acumulado em fator: {pct(g['ac'])} vira {fator_txt(1 + g['ac'] / 100)}.</li>
<li>Multiplique o aluguel atual pelo fator: R$ 2.000,00 × {fator_txt(1 + g['ac'] / 100)} = {reais(novo_g)}.</li>
<li>Arredonde para centavos só no final.</li>
</ol>
<p>A página de cada mês em <a href="../../reajuste/">Reajuste de contratos</a> já traz o fator, a tabela dos 12
meses e uma calculadora.</p>

<h2>IGP-M ou IPCA: quanto muda</h2>
<p>No mesmo mês, o IPCA acumulado em 12 meses foi de {pct(i['ac'])}. O mesmo aluguel de R$ 2.000,00 iria a
{reais(novo_i)} pelo IPCA, {reais(abs(novo_g - novo_i))} {'a mais' if novo_g > novo_i else 'a menos'} pelo
IGP-M. A diferença muda de mês para mês: o IGP-M acompanha preços no atacado e oscila mais. O guia
<a href="../ipca-igpm-inpc-igpdi/">IPCA, INPC, IGP-M e IGP-DI</a> explica por quê.</p>

<h2>E se o acumulado for negativo?</h2>
<p>O IGP-M já fechou 12 meses no negativo, como entre 2023 e 2024. Nesse caso o efeito depende da cláusula: há
contratos que aplicam a redução e há contratos que preveem só a manutenção do valor. Se o contrato não trata
disso, o caminho é negociar e, se preciso, buscar orientação jurídica.</p>
"""
    perguntas = [
        ("Como calcular o reajuste do aluguel?",
         f"Multiplique o aluguel atual por (1 + acumulado de 12 meses do índice do contrato ÷ 100). Com o IGP-M "
         f"acumulado até {ref}, de {pct(g['ac'])}, um aluguel de R$ 2.000,00 passa a {reais(novo_g)}."),
        ("Qual mês do índice devo usar?",
         "Em geral, o acumulado de 12 meses até o mês anterior ao aniversário do contrato, que é o mais recente já "
         "divulgado. Se o contrato definir outra defasagem, vale o contrato."),
        ("O reajuste pode ser feito em menos de um ano?",
         "Não. A Lei 10.192/2001 não permite reajuste de contrato com periodicidade inferior a um ano."),
    ]
    return ("reajuste-de-aluguel", "Como calcular o reajuste do aluguel pelo IGP-M ou IPCA, passo a passo",
            "Como calcular o reajuste do aluguel",
            f"Passo a passo do reajuste de aluguel: qual índice e qual mês usar, como transformar o acumulado em "
            f"fator e o que fazer se ele for negativo. Exemplo com o IGP-M até {ref}: {pct(g['ac'])}.",
            corpo, perguntas)


def mes_seguinte(dt) -> str:
    n = dt.year * 12 + dt.month
    return f"{['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'][n % 12]}"


def guia_indices(ix: dict) -> tuple:
    linhas = "".join(
        f"<tr><td>{n}</td><td>{prod}</td><td>{mes_ano(ix[n]['ref'])}</td><td>{pct(ix[n]['mensal'])}</td>"
        f"<td>{pct(ix[n]['ac'])}</td></tr>"
        for n, _, prod in INDICES)
    maior = max(INDICES, key=lambda t: ix[t[0]]["ac"])[0]
    menor = min(INDICES, key=lambda t: ix[t[0]]["ac"])[0]
    corpo = f"""
<p class="resposta">IPCA e INPC medem a inflação ao consumidor e são do IBGE. IGP-M e IGP-DI são da FGV IBRE e
misturam preços ao produtor, ao consumidor e da construção. Hoje o maior acumulado em 12 meses é o do
<b>{maior}</b> e o menor é o do <b>{menor}</b>.</p>

<table><caption>Último mês disponível de cada índice e acumulado em 12 meses</caption>
<thead><tr><th scope="col">Índice</th><th scope="col">Produtor</th><th scope="col">Mês</th><th scope="col">No mês</th><th scope="col">12 meses</th></tr></thead>
<tbody>{linhas}</tbody></table>

<h2>IPCA: a inflação oficial</h2>
<p>O IPCA mede a variação de preços para famílias com renda de 1 a 40 salários mínimos nas principais regiões
metropolitanas. É o índice da meta de inflação perseguida pelo Banco Central e o mais usado em contratos novos de
serviços e de aluguel.</p>

<h2>INPC: a inflação das famílias de menor renda</h2>
<p>O INPC usa a mesma pesquisa de preços do IPCA, mas pondera pelos gastos de famílias com renda de 1 a 5
salários mínimos. Por isso pesa mais em alimentação e menos em serviços. É a referência comum em dissídios e no
reajuste dos benefícios do INSS acima do salário mínimo.</p>

<h2>IGP-M e IGP-DI: preços do atacado também</h2>
<p>Os dois têm a mesma composição: 60% de preços ao produtor (IPA), 30% ao consumidor (IPC) e 10% da construção
(INCC). Como o atacado inclui matérias-primas cotadas em dólar, como minério, petróleo e grãos, os IGPs reagem
ao câmbio e às commodities e oscilam mais que o IPCA. A diferença entre eles é o período de coleta: o IGP-M
coleta do dia 21 do mês anterior ao dia 20 do mês de referência, e o IGP-DI coleta o mês cheio.</p>

<h2>Qual usar</h2>
<ul>
<li><b>Contrato:</b> o índice que estiver escrito nele. Trocar de índice exige acordo entre as partes.</li>
<li><b>Comparar com a inflação do dia a dia:</b> IPCA.</li>
<li><b>Salários e benefícios:</b> o INPC é a referência mais comum.</li>
<li><b>Custos de empresa ligados a matéria-prima:</b> os IGPs captam melhor o atacado.</li>
</ul>
<p>Para ver os quatro lado a lado num período qualquer, use a <a href="../../correcao/">correção monetária</a> ou
as páginas de <a href="../../reajuste/">reajuste</a>.</p>
"""
    perguntas = [
        ("Qual a diferença entre IPCA e IGP-M?",
         "O IPCA, do IBGE, mede só preços ao consumidor. O IGP-M, da FGV IBRE, mistura preços ao produtor (60%), ao "
         "consumidor (30%) e da construção (10%), e por isso reage mais ao dólar e às commodities."),
        ("Qual a diferença entre IPCA e INPC?",
         "Os dois usam a mesma coleta de preços do IBGE. O IPCA pondera pelos gastos de famílias com renda de 1 a 40 "
         "salários mínimos; o INPC, de 1 a 5 salários mínimos."),
        ("Qual a diferença entre IGP-M e IGP-DI?",
         "A composição é a mesma. Muda o período de coleta: o IGP-M vai do dia 21 do mês anterior ao dia 20 do mês de "
         "referência; o IGP-DI cobre o mês cheio."),
    ]
    return ("ipca-igpm-inpc-igpdi", "IPCA, INPC, IGP-M e IGP-DI: diferenças e qual usar",
            "IPCA, INPC, IGP-M e IGP-DI: diferenças e qual usar",
            "Quem produz cada índice de inflação, o que cada um mede, por que o IGP-M oscila mais e qual usar em "
            "contratos, salários e comparações. Tabela com o acumulado atual dos quatro.",
            corpo, perguntas)


def guia_acumulado(ix: dict) -> tuple:
    i = ix["IPCA"]
    tres = i["janela"][-3:]
    fator = 1.0
    passos = []
    for p in tres:
        fator *= 1 + p["valor"] / 100
        passos.append(f"<li>{mes_ano(p['dt']).capitalize()}: {pct(p['valor'])} → fator acumulado "
                      f"{fator_txt(fator)}</li>")
    soma = sum(p["valor"] for p in tres)
    corpo = f"""
<p class="resposta">O acumulado de vários meses é a <b>multiplicação</b> dos fatores de cada mês, menos 1. Não é a
soma das taxas. Em 12 meses: acumulado = (1 + t₁ ÷ 100) × (1 + t₂ ÷ 100) × … × (1 + t₁₂ ÷ 100) − 1.</p>

<h2>Exemplo com o IPCA</h2>
<p>Os três últimos meses do IPCA disponíveis no Observatório:</p>
<ol>{''.join(passos)}</ol>
<p>O acumulado dos três meses é {pct((fator - 1) * 100)}. A soma simples daria {pct(soma)}. A diferença é
pequena em três meses de inflação baixa, mas cresce com o tempo e com taxas maiores, porque cada mês incide
sobre o valor já corrigido pelos anteriores.</p>

<h2>Fator e acumulado são a mesma informação</h2>
<p>O fator é 1 + acumulado ÷ 100. Um acumulado de {pct(i['ac'])} é um fator de {fator_txt(1 + i['ac'] / 100)}.
Para corrigir ou reajustar um valor, basta multiplicá-lo pelo fator.</p>

<h2>Por que o Observatório pode diferir do número oficial em centésimos</h2>
<p>O IBGE e a FGV IBRE calculam o acumulado com números-índice, que têm várias casas decimais. A série mensal
publicada no SGS do Banco Central vem com duas casas. Compor as variações arredondadas pode dar uma diferença de
um ou dois centésimos de ponto percentual em relação ao acumulado divulgado pelo produtor. Para um contrato, vale
o número que o contrato manda usar.</p>

<h2>Acumulado negativo</h2>
<p>Quando o índice teve deflação suficiente no período, o fator fica abaixo de 1 e o acumulado é negativo.
Matematicamente o valor diminuiria. Em contratos, aplicar ou não a redução depende da cláusula.</p>

<h2>De onde vêm os números</h2>
<p>As variações mensais saem da API pública do SGS: série 433 (IPCA), 188 (INPC), 189 (IGP-M) e 190 (IGP-DI). A
coleta roda a cada 6 horas e o histórico fica versionado no
<a href="https://github.com/iosbilario/observatorio-taxas">repositório do projeto</a>, onde dá para refazer
qualquer conta.</p>
"""
    perguntas = [
        ("Como calcular a inflação acumulada em 12 meses?",
         "Multiplique (1 + variação do mês ÷ 100) dos 12 meses e subtraia 1. O resultado vezes 100 é o acumulado em "
         "porcentagem."),
        ("Posso somar as taxas mensais?",
         f"Não. A soma ignora que cada mês incide sobre o valor já corrigido. Nos três últimos meses do IPCA, a soma dá "
         f"{pct(soma)} e o acumulado correto, {pct((fator - 1) * 100)}."),
        ("Por que o acumulado do site difere do divulgado?",
         "O produtor calcula com números-índice de várias casas decimais; a série mensal do SGS tem duas. A diferença "
         "costuma ser de um ou dois centésimos de ponto percentual."),
    ]
    return ("como-calcular-acumulado", "Como calcular o acumulado de 12 meses de um índice (IPCA, IGP-M)",
            "Como calcular o acumulado de um índice",
            "Por que o acumulado é a multiplicação dos fatores e não a soma das taxas, com exemplo do IPCA atual, a "
            "relação entre fator e acumulado e por que o resultado pode diferir do oficial em centésimos.",
            corpo, perguntas)


def guia_ptax(px: dict) -> tuple:
    var_ano = (px["venda"] / px["inicio_ano"]["valor"] - 1) * 100
    corpo = f"""
<p class="resposta">A PTAX é a taxa de câmbio de referência calculada pelo Banco Central. Em {dia(px['dt'])}, o
dólar PTAX ficou em <b>R$ {fmt_num(px['venda'], 4)}</b> na venda e <b>R$ {fmt_num(px['compra'], 4)}</b> na
compra.</p>

<h2>Como ela é calculada</h2>
<p>Em cada dia útil, o Banco Central consulta os bancos que atuam como dealers de câmbio em quatro janelas ao
longo da manhã. A PTAX é a média dessas consultas, depois de descartar as cotações extremas, e sai no início da
tarde. Por isso há uma PTAX por dia útil, e nenhuma em fim de semana ou feriado.</p>

<h2>Compra e venda</h2>
<p>A taxa de venda é a que um banco cobra para vender dólar; a de compra, a que paga para comprar. A diferença
entre as duas costuma ficar abaixo de um centavo por dólar. Contratos e documentos fiscais costumam indicar qual
delas usar, e a de venda é a mais citada.</p>

<h2>Para que serve</h2>
<ul>
<li>Converter valores em contratos com cláusula em dólar.</li>
<li>Referência para declarações à Receita e para a liquidação de contratos de câmbio futuros.</li>
<li>Comparar o câmbio ao longo do tempo com uma taxa única e oficial, em vez da cotação comercial, que muda o dia
todo.</li>
</ul>

<h2>O dólar em {px['dt'].year}</h2>
<p>Desde o primeiro dia útil do ano, a PTAX de venda variou {pct(var_ano)}. A máxima do ano foi
R$ {fmt_num(px['max']['valor'], 4)}, em {dia(px['max']['dt'])}, e a mínima foi R$ {fmt_num(px['min']['valor'], 4)},
em {dia(px['min']['dt'])}, em {px['dias_ano']} dias úteis com cotação. Veja a série completa em
<a href="../../indicadores/dolar/">dólar PTAX venda</a> e <a href="../../indicadores/dolar-compra/">compra</a>.</p>

<h2>A PTAX não é a cotação do turismo</h2>
<p>Quem compra moeda em espécie ou usa cartão no exterior paga a cotação da casa de câmbio ou do banco, com
spread e IOF. Essa taxa fica acima da PTAX.</p>
"""
    perguntas = [
        ("O que é o dólar PTAX?",
         "É a taxa de câmbio de referência do Banco Central, a média das cotações informadas pelos dealers em quatro "
         "janelas de consulta ao longo da manhã de cada dia útil."),
        ("A que horas sai a PTAX?",
         "No início da tarde de cada dia útil, depois da última janela de consulta. Não há PTAX em fins de semana e "
         "feriados."),
        ("Qual foi a última PTAX?",
         f"Em {dia(px['dt'])}, R$ {fmt_num(px['venda'], 4)} na venda e R$ {fmt_num(px['compra'], 4)} na compra, séries "
         f"1 e 10813 do SGS do Banco Central."),
    ]
    return ("dolar-ptax", "Dólar PTAX: o que é, como é calculado e quando sai",
            "Dólar PTAX: o que é e quando sai",
            f"O que é a PTAX do Banco Central, como é calculada, a diferença entre compra e venda e para que serve. "
            f"Última cotação: R$ {fmt_num(px['venda'], 4)} na venda em {dia(px['dt'])}.",
            corpo, perguntas)


def guia_selic(ms: dict, sm: dict) -> tuple:
    regra_nova = ms["valor"] > 8.5
    poup = ("Com a Meta Selic acima de 8,5% ao ano, a poupança rende 0,5% ao mês mais a TR."
            if regra_nova else
            f"Com a Meta Selic em até 8,5% ao ano, a poupança rende 70% da Selic mais a TR, o que hoje equivale a cerca "
            f"de {pct(ms['valor'] * 0.7)} ao ano mais a TR.")
    mudou = (f"O valor atual vale desde {dia(ms['desde'])}; antes era {pct(ms['anterior'])} ao ano."
             if ms["anterior"] is not None else "")
    corpo = f"""
<p class="resposta">A Meta Selic é a taxa básica de juros definida pelo Copom. Hoje ela está em
<b>{pct(ms['valor'])} ao ano</b>. {mudou}</p>

<h2>Três números com o nome Selic</h2>
<ul>
<li><b>Meta Selic:</b> a taxa anual que o Copom, comitê do Banco Central, decide em oito reuniões por ano. É a que
sai no noticiário. Série 432 do SGS.</li>
<li><b>Selic efetiva:</b> a taxa média dos empréstimos de um dia entre bancos com títulos públicos como garantia.
Anda muito perto da meta, um pouco abaixo. Série 1178.</li>
<li><b>Selic acumulada no mês:</b> a Selic efetiva composta ao longo do mês. É a usada para corrigir valores,
como débitos e restituições de tributos federais. Série 4390.</li>
</ul>

<h2>Qual usar</h2>
<p>Para saber o nível dos juros, use a Meta Selic. Para calcular quanto um valor rendeu ou deve ser corrigido, use
a Selic acumulada no mês: nos 12 meses de {mes_ano(sm['ini'])} a {mes_ano(sm['ref'])}, ela acumulou
<b>{pct(sm['ac'])}</b>, com os meses compostos. Aplicar a Meta Selic anual sobre um período dá um resultado diferente,
porque a meta muda ao longo do tempo e não é a taxa efetivamente praticada.</p>

<h2>Selic e poupança</h2>
<p>{poup} A regra está na Lei 12.703/2012. Veja o rendimento mensal em
<a href="../../indicadores/poupanca/">poupança</a>.</p>

<h2>Selic e CDI</h2>
<p>O CDI é a taxa dos empréstimos de um dia entre bancos sem garantia de título público, calculada pela B3. Na
prática fica colado na Selic efetiva. O <a href="../../comparador/">comparador</a> mostra Selic, CDI e IPCA lado a
lado.</p>
"""
    perguntas = [
        ("Qual é a Meta Selic hoje?",
         f"{pct(ms['valor'])} ao ano, pela série 432 do SGS do Banco Central. {mudou}".strip()),
        ("Qual a diferença entre Meta Selic e Selic efetiva?",
         "A Meta Selic é a taxa anual decidida pelo Copom. A Selic efetiva é a taxa média praticada nos empréstimos de "
         "um dia entre bancos com títulos públicos, e fica um pouco abaixo da meta."),
        ("Qual Selic usar para corrigir um valor?",
         f"A Selic acumulada no mês (série 4390), composta mês a mês. De {mes_ano(sm['ini'])} a {mes_ano(sm['ref'])}, "
         f"ela acumulou {pct(sm['ac'])}."),
    ]
    return ("selic", "Meta Selic, Selic efetiva e Selic do mês: diferenças e qual usar",
            "Meta Selic, Selic efetiva e Selic do mês",
            f"A diferença entre Meta Selic, Selic efetiva e Selic acumulada no mês, qual usar para corrigir valores e "
            f"como a Selic define o rendimento da poupança. Meta Selic atual: {pct(ms['valor'])} ao ano.",
            corpo, perguntas)


def guia_correcao(ix: dict) -> tuple:
    i = ix["IPCA"]
    j = i["janela"]
    com_ini = acumulado(j)
    sem_ini = acumulado(j[1:])
    corpo = f"""
<p class="resposta">Corrigir um valor é atualizá-lo pela inflação de um período, para comparar dinheiro de datas
diferentes. A conta é a mesma do reajuste: valor × fator acumulado do índice no período.</p>

<h2>Correção não é juros</h2>
<p>A correção só repõe a perda de poder de compra. Juros remuneram o tempo e o risco e vêm por cima. Uma dívida
corrigida pelo IPCA mais juros de 1% ao mês cresce pelas duas coisas, e as duas contas são feitas em separado.</p>

<h2>Escolha o índice</h2>
<p>Se houver contrato, decisão judicial ou norma, use o índice que ela manda. Sem regra, o IPCA é a escolha mais
comum para medir inflação ao consumidor. Para débitos e créditos de tributos federais, a regra é a Selic. Os
guias <a href="../ipca-igpm-inpc-igpdi/">dos índices de inflação</a> e <a href="../selic/">da Selic</a> ajudam a
escolher.</p>

<h2>O detalhe que mais muda o resultado: o mês inicial entra ou não?</h2>
<p>“De janeiro a dezembro” pode significar duas coisas. Se o valor já existia no fim de janeiro, a inflação de
janeiro não incide sobre ele e a conta começa em fevereiro. Se o valor era de 1º de janeiro, janeiro entra. Com o
IPCA de {mes_ano(j[0]['dt'])} a {mes_ano(j[-1]['dt'])}:</p>
<ul>
<li>com {mes_ano(j[0]['dt'])} incluído (12 meses): {pct(com_ini)};</li>
<li>começando em {mes_ano(j[1]['dt'])} (11 meses): {pct(sem_ini)}.</li>
</ul>
<p>A <a href="../../correcao/">calculadora de correção</a> do Observatório trata o valor como existente no fechamento
do mês inicial, então aplica as taxas a partir do mês seguinte, e mostra a tabela mês a mês para conferir.</p>

<h2>Passo a passo</h2>
<ol>
<li>Defina o índice e as datas de início e de fim.</li>
<li>Decida se o mês inicial entra, pela regra acima.</li>
<li>Multiplique os fatores dos meses do período (veja <a href="../como-calcular-acumulado/">como calcular o
acumulado</a>).</li>
<li>Multiplique o valor pelo fator e arredonde só no final.</li>
</ol>
"""
    perguntas = [
        ("O que é correção monetária?",
         "É a atualização de um valor pela inflação de um período, para que ele mantenha o poder de compra. Não inclui "
         "juros."),
        ("Qual índice usar para corrigir um valor?",
         "O que o contrato, a decisão ou a norma mandar. Sem regra, o IPCA é o mais usado para inflação ao consumidor; "
         "tributos federais usam a Selic."),
        ("O mês inicial entra na correção?",
         f"Depende de quando o valor passou a existir. Com o IPCA, incluir {mes_ano(j[0]['dt'])} dá {pct(com_ini)}; "
         f"começar em {mes_ano(j[1]['dt'])} dá {pct(sem_ini)}."),
    ]
    return ("correcao-monetaria", "Correção monetária: como corrigir um valor pela inflação",
            "Correção monetária: como corrigir um valor",
            "Como corrigir um valor pela inflação: diferença entre correção e juros, qual índice usar, se o mês inicial "
            "entra na conta e o passo a passo com a calculadora do Observatório.",
            corpo, perguntas)


def hub(guias: list[tuple], atualizado: date) -> str:
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Guias", URL_HUB)])
    titulo = "Guias do Observatório de Taxas: reajuste, inflação, Selic e dólar"
    desc = ("Guias práticos para usar os indicadores do Banco Central: reajuste de aluguel, diferenças entre IPCA e "
            "IGP-M, cálculo do acumulado, dólar PTAX, Selic e correção monetária.")
    itens = "".join(f'<a href="{slug}/"><b>{e(h1)}</b><span>{e(desc_g)}</span></a>'
                    for slug, _, h1, desc_g, _, _ in guias)
    lista_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Guias",
                "itemListElement": [{"@type": "ListItem", "position": n, "url": f"{URL_HUB}{g[0]}/", "name": g[2]}
                                    for n, g in enumerate(guias, start=1)]}
    jsonld = jsonld_script(lista_ld) + "\n" + jsonld_script({"@context": "https://schema.org", **crumb_ld})
    return (head(titulo, desc, URL_HUB, jsonld, crumb_html, []).replace("</style>", GUIA_CSS + "</style>", 1)
            + f"""
<article class="guia">
<header><h1>Guias</h1>
<p class="resposta">Como usar os números do Banco Central no dia a dia: reajustar um contrato, escolher o índice
certo, conferir uma conta e entender a Selic e o dólar. Os exemplos são atualizados a cada coleta.</p></header>
<nav class="lista-guias" aria-label="Guias">{itens}</nav>
</article>
""" + RODAPE)


def gerar() -> dict[str, str]:
    ix = {n: indice(c) for n, c, _ in INDICES}
    ms, sm, px = meta_selic(), selic_mes(), ptax()
    atualizado = max(px["dt"], ms["ref"]).date()
    guias = [guia_aluguel(ix), guia_indices(ix), guia_acumulado(ix), guia_correcao(ix), guia_selic(ms, sm),
             guia_ptax(px)]
    saida = {"guias/index.html": hub(guias, atualizado)}
    for slug, titulo, h1, desc, corpo, perguntas in guias:
        saida[f"guias/{slug}/index.html"] = pagina(slug, titulo, h1, desc, corpo, perguntas, atualizado)
    return saida


def main() -> None:
    saida = gerar()
    for rel, texto in saida.items():
        out = DOCS / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(texto, encoding="utf-8")
    print(f"Guias gerados: {len(saida) - 1} + hub.")


if __name__ == "__main__":
    main()
