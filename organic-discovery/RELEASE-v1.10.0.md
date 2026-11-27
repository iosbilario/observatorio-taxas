# v1.10.0 — Contas que se refazem na versão dos dados, divulgações e calendário

Esta versão faz cada número que o site entrega (recibo do VAR, demonstrativo de
reajuste, citação de uma análise) apontar para o commit dos dados usado e
poder ser refeito naquela versão, mesmo depois de novas coletas. Também
acrescenta páginas permanentes de divulgação com RSS, o calendário oficial das
próximas divulgações, a consulta de uma série como estava numa data passada e
a evolução de um contrato ao longo dos aniversários. As fórmulas não mudaram:
as calculadoras dão os mesmos resultados da v1.9.0, agora com o fator de 10
casas em todo trecho que mostra a conta.

## Contas reproduzíveis

- **Recibos do VAR** guardam o commit dos dados. Abrir um recibo antigo refaz
  a conta naquela versão e avisa quando o valor atual é diferente.
- **Demonstrativo de reajuste:** cada página de mês tem um demonstrativo para
  copiar (WhatsApp, e-mail) com o link de conferência. O link
  `?dados=<commit>` refaz a conta com o fator daquela versão.
- **Fator com 10 casas** em todas as páginas, no demonstrativo, no MCP e nos
  textos que ensinam a conta. O valor em reais é calculado com o fator exibido,
  em centavos inteiros, para que qualquer pessoa reproduza os centavos à mão.
- **Citar uma análise:** as páginas de divulgação trazem uma referência pronta,
  com produtor, série, período e link versionado.
- **Página Sobre** refeita em torno de um exemplo: um aluguel de R$ 2.000,00
  reajustado pelo IGP-M de novembro de 2025 a outubro de 2026 (fator
  1,0524648668, R$ 2.104,93 na versão 3e6cee9) e o porquê dos sete centavos de
  diferença para a conta com o percentual arredondado.

## Divulgações e RSS

- `/divulgacoes/`: uma página permanente por divulgação: a leitura mensal do
  IPCA, o CDI acumulado contra o IPCA e a PTAX da semana, com gráfico de linha,
  tabela, CSV e histórico de revisões.
- `feed.xml`: RSS com cada divulgação nova e cada revisão. Os títulos dizem o
  tipo da alteração e nunca usam "correção".
- "Acompanhar este indicador" nas fichas: RSS, página da divulgação e dados.

## O que mudou nesta coleta

- `/mudancas/`: observações novas e valores alterados na última coleta, com o
  commit e o link para comparar com a versão anterior.
- **Classificação da alteração** pela natureza da série e pelo estado do
  período na hora da coleta: "Nova observação", "Atualização de período em
  andamento" (como o CDI acumulado de um mês ainda aberto), "Alteração em
  período encerrado" ou "Valor alterado". A classificação usa o dia da coleta
  em Brasília, não o dia em que a página é gerada, e não muda quando o site é
  regenerado depois.

## Calendário oficial

- `/calendario/`: próximas divulgações do IPCA e do IPCA-15 e reuniões do
  Copom, ligado da página inicial e das fichas do IPCA, do IPCA-15 e da Meta
  Selic.
- Fontes: API de calendário do IBGE (produtos 9256 e 9260), comunicados do
  Copom na API do Banco Central e o calendário oficial do Copom de 2026 e 2027
  (notas à imprensa do BCB), mantido em `data/calendario_copom.json`.
- Cada evento tem identificador estável (`ipca-2026-11`, `copom-2026-8`) e
  separa competência, data prevista, horário, data oficial e data em que o
  Observatório detectou o dado. Só fica "publicado" quando o dado aparece no
  SGS ou o comunicado existe. Datas remarcadas ficam registradas.

## Versão histórica

- `/historico/?serie=<código>&data=<AAAA-MM-DD>`: a série como o Observatório
  a registrou até o fim daquele dia (horário de Brasília), comparada com a
  atual por competência, com link para compartilhar.
- O índice de versões (`docs/data/versoes/`, 160 KB no total) vem do
  `git log --first-parent` de cada `data/<código>_history.json`. O navegador
  baixa só o índice da série e o arquivo da versão escolhida.
- Antes da primeira versão preservada, e quando a versão não carrega, a página
  diz isso em vez de mostrar o valor atual no lugar.

