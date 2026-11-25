"""Recibos do VAR reproduzíveis: o commit do recibo é o dos dados usados.

    python -m unittest tests.test_var_versao -v

O teste de revisão monta um repositório Git temporário com duas versões da
mesma série (a segunda revisa uma competência antiga) e roda o núcleo do VAR
(docs/var-nucleo.js) em node, lendo cada versão com `git show`. Não depende do
GitHub nem do Banco Central.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))

import render_index as ri  # noqa: E402
import versao_dados as vd  # noqa: E402

NODE = shutil.which("node")
REPO = "iosbilario/observatorio-taxas"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                               "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(cwd), "PATH": "/usr/bin:/bin"}).stdout.strip()


def serie(valores: dict[str, str]) -> str:
    return json.dumps([{"data": f"01/{m[5:]}/{m[:4]}", "valor": v} for m, v in valores.items()]) + "\n"


V1 = {"2025-01": "0.50", "2025-02": "0.40", "2025-03": "0.30", "2025-04": "0.20"}
V2 = dict(V1, **{"2025-01": "0.90"})   # revisão de uma competência antiga


class RepoDuasVersoes:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        (r / "docs" / "data").mkdir(parents=True)
        git(r, "init", "-q")
        (r / "docs/data/433_history.json").write_text(serie(V1))
        git(r, "add", "-A"); git(r, "commit", "-qm", "v1")
        self.sha1 = git(r, "rev-parse", "HEAD")
        (r / "docs/data/433_history.json").write_text(serie(V2))
        git(r, "add", "-A"); git(r, "commit", "-qm", "v2 revisa jan/2025")
        self.sha2 = git(r, "rev-parse", "HEAD")
        self.raiz = r
        return self

    def __exit__(self, *a):
        self.tmp.cleanup()


def nucleo(raiz: Path, js: str) -> dict:
    """Roda `js` em node com V = var-nucleo.js e um lerJson que resolve
    raw.githubusercontent.com/<repo>/<sha>/docs/data/X por `git show` e
    data/X pelo working tree de `raiz`."""
    prog = f"""
const V = require({json.dumps(str(DOCS / "var-nucleo.js"))});
const {{ execFileSync }} = require("child_process");
const fs = require("fs");
const RAIZ = {json.dumps(str(raiz))};
const RAW = "https://raw.githubusercontent.com/{REPO}/";
async function lerJson(url) {{
  if (url.startsWith(RAW)) {{
    const [sha, ...resto] = url.slice(RAW.length).split("/");
    try {{ return JSON.parse(execFileSync("git", ["show", sha + ":" + resto.join("/")], {{ cwd: RAIZ, stdio: ["ignore", "pipe", "ignore"] }}).toString()); }}
    catch (e) {{ throw new Error("404"); }}
  }}
  return JSON.parse(fs.readFileSync(RAIZ + "/docs/" + url, "utf8"));
}}
(async () => {{ const out = await (async () => {{ {js} }})(); console.log(JSON.stringify(out)); }})()
  .catch((e) => {{ console.error(e); process.exit(1); }});
"""
    r = subprocess.run([NODE, "-e", prog], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def acumulado(valores: dict[str, str]) -> float:
    f = 1.0
    for v in valores.values():
        f *= 1 + float(v) / 100
    return (f - 1) * 100


@unittest.skipUnless(NODE, "node não instalado (no CI ele existe)")
class ReciboReproduzivel(unittest.TestCase):

    CALC = ("const r = await V.carregaRecibo({{ lerJson, repo: {repo}, localBase: 'data/', cods: [433], shaPedido: {sha} }});"
            "if (r.erro) return r;"
            "const m = V.metrica(r.dados[433], 'fluxo', 'acum', '2025-01', '2025-04');"
            "return {{ sha: r.sha, modo: r.modo, metric: m.metric }};")

    def calc(self, raiz, sha):
        return nucleo(raiz, self.CALC.format(repo=json.dumps(REPO), sha=json.dumps(sha)))

    def test_recibo_da_primeira_versao_continua_igual_depois_da_revisao(self):
        with RepoDuasVersoes() as r:
            antes = self.calc(r.raiz, r.sha1)
            depois = self.calc(r.raiz, r.sha2)
        self.assertEqual(antes["modo"], "fixado")
        self.assertAlmostEqual(antes["metric"], acumulado(V1), places=9)
        self.assertAlmostEqual(depois["metric"], acumulado(V2), places=9)
        self.assertNotAlmostEqual(antes["metric"], depois["metric"], places=6)

    def test_recibo_novo_usa_e_grava_o_commit_publicado_em_versao_json(self):
        with RepoDuasVersoes() as r:
            # O site serve a v2 no working tree, mas versao.json ainda aponta a v1:
            # o recibo calcula com a v1 e grava a v1 (nunca mistura as duas).
            (r.raiz / "docs/data/versao.json").write_text(vd.conteudo(r.sha1, "2026-01-01T00:00:00Z"))
            out = self.calc(r.raiz, None)
        self.assertEqual(out["sha"], r.sha1)
        self.assertEqual(out["modo"], "versionado")
        self.assertAlmostEqual(out["metric"], acumulado(V1), places=9)

    def test_sem_github_o_recibo_sai_ao_vivo_e_sem_commit(self):
        with RepoDuasVersoes() as r:
            (r.raiz / "docs/data/versao.json").write_text(vd.conteudo("f" * 40, "2026-01-01T00:00:00Z"))
            out = self.calc(r.raiz, None)
        self.assertIsNone(out["sha"])
        self.assertEqual(out["modo"], "ao_vivo")
        self.assertAlmostEqual(out["metric"], acumulado(V2), places=9)

    def test_versao_do_link_indisponivel_nao_troca_de_versao(self):
        with RepoDuasVersoes() as r:
            out = self.calc(r.raiz, "e" * 40)
        self.assertEqual(out, {"erro": "versao_indisponivel", "sha": "e" * 40})

    def test_intervalos_comparaveis_e_duracao(self):
        out = nucleo(ROOT, """
