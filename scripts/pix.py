"""
pix.py — Código Pix da página /apoie/ e validação do BR Code (EMV), só stdlib.

O payload abaixo foi gerado pelo C6 Bank em 11/11/2026 e NÃO deve ser
alterado à mão: qualquer mudança invalida o CRC16 e o pagamento. Para trocar,
gere um novo código no banco, cole aqui e rode:

    python scripts/pix.py                      # valida e mostra os campos
    python scripts/gerar_qr_pix.py             # regenera docs/apoie/pix-qr.svg

Validação (Manual de Padrões para Iniciação do Pix / BR Code, EMV MPM):
  - estrutura TLV completa, sem sobra;
  - 00 = "01" (formato), 01 = "11" (QR estático, reutilizável);
  - 26 com GUI br.gov.bcb.pix e chave;
  - 53 = "986" (BRL), 58 = "BR";
  - SEM o campo 54 (valor): o valor é livre, definido por quem paga;
  - 63 = CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF) sobre todo o
    payload até "6304", inclusive.
"""

from __future__ import annotations

import sys

PAYLOAD = ("00020101021126580014br.gov.bcb.pix01362ade5464-c4a9-44f3-97cf-f54c04115a67"
           "5204000053039865802BR5914LBP TECNOLOGIA6009SAO PAULO622905251M76NA649SMB03G83PKYVAQFB6304F3AF")

RECEBEDOR = "LBP TECNOLOGIA"
CIDADE = "SAO PAULO"


def tlv(s: str) -> list[tuple[str, str]]:
    """Lista [(id, valor)] de um bloco EMV. Levanta ValueError se malformado."""
    out, i = [], 0
    while i < len(s):
        if i + 4 > len(s):
            raise ValueError(f"cabeçalho truncado na posição {i}")
        ident, tam = s[i:i + 2], s[i + 2:i + 4]
        if not (ident.isdigit() and tam.isdigit()):
            raise ValueError(f"id/tamanho inválido na posição {i}: {s[i:i + 4]!r}")
        n = int(tam)
        if i + 4 + n > len(s):
            raise ValueError(f"campo {ident} ultrapassa o fim")
        out.append((ident, s[i + 4:i + 4 + n]))
        i += 4 + n
    return out


def crc16(dados: str) -> str:
    c = 0xFFFF
    for b in dados.encode("utf-8"):
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return f"{c:04X}"


def validar(payload: str = PAYLOAD) -> dict:
    """Valida o BR Code e devolve os campos. Levanta ValueError no primeiro erro."""
    campos = dict(tlv(payload))
    ordem = [i for i, _ in tlv(payload)]
    if ordem[0] != "00" or campos["00"] != "01":
        raise ValueError("campo 00 (formato) deve ser '01' e vir primeiro")
    if ordem[-1] != "63" or len(campos["63"]) != 4:
        raise ValueError("campo 63 (CRC) deve ser o último, com 4 caracteres")
    calc = crc16(payload[:-4])
    if calc != campos["63"]:
        raise ValueError(f"CRC16 inválido: calculado {calc}, informado {campos['63']}")
    if campos.get("01") != "11":
        raise ValueError("campo 01 deve ser '11' (QR estático, reutilizável)")
    if "54" in campos:
        raise ValueError("o código tem valor fixo (campo 54); a página exige valor livre")
    conta = dict(tlv(campos["26"]))
    if conta.get("00", "").lower() != "br.gov.bcb.pix" or not conta.get("01"):
        raise ValueError("campo 26 sem GUI br.gov.bcb.pix ou sem chave")
    if campos.get("53") != "986" or campos.get("58") != "BR":
        raise ValueError("moeda (53) ou país (58) inesperados")
    adicionais = dict(tlv(campos.get("62", "")))
    return {
        "recebedor": campos.get("59"), "cidade": campos.get("60"),
        "mcc": campos.get("52"), "moeda": campos["53"], "pais": campos["58"],
        "estatico": True, "valor_fixo": None, "txid": adicionais.get("05"),
        "tipo_chave": "aleatória (EVP)" if len(conta["01"]) == 36 and conta["01"].count("-") == 4 else "outra",
        "crc": campos["63"],
    }


if __name__ == "__main__":
    try:
        info = validar()
    except ValueError as e:
        print(f"INVÁLIDO: {e}")
        sys.exit(1)
    for k, v in info.items():
        print(f"{k}: {v}")
    print("OK: BR Code válido, estático, sem valor fixo.")
