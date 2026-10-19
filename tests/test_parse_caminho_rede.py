"""Regressao do parse_dropped_path para caminhos de REDE (UNC).

Pedido do usuario (aba Banco de Dados): acessar o Excel em outro
computador/servidor. O parser antigo fazia `.replace("\\\\", "\\")`
cego — colar um UNC danificava o caminho (`\\servidor\...` virava
`\servidor\...`, inacessivel). O fix preserva as duas primeiras barras
do prefixo UNC e mantem o comportamento anterior para caminhos locais.
"""
from __future__ import annotations

import unittest

from penna.services.files import parse_dropped_path


class ParseUncTests(unittest.TestCase):
    def test_unc_colidado_e_preservado(self):
        caminho = parse_dropped_path("\\\\SERVIDOR\\Pacientes\\banco.xlsx")
        self.assertEqual(caminho, "\\\\SERVIDOR\\Pacientes\\banco.xlsx")

    def test_unc_entre_chaves_e_preservado(self):
        caminho = parse_dropped_path('{"\\\\SERVIDOR\\Pacientes\\banco.xlsx"}')
        self.assertEqual(caminho, "\\\\SERVIDOR\\Pacientes\\banco.xlsx")

    def test_unc_com_file_url_e_preservado(self):
        caminho = parse_dropped_path("file://\\\\SERVIDOR\\Pacientes\\banco.xlsx")
        self.assertEqual(caminho, "\\\\SERVIDOR\\Pacientes\\banco.xlsx")

    def test_local_continua_colapsando_barras_duplas_internas(self):
        caminho = parse_dropped_path("C:\\\\Dados\\\\banco.xlsx")
        self.assertEqual(caminho, "C:\\Dados\\banco.xlsx")

    def test_local_com_barras_normais_passa_igual(self):
        caminho = parse_dropped_path("C:/Dados/banco.xlsx")
        self.assertEqual(caminho, "C:\\Dados\\banco.xlsx")


if __name__ == "__main__":
    unittest.main()
