# Ciclo 2 — Descoberta e distribuição

Base: Bing SEO Analysis de 11/11/2026 (fornecido pelo dono), com 3 itens:
falta de backlinks de domínios reconhecidos (moderada), IndexNow não
configurado (alta) e um título longo (alta, 1 página). Ponto de partida: `main`
em `e3b2aa16` (merge do PR #15, v1.4.0); nada do PR #15 foi refeito.

## 1. IndexNow

Implementado. Desenho, códigos de resposta e ativação em [INDEXNOW.md](INDEXNOW.md).

| Requisito | Como foi atendido |
| --- | --- |
| Reutilizar `sitemap_lastmod.json` | É o estado atual; o estado do último envio usa o mesmo hash |
| Novas, alteradas, removidas | Diferença entre os dois estados (`planejar`) |
| Não reenviar inalteradas | Só a diferença é enviada; testes `test_sem_alteracao...` e `test_nao_reenvia...` |
| Canônicas e escapadas | URLs do sitemap; envio com `quote` RFC 3986; outro host é descartado |
| Arquivo de verificação | `docs/f38e6e174b4a83156de2bf6385271334.txt`, conferido antes de cada envio |
| Só após o deploy | Conferência da impressão digital no HTML servido em produção |
| Retry, timeout, logs | 3 tentativas com espera crescente; 20 s/30 s; log no job + `envios.jsonl` |
| Não bloquear a coleta | Workflow separado; falha não toca no `monitor.yml` |
| Sem concorrência/duplicado/antecipado | `concurrency: indexnow`; estado avança só no aceito; pendente se o site ainda não mudou |
| Dry-run local | `--dry-run` (e `--sem-verificar`, só junto) |
| Testes | 18 em `tests/test_indexnow.py` |

Prova contra produção (11/11/2026): a impressão digital do HTML servido em
`/`, `/reajuste/`, `/reajuste/igpm-julho-2026/`, `/reajuste/igpm-março-2026/`,
`/correcao/` e `/var.html` é igual à do `sitemap_lastmod.json`. Ou seja, a
conferência de deploy funciona com o Pages real. Dry-run da primeira execução
com `--desde 2026-11-11`: 530 URLs (as que mudaram na v1.4.0).

## 2. Títulos

Auditoria das 532 páginas indexáveis (HTML cru):

| Faixa | Antes do PR #15 | Depois do PR #15 | Neste ciclo |
| --- | --- | --- | --- |
| > 70 caracteres | 1 | 1 | 0 |
| > 65 | 2 | 2 | 1 |
| > 60 | 90 | 46 | 46 |
| Máximo | 73 | 73 | 66 |

**Página sinalizada pelo Bing (alta confiança):** `/correcao/`, título
"Calculadora de correção monetária entre datas: IPCA, IGP-M, INPC e IGP-DI",
73 caracteres. É o único acima de 70 e o único acima de 66, antes e depois do
PR #15, o que bate com "1 página afetada". O relatório não traz a URL, então
isso é inferência; a segunda candidata seria `/retransmissora.html` (66).

Correção: "Calculadora de correção monetária: IPCA, IGP-M, INPC e IGP-DI" (61),
no mesmo padrão do hub de reajuste ("Calculadora de reajuste de contrato: IPCA,
IGP-M, INPC e IGP-DI", 63). "Entre datas" segue no H1 e na descrição. A página
não está entre as mais citadas.

Sem outras mudanças: nenhum título duplicado, nenhum termo repetido no mesmo
título, todos os títulos de mês têm a competência e começam igual ao H1 (teste
de coerência do PR #15). Não foi aplicado limite geral: o Google não fixa
número de caracteres. O teste novo `test_titulos_ate_70_caracteres` só impede
a volta do caso apontado e explica o corte.

## 3. Referências externas

Backlink não se resolve com código. O que dá para fazer é deixar o projeto
fácil de citar e com motivos reais para ser citado.

Feito neste ciclo (no repositório, baixo risco):

- `LICENSE` (MIT, código) e `LICENSE-DADOS.md` (termos por série e textos CC BY 4.0).
- `CITATION.cff`: ativa o botão *Cite this repository* no GitHub, com a
  orientação de citar também o produtor de cada índice.
- README: link do site no domínio próprio (apontava para `github.io`), descrição
  sem atribuir os índices ao BCB e seção **Como citar e reutilizar** com URL
  permanente por versão (`/blob/v1.4.0/data/189_history.json`).

Avaliado, para decisão do dono (BACKLOG C2-01 a C2-07):

| Ação | Por quê |
| --- | --- |
| **Licença (resolvida neste ciclo)** | Código MIT (`LICENSE`). Dados em `LICENSE-DADOS.md`: séries do BCB sob ODbL 1.0, como o próprio BCB publica no Portal de Dados Abertos (conferido pela API do portal); IPCA, INPC, desocupação (IBGE), IGP-M e IGP-DI (FGV IBRE) não são relicenciadas e seguem os termos dos produtores; textos do site CC BY 4.0. A declaração CC0 saiu do JSON-LD e do `llms.txt`. Na verificação apareceram dois rótulos errados, corrigidos neste ciclo: série 4390 (era "CDI", é Selic acumulada no mês) e série 25 (poupança da regra até 03/05/2012) |
| Página pública de metodologia | Hoje a metodologia está espalhada (fichas, FAQ, README). Uma página única, estável, é o que jornalistas e pesquisadores linkam |
| DOI por versão (Zenodo + GitHub) | Referência acadêmica permanente; serviço externo, exige conta do dono |
| Descrição e tópicos do repositório | A descrição no GitHub ainda diz "indicadores do Banco Central"; sugerido: "Indicadores econômicos do Brasil (IPCA, INPC, IGP-M, Selic, câmbio) coletados do SGS/BCB a cada 6 h, versionados em Git, com reajuste e correção monetária." Tópicos: `igp-m`, `inpc`, `reajuste-aluguel`, `correcao-monetaria`, `indexnow` |
| Atribuição no código de embed da Retransmissora | Hoje o crédito fica dentro do iframe (não é link do site que publica). Um crédito visível fora do iframe ajuda a origem do dado aparecer. O Google trata links em widgets distribuídos com cautela: usar marca, não palavra-chave, e `rel="nofollow"` |
| Divulgação editorial | Artigo técnico no blog da LBP (já existe o do Confere), resposta em comunidades de dados abertos e finanças pessoais quando o assunto for o cálculo, contato com quem publica tabelas de reajuste. Sempre com o dado e a fonte, nunca troca ou compra de link |
| Catálogos de dados abertos | Listas curadas (ex.: awesome lists de dados abertos brasileiros) aceitam projetos por PR, com revisão humana |

Não feito, por instrução: publicações em redes sociais, alteração de serviços
externos, diretórios artificiais, compra ou troca de links, geração automática
de backlinks.

### Rótulos corrigidos

| Série SGS | Antes | Depois | Base |
| --- | --- | --- | --- |
| 4390 | CDI - acumulado no mês (%) | Selic - acumulada no mês (%) | Portal de Dados Abertos do BCB: "Taxa de juros - Selic acumulada no mês" (BCB/Demab). O CDI acumulado no mês é a série 4391 |
| 25 | Poupança - rendimento (%) | Poupança (depósitos até 03/05/2012) - rentabilidade (%) | Portal de Dados Abertos do BCB: "Depósitos de poupança (até 03.05.2012) - Rentabilidade no período" |

Só os rótulos mudaram: código SGS, valores, arquivos `*_history.json` e URLs
são os mesmos. O `CHANGELOG.md` mantém o rótulo antigo nas linhas já
registradas (histórico). Em 11/11/2026 as duas séries tinham os mesmos três
últimos valores na 4390 e na 4391 (0,31; 1,07; 1,08), então a troca de rótulo
não muda número publicado.

## 4. Mensuração mensal

Cinco camadas, que não se somam:

| Camada | Métrica | Fonte | Observação |
| --- | --- | --- | --- |
| Descoberta | URLs enviadas e aceitas | `envios.jsonl` (branch `indexnow-state`) | Nosso registro |
| Descoberta | URLs recebidas por IndexNow | Bing WMT → IndexNow | Do lado do Bing |
| Indexação | Páginas indexadas, excluídas, erros | Bing WMT (Site Explorer / URL Inspection), Search Console (Páginas) | Cobertura sobre as 532 URLs do sitemap |
| Exposição | Impressões, posição, CTR por consulta e página | Bing WMT e Search Console, CSV mensal | |
| Exposição em IA | Citações e URLs citadas | Bing WMT, relatório de IA | Não são visitas |
| Visitas | Cliques orgânicos | Bing WMT e Search Console | Clique ≠ visita |
| Visitas | Visitas por página, referência de buscadores e de plataformas de IA | GoatCounter | Plataformas sem referrer ficam de fora: é um piso |

Procedimento mensal (manual, sem API nem credencial):

1. Exportar os CSVs do Bing (páginas, consultas, IA, IndexNow) e do Search Console.
2. Guardar fora de `docs/` com o nome `AAAA-MM_<origem>_<relatorio>.csv`.
3. Contar no `envios.jsonl` as URLs aceitas no mês: `git show origin/indexnow-state:envios.jsonl`.
4. Preencher a tabela de acompanhamento em [BASELINE.md](BASELINE.md).

### Marcos de implantação

| Data | Versão | Mudança |
| --- | --- | --- |
| 11/11/2026 | v1.4.0 | PR #15 (auditoria, procedência, ficha técnica, FAQ, sitemap) |
| (data do merge) | v1.5.0 proposta | Este ciclo: IndexNow, título de `/correcao/`, CITATION.cff, README |
| (data do 1º envio real) | — | Primeira execução do `indexnow.yml` com `dry_run = false` |

Hipóteses para os próximos relatórios: (a) o intervalo entre a publicação e o
primeiro rastreamento das páginas alteradas diminui no Bing; (b) o item
"IndexNow" some do SEO Analysis; (c) o item "título longo" some no próximo
rastreamento de `/correcao/`. Nenhuma delas é garantida, e nenhuma mede
citações em IA diretamente.
