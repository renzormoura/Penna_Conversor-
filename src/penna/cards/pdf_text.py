"""Fontes, medição e quebra de texto para o PDF."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._reportlab import TTFError, TTFont, REPORTLAB as _REPORTLAB, pdfmetrics

# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

_FONTES_ARQUIVO = {
    ("Calibri", False, False): "calibri.ttf",
    ("Calibri", True, False): "calibrib.ttf",
    ("Calibri", False, True): "calibrii.ttf",
    ("Calibri", True, True): "calibribi.ttf",
    ("Arial", False, False): "arial.ttf",
    ("Arial", True, False): "arialbd.ttf",
    ("Arial", False, True): "ariali.ttf",
    ("Arial", True, True): "arialbi.ttf",
}
_FONTE_CACHE: Dict[Tuple[str, bool, bool], str] = {}


def fonte(nome: str, negrito: bool, italico: bool) -> str:
    chave = (nome or "Calibri", bool(negrito), bool(italico))
    if chave in _FONTE_CACHE:
        return _FONTE_CACHE[chave]
    nome_pdf = "Helvetica"
    try:
        arquivo = _FONTES_ARQUIVO.get(chave) or _FONTES_ARQUIVO.get(
            (chave[0], chave[1], False))
        if arquivo:
            caminho = Path("C:/Windows/Fonts") / arquivo
            if caminho.exists():
                alias = f"Penna-{chave[0]}-{int(chave[1])}{int(chave[2])}"
                pdfmetrics.registerFont(TTFont(alias, str(caminho)))
                nome_pdf = alias
    except (OSError, TTFError):
        nome_pdf = "Helvetica" if not chave[1] else "Helvetica-Bold"
    _FONTE_CACHE[chave] = nome_pdf
    return nome_pdf


def preparar_texto(texto: str, nome_pdf: str) -> str:
    texto = texto.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    texto = "".join(ch for ch in texto if ord(ch) >= 32)
    if nome_pdf.startswith("Helvetica"):
        texto = texto.encode("cp1252", errors="replace").decode("cp1252")
    return texto


# ---------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------

def exigir_reportlab() -> None:
    if not _REPORTLAB:
        raise RuntimeError(
            "biblioteca 'reportlab' não instalada — instale com "
            "'pip install reportlab' para gerar as fichas em PDF."
        )


def celula_padrao() -> Dict[str, Any]:
    """Estilo padrão para célula alvo de sobrescrita sem estilo no template."""
    return {
        "valor": "",
        "fonte": ("Calibri", 11.0, False, False),
        "cor_fonte": "#000000",
        "al": (None, None, False),
        "fill": None,
        "bordas": {},
    }


def medir(texto: str, nome_pdf: str, tamanho: float) -> float:
    try:
        return pdfmetrics.stringWidth(texto, nome_pdf, tamanho)
    except (KeyError, ValueError):  # fonte não registrada
        return len(texto) * tamanho * 0.5


def quebrar(texto: str, nome_pdf: str, tamanho: float, largura: float) -> List[str]:
    """Quebra de linha por palavra (como o wrap_text do Excel)."""
    if not texto:
        return [""]
    linhas: List[str] = []
    atual = ""
    for palavra in texto.split(" "):
        tentativa = f"{atual} {palavra}".strip()
        if atual and medir(tentativa, nome_pdf, tamanho) > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
        while medir(atual, nome_pdf, tamanho) > largura and len(atual) > 1:
            # palavra única mais larga que a célula: corta
            corte = len(atual)
            while corte > 1 and medir(atual[:corte], nome_pdf, tamanho) > largura:
                corte -= 1
            linhas.append(atual[:corte])
            atual = atual[corte:]
    if atual or not linhas:
        linhas.append(atual)
    return linhas
