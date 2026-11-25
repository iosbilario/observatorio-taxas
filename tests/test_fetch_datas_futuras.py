"""Séries com datas futuras (Meta Selic, 432) não podem parar de receber dias.

O SGS devolve a 432 dia a dia até a próxima reunião do Copom. Com só os
/ultimos/8, a partir de ~8 dias antes da reunião todos os pontos são futuros,
o fetch.py corta os oito e a série fica semanas sem dado. Foi assim que a
mudança de 06/08/2026 entrou como 09/09/2026 e a de 17/09/2026 como 28/10/2026.

    python -m unittest tests.test_fetch_datas_futuras -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fetch  # noqa: E402

HOJE = date(2026, 11, 25)


def dia(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def meta(d: date) -> str:
    """Meta fictícia com as datas reais de 2026: 14,25 até 05/08, 14,00 até 16/09, depois 13,75."""
    return "14.25" if d < date(2026, 8, 6) else "14.00" if d < date(2026, 9, 17) else "13.75"


def sgs(ultimos=None, data_inicial=None, data_final=None):
    """SGS simulado: a série vai até 09/12/2026, 14 dias depois de HOJE."""
    fim = date(2026, 12, 9)
    if ultimos:
        dias = [fim - timedelta(days=i) for i in range(ultimos)][::-1]
    else:
        a = datetime.strptime(data_inicial, "%d/%m/%Y").date()
        b = min(datetime.strptime(data_final, "%d/%m/%Y").date(), fim)
        dias = [a + timedelta(days=i) for i in range((b - a).days + 1)]
    return [{"data": dia(d), "valor": meta(d)} for d in dias]


class DatasFuturas(unittest.TestCase):

    def test_ultimos_8_sozinho_so_traz_datas_futuras(self):
        corte = (HOJE.year, HOJE.month, HOJE.day)
        self.assertFalse([p for p in sgs(ultimos=8) if fetch._chave_data(p["data"]) <= corte])

    def test_completa_janela_traz_os_dias_ate_hoje_sem_repetir(self):
        with mock.patch.object(fetch, "fetch_pontos", lambda base, cod, **kw: sgs(**kw)):
            novos = fetch.completa_janela("x", 432, sgs(ultimos=8), HOJE)
        datas = [p["data"] for p in novos]
        self.assertEqual(len(datas), len(set(datas)))
        self.assertEqual(datas[0], dia(HOJE - timedelta(days=fetch.JANELA_FUTURA_DIAS)))
        self.assertIn(dia(HOJE), datas)
        self.assertEqual(datas[-1], "09/12/2026")

    def test_serie_sem_data_futura_nao_faz_pedido_extra(self):
        mensal = [{"data": "01/10/2026", "valor": "0.1"}]
        with mock.patch.object(fetch, "fetch_pontos", side_effect=AssertionError("pedido extra")):
            self.assertIs(fetch.completa_janela("x", 433, mensal, HOJE), mensal)

    def test_coleta_preenche_o_buraco_e_acerta_as_datas_de_mudanca(self):
        """Histórico com o buraco real (dias até 13/07 e depois 29/07, 09/09 e
        28/10 a 04/11): depois de uma coleta, as mudanças caem em 06/08 e 17/09."""
        tem = [date(2026, 5, 1) + timedelta(days=i) for i in range(74)]          # até 13/07
        tem += [date(2026, 7, 29) + timedelta(days=i) for i in range(8)]         # 29/07 a 05/08
        tem += [date(2026, 9, 9) + timedelta(days=i) for i in range(8)]          # 09/09 a 16/09
        tem += [date(2026, 10, 28) + timedelta(days=i) for i in range(8)]        # 28/10 a 04/11
        historico = [{"data": dia(d), "valor": meta(d)} for d in tem]
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            (r / "data").mkdir(); (r / "docs" / "data").mkdir(parents=True)
            (r / "data" / "432_history.json").write_text(json.dumps(historico))
            cfg = {"base_url": "x", "series": [{"codigo": 432, "nome": "Meta Selic (% a.a.)"}]}

            class Relogio(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime(2026, 11, 25, 15, 0, tzinfo=tz)

            with mock.patch.multiple(fetch, DATA_DIR=r / "data", DOCS_DATA_DIR=r / "docs" / "data",
                                     CHANGELOG_PATH=r / "CHANGELOG.md", load_config=lambda: cfg,
                                     fetch_pontos=lambda base, cod, **kw: sgs(**kw), datetime=Relogio), \
                    mock.patch("builtins.print"):
                fetch.main()
            h = json.loads((r / "data" / "432_history.json").read_text())
        datas = [datetime.strptime(p["data"], "%d/%m/%Y").date() for p in h]
        self.assertEqual(datas[-1], HOJE)
        self.assertFalse([b for a, b in zip(datas, datas[1:]) if (b - a).days != 1])
        mudancas = [h[i]["data"] for i in range(1, len(h)) if h[i]["valor"] != h[i - 1]["valor"]]
        self.assertEqual(mudancas, ["06/08/2026", "17/09/2026"])


if __name__ == "__main__":
    unittest.main()
