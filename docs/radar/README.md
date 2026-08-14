# Radar de Recomendação — contrato de dados

Superfície pública em `/radar/`, servida pelo GitHub Pages junto com o resto do
site. HTML, CSS e JS vanilla, sem build. As páginas não têm estado próprio: tudo
que elas mostram é derivado, em tempo de carga, dos arquivos em `data/`.

**Este diretório é o contrato.** O coletor (que roda em outro repositório,
consulta os modelos e commita aqui) só precisa escrever os arquivos abaixo no
formato abaixo. Nada mais é combinado entre as duas pontas.

---

## Modelo de domínio

```
Sonda (nicho + localidade + prompts)
  └── Rodada (apuração semanal)
        └── Execução (prompt × modelo × repetição)
              ├── cita 0..N Estabelecimentos, cada um com posição
              └── tem 1 Recibo (a resposta bruta arquivada)
```

O **veredito** de um estabelecimento numa rodada — share, posição média, delta —
nunca é gravado. É sempre recalculado a partir das execuções. Se um número da
tela não puder ser reproduzido somando os JSONs, é bug.

---

## Arquivos

| Caminho | Papel | Quem escreve |
|---|---|---|
| `data/sondas/{slug}.json` | a sonda e todas as suas rodadas | coletor |
| `data/recibos/{id}.json` | resposta bruta de uma execução | coletor |
| `data/index.json` | índice das sondas ativas (home) | coletor |
| `data/busca.json` | índice de busca de estabelecimentos | coletor |
| `data/bundle.js` | espelho derivado de tudo acima | coletor (passo final) |

### `data/sondas/{slug}.json`

```json
{
  "sonda": {
    "slug": "odontologia-pinheiros-sp",
    "nicho": "Clínicas odontológicas",
    "localidade": "Pinheiros, São Paulo",
    "prompts": ["me indica um dentista bom em Pinheiros", "..."],
    "modelos": ["gemini-flash-grounding"],
    "repeticoes": 5,
    "demonstracao": true
  },
  "rodadas": [
    {
      "numero": 4,
      "apurada_em": "2026-08-09",
      "execucoes": [
        {
          "id": "r4-p1-m1-x1",
          "prompt_idx": 0,
          "modelo": "gemini-flash-grounding",
          "repeticao": 1,
          "citados": [{ "estabelecimento": "clinica-sorriso-pinheiros", "posicao": 1 }],
          "recibo": "recibos/r4-p1-m1-x1.json"
        }
      ]
    }
  ],
  "estabelecimentos": {
    "clinica-sorriso-pinheiros": {
      "nome": "Clínica Sorriso Pinheiros",
      "aliases": ["Sorriso Odontologia"]
    }
  }
}
```

Regras que o front-end assume:

- `rodadas` pode vir em qualquer ordem; a página reordena por `numero`
  decrescente. Rodada atual = maior `numero`.
- `rodadas: []` é válido e legítimo: renderiza o estado "primeira rodada roda
  domingo" com captura de e-mail, não um erro.
- `execucoes.length` é o **total da rodada** — o denominador de todo share e o
  número de blips na barra. Execução que falhou e não foi repetida não deve
  entrar, senão o denominador mente.
- `prompt_idx` indexa `sonda.prompts` (base 0).
- `posicao` é 1-based, na ordem em que o estabelecimento aparece na resposta.
- Um estabelecimento citado duas vezes na mesma execução conta **uma vez**; o
  front-end deduplica, mas o ideal é o coletor já não duplicar.
- Todo slug em `citados` precisa existir em `estabelecimentos`. Se faltar, a
  página cai para o próprio slug como nome, o que fica feio mas não quebra.
