"""Numeracao de APACs no formato oficial do sistema MAG.

O layout oficial (`apa_num`, 13 posicoes) define: 12 digitos de sequencia
+ 1 digito verificador (DV). Exemplo real do sistema: 3326700885662.

Quando a planilha nao traz `Numero_Apac` preenchido, este modulo gera a
numeracao automaticamente para que o TXT nao saia completado com zeros.
"""

from __future__ import annotations

import re
from typing import Iterable

SEQUENCE_DIGITS = 12
TOTAL_DIGITS = SEQUENCE_DIGITS + 1  # sequencia + DV
DV_MODULUS = 11
# Resto 10 vira 0 (DV tem apenas 1 digito).
# Validado contra a APAC real do sistema MAG: 3326700885662
# (sequencia 332670088566 % 11 = 2 = DV do arquivo real).

# Formato visual da sequencia no sistema antigo (APAC real 3326700885662):
# UU AAMM SSSSSS -> UF (2) + ano/mes da competencia (4) + sequencial (6).
# Assim os 6 primeiros digitos (usados nos blocos 06/13 como "numero parcial")
# ficam significativos, como no arquivo real: 3326700000000.
DEFAULT_UF = "33"  # RJ, usado quando a linha nao informa a UF
UF_DIGITS = 2
COMPETENCE_DIGITS = 4
SEQUENCE_TAIL_DIGITS = SEQUENCE_DIGITS - UF_DIGITS - COMPETENCE_DIGITS


def only_digits(value) -> str:
    return re.sub(r"\D", "", str(value if value is not None else ""))


def check_digit(sequence: str) -> str:
    """Digito verificador = resto do numero dividido por 11; resto 10 vira 0.
    Validado com 25 numeros reais do S_APAC.DBF do sistema MAG
    (3326700885046..3326600026937 e 3326700885662)."""
    digits = only_digits(sequence)[-SEQUENCE_DIGITS:].rjust(SEQUENCE_DIGITS, "0")
    return str(int(digits) % DV_MODULUS % 10)


def format_apac_number(sequence: str) -> str:
    """Completa a sequencia com o DV e devolve o numero de 13 digitos."""
    digits = only_digits(sequence)[-SEQUENCE_DIGITS:].rjust(SEQUENCE_DIGITS, "0")
    return digits + check_digit(digits)


def sequence_for_competence(competence: str, index: int, uf: str = DEFAULT_UF) -> str:
    """Sequencia de 12 digitos: UF + AAMM + sequencial de 6 digitos (1-based).
    Ex. (RJ, 2026-06, APAC 13): 332606000013."""
    digits = only_digits(competence)[:6].ljust(6, "0")
    uf_part = (only_digits(uf)[:UF_DIGITS] or DEFAULT_UF).rjust(UF_DIGITS, "0")
    aamm = digits[2:6]
    tail = str(index).rjust(SEQUENCE_TAIL_DIGITS, "0")
    return uf_part + aamm + tail


def _has_real_number(value) -> bool:
    """Considera numerado apenas se ha digitos e nao e tudo zeros
    (numero "0000000000000" na planilha conta como nao preenchido)."""
    digits = only_digits(value)
    return bool(digits) and set(digits) != {"0"}


def assign_missing_numbers(rows: Iterable[dict], column: str = "Numero_Apac",
                           competence_column: str = "Competencia",
                           fallback_competence: str = "",
                           uf_column: str = "Codigo_UF",
                           uf_resolver=None) -> int:
    """Preenche `column` in-place nas linhas sem numero, em ordem.

    A numeracao segue o padrao do sistema antigo: UF + AAMM + sequencial + DV,
    continua por competencia. Linhas ja numeradas sao preservadas.
    `uf_resolver(row)` permite deduzir a UF (ex.: pelo orgao emissor).
    Devolve a quantidade preenchida.
    """
    counters: dict[str, int] = {}
    filled = 0
    for row in rows:
        if not isinstance(row, dict) or column not in row:
            continue
        if _has_real_number(row.get(column, "")):
            continue
        competence = only_digits(row.get(competence_column, ""))[:6] or fallback_competence
        uf = ""
        if uf_resolver is not None:
            uf = only_digits(uf_resolver(row) or "")[:UF_DIGITS]
        if not uf:
            uf = only_digits(row.get(uf_column, "") or "")[:UF_DIGITS]
        counters[competence] = counters.get(competence, 0) + 1
        sequence = sequence_for_competence(competence, counters[competence], uf or DEFAULT_UF)
        row[column] = format_apac_number(sequence)
        filled += 1
    return filled
