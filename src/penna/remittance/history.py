"""Registro da remessa e histórico de APACs exportadas (alimenta o aviso 010084)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from penna.core import digits, resolve_row_value
from penna.layout import build_patient_lines, compute_checksum, header_competence

from .locations import SEM_COMPETENCIA, default_remittances_dir


def _numero13(valor: Any) -> str:
    return digits(valor).zfill(13)[:13]


def calcular_resumo(df: Any) -> Dict[str, Any]:
    """Contagens oficiais do TXT (como o RELEXP): competência, APACs, registros e checksum."""
    linhas: List[str] = []
    for _, serie in df.iterrows():
        linhas.extend(build_patient_lines(dict(serie)))
    return {
        "competencia": header_competence(linhas),
        "qtde_apacs": sum(1 for linha in linhas if linha.startswith("14")),
        "registros": len(linhas) + 1,  # + cabeçalho
        "checksum": compute_checksum(linhas),
    }


def registrar_remessa(
    txt_path: Path,
    df: Any,
    tipo: str = "1",
    substituida: str = "",
    pasta_base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Registra a remessa após a exportação (cópia do TXT + metadados + APACs).

    ``tipo``: 1-Normal, 2-Correção, 3-Substituição (padrão do RELEXP). Devolve o
    resumo gravado, que o comprovante usa.
    """
    txt_path = Path(txt_path)
    resumo = calcular_resumo(df)
    competencia = resumo.get("competencia") or SEM_COMPETENCIA
    base = Path(pasta_base) if pasta_base else default_remittances_dir()
    pasta = base / competencia / datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)

    copia: Path | str = pasta / txt_path.name
    try:
        shutil.copy2(txt_path, copia)
    except OSError:
        # Sem cópia o registro continua, mas não se mente no JSON: "copia" só
        # aponta para um arquivo que existe de fato.
        copia = ""

    numeros = [
        _numero13(n)
        for _, serie in df.iterrows()
        if (n := digits(resolve_row_value(dict(serie), "Numero_Apac")))
    ]
    (pasta / "apacs.txt").write_text("\n".join(numeros) + ("\n" if numeros else ""), encoding="cp1252")

    registro = {
        **resumo,
        "arquivo": txt_path.name,
        "copia": str(copia),
        "pasta": str(pasta),
        "datahora": datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "substituida": substituida,
        "origem": "Penna",
    }
    (pasta / "remessa.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return registro


def apacs_exportadas(pasta_base: Optional[Path] = None) -> Set[str]:
    """Números de APAC já exportados, de todas as competências.

    Lê os dois layouts de pasta: ``<base>/<pasta>/apacs.txt`` (antigo) e
    ``<base>/<competencia>/<carimbo>/apacs.txt`` (atual).
    """
    base = Path(pasta_base) if pasta_base else default_remittances_dir()
    numeros: Set[str] = set()
    if not base.exists():
        return numeros
    for padrao in ("*/apacs.txt", "*/*/apacs.txt"):
        for apacs in base.glob(padrao):
            try:
                linhas = apacs.read_text(encoding="cp1252", errors="replace").splitlines()
            except OSError:
                continue  # arquivo ilegível: as demais remessas continuam contando
            numeros.update(_numero13(linha) for linha in linhas if digits(linha))
    return numeros
