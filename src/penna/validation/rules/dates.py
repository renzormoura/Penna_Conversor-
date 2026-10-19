"""Regras de datas: validade das datas do TXT e coerência entre elas."""
from __future__ import annotations

from penna.core import normalize_date

from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import ERR, ROTULO_CORPO, Emissor
from ..regra import Regra

# Datas gravadas no TXT além do nascimento (validado à parte).
CAMPOS_DATA_TXT = (
    "Inicio_Validade", "Fim_Validade", "Data_Solicitacao",
    "Data_Autorizacao", "Data_Alta_Obito", "Data_Emissao",
)


def _dd_mm_aaaa(aaaammdd: str) -> str:
    return f"{aaaammdd[6:8]}/{aaaammdd[4:6]}/{aaaammdd[0:4]}" if len(aaaammdd) == 8 else aaaammdd


def _datas_txt(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010090 (regra local): data do TXT preenchida e inexistente."""
    for campo in CAMPOS_DATA_TXT:
        bruto = linha.valor(campo)
        if bruto and not normalize_date(bruto):
            emit.emitir(ERR, "010090", f"{campo.upper()}: DATA INVALIDA ({bruto})", ROTULO_CORPO)


def _solicitacao_vs_nascimento(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010042: solicitação anterior ao nascimento."""
    solicitacao = normalize_date(linha.valor("Data_Solicitacao"))
    if linha.nascimento_valido and solicitacao and solicitacao < linha.nascimento:
        emit.emitir(
            ERR, "010042",
            f"DATA DE SOLICITACAO ({_dd_mm_aaaa(solicitacao)}) "
            f"ANTERIOR A DATA DE NASCIMENTO({_dd_mm_aaaa(linha.nascimento)})",
            ROTULO_CORPO,
        )


def _encerramento_vs_fim(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010083: alta/óbito depois do fim da validade."""
    encerramento = normalize_date(linha.valor("Data_Alta_Obito"))
    fim = normalize_date(linha.valor("Fim_Validade"))
    if encerramento and fim and encerramento > fim:
        emit.emitir(
            ERR, "010083",
            f"DATA DE ENCERRAMENTO ({_dd_mm_aaaa(encerramento)}) MAIOR QUE DATA DE FIM ({_dd_mm_aaaa(fim)})",
            ROTULO_CORPO,
        )


DATAS_TXT = Regra("datas_do_txt", _datas_txt, codigos=("010090",))
SOLICITACAO_VS_NASCIMENTO = Regra("solicitacao_vs_nascimento", _solicitacao_vs_nascimento, codigos=("010042",))
ENCERRAMENTO_VS_FIM = Regra("encerramento_vs_fim", _encerramento_vs_fim, codigos=("010083",))
