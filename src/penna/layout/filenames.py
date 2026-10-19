"""Nome do arquivo de saída: o final é fixo pelo mês da competência (``APCEO26P.JUN``)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from penna.core import normalize_competence

MESES_SIGLA = {
    "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR", "05": "MAI", "06": "JUN",
    "07": "JUL", "08": "AGO", "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ",
}


def sigla_mes_competencia(competencia: Any) -> str:
    """``'202606'`` -> ``'JUN'``; vazio quando a competência não identifica o mês."""
    comp = normalize_competence(competencia)
    return MESES_SIGLA.get(comp[4:6], "") if comp else ""


def extensao_mes_competencia(competencia: Any) -> str:
    """``'202606'`` -> ``'.JUN'``: o final fixo do nome do arquivo."""
    sigla = sigla_mes_competencia(competencia)
    return f".{sigla}" if sigla else ""


def forcar_extensao_mes(caminho: Any, competencia: Any) -> Path:
    """Garante que o arquivo termine com a extensão do mês (``meu.txt`` -> ``meu.JUN``).

    O nome é livre; sem competência identificada o caminho é devolvido intacto.
    """
    path = Path(caminho)
    extensao = extensao_mes_competencia(competencia)
    if not extensao:
        return path
    try:
        return path.with_suffix(extensao)
    except ValueError:
        return path.parent / (path.name + extensao)


def normalize_output_name(excel_path: Path) -> str:
    """Nome base sugerido a partir da planilha (``base exemplo.xlsx`` tem nome próprio)."""
    if excel_path.name.lower() == "base exemplo.xlsx":
        return "base_exemplo_formatado.txt"
    return f"{excel_path.stem}_formatado.txt"


def nome_saida_sugerido(excel_path: Path, competencia: str = "") -> str:
    """Nome sugerido no diálogo Salvar: nome livre + extensão do mês (ou ``.txt``)."""
    nome = normalize_output_name(excel_path)
    extensao = extensao_mes_competencia(competencia)
    return str(Path(nome).with_suffix(extensao)) if extensao else nome
