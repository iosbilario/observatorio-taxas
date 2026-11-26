"""Entrega 2: calendário de divulgações (scripts/build_calendario.py).

Teste de aceite B com fontes controladas, sem rede.

    python -m unittest tests.test_calendario -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_calendario as K  # noqa: E402

FONTES = {
    "ibge": {"url": "https://ibge.exemplo/api", "conferido_em": "2027-01-10", "itens": [
        {"familia": "ipca", "id_ibge": 1, "titulo": "IPCA", "competencia": "2026-12", "data_divulgacao": "12/01/2027 12:00:00"},
        {"familia": "ipca15", "id_ibge": 2, "titulo": "IPCA-15", "competencia": "2027-01", "data_divulgacao": "27/01/2027 12:00:00"},
    ]},
    "copom_decisoes": {"url": "https://bcb.exemplo/comunicados", "conferido_em": "2027-01-10", "itens": [
        {"reuniao": 283, "data": "2026-12-09", "titulo": "283ª reunião - Copom mantém a taxa Selic em 13,75% a.a."},
    ]},
}
COPOM = {"conferido_em": "2026-11-26", "cobertura": {"fim": "2027-01-27"},
         "fontes": [{"ano": 2026, "url": "https://bcb.exemplo/nota-2026"}, {"ano": 2027, "url": "https://bcb.exemplo/nota-2027"}],
         "reunioes": [{"ano": 2026, "ordem": 8, "dias": ["2026-12-08", "2026-12-09"]},
                      {"ano": 2027, "ordem": 1, "dias": ["2027-01-26", "2027-01-27"]}]}
ANTERIOR = {"eventos": [{"id": "ipca-2026-12", "data_prevista": "2027-01-08", "datas_anteriores": []}]}
META = [{"data": "09/12/2026", "valor": "13.75"}, {"data": "10/12/2026", "valor": "13.75"}]


def gerar(hist433=(), hoje=date(2027, 1, 15), mudancas=None):
    return {ev["id"]: ev for ev in K.eventos(FONTES, COPOM, {433: list(hist433), 7478: [], 432: META},
                                              mudancas or {}, [], ANTERIOR, hoje)}


class Calendario(unittest.TestCase):

    def test_B_reagendado_preserva_o_id_e_guarda_a_data_anterior(self):
        ev = gerar()["ipca-2026-12"]
        self.assertEqual(ev["data_prevista"], "2027-01-12")
        self.assertEqual(ev["datas_anteriores"], ["2027-01-08"])
        html = K.pagina_evento(ev, {"ipca": "2027-01-12"}, date(2027, 1, 15))
        self.assertIn("Reagendado</dt><dd>data prevista anterior: 08/01/2027", html)

    def test_B_data_passou_sem_dado_continua_aguardando(self):
        ev = gerar()["ipca-2026-12"]
        self.assertEqual(ev["estado"], "aguardando")
        self.assertFalse(ev["publicado"])
        html = K.pagina_evento(ev, {"ipca": "2027-01-12"}, date(2027, 1, 15))
        self.assertIn("data passou, dado ainda não registrado", html)
        self.assertIn("Detectado pelo Observatório</dt><dd>ainda não", html)
        # antes da data: previsto
        self.assertEqual(gerar(hoje=date(2027, 1, 5))["ipca-2026-12"]["estado"], "previsto")

    def test_B_publicado_so_quando_o_dado_entra(self):
        mud = {"coletas": [{"gerado_em": "2027-01-12T15:20:00-03:00", "novas": [{"codigo": 433, "data": "01/12/2026"}]}]}
        ev = gerar(hist433=[{"data": "01/12/2026", "valor": "0.4"}], mudancas=mud)["ipca-2026-12"]
        self.assertEqual(ev["estado"], "publicado")
        self.assertEqual(ev["detectado_em"], "2027-01-12T15:20:00-03:00")
        self.assertIn("12/01/2027 às 15:20 (coleta do SGS)", K.pagina_evento(ev, {}, date(2027, 1, 15)))

    def test_B_copom_que_mantem_a_meta_e_decisao_vinculada_a_reuniao(self):
        ev = gerar()["copom-2026-8"]
        self.assertEqual(ev["estado"], "publicado")
        self.assertEqual(ev["reuniao"]["numero"], 283)
        self.assertEqual(ev["divulgacao_oficial"], "2026-12-09")
        self.assertEqual(ev["vigencia"]["inicio"], "2026-12-10")
        html = K.pagina_evento(ev, {}, date(2027, 1, 15))
        for trecho in ("Dias da reunião</dt><dd>08/12/2026 e 09/12/2026",
                       "Comunicação da decisão</dt><dd>09/12/2026 (comunicado oficial)",
                       "Decisão</dt><dd>283ª reunião - Copom mantém a taxa Selic em 13,75% a.a.",
                       "Vigência da meta</dt><dd>a partir de 10/12/2026"):
            self.assertIn(trecho, html)
        futura = gerar()["copom-2027-1"]
        self.assertEqual(futura["estado"], "previsto")
        self.assertIsNone(futura["reuniao"]["numero"])
        self.assertIn("ainda não comunicada", K.pagina_evento(futura, {}, date(2027, 1, 15)))

    def test_horario_nao_confirmado_e_fim_da_cobertura(self):
        ev = gerar()["ipca15-2027-01"]
        self.assertIsNone(ev["horario"])
        html = K.pagina_evento(ev, {"ipca15": "2027-01-27"}, date(2027, 2, 1))
        self.assertIn("Horário</dt><dd>não confirmado", html)
        self.assertIn("A agenda verificada desta família termina em 27/01/2027", html)

    def test_mesmas_entradas_mesmos_eventos(self):
        self.assertEqual(gerar(), gerar())


class Publicado(unittest.TestCase):

    def test_capa_fichas_e_paginas(self):
        cal = json.loads((ROOT / "data" / "calendario.json").read_text(encoding="utf-8"))
        ids = [ev["id"] for ev in cal["eventos"]]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertTrue((DOCS / "calendario" / i / "index.html").is_file(), i)
        capa = (DOCS / "index.html").read_text(encoding="utf-8")
        bloco = re.search(r"<!-- agenda:inicio -->(.*?)<!-- agenda:fim -->", capa, re.S).group(1)
        self.assertIn('href="calendario/', bloco)
        self.assertIn("Últimas divulgações", capa)
        for slug in ("ipca", "ipca-15", "meta-selic"):
            html = (DOCS / "indicadores" / slug / "index.html").read_text(encoding="utf-8")
            self.assertTrue('id="agenda-t">Próxima divulgação' in html, slug)
        fontes = json.loads((ROOT / "data" / "calendario_copom.json").read_text(encoding="utf-8"))
        for f in fontes["fontes"]:
            self.assertTrue(f["url"].startswith("https://www.bcb.gov.br/"), f)


if __name__ == "__main__":
    unittest.main()
