"""Item 6 do validador: competencia do catalogo, severidade das regras
(HIPOTESE x oficiais), 010084 e relatorio de regras desativadas."""
from __future__ import annotations

import unittest
from unittest import mock

import penna.validation as v
from penna.validation import lookups
from penna import reference
from tests.test_validador_sigtap import codigos, linha_base, validar


def _s_pa(cmp, idade_max):
    return {"PA_CMP": cmp, "PA_ID": "090501003", "PA_IDADEMX": idade_max, "PA_IDADEMN": "0"}


class TestCatalogoUsaCompetenciaDaPlanilha(unittest.TestCase):
    REGISTROS = [_s_pa("202605", "70"), _s_pa("202606", "80"), _s_pa("202607", "90")]

    def _catalogo(self, competencia):
        with mock.patch.object(reference, "carregar_tabela", return_value=self.REGISTROS):
            return v.carregar_catalogo_procedimentos(competencia)

    def test_usa_a_vigente_na_competencia_e_nunca_uma_futura(self):
        self.assertEqual(self._catalogo("202606")["090501003"]["PA_IDADEMX"], "80")
        self.assertEqual(self._catalogo("202609")["090501003"]["PA_IDADEMX"], "90")
        self.assertEqual(self._catalogo("202605")["090501003"]["PA_IDADEMX"], "70")

    def test_competencia_anterior_a_tabela_desativa_a_regra(self):
        self.assertIsNone(self._catalogo("202501"))

    def test_validar_planilha_passa_a_competencia_da_planilha(self):
        with mock.patch.object(reference, "carregar_tabela", return_value=self.REGISTROS):
            ocs = validar(linha_base(Competencia="202605", Data_Nascimento="19550615"),
                          catalogo_pa=None)
        # 70 anos no maximo na competencia 202605; a paciente tem 70 -> sem 000016
        self.assertNotIn("000016", codigos(ocs))
        with mock.patch.object(reference, "carregar_tabela", return_value=[_s_pa("202605", "60"),
                                                                        _s_pa("202607", "130")]):
            ocs = validar(linha_base(Competencia="202606", Data_Nascimento="19550615"),
                          catalogo_pa=None)
        self.assertIn("000016", codigos(ocs))  # 202606 usa a de 202605 (60), nao a de 202607


class TestSeveridadeDasRegras(unittest.TestCase):
    def test_hipotese_nao_bloqueia_ate_confirmar(self):
        self.assertEqual(v.SEVERIDADE_HIPOTESE, "AVS")
        com_secundario = dict(Sec1_Cod_Procedimento="0702010098", Sec1_Quantidade="1")
        # codigo -> (linha, bases injetadas)
        casos = {
            "000006": (linha_base(), dict(catalogo_pa={"090501003": {"PA_SECOBRI": "S"}})),
            "000007": (linha_base(Sexo="F"), dict(catalogo_pa={"090501003": {"PA_SEXO": "M"}})),
            "000008": (linha_base(Quantidade="3"),
                       dict(catalogo_pa={"090501003": {"PA_QTDMAX": "1"}})),
            "000009": (linha_base(**com_secundario),
                       dict(pares_secundarios={"090501003": {"021106001": "1"}})),
            "010040": (linha_base(Cid_Princ="Z99"), dict(cids_validos={"H26"})),
            "010041": (linha_base(Sexo="F", Cid_Princ="H40"),
                       dict(cids_validos={"H40"}, cids_registros=[{"CD_COD": "H40", "RESTRSEXO": "1"}])),
        }
        for cod, (linha, injetado) in casos.items():
            with self.subTest(cod=cod):
                ocs = validar(linha, **injetado)
                achados = [o for o in ocs if o.cod == cod]
                self.assertTrue(achados, f"{cod} nao disparou: {ocs}")
                self.assertTrue(all(o.tipo == "AVS" for o in achados), achados)
                self.assertFalse(v.tem_erros(ocs), ocs)

    def test_000005_estrutural_continua_bloqueando(self):
        ocs = validar([linha_base(Competencia="202606"), linha_base(Competencia="202607")])
        self.assertTrue(any(o.cod == "000005" and o.tipo == "ERR" for o in ocs))

    def test_regras_oficiais_continuam_err(self):
        ocs = validar(linha_base(Quantidade="0"))
        self.assertTrue(any(o.cod == "000024" and o.tipo == "ERR" for o in ocs))

    def test_010084_e_aviso_no_codigo_e_no_catalogo(self):
        ocs = validar(linha_base(), historico_apacs={"3326703612353"})
        alvo = [o for o in ocs if o.cod == "010084"]
        self.assertEqual([o.tipo for o in alvo], ["AVS"])
        self.assertEqual(v.SEVERIDADE_PADRAO["010084"], "AVS")
        self.assertEqual(v.SEVERIDADE_PADRAO["000024"], "ERR")
        self.assertEqual(v.SEVERIDADE_PADRAO["000007"], v.SEVERIDADE_HIPOTESE)
        self.assertEqual(set(v.SEVERIDADE_PADRAO), set(v.CATALOGO_CODIGOS))


class TestRegrasDesativadas(unittest.TestCase):
    def _validar_sem_bases(self, **extra):
        class _DF:
            def iterrows(self):
                yield None, linha_base()

        with mock.patch.object(reference, "carregar_tabela", return_value=None), \
                mock.patch.object(reference, "carregar_habilitacoes_cnes", return_value=None), \
                mock.patch.object(lookups, "carregar_base_ceps", return_value=None):
            return v.validar_planilha(_DF(), usar_remessa=False, **extra)

    def test_bases_ausentes_sao_listadas(self):
        resultado = self._validar_sem_bases()
        nomes = " ".join(resultado.regras_desativadas)
        for base in ("S_CEP", "S_PA", "S_PAPA", "S_PAHA", "S_CID", "S_PAREGR"):
            self.assertIn(base, nomes)

    def test_resultado_continua_sendo_lista_de_ocorrencias(self):
        resultado = self._validar_sem_bases()
        self.assertIsInstance(resultado, list)
        self.assertEqual(list(resultado), [o for o in resultado])

    def test_bases_injetadas_nao_sao_desativadas(self):
        resultado = validar(
            linha_base(),
            catalogo_pa={"090501003": {}}, pares_secundarios={}, cids_validos={"H40"},
        )
        nomes = " ".join(resultado.regras_desativadas)
        self.assertNotIn("S_CEP", nomes)
        self.assertNotIn("S_PA ", nomes + " ")
        self.assertNotIn("S_CID", nomes)


if __name__ == "__main__":
    unittest.main()


class TestTextoRegrasDesativadas(unittest.TestCase):
    def test_texto_para_a_ui(self):
        from penna.services.validation import texto_regras_desativadas
        self.assertEqual(texto_regras_desativadas([]), "")
        texto = texto_regras_desativadas(["CEP inexistente (S_CEP)", "CID (S_CID)"])
        self.assertTrue(texto.startswith("2 regras desativadas nesta validação"))
        self.assertIn("• CEP inexistente (S_CEP)", texto)
        self.assertTrue(texto_regras_desativadas(["x"]).startswith("1 regra desativada "))
