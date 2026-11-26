"""Demonstrativo de reajuste (docs/demonstrativo.js) e "Copiar demonstrativo".

O código testado roda em node, o mesmo arquivo servido ao navegador. As
referências são independentes: Decimal com o fator exibido (10 casas) e o
fator publicado nas páginas de mês.

    python -m unittest tests.test_demonstrativo -v
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DEMO = DOCS / "demonstrativo.js"
NODE = shutil.which("node")
SHA = "0123456789abcdef0123456789abcdef01234567"


def js(corpo: str, **dados) -> object:
    """Roda `corpo` (async) em node com D = demonstrativo.js; `corpo` faz return."""
    prog = (f"const D=require({json.dumps(str(DEMO))});"
            + "".join(f"const {k}={json.dumps(v)};" for k, v in dados.items())
            + f"(async()=>{{{corpo}}})().then(r=>process.stdout.write(JSON.stringify(r)))"
            + ".catch(e=>{console.error(e);process.exit(1)});")
    r = subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def fatores_publicados() -> dict[str, float]:
    out = {}
    for p in sorted((DOCS / "reajuste").glob("*/index.html")):
        m = re.search(r'data-fator="([0-9.]+)"', p.read_text(encoding="utf-8"))
        if m:
            out[p.parent.name] = float(m.group(1))
    return out


def brl(x: Decimal) -> str:
    s = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


@unittest.skipUnless(NODE, "node não encontrado")
class TestDemonstrativo(unittest.TestCase):

    def test_texto_completo(self):
        t = js("return D.texto({valor:2000,fator:1.0557990123,indice:'IGP-M',refYm:'2024-10',"
               "produtor:'FGV IBRE',link:D.linkConferencia('igpm','2024-10',sha)});", sha=SHA)
        self.assertEqual(t, "\n".join([
            "Reajuste pelo IGP-M (acumulado em 12 meses)",
            "Valor original: R$ 2.000,00",
            "Período: novembro de 2023 a outubro de 2024 (12 meses)",
            "Acumulado: 5,58%",
            "Fator: 1,0557990123",
            "Valor reajustado: R$ 2.111,60",
            "Diferença: + R$ 111,60",
            f"Confira o índice, o período e o fator: https://observatoriodetaxas.tec.br/reajuste/igpm-outubro-2024/?dados={SHA}",
            "Fonte: FGV IBRE, via SGS/Banco Central. Calculado pelo Observatório de Taxas. Conteúdo informativo.",
        ]))

    def test_percentual_arredondado_erra_centavos_e_fator_nao(self):
        """IGP-M até out/2024: 5,58% na tela; aplicar 5,58% a R$ 50.000 dá 7 centavos a mais."""
        f = fatores_publicados()["igpm-outubro-2024"]
        r = js("return {c:D.calcula(50000,f), pct:D.pctTxt((f-1)*100), fat:D.fatorTxt(f)};", f=f)
        self.assertEqual(r["pct"], "5,58%")
        pelo_pct = (Decimal(50000) * Decimal("1.0558")).quantize(Decimal("0.01"))
        pelo_fator = (Decimal(50000) * Decimal(r["fat"].replace(",", "."))).quantize(Decimal("0.01"), ROUND_HALF_UP)
        self.assertEqual(Decimal(str(r["c"]["novo"])), pelo_fator)
        self.assertEqual(pelo_fator, Decimal("52789.93"))
        self.assertEqual(pelo_pct - pelo_fator, Decimal("0.07"))

    def test_centavos_reproduziveis_em_toda_a_faixa(self):
        """Para todo fator publicado e valores de R$ 0,01 a R$ 10.000.000,00, o texto
        fecha à mão: valor × fator exibido (Decimal) = valor reajustado do texto, e
        fica a menos de R$ 0,001 (no produto) e de R$ 0,006 (no arredondado) de valor × fator completo."""
        fat = fatores_publicados()
        self.assertGreater(len(fat), 500)
        rnd = random.Random(42)
        valores = [0.01, 0.99, 1, 999.99, 2000, 123456.78, 9999999.99, 10000000]
        valores += [rnd.randint(1, 10**9) / 100 for _ in range(40)]
        casos = [[f, v] for f in fat.values() for v in valores]
        res = js("return casos.map(([f,v])=>{const c=D.calcula(v,f);return [D.fatorTxt(f),c.novo,c.diferenca];});",
                 casos=casos)
        for (f, v), (ftxt, novo, dif) in zip(casos, res):
            fd = Decimal(ftxt.replace(".", "").replace(",", "."))
            self.assertEqual(len(ftxt.split(",")[1]), 10, ftxt)
            vd = Decimal(str(v))
            esperado = (vd * fd).quantize(Decimal("0.01"), ROUND_HALF_UP)
            self.assertEqual(Decimal(str(novo)).quantize(Decimal("0.01")), esperado, (f, v))
            self.assertEqual(Decimal(str(dif)).quantize(Decimal("0.01")), esperado - vd, (f, v))
            self.assertLess(abs(vd * Decimal(repr(f)) - esperado), Decimal("0.006"), (f, v))
            self.assertLess(abs(vd * Decimal(repr(f)) - vd * fd), Decimal("0.001"), (f, v))

    def test_reajuste_negativo(self):
        t = js("return D.texto({valor:1000,fator:0.9876543211,indice:'IGP-M',refYm:'2023-08',"
               "produtor:'FGV IBRE',link:'L'});")
        self.assertIn("Acumulado: −1,23%", t)
        self.assertIn("Valor reajustado: R$ 987,65", t)
        self.assertIn("Diferença: − R$ 12,35", t)
        self.assertIn("Acumulado negativo: confira no contrato se a redução se aplica.", t)

    def test_sem_reducao_nao_tem_aviso(self):
        t = js("return D.texto({valor:1000,fator:1.05,indice:'IPCA',refYm:'2024-01',produtor:'IBGE',link:'L'});")
        self.assertNotIn("Acumulado negativo", t)
        self.assertIn("Período: fevereiro de 2023 a janeiro de 2024 (12 meses)", t)

    def test_link_nunca_leva_o_valor(self):
        r = js("const v=[1234.56,10000000];return v.map(x=>{"
               "const l=D.linkConferencia('ipca','2024-03',sha);"
               "const t=D.texto({valor:x,fator:1.04,indice:'IPCA',refYm:'2024-03',produtor:'IBGE',link:l});"
               "return [l,t.split('\\n').filter(s=>s.startsWith('Confira'))[0]];});", sha=SHA)
        for link, linha in r:
            self.assertEqual(link, f"https://observatoriodetaxas.tec.br/reajuste/ipca-março-2024/?dados={SHA}")
            self.assertEqual(linha, "Confira o índice, o período e o fator: " + link)
        sem = js("return [D.linkConferencia('ipca','2024-03',null),D.linkConferencia('ipca','2024-03','abc')];")
        self.assertEqual(sem, ["https://observatoriodetaxas.tec.br/reajuste/ipca-março-2024/"] * 2)

    def test_parse_valor(self):
        casos = {"2.000,00": 2000, "2000,5": 2000.5, "2000.50": 2000.5, "2.000": 2000,
                 "R$ 1.234,56": 1234.56, "10.000.000,00": 10000000, "0,01": 0.01,
                 "10.000.000,01": None, "0": None, "-5": None, "abc": None, "": None, "1,2,3": None}
        r = js("return casos.map(s=>D.parseValor(s));", casos=list(casos))
        self.assertEqual(dict(zip(casos, r)), casos)

    def test_fator_na_versao(self):
        hist = [{"data": f"01/{m:02d}/2024", "valor": "1,00"} for m in range(1, 13)]
        r = js("""
          const ok = await D.fatorNaVersao(async u => { urls.push(u); return hist; }, sha, 433, '2024-12');
          const falta = await D.fatorNaVersao(async () => hist, sha, 433, '2025-01');
          const fora = await D.fatorNaVersao(async () => { throw new Error('HTTP 404'); }, sha, 433, '2024-12');
          return {ok, falta, fora, urls};""", hist=hist, sha=SHA, urls=[])
        self.assertTrue(r["ok"]["ok"])
        self.assertAlmostEqual(r["ok"]["fator"], 1.01 ** 12, places=12)
        self.assertEqual(r["urls"], [f"https://raw.githubusercontent.com/iosbilario/observatorio-taxas/{SHA}/docs/data/433_history.json"])
        self.assertEqual(r["falta"], {"ok": False, "motivo": "competencia_indisponivel"})
        self.assertEqual(r["fora"], {"ok": False, "motivo": "versao_indisponivel"})


class TestPaginas(unittest.TestCase):

    @unittest.skipUnless(NODE, "node não encontrado")
    def test_todo_trecho_que_ensina_a_conta_usa_o_fator_do_demonstrativo(self):
        """Página do mês: todo fator escrito (resposta, card, FAQ, descrição) é o
        fatorTxt do demonstrativo, e o exemplo de R$ 2.000,00 é o calcula dele.
        Correção monetária: o mesmo, com o exemplo de R$ 1.000,00."""
        casos = []
        for sub, valor in (("reajuste", 2000), ("correcao", 1000)):
            for p in sorted((DOCS / sub).glob("*/index.html")):
                html = p.read_text(encoding="utf-8")
                fatores = set(re.findall(r"fator(?: de reajuste)?:? (?:<b>)?(\d+,\d+)", html))
                exemplos = set(re.findall(r"(?:passa[m]? a|→ <b>) ?R\$ ([\d.]+,\d\d)", html))
                if not fatores:
                    continue
                m = re.search(r'data-fator="([0-9.]+)"', html)
                casos.append([p.parent.name, sub, valor, m and float(m.group(1)), sorted(fatores), sorted(exemplos)])
        self.assertGreater(len([c for c in casos if c[1] == "reajuste"]), 500)
        self.assertGreater(len([c for c in casos if c[1] == "correcao"]), 3)
        for nome, sub, valor, f, fatores, exemplos in casos:
            self.assertEqual(len(fatores), 1, (nome, fatores))
            self.assertEqual(len(fatores[0].split(",")[1]), 10, (nome, fatores))
            self.assertLessEqual(len(exemplos), 1, (nome, exemplos))
        reaj = [c for c in casos if c[3] is not None]
        r = js("return casos.map(([n,s,v,f])=>[D.fatorTxt(f), D.br(D.calcula(v,f).novo,2)]);", casos=reaj)
        for (nome, _, _, _, fatores, exemplos), (ftxt, novo) in zip(reaj, r):
            self.assertEqual(fatores, [ftxt], nome)
            self.assertEqual(exemplos, [novo], nome)
        for nome, sub, valor, _, fatores, exemplos in casos:
            if exemplos:
                fd = Decimal(fatores[0].replace(",", "."))
                esperado = (Decimal(valor) * fd).quantize(Decimal("0.01"), ROUND_HALF_UP)
                self.assertEqual(Decimal(exemplos[0].replace(".", "").replace(",", ".")), esperado, nome)

    def test_paginas_de_mes_usam_o_componente(self):
        paginas = sorted((DOCS / "reajuste").glob("*-*-*/index.html"))
        self.assertGreater(len(paginas), 500)
        for p in paginas:
            html = p.read_text(encoding="utf-8")
            self.assertIn("data-demonstrativo", html, p)
            self.assertRegex(html, r'demonstrativo\.js\?v=[0-9a-f]+', p)
            self.assertNotIn("const FATOR=", html, p)
            self.assertIn("https://raw.githubusercontent.com", html, p)

    def test_home_usa_o_componente(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'demonstrativo\.js\?v=[0-9a-f]+')
        self.assertIn('id="rj-copiar"', html)
        self.assertIn("Demo.copiar(", html)
        self.assertRegex(html, r'id="rj-copiar-status"[^>]*role="status"')


if __name__ == "__main__":
    unittest.main()
