"""Testes do gate de consistencia pre-exportacao (apac_mag_validador).

O validador reproduz a checagem do programa antigo APAC-MAG: enquanto houver
ocorrencia ERR o TXT nao pode ser gerado; AVS (aviso) e listado mas permite
gerar. Codigos, SEQ e mensagens seguem o relatorio RCONSIST real
(RCONSIST.JUN/.OUT, R0201.NOV e logs S_APAERR dos backups de C:/APAC).
"""
from __future__ import annotations

import unittest
from unittest import mock

import apac_mag_validador as v


def linha_base(**substituicoes):
    """Linha de planilha valida (competencia 202606, APAC OCI oftalmologica)."""
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
        "Fim_Validade": "20260630",
        "Data_Alta_Obito": "20260602",
        "Data_Solicitacao": "20260601",
    }
    linha.update(substituicoes)
    return linha


def validar_linha(linha, ceps=None, pa=None):
    """Valida uma unica linha de forma hermetica (sem bases reais nem remessas)."""
    class _DF:
        def iterrows(self):
            yield None, linha

    # CNES executante fixo do fixture, independente do penna_config.json local.
    with mock.patch.object(v, "_cnes_padrao", return_value="4234316"):
        return v.validar_planilha(
            _DF(),
            base_ceps=ceps,
            catalogo_pa={} if pa is None else pa,  # {} = catalogo vazio (regra desativada)
            usar_sigtap=False,
            usar_remessa=False,
        )


class TestFormatoRconsist(unittest.TestCase):
    def test_formato_linha_idem_rconsist(self):
        o = v.Ocorrencia("202511", "3325700656553", "ERR", "000001", "000024",
                         "PROC.(0905010035) DE APAC PMAE, NAO É PERMITIDO QTD.(     0) ZERO PROC.PRINC. OU SECUNDARIO.")
        self.assertEqual(
            v.formatar_linha_rconsist(o),
            " 202511 3325700656553 ERR  000001 000024 PROC.(0905010035) DE APAC PMAE, "
            "NAO É PERMITIDO QTD.(     0) ZERO PROC.PRINC. OU SECUNDARIO.",
        )

    def test_seq_reinicia_por_apac(self):
        coletor = v._Coletor()
        coletor.adicionar("202606", "3326703612353", "ERR", "", "000016", "X")
        coletor.adicionar("202606", "3326703612353", "ERR", "", "000016", "Y")
        coletor.adicionar("202606", "3326703612353", "ERR", "", "000016", "Z")
        coletor.adicionar("202606", "3326703612397", "ERR", "", "000016", "W")
        seqs = [o.seq for o in coletor.itens]
        self.assertEqual(seqs, ["000001", "000002", "000003", "000001"])

    def test_rotulos_textuais_corpo_habili_cnes(self):
        coletor = v._Coletor()
        coletor.adicionar("202606", "3326703612353", "ERR", "CORPO", "010025", "DATA DE NASCIMENTO INVALIDA")
        coletor.adicionar("202606", "3326703612353", "AVS", "HABILI", "030008", "X")
        coletor.adicionar("202606", "3326703612353", "AVS", "CNES", "030001", "Y")
        self.assertEqual([o.seq for o in coletor.itens], ["CORPO", "HABILI", "CNES"])

    def test_bloqueia_apenas_err(self):
        self.assertTrue(v.Ocorrencia("202606", "1", "ERR", "CORPO", "010025", "x").bloqueia)
        self.assertFalse(v.Ocorrencia("202606", "1", "AVS", "HABILI", "030008", "x").bloqueia)
        self.assertTrue(v.tem_erros([v.Ocorrencia("202606", "1", "AVS", "HABILI", "030008", "x"),
                                     v.Ocorrencia("202606", "1", "ERR", "CORPO", "010025", "x")]))


