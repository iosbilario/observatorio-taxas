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
.lista-div li{margin:.45rem 0}
"""

# Séries com divulgação. "leitura" escolhe a função de scripts/leituras.py.
SERIES: dict[str, dict] = {
    "ipca": {"codigo": 433, "nome": "IPCA", "leitura": "mensal", "ficha": "indicadores/ipca/",
             "produtor": "IBGE", "reajuste": "ipca"},
}


# ── arquivo ───────────────────────────────────────────────────────────────

def ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def grava_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def leitura_de(chave: str, historicos: dict[int, list[dict]], competencia: str | None = None, **kw) -> dict:
    s = SERIES[chave]
    if s["leitura"] == "mensal":
        return L.leitura_mensal(s["codigo"], s["nome"], historicos[s["codigo"]], competencia)
    raise ValueError(s["leitura"])


def url_registro(chave: str, competencia: str, revisao: int) -> str:
    return f"{BASE_URL}/divulgacoes/{chave}/{competencia}/" + (f"revisao-{revisao}/" if revisao else "")


def _data_sgs(competencia: str) -> str:
    return f"01/{competencia[5:7]}/{competencia[:4]}"


def identificado_em(mudancas: dict, codigo: int, competencias: list[str], primeira: bool) -> dict | None:
    """Coleta (mudancas.json) que trouxe a observação nova ou a revisão de uma
    das competências: a mais antiga para uma publicação nova, a mais recente
    para uma revisão."""
    datas = {_data_sgs(c) for c in competencias}
    achadas = []
    for col in mudancas.get("coletas", []):
        itens = col.get("novas", []) + col.get("revisoes", [])
        if any(int(i.get("codigo", 0)) == codigo and i.get("data") in datas for i in itens):
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
    for chave, s in SERIES.items():
        if not historicos.get(s["codigo"]):
            continue
        atual = leitura_de(chave, historicos)
        da_serie = [p for p in pubs if p["serie"] == chave]
        competencias = sorted({p["competencia"] for p in da_serie} | {atual["competencia"]})
        for comp in competencias:
            lt = atual if comp == atual["competencia"] else leitura_de(chave, historicos, comp)
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
            alvo = [comp] if not revisa else [a["competencia"] for a in revisa["alteracoes"]]
            reg = {
                "id": f"{chave}-{comp}" + (f"-r{rev}" if rev else ""), "serie": chave, "codigo": s["codigo"],
                "competencia": comp, "revisao": rev, "url": url_registro(chave, comp, rev),
                "registrado_em": versao["data"], "versao_dados": {"sha": versao["sha"], "curto": versao["sha"][:7]},
                "identificado": identificado_em(mudancas, s["codigo"], alvo, primeira=not revisa),
                "divulgacao_oficial": None, "carga_inicial": not pubs and not novos, "revisa": revisa,
                "leitura": lt,
            }
            novos.append(reg)
    pubs.extend(novos)
    return novos


def dados_conferem(versao: dict, raiz: Path = ROOT) -> bool:
    """Os arquivos das séries são os do commit de versao.json? (git diff)"""
    arqs = [f"data/{s['codigo']}_history.json" for s in SERIES.values()]
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


def bloco_revisao(reg: dict) -> str:
    r = reg["revisa"]
    if not r:
        return ""
    sha_a, sha_b = r["versao_anterior"]["sha"], reg["versao_dados"]["sha"]
    cod = reg["codigo"]
    linhas = "".join(f"<tr><td>{e(L.mes_txt(a['competencia']))}</td><td>{v(a['antes'])}</td><td>{v(a['depois'])}</td></tr>"
                     for a in r["alteracoes"])
    anterior = r["id"]
    return (f'<section class="card" aria-labelledby="rev-t"><h2 id="rev-t">O que esta revisão mudou</h2>'
            f'<p>Esta leitura substitui a <a href="{url_por_id(anterior)}">anterior</a>, que continua publicada. '
            "Valores das competências que mudaram:</p>"
            '<div class="tabela-rolagem" role="region" aria-labelledby="rev-t" tabindex="0"><table><thead><tr>'
            '<th scope="col">Competência</th><th scope="col">Valor anterior</th><th scope="col">Valor revisado</th>'
            f"</tr></thead><tbody>{linhas}</tbody></table></div>"
            f'<p class="mut">Série na <a href="{RAW}/{sha_a}/data/{cod}_history.json">versão anterior ({sha_a[:7]})</a> '
            f'e na <a href="{RAW}/{sha_b}/data/{cod}_history.json">versão revisada ({sha_b[:7]})</a> · '
            f'<a href="{REPO_URL}/compare/{sha_a}...{sha_b}">comparar as versões no GitHub</a>.</p></section>')


_POR_ID: dict[str, str] = {}


def url_por_id(i: str) -> str:
    return _POR_ID.get(i, f"{BASE_URL}/divulgacoes/")


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
    curto = (f"{lt['nome']} de {L.mes_txt(lt['competencia'])}"
             + (f", revisão {reg['revisao']}" if reg["revisao"] else "") + ": leitura mensal e acumulado")
    topo = head(curto, desc, url, ld, crumb_html, []).replace("</style>", CSS + "</style>", 1)
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
                 "não registrado: esta é a primeira leitura do arquivo de divulgações, criado depois de a "
                 "competência chegar ao Observatório" if reg.get("carga_inicial") else "não registrado")
    kpis = "".join(f'<div class="kpi"><span>{e(r)}</span><b>{e(x)}</b></div>' for r, x in resumo_mensal(lt))
    nota = f'<p class="mut">{e(lt["nota"])}</p>' if lt.get("nota") else ""
    return (topo + f"""<article>
