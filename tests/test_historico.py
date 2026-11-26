"""Entrega 3: consulta por data histórica (docs/historico.js e scripts/versoes_series.py).

Teste de aceite C, sem rede: a lógica do navegador roda em node com o mesmo
arquivo servido ao site; o índice sai de um repositório Git temporário.

    python -m unittest tests.test_historico -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import versoes_series as VS  # noqa: E402

NODE = shutil.which("node")
# Duas coletas no dia 10/03 (a segunda às 23:30 de Brasília = 02:30 UTC do dia 11), nenhuma no dia 11,
# e no dia 12 uma versão que revisa fev/2026 e traz por backfill uma competência de 2015.
VERSOES = [{"sha": "a" * 40, "registrado_em": "2026-03-10T10:00:00-03:00"},
           {"sha": "b" * 40, "registrado_em": "2026-03-11T02:30:00Z"},
           {"sha": "c" * 40, "registrado_em": "2026-03-12T09:00:00-03:00"}]
V_B = [{"data": "01/01/2026", "valor": "0.30"}, {"data": "01/02/2026", "valor": "0.50"}, {"data": "01/03/2026", "valor": "0.10"}]
V_C = [{"data": "01/01/2015", "valor": "1.24"}, {"data": "01/01/2026", "valor": "0.30"},
       {"data": "01/02/2026", "valor": "0.55"}, {"data": "01/04/2026", "valor": "0.20"}]


def js(expr: str, **dados):
    prog = (f"const H=require({json.dumps(str(DOCS / 'historico.js'))});"
            + "".join(f"const {k}={json.dumps(v)};" for k, v in dados.items())
            + f"process.stdout.write(JSON.stringify(({expr})));")
    r = subprocess.run([NODE, "-"], input=prog, capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, "node não encontrado")
class Consulta(unittest.TestCase):

    def escolhe(self, dia):
        return js("H.escolher(v, d)", v=VERSOES, d=dia)

    def test_C_corte_no_fim_do_dia_em_brasilia(self):
        self.assertEqual(self.escolhe("2026-03-10")["versao"]["sha"], "b" * 40)   # 23:30 de Brasília ainda é dia 10
        depois_da_meia_noite = VERSOES[:1] + [{"sha": "d" * 40, "registrado_em": "2026-03-11T03:30:00Z"}]
        self.assertEqual(js("H.escolher(v,'2026-03-10')", v=depois_da_meia_noite)["versao"]["sha"], "a" * 40)

    def test_C_dia_sem_coleta_usa_a_ultima_versao_anterior(self):
        self.assertEqual(self.escolhe("2026-03-11")["versao"]["sha"], "b" * 40)
        self.assertEqual(self.escolhe("2026-03-12")["versao"]["sha"], "c" * 40)

    def test_C_antes_da_cobertura_mostra_a_primeira_data(self):
        r = self.escolhe("2026-03-09")
        self.assertTrue(r["antesDaCobertura"])
        self.assertIsNone(r["versao"])
        self.assertEqual(r["primeira"]["registrado_em"], "2026-03-10T10:00:00-03:00")

    def test_C_backfill_fica_fora_da_visao_anterior_e_revisao_aparece(self):
        linhas = {l["data"]: l for l in js("H.comparar(a, b)", a=V_B, b=V_C)}
        self.assertEqual(linhas["01/01/2015"]["situacao"], "entrou_depois")
        self.assertIsNone(linhas["01/01/2015"]["antes"])
        self.assertEqual(linhas["01/01/2026"]["situacao"], "igual")
        self.assertEqual((linhas["01/02/2026"]["situacao"], linhas["01/02/2026"]["antes"], linhas["01/02/2026"]["agora"]),
                         ("alterado", 0.5, 0.55))
        self.assertEqual(linhas["01/03/2026"]["situacao"], "deixou")
        self.assertEqual(linhas["01/04/2026"]["situacao"], "entrou_depois")
        self.assertEqual(js("H.resumo(H.comparar(a,b))", a=V_B, b=V_C),
                         {"igual": 1, "alterado": 1, "entrou_depois": 2, "deixou": 1})
        datas = [l["data"] for l in js("H.comparar(a, b)", a=V_B, b=V_C)]
        self.assertEqual(datas[0], "01/01/2015")                                  # ordem pela data de referência

    def test_url_da_versao_e_raw_do_commit(self):
        self.assertEqual(js("H.urlRaw(s,'data/433_history.json')", s="c" * 40),
                         f"https://raw.githubusercontent.com/iosbilario/observatorio-taxas/{'c' * 40}/data/433_history.json")


def git(cwd: Path, *args: str, data: str | None = None) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "HOME": str(cwd), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    if data:
        env.update(GIT_AUTHOR_DATE=data, GIT_COMMITTER_DATE=data)
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


class Indice(unittest.TestCase):

    def test_indice_lista_so_os_commits_que_mudaram_a_serie_na_ordem(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            (r / "data").mkdir()
            git(r, "init", "-q", "-b", "main")
            (r / "data/433_history.json").write_text(json.dumps(V_B))
            git(r, "add", "-A"); git(r, "commit", "-qm", "v1", data="2026-03-10T10:00:00-03:00")
            (r / "outro.txt").write_text("x")
            git(r, "add", "-A"); git(r, "commit", "-qm", "não mexe na série", data="2026-03-11T10:00:00-03:00")
            (r / "data/433_history.json").write_text(json.dumps(V_C))
            git(r, "add", "-A"); git(r, "commit", "-qm", "v2", data="2026-03-12T09:00:00-03:00")
            vs = VS.versoes(433, r)
            self.assertTrue(VS.historico_completo(r))
        self.assertEqual([v["registrado_em"] for v in vs], ["2026-03-10T10:00:00-03:00", "2026-03-12T09:00:00-03:00"])

    def test_indice_publicado_e_pagina(self):
        idx = json.loads((DOCS / "data" / "versoes" / "index.json").read_text(encoding="utf-8"))["series"]
        self.assertEqual(len(idx), 25)
        for s in idx:
            d = json.loads((DOCS / "data" / "versoes" / f"{s['codigo']}.json").read_text(encoding="utf-8"))
            ts = [v["registrado_em"] for v in d["versoes"]]
            self.assertEqual(ts[0], s["primeira"])
            self.assertEqual(len(ts), s["versoes"])
            self.assertTrue(all(len(v["sha"]) == 40 for v in d["versoes"]))
            self.assertLess((DOCS / "data" / "versoes" / f"{s['codigo']}.json").stat().st_size, 20_000)
        html = (DOCS / "historico" / "index.html").read_text(encoding="utf-8")
        self.assertIn("connect-src 'self' https://raw.githubusercontent.com", html)
        self.assertRegex(html, r'historico\.js\?v=[0-9a-f]{10}')
        ficha = (DOCS / "indicadores" / "ipca" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/historico/?serie=433">Consultar versão histórica</a>', ficha)


if __name__ == "__main__":
    unittest.main()
