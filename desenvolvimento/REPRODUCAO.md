# Reprodução

Dois processos diferentes, que **não** produzem necessariamente o mesmo
resultado:

- **Reprodução histórica:** usar uma versão do código e os dados como estavam
  naquela versão para refazer as páginas e os cálculos publicados.
- **Atualização de dados:** consultar o SGS de novo, o que traz pontos
  publicados depois da release e eventuais revisões de valores antigos.

## Ambiente

| Item | Valor |
| --- | --- |
| Python | 3.12 (versão usada pelos workflows); testado também em 3.13 |
| Dependências | `requirements.txt` (lock com hashes: `requests`, `pyyaml`, `pillow` e dependências transitivas), gerado de `requirements.in` |
| Sistema | Qualquer um com Python e Git; os workflows rodam em `ubuntu-latest` |
| Rede | Só para a atualização de dados (API do SGS) e para o teste ao vivo opcional |

```bash
git clone https://github.com/iosbilario/observatorio-taxas.git
cd observatorio-taxas
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.txt
```

## Configuração das séries

As séries ficam em [`config.yml`](../config.yml) (código SGS, nome e grupo).
A URL da API é `base_url`; `fetch.py` busca `/dados/ultimos/N` e
`backfill.py` busca por intervalo de datas.

## Reprodução histórica

O pacote arquivado no Zenodo contém só o código (ver
[`organic-discovery/ZENODO.md`](../organic-discovery/ZENODO.md)). Os dados de
cada versão estão no histórico Git do repositório:

```bash
git checkout v1.6.0                     # código e data/ exatamente como na tag
python scripts/build_pages.py           # páginas de reajuste
python scripts/build_correcao.py        # páginas de correção
python scripts/render_index.py          # página inicial + sitemap
python scripts/sync_nav.py
python scripts/adsense.py
python scripts/csp_hashes.py
python -m unittest discover -s tests -v
git status --short                      # só docs/index.html muda (hash do commit no carimbo)
```

Não rode `fetch.py` nem `backfill.py` nesse caso: eles buscariam dados novos.

- **Data de referência dos dados:** `data/meta.json` (`gerado_em`) registra a
  última coleta com mudança; cada `data/<codigo>_history.json` traz a data de
  referência de cada ponto (dia 1 do mês, para os índices mensais).
- **Ponto exato no tempo:** qualquer commit serve; `git log -- data/189_history.json`
  mostra quando cada ponto do IGP-M entrou ou foi revisado.
- **Verificação:** o workflow `validate.yml` confere, em todo PR, que regenerar
  as páginas a partir de `data/` reproduz o que está commitado.

## Reprodução dos cálculos

| Cálculo | Fórmula | Código | Teste |
| --- | --- | --- | --- |
| Acumulado de 12 meses e fator de reajuste | (1 + i₁/100) × … × (1 + i₁₂/100) − 1 | `acumulado()` em [`scripts/build_pages.py`](../scripts/build_pages.py) | `test_acumulado_composto_valor_conhecido`, `test_acumulado_ipca_bate_com_serie_oficial_13522` |
| Correção entre datas | produto das variações dos meses posteriores ao inicial até o final | `fator_periodo()` em [`scripts/build_correcao.py`](../scripts/build_correcao.py) | `test_correcao_12_meses_igual_ao_reajuste_do_ultimo_mes` |
| Valores publicados | — | páginas em `docs/reajuste/` e `docs/correcao/` | `test_valores_publicados_iguais_a_linha_de_base` |

Exemplo verificável na tag v1.6.0: IGP-M acumulado de agosto de 2025 a julho
de 2026 = 2,77% (fator 1,027722), em `docs/reajuste/igpm-julho-2026/`.

## Atualização de dados

```bash
python scripts/backfill.py              # opcional: histórico desde 2015 (ou: backfill.py 2019)
python scripts/fetch.py                 # pontos novos
```

Depois, o mesmo pipeline da seção anterior. Diferenças esperadas em relação à
release:

- pontos publicados depois da data da release;
- revisões feitas pelo produtor ou pelo SGS em valores antigos;
- séries diárias muito longas podem ter o alcance reduzido pelo `backfill.py`
  para caber no site estático;
- falha ou indisponibilidade da API do SGS no momento da consulta.

## Limitações

- O Observatório não publica data de divulgação oficial dos índices; registra
  a data de referência e o momento da coleta.
- Acumulados calculados a partir de variações mensais com 2 casas podem diferir
  em centésimos de ponto percentual dos acumulados divulgados pelos produtores
  (diferença máxima medida para o IPCA 12 meses: 0,0052 p.p.).
- O pacote do Zenodo não contém os dados; a reprodução histórica depende do
  repositório Git continuar acessível.
