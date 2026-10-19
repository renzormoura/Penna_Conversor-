"""Wrapper de retrocompatibilidade para apac_mag_gui.

A lógica da GUI foi movida para o pacote ui/:
    ui/theme.py      — paleta de cores e constantes visuais
    ui/components.py — HeaderCanvas, DropZone, PainelErros
    ui/app.py        — PennaApp (orquestração), main()

Este módulo re-exporta tudo que código externo (penna_app, PyInstaller .spec,
outros scripts) possa importar diretamente de apac_mag_gui, garantindo
compatibilidade sem alterações nesses chamadores.
"""
from __future__ import annotations

# Re-exporta o design system
from ui.theme import (  # noqa: F401
    COR_AZUL_PRINCIPAL,
    COR_AZUL_HOVER,
    COR_AZUL_ACTIVE,
    COR_AZUL_TINT,
    COR_AZUL_BORDA,
    COR_AZUL_DASH,
    COR_BRANCO,
    COR_FUNDO,
    COR_CARD,
    COR_BORDA,
    COR_TEXTO_TITULO,
    COR_TEXTO_CORPO,
    COR_TEXTO_MEDIO,
    COR_TEXTO_HINT,
    COR_SUCESSO,
    COR_SUCESSO_BG,
    COR_SUCESSO_BORDA,
    COR_ERRO,
    COR_ERRO_BG,
    # aliases retrocompat
    COR_HEADER_TOPO,
    COR_HEADER_BASE,
    COR_BORDA_CARD,
    COR_TEXTO_ESCURO,
    COR_ACENTO,
    COR_ACENTO_HOVER,
    # textos
    WINDOW_TITLE,
    DROP_HINT,
    APP_BRAND,
    APP_SUBTITLE,
    MSG_BLOQUEIO,
    MSG_AVISOS,
)

# Re-exporta os componentes
from ui.components import (  # noqa: F401
    HeaderCanvas,
    DropZone,
    PainelErros,
    carregar_icone_foto,
    desenhar_pena_vetorial,
)

# Re-exporta a lógica da aplicação
from ui.app import (  # noqa: F401
    PennaApp,
    ApacMagApp,
    formatar_tamanho_bytes,
    normalize_output_name,
    parse_dropped_path,
    convert_excel_to_txt,
    main,
)

# ---------------------------------------------------------------------------
# Ativa DPI awareness no Windows (mantido aqui para evitar duplicar em ui/app)
# ---------------------------------------------------------------------------
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

if __name__ == "__main__":
    main()
