"""Habilitações ativas de um CNES (tabela XUPSHA, por competência)."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from .dbf import ler_arquivo_dbf
from .tables import bundled_tables_dir, legacy_install_dir

_ARQUIVO = "XUPSHA.DBF"


def _candidatos(competencia: str, diretorio: Optional[Path]) -> List[Path]:
    """Onde procurar a XUPSHA: override, projeto e TXTCNES do programa original."""
    candidatos: List[Path] = []
    if diretorio:
        candidatos.append(Path(diretorio) / _ARQUIVO)
    candidatos.append(bundled_tables_dir() / _ARQUIVO)
    instalacao = legacy_install_dir()
    if instalacao.exists():
        pasta_txt = instalacao / "TXTCNES"
        if competencia:
            candidatos.append(pasta_txt / competencia / _ARQUIVO)
        candidatos.extend(sorted(pasta_txt.glob(f"*/{_ARQUIVO}"), reverse=True))
    return candidatos


def carregar_habilitacoes_cnes(
    cnes: str, competencia: str, diretorio: Optional[Path] = None
) -> Optional[Set[str]]:
    """Habilitações (HA) ativas do CNES na competência.

    ``None`` quando nenhuma XUPSHA existir: a regra fica desativada para não
    gerar falso positivo.
    """
    cnes7 = (cnes or "").zfill(7)[:7]
    registros = None
    for caminho in _candidatos(competencia, diretorio):
        if caminho.exists():
            registros = ler_arquivo_dbf(caminho)
            if registros is not None:
                break
    if not registros:
        return None
    ativas: Set[str] = set()
    for r in registros:
        if (r.get("UPSHA_UPS") or "").zfill(7)[:7] != cnes7:
            continue
        ini = (r.get("UPSHA_INI") or "").strip() or "000000"
        fim = (r.get("UPSHA_FIM") or "").strip() or "999999"
        ha = (r.get("UPSHA_HA") or "").strip()
        if ha and (not competencia or ini <= competencia <= fim):
            ativas.add(ha)
    return ativas
