# Diretrizes para novas páginas e atualizações

Valem para páginas manuais e para os geradores em `scripts/`.

## URLs

1. URL publicada é permanente. Não renomear slug, não trocar acentuação, não
   remover página que já existiu. Mudança inevitável = 301 (o GitHub Pages não
   faz 301 por arquivo; exigiria página de redirecionamento + canonical, então evite).
2. Forma canônica: diretório com barra final (`/reajuste/igpm-julho-2026/`) ou
   `.html` nas páginas raiz já existentes. Links internos novos devem apontar para
   a forma canônica, não para `index.html`.
3. Slug de mês: `<indice>-<mes por extenso>-<ano>`, como hoje.

## Metadados

- Um `<title>` e uma `description` únicos por página, montados a partir dos
  dados reais. Nada de valor ou data estimada.
- Um H1 no HTML inicial, coerente com o título.
- `<link rel="canonical">` absoluto no domínio `observatoriodetaxas.tec.br`,
  igual à própria URL. `og:url` igual ao canonical.
- `lang="pt-BR"`.

## Conteúdo de indicador

Toda página de indicador responde, em texto e sem JavaScript:

| Campo | Regra |
| --- | --- |
| Indicador | Sigla e nome completo |
| Competência | Mês de referência, com `<time datetime="AAAA-MM">` |
| Valor | Com unidade explícita (% no mês, % a.a., R$) e casas decimais da fonte |
| Acumulado | Dizer a janela (mês inicial a final) e o critério (composto) |
| Produtor | Órgão que calcula o índice (IBGE, FGV IBRE, BCB, B3) |
| Canal | Série do SGS e link para ela, quando o dado vem do SGS |
| Datas | Data de divulgação só se coletada; caso contrário, dizer que não é registrada |
| Derivados | Todo número calculado pelo Observatório é identificado como tal, com fórmula |

Procedência por série (fonte da verdade: `scripts/fontes.py` para os índices de preço):

| Série SGS | Produtor |
| --- | --- |
| 433, 13522 IPCA · 188 INPC · 24369 desocupação (PNAD Contínua) | IBGE |
| 189 IGP-M · 190 IGP-DI | FGV IBRE |
| 4390 CDI | B3 |
| 432, 1178 Selic · 226 TR · 25 poupança · 1, 10813, 21619 câmbio · 24363 IBC-Br | Banco Central do Brasil |

Nunca escrever "segundo o Banco Central" para um índice que o BCB só redistribui.

## Estrutura HTML

- `main` > `article` > `header` (H1 + resposta direta) > `section` com `h2`.
- Números em texto ou `<table>` com `<caption>` e `scope`. Gráfico (canvas/SVG)
  sempre acompanhado da tabela ou do texto com os mesmos números.
- Navegação por `<a href>` real. Seletor JS pode existir como atalho, nunca
  como único caminho até uma página indexável.

## Dados estruturados

- Só tipos com correspondência visível: `BreadcrumbList` igual à trilha
  visível; `FAQPage` só com perguntas e respostas que aparecem na página, com o
  MESMO texto; `Dataset` só na landing, descrevendo os JSONs publicados.
- Nada de `Review`, `AggregateRating`, autor fictício ou organização inventada.
- Gerar com `json.dumps` e escapar `</`.

## Sitemap

- Único escritor: `scripts/render_index.py`. Não escrever sitemap em outros scripts.
- `lastmod` muda só quando o conteúdo muda (estado em `data/sitemap_lastmod.json`).
  Página gerada com navegação que muda sozinha deve envolver o conteúdo próprio
  em `<!-- conteudo:inicio -->` e `<!-- conteudo:fim -->`; sem marcadores, vale o
  `<body>` sem header, scripts e estilos.
- Só URLs canônicas, indexáveis, com arquivo existente. `loc` escapado.
- Página noindex não entra.

## Texto jurídico

- Reajuste de aluguel: o índice é o do contrato. Não escrever "índice
  obrigatório", "padrão" ou "deve usar" para IGP-M/IPCA.
- Citar lei só com número e artigo conferidos, e manter o aviso de conteúdo
  informativo.

## Conteúdo novo

Criar página nova só quando houver demanda observada (consulta recorrente no
Bing Webmaster Tools / Search Console) e algo que a página existente não
responde. Não gerar páginas por combinação de palavras-chave, nem variações do
mesmo conteúdo.

## Robôs e IA

- Não servir conteúdo diferente por user agent. Não esconder texto.
- `robots.txt` é decisão de política: bloquear `bingbot`/`Googlebot` remove o
  site de Copilot/AI Overviews; bloquear `GPTBot`/`ClaudeBot`/`Google-Extended`
  afeta uso para treinamento, não a busca tradicional. Registrar o motivo de
  qualquer bloqueio.
- `llms.txt` é complementar e experimental; não substitui HTML e sitemap.

## Antes de publicar

```
python scripts/build_pages.py
python scripts/build_correcao.py
python scripts/render_index.py
python scripts/sync_nav.py
python scripts/csp_hashes.py
python -m unittest discover -s tests -v
python scripts/seo_audit.py
```

## IndexNow

- Não chamar o IndexNow à mão nem em outro script: o `indexnow.yml` cuida disso
  a partir do `sitemap_lastmod.json`. Página nova entra sozinha quando aparece no sitemap.
- Página removida: apagar o arquivo, regenerar; o envio só acontece quando a URL já responde 404.
- Trocar a chave: novo `docs/<chave>.txt`, atualizar `indexnow_key`, apagar o arquivo antigo depois do primeiro envio aceito.
