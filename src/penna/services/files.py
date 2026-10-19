"""Caminhos e arquivos da planilha: normalização do que o usuário solta ou cola.

Funções puras, sem Tk: a interface só repassa o texto recebido.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List
from urllib.parse import unquote

EXTENSOES_EXCEL = frozenset({".xlsx", ".xlsm", ".xls"})


def eh_planilha_excel(path: Path) -> bool:
    """``True`` se ``path`` existe e tem extensão de planilha Excel."""
    return path.exists() and path.suffix.lower() in EXTENSOES_EXCEL


def formatar_tamanho_bytes(tamanho: int) -> str:
    """Tamanho de arquivo legível (B, KB ou MB)."""
    if tamanho < 1024:
        return f"{tamanho} B"
    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.1f} KB"
    return f"{tamanho / (1024 * 1024):.1f} MB"


def _limpar(path: str) -> str:
    while path.startswith("{") and path.endswith("}"):
        path = path[1:-1].strip()
    if path.startswith("file://"):
        path = path[7:]
    path = unquote(path.strip().strip('"').strip("'"))
    # Barras normais viram invertidas (contrato Windows do conversor) ANTES da
    # checagem de UNC: assim ``\\//servidor/pasta`` também é reconhecido e
    # preservado como ``\\servidor\pasta``.
    path = path.replace("/", "\\")
    if path.startswith("\\\\"):
        path = "\\\\" + path[2:].replace("\\\\", "\\")
    else:
        path = path.replace("\\\\", "\\")
    return path.strip()


def parse_dropped_path(raw_value) -> str:
    """Caminho recebido de um evento de arrastar-e-soltar, normalizado.

    Trata listas, caminhos entre chaves ``{}``, ``file://``, UNC (``\\\\servidor``),
    aspas e barra invertida duplicada. Prefere o primeiro candidato que existe;
    se nenhum existir, devolve o primeiro mesmo assim.
    """
    if isinstance(raw_value, (list, tuple)):
        raw_value = " ".join(str(item) for item in raw_value)

    value = str(raw_value).strip().replace("\0", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if not value:
        return ""

    candidatos: List[str]
    if value.startswith("{") and value.endswith("}"):
        candidatos = [p.strip() for p in re.split(r"}\s*\{", value[1:-1].strip()) if p.strip()]
    elif "\n" in value:
        candidatos = [p.strip() for p in value.splitlines() if p.strip()]
    else:
        candidatos = [value]

    for candidato in candidatos:
        limpo = _limpar(candidato)
        if limpo and os.path.exists(limpo):
            return limpo
    return _limpar(candidatos[0]) if candidatos else ""
