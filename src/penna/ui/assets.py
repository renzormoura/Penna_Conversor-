"""Ícones e desenho da marca (ícone do PNG, com fallback vetorial)."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]

from penna import paths

from .theme import COR_AZUL_PRINCIPAL


def carregar_icone_foto(altura_alvo: int = 44):
    """Carrega o ícone oficial com antialiasing LANCZOS.

    Busca os candidatos na raiz de recursos (bundle do PyInstaller ou raiz do
    projeto). Retorna PhotoImage ou None se nenhum arquivo for encontrado.
    """
    nomes = ("penna.png", "penna_header.png", "penna.icon.png", "apac_icon.png", "apac_icon_header.png")
    candidates: list[Path] = [paths.project_root() / nome for nome in nomes]

    for path in candidates:
        if path.exists():
            try:
                if Image is not None and ImageTk is not None:
                    img = Image.open(path).convert("RGBA")
                    bbox = img.getbbox()
                    if bbox:
                        img = img.crop(bbox)
                    w, h = img.size
                    ratio = altura_alvo / max(1, h)
                    novo_w = max(1, round(w * ratio))
                    img = img.resize((novo_w, altura_alvo), Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(img)
                elif tk is not None:
                    return tk.PhotoImage(file=str(path))
            except (OSError, tk.TclError, ValueError):
                pass  # arquivo corrompido ou formato inválido: tenta o próximo
    return None


def desenhar_pena_vetorial(canvas, ox: int, oy: int,
                           escala: float = 0.65,
                           cor: str = COR_AZUL_PRINCIPAL) -> None:
    """Desenho vetorial de fallback da pena no azul oficial."""
    p = lambda x, y: (ox + x * escala, oy + y * escala)
    corpo = [p(36, 2), p(48, 24), p(47, 48), p(26, 72), p(8, 54), p(9, 26), p(21, 8)]
    canvas.create_polygon(corpo, smooth=True, fill=cor, outline="")
    canvas.create_line(
        [p(36, 5), p(39, 30), p(30, 54), p(25, 69)],
        smooth=True, width=max(2, round(2.5 * escala)), fill="#ffffff", capstyle="round",
    )
