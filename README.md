# observatorio-taxas

Observatório de baixíssima manutenção que **versiona séries de taxas e indicadores do Banco Central do Brasil (SGS) ao longo do tempo**, usando o próprio **Git como banco de dados temporal** e o **GitHub Actions como motor** — tudo a custo zero. A cada execução agendada, um robô consulta a API pública do SGS/BACEN, grava os valores como snapshots JSON em `data/` e commita as mudanças; o histórico de commits passa a ser, então, a linha do tempo de cada indicador, e uma página estática em `docs/` lê esses JSONs para desenhar os gráficos.

## Arquitetura — o loop API → Action → commit → Pages

O sistema é um ciclo fechado e sem servidor:

1. **API (SGS/BACEN).** `scripts/fetch.py` lê `config.yml` (lista de séries + `base_url`) e consulta a API de dados abertos do Banco Central para cada código.
2. **Action (GitHub Actions).** `.github/workflows/monitor.yml` roda por `cron` a cada 6 horas, prepara o Python, instala as dependências e executa o coletor.
3. **Commit (Git como base temporal).** Os snapshots JSON gerados em `data/` são commitados e enviados (push) automaticamente. Cada commit é um ponto no tempo — versionar é o que cria o histórico, sem precisar de banco de dados.
4. **Pages (visualização).** A página estática `docs/index.html` lê os JSONs de `../data/` e renderiza a série temporal, podendo ser publicada via GitHub Pages.

Estado atual: **apenas o esqueleto e as configurações estão prontos**. A lógica de coleta (`fetch.py`), o resumo opcional via API da Anthropic (`diff_summary.py`), o workflow (`monitor.yml`) e o gráfico (`index.html`) estão como _stubs_ com TODOs, para serem implementados depois.

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
