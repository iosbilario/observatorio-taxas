"""
Testes de aceitação de descoberta orgânica (SEO + recuperação por IA).

Verificam o HTML ESTÁTICO de docs/ (o que um robô sem JavaScript recebe) e as
fórmulas, contra os dados de data/. Só stdlib:

    python -m unittest discover -s tests -v

Rode depois do pipeline de geração (build_pages, build_correcao,
render_index, sync_nav, csp_hashes), na mesma ordem do workflow.

Checagem ao vivo (rede, opcional): ORGANIC_LIVE=1 python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
import urllib.request
from datetime import date, datetime
from decimal import Decimal, getcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages  # noqa: E402
import seo_audit  # noqa: E402
from fontes import FONTES  # noqa: E402

DOCS = ROOT / "docs"
DATA = ROOT / "data"
FIX = Path(__file__).resolve().parent / "fixtures"

# Exceções conhecidas, com motivo. Cada uma tem item no BACKLOG.
SEM_H1_NO_HTML_INICIAL = {
    "rebobinar.html": "conteúdo montado por JavaScript (BACKLOG B-02)",
}

_AUDIT = None
_PAGINAS = None


def auditoria() -> dict:
    global _AUDIT
    if _AUDIT is None:
        _AUDIT = seo_audit.auditar(DOCS)
    return _AUDIT


def paginas() -> dict:
    global _PAGINAS
    if _PAGINAS is None:
        _PAGINAS = seo_audit.carregar(DOCS)
    return _PAGINAS


def indexaveis() -> dict:
    return {k: v for k, v in paginas().items() if v["indexavel"]}


def fmt(v: float, dec: int = 2) -> str:
    return build_pages.fmt_num(v, dec)


class TestRastreamento(unittest.TestCase):
    def test_urls_da_linha_de_base_preservadas(self):
        """Toda URL que estava no sitemap original continua existindo e no sitemap."""
        base = FIX.joinpath("urls_baseline.txt").read_text(encoding="utf-8").split()
        atuais = {u["loc"] for u in seo_audit.sitemap_urls(DOCS)}
        sem_arquivo = [u for u in base if seo_audit.arquivo_de(u, DOCS) is None]
        fora = [u for u in base if u not in atuais]
        self.assertEqual(sem_arquivo, [])
        self.assertEqual(fora, [])

    def test_sitemap_so_com_urls_canonicas_publicaveis(self):
        a = auditoria()["achados"]
        for chave in ("sitemap_url_sem_arquivo", "sitemap_url_noindex",
                      "sitemap_url_nao_canonica", "sitemap_url_duplicada",
                      "indexavel_fora_do_sitemap"):
            self.assertEqual(a.get(chave, []), [], chave)

    def test_sitemap_com_urls_escapadas(self):
        """Protocolo de sitemaps: URL escapada (sem 'ç' cru, sem '&' solto)."""
        for u in seo_audit.sitemap_urls(DOCS):
            self.assertTrue(u["loc_bruto"].isascii(), u["loc_bruto"])
            self.assertNotIn("&", u["loc_bruto"])

    def test_sitemap_lastmod_e_data_valida_e_nao_futura(self):
        amanha = date.today().toordinal() + 1
        for u in seo_audit.sitemap_urls(DOCS):
            self.assertIsNotNone(u["lastmod"], u["loc"])
            d = datetime.strptime(u["lastmod"], "%Y-%m-%d").date()
            self.assertLessEqual(d.toordinal(), amanha, u["loc"])

    def test_estado_do_lastmod_cobre_o_sitemap(self):
        estado = json.loads((DATA / "sitemap_lastmod.json").read_text(encoding="utf-8"))
        locs = [u["loc"] for u in seo_audit.sitemap_urls(DOCS)]
        self.assertEqual(sorted(estado), sorted(locs))
        for u in seo_audit.sitemap_urls(DOCS):
            self.assertEqual(estado[u["loc"]]["lastmod"], u["lastmod"])

    def test_impressao_digital_ignora_navegacao_e_hash_do_commit(self):
        import tempfile
        import render_index
        base = ("<title>T</title><meta name=\"description\" content=\"D\"/><main>"
                "<!-- conteudo:inicio --><p>2,77%</p><!-- conteudo:fim -->{nav}</main>")
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.html"
            f.write_text(base.format(nav="<p>últimos 12: jan</p>"), encoding="utf-8")
            h1 = render_index.impressao_digital(f)
            f.write_text(base.format(nav="<p>últimos 12: fev</p>"), encoding="utf-8")
            self.assertEqual(render_index.impressao_digital(f), h1, "navegação fora do conteúdo mudou o hash")
            f.write_text(base.replace("2,77%", "2,78%").format(nav=""), encoding="utf-8")
            self.assertNotEqual(render_index.impressao_digital(f), h1, "mudança de valor não mudou o hash")
            g = Path(d) / "landing.html"
            g.write_text('<body><p class="boletim">commit <a href="x">abc1234</a> 13,75</p><main>m</main></body>',
                         encoding="utf-8")
            h2 = render_index.impressao_digital(g)
            g.write_text('<body><p class="boletim">commit <a href="x">def5678</a> 13,75</p><main>m</main></body>',
                         encoding="utf-8")
            self.assertEqual(render_index.impressao_digital(g), h2, "hash do commit mudou o lastmod")
            g.write_text('<body><p class="boletim">commit <a href="x">def5678</a> 14,25</p><main>m</main></body>',
                         encoding="utf-8")
            self.assertNotEqual(render_index.impressao_digital(g), h2, "número fora do <main> não mudou o hash")

    def test_robots_nao_bloqueia_conteudo_publico(self):
        robots = (DOCS / "robots.txt").read_text(encoding="utf-8")
        disallow = [ln.split(":", 1)[1].strip() for ln in robots.splitlines()
                    if ln.lower().startswith("disallow:")]
        self.assertEqual(disallow, ["/admin/"])
        self.assertIn("Sitemap: https://observatoriodetaxas.tec.br/sitemap.xml", robots)

    def test_canonical_unico_e_proprio(self):
        a = auditoria()["achados"]
        for chave in ("canonical_ausente_ou_multiplo", "canonical_outro_dominio",
                      "canonical_diferente_da_url", "og_url_outro_dominio"):
            self.assertEqual(a.get(chave, []), [], chave)

    def test_links_internos_sem_quebra(self):
        self.assertEqual(auditoria()["achados"].get("link_interno_quebrado", []), [])

    def test_sem_paginas_orfas(self):
        self.assertEqual(auditoria()["achados"].get("orfa_sem_link_interno", []), [])


class TestMetadados(unittest.TestCase):
    def test_titulos_ate_70_caracteres(self):
        """O Bing SEO Analysis de 11/11/2026 apontou 'título longo' em uma
        página; /correcao/ (73) era o único título acima de 70 e o único
        acima de 66. Este teste impede a volta do problema. Não é regra de
        buscador: o Google não fixa limite; 70 é o corte que separou a
        página sinalizada de todas as outras."""
        longos = {r: len(p["title"]) for r, p in indexaveis().items() if len(p["title"]) > 70}
        self.assertEqual(longos, {})

    def test_titulos_e_descricoes_unicos(self):
        a = auditoria()["achados"]
        self.assertEqual(a.get("titulo_duplicado", []), [])
        self.assertEqual(a.get("descricao_duplicada", []), [])
        self.assertEqual(a.get("sem_meta_description", []), [])

    def test_um_h1_no_html_inicial(self):
        for rel, pg in indexaveis().items():
            if rel in SEM_H1_NO_HTML_INICIAL:
                continue
            self.assertEqual(len(pg["h1"]), 1, f"{rel}: {pg['h1']}")

    def test_idioma_pt_br(self):
        for rel in indexaveis():
            html = (DOCS / rel).read_text(encoding="utf-8")
            self.assertIn('<html lang="pt-BR"', html, rel)

    def test_paginas_de_mes_tem_h1_coerente_com_a_url(self):
        for rel, pg in indexaveis().items():
            m = re.match(r"reajuste/([a-z]+)-([a-zç]+)-(\d{4})/index.html$", rel)
            if not m:
                continue
            nome = build_pages.INDICES[m.group(1)]["nome"]
            self.assertTrue(pg["h1"][0].startswith(f"{nome} de {m.group(2)} de {m.group(3)}"), rel)
            self.assertIn(f"{m.group(2)} de {m.group(3)}", pg["title"], rel)


class TestDadosEstruturados(unittest.TestCase):
    def test_jsonld_valido(self):
        self.assertEqual(auditoria()["achados"].get("jsonld_invalido", []), [])

    def test_faq_e_breadcrumb_batem_com_o_conteudo_visivel(self):
        for rel, pg in indexaveis().items():
            for bruto in pg["jsonld_brutos"]:
                obj = json.loads(bruto)
                if obj.get("@type") != "FAQPage":
                    continue
                for q in obj["mainEntity"]:
                    self.assertIn(q["name"], pg["texto"], f"{rel}: pergunta não visível")
                    self.assertIn(q["acceptedAnswer"]["text"], pg["texto"], f"{rel}: resposta não visível")
                self.assertEqual(obj["url"], pg["canonicals"][0], rel)
                bc = obj.get("breadcrumb")
                if bc:
                    itens = bc["itemListElement"]
                    self.assertEqual(itens[-1]["item"], pg["canonicals"][0], rel)
                    for it in itens:
                        self.assertIn(it["name"], pg["texto"], rel)

    def test_texto_juridico_nao_indica_indice_obrigatorio(self):
        """Reajuste de aluguel: o índice é escolha do contrato. Nenhuma página
        pode sugerir índice obrigatório ou padrão legal."""
        proibidas = re.compile(r"índice (?:obrigatório|oficial do aluguel|legal)|"
                               r"padrão do mercado imobiliário|deve(?:m)? usar o (?:IGP-M|IPCA|INPC|IGP-DI)|"
                               r"na maioria dos contratos", re.I)
        for rel, pg in indexaveis().items():
            texto = pg["texto"].replace("nenhuma lei fixa um índice obrigatório", "")
            self.assertIsNone(proibidas.search(texto), f"{rel}: {proibidas.search(texto)}")
        hub = indexaveis()["reajuste/index.html"]["texto"]
        self.assertIn("O índice é o que o contrato definir", hub)
        self.assertIn("nenhuma lei fixa um índice obrigatório", hub)

    def test_licencas_declaradas_coerentes(self):
        """Código MIT; dados sem CC0 (o Observatório não pode liberar em
        domínio público séries de IBGE e FGV); Dataset do JSON-LD aponta para
        ODbL (séries do BCB) ou para os termos por série."""
        self.assertTrue((ROOT / "LICENSE").is_file())
        termos = (ROOT / "LICENSE-DADOS.md").read_text(encoding="utf-8")
        for arq in list(DOCS.rglob("*.html")) + [DOCS / "llms.txt"]:
            txt = arq.read_text(encoding="utf-8")
            self.assertNotIn("publicdomain/zero", txt, arq)
            self.assertNotIn("CC0", txt, arq)
        permitidas = {"https://opendatacommons.org/licenses/odbl/1-0/",
                      "https://github.com/iosbilario/observatorio-taxas/blob/main/LICENSE-DADOS.md"}
        landing = paginas()["index.html"]
        for bruto in landing["jsonld_brutos"]:
            for it in json.loads(bruto).get("@graph", []):
                if it.get("@type") == "Dataset":
                    self.assertIn(it.get("license"), permitidas, it.get("name"))
        import yaml
        for s in yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["series"]:
            self.assertRegex(termos, rf"\b{s['codigo']}\b", f"série {s['codigo']} sem termo em LICENSE-DADOS.md")

    def test_procedencia_nao_atribui_ao_bacen_indices_de_outros_orgaos(self):
        proibidas = ["segundo dados do Banco Central do Brasil",
                     "Fonte primária: API pública do SGS/Banco Central do Brasil"]
        for sub in ("reajuste", "correcao"):
            for f in (DOCS / sub).rglob("index.html"):
                html = f.read_text(encoding="utf-8")
                for frase in proibidas:
                    self.assertNotIn(frase, html, f)


class TestDadosEFormulas(unittest.TestCase):
    def test_historicos_mensais_contiguos(self):
        """A janela de 12 meses assume série sem buracos."""
        for info in build_pages.INDICES.values():
            h = build_pages.load_history(info["codigo"])
            for a, b in zip(h, h[1:]):
                self.assertEqual((b["dt"].year * 12 + b["dt"].month) - (a["dt"].year * 12 + a["dt"].month), 1,
                                 f"série {info['codigo']}: buraco entre {a['dt']:%Y-%m} e {b['dt']:%Y-%m}")

    def test_acumulado_composto_valor_conhecido(self):
        j = [{"valor": 1.0}, {"valor": 2.0}, {"valor": -0.5}]
        getcontext().prec = 30
        esperado = (Decimal("1.01") * Decimal("1.02") * Decimal("0.995") - 1) * 100
        self.assertAlmostEqual(build_pages.acumulado(j), float(esperado), places=12)

    def test_acumulado_ipca_bate_com_serie_oficial_13522(self):
        """O IPCA 12 meses calculado pelo Observatório (composição de 433)
        bate com o acumulado publicado na série SGS 13522, a menos de
        arredondamento das variações mensais (2 casas)."""
        mensal = build_pages.load_history(433)
        oficial = {p["dt"]: p["valor"] for p in build_pages.load_history(13522)}
        comparados = 0
        for fim in range(11, len(mensal)):
            dt = mensal[fim]["dt"]
            if dt in oficial:
                ac = build_pages.acumulado(mensal[fim - 11: fim + 1])
                self.assertLess(abs(ac - oficial[dt]), 0.02, f"{dt:%Y-%m}: {ac} x {oficial[dt]}")
                comparados += 1
        self.assertGreater(comparados, 100)

    def test_valores_publicados_iguais_a_linha_de_base(self):
        """Nenhuma página mudou acumulado, fator ou o fator usado pela calculadora."""
        base = json.loads((FIX / "valores_baseline.json").read_text(encoding="utf-8"))
        for chave, v in base.items():
            html = (DOCS / chave / "index.html").read_text(encoding="utf-8")
            self.assertRegex(html, r'<p class="big[^"]*">' + re.escape(v["acumulado"]) + "</p>", chave)
            self.assertIn(f"<b>{v['fator']}</b>", html, chave)
            if "fator_js" in v:
                self.assertIn(f"const FATOR={v['fator_js']};", html, chave)

    def test_dados_centrais_no_html_inicial_de_todas_as_paginas_de_mes(self):
        """Indicador, competência, variação do mês, acumulado, fator, produtor
        e série do SGS aparecem como TEXTO no HTML, sem JavaScript."""
        pags = indexaveis()
        total = 0
        for key, info in build_pages.INDICES.items():
            hist = build_pages.load_history(info["codigo"])
            fonte = FONTES[info["codigo"]]
            for fim in range(11, len(hist)):
                j = hist[fim - 11: fim + 1]
                ref = j[-1]["dt"]
                rel = f"reajuste/{key}-{build_pages.slug_mes(ref)}/index.html"
                pg = pags[rel]
                ac = build_pages.acumulado(j)
                txt = pg["texto"]
                ref_txt = build_pages.mes_ano(ref)
                self.assertIn(f"O {info['nome']} de {ref_txt} variou {fmt(j[-1]['valor'])}% no mês", txt, rel)
                self.assertIn(f"acumulou {fmt(ac)}%", txt, rel)
                self.assertIn(fmt(1 + ac / 100, 6), txt, rel)
                self.assertIn(fonte["produtor"]["nome"], txt, rel)
                self.assertIn(f"série {info['codigo']}", txt, rel)
                self.assertIn(f"{build_pages.mes_ano(j[0]['dt'])} a {ref_txt}", txt, rel)
                total += 1
        self.assertEqual(total, sum(1 for r in pags if re.match(r"reajuste/[a-z]+-", r)))

    def test_coerencia_titulo_h1_canonical_jsonld_e_valores(self):
        """Em TODA página de mês: título, og:title, H1, canonical, breadcrumb e
        FAQ falam do mesmo índice e mês, com os mesmos números dos dados."""
        pags = indexaveis()
        for key, info in build_pages.INDICES.items():
            hist = build_pages.load_history(info["codigo"])
            for fim in range(11, len(hist)):
                j = hist[fim - 11: fim + 1]
                ref_txt = build_pages.mes_ano(j[-1]["dt"])
                rel = f"reajuste/{key}-{build_pages.slug_mes(j[-1]['dt'])}/index.html"
                pg = pags[rel]
                ac, m = fmt(build_pages.acumulado(j)), fmt(j[-1]["valor"])
                rotulo = f"{info['nome']} de {ref_txt}"
                self.assertEqual(pg["title"], f"{rotulo}: {m}% no mês e {ac}% em 12 meses", rel)
                html = (DOCS / rel).read_text(encoding="utf-8")
                self.assertIn(f'<meta property="og:title" content="{pg["title"]}"/>', html, rel)
                self.assertTrue(pg["h1"][0].startswith(rotulo), rel)
                self.assertEqual(pg["canonicals"], [seo_audit.url_de(rel)], rel)
                faq = next(json.loads(b) for b in pg["jsonld_brutos"] if '"FAQPage"' in b)
                respostas = " ".join(q["acceptedAnswer"]["text"] for q in faq["mainEntity"])
                self.assertIn(f"{m}% no mês", respostas, rel)
                self.assertIn(f"acumulou {ac}%", respostas, rel)
                self.assertEqual(faq["breadcrumb"]["itemListElement"][-1]["name"],
                                 f"{info['nome']} · {ref_txt}", rel)

    def test_correcao_12_meses_igual_ao_reajuste_do_ultimo_mes(self):
        for key in build_pages.INDICES:
            corr = (DOCS / "correcao" / key / "index.html").read_text(encoding="utf-8")
            m = re.search(r'href="https://observatoriodetaxas.tec.br/reajuste/([^/]+)/"', corr)
            self.assertIsNotNone(m, key)
            reaj = (DOCS / "reajuste" / m.group(1) / "index.html").read_text(encoding="utf-8")
            big = lambda h: re.search(r'<p class="big[^"]*">([^<]+)</p>', h).group(1)  # noqa: E731
            self.assertEqual(big(corr), big(reaj), key)


class TestNavegacao(unittest.TestCase):
    def test_meses_vizinhos_ligados(self):
        pags = indexaveis()
        for key, info in build_pages.INDICES.items():
            slugs = sorted((p for p in pags if p.startswith(f"reajuste/{key}-")),
                           key=lambda r: pags[r]["texto"])  # só precisa do conjunto
            for rel in slugs:
                links = set(seo_audit.links_internos(pags[rel]))
                m = re.match(rf"reajuste/{key}-([a-zç]+)-(\d{{4}})/", rel)
                mes = build_pages.MESES.index(m.group(1)) + 1
                dt = datetime(int(m.group(2)), mes, 1)
                for passo in (-1, 1):
                    viz = build_pages._vizinho(dt, passo)
                    alvo = f"reajuste/{key}-{build_pages.slug_mes(viz)}/index.html"
                    if alvo in pags:
                        self.assertIn(seo_audit.url_de(alvo), links, f"{rel} -> {alvo}")

    def test_pagina_de_mes_aponta_para_a_correcao_do_indice(self):
        for rel, pg in indexaveis().items():
            m = re.match(r"reajuste/([a-z]+)-", rel)
            if m:
                self.assertIn(f"https://observatoriodetaxas.tec.br/correcao/{m.group(1)}/",
                              seo_audit.links_internos(pg), rel)


@unittest.skipUnless(os.environ.get("ORGANIC_LIVE") == "1", "checagem ao vivo desligada (ORGANIC_LIVE=1)")
class TestAoVivo(unittest.TestCase):
    AMOSTRA = [
        "/", "/reajuste/", "/correcao/", "/rebobinar.html", "/var.html", "/retransmissora.html",
        "/reajuste/igpm-julho-2026/", "/reajuste/igpm-agosto-2026/", "/reajuste/inpc-dezembro-2025/",
        "/reajuste/ipca-janeiro-2026/", "/reajuste/igpdi-abril-2016/", "/correcao/ipca/",
        "/sitemap.xml", "/robots.txt", "/llms.txt",
    ]

    def test_paginas_publicas_http_200(self):
        for p in self.AMOSTRA:
            req = urllib.request.Request(seo_audit.BASE_URL + p, headers={"User-Agent": "observatorio-tests"})
            with urllib.request.urlopen(req, timeout=30) as r:
                self.assertEqual(r.status, 200, p)


if __name__ == "__main__":
    unittest.main()
