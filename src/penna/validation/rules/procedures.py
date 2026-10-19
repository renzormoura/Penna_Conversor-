"""Regras dos procedimentos (principal e secundários) e da regra condicionada 0009.

Os procedimentos são percorridos em ordem e, para cada um, as regras de item
rodam na ordem de :data:`REGRAS_DO_ITEM`: a ordem de emissão define a numeração
``SEQ`` do relatório e é preservada do programa original.
"""
from __future__ import annotations

from typing import Optional

from .. import catalog
from ..context import ContextoValidacao
from ..linha import LinhaApac
from ..model import AVS, ERR, ROTULO_CORPO, ROTULO_HABILITACAO, Emissor
from ..regra import ItemProcedimento, Regra, RegraItem
from .apac import cnes_da_linha

# Procedimento principal da planilha OCI (APAC PMAE na mensagem 000024).
APAC_PMAE = "0905010035"

# Lista fixa (AVS 030008) usada apenas quando não há base XUPSHA nem S_PAHA:
# procedimentos que geraram o aviso real no RCONSIST. Com as bases presentes,
# a regra usa S_PAHA x XUPSHA.
PROCEDIMENTOS_EXIGEM_HABILITACAO = frozenset({"0211060020", "0211060127", "0211060232", "0301010072"})

SEM_LIMITE_IDADE = 999
SEM_LIMITE_QUANTIDADE = 9999


def _int(valor: str, padrao: int) -> int:
    try:
        return int(valor or padrao)
    except ValueError:
        return padrao


def _quantidade(item: ItemProcedimento) -> int:
    return int((item.quantidade or "0").lstrip("0") or 0)


def idade_em_anos(nascimento: str, competencia: str) -> int:
    """Idade completa na competência; ``-1`` se alguma das datas for ilegível."""
    try:
        ano_nasc, mes_nasc = int(nascimento[:4]), int(nascimento[4:6])
        ano_ref, mes_ref = int(competencia[:4]), int(competencia[4:6])
    except (ValueError, IndexError):
        return -1
    return ano_ref - ano_nasc - (1 if mes_ref < mes_nasc else 0)


# --- Regras de linha ---------------------------------------------------------

