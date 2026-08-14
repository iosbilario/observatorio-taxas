# observatorio-taxas

> 📊 **Site:** https://iosbilario.github.io/observatorio-taxas/ · **100% gratuito** (sem servidor, sem banco de dados, sem serviços pagos)

Observatório de baixíssima manutenção que **versiona séries de taxas e indicadores do Banco Central do Brasil (SGS) ao longo do tempo**, usando o próprio **Git como banco de dados temporal** e o **GitHub Actions como motor** — tudo a custo zero. A cada execução agendada, um robô consulta a API pública do SGS/BACEN, grava os valores como snapshots JSON em `data/` e commita as mudanças; o histórico de commits passa a ser, então, a linha do tempo de cada indicador, e uma página estática em `docs/` lê esses JSONs para desenhar os gráficos.

## Arquitetura — o loop API → Action → commit → Pages

O sistema é um ciclo fechado e sem servidor:

1. **API (SGS/BACEN).** `scripts/fetch.py` lê `config.yml` (lista de séries + `base_url`) e consulta a API de dados abertos do Banco Central para cada código.
2. **Action (GitHub Actions).** `.github/workflows/monitor.yml` roda por `cron` a cada 6 horas, prepara o Python, instala as dependências e executa o coletor.
3. **Commit (Git como base temporal).** Os snapshots JSON gerados em `data/` são commitados e enviados (push) automaticamente. Cada commit é um ponto no tempo — versionar é o que cria o histórico, sem precisar de banco de dados.
4. **Pages (visualização).** A página estática `docs/index.html` lê os JSONs (espelhados em `docs/data/`) e renderiza a série temporal com Chart.js, publicada via GitHub Pages servindo a pasta `/docs`.

Estado atual: **implementado e em produção.** Coleta (`fetch.py`), workflow agendado (`monitor.yml`) e gráficos (`index.html`) funcionando; o site já está publicado. As mudanças de valor geram uma frase-resumo em PT-BR gerada localmente (grátis). A camada de IA via API da Anthropic (`diff_summary.py`) é um upgrade **opcional e pago**, desligado por padrão.

## Arquivos gerados em `data/`

A cada coleta, `fetch.py` produz (chaves ordenadas, UTF-8, indentado — para `git diff` limpo):

| Arquivo | Conteúdo |
| --- | --- |
| `data/<codigo>.json` | Último ponto bruto da série (`data`, `valor`, `codigo`, `nome`). |
| `data/<codigo>_history.json` | **Série temporal** acumulada: lista de `{data, valor}` por data de referência do BACEN, ordenada. Fundida por data (sem duplicar) a cada coleta. |
| `data/series.json` | Manifesto (`codigo`, `nome`, `valor_atual`, `data_referencia`, `ultima_mudanca`, `pontos`) consumido pela página. |
| `data/meta.json` | Instante da última coleta com mudança (`gerado_em_fmt`, ex.: `15/06/2026 às 15:06`), em **horário de Brasília** (UTC-3). Exibido no rodapé do site. Gravado **só quando há mudança de dados**, para preservar a idempotência do job. |
| `CHANGELOG.md` | Uma linha por mudança detectada: `[timestamp] <nome>: <antigo> -> <novo>`, seguida de uma frase-resumo em PT-BR (`↳ ... subiu/caiu de X para Y`). |

Os arquivos que a página consome (`series.json`, `meta.json` e cada `<codigo>_history.json`) são **espelhados em `docs/data/`**, porque o GitHub Pages servindo `/docs` só publica o que está dentro de `docs/`. O store canônico continua sendo `data/` na raiz.

## Estrutura

