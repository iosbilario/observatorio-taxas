"""Páginas /comparador/ e /simulador-cdi/ (scripts/build_ferramentas.py).

    python -m unittest tests.test_ferramentas_paginas -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 50
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import adsense  # noqa: E402
import build_ferramentas as bf  # noqa: E402
from build_pages import fmt_num  # noqa: E402

PAGINAS = {"comparador/index.html": bf.URL_COMP, "simulador-cdi/index.html": bf.URL_SIM}


def ler(rel: str) -> str:
    return (DOCS / rel).read_text(encoding="utf-8")


def jsonlds(h: str) -> list[dict]:
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]


def texto(h: str) -> str:
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


class TestHtml(unittest.TestCase):
    def test_metadados_seo(self):
        for rel, url in PAGINAS.items():
            h = ler(rel)
            self.assertEqual(len(re.findall(r"<h1\b", h)), 1, rel)
            self.assertRegex(h, rf'<link rel="canonical" href="{re.escape(url)}"/>')
            title = re.search(r"<title>(.*?)</title>", h).group(1)
            self.assertLessEqual(len(title), 70, rel)
            desc = re.search(r'<meta name="description" content="([^"]*)"', h).group(1)
            self.assertTrue(80 <= len(desc) <= 300, (rel, len(desc)))
            for og in ("og:title", "og:description", "og:url", "og:image"):
                self.assertIn(f'property="{og}"', h, (rel, og))
            self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1"/>', h)

    def test_jsonld_coerente_com_o_conteudo_visivel(self):
        for rel, url in PAGINAS.items():
            h = ler(rel)
            tipos = {d["@type"]: d for d in jsonlds(h)}
            self.assertEqual(set(tipos), {"WebApplication", "FAQPage", "BreadcrumbList"}, rel)
            self.assertEqual(tipos["WebApplication"]["url"], url)
            self.assertEqual(tipos["WebApplication"]["offers"]["price"], "0")
            visivel = texto(h)
            for q in tipos["FAQPage"]["mainEntity"]:
                self.assertIn(q["name"], visivel, rel)
                self.assertIn(q["acceptedAnswer"]["text"][:60], visivel, rel)
            self.assertEqual(tipos["BreadcrumbList"]["itemListElement"][-1]["item"], url)

    def test_conteudo_util_sem_javascript(self):
        for rel in PAGINAS:
            t = texto(ler(rel))
            for termo in ("Metodologia", "Fontes oficiais", "Perguntas e respostas", "SGS", "4389", "433"):
                self.assertIn(termo, t, (rel, termo))
            self.assertIn("<noscript>", ler(rel))
        comp = texto(ler("comparador/index.html"))
        self.assertRegex(comp, r"o CDI acumulou \d+,\d{2}% ?, a Selic acumulou \d+,\d{2}% ? e o IPCA acumulou \d+,\d{2}%")
        self.assertRegex(texto(ler("simulador-cdi/index.html")), r"R\$ 1\.000,00 a 100% do CDI, de \d\d/\d\d/\d{4}")

    def test_sem_recomendacao_de_investimento(self):
        for rel in PAGINAS:
            t = texto(ler(rel)).lower()
            self.assertIn("não são recomendação de investimento", t)
            for proibido in ("recomendamos", "invista já", "melhor investimento", "clique no anúncio"):
                self.assertNotIn(proibido, t, (rel, proibido))
        self.assertIn("o IPCA mede a variação de preços", texto(ler("comparador/index.html")))

    def test_scripts_so_de_mesma_origem_e_csp_estrita(self):
        for rel in PAGINAS:
            h = ler(rel)
            csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', h).group(1)
            self.assertNotIn("'unsafe-inline'", csp.split("script-src")[1].split(";")[0])
            for attrs, corpo in re.findall(r"<script\b([^>]*)>(.*?)</script>", h, re.S):
                self.assertTrue("src=" in attrs or "application/ld+json" in attrs, rel)
            self.assertNotRegex(h, r'\son[a-z]+="')

    def test_tabelas_com_rolagem_horizontal_no_celular(self):
        for rel in PAGINAS:
            h = ler(rel)
            for m in re.finditer(r"<table\b", h):
                antes = h[:m.start()]
                self.assertGreater(antes.rfind('<div class="rolagem"'), antes.rfind("</div>"), rel)
        self.assertIn("minmax(min(200px,100%),1fr)", bf.FERR_CSS)
        self.assertIn(".rolagem{overflow-x:auto}", bf.FERR_CSS)

    def test_links_internos_existem(self):
        for rel in PAGINAS:
            for alvo in re.findall(r'href="(/[^"#?]*)', ler(rel)):
                caminho = DOCS / alvo.lstrip("/")
                self.assertTrue(caminho.is_file() or (caminho / "index.html").is_file(), (rel, alvo))

    def test_sitemap_rodape_e_llms(self):
        sitemap = ler("sitemap.xml")
        rodape = (ROOT / "partials" / "rodape.html").read_text(encoding="utf-8")
        for url in PAGINAS.values():
            self.assertIn(f"<loc>{url}</loc>", sitemap)
        self.assertNotRegex(sitemap, r"<loc>[^<]*(comparador|simulador-cdi)/\?")
        self.assertIn("comparador/", rodape)
        self.assertIn("simulador-cdi/", rodape)
        self.assertIn("simulador-cdi/", ler("llms.txt"))
        self.assertIn('href="https://observatoriodetaxas.tec.br/simulador-cdi/"', ler("indicadores/cdi/index.html"))


class TestNumerosAssados(unittest.TestCase):
    """O exemplo estático bate com uma referência independente (Decimal)."""

    def test_comparador_padrao(self):
        c = bf.comparador_padrao()
        self.assertEqual(len(c["linhas"]), 12)
        for k, cod in (("cdi", 4391), ("selic", 4390), ("ipca", 433)):
            f = Decimal(1)
            for o in json.loads((ROOT / "data" / f"{cod}_history.json").read_text(encoding="utf-8")):
                d, m, a = o["data"].split("/")
                if c["de"] <= f"{a}-{m}" <= c["ate"]:
                    f *= 1 + Decimal(o["valor"]) / 100
            self.assertAlmostEqual(c["pct"][k], float((f - 1) * 100), places=10)
            self.assertIn(f"acumulou <b>{fmt_num(c['pct'][k], 2)}%</b>", ler("comparador/index.html"))

    def test_comparador_exclui_mes_corrente_parcial(self):
        c = bf.comparador_padrao()
        ultimo_di = json.loads((ROOT / "data" / "4389_history.json").read_text(encoding="utf-8"))[-1]["data"]
        d, m, a = ultimo_di.split("/")
        self.assertLess(c["fechado"]["cdi"], f"{a}-{m}")

    def test_simulador_padrao(self):
        s = bf.simulacao_padrao()
        um = Decimal(1)
        for cen in s["cenarios"]:
            saldo = Decimal(1000)
            for o in json.loads((ROOT / "data" / "4389_history.json").read_text(encoding="utf-8")):
                d, m, a = o["data"].split("/")
                if s["inicio"].isoformat() <= f"{a}-{m}-{d}" < s["fim"].isoformat():
                    saldo *= um + Decimal(cen["pct"]) / 100 * ((um + Decimal(o["valor"]) / 100) ** (um / 252) - um)
            self.assertAlmostEqual(cen["bruto"], float(saldo), places=8)
            rend = saldo - 1000
            ir = (rend * Decimal(str(s["aliquota_ir"])) / 100).quantize(Decimal("0.01"))
            self.assertAlmostEqual(cen["ir"], float(ir), places=2)
        self.assertIn(f"<b>R$ {fmt_num(s['cenarios'][1]['bruto'], 2)}</b> brutos", ler("simulador-cdi/index.html"))


class TestAdSense(unittest.TestCase):
    def test_espacos_marcados_fora_das_operacoes_e_vazios(self):
        for rel, nome in (("comparador/index.html", "comparador"), ("simulador-cdi/index.html", "simulador")):
            h = ler(rel)
            espacos = adsense.RE_ESPACO.findall(h)
            self.assertEqual([(e[1], e[2]) for e in espacos], [(nome, "")], rel)
            pos = h.index(f"<!-- anuncio:{nome}:inicio -->")
            self.assertGreater(pos, h.index('id="resultado"'), rel)        # depois do resultado
            self.assertLess(pos, h.index('id="met-t"'), rel)               # antes da metodologia
            self.assertNotIn("adsbygoogle", h)

    def test_com_anuncios_ligados_os_scripts_da_ferramenta_continuam_carregando(self):
        c = {"client": "ca-pub-4229313749435489", "slots": {"simulador": "1234567890"}, "ads_txt": "", "ativo": True,
             "consentimento": True}
        original = ler("simulador-cdi/index.html")
        ligado = adsense.ligar(original, c)
        self.assertNotIn('<script src="/simulador-cdi.js" defer></script>', ligado)
        self.assertIn('e.src="/simulador-cdi.js"', ligado)
        self.assertIn("'strict-dynamic'", ligado)
        for corpo in re.findall(r"<script>(.*?)</script>", ligado, re.S):
            import base64
            import hashlib
            h = "'sha256-" + base64.b64encode(hashlib.sha256(corpo.encode()).digest()).decode() + "'"
            self.assertIn(h, ligado)
        self.assertEqual(adsense.desligar(ligado), original)


if __name__ == "__main__":
    unittest.main()
