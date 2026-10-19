"""Primitivas de texto: conversão, dígitos, caixa e alinhamento de campos fixos.

Funções puras e totais: nunca lançam exceção (valor inválido vira ``""`` ou o
padrão pedido) e não têm efeito colateral.
"""
from __future__ import annotations

import math
import re
from typing import Any

_NULOS_TEXTUAIS = frozenset({"nan", "None", "NaT"})


def text(value: Any) -> str:
    """Converte qualquer valor para ``str`` limpa (sem None, NaN ou espaços nas pontas)."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    s = str(value).strip()
    # pandas stringifica NaN/None/NaT como texto
    return "" if s in _NULOS_TEXTUAIS else s


def digits(value: Any) -> str:
    """Somente os caracteres numéricos de ``value``."""
    return re.sub(r"\D", "", text(value))


def text_upper(value: Any) -> str:
    """Maiúsculas apenas para ASCII; acentos são preservados.

    Comportamento do programa antigo, confirmado no arquivo real APCEO26P.JUN
    (``JOãO`` continua com o ``ã`` minúsculo).
    """
    return "".join(ch.upper() if ch.isascii() else ch for ch in text(value))


def pad_right(value: Any, width: int, fill: str = " ") -> str:
    """Alinha à esquerda, trunca ou completa com ``fill`` até ``width`` caracteres."""
    return text(value)[:width].ljust(width, fill)


def pad_left(value: Any, width: int, fill: str = "0") -> str:
    """Alinha à direita, trunca ou completa com ``fill`` até ``width`` caracteres."""
    return text(value)[:width].rjust(width, fill)
