<p align="center">
  <a href="https://observatoriodetaxas.tec.br/"><img src="assets/readme/banner.svg" width="100%" alt="Observatório de Taxas. Os números mudam. O histórico fica. Indicadores econômicos brasileiros, séries históricas versionadas e ferramentas gratuitas para consulta, comparação e cálculo."></a>
</p>

<p align="center">
  <a href="https://observatoriodetaxas.tec.br/"><b>Site</b></a> ·
  <a href="https://observatoriodetaxas.tec.br/reajuste/">Reajuste</a> ·
  <a href="https://observatoriodetaxas.tec.br/correcao/">Correção monetária</a> ·
  <a href="https://observatoriodetaxas.tec.br/var.html">VAR</a> ·
  <a href="https://observatoriodetaxas.tec.br/data/series.json">Dados (JSON)</a> ·
  <a href="https://observatoriodetaxas.tec.br/mcp/">MCP (ChatGPT e Claude)</a> ·
  <a href="desenvolvimento/GUIA.md">Guia do desenvolvedor</a> ·
  <a href="https://observatoriodetaxas.tec.br/apoie/">Apoie</a>
</p>

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.24151062"><img src="https://zenodo.org/badge/DOI/10.5281/zenodo.24151062.svg" alt="DOI 10.5281/zenodo.24151062 (todas as versões, Zenodo)"></a>
</p>

O Observatório de Taxas publica indicadores econômicos do Brasil (Selic,
IPCA, INPC, IGP-M, CDI, câmbio, crédito, desemprego e outros, 25 séries) com o histórico completo de
cada número. Um robô coleta as séries a cada 6 horas e grava cada mudança como
um commit neste repositório. O site é estático, gratuito e sem cadastro.

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
- **Independente e gratuito.** O site é estático, sem banco de dados e sem
  anúncios. O servidor MCP roda à parte, no plano gratuito do Render, e só lê
  os JSON que o site publica. Projeto mantido pela LBP Tecnologia.

## Ferramentas

