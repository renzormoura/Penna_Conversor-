"""Núcleo puro do domínio: texto, datas, identificadores e acesso a linhas.

Sem I/O, sem estado global e sem dependência de outros pacotes de ``penna``.
"""
from .competence import (
    CAMPOS_COMPETENCIA,
    CAMPOS_DATA_COMPETENCIA,
    normalize_competence,
    resolve_competence,
)
from .dates import DATA_VAZIA, birth_date_to_txt, date_to_txt, is_real_date, normalize_date
from .identifiers import format_cpf, normalize_cns, normalize_code, normalize_cpf
from .rows import resolve_block_value, resolve_row_value
from .text import digits, pad_left, pad_right, text, text_upper

__all__ = [
    "CAMPOS_COMPETENCIA",
    "CAMPOS_DATA_COMPETENCIA",
    "DATA_VAZIA",
    "birth_date_to_txt",
    "date_to_txt",
    "digits",
    "format_cpf",
    "is_real_date",
    "normalize_cns",
    "normalize_code",
    "normalize_competence",
    "normalize_cpf",
    "normalize_date",
    "pad_left",
    "pad_right",
    "resolve_block_value",
    "resolve_competence",
    "resolve_row_value",
    "text",
    "text_upper",
]
