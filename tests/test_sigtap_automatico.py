"""Automático: o seletor foca e baixa o mês da planilha de cara.

Reclamação real de usuário: planilha de um mês diferente não era aceita —
o modo Automático nunca escolhia/baixava a base do mês dos formulários e a
validação caía nas bases locais de outro mês, sem download automático.

Coberto:
* ``sincronizar_com_planilha`` foca o mês da planilha no combobox;
* mês só no FTP -> download começa sozinho (uma única vez);
* escolha manual no combobox nunca é sobrescrita;
* voltar para "Automático" à mão reativa a detecção;
* mês ausente do FTP volta para "Automático" com aviso;
* foco pendente é aplicado quando as listas terminam de carregar;
* download falho permite nova tentativa e sucesso notifica ``on_change``;
* ``PennaApp`` chama a sincronização em ``test_load`` e ``run_conversion``;
* ``_resolver_sigtap`` usa o mês da planilha uma vez o ZIP estar em cache.

Sem display gráfico os testes de Tk são pulados (mesma política dos demais
testes de interface).
"""
from __future__ import annotations

import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from penna import remittance  # noqa: F401
from penna.services import validation as validacao_servico

try:
    import tkinter as tk
    from penna.ui import app as ui_app
    from penna.ui.app import PennaApp
    from penna.ui.widgets import SigtapSelector
except ImportError:  # sem tkinter: as classes de UI abaixo sao puladas
    tk = ui_app = PennaApp = SigtapSelector = None


def _esperar(condicao, root, timeout: float = 5.0) -> bool:
    limite = time.time() + timeout
    while time.time() < limite:
        root.update()
        if condicao():
            return True
        time.sleep(0.01)
    root.update()
    return condicao()


class TestResolverSigtap(unittest.TestCase):
    """resolver_sigtap (serviço, sem UI): o cache decide o mês."""

    def test_usa_mes_da_planilha_quando_zip_em_cache(self):
        with mock.patch("penna.reference.sigtap.listar_competencias_cache",
                        return_value=["202604"]):
            self.assertEqual(validacao_servico.resolver_sigtap("", "202604"), "202604")

    def test_sem_zip_em_cache_devolve_vazio_para_fallback_local(self):
        with mock.patch("penna.reference.sigtap.listar_competencias_cache",
                        return_value=[]):
            self.assertEqual(validacao_servico.resolver_sigtap("", "202604"), "")

    def test_escolha_manual_vence_o_cache(self):
        with mock.patch("penna.reference.sigtap.listar_competencias_cache",
                        return_value=["202604"]):
            self.assertEqual(validacao_servico.resolver_sigtap("202601", "202604"),
                             "202601")


@unittest.skipIf(tk is None, "tkinter indisponível")
class TestSincronizacaoNaApp(unittest.TestCase):
    """PennaApp delega ao seletor sem derrubar a UI se ele faltar."""

    def test_delega_ao_seletor(self):
        seletor = mock.Mock()
        app = types.SimpleNamespace(sigtap_sel=seletor)
        PennaApp._sincronizar_sigtap_planilha(app, "202604")
        seletor.sincronizar_com_planilha.assert_called_once_with("202604")

    def test_sem_seletor_nao_quebra(self):
        PennaApp._sincronizar_sigtap_planilha(types.SimpleNamespace(), "202604")

    def test_sem_competencia_nao_faz_nada(self):
        seletor = mock.Mock()
        app = types.SimpleNamespace(sigtap_sel=seletor)
        PennaApp._sincronizar_sigtap_planilha(app, "")
        seletor.sincronizar_com_planilha.assert_not_called()

    def test_erro_no_seletor_e_contido(self):
        seletor = mock.Mock()
        seletor.sincronizar_com_planilha.side_effect = RuntimeError("UI morta")
        app = types.SimpleNamespace(sigtap_sel=seletor)
        PennaApp._sincronizar_sigtap_planilha(app, "202604")  # não levanta


