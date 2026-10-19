"""Dados de referência de uma validação, carregados uma única vez por execução."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set

from penna import reference

from . import lookups


@dataclass
class ContextoValidacao:
    """Bases consultadas pelas regras. ``None`` (ou vazio) = base ausente: regra desativada."""

    base_ceps: Optional[Set[str]] = None
    catalogo_pa: Optional[lookups.CatalogoPA] = None
    pares_secundarios: Optional[lookups.Pares] = None
    habilitacoes_exigidas: Optional[Dict[str, set]] = None
    habilitacoes_cnes: Optional[Set[str]] = None
    cids_validos: Optional[Set[str]] = None
    cids_registros: Optional[lookups.Registros] = None
    cids_restricoes: Optional[Dict[str, str]] = None
    regras_condicionadas: Dict[str, set] = field(default_factory=dict)
    historico_apacs: Optional[Set[str]] = None


def _historico(pasta_remessas: Optional[Path]) -> Set[str]:
    from penna.remittance import apacs_exportadas  # lazy: remittance depende do layout

    return apacs_exportadas(pasta_remessas)


def montar_contexto(
    competencia: str,
    *,
    usar_sigtap: bool = True,
    usar_remessa: bool = True,
    pasta_remessas: Optional[Path] = None,
    sigtap_competencia: Optional[str] = None,
    **injetadas,
) -> ContextoValidacao:
    """Carrega as bases da competência; ``injetadas`` (``None`` = carregar) vence a leitura.

    Os testes injetam bases (inclusive vazias, para desativar uma regra); sem
    elas, as tabelas SIA são lidas uma única vez (``C:/APAC`` ou ``dados/bases_sia``).
    ``usar_sigtap=False`` desativa de uma vez as regras S_PAPA, S_PAHA, S_CID e
    S_PAREGR (mantendo idade e CEP).
    """
    ctx = ContextoValidacao(**{k: v for k, v in injetadas.items() if v is not None})
    regras_injetadas = injetadas.get("regras_condicionadas") is not None
    if ctx.base_ceps is None:
        ctx.base_ceps = lookups.carregar_base_ceps()
    if ctx.catalogo_pa is None:
        ctx.catalogo_pa = lookups.carregar_catalogo_procedimentos(competencia, sigtap_competencia)

    if usar_sigtap and competencia:
        if ctx.pares_secundarios is None:
            ctx.pares_secundarios = lookups.pares_secundarios(competencia, sigtap_competencia)
        if ctx.habilitacoes_exigidas is None:
            ctx.habilitacoes_exigidas = lookups.habilitacoes_exigidas(competencia, sigtap_competencia)
        if ctx.habilitacoes_cnes is None:
            ctx.habilitacoes_cnes = reference.carregar_habilitacoes_cnes(lookups.cnes_padrao(), competencia)
        if ctx.cids_registros is None:
            # Uma única carga do S_CID alimenta existência E restrição de sexo.
            ctx.cids_registros = reference.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
        if ctx.cids_validos is None:
            ctx.cids_validos = lookups.cids_validos_de(ctx.cids_registros, competencia)
        if not regras_injetadas:
            ctx.regras_condicionadas = lookups.regras_condicionadas(competencia, sigtap_competencia)

    if ctx.historico_apacs is None and usar_remessa:
        ctx.historico_apacs = _historico(pasta_remessas)
    # Com cids_validos definido (injetado ou derivado), a restrição de sexo também
    # precisa dos registros: carrega uma vez aqui, nunca dentro do loop de linhas.
    if ctx.cids_registros is None and ctx.cids_validos is not None:
        ctx.cids_registros = reference.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
    if ctx.cids_restricoes is None:
        ctx.cids_restricoes = lookups.indice_restricoes_sexo(ctx.cids_registros)
    return ctx
