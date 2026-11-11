# Auditoria SEO + GEO — estado original

Data: 11/11/2026. Commit auditado: `d95a2102` (snapshot 2026-11-11).
Método: leitura do código, HTML cru de `docs/` (sem executar JavaScript) via
`scripts/seo_audit.py`, requisições HTTP ao domínio de produção e Lighthouse 12
(mobile) em duas páginas. Linha de base numérica em [BASELINE.md](BASELINE.md).

## 1. Arquitetura descoberta

| Item | Como funciona |
| --- | --- |
| Hospedagem | GitHub Pages servindo `/docs` da `main`, domínio `observatoriodetaxas.tec.br` (CNAME), CDN Fastly do GitHub. Sem servidor, sem headers configuráveis. |
| Coleta | `.github/workflows/monitor.yml`, cron a cada 6 h: `fetch.py` consulta a API do SGS/BCB e grava `data/<codigo>_history.json` (espelhado em `docs/data/`). |
| Renderização | **SSG em Python (stdlib + PyYAML)**. Não há framework JS. `build_pages.py` gera 522 páginas `/reajuste/<indice>-<mes>-<ano>/` + hub; `build_correcao.py` gera `/correcao/` + 4 páginas; `render_index.py` "assa" o boletim no `index.html` e escreve o sitemap; `sync_nav.py` replica o header; `csp_hashes.py` atualiza a CSP. |
| Páginas manuais | `index.html`, `rebobinar.html`, `var.html`, `retransmissora.html`, `embed.html` (noindex), `admin/` (noindex + Disallow), `radar/` (noindex). |
| Determinismo | Rodar o pipeline sobre o commit auditado reproduz `docs/` byte a byte, exceto o hash do commit no carimbo do boletim. |

Página de mês (`/reajuste/igpm-julho-2026/`): o acumulado 12 meses, o fator, a
tabela de 12 meses e os links de navegação estão no HTML inicial. A calculadora
depende de JS, mas o resultado-padrão (exemplo R$ 2.000) é estático. A
renderização **já era adequada a robôs sem JS** nas famílias que recebem citações.

## 2. Matriz de problemas

Gravidade: Alta = afeta indexação/atribuição de forma comprovada; Média = sinal
conflitante ou informação ausente; Baixa = higiene.

| # | Gravidade | Onde | Evidência | Correção proposta | Risco |
| --- | --- | --- | --- | --- | --- |
| P1 | Alta | `docs/rebobinar.html` | `<link rel="canonical">` e `og:url` apontavam para `https://iosbilario.github.io/observatorio-taxas/rebobinar.html`, que responde 301 para o domínio próprio. Canonical cruzado para uma URL que redireciona de volta. | Canonical e og:url para `https://observatoriodetaxas.tec.br/rebobinar.html`. | Nenhum (URL pública não muda). |
| P2 | Alta | Rodapé e FAQ de **todas** as 527 páginas de reajuste/correção; JSON-LD `Dataset` da landing | Textos "Fonte primária: API pública do SGS/Banco Central do Brasil" e "segundo dados do Banco Central do Brasil (SGS)" para IPCA/INPC (IBGE) e IGP-M/IGP-DI (FGV IBRE). `sourceOrganization` = só BCB. | Atribuir o índice ao produtor e citar o SGS como canal de obtenção. | Nenhum para URLs. Corrige atribuição que sistemas de IA podem replicar. |
| P3 | Média | `docs/sitemap.xml` (3 escritores: `build_pages`, `build_correcao`, `render_index`) | As 532 URLs tinham `lastmod` = data do dia a cada coleta, inclusive páginas de 2016 que não mudam. O Google declara que só usa `lastmod` quando ele é consistente e verificável; o Bing o usa como sinal de atualização. | `lastmod` por impressão digital do conteúdo, um só escritor. | Baixo. |
| P4 | Média | 44 URLs com "março" no sitemap | `<loc>` com `ç` cru. O protocolo de sitemaps exige URL escapada. `/reajuste/igpm-mar%C3%A7o-2026/` responde 200. | Escapar o `loc` (mesma URL). | Nenhum. |
| P5 | Média | FAQPage das 527 páginas geradas | As perguntas do JSON-LD **não apareciam no conteúdo visível**. Dado estruturado sem correspondência no texto contraria as diretrizes do Google. | Seção "Perguntas e respostas" visível com o mesmo texto. | Baixo. |
| P6 | Média | Páginas de mês | Faltavam: variação **do mês** em destaque (só na última linha da tabela), produtor do índice, link para a série oficial, janela explícita (mês inicial a final), unidade, links para mês anterior/seguinte e link para a correção do mesmo índice. A data de divulgação não é coletada. | Resposta direta, ficha técnica `<dl>`, navegação entre meses vizinhos e link para a correção. Data de divulgação declarada como não registrada. | Baixo (conteúdo adicional, valores inalterados). |
| P7 | Média | Todas as páginas, header (`partials/nav.html`) | O menu aponta para `index.html` e `reajuste/index.html`, variantes não canônicas (as duas respondem 200 e têm canonical correto). 536 páginas com esse link. | Trocar para `./` e `reajuste/`. **Não aplicado**: quebra a navegação via `file://`, decisão de projeto documentada no README. Ver BACKLOG B-01. | Baixo, mas exige decisão. |
| P8 | Média | `rebobinar.html` | O `<main>` cru contém só "Carregando os commits da economia…". O H1 existe só dentro de template JS. Sem JS, a página não tem conteúdo. | Pré-renderizar o mês corrente no HTML (como já é feito no teaser da landing). BACKLOG B-02. | Médio (página manual grande). |
| P9 | Baixa | 527 páginas geradas | Sem `<link rel="icon">`: o navegador pede `/favicon.ico` e recebe 404 (Lighthouse: "errors-in-console"). | Ícone embutido igual ao da landing. | Nenhum. |
| P10 | Baixa | Breadcrumb visível | A trilha terminava no hub, sem a página atual; sem `BreadcrumbList`. | Trilha completa com `aria-current` e `BreadcrumbList` equivalente. | Nenhum. |
| P11 | Baixa | Landing, `WebSite.potentialAction` | `SearchAction` para `var.html?claim=`. O Google descontinuou a caixa de pesquisa de sitelinks em 2024. | Inofensivo; manter ou remover. BACKLOG B-07. | Nenhum. |
| P12 | Baixa | Cache | `cache-control: max-age=600` em fontes e HTML (fixo do GitHub Pages). | Só com CDN própria. BACKLOG B-08. | — |
| P13 | Baixa | Dataset "Inflação" | `distribution` listava 3 das 5 séries (faltavam 188 e 190). | Incluir. | Nenhum. |
| P14 | Informativa | `/index.html`, `/reajuste/index.html`, `/rebobinar` sem extensão | Respondem 200 (o Pages não redireciona). Todas carregam canonical para a forma oficial. | Nada a fazer além de P7. | — |

