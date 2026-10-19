"""Gate de tamanho maximo e de caracteres nao codificaveis (cp1252) do TXT."""
from __future__ import annotations

import unittest

import apac_mag_validador as v
from tests.test_validador_sigtap import linha_base, validar


def _achados(ocs, cod):
    return [o for o in ocs if o.cod == cod]


class TestTamanhoMaximo(unittest.TestCase):
    def test_texto_acima_da_largura_avisa_truncamento(self):
        ocs = validar(linha_base(Nome_Paciente="A" * 31))
        achado = _achados(ocs, "010092")
        self.assertEqual([o.tipo for o in achado], ["AVS"])
        self.assertIn("NOME_PACIENTE", achado[0].descricao)
        self.assertIn("31", achado[0].descricao)
        self.assertIn("30", achado[0].descricao)
        self.assertFalse(v.tem_erros(ocs), ocs)

    def test_no_limite_nao_avisa(self):
        self.assertEqual(_achados(validar(linha_base(Nome_Paciente="A" * 30)), "010092"), [])

    def test_larguras_dos_demais_campos(self):
        casos = {"Nome_Da_Mae": 30, "Rua": 30, "Numero_Endereco": 5, "Complemento": 10,
                 "Nome_Profissional": 30, "Autorizador_Nome": 30, "Bairro": 30, "Email": 40}
        for campo, largura in casos.items():
            with self.subTest(campo=campo):
                ok = validar(linha_base(**{campo: "B" * largura}))
                longo = validar(linha_base(**{campo: "B" * (largura + 1)}))
                self.assertEqual(_achados(ok, "010092"), [])
                self.assertEqual(len(_achados(longo, "010092")), 1)


class TestCaracteres(unittest.TestCase):
    def test_caractere_fora_do_cp1252_bloqueia(self):
        for texto in ("MARIA Ω", "JOÃO 😀", "ЖУК"):
            with self.subTest(texto=texto):
                ocs = validar(linha_base(Nome_Paciente=texto))
                achado = _achados(ocs, "010091")
                self.assertEqual([o.tipo for o in achado], ["ERR"])
                self.assertIn("NOME_PACIENTE", achado[0].descricao)

    def test_acentos_do_portugues_passam(self):
        ocs = validar(linha_base(Nome_Paciente="JOÃO ÇÃO ÁÉÍÓÚ âêô ü ñ"))
        self.assertEqual(_achados(ocs, "010091"), [])

    def test_controle_quebra_o_layout_e_bloqueia(self):
        for texto in ("MARIA\nSOUZA", "MARIA\tSOUZA", "MARIA\rSOUZA"):
            with self.subTest(texto=repr(texto)):
                self.assertEqual(len(_achados(validar(linha_base(Nome_Paciente=texto)), "010091")), 1)

    def test_gerador_nao_troca_por_interrogacao(self):
        import tempfile
        from pathlib import Path

        import pandas as pd

        import penna.layout as g
        from tests.test_config_seguro import EXEMPLO, config_em
        with tempfile.TemporaryDirectory() as td, config_em(EXEMPLO.read_text(encoding="utf-8")):
            with self.assertRaises(UnicodeEncodeError):
                g.exportar_txt(pd.DataFrame([linha_base(Nome_Paciente="MARIA Ω")]),
                               Path(td) / "saida.txt")


class TestCatalogo(unittest.TestCase):
    def test_codigos_novos_documentados_com_severidade(self):
        self.assertEqual(v.SEVERIDADE_PADRAO["010091"], "ERR")
        self.assertEqual(v.SEVERIDADE_PADRAO["010092"], "AVS")


if __name__ == "__main__":
    unittest.main()
