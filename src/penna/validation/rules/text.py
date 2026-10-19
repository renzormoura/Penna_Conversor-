"""Regras dos textos do TXT: caracteres suportados e largura máxima do layout."""
from __future__ import annotations

from penna.layout.constants import LARGURA_TEXTO

from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import AVS, ERR, ROTULO_CORPO, Emissor
from ..regra import Regra


def caractere_invalido_no_txt(valor: str) -> str:
    """Primeiro caractere que o TXT cp1252 não suporta (``''`` se nenhum).

    Controle (quebra de linha, tab) desmonta o layout fixo; fora do cp1252 o
    gerador antigo gravava ``?`` no lugar, corrompendo o dado fiscal.
    """
    for ch in valor:
        if ord(ch) < 32 or ord(ch) == 127:
            return repr(ch)
        try:
            ch.encode("cp1252")
        except UnicodeEncodeError:
            return ch
    return ""


def _textos_txt(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """010091 (ERR) caractere não suportado; 010092 (AVS) texto acima da largura (será truncado)."""
    for campo, largura in LARGURA_TEXTO.items():
        valor = linha.valor(campo)
        if not valor:
            continue
        ruim = caractere_invalido_no_txt(valor)
        if ruim:
            emit.emitir(ERR, "010091", f"{campo.upper()}: CARACTERE NAO SUPORTADO NO TXT ({ruim})", ROTULO_CORPO)
        if len(valor) > largura:
            emit.emitir(
                AVS, "010092",
                f"{campo.upper()}: TEXTO COM {len(valor)} CARACTERES, MAXIMO {largura} (SERA TRUNCADO)",
                ROTULO_CORPO,
            )


TEXTOS_TXT = Regra("textos_do_txt", _textos_txt, codigos=("010091", "010092"))
