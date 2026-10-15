"""TXT de referencia anonimizado (golden file): blocos 01 (header), 14, 06 e 13.

O arquivo tests/fixtures/apac_referencia.txt e um SNAPSHOT do gerador atual
para uma APAC ficticia (nenhum dado real; config de exemplo). Ele protege o
layout fiscal de mudancas acidentais byte a byte. Nao e uma amostra oficial:
quando uma mudanca de layout for intencional (ou confirmada contra um TXT real
do programa antigo), regenere com:

    set PENNA_REGENERAR_GOLDEN=1 && python -m unittest tests.test_golden_txt
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import apac_mag_gerador as g
from tests.test_config_seguro import EXEMPLO, config_em

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "apac_referencia.txt"

# APAC ficticia completa: principal + 2 secundarios, CID, acentos (cp1252).
LINHA_REFERENCIA = {
    "Competencia": "202606",
    "Numero_Apac": "3326700000017",
    "Cnes_Executante": "1234567",
    "Nome_Paciente": "JOÃO DA SILVA SAURO",
    "Nome_Da_Mae": "MARIA APARECIDA DA SILVA",
    "Data_Nascimento": "15061955",
    "Sexo": "M",
    "Raca": "01",
    "Cep": "26700000",
    "Logradouro": "081",
    "Rua": "RUA DAS FLORES",
    "Numero_Endereco": "340",
    "Complemento": "CASA 2",
    "Bairro": "CENTRO",
    "Codigo_Municipio": "3550308",
    "Telefone": "21987654321",
    "Email": "fulano@example.com",
    "Cpf_Paciente": "12345678909",
    "Cns_Paciente": "700000000000001",
    "Cod_Procedimento": "0905010035",
    "Cbo": "225265",
    "Quantidade": "1",
    "Sec1_Cod_Procedimento": "0211060232",
    "Sec1_Cbo": "225265",
    "Sec1_Quantidade": "1",
    "Sec2_Cod_Procedimento": "0211060100",
    "Sec2_Cbo": "225265",
    "Sec2_Quantidade": "2",
    "Cid_Princ": "H40",
    "Inicio_Validade": "20260501",
    "Fim_Validade": "20260630",
    "Data_Solicitacao": "20260601",
    "Data_Autorizacao": "20260602",
    "Data_Alta_Obito": "20260630",
    "Motivo_Saida": "11",
    "Nome_Profissional": "BELTRANO DE TAL",
    "Medico_Cns": "700000000000002",
    "Autorizador_Nome": "CICRANO DE TAL",
    "Autorizador_Cns": "700000000000003",
    "Cod_Orgao_Emiss": "M355030001",
}


def gerar_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as td, \
            config_em(EXEMPLO.read_text(encoding="utf-8")), \
            mock.patch.object(g, "_data_geracao", return_value="20260701"):
        saida = Path(td) / "saida.txt"
        g.exportar_txt(pd.DataFrame([LINHA_REFERENCIA]), saida)
        return saida.read_bytes()


class TestGoldenTxt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gerado = gerar_bytes()
        if os.environ.get("PENNA_REGENERAR_GOLDEN") == "1":
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_bytes(cls.gerado)
        cls.esperado = FIXTURE.read_bytes()

    def test_arquivo_identico_byte_a_byte(self):
        self.assertEqual(self.gerado, self.esperado)

    def test_estrutura_e_largura_dos_blocos(self):
        linhas = self.esperado.decode("cp1252").split("\r\n")
        self.assertEqual(linhas[-2:], ["", ""])  # termina com CRLF duplo
        linhas = linhas[:-2]
        tipos = [linha[:2] for linha in linhas]
        self.assertEqual(tipos, ["01", "14", "06", "13", "13", "13"])
        self.assertEqual(len(linhas[0]), 134)
        self.assertTrue(linhas[0].startswith("01#APAC202606000001"))
        self.assertEqual(len(linhas[1]), g.BLOCK_01_WIDTH)
        self.assertEqual([len(linha) for linha in linhas[3:5]], [g.BLOCK_03_WIDTH] * 2)
        self.assertEqual(len(linhas[5]), 44)  # ultimo 13 sem padding

    def test_cada_bloco_bate_com_o_golden(self):
        gerado = self.gerado.decode("cp1252").split("\r\n")
        esperado = self.esperado.decode("cp1252").split("\r\n")
        self.assertEqual(len(gerado), len(esperado))
        for i, (a, b) in enumerate(zip(gerado, esperado)):
            with self.subTest(linha=i, tipo=b[:2]):
                self.assertEqual(a, b)

    def test_golden_nao_contem_dado_real(self):
        texto = self.esperado.decode("cp1252")
        for real in ("4234316", "28580694001093", "MENDES", "OFTALMOLOGICAS"):
            self.assertNotIn(real, texto)


if __name__ == "__main__":
    unittest.main()
