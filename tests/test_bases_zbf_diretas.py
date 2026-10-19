"""Bases .ZBF versionadas direto em dados/bases_sia devem ser carregadas."""
from __future__ import annotations

import unittest
from unittest import mock

from penna import reference as bases
from penna.reference import tables as bases_tables

ESPERADO = {"S_CID": 14270, "S_PAPA": 4084, "S_PAHA": 65417, "S_PAREGR": 19888}


class TestZbfDiretoNaPasta(unittest.TestCase):
    def test_carrega_zbf_de_dir_local_sem_c_apac(self):
        inexistente = bases.bundled_tables_dir().parent / "_pasta_que_nao_existe_"
        with mock.patch.object(bases_tables, "legacy_install_dir", return_value=inexistente):
            for nome, total in ESPERADO.items():
                with self.subTest(tabela=nome):
                    registros = bases.carregar_tabela(nome)
                    self.assertIsNotNone(registros)
                    self.assertEqual(len(registros), total)

    def test_ordem_dbf_depois_zbf_direto_depois_backup(self):
        caminhos = [c.name for c in bases_tables._caminhos_candidatos("S_CID", bases.bundled_tables_dir())]
        self.assertEqual(caminhos[:4], ["S_CID.DBF", "S_CID.dbf", "S_CID.ZBF", "S_CID.zbf"])


if __name__ == "__main__":
    unittest.main()
