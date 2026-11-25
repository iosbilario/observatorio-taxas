<p align="center">
  <a href="https://observatoriodetaxas.tec.br/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/readme/banner-escuro.svg">
      <img src="assets/readme/banner.svg" width="100%" alt="Observatório de Taxas. Os números mudam. O histórico fica. Indicadores econômicos brasileiros, séries históricas versionadas e ferramentas gratuitas para consulta, comparação e cálculo.">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://observatoriodetaxas.tec.br/"><b>Site</b></a> ·
  <a href="https://observatoriodetaxas.tec.br/indicadores/">Indicadores</a> ·
  <a href="https://observatoriodetaxas.tec.br/comparador/">Comparador</a> ·
  <a href="https://observatoriodetaxas.tec.br/simulador-cdi/">Simulador de CDI</a> ·
  <a href="https://observatoriodetaxas.tec.br/reajuste/">Reajuste</a> ·
  <a href="https://observatoriodetaxas.tec.br/correcao/">Correção monetária</a> ·
  <a href="https://observatoriodetaxas.tec.br/guias/">Guias</a> ·
  <a href="https://observatoriodetaxas.tec.br/var.html">VAR</a> ·
  <a href="https://observatoriodetaxas.tec.br/data/series.json">Dados (JSON)</a> ·
  <a href="https://chatgpt.com/plugins/plugin_asdk_app_6af615624cb08191ae41993bad0b6279">Plugin no ChatGPT</a> ·
  <a href="https://observatoriodetaxas.tec.br/mcp/">MCP</a> ·
  <a href="desenvolvimento/GUIA.md">Guia do desenvolvedor</a> ·
  <a href="https://observatoriodetaxas.tec.br/apoie/">Apoie</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/c%C3%B3digo-MIT-green" alt="Licença do código: MIT"></a>
  <a href="LICENSE-DADOS.md"><img src="https://img.shields.io/badge/dados-ODbL%201.0%20(BCB)-blue" alt="Licença das séries do Banco Central: ODbL 1.0"></a>
  <a href="https://github.com/iosbilario/observatorio-taxas/actions/workflows/monitor.yml"><img src="https://img.shields.io/github/actions/workflow/status/iosbilario/observatorio-taxas/monitor.yml?label=coleta" alt="Status da coleta automática (monitor.yml)"></a>
  <a href="https://github.com/iosbilario/observatorio-taxas/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/iosbilario/observatorio-taxas/validate.yml?label=testes" alt="Status dos testes (validate.yml)"></a>
  <a href="https://github.com/iosbilario/observatorio-taxas/releases/latest"><img src="https://img.shields.io/github/v/release/iosbilario/observatorio-taxas?label=release" alt="Versão mais recente"></a>
  <a href="desenvolvimento/GUIA.md"><img src="https://img.shields.io/badge/python-%E2%89%A53.12-blue" alt="Python 3.12 ou superior"></a>
  <a href="https://github.com/iosbilario/observatorio-taxas/commits/main"><img src="https://img.shields.io/github/last-commit/iosbilario/observatorio-taxas?label=%C3%BAltimo%20commit" alt="Data do último commit"></a>
  <a href="https://github.com/iosbilario/observatorio-taxas/stargazers"><img src="https://img.shields.io/github/stars/iosbilario/observatorio-taxas?style=social" alt="Estrelas no GitHub"></a>
  <br>
  <a href="https://observatoriodetaxas.tec.br/"><img src="https://img.shields.io/website?url=https%3A%2F%2Fobservatoriodetaxas.tec.br&label=site" alt="Situação do site"></a>
  <a href="https://observatoriodetaxas.tec.br/indicadores/"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fobservatoriodetaxas.tec.br%2Fdata%2Fseries.json&query=%24.length&label=s%C3%A9ries&color=1B5FAB" alt="Número de séries acompanhadas"></a>
  <a href="https://observatoriodetaxas.tec.br/data/meta.json"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fobservatoriodetaxas.tec.br%2Fdata%2Fmeta.json&query=%24.gerado_em_fmt&label=%C3%BAltima%20coleta&color=111113" alt="Horário da última coleta com mudança"></a>
  <a href="https://doi.org/10.5281/zenodo.24151062"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.24151062.svg" alt="DOI 10.5281/zenodo.24151062 (todas as versões, Zenodo)"></a>
  <a href="https://refy.design/"><img src="https://img.shields.io/badge/design-Refy%20Design-B9431D" alt="Interface feita com o Refy Design"></a>