### Itens verificados sem problema

- `robots.txt`: só `Disallow: /admin/`, sitemap declarado. Googlebot, bingbot,
  GPTBot, OAI-SearchBot, PerplexityBot e ClaudeBot recebem 200 com o mesmo HTML.
  Não há bloqueio a robôs de busca, de treinamento ou de agentes. Essa é uma
  escolha de política do dono, não um defeito: bloquear robôs de treinamento
  (GPTBot, ClaudeBot) não afeta Google/Bing; bloquear `bingbot` afetaria Copilot.
- Sem `X-Robots-Tag`. `meta robots` coerente: noindex só em embed, admin e radar.
- HTTP→HTTPS e `www`→apex: 301. Sem barra final: 301 para a forma com barra.
  404 real para URLs inexistentes.
- Títulos e descrições: nenhum duplicado entre as 532 páginas indexáveis.
- Links internos: nenhum quebrado; nenhuma página órfã; todas as páginas de mês
  alcançáveis por `<a href>` a partir do hub (o seletor JS é atalho, não o único caminho).
- Séries mensais 433, 188, 189 e 190 contíguas desde 01/2015 (sem buracos que
  distorceriam a janela de 12 meses).
- Fórmula do acumulado: o IPCA 12 meses composto a partir da série 433 bate com
  a série oficial 13522 em todos os 130 meses comparáveis, com diferença máxima
  de 0,0052 p.p. (arredondamento das variações mensais).
- Os últimos 20 valores das séries 433, 188, 189 e 190 em `data/` são iguais aos da API do SGS em 11/11/2026.
- Desempenho (Lighthouse mobile, produção): ver BASELINE. Não há gargalo.

## 3. Rastreamento por família

| Família | URLs | Dados no HTML inicial | Observação |
| --- | --- | --- | --- |
| Landing `/` | 1 | Sim (boletim assado) | Bom. Dataset com atribuição incompleta (P2, P13). |
| Reajuste hub `/reajuste/` | 1 | Sim | Faltava responder "qual índice usar" e quem produz cada índice. |
| Reajuste mês | 522 | Sim (acumulado, fator, tabela) | P2, P5, P6, P9, P10. |
| Correção | 5 | Parcial: acumulado 12m estático; série completa só no JS | P2, P5. |
| Rebobinar | 1 | Não | P1, P8. |
| VAR / Retransmissora | 2 | Sim (estrutura); resultado do recibo depende de JS | Não auditado em profundidade. |

## 4. SEO convencional e recuperação por IA

O que importa para os dois é o mesmo e está documentado pelos buscadores:
HTML rastreável, URL canônica única, sitemap preciso e texto que responde à
pergunta com valor, unidade, período e fonte. Não há requisito técnico
específico de "IA" publicado pelo Google ou pela Microsoft além disso.

- **Recomendação oficial** (Google Search Central, Bing Webmaster Guidelines):
  canonical consistente, sitemap com `lastmod` preciso, dado estruturado
  coerente com o conteúdo visível, conteúdo útil e não duplicado.
- **Hipótese técnica**: texto de resposta direta ("O IGP-M de julho de 2026
  variou X% no mês") e ficha técnica explícita tornam a extração do número
  menos ambígua para sistemas que citam trechos. Nenhum buscador promete isso.
- **Experimento**: `llms.txt`. Já existe e é barato manter. Nenhum dos
  buscadores citados declara que o usa. Não deve ser priorizado.
