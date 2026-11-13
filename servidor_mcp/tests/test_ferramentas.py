"""Testes das ferramentas (sem rede, sobre data/ do repositório).

    python -m unittest discover -s servidor_mcp/tests -t . -v
"""

from __future__ import annotations

import json
import os
import re
import unittest
from contextlib import contextmanager
from pathlib import Path

import yaml

from servidor_mcp import catalogo as cat
from servidor_mcp import ferramentas as f
from servidor_mcp.dados import Dados

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
D = Dados(str(ROOT / "data"), ttl=3600)


@contextmanager
def restritas_liberadas():
    antes = os.environ.get("OBS_MCP_LIBERAR_RESTRITAS")
    os.environ["OBS_MCP_LIBERAR_RESTRITAS"] = "1"
    try:
        yield
    finally:
        if antes is None:
            os.environ.pop("OBS_MCP_LIBERAR_RESTRITAS", None)
        else:
            os.environ["OBS_MCP_LIBERAR_RESTRITAS"] = antes


def erro(fn, *args) -> dict:
    try:
        fn(*args)
    except f.ErroConsulta as e:
        return e.dados
    raise AssertionError("esperava ErroConsulta")


class TestCatalogoEFontes(unittest.TestCase):
    def test_catalogo_cobre_todas_as_series_do_config(self):
        cfg = {s["codigo"] for s in yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["series"]}
        self.assertEqual(set(cat.SERIES), cfg)

    def test_produtores(self):
        for cod in (433, 13522, 188, 24369):
            self.assertEqual(cat.SERIES[cod]["produtor"]["sigla"], "IBGE", cod)
        for cod in (189, 190):
            self.assertEqual(cat.SERIES[cod]["produtor"]["sigla"], "FGV IBRE", cod)
        for cod in (432, 1178, 4390, 226, 25, 1, 10813, 21619, 24363):
            self.assertEqual(cat.SERIES[cod]["produtor"]["sigla"], "BCB", cod)
        for cod in (195, 256, 20539, 20714, 21082, 13621, 4513):
            self.assertEqual(cat.SERIES[cod]["produtor"]["sigla"], "BCB", cod)
        self.assertEqual(cat.SERIES[7478]["produtor"]["sigla"], "IBGE")
        for cod in (4389, 4391):
            self.assertEqual(cat.SERIES[cod]["produtor"]["sigla"], "B3", cod)

    def test_cdi_e_ipca15_suspensos_series_novas_do_bcb_expostas(self):
        for cod in (4389, 4391, 7478):
            self.assertFalse(cat.exposta(cod), cod)
        for cod in (195, 256, 20539, 20714, 21082, 13621, 4513):
            self.assertTrue(cat.exposta(cod), cod)

    def test_series_novas_respondem_com_o_valor_publicado(self):
        for apelido, cod in (("reservas", 13621), ("inadimplencia", 21082), ("divida-liquida", 4513),
                             ("tjlp", 256), ("poupanca", 195), ("credito", 20539), ("juros-credito", 20714)):
            bruto = json.loads((ROOT / "data" / f"{cod}_history.json").read_text(encoding="utf-8"))
            r = f.get_latest_indicator(D, apelido)
            self.assertEqual(r["codigo_sgs"], cod, apelido)
            self.assertEqual(r["valor_publicado"], bruto[-1]["valor"], apelido)
        self.assertEqual(cat.resolver("poupanca-antiga"), 25)

    def test_cdi_suspenso_informa_o_motivo(self):
        e = erro(f.get_latest_indicator, D, "cdi")
        self.assertEqual(e["erro"], "indicador_suspenso")

    def test_licenciamento_padrao_suspende_ibge_e_fgv(self):
        for cod, m in cat.SERIES.items():
            if m["produtor"]["sigla"] == "BCB":
                self.assertEqual(cat.licenca(cod)["licenca"], "ODbL 1.0")
                self.assertTrue(cat.exposta(cod))
            else:
                self.assertFalse(cat.exposta(cod), cod)
        with restritas_liberadas():
            self.assertTrue(cat.exposta(189))

    def test_procedencia_em_toda_resposta(self):
        r = f.get_latest_indicator(D, "432")
        self.assertEqual(r["distribuidor"]["url"], "https://www3.bcb.gov.br/sgspub/")
        self.assertEqual(r["fonte_url"], "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json")
        self.assertIn("atribuicao", r["licenca"])
        self.assertIsNone(r["data_divulgacao"])
        self.assertIn("não são em tempo real", r["aviso"])

    def test_apelidos(self):
        for apelido, cod in (("Selic", 432), ("IGP-M", 189), ("igp_m", 189), ("dólar", 1), ("SGS-4390", 4390)):
            self.assertEqual(cat.resolver(apelido), cod, apelido)


