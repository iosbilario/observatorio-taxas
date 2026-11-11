# Linha de base

Duas origens, que não se misturam:

- **§1 Externa (fornecida pelo dono)**: Bing Webmaster Tools, ~3 meses até 11/11/2026. Não reproduzida nesta execução.
  Atenção: o repositório é público. Estes números agregados ficam visíveis no GitHub (não no site).
- **§2 Medida nesta execução**: commit `d95a2102`, 11/11/2026, antes das alterações.

## 1. Visibilidade (Bing Webmaster Tools, fornecido pelo dono)

São **citações de URL em respostas de IA** (Copilot e parceiros). Não são
visitas nem cliques e não devem ser somadas a eles.

| Métrica | Valor |
| --- | --- |
| Citações em respostas de IA (total do painel) | ~2.100 |
| URLs citadas (relatório exportado) | 59 |
| Citações no CSV de páginas | 1.717 |
| Participação da área `/reajuste/` no CSV | 81,8% |

| URL | Citações |
| --- | --- |
| `/reajuste/` | 308 |
| `/reajuste/igpm-julho-2026/` | 284 |
| `/` | 265 |
| `/reajuste/igpm-agosto-2026/` | 178 |
| `/reajuste/inpc-dezembro-2025/` | 125 |

Consultas recorrentes: taxa selic ipca; inpc 2026 acumulado 12 meses; igpm
agosto 2026; igpm acumulado 12 meses julho 2026; inpc acumulado 12 meses 2025;
correção pelo igpm; reajuste de aluguel banco central; saldo selic últimas.

## 2. Técnica (medida nesta execução, antes das mudanças)

### Rastreamento (`scripts/seo_audit.py` sobre o `docs/` original)

| Métrica | Valor |
| --- | --- |
| Arquivos HTML em `docs/` | 538 |
| Páginas indexáveis | 532 |
| URLs no sitemap | 532 |
| Valores distintos de `lastmod` | 1 (todas = 2026-11-11) |
| URLs com caractere não escapado no sitemap | 44 |
| Canonical fora do domínio | 1 (`rebobinar.html`) |
| Páginas sem H1 no HTML inicial | 1 (`rebobinar.html`) |
| Páginas com link interno para `index.html` | 536 |
| Títulos duplicados / descrições duplicadas | 0 / 0 |
| Links internos quebrados / páginas órfãs | 0 / 0 |
| Páginas com FAQPage / FAQ visível | 527 / 0 |
| Páginas com `og:image` | 1 |

Depois das mudanças (mesma ferramenta): `lastmod` com 2 valores, 0 URLs não
escapadas, 0 canonical fora do domínio, 527 FAQ visíveis = FAQPage. Continuam
1 página sem H1 (B-02) e 536 com link para `index.html` (B-01).

### HTTP (produção, curl)

| URL | Status | Bytes | gzip |
| --- | --- | --- | --- |
| `/` | 200 | 47.204 | 12.990 |
| `/reajuste/` | 200 | 65.103 | 9.667 |
| `/reajuste/igpm-julho-2026/` | 200 | 26.641 | 5.997 |
| `/correcao/` | 200 | — | 7.915 |
| `/reajuste/igpm-julho-2026` (sem barra) | 301 → com barra | | |
| `/index.html`, `/reajuste/index.html` | 200 (duplicata com canonical) | | |
| `http://`, `www.` | 301 | | |
| URL inexistente | 404 | | |

`cache-control: max-age=600`, compressão gzip, TTFB ~0,2 s (edge GRU).
User agents Googlebot, bingbot, GPTBot, OAI-SearchBot, PerplexityBot e ClaudeBot: 200, mesmo tamanho.

### Lighthouse 12, mobile, produção

| Página | Perf. | Acess. | Boas práticas | SEO | LCP | CLS | TBT | Peso |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | 99 | 100 | 96 | 100 | 1,9 s | 0 | 0 ms | 204 KiB |
| `/reajuste/igpm-julho-2026/` | 98 | 100 | 96 | 100 | 2,1 s | 0 | 0 ms | 149 KiB |

