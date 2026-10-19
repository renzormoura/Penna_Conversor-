"""Seleção de registros por competência (vigência das tabelas SIA)."""
from __future__ import annotations

from typing import List, Optional

from .dbf import Registro


def _maior_valor(registros: List[Registro], campo: str, competencia: str) -> Optional[str]:
    maior: Optional[str] = None
    for r in registros:
        valor = (r.get(campo) or "").strip()
        if valor and valor <= competencia and (maior is None or valor > maior):
            maior = valor
    return maior


def filtrar_por_competencia(registros: List[Registro], campo: str, competencia: str) -> List[Registro]:
    """Registros cujo campo-competência é o mais alto ainda ``<= competencia``.

    Replica o BDSIA: cada competência regrava a tabela, e a regra da APAC é a
    da tabela vigente na competência dela (nunca de uma competência futura).
    """
    if not registros or not competencia:
        return []
    vigente = _maior_valor(registros, campo, competencia)
    if vigente is None:
        return []
    return [r for r in registros if (r.get(campo) or "").strip() == vigente]


def filtrar_por_faixa(
    registros: List[Registro], campo_ini: str, campo_fim: str, competencia: str
) -> List[Registro]:
    """Registros cuja faixa ``[ini, fim]`` cobre a competência (S_CID, S_DEPARA)."""
    if not registros or not competencia:
        return []
    return [
        r for r in registros
        if ((r.get(campo_ini) or "").strip() or "000000") <= competencia
        <= ((r.get(campo_fim) or "").strip() or "999999")
    ]
