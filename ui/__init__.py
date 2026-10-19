"""Pacote de interface gráfica do Penna.

Módulos:
    theme      — paleta de cores e constantes visuais
    components — widgets reutilizáveis (HeaderCanvas, DropZone, PainelErros, SigtapSelector, VersaoSelector)
    app        — lógica de orquestração (PennaApp)
"""
from .theme import *          # noqa: F401, F403
from .components import (     # noqa: F401
    HeaderCanvas,
    DropZone,
    PainelErros,
    SigtapSelector,
    VersaoSelector,
    normalizar_versao,
    LoadingOverlay,
)
from .app import PennaApp     # noqa: F401
