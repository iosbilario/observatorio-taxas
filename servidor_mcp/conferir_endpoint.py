"""
conferir_endpoint.py — Chama um servidor MCP de verdade com o cliente oficial
(SDK Python, transporte Streamable HTTP) e confere as quatro ferramentas.

    python -m servidor_mcp.conferir_endpoint http://127.0.0.1:8000/mcp
    python -m servidor_mcp.conferir_endpoint https://<seu-servico>/mcp

Saída 0 se tudo responder como esperado. Útil antes de cadastrar o servidor
no ChatGPT ou no Claude e depois de cada deploy.
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

CASOS = [
    ("get_latest_indicator", {"indicador": "selic"}, False),
    ("get_indicator_history", {"indicador": "dolar", "data_inicial": "2026-01", "data_final": "2026-01"}, False),
    ("calculate_adjustment", {"valor": 1000, "indice": "selic-mensal", "data_inicial": "2025-01",
                              "data_final": "2025-12"}, False),
    ("compare_indicators", {"indicadores": ["selic", "dolar"], "data_inicial": "2026-01", "data_final": "2026-02"}, False),
    ("get_latest_indicator", {"indicador": "nao-existe"}, True),
]


async def conferir(url: str) -> int:
    falhas = 0
    async with streamable_http_client(url) as (ler, escrever, *_):
        async with ClientSession(ler, escrever) as s:
            init = await s.initialize()
            print(f"initialize: {init.server_info.name} {init.server_info.version}, protocolo {init.protocol_version}")
            tools = (await s.list_tools()).tools
            print("tools:", ", ".join(f"{t.name} (readOnly={t.annotations.read_only_hint})" for t in tools))
            for nome, args, espera_erro in CASOS:
                r = await s.call_tool(nome, args)
                ok = bool(r.is_error) == espera_erro
                falhas += not ok
                resumo = (r.structured_content or {}) if not r.is_error else r.content[0].text[:120]
                if isinstance(resumo, dict):
                    resumo = {k: resumo[k] for k in list(resumo)[:4]}
                print(f"{'OK ' if ok else 'FALHA'} {nome}: {json.dumps(resumo, ensure_ascii=False)[:200]}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(conferir(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp")))
