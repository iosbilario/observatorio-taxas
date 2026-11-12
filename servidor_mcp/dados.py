"""
dados.py — Leitura das séries publicadas pelo Observatório, com cache.

Fonte padrão: os JSON públicos do site (https://observatoriodetaxas.tec.br/data/),
os mesmos que o GitHub Pages serve e que o robô atualiza a cada 6 horas. O
servidor MCP não consulta o SGS diretamente: devolve exatamente o que o
Observatório publicou, com a data da coleta.

Variáveis de ambiente:
  OBS_MCP_DADOS      URL base ou diretório local (testes/desenvolvimento)
  OBS_MCP_CACHE_SEG  validade do cache em segundos (padrão 600)
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PADRAO = "https://observatoriodetaxas.tec.br/data"
TIMEOUT_SEG = 10
MAX_BYTES = 5 * 1024 * 1024
USER_AGENT = "observatorio-taxas-mcp/0.1 (+https://observatoriodetaxas.tec.br/mcp/)"


class FonteIndisponivel(RuntimeError):
    pass


class Dados:
    def __init__(self, base: str | None = None, ttl: float | None = None):
        self.base = (base or os.environ.get("OBS_MCP_DADOS") or PADRAO).rstrip("/")
        self.ttl = float(ttl if ttl is not None else os.environ.get("OBS_MCP_CACHE_SEG", 600))
        self._cache: dict[str, tuple[float, object, str]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def _baixar(self, nome: str) -> tuple[object, str]:
        if not self.base.startswith(("http://", "https://")):
            p = Path(self.base) / nome
            if not p.is_file():
                raise FonteIndisponivel(f"arquivo {nome} não encontrado")
            return json.loads(p.read_text(encoding="utf-8")), ""
        req = urllib.request.Request(f"{self.base}/{nome}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as r:
                corpo = r.read(MAX_BYTES + 1)
                if len(corpo) > MAX_BYTES:
                    raise FonteIndisponivel(f"{nome} maior que o limite")
                return json.loads(corpo.decode("utf-8")), r.headers.get("ETag", "")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise FonteIndisponivel(f"não foi possível ler {nome}: {e}") from e

    def _json(self, nome: str) -> tuple[object, str]:
        agora = time.monotonic()
        with self._lock:
            c = self._cache.get(nome)
            if c and agora - c[0] < self.ttl:
                return c[1], c[2]
        try:
            obj, etag = self._baixar(nome)
        except FonteIndisponivel:
            if c:                                   # serve o último bom em caso de falha
                return c[1], c[2]
            raise
        with self._lock:
            self._cache[nome] = (agora, obj, etag)
        return obj, etag

    # ------------------------------------------------------------------ #
    def meta(self) -> dict:
        obj, _ = self._json("meta.json")
        return obj if isinstance(obj, dict) else {}

    def historico(self, codigo: int) -> tuple[list[dict], str]:
        """[{dt: date, valor: float, valor_publicado: str}] ordenado, e o ETag do arquivo."""
        bruto, etag = self._json(f"{codigo}_history.json")
        pts = []
        for p in bruto if isinstance(bruto, list) else []:
            try:
                dt = datetime.strptime(p["data"], "%d/%m/%Y").date()
                pts.append({"dt": dt, "valor": float(str(p["valor"]).replace(",", ".")),
                            "valor_publicado": str(p["valor"])})
            except (KeyError, ValueError, TypeError):
                continue
        pts.sort(key=lambda x: x["dt"])
        return pts, etag

    def versao(self, codigo: int | None = None) -> dict:
        m = self.meta()
        v = {"ultima_coleta_com_mudanca": m.get("gerado_em"),
             "fonte_dos_arquivos": self.base if self.base.startswith("http") else "local",
             "repositorio": "https://github.com/iosbilario/observatorio-taxas",
             "como_fixar": ("Cada coleta é um commit em data/. Para o estado exato desta resposta, use o "
                            "commit da main anterior ou igual a ultima_coleta_com_mudanca.")}
        if codigo is not None:
            _, etag = self.historico(codigo)
            v["etag_arquivo"] = etag or None
        return v
