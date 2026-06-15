"""
diff_summary.py — Camada OPCIONAL de resumo em linguagem natural (DESLIGADA por padrão).

Recebe a descrição de uma mudança (o "diff" de uma série) e devolve uma frase
curta em PT-BR traduzindo o que aconteceu — ex.: "A meta Selic subiu de 13,75%
para 14,50% ao ano." Usa a API da Anthropic (modelo Sonnet, max_tokens baixo).

Este módulo é um PONTO DE EXTENSÃO pronto, mas NÃO é chamado pelo fluxo principal
(scripts/fetch.py). Assim o núcleo (coleta + versionamento) continua sem segredos
e sem dependências extras.

Como ativar
-----------
  1. Instalar a dependência (mantida fora de requirements.txt de propósito):
         pip install anthropic
  2. Exportar a chave:
         export ANTHROPIC_API_KEY="sk-ant-..."        # Windows: $env:ANTHROPIC_API_KEY="..."
  3. Chamar summarize_change(...) de onde quiser (ex.: dentro de fetch.py, ao
     detectar uma mudança), ou testar pela linha de comando:
         python scripts/diff_summary.py "Meta Selic (% a.a.): 13.75 -> 14.50"

Se a dependência ou a chave não estiverem presentes, a função levanta
RuntimeError com uma mensagem clara — nunca derruba quem a chamou por engano.
"""

from __future__ import annotations

import os
import sys

# Modelo enxuto e barato; max_tokens baixo porque a saída é uma única frase.
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 120


def summarize_change(diff_text: str) -> str:
    """
    Traduz um diff de série (ex.: "Meta Selic (% a.a.): 13.75 -> 14.50") em uma
    frase objetiva em PT-BR. Requer o pacote `anthropic` e ANTHROPIC_API_KEY.
    """
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Pacote 'anthropic' não instalado. Rode: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Defina a variável de ambiente ANTHROPIC_API_KEY.")

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=(
            "Você resume mudanças de indicadores econômicos do Banco Central do "
            "Brasil. Responda com UMA única frase objetiva em português, sem "
            "rodeios, indicando a direção (subiu/caiu/estável) e os valores."
        ),
        messages=[{
            "role": "user",
            "content": f"Traduza esta mudança em uma frase:\n\n{diff_text}",
        }],
    )
    return msg.content[0].text.strip()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python scripts/diff_summary.py "Nome: antigo -> novo"', file=sys.stderr)
        sys.exit(2)
    try:
        print(summarize_change(" ".join(sys.argv[1:])))
    except RuntimeError as exc:
        print(f"[diff_summary desativado] {exc}", file=sys.stderr)
        sys.exit(1)
