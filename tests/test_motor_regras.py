"""Invariantes do motor de validação (independentes das regras individuais)."""
from __future__ import annotations

import unittest

from penna.validation import CATALOGO_CODIGOS, SEVERIDADE_PADRAO
from penna.validation.context import ContextoValidacao
from penna.validation.rules import REGRAS_DA_LINHA, REGRAS_DO_ITEM

TODAS = (*REGRAS_DA_LINHA, *REGRAS_DO_ITEM)


class TestRegistroDeRegras(unittest.TestCase):
    def test_nomes_unicos(self):
        nomes = [r.nome for r in TODAS]
        self.assertEqual(len(nomes), len(set(nomes)))

    def test_todo_codigo_emitido_esta_no_catalogo(self):
        emitidos = {cod for r in TODAS for cod in r.codigos}
        self.assertLessEqual(emitidos, set(CATALOGO_CODIGOS))

    def test_todo_codigo_do_catalogo_tem_uma_regra_que_o_emite(self):
        emitidos = {cod for r in TODAS for cod in r.codigos}
        self.assertEqual(set(CATALOGO_CODIGOS) - emitidos, set())

    def test_numero_da_apac_e_a_primeira_regra(self):
        self.assertEqual(REGRAS_DA_LINHA[0].nome, "numero_apac")

    def test_regra_com_base_declara_o_texto_de_desativada(self):
        for r in TODAS:
            if r.base_ausente is not None:
                self.assertTrue(r.desativada, r.nome)

    def test_catalogo_e_severidade_cobrem_os_mesmos_codigos(self):
        self.assertEqual(set(CATALOGO_CODIGOS), set(SEVERIDADE_PADRAO))


class TestBasesAusentes(unittest.TestCase):
    def test_contexto_vazio_desativa_todas_as_regras_com_base(self):
        ctx = ContextoValidacao()
        desativadas = [r for r in TODAS if r.esta_desativada(ctx, sigtap_ativo=True)]
        self.assertTrue(desativadas)
        sem_sigtap = [r for r in TODAS if r.esta_desativada(ctx, sigtap_ativo=False)]
        self.assertTrue(all(not r.sigtap for r in sem_sigtap))
        self.assertLess(len(sem_sigtap), len(desativadas))


if __name__ == "__main__":
    unittest.main()
