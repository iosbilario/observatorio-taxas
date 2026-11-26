"""Entrega 1: leitura mensal do IPCA, divulgações permanentes e RSS.

Dados pequenos e controlados, sem rede (testes de aceite A a D do pedido).

    python -m unittest tests.test_divulgacoes -v
"""

from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_divulgacoes as D  # noqa: E402
import leituras as L  # noqa: E402

SHA1, SHA2, SHA3, SHA4 = ("1" * 40, "2" * 40, "3" * 40, "4" * 40)


def serie(valores: dict[str, float]) -> list[dict]:
    return [{"dt": datetime(int(k[:4]), int(k[5:]), 1), "valor": v} for k, v in sorted(valores.items())]


def treze(ultimo: float = 0.30, anterior: float = 0.50, saiu: float = 0.10) -> dict[str, float]:
    """13 competências (2025-01 a 2026-01): o mês mais recente (0,30%) é menor que
    o anterior (0,50%) e maior que o que sai da janela (0,10%)."""
    v = {L.soma_mes("2025-01", k): 0.40 for k in range(13)}
    v["2025-01"], v["2025-12"], v["2026-01"] = saiu, anterior, ultimo
    return v


def versao(sha: str, data: str) -> dict:
    return {"sha": sha, "curto": sha[:7], "data": data}


class LeituraMensal(unittest.TestCase):

    def test_A_desacelera_no_mes_e_sobe_no_acumulado_com_a_conta_refazivel(self):
        lt = L.leitura_mensal(433, "IPCA", serie(treze()))
        self.assertEqual(lt["competencia"], "2026-01")
        self.assertEqual(lt["lacunas"], [])
        txt = " ".join(lt["frases"])
        self.assertIn("A taxa mensal do IPCA desacelerou de 0,50% em dezembro de 2025 para 0,30% em janeiro de 2026", txt)
        self.assertIn("O acumulado em 12 meses subiu", txt)
        self.assertIn("a variação que entrou na janela, 0,30% em janeiro de 2026, foi maior do que a que saiu, "
                      "0,10% em janeiro de 2025", txt)
        self.assertIn("Os dois movimentos não se contradizem", txt)
        self.assertIn("desacelera para 0,30%", lt["titulo"])
        self.assertIn("sobe para", lt["titulo"])
        # A tabela refaz as duas contas com 12 meses cada.
        atual = [li["valor"] for li in lt["linhas"] if li["janela_atual"]]
        ant = [li["valor"] for li in lt["linhas"] if li["janela_anterior"]]
        self.assertEqual((len(atual), len(ant), len(lt["linhas"])), (12, 12, 13))

        def comp(vs):
            f = 1.0
            for x in vs:
                f *= 1 + x / 100
            return (f - 1) * 100
        self.assertAlmostEqual(comp(atual), lt["acumulado_12m"], places=12)
        self.assertAlmostEqual(comp(ant), lt["acumulado_12m_anterior"], places=12)
        self.assertAlmostEqual(lt["diferenca_pp"], comp(atual) - comp(ant), places=12)
        self.assertEqual([li["papel"] for li in lt["linhas"] if li["papel"]], ["saiu da janela", "entrou na janela"])
        self.assertIn("aritmética", lt["nota"])
        self.assertIn("alimentos, combustíveis ou serviços", lt["nota"])

    def test_A_pagina_mostra_a_tabela_e_abre_sem_javascript(self):
        reg = self._registro(treze())
        html = D.pagina(reg, [reg])
        self.assertIn("A conta, mês a mês", html)
        self.assertEqual(html.count("<tr><td>"), 13)
        self.assertIn("saiu da janela", html)
        self.assertIn("entrou na janela", html)
        self.assertIn("série 433", html)
        self.assertIn(f"commit <a href=\"{D.REPO_URL}/commit/{SHA1}\">{SHA1[:7]}</a>", html)
        self.assertNotIn("<script src", html)
        self.assertIn("Divulgação oficial</dt><dd>não informada", html)

    def test_B_mes_ausente_identificado_e_sem_acumulado_parcial(self):
        v = treze()
        del v["2025-07"]
        lt = L.leitura_mensal(433, "IPCA", serie(v))
        self.assertEqual(lt["lacunas"], ["2025-07"])
        self.assertIsNone(lt["acumulado_12m"])
        self.assertIsNone(lt["acumulado_12m_anterior"])
        txt = " ".join(lt["frases"])
        self.assertIn("Faltam no histórico do Observatório as competências de julho de 2025", txt)
        self.assertNotIn("acumulado em 12 meses subiu", txt)
        self.assertIn("desacelerou", txt)            # a comparação mensal continua sustentada
        self.assertNotIn("acumulado", lt["titulo"])
        reg = self._registro(v)
        html = D.pagina(reg, [reg])
        self.assertIn("<td>—</td>", html)
        self.assertNotRegex(html, r"Acumulado em 12 meses</span><b>\d")

    def test_B_falta_so_o_mes_que_saiu(self):
        v = treze()
        del v["2025-01"]
        lt = L.leitura_mensal(433, "IPCA", serie(v))
        self.assertIsNotNone(lt["acumulado_12m"])       # a janela atual está completa
        self.assertIsNone(lt["acumulado_12m_anterior"])
        self.assertEqual(lt["lacunas"], ["2025-01"])

    def _registro(self, valores):
        arq = {"formato": 1, "publicacoes": []}
        D.registrar(arq, {433: serie(valores)}, {}, versao(SHA1, "2026-02-10T12:00:00Z"))
        return arq["publicacoes"][0]


