#!/usr/bin/env python3
"""
fetch_calendario.py — Agendas oficiais das divulgações (IBGE e Banco Central).

Grava em data/calendario_fontes.json o que as fontes oficiais estruturadas
dizem, com a hora da conferência. O site é gerado só desse arquivo e do
calendário editorial data/calendario_copom.json (build_calendario.py), então
uma falha de rede não apaga a agenda: o arquivo anterior fica como está e a
página mostra a data da última conferência que deu certo.

  IBGE, IPCA (produto 9256) e IPCA-15 (produto 9260):
    https://servicodados.ibge.gov.br/api/v3/calendario/
    A API traz data e hora ("12:00:00" em todos os itens, sem fuso declarado).
    O Observatório guarda a hora como veio e mostra só a data como confirmada.
  Banco Central, decisões já comunicadas do Copom:
    https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados?quantidade=20
  As datas das reuniões FUTURAS do Copom não têm interface estável conhecida:
  ficam em data/calendario_copom.json, conferidas à mão nos comunicados
  oficiais do BC (ver o campo "fontes" e desenvolvimento/CALENDARIO.md).

Nunca derruba a coleta: em erro, imprime o motivo e sai com 0.

    python scripts/fetch_calendario.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SAIDA = ROOT / "data" / "calendario_fontes.json"
IBGE = "https://servicodados.ibge.gov.br/api/v3/calendario/"
COPOM = "https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados?quantidade=20"
PRODUTOS = {9256: "ipca", 9260: "ipca15"}
BRT = timezone(timedelta(hours=-3))


def ibge(dados: dict) -> list[dict]:
    out = []
    for it in dados.get("items", []):
        fam = PRODUTOS.get(it.get("produto_id"))
        if not fam or not it.get("mes_referencia_inicio"):
            continue
        out.append({"familia": fam, "id_ibge": it["id"], "titulo": it["titulo"],
                    "competencia": f"{int(it['ano_referencia_inicio']):04d}-{int(it['mes_referencia_inicio']):02d}",
                    "data_divulgacao": it["data_divulgacao"]})
    return sorted(out, key=lambda x: (x["familia"], x["competencia"]))


def copom(dados: dict) -> list[dict]:
    return sorted(({"reuniao": int(c["nro_reuniao"]), "data": c["dataReferencia"], "titulo": " ".join(c["titulo"].split())}
                   for c in dados.get("conteudo", [])), key=lambda x: x["reuniao"])


def main() -> None:
    anterior = {}
    if SAIDA.exists():
        anterior = json.loads(SAIDA.read_text(encoding="utf-8"))
    novo = dict(anterior)
    # Só o dia: a conferência roda a cada 6 horas, e a hora mudaria o arquivo
    # (e geraria commit) em toda coleta.
    agora = datetime.now(timezone.utc).astimezone(BRT).date().isoformat()
    for nome, url, extrai in (("ibge", IBGE, ibge), ("copom_decisoes", COPOM, copom)):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "observatorio-taxas (+https://observatoriodetaxas.tec.br)"})
            r.raise_for_status()
            itens = extrai(r.json())
            if not itens:
                raise ValueError("resposta sem itens")
        except Exception as exc:                          # rede, formato, fonte fora do ar
            print(f"[calendario] {nome}: {exc}; mantida a conferência de "
                  f"{(anterior.get(nome) or {}).get('conferido_em', 'nunca')}.", file=sys.stderr)
            continue
        novo[nome] = {"url": url, "itens": itens, "conferido_em": agora}
        print(f"[calendario] {nome}: {len(itens)} itens.")
    if novo != anterior:
        SAIDA.write_text(json.dumps(novo, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
