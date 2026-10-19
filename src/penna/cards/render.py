"""Geração dos PDFs: uma ficha por linha da planilha."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set

from ._reportlab import canvas as _canvas
from .content import montar_ficha
from .extras import EXTRA_GAP, desenhar_extras, escala_da_ficha
from .files import nome_arquivo_ficha
from .page import cabecalho_rodape, desenhar_pagina
from .pdf_text import exigir_reportlab
from .template import carregar_modelo
from .text import valor_texto

def gerar_ficha_pdf(row: Any, caminho: Path) -> Path:
    """Gera o PDF da ficha de uma linha e devolve o caminho gravado."""
    exigir_reportlab()
    modelo = carregar_modelo()
    ficha = montar_ficha(row)
    caminho = Path(caminho)
    caminho.parent.mkdir(exist_ok=True, parents=True)

    nome_paciente = valor_texto(dict(row).get("Nome_Paciente")) if row is not None else ""
    c = _canvas.Canvas(str(caminho), pagesize=modelo.pagina)
    # Codificação de fonte = UTF-8 (sobrescreve o default WinAnsi/Cp1252 do
    # reportlab) para que os glyphs acentuados que o PDF já contém sejam
    # extraídos pelo pdfminer / dumppdf com o texto correto.
    c._doc.userencode = False
    c.setTitle(f"Ficha da OCI - {nome_paciente or 'Paciente'}"[:120])
    c.setAuthor("Penna Conversor")
    c.setSubject("Ficha da OCI (APAC)")

    # Uma página: o formulário inteiro em escala reduzida e, abaixo dele, o
    # bloco de OUTROS DADOS DA LINHA (quando a linha tem algo fora do
    # formulário) em vez de uma segunda página.
    escala = escala_da_ficha(modelo, ficha)
    nc = modelo.colunas_para(ficha["sobrescritas"])
    ultima = len(modelo.paginas) - 1
    numero = 1
    for i, (r1, r2) in enumerate(modelo.paginas):
        y_fim = desenhar_pagina(c, modelo, ficha["sobrescritas"], r1, r2,
                                 ficha["ocultar"], ficha["suprimir"], escala)
        if i == ultima and ficha["extras"]:
            desenhar_extras(c, modelo, ficha["extras"], escala,
                             y_fim - EXTRA_GAP, nc)
        cabecalho_rodape(c, modelo, numero)
        c.showPage()
        numero += 1
    c.save()
    return caminho


def exportar_fichas(df: Any, pasta_destino: Path,
                    progresso=None) -> List[Path]:
    """Gera UMA ficha PDF por linha do DataFrame na pasta escolhida.

    ``progresso(titulo, detalhe)`` é opcional (mesmo contrato da tela de
    carregamento usada pela UI). Devolve a lista de PDFs gravados.
    """
    exigir_reportlab()
    destino = Path(pasta_destino)
    destino.mkdir(exist_ok=True, parents=True)

    linhas: List[Dict[str, str]] = []
    for _, serie in df.iterrows():
        row = {str(chave): valor_texto(valor) for chave, valor in serie.to_dict().items()}
        if any(row.values()):
            linhas.append(row)

    total = len(linhas)
    usados: Set[str] = set()
    gerados: List[Path] = []
    for indice, row in enumerate(linhas, start=1):
        arquivo = nome_arquivo_ficha(row, indice, usados)
        caminho = gerar_ficha_pdf(row, destino / arquivo)
        gerados.append(caminho)
        if progresso is not None:
            progresso(f"Gerando fichas em PDF… {indice}/{total}",
                      row.get("Nome_Paciente") or caminho.name)
    return gerados