</p>

O Observatório de Taxas publica indicadores econômicos do Brasil (Selic,
IPCA, INPC, IGP-M, CDI, câmbio, crédito, desemprego e outros, 25 séries) com o histórico completo de
cada número. Um robô coleta as séries a cada 6 horas e grava cada mudança como
um commit neste repositório. O site é estático, gratuito e sem cadastro, com
modo claro e escuro feitos com o [Refy Design](https://refy.design/).

## Conheça o Observatório

Quem precisa reajustar um aluguel, corrigir um valor ou conferir uma
afirmação sobre a economia costuma encontrar o número do mês, mas não o
caminho até ele: de onde veio, quando mudou, como foi calculado.

O Observatório guarda esse caminho:

- **Dados oficiais.** Os números vêm da API pública do SGS (Sistema
  Gerenciador de Séries Temporais) do Banco Central, que distribui séries
  próprias e de outros órgãos. Cada página diz quem produz o índice.
- **Histórico versionado.** Cada coleta que muda algum valor vira um commit.
  O histórico do Git é a linha do tempo de cada indicador, e qualquer número
  publicado pode ser conferido no ponto exato em que entrou.
- **Disponível em quatro formas.** Páginas em HTML (legíveis sem JavaScript),
  arquivos JSON em `/data/`, gráficos para incorporar em outros sites e um
  servidor MCP para assistentes como ChatGPT e Claude.
- **Feito para ler.** A página inicial responde as perguntas do dia ("Qual é a
  Selic hoje?", "Quanto vai subir o aluguel?") em uma frase, com o número, a
  variação no mês (▲ ▼ ■) e a data de referência. Cada mês de reajuste traz uma
  leitura própria, e seis guias explicam como usar os números.
- **Independente e gratuito.** O site é estático, sem banco de dados e sem
  anúncios. O servidor MCP roda à parte, no plano gratuito do Render, e só lê
  os JSON que o site publica. Projeto mantido pela LBP Tecnologia.

## Ferramentas

| Ferramenta | O que faz | Link |
| --- | --- | --- |
| Painel | As cinco perguntas do dia (Selic, inflação, dólar, aluguel, desemprego) respondidas em uma frase, com variação no mês, e mais 12 indicadores | [observatoriodetaxas.tec.br](https://observatoriodetaxas.tec.br/) |
| Indicadores | Uma página por série (25) com valor atual, contexto, últimos 12 meses e ficha técnica, mais uma tabela com todas | [/indicadores/](https://observatoriodetaxas.tec.br/indicadores/) |
| Comparador | Selic, CDI e IPCA acumulados em qualquer período, com gráfico, tabela mês a mês e link compartilhável | [/comparador/](https://observatoriodetaxas.tec.br/comparador/) |
| Simulador de CDI | Quanto rende X% do CDI com a taxa DI diária, IR e IOF do CDB, inflação do período e memória de cálculo em CSV | [/simulador-cdi/](https://observatoriodetaxas.tec.br/simulador-cdi/) |
| Reajuste de contratos | Acumulado de 12 meses, fator e calculadora por índice e mês: uma página para cada mês desde dezembro de 2015, com a leitura do mês (o que mudou e por quê, posição no histórico, comparação com os outros índices) | [/reajuste/](https://observatoriodetaxas.tec.br/reajuste/) |
| Correção monetária | Atualiza um valor entre duas datas pelo IPCA, IGP-M, INPC ou IGP-DI | [/correcao/](https://observatoriodetaxas.tec.br/correcao/) |
| Guias | Reajuste de aluguel, IPCA x INPC x IGP-M x IGP-DI, cálculo do acumulado, correção monetária, Selic e dólar PTAX, com exemplos atualizados a cada coleta | [/guias/](https://observatoriodetaxas.tec.br/guias/) |
| Rebobinar | A economia mês a mês, como uma linha do tempo de commits | [/rebobinar.html](https://observatoriodetaxas.tec.br/rebobinar.html) |
| VAR da Economia | Confere uma afirmação comparando dois períodos de uma série e emite um recibo com link permanente | [/var.html](https://observatoriodetaxas.tec.br/var.html) |
| Retransmissora | Gera o código para incorporar um gráfico que se atualiza sozinho | [/retransmissora.html](https://observatoriodetaxas.tec.br/retransmissora.html) |
| Dados abertos | Séries em JSON e manifesto de todas as séries | [/data/series.json](https://observatoriodetaxas.tec.br/data/series.json) |
| Servidor MCP | Consulta indicadores, séries e cálculos de dentro do ChatGPT, do Claude e de outros clientes MCP | [/mcp/](https://observatoriodetaxas.tec.br/mcp/) |

## Servidor MCP (ChatGPT e Claude)

Um servidor [MCP](https://modelcontextprotocol.io/) público, gratuito, sem
login e somente de leitura, em
`https://observatorio-taxas-mcp.onrender.com/mcp` (Streamable HTTP). O código
fica em [`servidor_mcp/`](servidor_mcp/).

| Ferramenta | O que faz |
| --- | --- |
| `get_latest_indicator` | Último valor publicado, com unidade, data de referência, data da coleta, produtor e código SGS |
| `get_indicator_history` | Série entre duas datas, até 500 pontos por chamada, com paginação |
| `calculate_adjustment` | Corrige um valor por um índice mensal entre dois meses, com fórmula e memória de cálculo |
| `compare_indicators` | Compara dois indicadores; só alinha ponto a ponto séries de mesma natureza e unidade |

- **Mesmos números do site.** O servidor lê os JSON publicados em `/data/` e
  importa as funções de cálculo do site (`fator_periodo` e `acumulado`). Não
  existe fórmula paralela.
- **Séries expostas:** só as do Banco Central (ODbL 1.0), incluindo crédito,
  reservas internacionais, dívida líquida e TJLP. IPCA, IPCA-15, INPC e
  desocupação (IBGE), IGP-M e IGP-DI (FGV IBRE) e CDI (B3) ficam suspensos no
  MCP até a confirmação dos termos de redistribuição com os produtores.
- **Privacidade:** recebe só os parâmetros da consulta, não grava parâmetros
  nem IP. Ver a [seção do MCP na política de privacidade](https://observatoriodetaxas.tec.br/privacidade/#mcp-t).
- **No ChatGPT:** o plugin oficial está no diretório desde 24/11/2026:
  [Observatório de Taxas no ChatGPT](https://chatgpt.com/plugins/plugin_asdk_app_6af615624cb08191ae41993bad0b6279).
  Guia de uso com telas reais, incluindo um alerta diário do dólar com tarefa
  agendada: [como usar o Observatório de Taxas no ChatGPT](https://lbptecnologia.com.br/blog/observatorio-de-taxas-no-chatgpt/).
- **No Claude e em outros clientes MCP:** passo a passo em
  [observatoriodetaxas.tec.br/mcp](https://observatoriodetaxas.tec.br/mcp/).
- **Custo:** R$ 0. Render Free num workspace sem cartão; o serviço dorme após
  15 minutos sem uso e leva cerca de 1 minuto para acordar.

Arquitetura, segurança, deploy e checklists de publicação:
[`servidor_mcp/README.md`](servidor_mcp/README.md).

## Interface

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme/observatorio-escuro.png">
    <img src="assets/readme/observatorio-claro.png" width="100%" alt="Captura da página inicial do Observatório de Taxas em 24/11/2026, modo claro: título Indicadores do Brasil, hoje, linha de coleta com o commit, as perguntas Qual é a Selic hoje (13,75% a.a., ■ 0,00 p.p. no mês), Qual é a inflação acumulada em 12 meses (4,63%, ▲ +0,05 p.p. no mês) e Quanto está o dólar hoje (R$ 5,8573, ▲ +R$ 0,4361 no mês), com minigráficos, e a coluna lateral com calculadoras, guias e atalhos.">
  </picture>
</p>
<p align="center"><sub>Página inicial em 24/11/2026, capturada do site publicado. O GitHub mostra a versão clara ou a escura conforme o seu tema.</sub></p>

## Design: feito com o Refy Design

A interface do Observatório usa o [**Refy Design**](https://refy.design/), um
design system open source (Apache 2.0) criado por
[Vinicius Coimbra](https://github.com/viniciuscoimbra). O Refy junta
componentes React e TypeScript, um pacote nativo para celular, templates prontos
e um catálogo que agentes de IA consultam pelo MCP antes de montar uma tela.
O tema inteiro (cor, fonte, raio, modo claro e escuro) fica num arquivo de tokens.

O Observatório mostra o Refy num cenário diferente do habitual. O site é HTML
estático gerado por Python, sem React. Mesmo assim, só os tokens bastaram para
redesenhar 574 páginas:

- [`docs/refy/tokens.css`](docs/refy/tokens.css) é o arquivo de tokens do
  `@refy-design/web` 1.11.0, servido pelo próprio site (a CSP continua
  `style-src 'self'`);
- [`docs/tema.css`](docs/tema.css) liga a paleta das páginas aos tokens do tema
  ativo, e [`docs/tema.js`](docs/tema.js) troca o modo claro e o escuro e
  lembra a escolha;
- as fontes (IBM Plex Serif, Manrope e Source Sans 3) vêm do pacote do Refy;
- a animação do título da página inicial, palavra por palavra, segue a do
  hero do [refy.design](https://refy.design/), feita só com CSS e desligada
  para quem pede menos movimento.

Para conhecer: [refy.design](https://refy.design/) ·
[código no GitHub](https://github.com/viniciuscoimbra/refy-design) (deixe uma ⭐) ·
[tema por arquivo](https://refy.design/docs) ·
[relato de um app feito com o Refy](https://lbptecnologia.com.br/blog/refy-design-meuconfere/).

## Arquitetura

```mermaid
flowchart TD
  A["config.yml<br/>séries monitoradas"] --> B["API SGS<br/>Banco Central"]
  B --> C["scripts/fetch.py<br/>coleta e funde"]
  C --> D[("data/*.json<br/>histórico versionado")]
  D --> E["Geradores Python<br/>reajuste, correção, indicadores,<br/>comparador, simulador, guias, sitemap"]
  E --> F["docs/<br/>HTML + JSON"]
  F --> G["GitHub Pages<br/>observatoriodetaxas.tec.br"]
  G --> H["IndexNow<br/>URLs alteradas"]
  G -- "/data/*.json" --> I["servidor_mcp/<br/>Render Free"]
  I --> J["ChatGPT, Claude<br/>e outros clientes MCP"]
  M{{"GitHub Actions<br/>monitor.yml, a cada 6 h"}} -.-> C
  M -.-> E
  M -. "commit + push" .-> D
```

Três camadas, com papéis diferentes:

| Camada | Onde | O que é |
| --- | --- | --- |
| Origem oficial | API do SGS | O dado como o Banco Central distribui. O Observatório não altera os valores. |
| Histórico versionado | `data/` | Um arquivo por série, fundido por data a cada coleta. É o armazenamento canônico. |
| Arquivos gerados | `docs/` | Páginas HTML, espelho dos JSONs e sitemap, reescritos a partir de `data/`. É o que o GitHub Pages publica. |
| Servidor MCP | `servidor_mcp/` | Lê os JSON publicados pelo site (cache de 10 min) e responde aos assistentes. Não consulta o SGS nem guarda estado. |

**Git como histórico temporal.** O `monitor.yml` só commita quando algum
arquivo muda, e os arquivos de `data/` só mudam quando o SGS traz valor novo
ou revisado. Assim, `git log -- data/189_history.json` mostra quando cada ponto
do IGP-M foi coletado ou revisado, e uma tag (`v1.4.0`, `v1.5.0`…) fixa o
estado de todas as séries numa data.

**Depois da publicação**, o `indexnow.yml` avisa os buscadores apenas das
URLs que mudaram, conferindo antes que o Pages já serve a versão nova
(ativo desde 13/11/2026; ver [`organic-discovery/INDEXNOW.md`](organic-discovery/INDEXNOW.md)).

## Dados e metodologia

| Índice | Produzido por | Série no SGS |
| --- | --- | --- |
| IPCA (mensal e 12 meses) | IBGE | 433, 13522 |
| INPC | IBGE | 188 |
| Taxa de desocupação (PNAD Contínua) | IBGE | 24369 |
| IPCA-15 | IBGE | 7478 |
| IGP-M, IGP-DI | FGV IBRE | 189, 190 |
| CDI (anualizado e acumulado no mês) | B3 | 4389, 4391 |
| Meta Selic, Selic anualizada, Selic acumulada no mês | Banco Central | 432, 1178, 4390 |
| TR, poupança (depósitos até 03/05/2012) | Banco Central | 226, 25 |
| Câmbio USD/BRL e EUR/BRL, IBC-Br | Banco Central | 1, 10813, 21619, 24363 |
| Poupança (depósitos desde 04/05/2012), TJLP | Banco Central | 195, 256 |
| Crédito: saldo, taxa média de juros, inadimplência | Banco Central | 20539, 20714, 21082 |
| Reservas internacionais, dívida líquida do setor público | Banco Central | 13621, 4513 |

O SGS do Banco Central distribui todas essas séries, mas o Banco Central não
produz o IPCA, o IPCA-15, o INPC, o IGP-M, o IGP-DI nem o CDI.

**Acumulados.** O acumulado de um período é composto, não somado:

```
acumulado = (1 + i₁/100) × (1 + i₂/100) × … × (1 + iₙ/100) − 1
```

O reajuste de 12 meses usa as 12 variações até o mês de referência
([`acumulado`](scripts/build_pages.py) em `scripts/build_pages.py`). A
correção entre datas aplica as variações dos meses posteriores ao inicial até
o final ([`fator_periodo`](scripts/build_correcao.py) em
`scripts/build_correcao.py`). O comparador compõe Selic, CDI e IPCA mês a mês,
e o simulador aplica o percentual do CDI à taxa DI de cada dia útil
([`docs/calculos.js`](docs/calculos.js); metodologia em
[`desenvolvimento/METODOLOGIA-FERRAMENTAS.md`](desenvolvimento/METODOLOGIA-FERRAMENTAS.md)). Os testes em [`tests/`](tests/) conferem a
fórmula contra a série oficial do IPCA 12 meses (SGS 13522) e garantem que os
valores publicados não mudam sem querer.

## Executando localmente

Requer Python 3.12 ou superior (o workflow usa 3.12). Os testes das
ferramentas de cálculo também usam Node.js, se estiver instalado.

```bash
git clone https://github.com/iosbilario/observatorio-taxas.git
cd observatorio-taxas
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install --require-hashes -r requirements.txt
```

```bash
python scripts/backfill.py                # opcional, uma vez: histórico desde 2015 (ou: backfill.py 2019)
python scripts/fetch.py                   # coleta os pontos novos em data/ e docs/data/
python scripts/build_pages.py             # páginas de reajuste
python scripts/build_correcao.py          # páginas de correção
python scripts/build_indicadores.py       # /indicadores/ (uma página por série)
python scripts/build_ferramentas.py       # /comparador/ e /simulador-cdi/
python scripts/build_guias.py             # /guias/
python scripts/render_index.py            # perguntas do dia na página inicial + sitemap
python scripts/sync_nav.py                # header, rodapé e tema claro/escuro em todas as páginas
python scripts/adsense.py                 # ads.txt; anúncios só se ligados em config.yml
python scripts/csp_hashes.py              # hashes da CSP
python scripts/build_og.py                # card social (og-image.png)
python -m unittest discover -s tests -v   # testes
python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Abra `http://127.0.0.1:8000`. Detalhes de cada script, da estrutura de pastas
e da configuração das séries estão no [Guia do desenvolvedor](desenvolvimento/GUIA.md).

Servidor MCP local, lendo o `data/` do repositório (ambiente virtual separado):

```bash
python -m venv .venv-mcp && source .venv-mcp/bin/activate
pip install --require-hashes -r servidor_mcp/requirements.txt
python -m unittest discover -s servidor_mcp/tests -t . -v
OBS_MCP_DADOS=data uvicorn servidor_mcp.servidor:app --host 127.0.0.1 --port 8000
```

O endpoint fica em `http://127.0.0.1:8000/mcp`. Para conferir um endpoint
publicado: `python -m servidor_mcp.conferir_endpoint https://observatorio-taxas-mcp.onrender.com/mcp`.

## Automações

| Workflow | Quando roda | O que faz |
| --- | --- | --- |
| [`monitor.yml`](.github/workflows/monitor.yml) | A cada 6 horas e sob demanda | Coleta as séries e as estrelas do repositório, gera as páginas, atualiza CSP e card social, e commita só se algo mudou |
| [`validate.yml`](.github/workflows/validate.yml) | Em pull requests | Roda os testes do site e do servidor MCP, regenera as páginas e confere que o resultado é igual ao commitado. Não toca na coleta |
| [`indexnow.yml`](.github/workflows/indexnow.yml) | Depois do monitor, em push na `main` e a cada 6 horas | Avisa os buscadores só das URLs alteradas, depois do deploy |
| [`mcp-acordado.yml`](.github/workflows/mcp-acordado.yml) | A cada 5 minutos, pelo agendamento | Chama o `/health` do servidor MCP para ele não dormir. O GitHub pode atrasar esse agendamento em horas, então o servidor às vezes leva cerca de 1 minuto para responder à primeira chamada |

O Render publica o servidor MCP sozinho (`render.yaml`) quando um commit na
`main` muda `servidor_mcp/` ou os scripts de cálculo.

O status de cada execução fica na aba [Actions](https://github.com/iosbilario/observatorio-taxas/actions).

## Como contribuir

- **Dado errado ou rótulo impreciso:** abra uma [issue](https://github.com/iosbilario/observatorio-taxas/issues)
  com a URL da página, a série (código SGS) e a fonte oficial que mostra o valor correto.
- **Problema no site:** [issue](https://github.com/iosbilario/observatorio-taxas/issues) com o endereço,
  o navegador e o que aconteceu.
- **Código:** abra um [pull request](https://github.com/iosbilario/observatorio-taxas/pulls).
  Altere os geradores em `scripts/` (não o HTML gerado em `docs/reajuste/` e
  `docs/correcao/`), rode o pipeline e os testes, e commite o resultado. O
  `validate.yml` confere isso no PR.
- **Segurança:** veja [`SECURITY.md`](SECURITY.md).

## Como citar e reutilizar

- **Citação:** botão *Cite this repository* do GitHub, a partir do [`CITATION.cff`](CITATION.cff).
  Cite também o produtor do índice (IBGE, FGV IBRE, B3 ou Banco Central).
- **Referência permanente a um dado:** use a versão. Ex.: IGP-M mensal como publicado na v1.4.0:
  [`blob/v1.4.0/data/189_history.json`](https://github.com/iosbilario/observatorio-taxas/blob/v1.4.0/data/189_history.json).
  A URL do site (`/data/189_history.json`) é sempre a versão mais recente.
- **Ponto no tempo exato:** cada coleta é um commit; o recibo do VAR traz o commit usado.
- **Arquivamento (Zenodo):** cada release é arquivada com DOI próprio. O pacote arquivado contém só o software; as séries ficam no repositório e no site. Ver [Citação acadêmica](#citação-acadêmica).

| O quê | Licença |
| --- | --- |
| Código | MIT ([`LICENSE`](LICENSE)) |
| Séries do Banco Central | ODbL 1.0, com atribuição ([`LICENSE-DADOS.md`](LICENSE-DADOS.md)) |
| IPCA, IPCA-15, INPC, desocupação (IBGE), IGP-M, IGP-DI (FGV IBRE), CDI (B3) | Termos dos produtores; não são relicenciadas ([`LICENSE-DADOS.md`](LICENSE-DADOS.md)) |
| Textos do site | CC BY 4.0, com atribuição |

## Citação acadêmica

O Observatório é software open source, não um artigo revisado por pares.
Para citar, use as referências abaixo conforme o que o trabalho precisa
reproduzir.

| O que citar | Quando usar | Onde obter |
| --- | --- | --- |
| **DOI da versão** | Resultado que precisa ser reproduzido com o mesmo código | v1.9.0: [10.5281/zenodo.24517515](https://doi.org/10.5281/zenodo.24517515). v1.8.0: [10.5281/zenodo.24208300](https://doi.org/10.5281/zenodo.24208300). v1.7.0: [10.5281/zenodo.24195784](https://doi.org/10.5281/zenodo.24195784). v1.6.0: [10.5281/zenodo.24151063](https://doi.org/10.5281/zenodo.24151063). Cada release nova recebe o seu |
| **DOI conceito** | Referência ao projeto em geral, sempre na versão mais recente | [10.5281/zenodo.24151062](https://doi.org/10.5281/zenodo.24151062) |
| **Commit Git** | Estado exato dos dados e das páginas num momento | `git log` ou o recibo do VAR, que traz o commit usado |
| **Data de referência dos indicadores** | Qual mês ou dia de cada série foi usado | Página do indicador ou `data/<codigo>_history.json` |

Cite também o produtor de cada índice usado (IBGE, FGV IBRE, B3 ou Banco Central).

Como citar a versão v1.9.0 (APA, no formato do Zenodo):

> Pereira, L. B. (2026). *Observatório de Taxas* (Version v1.9.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24517515

Para citar o projeto sem fixar a versão, use o DOI conceito
[10.5281/zenodo.24151062](https://doi.org/10.5281/zenodo.24151062). O botão *Cite this repository* do GitHub usa o
[`CITATION.cff`](CITATION.cff). Registro no Zenodo:
[zenodo.org/records/24517515](https://zenodo.org/records/24517515) (v1.9.0),
[zenodo.org/records/24208300](https://zenodo.org/records/24208300) (v1.8.0),
[zenodo.org/records/24195784](https://zenodo.org/records/24195784) (v1.7.0) e
[zenodo.org/records/24151063](https://zenodo.org/records/24151063) (v1.6.0).

O pacote arquivado no Zenodo contém só o software; os dados de cada versão
ficam no histórico do Git. Como refazer os resultados de uma versão:
[`desenvolvimento/REPRODUCAO.md`](desenvolvimento/REPRODUCAO.md). Como o
arquivamento funciona e como acompanhar: [`organic-discovery/ZENODO.md`](organic-discovery/ZENODO.md).

## Apoie o projeto

O Observatório é gratuito e continua gratuito. Se ele foi útil para você, uma
contribuição voluntária ajuda a manter a coleta, a infraestrutura e as
ferramentas: [observatoriodetaxas.tec.br/apoie](https://observatoriodetaxas.tec.br/apoie/).

---

<sub>Observatório de Taxas · LBP Tecnologia · Conteúdo informativo, sem caráter de recomendação financeira.</sub>
