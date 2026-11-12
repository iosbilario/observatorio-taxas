# v1.6.0 — Primeira versão arquivada no Zenodo

Primeira release do Observatório de Taxas arquivada no Zenodo, com DOI. É uma
release de software open source; não é artigo científico nem foi revisada por
pares.

## O que é o Observatório

Software de engenharia de dados que coleta indicadores econômicos brasileiros
na API pública do SGS do Banco Central a cada 6 horas, versiona as séries em
Git (um commit por mudança de valor) e gera um site estático em
https://observatoriodetaxas.tec.br/ com ferramentas gratuitas.

## Funcionalidades

- **Painel do dia:** Selic, IPCA 12 meses, dólar, IGP-M e desemprego, no HTML sem JavaScript.
- **Reajuste de contratos:** acumulado de 12 meses, fator e calculadora para cada índice e mês desde dezembro de 2015 (IPCA, IGP-M, INPC, IGP-DI).
- **Correção monetária** entre duas datas.
- **Rebobinar** (linha do tempo mensal), **VAR da Economia** (recibo verificável de uma afirmação) e **Retransmissora** (gráficos incorporáveis).
- **Dados abertos** em JSON (`/data/`).

## Arquitetura

`config.yml` → API SGS → `scripts/fetch.py` → `data/*.json` (histórico
versionado) → geradores Python → `docs/` → GitHub Pages → IndexNow.
Workflows: `monitor.yml` (a cada 6 h), `validate.yml` (pull requests) e
`indexnow.yml` (após a publicação).

## Novidades desde a v1.5.0

- Carrossel de indicadores na Retransmissora; fonte correta (IBGE, FGV IBRE) no rodapé dos gráficos incorporados.
- Página de apoio voluntário via Pix (`/apoie/`), com o código validado (EMV, CRC16).
- Páginas Sobre e Política de privacidade; `ads.txt` publicado; espaços de anúncio preparados e desligados.
- Calculadoras sem handlers inline (compatíveis com CSP por hash), com resultados idênticos.
- README redesenhado, guia do desenvolvedor, guia de reprodução e preparação para o Zenodo.

## Origem dos dados

Todas as séries vêm do SGS do Banco Central. IPCA, INPC e a taxa de
desocupação são produzidos pelo IBGE; IGP-M e IGP-DI, pela FGV IBRE; Selic, TR,
poupança, câmbio e IBC-Br, pelo Banco Central.

## Licenças e conteúdo arquivado

- **Código:** MIT.
- **Dados:** não estão sob a MIT. Séries do BCB sob ODbL 1.0; IBGE e FGV IBRE
  seguem os termos dos produtores. Ver `LICENSE-DADOS.md`.
- **O pacote arquivado no Zenodo contém só o software.** `data/`, `docs/data/`,
  as páginas geradas com valores e o `CHANGELOG.md` ficam fora via
  `.gitattributes` (`export-ignore`). Eles continuam no repositório e no site.

## Instalação

```bash
git clone https://github.com/iosbilario/observatorio-taxas.git
cd observatorio-taxas
python3.12 -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements.txt
```

## Reprodução

- **Histórica:** `git checkout v1.6.0` e rodar os geradores sem coletar
  (passo a passo em `desenvolvimento/REPRODUCAO.md`).
- **Atualização:** `scripts/fetch.py` consulta o SGS de novo e pode trazer
  pontos novos ou revisados; o resultado pode diferir desta release.

## Limitações conhecidas

- Sem data oficial de divulgação dos índices; o projeto registra a data de referência e a coleta.
- Acumulados compostos de variações com 2 casas podem diferir em centésimos de ponto percentual dos divulgados pelos produtores.
- O pacote do Zenodo não traz os dados; a reprodução histórica depende do repositório Git.
- O Rebobinar monta o conteúdo com JavaScript.

## Testes

Suíte em `tests/` (unittest, stdlib): fórmulas contra a série oficial do IPCA
12 meses, valores publicados contra a linha de base, SEO, Pix, AdSense,
IndexNow, licenças e conteúdo do pacote arquivado.
