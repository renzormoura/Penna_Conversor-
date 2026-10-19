r"""Acesso às tabelas SIA/SIGTAP (DBF/ZBF) com cache e ordem de busca padrão.

Ordem de busca de ``NOME``:

1. pasta do programa original (``PENNA_APAC_DIR``, padrão ``C:/APAC``) ou a
   pasta ``diretorio`` informada: ``NOME.DBF`` e ``NOME.ZBF``;
2. backups mensais dessa pasta: ``BACKUP/<AAAAMM>/NOME.ZBF`` (mais recente);
3. cópia versionada no projeto: ``dados/bases_sia/NOME.DBF`` ou ``NOME.ZBF``;
4. tabelas parseadas do ZIP SIGTAP (somente com ``sigtap_competencia``).

O cache é por (tabela, caminho, mtime): o arquivo só é relido quando muda.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from penna import paths

from .dbf import Registro, ler_arquivo_dbf, ler_zbf
from .selection import filtrar_por_competencia
from .sigtap import carregar_sigtap_competencia

_SUFIXOS = (".DBF", ".dbf", ".ZBF", ".zbf")
_TABELAS_SIGTAP = frozenset({"S_PAREGR", "S_PAPA", "S_PAHA", "S_PA", "S_CID"})
_CAMPO_COMPETENCIA = {"S_PAREGR": "REG_CMP", "S_PAPA": "PAPA_CMP", "S_PAHA": "PAHA_CMP"}


def legacy_install_dir() -> Path:
    """Instalação do programa original (``PENNA_APAC_DIR``, padrão ``C:/APAC``)."""
    return Path(os.environ.get("PENNA_APAC_DIR", "C:/APAC"))


def bundled_tables_dir() -> Path:
    """Cópia versionada das tabelas dentro do projeto."""
    return paths.reference_tables_dir()


_cache: Dict[tuple, Any] = {}

# Candidatos por (tabela, pastas): chave -> (assinatura das pastas, caminhos).
# Evita refazer milhares de globs (BACKUP/*/*.ZBF) a cada carregar_tabela.
_caminhos_cache: Dict[tuple, tuple] = {}


def _mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _assinatura_pastas(pastas: List[Path]) -> tuple:
    """Muda sempre que entra ou sai arquivo (ou mês de BACKUP) das pastas.

    Criar/apagar um arquivo altera o mtime do diretório e invalida o cache de
    candidatos; alterar só o conteúdo não muda a lista (o ``carregar_tabela``
    confere o mtime por caminho).
    """
    partes: List[Any] = []
    for pasta in pastas:
        partes.append(_mtime(pasta))
        try:
            meses = tuple((d.name, _mtime(d)) for d in sorted((pasta / "BACKUP").iterdir()) if d.is_dir())
        except OSError:
            meses = ()
        partes.append(meses)
    return tuple(partes)


def _caminhos_candidatos(nome: str, diretorio: Optional[Path]) -> List[Path]:
    """Caminhos possíveis da tabela, por prioridade (memorizado por pastas)."""
    nome = nome.upper()
    pastas = [Path(diretorio)] if diretorio else [legacy_install_dir(), bundled_tables_dir()]
    chave = (nome, tuple(str(p) for p in pastas))
    assinatura = _assinatura_pastas(pastas)
    memo = _caminhos_cache.get(chave)
    if memo is not None and memo[0] == assinatura:
        return memo[1]
    candidatos: List[Path] = []
    for pasta in pastas:
        candidatos.extend(pasta / (nome + sufixo) for sufixo in _SUFIXOS)
        backup = pasta / "BACKUP"
        if backup.exists():  # backups mensais, mais recente primeiro
            for ext in ("ZBF", "zbf"):
                candidatos.extend(sorted(backup.glob(f"*/{nome}.{ext}"), reverse=True))
    _caminhos_cache[chave] = (assinatura, candidatos)
    return candidatos


def carregar_tabela(
    nome: str,
    diretorio: Optional[Path] = None,
    sigtap_competencia: Optional[str] = None,
) -> Optional[List[Registro]]:
    """Registros da tabela (``S_PA``, ``S_PAPA``, ``S_CEP``...) ou ``None`` se não achada.

    Nunca lança por tabela ausente ou corrompida: o chamador desativa a regra.
    """
    chave_base = ("tabela", str(Path(diretorio) if diretorio else ""), nome.upper())
    for caminho in _caminhos_candidatos(nome, diretorio):
        if not caminho.exists():
            continue
        mtime = _mtime(caminho)
        if mtime is None:
            continue
        chave = chave_base + (str(caminho),)
        em_cache = _cache.get(chave)
        if em_cache is not None and em_cache[0] == mtime:
            return em_cache[1]
        registros = ler_zbf(caminho) if caminho.suffix.lower() == ".zbf" else ler_arquivo_dbf(caminho)
        if registros:
            _cache[chave] = (mtime, registros)
            return registros

    if sigtap_competencia and nome.upper() in _TABELAS_SIGTAP:
        # O ZIP já deve estar em disco: o download é responsabilidade da UI.
        dados = carregar_sigtap_competencia(sigtap_competencia)
        registros = dados.get(nome.upper()) if dados else None
        if registros:
            return registros
    return None


def competencia_disponivel_local(competencia: str) -> bool:
    """``True`` se S_PAREGR, S_PAPA e S_PAHA locais cobrem a competência.

    A UI usa isto para decidir se precisa oferecer o download do SIGTAP.
    """
    for nome, campo in _CAMPO_COMPETENCIA.items():
        registros = carregar_tabela(nome)
        if registros is None or not filtrar_por_competencia(registros, campo, competencia):
            return False
    return True
