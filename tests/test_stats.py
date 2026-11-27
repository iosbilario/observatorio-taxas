"""Coletor de acessos (scripts/fetch_stats.py) e painel /admin/.

A API do GoatCounter é simulada: nenhum teste acessa a rede nem precisa do
token.

    python -m unittest tests.test_stats -v
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_stats as FS  # noqa: E402

BRT = timezone(timedelta(hours=-3))


class Resposta:
    def __init__(self, dados):
        self.dados = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self.dados


def api_falsa(dias: list[str]):
    """Session.get simulado: /stats/total, /stats/hits e /stats/{página}."""
    def get(url, params=None, timeout=None):
        if url.endswith("/stats/total"):
            stats = [{"day": d, "daily": 24, "hourly": [1] * 23 + [ (2 if i == len(dias) - 1 else 1)]}
                     for i, d in enumerate(dias)]
            return Resposta({"total": 24 * len(dias), "stats": stats})
        if url.endswith("/stats/hits"):
            return Resposta({"hits": [
                {"path": "/", "count": 50}, {"path": "/reajuste/igpm-outubro-2026/", "count": 30},
                {"path": "/reajuste/evolucao/", "count": 5}, {"path": "/indicadores/ipca/", "count": 12},
                {"path": "/embed.html?s=432", "count": 3}, {"path": "/xyz", "count": 1}]})
        pagina = url.rsplit("/", 1)[1]
        return Resposta({"stats": [{"name": f"{pagina}-{i}", "count": 20 - i} for i in range(15)]})
    return get


class Coletor(unittest.TestCase):

    def test_secoes(self):
        casos = {"/": "Home", "/observatorio-taxas/": "Home", "/reajuste/evolucao/": "Evolução do contrato",
                 "/reajuste/ipca-março-2024/": "Reajuste", "/correcao/ipca/": "Correção",
                 "/indicadores/igp-m/": "Indicadores", "/var.html": "VAR da Economia",
                 "/embed.html?s=1": "Embeds", "/feed.xml": "Divulgações", "/sobre/": "Institucional",
                 "/admin/": "Admin", "/qualquer": "Outras", "/varx.html": "Outras"}
        for p, s in casos.items():
            self.assertEqual(FS.secao(p), s, p)

    def test_por_hora_corta_a_hora_em_andamento(self):
        serie = [{"data": "2026-11-26", "acessos": 0, "por_hora": list(range(24))},
                 {"data": "2026-11-27", "acessos": 0, "por_hora": [5] * 24}]
        agora = datetime(2026, 11, 27, 10, 40, tzinfo=BRT)
        ult48, ultima, media = FS.por_hora(serie, agora)
        self.assertEqual(ultima, {"hora": "2026-11-27T09:00", "acessos": 5})
        self.assertEqual(ult48[-1]["hora"], "2026-11-27T09:00")
        self.assertEqual(len(ult48), 34)              # 24 de ontem + 10 de hoje (0h a 9h)
        self.assertEqual(media[0], 2.5)
        self.assertEqual(len(media), 24)

    def test_main_grava_os_campos_novos_sem_rede(self):
        hoje = datetime.now(timezone.utc).astimezone(BRT).date()
        dias = [(hoje - timedelta(days=i)).isoformat() for i in range(30, -1, -1)]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"GOATCOUNTER_TOKEN": "teste"}), \
                mock.patch.object(FS, "DATA_DIR", Path(tmp) / "data"), \
                mock.patch.object(FS, "DOCS_DATA_DIR", Path(tmp) / "docs"), \
                mock.patch.object(FS, "load_code", return_value="exemplo"), \
                mock.patch("requests.Session.get", side_effect=api_falsa(dias)):
            FS.main()
            s = json.loads((Path(tmp) / "docs" / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(s["totais"]["30d_anteriores"]["visitantes"], 24 * 31)
        self.assertEqual(s["secoes_30d"][0], {"secao": "Home", "acessos": 50})
        self.assertIn({"secao": "Evolução do contrato", "acessos": 5}, s["secoes_30d"])
        self.assertEqual(set(s["detalhes_30d"]), {"origens", "navegadores", "sistemas", "telas", "paises"})
        self.assertEqual(len(s["detalhes_30d"]["origens"]), FS.TOP_DETALHE)
        self.assertEqual(s["detalhes_30d"]["origens"][0], {"nome": "toprefs-0", "acessos": 20})
        self.assertLessEqual(len(s["ultimas_48h"]), 48)
        self.assertIsNotNone(s["ultima_hora"])
        self.assertEqual(len(s["media_por_hora_do_dia"]), 24)
        self.assertNotIn("por_hora", s["serie_diaria"][0])     # série diária continua enxuta
        self.assertNotIn("teste", json.dumps(s))                # o token nunca vai para o JSON


class Painel(unittest.TestCase):

    def setUp(self):
        self.html = (DOCS / "admin" / "index.html").read_text(encoding="utf-8")

    def test_fora_da_busca_e_sem_script_externo(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow"/>', self.html)
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', self.html).group(1)
        self.assertIn("script-src 'self';", csp)
        self.assertNotIn("cdn.jsdelivr.net", self.html)
        self.assertNotRegex(self.html, r"<script>(?!</script>)")    # nenhum script inline
        self.assertNotIn("/admin/", (DOCS / "sitemap.xml").read_text(encoding="utf-8"))

    def test_segue_o_padrao_do_site(self):
        for trecho in ('data-theme="light"', 'class="nav-site"', 'class="rodape-site"', 'id="conteudo"',
                       "tema.css?v=", "tema.js?v=", "admin.js?v="):
            self.assertIn(trecho, self.html)

    @unittest.skipUnless(shutil.which("node"), "node não encontrado")
    def test_script_monta_o_painel_com_stats_antigo_e_novo(self):
        js = (DOCS / "admin.js").read_text(encoding="utf-8")
        prog = r"""
