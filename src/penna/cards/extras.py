"""Página final "OUTROS DADOS DA LINHA" (colunas sem campo no formulário)."""
from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from ._reportlab import HexColor, white
from .constants import GRADE_COR, GRADE_ESP
from .pdf_text import fonte, medir, preparar_texto
from .template import Modelo

_EXTRA_TITULO_ALT = 15.75    # altura do título do bloco de extras
_EXTRA_LINHA_ALT = 15.75     # altura de cada linha de pares rótulo/valor
EXTRA_GAP = 8.0             # respiro entre o formulário e o bloco de extras


def _altura_extras(extras: Sequence[Tuple[str, str, str]]) -> float:
    """Altura do bloco "OUTROS DADOS DA LINHA" (unidades do modelo)."""
    if not extras:
        return 0.0
    n_linhas = max((len(extras) + 1) // 2, 1)
    return _EXTRA_TITULO_ALT + n_linhas * _EXTRA_LINHA_ALT


def escala_da_ficha(modelo: Modelo, ficha: Dict[str, Any]) -> float:
    """Escala que faz a ficha INTEIRA caber em uma página A4.

    O formulário do modelo ocupa duas páginas impressas (quebra na linha
    ``_QUEBRA_PAGINA``) e as listas fixas do paciente ainda encolhem parte
    dele. Reduzir a escala (nunca amplia) mantém ficha + extras em UMA
    página, sem partir o documento.
    """
    larg_pag, alt_pag = modelo.pagina
    util_w = larg_pag - modelo.margem_esq - modelo.margem_dir
    util_h = alt_pag - modelo.margem_topo - modelo.margem_base
    altura = modelo.altura_visivel(ficha["ocultar"])
    if ficha["extras"]:
        altura += EXTRA_GAP + _altura_extras(ficha["extras"])
    if altura <= 0:
        return modelo.escala
    nc = modelo.colunas_para(ficha["sobrescritas"])
    escala = min(util_h / altura, util_w / modelo.xs[nc])
    return min(modelo.escala, escala)


def desenhar_extras(c, modelo: Modelo, extras: Sequence[Tuple[str, str, str]],
                     escala: float, y_topo: float, nc: int) -> None:
    """Uma vez só, na mesma página: colunas da linha sem campo no formulário.

    Desenhado na mesma transformação (origem + escala) do formulário, logo
    abaixo do conteúdo que ``desenhar_pagina`` deixou.
    """
    larg_pag = modelo.pagina[0]
    util = modelo.xs[nc]

    c.saveState()
    desloc = max(larg_pag - modelo.margem_esq - modelo.margem_dir
                 - util * escala, 0.0) / 2.0
    c.translate(modelo.margem_esq + desloc, 0)
    c.scale(escala, escala)

    # grade de 4 colunas (2 pares rótulo/valor por linha)
    larguras = [util * 0.20, util * 0.30, util * 0.20, util * 0.30]
    xs = [0.0]
    for w in larguras:
        xs.append(xs[-1] + w)

    altura_titulo = _EXTRA_TITULO_ALT
    altura_linha = _EXTRA_LINHA_ALT
    itens = list(extras)
    n_linhas = max((len(itens) + 1) // 2, 1)
    y_titulo = y_topo - altura_titulo
    y_fim = y_titulo - altura_linha * n_linhas

    # título da seção (mesma linguagem do formulário)
    c.setFillColor(white)
    c.rect(xs[0], y_titulo, util, altura_titulo, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(1.25)
    c.rect(xs[0], y_titulo, util, altura_titulo, stroke=1, fill=0)
    nome_titulo = fonte("Calibri", True, False)
    c.setFillColor(HexColor("#000000"))
    c.setFont(nome_titulo, 11)
    c.drawString(xs[0] + 6, y_titulo + 4,
                 preparar_texto("OUTROS DADOS DA LINHA — informação da linha "
                                 "sem campo no formulário da ficha", nome_titulo))

    # grade das linhas (por cima, como a planilha)
    c.setStrokeColor(HexColor(GRADE_COR))
    c.setLineWidth(GRADE_ESP)
    yy = y_titulo
    while yy >= y_fim - 0.1:
        c.line(xs[0], yy, xs[-1], yy)
        yy -= altura_linha
    for x in xs:
        c.line(x, y_fim, x, y_titulo)

    # pares rótulo/valor
    nome_rot = fonte("Calibri", True, False)
    nome_val = fonte("Calibri", False, False)
    for i, (rotulo, valor, _) in enumerate(itens):
        par = i % 2
        linha_y = y_titulo - (i // 2 + 1) * altura_linha
        x_rot = xs[par * 2]
        x_val = xs[par * 2 + 1]
        c.setFillColor(HexColor("#000000"))
        c.setFont(nome_rot, 9.5)
        rotulo_txt = preparar_texto(str(rotulo), nome_rot)
        while medir(rotulo_txt, nome_rot, 9.5) > larguras[par * 2] - 6 \
                and len(rotulo_txt) > 4:
            rotulo_txt = rotulo_txt[:-2]
        c.drawString(x_rot + 3, linha_y + 4.5, rotulo_txt)
        c.setFont(nome_val, 9.5)
        valor_txt = preparar_texto(str(valor), nome_val)
        while medir(valor_txt, nome_val, 9.5) > larguras[par * 2 + 1] - 6 \
                and len(valor_txt) > 4:
            valor_txt = valor_txt[:-2]
        c.drawString(x_val + 3, linha_y + 4.5, valor_txt)

    c.restoreState()
