"""Regras do paciente e do endereço: nascimento, CEP, raça e logradouro."""
from __future__ import annotations

from penna.core import digits, text

from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import ERR, ROTULO_CORPO, Emissor
from ..regra import Regra

# Raças válidas do campo AP_RACA (01..05 informadas, 99 = sem informação).
RACAS_VALIDAS = frozenset({"01", "02", "03", "04", "05", "99"})


def _nascimento(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010025: data de nascimento inexistente."""
    if not linha.nascimento_valido:
        emit.emitir(ERR, "010025", "DATA DE NASCIMENTO INVALIDA", ROTULO_CORPO)


def _cep(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010022: CEP fora da S_CEP (somente com a base presente)."""
    if ctx.base_ceps is None:
        return
    d = digits(linha.valor("Cep"))
    cep8 = d.zfill(8)[:8] if d else "00000000"
    if cep8 not in ctx.base_ceps:
        emit.emitir(ERR, "010022", f"CEP ({cep8}) NAO ENCONTRADO", ROTULO_CORPO)


def _raca(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010027: raça/cor fora de 01..05 e 99 (vazio vale 99)."""
    d = digits(linha.valor("Raca"))
    raca = d.zfill(2)[:2] if d else "99"
    if raca not in RACAS_VALIDAS:
        emit.emitir(ERR, "010027", f"RACA ({raca}) INVALIDA", ROTULO_CORPO)


def _logradouro(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010032: código do logradouro não numérico ou com mais de 3 dígitos."""
    codigo = text(linha.valor("Codigo_Logradouro", "Cod_Logradouro")).strip() or text(linha.valor("Logradouro")).strip()
    if not codigo or not codigo.isdigit() or len(codigo) > 3:
        emit.emitir(ERR, "010032", f"LOGRADOURO ({codigo}) INVALIDO", ROTULO_CORPO)


NASCIMENTO = Regra("data_nascimento", _nascimento, codigos=("010025",))
CEP = Regra(
    "cep", _cep, codigos=("010022",),
    base_ausente=lambda ctx: ctx.base_ceps is None,
    desativada="CEP inexistente (S_CEP)",
)
RACA = Regra("raca", _raca, codigos=("010027",))
LOGRADOURO = Regra("logradouro", _logradouro, codigos=("010032",))
