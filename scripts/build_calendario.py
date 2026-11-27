#!/usr/bin/env python3
"""
build_calendario.py — Calendário de divulgações (/calendario/).

Entradas (versionadas em data/):
  calendario_fontes.json  agendas oficiais estruturadas (fetch_calendario.py):
                          IBGE (IPCA e IPCA-15) e decisões já comunicadas do Copom
  calendario_copom.json   reuniões futuras do Copom, conferidas à mão nas notas
                          oficiais do BC (sem interface estável)
  calendario.json         estado anterior (para preservar identificadores e as
                          datas antigas de um evento reagendado)

Para cada evento, separa: a competência ou a reunião; a data prevista na
agenda oficial; o horário, só quando a fonte o confirma; a data oficial de
divulgação, só quando houver fonte; e a data em que o Observatório detectou o
dado (mudancas.json ou o histórico da série). Um evento só vira "publicado"
quando o dado aparece no Observatório, nunca porque a data chegou. No Copom,
reunião, comunicação da decisão e início da vigência da meta são datas
diferentes; uma decisão que mantém a meta também é uma decisão.

O endereço /calendario/<id>/ não muda quando o evento é reagendado ou muda de
estado: o id é a família e a competência ("ipca-2026-11") ou a reunião
("copom-2026-8", ano e ordem no calendário anual).

"Hoje" é a data do commit dos dados (versao.json), para a mesma entrada dar a
mesma página.

    python scripts/build_calendario.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_ferramentas import e, head  # noqa: E402
from build_pages import MESES, jsonld_script, migalhas  # noqa: E402

DATA = ROOT / "data"
DOCS = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
BRT = timezone(timedelta(hours=-3))
INICIO = "2026-01"          # primeiro mês com eventos no site (o arquivo do IBGE vai até 2017)

FAMILIAS = {
    "ipca": {"nome": "IPCA", "codigo": 433, "ficha": "indicadores/ipca/", "produtor": "IBGE",
             "pagina_oficial": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html"},
    "ipca15": {"nome": "IPCA-15", "codigo": 7478, "ficha": "indicadores/ipca-15/", "produtor": "IBGE",
               "pagina_oficial": "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9260-indice-nacional-de-precos-ao-consumidor-amplo-15.html"},
    "copom": {"nome": "Copom (Meta Selic)", "codigo": 432, "ficha": "indicadores/meta-selic/", "produtor": "Banco Central do Brasil",
              "pagina_oficial": "https://www.bcb.gov.br/controleinflacao/comunicadoscopom"},
}
CSS = """
.cal-lista{list-style:none;margin:0;padding:0}
.cal-lista li{border-bottom:1px solid var(--linha);padding:.7rem 0}
.cal-lista b{font-family:"Fraunces",Georgia,serif}
span.estado{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;
 border:1px solid var(--linha);border-radius:999px;padding:1px 8px;margin-left:.4rem;white-space:nowrap}
