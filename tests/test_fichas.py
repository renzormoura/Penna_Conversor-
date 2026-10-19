"""Testes das fichas em PDF (uma por linha) e das opções de exportação.

Cobre o contrato pedido:

* cada linha da planilha vira UMA ficha com todas as informações da linha;
* a montagem cobre a linha inteira (coluna exibida em seção ou listada em
  "OUTROS DADOS DA LINHA") — nada da linha se perde;
* formatos do formulário modelo (datas, CPF, CEP, raça, procedimento);
* nomes de arquivo seguros e sem colisão;
* a UI exporta exatamente o que foi marcado em OPÇÕES DE EXPORTAÇÃO.
"""
from __future__ import annotations

import contextlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from penna.cards import (_reportlab, constants, exportar_fichas, extras, gerar_ficha_pdf, montar_ficha,
                         nome_arquivo_ficha, template)
from penna.cards import text as cards_text


def linha_modelo() -> dict:
    """Linha equivalente à ficha da aba OCI OFTALMOLOGIA do Excel modelo."""
    linha = {
        "Numero_Apac": "3399999999999",
        "Competencia": "202508",
        "Cnes_Solicitante": "4234316",
        "Cnes_Executante": "4234316",
        "Inicio_Validade": "20250801",
        "Fim_Validade": "20251130",
        "Tipo_Apac": "003",
        "Tipo_Atendimento": "01",
        "Cpf_Paciente": "11144477735",
        "Cns_Paciente": "712345678901234",
        "Nome_Paciente": "MARIA CLARA DE ALMEIDA",
        "Nome_Da_Mae": "JOANA DE ALMEIDA",
        "Nome_Do_Responsavel": "",
        "Nome_Profissional": "ROBERTO CARLOS FERREIRA LIMA",
        "Cep": "26700000",
        "Logradouro": "31",
        "Rua": "RUA DAS FLORES",
        "Numero_Endereco": "123",
        "Codigo_Logradouro": "31",
        "Complemento": "",
        "Bairro": "CENTRO",
        "Telefone": "21912345678",
        "Email": "",
        "Codigo_Municipio": "3302809",
        "IBGE": "3302809",
        "Nome_Municipio": "MENDES",
        "Raca": "1",
        "Data_Nascimento": "19850412",
        "Sexo": "F",
        "Etnia": "",
        "Cod_Procedimento": "0905010035",
        "Cbo": "225265",
        "Quantidade": "1",
        "Cns_Executante": "123456789012345",
        "Cid_Princ": "H40",
        "Cid_Secun": "",
        "Cid_Causas_Assoc": "H00, H52",
        "Motivo_Saida": "11",
        "Data_Alta_Obito": "20250929",
        "Carater_Atend": "01",
        "Data_Solicitacao": "20250728",
        "Data_Autorizacao": "20250801",
        "Autorizador_Cns": "712345678901235",
        "Autorizador_Cpf": "12345678909",
        "Autorizador_Nome": "ROBERTO CARLOS FERREIRA LIMA",
        "Cod_Orgao_Emiss": "M330280001",
        "Medico_Cns": "712345678901235",
        "Medico_Cpf": "12345678909",
        "Medico_Nome": "ROBERTO CARLOS FERREIRA LIMA",
        "Situacao_De_Rua": "N",
        "Numero_Apac_Anterior": "000000000000/0",
        "Nacionalidade": "10",
        "No_Prontuario": "",
        "Equipe": "",
        "Equipe_Area": "",
        "Cnes_Terceiro": "",
        "Servico": "",
        "Classif": "",
        "Cnpj_Fornecedor": "",
        "Num_Nota_Fiscal": "",
        "Data_Identificacao": "20250728",
        "INE": "",
        "Fonte_Orcamentaria": "",
        "Emenda_Parlamentar": "",
        "Sec1_Cod_Procedimento": "021106023",
        "Sec1_Cbo": "225265",
        "Sec1_Quantidade": "1",
        "Sec2_Cod_Procedimento": "",
        "Sec2_Cbo": "",
        "Sec2_Quantidade": "",
        "Sec3_Cod_Procedimento": "",
        "Sec3_Cbo": "",
        "Sec3_Quantidade": "",
        "Sec4_Cod_Procedimento": "",
        "Sec4_Cbo": "",
        "Sec4_Quantidade": "",
        "Sec5_Cod_Procedimento": "",
        "Sec5_Cbo": "",
        "Sec5_Quantidade": "",
        "Sec6_Cod_Procedimento": "",
        "Sec6_Cbo": "",
        "Sec6_Quantidade": "",
        "Sec7_Cod_Procedimento": "",
        "Sec7_Cbo": "",
        "Sec7_Quantidade": "",
        "Sec8_Cod_Procedimento": "",
        "Sec8_Cbo": "",
        "Sec8_Quantidade": "",
    }
    # Cobertura total da linha: toda coluna está em alguma seção ou nos extras
    return {chave: valor for chave, valor in linha.items()}


