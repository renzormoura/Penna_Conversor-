"""Regras de consistência, na ordem em que rodam (a ordem define a numeração SEQ)."""
from ..regra import Regra
from .apac import CNES, HISTORICO, NUMERO_APAC
from .cid import CID_PRINCIPAL
from .dates import DATAS_TXT, ENCERRAMENTO_VS_FIM, SOLICITACAO_VS_NASCIMENTO
from .patient import CEP, LOGRADOURO, NASCIMENTO, RACA
from .procedures import PROCEDIMENTOS, QUANTIDADE_ZERO_PMAE, REGRA_CONDICIONADA_0009, REGRAS_DO_ITEM
from .text import TEXTOS_TXT

REGRAS_DA_LINHA: tuple[Regra, ...] = (
    NUMERO_APAC,          # fatal: sem número, as demais perdem o sentido
    HISTORICO,
    CNES,
    NASCIMENTO,
    DATAS_TXT,
    TEXTOS_TXT,
    CEP,
    RACA,
    LOGRADOURO,
    SOLICITACAO_VS_NASCIMENTO,
    ENCERRAMENTO_VS_FIM,
    QUANTIDADE_ZERO_PMAE,
    PROCEDIMENTOS,        # aplica REGRAS_DO_ITEM a cada procedimento
    REGRA_CONDICIONADA_0009,
    CID_PRINCIPAL,
)

__all__ = ["REGRAS_DA_LINHA", "REGRAS_DO_ITEM"]
