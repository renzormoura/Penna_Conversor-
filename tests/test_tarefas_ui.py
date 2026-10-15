"""Testes da máquina de tarefas em segundo plano (PennaApp._iniciar_tarefa).

Cobre o contrato da tela de carregamento sem montar a interface inteira:

* conclusão entrega o resultado na thread principal (callback único);
* erro da função vira ``{"ok": False, "erro": ...}`` para o dono;
* iniciar uma nova tarefa cancela a anterior (``{"cancelada": True}``);
* ``run_conversion`` não reentra enquanto ``_conversao_ativa`` estiver ativo.

Usa um objeto-falso com os atributos que a máquina lê (root, holders,
overlay) e um Tk real — necessário porque o overlay é um Toplevel de fato.
Sem display gráfico os testes são pulados.
"""
from __future__ import annotations

import threading
import time
import types
import unittest
from unittest import mock

try:
    import tkinter as tk
except Exception:  # pragma: sem cobertura
    tk = None

from ui import app as ui_app
from ui.app import PennaApp


def _esperar(condicao, root, timeout: float = 5.0) -> bool:
    """Roda o loop do Tk até a condição ser verdadeira (ou estourar)."""
    limite = time.time() + timeout
    while time.time() < limite:
        root.update()
        if condicao():
            return True
        time.sleep(0.01)
    root.update()
    return condicao()


@unittest.skipIf(tk is None, "tkinter indisponível")
class _BaseComTk(unittest.TestCase):
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

    def app_falso(self):
        """Objeto com o estado mínimo que _iniciar_tarefa manipula."""
        app = types.SimpleNamespace(
            root=self.root,
            _tarefa_cb=None,
            _tarefa_seq=0,
            _tarefa_holder=None,
            _tarefa_overlay=None,
            _conversao_ativa=False,
            status=[],
        )
        app._fechar_overlay = lambda: PennaApp._fechar_overlay(app)
        app._set_status = lambda msg, tipo="info": app.status.append((msg, tipo))
        return app


class TestIniciarTarefa(_BaseComTk):
    def test_concluso_entrega_resultado_na_thread_principal(self):
        app = self.app_falso()
        recebido: dict = {}

        def funcao(progresso):
            progresso("Lendo…", "etapa 1")
            time.sleep(0.05)
            return 42

        def ao_concluir(res):
            recebido["res"] = res
            recebido["thread"] = threading.current_thread().name

        PennaApp._iniciar_tarefa(app, "Titulo", "detalhe", funcao, ao_concluir)
        self.assertTrue(_esperar(lambda: "res" in recebido, self.root),
                        "callback não rodou")

        self.assertTrue(recebido["res"]["ok"])
        self.assertEqual(recebido["res"]["valor"], 42)
        self.assertEqual(recebido["thread"], threading.current_thread().name)
        # overlay fechado e fases registradas para o progresso
        self.assertIsNone(app._tarefa_overlay)
        self.assertIsNone(app._tarefa_cb)
        self.assertEqual(app._tarefa_holder["fases"][0], ("Lendo…", "etapa 1"))

    def test_erro_da_funcao_vai_para_o_callback(self):
        app = self.app_falso()
        recebido: dict = {}

        def funcao(progresso):
            raise ValueError("boom")

        PennaApp._iniciar_tarefa(app, "Titulo", "", funcao, recebido.update)
        self.assertTrue(_esperar(lambda: bool(recebido), self.root))
        self.assertFalse(recebido["ok"])
        self.assertIsInstance(recebido["erro"], ValueError)
        self.assertIsNone(app._tarefa_overlay)

    def test_tarefa_nova_cancela_a_anterior(self):
        app = self.app_falso()
        trava = threading.Event()
        chamadas_antigo: list = []
        novo: dict = {}

        def funcao_lenta(progresso):
            trava.wait(2.0)
            return "A"

        PennaApp._iniciar_tarefa(
            app, "A", "", funcao_lenta, lambda res: chamadas_antigo.append(dict(res)))
        # dá a tarefa A tempo de estar em andamento
        time.sleep(0.1)
        self.root.update()
        PennaApp._iniciar_tarefa(app, "B", "", lambda p: "B", novo.update)

        self.assertEqual(len(chamadas_antigo), 1)
        self.assertTrue(chamadas_antigo[0]["cancelada"])
        self.assertTrue(_esperar(lambda: "valor" in novo, self.root))
        self.assertEqual(novo["valor"], "B")

        # A termina depois: o callback antigo não é chamado de novo
        trava.set()
        time.sleep(0.2)
        self.root.update()
        self.assertEqual(len(chamadas_antigo), 1)
        self.assertIsNone(app._tarefa_cb)


class TestGuardaDeReentrada(_BaseComTk):
    def test_run_conversion_nao_reentra(self):
        app = self.app_falso()
        app._conversao_ativa = True  # conversão em andamento
        app.file_var = types.SimpleNamespace(get=lambda: "nao_existe.xlsx")

        with mock.patch.object(PennaApp, "_iniciar_tarefa") as iniciar, \
                mock.patch.object(PennaApp, "_set_status"), \
                mock.patch.object(ui_app, "messagebox") as messagebox:
            PennaApp.run_conversion(app)

        iniciar.assert_not_called()
        messagebox.showerror.assert_not_called()
        messagebox.showwarning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
