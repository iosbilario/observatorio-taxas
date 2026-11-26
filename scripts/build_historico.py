#!/usr/bin/env python3
"""
build_historico.py — Página /historico/: "Consultar versão histórica".

A pessoa escolhe a série e a data; docs/historico.js mostra o que o
Observatório tinha registrado até o fim daquele dia (horário de Brasília),
comparado com a versão atual. O índice das versões sai de
scripts/versoes_series.py (docs/data/versoes/). Esta página lista também a
primeira versão preservada de cada série, para quem procura uma data anterior.

    python scripts/build_historico.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_ferramentas import CSP, e, head  # noqa: E402
from build_pages import jsonld_script, migalhas  # noqa: E402

DOCS = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
URL = f"{BASE_URL}/historico/"
CSS = """
.tabela-rolagem{overflow-x:auto;margin:.4rem 0 1rem}
.tabela-rolagem:focus-visible{outline:2px solid var(--carimbo);outline-offset:2px}
.tabela-rolagem table{min-width:480px}
form.hist{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:.6rem 1rem;align-items:end}
form.hist button{margin-top:0}
"""


def pagina() -> str:
    idx = json.loads((DOCS / "data" / "versoes" / "index.json").read_text(encoding="utf-8"))["series"]
    versao = json.loads((DOCS / "data" / "versao.json").read_text(encoding="utf-8"))
    hoje = versao["data"][:10]
    opts = "".join(f'<option value="{s["codigo"]}">{e(s["nome"])}</option>' for s in idx)
    linhas = "".join(f'<tr><td>{e(s["nome"])}</td><td>{datetime.fromisoformat(s["primeira"]).strftime("%d/%m/%Y")}</td>'
                     f'<td>{s["versoes"]}</td></tr>' for s in idx)
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Consultar versão histórica", URL)])
    topo = head("Consultar versão histórica de uma série", "O que o Observatório de Taxas tinha registrado de uma série "
                "até uma data, comparado com o valor atual de cada observação.", URL,
                jsonld_script({"@context": "https://schema.org", **crumb_ld}), crumb_html, [])
    topo = topo.replace(CSP, CSP.replace("connect-src 'self'", "connect-src 'self' https://raw.githubusercontent.com"), 1)
    topo = topo.replace("</style>", CSS + "</style>", 1).replace("</head>", '<script src="../historico.js" defer></script>\n</head>', 1)
    return topo + f"""<h1>Consultar versão histórica</h1>
<p class="lead">Escolha a série e a data. A página mostra o que o Observatório tinha registrado até o fim daquele dia,
no horário de Brasília, e compara cada observação com o valor atual.</p>
<form class="hist card" id="hist-form">
<div><label for="hist-serie">Série</label><select id="hist-serie" name="serie">{opts}</select></div>
<div><label for="hist-data">Data</label><input id="hist-data" name="data" type="date" max="{hoje}" required/></div>
<div><button type="submit">Consultar</button></div>
</form>
<div id="hist-res" aria-live="polite"><noscript><p>A consulta precisa de JavaScript para ler a versão no GitHub. A tabela
abaixo mostra desde quando cada série tem versões preservadas.</p></noscript></div>
<section class="card" aria-labelledby="cob-t"><h2 id="cob-t">Desde quando dá para consultar</h2>
<p>A primeira versão preservada é o primeiro commit do repositório com o arquivo da série. Dados antigos carregados de
uma vez nessa data (por exemplo, a série desde 2015) não mostram como o site estava antes dela.</p>
<div class="tabela-rolagem" role="region" aria-labelledby="cob-t" tabindex="0"><table><thead><tr>
<th scope="col">Série</th><th scope="col">Primeira versão registrada</th><th scope="col">Versões</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
<p class="mut">"Registrado pelo Observatório" é a data do commit dos dados na main. O repositório não guarda a hora em
que o GitHub Pages publicou cada versão.</p></section>
</main><footer>Versões guardadas no histórico Git do repositório; cada consulta baixa só o arquivo da série escolhida.</footer></div></body></html>
"""


def main() -> None:
    (DOCS / "historico").mkdir(exist_ok=True)
    (DOCS / "historico" / "index.html").write_text(pagina(), encoding="utf-8")
    print("historico: página gerada.")


if __name__ == "__main__":
    main()
