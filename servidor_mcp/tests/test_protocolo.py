"""Testes do protocolo MCP e dos requisitos das plataformas (sem rede).

Cobre o que ChatGPT (plugin directory) e Claude (connectors directory)
verificam no servidor: Streamable HTTP, initialize nas versões de protocolo
atuais, tools/list com title e readOnlyHint/destructiveHint, erros com
detalhe, tamanho de resposta e limite de taxa.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["OBS_MCP_DADOS"] = str(ROOT / "data")
logging.disable(logging.INFO)

from starlette.testclient import TestClient  # noqa: E402

from servidor_mcp import servidor  # noqa: E402

H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(c, method, params=None, id_=1):
    r = c.post("/mcp", headers=H, json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
    return r


class TestProtocolo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(servidor.criar_app())
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def test_health(self):
        self.assertEqual(self.c.get("/health").json()["status"], "ok")

    def test_desafio_openai_sem_token_responde_404(self):
        os.environ.pop("OBS_MCP_OPENAI_CHALLENGE", None)
        self.assertEqual(self.c.get("/.well-known/openai-apps-challenge").status_code, 404)

    def test_desafio_openai_devolve_token_em_texto_puro(self):
        os.environ["OBS_MCP_OPENAI_CHALLENGE"] = "  tok-123abc \n"
        try:
            r = self.c.get("/.well-known/openai-apps-challenge")
        finally:
            del os.environ["OBS_MCP_OPENAI_CHALLENGE"]
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "tok-123abc")
        self.assertTrue(r.headers["content-type"].startswith("text/plain"))

    def test_initialize_em_versoes_atuais(self):
        for v in ("2025-03-26", "2025-06-18", "2025-11-25"):
            r = rpc(self.c, "initialize", {"protocolVersion": v, "capabilities": {},
                                           "clientInfo": {"name": "teste", "version": "1"}})
            res = r.json()["result"]
            self.assertEqual(res["serverInfo"]["name"], "observatorio-taxas")
            self.assertIn("tools", res["capabilities"])
            self.assertTrue(res["protocolVersion"])

    def test_tools_list_atende_as_duas_plataformas(self):
        tools = rpc(self.c, "tools/list").json()["result"]["tools"]
        self.assertEqual({t["name"] for t in tools},
                         {"get_latest_indicator", "get_indicator_history", "calculate_adjustment", "compare_indicators"})
        for t in tools:
            self.assertLessEqual(len(t["name"]), 64)
            self.assertTrue(t.get("title"), t["name"])
            a = t["annotations"]
            self.assertIs(a["readOnlyHint"], True, t["name"])
            self.assertIs(a["destructiveHint"], False, t["name"])
            self.assertIn("inputSchema", t)
            self.assertIn("outputSchema", t)
            desc = t["description"].lower()
            for proibido in ("ignore", "always call", "sempre chame", "system prompt", "instruç"):
                self.assertNotIn(proibido, desc, t["name"])

    def test_chamada_estruturada(self):
        res = rpc(self.c, "tools/call", {"name": "get_latest_indicator", "arguments": {"indicador": "selic"}}).json()["result"]
        self.assertFalse(res["isError"])
        self.assertEqual(res["structuredContent"]["codigo_sgs"], 432)
        self.assertEqual(json.loads(res["content"][0]["text"])["codigo_sgs"], 432)

    def test_erro_tem_codigo_e_mensagem(self):
        res = rpc(self.c, "tools/call", {"name": "get_latest_indicator", "arguments": {"indicador": "xyz"}}).json()["result"]
        self.assertTrue(res["isError"])
        corpo = json.loads(re.search(r"\{.*\}", res["content"][0]["text"], re.S).group(0))
        self.assertEqual(corpo["erro"], "indicador_desconhecido")
        self.assertTrue(corpo["mensagem"])

    def test_validacao_de_parametros(self):
        res = rpc(self.c, "tools/call", {"name": "calculate_adjustment",
                                          "arguments": {"valor": -1, "indice": "selic-mensal",
                                                        "data_inicial": "2025-01", "data_final": "2025-06"}}).json()["result"]
        self.assertTrue(res["isError"])
        res = rpc(self.c, "tools/call", {"name": "get_indicator_history",
                                          "arguments": {"indicador": "x" * 200, "data_inicial": "2025-01",
                                                        "data_final": "2025-06"}}).json()["result"]
        self.assertTrue(res["isError"])

    def test_corpo_grande_rejeitado(self):
        r = self.c.post("/mcp", headers=H, content=b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"x":"'
                        + b"a" * 70_000 + b'"}}')
        self.assertGreaterEqual(r.status_code, 400)


class TestLimiteDeTaxa(unittest.TestCase):
    def test_429_com_retry_after(self):
        with TestClient(servidor.criar_app(por_minuto=5)) as c:
            codigos = [rpc(c, "tools/list").status_code for _ in range(7)]
            self.assertEqual(codigos[:5], [200] * 5)
            r = rpc(c, "tools/list")
            self.assertEqual(r.status_code, 429)
            self.assertIn("Retry-After", r.headers)
            self.assertEqual(r.json()["erro"], "limite_de_taxa")
            self.assertEqual(c.get("/health").status_code, 200, "health fica fora do limite")

    def test_clientes_diferentes_tem_janelas_separadas(self):
        lim = servidor.LimiteDeTaxa(None, por_minuto=1)
        self.assertTrue(lim.permitido("a")[0])
        self.assertFalse(lim.permitido("a")[0])
        self.assertTrue(lim.permitido("b")[0])

    def test_ip_nao_e_guardado_em_claro(self):
        lim = servidor.LimiteDeTaxa(None)
        chave = lim._cliente({"headers": [(b"x-forwarded-for", b"203.0.113.9, 10.0.0.1")], "client": ("10.0.0.1", 1)})
        self.assertNotIn("203", chave)
        self.assertEqual(len(chave), 16)


if __name__ == "__main__":
    unittest.main()
