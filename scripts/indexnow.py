"""
indexnow.py — Notifica buscadores (protocolo IndexNow) SÓ das URLs que mudaram.

Fonte das mudanças: data/sitemap_lastmod.json (impressão digital do conteúdo
de cada URL, mantida por render_index.py). O estado do último envio bem
sucedido fica fora da main (branch `indexnow-state`, ver
.github/workflows/indexnow.yml). A diferença entre os dois estados dá:

  - novas:      URL no estado atual e ausente no anterior;
  - alteradas:  impressão digital diferente;
  - removidas:  URL no anterior e ausente no atual.

Antes de enviar, confirma o deploy NO SITE PUBLICADO:
  1. o arquivo de chave https://<host>/<chave>.txt responde com a chave;
  2. cada URL nova/alterada responde 200 com a MESMA impressão digital do
     estado (a versão no ar é a que vamos anunciar);
  3. cada URL removida responde 404 ou 410.
URL que não passa fica pendente: não é enviada e continua na diferença da
próxima execução. Sem diferença, nada é enviado.

Envio: POST JSON em lotes de até 10.000 URLs, timeout por requisição, retry
com espera crescente só para 429, 5xx e falha de rede. 400/403/422 não são
repetidos (erro de formato, chave ou host) e não avançam o estado.

IndexNow só avisa que a URL mudou. Não garante rastreamento, indexação nem
presença em respostas de IA.

Uso:
    python scripts/indexnow.py --anterior estado.json --saida novo.json --log envio.jsonl
    python scripts/indexnow.py --anterior estado.json --dry-run            # não envia nada
    python scripts/indexnow.py --anterior estado.json --dry-run --sem-verificar   # nem acessa o site

Saída: 0 = nada a fazer, enviado, ou pendente por deploy ainda não visível
(tenta de novo na próxima execução); 1 = erro que precisa de gente (chave
recusada, formato, host); 2 = uso incorreto.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_index import impressao_digital_html  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yml"
ESTADO_ATUAL = ROOT / "data" / "sitemap_lastmod.json"
BASE_URL = "https://observatoriodetaxas.tec.br"
HOST = urlparse(BASE_URL).netloc
USER_AGENT = "observatorio-taxas-indexnow/1.0 (+https://github.com/iosbilario/observatorio-taxas)"
LOTE_MAX = 10_000
CHAVE_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")

# Códigos de resposta do protocolo (https://www.indexnow.org/documentation).
CODIGOS = {
    200: "OK: URLs recebidas",
    202: "Accepted: URLs recebidas, validação da chave pendente",
    400: "Bad request: formato inválido",
    403: "Forbidden: chave inválida (arquivo não encontrado ou sem a chave)",
    422: "Unprocessable Entity: URL fora do host ou chave fora do padrão",
    429: "Too Many Requests: excesso de envios",
}
SUCESSO = {200, 202}
REPETIR = {429, 500, 502, 503, 504}


@dataclass
class Resposta:
    status: int          # 0 = falha de rede/timeout
    corpo: str = ""
    retry_after: float | None = None


Get = Callable[[str], Resposta]
Post = Callable[[str, dict], Resposta]


def _http_get(url: str, timeout: float = 20) -> Resposta:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Resposta(r.status, r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return Resposta(e.code, "")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Resposta(0, str(e))


def _http_post(url: str, payload: dict, timeout: float = 30) -> Resposta:
    dados = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method="POST", headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Resposta(r.status, r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        ra = e.headers.get("Retry-After") if e.headers else None
        try:
            ra = float(ra) if ra is not None else None
        except ValueError:
            ra = None
        return Resposta(e.code, e.read().decode("utf-8", "replace") if e.fp else "", ra)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Resposta(0, str(e))


def log(msg: str) -> None:
    print(f"[indexnow] {msg}", flush=True)


# --------------------------------------------------------------------------- #
def codificar(url: str) -> str:
    """URL escapada (RFC 3986), como o protocolo exige. Idempotente."""
    return quote(url, safe=":/?=&%#")


def carregar_estado(path: Path | None) -> dict[str, str] | None:
    """{url: hash}. Aceita o formato de sitemap_lastmod.json ({url: {hash,..}})
    e o formato do estado de envio ({"urls": {url: hash}})."""
    if path is None or not path.exists() or not path.read_text(encoding="utf-8").strip():
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    if "urls" in obj and isinstance(obj["urls"], dict):
        return dict(obj["urls"])
    return {u: (v["hash"] if isinstance(v, dict) else v) for u, v in obj.items()}


@dataclass
class Plano:
    novas: list[str] = field(default_factory=list)
    alteradas: list[str] = field(default_factory=list)
    removidas: list[str] = field(default_factory=list)

    @property
    def vazio(self) -> bool:
        return not (self.novas or self.alteradas or self.removidas)


def planejar(anterior: dict[str, str], atual: dict[str, str]) -> Plano:
    no_host = lambda u: urlparse(u).netloc == HOST  # noqa: E731
    return Plano(
        novas=sorted(u for u in atual if u not in anterior and no_host(u)),
        alteradas=sorted(u for u in atual if u in anterior and anterior[u] != atual[u] and no_host(u)),
        removidas=sorted(u for u in anterior if u not in atual and no_host(u)),
    )


def chave_publicada(chave: str, get: Get) -> bool:
    r = get(f"{BASE_URL}/{chave}.txt")
    return r.status == 200 and r.corpo.strip() == chave


def verificar_publicacao(plano: Plano, atual: dict[str, str], get: Get) -> tuple[list[str], list[str]]:
    """(prontas, pendentes) conforme o que o site publicado responde agora."""
    prontas, pendentes = [], []
    for u in plano.novas + plano.alteradas:
        r = get(codificar(u))
        ok = r.status == 200 and impressao_digital_html(r.corpo) == atual[u]
        (prontas if ok else pendentes).append(u)
        if not ok:
            log(f"pendente (no ar ainda não é a versão nova, HTTP {r.status}): {u}")
    for u in plano.removidas:
        r = get(codificar(u))
        ok = r.status in (404, 410)
        (prontas if ok else pendentes).append(u)
        if not ok:
            log(f"pendente (removida mas responde HTTP {r.status}): {u}")
    return prontas, pendentes


def enviar(urls: list[str], chave: str, endpoint: str, post: Post,
           tentativas: int = 3, espera: float = 5.0, dormir: Callable[[float], None] = time.sleep
           ) -> tuple[list[str], list[dict]]:
    """Envia em lotes. Devolve (urls aceitas, registro de cada requisição)."""
    aceitas, registro = [], []
    for i in range(0, len(urls), LOTE_MAX):
        lote = urls[i:i + LOTE_MAX]
        payload = {"host": HOST, "key": chave, "keyLocation": f"{BASE_URL}/{chave}.txt",
                   "urlList": [codificar(u) for u in lote]}
        for t in range(1, tentativas + 1):
            r = post(endpoint, payload)
            registro.append({"lote": i // LOTE_MAX + 1, "tentativa": t, "urls": len(lote),
                             "status": r.status, "significado": CODIGOS.get(r.status, "falha de rede" if r.status == 0 else "inesperado")})
            log(f"lote {i // LOTE_MAX + 1} ({len(lote)} URLs), tentativa {t}: HTTP {r.status} {CODIGOS.get(r.status, '')}")
            if r.status in SUCESSO:
                aceitas += lote
                break
            if (r.status in REPETIR or r.status == 0) and t < tentativas:
                pausa = min(r.retry_after if r.retry_after else espera * (3 ** (t - 1)), 120)
                dormir(pausa)
                continue
            break
    return aceitas, registro


def ler_config() -> tuple[str, str]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return str(cfg.get("indexnow_key", "")).strip(), str(cfg.get("indexnow_endpoint", "")).strip()


def executar(anterior_path: Path | None, saida: Path | None, log_path: Path | None,
             dry_run: bool, verificar: bool, desde: str | None,
             get: Get = _http_get, post: Post = _http_post,
             tentativas_deploy: int = 6, intervalo_deploy: float = 30.0,
             dormir: Callable[[float], None] = time.sleep,
             atual_path: Path = ESTADO_ATUAL, chave: str | None = None, endpoint: str | None = None,
             commit: str = "") -> int:
    if chave is None or endpoint is None:
        c, e = ler_config()
        chave, endpoint = chave if chave is not None else c, endpoint if endpoint is not None else e
    if not chave:
        log("indexnow_key vazio em config.yml: desligado.")
        return 0
    if not CHAVE_RE.match(chave) or not endpoint.startswith("https://"):
        log("configuração inválida (chave fora do padrão ou endpoint sem https).")
        return 1

    atual = carregar_estado(atual_path) or {}
    anterior = carregar_estado(anterior_path)
    if anterior is None:
        # Primeira execução: não há o que comparar. Não envia em massa; parte
        # do estado atual. Com --desde, considera como "novas" só as URLs cujo
        # conteúdo mudou a partir dessa data (lastmod >= desde).
        bruto = json.loads(atual_path.read_text(encoding="utf-8"))
        anterior = {u: v["hash"] for u, v in bruto.items() if not (desde and v.get("lastmod", "") >= desde)}
        log(f"sem estado anterior: semeando com {len(anterior)} URLs"
            + (f"; {len(atual) - len(anterior)} com lastmod >= {desde} entram como novas" if desde else "; nada a enviar"))

    plano = planejar(anterior, atual)
    log(f"plano: {len(plano.novas)} novas, {len(plano.alteradas)} alteradas, {len(plano.removidas)} removidas")
    for rot, lst in (("nova", plano.novas), ("alterada", plano.alteradas), ("removida", plano.removidas)):
        for u in lst[:50]:
            log(f"  {rot}: {u}")

    novo_estado = dict(anterior)
    registro: list[dict] = []
    aceitas: list[str] = []
    pendentes: list[str] = []

    if not plano.vazio:
        prontas = plano.novas + plano.alteradas + plano.removidas
        if verificar:
            chave_ok = False
            for t in range(1, tentativas_deploy + 1):
                if chave_publicada(chave, get):
                    chave_ok = True
                    break
                if t < tentativas_deploy:
                    dormir(intervalo_deploy)
            if not chave_ok:
                log("arquivo de chave não está publicado com o conteúdo esperado: nada enviado.")
                pendentes = prontas
                prontas = []
            else:
                for t in range(1, tentativas_deploy + 1):
                    prontas, pendentes = verificar_publicacao(plano, atual, get)
                    if not pendentes or t == tentativas_deploy:
                        break
                    log(f"{len(pendentes)} pendente(s); nova verificação em {intervalo_deploy:.0f}s ({t}/{tentativas_deploy})")
                    dormir(intervalo_deploy)
        if dry_run:
            log(f"DRY-RUN: enviaria {len(prontas)} URL(s) para {endpoint}; nada foi enviado.")
            for u in prontas[:50]:
                log(f"  enviaria: {codificar(u)}")
            return 0
        if prontas:
            aceitas, registro = enviar(prontas, chave, endpoint, post, dormir=dormir)
        for u in aceitas:
            if u in atual:
                novo_estado[u] = atual[u]
            else:
                novo_estado.pop(u, None)

    recusa = [r for r in registro if r["status"] in (400, 403, 422)]
    if saida:
        saida.write_text(json.dumps({"urls": novo_estado}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    entrada = {
        "quando": datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec="seconds"),
        "commit": commit, "endpoint": endpoint,
        "novas": len(plano.novas), "alteradas": len(plano.alteradas), "removidas": len(plano.removidas),
        "enviadas_aceitas": len(aceitas), "pendentes": len(pendentes), "requisicoes": registro,
        "urls_aceitas": aceitas[:200],
    }
    if log_path and not plano.vazio:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    log(f"resultado: {len(aceitas)} aceitas, {len(pendentes)} pendentes"
        + (f", {len(recusa)} recusa(s) do buscador" if recusa else ""))
    return 1 if recusa else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Notifica via IndexNow só as URLs alteradas.")
    ap.add_argument("--anterior", type=Path, help="estado do último envio (ausente/vazio = primeira execução)")
    ap.add_argument("--atual", type=Path, default=ESTADO_ATUAL)
    ap.add_argument("--saida", type=Path, help="onde gravar o novo estado de envio")
    ap.add_argument("--log", type=Path, help="arquivo JSONL que recebe uma linha por execução com envio")
    ap.add_argument("--dry-run", action="store_true", help="planeja (e verifica, se permitido) sem enviar")
    ap.add_argument("--sem-verificar", action="store_true", help="não acessa o site (só com --dry-run)")
    ap.add_argument("--desde", help="primeira execução: trata como novas as URLs com lastmod >= AAAA-MM-DD")
    ap.add_argument("--commit", default="")
    ap.add_argument("--tentativas-deploy", type=int, default=6)
    ap.add_argument("--intervalo-deploy", type=float, default=30.0)
    a = ap.parse_args(argv)
    if a.sem_verificar and not a.dry_run:
        ap.error("--sem-verificar só é permitido com --dry-run (nunca enviar sem confirmar o deploy)")
    if a.desde and not re.match(r"^\d{4}-\d{2}-\d{2}$", a.desde):
        ap.error("--desde no formato AAAA-MM-DD")
    return executar(a.anterior, a.saida, a.log, a.dry_run, not a.sem_verificar, a.desde,
                    tentativas_deploy=a.tentativas_deploy, intervalo_deploy=a.intervalo_deploy,
                    atual_path=a.atual, commit=a.commit)


if __name__ == "__main__":
    sys.exit(main())