class TestConsultas(unittest.TestCase):
    def test_ultimo_valor_igual_ao_arquivo(self):
        bruto = json.loads((ROOT / "data" / "1_history.json").read_text(encoding="utf-8"))
        r = f.get_latest_indicator(D, "dolar")
        self.assertEqual(r["valor_publicado"], bruto[-1]["valor"])
        d, m, a = bruto[-1]["data"].split("/")
        self.assertEqual(r["data_referencia"], f"{a}-{m}-{d}")
        self.assertEqual(r["data_ultima_coleta"], json.loads((ROOT / "data" / "meta.json").read_text())["gerado_em"])

    def test_indicador_desconhecido(self):
        e = erro(f.get_latest_indicator, D, "bitcoin")
        self.assertEqual(e["erro"], "indicador_desconhecido")
        self.assertTrue(all(x["codigo_sgs"] in cat.SERIES for x in e["indicadores_disponiveis"]))

    def test_indicador_suspenso_informa_onde_consultar(self):
        e = erro(f.get_latest_indicator, D, "igpm")
        self.assertEqual(e["erro"], "indicador_suspenso")
        self.assertIn("https://portalibre.fgv.br/igp", e["onde_consultar"])

    def test_datas_invalidas(self):
        for ini, fim in (("2026-13", "2026-12"), ("01/02/2026", "2026-03"), ("2026-02-30", "2026-03"), ("", "2026-03")):
            self.assertEqual(erro(f.get_indicator_history, D, "tr", ini, fim)["erro"], "data_invalida", ini)
        self.assertEqual(erro(f.get_indicator_history, D, "tr", "2026-05", "2026-01")["erro"], "periodo_invertido")

    def test_periodo_sem_dados(self):
        e = erro(f.get_indicator_history, D, "tr", "2001-01", "2001-12")
        self.assertEqual(e["erro"], "periodo_sem_dados")
        self.assertEqual(e["disponivel"]["inicio"][:4], "2015")

    def test_paginacao_limita_e_continua(self):
        p1 = f.get_indicator_history(D, "dolar", "2015-01", "2026-12")
        self.assertEqual(p1["observacoes"], f.MAX_PONTOS)
        prox = p1["paginacao"]["proxima_data_inicial"]
        p2 = f.get_indicator_history(D, "dolar", prox, "2026-12")
        self.assertGreater(p2["pontos"][0]["data_referencia"], p1["pontos"][-1]["data_referencia"])
        self.assertEqual(p2["pontos"][0]["data_referencia"], prox)

    def test_tamanho_das_respostas(self):
        r = f.get_indicator_history(D, "tr", "2015-01", "2026-12")
        self.assertLess(len(json.dumps(r, ensure_ascii=False).encode()), 256 * 1024)


