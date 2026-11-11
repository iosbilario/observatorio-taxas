# Validação

Executado em 11/11/2026 no macOS, Python 3.13, venv isolado com
`pip install --require-hashes -r requirements.txt`.

## Comandos

```
python scripts/build_pages.py
python scripts/build_correcao.py
python scripts/render_index.py
python scripts/sync_nav.py
python scripts/csp_hashes.py
python scripts/sync_nav.py --conferir
python scripts/csp_hashes.py --conferir
python -m unittest discover -s tests -v
ORGANIC_LIVE=1 python -m unittest tests.test_organic_discovery.TestAoVivo
python scripts/seo_audit.py
```

O repositório não tinha testes automatizados. A suíte nova usa só stdlib
(`unittest`), sem dependência nova no lock.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Pipeline (5 scripts, mesma ordem do workflow) | OK: 522 páginas de reajuste + hub, 4 de correção + hub, 532 URLs no sitemap |
| Idempotência (pipeline rodado 2x, md5 de todo HTML + sitemap + estado) | Idêntico |
| `sync_nav.py --conferir` / `csp_hashes.py --conferir` | Em dia |
| `python -m unittest discover -s tests` | **28 testes, OK, 1 pulado** (o teste ao vivo, que roda com `ORGANIC_LIVE=1`) |
| `TestAoVivo` com `ORGANIC_LIVE=1` (produção atual) | OK: 15 URLs de todas as famílias com HTTP 200 |
| Teste de mutação (alterar 2,77% → 2,78% numa página) | O teste de valores falha, como esperado; arquivo restaurado |
| `py_compile` de todos os scripts e testes | OK |
| Dados × API SGS ao vivo (últimos 20 pontos de 433, 188, 189, 190) | 80/80 iguais |
| IPCA 12m calculado × série oficial 13522 | 130 meses, diferença máxima 0,0052 p.p. |

### Cobertura dos critérios de aceitação (§11)

| Critério | Teste |
| --- | --- |
| URLs históricas preservadas | `test_urls_da_linha_de_base_preservadas` (532 URLs de `tests/fixtures/urls_baseline.txt`) |
| HTTP 200 | `TestAoVivo` (opcional, rede) |
| Uma canonical por conteúdo | `test_canonical_unico_e_proprio` |
| Títulos únicos | `test_titulos_e_descricoes_unicos` |
| H1 coerente | `test_um_h1_no_html_inicial`, `test_paginas_de_mes_tem_h1_coerente_com_a_url` |
| Dados centrais no HTML inicial | `test_dados_centrais_no_html_inicial_de_todas_as_paginas_de_mes` (522 páginas, recalculadas de `data/`) |
| Valores coerentes com a fonte | `test_acumulado_ipca_bate_com_serie_oficial_13522`, conferência ao vivo acima |
| Sitemap sem páginas inexistentes | `test_sitemap_so_com_urls_canonicas_publicaveis`, `test_sitemap_com_urls_escapadas` |
| Sem links internos quebrados | `test_links_internos_sem_quebra`, `test_sem_paginas_orfas` |
| Dados estruturados válidos | `test_jsonld_valido`, `test_faq_e_breadcrumb_batem_com_o_conteudo_visivel` |
| Fórmulas sem alteração acidental | `test_valores_publicados_iguais_a_linha_de_base` (526 páginas: acumulado, fator e `FATOR` do JS), `test_acumulado_composto_valor_conhecido`, `test_historicos_mensais_contiguos` |
| Build aprovado | pipeline acima |

### Exceção conhecida

`rebobinar.html` não tem H1 no HTML inicial (conteúdo 100% JS). Está na lista
`SEM_H1_NO_HTML_INICIAL` do teste, com referência ao BACKLOG B-02.

### Verificação visual

