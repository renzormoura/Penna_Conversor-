"""Acesso tolerante às colunas de uma linha da planilha (``dict`` por linha)."""
from __future__ import annotations

import re
from typing import Any, Dict

from .text import text

_VAZIOS = frozenset({"", "nan", "none"})

# Memo por processo: as mesmas dezenas de chaves de coluna são normalizadas
# centenas de milhares de vezes durante uma validação.
_CHAVES_NORMALIZADAS: Dict[str, str] = {}


def _normalize_key(key: str) -> str:
    """Nome de coluna comparável: minúsculo, sem espaços, hífens ou barras."""
    hit = _CHAVES_NORMALIZADAS.get(key)
    if hit is not None:
        return hit
    s = key.strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    s = re.sub(r"_+", "_", s)
    _CHAVES_NORMALIZADAS[key] = s
    return s


def resolve_row_value(row: Dict[str, Any], *candidates: str) -> str:
    """Primeiro valor não vazio entre as colunas candidatas de ``row``.

    Tenta o nome exato (caminho rápido) e, se preciso, compara nomes
    normalizados, tolerando variações de digitação nos cabeçalhos da planilha.
    ``nan``, ``None`` e ``""`` contam como vazio.
    """
    for candidate in candidates:
        v = text(row.get(candidate, ""))
        if v.lower() not in _VAZIOS:
            return v
        norm = _normalize_key(candidate)
        for key, val in row.items():
            if _normalize_key(str(key)) == norm:
                v = text(val)
                if v.lower() not in _VAZIOS:
                    return v
    return ""


def resolve_block_value(row: Dict[str, Any], field_name: str, default: str = "") -> str:
    """:func:`resolve_row_value` de uma coluna, com valor padrão."""
    value = resolve_row_value(row, field_name)
    return value if value != "" else default
