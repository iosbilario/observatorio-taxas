# Google AdSense

Como o Observatório se prepara para o AdSense, como ligar e desligar anúncios
e o checklist de aprovação. Estado atual: **ads.txt publicado, anúncios
desligados** (`adsense.ativo: false` em `config.yml`).

## 1. Auditoria (11/11/2026)

| Item | Situação antes | O que foi feito |
| --- | --- | --- |
| Verificação de propriedade | Método escolhido no AdSense: **ads.txt**. `/ads.txt` respondia 404 | `docs/ads.txt` com a linha fornecida pelo AdSense, gerado de `config.yml` por `scripts/adsense.py` |
| Política de privacidade | Não existia | `/privacidade/`, com as divulgações que o AdSense pede (cookies de terceiros, Google, como desativar), GoatCounter sem cookies, GitHub Pages e LGPD |
| Página institucional e contato | Contato só no formulário da landing (mailto) | `/sobre/`: o que é, fontes, quem mantém, política de anúncios e contato `contato@observatoriodetaxas.tec.br` |
| Links no site | — | "Sobre e contato" e "Privacidade" no rodapé de todas as páginas públicas (pelos geradores, sobrevive à regeneração) |
| Conteúdo original e navegação | 530 páginas indexáveis, navegação por links HTML, sem conteúdo copiado | Sem mudança |
| CSP | Meta CSP com `default-src 'self'`; hashes na landing, embed e apoie; `'unsafe-inline'` nas páginas geradas | Sem mudança enquanto desligado. Ver seção 3 |
| JavaScript | Calculadoras usavam `onsubmit="calc();return false"` (handler inline) | Trocado por `addEventListener`: handler inline não roda sob CSP por hash. Resultado das calculadoras idêntico (testado) |
| Consentimento | Nenhum mecanismo | Nenhum banner próprio: o Google exige CMP certificada para EEE, Reino Unido e Suíça; o próprio AdSense oferece a CMP do Google (Privacidade e mensagens) |
| Páginas adequadas | — | Ver seção 4 |