"""


def ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def hoje_dos_dados() -> date:
    v = ler(DOCS / "data" / "versao.json", {})
    if not v.get("data"):
        return date(1970, 1, 1)
    return datetime.fromisoformat(v["data"].replace("Z", "+00:00")).astimezone(BRT).date()


def mes_txt(comp: str) -> str:
    return f"{MESES[int(comp[5:7]) - 1]} de {comp[:4]}"


def dia_txt(iso: str | None) -> str:
    return "" if not iso else datetime.fromisoformat(iso[:10]).strftime("%d/%m/%Y")


def _hist(codigo: int) -> list[dict]:
    return ler(DATA / f"{codigo}_history.json", [])


def deteccao(mudancas: dict, codigo: int, data_sgs: str) -> str | None:
    """Hora da coleta (mudancas.json) que trouxe a observação pela primeira vez."""
    achadas = [c["gerado_em"] for c in mudancas.get("coletas", [])
               if any(int(n.get("codigo", 0)) == codigo and n.get("data") == data_sgs for n in c.get("novas", []))]
    return min(achadas) if achadas else None


# ── eventos ───────────────────────────────────────────────────────────────

def eventos(fontes: dict, copom: dict, historicos: dict[int, list[dict]], mudancas: dict,
            publicacoes: list[dict], anterior: dict, hoje: date) -> list[dict]:
    antes = {ev["id"]: ev for ev in anterior.get("eventos", [])}
    pubs = {(p["serie"], p["competencia"]): p for p in publicacoes if not p["revisao"]}
    saida = []

    # IBGE: IPCA e IPCA-15
    conf_ibge = (fontes.get("ibge") or {}).get("conferido_em")
    for it in (fontes.get("ibge") or {}).get("itens", []):
        fam, comp = it["familia"], it["competencia"]
        if comp < INICIO:
            continue
        f = FAMILIAS[fam]
        prevista = datetime.strptime(it["data_divulgacao"], "%d/%m/%Y %H:%M:%S").date().isoformat()
        data_sgs = f"01/{comp[5:7]}/{comp[:4]}"
        tem = any(p["data"] == data_sgs for p in historicos.get(f["codigo"], []))
        detectado = deteccao(mudancas, f["codigo"], data_sgs) if tem else None
        pub = pubs.get(("ipca", comp)) if fam == "ipca" else None
        saida.append({
            "id": f"{fam}-{comp}", "familia": fam, "titulo": f"{f['nome']} de {mes_txt(comp)}",
            "competencia": comp, "data_prevista": prevista, "horario": None,
            "horario_nota": "A agenda do IBGE traz 12:00:00 em todos os itens; o horário não é tratado como confirmado.",
            "divulgacao_oficial": None,
            "publicado": tem, "detectado_em": detectado,
            "analise": pub["url"] if pub else None,
            "fonte": {"nome": "Calendário de divulgações do IBGE (API)", "url": (fontes.get("ibge") or {}).get("url"),
                      "conferido_em": conf_ibge, "id_fonte": it["id_ibge"]},
        })

    # Copom: reuniões do calendário editorial + decisões comunicadas (API do BC)
    decisoes = {d["data"]: d for d in (fontes.get("copom_decisoes") or {}).get("itens", [])}
    conf_dec = (fontes.get("copom_decisoes") or {}).get("conferido_em")
    meta = historicos.get(432, [])
    for r in copom.get("reunioes", []):
        ident = f"copom-{r['ano']}-{r['ordem']}"
        dia2 = r["dias"][-1]
        dec = decisoes.get(dia2)
        vig = None
        if dec:
            depois = [p for p in meta if datetime.strptime(p["data"], "%d/%m/%Y").date().isoformat() > dia2]
            if depois:
                vig = {"inicio": datetime.strptime(depois[0]["data"], "%d/%m/%Y").date().isoformat(),
                       "meta": float(depois[0]["valor"]),
                       "detectado_em": deteccao(mudancas, 432, depois[0]["data"])}
        saida.append({
            "id": ident, "familia": "copom",
            "titulo": (f"Copom, {dec['reuniao']}ª reunião" if dec else f"Copom, {r['ordem']}ª reunião de {r['ano']}"),
            "reuniao": {"ano": r["ano"], "ordem": r["ordem"], "numero": dec["reuniao"] if dec else None,
                        "dias": r["dias"]},
            "data_prevista": dia2, "horario": None,
            "horario_nota": "O comunicado da decisão sai no segundo dia da reunião; a fonte usada não confirma o horário.",
            "divulgacao_oficial": dia2 if dec else None,
            "decisao": dec["titulo"] if dec else None,
            "publicado": bool(dec), "detectado_em": None, "vigencia": vig, "analise": None,
            "fonte": {"nome": "Calendário de reuniões (notas oficiais do BC) e comunicados do Copom (API do BC)",
                      "url": next((f["url"] for f in copom.get("fontes", []) if f["ano"] == r["ano"]), None),
                      "url_decisoes": (fontes.get("copom_decisoes") or {}).get("url"),
                      "conferido_em": copom.get("conferido_em"), "decisoes_conferidas_em": conf_dec},
        })

    # Reagendamento: guarda as datas previstas anteriores do mesmo id.
    for ev in saida:
        velho = antes.get(ev["id"])
        datas = list(velho.get("datas_anteriores", [])) if velho else []
        if velho and velho["data_prevista"] != ev["data_prevista"] and velho["data_prevista"] not in datas:
            datas.append(velho["data_prevista"])
        ev["datas_anteriores"] = datas
        ev["estado"] = ("publicado" if ev["publicado"] else
                        "aguardando" if ev["data_prevista"] < hoje.isoformat() else "previsto")
    return sorted(saida, key=lambda ev: (ev["data_prevista"], ev["id"]))


def cobertura(fontes: dict, copom: dict) -> dict:
    ibge = (fontes.get("ibge") or {}).get("itens", [])
    fim = {}
    for fam in ("ipca", "ipca15"):
        ds = [datetime.strptime(i["data_divulgacao"], "%d/%m/%Y %H:%M:%S").date().isoformat()
              for i in ibge if i["familia"] == fam]
        fim[fam] = max(ds) if ds else None
    fim["copom"] = (copom.get("cobertura") or {}).get("fim")
    return fim


# ── páginas ───────────────────────────────────────────────────────────────

ESTADO_TXT = {"previsto": "previsto", "aguardando": "data passou, dado ainda não registrado", "publicado": "publicado"}


def resumo_evento(ev: dict) -> str:
    est = ESTADO_TXT[ev["estado"]]
    if ev["familia"] == "copom" and ev["decisao"]:
        est = "decisão comunicada"
    return f'<b>{e(ev["titulo"])}</b> · {e(dia_txt(ev["data_prevista"]))} <span class="estado">{e(est)}</span>'


def pagina_evento(ev: dict, cob: dict, hoje: date) -> str:
    f = FAMILIAS[ev["familia"]]
    url = f"{BASE_URL}/calendario/{ev['id']}/"
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Calendário", f"{BASE_URL}/calendario/"),
                                     (ev["titulo"], url)])
    desc = f"{ev['titulo']}: data prevista {dia_txt(ev['data_prevista'])}, fonte oficial e situação no Observatório de Taxas."
    topo = head(f"{ev['titulo']}: calendário de divulgação", desc, url,
                jsonld_script({"@context": "https://schema.org", **crumb_ld}), crumb_html, []).replace("</style>", CSS + "</style>", 1)
    linhas = []
    if ev["familia"] == "copom":
        r = ev["reuniao"]
        linhas.append(("Reunião", f"{r['numero']}ª reunião" if r["numero"] else f"{r['ordem']}ª reunião ordinária de {r['ano']}"))
        linhas.append(("Dias da reunião", " e ".join(dia_txt(d) for d in r["dias"])))
        linhas.append(("Comunicação da decisão", dia_txt(ev["divulgacao_oficial"]) + " (comunicado oficial)"
                       if ev["divulgacao_oficial"] else f"prevista para {dia_txt(ev['data_prevista'])}, segundo dia da reunião"))
        linhas.append(("Decisão", ev["decisao"] or "ainda não comunicada na fonte consultada"))
        v = ev["vigencia"]
        linhas.append(("Vigência da meta", f"a partir de {dia_txt(v['inicio'])}, {str(v['meta']).replace('.', ',')}% ao ano, "
                       "registrada pelo Observatório na série 432" if v else "ainda não registrada na série 432"))
    else:
        linhas.append(("Competência", mes_txt(ev["competencia"])))
        linhas.append(("Data prevista", dia_txt(ev["data_prevista"]) + " (agenda oficial do IBGE)"))
        linhas.append(("Data oficial de divulgação", "não informada pela fonte usada"))
        linhas.append(("Detectado pelo Observatório",
                       (datetime.fromisoformat(ev["detectado_em"]).strftime("%d/%m/%Y às %H:%M") + " (coleta do SGS)")
                       if ev["detectado_em"] else ("registrado antes do início do registro de coletas"
                                                   if ev["publicado"] else "ainda não")))
    linhas.append(("Horário", ev["horario"] or "não confirmado (" + ev["horario_nota"] + ")"))
    if ev["datas_anteriores"]:
        linhas.append(("Reagendado", "data prevista anterior: " + ", ".join(dia_txt(d) for d in ev["datas_anteriores"])))
    linhas.append(("Situação no Observatório", ESTADO_TXT[ev["estado"]] if not (ev["familia"] == "copom" and ev["decisao"])
                   else "decisão comunicada"))
    fonte = ev["fonte"]
    linhas.append(("Fonte", f'<a href="{e(fonte["url"])}">{e(fonte["nome"])}</a>' + (
        f' · <a href="{e(fonte["url_decisoes"])}">comunicados</a>' if fonte.get("url_decisoes") else "")
        + f" · conferida em {e(dia_txt(fonte['conferido_em']))}"))
    dl = "".join(f"<dt>{e(a)}</dt><dd>{b if a == 'Fonte' else e(b)}</dd>" for a, b in linhas)
    links = [f'<a class="pill" href="../../{f["ficha"]}">Ficha do {e(f["nome"].split(" (")[0])}</a>',
             f'<a class="pill" href="{e(f["pagina_oficial"])}">Página oficial</a>',
             '<a class="pill" href="../">Calendário completo</a>']
    if ev["analise"]:
        links.insert(0, f'<a class="pill" href="{ev["analise"]}">Análise publicada</a>')
    aviso = ""
    fim = cob.get(ev["familia"])
    if fim and fim < hoje.isoformat():
        aviso = (f'<p class="aviso">A agenda verificada desta família termina em {e(dia_txt(fim))}. Eventos depois disso '
                 "ainda não constam da fonte consultada.</p>")
    return topo + f"""<article>
