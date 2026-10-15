"""Testes das regras SIGTAP do validador (S_PAPA, S_PAHA x XUPSHA, S_PA
extras, S_CID) com bases sinteticas — deterministico, sem depender de C:/APAC.

Os codigos com amostra oficial observada (000016, 000024, 010022, 010025,
010027, 010032, 010042, 010083, 010084, 030001, 030008) continuam cobertos em
test_validador_exportacao.py; aqui entram as novas familias HIPOTESE (000006,
000007, 000008, 000009, 010040, 010041) e a regra condicionada 0009.
"""
from __future__ import annotations

import unittest

import apac_mag_validador as v


def linha_base(**substituicoes):
    linha = {
        "Competencia": "202606",
        "Numero_Apac": "3326703612353",
        "Cnes_Executante": "4234316",
        "Data_Nascimento": "19550615",
        "Cep": "26700000",
        "Raca": "01",
        "Logradouro": "081",
        "Cod_Procedimento": "0905010035",
        "Quantidade": "1",
        "Cbo": "225265",
        "Sexo": "F",
        "Fim_Validade": "20260630",
        "Data_Alta_Obito": "20260602",
        "Data_Solicitacao": "20260601",
    }
    linha.update(substituicoes)
    return linha


def validar(linhas, **injetadas):
    """validar_planilha hermetico: sem bases reais, sem remessa."""
    if isinstance(linhas, dict):
        linhas = [linhas]

    class _DF:
        def iterrows(self):
            for linha in linhas:
                yield None, linha

    padroes = dict(
        base_ceps={"26700000"},
        catalogo_pa={},
        usar_sigtap=False,
        usar_remessa=False,
    )
    padroes.update(injetadas)
    return v.validar_planilha(_DF(), **padroes)


def codigos(ocorrencias):
    return [o.cod for o in ocorrencias]


class TestSecundarioObrigatorio(unittest.TestCase):
    def test_000006_principal_sem_secundario(self):
        pa = {"090501003": {"PA_SECOBRI": "S"}}
        ocs = validar(linha_base(), catalogo_pa=pa)
        self.assertIn("000006", codigos(ocs))
        alvo = [o for o in ocs if o.cod == "000006"][0]
        self.assertEqual(alvo.tipo, "ERR")
        self.assertEqual(
            alvo.descricao,
            "PROC.(0905010035) EXIGE PELO MENOS (1) PROC. SECUNDARIO OBRIGATORIO.",
        )

    def test_principal_com_secundario_nao_gera_000006(self):
        pa = {"090501003": {"PA_SECOBRI": "S"}}
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocs = validar(linha, catalogo_pa=pa)
        self.assertNotIn("000006", codigos(ocs))


class TestParPrincipalSecundario(unittest.TestCase):
    PARES = {"090501003": {"021106023": "9999", "021106012": "0001", "030101007": "0002"}}

    def test_000009_secundario_nao_permitido(self):
        linha = linha_base(Sec1_Cod_Procedimento="0702010098", Sec1_Quantidade="1")
        ocs = validar(linha, pares_secundarios=self.PARES)
        alvo = [o for o in ocs if o.cod == "000009"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "ERR")
        self.assertEqual(
            alvo[0].descricao,
            "PROC. SECUNDARIO (0702010098) NAO PERMITIDO PARA O PROC. PRINCIPAL (0905010035)",
        )

    def test_secundario_do_par_nao_gera_000009(self):
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocs = validar(linha, pares_secundarios=self.PARES)
        self.assertNotIn("000009", codigos(ocs))

    def test_000008_qtd_acima_do_maximo_do_par(self):
        # 030101007 aceita qtd max 2 no par; enviando 3 deve reprovar
        linha = linha_base(Sec1_Cod_Procedimento="0301010072", Sec1_Quantidade="3")
        ocs = validar(linha, pares_secundarios=self.PARES)
        alvo = [o for o in ocs if o.cod == "000008"]
        self.assertEqual(len(alvo), 1)
        self.assertIn("QTD. ACIMA DO MAXIMO PERMITIDO : 2", alvo[0].descricao)

    def test_000008_qtd_acima_do_maximo_do_procedimento(self):
        pa = {"021106023": {"PA_QTDMAX": "1"}}
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="2")
        ocs = validar(linha, catalogo_pa=pa)
        alvo = [o for o in ocs if o.cod == "000008"]
        self.assertEqual(len(alvo), 1)
        self.assertIn("QTD. ACIMA DO MAXIMO PERMITIDO : 1", alvo[0].descricao)

    def test_qtd_dentro_do_limite_ok(self):
        pa = {"021106023": {"PA_QTDMAX": "1"}}
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocs = validar(linha, catalogo_pa=pa, pares_secundarios=self.PARES)
        self.assertEqual([o for o in ocs if o.cod == "000008"], [])


class TestSexoProcedimento(unittest.TestCase):
    def test_000007_sexo_restrito(self):
        pa = {"090501003": {"PA_SEXO": "M"}}
        ocs = validar(linha_base(Sexo="F"), catalogo_pa=pa)
        alvo = [o for o in ocs if o.cod == "000007"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "ERR")
        self.assertEqual(
            alvo[0].descricao,
            "PROC.(0905010035) NAO PERMITIDO PARA SEXO DO USUARIO",
        )

    def test_sexo_compativel_sem_ocorrencia(self):
        pa = {"090501003": {"PA_SEXO": "F"}}
        ocs = validar(linha_base(Sexo="F"), catalogo_pa=pa)
        self.assertNotIn("000007", codigos(ocs))

    def test_sexo_a_ou_vazio_libera(self):
        pa = {"090501003": {"PA_SEXO": "A"}}
        ocs = validar(linha_base(Sexo="M"), catalogo_pa=pa)
        self.assertNotIn("000007", codigos(ocs))


