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
git checkout v1.9.0                     # código e data/ exatamente como na tag (ou v1.8.0, v1.7.0, v1.6.0)
python scripts/build_pages.py           # páginas de reajuste
python scripts/build_correcao.py        # páginas de correção
python scripts/build_indicadores.py     # /indicadores/ (a partir da v1.8.0)
python scripts/build_ferramentas.py     # comparador e simulador (a partir da v1.8.0)
python scripts/build_guias.py           # /guias/ (a partir da v1.9.0)
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

## Recibos do VAR

Cada recibo do VAR da Economia leva no link o commit dos dados (`?sha=`). O
VAR carrega as séries **daquele** commit em
`raw.githubusercontent.com/iosbilario/observatorio-taxas/<sha>/docs/data/`, então
um recibo aberto meses depois refaz a conta com os mesmos números, mesmo que o
produtor tenha revisado algum mês.

- **Recibo novo:** o VAR lê `docs/data/versao.json`, que o `monitor.yml` grava
  depois de cada coleta com o commit dos dados servidos
  ([`scripts/versao_dados.py`](../scripts/versao_dados.py)), carrega as séries
  desse commit e grava o mesmo hash no recibo. Se o GitHub não responder, o
  recibo sai com os dados do próprio site e sem commit ("dados ao vivo").
- **Link com `?sha=`:** só aquela versão. Se ela não carregar, a página avisa e
  oferece conferir a mesma afirmação com os dados atuais; nunca troca de versão
  sozinha. Links antigos sem `sha` abrem com a versão publicada hoje.
- **Limitação:** o link fixa os dados, não o código. A regra de cálculo é a do
  VAR publicado ([`docs/var-nucleo.js`](../docs/var-nucleo.js), função
  `metrica`); o projeto não versiona a regra à parte.
- **Teste:** `tests/test_var_versao.py` monta duas versões de uma série num
  repositório temporário (a segunda revisa uma competência antiga) e confere
  que o recibo da primeira continua dando o resultado original.

## Divulgações (leituras permanentes e RSS)

Cada nova competência de uma série acompanhada (hoje o IPCA) ganha uma leitura
permanente em `/divulgacoes/<serie>/<competencia>/`, que também é um item do
`/feed.xml` (RSS 2.0).

- **Arquivo durável:** `data/publicacoes.json` (espelho em `docs/data/`), mantido
  por [`scripts/build_divulgacoes.py`](../scripts/build_divulgacoes.py). Só
  cresce. Cada registro guarda a leitura inteira: números, tabela, texto, regra
  (`leitura-mensal-v1`) e versão dos dados. A página e o item do RSS são gerados
  só do registro, então não mudam quando os dados são revisados ou a regra muda.
- **Por que não `mudancas.json`:** ele guarda só as 30 coletas mais recentes.
  Entra apenas para saber quando o Observatório identificou a competência.
- **Eventos:** competência nova vira um registro (`ipca-2026-10`); nova coleta
  com os mesmos valores não muda nada; uma entrada da conta que muda vira um
  registro novo (`ipca-2026-10-r1`, `-r2`…), com valores anterior e revisado e
  as duas versões dos dados. Uma carga histórica só registra a competência mais
  recente de cada série.
- **Versão dos dados sem SHA futuro:** o registro nasce no passo da versão dos
  dados do `monitor.yml` (`build_divulgacoes.py --registrar`), depois do commit
  da coleta, quando o commit existe e está em `versao.json`. Antes de registrar,
  o script confere com `git diff` que os arquivos das séries são os desse commit.
- **Datas:** competência (mês do índice), identificado em (coleta que trouxe o
  dado) e registrado em (data do commit dos dados). A data oficial de divulgação
  do IBGE não está no SGS e fica como "não informada".
- **Teste:** `tests/test_divulgacoes.py`.
- **CDI e PTAX (Entrega 2):** o CDI registra uma leitura por competência mensal
  fechada (`cdi-2026-10`: 12 meses do CDI mensal, SGS 4391, contra o IPCA nas
  mesmas competências, taxa real = (1 + CDI) ÷ (1 + IPCA) − 1). A PTAX registra o
  fechamento semanal (`dolar-2026-W47`: última cotação da semana encerrada contra
  a última da semana anterior; semana encerrada = hoje já no sábado dela, com
  "hoje" = data do commit dos dados, para a leitura não depender da hora em que o
  script roda). A ficha da PTAX acompanha também a variação diária e mostra a
  semana em andamento como parcial; o parcial não entra no registro nem no RSS.
  Teste: `tests/test_leituras_cdi_ptax.py`.

## Reprodução dos cálculos

| Cálculo | Fórmula | Código | Teste |
| --- | --- | --- | --- |
| Acumulado de 12 meses e fator de reajuste | (1 + i₁/100) × … × (1 + i₁₂/100) − 1 | `acumulado()` em [`scripts/build_pages.py`](../scripts/build_pages.py) | `test_acumulado_composto_valor_conhecido`, `test_acumulado_ipca_bate_com_serie_oficial_13522` |
| Correção entre datas | produto das variações dos meses posteriores ao inicial até o final | `fator_periodo()` em [`scripts/build_correcao.py`](../scripts/build_correcao.py) | `test_correcao_12_meses_igual_ao_reajuste_do_ultimo_mes` |
| Valores publicados | — | páginas em `docs/reajuste/` e `docs/correcao/` | `test_valores_publicados_iguais_a_linha_de_base` |

Exemplo verificável nas tags v1.6.0, v1.7.0, v1.8.0 e v1.9.0: IGP-M acumulado de agosto de 2025 a julho
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
