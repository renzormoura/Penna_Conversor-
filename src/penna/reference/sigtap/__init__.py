"""SIGTAP (Tabela Unificada do DATASUS): download, cache e conversão para o esquema DBF."""
from .ftp import listar_competencias_ftp
from .store import (
    baixar_competencia,
    carregar_sigtap_competencia,
    limpar_cache_memoria,
    listar_competencias_cache,
)

__all__ = [
    "baixar_competencia",
    "carregar_sigtap_competencia",
    "limpar_cache_memoria",
    "listar_competencias_cache",
    "listar_competencias_ftp",
]
