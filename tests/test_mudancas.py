"""Entrega 3: "O que mudou nesta coleta?", rótulos de tempo da capa e menu.

    python -m unittest tests.test_mudancas -v
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_mudancas as bm  # noqa: E402
import fetch  # noqa: E402
import render_index as ri  # noqa: E402
import tempo_series as ts  # noqa: E402
import versao_dados as vd  # noqa: E402
from test_var_versao import RepoDuasVersoes, git  # noqa: E402

SHA_A = "a" * 40
SHA_B = "b" * 40
REPO_URL = "https://github.com/iosbilario/observatorio-taxas"


def pts(*pares):
    return [{"dt": datetime.strptime(d, "%d/%m/%Y"), "v": v} for d, v in pares]


class RotulosDeTempo(unittest.TestCase):

    def test_cada_natureza_tem_o_proprio_rotulo(self):
        casos = {
            (433, "01/10/2026"): "competência outubro de 2026",
            (189, "01/03/2026"): "competência março de 2026",
            (24369, "01/09/2026"): "trimestre móvel até setembro de 2026",
            (1, "25/11/2026"): "cotação de 25/11/2026",
            (21619, "25/11/2026"): "cotação de 25/11/2026",
            (1178, "24/11/2026"): "taxa do dia 24/11/2026",
            (195, "24/11/2026"): "período de 1 mês iniciado em 24/11/2026",
            (13621, "24/11/2026"): "posição em 24/11/2026",
        }
        for (cod, data), esperado in casos.items():
            self.assertEqual(ts.referencia(cod, data), esperado, cod)

    def test_meta_selic_separa_vigencia_da_ultima_observacao(self):
        s = pts(("01/09/2026", 14.0), ("28/10/2026", 13.75), ("29/10/2026", 13.75), ("04/11/2026", 13.75))
        self.assertEqual(ts.rotulo_card(432, s), "em vigor desde 28/10/2026 · última observação 04/11/2026")
        self.assertEqual(ts.vigencia_meta(s), (datetime(2026, 10, 28), 14.0))

    def test_capa_usa_os_rotulos_e_nao_o_ref_generico(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        boletim = re.search(r"<!-- boletim:inicio -->(.*?)<!-- boletim:fim -->", html, re.S).group(1)
        mais = re.search(r"<!-- mais:inicio -->(.*?)<!-- mais:fim -->", html, re.S).group(1)
        self.assertNotRegex(boletim + mais, r'class="num-ref">ref\.')
        self.assertRegex(boletim, r'num-ref">em vigor desde \d\d/\d\d/\d{4} · última observação \d\d/\d\d/\d{4}<')
        self.assertRegex(boletim, r'id="ipca".*?num-ref">competência [a-zç]+ de \d{4}<')
        self.assertRegex(boletim, r'id="dolar".*?num-ref">cotação de \d\d/\d\d/\d{4}<')
        self.assertRegex(boletim, r'id="desemprego".*?num-ref">trimestre móvel até [a-zç]+ de \d{4}<')
        self.assertIn("em vigor desde", boletim)
        self.assertNotIn("por decisão do Copom", boletim)
        self.assertRegex(mais, r'>Euro<small>R\$ por € · cotação de \d\d/\d\d/\d{4}</small>')

    def test_carimbo_separa_publicacao_e_leva_a_mudancas(self):
        c = ri.bloco_carimbo()
        self.assertIn("dados publicados às", c)
        self.assertIn('<a href="mudancas/">o que mudou nesta coleta?</a>', c)
        self.assertNotIn("coletado às", c)


class Coleta(unittest.TestCase):

    def test_compara_separa_novas_de_revisoes(self):
        antes = [{"data": "01/08/2026", "valor": "0.10"}, {"data": "01/09/2026", "valor": "0.20"}]
        novos = [{"data": "01/08/2026", "valor": "0.10"}, {"data": "01/09/2026", "valor": "0.25"},
                 {"data": "01/10/2026", "valor": "0.30"}]
        obs, rev = fetch.compara(433, "IPCA", antes, novos)
        self.assertEqual(obs, [{"codigo": 433, "nome": "IPCA", "data": "01/10/2026", "valor": "0.30"}])
        self.assertEqual(rev, [{"codigo": 433, "nome": "IPCA", "data": "01/09/2026", "antes": "0.20", "depois": "0.25"}])

    def _roda(self, raiz: Path, respostas: dict, versao: str | None = SHA_A):
        (raiz / "data").mkdir(exist_ok=True)
        (raiz / "docs" / "data").mkdir(parents=True, exist_ok=True)
        if versao:
            (raiz / "docs/data/versao.json").write_text(json.dumps({"sha": versao}))
        cfg = {"base_url": "x", "series": [{"codigo": c, "nome": f"S{c}"} for c in respostas]}
        with mock.patch.multiple(fetch, DATA_DIR=raiz / "data", DOCS_DATA_DIR=raiz / "docs" / "data",
                                 CHANGELOG_PATH=raiz / "CHANGELOG.md", load_config=lambda: cfg,
                                 fetch_pontos=lambda base, cod, ultimos=None: respostas[cod]), \
                mock.patch("builtins.print"):
            fetch.main()
        return json.loads((raiz / "data/mudancas.json").read_text()) if (raiz / "data/mudancas.json").exists() else None

    def test_coleta_registra_base_novas_revisoes_e_series_novas(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            m = self._roda(r, {433: [{"data": "01/09/2026", "valor": "0.20"}]})
            self.assertEqual(m["coletas"][0]["series_novas"], [{"codigo": 433, "nome": "S433", "pontos": 1}])
            m = self._roda(r, {433: [{"data": "01/09/2026", "valor": "0.25"}, {"data": "01/10/2026", "valor": "0.30"}]})
            c = m["coletas"][0]
            self.assertEqual(c["base"], SHA_A)
            self.assertIsNone(c["commit"])
            self.assertEqual([o["data"] for o in c["novas"]], ["01/10/2026"])
            self.assertEqual([(x["antes"], x["depois"]) for x in c["revisoes"]], [("0.20", "0.25")])
            self.assertEqual(len(m["coletas"]), 2)
            self.assertEqual(json.loads((r / "docs/data/mudancas.json").read_text()), m)

    def test_coleta_sem_mudanca_nao_grava_nada(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            self._roda(r, {433: [{"data": "01/09/2026", "valor": "0.20"}]})
            antes = (r / "data/mudancas.json").read_text()
            self._roda(r, {433: [{"data": "01/09/2026", "valor": "0.20"}]})
            self.assertEqual((r / "data/mudancas.json").read_text(), antes)

    def test_guarda_no_maximo_30_coletas(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            for i in range(35):
                self._roda(r, {433: [{"data": f"01/01/{1990 + i}", "valor": "0.1"}]})
            m = json.loads((r / "data/mudancas.json").read_text())
        self.assertEqual(len(m["coletas"]), fetch.MUDANCAS_MAX)
        self.assertEqual(m["coletas"][0]["novas"][0]["data"], "01/01/2024")


class VersaoPreencheCommit(unittest.TestCase):

    def test_versao_dados_preenche_o_commit_e_ignora_mudancas_json(self):
        with RepoDuasVersoes() as r:
            (r.raiz / "data").mkdir()
            coleta = {"coletas": [{"gerado_em": "2026-11-25T13:26:01-03:00", "base": r.sha1, "commit": None,
                                   "novas": [], "revisoes": [], "series_novas": []}]}
            for p in ("data/mudancas.json", "docs/data/mudancas.json"):
                (r.raiz / p).write_text(json.dumps(coleta))
            self.assertTrue(vd.grava(r.raiz))
            m = json.loads((r.raiz / "data/mudancas.json").read_text())
            self.assertEqual(m["coletas"][0]["commit"], r.sha2)
            git(r.raiz, "add", "-A"); git(r.raiz, "commit", "-qm", "versão dos dados")
            self.assertEqual(vd.commit_dos_dados(r.raiz)[0], r.sha2)
            self.assertFalse(vd.grava(r.raiz))

    def test_nao_marca_quando_o_commit_ainda_e_a_base(self):
        with RepoDuasVersoes() as r:
            (r.raiz / "data").mkdir()
            coleta = {"coletas": [{"gerado_em": "x", "base": r.sha2, "commit": None}]}
            (r.raiz / "data/mudancas.json").write_text(json.dumps(coleta))
            self.assertFalse(vd.marca_commit_da_coleta(r.sha2, r.raiz))


class Pagina(unittest.TestCase):

    COLETA = {"gerado_em": "2026-11-25T13:26:01-03:00", "base": SHA_A, "commit": SHA_B,
              "novas": [{"codigo": 1, "nome": "Câmbio USD/BRL - venda", "data": "25/11/2026", "valor": "5.8825"}],
              "revisoes": [{"codigo": 433, "nome": "IPCA - variação mensal (%)", "data": "01/09/2026",
                            "antes": "0.48", "depois": "0.5"}],
              "series_novas": []}

    def test_separa_revisoes_de_novas_com_valores_e_link(self):
        html = bm.pagina({"coletas": [self.COLETA]}, {"sha": SHA_B})
        rev = html.index("<h2 id=\"rev-t\">Revisões (1)")
        nov = html.index("<h2 id=\"novas-t\">Observações novas (1)")
        self.assertLess(rev, nov)
        self.assertIn("<td>IPCA - variação mensal (%)</td><td>competência setembro de 2026</td><td>0,48</td><td>0,5</td>", html)
        self.assertIn("<td>Câmbio USD/BRL - venda</td><td>cotação de 25/11/2026</td><td>—</td><td>5,8825</td>", html)
        ancora = hashlib.sha256(b"data/433_history.json").hexdigest()
        self.assertIn(f'{REPO_URL}/commit/{SHA_B}#diff-{ancora}', html)
        self.assertIn(f'{REPO_URL}/compare/{SHA_A}...{SHA_B}', html)
        self.assertIn("25/11/2026 às 13:26 (horário de Brasília)", html)

    def test_sem_mudanca_de_um_tipo_diz_isso(self):
        c = dict(self.COLETA, revisoes=[])
        html = bm.pagina({"coletas": [c]}, {})
        self.assertIn("Nenhum valor já publicado foi revisado nesta coleta.", html)
        c = dict(self.COLETA, novas=[])
        self.assertIn("Nenhuma observação nova nesta coleta.", bm.pagina({"coletas": [c]}, {}))

    def test_ultima_verificacao_separada_da_ultima_mudanca(self):
        html = bm.pagina({"coletas": [self.COLETA]}, {})
        self.assertIn("<b>Última mudança publicada:</b>", html)
        self.assertIn('data-verificacao data-publicado="2026-11-25T13:26:01-03:00"', html)
        self.assertIn("Uma verificação sem mudança não gera publicação.", html)
        self.assertIn("connect-src 'self' https://api.github.com", html)
        self.assertIn('src="../mudancas.js"', html)

    def test_primeira_publicacao_sem_base(self):
        html = bm.pagina({}, {"sha": SHA_B})
        self.assertIn("Primeira publicação desta página.", html)
        self.assertIn(f'{REPO_URL}/commit/{SHA_B}', html)
        self.assertNotIn("<table", html)
        sem_base = bm.pagina({"coletas": [dict(self.COLETA, base=None)]}, {})
        self.assertIn("não tinha uma versão anterior registrada", sem_base)
        self.assertNotIn("/compare/", sem_base)

    def test_commit_ainda_nao_preenchido_usa_o_historico_do_arquivo(self):
        html = bm.pagina({"coletas": [dict(self.COLETA, commit=None)]}, {})
        self.assertIn(f"{REPO_URL}/commits/main/data/433_history.json", html)

    def test_coletas_anteriores_sem_carregar_o_git(self):
        antiga = dict(self.COLETA, gerado_em="2026-11-24T07:00:00-03:00", commit=SHA_A)
        html = bm.pagina({"coletas": [self.COLETA, antiga]}, {})
        self.assertIn("Coletas anteriores", html)
        self.assertIn("24/11/2026 às 07:00", html)
        js = (DOCS / "mudancas.js").read_text(encoding="utf-8")
        self.assertNotIn("/commits", js)
        self.assertEqual(js.count("fetch("), 1)

    def test_pagina_publicada_tem_menu_e_esta_no_sitemap(self):
        html = (DOCS / "mudancas" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<!-- nav:start -->", html)
        self.assertRegex(html, r'mudancas\.js\?v=[0-9a-f]{10}')
        self.assertIn("<loc>https://observatoriodetaxas.tec.br/mudancas/</loc>",
                      (DOCS / "sitemap.xml").read_text(encoding="utf-8"))


class Menu(unittest.TestCase):

    def test_calculadoras_e_conferir_uma_afirmacao(self):
        nav = (ROOT / "partials" / "nav.html").read_text(encoding="utf-8")
        itens = re.findall(r'data-nav="([a-z]+)"[^>]*>([^<]+)</a>', nav)
        self.assertLessEqual(len(itens), 6)
        self.assertIn(("calculadoras", "Calculadoras"), itens)
        self.assertIn(("var", "Conferir uma afirmação"), itens)
        self.assertIn('href="{{P}}reajuste/index.html" data-nav="calculadoras"', nav)
        self.assertIn('title="VAR da Economia"', nav)

    def test_item_ativo_nas_calculadoras(self):
        for rel in ("reajuste/index.html", "correcao/ipca/index.html", "comparador/index.html",
                    "simulador-cdi/index.html"):
            html = (DOCS / rel).read_text(encoding="utf-8")
            self.assertIn('data-nav="calculadoras" aria-current="page">Calculadoras', html, rel)
        var = (DOCS / "var.html").read_text(encoding="utf-8")
        self.assertIn("<h1 class=\"titulo\">VAR da Economia</h1>", var)
        self.assertIn('data-nav="var" aria-current="page" title="VAR da Economia">Conferir uma afirmação', var)


if __name__ == "__main__":
    unittest.main()
