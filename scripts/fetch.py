"""
fetch.py — Coletor de séries do SGS/BACEN. STUB / NÃO IMPLEMENTADO.

Objetivo
--------
Ler `config.yml`, consultar cada série configurada na API de dados abertos do
Banco Central (SGS) e gravar/atualizar snapshots JSON dentro de `data/`. Esses
snapshots, versionados pelo Git, formam o "banco de dados temporal" do
observatório: cada commit é um ponto no tempo.

Como deve funcionar (a ser implementado pelo Claude Code)
---------------------------------------------------------
TODO:
  1. Carregar config.yml (pyyaml) -> base_url + lista de séries (codigo, nome).
  2. Para cada série, montar a URL substituindo {codigo} em base_url e fazer
     GET com `requests` (tratar timeout, status != 200 e JSON vazio).
  3. Normalizar a resposta do SGS (formato [{"data": "dd/mm/aaaa", "valor": "x"}]).
  4. Persistir em data/ -- sugestao de estrategia (decidir depois):
       - data/<codigo>.json  -> historico acumulado (append idempotente), e/ou
       - data/latest.json    -> ultimo valor de todas as series num so arquivo.
     Garantir idempotencia: nao duplicar pontos ja existentes para a mesma data.
  5. Escrever os JSON de forma estavel (chaves ordenadas, indent=2, newline final)
     para que o `git diff` entre snapshots seja limpo e legivel.
  6. Logar um resumo (quantas series OK, quantas falharam) no stdout.

Notas:
  - Nao derrubar a execucao inteira se UMA serie falhar; registrar e seguir.
  - Sem segredos: a API do SGS e publica e nao exige autenticacao.
"""

# TODO: implementar. Esqueleto apenas.
def main() -> None:
    raise NotImplementedError("fetch.py ainda nao foi implementado -- ver TODOs acima.")


if __name__ == "__main__":
    main()
