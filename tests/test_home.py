"""Página inicial: perguntas do dia, direcionadores, tema claro/escuro e animação.

    python -m unittest tests.test_home -v
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))

import render_index as ri  # noqa: E402


def home() -> str:
    return (DOCS / "index.html").read_text(encoding="utf-8")


class Direcionador(unittest.TestCase):

    def _pts(self, valores: list[tuple[str, float]]) -> list[dict]:
        return [{"dt": datetime.strptime(d, "%d/%m/%Y"), "v": v} for d, v in valores]

    def test_sobe_cai_e_igual(self):
        sobe = self._pts([("01/09/2026", 4.58), ("01/10/2026", 4.63)])
        self.assertEqual(ri._delta(sobe, 2, ""), ("up", "▲ +0,05 p.p. no mês"))
        cai = self._pts([("01/09/2026", 1.57), ("01/10/2026", 1.47)])
        self.assertEqual(ri._delta(cai, 2, ""), ("down", "▼ -0,10 p.p. no mês"))
        igual = self._pts([("28/10/2026", 13.75), ("04/11/2026", 13.75)])
        self.assertEqual(ri._delta(igual, 2, ""), ("flat", "■ 0,00 p.p. no mês"))

    def test_moeda_em_reais(self):
        pts = self._pts([("30/10/2026", 5.4212), ("24/11/2026", 5.8573)])
        self.assertEqual(ri._delta(pts, 4, "R$ "), ("up", "▲ +R$ 0,4361 no mês"))


class PaginaInicial(unittest.TestCase):

    def test_cinco_perguntas_com_resposta_valor_e_direcionador(self):
        html = home()
        for anchor, pergunta in (("selic", "Qual é a Selic hoje?"), ("ipca", "Qual é a inflação acumulada em 12 meses?"),
                                 ("dolar", "Quanto está o dólar hoje?"), ("igpm", "Quanto vai subir o aluguel?"),
                                 ("desemprego", "Qual é a taxa de desemprego?")):
            bloco = re.search(rf'<article class="resp" id="{anchor}">.*?</article>', html, re.S)
            self.assertIsNotNone(bloco, anchor)
            b = bloco.group(0)
            self.assertIn(f"<h2>{pergunta}</h2>", b)
            self.assertRegex(b, r'class="num-delta (up|down|flat)">[▲▼■] ')
            self.assertRegex(b, r"ref\. \d\d/\d\d/\d{4}")
            self.assertIn('class="spark" data-cod=', b)

    def test_mais_indicadores_ligam_paginas_que_existem(self):
        html = home()
        bloco = re.search(r"<!-- mais:inicio -->(.*?)<!-- mais:fim -->", html, re.S).group(1)
        links = re.findall(r'class="mais-card" href="(indicadores/[a-z0-9-]+/)"', bloco)
        self.assertGreaterEqual(len(links), 10)
        for rel in links:
            self.assertTrue((DOCS / rel / "index.html").is_file(), rel)
        self.assertEqual(bloco.count('class="num-delta'), len(links))

    def test_links_internos_da_home_existem(self):
        html = home()
        corpo = html.split('<main id="conteudo">', 1)[1].split("</main>", 1)[0]
        for href in set(re.findall(r'href="([a-z][a-z0-9/._-]*)"', corpo)):
            alvo = DOCS / href
            ok = alvo.is_file() or (alvo / "index.html").is_file()
            self.assertTrue(ok, href)

    def test_tema_claro_por_padrao_e_botao_so_na_home(self):
        html = home()
        self.assertIn('<html lang="pt-BR" data-theme="light">', html)
        self.assertIn('href="refy/tokens.css"', html)
        self.assertTrue((DOCS / "refy" / "tokens.css").is_file())
        self.assertIn("data-tema-botao hidden", html)
        self.assertIn('localStorage.setItem("tema"', html)
        # As outras páginas recebem o botão escondido e nenhum script que o mostre.
        outra = (DOCS / "reajuste" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-tema-botao hidden", outra)
        self.assertNotIn("data-tema-botao]", outra)
        self.assertNotIn("data-theme=", outra.split("<head>", 1)[0])

    def test_titulo_animado_tem_rotulo_e_respeita_movimento_reduzido(self):
        html = home()
        self.assertIn('<h1 class="titulo" aria-label="Indicadores do Brasil, hoje.">', html)
        self.assertEqual(html.count('class="w" style="--i:'), 4)
        self.assertRegex(html, r"(?s)prefers-reduced-motion: reduce\)\{\s*html\{[^}]*\}\s*\.titulo \.w")

    def test_fontes_novas_existem(self):
        for f in ("ibmplexserif-latin-400", "ibmplexserif-latin-600", "manrope-latin-0", "sourcesans3-latin-0"):
            self.assertTrue((DOCS / "fonts" / f"{f}.woff2").is_file(), f)


if __name__ == "__main__":
    unittest.main()
