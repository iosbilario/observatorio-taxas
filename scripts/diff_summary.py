"""
diff_summary.py — Camada de resumo em linguagem natural. STUB OPCIONAL.

Ideia (a ser implementada DEPOIS pelo Claude Code)
--------------------------------------------------
Apos cada coleta, comparar o snapshot novo com o anterior (via git ou
comparando os JSON em data/) e gerar um resumo curto e legivel das mudancas
das series -- ex.: "Selic estavel em 9,25%; USD/BRL subiu 0,8% no periodo".

Esse resumo usaria a API da Anthropic. Mantido COMENTADO de proposito para
nao introduzir dependencia nem exigir chave de API enquanto o nucleo (coleta +
versionamento) nao estiver pronto.

# TODO (descomentar e implementar depois):
#
# import os
# from anthropic import Anthropic
#
# def summarize(diff_text: str) -> str:
#     client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
#     msg = client.messages.create(
#         model="claude-haiku-4-5-20251001",
#         max_tokens=300,
#         messages=[{
#             "role": "user",
#             "content": f"Resuma em PT-BR, de forma objetiva, estas mudancas "
#                        f"nas series de taxas do BACEN:\n\n{diff_text}",
#         }],
#     )
#     return msg.content[0].text
#
# Observacao: a dependencia `anthropic` NAO esta em requirements.txt ainda.
# Adicione-a apenas quando esta camada for ativada.
"""

# TODO: implementar. Esqueleto apenas (camada opcional).
