"""Normalização de identificadores numéricos (CPF, CNS, códigos)."""
from __future__ import annotations

from typing import Any

from .text import digits, text


def normalize_cpf(value: Any) -> str:
    """CPF com 11 dígitos sem pontuação; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(11) if raw else ""


def format_cpf(value: Any) -> str:
    """``000.000.000-00``; completa com zeros à esquerda o CPF que o Excel gravou como número.

    Com 1 a 11 dígitos devolve o CPF formatado (``2937892744`` -> ``029.378.927-44``); sem
    dígitos ou com mais de 11 não é CPF e o texto original volta como está.
    """
    d = digits(value)
    if not d or len(d) > 11:
        return text(value)
    d = d.zfill(11)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def normalize_cns(value: Any) -> str:
    """CNS com 15 dígitos; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(15) if raw else ""


def normalize_code(value: Any, width: int) -> str:
    """Código numérico completado com zeros à esquerda até ``width``."""
    raw = digits(value)
    return raw.zfill(width) if raw else ""