const i = V.intervaloComparavel('2026-10', 48);
const com_buraco = V.metrica([{ym:'2026-01',v:1},{ym:'2026-03',v:1}], 'fluxo', 'acum', '2026-01', '2026-03');
const diario = V.metrica([{ym:'2026-01',v:5},{ym:'2026-01',v:6},{ym:'2026-02',v:7}], 'cambio', 'ponta', '2026-01', '2026-02');
return { i, a: V.mesesEntre(i.a1, i.a2), b: V.mesesEntre(i.b1, i.b2),
         buraco: V.duracaoTxt(com_buraco), diario: V.duracaoTxt(diario) };""")
        self.assertEqual(out["i"], {"a1": "2018-11", "a2": "2022-10", "b1": "2022-11", "b2": "2026-10"})
        self.assertEqual((out["a"], out["b"]), (48, 48))
        self.assertEqual(out["buraco"], "3 meses, 2 com dado")
        self.assertEqual(out["diario"], "2 meses")


class VersaoDosDados(unittest.TestCase):

    def test_commit_dos_dados_ignora_commits_que_so_mudam_versao_json(self):
        with RepoDuasVersoes() as r:
            self.assertTrue(vd.grava(r.raiz))
            git(r.raiz, "add", "-A"); git(r.raiz, "commit", "-qm", "versão dos dados")
            self.assertEqual(vd.commit_dos_dados(r.raiz)[0], r.sha2)
            self.assertFalse(vd.grava(r.raiz))          # idempotente
            v = json.loads((r.raiz / "docs/data/versao.json").read_text())
        self.assertEqual(v["sha"], r.sha2)
        self.assertEqual(v["curto"], r.sha2[:7])


class CapaEVar(unittest.TestCase):

    def test_carimbo_e_recibo_da_capa_apontam_o_commit_dos_dados(self):
        v = ri.versao_dados()
        if not v:
            self.skipTest("sem docs/data/versao.json")
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'dados do commit <a href="https://github.com/{REPO}/commit/{v["sha"]}">{v["curto"]}</a>', html)
        var = re.search(r"<!-- var:inicio -->(.*?)<!-- var:fim -->", html, re.S).group(1)
        self.assertIn(f"&amp;sha={v['sha']}", var)
        self.assertNotIn("commits/main", html)

    def test_recibo_da_capa_compara_periodos_de_mesma_duracao(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        var = re.search(r"<!-- var:inicio -->(.*?)<!-- var:fim -->", html, re.S).group(1)
        p = dict(re.findall(r"&amp;(a1|a2|b1|b2)=(\d{4}-\d{2})", var))
        n = lambda ym: int(ym[:4]) * 12 + int(ym[5:]) - 1  # noqa: E731
        self.assertEqual(n(p["a2"]) - n(p["a1"]), n(p["b2"]) - n(p["b1"]))
        self.assertEqual(n(p["b1"]), n(p["a2"]) + 1)
        self.assertEqual(len(re.findall(r"· 48 meses", var)), 2)

    def test_var_nao_consulta_a_api_do_github_e_avisa_versao_indisponivel(self):
        html = (DOCS / "var.html").read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", html)
        self.assertRegex(html, r'<script src="var-nucleo\.js\?v=[0-9a-f]{10}"></script>')
        self.assertIn("avisaVersaoIndisponivel", html)
        self.assertIn("Conferir a mesma afirmação com os dados atuais", html)
        self.assertIn("A regra de cálculo é a do VAR publicado", html)


if __name__ == "__main__":
    unittest.main()
