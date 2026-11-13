"""Cálculo do Comparador e do Simulador de CDI (docs/calculos.js).

O código testado roda em node, o mesmo arquivo servido ao navegador. As
referências NÃO usam essas funções: são uma reimplementação em Decimal
(alta precisão) e as próprias séries oficiais (4391 mensal contra a taxa DI
diária composta; IPCA composto contra o IPCA 12 meses da série 13522).

    python -m unittest tests.test_ferramentas_calc -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 50
ROOT = Path(__file__).resolve().parent.parent
CALC = ROOT / "docs" / "calculos.js"
NODE = shutil.which("node")


def js(expr: str, **dados) -> object:
    """Avalia `expr` em node com C = calculos.js e as variáveis dadas (JSON)."""
    prog = (f"const C=require({json.dumps(str(CALC))});"
            + "".join(f"const {k}={json.dumps(v)};" for k, v in dados.items())
            + f"process.stdout.write(JSON.stringify(({expr})));")
    r = subprocess.run([NODE, "-e", prog], capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def bruto(cod: int) -> list[dict]:
    return json.loads((ROOT / "data" / f"{cod}_history.json").read_text(encoding="utf-8"))


def iso(d: str) -> str:
    return datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")


def ref_cdi(diario: list[dict], inicio: str, fim: str, pct: str, valor: str) -> tuple[Decimal, int]:
    """Referência independente: Decimal, 1 + p × ((1 + DI)^(1/252) − 1) por dia útil."""
    saldo, n, p = Decimal(valor), 0, Decimal(pct) / 100
    um = Decimal(1)
    for o in diario:
        d = iso(o["data"])
        if inicio <= d < fim:
            fdi = (um + Decimal(o["valor"]) / 100) ** (um / Decimal(252))
            saldo *= um + p * (fdi - um)
            n += 1
    return saldo, n


def ref_mensal(cod: int, de: str, ate: str) -> Decimal:
    f = Decimal(1)
    for o in bruto(cod):
        m = iso(o["data"])[:7]
        if de <= m <= ate:
            f *= 1 + Decimal(o["valor"]) / 100
    return (f - 1) * 100


@unittest.skipUnless(NODE, "node não instalado (no CI ele existe)")
class TestComparador(unittest.TestCase):
    MAPAS = "({cdi:C.porMes(C.historico(cdi)),selic:C.porMes(C.historico(selic)),ipca:C.porMes(C.historico(ipca))})"

    def comparar(self, de: str, ate: str):
        return js(f"C.comparar({self.MAPAS},de,ate)", cdi=bruto(4391), selic=bruto(4390), ipca=bruto(433), de=de, ate=ate)

    def test_selecao_de_periodos_12_24_36_60(self):
        for n in (12, 24, 36, 60):
            de = js("C.somaMesesMes('2026-09',-(n-1))", n=n)
            r = self.comparar(de, "2026-09")
            self.assertEqual(r["meses"], n)
            self.assertEqual(r["linhas"][0]["mes"], de)
            self.assertEqual(r["linhas"][-1]["mes"], "2026-09")

    def test_acumulado_igual_a_referencia_decimal(self):
        r = self.comparar("2024-01", "2025-12")
        for k, cod in (("cdi", 4391), ("selic", 4390), ("ipca", 433)):
            self.assertAlmostEqual(r["resultado"][k]["pct"], float(ref_mensal(cod, "2024-01", "2025-12")), places=10)

    def test_ipca_composto_bate_com_ipca_12_meses_oficial(self):
        oficial = {iso(o["data"])[:7]: float(o["valor"]) for o in bruto(13522)}
        conferidos = 0
        for fim in ("2023-12", "2024-06", "2025-09", "2026-06"):
            de = js("C.somaMesesMes(f,-11)", f=fim)
            r = js(f"C.comparar({{ipca:C.porMes(C.historico(ipca))}},de,fim)", ipca=bruto(433), de=de, fim=fim)
            self.assertLess(abs(r["resultado"]["ipca"]["pct"] - oficial[fim]), 0.02, fim)
            conferidos += 1
        self.assertEqual(conferidos, 4)

    def test_periodo_invertido_e_mes_ausente(self):
        self.assertIn("erro", self.comparar("2025-06", "2025-01"))
        r = js("C.comparar({ipca:{'2025-01':0.16,'2025-03':0.56}},'2025-01','2025-03')")
        self.assertEqual(r["falta"], {"serie": "ipca", "mes": "2025-02"})
        self.assertIn("erro", js("C.comparar({},'2025-01','2025-03')"))

    def test_composicao_nao_e_soma(self):
        r = js("C.compor([1,1])")
        self.assertAlmostEqual(r["pct"], 2.01, places=12)
        self.assertAlmostEqual(js("C.compor([10,-10])")["pct"], -1.0, places=12)


@unittest.skipUnless(NODE, "node não instalado (no CI ele existe)")
class TestSimulador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.di = bruto(4389)

    def simular(self, inicio, fim, pct, valor, diario=None):
        return js("C.simularCDI(C.historico(d),i,f,p,v)", d=self.di if diario is None else diario,
                  i=inicio, f=fim, p=pct, v=valor)

    def test_100_por_cento_igual_a_referencia_decimal(self):
        r = self.simular("2025-01-02", "2026-01-02", 100, 1000)
        ref, n = ref_cdi(self.di, "2025-01-02", "2026-01-02", "100", "1000")
        self.assertEqual(r["diasUteis"], n)
        self.assertAlmostEqual(r["valorBruto"], float(ref), places=8)
        self.assertAlmostEqual(r["cdiAcumuladoPct"], float((ref / 1000 - 1) * 100), places=9)

    def test_percentuais_abaixo_e_acima_de_100(self):
        for p in ("90", "110", "120", "85.5"):
            r = self.simular("2024-03-01", "2025-03-01", float(p), 5000)
            ref, _ = ref_cdi(self.di, "2024-03-01", "2025-03-01", p, "5000")
            self.assertAlmostEqual(r["valorBruto"], float(ref), places=7, msg=p)

    def test_110_nao_e_1_1_vez_o_rendimento_de_100(self):
        r100 = self.simular("2025-01-02", "2026-01-02", 100, 1000)
        r110 = self.simular("2025-01-02", "2026-01-02", 110, 1000)
        ingenuo = 1.1 * r100["rendimentoBruto"]
        self.assertGreater(abs(r110["rendimentoBruto"] - ingenuo), 0.5)

    def test_100_por_cento_por_mes_bate_com_cdi_mensal_oficial(self):
        """Série diária composta no mês x série mensal 4391 (2 casas): diferença < 0,01 p.p."""
        mensal = {iso(o["data"])[:7]: float(o["valor"]) for o in bruto(4391)}
        for m in ("2024-05", "2025-02", "2025-08", "2026-03"):
            a, n = map(int, m.split("-"))
            ini = date(a, n, 1)
            fim = date(a + (n == 12), n % 12 + 1, 1)
            r = self.simular(ini.isoformat(), fim.isoformat(), 100, 100)
            self.assertLess(abs(r["rentabilidadeBrutaPct"] - mensal[m]), 0.01, m)

    def test_inicio_no_meio_do_mes_usa_so_dias_do_periodo(self):
        r = self.simular("2025-03-17", "2025-04-15", 100, 1000)
        ref, n = ref_cdi(self.di, "2025-03-17", "2025-04-15", "100", "1000")
        self.assertEqual(r["diasUteis"], n)
        self.assertEqual(r["linhas"][0]["data"] >= "2025-03-17", True)
        self.assertLess(r["linhas"][-1]["data"], "2025-04-15")
        self.assertAlmostEqual(r["valorBruto"], float(ref), places=9)
        self.assertEqual(r["diasCorridos"], 29)

    def test_sem_dados_nao_inventa(self):
        ultimo = iso(self.di[-1]["data"])
        depois = (date.fromisoformat(ultimo) + timedelta(days=10)).isoformat()
        self.assertIn("erro", self.simular("2025-01-02", depois, 100, 1000))
        self.assertIn("erro", self.simular("2010-01-04", "2011-01-04", 100, 1000))
        self.assertIn("erro", self.simular("2025-01-02", "2025-06-02", 100, 1000, diario=[]))
        fim_de_semana = self.simular("2025-03-08", "2025-03-10", 100, 1000)   # sábado a segunda
        self.assertEqual(fim_de_semana["diasUteis"], 0)
        self.assertEqual(fim_de_semana["valorBruto"], 1000)

    def test_taxas_nulas_e_negativas(self):
        sint = [{"data": "02/01/2025", "valor": "0"}, {"data": "03/01/2025", "valor": "-1"},
                {"data": "06/01/2025", "valor": "10"}]
        r = self.simular("2025-01-02", "2025-01-07", 100, 1000, diario=sint)
        um = Decimal(1)
        ref = Decimal(1000) * (um + Decimal("-0.01")) ** (um / 252) * (um + Decimal("0.10")) ** (um / 252)
        self.assertAlmostEqual(r["valorBruto"], float(ref), places=9)
        self.assertEqual(r["linhas"][0]["rendimento"], 0)
        self.assertLess(r["linhas"][1]["rendimento"], 0)
        neg = js("C.tributosCDB(-5, 10)")
        self.assertEqual((neg["iof"], neg["ir"]), (0, 0))

    def test_validacao_de_entradas(self):
        for args in (("2025-02-30", "2025-03-01", 100, 1000), ("2025-03-01", "2025-03-01", 100, 1000),
                     ("2025-03-01", "2025-04-01", 0, 1000), ("2025-03-01", "2025-04-01", 301, 1000),
                     ("2025-03-01", "2025-04-01", 100, -5)):
            self.assertIn("erro", self.simular(*args), args)


@unittest.skipUnless(NODE, "node não instalado (no CI ele existe)")
class TestTributosEArredondamento(unittest.TestCase):
    def test_tabela_regressiva_do_ir_nas_fronteiras(self):
        esperado = {1: 22.5, 180: 22.5, 181: 20, 360: 20, 361: 17.5, 720: 17.5, 721: 15, 3000: 15}
        self.assertEqual(js("Object.fromEntries(k.map(x=>[x,C.aliquotaIR(x)]))", k=list(esperado)),
                         {str(k): v for k, v in esperado.items()})

    def test_tabela_do_iof(self):
        tabela = {1: 96, 2: 93, 10: 66, 15: 50, 20: 33, 28: 6, 29: 3, 30: 0, 31: 0, 0: 0}
        self.assertEqual(js("Object.fromEntries(k.map(x=>[x,C.aliquotaIOF(x)]))", k=list(tabela)),
                         {str(k): v for k, v in tabela.items()})

    def test_iof_antes_do_ir_e_centavos(self):
        r = js("C.tributosCDB(100, 10)")
        self.assertEqual((r["iof"], r["ir"], r["total"]), (66.0, 7.65, 73.65))   # 22,5% de (100 − 66)
        r = js("C.tributosCDB(142.04, 365)")
        self.assertEqual(r["ir"], float((Decimal("142.04") * Decimal("0.175")).quantize(Decimal("0.01"))))

    def test_arredondamento_monetario(self):
        self.assertEqual(js("[C.centavos(0.005),C.centavos(1.005),C.centavos(2.675),C.centavos(-1.005),C.centavos(10)]"),
                         [0.01, 1.01, 2.68, -1.01, 10])

    def test_rentabilidade_real(self):
        self.assertAlmostEqual(js("C.rentabilidadeReal(10,5)"), float((Decimal("1.10") / Decimal("1.05") - 1) * 100), places=12)
        self.assertAlmostEqual(js("C.rentabilidadeReal(3,5)"), float((Decimal("1.03") / Decimal("1.05") - 1) * 100), places=12)

    def test_inflacao_do_periodo_por_competencias(self):
        r = js("C.inflacaoPeriodo(C.porMes(C.historico(i)),'2025-03-17','2026-03-16')", i=bruto(433))
        self.assertEqual((r["de"], r["ate"], r["meses"]), ("2025-03", "2026-02", 12))
        self.assertAlmostEqual(r["pct"], float(ref_mensal(433, "2025-03", "2026-02")), places=10)
        falta = js("C.inflacaoPeriodo({'2025-03':0.5},'2025-03-01','2025-06-01')")
        self.assertEqual(falta["falta"], "2025-04")
        self.assertIn("erro", js("C.inflacaoPeriodo({},'2025-03-01','2025-03-20')"))


@unittest.skipUnless(NODE, "node não instalado (no CI ele existe)")
class TestCsvEUrl(unittest.TestCase):
    def test_csv_da_memoria_de_calculo(self):
        out = js("C.csvSimulacao(C.simularCDI(C.historico(d),'2025-03-03','2025-03-08',110,1000))", d=bruto(4389))
        self.assertTrue(out.startswith("\ufeff"))
        linhas = out[1:].strip().split("\r\n")
        self.assertEqual(linhas[0].split(";")[0], "Data")
        self.assertEqual(len(linhas[0].split(";")), 7)
        dias = [o for o in bruto(4389) if "2025-03-03" <= iso(o["data"]) < "2025-03-08"]
        self.assertEqual(len(linhas), 1 + len(dias))     # 03 e 04/03/2025 são Carnaval: sem taxa DI
        self.assertEqual(len(dias), 3)
        self.assertRegex(linhas[1], r"^2025-03-05;\d+,\d{2};110,00;\d,\d{10};1\.000,00;")

    def test_csv_neutraliza_formulas(self):
        out = js("C.csv(['a'],[['=HYPERLINK(1)'],['texto;com;ponto e vírgula'],['-12,5']])")
        self.assertIn("'=HYPERLINK(1)", out)
        self.assertIn('"texto;com;ponto e vírgula"', out)
        self.assertIn("\r\n-12,5\r\n", out)

    def test_parametros_validos(self):
        p = js("C.lerParamsSimulador(new URLSearchParams(q))", q="valor=5000&percentual=110&periodo=12m&modo=bruto")
        self.assertEqual(p, {"valor": 5000, "percentual": 110, "periodo": "12m", "modo": "bruto"})
        p = js("C.lerParamsComparador(new URLSearchParams(q))", q="de=2024-01&ate=2025-12&i=ipca,cdi&ver=reais")
        self.assertEqual(p, {"de": "2024-01", "ate": "2025-12", "indicadores": ["cdi", "ipca"], "ver": "reais"})

    def test_parametros_invalidos_sao_ignorados(self):
        ruins = ("valor=<script>alert(1)</script>&percentual=1e5&periodo=13m&modo=javascript:x&de=2025-02-30&ate=x",
                 "valor=99999999999&percentual=-5", "valor=1000;drop&percentual=110%22")
        for q in ruins:
            self.assertEqual(js("C.lerParamsSimulador(new URLSearchParams(q))", q=q), {}, q)
        p = js("C.lerParamsComparador(new URLSearchParams(q))", q="de=2025-13&ate=2025-01&i=bitcoin,<b>&ver=html&meses=7")
        self.assertEqual(p, {})

    def test_periodo_rapido_termina_no_dia_seguinte_ao_ultimo_dado(self):
        self.assertEqual(js("C.periodoParaDatas('12m','2026-11-12')"), {"inicio": "2025-11-13", "fim": "2026-11-13"})
        self.assertEqual(js("C.somaMeses('2025-03-31',-1)"), "2025-02-28")


if __name__ == "__main__":
    unittest.main()