<h1>{e(t)}</h1>
{aviso}
<div class="kpis">{kpis}</div>
<section class="card" aria-labelledby="leit-t"><h2 id="leit-t">Leitura</h2>
{"".join(f"<p>{e(f)}</p>" for f in lt["frases"])}
{nota}
</section>
{bloco_revisao(reg)}
<section class="card" aria-labelledby="conta-t"><h2 id="conta-t">A conta, mês a mês</h2>
<p>Janela atual: {e(L.mes_txt(lt["janela"][0]))} a {e(L.mes_txt(lt["janela"][1]))}. Janela anterior:
{e(L.mes_txt(lt["janela_anterior"][0]))} a {e(L.mes_txt(lt["janela_anterior"][1]))}.</p>
{tabela_mensal(lt, reg["serie"], pre)}
</section>
<section class="card" aria-labelledby="proc-t"><h2 id="proc-t">Fonte, datas e versão</h2>
<dl class="ficha">
<dt>Indicador</dt><dd>{e(lt["nome"])}, produzido pelo {e(s["produtor"])}</dd>
<dt>Obtido em</dt><dd>SGS do Banco Central, <a href="https://api.bcb.gov.br/dados/serie/bcdata.sgs.{reg["codigo"]}/dados?formato=json">série {reg["codigo"]}</a></dd>
<dt>Competência</dt><dd><time datetime="{lt["competencia"]}">{e(L.mes_txt(lt["competencia"]))}</time></dd>
<dt>Identificado pelo Observatório</dt><dd>{ident_txt}</dd>
<dt>Divulgação oficial</dt><dd>não informada: o SGS não traz a data de divulgação do {e(s["produtor"])}, e o Observatório não a deduz da hora da coleta</dd>
<dt>Registrado em</dt><dd>{e(quando(reg["registrado_em"]))} (data do commit dos dados)</dd>
<dt>Versão dos dados</dt><dd>commit <a href="{REPO_URL}/commit/{sha}">{sha[:7]}</a> · <a href="{RAW}/{sha}/data/{reg["codigo"]}_history.json">série nessa versão (JSON)</a></dd>
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
    partes = [f"Competência: {L.mes_txt(lt['competencia'])}."] + lt["frases"][:2]
    if reg["revisa"]:
        alt = "; ".join(f"{L.mes_txt(a['competencia'])}: {v(a['antes'])} → {v(a['depois'])}"
                        for a in reg["revisa"]["alteracoes"])
        partes.insert(1, f"Revisão de dados: {alt}.")
    partes.append(f"Fonte: {s['produtor']}, via SGS {reg['codigo']} do Banco Central. "
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
    (DOCS / "divulgacoes").mkdir(exist_ok=True)
    (DOCS / "divulgacoes" / "index.html").write_text(hub(pubs), encoding="utf-8")
    (DOCS / "feed.xml").write_bytes(feed(pubs))


def main() -> None:
    arquivo = ler(ARQUIVO, {"formato": 1, "publicacoes": []})
    if "--registrar" in sys.argv:
        versao = ler(VERSAO, {})
        if not versao.get("sha"):
            print("divulgacoes: sem versao.json; nada registrado.")
        elif not dados_conferem(versao):
            print(f"divulgacoes: os dados não são os do commit {versao['sha'][:7]}; nada registrado.")
        else:
            historicos = {s["codigo"]: load_history(s["codigo"]) for s in SERIES.values()}
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
