"""Guias em /guias/: páginas geradas, ligadas ao sitemap e sem lacunas no texto.

    python -m unittest tests.test_guias -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_guias  # noqa: E402

SLUGS = ("reajuste-de-aluguel", "ipca-igpm-inpc-igpdi", "como-calcular-acumulado",
         "correcao-monetaria", "selic", "dolar-ptax")


class Guias(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.saida = build_guias.gerar()

    def test_gera_hub_e_seis_guias(self):
        esperado = {"guias/index.html"} | {f"guias/{s}/index.html" for s in SLUGS}
        self.assertEqual(set(self.saida), esperado)

    def test_hub_lista_todos_os_guias(self):
        hub = self.saida["guias/index.html"]
        for s in SLUGS:
            self.assertIn(f'href="{s}/"', hub)

    def test_cada_guia_tem_titulo_faq_e_canonical(self):
        for s in SLUGS:
            html = self.saida[f"guias/{s}/index.html"]
            self.assertIn(f'<link rel="canonical" href="https://observatoriodetaxas.tec.br/guias/{s}/"/>', html)
            self.assertEqual(html.count("<h1>"), 1, s)
            self.assertIn('"@type": "FAQPage"', html)
            self.assertIn("Perguntas e respostas", html)

    def test_texto_sem_valor_faltando(self):
        for rel, html in self.saida.items():
            texto = re.sub(r"<[^>]+>", " ", html)
            self.assertNotIn("None", texto, rel)
            self.assertNotIn("nan%", texto, rel)
            self.assertNotIn("{", re.sub(r"(?s)<style>.*?</style>|<script.*?</script>", "", html), rel)

    def test_guias_publicados_estao_no_sitemap(self):
        sitemap = (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://observatoriodetaxas.tec.br/guias/</loc>", sitemap)
        for s in SLUGS:
            self.assertIn(f"<loc>https://observatoriodetaxas.tec.br/guias/{s}/</loc>", sitemap)


if __name__ == "__main__":
    unittest.main()