## Evolução do contrato e comparação de índices

- `/reajuste/evolucao/`: valor de um contrato a cada aniversário desde o
  início, com índice, defasagem e data de corte. O novo valor de cada ano vira
  a base do seguinte. A conta para no primeiro mês que falta e diz o motivo
  (antes da cobertura, ainda não divulgado ou lacuna). Índices negativos são
  aplicados como publicados.
- "Comparar com outro índice": a mesma base e as mesmas competências por um
  segundo índice. A diferença só aparece nos aniversários calculados pelos
  dois. O valor do contrato fica no navegador (`sessionStorage`) e nunca vai
  para o endereço.

## Página inicial

- "Indicadores por tema" no lugar de "Mais indicadores": 25 séries em 6 temas,
  com minigráfico de 12 meses, abas no desktop e seções no celular. Voltar e
  Avançar restauram o tema.
- "Próximas divulgações" com os eventos do calendário.
- O card do IBC-Br passa a se chamar "IBC-Br · atividade econômica" e diz que a
  variação é sem ajuste sazonal. A ficha explica que o IBC-Br não é o PIB
  oficial do IBGE e por que o Banco Central destaca outro percentual.

## Correções

- **Correção monetária:** `1.000.000,00` era lido como 1.000 (resultado mil
  vezes menor) e `1000.50` como 100.050. As páginas de `/correcao/` passam a
  usar o mesmo leitor estrito do demonstrativo e recusam entrada inválida com
  aviso.
- **Meta Selic:** a coleta parava de receber dias novos quando o SGS devolvia
  datas futuras. A janela de coleta agora completa os 180 dias anteriores.
- **Comparador:** depois de um erro no formulário, o gráfico e a tabela antigos
  saem da tela. Cores legíveis no tema claro. Um mês só aparece como ponto.
- **Embed:** a variação de séries que já são taxas sai em pontos percentuais
  (Meta Selic de 14,00% para 13,75%: −0,25 p.p.).
- **Simulador de CDI:** o link gerado pela página reabre com o mesmo valor (o
  cálculo e a leitura do link usam o mesmo limite).
- **Catálogo no celular:** fechar um tema tira o tema do endereço; recarregar
  não o reabre.
- **Layout:** o bloco de estado de `/mudancas/` e os valores longos do catálogo
  (US$ 361.634 milhões) não saem mais da caixa.

## Outras mudanças

- Favicon e ícones com URL própria (`favicon.ico`, `favicon.svg`,
  `apple-touch-icon.png`) e `site.webmanifest`, para o ícone aparecer na busca.
- A coleta do GitHub Actions faz checkout com histórico completo
  (`fetch-depth: 0`), necessário para o índice de versões.
- `docs/mudancas/` e `docs/feed.xml` passam a ficar fora do pacote arquivado no
  Zenodo, como `docs/divulgacoes/`: trazem valores do IBGE e da FGV IBRE.

## Reprodução

- **Histórica:** `git checkout v1.10.0` e rodar os geradores sem coletar
  (passo a passo em `desenvolvimento/REPRODUCAO.md`). `fetch_calendario.py` e
  `versoes_series.py` consultam a rede ou o Git e não fazem parte da
  regeneração.
- **Ferramentas:** `node` executa `docs/calculos.js`, `docs/demonstrativo.js`
  e `docs/evolucao.js`, os mesmos arquivos servidos ao navegador.

## Testes

301 testes do site (2 pulados sem rede ou sem `cffconvert`) e 48 do servidor
MCP. Novos nesta versão: recibo do VAR na versão dos dados, demonstrativo e
leitor de valor, leitura do valor nas cinco páginas de correção (rodando o
script publicado em `node`), classificação das alterações, calendário,
versão histórica, evolução do contrato, divulgações e RSS, catálogo da página
inicial, ícones e datas futuras da Meta Selic.

## Limitações conhecidas

- O calendário do Copom depende do calendário oficial publicado pelo Banco
  Central uma vez por ano e mantido à mão em `data/calendario_copom.json`.
- A versão histórica começa na primeira versão preservada de cada série no Git
  (13/11/2026 para o CDI acumulado no mês).
- Os dados são coletados a cada 6 horas, não em tempo real.
