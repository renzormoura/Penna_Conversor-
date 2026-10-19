"""Datas do layout: tudo é normalizado para ``AAAAMMDD``."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .text import digits, text

DATA_VAZIA = "00000000"

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$")
_DIA_MES_ANO = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$")
_SECULOS_AAAAMMDD = ("19", "20")
_SECULOS_DDMMAAAA = ("18", "19", "20", "21")


def is_real_date(aaaammdd: str) -> bool:
    """``True`` quando ``aaaammdd`` é uma data que existe no calendário."""
    if len(aaaammdd) != 8 or not aaaammdd.isdigit():
        return False
    try:
        date(int(aaaammdd[:4]), int(aaaammdd[4:6]), int(aaaammdd[6:8]))
    except ValueError:
        return False
    return True


def _checked(aaaammdd: str) -> str:
    return aaaammdd if is_real_date(aaaammdd) else ""


def normalize_date(value: Any) -> str:
    """Normaliza ``value`` para ``AAAAMMDD``; vazio se ausente ou inexistente.

    Fonte única para gerador, validador e leitura da planilha. Aceita:

    - ``date``/``datetime`` nativos;
    - ISO, com ou sem hora (``2026-06-15``, ``2026-06-15 00:00:00``, ``...T10:30``);
    - ``DD/MM/AAAA`` (separadores ``/``, ``-`` ou ``.``);
    - 8 dígitos em ``AAAAMMDD`` (preferido) ou ``DDMMAAAA``;
    - ``AAAAMM`` (6 dígitos), assumindo dia 01.
    """
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m%d")
    raw_text = text(value)

    if m := _ISO.match(raw_text):
        return _checked(f"{m[1]}{int(m[2]):02d}{int(m[3]):02d}")
    if m := _DIA_MES_ANO.match(raw_text):
        return _checked(f"{m[3]}{int(m[2]):02d}{int(m[1]):02d}")

    raw = digits(raw_text)
    if len(raw) == 8:
        if raw[:2] in _SECULOS_AAAAMMDD and is_real_date(raw):
            return raw
        ddmmaaaa = raw[4:] + raw[2:4] + raw[:2]
        if ddmmaaaa[:2] in _SECULOS_DDMMAAAA and is_real_date(ddmmaaaa):
            return ddmmaaaa
        return ""
    if len(raw) == 6 and raw[:2] in _SECULOS_AAAAMMDD and 1 <= int(raw[4:]) <= 12:
        return raw + "01"
    return ""


def date_to_txt(value: Any) -> str:
    """Data para um campo ``AAAAMMDD`` do TXT; ``00000000`` se vazia ou inválida.

    Dado inválido é barrado antes pelo validador; este é só o último recurso.
    """
    return normalize_date(value) or DATA_VAZIA


def birth_date_to_txt(value: Any) -> str:
    """Data de nascimento para ``AAAAMMDD``.

    A planilha costuma gravar ``DDMMAAAA`` (``24011958``). Com 8 dígitos, se os
    4 últimos formam um ano plausível e dia/mês são válidos, converte; do
    contrário mantém os dígitos para o validador acusar. Demais formatos seguem
    :func:`date_to_txt`.
    """
    raw = digits(value)
    if len(raw) != 8:
        return date_to_txt(value)
    dia, mes, ano = raw[:2], raw[2:4], raw[4:]
    if ano[:2] in _SECULOS_DDMMAAAA and 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
        return ano + mes + dia
    return raw