<h1>{e(ev["titulo"])}</h1>
{aviso}<dl class="ficha">{dl}</dl>
<p>{"".join(links)}</p>
<p class="mut">O Observatório só marca um evento como publicado quando o dado aparece na fonte que ele coleta (SGS do
Banco Central) ou, no Copom, quando o comunicado oficial da decisão existe. A data chegar não basta.</p>
</article>
</main><footer>Agenda: IBGE e Banco Central do Brasil. Endereço estável: {e(url)}</footer></div></body></html>
"""


def hub(evs: list[dict], cob: dict, hoje: date, fontes: dict, copom: dict) -> str:
    url = f"{BASE_URL}/calendario/"
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Calendário", url)])
    topo = head("Calendário de divulgações: IPCA, IPCA-15 e Copom", "Próximas divulgações do IPCA e do IPCA-15 (IBGE) e "
                "reuniões do Copom, com a fonte oficial e a situação no Observatório de Taxas.", url,
                jsonld_script({"@context": "https://schema.org", **crumb_ld}), crumb_html, []).replace("</style>", CSS + "</style>", 1)
    prox = [ev for ev in evs if ev["data_prevista"] >= hoje.isoformat()]
    pass_ = [ev for ev in evs if ev["data_prevista"] < hoje.isoformat()][::-1]
    li = lambda ev: f'<li><a href="{ev["id"]}/">{resumo_evento(ev)}</a></li>'  # noqa: E731
    cobs = "; ".join(f"{FAMILIAS[k]['nome']}: até {dia_txt(v)}" for k, v in cob.items() if v)
    conf = (f"IBGE conferido em {dia_txt((fontes.get('ibge') or {}).get('conferido_em'))}; "
            f"reuniões do Copom conferidas em {dia_txt(copom.get('conferido_em'))}; decisões do Copom conferidas em "
            f"{dia_txt((fontes.get('copom_decisoes') or {}).get('conferido_em'))}")
    return topo + f"""<h1>Calendário de divulgações</h1>
