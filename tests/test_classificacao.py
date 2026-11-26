"""Entrega 1: o que uma mudança registrada quer dizer (tempo_series.classificar).

Teste de aceite A, sem rede.

    python -m unittest tests.test_classificacao -v
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_divulgacoes as D  # noqa: E402
import build_mudancas as M  # noqa: E402
import tempo_series as T  # noqa: E402
from test_divulgacoes import serie, treze, versao  # noqa: E402

# O caso real da coleta de 26/11/2026 (data/mudancas.json): CDI acumulado de novembro 0,76% -> 0,82%.
CDI_NOV = {"codigo": 4391, "nome": "CDI - acumulado no mês (%)", "data": "01/11/2026", "antes": "0.76", "depois": "0.82"}
COLETA = {"gerado_em": "2026-11-26T11:27:52-03:00", "base": "a" * 40, "commit": "b" * 40,
          "novas": [], "revisoes": [CDI_NOV], "series_novas": []}


class Classificar(unittest.TestCase):

    def test_A_cdi_de_novembro_e_atualizacao_de_periodo_em_andamento(self):
        self.assertEqual(T.classificar("revisao", 4391, "01/11/2026", COLETA["gerado_em"]), "andamento")
        html = M.pagina({"coletas": [COLETA]}, {})
        self.assertIn("<b>Atualização de período em andamento</b></td><td>0,76</td><td>0,82</td>"
                      "<td>26/11/2026 às 11:27</td>", html)
        self.assertNotRegex(html.lower(), r"corre[çc][ãa]o|erro do produtor|revis[ãa]o metodol")

    def test_A_regenerada_em_dezembro_diz_a_mesma_coisa(self):
        antes = M.pagina({"coletas": [COLETA]}, {})

        class Dezembro(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 12, 15, 10, 0, tzinfo=tz)

            @classmethod
            def today(cls):
                return datetime(2026, 12, 15, 10, 0)

        with mock.patch.object(M, "datetime", Dezembro), mock.patch.object(T, "datetime", Dezembro):
            depois = M.pagina({"coletas": [COLETA]}, {})
        self.assertEqual(antes, depois)

    def test_A_natureza_e_estado_do_periodo(self):
        casos = [
            # acumulado do mês: aberto até o último dia; logo depois do fim, indefinido; depois, encerrado
            (("revisao", 4391, "01/10/2026", "2026-11-03T09:00:00-03:00"), "alterado"),
            (("revisao", 4391, "01/10/2026", "2026-11-20T09:00:00-03:00"), "encerrado"),
            (("revisao", 4390, "01/11/2026", "2026-11-30T23:00:00-03:00"), "andamento"),
            # o fuso conta: 01/12 02:00 UTC ainda é 30/11 em Brasília
            (("revisao", 4391, "01/11/2026", "2026-12-01T02:00:00+00:00"), "andamento"),
            # cotação diária: um dia já concluído é período encerrado; o próprio dia, indefinido
            (("revisao", 1, "24/11/2026", "2026-11-26T11:00:00-03:00"), "encerrado"),
            (("revisao", 1, "26/11/2026", "2026-11-26T11:00:00-03:00"), "alterado"),
            # índice mensal publicado depois do mês: sempre encerrado
            (("revisao", 433, "01/09/2026", "2026-11-25T13:26:01-03:00"), "encerrado"),
            # meta Selic de um dia ainda por vir: não há como dizer
            (("revisao", 432, "30/11/2026", "2026-11-26T11:00:00-03:00"), "alterado"),
            (("nova", 4391, "01/11/2026", "2026-11-03T09:00:00-03:00"), "nova"),
        ]
        for args, esperado in casos:
            self.assertEqual(T.classificar(*args), esperado, args)

    def test_A_titulo_de_revisao_usa_a_classificacao(self):
        arq = {"formato": 1, "publicacoes": []}
        v = treze()
        D.registrar(arq, {433: serie(v)}, {}, versao("1" * 40, "2026-02-10T12:00:00Z"))
        v["2025-06"] = 0.9
        mud = {"coletas": [{"gerado_em": "2026-02-20T10:00:00-03:00", "commit": "2" * 40, "base": "1" * 40,
                            "novas": [], "revisoes": [{"codigo": 433, "data": "01/06/2025", "antes": "0.4",
                                                       "depois": "0.9"}]}]}
        r = D.registrar(arq, {433: serie(v)}, mud, versao("2" * 40, "2026-02-20T12:00:00Z"))[0]
        self.assertEqual(r["revisa"]["alteracoes"][0]["tipo"], "encerrado")
        self.assertTrue(D.titulo(r).startswith("Alteração em período encerrado (revisão 1) — IPCA de janeiro de 2026"))
        self.assertNotIn("orreç", D.titulo(r))
        self.assertIn("Alteração em período encerrado", D.resumo(r) + D.titulo(r))

    def test_ficha_mostra_as_mudancas_com_a_classificacao(self):
        html = (DOCS / "indicadores" / "cdi-acumulado-no-mes" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="mud-t">Mudanças recentes registradas', html)
        self.assertRegex(html, r"<td>competência novembro de 2026</td><td>Atualização de período em andamento</td>"
                               r"<td>0,76%</td><td>0,82%</td><td>26/11/2026 às 11:27</td>")

    def test_registros_antigos_sem_tipo_continuam_legiveis(self):
        reg = {"revisao": 1, "leitura": {"titulo": "X"}, "revisa": {"alteracoes": [{"competencia": "2026-01",
                                                                                   "antes": 1, "depois": 2}]}}
        self.assertEqual(D.titulo(reg), "Valor alterado (revisão 1) — X")


if __name__ == "__main__":
    unittest.main()
