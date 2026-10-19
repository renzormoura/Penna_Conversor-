"""Layouts de largura fixa dos TXT do SIGTAP e conversões para o esquema DBF.

As posições vêm do arquivo ``<tabela>_layout.txt`` do próprio ZIP quando
presente (``Coluna,Tamanho,Inicio,Fim,Tipo``); senão valem as padrão abaixo.
"""
from __future__ import annotations

import re
import zipfile
from typing import Dict, List, Tuple

Layout = Dict[str, Tuple[int, int]]  # coluna -> (inicio0, fim0) para fatiar a linha

LAYOUT_PADRAO: Dict[str, Layout] = {
    "tb_procedimento": {
        "CO_PROCEDIMENTO": (0, 10), "NO_PROCEDIMENTO": (10, 260),
        "TP_SEXO": (261, 262), "QT_MAXIMA_EXECUCAO": (262, 266),
        "VL_IDADE_MINIMA": (274, 278), "VL_IDADE_MAXIMA": (278, 282),
        "DT_COMPETENCIA": (330, 336),
    },
    "tb_cid": {"CO_CID": (0, 4), "TP_SEXO": (105, 106)},
    "rl_procedimento_compativel": {
        "CO_PROCEDIMENTO_PRINCIPAL": (0, 10), "CO_PROCEDIMENTO_COMPATIVEL": (12, 22),
        "QT_PERMITIDA": (25, 29), "DT_COMPETENCIA": (29, 35),
    },
    "rl_procedimento_habilitacao": {
        "CO_PROCEDIMENTO": (0, 10), "CO_HABILITACAO": (10, 14), "DT_COMPETENCIA": (18, 24),
    },
    "rl_procedimento_regra_cond": {"CO_PROCEDIMENTO": (0, 10), "CO_REGRA_CONDICIONADA": (10, 14)},
}


def ler_txt_zip(zf: zipfile.ZipFile, nome: str, encoding: str = "cp1252") -> List[str]:
    """Linhas de um TXT dentro do ZIP (``[]`` se ausente ou ilegível)."""
    try:
        with zf.open(nome) as f:
            return f.read().decode(encoding, errors="replace").splitlines()
    except (KeyError, OSError, zipfile.BadZipFile):
        return []


def ler_layout(zf: zipfile.ZipFile, tabela: str) -> Layout:
    """Layout da tabela: ``<tabela>_layout.txt`` do ZIP sobre o padrão embutido."""
    layout: Layout = dict(LAYOUT_PADRAO[tabela])
    alvo = f"{tabela}_layout.txt".lower()
    for nome in zf.namelist():
        if nome.lower().rsplit("/", 1)[-1] == alvo:
            for linha in ler_txt_zip(zf, nome):
                partes = [p.strip() for p in linha.split(",")]
                if len(partes) >= 4 and partes[2].isdigit() and partes[3].isdigit():
                    layout[partes[0].upper()] = (int(partes[2]) - 1, int(partes[3]))
            break
    return layout


def ler_tabela(zf: zipfile.ZipFile, tabela: str) -> Tuple[List[str], Layout]:
    """``(linhas, layout)`` de ``<tabela>.txt`` dentro do ZIP."""
    return ler_txt_zip(zf, f"{tabela}.txt"), ler_layout(zf, tabela)


def campo(linha: str, layout: Layout, coluna: str) -> str:
    ini, fim = layout[coluna]
    return linha[ini:fim].strip()


# --- Conversões SIGTAP -> esquema das tabelas DBF ----------------------------

def cod9(valor: str) -> str:
    """Código de procedimento sem DV: ``0905010035`` -> ``090501003``."""
    digitos = re.sub(r"\D", "", valor)
    return digitos[:9] if len(digitos) >= 10 else digitos


def idade_em_anos(meses: str) -> str:
    """Idade do SIGTAP (meses; vazio/9999 = sem limite) -> anos do DBF (``999``)."""
    if not meses.isdigit() or int(meses) >= 9999:
        return "999"
    return str(int(meses) // 12)


def sexo_procedimento(valor: str) -> str:
    """``TP_SEXO`` do procedimento: M/F/I(gnorado) -> M/F/A (como no S_PA)."""
    valor = valor.upper()
    return valor if valor in ("M", "F") else "A"


def sexo_cid(valor: str) -> str:
    """``TP_SEXO`` do CID: M/F/I(gnorado) -> 1/2/5 (como o RESTRSEXO do S_CID)."""
    return {"M": "1", "F": "2"}.get(valor.upper(), "5")
