"""Versão do cabeçalho '01#APAC...' escolhida pelo usuário por mês.

Cobre o pedido: o usuário escolhe a versão de cada mês (antes o sistema
sempre escrevia o automático 'Versao 04.01'). A escolha fica gravada no
penna_config.json (header.versao_escolhas), sobrepondo o histórico de
fábrica (header.versao_por_mes) e o padrão (header.versao), e o cabeçalho
usa o valor resolvido para a competência — sempre em 12 chars (134 no
header inteiro).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import apac_mag.config as config
from apac_mag_gerador import _montar_header, build_patient_lines
from ui.components import normalizar_versao


@contextmanager
def config_temporario(header_extra=None):
    """penna_config.json temporário no lugar do real (cache recarregado)."""
    original_path = config._config_path
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "penna_config.json"
        cfg = json.loads(json.dumps(config._FALLBACK))
        cfg["header"].update(header_extra or {})
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        config._config_path = lambda: path
        config.reload()
        try:
            yield path
        finally:
            config._config_path = original_path
            config.reload()


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


class TestGetVersao(unittest.TestCase):
    """get_versao resolve: escolha do usuário → histórico → padrão."""

    def test_padrao_automatico_quando_nao_ha_entradas(self):
        with config_temporario():
            self.assertEqual(config.get_versao("202606"), "Versao 04.01")
            self.assertEqual(config.get_versao(""), "Versao 04.01")
            self.assertEqual(config.get_versao("000000"), "Versao 04.01")

    def test_historico_do_mes(self):
        with config_temporario({"versao_por_mes": {"202603": "Versao 03.21"}}):
            self.assertEqual(config.get_versao("202603"), "Versao 03.21")
            # mês sem histórico continua no padrão
            self.assertEqual(config.get_versao("202606"), "Versao 04.01")

    def test_escolha_do_usuario_sobrepoe_historico_e_padrao(self):
        with config_temporario({
            "versao_por_mes": {"202603": "Versao 03.21"},
            "versao_escolhas": {"202606": "Versao 05.00"},
        }):
            self.assertEqual(config.get_versao("202606"), "Versao 05.00")  # escolha
            self.assertEqual(config.get_versao("202603"), "Versao 03.21")  # histórico
            self.assertEqual(config.get_versao("202607"), "Versao 04.01")  # padrão

    def test_aceita_formatos_de_data_da_competencia(self):
        with config_temporario({"versao_escolhas": {"202606": "Versao 03.21"}}):
            self.assertEqual(config.get_versao("01/06/2026"), "Versao 03.21")
            self.assertEqual(config.get_versao("20260601"), "Versao 03.21")


class TestSetVersaoMes(unittest.TestCase):
    """A escolha é persistida no arquivo (sobrevive a reinícios)."""

    def test_grava_e_remove_a_escolha_preservando_o_historico(self):
        with config_temporario({"versao_por_mes": {"202606": "Versao 04.01"}}) as path:
            self.assertTrue(config.set_versao_mes("202606", "Versao 03.19"))
            self.assertEqual(config.get_versao("202606"), "Versao 03.19")
            dados = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(dados["header"]["versao_escolhas"]["202606"], "Versao 03.19")
            self.assertEqual(dados["header"]["versao_por_mes"]["202606"], "Versao 04.01")

            # remover a escolha volta ao automático daquele mês (histórico intacto)
            self.assertTrue(config.set_versao_mes("202606", ""))
            self.assertEqual(config.get_versao("202606"), "Versao 04.01")
            dados = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("202606", dados["header"]["versao_escolhas"])

    def test_outros_campos_do_config_sao_preservados(self):
        with config_temporario() as path:
            dados = json.loads(path.read_text(encoding="utf-8"))
            dados["header"]["cgc"] = "11111111000111"
            path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            config.reload()

            self.assertTrue(config.set_versao_mes("202604", "Versao 03.26"))
            dados = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(dados["header"]["cgc"], "11111111000111")
            self.assertEqual(dados["header"]["versao_escolhas"]["202604"], "Versao 03.26")

    def test_competencia_invalida_retorna_false_sem_gravar(self):
        with config_temporario() as path:
            self.assertFalse(config.set_versao_mes("", "Versao 03.21"))
            self.assertFalse(config.set_versao_mes("000000", "Versao 03.21"))
            dados = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(dados["header"].get("versao_escolhas"), {})

    def test_config_corrompido_retorna_false_sem_apagar_o_arquivo(self):
        with config_temporario() as path:
            path.write_text("{json quebrado", encoding="utf-8")
            config.reload()
            self.assertFalse(config.set_versao_mes("202606", "Versao 03.21"))
            self.assertEqual(path.read_text(encoding="utf-8"), "{json quebrado")


class TestCabecalhoUsaVersaoEscolhida(unittest.TestCase):
    """O campo final do '01#APAC...' é a versão resolvida para o mês."""

    def _header(self, **header_extra):
        with config_temporario(header_extra or None):
            return _montar_header(build_patient_lines(linha_formulario()))

    def test_escolha_entra_no_cabecalho(self):
        header = self._header(versao_escolhas={"202606": "Versao 03.21"})
        self.assertTrue(header.startswith("01#APAC202606"), header)
        self.assertTrue(header.endswith("Versao 03.21"), header)
        self.assertEqual(len(header), 134)

    def test_sem_escolha_usa_o_padrao_automatico(self):
        header = self._header()
        self.assertTrue(header.endswith("Versao 04.01"), header)
        self.assertEqual(len(header), 134)

    def test_valor_curto_ou_longo_nao_quebra_os_134_chars(self):
        header = self._header(versao_escolhas={"202606": "X"})
        self.assertEqual(len(header), 134)
        self.assertTrue(header.endswith("X" + " " * 11), repr(header[-12:]))

        header = self._header(versao_escolhas={"202606": "Versao 09.99 EXTRA"})
        self.assertEqual(len(header), 134)
        self.assertTrue(header.endswith("Versao 09.99"), header)


class TestNormalizarVersao(unittest.TestCase):
    """normalizar_versao canoniza a grafia do campo de 12 chars."""

    def test_formatos(self):
        self.assertEqual(normalizar_versao("04.01"), "Versao 04.01")
        self.assertEqual(normalizar_versao("Versao 03.21"), "Versao 03.21")
        self.assertEqual(normalizar_versao("  versao 03.19 "), "Versao 03.19")
        self.assertEqual(normalizar_versao(""), "")
        self.assertEqual(normalizar_versao(None), "")


class TestConfigDeFabrica(unittest.TestCase):
    """O penna_config.example.json (versionado) traz o histórico conferido no antigo."""

    def test_mapa_historico_presente(self):
        caminho = Path(__file__).resolve().parent.parent / "penna_config.example.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        mapa = dados["header"]["versao_por_mes"]
        self.assertEqual(mapa["202512"], "Versao 03.18")
        self.assertEqual(mapa["202601"], "Versao 03.19")
        self.assertEqual(mapa["202603"], "Versao 03.21")
        self.assertEqual(mapa["202606"], "Versao 04.01")
        self.assertIn("versao_escolhas", dados["header"])


if __name__ == "__main__":
    unittest.main()
