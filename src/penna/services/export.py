"""Caso de uso: exportar a planilha validada (TXT fiscal, remessa e fichas em PDF)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional

from penna import cards, remittance
from penna.layout import (
    carregar_planilha,
    competencia_da_planilha,
    exportar_txt,
    forcar_extensao_mes,
    nome_saida_sugerido,
)

log = logging.getLogger("penna.export")

Progresso = Callable[[str, str], None]


@dataclass(frozen=True)
class PlanoExportacao:
    """O que exportar e para onde (escolhido pelo usuário antes de começar)."""

    txt: bool
    fichas: bool
    destino_txt: Optional[Path] = None   # None = o nome sugerido, ao lado da planilha
    pasta_fichas: Optional[Path] = None

    @property
    def algo_a_exportar(self) -> bool:
        return self.txt or self.fichas


@dataclass(frozen=True)
class ResultadoExportacao:
    """O que foi gerado. A remessa nunca bloqueia: sua falha vira ``aviso_remessa``."""

    txt: Optional[Path] = None
    comprovante: Optional[Path] = None
    demonstrativo: Optional[Path] = None
    aviso_remessa: str = ""
    fichas: List[Path] = field(default_factory=list)


def converter_excel_para_txt(excel_path: Path, output_path: Path | None = None) -> Path:
    """Converte o Excel em TXT fiscal e devolve o caminho gerado.

    O mês dos formulários fixa o final do nome (``.JUN``); o nome em si é livre.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {excel_path}")
    df = carregar_planilha(excel_path)
    if df.empty:
        raise ValueError("A planilha está vazia. Nenhuma linha foi exportada.")
    competencia = competencia_da_planilha(df)
    if output_path is None:
        pasta = excel_path.parent / "Formatado"
        pasta.mkdir(exist_ok=True, parents=True)
        output_path = pasta / nome_saida_sugerido(excel_path, competencia)
    else:
        output_path = forcar_extensao_mes(Path(output_path), competencia)
        output_path.parent.mkdir(exist_ok=True, parents=True)
    exportar_txt(df, output_path)
    return output_path


def _registrar_remessa(txt: Path, df: Any) -> tuple:
    """Remessa (histórico, comprovante e demonstrativo): nunca bloqueia a exportação.

    Devolve ``(comprovante, demonstrativo, aviso)``; o erro vira aviso, mas não some,
    porque o histórico de APACs depende dele.
    """
    try:
        resumo = remittance.registrar_remessa(txt, df)
        return remittance.gerar_comprovante(resumo), remittance.gerar_demonstrativo(df), ""
    except Exception as exc:  # noqa: BLE001  fronteira: qualquer falha vira aviso ao usuário
        log.exception("registro da remessa falhou (exportacao segue)")
        return None, None, str(exc) or type(exc).__name__


def exportar(
    df: Any,
    excel_path: Path,
    plano: PlanoExportacao,
    competencia: str,
    extensao: str,
    progresso: Progresso,
) -> ResultadoExportacao:
    """Executa o plano: TXT, depois remessa, depois fichas. Roda na thread da tarefa."""
    txt = comprovante = demonstrativo = None
    aviso = ""
    if plano.txt:
        progresso(
            "Gerando o TXT fiscal…",
            f"extensão {extensao or '.txt'} — competência {competencia[:4]}/{competencia[4:6]}",
        )
        txt = converter_excel_para_txt(excel_path, plano.destino_txt)
        progresso("Registrando a remessa…", "comprovante, demonstrativo e histórico")
        comprovante, demonstrativo, aviso = _registrar_remessa(txt, df)
    fichas: List[Path] = []
    if plano.fichas:
        progresso("Gerando as fichas em PDF…", f"{len(df)} paciente(s)")
        fichas = cards.exportar_fichas(df, plano.pasta_fichas, progresso=progresso)
    return ResultadoExportacao(txt, comprovante, demonstrativo, aviso, fichas)
