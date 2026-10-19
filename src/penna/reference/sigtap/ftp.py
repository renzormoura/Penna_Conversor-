r"""Acesso de rede ao FTP público do DATASUS (Tabela Unificada do SIGTAP).

    ftp://ftp2.datasus.gov.br/pub/sistemas/tup/downloads/
    TabelaUnificada_AAAAMM_vAAMMDDHHMM.zip  (~2 MB cada)

Só rede: o cache em disco fica em :mod:`penna.reference.sigtap.store`. Falhas de
rede nunca lançam; devolvem ``[]``/``None`` e o chamador desativa a regra.
"""
from __future__ import annotations

import ftplib
import io
import re
from typing import Callable, List, Optional

FTP_HOST = "ftp2.datasus.gov.br"
FTP_DIR = "/pub/sistemas/tup/downloads"
_RE_NOME = re.compile(r"TabelaUnificada_(\d{6})_v\d+\.zip", re.IGNORECASE)

Progresso = Callable[[int, int], None]


def _listar_nomes(timeout: int) -> List[str]:
    """Nomes dos arquivos no diretório do FTP (``LIST``)."""
    with ftplib.FTP(timeout=timeout) as ftp:
        ftp.connect(FTP_HOST, timeout=timeout)
        ftp.login()
        ftp.cwd(FTP_DIR)
        linhas: List[str] = []
        ftp.retrlines("LIST", linhas.append)
    return [partes[-1] for partes in (linha.split() for linha in linhas) if partes]


def listar_competencias_ftp(timeout: int = 10) -> List[str]:
    """Competências (AAAAMM) disponíveis no FTP, da mais recente para a mais antiga."""
    try:
        nomes = _listar_nomes(timeout)
    except ftplib.all_errors:
        return []
    return sorted({m[1] for nome in nomes if (m := _RE_NOME.match(nome))}, reverse=True)


def nome_arquivo_ftp(competencia: str, timeout: int = 15) -> Optional[str]:
    """Nome exato do ZIP da competência no FTP, ou ``None``."""
    try:
        nomes = _listar_nomes(timeout)
    except ftplib.all_errors:
        return None
    for nome in nomes:
        m = _RE_NOME.match(nome)
        if m and m[1] == competencia:
            return nome
    return None


def baixar_zip(nome_ftp: str, callback: Optional[Progresso] = None, timeout: int = 30) -> Optional[bytes]:
    """Conteúdo do ZIP ``nome_ftp``; ``callback(recebidos, total)`` durante o download."""
    buf = io.BytesIO()
    try:
        with ftplib.FTP(timeout=timeout) as ftp:
            ftp.connect(FTP_HOST, timeout=timeout)
            ftp.login()
            ftp.cwd(FTP_DIR)
            try:
                ftp.sendcmd("TYPE I")
                total = int(ftp.sendcmd(f"SIZE {nome_ftp}").split()[-1])
            except (ftplib.all_errors, ValueError, IndexError):
                total = 0
            recebidos = 0

            def _bloco(dados: bytes) -> None:
                nonlocal recebidos
                buf.write(dados)
                recebidos += len(dados)
                if callback:
                    callback(recebidos, total)

            ftp.retrbinary(f"RETR {nome_ftp}", _bloco, blocksize=65536)
    except ftplib.all_errors:
        return None
    return buf.getvalue()
