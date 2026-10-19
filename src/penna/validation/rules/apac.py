"""Regras de identificação da APAC: número, histórico de remessa e CNES."""
from __future__ import annotations

from penna.core import digits

from .. import lookups
from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import AVS, ERR, ROTULO_CNES, ROTULO_CORPO, Emissor
from ..regra import Regra


def _numero_apac(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> bool:
    """000005: sem número de APAC válido as demais regras perdem o sentido (fatal)."""
    if linha.numero_valido:
        return False
    emit.emitir(
        ERR, "000005",
        f"NUMERO DA APAC ({linha.texto_apac or 'VAZIO'}) INVALIDO PARA EXPORTACAO",
        ROTULO_CORPO, num_apac="",
    )
    return True


def _historico(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010084: APAC já exportada. Avisa e não bloqueia.

    O histórico é o registro local do Penna e a correção/substituição reenvia os
    mesmos números legitimamente; quem barra duplicidade de verdade é o site do
    DATASUS. Bloquear aqui impedia reexportar a planilha na mesma sessão.
    """
    if ctx.historico_apacs is not None and linha.num_apac in ctx.historico_apacs:
        emit.emitir(AVS, "010084", "NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE", ROTULO_CORPO)


def cnes_da_linha(linha: LinhaApac) -> str:
    """CNES executante com 7 dígitos; sem valor na linha vale o padrão do config."""
    informado = digits(linha.valor("Cnes_Executante")) or lookups.cnes_padrao()
    return informado.zfill(7)[:7]


def _cnes(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """030001: CNES executante diferente do estabelecimento configurado."""
    cnes7 = cnes_da_linha(linha)
    if cnes7 != lookups.cnes_padrao():
        emit.emitir(AVS, "030001", f"CNES EXECUTANTE({cnes7}) NAO ENCONTRADO", ROTULO_CNES)


NUMERO_APAC = Regra("numero_apac", _numero_apac, codigos=("000005",))
HISTORICO = Regra("historico_remessa", _historico, codigos=("010084",))
CNES = Regra("cnes_executante", _cnes, codigos=("030001",))
