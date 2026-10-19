"""Tarefas pesadas em segundo plano, com tela de carregamento e retorno na thread da UI."""
from __future__ import annotations

import logging
import threading
from tkinter import TclError
from typing import Any, Callable, Dict, Optional

from .widgets.loading_overlay import LoadingOverlay

log = logging.getLogger("penna.ui.tasks")

# Falhas esperadas de widget/thread Tk (janela destruída, fora do loop principal).
ERROS_TK = (TclError, RuntimeError)

INTERVALO_POLL_MS = 80

Progresso = Callable[[str, str], None]
Resultado = Dict[str, Any]


class TaskRunner:
    """Executa ``funcao(progresso)`` em thread enquanto o overlay mostra a etapa atual.

    O resultado é entregue sempre na thread principal, como ``{"ok": True, "valor": ...}``,
    ``{"ok": False, "erro": exc}`` ou ``{"cancelada": True}`` (outra tarefa tomou o lugar
    antes de esta entregar). Só uma tarefa fica ativa por vez.
    """

    def __init__(self, root, ao_falhar_callback: Optional[Callable[[str], None]] = None) -> None:
        self.root = root
        self._ao_falhar_callback = ao_falhar_callback
        self.seq = 0
        self.holder: Optional[dict] = None
        self.callback: Optional[Callable[[Resultado], None]] = None
        self.overlay: Optional[LoadingOverlay] = None

    def fechar_overlay(self) -> None:
        """Fecha a tela de carregamento, se houver."""
        overlay, self.overlay = self.overlay, None
        if overlay is not None:
            try:
                overlay.fechar()
            except ERROS_TK:
                pass

    def _cancelar_anterior(self) -> None:
        """Tarefa anterior sem resultado entregue: encerra e avisa o dono."""
        anterior = self.callback
        if anterior is None:
            return
        self.fechar_overlay()
        try:
            anterior({"ok": False, "cancelada": True})
        except Exception:  # noqa: BLE001  fronteira: callback de terceiros
            log.exception("callback da tarefa cancelada falhou")

    def iniciar(
        self,
        titulo: str,
        detalhe: str,
        funcao: Callable[[Progresso], Any],
        ao_concluir: Callable[[Resultado], None],
    ) -> None:
        """Inicia ``funcao`` em thread; ``progresso(titulo, detalhe)`` atualiza o overlay."""
        self._cancelar_anterior()

        self.seq += 1
        seq = self.seq
        holder: dict = {}
        self.holder = holder
        self.callback = ao_concluir

        overlay = LoadingOverlay(self.root, titulo, detalhe=detalhe)
        self.overlay = overlay
        overlay.tornar_modal()

        def progresso(titulo_fase: str, detalhe_fase: str = "") -> None:
            fase = (titulo_fase, detalhe_fase)
            holder["fase"] = fase
            holder.setdefault("fases", []).append(fase)

        def runner() -> None:
            try:
                holder.update({"fim": True, "ok": True, "valor": funcao(progresso)})
            except Exception as exc:  # noqa: BLE001  fronteira da thread: devolve o erro ao dono
                log.exception("tarefa em segundo plano falhou")
                holder.update({"fim": True, "ok": False, "erro": exc})

        try:
            threading.Thread(target=runner, daemon=True, name="penna-tarefa").start()
        except RuntimeError as exc:
            # Sem thread não há como processar: devolve o erro imediatamente.
            self.fechar_overlay()
            self.callback = None
            ao_concluir({"ok": False, "erro": exc})
            return

        ultima_fase: list = [None]

        def poll() -> None:
            if seq != self.seq:
                return  # outra tarefa assumiu; o overlay novo já está no ar
            if not holder.get("fim"):
                fase = holder.get("fase")
                if fase is not None and fase != ultima_fase[0]:
                    ultima_fase[0] = fase
                    try:
                        overlay.set_mensagem(fase[0], detalhe=fase[1])
                    except ERROS_TK:
                        pass
                try:
                    self.root.after(INTERVALO_POLL_MS, poll)
                except ERROS_TK:
                    pass
                return
            self.fechar_overlay()
            self.callback = None
            try:
                ao_concluir(holder)
            except Exception as exc:  # noqa: BLE001  fronteira: callback da UI
                log.exception("callback de conclusao da tarefa falhou")
                if self._ao_falhar_callback is not None:
                    self._ao_falhar_callback(f"Erro: {exc}")

        try:
            self.root.after(INTERVALO_POLL_MS, poll)
        except ERROS_TK:
            pass
