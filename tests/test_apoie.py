"""Testes da página /apoie/ (contribuição voluntária via Pix).

    python -m unittest tests.test_apoie -v

A correspondência QR × payload por decodificação exige `segno` e `zxing-cpp`
(só em máquina de desenvolvimento); sem eles esse teste é pulado e os demais
rodam só com stdlib.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pix  # noqa: E402
import seo_audit  # noqa: E402

DOCS = ROOT / "docs"
PAGINA = DOCS / "apoie" / "index.html"
QR = DOCS / "apoie" / "pix-qr.svg"
URL = "https://observatoriodetaxas.tec.br/apoie/"


def html() -> str:
    return PAGINA.read_text(encoding="utf-8")


class TestPayloadPix(unittest.TestCase):
    def test_payload_valido_estatico_e_sem_valor(self):
        info = pix.validar(pix.PAYLOAD)
        self.assertEqual(info["recebedor"], "LBP TECNOLOGIA")
        self.assertEqual(info["cidade"], "SAO PAULO")
        self.assertTrue(info["estatico"])
        self.assertIsNone(info["valor_fixo"])
        self.assertNotIn("54", dict(pix.tlv(pix.PAYLOAD)))

    def test_crc16_confere_e_detecta_alteracao(self):
        self.assertEqual(pix.crc16(pix.PAYLOAD[:-4]), pix.PAYLOAD[-4:])
        self.assertEqual(pix.crc16("123456789"), "29B1")      # vetor de referência CRC-16/CCITT-FALSE
        adulterado = pix.PAYLOAD.replace("LBP TECNOLOGIA", "LBP TECNOLOGIB")
        with self.assertRaises(ValueError):
            pix.validar(adulterado)

    def test_rejeita_valor_fixo_e_qr_dinamico(self):
        corpo = pix.PAYLOAD[:-4]                      # termina em "6304"
        com_valor = corpo.replace("5802BR", "540510.005802BR")
        with self.assertRaises(ValueError) as e:
            pix.validar(com_valor + pix.crc16(com_valor))
        self.assertIn("valor fixo", str(e.exception))
        dinamico = corpo.replace("010211", "010212")
        with self.assertRaises(ValueError) as e:
            pix.validar(dinamico + pix.crc16(dinamico))
        self.assertIn("estático", str(e.exception))

    def test_pagina_traz_o_payload_exato_uma_vez(self):
        h = html()
        m = re.search(r'<textarea[^>]*id="pix-cc"[^>]*>([^<]*)</textarea>', h)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), pix.PAYLOAD)
        self.assertEqual(h.count(pix.PAYLOAD), 1)

    def test_chave_nao_aparece_separada(self):
        chave = dict(pix.tlv(dict(pix.tlv(pix.PAYLOAD))["26"]))["01"]
        self.assertEqual(html().count(chave), 1, "a chave só pode aparecer dentro do payload")

    def test_payload_fora_de_urls_e_sem_formulario(self):
        h = html()
        for attr in re.findall(r'(?:href|src|action)="([^"]*)"', h):
            self.assertNotIn("br.gov.bcb.pix", attr)
        self.assertNotRegex(h, r"<form\b")
        self.assertNotRegex(h, r'<input\b')
        self.assertNotRegex(h.lower(), r"\bcpf\b|comprovante")


class TestQRCode(unittest.TestCase):
    def test_svg_limpo_preto_e_branco_com_viewbox(self):
        svg = QR.read_text(encoding="utf-8")
        self.assertIn("viewBox=", svg)
        self.assertNotRegex(svg, r"<text\b|<image\b|<script\b")
        cores = set(re.findall(r'(?:fill|stroke)="([^"]+)"', svg))
        self.assertTrue(cores <= {"#fff", "#ffffff", "#000", "#000000"}, cores)

    def test_qr_decodifica_exatamente_o_payload(self):
        try:
            import io
            import segno
            import zxingcpp
            from PIL import Image
        except ImportError:
            self.skipTest("segno/zxing-cpp não instalados (ferramentas só de desenvolvimento)")
        # 1) o SVG versionado é o que o gerador produz hoje (mesmo payload)
        q = segno.make(pix.PAYLOAD, error="m", micro=False, mode="byte")
        buf = io.BytesIO()
        q.save(buf, kind="svg", scale=8, border=4, dark="#000000", light="#ffffff",
               xmldecl=False, svgns=True, title="QR Code Pix", nl=True, omitsize=True)
        self.assertEqual(buf.getvalue().decode("utf-8"), QR.read_text(encoding="utf-8"))
        # 2) um leitor independente (ZXing) lê o mesmo conteúdo
        png = io.BytesIO()
        q.save(png, kind="png", scale=8, border=4)
        png.seek(0)
        lidos = zxingcpp.read_barcodes(Image.open(png))
        self.assertEqual([r.text for r in lidos], [pix.PAYLOAD])


class TestPagina(unittest.TestCase):
    def test_metadados_e_canonical(self):
        pg = seo_audit.analisar_pagina(PAGINA, DOCS)
        self.assertEqual(pg["canonicals"], [URL])
        self.assertEqual(pg["og_url"], URL)
        self.assertEqual(pg["h1"], ["Apoie o Observatório de Taxas"])
        self.assertTrue(pg["indexavel"])
        self.assertIn("Pix", pg["title"])

    def test_imagem_do_qr_tem_alt(self):
        m = re.search(r'<img src="pix-qr.svg"[^>]*alt="([^"]+)"', html())
        self.assertIsNotNone(m)
        self.assertIn("LBP TECNOLOGIA", m.group(1))

    def test_botao_de_copia_acessivel_e_com_alternativa(self):
        h = html()
        self.assertRegex(h, r'<button class="copiar" id="copiar" type="button" hidden>')
        self.assertRegex(h, r'id="status" role="status" aria-live="polite"')
        self.assertIn("navigator.clipboard", h)
        self.assertIn("window.isSecureContext", h)
        self.assertIn('execCommand("copy")', h)
        self.assertNotRegex(h, r"\son[a-z]+=", "handler inline quebraria a CSP por hash")

    def test_csp_por_hash_sem_unsafe_inline_no_script(self):
        csp = re.search(r'Content-Security-Policy" content="([^"]*)"', html()).group(1)
        script = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
        self.assertNotIn("'unsafe-inline'", script)
        self.assertIn("'sha256-", script)
        self.assertNotIn("pix", csp.lower())

    def test_conteudo_sem_numeros_ficticios(self):
        texto = seo_audit.analisar_pagina(PAGINA, DOCS)["texto"]
        self.assertNotRegex(texto, r"R\$\s?\d", "valor sugerido ou arrecadado não deve aparecer")
        self.assertNotRegex(texto.lower(), r"apoiadores|arrecadad|depoimento|anônim")
        self.assertIn("valor que quiser", texto)
        self.assertIn("permanece gratuito", texto)

    def test_no_sitemap_e_ligada_pelo_site(self):
        locs = [u["loc"] for u in seo_audit.sitemap_urls(DOCS)]
        self.assertIn(URL, locs)
        for rel in ("index.html", "reajuste/index.html", "reajuste/igpm-julho-2026/index.html",
                    "correcao/index.html", "rebobinar.html", "var.html", "retransmissora.html"):
            pg = seo_audit.analisar_pagina(DOCS / rel, DOCS)
            self.assertIn(URL, seo_audit.links_internos(pg), rel)
            self.assertIn("Apoie o projeto ♡", (DOCS / rel).read_text(encoding="utf-8"), rel)

    def test_funding_yml(self):
        txt = (ROOT / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
        self.assertEqual(txt.strip(), 'custom:\n  - "https://observatoriodetaxas.tec.br/apoie/"')
        self.assertNotRegex(txt, r"(?m)^github:")


if __name__ == "__main__":
    unittest.main()
