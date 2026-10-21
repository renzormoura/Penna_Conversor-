"""Correcoes vindas de uma planilha real: linhas em branco, CPF sem zero e situacao de rua."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from penna.cards import montar_ficha
from penna.cards.text import formatar_cpf
from penna.layout import carregar_planilha
from penna.remittance import formatting
from penna.remittance.statement import secao_apac
from tests.test_golden_txt import LINHA_REFERENCIA

EST = {"nome": "EST", "sigla": "", "cgc": "12345678000195", "destino": "D", "indicador": "M", "cnes": "1234567"}


class TestLinhasEmBranco(unittest.TestCase):
    def _planilha(self, linhas):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        caminho = Path(tmp.name) / "p.xlsx"
        pd.DataFrame(linhas).to_excel(caminho, index=False)
        return caminho

    def test_linhas_totalmente_vazias_sao_ignoradas(self):
        vazia = {k: "" for k in LINHA_REFERENCIA}
        caminho = self._planilha([LINHA_REFERENCIA, vazia, vazia, dict(LINHA_REFERENCIA, Numero_Apac="3326700000025")])
        df = carregar_planilha(caminho)
        self.assertEqual(list(df["Numero_Apac"]), ["3326700000017", "3326700000025"])

    def test_linha_com_algum_dado_e_mantida(self):
        parcial = {k: "" for k in LINHA_REFERENCIA}
        parcial["Nome_Paciente"] = "SEM NUMERO"
        df = carregar_planilha(self._planilha([LINHA_REFERENCIA, parcial]))
        self.assertEqual(len(df), 2)  # sem APAC mas com dado: o validador deve acusar

    def test_planilha_so_com_linhas_vazias_fica_vazia(self):
        vazia = {k: "" for k in LINHA_REFERENCIA}
        self.assertTrue(carregar_planilha(self._planilha([vazia, vazia])).empty)


class TestCpfSemZeroAEsquerda(unittest.TestCase):
    CASOS = {
        "2937892744": "029.378.927-44",     # 10 digitos: o Excel comeu o zero
        "210208767": "002.102.087-67",      # 9 digitos
        "188.944.777-38": "188.944.777-38",
        "18894477738": "188.944.777-38",
        "070.481.137-58\n": "070.481.137-58",
        "": "",
    }

    def test_ficha_completa_e_formata(self):
        for cru, esperado in self.CASOS.items():
            with self.subTest(cru=cru):
                self.assertEqual(formatar_cpf(cru), esperado)

    def test_demonstrativo_completa_e_formata(self):
        for cru, esperado in self.CASOS.items():
            with self.subTest(cru=cru):
                self.assertEqual(formatting.cpf(cru), esperado)

    def test_valor_que_nao_e_cpf_fica_como_esta(self):
        self.assertEqual(formatar_cpf("12345678901234"), "12345678901234")
        self.assertEqual(formatting.cpf("abc"), "abc")

    def test_ficha_usa_o_cpf_completo(self):
        ficha = montar_ficha(dict(LINHA_REFERENCIA, Cpf_Paciente="2937892744"))
        self.assertEqual(ficha["sobrescritas"]["K9"], "029.378.927-44")


class TestSituacaoDeRuaNoDemonstrativo(unittest.TestCase):
    def test_aparece_com_o_valor_da_planilha(self):
        for valor, esperado in (("N", "N"), ("S", "S"), ("", "N")):
            with self.subTest(valor=valor):
                texto = secao_apac(dict(LINHA_REFERENCIA, Situacao_De_Rua=valor), 1, EST, {})
                self.assertIn(f" SITUACAO DE RUA: {esperado}", texto)


if __name__ == "__main__":
    unittest.main()
