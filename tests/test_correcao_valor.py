"""Leitura do valor nas calculadoras de correção monetária (docs/correcao/).

Roda em node o script de cada página publicada, com um DOM mínimo, e
confere que o valor digitado é lido pelo mesmo leitor estrito do
demonstrativo: separador de milhar em todas as posições, ponto decimal
aceito e texto sobrando recusado com aviso, nunca corrigido pela metade.

    python -m unittest tests.test_correcao_valor -v
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NODE = shutil.which("node")
PAGINAS = sorted([DOCS / "correcao" / "index.html"] + list((DOCS / "correcao").glob("*/index.html")))
CASOS = {
    "1.000.000,00": 1000000, "1000000": 1000000, "1.000.000": 1000000, "R$ 1.000.000,00": 1000000,
    "1000.50": 1000.5, "1000,50": 1000.5, "1.000,50": 1000.5, "2.000": 2000, "0,01": 0.01,
}
INVALIDOS = ["1.000,00xyz", "abc", "", "1,000.00", "10.00.0", "0", "-5", "20.000.000,00"]

PROG = r"""
const fs = require("fs");
const html = fs.readFileSync(PAGINA, "utf8");
const base = PAGINA.replace(/\/[^\/]+$/, "/");
const els = {};
const el = (id) => els[id] || (els[id] = { id, value: "", textContent: "", innerHTML: "", options: [],
  appendChild(o) { this.options.push(o); }, addEventListener(t, f) { this["on" + t] = f; } });
global.document = { readyState: "complete", getElementById: el, querySelector: () => null,
  createElement: () => ({}), addEventListener(t, f) { if (t === "DOMContentLoaded") f(); } };
global.self = global; global.window = global;
if (/id="indice"/.test(html)) el("indice").value = html.match(/<select id="indice"><option value="([^"]+)"/)[1];
else els.indice = null;
const getId = document.getElementById; document.getElementById = (id) => id in els && els[id] === null ? null : getId(id);
for (const m of html.matchAll(/<script(?: src="([^"]+)")?[^>]*>([\s\S]*?)<\/script>/g)) {
  if (m[1] && /demonstrativo\.js/.test(m[1])) { const module = { exports: {} }; eval(fs.readFileSync(base + m[1].split("?")[0], "utf8")); global.ObsDemo = module.exports; }
  else if (!m[1] && /calc-form/.test(m[2])) eval(m[2]);
}
const out = {};
const SERIES_ = JSON.parse(html.match(/const SERIES = (.*);\n/)[1]);
const chave = els.indice ? els.indice.value : JSON.parse(html.match(/const DEFAULT_KEY = (.*);\n/)[1]);
for (const v of VALORES) {
  el("valor").value = v; el("res").textContent = ""; el("res").innerHTML = "";
  const pts = SERIES_[chave].pts; el("de").value = String(pts.length - 13); el("ate").value = String(pts.length - 1);
  el("calc-form").onsubmit({ preventDefault() {} });
  out[v] = el("res").innerHTML || ("AVISO:" + el("res").textContent);
}
process.stdout.write(JSON.stringify(out));
"""


def rodar(pagina: Path, valores: list[str]) -> dict[str, str]:
    prog = f"const PAGINA={json.dumps(str(pagina))};const VALORES={json.dumps(valores)};" + PROG
    r = subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def brl_para_num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


@unittest.skipUnless(NODE, "node não encontrado")
class TestValorDaCorrecao(unittest.TestCase):

    def test_ha_paginas(self):
        self.assertGreaterEqual(len(PAGINAS), 5)

    def test_mesmo_valor_em_formatos_diferentes_da_o_mesmo_resultado(self):
        for pag in PAGINAS:
            res = rodar(pag, list(CASOS))
            fator = None
            for entrada, esperado in CASOS.items():
                with self.subTest(pagina=pag.parent.name, entrada=entrada):
                    m = re.search(r"Valor corrigido: <b>R\$ ([\d.,]+)</b>.*?fator ([\d,]+)", res[entrada])
                    self.assertIsNotNone(m, res[entrada])
                    f = float(m.group(2).replace(",", "."))
                    fator = fator or f
                    self.assertAlmostEqual(brl_para_num(m.group(1)), round(esperado * f, 2), delta=0.011)

    def test_entrada_invalida_vira_aviso_e_nao_resultado(self):
        for pag in PAGINAS:
            res = rodar(pag, INVALIDOS)
            for entrada in INVALIDOS:
                with self.subTest(pagina=pag.parent.name, entrada=entrada):
                    self.assertTrue(res[entrada].startswith("AVISO:Informe um valor"), res[entrada])
                    self.assertNotIn("Valor corrigido", res[entrada])


if __name__ == "__main__":
    unittest.main()
