"""Tema claro/escuro em todas as páginas (docs/tema.css, docs/tema.js, sync_nav.py).

    python -m unittest tests.test_tema -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FORA = {"embed.html", "admin/index.html"}


def paginas():
    for p in sorted(DOCS.rglob("*.html")):
        rel = p.relative_to(DOCS).as_posix()
        if rel in FORA or rel.startswith("radar/"):
            continue
        yield rel, p.read_text(encoding="utf-8")


class TemaDoSite(unittest.TestCase):

    def test_toda_pagina_abre_clara_com_tema_e_botao(self):
        n = 0
        for rel, html in paginas():
            n += 1
            prefixo = "../" * rel.count("/")
            self.assertRegex(html, r'<html[^>]*data-theme="light"', rel)
            p = re.escape(prefixo)
            self.assertRegex(html, rf'href="{p}refy/tokens\.css\?v=[0-9a-f]{{10}}"', rel)
            self.assertEqual(len(re.findall(r'<link[^>]*refy/tokens\.css', html)), 1, rel)
            self.assertRegex(html, rf'href="{p}tema\.css\?v=[0-9a-f]{{10}}"', rel)
            self.assertRegex(html, rf'<script src="{p}tema\.js\?v=[0-9a-f]{{10}}"></script>', rel)
            self.assertIn("data-tema-botao hidden", html, rel)
            self.assertIn('<meta name="theme-color" content="#ffffff"', html, rel)
        self.assertGreater(n, 500)

    def test_tema_css_vem_depois_do_style_da_pagina(self):
        for rel, html in paginas():
            self.assertGreater(html.index("tema.css"), html.rfind("</style>", 0, html.index("</head>")), rel)

    def test_css_das_paginas_sem_tons_fixos_da_paleta_escura(self):
        for rel, html in paginas():
            css = " ".join(re.findall(r"(?s)<style[^>]*>(.*?)</style>", html))
            self.assertNotRegex(css, r"rgba\(\s*217\s*,\s*181\s*,\s*74", rel)
            self.assertNotRegex(css, r"rgba\(\s*233\s*,\s*230\s*,\s*220", rel)

    def test_aliases_de_fonte_batem_com_as_declaracoes_das_paginas(self):
        tema = (DOCS / "tema.css").read_text(encoding="utf-8")

        def descritores(bloco: str) -> str:
            return re.sub(r"src:[^;]*;", "", re.sub(r"\s+", "", bloco))

        alias = {re.search(r"font-family:'([^']+)'", b).group(1): descritores(b)
                 for b in re.findall(r"@font-face\{[^}]*\}", tema) if "'Fraunces'" in b or "'Archivo'" in b}
        self.assertEqual(set(alias), {"Fraunces", "Archivo"})
        for rel, html in paginas():
            for b in re.findall(r"@font-face\s*\{[^}]*\}", html):
                fam = re.search(r"font-family:\s*'([^']+)'", b)
                if fam and fam.group(1) in alias:
                    self.assertEqual(descritores(b), alias[fam.group(1)], rel)

    def test_versao_dos_arquivos_bate_com_o_conteudo(self):
        import hashlib
        for nome in ("nav.css", "tema.css", "tema.js", "refy/tokens.css", "estrelas.js"):
            v = hashlib.sha256((DOCS / nome).read_bytes()).hexdigest()[:10]
            for rel, html in paginas():
                for achado in re.findall(rf'{re.escape(nome)}\?v=([0-9a-f]+)"', html):
                    self.assertEqual(achado, v, (rel, nome))

    def test_radar_continua_com_a_paleta_propria(self):
        for p in (DOCS / "radar").glob("*.html"):
            html = p.read_text(encoding="utf-8")
            self.assertNotIn("tema.css", html, p.name)
            self.assertIn("tema-radar", html, p.name)


if __name__ == "__main__":
    unittest.main()
