"""Casos de uso sem interface: caminhos, plano de exportação e textos finais."""
from __future__ import annotations

import unittest
from pathlib import Path

from penna.services.export import PlanoExportacao, ResultadoExportacao
from penna.services.files import eh_planilha_excel, formatar_tamanho_bytes
from penna.services.messages import mensagem_exportacao, rotulo_do_que_saiu, status_exportacao
from penna.services.validation import texto_regras_desativadas

AVISOS = "{n_avs} aviso(s) de teste."


class TestArquivos(unittest.TestCase):
    def test_tamanho_legivel(self):
        self.assertEqual(formatar_tamanho_bytes(512), "512 B")
        self.assertEqual(formatar_tamanho_bytes(2048), "2.0 KB")
        self.assertEqual(formatar_tamanho_bytes(3 * 1024 * 1024), "3.0 MB")

    def test_planilha_excel_exige_extensao_e_existencia(self):
        self.assertFalse(eh_planilha_excel(Path("nao_existe.xlsx")))
        self.assertTrue(eh_planilha_excel(Path(__file__).resolve().parent.parent / "Excel_Base.xlsx"))
        self.assertFalse(eh_planilha_excel(Path(__file__)))


class TestPlano(unittest.TestCase):
    def test_algo_a_exportar(self):
        self.assertFalse(PlanoExportacao(False, False).algo_a_exportar)
        self.assertTrue(PlanoExportacao(True, False).algo_a_exportar)
        self.assertTrue(PlanoExportacao(False, True).algo_a_exportar)


class TestMensagens(unittest.TestCase):
    TXT = Path("C:/saida/APCEO26P.JUN")

    def test_rotulo_so_do_que_saiu(self):
        self.assertEqual(rotulo_do_que_saiu(ResultadoExportacao()), "nenhum arquivo")
        self.assertEqual(rotulo_do_que_saiu(ResultadoExportacao(txt=self.TXT)), "APCEO26P.JUN")
        misto = ResultadoExportacao(txt=self.TXT, fichas=[Path("a.pdf"), Path("b.pdf")])
        self.assertEqual(rotulo_do_que_saiu(misto), "APCEO26P.JUN + 2 ficha(s) PDF")

    def test_status_com_e_sem_avisos(self):
        res = ResultadoExportacao(txt=self.TXT)
        self.assertEqual(status_exportacao(res, 0, "202606", ".JUN", ""),
                         "Exportação gerada — competência 2026/06: APCEO26P.JUN")
        self.assertEqual(status_exportacao(res, 2, "202606", ".JUN", ""),
                         "Exportação com 2 aviso(s) — competência 2026/06: APCEO26P.JUN")

    def test_status_resume_as_regras_desativadas(self):
        aviso = texto_regras_desativadas(["CEP inexistente (S_CEP)"])
        status = status_exportacao(ResultadoExportacao(txt=self.TXT), 0, "202606", ".JUN", aviso)
        self.assertTrue(status.endswith("— 1 regra desativada nesta validação (base ausente)."))

    def test_dialogo_final_completo(self):
        res = ResultadoExportacao(
            txt=self.TXT, comprovante=Path("c.PRN"), demonstrativo=Path("d.TXT"),
            aviso_remessa="disco cheio", fichas=[Path("a.pdf")],
        )
        texto = mensagem_exportacao(res, 3, "202606", ".JUN", Path("C:/saida/meu.txt"),
                                    Path("C:/fichas"), "", AVISOS)
        for trecho in ("TXT gerado:", "extensão .JUN fixada", "Nome ajustado: meu.txt → APCEO26P.JUN",
                       "Comprovante:", "Demonstrativo:", "histórico de remessa não registrado (disco cheio)",
                       "Fichas (PDF): 1 arquivo(s)", "3 aviso(s) de teste."):
            self.assertIn(trecho, texto)

    def test_so_fichas_nao_menciona_txt(self):
        texto = mensagem_exportacao(ResultadoExportacao(fichas=[Path("a.pdf")]), 0, "202606", ".JUN",
                                    None, Path("C:/fichas"), "", AVISOS)
        self.assertNotIn("TXT gerado", texto)
        self.assertIn("Fichas (PDF)", texto)


if __name__ == "__main__":
    unittest.main()
