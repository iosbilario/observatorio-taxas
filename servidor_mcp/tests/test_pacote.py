"""Validação do pacote do ChatGPT e dos materiais públicos exigidos pelas duas plataformas.

Limites conferidos na documentação de submissão da OpenAI (developers.openai.com/plugins/deploy/submission).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import struct

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "servidor_mcp" / "plugin-openai"
SITE = "https://observatoriodetaxas.tec.br/"


class TestPacoteOpenAI(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((PKG / "plugin.json").read_text(encoding="utf-8"))
        self.ui = self.p["extensions"]["com.openai"]["interface"]
        self.rev = self.p["extensions"]["com.openai"]["review"]

    def test_identidade_do_pacote(self):
        self.assertEqual(self.p["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertRegex(self.p["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(self.p["name"]), 64)
        self.assertRegex(self.p["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(self.p["author"]["name"], "LBP Tecnologia")

    def test_listagem_dentro_dos_limites(self):
        self.assertEqual(self.ui["displayName"], "Observatório de Taxas")
        self.assertLessEqual(len(self.ui["displayName"]), 30)
        self.assertLessEqual(len(self.ui["shortDescription"]), 30)
        self.assertLessEqual(len(self.ui["longDescription"]), 4000)
        self.assertLessEqual(len(self.ui["developerName"]), 80)
        self.assertLessEqual(len(self.ui["defaultPrompt"]), 3)
        for pr in self.ui["defaultPrompt"]:
            self.assertLessEqual(len(pr), 128, pr)
        self.assertLessEqual(len(self.ui["capabilities"]), 20)
        for cor in ("brandColor", "brandColorDark"):
            self.assertRegex(self.ui[cor], r"^#[0-9A-F]{6}$")

    def test_urls_obrigatorias_https_e_publicadas(self):
        paginas = {"websiteURL": "index.html", "supportURL": "mcp/index.html",
                   "privacyPolicyURL": "privacidade/index.html", "termsOfServiceURL": "termos/index.html"}
        for campo, arq in paginas.items():
            self.assertTrue(self.ui[campo].startswith(SITE), campo)
            self.assertTrue((ROOT / "docs" / arq).is_file(), campo)

    def test_icones_quadrados(self):
        for campo in ("logo", "composerIcon"):
            caminho = PKG / self.ui[campo]
            self.assertTrue(self.ui[campo].startswith("./"))
            cab = caminho.read_bytes()[:24]
            self.assertEqual(cab[:8], b"\x89PNG\r\n\x1a\n")
            larg, alt = struct.unpack(">II", cab[16:24])        # IHDR, sem depender de Pillow
            self.assertEqual(larg, alt)
            self.assertGreaterEqual(larg, 48)
            self.assertLess(caminho.stat().st_size, 5 * 1024 * 1024)

    def test_casos_de_revisao(self):
        casos = self.rev["test_cases"]
        self.assertEqual(len(casos["positive"]), 5)
        self.assertEqual(len(casos["negative"]), 3)
        ferramentas = {"get_latest_indicator", "get_indicator_history", "calculate_adjustment", "compare_indicators"}
        usadas = set()
        for c in casos["positive"]:
            for campo in ("description", "prompt", "tools_triggered", "expected_behavior"):
                self.assertTrue(c[campo].strip(), campo)
            nomes = {x.strip() for x in c["tools_triggered"].split(",")}
            self.assertTrue(nomes <= ferramentas, nomes)
            usadas |= nomes
        self.assertEqual(usadas, ferramentas, "toda ferramenta aparece em algum caso positivo")
        for c in casos["negative"]:
            self.assertTrue(c["description"] and c["prompt"])
        self.assertIs(self.rev["commerce"], False)

    def test_sem_credenciais_no_pacote(self):
        txt = (PKG / "plugin.json").read_text(encoding="utf-8")
        self.assertNotIn("test_credentials", txt)
        self.assertNotIn("reviewer_instructions", txt)
        self.assertNotRegex(txt, r"(?i)(password|senha|token|secret)\"\s*:")

    def test_video_pendente_ou_https(self):
        url = self.rev["demo_recording_url"]
        self.assertTrue(url == "" or url.startswith("https://"), "demo_recording_url: vazio até o vídeo existir")

    def test_mcp_json_um_servidor_streamable(self):
        m = json.loads((PKG / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(len(m["mcpServers"]), 1)
        srv = next(iter(m["mcpServers"].values()))
        self.assertEqual(srv["type"], "streamable-http")
        self.assertRegex(srv["url"], r"^https://[^/]+/mcp$")


class TestMateriaisPublicos(unittest.TestCase):
    def test_pagina_mcp_lista_as_ferramentas_e_suspensoes(self):
        h = (ROOT / "docs" / "mcp" / "index.html").read_text(encoding="utf-8")
        for t in ("get_latest_indicator", "get_indicator_history", "calculate_adjustment", "compare_indicators"):
            self.assertIn(t, h)
        self.assertIn("Suspensos nesta integração", h)
        self.assertIn("Não são dados em tempo real", h)

    def test_privacidade_cobre_o_mcp(self):
        h = (ROOT / "docs" / "privacidade" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="mcp-t"', h)
        self.assertIn("não são gravados", h)

    def test_readme_tem_checklists(self):
        r = (ROOT / "servidor_mcp" / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Checklist — ChatGPT", r)
        self.assertIn("## Checklist — Claude", r)
        self.assertNotRegex(r, r"sk-[A-Za-z0-9]{20,}")


if __name__ == "__main__":
    unittest.main()
