"""Mês dos formularios: competência no cabeçalho do TXT e extensão fixa
do nome do arquivo final (padrão do programa antigo — APCEO26P.JUN).

Cobre as duas metades do pedido:
1) o sistema ANALISA de qual mês são os formularios e coloca isso no
   cabeçalho '01#APAC<competencia>...' (mesmo sem a coluna Competencia,
   mesmo com a data em DDMMAAAA/MM/AAAA/datetime);
2) o nome do arquivo final é livre, mas o FINAL é fixo pelo mês
   (extensão .JUN/.JUL/... derivada da competência).
"""
from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from penna.core import normalize_competence, resolve_competence
from apac_mag_gerador import (
    _montar_header,
    build_patient_lines,
    competencia_da_planilha,
    competence_from_row,
    extensao_mes_competencia,
    forcar_extensao_mes,
    sigla_mes_competencia,
)
try:
    from ui.app import nome_saida_sugerido
except ImportError:  # sem tkinter
    nome_saida_sugerido = None


class _DF:
    """DataFrame mínimo no formato consumido pelo gerador."""

    def __init__(self, linhas):
        self._linhas = linhas

    def iterrows(self):
        for linha in self._linhas:
            yield None, linha


def linha_formulario(**substituicoes):
    """Linha de formulário como a do APCEO26P.JUN: junho/2026."""
    linha = {
        "Numero_Apac": "3326703612353",
        "Cnes_Executante": "4234316",
        "Nome_Paciente": "MARIA DE SOUZA",
        "Nome_Da_Mae": "JOSEFA DE SOUZA",
        "Data_Nascimento": "15061955",
        "Cep": "26700000",
        "Raca": "01",
        "Logradouro": "081",
        "Rua": "FABIO ARAO REIS",
        "Cod_Procedimento": "0905010035",
        "Cbo": "225265",
        "Quantidade": "1",
        "Cid_Princ": "H40",
        "Inicio_Validade": "20260501",
        "Fim_Validade": "20260630",
        "Data_Solicitacao": "20260601",
        "Motivo_Saida": "11",
    }
    linha.update(substituicoes)
    return linha


class TestNormalizeCompetence(unittest.TestCase):
    """normalize_competence reconhece o formato REAL da célula."""

    def test_formatos_reconhecidos(self):
        casos = {
            "202606": "202606",
            "20260601": "202606",
            "30062026": "202606",
            "01/06/2026": "202606",
            "06/2026": "202606",
            "2026-06": "202606",
            "2026-06-01 00:00:00": "202606",
            datetime(2026, 6, 1): "202606",
        }
        for valor, esperado in casos.items():
            self.assertEqual(normalize_competence(valor), esperado, repr(valor))

    def test_valores_sem_mes_identificavel_devolvem_vazio(self):
        for valor in ("", "abc", "123", "000000", "132026", None):
            self.assertEqual(normalize_competence(valor), "", repr(valor))


class TestCompetenciaDoFormulario(unittest.TestCase):
    """competence_from_row analisa o formulário, não só a coluna Competencia."""

    def test_usa_coluna_competencia_em_qualquer_formato(self):
        self.assertEqual(competence_from_row({"Competencia": "202606"}), "202606")
        self.assertEqual(competence_from_row({"Competencia": "01/06/2026"}), "202606")
        self.assertEqual(competence_from_row({"Competencia": "06/2026"}), "202606")

    def test_sem_coluna_analisa_as_datas_do_formulario(self):
        linha = {"Fim_Validade": "30/06/2026", "Inicio_Validade": "01/05/2026"}
        self.assertEqual(competence_from_row(linha), "202606")

    def test_data_de_autorizacao_tem_prioridade_sobre_a_validade(self):
        linha = {"Data_Autorizacao": "09/06/2026", "Fim_Validade": "20260630"}
        self.assertEqual(competence_from_row(linha), "202606")

    def test_competencia_zerada_cai_nas_datas(self):
        linha = {"Competencia": "000000", "Data_Solicitacao": "20260601"}
        self.assertEqual(competence_from_row(linha), "202606")

    def test_sem_nada_preserva_largura_do_layout(self):
        # bloco 14 é posicional: 6 chars de competência, sempre
        self.assertEqual(competence_from_row({}), "000000")
        self.assertEqual(resolve_competence({}), "")


class TestCabecalhoDoTxt(unittest.TestCase):
    """O cabeçalho '01#APAC...' recebe o mês analisado nos formularios."""

    def test_cabecalho_competencia_derivada_das_datas(self):
        linha = linha_formulario(Competencia="")
        header = _montar_header(build_patient_lines(linha))
        self.assertTrue(header.startswith("01#APAC202606"), header)

    def test_cabecalho_competencia_em_formato_data(self):
        linha = linha_formulario(Competencia="01/06/2026")
        header = _montar_header(build_patient_lines(linha))
        self.assertTrue(header.startswith("01#APAC202606"), header)

    def test_competencia_da_planilha_pega_o_mes_das_linhas(self):
        self.assertEqual(
            competencia_da_planilha(_DF([linha_formulario(Competencia="")])),
            "202606",
        )
        self.assertEqual(
            competencia_da_planilha(_DF([{"Competencia": "06/2026"}])),
            "202606",
        )
        self.assertEqual(competencia_da_planilha(_DF([])), "")
        self.assertEqual(competencia_da_planilha(_DF([{}])), "")


class TestExtensaoDoMes(unittest.TestCase):
    """Final fixo do nome do arquivo: extensão igual ao mês da competência."""

    def test_sigla_e_extensao_por_mes(self):
        self.assertEqual(sigla_mes_competencia("202606"), "JUN")
        self.assertEqual(extensao_mes_competencia("202606"), ".JUN")
        self.assertEqual(extensao_mes_competencia("202601"), ".JAN")
        self.assertEqual(extensao_mes_competencia("202612"), ".DEZ")

    def test_sem_mes_nao_ha_extensao(self):
        self.assertEqual(sigla_mes_competencia(""), "")
        self.assertEqual(extensao_mes_competencia("000000"), "")
        self.assertEqual(extensao_mes_competencia("132026"), "")

    def test_forca_extensao_do_mes_sobre_o_nome_escolhido(self):
        casos = [
            ("meu_arquivo", "meu_arquivo.JUN"),
            ("meu_arquivo.txt", "meu_arquivo.JUN"),
            ("meu_arquivo.JUL", "meu_arquivo.JUN"),   # mês errado → corrigido
            ("meu_arquivo.jun", "meu_arquivo.JUN"),
            ("meu_arquivo.JUN", "meu_arquivo.JUN"),
        ]
        for nome, esperado in casos:
            resultado = forcar_extensao_mes(Path("C:/saida") / nome, "202606")
            self.assertEqual(resultado.name, esperado, nome)

    def test_sem_competencia_o_nome_fica_intacto(self):
        self.assertEqual(forcar_extensao_mes("meu.txt", "").name, "meu.txt")

    @unittest.skipIf(nome_saida_sugerido is None, "tkinter indisponível")
    def test_nome_sugerido_no_dialogo_usa_extensao_do_mes(self):
        self.assertEqual(
            nome_saida_sugerido(Path("base exemplo.xlsx"), "202606"),
            "base_exemplo_formatado.JUN",
        )
        self.assertEqual(
            nome_saida_sugerido(Path("C:/planilhas/apac junho.xlsx"), "202606"),
            "apac junho_formatado.JUN",
        )
        self.assertEqual(
            nome_saida_sugerido(Path("planilha.xlsx"), ""),
            "planilha_formatado.txt",
        )


if __name__ == "__main__":
    unittest.main()
