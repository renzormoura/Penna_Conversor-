"""Testes do modulo de bases SIA (penna.reference).

Os testes unitarios usam DBFs sinteticos gerados aqui (sem depender de
C:/APAC); os de integracao rodam so quando as bases reais existirem.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from penna import reference as bases


def montar_dbf(campos, registros: list[dict]) -> bytes:
    """Gera um DBF III em memoria: campos=[(nome, tam)], registros=[{campo: valor}]."""
    hlen = 32 + 32 * len(campos) + 1
    rlen = 1 + sum(tam for _, tam in campos)
    header = bytearray()
    header += b"\x03"                        # versao dBase III
    header += b"\x1d\x07\x09"                # data (3 bytes, nao usada pelo leitor)
    header += struct.pack("<I", len(registros))
    header += struct.pack("<H", hlen)
    header += struct.pack("<H", rlen)
    header += b"\x00" * 20
    for nome, tam in campos:
        entrada = bytearray()
        entrada += nome.encode("ascii")[:11].ljust(11, b"\0")
        entrada += b"C"                      # tipo caractere
        entrada += b"\x00" * 4
        entrada += bytes([tam])
        entrada += b"\x00" * 15
        header += entrada
    header += b"\x0D"
    corpo = bytearray()
    for registro in registros:
        linha = bytearray(b" ")
        for nome, tam in campos:
            linha += str(registro.get(nome, ""))[:tam].ljust(tam).encode("cp850")
        corpo += linha
    return bytes(header + corpo + b"\x1A")


def montar_zbf(caminho: Path, campos, registros) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    nome_interno = caminho.stem.upper() + ".DBF"
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome_interno, montar_dbf(campos, registros))


class TestLeitorDbf(unittest.TestCase):
    def test_le_dbf_sintetico(self):
        dados = montar_dbf([("PA_ID", 9), ("PA_DC", 10)], [{"PA_ID": "090501003", "PA_DC": "OCI AVAL"}])
        registros = bases.ler_dbf(dados)
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["PA_ID"], "090501003")
        self.assertEqual(registros[0]["PA_DC"], "OCI AVAL")

    def test_bytes_invalidos_devolvem_none(self):
        self.assertIsNone(bases.ler_dbf(b"nao e um dbf"))
        self.assertIsNone(bases.ler_dbf(b""))

    def test_le_zbf_sintetico(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "S_TESTE.ZBF"
            montar_zbf(caminho, [("CEP", 8)], [{"CEP": "26700000"}])
            registros = bases.ler_zbf(caminho)
            self.assertEqual(registros[0]["CEP"], "26700000")


class TestCacheEBusca(unittest.TestCase):
    def test_carregar_tabela_de_diretorio_com_cache(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            (base / "S_TESTE.DBF").write_bytes(
                montar_dbf([("COD", 4)], [{"COD": "A001"}])
            )
            registros = bases.carregar_tabela("S_TESTE", diretorio=base)
            self.assertEqual(registros[0]["COD"], "A001")
            # segunda chamada vem do cache (mesmo objeto)
            self.assertIs(registros, bases.carregar_tabela("S_TESTE", diretorio=base))

    def test_tabela_ausente_devolve_none(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.assertIsNone(bases.carregar_tabela("S_INEXISTENTE", diretorio=Path(pasta)))

    def test_preferencia_dbf_sobre_backup_zbf(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            montar_zbf(base / "BACKUP" / "202601" / "S_TESTE.ZBF",
                       [("COD", 10)], [{"COD": "DOBACKUP"}])
            registros = bases.carregar_tabela("S_TESTE", diretorio=base)
            # sem DBF avulso, cai no backup mais recente
            self.assertEqual(registros[0]["COD"], "DOBACKUP")
            (base / "S_TESTE.DBF").write_bytes(montar_dbf([("COD", 10)], [{"COD": "AVULSO"}]))
            registros = bases.carregar_tabela("S_TESTE", diretorio=base)
            self.assertEqual(registros[0]["COD"], "AVULSO")


class TestFiltros(unittest.TestCase):
    REGISTROS = [
        {"PAHA_CMP": "202512", "PAHA_PA": "010101001", "PAHA_HA": "1701"},
        {"PAHA_CMP": "202605", "PAHA_PA": "010101001", "PAHA_HA": "3801"},
        {"PAHA_CMP": "202605", "PAHA_PA": "090501003", "PAHA_HA": "3802"},
    ]

    def test_filtrar_por_competencia_pega_vigente(self):
        vigentes = bases.filtrar_por_competencia(self.REGISTROS, "PAHA_CMP", "202606")
        competencias = {r["PAHA_CMP"] for r in vigentes}
        self.assertEqual(competencias, {"202605"})

    def test_filtrar_por_competencia_sem_futuro(self):
        vigentes = bases.filtrar_por_competencia(self.REGISTROS, "PAHA_CMP", "202601")
        self.assertEqual({r["PAHA_CMP"] for r in vigentes}, {"202512"})

    def test_filtrar_por_faixa(self):
        registros = [{"CMP_INI": "200801", "CMP_FIM": "999999", "CD_COD": "H40"}]
        self.assertEqual(len(bases.filtrar_por_faixa(registros, "CMP_INI", "CMP_FIM", "202606")), 1)
        self.assertEqual(len(bases.filtrar_por_faixa(registros, "CMP_INI", "CMP_FIM", "200601")), 0)

    def test_habilitacoes_do_cnes(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            (base / "XUPSHA.DBF").write_bytes(montar_dbf(
                [("UPSHA_UPS", 7), ("UPSHA_HA", 4), ("UPSHA_INI", 6), ("UPSHA_FIM", 6)],
                [{"UPSHA_UPS": "4234316", "UPSHA_HA": "3801", "UPSHA_INI": "202409", "UPSHA_FIM": "999999"},
                 {"UPSHA_UPS": "4234316", "UPSHA_HA": "0501", "UPSHA_INI": "202601", "UPSHA_FIM": "202603"}],
            ))
            ativas = bases.carregar_habilitacoes_cnes("4234316", "202606", diretorio=base)
            self.assertEqual(ativas, {"3801"})  # 0501 venceu em 202603


class TestIntegracaoBasesReais(unittest.TestCase):
    def test_bases_versionadas_do_projeto_carregam(self):
        for tabela, minimo in (("S_PA", 1000), ("S_PAHA", 1000), ("S_PAPA", 100),
                               ("S_PAREGR", 100), ("S_CID", 1000), ("S_DEPARA", 100)):
            registros = bases.carregar_tabela(tabela)
            if registros is None:
                self.skipTest(f"base {tabela} nao disponivel nesta maquina")
            self.assertGreaterEqual(len(registros), minimo, tabela)

    def test_xupsha_do_projeto(self):
        habilitacoes = bases.carregar_habilitacoes_cnes("4234316", "202606")
        if habilitacoes is None:
            self.skipTest("XUPSHA nao disponivel nesta maquina")
        self.assertIn("3801", habilitacoes)


if __name__ == "__main__":
    unittest.main()
