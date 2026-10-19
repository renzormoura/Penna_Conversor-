"""Visão tipada de uma linha da planilha, calculada uma única vez por linha."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from penna.core import (
    birth_date_to_txt,
    digits,
    is_real_date,
    resolve_competence,
    resolve_row_value,
    text,
    text_upper,
)
from penna.layout.constants import MAX_PROCEDIMENTOS_SECUNDARIOS

from .model import Emissor

Row = Dict[str, Any]
Item = Tuple[str, str]  # (código do procedimento com 10 dígitos, quantidade)


def valor(row: Row, *campos: str) -> str:
    """Primeiro valor não vazio entre as colunas candidatas (nome tolerante)."""
    return resolve_row_value(row, *campos)


def procedimentos_da_linha(row: Row) -> List[Item]:
    """Principal e secundários preenchidos, como ``(código10, quantidade)``."""
    itens: List[Item] = []
    principal = digits(valor(row, "Cod_Procedimento"))
    if principal:
        itens.append((principal.rjust(10, "0"), digits(valor(row, "Quantidade")) or "0"))
    for i in range(1, MAX_PROCEDIMENTOS_SECUNDARIOS + 1):
        codigo = digits(valor(row, f"Sec{i}_Cod_Procedimento"))
        if codigo:
            itens.append((codigo.rjust(10, "0"), digits(valor(row, f"Sec{i}_Quantidade")) or "0"))
    return itens


@dataclass(frozen=True)
class LinhaApac:
    """Uma APAC da planilha, com os valores que mais de uma regra consulta."""

    row: Row
    cmpt: str            # competência AAAAMM ("" se não identificável)
    num_apac: str        # só dígitos
    texto_apac: str      # Numero_Apac como digitado
    nascimento: str      # AAAAMMDD (pode ser inválido: veja nascimento_valido)
    nascimento_valido: bool
    sexo: str            # primeira letra maiúscula ("" se ausente)
    itens: List[Item]

    @classmethod
    def de(cls, row: Row, cmpt: str | None = None) -> "LinhaApac":
        nascimento = birth_date_to_txt(valor(row, "Data_Nascimento"))
        return cls(
            row=row,
            cmpt=resolve_competence(row) if cmpt is None else cmpt,
            num_apac=digits(valor(row, "Numero_Apac")),
            texto_apac=text(valor(row, "Numero_Apac")).strip(),
            nascimento=nascimento,
            nascimento_valido=is_real_date(nascimento),
            sexo=text_upper(valor(row, "Sexo"))[:1],
            itens=procedimentos_da_linha(row),
        )

    @property
    def numero_valido(self) -> bool:
        return bool(self.num_apac) and set(self.num_apac) != {"0"}

    def emissor(self, coletor) -> Emissor:
        return Emissor(coletor, self.cmpt, self.num_apac)

    def valor(self, *campos: str) -> str:
        return valor(self.row, *campos)
