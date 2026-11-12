# Servidor MCP do Observatório de Taxas

Um servidor MCP remoto (Streamable HTTP), público, sem login e somente de
leitura, para ChatGPT, Claude e outros clientes MCP. A mesma implementação
atende as duas plataformas.

Página pública: [observatoriodetaxas.tec.br/mcp](https://observatoriodetaxas.tec.br/mcp/).

## Arquitetura

```
SGS/BCB ──(robô a cada 6 h, monitor.yml)──> data/*.json ──> GitHub Pages
                                                              │ /data/<codigo>_history.json
                                                              ▼
                      ChatGPT / Claude ──HTTPS──> servidor MCP (este diretório)
                                                  cache de 10 min, sem banco
```

- O servidor **não** consulta o SGS. Lê os JSON que o site já publica, então
  devolve exatamente os números do Observatório, com a data da coleta.
- Os cálculos importam as funções do site: `fator_periodo` de
  `scripts/build_correcao.py` (calculadora de correção) e `acumulado` de
  `scripts/build_pages.py` (páginas de reajuste). Não há fórmula paralela.
- Sem estado: `stateless_http=True`, respostas JSON, sem sessão nem banco.
- Deploy independente do GitHub Pages: o site continua estático e não depende
  do servidor.

| Arquivo | Papel |
| --- | --- |
| `servidor.py` | MCP (SDK oficial `mcp` 2.3.0), rotas `/mcp` e `/health`, limite de taxa, limites de tamanho |
| `ferramentas.py` | As 4 ferramentas como funções puras, validação e erros estruturados |
| `catalogo.py` | Produtor, distribuidor, unidade, periodicidade, natureza e licença de cada série |
| `dados.py` | Leitura dos JSON publicados com timeout, limite de bytes e cache |
| `conferir_endpoint.py` | Cliente MCP oficial que confere um endpoint real |
| `Dockerfile`, `../render.yaml` | Deploy |
| `plugin-openai/` | Pacote para o diretório de plugins do ChatGPT |
| `tests/` | Testes |

## Ferramentas

Todas com `title` e `readOnlyHint: true`, `destructiveHint: false`,
`idempotentHint: true`, `openWorldHint: false`.

| Ferramenta | Entrada | Saída principal |
| --- | --- | --- |
| `get_latest_indicator` | `indicador` | valor, unidade, data de referência, competência, data da coleta, produtor, código SGS, fonte, URL no site |
| `get_indicator_history` | `indicador`, `data_inicial`, `data_final` | pontos, unidade, cobertura pedida/retornada/disponível, versão dos dados; até 500 pontos com `paginacao.proxima_data_inicial` |
| `calculate_adjustment` | `valor`, `indice`, `data_inicial`, `data_final` | taxa acumulada, fator, valor final, valores arredondados como no site, fórmula, memória mês a mês, link equivalente no site |
| `compare_indicators` | `indicadores` (2), `data_inicial`, `data_final` | resumo de cada série, metodologia, cobertura; alinhamento ponto a ponto só para mesma natureza, unidade e periodicidade |

Datas: `AAAA-MM-DD` ou `AAAA-MM`. Indicadores: código SGS ou apelido (`selic`,
`selic-efetiva`, `selic-mensal`, `tr`, `poupanca`, `dolar`, `dolar-compra`,
`euro`, `ibc-br`).

**Regra do cálculo:** igual à calculadora de correção do site, aplica as
variações dos meses **posteriores** ao mês inicial até o mês final. Um
reajuste de 12 meses até julho de 2026 é `data_inicial=2025-07`,
`data_final=2026-07`. Só índices de variação mensal são aceitos.

**Erros:** `isError: true` com JSON `{erro, mensagem, ...}`. Códigos:
`indicador_desconhecido`, `indicador_suspenso`, `data_invalida`,
`periodo_invertido`, `periodo_fora_do_alcance`, `periodo_sem_dados`,
`valor_invalido`, `indice_nao_aplicavel`, `parametro_invalido`,
`fonte_indisponivel`, `resposta_grande`. HTTP 429 `limite_de_taxa` com
`Retry-After`.

**Datas:** `data_referencia` é a data do ponto no SGS; `data_ultima_coleta` é
a última coleta com mudança feita pelo Observatório; `data_divulgacao` é
sempre `null` porque o projeto não registra a divulgação oficial.

## Licenciamento das séries

| Séries | Produtor | Situação no MCP |
| --- | --- | --- |
| 432, 1178, 4390, 226, 25, 1, 10813, 21619, 24363 | Banco Central | **Expostas** (ODbL 1.0, conferida no Portal de Dados Abertos do BCB; atribuição em cada resposta) |
| 433, 13522, 188, 24369 | IBGE | **Suspensas**: sem autorização clara de redistribuição automatizada verificada |
| 189, 190 | FGV IBRE | **Suspensas**: os termos do portal da FGV IBRE proíbem reprodução sem autorização |

As suspensas respondem `indicador_suspenso` com o motivo e onde consultar. A
liberação é uma decisão do proprietário: depois de confirmar os termos com o
produtor, definir `OBS_MCP_LIBERAR_RESTRITAS=1` no serviço. A licença MIT
cobre só o código. Detalhes em [`../LICENSE-DADOS.md`](../LICENSE-DADOS.md).

A ODbL exige atribuição e que bases derivadas publicadas fiquem sob a mesma
licença; isso vale para quem redistribuir as respostas.

## Segurança e limites

- Somente leitura: nenhuma ferramenta grava, envia ou paga nada.
- Validação por esquema (Pydantic) e nas funções; corpo de requisição até 64 KB.
- Até 500 pontos por série e 256 KB por resposta.
- Limite de taxa: 60 requisições/min por cliente e 1.200/min no total; `/health` fica de fora.
- Cliente identificado por hash do IP com sal aleatório, só em memória, por até 60 s. O IP não é gravado.
- Logs: nome da ferramenta, resultado, bytes e tempo. Sem parâmetros, sem IP, sem log de acesso do uvicorn (`--no-access-log`).
- Proteção contra DNS rebinding quando `OBS_MCP_HOSTS` é definido.
- Imagem com usuário sem privilégios, dependências com hash (`requirements.txt`).
- Sem credenciais: nada a configurar como segredo.

## Hospedagem (custo R$ 0)

| Opção | Custo | Limites gratuitos | Riscos |
| --- | --- | --- | --- |
| **Render, Web Service Free** (escolhida) | R$ 0, sem cartão | 512 MB, 0,1 CPU, 750 h/mês por workspace, 5 GB de banda/mês (plano Hobby desde abr/2026) | Dorme após 15 min sem tráfego (~1 min para acordar); sem cartão, excedente suspende o serviço em vez de cobrar |
| Hugging Face Spaces (Docker, CPU básica) | R$ 0 | 2 vCPU, 16 GB | Dorme após inatividade; política de uso voltada a demos de ML |
| Fly.io / Railway / Cloud Run | Exigem cartão | Créditos ou cotas com cobrança automática acima do limite | Fora do requisito de custo zero |
| Cloudflare Workers | R$ 0 | 100 mil req/dia | Exigiria reescrever em JS/TS ou Python Workers e duplicar as fórmulas |

Render atende sem duplicar código e sem cartão. Para o arranque a frio, as
duas plataformas toleram respostas lentas na primeira chamada; se a revisão
reclamar, a alternativa gratuita é um ping externo a cada 10 min (consome
horas: 750 h cobrem um serviço 24/7 em mês de 31 dias) — decisão do
proprietário, não incluída.

**Não cadastrar cartão no Render.** Com cartão, banda acima de 5 GB passa a
ser cobrada (US$ 0,15/GB).

## Rodar localmente

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r servidor_mcp/requirements.txt
OBS_MCP_DADOS=data uvicorn servidor_mcp.servidor:app --host 127.0.0.1 --port 8000
python -m servidor_mcp.conferir_endpoint http://127.0.0.1:8000/mcp
python -m unittest discover -s servidor_mcp/tests -t . -v
```

Sem `OBS_MCP_DADOS`, o servidor lê os JSON públicos do site. Para testar no
MCP Inspector: `npx @modelcontextprotocol/inspector` e conectar em
`http://127.0.0.1:8000/mcp` (Streamable HTTP).

## Deploy no Render (feito pelo proprietário)

1. render.com → entrar com o GitHub, **sem cadastrar cartão**.
2. **New → Blueprint** → repositório `iosbilario/observatorio-taxas` (lê `render.yaml`, plano `free`).
3. Depois do primeiro deploy: definir `OBS_MCP_HOSTS` com o host gerado (ex.: `observatorio-taxas-mcp.onrender.com`).
4. `python -m servidor_mcp.conferir_endpoint https://<host>/mcp`.
5. Se o host não for `observatorio-taxas-mcp.onrender.com`, atualizar `plugin-openai/mcp.json` e `docs/mcp/index.html`.

Domínio próprio (`mcp.observatoriodetaxas.tec.br`) é opcional e gratuito no
Render; recomendado, porque o ChatGPT verifica o domínio e o Claude pede que o
domínio do servidor corresponda ao serviço.

## Checklist — ChatGPT (diretório de plugins)

Referência: [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission) e [plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines).

- [ ] Servidor no ar em HTTPS e `conferir_endpoint.py` verde
- [ ] Verificação de identidade (individual ou empresa "LBP Tecnologia") em platform.openai.com → Organization settings; a submissão é rejeitada sem ela
- [ ] Conferir/ajustar `plugin-openai/mcp.json` (URL) e gravar o vídeo de demonstração; preencher `review.demo_recording_url` em `plugin.json`
- [ ] Gerar o ZIP: `cd servidor_mcp/plugin-openai && zip -r ../observatorio-de-taxas-plugin.zip plugin.json mcp.json assets`
- [ ] platform.openai.com/plugins → **Upload new or existing plugin** → escolher a identidade verificada → enviar o ZIP
- [ ] **MCPs → Connect**: publicar o token de verificação em `https://<host-do-mcp>/.well-known/openai-apps-challenge` (texto puro; exige rota no servidor ou domínio próprio — pendência abaixo), autenticação "nenhuma"
- [ ] Aguardar o scan das 4 ferramentas e resolver os achados
- [ ] Conferir em **Review details** os 5 casos positivos e 3 negativos importados (não há credenciais: o serviço é público)
- [ ] **Submit for review**, aceitar as declarações; após aprovação, **Publish plugin**
- [ ] Antes: testar no ChatGPT em modo desenvolvedor (Settings → Apps → criar app com a URL do MCP)

## Checklist — Claude (diretório de conectores)

Referência: [Submit a connector](https://claude.com/docs/connectors/building/submission) e [pre-submission checklist](https://claude.com/docs/connectors/building/review-criteria).

- [ ] Servidor no ar em HTTPS, acessível pela internet pública
- [ ] Cada ferramenta com `title` e `readOnlyHint` (feito; testado em `test_protocolo.py`)
- [ ] Testar no MCP Inspector e como conector personalizado no Claude (Settings → Connectors → Add custom connector → URL `/mcp`), chamando as 4 ferramentas
- [ ] Materiais: documentação ([/mcp/](https://observatoriodetaxas.tec.br/mcp/)), política de privacidade ([/privacidade/](https://observatoriodetaxas.tec.br/privacidade/)), contato de suporte, ícone (`docs/mcp/icone.png`)
- [ ] Credenciais de teste: não se aplica (sem login); declarar no portal que o serviço é público
- [ ] Conta Claude em plano pago para submeter
- [ ] Portal de desenvolvedor do Claude → enviar o conector e confirmar o passo **Test & launch**
- [ ] Domínio do servidor correspondendo ao serviço: preferir `mcp.observatoriodetaxas.tec.br`

## Pendências antes de abrir ao público

1. **Deploy** no Render pelo proprietário (sem cartão) e conferência do endpoint.
2. **Domínio do MCP**: `onrender.com` não é do Observatório. Para a verificação do ChatGPT e o critério de domínio do Claude, configurar `mcp.observatoriodetaxas.tec.br` (CNAME, gratuito) e acrescentar a rota `/.well-known/openai-apps-challenge` com o token que o portal fornecer.
3. **Vídeo de demonstração** para a revisão do ChatGPT.
4. **Verificação de identidade** na OpenAI e conta paga no Claude.
5. **Séries do IBGE e da FGV**: seguem suspensas até confirmação dos termos.
