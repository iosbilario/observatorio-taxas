# Melhorias implementadas

Todas as mudanças de páginas geradas foram feitas **nos geradores** (as 527
páginas são reescritas a cada coleta; editar o HTML direto seria desfeito).
Nenhuma URL pública mudou. Nenhuma fórmula mudou: os valores de acumulado,
fator e o `FATOR` da calculadora de todas as 526 páginas de reajuste/correção
são idênticos aos da linha de base (teste `test_valores_publicados_iguais_a_linha_de_base`).

| # | Melhoria | Problema | Arquivos | Teste |
| --- | --- | --- | --- | --- |
| M1 | Canonical e og:url do Rebobinar no domínio próprio | P1 | `docs/rebobinar.html` | `test_canonical_unico_e_proprio` |
| M2 | Procedência correta: IPCA/INPC → IBGE; IGP-M/IGP-DI → FGV IBRE; SGS/BCB como canal de obtenção. Fonte única em `fontes.py` | P2 | `scripts/fontes.py` (novo), `scripts/build_pages.py`, `scripts/build_correcao.py`, `docs/index.html` (JSON-LD Dataset), `docs/llms.txt` | `test_procedencia_nao_atribui_ao_bacen_indices_de_outros_orgaos`, `test_dados_centrais_no_html_inicial...` |
| M3 | `lastmod` por impressão digital do conteúdo (`<title>` + description + `<main>`, sem o hash do commit), estado em `data/sitemap_lastmod.json`; `render_index.py` vira o único escritor do sitemap; `changefreq` removido (ignorado pelo Google) | P3 | `scripts/render_index.py`, `scripts/build_pages.py`, `scripts/build_correcao.py`, `data/sitemap_lastmod.json` (novo) | `test_estado_do_lastmod_cobre_o_sitemap`, `test_sitemap_lastmod_e_data_valida...` |
| M4 | `loc` do sitemap percent-encoded (44 URLs de março) | P4 | `scripts/render_index.py` | `test_sitemap_com_urls_escapadas` |
| M5 | FAQ visível com o mesmo texto do FAQPage; perguntas novas reais ("Qual foi o IGP-M de julho de 2026?", "Qual mês do índice devo usar?", "Quem calcula o IPCA?", "Como a calculadora faz a conta?") | P5, C.1 | `scripts/build_pages.py`, `scripts/build_correcao.py` | `test_faq_e_breadcrumb_batem_com_o_conteudo_visivel` |
| M6 | Página de mês: resposta direta com `<time>`, ficha técnica (indicador e nome completo, produtor com link, série SGS com link para a API, competência, variação do mês, acumulado e janela, unidade, critério de acumulação, data de divulgação declarada como não registrada), `<caption>` na tabela, `<article>/<header>/<section>` | P6, A.2, B.1, B.2 | `scripts/build_pages.py` | `test_dados_centrais_no_html_inicial_de_todas_as_paginas_de_mes` |
| M7 | Links para mês anterior/seguinte e para a correção do mesmo índice; correção aponta para a memória de cálculo do último mês | P6, D | `scripts/build_pages.py`, `scripts/build_correcao.py` | `test_meses_vizinhos_ligados`, `test_pagina_de_mes_aponta_para_a_correcao_do_indice`, `test_correcao_12_meses_igual_ao_reajuste...` |
| M8 | Breadcrumb completo com `aria-current` + `BreadcrumbList` com os mesmos nomes/URLs | P10 | `scripts/build_pages.py`, `scripts/build_correcao.py` | `test_faq_e_breadcrumb_batem...` |
| M9 | Favicon embutido nas páginas geradas (elimina 404 de `/favicon.ico`) | P9 | `scripts/build_pages.py`, `scripts/build_correcao.py` | inspeção |
| M10 | Hub de reajuste: seção "Qual índice usar no reajuste do aluguel?" (Lei 8.245/1991 art. 17; Lei 10.192/2001 art. 2º; o BCB não define nem calcula os índices) e lista de produtores | C.1, C.3 (consulta "reajuste de aluguel banco central") | `scripts/build_pages.py` | `test_um_h1_no_html_inicial` |
| M11 | Dataset "Inflação" com as 5 séries em `distribution`; Dataset "Atividade" com IBGE (PNAD) e BCB (IBC-Br) | P2, P13 | `docs/index.html` | `test_jsonld_valido` |
| M12 | Ferramenta de auditoria do HTML cru e suíte de aceitação | §11 | `scripts/seo_audit.py`, `tests/test_organic_discovery.py`, `tests/fixtures/` | 25 testes |

## Títulos e H1 (antes → depois)

| Elemento | Antes | Depois |
| --- | --- | --- |
| `<title>` mês | `Reajuste IGP-M julho de 2026: acumulado 12 meses de 2,77%` | `IGP-M de julho de 2026: -1,16% no mês e 2,77% em 12 meses` |
| H1 mês | `Reajuste pelo IGP-M: julho de 2026` | `IGP-M de julho de 2026: acumulado em 12 meses e reajuste` |
| description mês | `... dados oficiais do BACEN.` | `O IGP-M (FGV IBRE) variou -1,16% em julho de 2026 e acumulou 2,77% nos 12 meses até julho de 2026 (fator 1,027722). Memória de cálculo e calculadora de reajuste de aluguel e contratos.` |

O título passou a trazer a variação do mês, que é o que as consultas
"igpm agosto 2026" pedem, e continua trazendo o acumulado
("igpm acumulado 12 meses julho 2026"). Isso é uma hipótese de clareza, não
uma promessa de posição.

## Diferenças esperadas no HTML (antes × depois)

- 527 páginas geradas: novas seções, CSS, favicon, rodapé e JSON-LD. Valores numéricos idênticos.
- Peso da página de mês: 26,6 KB → 32,9 KB (gzip 6,0 → 7,6 KB). Hub: 65,1 → 68,8 KB.
- `docs/index.html`: só o JSON-LD (e o hash do commit no carimbo, que muda a cada run).
- `docs/sitemap.xml`: sem `changefreq`, `loc` escapado, `lastmod` por conteúdo.
  Nesta primeira execução, 530 URLs recebem 11/11/2026 (o conteúdo mudou hoje) e
  `var.html`/`retransmissora.html` mantêm 14/08/2026 (último commit do arquivo).
- Efeito colateral positivo: sem dado novo, o sitemap deixa de mudar todo dia,
  o que reduz commits vazios do robô.

## Não alterado de propósito

- URLs, slugs (inclusive os com `ç`), redirecionamentos.
- `acumulado()`, `fator_periodo()`, JS das calculadoras.
- Identidade visual (mesmos tokens, fontes e componentes; ver capturas em VALIDATION).
- Header/menu (`partials/nav.html`), `robots.txt`, workflow.
