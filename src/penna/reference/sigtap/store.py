"""Cache do SIGTAP: ZIPs em disco (reuso offline) e tabelas parseadas em memória."""
from __future__ import annotations

import re
import threading
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

from penna import paths

from . import ftp, parser
from .layouts import ler_tabela

Tabelas = Dict[str, List[Dict[str, str]]]

# Abaixo disto o arquivo é um download incompleto, não um ZIP válido.
TAMANHO_MINIMO_ZIP = 100_000

_cache_memoria: Dict[str, Tabelas] = {}
_cache_lock = threading.Lock()


def _dir_cache() -> Path:
    """Pasta onde os ZIPs baixados ficam guardados (criada sob demanda)."""
    pasta = paths.executable_dir() / "dados" / "sigtap_cache"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _caminho_zip(competencia: str) -> Path:
    return _dir_cache() / f"TabelaUnificada_{competencia}.zip"


def _zip_valido(path: Path) -> bool:
    return path.exists() and path.stat().st_size > TAMANHO_MINIMO_ZIP


def listar_competencias_cache() -> List[str]:
    """Competências já baixadas em disco (AAAAMM), da mais recente para a mais antiga."""
    comps = {
        m[1]
        for f in _dir_cache().glob("TabelaUnificada_??????.zip")
        if (m := re.match(r"TabelaUnificada_(\d{6})\.zip", f.name, re.IGNORECASE))
    }
    return sorted(comps, reverse=True)


def baixar_competencia(
    competencia: str,
    callback: Optional[Callable[[int, int], None]] = None,
    timeout: int = 30,
) -> Optional[Path]:
    """Garante o ZIP da competência em disco e devolve o caminho (``None`` se falhar)."""
    destino = _caminho_zip(competencia)
    if _zip_valido(destino):
        return destino
    nome = ftp.nome_arquivo_ftp(competencia)
    if not nome:
        return None
    conteudo = ftp.baixar_zip(nome, callback=callback, timeout=timeout)
    if conteudo is None:
        return None
    destino.write_bytes(conteudo)
    return destino


def carregar_sigtap_competencia(
    competencia: str,
    callback_download: Optional[Callable[[int, int], None]] = None,
) -> Optional[Tabelas]:
    """Tabelas SIGTAP da competência no esquema DBF (baixa o ZIP se preciso).

    Chaves: ``S_PAREGR``, ``S_PAPA``, ``S_PAHA``, ``S_PA``, ``S_CID``. ``None``
    se o ZIP não estiver disponível ou for inválido.
    """
    with _cache_lock:
        if competencia in _cache_memoria:
            return _cache_memoria[competencia]

    zip_path = _caminho_zip(competencia)
    if not _zip_valido(zip_path):
        zip_path = baixar_competencia(competencia, callback=callback_download) or zip_path
    if not _zip_valido(zip_path):
        return None

    try:
        with zipfile.ZipFile(zip_path) as zf:
            def tabela(nome: str, parsear):
                linhas, layout = ler_tabela(zf, nome)
                return parsear(linhas, competencia, layout)

            resultado: Tabelas = {
                "S_PAREGR": tabela("rl_procedimento_regra_cond", parser.parsear_regras_condicionadas),
                "S_PAPA": tabela("rl_procedimento_compativel", parser.parsear_pares_compativeis),
                "S_PAHA": tabela("rl_procedimento_habilitacao", parser.parsear_habilitacoes),
                "S_PA": tabela("tb_procedimento", parser.parsear_procedimentos),
                "S_CID": tabela("tb_cid", parser.parsear_cids),
            }
    except (zipfile.BadZipFile, OSError):
        return None

    with _cache_lock:
        _cache_memoria[competencia] = resultado
    return resultado


def limpar_cache_memoria() -> None:
    """Libera o cache em memória (ao trocar de competência na UI)."""
    with _cache_lock:
        _cache_memoria.clear()
