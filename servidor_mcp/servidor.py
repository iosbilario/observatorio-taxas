"""
servidor.py — Servidor MCP remoto (Streamable HTTP) do Observatório de Taxas.

Uma implementação para ChatGPT e Claude: as duas plataformas conectam
servidores MCP remotos por HTTPS com o transporte Streamable HTTP.

    uvicorn servidor_mcp.servidor:app --host 0.0.0.0 --port 8000

Rotas:
  POST /mcp     endpoint MCP (JSON-RPC; respostas JSON, sem sessão)
  GET  /health  verificação de saúde (não consulta dados)
  GET  /.well-known/openai-apps-challenge  token de verificação de domínio da OpenAI

Variáveis de ambiente (todas opcionais):
  OBS_MCP_DADOS               URL base ou diretório dos JSON (padrão: site público)
  OBS_MCP_CACHE_SEG           cache dos JSON, em segundos (padrão 600)
  OBS_MCP_HOSTS               hosts aceitos, separados por vírgula (proteção DNS rebinding)
  OBS_MCP_LIMITE_POR_MINUTO   requisições por cliente por minuto (padrão 60)
  OBS_MCP_LIBERAR_RESTRITAS   "1" expõe IBGE/FGV (só após confirmar os termos)
  OBS_MCP_OPENAI_CHALLENGE    token mostrado pela OpenAI na verificação de domínio
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.responses import JSONResponse, PlainTextResponse

from . import __version__
from . import ferramentas as f
from .dados import Dados

log = logging.getLogger("observatorio.mcp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MAX_RESPOSTA_BYTES = 256 * 1024
DADOS = Dados()

INSTRUCOES = (
    "Indicadores econômicos brasileiros publicados pelo Observatório de Taxas a partir do SGS do Banco Central, "
    "com cálculos de correção pelo produto das variações mensais. Cada resposta informa produtor, distribuidor, "
    "licença, unidade, data de referência e data da coleta. Os dados são atualizados a cada 6 horas."
)

mcp = MCPServer(name="observatorio-taxas", title="Observatório de Taxas", instructions=INSTRUCOES,
                website_url="https://observatoriodetaxas.tec.br/mcp/", version=__version__)

LEITURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

Indicador = Annotated[str, Field(min_length=1, max_length=40, description=(
    "Código SGS (ex.: 432) ou apelido: selic, selic-efetiva, selic-mensal, tr, poupanca, dolar, dolar-compra, "
    "euro, ibc-br. IPCA, INPC, IGP-M, IGP-DI e desocupação podem estar suspensos por licenciamento."))]
Data = Annotated[str, Field(min_length=7, max_length=10, description="AAAA-MM-DD ou AAAA-MM")]


def _executar(nome: str, fn, *args) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        r = fn(DADOS, *args)
    except f.ErroConsulta as e:
        log.info("tool=%s erro=%s ms=%d", nome, e.dados["erro"], (time.monotonic() - t0) * 1000)
        raise ToolError(str(e)) from None
    tam = len(json.dumps(r, ensure_ascii=False).encode())
    if tam > MAX_RESPOSTA_BYTES:
        log.info("tool=%s erro=resposta_grande bytes=%d", nome, tam)
        raise ToolError(json.dumps({"erro": "resposta_grande", "mensagem": "Resposta acima do limite; reduza o período."},
                                   ensure_ascii=False))
    log.info("tool=%s ok bytes=%d ms=%d", nome, tam, (time.monotonic() - t0) * 1000)
    return r


@mcp.tool(name="get_latest_indicator", title="Último valor de um indicador", annotations=LEITURA)
def get_latest_indicator(indicador: Indicador) -> dict[str, Any]:
    """Retorna o valor mais recente publicado pelo Observatório para um indicador econômico brasileiro, com unidade,
    data de referência, data da coleta, produtor, código SGS, link da fonte e link da página no Observatório."""
    return _executar("get_latest_indicator", f.get_latest_indicator, indicador)


@mcp.tool(name="get_indicator_history", title="Série histórica de um indicador", annotations=LEITURA)
def get_indicator_history(indicador: Indicador, data_inicial: Data, data_final: Data) -> dict[str, Any]:
    """Retorna os pontos de um indicador entre duas datas (até 500 por chamada; se houver mais, informa
    paginacao.proxima_data_inicial), com unidade, fonte, intervalo disponível e versão dos dados."""
    return _executar("get_indicator_history", f.get_indicator_history, indicador, data_inicial, data_final)


@mcp.tool(name="calculate_adjustment", title="Calcular reajuste ou correção", annotations=LEITURA)
def calculate_adjustment(
    valor: Annotated[float, Field(gt=0, le=1e12, description="Valor original em reais")],
    indice: Indicador, data_inicial: Data, data_final: Data,
) -> dict[str, Any]:
    """Corrige um valor por um índice de variação mensal entre dois meses, com a mesma regra da calculadora de
    correção do Observatório: aplica as variações dos meses posteriores ao mês inicial até o mês final. Retorna
    taxa acumulada, fator, valor final, fórmula e memória de cálculo mês a mês."""
    return _executar("calculate_adjustment", f.calculate_adjustment, valor, indice, data_inicial, data_final)


@mcp.tool(name="compare_indicators", title="Comparar dois indicadores", annotations=LEITURA)
def compare_indicators(
    indicadores: Annotated[list[Indicador], Field(min_length=2, max_length=2, description="Dois indicadores")],
    data_inicial: Data, data_final: Data,
) -> dict[str, Any]:
    """Compara dois indicadores num período. Só alinha ponto a ponto séries de mesma natureza, unidade e
    periodicidade; caso contrário, resume cada uma separadamente e explica por que não são comparáveis."""
    return _executar("compare_indicators", f.compare_indicators, indicadores, data_inicial, data_final)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok", "versao": __version__, "ferramentas": 4})


@mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def desafio_openai(_request):
    """Verificação de domínio da submissão à OpenAI: devolve o token em texto puro."""
    token = os.environ.get("OBS_MCP_OPENAI_CHALLENGE", "").strip()
    if not token:
        return PlainTextResponse("not found", status_code=404)
    return PlainTextResponse(token)


@mcp.custom_route("/", methods=["GET"])
async def raiz(_request):
    return JSONResponse({"servico": "Observatório de Taxas — servidor MCP", "endpoint_mcp": "/mcp",
                         "documentacao": "https://observatoriodetaxas.tec.br/mcp/"})


# ------------------------------------------------------------------ limites
class LimiteDeTaxa:
    """Janela deslizante de 60 s por cliente (IP com hash, nunca guardado em claro) e um teto global."""

    def __init__(self, app, por_minuto: int | None = None, global_por_minuto: int = 1200):
        self.app = app
        self.por_minuto = int(por_minuto or os.environ.get("OBS_MCP_LIMITE_POR_MINUTO", 60))
        self.global_por_minuto = global_por_minuto
        self._janelas: dict[str, list[float]] = {}
        self._global: list[float] = []
        self._lock = threading.Lock()
        self._sal = os.urandom(16)

    def _cliente(self, scope) -> str:
        cab = dict(scope.get("headers") or [])
        ip = (cab.get(b"x-forwarded-for", b"").split(b",")[-1].strip()
              or (scope.get("client") or ("?",))[0].encode())
        return hashlib.sha256(self._sal + ip).hexdigest()[:16]

    def permitido(self, chave: str) -> tuple[bool, int]:
        agora = time.monotonic()
        with self._lock:
            self._global = [t for t in self._global if agora - t < 60]
            j = [t for t in self._janelas.get(chave, []) if agora - t < 60]
            if len(j) >= self.por_minuto or len(self._global) >= self.global_por_minuto:
                self._janelas[chave] = j
                espera = int(60 - (agora - (j[0] if j else self._global[0]))) + 1
                return False, espera
            j.append(agora)
            self._global.append(agora)
            self._janelas[chave] = j
            if len(self._janelas) > 50_000:
                self._janelas = {k: v for k, v in self._janelas.items() if v and agora - v[-1] < 60}
            return True, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") == "/health":
            return await self.app(scope, receive, send)
        ok, espera = self.permitido(self._cliente(scope))
        if not ok:
            log.info("limite_de_taxa path=%s", scope.get("path"))
            r = JSONResponse({"erro": "limite_de_taxa", "mensagem": "Muitas requisições. Tente de novo em instantes.",
                              "tentar_em_segundos": espera}, status_code=429, headers={"Retry-After": str(espera)})
            return await r(scope, receive, send)
        return await self.app(scope, receive, send)


def criar_app(por_minuto: int | None = None):
    hosts = [h.strip() for h in os.environ.get("OBS_MCP_HOSTS", "").split(",") if h.strip()]
    seguranca = TransportSecuritySettings(enable_dns_rebinding_protection=bool(hosts),
                                          allowed_hosts=hosts, allowed_origins=[])
    base = mcp.streamable_http_app(stateless_http=True, json_response=True, max_request_body_size=64 * 1024,
                                   transport_security=seguranca, host="0.0.0.0")
    return LimiteDeTaxa(base, por_minuto=por_minuto)


app = criar_app()
