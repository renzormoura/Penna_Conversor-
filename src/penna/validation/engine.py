"""Motor de validação: aplica as regras a cada linha da planilha e agrega o relatório."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from penna.core import resolve_competence

from .context import ContextoValidacao, montar_contexto
from .linha import LinhaApac
from .model import ERR, ROTULO_CORPO, Coletor, Ocorrencia, ResultadoValidacao
from .regra import Regra
from .rules import REGRAS_DA_LINHA, REGRAS_DO_ITEM

_PLANILHA_VAZIA = Ocorrencia("", "", ERR, ROTULO_CORPO, "000005", "PLANILHA VAZIA - NENHUMA APAC PARA EXPORTAR")


def regras_desativadas(
    ctx: ContextoValidacao,
    sigtap_ativo: bool,
    regras: Iterable[Regra] = REGRAS_DA_LINHA,
    regras_item: Iterable = REGRAS_DO_ITEM,
) -> List[str]:
    """Descrições das regras que não rodaram por falta de base, sem repetição e em ordem."""
    descricoes: List[str] = []
    for regra in (*regras, *regras_item):
        if regra.esta_desativada(ctx, sigtap_ativo) and regra.desativada not in descricoes:
            descricoes.append(regra.desativada)
    return descricoes


def _validar_linha(linha: LinhaApac, ctx: ContextoValidacao, coletor: Coletor, regras: Iterable[Regra]) -> None:
    emit = linha.emissor(coletor)
    for regra in regras:
        if regra.verificar(linha, ctx, emit):
            return  # regra fatal: as demais perdem o sentido para esta linha


def _apontar_competencia_divergente(
    linha: LinhaApac, referencia: str, ja_apontadas: Set[str], coletor: Coletor
) -> None:
    """000005: o arquivo é de uma só competência; cada divergente é apontada uma vez."""
    if referencia and linha.cmpt and linha.cmpt != referencia and linha.cmpt not in ja_apontadas:
        ja_apontadas.add(linha.cmpt)
        coletor.adicionar(
            referencia, linha.num_apac, ERR, ROTULO_CORPO, "000005",
            f"COMPETENCIA ({linha.cmpt}) DIFERENTE DA COMPETENCIA ({referencia}) DO ARQUIVO",
        )


def validar_planilha(
    df: Any,
    base_ceps: Optional[Set[str]] = None,
    catalogo_pa: Optional[Dict[str, Dict[str, str]]] = None,
    usar_remessa: bool = True,
    pasta_remessas: Optional[Path] = None,
    usar_sigtap: bool = True,
    pares_secundarios: Optional[Dict[str, Dict[str, str]]] = None,
    habilitacoes_exigidas: Optional[Dict[str, set]] = None,
    habilitacoes_cnes: Optional[set] = None,
    cids_validos: Optional[Set[str]] = None,
    cids_registros: Optional[List[Dict[str, str]]] = None,
    regras_condicionadas: Optional[Dict[str, set]] = None,
    historico_apacs: Optional[Set[str]] = None,
    sigtap_competencia: Optional[str] = None,
) -> ResultadoValidacao:
    """Valida TODAS as linhas da planilha e devolve o relatório no formato RCONSIST.

    A geração do TXT só pode prosseguir sem ocorrência ERR (AVS não bloqueia, como
    no programa original). Os parâmetros ``None`` carregam a base correspondente
    uma única vez; informar uma base (inclusive vazia) a injeta, o que permite
    testar sem as tabelas reais ou desativar uma regra.

    ``sigtap_competencia``: competência (ex.: ``"202606"``) cujo ZIP do SIGTAP
    baixado serve de fallback quando as tabelas DBF locais não cobrem o mês.
    """
    linhas = [] if df is None else [dict(serie) for _, serie in df.iterrows()]
    if not linhas:
        return ResultadoValidacao([_PLANILHA_VAZIA])

    referencia = resolve_competence(linhas[0])
    ctx = montar_contexto(
        referencia,
        usar_sigtap=usar_sigtap,
        usar_remessa=usar_remessa,
        pasta_remessas=pasta_remessas,
        sigtap_competencia=sigtap_competencia,
        base_ceps=base_ceps,
        catalogo_pa=catalogo_pa,
        pares_secundarios=pares_secundarios,
        habilitacoes_exigidas=habilitacoes_exigidas,
        habilitacoes_cnes=habilitacoes_cnes,
        cids_validos=cids_validos,
        cids_registros=cids_registros,
        regras_condicionadas=regras_condicionadas,
        historico_apacs=historico_apacs,
    )

    coletor = Coletor()
    ja_apontadas: Set[str] = set()
    for row in linhas:
        linha = LinhaApac.de(row)
        _apontar_competencia_divergente(linha, referencia, ja_apontadas, coletor)
        _validar_linha(linha, ctx, coletor, REGRAS_DA_LINHA)
    if not referencia:
        coletor.adicionar("", "", ERR, ROTULO_CORPO, "000005", "COMPETENCIA (VAZIA) INVALIDA PARA EXPORTACAO")

    return ResultadoValidacao(coletor.itens, regras_desativadas(ctx, usar_sigtap and bool(referencia)))
