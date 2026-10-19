"""Golden files anonimizados do comprovante (RELEXP) e do demonstrativo (R0201).

Regenerar (mudanca intencional): set PENNA_REGENERAR_GOLDEN=1 e rodar este modulo.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from penna.remittance import establishment
from penna.remittance.receipt import montar_comprovante
from penna.remittance.statement import secao_apac
from tests.test_golden_txt import LINHA_REFERENCIA

PASTA = Path(__file__).resolve().parent / "fixtures"
EST = {"nome": "ESTABELECIMENTO EXEMPLO", "sigla": "EXEMPLO", "cgc": "12345678000195",
       "destino": "SECRETARIA MUNICIPAL DE SAUDE EXEMPLO", "indicador": "M", "cnes": "1234567"}
RESUMO = {"competencia": "202606", "arquivo": "APCEX26P.JUN", "registros": 6, "qtde_apacs": 1,
          "tipo": "3", "substituida": "000123"}


def _comprovante() -> bytes:
    return "\r\n".join(montar_comprovante(RESUMO, EST, "01/07/2026")).encode("cp1252")


def _demonstrativo() -> bytes:
    descricoes = {"090501003": "OCI AVALIACAO INICIAL EM OFTALMOLOGIA"}
    with mock.patch.object(establishment, "regras_do_procedimento", return_value=["0009"]):
        return secao_apac(LINHA_REFERENCIA, 1, EST, descricoes).encode("cp1252")


class TestRemessaGolden(unittest.TestCase):
    def _conferir(self, nome: str, gerado: bytes) -> None:
        alvo = PASTA / nome
        if os.environ.get("PENNA_REGENERAR_GOLDEN") == "1":
            alvo.write_bytes(gerado)
        self.assertEqual(gerado, alvo.read_bytes())

    def test_comprovante(self):
        self._conferir("comprovante_referencia.prn", _comprovante())

    def test_demonstrativo(self):
        self._conferir("demonstrativo_referencia.txt", _demonstrativo())


if __name__ == "__main__":
    unittest.main()
