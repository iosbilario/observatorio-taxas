#!/usr/bin/env python3
"""Replica o header de navegação em todas as páginas de docs/.

O bloco canônico é `partials/nav.html`, na raiz do repositório — fora de
docs/ de propósito, porque docs/ é o que o GitHub Pages serve.

O header é HTML estático dentro de cada página, nunca injetado por
JavaScript: crawler de LLM em geral não executa JS, e ser legível por
máquina é estratégia central deste site.

Por página, o script ajusta:
  - o prefixo relativo dos links ("", "../", "../../"), conforme a
    profundidade, para funcionar no Pages e também via file://;
  - o item ativo, via aria-current="page";
  - a classe `tema-radar` no <body> das páginas do Radar;
  - o <link> para nav.css, inserido antes de </head> se faltar.

É idempotente: rodar duas vezes não muda nada. Rode sempre depois dos
geradores (build_pages.py, build_correcao.py), que reescrevem as páginas
de reajuste e correção do zero.

    python scripts/sync_nav.py            # aplica
    python scripts/sync_nav.py --conferir # só reporta, não escreve (CI)

PÁGINA NOVA: basta ter os marcadores `nav:start` e `nav:end` no corpo, ou
nenhum — o script insere sozinho, depois do skip link. Depois é só rodar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
PARTIAL = RAIZ / "partials" / "nav.html"

INICIO = "<!-- nav:start -->"
FIM = "<!-- nav:end -->"
NOTA = ("<!-- Header replicado de partials/nav.html por scripts/sync_nav.py. "
        "Não edite aqui: edite o partial e rode o script. -->")

# Ficam de fora, e por motivo — não por esquecimento.
IGNORADAS = {
    "embed.html":
        "payload de iframe; o header vazaria para o site de terceiros",
    "admin/index.html":
        "painel interno (Disallow no robots) e sem landmark #conteudo",
}


def chave_ativa(rel: str) -> str | None:
    """Qual item do menu representa esta página. None = nenhum."""
    if rel == "index.html":
        return "painel"
    if rel == "rebobinar.html":
        return "rebobinador"
    if rel == "var.html":
        return "var"
    if rel == "retransmissora.html":
        return "embeds"
    if rel.startswith("reajuste/"):
        return "reajuste"
    # correcao/** e radar/**: sem item próprio no menu. Correção é alcançada
    # de dentro do hub de Reajuste; o Radar saiu do menu enquanto o coletor
    # não está no ar. Sem item, sem aria-current — mentir seria pior.
    return None


def corpo_do_partial() -> str:
    bruto = PARTIAL.read_text(encoding="utf-8")
    # O comentário de cabeçalho do partial explica o processo para quem edita
    # o repositório; não precisa viajar para dentro de 528 páginas.
    sem_comentario = re.sub(r"^\s*<!--.*?-->\s*", "", bruto, count=1, flags=re.S)
    return sem_comentario.strip()


def bloco(corpo: str, prefixo: str, ativo: str | None) -> str:
    html = corpo.replace("{{P}}", prefixo)
    if ativo:
        alvo = f'data-nav="{ativo}"'
        if alvo not in html:
            raise SystemExit(f"item '{ativo}' não existe no partial")
        html = html.replace(alvo, f'{alvo} aria-current="page"', 1)
    return f"{INICIO}\n{NOTA}\n{html}\n{FIM}"


def garante_marcadores(html: str, rel: str) -> str:
    """Cria o par de marcadores na primeira vez, no lugar certo da página."""
    if INICIO in html and FIM in html:
        return html

    vazio = f"{INICIO}\n{FIM}"

    # 1. Páginas que já tinham uma barra de topo própria: o header global
    #    toma o lugar dela. Deixar as duas seria navegação em dobro.
    for classe in ("top", "topo"):
        padrao = re.compile(
            rf'[ \t]*<header class="{classe}">.*?</header>\n?', re.S)
        if padrao.search(html):
            return padrao.sub(vazio + "\n", html, count=1)

    # 2. Logo depois do skip link, que permanece o primeiro focável.
    skip = re.compile(r'(<a class="(?:skip-link|pular)"[^>]*>.*?</a>)', re.S)
    if skip.search(html):
        return skip.sub(r"\1\n" + vazio, html, count=1)

    # 3. Último recurso: abertura do <body>.
    corpo = re.compile(r"(<body[^>]*>)")
    if corpo.search(html):
        return corpo.sub(r"\1\n" + vazio, html, count=1)

    raise SystemExit(f"não achei onde colocar o nav em {rel}")


def garante_css(html: str, prefixo: str) -> str:
    if "nav.css" in html:
        return html
    link = f'  <link rel="stylesheet" href="{prefixo}nav.css" />\n'
    if "</head>" not in html:
        raise SystemExit("página sem </head>")
    return html.replace("</head>", link + "</head>", 1)


def garante_tema(html: str, rel: str) -> str:
    """Páginas do Radar carregam a paleta do Radar no mesmo header."""
    if not rel.startswith("radar/"):
        return html
    m = re.search(r"<body([^>]*)>", html)
    if not m:
        raise SystemExit(f"{rel} sem <body>")
    atributos = m.group(1)
    if "tema-radar" in atributos:
        return html
    if 'class="' in atributos:
        novo = atributos.replace('class="', 'class="tema-radar ', 1)
    else:
        novo = atributos + ' class="tema-radar"'
    return html[:m.start()] + f"<body{novo}>" + html[m.end():]


def sincroniza(caminho: Path, corpo: str) -> bool:
    rel = caminho.relative_to(DOCS).as_posix()
    original = caminho.read_text(encoding="utf-8")

    prefixo = "../" * rel.count("/")
    html = garante_marcadores(original, rel)
    html = garante_tema(html, rel)
    html = garante_css(html, prefixo)

    novo_bloco = bloco(corpo, prefixo, chave_ativa(rel))
    html = re.sub(
        re.escape(INICIO) + r".*?" + re.escape(FIM),
        lambda _: novo_bloco,          # lambda: o bloco tem \1, \g e afins
        html,
        count=1,
        flags=re.S,
    )

    if html == original:
        return False
    caminho.write_text(html, encoding="utf-8")
    return True


def main() -> None:
    conferir = "--conferir" in sys.argv
    corpo = corpo_do_partial()

    alvos, puladas = [], []
    for caminho in sorted(DOCS.rglob("*.html")):
        rel = caminho.relative_to(DOCS).as_posix()
        if rel in IGNORADAS:
            puladas.append(rel)
        else:
            alvos.append(caminho)

    if conferir:
        pendentes = []
        for caminho in alvos:
            antes = caminho.read_text(encoding="utf-8")
            if sincroniza(caminho, corpo):
                caminho.write_text(antes, encoding="utf-8")
                pendentes.append(caminho.relative_to(DOCS).as_posix())
        if pendentes:
            print(f"nav desatualizado em {len(pendentes)} página(s):")
            for p in pendentes[:10]:
                print("  -", p)
            raise SystemExit(1)
        print(f"nav em dia nas {len(alvos)} páginas.")
        return

    mudadas = sum(sincroniza(caminho, corpo) for caminho in alvos)
    sem_item = sum(1 for c in alvos
                   if chave_ativa(c.relative_to(DOCS).as_posix()) is None)

    print(f"nav sincronizado: {mudadas} página(s) alterada(s) de {len(alvos)}.")
    print(f"sem item ativo (esperado): {sem_item} página(s) em correcao/.")
    for rel in puladas:
        print(f"pulada: {rel} — {IGNORADAS[rel]}")


if __name__ == "__main__":
    main()
