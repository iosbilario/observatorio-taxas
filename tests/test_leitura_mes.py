"""Leitura do mês nas páginas de reajuste: o texto sai dos números do mês.

    python -m unittest tests.test_leitura_mes -v
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_pages as bp  # noqa: E402


def _serie(inicio: tuple[int, int], valores: list[float]) -> list[dict]:
    ano, mes = inicio
    pts = []
    for v in valores:
        pts.append({"dt": datetime(ano, mes, 1), "valor": v})
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return pts


def _janelas(hist: list[dict]) -> list[list[dict]]:
    return [hist[f - 11: f + 1] for f in range(11, len(hist))]


def _ctx(series: dict[str, list[dict]]) -> dict:
    return bp.montar_contexto({k: _janelas(h) for k, h in series.items()})


class LeituraDoMes(unittest.TestCase):

    def test_explica_alta_pelo_mes_que_entrou_e_o_que_saiu(self):
        # 24 meses de 0,30% e um último de 1,00%: o acumulado sobe porque
        # entrou 1,00% e saiu 0,30%.
        igpm = _serie((2023, 1), [0.30] * 24 + [1.00])
        ipca = _serie((2023, 1), [0.40] * 25)
        ctx = _ctx({"igpm": igpm, "ipca": ipca})
        html, extras = bp.leitura_do_mes("igpm", bp.INDICES["igpm"], igpm[-12:], ctx)

        self.assertIn("subiu de", html)
        self.assertIn("1,00% em janeiro de 2025", html)
        self.assertIn("0,30% em janeiro de 2024", html)
        self.assertTrue("maior desde" in html or "maior de todo o histórico" in html)
        self.assertIn("a menos do que pelo IPCA", html)
        self.assertEqual(extras[0][0], "Por que o IGP-M acumulado subiu em janeiro de 2025?")

    def test_estavel_e_sem_mes_negativo(self):
        igpm = _serie((2023, 1), [0.50] * 25)
        html, extras = bp.leitura_do_mes("igpm", bp.INDICES["igpm"], igpm[-12:], _ctx({"igpm": igpm}))

        self.assertIn("praticamente estável", html)
        self.assertIn("Nenhum dos 12 meses teve variação negativa.", html)
        self.assertEqual(extras[0][0], "O IGP-M acumulado mudou em janeiro de 2025?")

    def test_pagina_de_mes_nao_repete_a_lista_completa_de_meses(self):
        igpm = _serie((2023, 1), [0.30] * 25)
        janelas = {"igpm": _janelas(igpm)}
        paginas = {f"igpm-{bp.slug_mes(j[-1]['dt'])}": {"nome": "IGP-M", "ref": bp.mes_ano(j[-1]["dt"]),
                                                       "key": "igpm", "dt": j[-1]["dt"]}
                   for j in janelas["igpm"]}
        _, html = bp.build_month_page("igpm", bp.INDICES["igpm"], janelas["igpm"][-1], paginas,
                                      bp.montar_contexto(janelas))
        self.assertNotIn("Todos os meses (", html)
        self.assertIn("IGP-M em janeiro de outros anos", html)
        self.assertIn("Leitura do mês", html)


if __name__ == "__main__":
    unittest.main()