class TestCalculos(unittest.TestCase):
    def test_reproduz_o_fator_de_todas_as_paginas_de_reajuste(self):
        """O FATOR da calculadora de cada página /reajuste/<indice>-<mes>-<ano>/ é reproduzido exatamente."""
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                 "setembro", "outubro", "novembro", "dezembro"]
        n, sem_mes_anterior = 0, []
        with restritas_liberadas():
            for pag in sorted((DOCS / "reajuste").glob("*-*-*/index.html")):
                chave, mes, ano = re.match(r"([a-z]+)-([a-zç]+)-(\d{4})", pag.parent.name).groups()
                m = meses.index(mes) + 1
                a0, m0 = (int(ano) - 1, m)
                if int(ano) == 2015:          # 1ª página: o mês anterior (dez/2014) não está nos dados
                    sem_mes_anterior.append(pag.parent.name)
                    continue
                r = f.calculate_adjustment(D, 2000.0, chave, f"{a0}-{m0:02d}", f"{ano}-{m:02d}")
                js = float(re.search(r"const FATOR=([0-9.e-]+);", pag.read_text(encoding="utf-8")).group(1))
                self.assertEqual(r["fator"], js, pag.parent.name)
                self.assertEqual(r["periodo"]["meses_aplicados"], 12)
                n += 1
        self.assertGreater(n, 500)
        self.assertEqual(len(sem_mes_anterior), 4, sem_mes_anterior)

    def test_reproduz_a_pagina_de_correcao(self):
        with restritas_liberadas():
            for chave in ("ipca", "igpm", "inpc", "igpdi"):
                html = (DOCS / "correcao" / chave / "index.html").read_text(encoding="utf-8")
                ref = re.search(r"acumulado nos 12 meses até ([a-zç]+) de (\d{4})", html)
                fator_txt = re.search(r"Fator: <b>([0-9,]+)</b>", html).group(1)
                meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                         "setembro", "outubro", "novembro", "dezembro"]
                m, a = meses.index(ref.group(1)) + 1, int(ref.group(2))
                r = f.calculate_adjustment(D, 1000.0, chave, f"{a - 1}-{m:02d}", f"{a}-{m:02d}")
                self.assertEqual(r["arredondado"]["fator"].replace(".", ","), fator_txt, chave)

    def test_acumulado_negativo(self):
        with restritas_liberadas():
            r = f.calculate_adjustment(D, 2000.0, "igpm", "2022-12", "2023-12")
        self.assertEqual(r["arredondado"]["taxa_acumulada_pct"], "-3.18")
        self.assertLess(r["valor_final"], 2000)
        self.assertTrue(r["observacoes"])
        self.assertIn("igpm-dezembro-2023", r["equivalencia_no_site"]["reajuste_12_meses"])

    def test_arredondamento_e_memoria(self):
        r = f.calculate_adjustment(D, 1000.0, "selic-mensal", "2025-10", "2026-10")
        self.assertEqual(len(r["memoria_de_calculo"]), 12)
        self.assertAlmostEqual(r["memoria_de_calculo"][-1]["fator_acumulado"], r["fator"], places=12)
        self.assertEqual(r["arredondado"]["valor_final"], f"{1000.0 * r['fator']:.2f}")
        self.assertEqual(r["arredondado"]["fator"], f"{r['fator']:.6f}")

    def test_calculo_rejeita_serie_que_nao_e_variacao_mensal(self):
        e = erro(f.calculate_adjustment, D, 1000.0, "dolar", "2025-01", "2025-06")
        self.assertEqual(e["erro"], "indice_nao_aplicavel")
        self.assertIn(4390, e["indices_aceitos"])

    def test_calculo_valida_valor_e_periodo(self):
        self.assertEqual(erro(f.calculate_adjustment, D, -5, "selic-mensal", "2025-01", "2025-06")["erro"], "valor_invalido")
        self.assertEqual(erro(f.calculate_adjustment, D, 10, "selic-mensal", "2025-06", "2025-06")["erro"], "periodo_invertido")
        self.assertEqual(erro(f.calculate_adjustment, D, 10, "selic-mensal", "2030-01", "2030-06")["erro"], "periodo_sem_dados")


class TestComparacao(unittest.TestCase):
    def test_naturezas_diferentes_nao_sao_alinhadas(self):
        r = f.compare_indicators(D, ["selic", "dolar"], "2026-01", "2026-03")
        self.assertFalse(r["comparavel_diretamente"])
        self.assertNotIn("pontos_alinhados", r)
        self.assertIn("Não comparáveis", r["metodologia"])

    def test_mesma_natureza_alinha(self):
        r = f.compare_indicators(D, ["dolar", "dolar-compra"], "2026-01", "2026-01")
        self.assertTrue(r["comparavel_diretamente"])
        self.assertEqual(r["pontos_alinhados_total"], len(r["pontos_alinhados"]))
        p = r["pontos_alinhados"][0]
        self.assertAlmostEqual(p["diferenca_a_menos_b"], p["a"] - p["b"])

    def test_variacoes_mensais_comparam_acumulado(self):
        with restritas_liberadas():
            r = f.compare_indicators(D, ["selic-mensal", "ipca"], "2025-01", "2025-12")
        self.assertTrue(r["comparavel_diretamente"])
        self.assertIn("acumulados_no_periodo", r)

    def test_parametros(self):
        self.assertEqual(erro(f.compare_indicators, D, ["selic"], "2026-01", "2026-02")["erro"], "parametro_invalido")
        self.assertEqual(erro(f.compare_indicators, D, ["selic", "432"], "2026-01", "2026-02")["erro"], "parametro_invalido")


if __name__ == "__main__":
    unittest.main()