<p class="lead">As próximas divulgações do IPCA e do IPCA-15 (IBGE) e as reuniões do Copom (Banco Central), com o que
o Observatório já registrou de cada uma.</p>
<p class="mut">Cobertura verificada: {e(cobs)}. Conferência das fontes: {e(conf)}. Situação calculada com os dados de
{e(hoje.strftime('%d/%m/%Y'))}.</p>
<h2>Próximas</h2><ul class="cal-lista">{"".join(li(ev) for ev in prox) or "<li>Nenhum evento futuro na agenda verificada.</li>"}</ul>
<h2>Já passaram</h2><ul class="cal-lista">{"".join(li(ev) for ev in pass_)}</ul>
<p class="mut">Como a agenda é mantida: desenvolvimento/CALENDARIO.md no repositório.</p>
</main><footer>Agenda: IBGE (API do calendário de divulgações) e Banco Central do Brasil (notas oficiais e comunicados do
Copom).</footer></div></body></html>
"""


def bloco_proximos(evs: list[dict], hoje: date, pre: str = "", n: int = 4) -> str:
    prox = [ev for ev in evs if ev["data_prevista"] >= hoje.isoformat()][:n]
    itens = "".join(f'<li><a href="{pre}calendario/{ev["id"]}/">{resumo_evento(ev)}</a></li>' for ev in prox)
    return (f'<ul class="cal-lista">{itens or "<li>Nenhum evento futuro na agenda verificada.</li>"}</ul>'
            f'<p><a href="{pre}calendario/">Calendário completo</a></p>')


def proximo_da_familia(evs: list[dict], familia: str, hoje: date) -> dict | None:
    return next((ev for ev in evs if ev["familia"] == familia and ev["data_prevista"] >= hoje.isoformat()), None)


def carregar() -> tuple[list[dict], dict, date, dict, dict]:
    fontes, copom = ler(DATA / "calendario_fontes.json", {}), ler(DATA / "calendario_copom.json", {})
    historicos = {f["codigo"]: _hist(f["codigo"]) for f in FAMILIAS.values()}
    hoje = hoje_dos_dados()
    evs = eventos(fontes, copom, historicos, ler(DATA / "mudancas.json", {}),
                  ler(DATA / "publicacoes.json", {}).get("publicacoes", []), ler(DATA / "calendario.json", {}), hoje)
    return evs, cobertura(fontes, copom), hoje, fontes, copom


def main() -> None:
    evs, cob, hoje, fontes, copom = carregar()
    estado = {"eventos": evs, "cobertura": cob}
    (DATA / "calendario.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")
    for ev in evs:
        d = DOCS / "calendario" / ev["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(pagina_evento(ev, cob, hoje), encoding="utf-8")
    (DOCS / "calendario" / "index.html").write_text(hub(evs, cob, hoje, fontes, copom), encoding="utf-8")
    print(f"calendario: {len(evs)} eventos.")


if __name__ == "__main__":
    main()