Referências oficiais consultadas: [divulgações obrigatórias na política de
privacidade](https://support.google.com/adsense/answer/1348695),
[requisitos de consentimento (EEE, Reino Unido, Suíça)](https://support.google.com/adsense/answer/13790256),
[CSP com o código do AdSense](https://support.google.com/adsense/answer/16283098),
[políticas do programa](https://support.google.com/adsense/answer/48182).

## 2. Configuração (fonte única)

```yaml
adsense:
  client: "ca-pub-4229313749435489"
  ads_txt: "google.com, pub-4229313749435489, DIRECT, f08c47fec0942fa0"
  ativo: false
  consentimento_configurado: false
  slots: {}
```

`scripts/adsense.py` valida o formato (`ca-pub-` + 16 dígitos), confere que
o pub do ads.txt é o mesmo do client e rejeita qualquer outro identificador.
Roda no `monitor.yml` depois do `sync_nav.py` e nunca falha a coleta: se a
ativação estiver incompleta, emite um aviso e fica desligado.

## 3. CSP: por que a ativação muda a política

O AdSense só suporta **CSP estrita** (nonce + `'strict-dynamic'`), porque os
domínios que o código usa mudam com o tempo. Um site estático não gera nonce
por requisição; o equivalente é a CSP estrita **por hash**:

```
script-src 'sha256-…' 'strict-dynamic' 'unsafe-inline' 'unsafe-eval' https: http:
```

Com `'strict-dynamic'`, o navegador só executa os scripts inline com hash
listado e o que eles carregam. Por isso, nas páginas com anúncio, o
`adsense.py`:

- insere no `<head>` um carregador inline que cria o script do AdSense **e** o
  do GoatCounter (que deixaria de carregar pela lista de hosts);
- recalcula os hashes de todos os scripts inline;
- acrescenta `https:` em `frame-src`, `img-src` e `connect-src` (iframes e
  pixels dos anúncios);
- guarda a CSP e a tag do GoatCounter originais num comentário, para que
  desligar restaure a página byte a byte (testado).

Páginas sem anúncio continuam com a CSP atual.

## 4. Onde os anúncios podem aparecer

Espaços marcados por `<!-- anuncio:NOME:inicio --><!-- anuncio:NOME:fim -->`,
vazios enquanto desligado:

| Espaço | Página | Posição |
| --- | --- | --- |
| `inicio` | `/` | Entre o bloco do VAR e o de Reajuste, separado por linha |
| `reajuste-hub` | `/reajuste/` | Depois de "Qual índice usar no reajuste do aluguel?" |
| `reajuste-mes` | `/reajuste/<indice>-<mes>-<ano>/` (522) | Depois das perguntas e respostas, antes da navegação de meses |
| `correcao-hub` | `/correcao/` | Depois das perguntas e respostas |
| `correcao-indice` | `/correcao/<indice>/` | Depois das perguntas e respostas |

Regras aplicadas e testadas:

- Nunca dentro de formulário, calculadora, resultado, tabela de memória de
  cálculo ou ficha técnica.
- Rótulo visível "Publicidade" e borda de separação; nada que imite botão das
  calculadoras.
- Altura reservada (300 px) para não deslocar o conteúdo quando o anúncio
  carrega.
- Sem anúncio em: Rebobinar, VAR, Retransmissora, embed, Apoie, Sobre,
  Privacidade e páginas internas (admin, radar).
- Unidades manuais, não "anúncios automáticos": com anúncios automáticos o
  Google escolhe a posição e pode colocar perto das calculadoras.

## 5. Como ativar

Só depois de o AdSense aprovar o site.

1. **AdSense → Privacidade e mensagens:** criar e publicar a mensagem de
   regulamentações europeias (CMP do Google). Ela aparece só para visitantes
   do EEE, Reino Unido e Suíça.
2. **AdSense → Anúncios → Por bloco de anúncios:** criar uma unidade de
   display para cada espaço que quiser usar e copiar o `data-ad-slot`.
3. Em `config.yml`:

   ```yaml
   adsense:
     ativo: true
     consentimento_configurado: true
     slots:
       reajuste-mes: "<data-ad-slot da unidade>"
       correcao-indice: "<data-ad-slot da unidade>"
   ```

4. Localmente: `python scripts/adsense.py && python scripts/csp_hashes.py &&
   python -m unittest discover -s tests`, abrir uma página de mês e conferir no
   console que não há violação de CSP.
5. Abrir PR, conferir o `validate.yml`, fazer o merge. O próximo `monitor.yml`
   mantém os anúncios nas páginas regeneradas.

## 6. Como desativar

`ativo: false` em `config.yml` e rodar o pipeline (ou esperar o próximo
`monitor.yml`). O `adsense.py` remove todo código de anúncio e restaura a CSP
original. O `ads.txt` permanece; para retirar o site do AdSense, apague a
linha `ads_txt` e o arquivo `docs/ads.txt`.

## 7. Impacto medido

| | Desligado | Ligado (simulação com rede do Google bloqueada) |
| --- | --- | --- |
| HTML da página de mês | +70 bytes (marcadores) | +~1,5 KB (carregador, espaço, hashes) |
| Scripts de terceiros | nenhum novo | `adsbygoogle.js` e os que ele carregar (não medidos: dependem do anúncio) |
| Layout | igual | espaço com altura fixa de 300 px; nada acima dele se move |
| Calculadoras | resultado idêntico | resultado idêntico, sem violação de CSP |

Com anúncios reais, LCP e TBT pioram em alguma medida; medir com Lighthouse
na primeira semana e reduzir os espaços se a página de mês passar de 2,5 s de
LCP no mobile.

## 8. Checklist de aprovação no AdSense

- [ ] PR mergeado e `https://observatoriodetaxas.tec.br/ads.txt` responde com a linha do AdSense
- [ ] Em **Sites**, clicar em **Verificar** (método ads.txt) e depois **Pedir revisão**
- [ ] `/privacidade/` e `/sobre/` publicadas e ligadas no rodapé
- [ ] Informar a URL da política de privacidade em **Privacidade e mensagens** (se pedido)
- [ ] Criar e publicar a mensagem de consentimento (CMP do Google) para EEE, Reino Unido e Suíça
- [ ] Aguardar aprovação (o Google informa por e-mail; pode levar dias ou semanas)
- [ ] Criar as unidades de anúncio e preencher `slots` em `config.yml`
- [ ] `ativo: true` e `consentimento_configurado: true` em PR próprio; testes verdes
- [ ] Depois do deploy: conferir console sem violação de CSP e anúncios só nos espaços previstos
- [ ] Acompanhar no AdSense o status do ads.txt e avisos de política