class TestRegrasCorpo(unittest.TestCase):
    def test_linha_valida_nao_gera_ocorrencias(self):
        ocorrencias = validar_linha(linha_base(), ceps={"26700000"}, pa=None)
        self.assertEqual(ocorrencias, [])

    def test_codigo_000024_mensagem_exata_do_rconsist(self):
        linha = linha_base(Quantidade="0")
        ocorrencias = validar_linha(linha, ceps=set(), pa=None)
        cod24 = [o for o in ocorrencias if o.cod == "000024"]
        self.assertEqual(len(cod24), 1)
        o = cod24[0]
        self.assertEqual(o.tipo, "ERR")
        self.assertEqual(o.cmpt, "202606")
        self.assertEqual(o.num_apac, "3326703612353")
        self.assertTrue(o.seq.isdigit())
        self.assertEqual(
            o.descricao,
            "PROC.(0905010035) DE APAC PMAE, NAO É PERMITIDO QTD.(     0) ZERO PROC.PRINC. OU SECUNDARIO.",
        )

    def test_codigo_000024_secundario_zero(self):
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="0")
        ocorrencias = validar_linha(linha, ceps=set(), pa=None)
        cod24 = [o for o in ocorrencias if o.cod == "000024"]
        self.assertEqual(len(cod24), 1)
        self.assertIn("PROC.(0211060232)", cod24[0].descricao)

    def test_codigo_010025_nascimento_invalida(self):
        ocorrencias = validar_linha(linha_base(Data_Nascimento="19559999"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010025"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "ERR")
        self.assertEqual(alvo[0].seq, "CORPO")
        self.assertEqual(alvo[0].descricao, "DATA DE NASCIMENTO INVALIDA")

    def test_codigo_010022_cep_nao_encontrado(self):
        ocorrencias = validar_linha(linha_base(Cep="02770000"), ceps={"26700000"}, pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010022"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].descricao, "CEP (02770000) NAO ENCONTRADO")
        self.assertEqual(alvo[0].tipo, "ERR")

    def test_codigo_010027_raca_invalida(self):
        ocorrencias = validar_linha(linha_base(Raca="88"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010027"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].descricao, "RACA (88) INVALIDA")
        self.assertEqual(alvo[0].tipo, "ERR")

    def test_raca_99_sem_informacao_valida(self):
        ocorrencias = validar_linha(linha_base(Raca=""), ceps=set(), pa=None)
        self.assertEqual([o for o in ocorrencias if o.cod == "010027"], [])

    def test_codigo_010032_logradouro_invalido(self):
        ocorrencias = validar_linha(linha_base(Logradouro="RUA"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010032"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].descricao, "LOGRADOURO (RUA) INVALIDO")
        self.assertEqual(alvo[0].tipo, "ERR")

    def test_codigo_010042_solicitacao_antes_do_nascimento(self):
        ocorrencias = validar_linha(linha_base(Data_Solicitacao="19550101"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010042"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(
            alvo[0].descricao,
            "DATA DE SOLICITACAO (01/01/1955) ANTERIOR A DATA DE NASCIMENTO(15/06/1955)",
        )

    def test_codigo_010083_encerramento_maior_que_fim(self):
        ocorrencias = validar_linha(linha_base(Data_Alta_Obito="20260701"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "010083"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(
            alvo[0].descricao,
            "DATA DE ENCERRAMENTO (01/07/2026) MAIOR QUE DATA DE FIM (30/06/2026)",
        )

    def test_codigo_000005_apac_vazia_ou_zerada(self):
        for apac in ("", "0000000000000"):
            ocorrencias = validar_linha(linha_base(Numero_Apac=apac), ceps=set(), pa=None)
            alvo = [o for o in ocorrencias if o.cod == "000005"]
            self.assertEqual(len(alvo), 1, f"APAC={apac!r}")
            self.assertEqual(alvo[0].tipo, "ERR")

    def test_competencia_divergente_bloqueia(self):
        class _DF:
            def iterrows(self):
                yield None, linha_base()
                yield None, linha_base(Numero_Apac="3326703612397", Competencia="202605")

        ocorrencias = v.validar_planilha(_DF(), base_ceps=set(), catalogo_pa=None)
        alvo = [o for o in ocorrencias if o.cod == "000005" and "COMPETENCIA" in o.descricao]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "ERR")
        self.assertIn("COMPETENCIA (202605) DIFERENTE DA COMPETENCIA (202606)", alvo[0].descricao)

    def test_planilha_vazia_bloqueia(self):
        class _DF:
            def iterrows(self):
                return iter(())

        ocorrencias = v.validar_planilha(_DF(), base_ceps=set(), catalogo_pa=None)
        self.assertTrue(v.tem_erros(ocorrencias))


class TestAvisosEIdade(unittest.TestCase):
    def test_codigo_030008_habilitacao_nao_bloqueia(self):
        linha = linha_base(Sec1_Cod_Procedimento="0211060232", Sec1_Quantidade="1")
        ocorrencias = validar_linha(linha, ceps={"26700000"}, pa=None)
        alvo = [o for o in ocorrencias if o.cod == "030008"]
        self.assertEqual(len(alvo), 1)
        o = alvo[0]
        self.assertEqual(o.tipo, "AVS")
        self.assertEqual(o.seq, "HABILI")
        self.assertEqual(
            o.descricao,
            "PROCED.(0211060232) EXIGE HABILITACAO NAO ENCONTRADA NO CNES(4234316)",
        )
        self.assertFalse(v.tem_erros(ocorrencias))

    def test_codigo_030001_cnes_divergente_e_aviso(self):
        ocorrencias = validar_linha(linha_base(Cnes_Executante="1234567"), ceps=set(), pa=None)
        alvo = [o for o in ocorrencias if o.cod == "030001"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(alvo[0].tipo, "AVS")
        self.assertEqual(alvo[0].seq, "CNES")
        self.assertEqual(alvo[0].descricao, "CNES EXECUTANTE(1234567) NAO ENCONTRADO")

    def test_codigo_000016_idade_maxima_com_catalogo(self):
        pa = {"090501003": {"PA_IDADEMX": "70", "PA_IDADEMN": "9"}}
        linha = linha_base(Data_Nascimento="19550615")  # 71 anos em 202606
        ocorrencias = validar_linha(linha, ceps={"26700000"}, pa=pa)
        alvo = [o for o in ocorrencias if o.cod == "000016"]
        self.assertEqual(len(alvo), 1)
        self.assertEqual(
            alvo[0].descricao,
            "PROC.(0905010035) NAO PERMITIDO PARA IDADE MAX.DO USUARIO : 70",
        )

    def test_codigo_000016_idade_minima(self):
        pa = {"090501003": {"PA_IDADEMX": "130", "PA_IDADEMN": "9"}}
        linha = linha_base(Data_Nascimento="20250615")  # 1 ano em 202606
        ocorrencias = validar_linha(linha, ceps=set(), pa=pa)
        alvo = [o for o in ocorrencias if o.cod == "000016"]
        self.assertEqual(len(alvo), 1)
        self.assertIn("IDADE MIN.DO USUARIO : 9", alvo[0].descricao)

    def test_sem_catalogo_regra_de_idade_fica_desativada(self):
        linha = linha_base(Data_Nascimento="19550615")
        ocorrencias = validar_linha(linha, ceps=set(), pa=None)
        self.assertEqual([o for o in ocorrencias if o.cod == "000016"], [])


class TestIntegracao(unittest.TestCase):
    def test_resumo(self):
        n_err, n_avs = v.resumo([v.Ocorrencia("202606", "1", "ERR", "CORPO", "010025", "a"),
                                 v.Ocorrencia("202606", "1", "AVS", "HABILI", "030008", "b"),
                                 v.Ocorrencia("202606", "1", "AVS", "CNES", "030001", "c")])
        self.assertEqual((n_err, n_avs), (1, 2))

    def test_bases_do_sistema_antigo_quando_disponiveis(self):
        """C:/APAC presente: S_CEP tem 26700000 (Mendes/RJ) e 02770000 (SP) nao."""
        ceps = v.carregar_base_ceps()
        if ceps is None:
            self.skipTest("S_CEP.DBF do sistema antigo nao disponivel nesta maquina")
        self.assertIn("26700000", ceps)
        self.assertNotIn("02770000", ceps)

        pa = v.carregar_catalogo_procedimentos()
        if pa is None:
            self.skipTest("S_PA.DBF do sistema antigo nao disponivel nesta maquina")
        proc = pa.get("090501003")
        self.assertIsNotNone(proc)
        self.assertEqual(proc.get("PA_IDADEMN"), "9")


if __name__ == "__main__":
    unittest.main()
