"""Rodapé do site (partials/rodape.html) e contador de estrelas do GitHub.

    python -m unittest tests.test_rodape -v
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_github  # noqa: E402
import sync_nav  # noqa: E402

COLUNAS = ("Produto", "Documentação", "Para IAs", "Projeto")


def paginas():
    for p in sorted(DOCS.rglob("*.html")):
        rel = p.relative_to(DOCS).as_posix()
        if rel not in sync_nav.IGNORADAS:
            yield rel, p.read_text(encoding="utf-8")


class TestRodape(unittest.TestCase):
    def test_todas_as_paginas_tem_um_footer_com_o_rodape_dentro(self):
        total = 0
        for rel, html in paginas():
            self.assertEqual(html.count("<footer"), 1, rel)
            footer = re.search(r"<footer\b.*?</footer>", html, re.S).group(0)
            self.assertIn(sync_nav.RODAPE_INICIO, footer, rel)
            self.assertIn(sync_nav.RODAPE_FIM, footer, rel)
            for coluna in COLUNAS:
                self.assertIn(f">{coluna}</h2>", footer, f"{rel}: {coluna}")
            total += 1
        self.assertGreater(total, 500)

    def test_links_internos_do_rodape_existem(self):
        corpo = sync_nav.corpo_do_partial(sync_nav.PARTIAL_RODAPE)
        for alvo in re.findall(r'href="\{\{P\}\}([^"#]*)', corpo):
            caminho = DOCS / alvo
            self.assertTrue(caminho.is_file() or (caminho / "index.html").is_file(), alvo)

    def test_procedencia_continua_no_rodape_das_paginas_de_indice(self):
        html = (DOCS / "reajuste" / "ipca-julho-2026" / "index.html").read_text(encoding="utf-8")
        footer = re.search(r"<footer\b.*?</footer>", html, re.S).group(0)
        self.assertIn("produzidos pelo IBGE", footer)
        self.assertIn("FGV IBRE", footer)

    def test_ano_do_rodape_e_o_da_geracao(self):
        corpo = sync_nav.corpo_do_partial(sync_nav.PARTIAL_RODAPE)
        self.assertIn("{{ANO}}", corpo)
        self.assertIn("© 2031 Observatório", sync_nav.bloco_rodape(corpo, "", 2031))

    def test_rodape_fora_da_impressao_digital_do_sitemap(self):
        import render_index
        html = (DOCS / "sobre" / "index.html").read_text(encoding="utf-8")
        outro = re.sub(r"© \d{4} Observatório", "© 2099 Observatório", html)
        self.assertNotEqual(html, outro)
        self.assertEqual(render_index.impressao_digital_html(html), render_index.impressao_digital_html(outro))


class TestEstrelas(unittest.TestCase):
    def test_header_tem_link_do_github_e_script_de_mesma_origem(self):
        for rel, html in paginas():
            self.assertIn('class="nav-github"', html, rel)
            prefixo = "../" * rel.count("/")
            self.assertIn(f'<script src="{prefixo}estrelas.js" defer></script>', html, rel)

    def test_script_nao_fala_com_o_github(self):
        js = (DOCS / "estrelas.js").read_text(encoding="utf-8")
        codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
        self.assertNotIn("github.com", codigo)
        self.assertIn('"data/github.json"', codigo)

    def test_arquivo_publicado_valido(self):
        for p in fetch_github.SAIDAS:
            d = json.loads(p.read_text(encoding="utf-8"))
            self.assertIsInstance(d["estrelas"], int)
            self.assertGreaterEqual(d["estrelas"], 0)

    def test_extrai_estrelas_rejeita_valores_invalidos(self):
        self.assertEqual(fetch_github.extrai_estrelas({"stargazers_count": 7}), 7)
        for ruim in ({}, {"stargazers_count": -1}, {"stargazers_count": "7"}, {"stargazers_count": True}):
            with self.assertRaises(ValueError):
                fetch_github.extrai_estrelas(ruim)

    def test_so_grava_quando_o_numero_muda(self):
        with tempfile.TemporaryDirectory() as d:
            saidas = [Path(d) / "a" / "github.json", Path(d) / "b" / "github.json"]
            self.assertTrue(fetch_github.grava_se_mudou(3, saidas))
            self.assertFalse(fetch_github.grava_se_mudou(3, saidas))
            self.assertTrue(fetch_github.grava_se_mudou(4, saidas))
            self.assertEqual(json.loads(saidas[1].read_text(encoding="utf-8"))["estrelas"], 4)

    def test_erro_de_rede_nao_derruba_o_monitor(self):
        with mock.patch.object(fetch_github, "consulta", side_effect=OSError("sem rede")), \
             mock.patch.object(fetch_github, "grava_se_mudou") as grava:
            self.assertEqual(fetch_github.main(), 0)
            grava.assert_not_called()


if __name__ == "__main__":
    unittest.main()
