"""TXT do SIGTAP -> registros no MESMO esquema das tabelas DBF do APAC-MAG.

Contrato (o que o validador lê das tabelas DBF):

- procedimentos com 9 dígitos, sem o DV (o ZIP traz 10 com DV);
- S_PA: ``PA_IDADEMN``/``PA_IDADEMX`` em ANOS (999 = sem limite; o SIGTAP traz
  meses, 9999 = sem limite), ``PA_SEXO`` M/F/A, ``PA_QTDMAX``, ``PA_SECOBRI``, ``PA_DC``;
- S_CID: ``RESTRSEXO`` 1 (só masculino), 2 (só feminino) ou 5 (sem restrição),
  incluindo as categorias de 3 caracteres (o SIGTAP só lista subcategorias de 4).

ZIP -> DBF:  rl_procedimento_regra_cond -> S_PAREGR, rl_procedimento_compativel
-> S_PAPA, rl_procedimento_habilitacao -> S_PAHA, tb_procedimento -> S_PA,
tb_cid -> S_CID.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .layouts import (
    LAYOUT_PADRAO,
    Layout,
    campo,
    cod9,
    idade_em_anos,
    sexo_cid,
    sexo_procedimento,
)

Registros = List[Dict[str, str]]


def parsear_regras_condicionadas(linhas: List[str], competencia: str, layout: Optional[Layout] = None) -> Registros:
    """``rl_procedimento_regra_cond`` -> S_PAREGR (REG_PA, REG_REGRA, REG_CMP)."""
    lay = layout or LAYOUT_PADRAO["rl_procedimento_regra_cond"]
    return [
        {
            "REG_PA": cod9(campo(linha, lay, "CO_PROCEDIMENTO")),
            "REG_REGRA": campo(linha, lay, "CO_REGRA_CONDICIONADA"),
            "REG_CMP": competencia,
            "REG_CHKSM": "",
        }
        for linha in linhas
        if len(linha) >= 14
    ]


def parsear_pares_compativeis(linhas: List[str], competencia: str, layout: Optional[Layout] = None) -> Registros:
    """``rl_procedimento_compativel`` -> S_PAPA.

    Linha: principal(10) registro(2) compatível(10) registro(2)
    tp_compatibilidade(1) qt_permitida(4) competência(6). Aceita todos os
    tipos: o S_PAPA do APAC-MAG guarda todos os pares.
    """
    lay = layout or LAYOUT_PADRAO["rl_procedimento_compativel"]
    return [
        {
            "PAPA_PRINC": cod9(campo(linha, lay, "CO_PROCEDIMENTO_PRINCIPAL")),
            "PAPA_SECUN": cod9(campo(linha, lay, "CO_PROCEDIMENTO_COMPATIVEL")),
            "PAPA_QTMAX": campo(linha, lay, "QT_PERMITIDA"),
            "PAPA_CMP": campo(linha, lay, "DT_COMPETENCIA") or competencia,
        }
        for linha in linhas
        if len(linha) >= 35
    ]


def parsear_habilitacoes(linhas: List[str], competencia: str, layout: Optional[Layout] = None) -> Registros:
    """``rl_procedimento_habilitacao`` -> S_PAHA (PAHA_PA, PAHA_HA, PAHA_CMP)."""
    lay = layout or LAYOUT_PADRAO["rl_procedimento_habilitacao"]
    return [
        {
            "PAHA_PA": cod9(campo(linha, lay, "CO_PROCEDIMENTO")),
            "PAHA_HA": campo(linha, lay, "CO_HABILITACAO"),
            "PAHA_CMP": campo(linha, lay, "DT_COMPETENCIA") or competencia,
        }
        for linha in linhas
        if len(linha) >= 14
    ]


def parsear_procedimentos(linhas: List[str], competencia: str, layout: Optional[Layout] = None) -> Registros:
    """``tb_procedimento`` -> S_PA.

    ``PA_SECOBRI`` vem vazio: o SIGTAP não traz o indicador "secundário
    obrigatório", e vazio mantém essa regra desativada (nunca falso positivo).
    """
    lay = layout or LAYOUT_PADRAO["tb_procedimento"]
    minimo = max(fim for _, fim in lay.values())
    registros: Registros = []
    for linha in linhas:
        if len(linha) < minimo:
            continue
        codigo = re.sub(r"\D", "", campo(linha, lay, "CO_PROCEDIMENTO"))
        registros.append({
            "PA_ID": cod9(codigo),
            "PA_DV": codigo[9:10],
            "PA_DC": campo(linha, lay, "NO_PROCEDIMENTO"),
            "PA_SEXO": sexo_procedimento(campo(linha, lay, "TP_SEXO")),
            "PA_QTDMAX": campo(linha, lay, "QT_MAXIMA_EXECUCAO") or "9999",
            "PA_IDADEMN": idade_em_anos(campo(linha, lay, "VL_IDADE_MINIMA")),
            "PA_IDADEMX": idade_em_anos(campo(linha, lay, "VL_IDADE_MAXIMA")),
            "PA_SECOBRI": "",
            "PA_CMP": campo(linha, lay, "DT_COMPETENCIA") or competencia,
        })
    return registros


def parsear_cids(linhas: List[str], competencia: str, layout: Optional[Layout] = None) -> Registros:
    """``tb_cid`` -> S_CID (CD_COD, RESTRSEXO 1/2/5, CMP_INI, CMP_FIM).

    A categoria de 3 caracteres (A00) é sintetizada, sem restrição de sexo,
    para que CIDs de 3 caracteres da planilha não virem "não encontrado".
    """
    lay = layout or LAYOUT_PADRAO["tb_cid"]
    registros: Registros = []
    vistos = set()
    for linha in linhas:
        if len(linha) < 106:
            continue
        codigo = campo(linha, lay, "CO_CID").upper()
        if not codigo:
            continue
        registros.append({
            "CD_COD": codigo,
            "RESTRSEXO": sexo_cid(campo(linha, lay, "TP_SEXO")),
            "CMP_INI": "000000",
            "CMP_FIM": "999999",
        })
        vistos.add(codigo)
    for categoria in sorted({c[:3] for c in vistos if len(c) == 4} - vistos):
        registros.append({"CD_COD": categoria, "RESTRSEXO": "5", "CMP_INI": "000000", "CMP_FIM": "999999"})
    return registros