def texto_da_ficha(ficha: dict) -> str:
    partes: list[str] = []
    for bloco in ficha["blocos"]:
        partes.append(bloco.get("titulo") or "")
        for rotulo, valor, _tipo in bloco.get("itens") or []:
            partes.append(rotulo)
            partes.append(valor)
        for proc in bloco.get("procedimentos") or []:
            partes.extend(proc.values())
    return "\n".join(partes)


class TestMontarFicha(unittest.TestCase):
    def test_cobre_toda_a_linha(self):
        """Nenhuma informação da linha se perde: cada coluna COM valor sai numa
        seção do formulário ou no bloco de OUTROS DADOS DA LINHA. Coluna vazia
        não é informação e não é listada."""
        linha = linha_modelo()
        ficha = montar_ficha(linha)
        rotulos_extras = {rotulo for rotulo, _, _ in ficha["extras"]}
        for coluna, valor in linha.items():
            if not str(valor).strip():
                continue
            self.assertTrue(
                coluna in ficha["cobertos"]
                or cards_text.rotulo_coluna(coluna) + ":" in rotulos_extras,
                f"coluna {coluna} não aparece em nenhuma seção da ficha",
            )

    def test_valores_do_modelo_com_formatos(self):
        ficha = montar_ficha(linha_modelo())
        texto = texto_da_ficha(ficha)
        # identificação
        self.assertIn("MARIA CLARA DE ALMEIDA", texto)
        self.assertIn("3399999999999", texto)
        self.assertIn("4234316", texto)
        self.assertIn("M330280001", texto)
        # formatos do formulário
        self.assertIn("111.444.777-35", texto)          # CPF
        self.assertIn("12/04/1985", texto)              # data nascimento
        self.assertIn("28/07/2025", texto)              # data solicitação
        self.assertIn("01/08/2025", texto)              # data autorização
        self.assertIn("26700-000", texto)               # CEP
        self.assertIn("1 - BRANCO", texto)              # raça/cor
        self.assertIn("F - FEMININO", texto)            # sexo
        self.assertIn("2025/08", texto)                 # competência
        self.assertIn("11 - ALTA CURADO", texto)        # motivo saída
        # procedimento principal formatado + secundário na tabela
        self.assertIn("09.05.01.003-5", texto)
        self.assertIn("02.11.06.023", texto)
        # diagnósticos
        self.assertIn("H40", texto)
        self.assertIn("H00", texto)
        # blocos do formulário
        for titulo in ("DADOS DO PACIENTE", "DADOS DO SOLICITANTE",
                       "EMISSOR DA OCI", "ENCERRAMENTO DA APAC",
                       "MÉDICO AUTORIZADOR DA APAC"):
            self.assertIn(titulo, texto)

    def test_extras_listam_colunas_fora_das_secoes(self):
        ficha = montar_ficha(linha_modelo())
        rotulos = {rotulo for rotulo, _, _ in ficha["extras"]}
        self.assertIn("COMPETENCIA:", rotulos)          # com valor na linha
        self.assertIn("INICIO VALIDADE:", rotulos)
        # coluna vazia não é informação: não é listada
        self.assertNotIn("EQUIPE:", rotulos)
        self.assertNotIn("CNPJ FORNECEDOR:", rotulos)
        # nada que já está em seção aparece de novo nos extras
        self.assertNotIn("NOME PACIENTE:", rotulos)

    def test_coluna_vazia_vira_extra_com_valor(self):
        """A supressão é do vazio: preenchendo a coluna, ela aparece."""
        linha = linha_modelo()
        linha["Equipe"] = "EQUIPE 1"
        rotulos = {rotulo: valor for rotulo, valor, _ in montar_ficha(linha)["extras"]}
        self.assertEqual(rotulos.get("EQUIPE:"), "EQUIPE 1")

    def test_linha_vazia_nao_explode(self):
        ficha = montar_ficha({})
        self.assertTrue(ficha["blocos"])


