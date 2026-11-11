# IndexNow no Observatório

IndexNow é um protocolo para o site avisar buscadores participantes (Bing,
Yandex, Seznam, Naver, entre outros; os envios são compartilhados entre eles)
que uma URL foi criada, alterada ou removida. **Ele não garante rastreamento,
indexação, posição nem presença em respostas de IA.** O HTTP 200 só confirma o
recebimento. Referência: [documentação do protocolo](https://www.indexnow.org/documentation).

## Fluxo

```
monitor.yml (coleta SGS → páginas → render_index → commit/push na main)
        │                     data/sitemap_lastmod.json = impressão digital por URL
        ▼
GitHub Pages publica a main
        ▼
indexnow.yml (workflow_run do monitor | push na main | a cada 6 h | manual)
  1. lê o estado do último envio (branch indexnow-state, estado.json)
  2. diferença com data/sitemap_lastmod.json → novas, alteradas, removidas
  3. confirma o deploy NO SITE: chave em /<chave>.txt; cada URL nova/alterada
     responde 200 com a mesma impressão digital; cada removida responde 404/410
  4. envia só as confirmadas (POST, lotes de até 10.000)
  5. avança o estado só das URLs aceitas (200/202) e grava o histórico
```

URL que não passa na conferência fica pendente e volta na próxima execução.
Sem diferença, nada é enviado. Não existe envio do sitemap inteiro.

## Peças

| Peça | Papel |
| --- | --- |
| `scripts/indexnow.py` | Plano, conferência do deploy, envio com retry e estado |
| `.github/workflows/indexnow.yml` | Disparo, fila única (`concurrency: indexnow`), gravação do estado |
| `config.yml` → `indexnow_key`, `indexnow_endpoint` | Chave e endpoint (`https://api.indexnow.org/indexnow`) |
| `docs/<chave>.txt` | Arquivo de verificação na raiz do domínio (exigido pelo protocolo). A chave não é segredo: precisa ser pública |
| branch `indexnow-state` | `estado.json` (impressão digital da última versão aceita por URL) e `envios.jsonl` (uma linha por execução com envio) |
| `tests/test_indexnow.py` | 18 testes sem rede |

O estado fica fora da `main` para não disputar push com o robô de coleta nem
gerar commit no site. Se a branch for apagada, a próxima execução semeia o
estado com a situação atual e não envia nada.

## Garantias e limites

- **Só depois do deploy:** a conferência compara o HTML servido em produção com a impressão digital do estado. Se o Pages ainda serve a versão antiga, a URL espera.
- **Sem duplicados:** a fila única impede envios simultâneos; URL aceita sai da diferença.
- **Sem bloquear a coleta:** é outro workflow. Falha do IndexNow não afeta o `monitor.yml`.
- **URLs canônicas e escapadas:** o estado usa as URLs do sitemap (as canônicas); o envio usa a forma escapada (`mar%C3%A7o`). URL de outro host é descartada.
- **Retry:** até 3 tentativas para 429, 5xx e falha de rede (5 s, 15 s; respeita `Retry-After` até 120 s). Timeout de 20 s na conferência e 30 s no envio.
- **Limite conhecido:** o lote aceito pelo buscador avança como um todo; não há confirmação por URL no protocolo.

## Códigos de resposta

| HTTP | Significado (protocolo) | O que o script faz |
| --- | --- | --- |
| 200 | URLs recebidas | Avança o estado |
| 202 | Recebidas; validação da chave pendente | Avança o estado (comum no primeiro envio) |
| 400 | Formato inválido | Não repete, não avança, workflow fica vermelho |
| 403 | Chave inválida (arquivo ausente ou sem a chave) | Idem |
| 422 | URL fora do host ou chave fora do padrão | Idem |
| 429 | Excesso de envios | Repete com espera |
| 5xx / rede | Indisponibilidade | Repete; se esgotar, as URLs voltam na próxima execução |

## Comandos

```
python scripts/indexnow.py --anterior estado.json --dry-run --sem-verificar
python scripts/indexnow.py --anterior estado.json --dry-run
python -m unittest tests.test_indexnow -v
```

`--dry-run` nunca envia. `--sem-verificar` (não acessar o site) só é aceito
junto com `--dry-run`.

## Ativação (depois do merge)

1. Confirmar que `https://observatoriodetaxas.tec.br/<chave>.txt` responde com a chave.
2. Rodar o workflow **indexnow** manualmente com `dry_run = true` e ler o log.
3. Decidir a primeira execução real:
   - sem `desde`: semeia o estado e não envia nada; a partir daí, só mudanças;
   - com `desde = 2026-11-11`: envia também as 530 URLs cujo conteúdo mudou na v1.4.0 (mudaram de fato; não é reenvio de página inalterada).
4. Rodar com `dry_run = false`. Depois disso, o fluxo é automático.

## Como conferir o recebimento no Bing

- **Bing Webmaster Tools → IndexNow:** lista as URLs recebidas por IndexNow e a data. É a fonte de "recebidas".
- **URL Inspection:** mostra, por URL, a última data de rastreamento e se está indexada.
- **Do nosso lado:** `envios.jsonl` na branch `indexnow-state` registra quando, quantas URLs, o status de cada requisição e o commit da main.

Comparar as duas pontas mensalmente: enviadas (nossas) × recebidas (Bing) × rastreadas/indexadas (URL Inspection, relatório de páginas).
