"""Competência (``AAAAMM``) de um formulário APAC."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict

from .rows import resolve_row_value
from .text import digits

CAMPOS_COMPETENCIA = ("Competencia", "Competência", "AP_CMP")

# Datas do próprio formulário, por ordem de preferência, usadas quando a coluna
# de competência não existe ou está vazia: é o mês de quem preencheu a APAC.
CAMPOS_DATA_COMPETENCIA = (
    "Data_Autorizacao",
    "Data_Solicitacao",
    "Data_Alta_Obito",
    "Fim_Validade",
    "Inicio_Validade",
)


def _ano_mes(ano: str, mes: str) -> str:
    """``('2026', '06')`` -> ``'202606'``; fora do padrão -> ``''``."""
    if (
        len(ano) == 4
        and ano.isdigit()
        and ano[:2] in ("19", "20")
        and mes.isdigit()
        and 1 <= int(mes) <= 12
    ):
        return ano + mes
    return ""


def normalize_competence(value: Any) -> str:
    """Competência ``AAAAMM`` a partir do formato real da célula.

    Aceita ``AAAAMM``, ``AAAAMMDD`` (inclusive ``datetime``), ``DDMMAAAA``,
    ``DD/MM/AAAA`` e ``MM/AAAA``. Vazio quando ano e mês não podem ser
    identificados, em vez de devolver dígitos que não são a competência.
    """
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m")
    raw = digits(value)
    if len(raw) >= 8:
        return _ano_mes(raw[:4], raw[4:6]) or _ano_mes(raw[4:8], raw[2:4])
    if len(raw) == 6:
        return _ano_mes(raw[:4], raw[4:6]) or _ano_mes(raw[2:6], raw[:2])
    return ""


def resolve_competence(row: Dict[str, Any]) -> str:
    """Competência do formulário, sem nunca inventar uma.

    1. coluna de competência, em qualquer formato reconhecível;
    2. senão, o mês das datas do formulário (autorização, solicitação, alta,
       validade);
    3. vazio quando nada identifica o mês.
    """
    comp = normalize_competence(resolve_row_value(row, *CAMPOS_COMPETENCIA))
    if comp:
        return comp
    for campo in CAMPOS_DATA_COMPETENCIA:
        comp = normalize_competence(resolve_row_value(row, campo))
        if comp:
            return comp
    return ""
