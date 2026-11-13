# v1.7.0 — Servidor MCP para ChatGPT e Claude

Esta versão acrescenta um servidor MCP (Model Context Protocol) público,
gratuito, sem login e somente de leitura. Com ele, assistentes como ChatGPT e
Claude consultam os indicadores do Observatório e fazem os mesmos cálculos do
site, com fonte, licença e data da coleta em cada resposta. O site e os dados
não mudaram de fórmula nem de URL.

## Servidor MCP

- **Endpoint:** `https://observatorio-taxas-mcp.onrender.com/mcp` (Streamable HTTP, sem sessão).
- **Documentação e suporte:** https://observatoriodetaxas.tec.br/mcp/
- **Código:** `servidor_mcp/`, com o SDK oficial `mcp` 2.3.0 e dependências travadas com hash.
- **Ferramentas:**
  - `get_latest_indicator`: último valor publicado de um indicador.
  - `get_indicator_history`: série entre duas datas, até 500 pontos por chamada.
  - `calculate_adjustment`: correção de um valor por um índice mensal, com memória de cálculo.
  - `compare_indicators`: comparação de dois indicadores de mesma natureza e unidade.
- **Mesmos números do site:** o servidor lê os JSON publicados em `/data/` e
  importa `fator_periodo` (`scripts/build_correcao.py`) e `acumulado`
  (`scripts/build_pages.py`). Testado no ChatGPT e no Claude em 12/11/2026:
  R$ 1.000 pela Selic acumulada no mês de 2024-12 a 2025-12 = R$ 1.143,33
  (fator 1,1433276), igual à calculadora do site.
- **Séries expostas:** só as do Banco Central, sob ODbL 1.0. IPCA, INPC e
  desocupação (IBGE), IGP-M e IGP-DI (FGV IBRE) ficam suspensos no MCP até a
  confirmação dos termos de redistribuição. Continuam no site.
- **Segurança e privacidade:** limites de 64 KB por requisição, 256 KB por
  resposta e 60 chamadas por minuto por cliente; proteção de host
  (`OBS_MCP_HOSTS`); IP só como hash com sal, em memória, por até 1 minuto;
  logs sem parâmetros e sem IP. Contêiner sem root.
- **Hospedagem:** Render Free num workspace sem cartão, custo R$ 0. Sem cartão,
  um excedente suspende o serviço em vez de gerar cobrança.

## Publicação nos diretórios

- **ChatGPT:** pacote em `servidor_mcp/plugin-openai/` (formato Agent Plugins),
  com 5 casos de teste positivos, 3 negativos e vídeo de demonstração. Domínio
  verificado pela rota `/.well-known/openai-apps-challenge`. Enviado para
  revisão em 12/11/2026.
- **Claude:** conector enviado ao diretório em 12/11/2026, em revisão.
- **Versão do servidor:** 0.1.0, independente da versão do repositório.

## Outras mudanças desde a v1.6.0

- Páginas novas: `/mcp/` (documentação e suporte) e `/termos/` (termos de uso).
- Política de privacidade com a seção do MCP: dados recebidos, finalidade,
  registros técnicos (7 dias), destinatários e controles do usuário.
- `validate.yml` ganhou o job `mcp`, com a suíte do servidor.
- Workflow temporário `mcp-acordado.yml`, que mantém o servidor acordado
  durante a revisão dos diretórios.
- O teste de linha de base passou a usar só as páginas de mês fechado
  (`reajuste/*`); as páginas `correcao/*` são conferidas contra `data/` a cada
  execução, porque mudam com cada coleta.
- README com a seção do servidor MCP e como rodá-lo localmente.

## Licenças e conteúdo arquivado

Sem mudança em relação à v1.6.0. Código sob MIT; dados sob os termos de cada
produtor (`LICENSE-DADOS.md`). O pacote arquivado no Zenodo contém só o
software, agora incluindo `servidor_mcp/`; `data/` e as páginas geradas com
valores ficam fora via `.gitattributes`.

## Reprodução

- **Histórica:** `git checkout v1.7.0` e rodar os geradores sem coletar
  (passo a passo em `desenvolvimento/REPRODUCAO.md`).
- **Servidor MCP local:** `pip install --require-hashes -r servidor_mcp/requirements.txt`
  e `OBS_MCP_DADOS=data uvicorn servidor_mcp.servidor:app --port 8000`.

## Testes

98 testes do site (`tests/`) e 45 do servidor MCP (`servidor_mcp/tests/`),
incluindo protocolo MCP nas versões 2025-03-26, 2025-06-18 e 2025-11-25,
casos negativos, limites, pacote do plugin e política de privacidade.

## Limitações conhecidas

- Os dados do MCP são os do site: coletados a cada 6 horas, não em tempo real.
- No plano gratuito, a primeira chamada depois de 15 minutos sem uso leva cerca de 1 minuto.
- Os índices de inflação do IBGE e da FGV ainda não estão no MCP.
- Sem data oficial de divulgação dos índices; o projeto registra a data de referência e a coleta.
