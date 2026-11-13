"""Vitrine de indicadores (docs/indicadores/), gerada por scripts/build_indicadores.py.

    python -m unittest tests.test_indicadores -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_indicadores as bi  # noqa: E402
from servidor_mcp import catalogo as cat  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["series"]


def ler(cod: int) -> str:
    return (DOCS / "indicadores" / bi.PAGINAS[cod]["slug"] / "index.html").read_text(encoding="utf-8")


def jsonlds(html: str) -> list[dict]:
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


class TestVitrine(unittest.TestCase):
    def test_toda_serie_do_config_tem_pagina_e_slug_unico(self):
        slugs = [bi.PAGINAS[s["codigo"]]["slug"] for s in CFG]
        self.assertEqual(len(slugs), len(set(slugs)))
        for s in CFG:
            self.assertTrue((DOCS / "indicadores" / bi.PAGINAS[s["codigo"]]["slug"] / "index.html").is_file(), s)

    def test_primeira_frase_traz_valor_referencia_e_produtor_do_ultimo_mes_fechado(self):
        for s in CFG:
            cod = s["codigo"]
            pts, _ = bi.completos(cod, bi.load_history(cod))
            esperado = bi.valor(cod, pts[-1]["valor"])
            lead = re.search(r'<p class="lead">(.*?)</p>', ler(cod), re.S).group(1)
            self.assertIn(f"<b>{esperado}</b>", lead, cod)
            self.assertIn(bi.data_ref(cod, pts[-1]["dt"]), lead, cod)
            self.assertIn(cat.SERIES[cod]["produtor"]["nome"], lead, cod)
            self.assertIn(f"série {cod}", lead, cod)

    def test_valor_bate_com_o_json_publicado(self):
        for cod in (432, 1, 13621, 20539):
            bruto = json.loads((ROOT / "data" / f"{cod}_history.json").read_text(encoding="utf-8"))
            self.assertIn(f"<b>{bi.valor(cod, float(bruto[-1]['valor']))}</b>", ler(cod), cod)

    def test_acumulado_12_meses_do_ipca_bate_com_a_serie_13522(self):
        html = ler(433)
        ipca12 = json.loads((ROOT / "data" / "13522_history.json").read_text(encoding="utf-8"))[-1]
        pts = bi.load_history(433)
        if pts[-1]["dt"].strftime("01/%m/%Y") == ipca12["data"]:
            ac = float(ipca12["valor"])
            self.assertIn(f"<b>{bi.fmt_num(ac, 2)}%</b>", html)

    def test_mes_corrente_parcial_fica_fora_dos_numeros_principais(self):
        pts = bi.load_history(4391)
        fechados, parcial = bi.completos(4391, pts)
        if parcial:
            self.assertIn("ainda está em andamento", ler(4391))
            self.assertIn(f"<b>{bi.valor(4391, fechados[-1]['valor'])}</b>", ler(4391))

    def test_jsonld_dataset_faq_e_breadcrumb(self):
        for s in CFG:
            cod = s["codigo"]
            tipos = {d.get("@type"): d for d in jsonlds(ler(cod))}
            self.assertEqual(set(tipos), {"Dataset", "FAQPage", "BreadcrumbList"}, cod)
            ds = tipos["Dataset"]
            self.assertEqual(ds["creator"]["name"], cat.SERIES[cod]["produtor"]["nome"], cod)
            self.assertEqual(ds["license"], bi.licenca_url(cod), cod)
            self.assertIn(f"{bi.BASE_URL}/data/{cod}_history.json",
                          [d["contentUrl"] for d in ds["distribution"]], cod)
            self.assertGreaterEqual(len(tipos["FAQPage"]["mainEntity"]), 5, cod)

    def test_licenca_odbl_so_para_series_do_bcb(self):
        for s in CFG:
            cod = s["codigo"]
            if cat.SERIES[cod]["produtor"] is cat.BCB:
                self.assertEqual(bi.licenca_url(cod), bi.ODBL_URL, cod)
            else:
                self.assertEqual(bi.licenca_url(cod), bi.LICENCA_DADOS_URL, cod)

    def test_sem_script_inline_executavel_e_csp_sem_unsafe_inline(self):
        for s in CFG:
            html = ler(s["codigo"])
            csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', html).group(1)
            self.assertNotIn("'unsafe-inline'", csp.split("script-src")[1].split(";")[0])
            for attrs, corpo in re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S):
                self.assertTrue("src=" in attrs or "application/ld+json" in attrs, s["codigo"])

    def test_hub_lista_todas_as_series_com_link(self):
        hub = (DOCS / "indicadores" / "index.html").read_text(encoding="utf-8")
        for s in CFG:
            self.assertIn(f'href="{bi.url_pagina(s["codigo"])}"', hub, s["codigo"])
        itens = [d for d in jsonlds(hub) if d.get("@type") == "ItemList"][0]
        self.assertEqual(itens["numberOfItems"], len(CFG))

    def test_paginas_no_sitemap_e_no_menu(self):
        sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn(f"<loc>{bi.HUB_URL}</loc>", sitemap)
        for s in CFG:
            self.assertIn(f"<loc>{bi.url_pagina(s['codigo'])}</loc>", sitemap, s["codigo"])
        self.assertIn('data-nav="indicadores" aria-current="page"', ler(432))
        self.assertIn("indicadores/", (DOCS / "llms.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
