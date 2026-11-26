#!/usr/bin/env python3
"""
build_mudancas.py — Página estática /mudancas/: "O que mudou nesta coleta?".

Lê data/mudancas.json, que o fetch.py grava a cada coleta que publica dados
(no máximo as últimas 30), e mostra a mais recente separando:

  - revisões: data que já estava publicada e mudou de valor (o SGS reescreveu);
  - observações novas: data que ainda não existia.

Cada linha traz indicador, referência (competência, cotação etc., por
tempo_series.py), valor anterior e novo, e o link para o diff do arquivo no
commit da coleta. O navegador não consulta o histórico do Git: tudo o que a
página mostra está no HTML. O único pedido opcional é a hora da última
verificação (execução do monitor no GitHub Actions), feito por mudancas.js;
sem ele a página continua completa.

Sem mudancas.json (primeira publicação, antes de qualquer coleta registrada)
a página diz que ainda não há base anterior para comparar.

O menu e o rodapé entram por sync_nav.py; o sitemap, por render_index.py.

    python scripts/build_mudancas.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_ferramentas import CSP, e, head  # noqa: E402
from build_pages import jsonld_script, migalhas  # noqa: E402
from tempo_series import classificar, explicacao_tipo, referencia, rotulo_tipo  # noqa: E402

DOCS = ROOT / "docs"
SAIDA = DOCS / "mudancas" / "index.html"
FONTE = ROOT / "data" / "mudancas.json"
VERSAO = DOCS / "data" / "versao.json"
BASE_URL = "https://observatoriodetaxas.tec.br"
URL = f"{BASE_URL}/mudancas/"
REPO = "iosbilario/observatorio-taxas"
REPO_URL = f"https://github.com/{REPO}"
CSP_PAGINA = CSP.replace("connect-src 'self'", "connect-src 'self' https://api.github.com")

CSS_PAGINA = """
.tabela-rolagem{overflow-x:auto;margin:.4rem 0 1rem}
.tabela-rolagem:focus-visible{outline:2px solid var(--carimbo);outline-offset:2px}
.tabela-rolagem table{min-width:520px}
.estado{border-left:3px solid var(--carimbo);padding:.2rem 0 .2rem .9rem;margin:1rem 0}
.estado p{margin:.3rem 0}
.coletas li{margin:.35rem 0}
"""


def le(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def valor(v) -> str:
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        return str(v)
    return f"{x:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def quando(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return d.strftime("%d/%m/%Y às %H:%M") + " (horário de Brasília)"


def link_diff(coleta: dict, codigo) -> str:
    """Diff do arquivo da série no commit da coleta. Antes de o commit existir
    (o versao_dados.py o preenche no mesmo job), o histórico do arquivo."""
    arq = f"data/{codigo}_history.json"
    if coleta.get("commit"):
        ancora = hashlib.sha256(arq.encode()).hexdigest()
        return f"{REPO_URL}/commit/{coleta['commit']}#diff-{ancora}"
    return f"{REPO_URL}/commits/main/{arq}"


def tabela(titulo_id: str, legenda: str, cab: list[str], linhas: list[list[str]]) -> str:
    th = "".join(f'<th scope="col">{c}</th>' for c in cab)
    corpo = "\n".join("<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>" for l in linhas)
    return (f'<div class="tabela-rolagem" role="region" aria-labelledby="{titulo_id}" tabindex="0">'
            f'<table><caption class="mut">{e(legenda)}</caption><thead><tr>{th}</tr></thead>'
            f"<tbody>\n{corpo}\n</tbody></table></div>")


def secao_revisoes(c: dict) -> str:
    """Datas que já existiam e voltaram com outro valor, classificadas pela
    natureza da série e pelo estado do período NA HORA DA COLETA
    (tempo_series.classificar): o texto não muda quando a página é refeita."""
    rev = c.get("revisoes", [])
    if not rev:
        return ('<h2 id="rev-t">Valores alterados</h2>\n<p>Nenhum valor já publicado mudou nesta coleta.</p>')
    tipos = [classificar("revisao", r["codigo"], r["data"], c["gerado_em"]) for r in rev]
    linhas = [[e(r["nome"]), e(referencia(r["codigo"], r["data"])), f"<b>{e(rotulo_tipo(t))}</b>",
               e(valor(r["antes"])), e(valor(r["depois"])), e(quando(c["gerado_em"]).replace(" (horário de Brasília)", "")),
               f'<a href="{link_diff(c, r["codigo"])}">ver no GitHub</a>'] for r, t in zip(rev, tipos)]
    legenda = "".join(f"<li><b>{e(rotulo_tipo(t))}.</b> {e(explicacao_tipo(t))}</li>"
                      for t in dict.fromkeys(tipos))
    return (f'<h2 id="rev-t">Valores alterados ({len(rev)})</h2>\n'
            '<p>Datas que já estavam no histórico e voltaram do Banco Central com outro valor.</p>\n'
            f'<ul class="mut">{legenda}</ul>\n'
            + tabela("rev-t", "Valores alterados, com o estado do período na hora da coleta",
                     ["Indicador", "Referência", "O que mudou", "Valor anterior", "Valor novo", "Registrado em",
                      "Mudança"], linhas))


def secao_novas(c: dict) -> str:
    obs = c.get("novas", [])
    if not obs:
        return '<h2 id="novas-t">Observações novas</h2>\n<p>Nenhuma observação nova nesta coleta.</p>'
    linhas = [[e(o["nome"]), e(referencia(o["codigo"], o["data"])), "—", e(valor(o["valor"])),
               f'<a href="{link_diff(c, o["codigo"])}">ver no GitHub</a>'] for o in obs]
    return (f'<h2 id="novas-t">Observações novas ({len(obs)})</h2>\n'
            '<p>Datas que ainda não existiam no site. O valor anterior não se aplica.</p>\n'
            + tabela("novas-t", "Observações novas",
                     ["Indicador", "Referência", "Valor anterior", "Valor novo", "Mudança"], linhas))


def secao_series_novas(c: dict) -> str:
    sn = c.get("series_novas", [])
    if not sn:
        return ""
    itens = "".join(f"<li>{e(s['nome'])}: {s['pontos']} pontos, sem versão anterior para comparar.</li>" for s in sn)
    return f'<h2>Séries publicadas pela primeira vez</h2>\n<ul>{itens}</ul>'


def verificacao(gerado_em: str | None) -> str:
    """Última verificação, separada da última mudança. Preenchida no navegador
    por mudancas.js (API pública do GitHub Actions); sem JS, a frase fixa."""
    return (f'<p data-verificacao data-publicado="{e(gerado_em or "")}" data-repo="{REPO}">'
            "<b>Última verificação:</b> a coleta consulta o Banco Central a cada 6 horas e só publica quando algum "
            "dado muda. Uma verificação sem mudança não gera publicação.</p>")


def corpo(dados: dict, versao: dict) -> str:
    coletas = dados.get("coletas") or []
    if not coletas:
        sha = versao.get("sha")
        atual = (f' Os dados no ar são os do commit <a href="{REPO_URL}/commit/{sha}">{e(sha[:7])}</a>.'
                 if sha else "")
        return (f'<div class="estado"><p><b>Primeira publicação desta página.</b> Ainda não há uma coleta anterior '
                f"registrada para comparar, então não dá para dizer o que é novo e o que foi revisado.{atual}</p>"
                "<p>A partir da próxima coleta que trouxer dados novos, esta página lista as observações novas e as "
                "revisões, com o valor anterior e o novo.</p>"
                + verificacao(None) + "</div>")
    c = coletas[0]
    com = c.get("commit")
    base = c.get("base")
    sobre = (f' · commit <a href="{REPO_URL}/commit/{com}">{e(com[:7])}</a>' if com else "")
    comp = (f' · <a href="{REPO_URL}/compare/{base}...{com}">comparar com a versão anterior ({e(base[:7])})</a>'
            if com and base else "")
    sem_base = ("" if base else
                "<p>Esta coleta não tinha uma versão anterior registrada dos dados; a comparação vale só "
                "para as séries que já existiam.</p>")
    n_rev, n_obs = len(c.get("revisoes", [])), len(c.get("novas", []))
    resumo = f"{n_obs} observação(ões) nova(s) e {n_rev} valor(es) alterado(s)."
    html = (f'<div class="estado"><p><b>Última mudança publicada:</b> {e(quando(c["gerado_em"]))}{sobre}{comp}.</p>'
            f"<p>{resumo}</p>{sem_base}" + verificacao(c["gerado_em"]) + "</div>\n"
            + secao_revisoes(c) + "\n" + secao_novas(c) + "\n" + secao_series_novas(c))
    if len(coletas) > 1:
        itens = []
        for k in coletas[1:]:
            link = (f' · <a href="{REPO_URL}/commit/{k["commit"]}">{e(k["commit"][:7])}</a>' if k.get("commit") else "")
            itens.append(f"<li>{e(quando(k['gerado_em']))}: {len(k.get('novas', []))} nova(s), "
                         f"{len(k.get('revisoes', []))} valor(es) alterado(s){link}</li>")
        html += ("\n<h2>Coletas anteriores</h2>\n<p class=\"mut\">As últimas publicações guardadas no site. "
                 f'O histórico completo fica no <a href="{REPO_URL}/commits/main/data">Git</a>.</p>\n'
                 f'<ul class="coletas">{"".join(itens)}</ul>')
    return html


RODAPE = """
</main>
<footer>As séries vêm da <a href="https://www3.bcb.gov.br/sgspub/">API pública do SGS</a> do Banco Central e são
gravadas sem alteração. Cada coleta que muda algum dado vira um commit público no GitHub, e esta página mostra o
que a última trouxe.
</footer>
</div></body></html>
"""


def pagina(dados: dict, versao: dict) -> str:
    titulo = "O que mudou nesta coleta? Observações novas e revisões"
    desc = ("Quais indicadores ganharam dados novos e quais valores o Banco Central revisou na última coleta do "
            "Observatório de Taxas, com o valor anterior, o novo e o link para o commit.")
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("O que mudou nesta coleta?", URL)])
    ld = jsonld_script({"@context": "https://schema.org", "@type": "WebPage", "name": titulo, "description": desc,
                        "url": URL, "inLanguage": "pt-BR", "isPartOf": {"@id": f"{BASE_URL}/#website"}})
    ld += "\n" + jsonld_script({"@context": "https://schema.org", **crumb_ld})
    topo = head(titulo, desc, URL, ld, crumb_html, [])
    topo = topo.replace(CSP, CSP_PAGINA, 1).replace("</style>", CSS_PAGINA + "</style>", 1)
    topo = topo.replace("</head>", '<script src="../mudancas.js" defer></script>\n</head>', 1)
    return (topo + "<h1>O que mudou nesta coleta?</h1>\n"
            '<p class="mut">A coleta consulta o SGS do Banco Central a cada 6 horas. Esta página separa as '
            "observações novas das revisões de valores que já estavam publicados.</p>\n"
            + corpo(dados, versao) + RODAPE)


def main() -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(pagina(le(FONTE, {}), le(VERSAO, {})), encoding="utf-8")
    print("mudancas/index.html: gerada.")


if __name__ == "__main__":
    main()
