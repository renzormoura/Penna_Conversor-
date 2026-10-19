"""Teste de integração das OPÇÕES DE EXPORTAÇÃO na interface real.

Roda o ``PennaApp.run_conversion`` de verdade (validação, diálogos, tarefa em
segundo plano e mensagem final), com os diálogos nativos substituídos por
dublês, e confere que saem EXATAMENTE as opções marcadas:

* só TXT        -> sai o TXT com extensão do mês, nenhum PDF;
* só fichas     -> sai uma ficha PDF por linha, nenhum TXT;
* ambas         -> saem os dois;
* nenhuma       -> aviso e nenhum diálogo aberto.

Sem display gráfico os testes são pulados (mesma política de
``tests/test_tarefas_ui.py``).
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

try:
    import tkinter as tk
    from ui import app as ui_app
    from ui.app import PennaApp
except ImportError:  # sem tkinter: as classes de UI abaixo sao puladas
    tk = ui_app = PennaApp = None


def linha_valida() -> dict:
    """Linha que passa no gate (competência 202606, OCI oftalmológica)."""
    return {
        "Competencia": "202606",
        "Numero_Apac": "3326705551111",
        "Cnes_Executante": "4234316",
        "Cnes_Solicitante": "4234316",
        "Inicio_Validade": "20260601",
        "Fim_Validade": "20260630",
        "Tipo_Apac": "003",
        "Nome_Paciente": "PACIENTE TESTE EXPORTACAO",
        "Nome_Da_Mae": "MAE DO TESTE",
        "Cpf_Paciente": "12345678909",
        "Cns_Paciente": "712345678901234",
        "Data_Nascimento": "19550615",
        "Sexo": "F",
        "Raca": "01",
        "Cep": "26700000",
        "Logradouro": "081",
        "Rua": "RUA DAS FLORES",
        "Numero_Endereco": "10",
        "Bairro": "CENTRO",
        "Nome_Municipio": "MENDES",
        "Codigo_Municipio": "3302809",
        "Cod_Procedimento": "0905010035",
        "Cbo": "225265",
        "Quantidade": "1",
        "Cid_Princ": "H40",
        "Nome_Profissional": "MEDICO TESTE",
        "Autorizador_Nome": "MEDICO TESTE",
        "Autorizador_Cns": "712345678901235",
        "Data_Solicitacao": "20260601",
        "Data_Autorizacao": "20260602",
        "Data_Alta_Obito": "20260602",
        "Motivo_Saida": "11",
        "Carater_Atend": "01",
        "Sec1_Cod_Procedimento": "021106023",
        "Sec1_Cbo": "225265",
        "Sec1_Quantidade": "1",
    }


@unittest.skipIf(tk is None, "tkinter indisponível")
class TestExportacaoComOpcoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except Exception as exc:  # sem display (servidor/CI)
            raise unittest.SkipTest(f"sem display gráfico: {exc}")
        cls.root.withdraw()
        # O app agenda "carregar arquivo dos argumentos" — sem argumentos reais
        # ele tentaria abrir um caminho inexistente e abriria um diálogo.
        cls._argv = list(sys.argv)
        sys.argv = sys.argv[:1]
        cls.app = PennaApp(cls.root)

    @classmethod
    def tearDownClass(cls):
        sys.argv = cls._argv
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _esperar(self, condicao, timeout: float = 60.0) -> bool:
        limite = time.time() + timeout
        while time.time() < limite:
            self.root.update()
            if condicao():
                return True
            time.sleep(0.02)
        self.root.update()
        return condicao()

    def _exportar(self, txt: bool, fichas: bool) -> dict:
        """Roda o fluxo real com diálogos simulados e devolve o resultado."""
        resultado: dict = {}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            excel = tmp_path / "planilha_teste.xlsx"
            pd.DataFrame([linha_valida()]).to_excel(excel, index=False)
            destino_txt = tmp_path / "saida.txt"
            pasta_fichas = tmp_path / "fichas"

            app = self.app
            app.var_exportar_txt.set(txt)
            app.var_exportar_fichas.set(fichas)
            app.file_var.set(str(excel))
            app._conversao_ativa = False

            # gate coberto por test_validador_*; aqui interessa o fluxo da UI
            with mock.patch.object(ui_app, "validar_planilha", return_value=[]), \
                    mock.patch.object(ui_app, "messagebox") as messagebox, \
                    mock.patch.object(ui_app.filedialog, "asksaveasfilename",
                                      return_value=str(destino_txt)) as salvar, \
                    mock.patch.object(ui_app.filedialog, "askdirectory",
                                      return_value=str(pasta_fichas)) as pasta, \
                    mock.patch.object(
                        ui_app.remittance, "registrar_remessa",
                        side_effect=RuntimeError("remessa desativada no teste")):
                app.run_conversion()
                concluiu = self._esperar(
                    lambda: (messagebox.showinfo.called
                             or messagebox.showwarning.called
                             or messagebox.showerror.called))

                resultado = {
                    "concluiu": concluiu,
                    "dialogo_txt": salvar.called,
                    "dialogo_pasta": pasta.called,
                    "aviso": messagebox.showwarning,
                    "erro": messagebox.showerror,
                    "info": messagebox.showinfo,
                    "txt_gerado": [p.name for p in tmp_path.glob("*.JUN")]
                                 + [p.name for p in tmp_path.glob("*.txt")],
                    "fichas": [
                        (p.name, p.read_bytes()[:5], p.stat().st_size)
                        for p in sorted(pasta_fichas.glob("*.pdf"))
                    ] if pasta_fichas.exists() else [],
                    "mensagem": (messagebox.showinfo.call_args[0][1]
                                 if messagebox.showinfo.called else ""),
                    "aviso_titulo": (messagebox.showwarning.call_args[0][0]
                                      if messagebox.showwarning.called else ""),
                    "aviso_texto": (messagebox.showwarning.call_args[0][1]
                                    if messagebox.showwarning.called else ""),
                    "erro_texto": (messagebox.showerror.call_args[0][1]
                                   if messagebox.showerror.called else ""),
                }
        return resultado

    def test_apenas_txt(self):
        res = self._exportar(txt=True, fichas=False)
        self.assertTrue(res["concluiu"], f"fluxo não terminou: {res['erro_texto']}")
        self.assertEqual(res["erro_texto"], "")
        self.assertTrue(res["dialogo_txt"], "diálogo Salvar TXT não abriu")
        self.assertFalse(res["dialogo_pasta"], "pasta de fichas pedida sem opção")
        self.assertEqual(res["fichas"], [], "PDF gerado sem a opção marcada")
        self.assertEqual(res["txt_gerado"], ["saida.JUN"])
        self.assertIn("TXT gerado", res["mensagem"])
        self.assertNotIn("Fichas (PDF)", res["mensagem"])

    def test_apenas_fichas(self):
        res = self._exportar(txt=False, fichas=True)
        self.assertTrue(res["concluiu"], f"fluxo não terminou: {res['erro_texto']}")
        self.assertEqual(res["erro_texto"], "")
        self.assertFalse(res["dialogo_txt"], "diálogo Salvar TXT abriu sem a opção")
        self.assertTrue(res["dialogo_pasta"], "diálogo da pasta não abriu")
        self.assertEqual(res["txt_gerado"], [], "TXT gerado sem a opção marcada")
        self.assertEqual(len(res["fichas"]), 1, "esperava uma ficha por linha")
        nome, cabecalho, tamanho = res["fichas"][0]
        self.assertEqual(nome, "PACIENTE TESTE EXPORTACAO_3326705551111.pdf")
        self.assertEqual(cabecalho, b"%PDF-")
        self.assertGreater(tamanho, 5_000)
        self.assertIn("Fichas (PDF): 1 arquivo(s)", res["mensagem"])
        self.assertNotIn("TXT gerado", res["mensagem"])

    def test_ambas_as_opcoes(self):
        res = self._exportar(txt=True, fichas=True)
        self.assertTrue(res["concluiu"], f"fluxo não terminou: {res['erro_texto']}")
        self.assertEqual(res["erro_texto"], "")
        self.assertTrue(res["dialogo_txt"])
        self.assertTrue(res["dialogo_pasta"])
        self.assertEqual(res["txt_gerado"], ["saida.JUN"])
        self.assertEqual(len(res["fichas"]), 1)
        self.assertEqual(res["fichas"][0][1], b"%PDF-")
        self.assertIn("TXT gerado", res["mensagem"])
        self.assertIn("Fichas (PDF): 1 arquivo(s)", res["mensagem"])

    def test_nenhuma_opcao_avisa_e_nao_abre_dialogo(self):
        res = self._exportar(txt=False, fichas=False)
        self.assertFalse(res["dialogo_txt"])
        self.assertFalse(res["dialogo_pasta"])
        self.assertFalse(res["info"].called)
        self.assertTrue(res["aviso"].called)
        self.assertIn("Nenhuma exportação selecionada", res["aviso_titulo"])
        self.assertEqual(res["txt_gerado"], [])
        self.assertEqual(res["fichas"], [])


if __name__ == "__main__":
    unittest.main()