class TestNomesDeArquivo(unittest.TestCase):
    def test_nome_usa_nome_e_numero_da_apac(self):
        nome = nome_arquivo_ficha(linha_modelo(), 1)
        self.assertEqual(nome, "MARIA CLARA DE ALMEIDA_3399999999999.pdf")

    def test_nome_seguro_sem_caracteres_invalidos(self):
        linha = {"Nome_Paciente": 'JOAO/DA:SILVA*?"<>|', "Numero_Apac": ""}
        nome = nome_arquivo_ficha(linha, 3)
        self.assertNotIn("/", nome)
        self.assertNotIn(":", nome)
        self.assertTrue(nome.endswith(".pdf"))

    def test_nome_sem_dados_usa_indice(self):
        self.assertEqual(nome_arquivo_ficha({}, 7), "ficha_007.pdf")

    def test_colisao_recebe_sufixo(self):
        usados: set[str] = set()
        primeiro = nome_arquivo_ficha(linha_modelo(), 1, usados)
        segundo = nome_arquivo_ficha(linha_modelo(), 2, usados)
        self.assertNotEqual(primeiro, segundo)
        self.assertIn(segundo, {"MARIA CLARA DE ALMEIDA_3399999999999_2.pdf"})


class TestExportarFichas(unittest.TestCase):
    def test_uma_ficha_por_linha_em_pdf_valido(self):
        df = pd.DataFrame([linha_modelo(), linha_modelo()])
        with tempfile.TemporaryDirectory() as tmp:
            fases: list[str] = []
            gerados = exportar_fichas(
                df, Path(tmp),
                progresso=lambda titulo, detalhe="": fases.append(titulo),
            )
            self.assertEqual(len(gerados), 2)
            # colisão de nome resolvida: dois arquivos distintos
            self.assertEqual(len({p.name for p in gerados}), 2)
            for caminho in gerados:
                self.assertTrue(caminho.exists())
                dados = caminho.read_bytes()
                self.assertTrue(dados.startswith(b"%PDF-"), caminho.name)
                self.assertGreater(len(dados), 5_000)
                # múltiplas páginas do formulário renderizadas
                self.assertGreaterEqual(dados.count(b"/Type /Page"), 1)
            # progresso reportado para a tela de carregamento
            self.assertEqual(len(fases), 2)

    def test_pasta_de_destino_e_criada(self):
        df = pd.DataFrame([linha_modelo()])
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "nova" / "fichas"
            gerados = exportar_fichas(df, destino)
            self.assertTrue(destino.is_dir())
            self.assertTrue(gerados[0].exists())

    def test_relata_ausencia_do_reportlab(self):
        from penna.cards.pdf_text import exigir_reportlab

        if _reportlab.REPORTLAB:
            exigir_reportlab()  # não deve levantar
        else:  # pragma: no cover - só quando reportlab não instalado
            with self.assertRaises(RuntimeError):
                exigir_reportlab()


try:
    import tkinter  # noqa: F401
    _TEM_TK = True
except ImportError:
    _TEM_TK = False


@unittest.skipUnless(_TEM_TK, "tkinter indisponível")
class TestOpcoesDeExportacao(unittest.TestCase):
    """A UI exporta somente o que foi marcado em OPÇÕES DE EXPORTAÇÃO."""

    @staticmethod
    def _app(txt, fichas):
        from penna.ui.app import PennaApp

        app = types.SimpleNamespace(
            var_exportar_txt=types.SimpleNamespace(get=lambda: txt),
            var_exportar_fichas=types.SimpleNamespace(get=lambda: fichas),
        )
        return PennaApp._opcoes_exportacao(app)

    def test_apenas_txt(self):
        self.assertEqual(self._app(True, False), (True, False))

    def test_apenas_fichas(self):
        self.assertEqual(self._app(False, True), (False, True))

    def test_ambas(self):
        self.assertEqual(self._app(True, True), (True, True))

    def test_objeto_sem_variaveis_mantem_comportamento_antigo(self):
        from penna.ui.app import PennaApp

        app = types.SimpleNamespace()  # testes antigos / objetos-falsos
        self.assertEqual(PennaApp._opcoes_exportacao(app), (True, False))


class _CanvasFalso:
    """Canvas de mentira: registra os textos desenhados, página por página."""

    def __init__(self, *_args, **_kwargs):
        self.paginas: list[list[str]] = []
        self._textos: list[str] = []
        self._doc = types.SimpleNamespace(userencode=True)

    def drawString(self, _x, _y, texto, *_args, **_kwargs):
        self._textos.append(str(texto))

    drawCentredString = drawString
    drawRightString = drawString

    def showPage(self):
        self.paginas.append(list(self._textos))
        self._textos = []

    def beginPath(self):
        return self

    def __getattr__(self, _nome):     # rect/line/setFont/...: ignorados
        return lambda *_args, **_kwargs: None


