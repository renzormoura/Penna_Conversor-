"""Regra do CID principal: existência na S_CID e restrição de sexo."""
from __future__ import annotations

from penna.core import text_upper

from .. import catalog, lookups
from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import ROTULO_CORPO, Emissor
from ..regra import Regra


def _cid_principal(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010040 (HIPOTESE) CID inexistente; 010041 (HIPOTESE) CID restrito ao outro sexo."""
    cid = text_upper(linha.valor("Cid_Princ")).replace(" ", "")[:4]
    if not cid or ctx.cids_validos is None:
        return
    # aceita a categoria (3 caracteres) quando a subcategoria digitada não existe
    if cid not in ctx.cids_validos and cid[:3] not in ctx.cids_validos:
        emit.emitir(catalog.SEVERIDADE_HIPOTESE, "010040", f"CID ({cid}) NAO ENCONTRADO", ROTULO_CORPO)
        return
    base = ctx.cids_restricoes if ctx.cids_restricoes is not None else ctx.cids_registros
    restricao = lookups.restricao_sexo_cid(cid[:3], base)
    esperado = {"1": "M", "2": "F"}.get(restricao or "", "")
    if esperado and linha.sexo in ("M", "F") and linha.sexo != esperado:
        emit.emitir(
            catalog.SEVERIDADE_HIPOTESE, "010041", f"CID ({cid}) NAO PERMITIDO PARA O SEXO DO USUARIO", ROTULO_CORPO
        )


CID_PRINCIPAL = Regra(
    "cid_principal", _cid_principal, codigos=("010040", "010041"),
    base_ausente=lambda ctx: ctx.cids_validos is None,
    desativada="CID valido e restricao de sexo (S_CID)", sigtap=True,
)
