"""Testes do ciclo da remessa (apac_mag_remessa): registro, comprovante,
demonstrativo e o historico que alimenta o aviso oficial 010084."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apac_mag_remessa as rem


def linha_base(**substituicoes):
    linha = {
        "Competencia": "202606",
        "Numero_Apac": "3326703612353",
        "Cnes_Executante": "4234316",
        "Nome_Paciente": "MARIA DE SOUZA",
        "Nome_Da_Mae": "JOSEFA DE SOUZA",
        "Data_Nascimento": "15061955",
        "Cep": "26700000",
        "Raca": "01",
        "Logradouro": "081",
        "Rua": "FABIO ARAO REIS",
        "Numero_Endereco": "340",
        "Codigo_Municipio": "3302809",
        "Sexo": "F",
        "Cod_Procedimento": "0905010035",
        "Cbo": "225265",
        "Quantidade": "1",
        "Sec1_Cod_Procedimento": "0211060232",
        "Sec1_Cbo": "225265",
        "Sec1_Quantidade": "1",
        "Cid_Princ": "H40",
        "Inicio_Validade": "20260601",
        "Fim_Validade": "20260630",
        "Data_Alta_Obito": "20260602",
        "Data_Solicitacao": "20260601",
        "Motivo_Saida": "11",
        "Nome_Profissional": "SERGIO ROBERTO MATOS",
        "Medico_Cns": "712345678901235",
        "Autorizador_Nome": "FERNANDA LOPES ALVES",
        "Autorizador_Cns": "712345678901236",
        "Cod_Orgao_Emiss": "M330280001",
    }
    linha.update(substituicoes)
    return linha


class _DF:
    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        for linha in self._linhas:
            yield None, linha


# Estabelecimento fixo do comprovante: o teste não depende do config real
# (penna_config.json) de cada máquina — dados fictícios de propósito.
_ESTABELECIMENTO_TESTE = {
    "nome": "CENTRO DE ESPECIALIDADES OFTALCEOF",
    "sigla": "",
    "cgc": "11111111000111",
    "destino": "SECRETARIA MUNICIPAL DE SAUDE DE MENDES",
    "indicador": "M",
    "cnes": "",
}


class TestRegistro(unittest.TestCase):
    def test_registrar_remessa_gera_pacote_completo(self):
        with tempfile.TemporaryDirectory() as pasta:
            txt = Path(pasta) / "APCEO26P.JUN"
            txt.write_bytes(b"01#APAC...(conteudo de teste)")
            registro = rem.registrar_remessa(txt, _DF([linha_base()]), tipo="2",
                                             pasta_base=Path(pasta) / "remessas")
            pasta_remessa = Path(registro["pasta"])
            self.assertTrue((pasta_remessa / "remessa.json").exists())
            self.assertTrue((pasta_remessa / "apacs.txt").exists())
            self.assertTrue((pasta_remessa / txt.name).exists())
            self.assertEqual(registro["tipo"], "2")
            self.assertEqual(registro["qtde_apacs"], 1)
            self.assertEqual(registro["competencia"], "202606")
            numeros = (pasta_remessa / "apacs.txt").read_text(encoding="cp1252").split()
            self.assertEqual(numeros, ["3326703612353"])

    def test_historico_detecta_apac_exportada(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta) / "remessas"
            txt = Path(pasta) / "arquivo.JUN"
            txt.write_bytes(b"x")
            rem.registrar_remessa(txt, _DF([linha_base(), linha_base(Numero_Apac="3326703612397")]),
                                  pasta_base=base)
            historico = rem.apacs_exportadas(base)
            self.assertIn("3326703612353", historico)
            self.assertIn("3326703612397", historico)
            self.assertNotIn("9999999999999", historico)
            # sem pasta, historico vazio (nunca travar)
            self.assertEqual(rem.apacs_exportadas(Path(pasta) / "vazia"), set())

    def test_resumo_conta_apacs_e_registros(self):
        resumo = rem.calcular_resumo(_DF([linha_base(), linha_base(Numero_Apac="3326703612397")]))
        self.assertEqual(resumo["qtde_apacs"], 2)
        self.assertEqual(resumo["competencia"], "202606")
        # 2 APACs -> 2 blocos 14 + 2 blocos 06 + 4 blocos 13 + header
        self.assertEqual(resumo["registros"], 9)


class TestComprovante(unittest.TestCase):
    def test_comprovante_no_formato_relexp(self):
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(rem, "_dados_estabelecimento",
                                  return_value=dict(_ESTABELECIMENTO_TESTE)):
            resumo = rem.calcular_resumo(_DF([linha_base()]))
            resumo.update({"arquivo": "APCEO26P.JUN", "tipo": "1", "pasta": pasta})
            destino = rem.gerar_comprovante(resumo, destino=Path(pasta) / "comprovante.PRN")
            conteudo = destino.read_bytes().decode("cp1252")
            self.assertIn("COMPROVANTE DE REMESSA APAC-MAG", conteudo)
            self.assertIn("ORGAO RESPONSVEL PELA INFORMACAO", conteudo)
            self.assertIn("NOME   : CENTRO DE ESPECIALIDADES OFTAL", conteudo)
            self.assertIn("C.G.C. : 11.111.111/0001-11", conteudo)
            self.assertIn("SECRETARIA DE SAUDE DESTINO DOS A.P.A.C.(s)", conteudo)
            self.assertIn("NOME  : SECRETARIA MUNICIPAL DE SAUDE DE MENDES", conteudo)
            self.assertIn("ORGAO (M)UNICIPAL OU (E)STADUAL : M", conteudo)
            self.assertIn("NOME : APCEO26P.JUN", conteudo)
            self.assertIn("REGISTROS GRAVADOS : 00005", conteudo)
            self.assertIn("PAC(s) : 000001", conteudo)
            self.assertIn("IDENT. PROCESSAMENTO : 1-NORMAL", conteudo)
            self.assertIn("Carimbo e", conteudo)
            # CRLF como no arquivo do antigo
            self.assertIn("\r\n", conteudo)

    def test_comprovante_substituicao_mostra_campo(self):
        with tempfile.TemporaryDirectory() as pasta:
            resumo = rem.calcular_resumo(_DF([linha_base()]))
            resumo.update({"arquivo": "X.JUN", "tipo": "3", "substituida": "APCEO26A",
                           "pasta": pasta})
            destino = rem.gerar_comprovante(resumo, destino=Path(pasta) / "c.PRN")
            conteudo = destino.read_bytes().decode("cp1252")
            self.assertIn("3-SUBSTITUICAO", conteudo)
            self.assertIn("REMESSA A SUBSTITUIR: APCEO26A", conteudo)


class TestDemonstrativo(unittest.TestCase):
    def test_demonstrativo_estilo_r0201(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = rem.gerar_demonstrativo(_DF([linha_base()]),
                                              destino=Path(pasta) / "demo.TXT")
            conteudo = destino.read_bytes().decode("cp1252")
            self.assertIn("DEMONSTRATIVO DE APAC MAGNETICO", conteudo)
            self.assertIn("NUMERO DO APAC: 332670361235-3", conteudo[:600])  # apac+DV formatado
            self.assertIn("NOME:               MARIA DE SOUZA", conteudo)
            self.assertIn("DATA DE NASCIMENTO: 15/06/1955", conteudo)
            self.assertIn("SEXO: FEMININO", conteudo)
            self.assertIn("RACA: 01 BRANCA", conteudo)
            self.assertIn("C.I.D. PRINCIPAL         H40", conteudo)
            self.assertIn("PROCEDIMENTOS REALIZADOS:", conteudo)
            self.assertIn("090501003-5", conteudo)
            self.assertIn("021106023-2", conteudo)
            self.assertIn("MOTIVO DE SAIDA   : 11 / ALTA CURADO", conteudo)
            self.assertIn("COD.ORGAO EMISS.: M330280001", conteudo)
            self.assertIn("\r\n", conteudo)

    def test_demonstrativo_multiplas_apacs(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = rem.gerar_demonstrativo(
                _DF([linha_base(), linha_base(Numero_Apac="3326703612397", Nome_Paciente="JOAO PEREIRA")]),
                destino=Path(pasta) / "demo2.TXT")
            conteudo = destino.read_bytes().decode("cp1252")
            self.assertIn("PAG.:    1", conteudo)
            self.assertIn("PAG.:    2", conteudo)
            self.assertIn("JOAO PEREIRA", conteudo)


if __name__ == "__main__":
    unittest.main()
