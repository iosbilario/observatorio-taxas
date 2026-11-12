"""
gerar_qr_pix.py — Gera docs/apoie/pix-qr.svg a partir de scripts/pix.py.

Ferramenta de manutenção, NÃO roda no workflow (o SVG é versionado). Exige a
biblioteca `segno` (pura Python, só para quem regenera):

    pip install segno
    python scripts/gerar_qr_pix.py

O QR leva exatamente o payload validado: módulos pretos sobre branco, sem
estilização, com a margem de 4 módulos que a especificação pede.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pix import PAYLOAD, validar  # noqa: E402

DESTINO = Path(__file__).resolve().parent.parent / "docs" / "apoie" / "pix-qr.svg"


def main() -> int:
    validar(PAYLOAD)
    import segno  # dependência só desta ferramenta

    qr = segno.make(PAYLOAD, error="m", micro=False, mode="byte")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    qr.save(str(DESTINO), kind="svg", scale=8, border=4, dark="#000000", light="#ffffff",
            xmldecl=False, svgns=True, title="QR Code Pix", nl=True, omitsize=True)
    print(f"{DESTINO.relative_to(DESTINO.parents[2])}: versão {qr.version}, correção {qr.error}, "
          f"{qr.symbol_size(scale=1, border=4)[0]} módulos com margem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
