"""Normalizacao unica de datas (gerador e validador) para AAAAMMDD."""
from __future__ import annotations

import unittest

import penna.layout as g
from penna.core import normalize_date
from tests.test_validador_exportacao import linha_base, validar_linha

CAMPOS = ["Inicio_Validade", "Fim_Validade", "Data_Solicitacao", "Data_Autorizacao",
          "Data_Alta_Obito", "Data_Emissao"]
FORMATOS = ["20260615", "15/06/2026", "15062026", "2026-06-15", "2026-06-15 00:00:00",
            "2026-06-15T10:30:00"]


class TestNormalizeDate(unittest.TestCase):
    def test_formatos(self):
        for entrada in FORMATOS:
            with self.subTest(entrada=entrada):
                self.assertEqual(normalize_date(entrada), "20260615")

    def test_invalida(self):
        for entrada in ["31/02/2026", "20261340", "abc", "99999999", ""]:
            with self.subTest(entrada=entrada):
                self.assertEqual(normalize_date(entrada), "")


class TestGeradorDatas(unittest.TestCase):
    def test_todos_formatos_geram_mesmo_txt(self):
        for campo in CAMPOS:
            referencia = g.build_body_block(linha_base(**{campo: "20260615"}))
            self.assertIn("20260615", referencia, campo)
            for entrada in FORMATOS:
                with self.subTest(campo=campo, entrada=entrada):
                    self.assertEqual(g.build_body_block(linha_base(**{campo: entrada})), referencia)


class TestValidadorDatas(unittest.TestCase):
    def _erros(self, **kw):
        return [o for o in validar_linha(linha_base(**kw)) if o.tipo == "ERR"]

    def test_data_invalida_bloqueia(self):
        for campo in CAMPOS:
            with self.subTest(campo=campo):
                erros = self._erros(**{campo: "31/02/2026"})
                self.assertTrue(any(campo.upper() in o.descricao.upper() for o in erros), erros)

    def test_formatos_validos_nao_bloqueiam(self):
        for campo in CAMPOS:
            for entrada in FORMATOS:
                with self.subTest(campo=campo, entrada=entrada):
                    erros = self._erros(**{campo: entrada})
                    self.assertFalse(any(campo.upper() in o.descricao.upper() for o in erros), erros)


if __name__ == "__main__":
    unittest.main()
