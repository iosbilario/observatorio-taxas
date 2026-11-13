# Metodologia: Comparador e Simulador de CDI

Páginas: [/comparador/](https://observatoriodetaxas.tec.br/comparador/) e
[/simulador-cdi/](https://observatoriodetaxas.tec.br/simulador-cdi/).
Código: `docs/calculos.js` (cálculo, também usado pelos testes),
`docs/comparador.js` e `docs/simulador-cdi.js` (interface),
`scripts/build_ferramentas.py` (HTML estático e exemplo pré-calculado).

## Séries: quais entram em cálculo

| Série | SGS | Natureza | Uso nas ferramentas |
| --- | --- | --- | --- |
| Meta Selic | 432 | Meta anual do Copom (% a.a.) | **Não entra.** É política monetária, não uma taxa acumulada em período nenhum. |
| Selic efetiva anualizada | 1178 | Taxa diária anualizada, base 252 | Só para conferência e para a diferença Selic × CDI no texto do comparador. |
| Selic acumulada no mês | 4390 | % no mês, 2 casas | **Comparador.** Composta mês a mês. |
| CDI (taxa DI) anualizado | 4389 | Taxa diária anualizada, base 252 (B3) | **Simulador.** Única série que permite aplicar "X% do CDI" corretamente e usar datas exatas. |
| CDI acumulado no mês | 4391 | % no mês, 2 casas (B3) | **Comparador.** Composta mês a mês. |
| IPCA mensal | 433 | Variação no mês (IBGE) | **Comparador e inflação do simulador.** Composta mês a mês. |
| IPCA em 12 meses | 13522 | Já acumulado (IBGE) | **Não entra.** Compô-lo de novo contaria a inflação mais de uma vez. Usado nos testes como conferência. |

Conferências feitas na auditoria (13/11/2026):

- A taxa DI diária (4389) composta dentro de cada mês reproduz o CDI
  acumulado no mês (4391) com diferença máxima de 0,005 p.p. em 24 meses,
  efeito do arredondamento a 2 casas da série mensal. O mesmo vale para
  1178 × 4390.
- Neste período, Selic efetiva e CDI coincidem dia a dia (13,65% a.a. em
  novembro de 2026), por isso o comparador mostra o mesmo acumulado para os
  dois. Não é erro: é o dado publicado.
- Aplicar 90% sobre o CDI acumulado no mês, em vez de sobre a taxa de cada dia,
  muda o resultado de 2025 em 0,015 p.p. O simulador usa sempre a taxa diária.

## Comparador

Competências do mês inicial ao mês final, **inclusive**:

```
fator    = Π (1 + taxa do mês ÷ 100)
variação = (fator − 1) × 100
real     = (1 + CDI) ÷ (1 + IPCA) − 1
```

- As três séries são mensais e têm a mesma natureza (taxa ou variação que vale
  para o próprio mês), então a composição é válida.
- O mês corrente da Selic e do CDI acumulados no mês é parcial enquanto a série
  diária correspondente tiver dias nesse mês; ele fica de fora
  (`build_indicadores.completos`). O mês final máximo é o último fechado comum
  às séries escolhidas.
- Falta de qualquer competência numa série escolhida interrompe o cálculo com
  mensagem; nada é estimado.
- "R$ 1.000 corrigidos" é R$ 1.000 × fator. Para o IPCA, significa o custo, no
  fim do período, do que custava R$ 1.000 no início, e não rendimento.
- Convenção diferente da calculadora de correção (`/correcao/`), que aplica os
  meses **posteriores** ao inicial. O comparador inclui o mês inicial porque
  o usuário escolhe competências, não datas de contrato.

## Simulador

Para cada dia útil `d` com taxa DI publicada, de `aplicação` (inclusive) a
`resgate` (exclusive):

```
fator_DI(d) = (1 + DI(d) ÷ 100)^(1/252)
fator(d)    = 1 + (percentual ÷ 100) × (fator_DI(d) − 1)
saldo       = valor × Π fator(d)
```

- O percentual é aplicado à taxa de cada dia **antes** da composição; 110%
  do CDI não é 1,10 × o rendimento de 100% (a página mostra a diferença).
- Dias sem taxa (fins de semana, feriados, Carnaval) não rendem e não são
  interpolados.
- Resgate depois do dia seguinte à última taxa DI publicada é recusado.
- Períodos rápidos terminam no dia seguinte à última taxa publicada e começam
  N meses antes, no mesmo dia do mês.

### Tributos (CDB, pessoa física), conferidos em 13/11/2026

- **IR**: Lei 11.033/2004, art. 1º, sobre o rendimento, por dias corridos
  entre aplicação e resgate: 22,5% até 180; 20% de 181 a 360; 17,5% de 361 a
  720; 15% acima de 720. A MP 1.303/2025, que propunha alíquota única, perdeu
  a validade; fontes de outubro e novembro de 2026 confirmam a tabela.
- **IOF**: Decreto 6.306/2007, art. 32 e anexo, sobre o rendimento, em resgates
  com 1 a 29 dias corridos: 96%, 93%, 90%, 86%, 83%, 80%, 76%, 73%, 70%, 66%,
  63%, 60%, 56%, 53%, 50%, 46%, 43%, 40%, 36%, 33%, 30%, 26%, 23%, 20%, 16%,
  13%, 10%, 6%, 3%; zero a partir de 30 dias. Os decretos de 2025 sobre IOF
  mudaram crédito, câmbio e previdência, não esta tabela.
- O IR incide sobre o rendimento menos o IOF. Cada tributo é arredondado para
  centavos (meio centavo para cima). Rendimento zero ou negativo não gera
  imposto.
- **Não calculados**: LCI e LCA (isentas de IR para pessoa física, mas com
  carência e regras próprias), fundos (come-cotas), pessoa jurídica. Para esses
  casos o simulador mostra só o valor bruto.

### Inflação e poder de compra

IPCA das competências do mês da aplicação ao mês anterior ao do resgate.
É aproximação: aplicações no meio do mês contam o mês inteiro. Se faltar o IPCA
de algum desses meses, a taxa real e o poder de compra não são exibidos.

```
real            = (1 + rentabilidade nominal) ÷ (1 + IPCA) − 1
poder de compra = valor final ÷ fator do IPCA
```

### Arredondamento

O cálculo usa precisão de ponto flutuante em todas as etapas e arredonda só o
que é exibido. Instituições truncam fatores diários com regras próprias; o
extrato pode diferir em centavos.

## Parâmetros de URL

| Página | Parâmetro | Formato |
| --- | --- | --- |
| comparador | `de`, `ate` | `aaaa-mm` |
| comparador | `meses` | 12, 24, 36 ou 60 |
| comparador | `i` | lista de `cdi`, `selic`, `ipca` |
| comparador | `ver` | `pct` ou `reais` |
| simulador | `valor` | número até 1 bilhão, até 2 casas |
| simulador | `percentual` | 0,01 a 300 |
| simulador | `periodo` | `6m`, `12m`, `24m`, `36m`, `60m` |
| simulador | `de`, `ate` | `aaaa-mm-dd` (substituem `periodo`) |
| simulador | `modo` | `liquido` ou `bruto` |

Qualquer outro valor é ignorado. Nada da URL é inserido como HTML. A
canonical é sempre a URL da ferramenta sem parâmetros, e o sitemap só tem as
duas URLs principais.

## Limitações

- Comparador mensal: a granularidade mínima é o mês; para datas exatas, use o
  simulador.
- Séries mensais com 2 casas decimais: acumulados podem diferir em centésimos
  dos calculados com números-índice ou taxas diárias.
- Simulador não considera custos, spread, risco do emissor, FGC, marcação a
  mercado nem regras de carência.
- A tabela de tributos é fixa no código, com a data da conferência. Mudança de
  legislação exige atualizar `docs/calculos.js` e os testes.

## Testes

- `tests/test_ferramentas_calc.py`: executa `docs/calculos.js` em node e compara
  com uma reimplementação em `Decimal` e com séries oficiais (4391 e 13522).
- `tests/test_ferramentas_paginas.py`: HTML, SEO, JSON-LD × texto visível,
  links, sitemap, tabelas responsivas, exemplo estático contra `Decimal`,
  espaços de anúncio e funcionamento com anúncios ligados.