const JS = require("fs").readFileSync(process.argv[2], "utf8");
function nodeFalso(tag) {
  return { tag, children: [], attrs: {}, style: {}, className: "", _t: "",
    set textContent(v) { this._t = v; this.children = []; }, get textContent() { return this._t + this.children.map(c => c.textContent).join(" "); },
    appendChild(c) { this.children.push(c); return c; }, setAttribute(k, v) { this.attrs[k] = v; } };
}
async function roda(stats) {
  const app = nodeFalso("div"), coleta = nodeFalso("p");
  global.document = { getElementById: id => id === "app" ? app : coleta, createElement: nodeFalso, createElementNS: (ns, t) => nodeFalso(t), createTextNode: (x) => ({ textContent: x }) };
  global.fetch = async () => ({ ok: true, json: async () => stats });
  eval(JS); await new Promise(r => setTimeout(r, 20));
  return app.textContent;
}
(async () => {
  const antigo = { gerado_em_fmt: "26/11/2026 às 22:16", totais: { all_time: { acessos: 10, visitantes: 5 }, ultimos_30d: { acessos: 8, visitantes: 4 } },
                   grupos: { Reajuste: { acessos: 3, sub: { IPCA: 1 } } }, top_paginas: [{ path: "/", count: 3 }], serie_diaria: [{ data: "2026-11-26", acessos: 4 }] };
  const novo = Object.assign({}, antigo, { totais: { all_time: { acessos: 10, visitantes: 5 }, ultimos_30d: { acessos: 8, visitantes: 4 }, "30d_anteriores": { visitantes: 2 } },
                   ultima_hora: { hora: "2026-11-27T09:00", acessos: 7 }, ultimas_48h: [{ hora: "2026-11-27T09:00", acessos: 7 }],
                   media_por_hora_do_dia: Array.from({ length: 24 }, (_, h) => h === 14 ? 3 : 1),
                   secoes_30d: [{ secao: "Home", acessos: 5 }], detalhes_30d: { origens: [{ nome: "google.com", acessos: 3 }] } });
  process.stdout.write(JSON.stringify({ antigo: await roda(antigo), novo: await roda(novo) }));
})();
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(prog)
        try:
            r = subprocess.run(["node", f.name, str(DOCS / "admin.js")], capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(f.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertIn("Disponível a partir da próxima coleta", out["antigo"])
        self.assertIn("comparação a partir da próxima coleta", out["antigo"])
        self.assertIn("▲ +100% ante os 30 dias anteriores", out["novo"])
        self.assertIn("visitantes das 09h às 09h59 de 27/11", out["novo"])
        self.assertIn("das 14h às 14h59", out["novo"])
        self.assertIn("google.com", out["novo"])
        self.assertIn("Média por dia nos 30 dias: 4", out["antigo"])
        self.assertIn("Média das 24 horas: 1,1", out["novo"])


if __name__ == "__main__":
    unittest.main()
