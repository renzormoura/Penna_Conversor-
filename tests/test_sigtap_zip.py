"""Parser do ZIP SIGTAP: mesmo esquema das tabelas DBF (sem rede)."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import apac_mag_sigtap_download as sig
import apac_mag_validador as v
from tests.test_validador_exportacao import linha_base, validar_linha

COMP = "202606"


def _txt(*campos: tuple) -> str:
    """Linha de largura fixa: campos = (valor, largura)."""
    return "".join(str(valor).ljust(larg)[:larg] for valor, larg in campos)


def linha_procedimento(codigo10, nome, sexo, qtmax, idmin_meses, idmax_meses):
    return _txt((codigo10, 10), (nome, 250), ("2", 1), (sexo, 1), (qtmax, 4), ("0", 4),
                ("0", 4), (idmin_meses, 4), (idmax_meses, 4), ("0", 12), ("0", 12),
                ("0", 12), ("01", 2), ("", 6), ("0", 4), (COMP, 6))


def linha_cid(cid, sexo):
    return _txt((cid, 4), (f"{cid} descricao", 100), ("N", 1), (sexo, 1), ("N", 1), ("0", 4))


def montar_zip(destino: Path, com_layout: bool = False) -> None:
    arquivos = {
        "tb_procedimento.txt": [
            linha_procedimento("0905010035", "OCI AVALIACAO INICIAL", "I", "0001", "0108", "1560"),
            linha_procedimento("0301010072", "CONSULTA", "F", "0002", "0000", "9999"),
        ],
        "tb_cid.txt": [linha_cid("H400", "I"), linha_cid("H401", "I"), linha_cid("N400", "M"),
                       linha_cid("O800", "F")],
        "rl_procedimento_compativel.txt": [
            _txt(("0905010035", 10), ("01", 2), ("0211060011", 10), ("01", 2), ("2", 1),
                 ("0001", 4), (COMP, 6)),
        ],
        "rl_procedimento_habilitacao.txt": [
            _txt(("0905010035", 10), ("1706", 4), ("0000", 4), (COMP, 6)),
        ],
        "rl_procedimento_regra_cond.txt": [_txt(("0905010035", 10), ("0001", 4))],
    }
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_STORED) as zf:
        for nome, linhas in arquivos.items():
            zf.writestr(nome, "\r\n".join(linhas) + "\r\n")
        if com_layout:
            # layout com a coluna de idade deslocada de proposito (+0, so prova o uso)
            zf.writestr("tb_cid_layout.txt",
                        "Coluna,Tamanho,Inicio,Fim,Tipo\r\nCO_CID,4,1,4,VARCHAR2\r\n"
                        "TP_SEXO,1,106,106,VARCHAR2\r\n")
        zf.writestr("filler.bin", b"\0" * 120_000)  # passa do limite de ZIP valido


class TestZipSigtapMesmoEsquemaDoDbf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        pasta = Path(cls._tmp.name)
        montar_zip(pasta / f"TabelaUnificada_{COMP}.zip", com_layout=True)
        with mock.patch.object(sig, "_dir_cache", return_value=pasta):
            sig.limpar_cache_memoria()
            cls.dados = sig.carregar_sigtap_competencia(COMP)
            sig.limpar_cache_memoria()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_s_pa_chaves_e_codigo_de_9_digitos(self):
        pa = {r["PA_ID"]: r for r in self.dados["S_PA"]}
        self.assertIn("090501003", pa)
        oci = pa["090501003"]
        self.assertEqual(oci["PA_DV"], "5")
        for chave in ("PA_IDADEMN", "PA_IDADEMX", "PA_QTDMAX", "PA_SECOBRI", "PA_SEXO", "PA_DC"):
            self.assertIn(chave, oci)
        for chave in ("PA_IDMIN", "PA_IDMAX", "PA_QTMAX"):
            self.assertNotIn(chave, oci)

    def test_s_pa_idade_em_anos_e_sexo_como_no_dbf(self):
        pa = {r["PA_ID"]: r for r in self.dados["S_PA"]}
        oci, consulta = pa["090501003"], pa["030101007"]
        self.assertEqual((oci["PA_IDADEMN"], oci["PA_IDADEMX"]), ("9", "130"))  # 108 e 1560 meses
        self.assertEqual((consulta["PA_IDADEMN"], consulta["PA_IDADEMX"]), ("0", "999"))
        self.assertEqual((oci["PA_SEXO"], consulta["PA_SEXO"]), ("A", "F"))
        self.assertEqual(oci["PA_QTDMAX"], "0001")

    def test_tabelas_relacionais_com_9_digitos(self):
        self.assertEqual(self.dados["S_PAPA"][0]["PAPA_PRINC"], "090501003")
        self.assertEqual(self.dados["S_PAPA"][0]["PAPA_SECUN"], "021106001")
        self.assertEqual(self.dados["S_PAHA"][0]["PAHA_PA"], "090501003")
        self.assertEqual(self.dados["S_PAHA"][0]["PAHA_HA"], "1706")
        self.assertEqual(self.dados["S_PAREGR"][0]["REG_PA"], "090501003")

    def test_s_cid_restricao_sexo_como_no_dbf_e_categoria_de_3(self):
        cid = {r["CD_COD"]: r["RESTRSEXO"] for r in self.dados["S_CID"]}
        self.assertEqual((cid["H400"], cid["N400"], cid["O800"]), ("5", "1", "2"))
        self.assertIn("H40", cid)  # categoria de 3 sintetizada
        self.assertEqual(cid["H40"], "5")


class TestZipAlimentaOValidador(unittest.TestCase):
    """As regras disparam com as tabelas vindas do ZIP (antes nunca disparavam)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        pasta = Path(cls._tmp.name)
        montar_zip(pasta / f"TabelaUnificada_{COMP}.zip")  # sem layout: posicoes padrao
        with mock.patch.object(sig, "_dir_cache", return_value=pasta):
            sig.limpar_cache_memoria()
            cls.dados = sig.carregar_sigtap_competencia(COMP)
            sig.limpar_cache_memoria()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_idade_maxima_dispara_com_catalogo_do_zip(self):
        catalogo = {r["PA_ID"]: r for r in self.dados["S_PA"]}
        catalogo["090501003"] = dict(catalogo["090501003"], PA_IDADEMX="60")  # forca limite
        ocorrencias = validar_linha(linha_base(Data_Nascimento="19550615"), ceps={"26700000"},
                                    pa=catalogo)
        self.assertTrue(any(o.cod == "000016" for o in ocorrencias), ocorrencias)

    def test_idade_minima_do_zip_dispara(self):
        catalogo = {r["PA_ID"]: r for r in self.dados["S_PA"]}
        ocorrencias = validar_linha(linha_base(Data_Nascimento="20200101"), ceps={"26700000"},
                                    pa=catalogo)
        alvo = [o for o in ocorrencias if o.cod == "000016"]
        self.assertEqual(len(alvo), 1)
        self.assertIn("MIN", alvo[0].descricao)

    def test_cid_de_3_caracteres_existe_na_tabela_do_zip(self):
        codigos = {r["CD_COD"] for r in self.dados["S_CID"]}
        self.assertLessEqual({"H40", "H400", "N40"}, codigos)


if __name__ == "__main__":
    unittest.main()
