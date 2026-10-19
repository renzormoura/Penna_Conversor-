"""Índices em memória derivados das tabelas SIA/SIGTAP, na vigência da competência.

Toda função devolve ``None`` (ou vazio) quando a base não existe: a regra
correspondente fica desativada, nunca gera falso positivo. As tabelas são lidas
sempre via ``penna.reference`` (ponto único de acesso e de cache).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Union

from penna import reference
from penna.config import get_defaults

Registros = List[Dict[str, str]]
CatalogoPA = Dict[str, Dict[str, str]]
Pares = Dict[str, Dict[str, str]]

# CEPs de garantia somados à S_CEP quando ela existe (município do estabelecimento original).
CEPS_GARANTIDOS = {"26700000"}

_ceps_cache: Optional[Set[str]] = None
_ceps_carregado = False


def cnes_padrao() -> str:
    """CNES executante do estabelecimento, lido do config no momento do uso."""
    return (get_defaults().get("Cnes_Executante") or "").zfill(7)


def carregar_base_ceps() -> Optional[Set[str]]:
    """Conjunto de CEPs da S_CEP (1,6 milhão de registros), lido uma vez; ``None`` se ausente."""
    global _ceps_cache, _ceps_carregado
    if _ceps_carregado:
        return _ceps_cache
    _ceps_carregado = True
    registros = reference.carregar_tabela("S_CEP")
    _ceps_cache = ({r.get("CEP", "") for r in registros if r.get("CEP")} | CEPS_GARANTIDOS) if registros else None
    return _ceps_cache


def carregar_catalogo_procedimentos(
    competencia: str = "", sigtap_competencia: Optional[str] = None
) -> Optional[CatalogoPA]:
    """S_PA indexada por código, na versão vigente na competência da planilha.

    Usa a competência mais alta ``<= competencia`` (nunca uma futura); sem
    competência, a mais recente da tabela. ``None`` desativa as regras
    (tabela ausente ou sem versão vigente para o mês).
    """
    registros = reference.carregar_tabela("S_PA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    if competencia:
        registros = reference.filtrar_por_competencia(registros, "PA_CMP", competencia)
    else:
        mais_recente = max((r.get("PA_CMP", "") for r in registros), default="")
        registros = [r for r in registros if r.get("PA_CMP", "") == mais_recente]
    catalogo = {r["PA_ID"]: r for r in registros if r.get("PA_ID")}
    return catalogo or None


def pares_secundarios(competencia: str, sigtap_competencia: Optional[str] = None) -> Optional[Pares]:
    """S_PAPA da competência: ``{principal: {secundário: qtmax}}``; ``None`` se ausente."""
    registros = reference.carregar_tabela("S_PAPA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    pares: Pares = {}
    for r in reference.filtrar_por_competencia(registros, "PAPA_CMP", competencia):
        principal = (r.get("PAPA_PRINC") or "").strip()
        secundario = (r.get("PAPA_SECUN") or "").strip()
        if principal and secundario:
            pares.setdefault(principal, {})[secundario] = (r.get("PAPA_QTMAX") or "").strip()
    return pares


def habilitacoes_exigidas(competencia: str, sigtap_competencia: Optional[str] = None) -> Optional[Dict[str, set]]:
    """S_PAHA da competência: ``{procedimento: {habilitações}}``; ``None`` se ausente."""
    registros = reference.carregar_tabela("S_PAHA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    exigidas: Dict[str, set] = {}
    for r in reference.filtrar_por_competencia(registros, "PAHA_CMP", competencia):
        proc = (r.get("PAHA_PA") or "").strip()
        ha = (r.get("PAHA_HA") or "").strip()
        if proc and ha:
            exigidas.setdefault(proc, set()).add(ha)
    return exigidas


def cids_validos_de(registros: Optional[Registros], competencia: str) -> Optional[Set[str]]:
    """Códigos de CID vigentes na competência; ``None`` sem registros."""
    if not registros:
        return None
    vigentes = reference.filtrar_por_faixa(registros, "CMP_INI", "CMP_FIM", competencia)
    return {(r.get("CD_COD") or "").strip().upper() for r in vigentes if r.get("CD_COD")}


def indice_restricoes_sexo(registros: Optional[Registros]) -> Optional[Dict[str, str]]:
    """``{CD_COD: RESTRSEXO}`` montado uma vez por validação (a primeira ocorrência vence)."""
    if not registros:
        return None
    indice: Dict[str, str] = {}
    for r in registros:
        cod = (r.get("CD_COD") or "").strip().upper()
        if cod and cod not in indice:
            indice[cod] = (r.get("RESTRSEXO") or "").strip()
    return indice


def restricao_sexo_cid(
    cod: str,
    registros: Optional[Union[Registros, Dict[str, str]]] = None,
    sigtap_competencia: Optional[str] = None,
) -> Optional[str]:
    """``RESTRSEXO`` do CID (1 = só masculino, 2 = só feminino).

    ``registros`` aceita a lista de registros ou o índice pré-construído
    (lookup O(1)); sem nada, lê a S_CID.
    """
    if registros is None:
        registros = reference.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    if isinstance(registros, dict):
        return (registros[cod] or "").strip() if cod in registros else None
    for r in registros:
        if (r.get("CD_COD") or "").strip().upper() == cod:
            return (r.get("RESTRSEXO") or "").strip()
    return None


def regras_condicionadas(competencia: str, sigtap_competencia: Optional[str] = None) -> Dict[str, set]:
    """S_PAREGR da competência: ``{procedimento: {regras}}`` (vazio se ausente)."""
    registros = reference.carregar_tabela("S_PAREGR", sigtap_competencia=sigtap_competencia)
    if not registros:
        return {}
    regras: Dict[str, set] = {}
    for r in reference.filtrar_por_competencia(registros, "REG_CMP", competencia):
        proc = (r.get("REG_PA") or "").strip()
        regra = (r.get("REG_REGRA") or "").strip()
        if proc and regra:
            regras.setdefault(proc, set()).add(regra)
    return regras
