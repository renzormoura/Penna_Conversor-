"""Leitura da planilha de entrada."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

import pandas as pd

from penna.config import get_defaults
from penna.core import resolve_competence

from .columns import COLUNAS_PLANILHA


def _sem_linhas_em_branco(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta linhas sem nenhum valor (só formatação no Excel).

    O índice original é mantido: ``apacs_sem_numero`` e os relatórios apontam a linha do Excel.
    """
    preenchida = (df.astype(str).apply(lambda coluna: coluna.str.strip()) != "").any(axis=1)
    return df[preenchida]


def carregar_planilha(caminho: Path) -> pd.DataFrame:
    """Lê o Excel e garante todas as colunas esperadas, sempre como texto."""
    df = pd.read_excel(caminho, dtype=str, engine="openpyxl", keep_default_na=False)
    for coluna in COLUNAS_PLANILHA:
        if coluna not in df.columns:
            df[coluna] = ""
    for coluna in get_defaults():
        if coluna in df.columns:
            df[coluna] = df[coluna].fillna("")
    return _sem_linhas_em_branco(df.fillna(""))


def competencia_da_planilha(df: Any) -> str:
    """Mês dos formulários: a primeira competência identificada nas linhas."""
    try:
        for _, serie in df.iterrows():
            competencia = resolve_competence(dict(serie))
            if competencia:
                return competencia
    except (AttributeError, TypeError, ValueError):
        pass  # df sem iterrows ou linhas ilegíveis: sem competência identificável
    return ""


def apacs_sem_numero(df: pd.DataFrame) -> List[int]:
    """Linhas (número da linha do Excel) sem ``Numero_Apac`` válido.

    O gerador não inventa números: a numeração vem sempre da coluna. Normaliza a
    coluna para texto (efeito colateral necessário); quem exibe o aviso é o chamador.
    """
    if "Numero_Apac" not in df.columns:
        df["Numero_Apac"] = ""
    df["Numero_Apac"] = df["Numero_Apac"].where(df["Numero_Apac"].notna(), "").astype(str)
    return [
        pos
        for pos, numero in zip(df.index + 2, df["Numero_Apac"])
        if not (d := re.sub(r"\D", "", numero)) or set(d) == {"0"}
    ]
