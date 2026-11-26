"""Entrega 2: leituras do CDI (contra o IPCA) e do dólar PTAX.

Dados controlados e sem rede (testes de aceite F e G). O comparador e o
simulador são abertos em node com o MESMO docs/calculos.js do navegador.

    python -m unittest tests.test_leituras_cdi_ptax -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import build_divulgacoes as D  # noqa: E402
import leituras as L  # noqa: E402

NODE = shutil.which("node")


def dias(valores: dict[str, float]) -> list[dict]:
    return [{"dt": datetime.strptime(k, "%Y-%m-%d"), "valor": v} for k, v in sorted(valores.items())]


def meses(valores: dict[str, float]) -> list[dict]:
    return [{"dt": datetime(int(k[:4]), int(k[5:]), 1), "valor": v} for k, v in sorted(valores.items())]


def js(expr: str, **dados):
    prog = (f"const C=require({json.dumps(str(DOCS / 'calculos.js'))});"
            + "".join(f"const {k}={json.dumps(v)};" for k, v in dados.items())
            + f"process.stdout.write(JSON.stringify(({expr})));")
    r = subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


# Semanas de novembro de 2026: 9-13 (anterior), 16-20 (sexta 20 é feriado), 23-27 (em andamento).
PTAX = {"2026-11-09": 5.60, "2026-11-10": 5.61, "2026-11-11": 5.62, "2026-11-12": 5.63, "2026-11-13": 5.65,
        "2026-11-16": 5.70, "2026-11-17": 5.72, "2026-11-18": 5.71, "2026-11-19": 5.75,
        "2026-11-23": 5.74, "2026-11-24": 5.73, "2026-11-25": 5.70}


class Ptax(unittest.TestCase):

    def test_F_sexta_sem_publicacao_usa_a_ultima_cotacao_da_semana(self):
        lt = L.leitura_ptax(dias(PTAX), date(2026, 11, 21))            # sábado: semana 16-20 encerrada
        f = lt["fechamento"]
        self.assertEqual(lt["competencia"], "2026-W47")
        self.assertEqual((f["data"], f["data_anterior"]), ("2026-11-19", "2026-11-13"))
        self.assertAlmostEqual(f["variacao_reais"], 0.10, places=10)
        self.assertAlmostEqual(f["variacao_pct"], (5.75 / 5.65 - 1) * 100, places=10)
        txt = " ".join(lt["frases"])
        self.assertIn("o dólar subiu", txt)
        self.assertIn("quinta-feira 19/11/2026, foi R$ 5,7500", txt)
        self.assertIn("sexta-feira 13/11/2026 (R$ 5,6500)", txt)
        self.assertIn("Não houve PTAX na sexta-feira, 20/11/2026", txt)
        self.assertIsNone(lt["parcial"])
        self.assertEqual(lt["entradas"], {"2026-11-19": 5.75, "2026-11-13": 5.65})

    def test_F_semana_em_andamento_e_parcial_e_queda(self):
        lt = L.leitura_ptax(dias(PTAX), date(2026, 11, 25))            # quarta: semana 23-27 aberta
        self.assertEqual(lt["competencia"], "2026-W47")                 # a encerrada continua sendo a 16-20
        p = lt["parcial"]
        self.assertEqual((p["semana"], p["data"]), ("2026-W48", "2026-11-25"))
        self.assertAlmostEqual(p["variacao_reais"], 5.70 - 5.75, places=10)
        txt = " ".join(lt["frases"])
        self.assertIn("Resultado parcial da semana em andamento: até 25/11/2026", txt)
        self.assertIn("−R$ 0,0500", txt)
        d = lt["diaria"]
        self.assertEqual((d["data"], d["data_anterior"]), ("2026-11-25", "2026-11-24"))
        self.assertLess(d["variacao_reais"], 0)
        self.assertTrue(any(k == "Semana em andamento (parcial)" for k, _ in lt["kpis"]))

    def test_F_sem_base_de_comparacao(self):
        so_uma = {k: x for k, x in PTAX.items() if k >= "2026-11-16" and k <= "2026-11-19"}
        lt = L.leitura_ptax(dias(so_uma), date(2026, 11, 21))
        self.assertIsNone(lt["fechamento"])
        self.assertIn("sem base de comparação", " ".join(lt["frases"]))
        self.assertIn("sem base de comparação", lt["titulo"])
        nenhuma = L.leitura_ptax(dias({"2026-11-23": 5.7}), date(2026, 11, 25))
        self.assertIsNone(nenhuma["competencia"])
        self.assertIn("Ainda não há uma semana encerrada", " ".join(nenhuma["frases"]))

    def test_F_registro_semanal_nao_leva_o_parcial_e_fica_igual(self):
        arq = {"formato": 1, "publicacoes": []}
        h = {1: dias(PTAX)}
        v1 = {"sha": "a" * 40, "curto": "aaaaaaa", "data": "2026-11-25T15:00:00Z"}
        novos = D.registrar(arq, h, {}, v1)
        self.assertEqual([n["id"] for n in novos], ["dolar-2026-W47"])
        self.assertIsNone(novos[0]["leitura"]["parcial"])
        self.assertNotIn("parcial", " ".join(novos[0]["leitura"]["frases"]))
        v2 = {"sha": "b" * 40, "curto": "bbbbbbb", "data": "2026-11-26T15:00:00Z"}
        self.assertEqual(D.registrar(arq, h, {}, v2), [])               # mesma semana, mesmas entradas
        h[1] = dias({**PTAX, "2026-11-26": 5.69, "2026-11-27": 5.80})
        v3 = {"sha": "c" * 40, "curto": "ccccccc", "data": "2026-11-28T15:00:00Z"}
        self.assertEqual([n["id"] for n in D.registrar(arq, h, {}, v3)], ["dolar-2026-W48"])


CDI = {L.soma_mes("2025-10", k): 1.0 for k in range(13)}
IPCA = {L.soma_mes("2025-10", k): 0.4 for k in range(13)}
CDI_DIA = {f"2026-{m:02d}-{d:02d}": 14.15 for m in range(1, 12) for d in (5, 15)}


class Cdi(unittest.TestCase):

    def test_G_leitura_usa_competencias_fechadas_comuns(self):
        cdi = dict(CDI, **{"2026-11": 0.5})                              # novembro em andamento (há dias de nov)
        lt = L.leitura_cdi(meses(cdi), meses(IPCA), dias(CDI_DIA))
        self.assertEqual((lt["inicio"], lt["fim"], lt["mes_aberto"]), ("2025-11", "2026-10", "2026-11"))
        self.assertAlmostEqual(lt["cdi_acumulado"], (1.01 ** 12 - 1) * 100, places=10)
        self.assertAlmostEqual(lt["ipca_acumulado"], (1.004 ** 12 - 1) * 100, places=10)
        self.assertAlmostEqual(lt["taxa_real"], ((1.01 / 1.004) ** 12 - 1) * 100, places=10)
        txt = " ".join(lt["frases"])
        self.assertIn("De novembro de 2025 a outubro de 2026 (12 competências fechadas)", txt)
        self.assertIn("acima do IPCA", txt)
        self.assertIn("Novembro de 2026 ainda está em andamento", txt)
        self.assertIn("SGS 4391", lt["nota"])
        self.assertIn("SGS 4389", lt["nota"])
        self.assertIn("14,15% ao ano na data de 15/11/2026", lt["nota"])

    def test_G_falta_ipca_numa_competencia(self):
        ipca = dict(IPCA)
        del ipca["2026-03"]
        lt = L.leitura_cdi(meses(CDI), meses(ipca), [], "2026-10")
        self.assertIsNone(lt["taxa_real"])
        self.assertIn("IPCA de março de 2026", " ".join(lt["frases"]))

    @unittest.skipUnless(NODE, "node não encontrado")
    def test_G_link_abre_o_comparador_com_os_mesmos_indicadores_periodo_e_resultado(self):
        lt = L.leitura_cdi(meses(CDI), meses(IPCA), [], "2026-10")
        q = dict((k, v[0]) for k, v in parse_qs(urlsplit(lt["links"]["comparador"]).query).items())
        self.assertEqual(urlsplit(lt["links"]["comparador"]).path, "/comparador/")
        r = js("(()=>{const p=C.lerParamsComparador(new URLSearchParams(q));"
               "const mapas={};p.indicadores.forEach(k=>mapas[k]=k==='cdi'?cdi:ipca);"
               "const res=C.comparar(mapas,p.de,p.ate);const u=res.linhas[res.linhas.length-1];"
               "return {p:p,cdi:(u.fatores.cdi-1)*100,ipca:(u.fatores.ipca-1)*100,"
               "real:C.rentabilidadeReal((u.fatores.cdi-1)*100,(u.fatores.ipca-1)*100),n:res.linhas.length};})()",
               q=q, cdi=CDI, ipca=IPCA)
        self.assertEqual(r["p"]["indicadores"], ["cdi", "ipca"])
        self.assertEqual((r["p"]["de"], r["p"]["ate"], r["p"]["ver"]), ("2025-11", "2026-10", "pct"))
        self.assertEqual(r["n"], 12)
        self.assertAlmostEqual(r["cdi"], lt["cdi_acumulado"], places=9)
        self.assertAlmostEqual(r["ipca"], lt["ipca_acumulado"], places=9)
        self.assertAlmostEqual(r["real"], lt["taxa_real"], places=9)

    @unittest.skipUnless(NODE, "node não encontrado")
    def test_G_datas_encaminhadas_ao_simulador(self):
        lt = L.leitura_cdi(meses(CDI), meses(IPCA), [], "2026-10")
        q = dict((k, v[0]) for k, v in parse_qs(urlsplit(lt["links"]["simulador"]).query).items())
        p = js("C.lerParamsSimulador(new URLSearchParams(q))", q=q)
        # Aplicação no 1º dia do 1º mês; resgate no 1º dia do mês seguinte ao último (não rende nesse dia).
        self.assertEqual(p, {"valor": 1000, "percentual": 100, "de": "2025-11-01", "ate": "2026-11-01", "modo": "bruto"})
        diario = [{"d": f"{k}", "v": v} for k, v in sorted(
            {(date(2025, 10, 1) + timedelta(days=i)).isoformat(): 14.0 for i in range(0, 420)
             if (date(2025, 10, 1) + timedelta(days=i)).weekday() < 5}.items())]
        r = js("C.simularCDI(diario,p.de,p.ate,p.percentual,p.valor)", diario=diario, p=p)
        self.assertNotIn("erro", r)
        usados = [l["data"] for l in r["linhas"]]
        self.assertGreaterEqual(min(usados), "2025-11-01")
        self.assertLess(max(usados), "2026-11-01")


class Publicado(unittest.TestCase):

    def assertTem(self, trecho, html):
        self.assertTrue(trecho in html, f"faltou: {trecho}")

    def test_fichas_mostram_leitura_links_e_registro(self):
        cdi = (DOCS / "indicadores" / "cdi" / "index.html").read_text(encoding="utf-8")
        self.assertTem('id="leitura"', cdi)
        self.assertTem("/comparador/?de=", cdi)
        self.assertTem("i=cdi,ipca", cdi)
        self.assertTem("/simulador-cdi/?valor=1000&amp;percentual=100&amp;de=", cdi)
        self.assertTem("O simulador trabalha com dias úteis", cdi)
        dolar = (DOCS / "indicadores" / "dolar" / "index.html").read_text(encoding="utf-8")
        self.assertTem('id="leitura"', dolar)
        self.assertTem("contra a última da semana anterior", dolar)
        self.assertTem("em relação à observação anterior", dolar)
        arq = json.loads((ROOT / "data" / "publicacoes.json").read_text(encoding="utf-8"))
        series = {p["serie"] for p in arq["publicacoes"]}
        self.assertEqual(series, {"ipca", "cdi", "dolar"})
        for p in arq["publicacoes"]:
            self.assertIn(p["url"], (DOCS / "feed.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
