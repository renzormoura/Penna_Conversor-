"""Leitores dos formatos binários das bases SIA: DBF III e backup ``.ZBF`` (zip).

Nenhuma função lança por arquivo ausente ou corrompido: devolvem ``None`` e o
chamador desativa a regra correspondente (nunca falso positivo).
"""
from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional

Registro = Dict[str, str]
_ENCODING = "cp850"


def ler_dbf(data: bytes) -> Optional[List[Registro]]:
    """Registros de um DBF III a partir dos bytes; ``None`` se inválido."""
    try:
        if len(data) < 33 or data[:1] != b"\x03":
            return None
        nrec = struct.unpack("<I", data[4:8])[0]
        hlen = struct.unpack("<H", data[8:10])[0]
        rlen = struct.unpack("<H", data[10:12])[0]
        if hlen < 33 or rlen <= 1:
            return None
        campos: List[tuple] = []
        i = 32
        while i < hlen and data[i] != 0x0D:
            nome = data[i : i + 11].split(b"\0")[0].decode("ascii", "replace")
            tamanho = data[i + 16]
            if tamanho <= 0:
                return None
            campos.append((nome, tamanho))
            i += 32
        if not campos:
            return None
        registros: List[Registro] = []
        off = hlen
        for _ in range(nrec):
            rec = data[off : off + rlen]
            if len(rec) < rlen or rec[0:1] not in (b" ", b"*"):
                break
            valores: Registro = {}
            pos = 1
            for nome, tamanho in campos:
                valores[nome] = rec[pos : pos + tamanho].decode(_ENCODING, "replace").strip()
                pos += tamanho
            registros.append(valores)
            off += rlen
        return registros
    except (struct.error, ValueError, IndexError):
        return None  # DBF truncado ou corrompido: tabela indisponível


def ler_arquivo_dbf(path: Path) -> Optional[List[Registro]]:
    """Registros de um arquivo ``.DBF``; ``None`` se ilegível."""
    try:
        return ler_dbf(Path(path).read_bytes())
    except OSError:
        return None


def ler_zbf(path: Path) -> Optional[List[Registro]]:
    """Registros de um backup ``.ZBF`` (zip com o DBF dentro); ``None`` se ilegível."""
    try:
        with zipfile.ZipFile(path) as z:
            return ler_dbf(z.read(z.namelist()[0]))
    except (zipfile.BadZipFile, OSError, IndexError, KeyError, RuntimeError,
            NotImplementedError, zlib.error):
        return None
