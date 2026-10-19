"""Testes dos caches de performance da validação.

Cobrem as três otimizações sem tocar na semântica das regras:

1. S_CID carregado UMA vez por validação (antes: uma carga por linha);
2. `_normalize_key` com memo (mesmo resultado, objeto reaproveitado);
3. `_caminhos_candidatos` memorizado e invalidado quando entra um backup.

Todos herméticos: não dependem de C:/APAC nem de rede.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from penna.reference import tables as bases_tables
import apac_mag_validador as v
from penna.core import resolve_row_value
from penna.core.rows import _normalize_key

from test_validador_sigtap import linha_base


class _DF:
    """DF mínimo com iterrows (mesmo formato aceito por validar_planilha)."""

    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        for indice, linha in enumerate(self._linhas):
            yield indice, linha


class TestCargaUnicaDoSidCid(unittest.TestCase):
    def test_s_cid_e_carregado_uma_vez_para_toda_a_planilha(self):
        """20 linhas com CID conhecido: era 20 cargas de S_CID, agora 1."""
        linhas = [linha_base(Cid_Princ="H40") for _ in range(20)]
        with mock.patch.object(
            v.bases, "carregar_tabela", wraps=v.bases.carregar_tabela
        ) as espi:
            ocorrencias = v.validar_planilha(
                _DF(linhas),
                base_ceps={"26700000"},
                catalogo_pa={},
                usar_sigtap=False,
                usar_remessa=False,
                cids_validos={"H40"},
            )
        cargas_cid = [
            chamada for chamada in espi.call_args_list
            if chamada.args and chamada.args[0] == "S_CID"
        ]
        self.assertEqual(len(cargas_cid), 1,
                         f"S_CID carregado {len(cargas_cid)}x (esperado 1)")
        # a validação roda inteira com o índice em memória
        self.assertIsInstance(ocorrencias, list)

    def test_registros_injetados_geram_indice_sem_recarregar(self):
        """cids_registros informado (formato dos testes): nenhuma carga."""
        linhas = [linha_base(Cid_Princ="N80", Sexo="M") for _ in range(5)]
        with mock.patch.object(
            v.bases, "carregar_tabela", wraps=v.bases.carregar_tabela
        ) as espi:
            ocorrencias = v.validar_planilha(
                _DF(linhas),
                base_ceps={"26700000"},
                catalogo_pa={},
                usar_sigtap=False,
                usar_remessa=False,
                cids_validos={"N80"},
                cids_registros=[{"CD_COD": "N80", "RESTRSEXO": "2"}],
            )
        self.assertEqual(
            [c for c in espi.call_args_list if c.args and c.args[0] == "S_CID"],
            [],
        )
        self.assertEqual([o.cod for o in ocorrencias].count("010041"), 5)


class TestMemoDaNormalizacao(unittest.TestCase):
    def test_memo_preserva_resultado_e_reaproveita_objeto(self):
        self.assertEqual(_normalize_key("Nome_Paciente"), "nome_paciente")
        self.assertEqual(_normalize_key("Nome Paciente"), "nome_paciente")
        self.assertEqual(_normalize_key("nome-paciente"), "nome_paciente")
        self.assertEqual(_normalize_key("Cod/Procedimento"), "cod_procedimento")
        # segundo acesso vem do memo (mesmo objeto)
        self.assertIs(_normalize_key("Nome_Paciente"), _normalize_key("Nome_Paciente"))

    def test_resolve_row_value_com_chaves_de_caso_misto(self):
        row = {"Nome_Paciente": "MARIA", "Competencia": "202606"}
        self.assertEqual(resolve_row_value(row, "nome_paciente"), "MARIA")
        self.assertEqual(resolve_row_value(row, "NOME-PACIENTE"), "MARIA")
        self.assertEqual(resolve_row_value(row, "Competencia ", "x"), "202606")
        self.assertEqual(resolve_row_value(row, "Inexistente"), "")


class TestCacheDeCaminhosCandidatos(unittest.TestCase):
    def test_memoriza_e_invalida_quando_aparece_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            primeira = bases_tables._caminhos_candidatos("S_PA", pasta)
            segunda = bases_tables._caminhos_candidatos("S_PA", pasta)
            self.assertIs(primeira, segunda, "candidatos não memorizados")

            backup = pasta / "BACKUP" / "209901"
            backup.mkdir(parents=True)
            zbf = backup / "S_PA.ZBF"
            zbf.write_bytes(b"")

            terceira = bases_tables._caminhos_candidatos("S_PA", pasta)
            self.assertIsNot(terceira, primeira, "cache não invalidado")
            self.assertIn(zbf, terceira)

    def test_candidatos_priorizam_dbf_sobre_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            dbf = pasta / "S_PA.DBF"
            dbf.write_bytes(b"")
            candidatos = bases_tables._caminhos_candidatos("S_PA", pasta)
            self.assertEqual(candidatos[0], dbf)


if __name__ == "__main__":
    unittest.main()
