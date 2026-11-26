"""Entrega 3: acompanhar um indicador e citar uma análise reproduzível.

Teste de aceite E e os arquivos baixáveis (CSV e imagem), sem rede.

    python -m unittest tests.test_citar -v
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_divulgacoes as D  # noqa: E402
import build_indicadores as BI  # noqa: E402
import leituras as L  # noqa: E402
from test_divulgacoes import serie, treze, versao  # noqa: E402

NODE = shutil.which("node")
SHA_A, SHA_B = "a" * 40, "b" * 40


def tabela_html(html: str, id_rotulo: str = "conta-t") -> list[list[str]]:
    """Linhas (texto das células) da tabela ligada a `id_rotulo`."""
    m = re.search(rf'aria-labelledby="{id_rotulo}" tabindex="0"><table>(.*?)</table>', html, re.S)
    corpo = re.sub(r"<caption.*?</caption>|<thead>.*?</thead>", "", m.group(1), flags=re.S)
    return [[unescape(re.sub(r"<[^>]+>", "", c)) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            for tr in re.findall(r"<tr>(.*?)</tr>", corpo, re.S)]


def csv_linhas(texto: str) -> tuple[dict, list[list[str]]]:
    linhas = list(csv.reader(io.StringIO(texto.lstrip("\ufeff")), delimiter=";"))
    i = linhas.index([])
    return {li[0]: li[1] for li in linhas[:i]}, linhas[i + 2:]


def numero(s: str) -> float | None:
    s = s.replace("%", "").replace("R$", "").strip()
    return None if s in ("", "—") else float(s.replace(".", "").replace(",", "."))


class CitacaoReproduzivel(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmp.name) / "docs"
        self.docs.mkdir()
        self.p = mock.patch.object(D, "DOCS", self.docs)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def ler(self, url: str, arq: str = "index.html") -> str:
        return (self.docs / url.removeprefix(D.BASE_URL + "/") / arq).read_text(encoding="utf-8")

    def test_E_citacao_antiga_reproduz_e_acompanhar_mostra_o_atual(self):
        arq = {"formato": 1, "publicacoes": []}
        v1 = treze()
        D.registrar(arq, {433: serie(v1)}, {}, versao(SHA_A, "2026-02-10T12:00:00Z"))
        D.gerar(arq)
        r0 = arq["publicacoes"][0]
        pag0, csv0, svg0 = self.ler(r0["url"]), self.ler(r0["url"], "dados.csv"), self.ler(r0["url"], "grafico.svg")
        ac_original = r0["leitura"]["acumulado_12m"]

        # O produtor revisa um mês e a regra da leitura muda de versão.
        v2 = dict(v1, **{"2025-06": 0.90})
        with mock.patch.object(L, "REGRA_MENSAL", "leitura-mensal-v2"):
            novos = D.registrar(arq, {433: serie(v2)}, {}, versao(SHA_B, "2026-02-20T12:00:00Z"))
            atual = D.leitura_de("ipca", {433: serie(v2)})
        self.assertEqual([n["id"] for n in novos], ["ipca-2026-01-r1"])
        self.assertEqual(novos[0]["leitura"]["regra"], "leitura-mensal-v2")
        D.gerar(arq)

        # A citação antiga: mesmo número, mesma versão, mesma regra, mesmo CSV e mesma imagem.
        pag0b = self.ler(r0["url"])
        self.assertIn(f"Acumulado em 12 meses</span><b>{D.v(ac_original)}</b>", pag0b)
        self.assertIn("leitura-mensal-v1", pag0b)
        self.assertIn(SHA_A[:7], pag0b)
        self.assertIn("Esta leitura foi revisada depois", pag0b)
        self.assertEqual(self.ler(r0["url"], "dados.csv"), csv0)
        self.assertEqual(self.ler(r0["url"], "grafico.svg"), svg0)
        self.assertEqual(tabela_html(pag0b), tabela_html(pag0))

        # O CSV da citação antiga bate com a tabela dela.
        meta, linhas = csv_linhas(csv0)
        self.assertEqual(meta["Versão dos dados"], SHA_A)
        self.assertEqual(meta["Regra"], "leitura-mensal-v1")
        self.assertEqual(meta["Citar (link permanente)"], r0["url"])
        html_linhas = tabela_html(pag0)
        self.assertEqual(len(linhas), len(html_linhas))
        def norm(x: str):
            try:
                return numero(x)
            except ValueError:
                return x
        for c, h in zip(linhas, html_linhas):
            self.assertEqual(c[0].split(" (")[0], h[0])
            self.assertEqual([norm(x) for x in c[1:]], [norm(x) for x in h[1:]], c[0])
        self.assertAlmostEqual(numero(linhas[-1][3]), round(ac_original, 2), places=9)

        # Acompanhar: a ficha recalcula com os dados de agora e cita o registro novo.
        self.assertNotAlmostEqual(atual["acumulado_12m"], ac_original, places=6)
        with mock.patch.object(BI, "load_history", lambda c: serie(v2) if c == 433 else []), \
                mock.patch.object(D, "ler", lambda p, padrao: arq if p == D.ARQUIVO else padrao), \
                mock.patch.object(L, "REGRA_MENSAL", "leitura-mensal-v2"):
            ficha = BI.bloco_leitura(433, serie(v2))
        self.assertIn(D.v(atual["acumulado_12m"]), ficha)
        self.assertIn(f'href="{novos[0]["url"]}">Citar esta análise</a>', ficha)
        self.assertIn('>Acompanhar este indicador</a>', ficha)
        self.assertIn(f'href="{r0["url"].replace("2026-01/", "2026-01/revisao-1/")}">Citar esta análise', self.ler(novos[0]["url"]))

        # Só a regra mudar (sem dado novo) não cria registro: a citação não muda.
        with mock.patch.object(L, "REGRA_MENSAL", "leitura-mensal-v3"):
            self.assertEqual(D.registrar(arq, {433: serie(v2)}, {}, versao("c" * 40, "2026-03-01T12:00:00Z")), [])

    def test_acoes_csv_e_imagem_identificam_fonte_versao_regra(self):
        arq = {"formato": 1, "publicacoes": []}
        D.registrar(arq, {433: serie(treze())}, {}, versao(SHA_A, "2026-02-10T12:00:00Z"))
        D.gerar(arq)
        r = arq["publicacoes"][0]
        pag = self.ler(r["url"])
        self.assertIn(f'href="{D.url_ficha(r)}">Acompanhar este indicador</a>', pag)
        self.assertIn(f'href="{r["url"]}">Citar esta análise</a>', pag)
        self.assertIn(f'href="{r["url"]}dados.csv" download>Baixar CSV do recorte</a>', pag)
        self.assertIn(f'href="{r["url"]}grafico.svg" download>Baixar imagem do gráfico (SVG)</a>', pag)
        self.assertIn('<img src="grafico.svg"', pag)
        cit = D.citacao(r)
        for trecho in ("SGS 433", "recorte: janeiro de 2026", "transformação: acumulado em 12 meses",
                       f"dados do commit {SHA_A}", "regra leitura-mensal-v1", r["url"]):
            self.assertIn(trecho, cit)
        svg = ET.fromstring(self.ler(r["url"], "grafico.svg"))
        textos = " ".join(t.text or "" for t in svg.iter("{http://www.w3.org/2000/svg}text"))
        self.assertIn("Fonte: IBGE, via SGS 433", textos)
        self.assertIn(f"dados do commit {SHA_A[:7]}", textos)
        self.assertIn("regra leitura-mensal-v1", textos)
        self.assertIn(r["url"], textos)
        barras = [x for x in svg.iter("{http://www.w3.org/2000/svg}rect") if x.find("{http://www.w3.org/2000/svg}title") is not None]
        self.assertEqual(len(barras), 13)                   # um ponto por competência da tabela
        meta, _ = csv_linhas(self.ler(r["url"], "dados.csv"))
        self.assertEqual(meta["Unidade"], "% (variação no mês e acumulado)")
        self.assertEqual(meta["Recorte"], "janeiro de 2026")


class Publicado(unittest.TestCase):

    def test_registros_publicados_tem_csv_imagem_e_acoes(self):
        arq = json.loads((ROOT / "data" / "publicacoes.json").read_text(encoding="utf-8"))
        for p in arq["publicacoes"]:
            pasta = DOCS / p["url"].removeprefix(D.BASE_URL + "/")
            html = (pasta / "index.html").read_text(encoding="utf-8")
            meta, linhas = csv_linhas((pasta / "dados.csv").read_text(encoding="utf-8"))
            self.assertEqual(meta["Versão dos dados"], p["versao_dados"]["sha"], p["id"])
            self.assertEqual(len(linhas), len(tabela_html(html)), p["id"])
            ET.fromstring((pasta / "grafico.svg").read_text(encoding="utf-8"))
            self.assertTrue(">Acompanhar este indicador</a>" in html and ">Citar esta análise</a>" in html, p["id"])
        for ficha in ("ipca", "cdi", "dolar"):
            html = (DOCS / "indicadores" / ficha / "index.html").read_text(encoding="utf-8")
            self.assertTrue(">Acompanhar este indicador</a>" in html, ficha)
            self.assertTrue(">Citar esta análise</a>" in html, ficha)
            self.assertTrue("Baixar CSV do recorte" in html, ficha)

    def test_404_explica_versao_indisponivel_com_link_separado(self):
        html = (DOCS / "404.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex" />', html)
        self.assertIn('<base href="/" />', html)
        self.assertIn("A versão pedida desta análise não está disponível", html)
        self.assertIn('href="indicadores/ipca/#leitura"', html)
        self.assertNotIn("http-equiv=\"refresh\"", html)

    @unittest.skipUnless(NODE, "node não encontrado")
    def test_404_js_aponta_a_visao_atual(self):
        prog = (f"const A=require({json.dumps(str(DOCS / '404.js'))});"
                "process.stdout.write(JSON.stringify(['/divulgacoes/ipca/2031-01/','/divulgacoes/cdi/2026-10/revisao-9/',"
                "'/divulgacoes/xyz/1/','/outra/'].map(A.alvo)));")
        r = json.loads(subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=60).stdout)
        self.assertEqual(r[0], {"serie": "ipca", "periodo": "2031-01", "nome": "IPCA", "atual": "/indicadores/ipca/#leitura"})
        self.assertEqual(r[1]["atual"], "/indicadores/cdi/#leitura")
        self.assertEqual(r[2]["atual"], "/divulgacoes/")
        self.assertIsNone(r[3])


if __name__ == "__main__":
    unittest.main()