@unittest.skipIf(tk is None, "tkinter indisponível")
class TestSigtapSelectorAutomatico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except Exception as exc:  # sem display (servidor/CI)
            raise unittest.SkipTest(f"sem display gráfico: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _seletor(self, local=(), ftp=()):
        """Seletor com listas simuladas (sem rede, sem thread).

        A thread real depende de ``after`` cross-thread, que só funciona
        dentro de ``mainloop()`` (os testes bombeiam ``update()``). Aqui a
        mesma ``_aplicar_listas`` roda síncrono — mesmo caminho de código.
        """
        with mock.patch.object(SigtapSelector, "_atualizar_listas_async",
                               lambda self: None):
            sel = SigtapSelector(self.root)
        # em produção a thread grava as listas e só então aplica na UI
        sel._competencias_local = set(local)
        sel._competencias_ftp = list(ftp)
        todas = sorted(set(ftp) | set(local), reverse=True)
        sel._aplicar_listas(["Automático"] + [sel._fmt(c) for c in todas], todas)
        self.assertTrue(sel._ftp_pronto, "listas do seletor não aplicadas")
        return sel

    def test_foca_mes_quando_ja_em_cache(self):
        sel = self._seletor(local=["202604"], ftp=["202604"])
        with mock.patch.object(sel, "_iniciar_download") as baixar:
            sel.sincronizar_com_planilha("202604")
        self.assertEqual(sel.get_competencia(), "202604")
        baixar.assert_not_called()
        self.assertIn("cache local", sel._lbl_status.cget("text"))

    def test_baixa_automaticamente_quando_mes_so_no_ftp(self):
        sel = self._seletor(local=[], ftp=["202604", "202606"])
        with mock.patch.object(sel, "_iniciar_download") as baixar:
            sel.sincronizar_com_planilha("202604")
            self.assertEqual(baixar.call_count, 1,
                             "download automático não disparou")
            # revalidação pós-download (on_change) não deve repetir o download
            sel.sincronizar_com_planilha("202604")
            self.assertEqual(baixar.call_count, 1)
        self.assertEqual(sel.get_competencia(), "202604")

    def test_nao_sobrescreve_escolha_manual_do_usuario(self):
        sel = self._seletor(local=["202602", "202604"],
                            ftp=["202602", "202604"])
        sel.competencia_var.set("2026/02")
        sel._ao_selecionar()  # ação do usuário no combobox
        sel.sincronizar_com_planilha("202604")
        self.assertEqual(sel.get_competencia(), "202602",
                         "foco automático sobrescreveu escolha manual")

    def test_automático_escolhido_a_mão_reativa_a_deteccao(self):
        sel = self._seletor(local=["202602", "202604"],
                            ftp=["202602", "202604"])
        sel.competencia_var.set("2026/02")
        sel._ao_selecionar()
        sel.sincronizar_com_planilha("202604")
        self.assertEqual(sel.get_competencia(), "202602")
        # usuário volta para "Automático": a próxima planilha é detectada
        sel.competencia_var.set("Automático")
        sel._ao_selecionar()
        sel.sincronizar_com_planilha("202604")
        self.assertEqual(sel.get_competencia(), "202604")

    def test_mes_ausente_no_ftp_volta_para_automatico_com_aviso(self):
        sel = self._seletor(local=[], ftp=["202606"])
        sel.sincronizar_com_planilha("202601")
        self.assertEqual(sel.get_competencia(), "")
        self.assertIn("sem base no FTP", sel._lbl_status.cget("text"))

    def test_foco_pendente_aplica_quando_listas_concluem(self):
        sel = self._seletor(local=[], ftp=["202604"])
        sel._ftp_pronto = False  # simula listas ainda carregando
        sel.sincronizar_com_planilha("202604")
        self.assertEqual(sel.competencia_var.get(), "Automático",
                         "foco aplicado antes das listas chegarem")
        sel._aplicar_listas(["Automático", "2026/04"], ["202604"])
        self.assertEqual(sel.get_competencia(), "202604")

    def test_download_falho_permite_nova_tentativa(self):
        sel = self._seletor(local=[], ftp=["202604"])
        with mock.patch.object(sel, "_iniciar_download") as baixar:
            sel.sincronizar_com_planilha("202604")
            self.assertEqual(baixar.call_count, 1)
            sel._baixando = True
            sel._download_concluido("202604", sucesso=False)
            sel.sincronizar_com_planilha("202604")
            self.assertEqual(baixar.call_count, 2,
                             "falha no download bloqueou nova tentativa")

    def test_download_concluido_notifica_on_change(self):
        sel = self._seletor(local=[], ftp=["202604"])
        notificado = []
        sel._on_change = notificado.append
        sel._baixando = True
        sel._download_concluido("202604", sucesso=True)
        self.assertEqual(notificado, ["202604"])


@unittest.skipIf(tk is None, "tkinter indisponível")
class TestSincronizacaoNoFluxoReal(unittest.TestCase):
    """Fiação da UI: carregar/executar sincroniza o seletor com o mês lido."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except Exception as exc:  # sem display (servidor/CI)
            raise unittest.SkipTest(f"sem display gráfico: {exc}")
        cls.root.withdraw()
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

    def _excel_tmp(self, tmp: Path) -> Path:
        linha = {
            "Competencia": "202604",
            "Numero_Apac": "3326704442222",
            "Nome_Paciente": "PACIENTE TESTE SIGTAP",
        }
        excel = tmp / "planilha_mes_diferente.xlsx"
        pd.DataFrame([linha]).to_excel(excel, index=False)
        return excel

    def _esperar(self, condicao, timeout: float = 30.0) -> bool:
        return _esperar(condicao, self.root, timeout)

    def test_test_load_sincroniza_seletor_com_o_mes(self):
        app = self.app
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            excel = self._excel_tmp(Path(tmp))
            app.file_var.set(str(excel))
            with mock.patch.object(validacao_servico, "validar_planilha", return_value=[]), \
                 mock.patch.object(PennaApp, "_sincronizar_sigtap_planilha") as sync:
                app.test_load()
                self.assertTrue(
                    self._esperar(lambda: sync.called),
                    "test_load não sincronizou o seletor com o mês")
                sync.assert_called_with("202604")

    def test_run_conversion_sincroniza_seletor_com_o_mes(self):
        app = self.app
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            excel = self._excel_tmp(tmp_path)
            app.file_var.set(str(excel))
            app.var_exportar_txt.set(True)
            app.var_exportar_fichas.set(False)
            app._conversao_ativa = False
            with mock.patch.object(validacao_servico, "validar_planilha", return_value=[]), \
                 mock.patch.object(ui_app, "messagebox") as messagebox, \
                 mock.patch.object(ui_app.filedialog, "asksaveasfilename",
                                   return_value=str(tmp_path / "saida.txt")), \
                 mock.patch.object(PennaApp, "_sincronizar_sigtap_planilha") as sync:
                app.run_conversion()
                self.assertTrue(
                    self._esperar(lambda: sync.called
                                  or messagebox.showinfo.called
                                  or messagebox.showerror.called),
                    "run_conversion não terminou")
                self.assertTrue(sync.called,
                                "run_conversion não sincronizou o seletor")
                sync.assert_called_with("202604")


if __name__ == "__main__":
    unittest.main()
