"""
adsense.py — Google AdSense: ads.txt sempre; anúncios só quando autorizados.

Fonte única: o bloco `adsense` de config.yml.

Sempre:
  - valida o identificador (`ca-pub-` + 16 dígitos) e a linha do ads.txt
    fornecida pelo AdSense (mesmo pub, DIRECT, id de certificação do Google);
  - escreve docs/ads.txt (publicado na raiz do domínio pelo GitHub Pages).

Com `ativo: true` E `consentimento_configurado: true`, em cada página que tem
espaços marcados `<!-- anuncio:NOME:inicio -->…<!-- anuncio:NOME:fim -->`:
  - preenche os espaços que têm id em `slots`, com rótulo "Publicidade" e
    altura reservada (sem deslocar o layout);
  - insere no <head> um carregador inline que cria o script do AdSense e o
    do GoatCounter;
  - troca a CSP da página pela CSP estrita aceita pelo AdSense (hash +
    'strict-dynamic'), guardando a original para poder voltar.

Com `ativo: false` (padrão) ou sem consentimento configurado: remove todo
código de anúncio e restaura a CSP e o GoatCounter originais. Nunca falha o
workflow: se a ativação estiver incompleta, avisa e fica desligado.

    python scripts/adsense.py              # aplica conforme config.yml
    python scripts/adsense.py --conferir   # só verifica (CI/testes)

Ordem no workflow: depois de sync_nav.py, antes de csp_hashes.py.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from csp_hashes import RE_META_CSP, hashes_inline  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yml"
DOCS = ROOT / "docs"

RE_CLIENT = re.compile(r"^ca-pub-(\d{16})$")
RE_ADSTXT = re.compile(r"^google\.com, pub-(\d{16}), DIRECT, f08c47fec0942fa0$")
RE_SLOT = re.compile(r"^\d{6,20}$")
ESPACOS = ("inicio", "reajuste-hub", "reajuste-mes", "correcao-hub", "correcao-indice", "comparador", "simulador")

RE_ESPACO = re.compile(r"(<!-- anuncio:([a-z-]+):inicio -->)(.*?)(<!-- anuncio:\2:fim -->)", re.S)
RE_BLOCO_HEAD = re.compile(r"\n?<!-- adsense:inicio -->.*?<!-- adsense:fim -->", re.S)
RE_ORIGINAL = re.compile(r'<!-- adsense:original csp="([A-Za-z0-9+/=]*)" gc="([A-Za-z0-9+/=]*)" -->')
MARCA_GC = "<!-- adsense:gc -->"
# Com 'strict-dynamic', <script src> de mesma origem sem hash deixa de rodar.
# Ao ligar, cada um vira um carregador inline (com hash na CSP), e ao desligar
# volta a ser a tag original.
RE_EXTERNO = re.compile(r'<script src="((?!https?:|//)[^"<>]+)" defer></script>')
RE_CARREGADOR = re.compile(r'<!-- adsense:externo src="([A-Za-z0-9+/=]*)" --><script>.*?</script>', re.S)


def carregador(src: str) -> str:
    return (f'<!-- adsense:externo src="{b64(src)}" --><script>(function(){{var e=document.createElement("script");'
            f'e.src={json.dumps(src)};e.async=false;document.head.appendChild(e);}})();</script>')
RE_GOAT = re.compile(r'[ \t]*<script data-goatcounter="([^"]+)"\s+async src="https://gc\.zgo\.at/count\.js"></script>\n?')


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def de64(s: str) -> str:
    return base64.b64decode(s.encode("ascii")).decode("utf-8")


def carregar(config: Path = CONFIG) -> dict:
    cfg = (yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("adsense") or {}
    client = str(cfg.get("client", "")).strip()
    ads_txt = str(cfg.get("ads_txt", "")).strip()
    m1, m2 = RE_CLIENT.match(client), RE_ADSTXT.match(ads_txt)
    if not m1:
        raise SystemExit(f"adsense.client inválido: {client!r} (esperado ca-pub- + 16 dígitos)")
    if not m2 or m2.group(1) != m1.group(1):
        raise SystemExit("adsense.ads_txt inválido ou com pub diferente do client")
    slots = {str(k): str(v) for k, v in (cfg.get("slots") or {}).items()}
    for nome, sid in slots.items():
        if nome not in ESPACOS or not RE_SLOT.match(sid):
            raise SystemExit(f"adsense.slots: espaço {nome!r} ou id {sid!r} inválido")
    return {"client": client, "ads_txt": ads_txt, "slots": slots,
            "ativo": bool(cfg.get("ativo")), "consentimento": bool(cfg.get("consentimento_configurado"))}


def pode_veicular(c: dict, docs: Path = DOCS) -> tuple[bool, str]:
    if not c["ativo"]:
        return False, "desligado (ativo: false)"
    if not c["consentimento"]:
        return False, "ativo: true, mas consentimento_configurado: false — anúncios NÃO inseridos"
    if not (docs / "privacidade" / "index.html").is_file():
        return False, "sem docs/privacidade/ — anúncios NÃO inseridos"
    if not c["slots"]:
        return False, "nenhum id em slots — anúncios NÃO inseridos"
    return True, "ligado"


def bloco_espaco(c: dict, nome: str) -> str:
    sid = c["slots"].get(nome)
    if not sid:
        return ""
    return (
        '<aside class="pub" aria-label="Publicidade" style="margin:1.6rem 0;padding-top:.6rem;'
        'border-top:1px solid rgba(233,230,220,.14);min-height:300px">'
        '<p style="margin:0 0 .4rem;font-family:\'IBM Plex Mono\',monospace;font-size:.62rem;'
        'letter-spacing:.14em;text-transform:uppercase;color:rgba(233,230,220,.55)">Publicidade</p>'
        f'<ins class="adsbygoogle" style="display:block;min-height:250px" data-ad-client="{c["client"]}" '
        f'data-ad-slot="{sid}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
        "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script></aside>"
    )


def bloco_head(c: dict, csp_original: str, goat_original: str, goat_url: str) -> str:
    goat = (f"s('https://gc.zgo.at/count.js',{{'data-goatcounter':'{goat_url}'}});" if goat_url else "")
    return (
        "\n<!-- adsense:inicio -->\n"
        f'<!-- adsense:original csp="{b64(csp_original)}" gc="{b64(goat_original)}" -->\n'
        "<script>(function(){function s(u,a){var e=document.createElement('script');e.async=true;e.src=u;"
        "for(var k in a){e.setAttribute(k,a[k]);}document.head.appendChild(e);}"
        f"s('https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={c['client']}',"
        "{crossorigin:'anonymous'});" + goat + "})();</script>\n"
        "<!-- adsense:fim -->"
    )


def csp_estrita(original: str, hashes: list[str]) -> str:
    """CSP estrita no formato documentado pelo AdSense (hash no lugar de nonce)."""
    novas, vistos = [], set()
    for d in (x.strip() for x in original.split(";") if x.strip()):
        nome = d.split()[0]
        vistos.add(nome)
        if nome == "script-src":
            d = " ".join(["script-src"] + hashes + ["'strict-dynamic'", "'unsafe-inline'", "'unsafe-eval'", "https:", "http:"])
        elif nome in ("img-src", "connect-src", "frame-src") and "https:" not in d.split():
            d += " https:"
        novas.append(d)
    if "frame-src" not in vistos:
        novas.append("frame-src 'self' https:")
    return "; ".join(novas)


def desligar(html: str) -> str:
    html = RE_ESPACO.sub(lambda m: m.group(1) + m.group(4), html)
    html = RE_CARREGADOR.sub(lambda m: f'<script src="{de64(m.group(1))}" defer></script>', html)
    m = RE_ORIGINAL.search(html)
    if m:
        csp, goat = de64(m.group(1)), de64(m.group(2))
        html = RE_BLOCO_HEAD.sub("", html)
        html = RE_META_CSP.sub(lambda x: x.group(1) + csp + x.group(3), html, count=1)
        html = html.replace(MARCA_GC, goat, 1)
    return html


def ligar(html: str, c: dict) -> str:
    html = desligar(html)
    if not RE_ESPACO.search(html):
        return html
    html = RE_ESPACO.sub(lambda m: m.group(1) + bloco_espaco(c, m.group(2)) + m.group(4), html)
    if "adsbygoogle" not in html:
        return html                                     # página sem espaço com id
    csp_m = RE_META_CSP.search(html)
    if not csp_m:
        raise SystemExit("página com espaço de anúncio sem meta CSP")
    g = RE_GOAT.search(html)
    goat_original, goat_url = (g.group(0), g.group(1)) if g else ("", "")
    if g:
        html = html[:g.start()] + MARCA_GC + html[g.end():]
    html = html.replace("</head>", bloco_head(c, csp_m.group(2), goat_original, goat_url) + "</head>", 1)
    html = RE_EXTERNO.sub(lambda m: carregador(m.group(1)), html)
    if re.search(r"\son[a-z]+=\"", html):
        raise SystemExit("página com handler inline (on*=): incompatível com CSP por hash")
    hashes = hashes_inline(html)
    csp_m = RE_META_CSP.search(html)
    return html[:csp_m.start()] + csp_m.group(1) + csp_estrita(csp_m.group(2), hashes) + csp_m.group(3) + html[csp_m.end():]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--docs", type=Path, default=DOCS)
    a = ap.parse_args(argv)
    docs = a.docs
    c = carregar(a.config)
    ok, motivo = pode_veicular(c, docs)
    if c["ativo"] and not ok:
        print(f"::warning::AdSense: {motivo}")

    pendentes = []
    ads = docs / "ads.txt"
    if not ads.exists() or ads.read_text(encoding="utf-8") != c["ads_txt"] + "\n":
        pendentes.append("ads.txt")
        if not a.conferir:
            ads.write_text(c["ads_txt"] + "\n", encoding="utf-8")

    mudadas = 0
    for f in sorted(docs.rglob("*.html")):
        html = f.read_text(encoding="utf-8")
        if "<!-- anuncio:" not in html and "<!-- adsense:" not in html:
            continue
        novo = ligar(html, c) if ok else desligar(html)
        if novo != html:
            mudadas += 1
            pendentes.append(f.relative_to(docs).as_posix())
            if not a.conferir:
                f.write_text(novo, encoding="utf-8")
    print(f"AdSense: {motivo}; ads.txt em dia; {mudadas} página(s) {'fora do estado' if a.conferir else 'atualizada(s)'}.")
    if a.conferir and pendentes:
        print("pendente: " + ", ".join(pendentes[:10]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