```
observatorio-taxas/
├── .github/workflows/monitor.yml   # workflow agendado (cron 6h) → fetch → commit/push
├── data/                           # snapshots + histórico (store canônico, versionado)
│   ├── <codigo>.json               #   último valor bruto de cada série
│   ├── <codigo>_history.json       #   série temporal [{data, valor}] por data de referência
│   ├── series.json                 #   manifesto consumido pela página
│   └── meta.json                   #   horário da última coleta (rodapé do site)
├── scripts/fetch.py                # coletor SGS/BACEN + resumo grátis das mudanças
├── scripts/backfill.py             # carga inicial do histórico (N anos; padrão 2)
├── scripts/diff_summary.py         # upgrade opcional/pago: resumo via API da Anthropic
├── partials/nav.html               # bloco canônico do header (fora de docs/: não é servido)
├── scripts/sync_nav.py             # replica o header em todas as páginas de docs/
├── docs/nav.css                    # estilo do header, compartilhado por todas as páginas
├── docs/index.html                 # landing page + dashboard interativo (Chart.js) — via Pages
├── docs/radar/                     # Radar de Recomendação (produto próprio; ver docs/radar/README.md)
├── docs/data/                      # espelho dos JSONs que a página lê (servido por /docs)
├── docs/og-image.png               # imagem de compartilhamento (Open Graph / Twitter)
├── docs/robots.txt, sitemap.xml    # SEO / indexação
├── docs/.nojekyll                  # desativa o Jekyll no GitHub Pages
├── CHANGELOG.md                    # log de mudanças de valor (gerado automaticamente)
├── config.yml                      # séries monitoradas
├── requirements.txt                # requests, pyyaml
├── .gitignore                      # padrão Python + .claude/ (config local de preview)
└── README.md
```

## Navegação do site

O header é **HTML estático dentro de cada página**, nunca injetado por
JavaScript: crawler de LLM em geral não executa JS, e ser legível por máquina é
estratégia central deste site. Também é o que faz o menu funcionar com JS
desligado e com o site aberto do disco (`file://`).

A fonte da verdade é [`partials/nav.html`](partials/nav.html) — fora de `docs/`
porque `docs/` é o que o Pages serve. Ele é replicado em cada página entre os
marcadores `nav:start` e `nav:end` por:

```bash
python scripts/sync_nav.py
```

O script ajusta por página o prefixo relativo dos links (`../`), o item ativo
(`aria-current="page"`), a classe `tema-radar` nas páginas do Radar e o `<link>`
para `nav.css`. É idempotente.

**Página nova:** não precisa fazer nada além de rodar o script — ele insere os
marcadores sozinho, logo depois do skip link. Se quiser controlar a posição,
coloque `<!-- nav:start -->` e `<!-- nav:end -->` onde o header deve ficar.

**Não edite o header dentro das páginas**: a próxima sincronização desfaz. Edite
o partial e rode o script. `python scripts/sync_nav.py --conferir` falha se
alguma página estiver fora de sincronia (útil em CI).

O passo roda no workflow **depois** de `build_pages.py` e `build_correcao.py`,
que reescrevem as ~518 páginas de reajuste e correção a cada coleta — sem isso o
header sumiria delas. Ficam de fora, de propósito, `docs/embed.html` (payload de
iframe em sites de terceiros) e `docs/admin/index.html` (painel interno).

## Rodando localmente

```bash
# 1. (opcional) ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. dependências
pip install -r requirements.txt

# 3. (uma vez) carga inicial do histórico — puxa 2 anos de cada série
python scripts/backfill.py            # ou: python scripts/backfill.py 5  (5 anos)

# 4. coletar — funde os pontos novos nos JSONs de data/ (e espelho em docs/data/)
python scripts/fetch.py

# 5. visualizar a página localmente
python -m http.server -d docs 8000
# abra http://localhost:8000
```

## Configuração

