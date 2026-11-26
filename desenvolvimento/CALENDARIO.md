# Calendário de divulgações

A página `/calendario/` e os blocos "Próximas divulgações" (capa) e "Próxima
divulgação" (fichas do IPCA, do IPCA-15 e da Meta Selic) saem de
[`scripts/build_calendario.py`](../scripts/build_calendario.py).

## Fontes

| Família | Fonte | Tipo | Arquivo no repositório |
| --- | --- | --- | --- |
| IPCA (produto 9256) e IPCA-15 (produto 9260) | [API do calendário do IBGE](https://servicodados.ibge.gov.br/api/v3/calendario/) | estruturada, coletada a cada 6 horas por `fetch_calendario.py` | `data/calendario_fontes.json` (`ibge`) |
| Decisões já comunicadas do Copom | [API de comunicados do Copom](https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados?quantidade=20) | estruturada, coletada a cada 6 horas | `data/calendario_fontes.json` (`copom_decisoes`) |
| Datas das reuniões futuras do Copom | notas oficiais do BC: [calendário 2026](https://www.bcb.gov.br/api/servico/sitebcb/notasimprensa/20739) (Comunicado nº 43.383, 24/06/2025) e [calendário 2027](https://www.bcb.gov.br/api/servico/sitebcb/notasimprensa/21173) (Comunicado nº 45.452, 23/06/2026) | editorial: não há interface estável para as reuniões futuras | `data/calendario_copom.json` |

Cobertura conferida em 26/11/2026: IPCA até a divulgação de 12/01/2027
(competência dezembro de 2026); IPCA-15 até 23/12/2026 (competência dezembro de
2026); Copom até a reunião de 7 e 8/12/2027.

## Regras

- O identificador do evento não muda: `ipca-2026-11`, `ipca15-2026-12`,
  `copom-2026-8` (ano e ordem no calendário anual). Um reagendamento guarda a
  data anterior em `datas_anteriores` (`data/calendario.json`).
- "Publicado" só quando o dado aparece no SGS (IPCA e IPCA-15) ou quando existe
  o comunicado oficial (Copom). A data prevista passar não basta: o evento fica
  como "data passou, dado ainda não registrado".
- No Copom, a reunião (dois dias), a comunicação da decisão (segundo dia,
  comunicado oficial) e o início da vigência (primeiro dia com o valor na série
  432) aparecem separados. Uma decisão que mantém a meta também é decisão.
- Horário: a API do IBGE traz `12:00:00` em todos os itens, sem fuso; não é
  tratado como confirmado. A fonte do Copom usada não traz horário.
- Falha de fonte: `fetch_calendario.py` mantém o último arquivo válido; a página
  mostra a data da última conferência de cada fonte. Depois do fim da
  cobertura, a ficha e a página do evento avisam.

## Como atualizar o calendário do Copom

Quando o BC publicar o calendário de um ano novo (até junho do ano anterior):

1. Abra a nota oficial (ou o comunicado) e acrescente as reuniões em
   `data/calendario_copom.json`, com `ano`, `ordem` (1 a 8) e os dois `dias`.
2. Acrescente a nota em `fontes`, com `url` e `publicado_em`, e ajuste
   `cobertura.fim` e `conferido_em`.
3. Se uma reunião for remarcada, troque só os `dias`: o id (`copom-ano-ordem`)
   continua o mesmo e a data antiga entra em `datas_anteriores`.
4. Rode `python scripts/build_calendario.py` e os testes
   (`python -m unittest tests.test_calendario`).

Nunca preencha datas estimadas pela recorrência das reuniões: só datas de fonte
oficial.