| Ferramenta | O que faz | Link |
| --- | --- | --- |
| Indicadores | Uma página por série (25) com valor atual, contexto, últimos 12 meses, ficha técnica e JSON-LD Dataset e FAQPage, mais uma tabela com todas | [/indicadores/](https://observatoriodetaxas.tec.br/indicadores/) |
| Painel | Os números do dia (Selic, IPCA 12 meses, dólar, IGP-M, desemprego) com variação no mês | [observatoriodetaxas.tec.br](https://observatoriodetaxas.tec.br/) |
| Reajuste de contratos | Acumulado de 12 meses, fator e calculadora por índice e mês: uma página para cada mês desde dezembro de 2015 | [/reajuste/](https://observatoriodetaxas.tec.br/reajuste/) |
| Correção monetária | Atualiza um valor entre duas datas pelo IPCA, IGP-M, INPC ou IGP-DI | [/correcao/](https://observatoriodetaxas.tec.br/correcao/) |
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
- **Como conectar:** passo a passo para o ChatGPT (Plugins) e o Claude
  (Customize → Connectors) em [observatoriodetaxas.tec.br/mcp](https://observatoriodetaxas.tec.br/mcp/).
  Em 13/11/2026, o plugin está em revisão no diretório da OpenAI e o conector,
  no diretório do Claude.
- **Custo:** R$ 0. Render Free num workspace sem cartão; o serviço dorme após
  15 minutos sem uso e leva cerca de 1 minuto para acordar.

Arquitetura, segurança, deploy e checklists de publicação:
[`servidor_mcp/README.md`](servidor_mcp/README.md).

## Interface

<p align="center">
  <img src="assets/readme/observatorio-desktop.png" width="100%" alt="Captura da página inicial do Observatório de Taxas em 11/11/2026: título, data, linha de coleta com o commit, cinco indicadores do dia (Meta Selic 13,75% a.a., IPCA 12 meses 4,58%, dólar R$ 5,5840, IGP-M 1,47% no mês, desemprego 5,2%) com minigráficos e, abaixo, o bloco do Rebobinar.">
</p>
<p align="center"><sub>Página inicial em 11/11/2026, capturada do site publicado.</sub></p>

## Arquitetura

```mermaid
flowchart TD
  A["config.yml<br/>séries monitoradas"] --> B["API SGS<br/>Banco Central"]
  B --> C["scripts/fetch.py<br/>coleta e funde"]
  C --> D[("data/*.json<br/>histórico versionado")]
  D --> E["Geradores Python<br/>reajuste, correção,<br/>landing, sitemap"]
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
(primeira execução manual; ver [`organic-discovery/INDEXNOW.md`](organic-discovery/INDEXNOW.md)).

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
`scripts/build_correcao.py`). Os testes em [`tests/`](tests/) conferem a
fórmula contra a série oficial do IPCA 12 meses (SGS 13522) e garantem que os
valores publicados não mudam sem querer.

## Executando localmente

Requer Python 3.12 ou superior (o workflow usa 3.12).

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
python scripts/render_index.py            # boletim da página inicial + sitemap
python scripts/sync_nav.py                # header em todas as páginas
python scripts/adsense.py                 # ads.txt; anúncios só se ligados em config.yml
python scripts/csp_hashes.py              # hashes da CSP
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
| [`monitor.yml`](.github/workflows/monitor.yml) | A cada 6 horas e sob demanda | Coleta as séries, gera as páginas, atualiza CSP e card social, e commita só se algo mudou |
| [`validate.yml`](.github/workflows/validate.yml) | Em pull requests | Roda os testes do site e do servidor MCP, regenera as páginas e confere que o resultado é igual ao commitado. Não toca na coleta |
| [`indexnow.yml`](.github/workflows/indexnow.yml) | Depois do monitor, em push na `main` e a cada 6 horas | Avisa os buscadores só das URLs alteradas, depois do deploy |
| [`mcp-acordado.yml`](.github/workflows/mcp-acordado.yml) | A cada 5 minutos (temporário) | Chama o `/health` do servidor MCP para ele não dormir durante a revisão dos diretórios. Será desligado depois das aprovações |

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
  Cite também o produtor do índice (IBGE, FGV IBRE ou Banco Central).
- **Referência permanente a um dado:** use a versão. Ex.: IGP-M mensal como publicado na v1.4.0:
  [`blob/v1.4.0/data/189_history.json`](https://github.com/iosbilario/observatorio-taxas/blob/v1.4.0/data/189_history.json).
  A URL do site (`/data/189_history.json`) é sempre a versão mais recente.
- **Ponto no tempo exato:** cada coleta é um commit; o recibo do VAR traz o commit usado.
- **Arquivamento (Zenodo):** cada release é arquivada com DOI próprio. O pacote arquivado contém só o software; as séries ficam no repositório e no site. Ver [Citação acadêmica](#citação-acadêmica).

| O quê | Licença |
| --- | --- |
| Código | MIT ([`LICENSE`](LICENSE)) |
| Séries do Banco Central | ODbL 1.0, com atribuição ([`LICENSE-DADOS.md`](LICENSE-DADOS.md)) |
| IPCA, INPC, desocupação (IBGE), IGP-M, IGP-DI (FGV IBRE) | Termos dos produtores; não são relicenciadas ([`LICENSE-DADOS.md`](LICENSE-DADOS.md)) |
| Textos do site | CC BY 4.0, com atribuição |

## Citação acadêmica

O Observatório é software open source, não um artigo revisado por pares.
Para citar, use as referências abaixo conforme o que o trabalho precisa
reproduzir.

| O que citar | Quando usar | Onde obter |
| --- | --- | --- |
| **DOI da versão** | Resultado que precisa ser reproduzido com o mesmo código | v1.7.0: [10.5281/zenodo.24195784](https://doi.org/10.5281/zenodo.24195784). v1.6.0: [10.5281/zenodo.24151063](https://doi.org/10.5281/zenodo.24151063). Cada release nova recebe o seu |
| **DOI conceito** | Referência ao projeto em geral, sempre na versão mais recente | [10.5281/zenodo.24151062](https://doi.org/10.5281/zenodo.24151062) |
| **Commit Git** | Estado exato dos dados e das páginas num momento | `git log` ou o recibo do VAR, que traz o commit usado |
| **Data de referência dos indicadores** | Qual mês ou dia de cada série foi usado | Página do indicador ou `data/<codigo>_history.json` |

Cite também o produtor de cada índice usado (IBGE, FGV IBRE ou Banco Central).

Como citar a versão v1.7.0 (APA, no formato do Zenodo):

> Pereira, L. B. (2026). *Observatório de Taxas* (Version v1.7.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24195784

Para citar o projeto sem fixar a versão, use o DOI conceito
[10.5281/zenodo.24151062](https://doi.org/10.5281/zenodo.24151062). O botão *Cite this repository* do GitHub usa o
[`CITATION.cff`](CITATION.cff). Registro no Zenodo:
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
