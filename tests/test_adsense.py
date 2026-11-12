"""Testes da preparação para o Google AdSense (scripts/adsense.py).

    python -m unittest tests.test_adsense -v

A simulação de ativação roda numa CÓPIA temporária de docs/ com um config
temporário; nada é ligado no site real.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import adsense  # noqa: E402
import seo_audit  # noqa: E402
from csp_hashes import RE_META_CSP, hashes_inline  # noqa: E402

DOCS = ROOT / "docs"
PUB = "4229313749435489"
LINHA = f"google.com, pub-{PUB}, DIRECT, f08c47fec0942fa0"
COM_ESPACO = ["index.html", "reajuste/index.html", "reajuste/igpm-julho-2026/index.html",
              "correcao/index.html", "correcao/ipca/index.html"]
SEM_ANUNCIO = ["embed.html", "rebobinar.html", "var.html", "retransmissora.html",
               "apoie/index.html", "privacidade/index.html", "sobre/index.html", "admin/index.html"]


def csp(html: str) -> dict[str, list[str]]:
    m = RE_META_CSP.search(html)
    return {d.split()[0]: d.split()[1:] for d in (x.strip() for x in m.group(2).split(";")) if d}


class TestConfiguracaoEAdsTxt(unittest.TestCase):
    def test_config_centralizada_com_o_id_fornecido(self):
        c = adsense.carregar()
        self.assertEqual(c["client"], f"ca-pub-{PUB}")
        self.assertEqual(c["ads_txt"], LINHA)
        self.assertFalse(c["ativo"], "anúncios devem ficar desligados até aprovação e consentimento")
        self.assertFalse(c["consentimento"])

    def test_ads_txt_na_raiz_publicada_exatamente_como_o_google_forneceu(self):
        self.assertEqual((DOCS / "ads.txt").read_text(encoding="utf-8"), LINHA + "\n")
        self.assertTrue((DOCS / "CNAME").read_text(encoding="utf-8").strip() == "observatoriodetaxas.tec.br")
        self.assertNotIn("ads.txt", (DOCS / "robots.txt").read_text(encoding="utf-8"))

    def test_rejeita_id_ficticio_ou_divergente(self):
        with tempfile.TemporaryDirectory() as d:
            for client, linha in (("ca-pub-1234", LINHA), ("ca-pub-0000000000000000", LINHA),
                                  (f"ca-pub-{PUB}", "google.com, pub-1111111111111111, DIRECT, f08c47fec0942fa0"),
                                  (f"ca-pub-{PUB}", f"google.com, pub-{PUB}, RESELLER, f08c47fec0942fa0")):
                cfg = Path(d) / "c.yml"
                cfg.write_text(yaml.safe_dump({"adsense": {"client": client, "ads_txt": linha}}), encoding="utf-8")
                with self.assertRaises(SystemExit):
                    adsense.carregar(cfg)

    def test_nenhum_identificador_ficticio_no_repositorio_publicado(self):
        achados = []
        for f in list(DOCS.rglob("*.html")) + list(DOCS.rglob("*.txt")) + [ROOT / "config.yml"]:
            t = f.read_text(encoding="utf-8", errors="ignore")
            for pub in re.findall(r"pub-(\d+)", t):
                if pub != PUB:
                    achados.append(f"{f}: pub-{pub}")
        self.assertEqual(achados, [])


class TestDesligado(unittest.TestCase):
    def test_nenhum_codigo_de_anuncio_publicado(self):
        for f in DOCS.rglob("*.html"):
            t = f.read_text(encoding="utf-8")
            for termo in ("adsbygoogle", "googlesyndication", "<!-- adsense:inicio", "'strict-dynamic'"):
                self.assertNotIn(termo, t, f"{f}: {termo}")

    def test_espacos_marcados_e_vazios_nas_paginas_elegiveis(self):
        for rel in COM_ESPACO:
            t = (DOCS / rel).read_text(encoding="utf-8")
            espacos = adsense.RE_ESPACO.findall(t)
            self.assertEqual(len(espacos), 1, rel)
            self.assertEqual(espacos[0][2], "", rel)
        for rel in SEM_ANUNCIO:
            self.assertNotIn("<!-- anuncio:", (DOCS / rel).read_text(encoding="utf-8"), rel)

    def test_estado_conferido(self):
        self.assertEqual(adsense.main(["--conferir"]), 0)

    def test_sem_handlers_inline_nas_paginas_com_espaco(self):
        for rel in COM_ESPACO + ["reajuste/ipca-dezembro-2015/index.html", "correcao/igpm/index.html"]:
            self.assertNotRegex((DOCS / rel).read_text(encoding="utf-8"), r'\son[a-z]+="', rel)

    def test_paginas_institucionais_ligadas_e_no_sitemap(self):
        locs = [u["loc"] for u in seo_audit.sitemap_urls(DOCS)]
        for slug in ("sobre", "privacidade"):
            url = f"https://observatoriodetaxas.tec.br/{slug}/"
            self.assertIn(url, locs)
            pg = seo_audit.analisar_pagina(DOCS / slug / "index.html", DOCS)
            self.assertEqual(pg["canonicals"], [url])
            self.assertEqual(len(pg["h1"]), 1)
            for rel in ("index.html", "reajuste/igpm-julho-2026/index.html", "correcao/index.html", "apoie/index.html"):
                self.assertIn(url, seo_audit.links_internos(seo_audit.analisar_pagina(DOCS / rel, DOCS)), rel)

    def test_politica_de_privacidade_tem_as_divulgacoes_do_adsense(self):
        t = seo_audit.analisar_pagina(DOCS / "privacidade" / "index.html", DOCS)["texto"]
        for trecho in ("Fornecedores terceiros, incluindo o Google, usam cookies",
                       "Configurações de anúncios do Google", "www.aboutads.info",
                       "Espaço Econômico Europeu", "contato@observatoriodetaxas.tec.br"):
            self.assertIn(trecho, t)
        h = (DOCS / "privacidade" / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://adssettings.google.com/", h)


class TestAtivacaoSimulada(unittest.TestCase):
    """Liga numa cópia de docs/ com id de espaço de teste e confere o resultado."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.docs = Path(cls.tmp.name) / "docs"
        cls.docs.mkdir()
        for rel in COM_ESPACO + SEM_ANUNCIO + ["reajuste/ipca-dezembro-2015/index.html"]:
            (cls.docs / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DOCS / rel, cls.docs / rel)
        base = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["adsense"]
        cls.cfg_on = Path(cls.tmp.name) / "on.yml"
        cls.cfg_off = Path(cls.tmp.name) / "off.yml"
        on = dict(base, ativo=True, consentimento_configurado=True,
                  slots={n: "9999999999" for n in adsense.ESPACOS})
        cls.cfg_on.write_text(yaml.safe_dump({"adsense": on}, allow_unicode=True), encoding="utf-8")
        cls.cfg_off.write_text(yaml.safe_dump({"adsense": base}, allow_unicode=True), encoding="utf-8")
        cls.antes = {f.relative_to(cls.docs).as_posix(): f.read_text(encoding="utf-8") for f in cls.docs.rglob("*.html")}
        assert adsense.main(["--config", str(cls.cfg_on), "--docs", str(cls.docs)]) == 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ler(self, rel):
        return (self.docs / rel).read_text(encoding="utf-8")

    def test_sem_consentimento_nao_liga(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs"
            shutil.copytree(DOCS / "reajuste" / "igpm-julho-2026", docs / "reajuste" / "igpm-julho-2026")
            (docs / "privacidade").mkdir()
            (docs / "privacidade" / "index.html").write_text("x", encoding="utf-8")
            base = yaml.safe_load(self.cfg_on.read_text(encoding="utf-8"))["adsense"]
            cfg = Path(d) / "c.yml"
            cfg.write_text(yaml.safe_dump({"adsense": dict(base, consentimento_configurado=False)}), encoding="utf-8")
            adsense.main(["--config", str(cfg), "--docs", str(docs)])
            self.assertNotIn("adsbygoogle", (docs / "reajuste" / "igpm-julho-2026" / "index.html").read_text(encoding="utf-8"))

    def test_anuncios_so_nas_paginas_elegiveis(self):
        for rel in COM_ESPACO:
            self.assertEqual(self.ler(rel).count('class="adsbygoogle"'), 1, rel)
        for rel in SEM_ANUNCIO:
            self.assertNotIn("adsbygoogle", self.ler(rel), rel)

    def test_espaco_rotulado_e_fora_de_formularios_e_resultados(self):
        for rel in COM_ESPACO:
            h = self.ler(rel)
            ini = h.index('<aside class="pub"')
            antes = h[:ini]
            self.assertEqual(antes.count("<form"), antes.count("</form>"), f"{rel}: anúncio dentro de formulário")
            self.assertIn('aria-label="Publicidade"', h)
            self.assertIn(">Publicidade</p>", h)
            self.assertRegex(h, r'<aside class="pub"[^>]*min-height:300px')
            bloco = h[ini:h.index("</aside>", ini)]
            self.assertNotRegex(bloco, r"<button|<form|<input|id=\"res\"")
        mes = self.ler("reajuste/igpm-julho-2026/index.html")
        self.assertGreater(mes.index('<aside class="pub"'), mes.index("<!-- conteudo:fim -->"))

    def test_csp_estrita_no_formato_do_adsense_e_hashes_corretos(self):
        for rel in COM_ESPACO:
            h = self.ler(rel)
            d = csp(h)
            ss = d["script-src"]
            for f in ("'strict-dynamic'", "'unsafe-inline'", "'unsafe-eval'", "https:", "http:"):
                self.assertIn(f, ss, rel)
            self.assertEqual(sorted(x for x in ss if x.startswith("'sha256-")), sorted(hashes_inline(h)), rel)
            self.assertIn("'none'", d["object-src"])
            self.assertIn("https:", d["frame-src"])
            self.assertNotRegex(h, r'<script data-goatcounter[^>]*src=', "GoatCounter deve vir pelo carregador")
            self.assertIn("gc.zgo.at/count.js", h)
            self.assertIn(f"adsbygoogle.js?client=ca-pub-{PUB}", h)

    def test_desligar_restaura_exatamente_o_original(self):
        try:
            adsense.main(["--config", str(self.cfg_off), "--docs", str(self.docs)])
            depois = {f.relative_to(self.docs).as_posix(): f.read_text(encoding="utf-8") for f in self.docs.rglob("*.html")}
            for rel in self.antes:
                self.assertEqual(depois[rel], self.antes[rel], rel)
        finally:
            adsense.main(["--config", str(self.cfg_on), "--docs", str(self.docs)])

    def test_peso_adicional_pequeno(self):
        h_on = self.ler("reajuste/igpm-julho-2026/index.html")
        h_off = self.antes["reajuste/igpm-julho-2026/index.html"]
        self.assertLess(len(h_on.encode()) - len(h_off.encode()), 3000)


if __name__ == "__main__":
    unittest.main()
