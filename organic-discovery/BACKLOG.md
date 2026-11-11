# Backlog (exige aprovação ou investigação)

Ordenado por benefício esperado ÷ (risco + esforço).

| # | Item | Por que não foi feito agora | Benefício | Risco / esforço |
| --- | --- | --- | --- | --- |
| B-01 | Links do header para a forma canônica (`./`, `reajuste/`) em vez de `index.html` | O README define como requisito o menu funcionar via `file://`; a troca quebra isso. Mudança de 6 strings em `partials/nav.html` + `sync_nav.py` (raiz precisa de `./`). | Remove 536 páginas com link interno para URL não canônica (sinal conflitante, hoje mitigado pelo canonical). | Baixo / 30 min. Decisão do dono. |
| B-02 | Pré-renderizar o Rebobinar (mês corrente: manchete, diff dos indicadores, H1) no HTML, como o `render_index.py` já faz no teaser da landing | Página manual de 613 linhas, toda em JS; exige marcador novo e gerador. | Página hoje vazia para robô sem JS. | Médio / 2–4 h. |
| B-03 | Registrar a **data em que cada ponto foi coletado pela primeira vez** (derivável do `git log` dos `*_history.json`) e mostrá-la como "coletado em" | Exige mudança no `fetch.py` ou um script de backfill pelo histórico do Git. Não é a data de divulgação oficial, e precisa ser rotulada assim. | Preenche "data de atualização" de forma verificável, sem inventar data de divulgação. | Baixo-médio / 2 h. |
| B-04 | Data oficial de divulgação (calendários IBGE e FGV IBRE) | Fonte nova, sem API estável conhecida; risco de dado errado. | Campo pedido em B.1. | Médio. Investigar. |
| B-05 | ~~Rodar os testes no CI~~ **Feito na revisão do PR #15**: `.github/workflows/validate.yml`, só em PR, independente do `monitor.yml`. Falta só, se quiser, marcar o check como obrigatório em Settings → Branches. | — | — | — |
| B-06 | Página explicativa "Selic Meta × Selic efetiva" e "taxa Selic × IPCA (juro real)" | Demanda aparece nas consultas ("taxa selic ipca", "saldo selic últimas"), mas é conteúdo novo; precisa de redação revisada. As séries 432 e 1178 já existem. | Responde consultas que hoje caem na landing. | Médio / 3 h + revisão. |
| B-07 | Remover `SearchAction` do JSON-LD da landing | Inofensivo; o Google descontinuou o recurso em 2024. | Higiene. | Nenhum / 5 min. |
| B-08 | CDN própria (Cloudflare grátis) na frente do Pages para cache longo de fontes e headers (`X-Robots-Tag`, HSTS, CSP real) | Mudança de infraestrutura/DNS. | Lighthouse aponta cache de 10 min em ~140 KB de fontes. Ganho pequeno: performance já é 98–99. | Médio. |
| B-09 | `og:image` por página de mês | O card atual mostra os números do dia, não os do mês: usá-lo nas páginas de mês seria inconsistente. Exigiria gerar 522 imagens. | Compartilhamento social. | Médio. Baixa prioridade. |
| B-10 | Tabela estática da série completa nas páginas de correção (hoje só no JS) | Pode ficar grande (141 meses × 4); a memória de cálculo já existe nas páginas de reajuste, agora ligadas. | Pequeno. | Baixo. |
| B-11 | Importador manual dos CSVs do Bing Webmaster Tools / Search Console | Ver BASELINE §3. Precisa dos arquivos exportados. Manter **fora de `docs/`** para não publicar dado privado. | Série temporal de citações e cliques. | Baixo / 2 h. |
| B-12 | Revisar o `font-size` < 12 px em `.pill.mini`, `.ano-grp .ano`, `pre.snip` e `.carta label` (Lighthouse) | Mexe no visual. | Legibilidade mobile. | Baixo, mas é design. |

## Riscos para indexação a monitorar após o deploy

- 527 páginas mudam de título, H1 e description no mesmo dia. As URLs e os
  números não mudam. É normal haver reprocessamento por algumas semanas; uma
  queda temporária de impressões nas páginas de reajuste é possível e não deve
  ser confundida com efeito das melhorias.
- O `lastmod` de 530 URLs vai para 11/11/2026 (verdadeiro: o conteúdo mudou).
  Depois disso, só muda quando o conteúdo muda.

## Ciclo 2 (11/11/2026)

| # | Item | Por que não foi feito agora | Benefício | Risco / esforço |
| --- | --- | --- | --- | --- |
| C2-01 | Definir licença: código (ex.: MIT) e dados. Revisar a declaração CC0 do JSON-LD e do `llms.txt`, porque IGP-M/IGP-DI (FGV IBRE) e IPCA/INPC (IBGE) seguem os termos dos produtores | Decisão jurídica do dono | Destrava reutilização e citação por terceiros | Baixo esforço, decisão sensível |
| C2-02 | Página pública `/metodologia.html` com fórmulas, procedência por série, periodicidade e limitações | Conteúdo novo; precisa de redação revisada | Página estável para jornalistas e pesquisadores linkarem | Médio / 3 h |
| C2-03 | DOI por versão via integração Zenodo–GitHub | Serviço externo, conta do dono | Referência acadêmica permanente | Baixo / 30 min do dono |
| C2-04 | Atualizar descrição e tópicos do repositório (texto sugerido em CICLO_2.md) | Alteração em configuração do GitHub, fora do código | Busca dentro do GitHub e clareza da procedência | Nenhum / 5 min |
| C2-05 | Crédito visível, com marca e `rel="nofollow"`, no código de embed da Retransmissora | Muda o produto de embed; política de links em widgets | Origem do dado visível em sites de terceiros | Baixo |
| C2-06 | Decidir a primeira execução real do IndexNow: com ou sem `desde = 2026-11-11` | Decisão do dono (ver INDEXNOW.md) | Avisa as 530 URLs alteradas na v1.4.0 | Nenhum |
| C2-07 | Divulgação editorial (artigo técnico, comunidades, catálogos de dados abertos) | Ação humana, fora do repositório | Referências externas legítimas | — |
