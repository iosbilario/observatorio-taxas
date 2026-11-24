# v1.9.0 — Novo visual com o Refy Design, modo claro e escuro e guias

Esta versão redesenha o site inteiro com os tokens do
[Refy Design](https://refy.design/), põe o modo claro como padrão com um botão
para o escuro, reescreve a página inicial em perguntas do dia e acrescenta
seis guias e uma leitura própria em cada página de reajuste. As fórmulas, as
séries e as URLs existentes não mudaram: as calculadoras dão os mesmos
resultados da v1.8.0.

## Feito com o Refy Design

O [Refy Design](https://refy.design/) é um design system open source
(Apache 2.0) criado por [Vinicius Coimbra](https://github.com/viniciuscoimbra):
componentes React e TypeScript, pacote nativo para celular, templates e um
catálogo que agentes de IA consultam pelo MCP antes de montar uma tela. O tema
inteiro fica num arquivo de tokens.

O Observatório usa o Refy de um jeito pouco comum. O site é HTML estático
gerado por Python, sem React, e mesmo assim só os tokens bastaram para trocar
o visual de 574 páginas:

- `docs/refy/tokens.css`: os tokens do `@refy-design/web` 1.11.0, servidos pelo
  próprio site. A CSP continua `style-src 'self'` e `font-src 'self'`.
- `docs/tema.css`: liga a paleta das páginas (`--cofre`, `--papel`,
  `--carimbo`...) aos tokens do tema ativo. Nenhum gerador precisou mudar de
  cor um por um.
- `docs/tema.js`: aplica o tema salvo antes da primeira pintura, liga o botão
  de tema do menu e faz os gráficos incorporados acompanharem o tema.
- Fontes do pacote do Refy: IBM Plex Serif nos títulos, Source Sans 3 no texto,
  Manrope nos números.
- A animação do título da página inicial segue a do hero do
  [refy.design](https://refy.design/): cada palavra sobe de uma máscara, uma
  depois da outra. É feita só com CSS e fica parada para quem pede menos
  movimento.

Para conhecer o Refy: [refy.design](https://refy.design/) ·
[código no GitHub](https://github.com/viniciuscoimbra/refy-design) ·
[relato de um app feito com ele](https://lbptecnologia.com.br/blog/refy-design-meuconfere/).

## Página inicial

- Abre com o título "Indicadores do Brasil, hoje." e as cinco perguntas do dia:
  Selic, inflação em 12 meses, dólar, aluguel (IGP-M) e desemprego. Cada uma
  tem a resposta em uma frase montada com os números, o valor, o direcionador
  do mês (▲ subiu, ▼ caiu, ■ igual, com cor), a data de referência e um
  minigráfico.
- Grade com mais 12 indicadores, cada um com valor, direcionador e link para a
  sua página.
- Coluna lateral com calculadoras, guias, Rebobinador, VAR, gráficos para
  incorporar e o plugin do ChatGPT.
- Abaixo: calculadora de reajuste, guias, Rebobinador e VAR, gráficos
  incorporáveis, perguntas frequentes e a carta para redações.

## Páginas de reajuste

Cada uma das 524 páginas de índice e mês ganhou a seção **Leitura do mês**,
escrita a partir dos números daquele mês: quanto o acumulado mudou e por quê
(a variação que entrou na janela comparada com a que saiu), a sequência de altas
ou quedas, o acumulado um ano antes, a posição entre os mesmos meses de outros
anos, recordes da variação mensal, os extremos da janela e a diferença em reais
para os outros índices. A navegação deixou de repetir a lista de todos os meses
em cada página; a lista completa fica no hub `/reajuste/`.

## Guias /guias/

Seis guias com números de exemplo atualizados a cada coleta: reajuste de
aluguel, IPCA x INPC x IGP-M x IGP-DI, cálculo do acumulado, correção
monetária, Selic (meta, efetiva e do mês) e dólar PTAX. Cada um tem JSON-LD
Article, FAQPage e BreadcrumbList com o mesmo texto da página.

## Card social

`scripts/build_og.py` desenha o card de compartilhamento no tema claro, com os
três números do dia e o direcionador do mês. O `og:image` da página inicial
leva `?v=<hash da imagem>`, para WhatsApp e LinkedIn baixarem o card novo.

## Outras mudanças

- Os arquivos compartilhados (`nav.css`, `tema.css`, `tema.js`,
  `refy/tokens.css`, `estrelas.js`) levam `?v=<hash do conteúdo>` em todas as
  páginas. Uma página nova nunca carrega com o CSS antigo do cache.
- Logo do Observatório no menu.
- O plugin oficial do ChatGPT está no diretório desde 24/11/2026, com banner na
  página inicial, em `/mcp/` e no rodapé.
- `docs/indicadores/` e `docs/guias/` passam a ficar fora do pacote arquivado
  no Zenodo, como `docs/reajuste/` e `docs/correcao/`: trazem valores do IBGE e
  da FGV IBRE.
- PyYAML 6.0.4.

## Fora desta versão

- As páginas do Radar mantêm a paleta própria e continuam fora do menu.
- O `embed.html` segue com o tema escolhido por parâmetro (`tema=claro` ou
  `tema=escuro`), porque é exibido em sites de terceiros.

## Reprodução

- **Histórica:** `git checkout v1.9.0` e rodar os geradores sem coletar
  (passo a passo em `desenvolvimento/REPRODUCAO.md`).
- **Ferramentas:** `node` executa `docs/calculos.js`, o mesmo arquivo servido ao navegador.

## Testes

178 testes do site e 48 do servidor MCP. Novos nesta versão: tema em todas as
páginas (data-theme, tokens, ordem do CSS, versão dos arquivos, aliases de
fonte), perguntas e direcionadores da página inicial, leitura do mês e guias.

## Limitações conhecidas

- A leitura do mês e os guias são texto gerado a partir dos dados; se o
  produtor revisar um mês, o texto muda na coleta seguinte.
- Os dados são coletados a cada 6 horas, não em tempo real.