Edite `config.yml` para ajustar ou ampliar as séries monitoradas. Os códigos do SGS devem ser validados (referência: https://www3.bcb.gov.br/sgspub/).

A API do SGS é pública e retorna `[{"data": "dd/mm/aaaa", "valor": "x"}]`. A `base_url` em `config.yml` é a base sem sufixo; o código monta `/dados/ultimos/N` (coleta) ou `?dataInicial=&dataFinal=` (backfill). Ajuste `anos_historico` para mudar a janela do `backfill.py`.

## Página (landing page + dashboard)

`docs/index.html` é uma **landing page** de página única (sem etapa de build), em layout escuro e responsivo, com:

- **Hero ao vivo** — destaques (Selic, IPCA 12 meses, dólar, desemprego) lidos de `series.json`, cada um com a **tendência de 90 dias** calculada do histórico.
- **"A história dos dados"** — parágrafo executivo conectando juros, inflação, câmbio e atividade ao dia a dia, e **"Impacto no Brasil real"** explicando o que cada grupo de indicadores move.
- **Dashboard** — uma série por indicador com **Chart.js**, filtros de período (**7, 15, 30, 60, 90, 120, 365 dias** e *Tudo*) e a **variação percentual no período**. O **ponto de dados mais recente é destacado** em todos os gráficos. O rodapé mostra o **horário da última coleta** (de `meta.json`) e a data da última mudança de valor.
- **Metodologia & transparência** — métricas dinâmicas (nº de séries, total de pontos) e os pilares do projeto.

> Segurança: todos os valores vindos da API são injetados na página com escape de HTML (`esc()`), como defesa em profundidade contra XSS — mesmo sendo fonte oficial via HTTPS.

## SEO / indexação

A página inclui `title`/`description`/`keywords`, `canonical`, Open Graph, Twitter Card, favicon embutido e **dados estruturados JSON-LD** (`WebSite` + `Organization` + `Dataset`, ótimos para busca tradicional e para motores generativos). Há `docs/robots.txt`, `docs/sitemap.xml` e `docs/.nojekyll`.

Para acelerar a indexação: cadastre o site no **[Google Search Console](https://search.google.com/search-console)** (e no **Bing Webmaster Tools**), confirme a propriedade e envie a sitemap `https://iosbilario.github.io/observatorio-taxas/sitemap.xml`.

## Resumo das mudanças no CHANGELOG (grátis, padrão)

Ao detectar uma mudança, o `fetch.py` anexa ao `CHANGELOG.md` uma frase em PT-BR (indentada com `↳`) gerada **localmente, em Python puro — sem API, sem chave, sem custo**. É o comportamento padrão e mantém o projeto **100% NoCost**:

```
[2026-06-15 ...] Câmbio USD/BRL - venda: 5.0827 -> 5.0430
    ↳ Câmbio USD/BRL - venda: caiu de 5,0827 para 5,043.
```

### Upgrade OPCIONAL e PAGO via API da Anthropic (`diff_summary.py`)

Quem quiser frases mais "naturais" pode, **por conta própria**, ligar a camada de IA — mas ela **custa por uso** (a API da Anthropic exige conta com créditos) e por isso vem **desligada**. O `fetch.py` só a tenta se a variável `ANTHROPIC_API_KEY` estiver definida; sem ela, usa o resumo grátis acima, em silêncio.

```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows: $env:ANTHROPIC_API_KEY="..."
python scripts/diff_summary.py "Meta Selic (% a.a.): 13.75 -> 14.50"
```

No workflow, basta cadastrar o secret `ANTHROPIC_API_KEY` (`gh secret set ANTHROPIC_API_KEY` ou em *Settings → Secrets*); o `monitor.yml` instala `anthropic` e injeta a chave **só quando o secret existe**. Sem secret, nada de IA e nenhum custo.

> Nunca comite a chave nem a cole em chats/arquivos versionados — o `.gitignore` já bloqueia `.env`. Se uma chave vazar, revogue-a no console da Anthropic e gere outra.

## Publicação no GitHub Pages (servindo `/docs`)

1. **Settings → Actions → General → Workflow permissions** → selecione **Read and write permissions** e salve. Isso permite ao `monitor.yml` commitar os snapshots de volta usando o `GITHUB_TOKEN` padrão.
2. **Settings → Pages** → em *Build and deployment*, *Source* = **Deploy from a branch**; escolha a branch (`main`) e a pasta **`/docs`**; salve.
3. Aguarde o deploy; o site fica em `https://<usuario>.github.io/<repo>/`.
4. Rode o workflow uma vez (aba **Actions → monitor → Run workflow**) para gerar e commitar os primeiros JSONs em `docs/data/`. A partir daí ele roda sozinho a cada 6 h.