INP não é medido em laboratório (TBT 0 ms é o indicador substituto). Alertas:
cache curto de fontes (fixo do Pages), `/favicon.ico` 404 nas páginas geradas
(corrigido), fontes < 12 px em pills e rótulos (B-12).

## 3. Mensuração daqui em diante

### Exposição (não são visitas)

| Métrica | Fonte | Frequência |
| --- | --- | --- |
| Impressões orgânicas, posição média, CTR por consulta e por página | Search Console (Google) e Bing Webmaster Tools, exportação CSV | Mensal |
| Páginas indexadas e erros de rastreamento | Search Console "Páginas"; Bing "Index Explorer" / "Site Explorer" | Mensal |
| Citações de IA, URLs citadas, participação por consulta | Bing Webmaster Tools, relatório de IA | Mensal |

### Visitas

| Métrica | Fonte |
| --- | --- |
| Cliques orgânicos | Search Console / Bing (é clique, não visita) |
| Visitas por página e por recurso (reajuste, correção, VAR, embeds) | GoatCounter (`data/stats.json`, `fetch_stats.py`) |
| Referência de buscadores e de plataformas de IA (`copilot.microsoft.com`, `bing.com`, `chatgpt.com`, `perplexity.ai`, `gemini.google.com`) | GoatCounter, campo referrer. Muitas plataformas não enviam referrer: o número é um piso. |

Regras: nunca somar citações com cliques ou visitas; comparar sempre o mesmo
período e a mesma origem; registrar a data de cada deploy relevante para ler as
séries antes/depois.

### Marcos de publicação

| Data | Versão | O que entrou |
| --- | --- | --- |
| 11/11/2026 | `v1.4.0` (merge do PR #15; o commit exato é o da tag) | Primeira intervenção técnica orientada pelos relatórios de IA: procedência dos índices, ficha técnica, FAQ visível, sitemap com lastmod por conteúdo, testes e validação de PR |
| (data do merge) | `v1.5.0` proposta | Ciclo 2: IndexNow (só URLs alteradas, após o deploy), título de `/correcao/` (73 → 61 caracteres), CITATION.cff, README |

Bing SEO Analysis de 11/11/2026 (fornecido pelo dono, antes do ciclo 2): 3 itens,
falta de backlinks de domínios reconhecidos (moderada), IndexNow (alta), título
longo em 1 página (alta).

Para comparar antes/depois, use 11/11/2026 como corte. Nenhuma variação de
citações ou cliques deve ser atribuída a esta versão sem comparar com a
sazonalidade dos índices (o IGP-M sai no fim de cada mês).

### Importação manual (sem API/credencial nesta execução)

1. Exportar mensalmente os CSVs (Bing: páginas, consultas, citações de IA; Search Console: Desempenho por consulta e por página).
2. Guardar **fora de `docs/`** (que é público), por exemplo num diretório local ignorado pelo Git ou num repositório privado, com nome `AAAA-MM_<origem>_<relatorio>.csv`.
3. Um script futuro (B-11) consolida em uma tabela com `mes, origem, metrica, url, consulta, valor`, sem publicar nada.

### Hipóteses para os próximos relatórios do Bing

| Hipótese | Como ler |
| --- | --- |
| H1. Páginas de mês com a variação do mês no título e na resposta direta passam a ser citadas também em consultas do tipo "igpm <mês> <ano>" (valor do mês), não só "acumulado 12 meses" | Participação dessas consultas nas citações das URLs `/reajuste/<indice>-<mes>-<ano>/` |
| H2. A seção "Qual índice usar" do hub muda as URLs citadas para "reajuste de aluguel banco central" | URL citada para essa consulta (hoje `/reajuste/`?) e texto atribuído |
| H3. Atribuição correta (IBGE/FGV) aparece em respostas que citam o site | Leitura manual de amostra de respostas do Copilot |
| H4. `lastmod` preciso altera a frequência de rastreamento das páginas antigas | Bing "Crawl information" / Search Console "Estatísticas de rastreamento" |

Nenhuma dessas hipóteses é garantida. Variação de citações tem muitas causas
fora do site (mudanças nos sistemas de IA, sazonalidade de reajuste, divulgação
do IGP-M no fim do mês).
