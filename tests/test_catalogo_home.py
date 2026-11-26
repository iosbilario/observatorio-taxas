"""Indicadores por tema na página inicial (scripts/catalogo_home.py).

    python -m unittest tests.test_catalogo_home -v
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_indicadores as BI  # noqa: E402
import catalogo_home as C  # noqa: E402


def bloco_publicado() -> str:
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    return re.search(r"<!-- mais:inicio -->(.*?)<!-- mais:fim -->", html, re.S).group(1)


def diaria(inicio: datetime, valores: list[float], passo: int = 1) -> list[dict]:
    return [{"dt": inicio + timedelta(days=i * passo), "valor": v} for i, v in enumerate(valores)]


class Catalogo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.series = BI.series_config()
        cls.hist = {it["codigo"]: BI.load_history(it["codigo"]) for it in cls.series}
        cls.temas = C.temas(cls.series, cls.hist)
        cls.html = bloco_publicado()

    def test_toda_serie_com_ficha_aparece_uma_vez_e_as_contagens_somam(self):
        fichas = {c for c, p in BI.PAGINAS.items() if (DOCS / "indicadores" / p["slug"] / "index.html").is_file()}
        codigos = [li["codigo"] for t in self.temas for li in t["linhas"]]
        self.assertEqual(sorted(codigos), sorted(fichas))
        self.assertEqual(len(codigos), len(set(codigos)))
        cont = {t["titulo"]: t["n"] for t in self.temas}
        self.assertEqual(cont, {"Inflação": 6, "Juros e poupança": 9, "Câmbio": 3, "Crédito": 3,
                                "Atividade e emprego": 2, "Setor externo e fiscal": 2})
        self.assertEqual(sum(cont.values()), len(fichas))
        self.assertIn(f"{len(fichas)} séries em {len(self.temas)} temas.", self.html)
        links = re.findall(r'class="cat-linha" href="(indicadores/[a-z0-9-]+/)"', self.html)
        self.assertEqual(len(links), len(fichas))
        self.assertEqual(len(set(links)), len(links))
        for rel in links:
            self.assertTrue((DOCS / rel / "index.html").is_file(), rel)
        self.assertIn('href="indicadores/">Ver o catálogo completo', (DOCS / "index.html").read_text(encoding="utf-8"))

    def test_ordem_e_indicador_de_referencia(self):
        self.assertEqual([t["id"] for t in self.temas], ["inflacao", "juros", "cambio", "credito", "atividade", "externo"])
        self.assertEqual([t["referencia"]["codigo"] for t in self.temas], [13522, 432, 1, 21082, 24369, 13621])
        self.assertIn('data-inicial="inflacao"', self.html)

    def test_resumo_do_tema_curto_e_sem_unidade_repetida(self):
        cabs = dict(re.findall(r'data-tema="([a-z]+)"><span class="cat-tema-nome">.*?<span class="cat-tema-ref">(.*?)</span>', self.html))
        texto = {k: re.sub(r"<[^>]+>", "", v) for k, v in cabs.items()}
        self.assertRegex(texto["inflacao"], r"^IPCA em 12 meses · \d+,\d\d%$")
        self.assertRegex(texto["juros"], r"^Meta Selic · \d+,\d\d% a\.a\.$")
        self.assertRegex(texto["cambio"], r"^Dólar PTAX de venda · R\$ \d+,\d{4}$")
        self.assertRegex(texto["credito"], r"^Inadimplência · ")
        self.assertRegex(texto["atividade"], r"^Desemprego · ")
        self.assertRegex(texto["externo"], r"^Reservas internacionais · US\$ ")
        self.assertIn(">Dólar PTAX de venda<small>", self.html)
        self.assertIn(">Dólar PTAX de compra<small>", self.html)

    def test_troca_de_tema_entra_no_historico(self):
        js = (DOCS / "catalogo.js").read_text(encoding="utf-8")
        self.assertIn("history.pushState", js)
        self.assertNotIn("history.replaceState(", js)
        self.assertIn('addEventListener("popstate"', js)

    def test_formatos_unidades_e_rotulos_de_periodo(self):
        li = {x["codigo"]: x for t in self.temas for x in t["linhas"]}
        self.assertRegex(li[4389]["valor"], r"^\d+,\d\d% a\.a\.$")             # CDI anualizado
        self.assertTrue(li[4389]["ref"].startswith("taxa do dia "))
        self.assertEqual(li[4389]["unidade"], "% a.a.")
        self.assertRegex(li[4391]["valor"], r"^\d+,\d\d%$")                     # CDI acumulado no mês
        self.assertEqual(li[4391]["unidade"], "% no mês")
        self.assertTrue(li[4391]["ref"].startswith("competência "))
        self.assertRegex(li[1]["valor"], r"^R\$ \d+,\d{4}$")                    # dólar
        self.assertTrue(li[1]["ref"].startswith("cotação de "))
        self.assertTrue(li[1]["variacao"]["base"].startswith("cotação de "))
        self.assertTrue(li[1]["variacao"]["texto"].endswith("%"))               # cotação varia em %
        self.assertRegex(li[4513]["valor"], r"% do PIB$")                       # dívida em % do PIB
        self.assertTrue(li[4513]["variacao"]["texto"].endswith("p.p."))
        self.assertTrue(li[24369]["ref"].startswith("trimestre móvel até "))    # desemprego
        self.assertTrue(li[24369]["variacao"]["base"].startswith("trimestre móvel até "))
        self.assertTrue(li[432]["ref"].startswith("em vigor desde "))
        for c in (25, 195):                                                     # as duas poupanças
            self.assertEqual(li[c]["unidade"], "% no período")
            self.assertIn(f">{li[c]['nome']}<small>% no período · período de 1 mês iniciado em", self.html)
        self.assertIn("Poupança (depósitos até 03/05/2012)", self.html)
        self.assertIn("Rendimento da poupança", self.html)

    def test_variacao_compreensivel_sem_cor(self):
        for x in re.findall(r'<span class="cat-var">(.*?)</span></span>', self.html):
            texto = re.sub(r"<[^>]+>", "", x)
            self.assertRegex(texto, r"(alta|queda|estável) · base: ", texto)
        self.assertNotIn("num-delta up", self.html)
        self.assertNotIn("var(--sobe)", re.search(r"/\* =+ Indicadores por tema.*?\}\n\}", (DOCS / "index.html").read_text(encoding="utf-8"), re.S).group(0))

    def test_uma_acao_por_tema_no_maximo(self):
        acoes = {t["id"]: t["acao"] for t in self.temas}
        self.assertEqual(acoes["inflacao"][0], "correcao/")
        self.assertEqual(acoes["juros"][0], "comparador/")
        self.assertEqual([k for k, v in acoes.items() if v], ["inflacao", "juros"])
        for painel in re.findall(r'<section class="cat-painel".*?</section>', self.html, re.S):
            self.assertLessEqual(painel.count('class="cat-acao"'), 1)

    def test_sem_javascript_todos_os_temas_e_fichas_estao_no_html(self):
        for t in self.temas:
            self.assertIn(f'href="#catalogo-{t["id"]}"', self.html)
            self.assertIn(f'id="catalogo-{t["id"]}"', self.html)
        self.assertNotIn(" hidden", self.html)            # nada escondido no HTML inicial

    def test_mesmos_dados_mesmo_catalogo(self):
        self.assertEqual(C.gerar(), C.gerar())
        self.assertEqual(C.gerar().strip(), self.html.strip())

    def test_home_nao_baixa_historicos_para_o_catalogo(self):
        js = (DOCS / "catalogo.js").read_text(encoding="utf-8")
        self.assertNotIn("fetch(", js)
        self.assertNotIn("_history.json", self.html)
        self.assertRegex((DOCS / "index.html").read_text(encoding="utf-8"), r'<script src="catalogo\.js\?v=[0-9a-f]{10}" defer>')

    def test_serie_nova_com_grupo_e_ficha_entra_sozinha(self):
        series = self.series + [{"codigo": 99999, "grupo": "Câmbio"}, {"codigo": 99998, "grupo": "Tema novo"}]
        hist = {**self.hist, 99999: diaria(datetime(2026, 1, 1), [1.0, 2.0]),
                99998: diaria(datetime(2026, 1, 1), [3.0])}
        pag = {**BI.PAGINAS, 99999: dict(slug="x", curto="Série X", casas=2, suf="%"),
               99998: dict(slug="y", curto="Série Y", casas=2, suf="%")}
        ser = {**C.cat.SERIES, 99999: dict(C.cat.SERIES[1], unidade="%"), 99998: dict(C.cat.SERIES[1], unidade="%")}
        with mock.patch.object(BI, "PAGINAS", pag), mock.patch.dict(C.cat.SERIES, ser):
            ts = C.temas(series, hist)
        self.assertEqual(next(t for t in ts if t["id"] == "cambio")["n"], 4)
        self.assertEqual(ts[-1]["titulo"], "Tema novo")
        self.assertEqual(ts[-1]["id"], "tema-novo")


class Minigrafico(unittest.TestCase):

    def pontos(self, svg: str) -> list[tuple[str, float, float]]:
        d = re.search(r'<path d="([^"]+)"', svg)
        return [(m[0], float(m[1]), float(m[2])) for m in re.findall(r"([ML])([\d.]+) ([\d.]+)", d.group(1))] if d else []

    def test_serie_constante_e_linha_horizontal(self):
        svg = C.minigrafico(1, diaria(datetime(2026, 1, 5), [5.0] * 30))
        ys = {y for _, _, y in self.pontos(svg)}
        self.assertEqual(len(ys), 1)

    def test_um_ponto_vira_ponto(self):
        svg = C.minigrafico(433, [{"dt": datetime(2026, 10, 1), "valor": 0.3}])
        self.assertNotIn("<path", svg)
        self.assertEqual(svg.count("<circle"), 1)

    def test_historico_curto_mantem_valor_e_ficha(self):
        li = C.linha(433, [{"dt": datetime(2026, 10, 1), "valor": 0.3}])
        self.assertEqual(li["valor"], "0,30%")
        self.assertIsNone(li["variacao"])
        self.assertEqual(li["url"], "indicadores/ipca/")
        self.assertIn("sem base de comparação", C._linha_html(li))
        self.assertEqual(C.linha(433, [])["valor"], None)
        self.assertIn('href="indicadores/ipca/"', C._linha_html(C.linha(433, [])))

    def test_lacuna_mensal_quebra_a_linha_e_x_usa_datas_reais(self):
        meses = [datetime(2025, m, 1) for m in range(11, 13)] + [datetime(2026, m, 1) for m in (1, 2, 3, 7, 8, 9, 10)]
        svg = C.minigrafico(433, [{"dt": d, "valor": 0.1 * i} for i, d in enumerate(meses)])
        p = self.pontos(svg)
        self.assertEqual([c for c, _, _ in p].count("M"), 2)                    # buraco abr-jun
        xs = [x for _, x, _ in p]
        passo = xs[1] - xs[0]
        self.assertGreater(xs[5] - xs[4], 3 * passo)                           # o buraco ocupa espaço
        self.assertEqual(len(p), len(meses))                                   # nenhum ponto inventado

    def test_diaria_simplificada_preserva_primeiro_ultimo_e_extremos(self):
        vals = [5.0 + (i % 17) * 0.01 for i in range(250)]
        vals[123], vals[200] = 9.0, 1.0
        pts = diaria(datetime(2025, 12, 1), vals)
        jan = C.janela_12m(pts)
        sim = C.simplifica(jan)
        self.assertLessEqual(len(sim), C.MAX_PONTOS + 3)
        self.assertEqual(sim[0], jan[0])
        self.assertEqual(sim[-1], jan[-1])
        self.assertIn(max(jan, key=lambda p: p["valor"]), sim)
        self.assertIn(min(jan, key=lambda p: p["valor"]), sim)
        self.assertTrue(all(p in jan for p in sim))

    def test_janela_termina_na_ultima_observacao(self):
        pts = [{"dt": datetime(2024, m, 1), "valor": float(m)} for m in range(1, 13)] + \
              [{"dt": datetime(2025, m, 1), "valor": float(m)} for m in range(1, 7)]
        jan = C.janela_12m(pts)
        self.assertEqual(jan[-1]["dt"], datetime(2025, 6, 1))
        self.assertEqual(jan[0]["dt"], datetime(2024, 7, 1))
        self.assertEqual(len(jan), 12)


if __name__ == "__main__":
    unittest.main()
