"""Normalização de identificadores numéricos (CPF, CNS, códigos)."""
from __future__ import annotations

from typing import Any

from .text import digits


def normalize_cpf(value: Any) -> str:
    """CPF com 11 dígitos sem pontuação; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(11) if raw else ""


def normalize_cns(value: Any) -> str:
    """CNS com 15 dígitos; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(15) if raw else ""


def normalize_code(value: Any, width: int) -> str:
    """Código numérico completado com zeros à esquerda até ``width``."""
    raw = digits(value)
    return raw.zfill(width) if raw else ""