def textos_da_ficha(linha: dict) -> list[list[str]]:
    """Textos efetivamente desenhados pela ficha, por página (canvas falso)."""
    canvases: list[_CanvasFalso] = []

    def fabrica(*_args, **_kwargs):
        canvas_falso = _CanvasFalso()
        canvases.append(canvas_falso)
        return canvas_falso

    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(_reportlab.canvas, "Canvas", fabrica):
            gerar_ficha_pdf(linha, Path(tmp) / "ficha.pdf")
    return canvases[0].paginas


@unittest.skipUnless(_reportlab.REPORTLAB, "reportlab ausente")
class TestSoOQueOPacienteTem(unittest.TestCase):
    """As listas fixas do modelo só trazem o que o paciente fez/recebeu.

    Procedimentos não realizados e CIDs que não são do paciente saem da
    ficha em vez de ocupar espaço.
    """

    # ------------------------------------------------------------------
    # procedimentos (tabela de secundários e consultas do encerramento)
    def test_procedimento_nao_realizado_sai_da_ficha(self):
        modelo = template.carregar_modelo()
        ficha = montar_ficha(linha_modelo())
        # o paciente tem o Sec1 (02.11.06.023-2) e mais nada das listas
        feitas = {r for r, cod in modelo.proc_linhas
                  if cod == "021106023"}
        self.assertTrue(feitas, "fixture sem o procedimento secundário")
        for linha, _cod in modelo.proc_linhas:
            if linha in feitas:
                self.assertNotIn(linha, ficha["ocultar"])
            else:
                self.assertIn(linha, ficha["ocultar"],
                              f"linha {linha} sem procedimento ficou na ficha")

    def test_consulta_do_paciente_fica_e_a_outra_sai(self):
        modelo = template.carregar_modelo()
        linha = linha_modelo()
        linha["Cod_Procedimento"] = "0301010072"      # 03.01.01.007-2
        ficha = montar_ficha(linha)
        for ref, cod in modelo.geral_linhas:
            if cod == "030101007":
                self.assertNotIn(ref, ficha["ocultar"])
            else:
                self.assertIn(ref, ficha["ocultar"])
        # com uma consulta informada, o título/nota da seção continuam
        self.assertNotIn(constants.CONSULTAS_INI, ficha["ocultar"])

    def test_consulta_ausente_remove_titulo_e_nota_da_secao(self):
        ficha = montar_ficha(linha_modelo())     # sem consulta nenhuma
        for ref in range(constants.CONSULTAS_INI,
                         constants.CONSULTAS_FIM + 1):
            self.assertIn(ref, ficha["ocultar"])
        desenhado = "\n".join(t for pagina in textos_da_ficha(linha_modelo())
                              for t in pagina)
        self.assertNotIn("Ao menos um dos procedimentos", desenhado)

    def test_procedimento_fora_das_listas_vai_para_os_extras(self):
        """Procedimento que não está nas listas fixas não se perde:
        sai na página de OUTROS DADOS DA LINHA."""
        linha = linha_modelo()
        linha["Sec2_Cod_Procedimento"] = "0401010033"
        linha["Sec2_Cbo"] = "225265"
        linha["Sec2_Quantidade"] = "1"
        ficha = montar_ficha(linha)
        rotulos = {rotulo for rotulo, _, _ in ficha["extras"]}
        self.assertIn("SEC2 COD PROCEDIMENTO:", rotulos)

    def test_pdf_nao_imprime_procedimento_que_nao_foi_feito(self):
        modelo = template.carregar_modelo()
        feito = "021106023"
        desenhado = "\n".join(t for pagina in textos_da_ficha(linha_modelo())
                              for t in pagina)
        for linha, cod in modelo.proc_linhas:
            descricao = modelo.valor(linha, 4)
            if not descricao:
                continue
            if cod == feito:
                self.assertIn(descricao, desenhado)
            else:
                self.assertNotIn(descricao, desenhado,
                                 f"procedimento não feito saiu na ficha: {descricao}")

    # ------------------------------------------------------------- CIDs
    def test_tabela_de_cids_fica_so_com_o_cid_do_paciente(self):
        modelo = template.carregar_modelo()
        ficha = montar_ficha(linha_modelo())     # H40 + causas H00 e H52
        paciente = {"H00", "H40", "H52"}
        esquerda = dict(modelo.cid_esq)
        direita = dict(modelo.cid_dir)
        col_dir = constants.CID_COL_DIR
        # o que continua na ficha: nem linha oculta, nem metade suprimida
        desenhados: set[str] = set()
        for ref in sorted(set(esquerda) | set(direita)):
            if ref in ficha["ocultar"]:
                continue
            if (ref, 2) not in ficha["suprimir"]:
                desenhados.add(esquerda.get(ref, ""))
            if (ref, col_dir) not in ficha["suprimir"]:
                desenhados.add(direita.get(ref, ""))
        self.assertEqual(desenhados, paciente)
        self.assertLess(len(desenhados),
                        len(modelo.cid_esq) + len(modelo.cid_dir))

    def test_cid_fora_do_catalogo_nao_some_da_ficha(self):
        """CID que não está na tabela do modelo vai para os extras (não some)."""
        modelo = template.carregar_modelo()
        linha = linha_modelo()
        linha["Cid_Princ"] = "Z999"
        linha["Cid_Causas_Assoc"] = ""
        ficha = montar_ficha(linha)
        for ref, _cod in modelo.cid_esq + modelo.cid_dir:
            self.assertIn(ref, ficha["ocultar"])
        rotulos = {rotulo for rotulo, _, _ in ficha["extras"]}
        self.assertIn("CID PRINC:", rotulos)

    def test_pdf_nao_imprime_o_catalogo_de_cids(self):
        modelo = template.carregar_modelo()
        do_paciente = {"H00", "H40", "H52"}
        desenhado = "\n".join(t for pagina in textos_da_ficha(linha_modelo())
                              for t in pagina)
        for _ref, cod in modelo.cid_esq + modelo.cid_dir:
            if cod in do_paciente:
                self.assertIn(cod, desenhado)
            else:
                self.assertNotIn(cod, desenhado,
                                 f"CID do catálogo saiu na ficha: {cod}")