class ArquivoEFeed(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmp.name) / "docs"
        self.docs.mkdir()
        self.p = mock.patch.object(D, "DOCS", self.docs)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def abre(self, url: str) -> str:
        self.assertTrue(url.startswith(D.BASE_URL + "/"), url)
        return (self.docs / url.removeprefix(D.BASE_URL + "/") / "index.html").read_text(encoding="utf-8")

    def test_C_gerar_duas_vezes_da_o_mesmo_feed_e_cada_item_abre(self):
        arq = {"formato": 1, "publicacoes": []}
        hist = {433: serie(treze())}
        v = versao(SHA1, "2026-02-10T12:00:00Z")
        self.assertEqual(len(D.registrar(arq, hist, {}, v)), 1)
        D.gerar(arq)
        feed1 = (self.docs / "feed.xml").read_bytes()
        pag1 = self.abre(arq["publicacoes"][0]["url"])
        antes = copy.deepcopy(arq)
        # Nova coleta, mesmos valores, outra versão e outro dia: nada muda.
        self.assertEqual(D.registrar(arq, hist, {}, versao(SHA2, "2026-02-11T12:00:00Z")), [])
        self.assertEqual(arq, antes)
        D.gerar(arq)
        self.assertEqual((self.docs / "feed.xml").read_bytes(), feed1)
        self.assertEqual(self.abre(arq["publicacoes"][0]["url"]), pag1)
        rss = ET.fromstring(feed1)
        self.assertEqual(rss.tag, "rss")
        self.assertEqual(rss.get("version"), "2.0")
        itens = rss.findall("channel/item")
        self.assertEqual(len(itens), 1)
        for it in itens:
            link, guid = it.findtext("link"), it.findtext("guid")
            self.assertEqual(link, guid)
            self.assertEqual(it.find("guid").get("isPermaLink"), "true")
            self.assertEqual(it.findtext("pubDate"), "Tue, 10 Feb 2026 12:00:00 GMT")
            self.assertIn("Competência: janeiro de 2026.", it.findtext("description"))
            self.assertIn(it.findtext("title"), self.abre(link).replace("&#x27;", "'"))
        self.assertEqual(rss.find("channel/{http://www.w3.org/2005/Atom}link").get("href"), D.FEED_URL)

    def test_C_escape_de_xml(self):
        arq = {"formato": 1, "publicacoes": []}
        D.registrar(arq, {433: serie(treze())}, {}, versao(SHA1, "2026-02-10T12:00:00Z"))
        arq["publicacoes"][0]["leitura"]["titulo"] = 'IPCA <b>&</b> "teste"'
        rss = ET.fromstring(D.feed(arq["publicacoes"]))
        self.assertEqual(rss.findtext("channel/item/title"), 'IPCA <b>&</b> "teste"')

    def test_D_inicial_duas_revisoes_e_carga_historica(self):
        # Carga histórica: 10 anos de dados entram de uma vez num arquivo vazio.
        v = {L.soma_mes("2016-01", k): 0.3 for k in range(120)}
        v.update({k: x for k, x in treze().items()})
        arq = {"formato": 1, "publicacoes": []}
        novos = D.registrar(arq, {433: serie(v)}, {}, versao(SHA1, "2026-02-10T12:00:00Z"))
        self.assertEqual([n["id"] for n in novos], ["ipca-2026-01"])       # só a competência mais recente
        self.assertTrue(novos[0]["carga_inicial"])
        self.assertIsNone(novos[0]["identificado"])

        # Observação inicial de uma competência nova, identificada por uma coleta.
        v["2026-02"] = 0.20
        mud = {"coletas": [{"gerado_em": "2026-03-10T09:15:00-03:00", "commit": SHA2, "base": SHA1,
                            "novas": [{"codigo": 433, "data": "01/02/2026", "valor": "0.2"}], "revisoes": []}]}
        novos = D.registrar(arq, {433: serie(v)}, mud, versao(SHA2, "2026-03-10T12:16:00Z"))
        self.assertEqual([n["id"] for n in novos], ["ipca-2026-02"])
        self.assertFalse(novos[0]["carga_inicial"])
        self.assertEqual(novos[0]["identificado"], {"gerado_em": "2026-03-10T09:15:00-03:00", "commit": SHA2})

        # Duas revisões sucessivas da mesma competência.
        v["2026-02"] = 0.25
        r1 = D.registrar(arq, {433: serie(v)}, {}, versao(SHA3, "2026-03-20T12:00:00Z"))
        v["2026-02"] = 0.27
        r2 = D.registrar(arq, {433: serie(v)}, {}, versao(SHA4, "2026-03-25T12:00:00Z"))
        self.assertEqual([r["id"] for r in r1 + r2], ["ipca-2026-02-r1", "ipca-2026-02-r2"])
        self.assertEqual(r1[0]["revisa"]["alteracoes"], [{"competencia": "2026-02", "antes": 0.2, "depois": 0.25}])
        self.assertEqual(r2[0]["revisa"]["alteracoes"], [{"competencia": "2026-02", "antes": 0.25, "depois": 0.27}])
        self.assertEqual(r2[0]["revisa"]["versao_anterior"]["sha"], SHA3)
        # A publicação inicial continua no arquivo, igual.
        ini = next(p for p in arq["publicacoes"] if p["id"] == "ipca-2026-02")
        self.assertEqual(ini["leitura"]["entradas"]["2026-02"], 0.2)
        self.assertEqual(ini["versao_dados"]["sha"], SHA2)

        D.gerar(arq)
        self.assertIn("Esta leitura foi revisada depois", self.abre(ini["url"]))
        pr2 = self.abre(r2[0]["url"])
        self.assertIn("O que esta revisão mudou", pr2)
        self.assertIn(f"/{SHA3}/data/433_history.json", pr2)
        self.assertIn(f"/compare/{SHA3}...{SHA4}", pr2)
        rss = ET.fromstring((self.docs / "feed.xml").read_bytes())
        guids = [i.findtext("guid") for i in rss.findall("channel/item")]
        self.assertEqual(len(guids), 4)                  # carga inicial + nova + 2 revisões, não 120
        self.assertEqual(len(set(guids)), 4)
        self.assertTrue(guids[0].endswith("/divulgacoes/ipca/2026-02/revisao-2/"))
        for g in guids:
            self.abre(g)


