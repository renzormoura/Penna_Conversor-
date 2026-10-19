"""Área de arraste/clique com estados visuais (idle, dragover, loaded)."""
from __future__ import annotations

import tkinter as tk
from tkinter import TclError

from ..theme import (
    COR_AZUL_DASH,
    COR_AZUL_PRINCIPAL,
    COR_AZUL_TINT,
    COR_BRANCO,
    COR_SUCESSO,
    COR_SUCESSO_BG,
    COR_SUCESSO_BORDA,
    COR_TEXTO_HINT,
    COR_TEXTO_MEDIO,
    COR_TEXTO_TITULO,
)


class DropZone(tk.Canvas):
    """Área de arraste/clique com três estados visuais: idle, dragover, loaded."""

    def __init__(self, master, hint_text: str, on_click_callback=None, **kw):
        super().__init__(master, height=144, highlightthickness=0, bd=0,
                         bg=COR_BRANCO, cursor="hand2", **kw)
        self._hint = hint_text
        self._text = hint_text
        self._state = "idle"
        self._file_name = ""
        self._file_size = ""
        self._on_click = on_click_callback
        self.bind("<Configure>", lambda _: self._render())
        self.bind("<Button-1>", self._handle_click)
        self._render()

    def _handle_click(self, _event) -> None:
        if self._on_click is not None:
            self._on_click()

    # ---- Mutações de estado públicas ----

    def set_state_idle(self, hint_text: str | None = None) -> None:
        self._state = "idle"
        if hint_text:
            self._hint = self._text = hint_text
        self._render()

    def set_state_dragover(self) -> None:
        self._state = "dragover"
        self._render()

    def set_state_loaded(self, file_name: str, file_size: str = "") -> None:
        self._state = "loaded"
        self._file_name = file_name
        self._file_size = file_size
        self._render()

    # ---- configure retrocompat (aceita `text=` sem quebrar) ----

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        text_val = kw.pop("text", None)
        kw.pop("bg", None)
        kw.pop("fg", None)
        kw.pop("relief", None)
        kw.pop("bd", None)
        if text_val is not None:
            s = str(text_val)
            if "Arquivo recebido" in s:
                parts = s.splitlines()
                self._state = "loaded"
                self._file_name = parts[-1] if len(parts) > 1 else s
            elif "SOLTE" in s.upper():
                self._state = "dragover"
            else:
                self._state = "idle"
                self._text = s
        if kw:
            try:
                super().configure(**kw)
            except (TclError, RuntimeError):
                pass
        self._render()

    config = configure

    def _render(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 260)
        h, m = 144, 5
        cx, cy = w // 2, h // 2

        if self._state == "dragover":
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_AZUL_TINT, outline=COR_AZUL_PRINCIPAL, width=2)
            self._draw_upload_icon(cx, cy, COR_AZUL_PRINCIPAL)
            self.create_text(cx, cy + 8, text="Solte a planilha Excel aqui",
                             font=("Segoe UI", 12, "bold"), fill=COR_AZUL_PRINCIPAL)
            self.create_text(cx, cy + 30, text="O arquivo será carregado instantaneamente",
                             font=("Segoe UI", 9), fill=COR_AZUL_PRINCIPAL)

        elif self._state == "loaded":
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_SUCESSO_BG, outline=COR_SUCESSO_BORDA, width=1.5)
            badge_y = cy - 26
            self.create_oval(cx - 15, badge_y - 15, cx + 15, badge_y + 15,
                             fill=COR_SUCESSO, outline="")
            self.create_line(cx - 6, badge_y, cx - 2, badge_y + 4, cx + 7, badge_y - 5,
                             fill=COR_BRANCO, width=2.5, capstyle="round", joinstyle="round")
            name = self._file_name
            if len(name) > 65:
                name = name[:32] + "..." + name[-28:]
            self.create_text(cx, cy + 8, text=name,
                             font=("Segoe UI", 11, "bold"), fill=COR_TEXTO_TITULO)
            extra = f" ({self._file_size})" if self._file_size else ""
            self.create_text(cx, cy + 30,
                             text=f"Planilha pronta para conversão{extra} • Clique para trocar",
                             font=("Segoe UI", 9), fill=COR_SUCESSO)

        else:  # idle
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_BRANCO, outline=COR_AZUL_DASH, width=1.5, dash=(6, 4))
            self._draw_upload_icon(cx, cy, COR_AZUL_PRINCIPAL, small=True)
            self.create_text(cx, cy + 6, text="Arraste e solte o arquivo Excel aqui",
                             font=("Segoe UI", 11, "bold"), fill=COR_TEXTO_TITULO)
            self.create_text(cx, cy + 26, text="ou clique nesta área para selecionar",
                             font=("Segoe UI", 9), fill=COR_TEXTO_MEDIO)
            self.create_text(cx, cy + 44, text="Suporta formatos .xlsx, .xlsm e .xls",
                             font=("Segoe UI", 8), fill=COR_TEXTO_HINT)

    def _draw_upload_icon(self, cx: int, cy: int, cor: str, small: bool = False) -> None:
        """Ícone de upload (seta para cima + bandeja)."""
        w_line = 2 if small else 2.5
        top = cy - 38 if small else cy - 40
        mid = cy - 18
        self.create_line(cx - 18, cy - 24, cx - 18, cy - 12,
                         cx + 18, cy - 12, cx + 18, cy - 24,
                         fill=cor, width=2, capstyle="round", joinstyle="round")
        self.create_line(cx, top, cx, mid, fill=cor, width=w_line, capstyle="round")
        self.create_line(cx - 7, cy - 26, cx, mid, cx + 7, cy - 26,
                         fill=cor, width=w_line, capstyle="round", joinstyle="round")