@unittest.skipUnless(_reportlab.REPORTLAB, "reportlab ausente")
class TestFichaEmUmaPagina(unittest.TestCase):
    """A ficha inteira (formulário + OUTROS DADOS DA LINHA) sai em UMA página.

    O modelo imprime em duas páginas (quebra na linha 68/69); a ficha reduz a
    escala para manter tudo em uma folha A4, com o bloco de extras logo
    abaixo do formulário em vez de virar página.
    """

    def test_modelo_nao_quebra_mais_o_formulario(self):
        modelo = template.carregar_modelo()
        self.assertEqual(modelo.paginas, [(1, modelo.linhas_total)])

    def test_pdf_tem_uma_unica_pagina(self):
        self.assertEqual(len(textos_da_ficha(linha_modelo())), 1)

    def test_extras_entram_na_mesma_pagina_do_formulario(self):
        paginas = textos_da_ficha(linha_modelo())
        desenhado = "\n".join(paginas[0])
        self.assertIn("ENCERRAMENTO DA APAC", desenhado)   # fim do formulário
        self.assertIn("OUTROS DADOS DA LINHA", desenhado)  # bloco de extras
        self.assertIn("2025/08", desenhado)                # competência (extra)

    def test_escala_cabe_na_pagina_e_nunca_amplia(self):
        modelo = template.carregar_modelo()
        ficha = montar_ficha(linha_modelo())
        escala = extras.escala_da_ficha(modelo, ficha)
        util_h = modelo.pagina[1] - modelo.margem_topo - modelo.margem_base
        altura = (modelo.altura_visivel(ficha["ocultar"])
                  + extras.EXTRA_GAP
                  + extras._altura_extras(ficha["extras"]))
        self.assertLessEqual(escala * altura, util_h + 0.5)
        self.assertLessEqual(escala, 1.0)
        self.assertGreater(escala, 0.9)     # praticamente em tamanho real

    def test_linhas_sem_tinta_do_formulario_nao_ocupam_espaco(self):
        """As folgas em branco do formulário saem da ficha (a altura que elas
        ocupavam é o que permite caber tudo em uma página), e nenhuma linha
        com tinta é escondida por isso."""
        from openpyxl.utils import get_column_letter

        modelo = template.carregar_modelo()
        ficha = montar_ficha(linha_modelo())
        sobre = ficha["sobrescritas"]

        def tem_tinta(linha: int) -> bool:
            for coluna in range(1, modelo.n_colunas + 1):
                info = modelo.celulas.get((linha, coluna)) or {}
                ref = f"{get_column_letter(coluna)}{linha}"
                texto = sobre.get(ref, info.get("valor"))
                fundo = str(info.get("fill") or "").lstrip("#").upper()
                if (texto and str(texto).strip()) or info.get("bordas") \
                        or (fundo and fundo != "FFFFFF"):
                    return True
            return False

        brancas = [
            r for r in range(1, modelo.linhas_total + 1)
            if modelo.alturas[r - 1] > 0
            and not any(modelo.merges.get((r, c))
                        for c in range(1, modelo.n_colunas + 1))
            and not tem_tinta(r)
        ]
        self.assertTrue(brancas, "o formulário não tem folga em branco")
        for ref in brancas:
            self.assertIn(ref, ficha["ocultar"],
                          f"linha em branco {ref} ficou ocupando espaço")

    def test_fica_em_uma_pagina_mesmo_sem_extras(self):
        linha = linha_modelo()
        for coluna in ("Competencia", "Inicio_Validade", "Fim_Validade",
                       "Tipo_Apac", "Tipo_Atendimento", "Codigo_Municipio",
                       "IBGE", "Cns_Executante", "Carater_Atend",
                       "Autorizador_Cpf", "Medico_Cpf", "Situacao_De_Rua",
                       "Numero_Apac_Anterior", "Nacionalidade"):
            linha[coluna] = ""
        self.assertEqual(len(textos_da_ficha(linha)), 1)


