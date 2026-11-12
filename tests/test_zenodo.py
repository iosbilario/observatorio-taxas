"""Testes da preparação para o Zenodo (CITATION.cff e arquivo da release).

    python -m unittest tests.test_zenodo -v
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FORA = ("data/", "docs/data/", "docs/reajuste/", "docs/correcao/", "CHANGELOG.md",
        "tests/fixtures/valores_baseline.json")


class TestCitation(unittest.TestCase):
    def setUp(self):
        self.cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    def test_campos_que_o_zenodo_le(self):
        c = self.cff
        self.assertEqual(c["cff-version"], "1.2.0")
        self.assertEqual(c["title"], "Observatório de Taxas")
        self.assertEqual(c["type"], "software")
        self.assertEqual(c["license"], "MIT")
        self.assertRegex(c["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(str(c["date-released"]), r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(c["repository-code"], "https://github.com/iosbilario/observatorio-taxas")
        self.assertEqual(c["url"], "https://observatoriodetaxas.tec.br/")
        self.assertTrue(c["abstract"].strip())
        self.assertIn("LICENSE-DADOS.md", c["message"])

    def test_autor_sem_identificadores_inventados(self):
        self.assertEqual(self.cff["authors"][0]["family-names"], "Pereira")
        self.assertEqual(self.cff["authors"][0]["given-names"], "Leandro Borges")
        texto = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertNotRegex(texto, r"(?im)^\s*(doi|orcid):|10\.5281/zenodo|orcid\.org")
        self.assertNotIn("identifiers", self.cff)

    def test_versao_corresponde_a_uma_tag_existente_ou_a_proxima(self):
        tags = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        if not tags:
            self.skipTest("clone sem tags (CI raso)")
        ultima = max(tags, key=lambda t: tuple(int(x) for x in t[1:].split(".")))
        atual = tuple(int(x) for x in self.cff["version"].split("."))
        self.assertGreaterEqual(atual, tuple(int(x) for x in ultima[1:].split(".")))

    def test_fonte_unica_de_metadados(self):
        self.assertFalse((ROOT / ".zenodo.json").exists(), "com .zenodo.json o Zenodo ignora o CITATION.cff")


class TestArquivoDaRelease(unittest.TestCase):
    def test_arquivo_so_com_o_software(self):
        r = subprocess.run(["git", "archive", "--worktree-attributes", "--format=tar", "HEAD"],
                           cwd=ROOT, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        nomes = subprocess.run(["tar", "-t"], input=r.stdout, capture_output=True).stdout.decode().split("\n")
        vazados = [n for n in nomes if n.startswith(FORA)]
        self.assertEqual(vazados, [])
        for obrigatorio in ("LICENSE", "LICENSE-DADOS.md", "CITATION.cff", "README.md",
                            "scripts/fetch.py", "scripts/build_pages.py", "config.yml"):
            self.assertIn(obrigatorio, nomes)

    def test_gitattributes_declara_as_exclusoes(self):
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for caminho in FORA:
            self.assertRegex(attrs, rf"(?m)^{re.escape(caminho)}\s+export-ignore$")


if __name__ == "__main__":
    unittest.main()
