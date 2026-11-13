# v1.8.0 — Indicadores, comparador e simulador de CDI

Esta versão amplia o Observatório de 15 para 25 séries, cria uma página
pública para cada indicador e acrescenta duas ferramentas de cálculo: o
comparador de Selic, CDI e IPCA e o simulador de rendimento do CDI. As
fórmulas e URLs existentes não mudaram; as calculadoras de reajuste e
correção dão os mesmos resultados da v1.7.0.

## Indicadores novos

Dez séries, com histórico desde 01/01/2015:

| SGS | Indicador | Produtor |
| --- | --- | --- |
| 195 | Poupança, depósitos a partir de 04/05/2012 | BCB |
| 4389 | CDI (taxa DI) anualizado, base 252 | B3 |
| 4391 | CDI acumulado no mês | B3 |
| 256 | TJLP | BCB |
| 7478 | IPCA-15 | IBGE |
| 20539 | Saldo da carteira de crédito | BCB |
| 20714 | Taxa média de juros do crédito | BCB |
| 21082 | Inadimplência do crédito | BCB |
| 13621 | Reservas internacionais | BCB |
| 4513 | Dívida líquida do setor público (% do PIB) | BCB |

Nomes e licença conferidos no Portal de Dados Abertos do BCB onde a série
aparece. No servidor MCP, as séries do BCB ficam expostas; CDI (B3) e
IPCA-15 (IBGE) ficam suspensos pela mesma regra de licenciamento do IPCA.

## Vitrine /indicadores/

- Hub com as 25 séries agrupadas, valor atual, referência, produtor e código SGS.
- Uma página por série (`/indicadores/<slug>/`): resposta na primeira frase,
  números de contexto, o que o indicador mede, últimos 12 meses, ficha
  técnica, gráfico, perguntas e respostas e JSON-LD Dataset, FAQPage e
  BreadcrumbList.
- Selic e CDI acumulados no mês excluem o mês corrente ainda parcial.

## Comparador /comparador/

Selic acumulada no mês (4390), CDI acumulado no mês (4391) e IPCA mensal (433)
compostos por competência: `fator = Π (1 + taxa ÷ 100)`. Períodos de 12 a 60
meses ou personalizados, gráfico, tabela mês a mês, R$ 1.000 corrigidos, taxa
real e link compartilhável.

## Simulador /simulador-cdi/

X% do CDI com a taxa DI diária (4389): `fator(d) = 1 + p × ((1 + DI)^(1/252) − 1)`.
IR regressivo (Lei 11.033/2004) e IOF (Decreto 6.306/2007) do CDB de pessoa
física, inflação do período, rentabilidade real, poder de compra e memória de
cálculo diária em CSV. Regras conferidas em 13/11/2026. Metodologia em
`desenvolvimento/METODOLOGIA-FERRAMENTAS.md`.

## Site

- Rodapé em colunas (Produto, Documentação, Para IAs, Projeto) em todas as páginas.
- Botão do GitHub com contador de estrelas no header, atualizado pelo robô a cada 6 horas.
- Item "Indicadores" no menu.
- IndexNow ativado: o primeiro envio mandou 43 URLs; a partir daí, cada coleta e cada merge avisam só as páginas que mudaram.
- Com anúncios ligados, os scripts de mesma origem continuam carregando sob a CSP estrita do AdSense (anúncios seguem desligados).

## Licenças e conteúdo arquivado

Código sob MIT; dados sob os termos de cada produtor (`LICENSE-DADOS.md`,
atualizado com as séries novas e a B3). O pacote arquivado no Zenodo contém só
o software; `data/` e as páginas geradas com valores ficam fora via
`.gitattributes`.

## Reprodução

- **Histórica:** `git checkout v1.8.0` e rodar os geradores sem coletar
  (passo a passo em `desenvolvimento/REPRODUCAO.md`).
- **Ferramentas:** `node` executa `docs/calculos.js`, o mesmo arquivo servido ao navegador.

## Testes

156 testes do site e 48 do servidor MCP. As ferramentas são conferidas contra
uma reimplementação em `Decimal` e contra as séries oficiais (CDI mensal 4391 e
IPCA 12 meses 13522).

## Limitações conhecidas

- Comparador com granularidade mensal; séries mensais com 2 casas podem diferir em centésimos de cálculos com números-índice.
- Simulador sem custos, risco do emissor, FGC ou carência; líquido só para CDB pessoa física.
- Inflação do simulador por meses inteiros.
- Os dados são coletados a cada 6 horas, não em tempo real.
