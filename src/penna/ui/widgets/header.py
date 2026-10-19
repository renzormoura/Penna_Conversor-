"""Cabeçalho da janela: ícone da marca e competência detectada."""
from __future__ import annotations

import tkinter as tk

from ..theme import (
    COR_AZUL_BORDA,
    COR_AZUL_PRINCIPAL,
    COR_AZUL_TINT,
    COR_BORDA,
    COR_BRANCO,
    COR_FUNDO,
    COR_SUCESSO,
    COR_TEXTO_CORPO,
    COR_TEXTO_MEDIO,
    COR_TEXTO_TITULO,
)
from ..assets import carregar_icone_foto, desenhar_pena_vetorial


class HeaderCanvas(tk.Canvas):
    """Cabeçalho minimalista: fundo branco, faixa azul no topo, ícone e badge."""

    def __init__(self, master, **kw):
        super().__init__(master, height=76, highlightthickness=0, bd=0, bg=COR_BRANCO, **kw)
        self._icon_photo = carregar_icone_foto(altura_alvo=42)
        self._competencia = ""
        self.bind("<Configure>", lambda _: self._render())
        self._render()

    def set_competencia(self, texto: str) -> None:
        """Exibe no cabeçalho o mês analisado nos formularios (ex.:
        'COMPETÊNCIA 2026/06 • JUN'). Texto vazio limpa a exibição."""
        self._competencia = texto or ""
        self._render()

    def _render(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 400)
        h = 76

        self.create_rectangle(0, 0, w, h, fill=COR_BRANCO, outline="")
        self.create_rectangle(0, 0, w, 3, fill=COR_AZUL_PRINCIPAL, outline="")
        self.create_line(0, h - 1, w, h - 1, fill=COR_BORDA, width=1)

        if self._icon_photo is not None:
            self.create_image(44, 40, image=self._icon_photo)
        else:
            desenhar_pena_vetorial(self, 28, 16, escala=0.68, cor=COR_AZUL_PRINCIPAL)

        self.create_text(76, 29, text="PENNA",
                         font=("Segoe UI", 18, "bold"), fill=COR_TEXTO_TITULO, anchor="w")

        bx1, by1, bx2, by2 = 168, 20, 262, 38
        self.create_rectangle(bx1, by1, bx2, by2, fill=COR_AZUL_TINT, outline=COR_AZUL_BORDA, width=1)
        self.create_text((bx1 + bx2) // 2, (by1 + by2) // 2,
                         text="PENNA FISCAL", font=("Segoe UI", 8, "bold"), fill=COR_AZUL_PRINCIPAL)

        self.create_text(76, 52, text="Gerador e Validador de Arquivo Fiscal • SUS",
                         font=("Segoe UI", 9), fill=COR_TEXTO_MEDIO, anchor="w")

        if w >= 660:
            rx, pill_w, pill_h = w - 24, 126, 24
            py1 = (h - pill_h) // 2 + 1
            py2 = py1 + pill_h
            self.create_rectangle(rx - pill_w, py1, rx, py2, fill=COR_FUNDO, outline=COR_BORDA, width=1)
            dot_cx = rx - pill_w + 12
            dot_cy = (py1 + py2) // 2
            self.create_oval(dot_cx - 4, dot_cy - 4, dot_cx + 4, dot_cy + 4,
                             fill=COR_SUCESSO, outline="")
            self.create_text(rx - pill_w + 24, dot_cy, text="Sistema Pronto",
                             font=("Segoe UI", 8, "bold"), fill=COR_TEXTO_CORPO, anchor="w")

            if self._competencia:
                self.create_text(rx, py2 + 11, text=self._competencia,
                                 font=("Segoe UI", 8, "bold"),
                                 fill=COR_AZUL_PRINCIPAL, anchor="e")
