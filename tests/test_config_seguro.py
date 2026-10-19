"""Config ausente/corrompido/parcial nunca pode gerar TXT com outra identidade."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pandas as pd

import apac_mag.config as config
import apac_mag_gerador as g

EXEMPLO = Path(__file__).resolve().parent.parent / "penna_config.example.json"


@contextmanager
def config_em(conteudo=None):
    """Aponta o config para um arquivo temporário (None = arquivo ausente)."""
    original = config._config_path
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "penna_config.json"
        if conteudo is not None:
            path.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo),
                            encoding="utf-8")
        config._config_path = lambda: path
        try:
            with mock.patch("warnings.warn"):
                config.reload()
                yield path
        finally:
            config._config_path = original
            config.reload()


class TestFallbackSemIdentidadeReal(unittest.TestCase):
    def test_fallback_usa_placeholders(self):
        h, d = config._FALLBACK["header"], config._FALLBACK["defaults"]
        self.assertEqual(d["Cnes_Executante"], "0000000")
        self.assertEqual(d["Cnes_Solicitante"], "0000000")
        self.assertEqual(h["orgao_responsavel"], "NAO CONFIGURADO")
        self.assertEqual(h["destino"], "NAO CONFIGURADO")
        self.assertEqual(h["cgc"], "00000000000000")


class TestGateDeConfig(unittest.TestCase):
    def test_ausente_bloqueia(self):
        with config_em(None):
            self.assertTrue(any("não encontrado" in p for p in config.problemas_configuracao()))
            with self.assertRaises(config.ConfigInvalidaError):
                config.verificar_configuracao()

    def test_corrompido_bloqueia(self):
        with config_em("{json quebrado"):
            self.assertTrue(any("não pôde ser lido" in p for p in config.problemas_configuracao()))
            with self.assertRaises(config.ConfigInvalidaError):
                config.verificar_configuracao()

    def test_placeholders_bloqueiam(self):
        with config_em({"header": {"orgao_responsavel": "OK"}}):
            with self.assertRaises(config.ConfigInvalidaError) as ctx:
                config.verificar_configuracao()
            self.assertTrue(any("Cnes_Executante" in p for p in ctx.exception.problemas))

    def test_exemplo_versionado_passa(self):
        with config_em(EXEMPLO.read_text(encoding="utf-8")):
            self.assertEqual(config.problemas_configuracao(), [])

    def test_exportar_txt_recusa_config_invalido(self):
        with config_em(None), tempfile.TemporaryDirectory() as td:
            saida = Path(td) / "saida.txt"
            with self.assertRaises(config.ConfigInvalidaError):
                g.exportar_txt(pd.DataFrame([{"Numero_Apac": "3326703612353"}]), saida)
            self.assertFalse(saida.exists())


class TestMergeComFabrica(unittest.TestCase):
    def test_config_parcial_completa_chave_a_chave(self):
        parcial = {"header": {"orgao_responsavel": "MEU ORGAO"}, "defaults": {"Cnes_Executante": "7654321"}}
        with config_em(parcial):
            h, d = config.get_header(), config.get_defaults()
            self.assertEqual(h["orgao_responsavel"], "MEU ORGAO")
            self.assertEqual(h["destino_indicador"], "M")
            self.assertEqual(d["Cnes_Executante"], "7654321")
            self.assertEqual(d["Tipo_Apac"], "003")
            self.assertEqual(config.get_versao("202606"), "Versao 04.01")

    def test_versao_por_mes_de_fabrica_sem_config(self):
        with config_em({"header": {"versao_por_mes": {"202607": "Versao 05.00"}}}):
            self.assertEqual(config.get_versao("202601"), "Versao 03.19")
            self.assertEqual(config.get_versao("202607"), "Versao 05.00")

    def test_secao_com_tipo_errado_cai_na_fabrica(self):
        with config_em({"header": "lixo", "defaults": []}):
            self.assertIn("destino_indicador", config.get_header())
            self.assertIn("Cnes_Executante", config.get_defaults())


class TestGravacaoAtomica(unittest.TestCase):
    def test_falha_no_replace_preserva_original_e_limpa_temporario(self):
        with config_em(EXEMPLO.read_text(encoding="utf-8")) as path:
            antes = path.read_text(encoding="utf-8")
            with mock.patch("os.replace", side_effect=OSError("disco")):
                self.assertFalse(config.set_versao_mes("202606", "Versao 03.21"))
            self.assertEqual(path.read_text(encoding="utf-8"), antes)
            self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])

    def test_gravacao_normal_usa_replace(self):
        with config_em(EXEMPLO.read_text(encoding="utf-8")) as path:
            with mock.patch("os.replace", wraps=os.replace) as replace:
                self.assertTrue(config.set_versao_mes("202606", "Versao 03.21"))
            replace.assert_called_once()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))
                             ["header"]["versao_escolhas"]["202606"], "Versao 03.21")


if __name__ == "__main__":
    unittest.main()


class TestSemEstadoGlobalNaImportacao(unittest.TestCase):
    """Trocar o config em runtime vale na proxima geracao/validacao."""

    def test_gerador_le_defaults_no_momento_do_uso(self):
        import apac_mag_validador as v
        base = json.loads(EXEMPLO.read_text(encoding="utf-8"))
        for cnes in ("7654321", "1111111"):
            base["defaults"]["Cnes_Executante"] = cnes
            with config_em(base):
                self.assertIn(cnes, g.build_block_01({"Numero_Apac": "3326703612353"}))
                self.assertEqual(v._cnes_padrao(), cnes)

    def test_sem_constantes_de_modulo_com_o_config(self):
        import apac_mag_validador as v
        for modulo, nomes in ((g, ("DEFAULT_VALUES", "HEADER_ORGAO_RESP", "HEADER_CGC")),
                              (v, ("DEFAULT_VALUES", "_CNES_PADRAO"))):
            for nome in nomes:
                self.assertFalse(hasattr(modulo, nome), f"{modulo.__name__}.{nome}")
