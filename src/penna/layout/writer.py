"""Montagem e gravação do arquivo TXT fiscal."""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from penna.config import verificar_configuracao

from .blocks import build_patient_lines
from .constants import ACTION_CONTENT_WIDTH, ACTION_WIDTH
from .header import build_header
from .workbook import apacs_sem_numero

ENCODING = "cp1252"


def render_txt(linhas: List[str]) -> str:
    """Texto do arquivo a partir das linhas de APACs (sem cabeçalho).

    Formato do programa original: toda linha termina em CRLF, a última ``13``
    fica sem padding (44) e o arquivo termina com CRLF duplo. Sem linhas, só o
    CRLF final.
    """
    linhas = [linha for linha in linhas if linha.strip()]
    if linhas:
        if linhas[-1].startswith("13") and len(linhas[-1]) == ACTION_WIDTH:
            linhas[-1] = linhas[-1][:ACTION_CONTENT_WIDTH]
        linhas.insert(0, build_header(linhas))
    return "".join(linha + "\r\n" for linha in linhas) + "\r\n"


def exportar_txt(df: pd.DataFrame, caminho_saida: Path) -> pd.DataFrame:
    """Gera o TXT fiscal em CP1252 no padrão APAC-MAG.

    Levanta :class:`~penna.config.ConfigInvalidaError` se o ``penna_config.json``
    estiver ausente, corrompido ou com valores de fábrica. A codificação é
    estrita: o gate do validador já barra o que não codifica, e se algo escapar
    a gravação falha alto em vez de trocar o dado por ``?``.
    """
    verificar_configuracao()
    apacs_sem_numero(df)  # normaliza Numero_Apac para texto
    linhas: List[str] = []
    for _, row in df.iterrows():
        linhas.extend(build_patient_lines(row.to_dict()))
    caminho_saida.write_bytes(render_txt(linhas).encode(ENCODING))
    return df