def _quantidade_zero_pmae(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000024: APAC PMAE não admite quantidade zero (mensagem literal do RCONSIST.NOV)."""
    if not any(codigo == APAC_PMAE for codigo, _ in linha.itens):
        return
    for codigo, quantidade in linha.itens:
        if (quantidade or "0").lstrip("0") == "":
            zero = ((quantidade or "0").lstrip("0") or "0").rjust(6)
            emit.emitir(
                ERR, "000024",
                f"PROC.({codigo}) DE APAC PMAE, NAO É PERMITIDO QTD.({zero}) ZERO PROC.PRINC. OU SECUNDARIO.",
            )


def _procedimento_no_catalogo(chave: str, ctx: ContextoValidacao) -> Optional[dict]:
    if ctx.catalogo_pa is None:
        return None
    return ctx.catalogo_pa.get(chave) or ctx.catalogo_pa.get(chave.lstrip("0").zfill(9))


def _por_procedimento(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    for posicao, (codigo, quantidade) in enumerate(linha.itens):
        item = ItemProcedimento(posicao, codigo, quantidade, _procedimento_no_catalogo(codigo[:9], ctx))
        for regra in REGRAS_DO_ITEM:
            regra.verificar(item, linha, ctx, emit)


def _regra_condicionada_0009(linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """030009: o principal impede valor nos secundários (AVS impresso no R0201)."""
    principal = linha.itens[0][0][:9] if linha.itens else ""
    if "0009" in (ctx.regras_condicionadas or {}).get(principal, set()) and len(linha.itens) > 1:
        if any(quantidade.lstrip("0") for _, quantidade in linha.itens[1:]):
            emit.emitir(
                AVS, "030009",
                "REGRA CONDICIONADA 0009 : PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS",
                ROTULO_CORPO,
            )


# --- Regras de item ----------------------------------------------------------

def _idade(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000016: idade fora do intervalo do procedimento (S_PA: PA_IDADEMN/PA_IDADEMX, em anos)."""
    if item.pa is None or not linha.nascimento_valido or not linha.cmpt:
        return
    idade = idade_em_anos(linha.nascimento, linha.cmpt)
    if idade < 0:
        return
    try:
        maxima = int(item.pa.get("PA_IDADEMX", "") or SEM_LIMITE_IDADE)
        minima = int(item.pa.get("PA_IDADEMN", "") or SEM_LIMITE_IDADE)
    except ValueError:  # valor corrompido na tabela: sem limite
        maxima = minima = SEM_LIMITE_IDADE
    if maxima < SEM_LIMITE_IDADE and idade > maxima:
        emit.emitir(ERR, "000016", f"PROC.({item.codigo}) NAO PERMITIDO PARA IDADE MAX.DO USUARIO : {maxima}")
    elif minima < SEM_LIMITE_IDADE and idade < minima:
        emit.emitir(ERR, "000016", f"PROC.({item.codigo}) NAO PERMITIDO PARA IDADE MIN.DO USUARIO : {minima}")


def _sexo(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000007 (HIPOTESE): procedimento restrito a um sexo (S_PA: PA_SEXO = M/F/A)."""
    if item.pa is None or linha.sexo not in ("M", "F", "I"):
        return
    sexo_pa = (item.pa.get("PA_SEXO") or "").strip().upper()
    if sexo_pa in ("M", "F") and linha.sexo != sexo_pa and linha.sexo != "I":
        emit.emitir(catalog.SEVERIDADE_HIPOTESE, "000007", f"PROC.({item.codigo}) NAO PERMITIDO PARA SEXO DO USUARIO")


def _quantidade_maxima(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000008 (HIPOTESE): quantidade acima do máximo do procedimento (S_PA: PA_QTDMAX)."""
    if item.pa is None:
        return
    maxima = _int(item.pa.get("PA_QTDMAX", ""), SEM_LIMITE_QUANTIDADE)
    if maxima < SEM_LIMITE_QUANTIDADE and _quantidade(item) > maxima:
        emit.emitir(catalog.SEVERIDADE_HIPOTESE, "000008", f"PROC.({item.codigo}) QTD. ACIMA DO MAXIMO PERMITIDO : {maxima}")


def _secundario_obrigatorio(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000006 (HIPOTESE): principal que exige ao menos um secundário (S_PA: PA_SECOBRI = S)."""
    if item.posicao == 0 and item.pa is not None and (item.pa.get("PA_SECOBRI") or "").strip().upper() == "S":
        if len(linha.itens) < 2:
            emit.emitir(
                catalog.SEVERIDADE_HIPOTESE, "000006",
                f"PROC.({item.codigo}) EXIGE PELO MENOS (1) PROC. SECUNDARIO OBRIGATORIO.",
            )


def _habilitacao(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """030008: habilitação exigida (S_PAHA) ausente no CNES (XUPSHA); sem as bases, lista fixa."""
    exigidas, do_cnes = ctx.habilitacoes_exigidas, ctx.habilitacoes_cnes
    if exigidas is not None and do_cnes is not None:
        necessarias = exigidas.get(item.chave)
        if not necessarias or do_cnes & necessarias:
            return
    elif not (exigidas is None and do_cnes is None and item.codigo in PROCEDIMENTOS_EXIGEM_HABILITACAO):
        return
    emit.emitir(
        AVS, "030008",
        f"PROCED.({item.codigo}) EXIGE HABILITACAO NAO ENCONTRADA NO CNES({cnes_da_linha(linha)})",
        ROTULO_HABILITACAO,
    )


def _par_principal_secundario(item: ItemProcedimento, linha: LinhaApac, ctx: ContextoValidacao, emit: Emissor) -> None:
    """000009 (HIPOTESE): secundário fora dos compatíveis do principal (S_PAPA); e a quantidade do par."""
    if ctx.pares_secundarios is None or item.posicao == 0:
        return
    principal = linha.itens[0][0]
    permitidos = ctx.pares_secundarios.get(principal[:9])
    if permitidos is None:
        return
    chave = item.chave
    sem_zeros = {p.lstrip("0") for p in permitidos}
    if chave not in permitidos and chave.lstrip("0") not in sem_zeros:
        emit.emitir(
            catalog.SEVERIDADE_HIPOTESE, "000009",
            f"PROC. SECUNDARIO ({item.codigo}) NAO PERMITIDO PARA O PROC. PRINCIPAL ({principal})",
        )
        return
    limite = permitidos.get(chave) or next((q for p, q in permitidos.items() if p.lstrip("0") == chave.lstrip("0")), "")
    maxima = _int((limite or str(SEM_LIMITE_QUANTIDADE)).lstrip("0"), SEM_LIMITE_QUANTIDADE)
    if maxima < SEM_LIMITE_QUANTIDADE and _quantidade(item) > maxima:
        emit.emitir(catalog.SEVERIDADE_HIPOTESE, "000008", f"PROC.({item.codigo}) QTD. ACIMA DO MAXIMO PERMITIDO : {maxima}")


_SEM_S_PA = "idade, sexo, quantidade e secundario obrigatorio (S_PA)"


def _sem_catalogo(ctx: ContextoValidacao) -> bool:
    return not ctx.catalogo_pa


REGRAS_DO_ITEM = (
    RegraItem("idade_do_procedimento", _idade, ("000016",), _sem_catalogo, _SEM_S_PA),
    RegraItem("sexo_do_procedimento", _sexo, ("000007",), _sem_catalogo, _SEM_S_PA),
    RegraItem("quantidade_maxima", _quantidade_maxima, ("000008",), _sem_catalogo, _SEM_S_PA),
    RegraItem("secundario_obrigatorio", _secundario_obrigatorio, ("000006",), _sem_catalogo, _SEM_S_PA),
    RegraItem(
        "habilitacao_do_cnes", _habilitacao, ("030008",),
        lambda ctx: ctx.habilitacoes_exigidas is None or ctx.habilitacoes_cnes is None,
        "habilitacao do CNES (S_PAHA/XUPSHA)", sigtap=True,
    ),
    RegraItem(
        "par_principal_secundario", _par_principal_secundario, ("000009", "000008"),
        lambda ctx: ctx.pares_secundarios is None,
        "par principal/secundario (S_PAPA)", sigtap=True,
    ),
)

QUANTIDADE_ZERO_PMAE = Regra("quantidade_zero_pmae", _quantidade_zero_pmae, codigos=("000024",))
PROCEDIMENTOS = Regra("procedimentos", _por_procedimento, codigos=("000016", "000007", "000008", "000006", "030008", "000009"))
REGRA_CONDICIONADA_0009 = Regra(
    "regra_condicionada_0009", _regra_condicionada_0009, codigos=("030009",),
    base_ausente=lambda ctx: not ctx.regras_condicionadas,
    desativada="regra condicionada (S_PAREGR)", sigtap=True,
)
