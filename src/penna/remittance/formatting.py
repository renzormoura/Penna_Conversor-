"""Formatação dos relatórios de remessa (mesmo visual dos relatórios do original)."""
from __future__ import annotations

from typing import Any

from penna.core import digits, text


def digitos(valor: Any, padrao: str = "") -> str:
    """Somente os dígitos de ``valor``; ``padrao`` se não houver nenhum."""
    return digits(valor) or padrao


def com_dv(codigo: str, quantidade: int) -> str:
    """``1234567890`` -> ``123456789-0``: separa o DV depois de ``quantidade`` dígitos."""
    codigo = digitos(codigo)
    return codigo if len(codigo) <= quantidade else f"{codigo[:quantidade]}-{codigo[quantidade:]}"


def data(valor: Any) -> str:
    """``dd/mm/aaaa`` a partir de DDMMAAAA (planilha) ou AAAAMMDD (layout)."""
    d = digitos(valor)
    if len(d) == 8:
        if 1 <= int(d[:2]) <= 31 and 1 <= int(d[2:4]) <= 12:
            return f"{d[:2]}/{d[2:4]}/{d[4:]}"   # DDMMAAAA
        if 1 <= int(d[4:6]) <= 12 and 1 <= int(d[6:8]) <= 31:
            return f"{d[6:8]}/{d[4:6]}/{d[:4]}"  # AAAAMMDD
    return text(valor)


def cpf(valor: Any) -> str:
    d = digitos(valor)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else text(valor)


def cep(valor: Any) -> str:
    d = digitos(valor).zfill(8)[:8]
    return f"{d[:5]}-{d[5:]}"


def cgc(valor: Any) -> str:
    d = digitos(valor).zfill(14)[:14]
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


SEXO = {"M": "MASCULINO", "F": "FEMININO", "I": "INDETERMINADO"}
RACA = {"01": "BRANCA", "02": "PRETA", "03": "PARDA", "04": "AMARELA", "05": "INDIGENA", "99": "SEM INFORMACAO"}
MOTIVO_SAIDA = {"11": "ALTA CURADO"}

# Descrições oficiais das regras condicionadas (impressas no R0201 do original)
DESCRICOES_REGRAS = {
    "0009": "PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS",
}
