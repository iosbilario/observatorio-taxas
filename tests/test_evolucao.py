"""Entregas 4 e 5: evolução anual de um contrato e comparação de dois índices.

Testes de aceite D e E: a conta roda em node com os mesmos docs/evolucao.js e
docs/demonstrativo.js servidos ao navegador. Referência independente em Decimal.

    python -m unittest tests.test_evolucao -v
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
NODE = shutil.which("node")


def js(expr: str, **dados):
    prog = (f"const V=require({json.dumps(str(DOCS / 'evolucao.js'))});"
            + "".join(f"const {k}={json.dumps(v)};" for k, v in dados.items())
            + f"process.stdout.write(JSON.stringify(({expr})));")
    r = subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def soma(ym: str, n: int) -> str:
    t = int(ym[:4]) * 12 + int(ym[5:]) - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


# Fixture: três janelas a partir de nov/2023 (regra: até o mês anterior ao aniversário).
MAPA = {}
for k in range(12):
    MAPA[soma("2023-11", k)] = 0.37         # 1º aniversário (nov/2024)
    MAPA[soma("2024-11", k)] = -0.31        # 2º, acumulado negativo (nov/2025)
    MAPA[soma("2025-11", k)] = 0.43         # 3º (nov/2026)
BASE = 123456.78


def ref_decimal(mapa: dict, base: float, janelas: list[tuple[str, str]]) -> list[Decimal]:
    saldo, out = Decimal(repr(base)), []
    for ini, _ in janelas:
        f = 1.0
        for k in range(12):
            f *= 1 + mapa[soma(ini, k)] / 100
        f10 = Decimal(repr(f)).quantize(Decimal("1e-10"), ROUND_HALF_UP)
        saldo = (saldo * f10).quantize(Decimal("0.01"), ROUND_HALF_UP)
        out.append(saldo)
    return out


@unittest.skipUnless(NODE, "node não encontrado")
class Evolucao(unittest.TestCase):

    def test_D_tres_aniversarios_janelas_arredondamento_e_saldo_transportado(self):
        r = js("V.evolucao(m, b, '2023-11', 1, '2026-11')", m=MAPA, b=BASE)
        self.assertIsNone(r["parada"])
        self.assertEqual([(l["aniversario"], l["janela"]) for l in r["linhas"]],
                         [("2024-11", ["2023-11", "2024-10"]), ("2025-11", ["2024-11", "2025-10"]),
                          ("2026-11", ["2025-11", "2026-10"])])
        esperado = ref_decimal(MAPA, BASE, [l["janela"] for l in r["linhas"]])
        self.assertEqual([Decimal(str(l["novo"])) for l in r["linhas"]], esperado)
        self.assertEqual(r["linhas"][1]["antes"], r["linhas"][0]["novo"])           # base do ano seguinte
        self.assertEqual(r["linhas"][2]["antes"], r["linhas"][1]["novo"])
        self.assertLess(r["linhas"][1]["acumulado"], 0)                             # índice negativo
        self.assertLess(r["linhas"][1]["novo"], r["linhas"][1]["antes"])
        self.assertTrue(all(len(l["competencias"]) == 12 for l in r["linhas"]))

    def test_D_percentual_de_exibicao_arredondado_mudaria_os_centavos(self):
        r = js("V.evolucao(m, b, '2023-11', 1, '2026-11')", m=MAPA, b=BASE)
        difere = False
        for l in r["linhas"]:
            pct2 = Decimal(repr(l["acumulado"])).quantize(Decimal("0.01"), ROUND_HALF_UP)
            pelo_pct = (Decimal(repr(l["antes"])) * (1 + pct2 / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            difere |= pelo_pct != Decimal(str(l["novo"]))
        self.assertTrue(difere)

    def test_D_lacuna_intermediaria_preserva_anos_anteriores_e_interrompe(self):
        m = dict(MAPA)
        del m["2025-03"]
        r = js("V.evolucao(m, b, '2023-11', 1, '2026-11')", m=m, b=BASE)
        self.assertEqual(len(r["linhas"]), 1)
        self.assertEqual((r["parada"]["aniversario"], r["parada"]["faltam"], r["parada"]["motivo"]),
                         ("2025-11", ["2025-03"], "lacuna"))

    def test_D_primeiro_aniversario_nao_alcancado_e_antes_da_cobertura(self):
        r = js("V.evolucao(m, b, '2023-11', 1, '2024-10')", m=MAPA, b=BASE)
        self.assertEqual((r["aniversarios"], r["linhas"]), (0, []))
        r = js("V.evolucao(m, b, '2022-05', 1, '2026-11')", m=MAPA, b=BASE)
        self.assertEqual(r["parada"]["motivo"], "antes_da_cobertura")
        self.assertEqual(r["parada"]["primeiro"], "2023-11")

    def test_regras_de_referencia(self):
        a = js("[0,1,2].map(d=>V.aniversarios('2023-11', d, '2024-11')[0].janela)")
        self.assertEqual(a, [["2023-12", "2024-11"], ["2023-11", "2024-10"], ["2023-10", "2024-09"]])

    def test_homologacao_com_dados_reais_do_ipca(self):
        hist = json.loads((ROOT / "data" / "433_history.json").read_text(encoding="utf-8"))
        r = js("V.evolucao(V.porMes(h), 2000, '2023-11', 1, '2025-11')", h=hist)
        self.assertEqual([l["janela"] for l in r["linhas"]], [["2023-11", "2024-10"], ["2024-11", "2025-10"]])
        self.assertEqual([c["ym"] for c in r["linhas"][0]["competencias"]][:2], ["2023-11", "2023-12"])


@unittest.skipUnless(NODE, "node não encontrado")
class Comparacao(unittest.TestCase):

    def test_E_mesmo_indice_da_diferenca_zero_em_todos_os_aniversarios(self):
        c = js("V.comparar(m, m, b, '2023-11', 1, '2026-11')", m=MAPA, b=BASE)
        self.assertEqual(len(c["linhas"]), 3)
        self.assertTrue(all(l["diferenca"] == 0 for l in c["linhas"]))

    def test_E_saldos_independentes_a_partir_da_mesma_base(self):
        outro = {k: v + 0.1 for k, v in MAPA.items()}
        c = js("V.comparar(a, b2, b, '2023-11', 1, '2026-11')", a=MAPA, b2=outro, b=BASE)
        self.assertEqual(c["a"]["linhas"][0]["antes"], c["b"]["linhas"][0]["antes"])
        self.assertEqual(c["b"]["linhas"][1]["antes"], c["b"]["linhas"][0]["novo"])
        self.assertEqual(c["a"]["linhas"][1]["antes"], c["a"]["linhas"][0]["novo"])
        self.assertNotEqual(c["a"]["linhas"][1]["antes"], c["b"]["linhas"][1]["antes"])
        esperado_b = ref_decimal(outro, BASE, [l["janela"] for l in c["linhas"]])
        self.assertEqual([Decimal(str(l["b"]["novo"])) for l in c["linhas"]], esperado_b)
        for l in c["linhas"]:
            self.assertAlmostEqual(l["diferenca"], round(l["b"]["novo"] - l["a"]["novo"], 2), places=9)
            self.assertEqual(l["a"]["janela"], l["b"]["janela"])

    def test_E_periodos_incompativeis_nao_tem_diferenca(self):
        outro = dict(MAPA)
        del outro["2025-02"]
        c = js("V.comparar(a, b2, b, '2023-11', 1, '2026-11')", a=MAPA, b2=outro, b=BASE)
        self.assertEqual(len(c["linhas"]), 1)
        self.assertEqual(c["conferidoAte"], "2024-11")
        self.assertEqual(len(c["a"]["linhas"]), 3)
        self.assertEqual(c["b"]["parada"]["faltam"], ["2025-02"])


class Privacidade(unittest.TestCase):

    def test_valor_do_contrato_fica_fora_de_url_e_requisicoes(self):
        ev = (DOCS / "evolucao.js").read_text(encoding="utf-8")
        demo = (DOCS / "demonstrativo.js").read_text(encoding="utf-8")
        for chamada in re.findall(r"fetch\(([^)]*)\)", ev):
            self.assertIn("_history.json", chamada)
        self.assertNotRegex(ev, r"replaceState\([^;]*valor")
        self.assertIn('sessionStorage.setItem("obs-evolucao"', demo)
        corpo = demo[demo.index("function linkComparar"):demo.index("function ligaComparar")]
        self.assertNotIn("valor", corpo)

    def test_links_nas_paginas(self):
        mes = (DOCS / "reajuste" / "igpm-outubro-2024" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-demo-comparar hidden", mes)
        self.assertIn('href="../evolucao/?indice=igpm&amp;inicio=2023-11&amp;regra=1">Ver evolução desde o início do contrato', mes)
        hub = (DOCS / "reajuste" / "index.html").read_text(encoding="utf-8")
        self.assertIn("reajuste/evolucao/\">Ver evolução desde o início do contrato", hub)
        capa = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="rj-comparar" hidden', capa)
        pag = (DOCS / "reajuste" / "evolucao" / "index.html").read_text(encoding="utf-8")
        self.assertRegex(pag, r'evolucao\.js\?v=[0-9a-f]{10}')
        self.assertIn("Comparar com outro índice", pag)
        self.assertIn('id="evol-exemplo"', pag)


if __name__ == "__main__":
    unittest.main()
