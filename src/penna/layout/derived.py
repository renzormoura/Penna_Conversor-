"""Valores derivados da linha da planilha usados por mais de um bloco do TXT."""
from __future__ import annotations

import re
from typing import Any, Dict

from penna.config import get_defaults
from penna.core import digits, pad_left, resolve_block_value, resolve_competence, resolve_row_value, text

from .constants import COMPETENCIA_INDEFINIDA


def competence_from_row(row: Dict[str, Any]) -> str:
    """Competência ``AAAAMM`` do formulário, ou ``000000`` se nenhum mês é identificável.

    Usa a coluna de competência em qualquer formato reconhecível e, sem ela, as
    datas do formulário. O ``000000`` preserva a largura fixa do layout.
    """
    return resolve_competence(row) or COMPETENCIA_INDEFINIDA


def uf_from_row(row: Dict[str, Any], numero_apac: str = "") -> str:
    """Código da UF (2 dígitos): coluna própria, senão órgão emissor, senão nº da APAC."""
    valor = resolve_row_value(row, "Codigo_UF", "Código_UF", "UF", "AP_CODUF")
    if not valor:
        valor = re.sub(r"\D", "", resolve_row_value(row, "Cod_Orgao_Emiss"))[:2]
    if not valor:
        valor = re.sub(r"\D", "", numero_apac)[:2]
    return valor[-2:].zfill(2)


def ibge_code(row: Dict[str, Any]) -> str:
    """Código IBGE do município: 6 dígitos + espaço (sem DV), como no arquivo real.

    Sem valor na linha, usa o padrão do config; sem nenhum, 7 espaços.
    """
    d = digits(text(resolve_block_value(row, "Codigo_Municipio", resolve_block_value(row, "IBGE", ""))))
    if len(d) < 6:
        d = digits(get_defaults().get("Codigo_Municipio", ""))
    return d[:6] + " " if len(d) >= 6 else " " * 7


def numeric_field(value: Any, width: int) -> str:
    """Campo numérico: zeros à esquerda se há valor, brancos se não há.

    Texto não numérico (ex.: ``AMB``) é descartado, como no sistema original.
    """
    d = digits(value)
    return d.rjust(width, "0") if d else " " * width


def apac_number(row: Dict[str, Any]) -> str:
    """Número da APAC nos blocos 06 e 13: 13 dígitos completos (confirmado no arquivo real)."""
    return pad_left(resolve_block_value(row, "Numero_Apac", "0"), 13, "0")