Capturas com Chrome headless, servidor local em 127.0.0.1: página de mês
(600 px) e hub (1280 px). Mesmos tokens, fontes e componentes; a ficha técnica
e o FAQ usam o estilo de card existente. Em 420 px o Chrome headless no macOS
renderiza com largura mínima maior que a janela e corta a lateral; a linha de
base mostra o mesmo corte, então não é regressão. A verificação mobile real
fica para o navegador do dono.

## Limitações

- O IBGE responde 403 a requisições automatizadas (curl e fetch). Os links
  `ibge.gov.br/.../9256-...` (IPCA) e `9258-...` (INPC) são as páginas
  oficiais conhecidas dos índices, mas não foram confirmados por HTTP nesta
  execução. Abrir no navegador antes de publicar.
- A série 13522 não respondeu na conferência ao vivo (timeout); ela foi validada contra o histórico local.
- Lighthouse rodou só na produção atual (antes). Depois do deploy, repetir nas mesmas URLs.
- Os testes leem `docs/` como está no disco: rode o pipeline antes.
- Não há validação contra o Rich Results Test / Schema Markup Validator (exigem
  navegador e URL pública). Fazer após o deploy em 3 páginas: `/`,
  `/reajuste/igpm-julho-2026/`, `/correcao/ipca/`.
- O workflow `validate.yml` roda nos PRs, mas não pôde ser executado no GitHub antes do push; a primeira execução real é a deste PR.

## Revisão final do PR #15

### Workflow de validação (`.github/workflows/validate.yml`)

Dispara em `pull_request` e `workflow_dispatch`, com `contents: read`, sem
commit e sem push. Não compartilha `concurrency` com o `monitor.yml`, então
nunca atrasa nem bloqueia a coleta. Passos: testes sobre o `docs/` commitado;
regeneração com os mesmos scripts do `monitor.yml`; `git diff --exit-code`
(exceto `docs/index.html`, cujo carimbo leva o hash do commit); testes de novo.

### Mecanismo de `lastmod` (simulação em worktree descartável)

| Cenário | Resultado |
| --- | --- |
| Reconstrução sem dado novo | Sitemap e estado inalterados |
| Commit do robô sem dado novo + reconstrução | Inalterados (o hash do commit no carimbo é ignorado) |
| Coleta nova (IGP-M nov/2026 fictício, data simulada 01/12/2026) | 533 URLs; só 5 com lastmod novo: `/`, `/reajuste/`, `/correcao/igpm/`, `/reajuste/igpm-outubro-2026/` (ganha o link "mês seguinte") e a página nova. As outras ~130 páginas de IGP-M mantêm a data |
| Reconstrução após o commit da coleta | Inalterados |
| Clone raso (`--depth 1`, como o CI) | Inalterados (o estado versionado dispensa o histórico do Git) |

A primeira versão da impressão digital usava `<main>` e falhava em dois
pontos, corrigidos nesta revisão: (1) o bloco "últimos 12 meses" fica no
`<main>` e mudaria o lastmod de todas as páginas do índice a cada mês;
(2) o boletim da landing fica fora do `<main>` e o lastmod da home não
acompanharia os números do dia. Agora as páginas de mês marcam o conteúdo com
`<!-- conteudo:inicio -->`/`<!-- conteudo:fim -->` e as demais usam o `<body>`
sem header, scripts e estilos. O estado foi semeado de novo com a impressão
digital nova.

### Amostra de páginas

As 5 páginas pedidas e mais 9 da amostra (6 meses sorteados com semente fixa, `/correcao/ipca/`, `/` e `/rebobinar.html`): título, H1, canonical
e JSON-LD conferidos, e variação do mês, acumulado e fator recalculados de
`data/` e iguais no título, no texto e no FAQPage. Exemplos: `/reajuste/igpm-julho-2026/` -1,16% · 2,77% · 1,027722;
`/reajuste/igpm-agosto-2026/` -0,22% · 2,18% · 1,021782; `/reajuste/inpc-dezembro-2025/` 0,21% · 3,90% · 1,038979.
O teste `test_coerencia_titulo_h1_canonical_jsonld_e_valores` faz a mesma
conferência nas 522 páginas de mês.
