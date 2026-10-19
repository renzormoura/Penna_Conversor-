r"""Modelo do relatório de consistência (formato RCONSIST do programa original).

    CMPT.  NUM.APAC      TIPO SEQ.   COD.   DESCRICAO
    202511 3325700656553 ERR  000001 000024 PROC.(0905010035) DE APAC PMAE...

Numeração herdada do original:

- ``SEQ`` numérico (000001, 000002...) REINICIA a cada APAC;
- ocorrências de corpo usam o rótulo ``CORPO`` (``ERR  CORPO  010025``), as de
  habilitação ``HABILI`` e as de CNES ``CNES``: rótulo não consome número;
- ``ERR`` bloqueia a exportação; ``AVS`` é listado e permite gerar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

ERR = "ERR"
AVS = "AVS"

ROTULO_CORPO = "CORPO"
ROTULO_HABILITACAO = "HABILI"
ROTULO_CNES = "CNES"


@dataclass(frozen=True)
class Ocorrencia:
    """Uma linha do relatório de consistência."""

    cmpt: str
    num_apac: str
    tipo: str  # ERR (bloqueia) ou AVS (aviso, permite exportar)
    seq: str   # "000001"... ou rótulo textual (CORPO, HABILI, CNES)
    cod: str
    descricao: str

    @property
    def bloqueia(self) -> bool:
        return self.tipo == ERR


class ResultadoValidacao(list):
    """Lista de :class:`Ocorrencia` com metadados da validação.

    ``regras_desativadas``: regras que não rodaram por falta da base de dados
    (ex.: ``"CEP inexistente (S_CEP)"``), para a UI avisar que a validação foi parcial.
    """

    def __init__(self, itens: Iterable[Any] = (), regras_desativadas: Iterable[str] = ()):
        super().__init__(itens)
        self.regras_desativadas: List[str] = list(regras_desativadas)


def formatar_linha_rconsist(o: Ocorrencia) -> str:
    """A ocorrência exatamente como a linha do RCONSIST do original."""
    return f" {o.cmpt} {o.num_apac} {o.tipo:<4} {o.seq:<6} {o.cod} {o.descricao}"


def tem_erros(ocorrencias: Iterable[Ocorrencia]) -> bool:
    """``True`` se existe ao menos uma ocorrência ERR (bloqueia a geração)."""
    return any(o.tipo == ERR for o in ocorrencias)


def resumo(ocorrencias: Iterable[Ocorrencia]) -> Tuple[int, int]:
    """``(quantidade de ERR, quantidade de AVS)``."""
    itens = list(ocorrencias)
    n_err = sum(1 for o in itens if o.tipo == ERR)
    return n_err, len(itens) - n_err


class Coletor:
    """Acumula as ocorrências com a numeração ``SEQ`` do original."""

    def __init__(self) -> None:
        self.itens: List[Ocorrencia] = []
        self._chave_atual: Optional[tuple] = None
        self._contador = 0

    def adicionar(self, cmpt: str, num_apac: str, tipo: str, rotulo_seq: str, cod: str, descricao: str) -> None:
        chave = (cmpt, num_apac)
        if chave != self._chave_atual:
            self._chave_atual = chave
            self._contador = 0
        if rotulo_seq:
            seq = rotulo_seq
        else:
            self._contador += 1
            seq = f"{self._contador:06d}"
        self.itens.append(Ocorrencia(cmpt, num_apac, tipo, seq, cod, descricao))


class Emissor:
    """Ponto de emissão de uma linha da planilha: já conhece competência e nº da APAC."""

    def __init__(self, coletor: Coletor, cmpt: str, num_apac: str) -> None:
        self._coletor = coletor
        self.cmpt = cmpt
        self.num_apac = num_apac

    def emitir(self, tipo: str, cod: str, descricao: str, rotulo: str = "", num_apac: Optional[str] = None) -> None:
        """Registra a ocorrência; ``rotulo`` vazio consome o próximo ``SEQ`` numérico."""
        self._coletor.adicionar(
            self.cmpt, self.num_apac if num_apac is None else num_apac, tipo, rotulo, cod, descricao
        )
