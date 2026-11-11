"""
seo_audit.py — Auditoria do HTML ESTÁTICO servido em docs/ (o que um robô sem
JavaScript recebe).

Lê cada .html de docs/ como texto cru, ignora o conteúdo de <script>/<style>
(robô sem JS não executa nem lê como texto) e extrai: título, descrição,
robots, canonical, H1, Open Graph, tipos JSON-LD, links <a href> internos e o
texto visível. A partir disso relata:

  - páginas indexáveis sem canonical, com canonical fora do domínio ou
    apontando para outra URL;
  - títulos e descrições duplicados;
  - páginas sem H1 (ou com mais de um) no HTML inicial;
  - links internos quebrados (alvo inexistente em docs/);
  - links internos para variantes não canônicas (/index.html);
  - URLs do sitemap sem arquivo, não canônicas ou noindex;
  - páginas indexáveis fora do sitemap e páginas sem link interno (órfãs).

Só stdlib, sem rede. Usado por tests/test_organic_discovery.py e para gerar a
linha de base de organic-discovery/BASELINE.md:

    python scripts/seo_audit.py                 # resumo do docs/ atual
    python scripts/seo_audit.py --docs <dir>    # outro diretório (ex.: snapshot)
    python scripts/seo_audit.py --json          # relatório completo em JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
BASE_URL = "https://observatoriodetaxas.tec.br"
HOST = urlparse(BASE_URL).netloc

# Fora da auditoria de indexação: não são páginas públicas de conteúdo.
NAO_PUBLICAS_PREFIXOS = ("admin/", "security-audit/")


class _Pagina(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.canonicals: list[str] = []
        self.h1: list[str] = []
        self.links: list[str] = []
        self.jsonld: list[str] = []
        self.texto: list[str] = []
        self._pilha_skip = 0
        self._em_title = False
        self._em_h1 = 0
        self._h1_buf: list[str] = []
        self._em_jsonld = False
        self._jsonld_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self._em_jsonld = True
                self._jsonld_buf = []
            self._pilha_skip += 1
            return
        if tag in ("style", "template"):
            self._pilha_skip += 1
            return
        if self._pilha_skip:
            return
        if tag == "title":
            self._em_title = True
        elif tag == "meta":
            chave = a.get("name") or a.get("property")
            if chave:
                self.meta[chave.lower()] = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").split():
            self.canonicals.append(a.get("href", ""))
        elif tag == "h1":
            self._em_h1 += 1
            self._h1_buf = []
        elif tag == "a" and "href" in a:
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "script":
            if self._em_jsonld:
                self.jsonld.append("".join(self._jsonld_buf))
                self._em_jsonld = False
            self._pilha_skip = max(0, self._pilha_skip - 1)
            return
        if tag in ("style", "template"):
            self._pilha_skip = max(0, self._pilha_skip - 1)
            return
        if self._pilha_skip:
            return
        if tag == "title":
            self._em_title = False
        elif tag == "h1" and self._em_h1:
            self._em_h1 -= 1
            self.h1.append(" ".join("".join(self._h1_buf).split()))

    def handle_data(self, data):
        if self._em_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._pilha_skip:
            return
        if self._em_title:
            self.title += data
        if self._em_h1:
            self._h1_buf.append(data)
        self.texto.append(data)


def url_de(rel: str) -> str:
    """URL pública canônica esperada para um arquivo relativo a docs/."""
    if rel == "index.html":
        return f"{BASE_URL}/"
    if rel.endswith("/index.html"):
        return f"{BASE_URL}/{rel[: -len('index.html')]}"
    return f"{BASE_URL}/{rel}"


def arquivo_de(url: str, docs: Path) -> Path | None:
    """Arquivo em docs/ que o GitHub Pages serviria para a URL (ou None)."""
    caminho = urlparse(url).path.lstrip("/")
    cands = []
    if caminho == "" or caminho.endswith("/"):
        cands.append(caminho + "index.html")
    else:
        cands += [caminho, caminho + ".html", caminho + "/index.html"]
    for c in cands:
        p = docs / c
        if p.is_file():
            return p
    return None


def analisar_pagina(path: Path, docs: Path) -> dict:
    rel = path.relative_to(docs).as_posix()
    p = _Pagina()
    p.feed(path.read_text(encoding="utf-8"))
    robots = p.meta.get("robots", "").lower()
    tipos: list[str] = []
    erros_jsonld: list[str] = []
    for bloco in p.jsonld:
        try:
            obj = json.loads(bloco)
        except json.JSONDecodeError as e:
            erros_jsonld.append(str(e))
            continue
        itens = obj.get("@graph", [obj]) if isinstance(obj, dict) else obj
        for it in itens:
            t = it.get("@type") if isinstance(it, dict) else None
            if t:
                tipos += t if isinstance(t, list) else [t]
    return {
        "rel": rel,
        "url": url_de(rel),
        "title": " ".join(p.title.split()),
        "description": p.meta.get("description", ""),
        "robots": robots,
        "indexavel": "noindex" not in robots and not rel.startswith(NAO_PUBLICAS_PREFIXOS),
        "canonicals": p.canonicals,
        "h1": p.h1,
        "og_image": p.meta.get("og:image", ""),
        "og_url": p.meta.get("og:url", ""),
        "jsonld_tipos": tipos,
        "jsonld_brutos": p.jsonld,
        "jsonld_erros": erros_jsonld,
        "links": p.links,
        "texto": " ".join(" ".join(p.texto).split()),
    }


def carregar(docs: Path) -> dict[str, dict]:
    return {
        pg["rel"]: pg
        for pg in (analisar_pagina(f, docs) for f in sorted(docs.rglob("*.html")))
    }


def links_internos(pg: dict) -> list[str]:
    """Links <a href> do próprio domínio, resolvidos para URL absoluta."""
    out = []
    for href in pg["links"]:
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        absoluto, _ = urldefrag(urljoin(pg["url"], href))
        alvo = urlparse(absoluto)
        if alvo.scheme in ("http", "https") and alvo.netloc == HOST:
            out.append(absoluto.split("?", 1)[0])
    return out


def sitemap_urls(docs: Path) -> list[dict]:
    sm = docs / "sitemap.xml"
    if not sm.exists():
        return []
    xml = sm.read_text(encoding="utf-8")
    return [
        {"loc": unquote(loc), "loc_bruto": loc, "lastmod": (re.search(r"<lastmod>(.*?)</lastmod>", blk) or [None, None])[1]}
        for blk in re.findall(r"<url>(.*?)</url>", xml, re.S)
        for loc in re.findall(r"<loc>(.*?)</loc>", blk)
    ]


def auditar(docs: Path) -> dict:
    paginas = carregar(docs)
    idx = {k: v for k, v in paginas.items() if v["indexavel"]}
    achados: dict[str, list] = defaultdict(list)

    for rel, pg in idx.items():
        if len(pg["canonicals"]) != 1:
            achados["canonical_ausente_ou_multiplo"].append(rel)
        else:
            c = pg["canonicals"][0]
            if urlparse(c).netloc != HOST:
                achados["canonical_outro_dominio"].append(f"{rel} -> {c}")
            elif c != pg["url"]:
                achados["canonical_diferente_da_url"].append(f"{rel} -> {c}")
        if pg["og_url"] and urlparse(pg["og_url"]).netloc != HOST:
            achados["og_url_outro_dominio"].append(f"{rel} -> {pg['og_url']}")
        if len(pg["h1"]) != 1:
            achados["h1_ausente_ou_multiplo_no_html_inicial"].append(f"{rel} ({len(pg['h1'])})")
        if not pg["description"]:
            achados["sem_meta_description"].append(rel)
        if pg["jsonld_erros"]:
            achados["jsonld_invalido"].append(rel)

    for campo, nome in (("title", "titulo_duplicado"), ("description", "descricao_duplicada")):
        cont = Counter(pg[campo] for pg in idx.values() if pg[campo])
        for valor, n in cont.items():
            if n > 1:
                achados[nome].append(f"{n}x {valor[:90]}")

    recebe_link: Counter = Counter()
    for rel, pg in paginas.items():
        for alvo in links_internos(pg):
            if alvo.endswith("/index.html") or alvo == f"{BASE_URL}/index.html":
                achados["link_interno_para_index_html"].append(rel)
            if arquivo_de(alvo, docs) is None and not alvo.endswith((".json", ".txt", ".xml", ".png", ".pdf")):
                achados["link_interno_quebrado"].append(f"{rel} -> {alvo}")
            arq = arquivo_de(alvo, docs)
            if arq is not None:
                recebe_link[arq.relative_to(docs).as_posix()] += 1

    sm = sitemap_urls(docs)
    locs = [u["loc"] for u in sm]
    for u in locs:
        arq = arquivo_de(u, docs)
        if arq is None:
            achados["sitemap_url_sem_arquivo"].append(u)
            continue
        pg = paginas.get(arq.relative_to(docs).as_posix())
        if pg and not pg["indexavel"]:
            achados["sitemap_url_noindex"].append(u)
        if pg and pg["canonicals"] and pg["canonicals"][0] != u:
            achados["sitemap_url_nao_canonica"].append(u)
    for u, n in Counter(locs).items():
        if n > 1:
            achados["sitemap_url_duplicada"].append(u)
    lastmods = Counter(u["lastmod"] for u in sm)
    no_sitemap = set(locs)
    for rel, pg in idx.items():
        if pg["url"] not in no_sitemap:
            achados["indexavel_fora_do_sitemap"].append(rel)
        if recebe_link[rel] == 0 and rel != "index.html":
            achados["orfa_sem_link_interno"].append(rel)

    # link_interno_para_index_html: agrupa por página (uma linha por página).
    achados["link_interno_para_index_html"] = sorted(set(achados["link_interno_para_index_html"]))

    return {
        "docs": str(docs),
        "paginas_html": len(paginas),
        "paginas_indexaveis": len(idx),
        "sitemap_urls": len(locs),
        "sitemap_lastmod_distintos": len(lastmods),
        "sitemap_lastmod_mais_comum": lastmods.most_common(1)[0] if lastmods else None,
        "jsonld_tipos": dict(Counter(t for pg in idx.values() for t in pg["jsonld_tipos"])),
        "sem_og_image": sum(1 for pg in idx.values() if not pg["og_image"]),
        "achados": {k: v for k, v in sorted(achados.items()) if v},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--docs", type=Path, default=DOCS_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rel = auditar(args.docs.resolve())
    if args.json:
        print(json.dumps(rel, ensure_ascii=False, indent=2))
        return 0
    for k in ("paginas_html", "paginas_indexaveis", "sitemap_urls",
              "sitemap_lastmod_distintos", "sitemap_lastmod_mais_comum", "jsonld_tipos", "sem_og_image"):
        print(f"{k}: {rel[k]}")
    for nome, itens in rel["achados"].items():
        print(f"\n[{nome}] {len(itens)}")
        for i in itens[:6]:
            print(f"  - {i}")
        if len(itens) > 6:
            print(f"  ... +{len(itens) - 6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
