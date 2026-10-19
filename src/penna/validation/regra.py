"""Contrato de uma regra do motor de validação."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .context import ContextoValidacao
from .linha import LinhaApac
from .model import Emissor

# Uma regra inspeciona a linha (com o contexto de bases) e emite ocorrências.
# Devolver True interrompe as demais regras daquela linha (erro fatal).
Verificar = Callable[[LinhaApac, ContextoValidacao, Emissor], Optional[bool]]


@dataclass(frozen=True)
class Regra:
    """Uma regra de consistência.

    ``codigos``: códigos de ocorrência que ela pode emitir (documentação e testes).
    ``base_ausente``: diz se a base que a regra exige falta no contexto; nesse
    caso a regra não dispara (nunca falso positivo) e é listada como desativada
    com o texto ``desativada``. Regras sem base exigida omitem ambos.
    ``sigtap``: a regra depende das tabelas SIGTAP e só é listada como
    desativada quando essas regras estão ligadas.
    """

    nome: str
    verificar: Verificar
    codigos: tuple = ()
    base_ausente: Optional[Callable[[ContextoValidacao], bool]] = None
    desativada: str = ""
    sigtap: bool = False

    def esta_desativada(self, ctx: ContextoValidacao, sigtap_ativo: bool) -> bool:
        if self.base_ausente is None or (self.sigtap and not sigtap_ativo):
            return False
        return self.base_ausente(ctx)


@dataclass(frozen=True)
class ItemProcedimento:
    """Um procedimento da APAC (principal ou secundário) sob verificação."""

    posicao: int                      # 0 = principal
    codigo: str                       # 10 dígitos
    quantidade: str
    pa: Optional[dict] = None         # registro da S_PA, se a base existir e o código constar

    @property
    def chave(self) -> str:
        """Código sem o DV (9 dígitos), a chave das tabelas SIGTAP."""
        return self.codigo[:9]


VerificarItem = Callable[[ItemProcedimento, LinhaApac, ContextoValidacao, Emissor], None]


@dataclass(frozen=True)
class RegraItem:
    """Regra aplicada a cada procedimento da APAC, na ordem dos procedimentos.

    Mesmos campos de :class:`Regra`; ``verificar`` recebe o item e não interrompe.
    """

    nome: str
    verificar: VerificarItem
    codigos: tuple = ()
    base_ausente: Optional[Callable[[ContextoValidacao], bool]] = None
    desativada: str = ""
    sigtap: bool = False

    esta_desativada = Regra.esta_desativada
