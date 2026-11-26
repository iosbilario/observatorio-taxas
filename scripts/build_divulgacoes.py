#!/usr/bin/env python3
"""
build_divulgacoes.py — Divulgações permanentes, arquivo durável e RSS.

Para cada série acompanhada (SERIES), calcula a leitura da competência mais
recente (scripts/leituras.py) e mantém data/publicacoes.json (espelho em
docs/data/), um arquivo que SÓ CRESCE:

  - primeira leitura de uma competência -> um registro novo (revisao 0);
  - mesma competência com as mesmas entradas -> nada muda (id, texto e datas
    originais ficam como estavam);
  - alguma entrada da conta mudou (revisão do produtor, mês que faltava e
    chegou) -> um registro novo, revisao 1, 2, ..., com os valores anterior e
    revisado e as duas versões dos dados. O registro original continua lá.

Cada registro guarda a leitura inteira (números, tabela, texto, regra e versão
dos dados). As páginas /divulgacoes/<serie>/<competencia>/ e o /feed.xml são
gerados só a partir desse arquivo, então uma divulgação antiga continua igual
mesmo depois de os dados serem revisados ou de a regra mudar.

Por que não basta mudancas.json: ele guarda só as 30 coletas mais recentes. Ele
entra aqui apenas para saber QUANDO o Observatório identificou a competência.

Datas, sem misturar: a competência é o mês do índice; "identificado em" é a
hora da coleta que trouxe o dado (mudancas.json); "registrado em" é a data do
commit dos dados (versao.json). A data oficial de divulgação do produtor não
está no SGS, então fica vazia.

Versão dos dados: um registro só nasce com --registrar, que o monitor.yml roda
DEPOIS do commit da coleta e do versao_dados.py, quando o commit que contém os
dados já existe. Antes de registrar, o script confere com o Git que os
arquivos das séries são idênticos aos desse commit; se não forem (ou o commit
não estiver no clone), não registra nada. Sem --registrar, só refaz as páginas
e o feed a partir do arquivo (é o que o validate.yml confere).

Carga histórica: só a competência mais recente de cada série vira registro; um
backfill de anos não vira anos de itens no feed.

    python scripts/build_divulgacoes.py               # páginas + feed
    python scripts/build_divulgacoes.py --registrar   # + novos registros
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import leituras as L  # noqa: E402
from build_ferramentas import e, head  # noqa: E402
from build_pages import fmt_num, jsonld_script, load_history, migalhas, slug_mes  # noqa: E402

DOCS = ROOT / "docs"
ARQUIVO = ROOT / "data" / "publicacoes.json"
ESPELHO = DOCS / "data" / "publicacoes.json"
MUDANCAS = ROOT / "data" / "mudancas.json"
VERSAO = DOCS / "data" / "versao.json"
BASE_URL = "https://observatoriodetaxas.tec.br"
REPO = "iosbilario/observatorio-taxas"
REPO_URL = f"https://github.com/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}"
FEED_URL = f"{BASE_URL}/feed.xml"
ITENS_NO_FEED = 50
CSS = """
.tabela-rolagem{overflow-x:auto;margin:.4rem 0 1rem}
.tabela-rolagem:focus-visible{outline:2px solid var(--carimbo);outline-offset:2px}
.tabela-rolagem table{min-width:560px}
caption{caption-side:bottom;text-align:left;padding-top:.5rem}
.grafico-div img{width:100%;height:auto;border-radius:6px;background:#fff}
.grafico-div{margin:1rem 0}
.lista-div li{margin:.45rem 0}
"""

# Séries com divulgação. "leitura" escolhe a função de scripts/leituras.py.
# "series" = códigos SGS que a leitura usa (todos conferidos com o Git antes
# de registrar). Cadência: IPCA e CDI por competência mensal; PTAX pelo
# fechamento semanal (a ficha acompanha também a variação diária).
SERIES: dict[str, dict] = {
    "ipca": {"codigo": 433, "nome": "IPCA", "leitura": "mensal", "ficha": "indicadores/ipca/",
             "produtor": "IBGE", "reajuste": "ipca", "series": [433]},
    "cdi": {"codigo": 4391, "nome": "CDI", "leitura": "cdi", "ficha": "indicadores/cdi/",
            "produtor": "B3 (taxa DI)", "series": [4391, 433, 4389]},
    "dolar": {"codigo": 1, "nome": "Dólar PTAX (venda)", "leitura": "ptax", "ficha": "indicadores/dolar/",
              "produtor": "Banco Central do Brasil", "series": [1]},
}
FICHA_POR_CODIGO = {433: "ipca", 4389: "cdi", 1: "dolar"}   # página /indicadores/ que mostra a leitura


def hoje_da_versao(versao: dict):
    """Data de referência de uma leitura que depende de "hoje" (semana aberta
    ou encerrada): a data do commit dos dados, em Brasília. Mesmas entradas,
    mesma leitura."""
    from datetime import timedelta
    d = datetime.fromisoformat(versao["data"].replace("Z", "+00:00"))
    return d.astimezone(timezone(timedelta(hours=-3))).date()


# ── arquivo ───────────────────────────────────────────────────────────────

def ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def grava_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def leitura_de(chave: str, historicos: dict[int, list[dict]], competencia: str | None = None,
               hoje=None) -> dict:
    s, h = SERIES[chave], historicos
    if s["leitura"] == "mensal":
        return L.leitura_mensal(s["codigo"], s["nome"], h[s["codigo"]], competencia)
    if s["leitura"] == "cdi":
        return L.leitura_cdi(h[4391], h[433], h.get(4389, []), competencia)
    if s["leitura"] == "ptax":
        return L.leitura_ptax(h[1], hoje, competencia)
    raise ValueError(s["leitura"])


def url_registro(chave: str, competencia: str, revisao: int) -> str:
    return f"{BASE_URL}/divulgacoes/{chave}/{competencia}/" + (f"revisao-{revisao}/" if revisao else "")


def observacao(chave: str, entrada: str) -> tuple[int, str]:
    """(código SGS, data no formato do SGS) de uma chave de `entradas`:
    "2026-10" (mês), "cdi:2026-10" / "ipca:2026-10" (série:mês) ou
    "2026-11-19" (dia)."""
    cod = SERIES[chave]["codigo"]
    if ":" in entrada:
        nome, entrada = entrada.split(":", 1)
        cod = {"cdi": 4391, "ipca": 433}[nome]
    if len(entrada) == 7:
        return cod, f"01/{entrada[5:7]}/{entrada[:4]}"
    return cod, f"{entrada[8:10]}/{entrada[5:7]}/{entrada[:4]}"


def identificado_em(mudancas: dict, alvo: set[tuple[int, str]], primeira: bool) -> dict | None:
    """Coleta (mudancas.json) que trouxe a observação nova ou a revisão: a mais
    antiga para uma publicação nova, a mais recente para uma revisão."""
    achadas = []
    for col in mudancas.get("coletas", []):
        itens = col.get("novas", []) + col.get("revisoes", [])
        if any((int(i.get("codigo", 0)), i.get("data")) in alvo for i in itens):
            achadas.append(col)
    if not achadas:
        return None
    col = min(achadas, key=lambda c: c["gerado_em"]) if primeira else max(achadas, key=lambda c: c["gerado_em"])
    return {"gerado_em": col["gerado_em"], "commit": col.get("commit")}


def registrar(arquivo: dict, historicos: dict[int, list[dict]], mudancas: dict, versao: dict) -> list[dict]:
    """Acrescenta ao arquivo os registros novos e devolve só os acrescentados.
    Determinístico: mesmas entradas, nenhum registro novo."""
    pubs = arquivo.setdefault("publicacoes", [])
    novos: list[dict] = []
    hoje = hoje_da_versao(versao)
    for chave, s in SERIES.items():
        if not all(historicos.get(c) for c in s["series"] if c != 4389):
            continue
        atual = leitura_de(chave, historicos, hoje=hoje)
        if not atual["competencia"] or not atual["entradas"]:
            continue
        da_serie = [p for p in pubs if p["serie"] == chave]
        competencias = sorted({p["competencia"] for p in da_serie} | {atual["competencia"]})
        for comp in competencias:
            # Sempre com a competência explícita: o registro é a leitura DAQUELE
            # período (na PTAX, a semana encerrada, sem o parcial da seguinte).
            lt = leitura_de(chave, historicos, comp, hoje)
            mesmas = [p for p in da_serie if p["competencia"] == comp]
            if not mesmas:
                if comp != atual["competencia"]:
                    continue
                rev, revisa = 0, None
            else:
                ult = max(mesmas, key=lambda p: p["revisao"])
                antes = ult["leitura"]["entradas"]
                if antes == lt["entradas"]:
                    continue
                alter = [{"competencia": c, "antes": antes.get(c), "depois": lt["entradas"].get(c)}
                         for c in sorted(set(antes) | set(lt["entradas"])) if antes.get(c) != lt["entradas"].get(c)]
                rev = ult["revisao"] + 1
                revisa = {"id": ult["id"], "versao_anterior": ult["versao_dados"], "alteracoes": alter}
            if revisa:
                alvo = {observacao(chave, a["competencia"]) for a in revisa["alteracoes"]}
            else:
                chave_nova = {"mensal": comp, "cdi": f"cdi:{comp}",
                              "ptax": (lt.get("fechamento") or {}).get("data", "")}[s["leitura"]]
                alvo = {observacao(chave, chave_nova)} if chave_nova else set()
            reg = {
                "id": f"{chave}-{comp}" + (f"-r{rev}" if rev else ""), "serie": chave, "codigo": s["codigo"],
                "competencia": comp, "revisao": rev, "url": url_registro(chave, comp, rev),
                "registrado_em": versao["data"], "versao_dados": {"sha": versao["sha"], "curto": versao["sha"][:7]},
                "identificado": identificado_em(mudancas, alvo, primeira=not revisa),
                "divulgacao_oficial": None, "carga_inicial": not da_serie and not any(n["serie"] == chave for n in novos), "revisa": revisa,
                "leitura": lt,
            }
            novos.append(reg)
    pubs.extend(novos)
    return novos


def dados_conferem(versao: dict, raiz: Path = ROOT) -> bool:
    """Os arquivos das séries são os do commit de versao.json? (git diff)"""
    arqs = sorted({f"data/{c}_history.json" for s in SERIES.values() for c in s["series"]})
    r = subprocess.run(["git", "diff", "--quiet", versao["sha"], "--", *arqs], cwd=raiz,
                       capture_output=True, text=True)
    return r.returncode == 0


# ── páginas ───────────────────────────────────────────────────────────────

def quando(iso: str | None) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo and d.utcoffset().total_seconds() == 0:
        return d.strftime("%d/%m/%Y às %H:%M (UTC)")
    return d.strftime("%d/%m/%Y às %H:%M (horário de Brasília)")


def caminho(reg: dict) -> Path:
    return DOCS / reg["url"].removeprefix(BASE_URL + "/") / "index.html"


def prefixo(reg: dict) -> str:
    return "../" * (reg["url"].removeprefix(BASE_URL + "/").rstrip("/").count("/") + 1)


def v(x, sufixo: str = "%") -> str:
    return "—" if x is None else f"{fmt_num(x)}{sufixo}"


def tabela_mensal(lt: dict, serie: str, pre: str, rotulo: str = "conta-t") -> str:
    s = SERIES[serie]
    linhas = []
    for li in lt["linhas"]:
        c = li["competencia"]
        nome = L.mes_txt(c)
        if s.get("reajuste") and (DOCS / "reajuste" / f"{s['reajuste']}-{slug_mes(L.dt_ym(c))}" / "index.html").exists():
            nome = f'<a href="{pre}reajuste/{s["reajuste"]}-{slug_mes(L.dt_ym(c))}/">{e(nome)}</a>'
        else:
            nome = e(nome)
        fator = "—" if li["valor"] is None else fmt_num(1 + li["valor"] / 100, 6)
        linhas.append(f"<tr><td>{nome}</td><td>{v(li['valor'])}</td><td>{fator}</td>"
                      f"<td>{'sim' if li['janela_atual'] else ''}</td><td>{'sim' if li['janela_anterior'] else ''}</td>"
                      f"<td>{e(li['papel'])}</td></tr>")
    rodape = (f"<tr><th scope=\"row\">Acumulado em 12 meses</th><td></td><td></td>"
              f"<td>{v(lt['acumulado_12m'])}</td><td>{v(lt['acumulado_12m_anterior'])}</td><td></td></tr>")
    return (f'<div class="tabela-rolagem" role="region" aria-labelledby="{rotulo}" tabindex="0"><table>'
            '<caption class="mut">Acumulado = (1 + taxa₁ ÷ 100) × … × (1 + taxa₁₂ ÷ 100) − 1, com os 12 meses '
            'marcados em cada janela.</caption>'
            '<thead><tr><th scope="col">Competência</th><th scope="col">Variação no mês</th>'
            '<th scope="col">Fator do mês</th><th scope="col">Janela atual</th>'
            '<th scope="col">Janela anterior</th><th scope="col">Papel na troca</th></tr></thead>'
            f"<tbody>{''.join(linhas)}</tbody><tfoot>{rodape}</tfoot></table></div>")


def resumo_mensal(lt: dict) -> list[tuple[str, str]]:
    return [
        ("Competência", L.mes_txt(lt["competencia"])),
        ("Taxa no mês", v(lt["mensal"])),
        (f"Taxa em {L.mes_txt(lt['anterior'])}", v(lt["mensal_anterior"])),
        ("Acumulado em 12 meses", v(lt["acumulado_12m"])),
        (f"Acumulado até {L.mes_txt(lt['anterior'])}", v(lt["acumulado_12m_anterior"])),
        ("Diferença entre os acumulados", "—" if lt["diferenca_pp"] is None else
         f"{'+' if lt['diferenca_pp'] > 0 else '−' if lt['diferenca_pp'] < 0 else ''}{fmt_num(abs(lt['diferenca_pp']))} p.p."),
        (f"Entrou na janela ({L.mes_txt(lt['competencia'])})", v(lt["mensal"])),
        (f"Saiu da janela ({L.mes_txt(lt['saiu'])})", v(lt["saiu_valor"])),
    ]


def titulo(reg: dict) -> str:
    t = reg["leitura"]["titulo"]
    return f"Revisão {reg['revisao']} — {t}" if reg["revisao"] else t


def rotulo_entrada(chave: str, k: str) -> str:
    if ":" in k:
        nome, k = k.split(":", 1)
        return f"{nome.upper()} de {L.mes_txt(k)}"
    return L.mes_txt(k) if len(k) == 7 else f"{k[8:10]}/{k[5:7]}/{k[:4]}"


def fmt_entrada(chave: str, x) -> str:
    if x is None:
        return "ausente"
    return f"R$ {fmt_num(x, 4)}" if SERIES[chave]["leitura"] == "ptax" else v(x)


def periodo(lt: dict) -> str:
    if lt["regra"].startswith("leitura-mensal"):
        return L.mes_txt(lt["competencia"])
    if lt["regra"].startswith("leitura-cdi"):
        return f"{L.mes_txt(lt['inicio'])} a {L.mes_txt(lt['fim'])}"
    seg = L._segunda(lt["competencia"])
    from datetime import timedelta
    return f"semana de {seg:%d/%m} a {seg + timedelta(days=4):%d/%m/%Y}"


SUFIXO = {"mensal": "leitura mensal e acumulado", "cdi": "acumulado e taxa real", "ptax": "fechamento semanal"}


def titulo_curto(reg: dict) -> str:
    lt, s = reg["leitura"], SERIES[reg["serie"]]
    base = (f"{lt['nome']} de {periodo(lt)}" if s["leitura"] != "ptax" else f"{lt['nome']}, {periodo(lt)}")
    base += f", revisão {reg['revisao']}" if reg["revisao"] else ""
    t = f"{base}: {SUFIXO[s['leitura']]}"
    return t if len(t) <= 70 else base[:70]


def bloco_revisao(reg: dict) -> str:
    r = reg["revisa"]
    if not r:
        return ""
    sha_a, sha_b = r["versao_anterior"]["sha"], reg["versao_dados"]["sha"]
    chave = reg["serie"]
    linhas = "".join(f"<tr><td>{e(rotulo_entrada(chave, a['competencia']))}</td><td>{e(fmt_entrada(chave, a['antes']))}</td>"
                     f"<td>{e(fmt_entrada(chave, a['depois']))}</td></tr>" for a in r["alteracoes"])
    versoes = " · ".join(
        f'série {c}: <a href="{RAW}/{sha_a}/data/{c}_history.json">versão anterior ({sha_a[:7]})</a>, '
        f'<a href="{RAW}/{sha_b}/data/{c}_history.json">versão revisada ({sha_b[:7]})</a>'
        for c in SERIES[chave]["series"])
    return (f'<section class="card" aria-labelledby="rev-t"><h2 id="rev-t">O que esta revisão mudou</h2>'
            f'<p>Esta leitura substitui a <a href="{url_por_id(r["id"])}">anterior</a>, que continua publicada. '
            "Valores que mudaram:</p>"
            '<div class="tabela-rolagem" role="region" aria-labelledby="rev-t" tabindex="0"><table><thead><tr>'
            '<th scope="col">Observação</th><th scope="col">Valor anterior</th><th scope="col">Valor revisado</th>'
            f"</tr></thead><tbody>{linhas}</tbody></table></div>"
            f'<p class="mut">{versoes} · <a href="{REPO_URL}/compare/{sha_a}...{sha_b}">comparar as versões no '
            "GitHub</a>.</p></section>")


_POR_ID: dict[str, str] = {}


def url_por_id(i: str) -> str:
    return _POR_ID.get(i, f"{BASE_URL}/divulgacoes/")


def kpis_de(lt: dict) -> list:
    return resumo_mensal(lt) if lt["regra"].startswith("leitura-mensal") else lt["kpis"]


def tabela_generica(lt: dict, rotulo: str) -> str:
    def cel(x):
        return "—" if x is None else e(fmt_num(x)) if isinstance(x, float) else e(x)
    th = "".join(f'<th scope="col">{e(c)}</th>' for c in lt["tabela"]["cab"])
    corpo = "".join("<tr>" + "".join(f"<td>{cel(x)}</td>" for x in li) + "</tr>" for li in lt["tabela"]["linhas"])
    return (f'<div class="tabela-rolagem" role="region" aria-labelledby="{rotulo}" tabindex="0"><table>'
            f"<thead><tr>{th}</tr></thead><tbody>{corpo}</tbody></table></div>")


def conta_de(lt: dict, serie: str, pre: str, rotulo: str = "conta-t", h: str = "h2") -> str:
    """Seção com a tabela que permite refazer a conta (e, no CDI, os links para
    o comparador e o simulador com o mesmo período)."""
    if lt["regra"].startswith("leitura-mensal"):
        return (f'<{h} id="{rotulo}">A conta, mês a mês</{h}>'
                f'<p>Janela atual: {e(L.mes_txt(lt["janela"][0]))} a {e(L.mes_txt(lt["janela"][1]))}. Janela anterior: '
                f'{e(L.mes_txt(lt["janela_anterior"][0]))} a {e(L.mes_txt(lt["janela_anterior"][1]))}.</p>'
                + tabela_mensal(lt, serie, pre, rotulo))
    html = f'<{h} id="{rotulo}">Os dados usados</{h}>' + tabela_generica(lt, rotulo)
    if lt["regra"].startswith("leitura-cdi"):
        lk = lt["links"]
        html += (f'<p><a class="pill" href="{e(lk["comparador"])}">Abrir no comparador ({e(periodo(lt))})</a>'
                 f'<a class="pill" href="{e(lk["simulador"])}">Simular 100% do CDI no mesmo período</a></p>'
                 f'<p class="mut">O comparador usa as mesmas competências fechadas, de {e(L.mes_txt(lt["inicio"]))} a '
                 f'{e(L.mes_txt(lt["fim"]))}, com o CDI mensal (SGS 4391). O simulador trabalha com dias úteis: '
                 f'aplica a taxa DI diária (SGS 4389) de {lk["simulador_de"][8:]}/{lk["simulador_de"][5:7]}/'
                 f'{lk["simulador_de"][:4]} (aplicação) até {lk["simulador_ate"][8:]}/{lk["simulador_ate"][5:7]}/'
                 f'{lk["simulador_ate"][:4]} (resgate, sem render nesse dia). Por isso o resultado dele pode diferir '
                 "em centésimos do acumulado mensal.</p>")
    return html


def pagina(reg: dict, todos: list[dict]) -> str:
    s, lt = SERIES[reg["serie"]], reg["leitura"]
    url, pre = reg["url"], prefixo(reg)
    t = titulo(reg)
    desc = " ".join(lt["frases"][:2])[:300]
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"),
                                     ("Divulgações", f"{BASE_URL}/divulgacoes/"), (t, url)])
    ld = jsonld_script({"@context": "https://schema.org", "@type": "Article", "headline": t[:110],
                        "description": desc, "url": url, "inLanguage": "pt-BR",
                        "datePublished": reg["registrado_em"], "isPartOf": {"@id": f"{BASE_URL}/#website"},
                        "publisher": {"@type": "Organization", "name": "Observatório de Taxas", "url": f"{BASE_URL}/"}})
    ld += "\n" + jsonld_script({"@context": "https://schema.org", **crumb_ld})
    topo = head(titulo_curto(reg), desc, url, ld, crumb_html, []).replace("</style>", CSS + "</style>", 1)
    mais_novas = [p for p in todos if p["serie"] == reg["serie"] and p["competencia"] == reg["competencia"]
                  and p["revisao"] > reg["revisao"]]
    aviso = ""
    if mais_novas:
        ult = max(mais_novas, key=lambda p: p["revisao"])
        aviso = (f'<p class="aviso"><b>Esta leitura foi revisada depois.</b> Ela fica publicada como estava, com os dados '
                 f'da versão {reg["versao_dados"]["curto"]}. <a href="{ult["url"]}">Ver a revisão {ult["revisao"]}</a>.</p>')
    sha = reg["versao_dados"]["sha"]
    ident = reg.get("identificado")
    ident_txt = (f'{e(quando(ident["gerado_em"]))}, na coleta automática do SGS' if ident else
                 "não registrado: esta é a primeira leitura do arquivo de divulgações, criado depois de o "
                 "dado chegar ao Observatório" if reg.get("carga_inicial") else "não registrado")
    kpis = "".join(f'<div class="kpi"><span>{e(r)}</span><b>{e(x)}</b></div>' for r, x in kpis_de(lt))
    nota = f'<p class="mut">{e(lt["nota"])}</p>' if lt.get("nota") else ""
    fontes = " · ".join(f'<a href="https://api.bcb.gov.br/dados/serie/bcdata.sgs.{c}/dados?formato=json">série {c}</a>'
                        for c in s["series"])
    jsons = " · ".join(f'<a href="{RAW}/{sha}/data/{c}_history.json">série {c} nessa versão (JSON)</a>'
                       for c in s["series"])
    rot_periodo = "Competência" if s["leitura"] == "mensal" else "Período"
    return (topo + f"""<article>
<h1>{e(t)}</h1>
{aviso}
<div class="kpis">{kpis}</div>
<section class="card" aria-labelledby="leit-t"><h2 id="leit-t">Leitura</h2>
{"".join(f"<p>{e(f)}</p>" for f in lt["frases"])}
{nota}
</section>
<figure class="card grafico-div"><img src="grafico.svg" width="720" height="340" alt="{e(grafico_alt(reg))}"/>
<figcaption class="mut">Os mesmos números da tabela abaixo.</figcaption></figure>
{bloco_acoes(reg, url_ficha(reg))}
{bloco_revisao(reg)}
<section class="card" aria-labelledby="conta-t">{conta_de(lt, reg["serie"], pre)}</section>
<section class="card" aria-labelledby="proc-t"><h2 id="proc-t">Fonte, datas e versão</h2>
<dl class="ficha">
<dt>Indicador</dt><dd>{e(lt["nome"])}, produzido por {e(s["produtor"])}</dd>
<dt>Obtido em</dt><dd>SGS do Banco Central: {fontes}</dd>
<dt>{rot_periodo}</dt><dd>{e(periodo(lt))}</dd>
<dt>Identificado pelo Observatório</dt><dd>{ident_txt}</dd>
<dt>Divulgação oficial</dt><dd>não informada: o SGS não traz a data de divulgação do produtor, e o Observatório não a deduz da hora da coleta</dd>
<dt>Registrado em</dt><dd>{e(quando(reg["registrado_em"]))} (data do commit dos dados)</dd>
<dt>Versão dos dados</dt><dd>commit <a href="{REPO_URL}/commit/{sha}">{sha[:7]}</a> · {jsons}</dd>
<dt>Regra</dt><dd><code>{e(lt["regra"])}</code> (<a href="{REPO_URL}/blob/{sha}/scripts/leituras.py">código nessa versão</a>)</dd>
<dt>Identificador</dt><dd><code>{e(reg["id"])}</code></dd>
</dl></section>
<p><a class="pill" href="{pre}{s["ficha"]}#leitura">Ficha do {e(s["nome"])}: leitura atual</a><a class="pill" href="{pre}divulgacoes/">Todas as divulgações</a><a class="pill" href="{FEED_URL}">RSS</a></p>
</article>
""" + RODAPE)


RODAPE = """
</main>
<footer>Leituras calculadas pelo Observatório de Taxas com as séries do SGS do Banco Central, sem alterar os
valores. Cada divulgação fica publicada como foi registrada; revisões viram registros novos. Conteúdo informativo.
</footer>
</div></body></html>
"""


def hub(pubs: list[dict]) -> str:
    url = f"{BASE_URL}/divulgacoes/"
    t = "Divulgações: leituras de cada nova competência"
    desc = ("Leituras permanentes de cada nova competência dos indicadores acompanhados pelo Observatório de Taxas, "
            "com a conta mês a mês, a versão dos dados e as revisões. Também em RSS.")
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Divulgações", url)])
    topo = head(t, desc, url, jsonld_script({"@context": "https://schema.org", **crumb_ld}), crumb_html,
                []).replace("</style>", CSS + "</style>", 1)
    itens = "".join(
        f'<li><a href="{p["url"]}">{e(titulo(p))}</a> <span class="mut">· registrado em '
        f'{e(quando(p["registrado_em"]))}</span></li>' for p in ordenadas(pubs))
    vazio = "<p>Nenhuma divulgação registrada ainda.</p>" if not pubs else ""
    return (topo + f"""<h1>Divulgações</h1>
<p class="lead">Cada nova competência de um indicador acompanhado ganha uma leitura permanente: os números, a conta
mês a mês e a versão dos dados. Quando o produtor revisa um valor, a leitura revisada vira um registro novo, e a
anterior continua aqui.</p>
<p><a class="pill" href="{FEED_URL}">Assinar o RSS</a></p>
{vazio}<ul class="lista-div">{itens}</ul>
""" + RODAPE)


def registro_da_leitura(pubs: list[dict], serie: str, lt: dict) -> dict | None:
    """O registro permanente que guarda exatamente esta leitura (mesma
    competência e mesmas entradas), se já existir."""
    iguais = [p for p in pubs if p["serie"] == serie and p["competencia"] == lt["competencia"]
              and p["leitura"]["entradas"] == lt["entradas"]]
    return max(iguais, key=lambda p: p["revisao"]) if iguais else None


def ordenadas(pubs: list[dict]) -> list[dict]:
    return sorted(pubs, key=lambda p: (p["registrado_em"], p["competencia"], p["revisao"], p["id"]), reverse=True)


# ── RSS ───────────────────────────────────────────────────────────────────

def _rfc822(iso: str) -> str:
    return format_datetime(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc), usegmt=True)


def resumo(reg: dict) -> str:
    lt, s = reg["leitura"], SERIES[reg["serie"]]
    rot = "Competência" if s["leitura"] == "mensal" else "Período"
    partes = [f"{rot}: {periodo(lt)}."] + lt["frases"][:2]
    if reg["revisa"]:
        alt = "; ".join(f"{rotulo_entrada(reg['serie'], a['competencia'])}: {fmt_entrada(reg['serie'], a['antes'])} → "
                        f"{fmt_entrada(reg['serie'], a['depois'])}" for a in reg["revisa"]["alteracoes"])
        partes.insert(1, f"Revisão de dados: {alt}.")
    partes.append(f"Fonte: {s['produtor']}, via SGS {', '.join(map(str, s['series']))} do Banco Central. "
                  f"Versão dos dados: {reg['versao_dados']['curto']}.")
    return " ".join(partes)


def feed(pubs: list[dict]) -> bytes:
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    for tag, txt in (("title", "Observatório de Taxas — divulgações"), ("link", f"{BASE_URL}/divulgacoes/"),
                     ("description", "Leitura de cada nova competência dos indicadores acompanhados, com a conta e a "
                                     "versão dos dados."), ("language", "pt-BR")):
        ET.SubElement(ch, tag).text = txt
    ET.SubElement(ch, "{http://www.w3.org/2005/Atom}link",
                  {"href": FEED_URL, "rel": "self", "type": "application/rss+xml"})
    itens = ordenadas(pubs)[:ITENS_NO_FEED]
    if itens:
        ET.SubElement(ch, "lastBuildDate").text = _rfc822(itens[0]["registrado_em"])
    for p in itens:
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = titulo(p)
        ET.SubElement(it, "link").text = p["url"]
        ET.SubElement(it, "guid", {"isPermaLink": "true"}).text = p["url"]
        ET.SubElement(it, "pubDate").text = _rfc822(p["registrado_em"])
        ET.SubElement(it, "category").text = SERIES[p["serie"]]["nome"]
        ET.SubElement(it, "description").text = resumo(p)
    ET.indent(rss)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="utf-8") + b"\n"


# ── principal ─────────────────────────────────────────────────────────────

def gerar(arquivo: dict) -> None:
    pubs = arquivo.get("publicacoes", [])
    _POR_ID.clear()
    _POR_ID.update({p["id"]: p["url"] for p in pubs})
    for p in pubs:
        c = caminho(p)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(pagina(p, pubs), encoding="utf-8")
        (c.parent / "dados.csv").write_bytes(csv_registro(p).encode("utf-8"))
        (c.parent / "grafico.svg").write_text(svg_registro(p), encoding="utf-8")
    (DOCS / "divulgacoes").mkdir(exist_ok=True)
    (DOCS / "divulgacoes" / "index.html").write_text(hub(pubs), encoding="utf-8")
    (DOCS / "feed.xml").write_bytes(feed(pubs))


# ── citar, baixar e acompanhar (Entrega 3) ────────────────────────────────
#
# Decisão: uma citação aponta para o REGISTRO, não para "a série no commit X
# refeita pela regra de hoje". O registro (data/publicacoes.json) já guarda o
# resultado e a memória de cálculo da regra que o produziu, e a página, o CSV e
# a imagem são gerados só dele. Assim a citação continua dando o mesmo número
# depois de uma revisão dos dados ou de uma regra nova, sem o site precisar
# guardar versões antigas do código. O link de acompanhamento leva à ficha do
# indicador, que recalcula com os dados de agora.

TRANSFORMACAO = {
    "mensal": "acumulado em 12 meses = (1 + taxa₁ ÷ 100) × … × (1 + taxa₁₂ ÷ 100) − 1, na janela atual e na anterior",
    "cdi": "acumulado no período = produto de (1 + taxa do mês ÷ 100) − 1; taxa real = (1 + CDI) ÷ (1 + IPCA) − 1",
    "ptax": "variação em reais = cotação − cotação de comparação; em percentual = cotação ÷ cotação de comparação − 1",
}
UNIDADE = {"mensal": "% (variação no mês e acumulado)", "cdi": "% no mês e no período",
           "ptax": "R$ por dólar (PTAX de venda)"}


def url_ficha(reg: dict) -> str:
    return f"{BASE_URL}/{SERIES[reg['serie']]['ficha']}#leitura"


def citacao(reg: dict) -> str:
    """Texto de citação: série, recorte, transformação, versão e regra."""
    lt, s = reg["leitura"], SERIES[reg["serie"]]
    return (f"Observatório de Taxas. {titulo(reg)}. {s['nome']} ({s['produtor']}), SGS "
            f"{', '.join(map(str, s['series']))}; recorte: {periodo(lt)}; transformação: "
            f"{TRANSFORMACAO[s['leitura']]}; dados do commit {reg['versao_dados']['sha']}; regra {lt['regra']}. "
            f"Disponível em: {reg['url']}")


def tabela_linhas(reg: dict) -> tuple[list[str], list[list[str]]]:
    """Cabeçalho e linhas da tabela da página, como texto, para o CSV."""
    lt = reg["leitura"]
    if lt["regra"].startswith("leitura-mensal"):
        cab = ["Competência", "Variação no mês (%)", "Fator do mês", "Janela atual", "Janela anterior", "Papel na troca"]
        lin = [[L.mes_txt(li["competencia"]), "" if li["valor"] is None else fmt_num(li["valor"]),
                "" if li["valor"] is None else fmt_num(1 + li["valor"] / 100, 6),
                "sim" if li["janela_atual"] else "", "sim" if li["janela_anterior"] else "", li["papel"]]
               for li in lt["linhas"]]
        lin.append(["Acumulado em 12 meses (%)", "", "",
                    "" if lt["acumulado_12m"] is None else fmt_num(lt["acumulado_12m"]),
                    "" if lt["acumulado_12m_anterior"] is None else fmt_num(lt["acumulado_12m_anterior"]), ""])
        return cab, lin
    cel = (lambda x: "" if x is None else fmt_num(x) if isinstance(x, float) else str(x))
    return list(lt["tabela"]["cab"]), [[cel(x) for x in li] for li in lt["tabela"]["linhas"]]


def _csv_celula(x: str) -> str:
    """Mesma regra do docs/calculos.js: ';' como separador e sem fórmula no Excel."""
    if x and x[0] in "=+-@\t\r" and not (x[0] == "-" and x[1:2].isdigit()):
        x = "'" + x
    return '"' + x.replace('"', '""') + '"' if any(c in x for c in ';"\n\r') else x


def csv_registro(reg: dict) -> str:
    lt, s = reg["leitura"], SERIES[reg["serie"]]
    meta = [
        ["Observatório de Taxas", titulo(reg)],
        ["Série", f"{s['nome']}, produzido por {s['produtor']}; SGS {', '.join(map(str, s['series']))}"],
        ["Recorte", periodo(lt)],
        ["Transformação", TRANSFORMACAO[s["leitura"]]],
        ["Unidade", UNIDADE[s["leitura"]]],
        ["Versão dos dados", reg["versao_dados"]["sha"]],
        ["Regra", lt["regra"]],
        ["Registrado em", reg["registrado_em"]],
        ["Citar (link permanente)", reg["url"]],
        ["Acompanhar (visão atualizada)", url_ficha(reg)],
        [],
    ]
    cab, lin = tabela_linhas(reg)
    linhas = meta + [cab] + lin
    return "\ufeff" + "\r\n".join(";".join(_csv_celula(c) for c in li) for li in linhas) + "\r\n"


def svg_registro(reg: dict) -> str:
    """Gráfico de barras do recorte, com título, fonte, versão e regra no próprio
    arquivo (continua compreensível depois de baixado)."""
    lt, s = reg["leitura"], SERIES[reg["serie"]]
    if lt["regra"].startswith("leitura-mensal"):
        rot = [li["competencia"][2:].replace("-", "/") for li in lt["linhas"]]
        series = [(f"{lt['nome']} no mês (%)", [li["valor"] for li in lt["linhas"]], "#1f5fa8")]
        destaque = {i: "#c0392b" if li["papel"] == "saiu da janela" else "#1e8449"
                    for i, li in enumerate(lt["linhas"]) if li["papel"]}
    elif lt["regra"].startswith("leitura-cdi"):
        ls = lt["tabela"]["linhas"]
        rot = [L.soma_mes(lt["inicio"], k)[2:].replace("-", "/") for k in range(len(ls))]
        series = [("CDI no mês (%)", [li[1] for li in ls], "#1f5fa8"), ("IPCA no mês (%)", [li[2] for li in ls], "#b9770e")]
        destaque = {}
    else:
        ls = lt["tabela"]["linhas"]
        rot = [li[0].split()[-1][:5] for li in ls]
        series = [("PTAX de venda (R$)", [float(li[2].replace(".", "").replace(",", ".")) for li in ls], "#1f5fa8")]
        destaque = {i: "#1e8449" for i, li in enumerate(ls) if li[1] == "encerrada"}
    W, H, ml, mr, mt, mb = 720, 340, 56, 16, 64, 84
    vals = [x for _, vs, _ in series for x in vs if x is not None]
    lo, hi = (min(vals + [0.0]), max(vals + [0.0])) if s["leitura"] != "ptax" else (min(vals) * 0.995, max(vals) * 1.002)
    if hi == lo:
        hi = lo + 1
    n, k = len(rot), len(series)
    larg = (W - ml - mr) / max(n, 1)
    y = (lambda x: mt + (hi - x) * (H - mt - mb) / (hi - lo))
    partes = [f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
              f'<text x="{ml}" y="22" font-size="14" font-weight="700" fill="#111">{e(titulo(reg))[:110]}</text>',
              f'<text x="{ml}" y="42" font-size="11" fill="#444">{e(periodo(lt))} · {e(UNIDADE[s["leitura"]])}</text>',
              f'<line x1="{ml}" x2="{W - mr}" y1="{y(max(lo, 0) if s["leitura"] != "ptax" else lo):.1f}" '
              f'y2="{y(max(lo, 0) if s["leitura"] != "ptax" else lo):.1f}" stroke="#888"/>']
    for marca in (lo, (lo + hi) / 2, hi):
        partes.append(f'<text x="{ml - 6}" y="{y(marca) + 4:.1f}" font-size="10" fill="#555" text-anchor="end">'
                      f'{e(fmt_num(marca, 2 if s["leitura"] != "ptax" else 4))}</text>')
    base = y(0) if s["leitura"] != "ptax" else y(lo)
    for i in range(n):
        for j, (_, vs, cor) in enumerate(series):
            x = vs[i]
            if x is None:
                continue
            bw = larg * 0.7 / k
            bx = ml + i * larg + larg * 0.15 + j * bw
            top, alt = (y(x), base - y(x)) if y(x) < base else (base, y(x) - base)
            partes.append(f'<rect x="{bx:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(alt, 0.5):.1f}" '
                          f'fill="{destaque.get(i, cor) if k == 1 else cor}"><title>{e(rot[i])}: '
                          f'{e(fmt_num(x, 4 if s["leitura"] == "ptax" else 2))}</title></rect>')
        partes.append(f'<text x="{ml + i * larg + larg / 2:.1f}" y="{H - mb + 16}" font-size="10" fill="#333" '
                      f'text-anchor="middle">{e(rot[i])}</text>')
    leg = " · ".join(nome for nome, _, _ in series)
    partes.append(f'<text x="{ml}" y="{H - 46}" font-size="10" fill="#333">{e(leg)}</text>')
    partes.append(f'<text x="{ml}" y="{H - 30}" font-size="10" fill="#555">Fonte: {e(s["produtor"])}, via SGS '
                  f'{e(", ".join(map(str, s["series"])))} do Banco Central · dados do commit '
                  f'{reg["versao_dados"]["curto"]} · regra {e(lt["regra"])}</text>')
    partes.append(f'<text x="{ml}" y="{H - 14}" font-size="10" fill="#555">{e(reg["url"])}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'font-family="Arial, Helvetica, sans-serif" role="img"><title>{e(titulo(reg))}</title>'
            + "".join(partes) + "</svg>\n")


def grafico_alt(reg: dict) -> str:
    lt = reg["leitura"]
    return f"Gráfico de barras: {titulo(reg)}. {periodo(lt)}. Valores na tabela da página."


def bloco_acoes(reg: dict | None, ficha: str, pre: str = "", h: str = "h2") -> str:
    """Acompanhar (visão atual, ficha) e citar (registro permanente), com o CSV e
    a imagem do recorte citado. Links comuns: funcionam sem JavaScript e pelo
    teclado."""
    seguir = (f'<p><a class="pill" href="{ficha}">Acompanhar este indicador</a> '
              '<span class="mut">abre a ficha, que se atualiza a cada coleta com dado novo.</span></p>')
    if not reg:
        return (f'<section class="card" aria-labelledby="usar-t"><{h} id="usar-t">Acompanhar e citar</{h}>{seguir}'
                '<p class="mut">Citar esta análise: o registro permanente ainda não existe para esta leitura.</p></section>')
    base = reg["url"]
    return (f'<section class="card" aria-labelledby="usar-t"><{h} id="usar-t">Acompanhar e citar</{h}>{seguir}'
            f'<p><a class="pill" href="{base}">Citar esta análise</a> <span class="mut">link permanente: '
            'continua mostrando este resultado, com estes dados e esta regra, mesmo depois de revisões.</span></p>'
            f'<p class="mut" id="citacao-{e(reg["id"])}">{e(citacao(reg))}</p>'
            f'<p><a class="pill" href="{base}dados.csv" download>Baixar CSV do recorte</a>'
            f'<a class="pill" href="{base}grafico.svg" download>Baixar imagem do gráfico (SVG)</a></p></section>')


def main() -> None:
    arquivo = ler(ARQUIVO, {"formato": 1, "publicacoes": []})
    if "--registrar" in sys.argv:
        versao = ler(VERSAO, {})
        if not versao.get("sha"):
            print("divulgacoes: sem versao.json; nada registrado.")
        elif not dados_conferem(versao):
            print(f"divulgacoes: os dados não são os do commit {versao['sha'][:7]}; nada registrado.")
        else:
            historicos = {c: load_history(c) for s in SERIES.values() for c in s["series"]}
            novos = registrar(arquivo, historicos, ler(MUDANCAS, {}), versao)
            for n in novos:
                print(f"divulgacoes: novo registro {n['id']}")
            if novos:
                grava_json(ARQUIVO, arquivo)
    grava_json(ESPELHO, arquivo)
    gerar(arquivo)
    print(f"divulgacoes: {len(arquivo.get('publicacoes', []))} registro(s), páginas e feed.xml gerados.")


if __name__ == "__main__":
    main()