class TestBuscaDoModeloFrozen(unittest.TestCase):
    """No EXE one-file o exportador só encontra o modelo se ele estiver no
    bundle (``_MEIPASS``) ou ao lado do .exe — era o que faltava: o spec não
    embutia ``dados/modelo_ficha...xlsx`` e a exportação falhava no EXE.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.exe_dir = base / "app"
        self.bundle = base / "bundle"
        self.exe_dir.mkdir()
        self.bundle.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _frozen(self):
        """Contexto: EXE congelado, .exe em self.exe_dir, bundle em self.bundle."""
        return (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(
                sys, "executable", str(self.exe_dir / "PennaConversor.exe")
            ),
            mock.patch.object(sys, "_MEIPASS", str(self.bundle), create=True),
        )

    def test_acha_modelo_no_bundle_sem_nada_ao_lado(self):
        """Cenário do bug reportado: instalação só com o .exe (one-file) —
        o modelo vem embutido no bundle e DEVE ser encontrado lá."""
        modelo = self.bundle / "dados" / constants.NOME_TEMPLATE
        modelo.parent.mkdir()
        modelo.write_bytes(b"")
        with contextlib.ExitStack() as st:
            for patch in self._frozen():
                st.enter_context(patch)
            achado = template.achar_template()
        self.assertEqual(achado, modelo)

    def test_modelo_ao_lado_do_exe_vence_o_bundle(self):
        """Padrão do penna_config.json: o que o cliente deixar/editar ao lado
        do .exe tem prioridade sobre o arquivo de fábrica no bundle."""
        de_fabrica = self.bundle / "dados" / constants.NOME_TEMPLATE
        de_fabrica.parent.mkdir()
        de_fabrica.write_bytes(b"")
        editado = self.exe_dir / "dados" / constants.NOME_TEMPLATE
        editado.parent.mkdir()
        editado.write_bytes(b"")
        with contextlib.ExitStack() as st:
            for patch in self._frozen():
                st.enter_context(patch)
            achado = template.achar_template()
        self.assertEqual(achado, editado)

    def test_modelo_original_tambem_no_bundle(self):
        """O fallback de textos acentuados (MODELO_FATURAMENTO_OCI*.xlsx)
        também precisa estar embutido, senão os acentos voltam a vir da
        base S_PA sem acento no EXE."""
        orig = self.bundle / "MODELO_FATURAMENTO_OCI_teste.xlsx"
        orig.write_bytes(b"")
        with contextlib.ExitStack() as st:
            for patch in self._frozen():
                st.enter_context(patch)
            achado = template.achar_template_original()
        self.assertEqual(achado, orig)

    def test_ordem_dos_candidatos_frozen(self):
        """Ordem: ao lado do .exe → bundle → diretório do módulo → CWD."""
        with contextlib.ExitStack() as st:
            for patch in self._frozen():
                st.enter_context(patch)
            bases = template.bases_template()
        self.assertEqual(bases[0], self.exe_dir.resolve())
        self.assertEqual(bases[1], self.bundle)


if __name__ == "__main__":
    unittest.main()
