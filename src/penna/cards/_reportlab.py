"""Importação protegida do reportlab: sem ele o programa segue (só as fichas ficam indisponíveis)."""
from __future__ import annotations

try:  # pragma: no cover - degradação graciosa quando reportlab ausente
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFError, TTFont
    from reportlab.pdfgen import canvas

    REPORTLAB = True
except ImportError:  # pragma: no cover
    REPORTLAB = False
    TTFError = OSError  # type: ignore[assignment,misc]

__all__ = ["A4", "REPORTLAB", "HexColor", "TTFError", "TTFont", "black", "canvas", "pdfmetrics", "white"]
