"""
csp_hashes.py — Troca 'unsafe-inline' por hashes sha256 no script-src da CSP.

Para cada página em PAGINAS, o script:

  1. enumera os blocos <script> inline (sem src=), ignorando os
     type="application/ld+json" (não são executáveis, CSP não os cobre);
  2. calcula o sha256 (base64) do conteúdo EXATO de cada bloco — o mesmo
     cálculo que o navegador faz;
  3. reescreve a diretiva script-src da <meta http-equiv=CSP>: remove
     'unsafe-inline' e quaisquer 'sha256-...' antigos, e insere os novos.

Com hash presente, o navegador passa a executar SÓ os blocos listados: um
<script> injetado por XSS deixa de rodar mesmo que algum esc() falhe. Rode
SEMPRE depois de qualquer gerador que reescreva estas páginas (no workflow,
depois de render_index.py e sync_nav.py). Idempotente, só stdlib.

Escopo atual: index.html e embed.html (páginas de maior tráfego, sem handlers
inline). Para ampliar, basta acrescentar em PAGINAS — mas a página não pode
ter atributos on*= (hash não cobre event handlers) nem javascript: em href.

    python scripts/csp_hashes.py            # aplica
    python scripts/csp_hashes.py --conferir # só reporta, não escreve (CI)
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PAGINAS = ["index.html", "embed.html"]

RE_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
RE_META_CSP = re.compile(
    r'(<meta\s+http-equiv="Content-Security-Policy"\s+content=")([^"]*)(")',
    re.I,
)


def hashes_inline(html: str) -> list[str]:
    """sha256 (base64) de cada <script> inline executável, na ordem."""
    out = []
    for attrs, corpo in RE_SCRIPT.findall(html):
        if re.search(r"\bsrc\s*=", attrs, re.I):
            continue                      # externo: coberto por host na CSP
        m = re.search(r'\btype\s*=\s*"([^"]*)"', attrs, re.I)
        if m and m.group(1).strip().lower() not in ("", "text/javascript", "module"):
            continue                      # ld+json e afins: não executáveis
        digest = hashlib.sha256(corpo.encode("utf-8")).digest()
        out.append("'sha256-" + base64.b64encode(digest).decode("ascii") + "'")
    return out


def reescreve_csp(html: str, hashes: list[str], rel: str) -> str:
    m = RE_META_CSP.search(html)
    if not m:
        raise SystemExit(f"{rel}: meta de CSP não encontrada")

    diretivas = [d.strip() for d in m.group(2).split(";") if d.strip()]
    novas = []
    achou = False
    for d in diretivas:
        nome, *fontes = d.split()
        if nome != "script-src":
            novas.append(d)
            continue
        achou = True
        mantidas = [f for f in fontes
                    if f != "'unsafe-inline'" and not f.startswith("'sha256-")]
        novas.append(" ".join([nome] + mantidas + hashes))
    if not achou:
        raise SystemExit(f"{rel}: CSP sem diretiva script-src")

    return html[:m.start()] + m.group(1) + "; ".join(novas) + m.group(3) + html[m.end():]


def main() -> None:
    conferir = "--conferir" in sys.argv
    pendentes = []
    for rel in PAGINAS:
        caminho = DOCS / rel
        html = caminho.read_text(encoding="utf-8")
        hs = hashes_inline(html)
        novo = reescreve_csp(html, hs, rel)
        if novo == html:
            print(f"[ok] {rel}: CSP em dia ({len(hs)} script(s) inline).")
            continue
        if conferir:
            pendentes.append(rel)
        else:
            caminho.write_text(novo, encoding="utf-8")
            print(f"[atualizada] {rel}: {len(hs)} hash(es) na script-src.")
    if pendentes:
        print(f"CSP desatualizada em: {', '.join(pendentes)}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
