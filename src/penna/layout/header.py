"""Cabeçalho ``01#APAC`` (134 caracteres) e seu checksum."""
from __future__ import annotations

import re
from datetime import date
from typing import List

from penna.config import get_header, get_versao
from penna.core import digits, pad_right, text_upper

from .constants import COMPETENCIA_INDEFINIDA, HEADER_DESTINO_WIDTH, HEADER_ORGAO_WIDTH, HEADER_VERSAO_WIDTH


def header_competence(linhas: List[str]) -> str:
    """Competência do cabeçalho: a do primeiro bloco 14 que traz um mês real."""
    for linha in linhas:
        if linha.startswith("14"):
            competencia = linha[2:8]
            if competencia and competencia != COMPETENCIA_INDEFINIDA:
                return competencia
    return COMPETENCIA_INDEFINIDA


def compute_checksum(linhas: List[str]) -> str:
    """Checksum do cabeçalho (validado no arquivo real: ``1155``).

    ``(soma dos nºs de APAC + soma dos procedimentos + soma das quantidades) mod 1111 + 1111``.
    """
    total = 0
    for linha in linhas:
        tipo = linha[:2]
        if tipo == "14":
            total += int(linha[8:21])
        elif tipo == "13":
            total += int(linha[21:31])
            total += int(re.sub(r"\D", "", linha[37:44]) or "0")
    return str(total % 1111 + 1111)


def generation_date() -> str:
    """Data de geração (``AAAAMMDD``) gravada no cabeçalho; isolada para os testes."""
    return date.today().strftime("%Y%m%d")


def build_header(linhas: List[str]) -> str:
    """Cabeçalho ``01#APAC`` das linhas do arquivo, idêntico ao do programa original.

    Campos: competência, nº de APACs (6), checksum (4), órgão (36), CGC (14),
    destino (40), indicador M/E, data de geração e versão (12, resolvida por mês).
    O config é relido a cada geração para refletir mudanças em execução.
    """
    h = get_header()
    competencia = header_competence(linhas)
    qtde_apacs = sum(1 for linha in linhas if linha.startswith("14"))
    return (
        "01#APAC"
        + competencia
        + str(qtde_apacs).rjust(6, "0")
        + compute_checksum(linhas)
        + pad_right(text_upper(h["orgao_responsavel"]), HEADER_ORGAO_WIDTH)
        + digits(h["cgc"]).rjust(14, "0")
        + pad_right(text_upper(h["destino"]), HEADER_DESTINO_WIDTH)
        + h["destino_indicador"][:1]
        + generation_date()
        + pad_right(get_versao(competencia), HEADER_VERSAO_WIDTH)
    )
