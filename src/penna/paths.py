"""Localização de pastas e recursos, em um único lugar.

Cobre os dois modos de execução: código-fonte (pasta do repositório) e
executável PyInstaller (``sys._MEIPASS`` para recursos embutidos e pasta do
``.exe`` para arquivos editáveis pelo usuário).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "PennaConversor"


def is_frozen() -> bool:
    """``True`` quando rodando como executável PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Raiz dos recursos embutidos (ícones, ``dados/``, modelo de config)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def executable_dir() -> Path:
    """Pasta do ``.exe`` (frozen) ou raiz do projeto (código-fonte)."""
    return Path(sys.executable).resolve().parent if is_frozen() else project_root()


def user_data_dir() -> Path:
    r"""Pasta gravável do usuário (``%LOCALAPPDATA%\PennaConversor``)."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home()) / APP_DIRNAME


def data_dir() -> Path:
    """Pasta ``dados/`` embutida (bases SIA, modelo da ficha)."""
    return project_root() / "dados"


def reference_tables_dir() -> Path:
    """Bases SIA/SIGTAP versionadas junto ao programa."""
    return data_dir() / "bases_sia"
