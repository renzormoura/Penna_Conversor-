r"""Onde ficam as remessas: ``<base>/<AAAAMM>/<AAAAMMDD_HHMMSS>/``.

    remessa.json         metadados da remessa (UTF-8)
    apacs.txt            números de APAC exportados (1 por linha)
    <arquivo>            cópia do TXT fiscal enviado
    Comprovante_*.PRN    comprovante no formato RELEXP
    Demonstrativo_*.TXT  demonstrativo no estilo R0201

O conteúdo tem dado pessoal em texto puro: ver ``docs/LGPD.md``.
"""
from __future__ import annotations

from pathlib import Path

from penna import paths

SEM_COMPETENCIA = "SEMCOMP"


def user_remittances_dir() -> Path:
    """``%USERPROFILE%\\Penna\\remessas``: estável entre sessões, mesmo no executável."""
    return Path.home() / "Penna" / "remessas"


def project_remittances_dir() -> Path:
    """``dados/remessas`` do projeto (no executável onefile é uma pasta temporária)."""
    return paths.data_dir() / "remessas"


def default_remittances_dir() -> Path:
    """Primeira pasta de remessas gravável.

    No executável onefile a pasta do projeto some ao fechar o programa, fazendo o
    histórico de APACs sumir entre sessões; por isso ele prefere o perfil do
    usuário. Rodando do código-fonte, prefere o projeto.
    """
    ordem = (
        (user_remittances_dir(), project_remittances_dir())
        if paths.is_frozen()
        else (project_remittances_dir(), user_remittances_dir())
    )
    for pasta in ordem:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue  # sem permissão: tenta a próxima
        return pasta
    return project_remittances_dir()
