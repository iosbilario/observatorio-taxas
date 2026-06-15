# observatorio-taxas

Observatório de baixíssima manutenção que **versiona séries de taxas e indicadores do Banco Central do Brasil (SGS) ao longo do tempo**, usando o próprio **Git como banco de dados temporal** e o **GitHub Actions como motor** — tudo a custo zero. A cada execução agendada, um robô consulta a API pública do SGS/BACEN, grava os valores como snapshots JSON em `data/` e commita as mudanças; o histórico de commits passa a ser, então, a linha do tempo de cada indicador, e uma página estática em `docs/` lê esses JSONs para desenhar os gráficos.

## Arquitetura — o loop API → Action → commit → Pages

O sistema é um ciclo fechado e sem servidor:

1. **API (SGS/BACEN).** `scripts/fetch.py` lê `config.yml` (lista de séries + `base_url`) e consulta a API de dados abertos do Banco Central para cada código.
2. **Action (GitHub Actions).** `.github/workflows/monitor.yml` roda por `cron` a cada 6 horas, prepara o Python, instala as dependências e executa o coletor.
3. **Commit (Git como base temporal).** Os snapshots JSON gerados em `data/` são commitados e enviados (push) automaticamente. Cada commit é um ponto no tempo — versionar é o que cria o histórico, sem precisar de banco de dados.
4. **Pages (visualização).** A página estática `docs/index.html` lê os JSONs (espelhados em `docs/data/`) e renderiza a série temporal com Chart.js, publicada via GitHub Pages servindo a pasta `/docs`.

Estado atual: **implementado e funcional** — coleta (`fetch.py`), workflow (`monitor.yml`) e gráfico (`index.html`) prontos. O resumo em linguagem natural via API da Anthropic (`diff_summary.py`) está pronto como ponto de extensão, porém **desligado por padrão**.

## Arquivos gerados em `data/`

A cada coleta, `fetch.py` produz (chaves ordenadas, UTF-8, indentado — para `git diff` limpo):

| Arquivo | Conteúdo |
| --- | --- |
| `data/<codigo>.json` | Último snapshot bruto da série (`data`, `valor`, `codigo`, `nome`). |
| `data/<codigo>_history.json` | Histórico acumulado: lista de `{data_coleta, valor, data_referencia}`. **Só recebe um novo ponto quando o valor muda** — esse é o "diff" que vira evento. |
| `data/series.json` | Manifesto (`codigo`, `nome`, `valor_atual`, ...) consumido pela página. |
| `CHANGELOG.md` | Uma linha por mudança detectada: `[timestamp] <nome>: <antigo> -> <novo>`. |

Os arquivos que a página consome (`series.json` e cada `<codigo>_history.json`) são **espelhados em `docs/data/`**, porque o GitHub Pages servindo `/docs` só publica o que está dentro de `docs/`. O store canônico continua sendo `data/` na raiz.

## Estrutura

```
observatorio-taxas/
├── .github/workflows/monitor.yml   # STUB: workflow agendado (cron 6h) → fetch → commit/push
├── data/.gitkeep                   # snapshots JSON serão commitados aqui
├── scripts/fetch.py                # STUB: coletor SGS/BACEN
├── scripts/diff_summary.py         # STUB opcional: resumo via API da Anthropic
├── docs/index.html                 # STUB: página/gráfico da série temporal
├── config.yml                      # séries monitoradas (pronto)
├── requirements.txt                # requests, pyyaml (pronto)
├── .gitignore                      # padrão Python (pronto)
└── README.md
```

## Rodando localmente

```bash
# 1. (opcional) ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. dependências
pip install -r requirements.txt

# 3. coletar (após implementar fetch.py) — grava/atualiza JSONs em data/
python scripts/fetch.py

# 4. visualizar a página localmente
python -m http.server -d docs 8000
# abra http://localhost:8000
```

## Configuração

Edite `config.yml` para ajustar ou ampliar as séries monitoradas. Os códigos do SGS devem ser validados (referência: https://www3.bcb.gov.br/sgspub/).

A API do SGS é pública e retorna `[{"data": "dd/mm/aaaa", "valor": "x"}]`; a `base_url` em `config.yml` usa o sufixo `/dados/ultimos/1` para pegar o valor mais recente.

## Resumo opcional via API da Anthropic (`diff_summary.py`)

Camada **desligada por padrão** — o núcleo não depende dela nem exige chave de API. O `fetch.py` já está plugado: ao detectar uma mudança, tenta gerar uma frase e a anexa ao `CHANGELOG.md` (indentada com `↳`); se o pacote ou a chave faltarem, a coleta segue normalmente sem o resumo.

**Ativar na nuvem (workflow):** cadastre a chave como secret do repositório:

```bash
gh secret set ANTHROPIC_API_KEY        # cole o valor no prompt (não fica no histórico)
```

O `monitor.yml` instala o pacote `anthropic` e injeta a chave **apenas quando o secret existe**, então forks sem chave continuam rodando sem custo.

**Testar localmente:**

```bash
pip install anthropic                     # dependência mantida fora de requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows: $env:ANTHROPIC_API_KEY="..."
python scripts/diff_summary.py "Meta Selic (% a.a.): 13.75 -> 14.50"
# -> "A meta Selic subiu de 13,75% para 14,50% ao ano."
```

> Nunca comite a chave nem a cole em chats/arquivos versionados — o `.gitignore` já bloqueia `.env`. Se uma chave vazar, revogue-a no console da Anthropic e gere outra.

## Publicação no GitHub Pages (servindo `/docs`)

1. **Settings → Actions → General → Workflow permissions** → selecione **Read and write permissions** e salve. Isso permite ao `monitor.yml` commitar os snapshots de volta usando o `GITHUB_TOKEN` padrão.
2. **Settings → Pages** → em *Build and deployment*, *Source* = **Deploy from a branch**; escolha a branch (`main`) e a pasta **`/docs`**; salve.
3. Aguarde o deploy; o site fica em `https://<usuario>.github.io/<repo>/`.
4. Rode o workflow uma vez (aba **Actions → monitor → Run workflow**) para gerar e commitar os primeiros JSONs em `docs/data/`. A partir daí ele roda sozinho a cada 6 h.
