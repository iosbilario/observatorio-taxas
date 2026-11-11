# Dados e textos: termos de uso

O Observatório de Taxas **não é dono** da maior parte dos números que publica.
Ele coleta as séries na API pública do SGS (Sistema Gerenciador de Séries
Temporais) do Banco Central do Brasil, e o SGS redistribui séries que outros
órgãos produzem. Por isso não existe uma licença única para os dados: cada
série segue os termos de quem a publica e de quem a produz.

O código do repositório (scripts/, tests/, .github/, partials/ e o código HTML,
CSS e JavaScript das páginas em docs/) está sob a licença MIT (arquivo
`LICENSE`). A MIT não cobre os dados nem os textos descritos abaixo.

## 1. Séries do Banco Central do Brasil

| Série SGS | Conteúdo |
| --- | --- |
| 432 | Meta Selic |
| 1178 | Selic anualizada |
| 4390 | Selic acumulada no mês |
| 226 | TR |
| 25 | Poupança, rentabilidade dos depósitos até 03/05/2012 (regra antiga) |
| 1, 10813, 21619 | Câmbio USD/BRL venda e compra, EUR/BRL venda |
| 24363 | IBC-Br |

O Banco Central publica essas séries no
[Portal de Dados Abertos do BCB](https://dadosabertos.bcb.gov.br/) sob a
**Open Data Commons Open Database License (ODbL) 1.0**
([texto](https://opendatacommons.org/licenses/odbl/1-0/)). Conferido em
11/11/2026 pela API do portal (`license_id: odc-odbl`) nas séries 432, 1178,
4390, 25, 1, 10813 e 24363. As séries 226 (TR) e 21619 (EUR) não foram
localizadas na busca do portal; são produzidas pelo BCB e o Observatório as
trata nos mesmos termos, com atribuição.

A cópia dessas séries em `data/` e `docs/data/` é redistribuída nos mesmos
termos: **ODbL 1.0, com atribuição "Fonte: Banco Central do Brasil (SGS)"**.
A ODbL exige atribuição e que bases derivadas publicadas fiquem sob a mesma
licença.

## 2. Séries de outros produtores, redistribuídas pelo SGS

| Série SGS | Índice | Produtor |
| --- | --- | --- |
| 433, 13522 | IPCA (mensal e 12 meses) | IBGE |
| 188 | INPC | IBGE |
| 24369 | Taxa de desocupação (PNAD Contínua) | IBGE |
| 189 | IGP-M | FGV IBRE |
| 190 | IGP-DI | FGV IBRE |

Essas séries **não** aparecem com licença no Portal de Dados Abertos do BCB
(busca pelos códigos em 11/11/2026 sem resultado). O Observatório **não as
relicencia**: o uso segue os termos de cada produtor, e qualquer reutilização
deve citar o produtor (IBGE ou FGV IBRE) e o canal (SGS do Banco Central).

Os termos de uso do portal da FGV IBRE restringem a reprodução do conteúdo do
portal sem autorização. O Observatório não copia conteúdo desse portal; obtém
os valores agregados mensais pelo SGS, onde são públicos. Quem pretende
redistribuir IGP-M ou IGP-DI em escala ou com fins comerciais deve consultar
a FGV IBRE.

## 3. Valores calculados pelo Observatório

Acumulados de 12 meses, fatores de reajuste e de correção e tabelas de
memória de cálculo são derivados das séries acima por fórmula documentada
(produto de 1 + variação mensal ÷ 100, menos 1). Valem para eles os mesmos
termos da série de origem: ODbL para as séries do BCB; termos do produtor,
com citação, para IBGE e FGV IBRE. O Observatório não reivindica direito
exclusivo sobre esses cálculos.

## 4. Textos e páginas do site

Os textos explicativos das páginas de observatoriodetaxas.tec.br (ficha
técnica, perguntas e respostas, metodologia), excluídos os dados das seções
1 a 3, estão sob **Creative Commons Atribuição 4.0 (CC BY 4.0)**
([texto](https://creativecommons.org/licenses/by/4.0/deed.pt-br)), com
atribuição "Observatório de Taxas (LBP Tecnologia)" e link para a página.
A marca "Observatório de Taxas" e a identidade visual não estão incluídas.

## Como atribuir

> Fonte: IBGE (IPCA), via SGS/Banco Central do Brasil, série 433. Cálculo do
> acumulado: Observatório de Taxas, observatoriodetaxas.tec.br, versão v1.4.0.

---

Este documento descreve a procedência e os termos aplicáveis conforme
verificados em 11/11/2026. Não é parecer jurídico.
