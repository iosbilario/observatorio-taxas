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
DOI_CONCEITO = "10.5281/zenodo.24151062"   # conferido em /api/records/24151063 (conceptdoi)
DOI_VERSAO_160 = "10.5281/zenodo.24151063"
DOI_VERSAO_170 = "10.5281/zenodo.24195784"   # conferido em /api/records/24195784
DOIS_REAIS = {DOI_CONCEITO, DOI_VERSAO_160, DOI_VERSAO_170}
REGISTROS_REAIS = {"24151063", "24195784"}
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
        self.assertNotRegex(texto, r"(?im)orcid")
        self.assertEqual(set(re.findall(r"10\.5281/zenodo\.\d+", texto)), DOIS_REAIS)
        self.assertEqual(self.cff["doi"], DOI_CONCEITO)

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


# --------------------------------------------------------------------------
# Preparação da release v1.6.0 (validade, consistência, links, segurança)
# --------------------------------------------------------------------------
DOCS_MD = ["README.md", "organic-discovery/ZENODO.md", "organic-discovery/RELEASE-v1.6.0.md",
           "organic-discovery/RELEASE-v1.7.0.md", "organic-discovery/RELEASE-v1.8.0.md",
           "desenvolvimento/REPRODUCAO.md", "desenvolvimento/GUIA.md", "desenvolvimento/METODOLOGIA-FERRAMENTAS.md"]


def _arquivo() -> list[str]:
    r = subprocess.run(["git", "archive", "--worktree-attributes", "--format=tar", "HEAD"],
                       cwd=ROOT, capture_output=True)
    return [n for n in subprocess.run(["tar", "-t"], input=r.stdout, capture_output=True)
            .stdout.decode().split("\n") if n and not n.endswith("/")]


class TestReleasePreparada(unittest.TestCase):
    def setUp(self):
        self.cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    def test_cff_valido_pelo_schema_quando_cffconvert_disponivel(self):
        try:
            from cffconvert.cli.create_citation import create_citation
            from cffconvert.cli.validate_or_write_output import validate_or_write_output
        except ImportError:
            self.skipTest("cffconvert não instalado (só desenvolvimento)")
        citation = create_citation(str(ROOT / "CITATION.cff"), None)
        validate_or_write_output(None, "zenodo", True, citation)   # levanta exceção se inválido

    def test_versao_consistente_entre_citation_e_notas(self):
        v = self.cff["version"]
        notas = ROOT / "organic-discovery" / f"RELEASE-v{v}.md"
        self.assertTrue(notas.is_file(), f"faltam as notas da release v{v}")
        self.assertTrue(notas.read_text(encoding="utf-8").startswith(f"# v{v}"))
        self.assertIn(f"git checkout v{v}", (ROOT / "desenvolvimento" / "REPRODUCAO.md").read_text(encoding="utf-8"))

    def test_so_os_dois_reais_conferidos_no_zenodo(self):
        for rel in DOCS_MD + ["CITATION.cff", "docs/sobre/index.html"]:
            t = (ROOT / rel).read_text(encoding="utf-8")
            self.assertTrue(set(re.findall(r"10\.5281/zenodo\.\d+", t)) <= DOIS_REAIS, rel)
            self.assertNotRegex(t, r"(?i)doi\.org/10\.(?!5281/zenodo\.(?:2415106[23]|24195784)\b)", rel)
            for rec in re.findall(r"zenodo\.org/records?/(\d+)", t):
                self.assertIn(rec, REGISTROS_REAIS, rel)

    def test_readme_tem_citacao_academica_sem_placeholder(self):
        t = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Citação acadêmica", t)
        for termo in ("DOI da versão", "DOI conceito", "Commit Git", "Data de referência"):
            self.assertIn(termo, t)
        self.assertNotRegex(t, r"XXXX|0000000|<DOI>|DOI_AQUI")
        self.assertIn(f"https://zenodo.org/badge/DOI/{DOI_CONCEITO}.svg", t)
        self.assertIn(f"https://doi.org/{DOI_VERSAO_160}", t)
        self.assertIn(f"https://doi.org/{DOI_VERSAO_170}", t)

    def test_links_relativos_dos_documentos_existem(self):
        faltando = []
        for rel in DOCS_MD:
            base = (ROOT / rel).parent
            for alvo in re.findall(r"\]\(([^)#:\s]+)(?:#[^)]*)?\)", (ROOT / rel).read_text(encoding="utf-8")):
                if not (base / alvo).resolve().exists():
                    faltando.append(f"{rel} -> {alvo}")
        self.assertEqual(faltando, [])

    def test_comandos_de_reproducao_apontam_para_scripts_existentes(self):
        for rel in ("README.md", "desenvolvimento/REPRODUCAO.md", "organic-discovery/RELEASE-v1.6.0.md",
                    "organic-discovery/RELEASE-v1.7.0.md", "organic-discovery/RELEASE-v1.8.0.md"):
            for script in re.findall(r"python\S* (scripts/[a-z_]+\.py)", (ROOT / rel).read_text(encoding="utf-8")):
                self.assertTrue((ROOT / script).is_file(), f"{rel}: {script}")
            self.assertNotIn("backfill.py 5", (ROOT / rel).read_text(encoding="utf-8"))

    def test_licencas_consistentes(self):
        lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(lic.startswith("MIT License"))
        self.assertEqual(self.cff["license"], "MIT")
        dados = (ROOT / "LICENSE-DADOS.md").read_text(encoding="utf-8")
        for termo in ("ODbL", "IBGE", "FGV IBRE", "não as\nrelicencia"):
            self.assertIn(termo, dados)

    def test_pacote_sem_credenciais_nem_arquivos_privados(self):
        nomes = _arquivo()
        privados = [n for n in nomes if re.search(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_rsa.*|.*\.p12|\.npmrc|\.pypirc)$", n)]
        self.assertEqual(privados, [])
        segredo = re.compile(r"(ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|"
                             r"sk-ant-[A-Za-z0-9-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[bap]-[A-Za-z0-9-]{10,})")
        achados = []
        for n in nomes:
            p = ROOT / n
            if p.suffix.lower() in (".png", ".woff2", ".ttf", ".pdf", ".zip"):
                continue
            try:
                t = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            if segredo.search(t):
                achados.append(n)
        self.assertEqual(achados, [])

    def test_pacote_traz_o_necessario_para_reproduzir(self):
        nomes = set(_arquivo())
        for n in ("requirements.txt", "requirements.in", "config.yml", "CITATION.cff", "LICENSE",
                  "LICENSE-DADOS.md", "desenvolvimento/REPRODUCAO.md", "organic-discovery/ZENODO.md",
                  "organic-discovery/RELEASE-v1.6.0.md", "organic-discovery/RELEASE-v1.7.0.md",
                  "organic-discovery/RELEASE-v1.8.0.md", "docs/calculos.js", "scripts/build_ferramentas.py",
                  "servidor_mcp/servidor.py", "servidor_mcp/requirements.txt", ".github/workflows/monitor.yml",
                  "scripts/fetch.py", "scripts/backfill.py", "scripts/build_pages.py", "scripts/build_correcao.py"):
            self.assertIn(n, nomes)
