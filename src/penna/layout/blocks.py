"""Blocos 06 (CID principal) e 13 (procedimentos) e a montagem das linhas de uma APAC."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from penna.core import pad_left, resolve_block_value, text_upper

from .body import build_body_block
from .constants import ACTION_WIDTH, MAX_PROCEDIMENTOS_SECUNDARIOS
from .derived import apac_number, competence_from_row

Row = Dict[str, Any]


def build_cid_block(row: Row) -> str:
    """Bloco 06: ``06`` + competência + nº da APAC (13) + CID.

    O sistema antigo grava o CID como digitado (``H40`` = 3 caracteres, sem padding).
    Vazio quando a linha não tem CID principal.
    """
    cid = re.sub(r"[^A-Z0-9]", "", text_upper(resolve_block_value(row, "Cid_Princ", "")))[:4]
    if not cid:
        return ""
    return "06" + competence_from_row(row) + apac_number(row) + cid


def build_action_block(row: Row, campo_codigo: str, campo_cbo: str, campo_quantidade: str) -> str:
    """Bloco 13: ``13`` + competência + nº da APAC (13) + procedimento (10) + CBO (6) + quantidade (7).

    Completado com espaços até 97 caracteres. O sistema antigo não exporta
    CNPJ, NF, CID, serviço, classificação, equipe nem terceiro.
    """
    codigo = pad_left(resolve_block_value(row, campo_codigo, ""), 10, "0")
    cbo = pad_left(resolve_block_value(row, campo_cbo, ""), 6, "0")
    quantidade = pad_left(resolve_block_value(row, campo_quantidade, ""), 7, "0")
    bloco = "13" + competence_from_row(row) + apac_number(row) + codigo + cbo + quantidade
    return bloco.ljust(ACTION_WIDTH)


def build_secondary_block(row: Row, index: int) -> str:
    """Bloco 13 do procedimento secundário ``SecN``; vazio se a linha não o informa."""
    campo_codigo = f"Sec{index}_Cod_Procedimento"
    if not resolve_block_value(row, campo_codigo, ""):
        return ""
    return build_action_block(row, campo_codigo, f"Sec{index}_Cbo", f"Sec{index}_Quantidade")


def build_patient_lines(row: Row) -> List[str]:
    """Linhas de uma APAC, em ordem: corpo (14), CID (06), principal (13) e secundários (13)."""
    linhas = [
        build_body_block(row),
        build_cid_block(row),
        build_action_block(row, "Cod_Procedimento", "Cbo", "Quantidade"),
        *(build_secondary_block(row, i) for i in range(1, MAX_PROCEDIMENTOS_SECUNDARIOS + 1)),
    ]
    return [linha for linha in linhas if linha.strip()]