- `recibo` é o caminho relativo a `data/`.
- `demonstracao` liga o selo "dados de demonstração" — ver a seção
  [O selo de demonstração](#o-selo-de-demonstração), que é o contrato de como
  ele sai do ar.

### `data/recibos/{id}.json`

```json
{
  "id": "r4-p1-m1-x1",
  "quando": "2026-08-09T06:00:00-03:00",
  "modelo": "gemini-flash-grounding",
  "prompt": "me indica um dentista bom em Pinheiros",
  "resposta_bruta": "texto integral, sem edição",
  "fontes_citadas": [{ "titulo": "…", "url": "https://…" }],
  "demonstracao": true
}
```

`resposta_bruta` é exibida como veio, com quebras de linha preservadas e os
nomes do estabelecimento destacados na hora (casamento sem acento e sem caixa,
usando `nome` + `aliases`). Não pré-processe, não resuma, não limpe markdown:
o valor do recibo é ser cru.

`fontes_citadas` aceita objetos `{titulo, url}` ou strings simples.

### `data/index.json`

```json
{
  "gerado_em": "2026-08-09",
  "sondas": [
    {
      "slug": "odontologia-pinheiros-sp",
      "nicho": "Clínicas odontológicas",
      "localidade": "Pinheiros, São Paulo",
      "rodada_atual": 4,
      "apurada_em": "2026-08-09",
      "total_execucoes": 15,
      "lider": { "slug": "…", "nome": "…", "mencoes": 12 }
    }
  ]
}
```

`rodada_atual`, `apurada_em`, `total_execucoes` e `lider` são **denormalizações**
— existem só para a home montar os cards sem baixar todas as sondas. São
derivados da sonda correspondente e precisam ser reescritos a cada rodada.
`rodada_atual: null` e `lider: null` para sonda sem rodada apurada.

### `data/busca.json`

```json
{
  "estabelecimentos": [
    {
      "slug": "clinica-sorriso-pinheiros",
      "nome": "Clínica Sorriso Pinheiros",
      "aliases": ["Sorriso Odontologia"],
      "sonda": "odontologia-pinheiros-sp",
      "nicho": "Clínicas odontológicas",
      "localidade": "Pinheiros, São Paulo"
    }
  ]
}
```

Índice plano de todos os estabelecimentos de todas as sondas. Alimenta a busca
da home e é como `negocio.html?e={slug}` descobre a que sonda um negócio
pertence. Um estabelecimento que aparece em duas sondas precisa de duas entradas
— e, hoje, a página do negócio usa a primeira que casar.

### `data/bundle.js`

```js
window.__RADAR_BUNDLE__ = { index: {…}, busca: {…}, sondas: {…}, recibos: {…} };
```

Espelho derivado, não fonte. Existe por um motivo específico: `fetch()` de
arquivo local é bloqueado em páginas abertas via `file://` (origem opaca), então
sem ele as páginas só funcionariam servidas por HTTP. O front-end tenta o
`fetch()` do JSON primeiro e só injeta o bundle quando o fetch falha — em
produção ele nunca é baixado.

O coletor deve regerá-lo como último passo, a partir dos JSONs recém-escritos.

---

## O selo de demonstração

Enquanto os dados publicados forem fixtures, **toda página do Radar exibe o selo
"dados de demonstração"** e as fontes dos recibos usam o TLD reservado
`exemplo.invalid`. A razão é o próprio produto: o Radar vende prova auditável, e
publicar resposta de IA inventada sem rótulo seria fabricar recibo.

### Como o site detecta

Um único campo booleano no JSON da sonda, lido pelo motor a cada carga:

```json
{ "sonda": { "slug": "…", "demonstracao": true } }
```

| Valor | Efeito |
|---|---|
| `true` | selo visível em todas as telas que mostram aquela sonda |
| `false` ou ausente | selo escondido; nada mais muda |

O campo é **por sonda**, não global: uma sonda real e uma de demonstração podem
conviver, cada uma com seu selo. Os recibos carregam o mesmo campo, que controla
a nota no rodapé do painel de recibo.

Não existe interruptor separado, configuração de build nem variável de ambiente.
O selo é uma função dos dados — é o que impede que ele fique ligado (ou
desligado) por esquecimento.

### Quando o selo sai

Quando o coletor publicar a **primeira rodada real**, ele grava a sonda
`demonstracao: false` (ou simplesmente omite o campo) junto com as rodadas
coletadas. O selo some na mesma publicação, sem deploy nem edição de HTML.

Duas coisas **não** são automáticas e precisam de mão humana nessa virada:

1. **A numeração recomeça.** A série de demonstração vai até a rodada 4. A
   primeira rodada real é a rodada 1: apague as rodadas de fixture em vez de
   continuar a contagem, senão o histórico mistura dado inventado com dado
   coletado.
2. **`metodologia.html` tem uma seção escrita à mão** — "Estado atual:
   demonstração" — que explica em prosa o que o selo significa. Prosa não é
   derivável de JSON: remova ou reescreva essa seção manualmente na mesma
   entrega.

> Nota de nomenclatura: o campo se chama `demonstracao`, e não `demo`, para o
> schema ficar todo em português, como `apurada_em`, `citados` e `execucoes`.
> É o mesmo mecanismo de um `demo: true|false`.

---

## Fixtures de demonstração

Enquanto o coletor não existe, os arquivos em `data/` são gerados por
`scripts/radar_fixtures.py`, na raiz do repositório:

```bash
python scripts/radar_fixtures.py
```

Determinístico: mesma semente, mesmos bytes. Uma sonda, 4 rodadas, 15 execuções
por rodada, 60 recibos, 8 estabelecimentos fictícios. **Nenhum nome corresponde
a negócio real** e as URLs de fonte usam o TLD reservado `exemplo.invalid`, que
não resolve por definição. Todas as páginas que consomem esses dados exibem o
selo "dados de demonstração".

Quando o coletor entrar, este script sai — ou vira o gerador de fixtures dos
testes.

---

## Páginas

| Arquivo | O que é |
|---|---|
| `index.html` | home: demo vivo da última rodada, busca de negócio, sondas ativas |
| `sonda.html?s={slug}` | placar do nicho-bairro, com histórico por rodada (`#rodada-N`) |
| `negocio.html?e={slug}` | veredito de um estabelecimento, com recibos |
| `metodologia.html` | o que é medido, como, e o que isso não prova |
| `radar.css` | tokens e componentes |
| `radar.js` | carga de dados, derivações, blips, recibo, gráfico |

Sem localStorage nem sessionStorage: estado só em memória, por decisão de
projeto. A captura de e-mail valida e confirma na tela, sem backend — o ponto de
entrada do endpoint real está marcado com comentário em `radar.js`
(`ligarAlerta`).

## Detalhes de implementação que valem saber

- **Fontes** são as já self-hospedadas do site (`/fonts/`), referenciadas por
  caminho relativo. A CSP das páginas é `font-src 'self'`, então Google Fonts
  não carregaria. Archivo faz o display e o corpo; IBM Plex Mono faz todo dado.
- **Gráfico** é SVG escrito à mão, não Chart.js: as páginas públicas deste site
  não carregam CDN (`script-src 'self'`) e precisam abrir do disco.
- **A varredura** (linha âmbar que acende os blips ao carregar o placar) é a
  única animação do produto, dura 400 ms e some sob
  `prefers-reduced-motion: reduce`.
- **Blips**: só os acesos são botões e recebem foco. Os apagados são `<span>`
  fora da árvore de acessibilidade — o grupo já anuncia "citado em N de M".
