"""Nome seguro dos arquivos PDF das fichas."""
from __future__ import annotations

import re
from typing import Any, Optional, Set

from .text import valor_texto

# ---------------------------------------------------------------------------
# Nomes de arquivo
# ---------------------------------------------------------------------------

_RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
               *(f"LPT{i}" for i in range(1, 10))}


def _seguro(texto: str) -> str:
    texto = re.sub(r'[\\/:*?"<>|]', " ", texto)
    return re.sub(r"\s+", " ", texto).strip(" .")


def nome_arquivo_ficha(row: Any, indice: int, usados: Optional[Set[str]] = None) -> str:
    """Nome seguro ``NomePaciente_NumeroApac.pdf`` (com desempate)."""
    valores = dict(row) if row is not None else {}
    nome = _seguro(valor_texto(valores.get("Nome_Paciente")))
    apac = re.sub(r"\D", "", valor_texto(valores.get("Numero_Apac")))
    base = "_".join(parte for parte in (nome, apac) if parte)
    base = base[:80].strip(" ._")
    if not base or base.upper() in _RESERVADOS:
        base = base if base and base.upper() not in _RESERVADOS else f"ficha_{indice:03d}"
    nome_final = f"{base}.pdf"
    if usados is not None:
        tentativa = 2
        while nome_final.lower() in usados:
            nome_final = f"{base}_{tentativa}.pdf"
            tentativa += 1
        usados.add(nome_final.lower())
    return nome_final
