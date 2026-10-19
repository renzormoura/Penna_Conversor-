"""Tela de carregamento modal com spinner e mensagem de fase."""
from __future__ import annotations

import tkinter as tk
from tkinter import TclError

from ..theme import (
    COR_AZUL_PRINCIPAL,
    COR_BORDA,
    COR_BRANCO,
    COR_TEXTO_MEDIO,
    COR_TEXTO_TITULO,
)


class LoadingOverlay(tk.Toplevel):
    """Janela de carregamento centralizada sobre a janela principal.

    Exibe um spinner animado, uma mensagem principal e uma mensagem
    de detalhe que podem ser atualizadas em tempo real via `set_mensagem()`.

    Uso:
        overlay = LoadingOverlay(root, "Gerando arquivo...")
        overlay.tornar_modal()   # best-effort: bloqueia a janela principal
        # ... trabalho pesado em outra thread, com set_mensagem() por etapa ...
        overlay.fechar()
    """

    _RAIO      = 18      # raio do spinner
    _ESPESSURA = 4       # largura do arco
    _PASSOS    = 12      # segmentos do spinner
    _INTERVALO = 60      # ms por frame

    def __init__(self, parent, mensagem: str = "Processando…", detalhe: str = "") -> None:
        super().__init__(parent)
        self._parent = parent
        self._angulo = 0
        self._ativo  = True
        self._after_id = None

        # Janela sem decoração, sempre no topo
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COR_BRANCO)

        # Sombra leve via borda
        outer = tk.Frame(
            self, bg=COR_BORDA,
            highlightthickness=0, bd=0,
        )
        outer.pack(padx=1, pady=1)

        inner = tk.Frame(outer, bg=COR_BRANCO, padx=40, pady=32)
        inner.pack()

        # Spinner canvas
        d = (self._RAIO + self._ESPESSURA) * 2 + 4
        self._canvas = tk.Canvas(
            inner, width=d, height=d,
            bg=COR_BRANCO, highlightthickness=0, bd=0,
        )
        self._canvas.pack(pady=(0, 18))
        self._desenhar_spinner(0)

        # Mensagem principal
        self._lbl_msg = tk.Label(
            inner, text=mensagem,
            bg=COR_BRANCO, fg=COR_TEXTO_TITULO,
            font=("Segoe UI", 12, "bold"),
            wraplength=280,
        )
        self._lbl_msg.pack()

        # Detalhe
        self._lbl_detalhe = tk.Label(
            inner, text=detalhe or "",
            bg=COR_BRANCO, fg=COR_TEXTO_MEDIO,
            font=("Segoe UI", 9),
            wraplength=280,
        )
        self._lbl_detalhe.pack(pady=(4, 0))

        self._centralizar()
        self.lift()
        self.focus_set()
        self._animar()

    # ------------------------------------------------------------------
    # Posicionamento
    # ------------------------------------------------------------------

    def _centralizar(self) -> None:
        self.update_idletasks()
        pw = self._parent.winfo_width()
        ph = self._parent.winfo_height()
        px = self._parent.winfo_rootx()
        py = self._parent.winfo_rooty()
        w  = self.winfo_reqwidth()
        h  = self.winfo_reqheight()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Spinner
    # ------------------------------------------------------------------

    def _desenhar_spinner(self, angulo_inicio: int) -> None:
        self._canvas.delete("all")
        cx = cy = self._RAIO + self._ESPESSURA + 2
        r  = self._RAIO

        # Trilha cinza suave
        self._canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=0, extent=359,
            style="arc", outline=COR_BORDA,
            width=self._ESPESSURA,
        )

        # Arco azul animado (270° de extensão)
        self._canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=angulo_inicio, extent=270,
            style="arc", outline=COR_AZUL_PRINCIPAL,
            width=self._ESPESSURA,
        )

    def _animar(self) -> None:
        if not self._ativo:
            return
        self._angulo = (self._angulo + 12) % 360
        self._desenhar_spinner(self._angulo)
        try:
            self._after_id = self.after(self._INTERVALO, self._animar)
        except (TclError, RuntimeError):
            pass

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_mensagem(self, mensagem: str, detalhe: str = "") -> None:
        """Atualiza o texto exibido sem fechar o overlay."""
        try:
            self._lbl_msg.configure(text=mensagem)
            self._lbl_detalhe.configure(text=detalhe or "")
            self._centralizar()
            self.update_idletasks()
        except (TclError, RuntimeError):
            pass

    def tornar_modal(self) -> None:
        """Bloqueia a interação com a janela principal enquanto visível.

        Best-effort: se o grab falhar (janela ainda não mapeada), o
        overlay segue apenas informativo — o fluxo continua correto.
        """
        def _grab() -> None:
            try:
                if self.winfo_exists():
                    self.grab_set()
            except (TclError, RuntimeError):
                pass
        try:
            self.after(30, _grab)
        except (TclError, RuntimeError):
            pass

    def fechar(self) -> None:
        """Para a animação e fecha o overlay."""
        self._ativo = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except (TclError, RuntimeError):
                pass
        try:
            self.grab_release()
        except (TclError, RuntimeError):
            pass
        try:
            self.destroy()
        except (TclError, RuntimeError):
            pass
        try:
            self._parent.focus_set()
        except (TclError, RuntimeError):
            pass
