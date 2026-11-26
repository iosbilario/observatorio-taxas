"""Ícones com URL própria, que o Google consegue usar no resultado da busca.

    python -m unittest tests.test_icones -v
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IGNORADAS = {"embed.html", "admin/index.html"}


class Icones(unittest.TestCase):

    def test_arquivos_quadrados_e_multiplos_de_48(self):
        for nome, lado in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
            with Image.open(DOCS / nome) as im:
                self.assertEqual(im.size, (lado, lado), nome)
        with Image.open(DOCS / "favicon.ico") as ico:
            self.assertIn((48, 48), ico.info["sizes"])
        self.assertEqual(192 % 48, 0)
        self.assertIn("<svg", (DOCS / "favicon.svg").read_text(encoding="utf-8"))
        m = json.loads((DOCS / "site.webmanifest").read_text(encoding="utf-8"))
        for i in m["icons"]:
            self.assertTrue((DOCS / i["src"].lstrip("/")).is_file(), i)

    def test_todas_as_paginas_ligam_os_arquivos_e_nenhuma_usa_data(self):
        n = 0
        for p in sorted(DOCS.rglob("*.html")):
            rel = p.relative_to(DOCS).as_posix()
            if rel in IGNORADAS:
                continue
            html = p.read_text(encoding="utf-8")
            prefixo = "../" * rel.count("/")
            head = html.split("</head>", 1)[0]
            self.assertNotIn('rel="icon" href="data:', html, rel)
            self.assertEqual(head.count("<!-- icones:start -->"), 1, rel)
            for arq in ("favicon.ico", "favicon.svg", "icon-192.png", "apple-touch-icon.png", "site.webmanifest"):
                self.assertIn(f'href="{prefixo}{arq}"', head, rel)
                self.assertTrue((p.parent / f"{prefixo}{arq}").resolve().is_file(), (rel, arq))
            n += 1
        self.assertGreater(n, 570)

    def test_robots_nao_bloqueia_os_icones(self):
        robots = (DOCS / "robots.txt").read_text(encoding="utf-8")
        for linha in re.findall(r"(?im)^disallow:\s*(\S+)", robots):
            for arq in ("/favicon.ico", "/favicon.svg", "/icon-192.png"):
                self.assertFalse(arq.startswith(linha), (linha, arq))


if __name__ == "__main__":
    unittest.main()
