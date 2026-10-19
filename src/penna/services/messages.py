"""Textos de status e de diálogo do fim da exportação (puros, testáveis sem Tk)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .export import ResultadoExportacao


def _competencia_legivel(competencia: str) -> str:
    return f"{competencia[:4]}/{competencia[4:6]}"


def rotulo_do_que_saiu(resultado: ResultadoExportacao) -> str:
    """O que foi gerado, só o que o usuário marcou (``APCEO26P.JUN + 3 ficha(s) PDF``)."""
    partes = []
    if resultado.txt is not None:
        partes.append(resultado.txt.name)
    if resultado.fichas:
        partes.append(f"{len(resultado.fichas)} ficha(s) PDF")
    return " + ".join(partes) or "nenhum arquivo"


def status_exportacao(
    resultado: ResultadoExportacao,
    n_avs: int,
    competencia: str,
    extensao: str,
    aviso_desativadas: str,
) -> str:
    """Linha do rodapé ao concluir a exportação."""
    mes = f" — competência {_competencia_legivel(competencia)}" if extensao else ""
    desativadas = f" — {aviso_desativadas.splitlines()[0]}" if aviso_desativadas else ""
    rotulo = rotulo_do_que_saiu(resultado)
    if n_avs:
        return f"Exportação com {n_avs} aviso(s){mes}: {rotulo}{desativadas}"
    return f"Exportação gerada{mes}: {rotulo}{desativadas}"


def mensagem_exportacao(
    resultado: ResultadoExportacao,
    n_avs: int,
    competencia: str,
    extensao: str,
    escolhido: Optional[Path],
    pasta_fichas: Optional[Path],
    aviso_desativadas: str,
    msg_avisos: str,
) -> str:
    """Diálogo final com os caminhos gerados e tudo o que o usuário precisa saber.

    ``msg_avisos``: texto com ``{n_avs}`` (vem do tema da interface).
    """
    mensagem = "Exportação concluída:"
    txt = resultado.txt
    if txt is not None:
        mensagem += f"\n\nTXT gerado:\n{txt}"
        if extensao:
            mensagem += (
                f"\n\nCompetência {_competencia_legivel(competencia)} — "
                f"extensão {extensao} fixada pelo mês dos formulários."
            )
        if escolhido is not None and txt.name != escolhido.name:
            mensagem += f"\nNome ajustado: {escolhido.name} → {txt.name}"
        if resultado.comprovante is not None:
            mensagem += f"\n\nComprovante:\n{resultado.comprovante}"
            if resultado.demonstrativo is not None:
                mensagem += f"\n\nDemonstrativo:\n{resultado.demonstrativo}"
        if resultado.aviso_remessa:
            # A remessa nunca bloqueia a exportação, mas o aviso não pode sumir:
            # o histórico de APACs depende dela.
            mensagem += f"\n\nAviso: histórico de remessa não registrado ({resultado.aviso_remessa})."
    if resultado.fichas:
        mensagem += f"\n\nFichas (PDF): {len(resultado.fichas)} arquivo(s) em:\n{pasta_fichas}"
    if n_avs:
        mensagem += f"\n\n{msg_avisos.format(n_avs=n_avs)}"
    if aviso_desativadas:
        mensagem += f"\n\n{aviso_desativadas}"
    return mensagem
