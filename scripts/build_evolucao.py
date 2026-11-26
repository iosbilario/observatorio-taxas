#!/usr/bin/env python3
"""
build_evolucao.py — /reajuste/evolucao/: evolução anual de um contrato e
comparação com outro índice.

A página é estática; a conta roda no navegador (docs/evolucao.js, que usa a
conta do demonstrativo, docs/demonstrativo.js). O valor do contrato nunca sai do
navegador. A cobertura de cada índice vem de data/ no build, para o formulário
oferecer só meses com dado.

    python scripts/build_evolucao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_ferramentas import e, head  # noqa: E402
from build_pages import INDICES, MESES, jsonld_script, load_history, migalhas  # noqa: E402

DOCS = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
URL = f"{BASE_URL}/reajuste/evolucao/"
ORDEM = ("ipca", "igpm", "inpc", "igpdi")
CSS = """
.tabela-rolagem{overflow-x:auto;margin:.6rem 0 1rem}
.tabela-rolagem:focus-visible{outline:2px solid var(--carimbo);outline-offset:2px}
.tabela-rolagem table{min-width:640px}
.tabela-rolagem td{white-space:nowrap}
.tabela-rolagem details td{white-space:normal}
form .linha{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:.4rem 1rem}
fieldset{border:1px solid var(--linha);border-radius:8px;margin:.6rem 0;padding:.4rem .8rem .8rem}
legend{font-family:"IBM Plex Mono",monospace;font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;color:var(--papel-45)}
.exemplo{border-left:3px solid var(--carimbo);padding:.2rem .8rem;margin:.6rem 0}
textarea{width:100%;font:inherit;margin-top:.5rem}
"""


def cobertura() -> dict[str, tuple[str, str]]:
    out = {}
    for k in ORDEM:
        pts = load_history(INDICES[k]["codigo"])
        out[k] = (pts[0]["dt"].strftime("%Y-%m"), pts[-1]["dt"].strftime("%Y-%m"))
    return out


def sel_mes(nome: str, rotulo: str, padrao: str, anos: range) -> str:
    meses = "".join(f'<option value="{i:02d}"{" selected" if f"{i:02d}" == padrao[5:] else ""}>{MESES[i - 1]}</option>'
                    for i in range(1, 13))
    an = "".join(f'<option value="{a}"{" selected" if str(a) == padrao[:4] else ""}>{a}</option>' for a in anos)
    return (f'<fieldset><legend>{e(rotulo)}</legend><div class="linha">'
            f'<div><label for="{nome}_mes">Mês</label><select id="{nome}_mes" name="{nome}_mes">{meses}</select></div>'
            f'<div><label for="{nome}_ano">Ano</label><select id="{nome}_ano" name="{nome}_ano">{an}</select></div>'
            "</div></fieldset>")


def pagina() -> str:
    cob = cobertura()
    ini_min = min(a for a, _ in cob.values())
    fim_max = max(b for _, b in cob.values())
    anos = range(int(ini_min[:4]), int(fim_max[:4]) + 2)
    opcoes = "".join(f'<option value="{k}">{e(INDICES[k]["nome"])} (dados de {e(MESES[int(cob[k][0][5:]) - 1])} de '
                     f'{cob[k][0][:4]} a {e(MESES[int(cob[k][1][5:]) - 1])} de {cob[k][1][:4]})</option>' for k in ORDEM)
    cen = "".join(f'<option value="{k}"{" selected" if k == "ipca" else ""}>{e(INDICES[k]["nome"])}</option>' for k in ORDEM)
    crumb_html, crumb_ld = migalhas([("Observatório de Taxas", f"{BASE_URL}/"), ("Reajuste de contratos", f"{BASE_URL}/reajuste/"),
                                     ("Evolução do contrato", URL)])
    topo = head("Evolução de um contrato: reajustes anuais desde o início", "Reconstrua os reajustes anuais de um aluguel ou "
                "contrato pelo IPCA, IGP-M, INPC ou IGP-DI, com a memória de cada aniversário, e compare dois índices em reais.",
                URL, jsonld_script({"@context": "https://schema.org", **crumb_ld}), crumb_html, [])
    topo = topo.replace("</style>", CSS + "</style>", 1).replace(
        "</head>", '<script src="../../demonstrativo.js" defer></script>\n<script src="../../evolucao.js" defer></script>\n</head>', 1)
    return topo + f"""<h1>Evolução do contrato desde o início</h1>
<p class="lead">Para quem conhece o valor inicial e quer entender como se chegou ao valor de hoje: cada aniversário,
com as 12 competências aplicadas, o fator, o arredondamento e a base do ano seguinte.</p>
<form id="evol-form" class="card" novalidate>
<label for="valor">Valor inicial do contrato (R$)</label>
<input id="valor" name="valor" type="text" inputmode="decimal" autocomplete="off" placeholder="2.000,00"/>
<p class="mut">O valor fica no seu navegador: não vai para o endereço da página, para métricas nem para outros sites.</p>
{sel_mes("inicio", "Início do contrato", "2023-11", anos)}
<div class="linha">
<div><label for="indice">Índice do contrato</label><select id="indice" name="indice">{opcoes}</select></div>
<div><label for="regra">Regra de referência</label><select id="regra" name="regra">
<option value="1" selected>Acumulado até o mês anterior ao aniversário</option>
<option value="2">Acumulado até dois meses antes do aniversário</option>
<option value="0">Acumulado até o mês do aniversário</option></select></div>
</div>
<p class="exemplo" id="evol-exemplo" aria-live="polite">Com esta regra, um contrato iniciado em novembro de 2023 tem o
primeiro reajuste em novembro de 2024, pelo acumulado de novembro de 2023 a outubro de 2024.</p>
{sel_mes("corte", "Data de corte (até quando calcular)", fim_max, anos)}
<button type="submit">Ver evolução desde o início do contrato</button>
</form>
<div id="evol-res" aria-live="polite"><noscript><p>A conta roda no seu navegador e precisa de JavaScript. As tabelas mensais de
cada índice estão em <a href="../">Reajuste de contratos</a>.</p></noscript></div>
<section class="card" id="evol-cmp" hidden aria-labelledby="evol-cmp-t"><h2 id="evol-cmp-t">Comparar com outro índice</h2>
<form id="evol-cmp-form"><label for="cenario">Índice do cenário</label><select id="cenario" name="cenario">{cen}</select>
<button type="submit">Comparar com outro índice</button></form>
<div id="evol-cmp-res" aria-live="polite"></div></section>
<p class="mut">Mesma conta do demonstrativo de reajuste: fator com 10 casas e centavos com meio centavo para cima. Fonte:
séries do SGS do Banco Central (IPCA e INPC do IBGE; IGP-M e IGP-DI da FGV IBRE). Conteúdo informativo: confira o índice
e a regra do seu contrato.</p>
</main><footer>Cálculo no navegador, com as séries públicas do Observatório de Taxas.</footer></div></body></html>
"""


def main() -> None:
    d = DOCS / "reajuste" / "evolucao"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(pagina(), encoding="utf-8")
    print("evolucao: página gerada.")


if __name__ == "__main__":
    main()
