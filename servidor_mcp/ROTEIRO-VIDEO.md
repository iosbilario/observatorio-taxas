# Roteiro do vídeo de demonstração (revisão da OpenAI)

Duração alvo: 2 a 3 minutos, sem cortes no meio das chamadas. Gravar a tela do
ChatGPT na web com o plugin pessoal já instalado. Narração opcional; se não
houver, as perguntas na tela bastam.

Antes de gravar: abrir uma conversa e fazer uma pergunta qualquer ao plugin,
para o Render acordar o serviço e o vídeo não mostrar a espera de cerca de 1
minuto.

## Cenas

1. **Abertura (10 s).** Mostrar [chatgpt.com/plugins](https://chatgpt.com/plugins)
   com o plugin Observatório de Taxas instalado. Abrir uma conversa nova.

2. **Último valor (30 s).** Digitar `@`, escolher Observatório de Taxas e perguntar:

   > Qual é a Meta Selic mais recente e desde quando ela vale?

   Expandir a chamada `get_latest_indicator` e mostrar fonte, data de
   referência e data da coleta na resposta.

3. **Cálculo verificável (45 s).** Perguntar:

   > Quanto R$ 1.000 corrigidos pela Selic acumulada no mês de dezembro de 2024 a dezembro de 2025 viram?

   Mostrar a chamada `calculate_adjustment`, o fator (1,143328) e a memória
   de cálculo mês a mês. Se quiser, abra a
   [calculadora de correção do site](https://observatoriodetaxas.tec.br/correcao/)
   em outra aba para mostrar que o número é o mesmo.

4. **Série histórica (20 s).** Perguntar:

   > Mostre o dólar de venda em janeiro de 2026.

   Mostrar a chamada `get_indicator_history`.

5. **Comparação e recusa (30 s).** Perguntar:

   > Compare a Meta Selic com o dólar em 2026.

   Mostrar que `compare_indicators` explica por que taxa anual e cotação não
   são comparáveis ponto a ponto.

6. **Casos negativos (30 s).** Perguntar:

   > Quanto vai estar a Selic em dezembro de 2027?

   Mostrar que o plugin não faz previsões. Depois perguntar:

   > Qual foi o IGP-M de outubro de 2026 pelo Observatório?

   Mostrar que a série aparece como suspensa por licenciamento.

7. **Fechamento (10 s).** Mostrar a página
   [observatoriodetaxas.tec.br/mcp](https://observatoriodetaxas.tec.br/mcp/)
   com suporte, privacidade e termos.

## Publicação do vídeo

Subir no YouTube como **Não listado** (gratuito) ou outro serviço com link
público. Colocar o link em `review.demo_recording_url` no
`plugin-openai/plugin.json` antes de gerar o ZIP.
