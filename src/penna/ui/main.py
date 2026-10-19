"""Ponto de entrada da interface: log em arquivo, janela e carga da planilha inicial."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from tkinter import Tk

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None  # type: ignore[assignment]

from penna import paths

from .app import PennaApp

LOG_FILENAME = "penna.log"
EXEMPLO_NO_DESKTOP = "base exemplo.xlsx"


def configurar_logging() -> None:
    r"""Log em arquivo (o executável não tem console): ``%LOCALAPPDATA%\PennaConversor\penna.log``.

    Guarda só tracebacks de falhas inesperadas, com rotação. Falha ao criar o
    arquivo nunca impede o programa de abrir.
    """
    pasta = paths.user_data_dir()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            pasta / LOG_FILENAME, maxBytes=512_000, backupCount=2, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger("penna")
    raiz.setLevel(logging.INFO)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in raiz.handlers):
        raiz.addHandler(handler)


def _carregar_planilha_inicial(app: PennaApp) -> None:
    """Planilha passada na linha de comando; senão a de exemplo do Desktop, se existir."""
    if len(sys.argv) > 1:
        app.set_file(" ".join(sys.argv[1:]))
        return
    for desktop in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"):
        candidato = desktop / EXEMPLO_NO_DESKTOP
        if candidato.exists():
            app.set_file(str(candidato))
            if app.file_var.get():
                app._set_status(f"{EXEMPLO_NO_DESKTOP} carregado do Desktop.", tipo="sucesso")
            return


def main() -> None:
    """Inicia o Penna em modo standalone (TkinterDnD quando disponível)."""
    configurar_logging()
    root = TkinterDnD.Tk() if TkinterDnD is not None else Tk()
    app = PennaApp(root)
    _carregar_planilha_inicial(app)
    root.mainloop()


if __name__ == "__main__":
    main()
