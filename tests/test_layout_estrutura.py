"""Invariantes estruturais do layout (independentes do golden file)."""
from __future__ import annotations

import unittest
from dataclasses import fields

from penna.layout import ApacBody, body_from_row, render_txt
from penna.layout.constants import ACTION_WIDTH, BODY_WIDTH
from tests.test_config_seguro import EXEMPLO, config_em
from tests.test_golden_txt import LINHA_REFERENCIA


class TestApacBody(unittest.TestCase):
    def _corpo(self, linha=None):
        with config_em(EXEMPLO.read_text(encoding="utf-8")):
            return body_from_row(LINHA_REFERENCIA if linha is None else linha)

    def test_campos_somam_534_mais_tipo_e_espaco_final(self):
        corpo = self._corpo()
        total = sum(len(getattr(corpo, f.name)) for f in fields(ApacBody))
        self.assertEqual(total, BODY_WIDTH - len("14") - 1)
        self.assertEqual(len(corpo.render()), BODY_WIDTH)

    def test_linha_vazia_mantem_a_largura_fixa(self):
        corpo = self._corpo({})
        self.assertEqual(len(corpo.render()), BODY_WIDTH)
        self.assertEqual(corpo.competencia, "000000")

    def test_ordem_do_layout_e_a_ordem_de_declaracao(self):
        nomes = [f.name for f in fields(ApacBody)]
        self.assertEqual((nomes[0], nomes[1], nomes[-1]), ("competencia", "numero_apac", "emenda"))
        self.assertEqual(len(nomes), len(set(nomes)))


class TestRenderTxt(unittest.TestCase):
    def test_sem_linhas_so_o_crlf_final(self):
        self.assertEqual(render_txt([]), "\r\n")

    def test_ultimo_bloco_13_perde_o_padding_e_ha_header(self):
        with config_em(EXEMPLO.read_text(encoding="utf-8")):
            bloco = "13" + "202606" + "3326700000017" + "0905010035" + "225265" + "0000001"
            texto = render_txt([bloco.ljust(ACTION_WIDTH)])
        linhas = texto.split("\r\n")
        self.assertTrue(linhas[0].startswith("01#APAC"))
        self.assertEqual(len(linhas[1]), 44)
        self.assertTrue(texto.endswith("\r\n\r\n"))


if __name__ == "__main__":
    unittest.main()
