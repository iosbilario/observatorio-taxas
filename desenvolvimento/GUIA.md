# Guia do desenvolvedor

Detalhes operacionais do Observatório de Taxas. A visão geral está no
[README](../README.md); auditoria e regras de SEO, em
[`organic-discovery/`](../organic-discovery/).

## Sumário

- [Arquivos gerados em `data/`](#arquivos-gerados-em-data)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pipeline de geração](#pipeline-de-geração)
- [Navegação do site](#navegação-do-site)
- [Configuração das séries](#configuração-das-séries)
- [Página inicial](#página-inicial)
- [SEO, sitemap e IndexNow](#seo-sitemap-e-indexnow)
- [CHANGELOG e resumo opcional por IA](#changelog-e-resumo-opcional-por-ia)
- [Página de apoio (Pix)](#página-de-apoio-pix)
- [Publicação no GitHub Pages](#publicação-no-github-pages)
- [Google AdSense](ADSENSE.md) (documento à parte)
- [Reprodução de uma versão](REPRODUCAO.md) (documento à parte)
- [Zenodo e DOI](../organic-discovery/ZENODO.md) (documento à parte)

## Arquivos gerados em `data/`

A cada coleta, `scripts/fetch.py` produz (chaves ordenadas, UTF-8, indentado,
para `git diff` limpo):

| Arquivo | Conteúdo |
| --- | --- |
| `data/<codigo>.json` | Último ponto bruto da série (`data`, `valor`, `codigo`, `nome`). |
| `data/<codigo>_history.json` | Série temporal acumulada: lista de `{data, valor}` por data de referência do SGS, ordenada. Fundida por data (sem duplicar) a cada coleta. |
| `data/series.json` | Manifesto (`codigo`, `nome`, `grupo`, `valor_atual`, `data_referencia`, `ultima_mudanca`, `pontos`) consumido pelas páginas. |
| `data/meta.json` | Instante da última coleta com mudança (`gerado_em_fmt`, ex.: `15/06/2026 às 15:06`), em horário de Brasília. Gravado só quando há mudança de dados, para o job ser idempotente. |
| `data/stats.json` | Estatísticas de acesso do GoatCounter (`scripts/fetch_stats.py`, só com o secret `GOATCOUNTER_TOKEN`). |
| `data/sitemap_lastmod.json` | Impressão digital do conteúdo de cada URL e data da última mudança (mantido por `scripts/render_index.py`). |
| `CHANGELOG.md` | Uma linha por mudança detectada: `[timestamp] <nome>: <antigo> -> <novo>`, seguida de uma frase-resumo em PT-BR. |

Os arquivos que o site lê (`series.json`, `meta.json`, `stats.json` e cada
`<codigo>_history.json`) são espelhados em `docs/data/`, porque o GitHub Pages
servindo `/docs` só publica o que está dentro de `docs/`. O armazenamento
canônico continua sendo `data/` na raiz.

## Estrutura do repositório

```
observatorio-taxas/
├── .github/workflows/
│   ├── monitor.yml          # a cada 6 h: coleta → páginas → commit/push
│   ├── validate.yml         # testes em pull request (não toca na coleta)
│   └── indexnow.yml         # avisa buscadores das URLs alteradas, após o deploy
├── .github/FUNDING.yml      # botão Sponsor → /apoie/
├── config.yml               # séries monitoradas, GoatCounter, IndexNow
├── data/                    # armazenamento canônico, versionado
├── scripts/
│   ├── fetch.py             # coletor SGS + resumo grátis das mudanças
│   ├── backfill.py          # carga histórica (desde 2015, ou um ano informado)
│   ├── build_pages.py       # 522 páginas /reajuste/<indice>-<mes>-<ano>/ + hub
│   ├── build_correcao.py    # /correcao/ + uma página por índice
│   ├── render_index.py      # boletim do dia na landing + sitemap (único escritor)
│   ├── sync_nav.py          # replica o header em todas as páginas
│   ├── csp_hashes.py        # hashes sha256 dos scripts inline na CSP
│   ├── build_og.py          # card social (og-image.png) com os números do dia
│   ├── fetch_stats.py       # estatísticas do GoatCounter (opcional)
│   ├── indexnow.py          # aviso IndexNow só das URLs que mudaram
│   ├── fontes.py            # procedência dos índices (IBGE, FGV IBRE, BCB)
│   ├── pix.py               # código Pix da /apoie/ e validação EMV/CRC16
│   ├── gerar_qr_pix.py      # regenera docs/apoie/pix-qr.svg (exige segno)
│   ├── seo_audit.py         # auditoria do HTML como um robô sem JS o recebe
│   ├── diff_summary.py      # opcional e pago: resumo via API da Anthropic
│   └── radar_fixtures.py    # dados de exemplo do Radar (página interna)
├── partials/nav.html        # header canônico (fora de docs/: não é publicado)
├── docs/                    # o que o GitHub Pages publica
│   ├── index.html           # página inicial
│   ├── reajuste/, correcao/ # páginas geradas
│   ├── rebobinar.html, var.html, retransmissora.html, embed.html
│   ├── apoie/               # contribuição voluntária via Pix
│   ├── data/                # espelho dos JSONs
│   ├── radar/, admin/       # internos (noindex; admin também em Disallow)
│   ├── llms.txt, robots.txt, sitemap.xml, CNAME, .nojekyll
│   └── <chave>.txt          # arquivo de verificação do IndexNow
├── tests/                   # testes (unittest, stdlib)
├── organic-discovery/       # auditoria SEO/GEO, diretrizes, IndexNow
├── assets/                  # fontes OFL e imagens do README (não publicados)
├── CITATION.cff, LICENSE, LICENSE-DADOS.md
└── requirements.in / requirements.txt   # lock com hashes (requests, pyyaml, pillow)
```

## Pipeline de geração

Ordem usada pelo `monitor.yml` (e a que deve ser seguida localmente):

```bash
python scripts/fetch.py           # coleta e funde os pontos novos
python scripts/build_pages.py     # páginas de reajuste
python scripts/build_correcao.py  # páginas de correção
python scripts/render_index.py    # boletim da landing + sitemap
python scripts/sync_nav.py        # header em todas as páginas
python scripts/adsense.py         # ads.txt; anúncios só se ligados (ver ADSENSE.md)
python scripts/csp_hashes.py      # CSP com os hashes dos scripts inline
python scripts/build_og.py        # card social
```

Conferências que não escrevem nada (úteis antes de um PR):

```bash
python scripts/sync_nav.py --conferir
python scripts/csp_hashes.py --conferir
python -m unittest discover -s tests -v
python scripts/seo_audit.py
```

## Navegação do site

O header é HTML estático dentro de cada página, nunca injetado por
JavaScript: o menu funciona com JS desligado, com o site aberto do disco
(`file://`) e para robôs que não executam JS.

A fonte da verdade é [`partials/nav.html`](../partials/nav.html), fora de
`docs/` porque `docs/` é o que o Pages serve. Ele é replicado em cada página
entre os marcadores `nav:start` e `nav:end` por `python scripts/sync_nav.py`,
que ajusta por página o prefixo relativo dos links (`../`), o item ativo
(`aria-current="page"`), a classe `tema-radar` nas páginas do Radar e o
`<link>` para `nav.css`. É idempotente.

- **Página nova:** basta rodar o script; ele insere os marcadores logo depois do skip link.
- **Não edite o header dentro das páginas:** a próxima sincronização desfaz. Edite o partial.
- O passo roda depois de `build_pages.py` e `build_correcao.py`, que reescrevem as páginas de reajuste e correção a cada coleta.
- Ficam de fora, de propósito, `docs/embed.html` (iframe em sites de terceiros) e `docs/admin/index.html` (painel interno).

## Configuração das séries

Edite `config.yml` para ajustar ou ampliar as séries. Valide os códigos no
[SGS](https://www3.bcb.gov.br/sgspub/).

A API do SGS é pública e retorna `[{"data": "dd/mm/aaaa", "valor": "x"}]`.
`base_url` é a base sem sufixo; o código monta `/dados/ultimos/N` (coleta) ou
`?dataInicial=&dataFinal=` (backfill). O `backfill.py` busca desde 01/01/2015
por padrão (`python scripts/backfill.py 2019` busca desde 2019), em janelas,
e reduz o alcance de séries diárias que deixariam o JSON grande demais.

## Página inicial

`docs/index.html` é escrita à mão. O `render_index.py` reescreve só o que fica
entre marcadores (`boletim`, `var`, `rebobinar`), então os números aparecem no
HTML sem JavaScript:

- **Boletim do dia:** Selic, IPCA 12 meses, dólar, IGP-M no mês e desemprego, com variação no mês, data de referência e minigráfico desenhado em SVG.
- **Rebobinar:** fita dos últimos 6 meses e a manchete do mês.
- **VAR:** um recibo de exemplo (IPCA 2019–2022 contra 2023–hoje).
- **Reajuste**, **Retransmissora** (carrossel de 7 séries com o código de incorporação) e o bloco **Para redações e newsletters**.

Todos os valores vindos da API passam por escape de HTML (`esc()`) antes de
entrar na página. A landing e o embed usam CSP com hashes por script
(`csp_hashes.py`), sem `'unsafe-inline'` no `script-src`.

## SEO, sitemap e IndexNow

- Cada página tem `title`, `description`, `canonical`, Open Graph e, onde há
  correspondência com o conteúdo visível, JSON-LD (`WebSite`, `Organization`,
  `Dataset`, `FAQPage`, `BreadcrumbList`).
- `docs/robots.txt`, `docs/sitemap.xml` e `docs/.nojekyll`.
- O sitemap é escrito só por `render_index.py`, com `lastmod` por conteúdo
  (`data/sitemap_lastmod.json`).
- O IndexNow (`scripts/indexnow.py` + `.github/workflows/indexnow.yml`) avisa
  só as URLs novas, alteradas ou removidas, depois de conferir que o Pages já
  serve a versão nova. A primeira execução é manual; detalhes em
  [`organic-discovery/INDEXNOW.md`](../organic-discovery/INDEXNOW.md).
- Envie o sitemap no [Google Search Console](https://search.google.com/search-console)
  e no [Bing Webmaster Tools](https://www.bing.com/webmasters):
  `https://observatoriodetaxas.tec.br/sitemap.xml`.

## CHANGELOG e resumo opcional por IA

Ao detectar uma mudança, o `fetch.py` anexa ao `CHANGELOG.md` uma frase em
PT-BR gerada localmente, em Python puro, sem API e sem custo:

```
[2026-06-15 ...] Câmbio USD/BRL - venda: 5.0827 -> 5.0430
    ↳ Câmbio USD/BRL - venda: caiu de 5,0827 para 5,043.
```

### Opcional e pago: resumo via API da Anthropic (`diff_summary.py`)

Desligado por padrão. O `fetch.py` só tenta usar se a variável
`ANTHROPIC_API_KEY` existir; sem ela, usa o resumo grátis acima.

```bash
pip install anthropic
export ANTHROPIC_API_KEY="..."
python scripts/diff_summary.py "Meta Selic (% a.a.): 13.75 -> 14.50"
```

No workflow, cadastre o secret `ANTHROPIC_API_KEY` (`gh secret set
ANTHROPIC_API_KEY` ou *Settings → Secrets*); o `monitor.yml` instala
`anthropic` e injeta a chave só quando o secret existe.

> Nunca comite a chave nem a cole em chats ou arquivos versionados; o
> `.gitignore` já bloqueia `.env`. Se uma chave vazar, revogue-a no console da
> Anthropic e gere outra.

## Página de apoio (Pix)

`docs/apoie/` é estática. O código Pix fica em `scripts/pix.py` e é validado
(estrutura EMV, QR estático, sem valor fixo, CRC16) pelos testes. Para trocar:
gere um novo código no banco, cole em `scripts/pix.py` e no campo da página,
rode `python scripts/gerar_qr_pix.py` (exige `segno`) e
`python -m unittest tests.test_apoie`. O QR estático depende de a chave Pix e
a conta continuarem ativas.

## Publicação no GitHub Pages

1. **Settings → Actions → General → Workflow permissions:** *Read and write permissions*, para o `monitor.yml` commitar os snapshots com o `GITHUB_TOKEN`.
2. **Settings → Pages:** *Deploy from a branch*, branch `main`, pasta `/docs`.
3. Domínio próprio em `docs/CNAME` (`observatoriodetaxas.tec.br`).
4. Rode o workflow uma vez (**Actions → monitor → Run workflow**) para gerar os primeiros JSONs. Depois ele roda sozinho a cada 6 horas.