class Publicado(unittest.TestCase):

    def test_arquivo_publicado_bate_com_paginas_feed_e_ficha(self):
        arq = json.loads((ROOT / "data" / "publicacoes.json").read_text(encoding="utf-8"))
        self.assertEqual(arq, json.loads((DOCS / "data" / "publicacoes.json").read_text(encoding="utf-8")))
        pubs = arq["publicacoes"]
        self.assertTrue(pubs)
        rss = ET.fromstring((DOCS / "feed.xml").read_bytes())
        links = [i.findtext("link") for i in rss.findall("channel/item")]
        self.assertEqual(sorted(links), sorted(p["url"] for p in pubs))
        for p in pubs:
            html = (DOCS / p["url"].removeprefix(D.BASE_URL + "/") / "index.html").read_text(encoding="utf-8")
            ficha_rel = D.SERIES[p["serie"]]["ficha"]
            pre = "../" * (p["url"].removeprefix(D.BASE_URL + "/").rstrip("/").count("/") + 1)
            self.assertTrue(f'href="{pre}{ficha_rel}#leitura"' in html, p["id"])
            self.assertTrue("<!-- nav:start -->" in html, p["id"])
            ficha = (DOCS / ficha_rel / "index.html").read_text(encoding="utf-8")
            self.assertTrue('id="leitura"' in ficha and p["url"] in ficha, p["id"])
        capa = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="divulgacoes/ipca/', capa)
        self.assertIn('href="feed.xml"', capa)
        sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://observatoriodetaxas.tec.br/divulgacoes/</loc>", sitemap)
        for p in pubs:
            self.assertIn(f"<loc>{p['url']}</loc>", sitemap)

    def test_autodiscovery_em_todas_as_paginas_e_link_visivel(self):
        n = 0
        for p in DOCS.rglob("*.html"):
            rel = p.relative_to(DOCS).as_posix()
            if rel in ("embed.html", "admin/index.html"):
                continue
            html = p.read_text(encoding="utf-8")
            head = html.split("</head>", 1)[0]
            self.assertIn('rel="alternate" type="application/rss+xml"', head, rel)
            self.assertIn('href="https://observatoriodetaxas.tec.br/feed.xml"', head, rel)
            self.assertRegex(html, r'<a href="(\.\./)*feed\.xml">RSS</a>', rel)
            n += 1
        self.assertGreater(n, 570)

    def test_versao_dados_ignora_o_arquivo_de_divulgacoes(self):
        import versao_dados as vd
        src = Path(vd.__file__).read_text(encoding="utf-8")
        self.assertIn(":(exclude)data/publicacoes.json", src)
        self.assertIn(":(exclude)docs/data/publicacoes.json", src)

    def test_registrar_recusa_dados_diferentes_do_commit(self):
        with mock.patch.object(D, "dados_conferem", return_value=False), \
                mock.patch.object(D, "grava_json") as g, mock.patch.object(D, "gerar"), \
                mock.patch.object(sys, "argv", ["x", "--registrar"]), mock.patch("builtins.print") as pr:
            D.main()
        self.assertEqual(g.call_count, 1)                # só o espelho, sem registro novo
        self.assertIn("nada registrado", " ".join(str(c) for c in pr.call_args_list))


if __name__ == "__main__":
    unittest.main()