class TestHabilitacaoReal(unittest.TestCase):
    def test_030008_com_s_paha_e_xupsha(self):
        exigidas = {"090501003": {"3801", "3802"}}
        # CNES so tem 3801: a regra do antigo e "ao menos uma" das exigidas
        ocs = validar(linha_base(), habilitacoes_exigidas=exigidas, habilitacoes_cnes={"3801"})
        self.assertNotIn("030008", codigos(ocs))

        # CNES sem nenhuma das exigidas -> AVS 030008
        ocs = validar(linha_base(), habilitacoes_exigidas=exigidas, habilitacoes_cnes={"0501"})
        alvo = [o for o in ocs if o.cod == "030008"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "AVS")
        self.assertEqual(alvo[0].seq, "HABILI")
        self.assertEqual(
            alvo[0].descricao,
            "PROCED.(0905010035) EXIGE HABILITACAO NAO ENCONTRADA NO CNES(4234316)",
        )

    def test_sem_bases_mantem_lista_fixa_do_fallback(self):
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocs = validar(linha)  # nem S_PAHA nem XUPSHA -> fallback
        self.assertIn("030008", codigos(ocs))


class TestCid(unittest.TestCase):
    def test_010040_cid_inexistente(self):
        ocs = validar(linha_base(Cid_Princ="Z99"), cids_validos={"H40", "H26", "H52"})
        alvo = [o for o in ocs if o.cod == "010040"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "ERR")
        self.assertEqual(alvo[0].seq, "CORPO")
        self.assertEqual(alvo[0].descricao, "CID (Z99) NAO ENCONTRADO")

    def test_cid_valido_categoria_aceita(self):
        ocs = validar(linha_base(Cid_Princ="H40"), cids_validos={"H40"})
        self.assertEqual([o for o in ocs if o.cod == "010040"], [])

    def test_010041_cid_restrito_ao_sexo(self):
        # N80 e restrito ao sexo feminino (RESTRSEXO=2): paciente M reprova
        ocs = validar(linha_base(Cid_Princ="N80", Sexo="M"), cids_validos={"N80"},
                      cids_registros=[{"CD_COD": "N80", "RESTRSEXO": "2"}])
        alvo = [o for o in ocs if o.cod == "010041"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].descricao, "CID (N80) NAO PERMITIDO PARA O SEXO DO USUARIO")

    def test_cid_compativel_com_sexo(self):
        ocs = validar(linha_base(Cid_Princ="N80"), cids_validos={"N80"},
                      cids_registros=[{"CD_COD": "N80", "RESTRSEXO": "2"}])
        self.assertNotIn("010041", codigos(ocs))
        # sexo M com CID restrito a M (RESTRSEXO=1) tambem passa
        ocs = validar(linha_base(Cid_Princ="C61", Sexo="M"), cids_validos={"C61"},
                      cids_registros=[{"CD_COD": "C61", "RESTRSEXO": "1"}])
        self.assertNotIn("010041", codigos(ocs))


class TestRegraCondicionada(unittest.TestCase):
    def test_030009_principal_0009_impede_secundarios(self):
        regras = {"090501003": {"0009"}}
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocs = validar(linha, regras_condicionadas=regras)
        alvo = [o for o in ocs if o.cod == "030009"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "AVS")
        self.assertEqual(
            alvo[0].descricao,
            "REGRA CONDICIONADA 0009 : PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS",
        )

    def test_secundarios_zerados_nao_disparam_0009(self):
        regras = {"090501003": {"0009"}}
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="0")
        ocs = validar(linha, regras_condicionadas=regras)
        self.assertEqual([o for o in ocs if o.cod == "030009"], [])


class TestHistoricoRemessa(unittest.TestCase):
    def test_010084_apac_ja_exportada(self):
        ocs = validar(linha_base(), historico_apacs={"3326703612353"})
        alvo = [o for o in ocs if o.cod == "010084"]
        self.assertEqual(len(alvo), 1)
        # 010084 AVISA sobre reenvio (historico local do Penna), nao bloqueia:
        # correcao/substituicao reenvia os mesmos numeros legitimamente e o
        # bloqueio impedia reexportar a planilha na mesma sessao.
        self.assertEqual(alvo[0].tipo, "AVS")
        self.assertEqual(alvo[0].seq, "CORPO")
        self.assertEqual(
            alvo[0].descricao,
            "NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE",
        )

    def test_apac_nova_passa(self):
        ocs = validar(linha_base(), historico_apacs={"1111111111111"})
        self.assertEqual([o for o in ocs if o.cod == "010084"], [])


class TestCatalogo(unittest.TestCase):
    def test_novos_codigos_documentados(self):
        for cod in ("000006", "000007", "000008", "000009", "010040", "010041", "010084", "030009"):
            self.assertIn(cod, v.CATALOGO_CODIGOS)


if __name__ == "__main__":
    unittest.main()
