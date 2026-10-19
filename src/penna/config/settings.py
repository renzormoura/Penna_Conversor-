r"""Configuração do estabelecimento (``penna_config.json``).

Três responsabilidades, nesta ordem no arquivo:

1. **Localização** do arquivo, no código-fonte e no executável.
2. **Carga** mesclada chave a chave com os valores de fábrica (cache por processo).
3. **Validação** (gate de exportação) e **gravação atômica** das escolhas do usuário.

Executável: o arquivo editável é procurado ao lado do ``.exe`` e em
``%LOCALAPPDATA%\PennaConversor``; se não existir, uma cópia de fábrica é
materializada no primeiro local gravável.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List

from penna import paths
from penna.core import normalize_competence

from .factory import CAMPOS_IDENTIDADE as _CAMPOS_IDENTIDADE
from .factory import FALLBACK as _FALLBACK
from .factory import VERSAO_POR_MES_FABRICA as _VERSAO_POR_MES_FABRICA  # noqa: F401  (re-export p/ testes)

CONFIG_FILENAME = "penna_config.json"
EXAMPLE_FILENAME = "penna_config.example.json"


class ConfigInvalidaError(RuntimeError):
    """Config ausente, corrompido ou ainda com valores de fábrica."""

    def __init__(self, problemas: List[str]):
        self.problemas = list(problemas)
        super().__init__("\n".join(self.problemas))


# ==============================================================================
# 1. Localização
# ==============================================================================

def _candidatos_editaveis() -> List[Path]:
    """Locais onde o usuário pode editar o config (somente no executável)."""
    if not paths.is_frozen():
        return []
    return [paths.executable_dir() / CONFIG_FILENAME, paths.user_data_dir() / CONFIG_FILENAME]


def _pode_escrever(destino: Path) -> bool:
    """``True`` quando é possível criar o arquivo (e a pasta pai) em ``destino``."""
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        teste = destino.parent / ".penna_teste_escrita"
        teste.write_bytes(b"t")
        teste.unlink()
    except OSError:
        return False
    return True


def _materializar_config(destino: Path) -> bool:
    """Copia o config de fábrica embutido para um local editável do usuário.

    Roda uma vez, no primeiro uso do executável. Em falha (sem permissão,
    disco cheio) devolve ``False`` e o sistema segue com os valores de fábrica.
    """
    try:
        embutido = next(
            (p for p in (paths.project_root() / CONFIG_FILENAME, paths.project_root() / EXAMPLE_FILENAME)
             if p.exists()),
            None,
        )
        if embutido is not None:
            conteudo = embutido.read_text(encoding="utf-8")
        else:
            conteudo = json.dumps(_FALLBACK, ensure_ascii=False, indent=2) + "\n"
        _gravar_atomico(destino, conteudo)
    except OSError:
        return False
    return True


def _config_path() -> Path:
    """Caminho do ``penna_config.json`` em uso.

    Executável: config editável (ao lado do ``.exe`` ou em ``%LOCALAPPDATA%``),
    materializado se ainda não existir; depois o embutido (somente leitura).
    Código-fonte: raiz do projeto, depois o diretório de trabalho.
    """
    editaveis = [p for p in _candidatos_editaveis() if p.exists()]
    if not editaveis:
        for candidato in _candidatos_editaveis():
            if _pode_escrever(candidato) and _materializar_config(candidato):
                return candidato
    if editaveis:
        return editaveis[0]

    raiz = paths.project_root() / CONFIG_FILENAME
    for candidato in (raiz, Path.cwd() / CONFIG_FILENAME):
        if candidato.exists():
            return candidato
    return raiz  # destino padrão para escrita futura


# ==============================================================================
# 2. Carga (cache por processo)
# ==============================================================================

_cache: Dict[str, Any] | None = None
# Problema ao ler o arquivo ("" = leu bem); alimenta o gate de exportação.
_erro_leitura: str = ""


def _mesclar(fabrica: Dict[str, Any], usuario: Any) -> Dict[str, Any]:
    """Mescla chave a chave: o que o usuário definiu vence a fábrica."""
    resultado = copy.deepcopy(fabrica)
    if not isinstance(usuario, dict):
        return resultado
    for chave, valor in usuario.items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = _mesclar(resultado[chave], valor)
        else:
            resultado[chave] = valor
    return resultado


def _ler_arquivo(path: Path) -> Dict[str, Any]:
    """Conteúdo do JSON do usuário; registra em ``_erro_leitura`` se faltar ou estiver ruim."""
    global _erro_leitura
    _erro_leitura = ""
    if not path.exists():
        _erro_leitura = f"{CONFIG_FILENAME} não encontrado (buscado em {path})."
    else:
        try:
            lido = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(lido, dict):
                raise ValueError("o conteúdo não é um objeto JSON")
            return lido
        except (OSError, ValueError) as exc:  # JSONDecodeError é ValueError
            _erro_leitura = f"{CONFIG_FILENAME} em {path} não pôde ser lido ({exc})."
    warnings.warn(f"{_erro_leitura} Usando valores de fábrica.", stacklevel=4)
    return {}


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        cfg = _mesclar(_FALLBACK, _ler_arquivo(_config_path()))
        # header/defaults sempre completos, mesmo com seção de tipo errado.
        for secao in ("header", "defaults"):
            if not isinstance(cfg.get(secao), dict):
                cfg[secao] = copy.deepcopy(_FALLBACK[secao])
        _cache = cfg
    return _cache


def reload() -> None:
    """Descarta o cache e relê o arquivo (testes e após gravar)."""
    global _cache
    _cache = None
    _load()


def get_config() -> Dict[str, Any]:
    """Configuração completa, já mesclada com a de fábrica."""
    return _load()


def get_header() -> Dict[str, Any]:
    """Seção ``header`` (órgão, CGC, destino, versão...)."""
    return dict(_load()["header"])


def get_defaults() -> Dict[str, str]:
    """Seção ``defaults`` (CNES, tipo de APAC, município...)."""
    return dict(_load()["defaults"])


# ==============================================================================
# 3. Validação e gravação
# ==============================================================================

def problemas_configuracao() -> List[str]:
    """Motivos pelos quais o config não serve para gerar o TXT (vazio = ok)."""
    cfg = _load()
    problemas: List[str] = []
    if _erro_leitura:
        problemas.append(_erro_leitura)
    for secao, campo in _CAMPOS_IDENTIDADE:
        valor = str(cfg[secao].get(campo, "") or "").strip()
        padrao = str(_FALLBACK[secao].get(campo, "") or "").strip()
        digitos = valor.replace(".", "").replace("/", "").replace("-", "")
        if not valor or valor == padrao or (digitos.isdigit() and not digitos.strip("0")):
            problemas.append(f"{secao}.{campo} não foi preenchido (valor: {valor or 'vazio'}).")
    return problemas


def verificar_configuracao() -> None:
    """Levanta :class:`ConfigInvalidaError` se o config não está pronto para exportar."""
    problemas = problemas_configuracao()
    if problemas:
        raise ConfigInvalidaError(problemas)


def _gravar_atomico(path: Path, conteudo: str) -> None:
    """Grava via arquivo temporário na mesma pasta + ``os.replace`` (tudo ou nada)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as arq:
            arq.write(conteudo)
            arq.flush()
            os.fsync(arq.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- Versão do cabeçalho "01#APAC..." por competência -------------------------

def get_versao(competencia: Any = "") -> str:
    """Versão do cabeçalho para a competência informada.

    Ordem: ``header.versao_escolhas[AAAAMM]`` (escolha do usuário) >
    ``header.versao_por_mes[AAAAMM]`` (histórico de fábrica) > ``header.versao``
    (padrão). Sem competência identificada, vale o padrão.
    """
    h = _load()["header"]
    comp = normalize_competence(competencia)
    if comp:
        for mapa in (h.get("versao_escolhas"), h.get("versao_por_mes")):
            valor = str((mapa or {}).get(comp, "") or "").strip()
            if valor:
                return valor
    return str(h.get("versao") or "").strip() or _FALLBACK["header"]["versao"]


def set_versao_mes(competencia: Any, versao: str) -> bool:
    """Grava (ou remove, com ``versao=''``) a escolha do usuário para o mês.

    Persiste em ``header.versao_escolhas[AAAAMM]`` no config editável e
    recarrega o cache. Devolve ``False`` se a competência é inválida ou o
    arquivo não pôde ser lido ou gravado (nunca lança).
    """
    comp = normalize_competence(competencia)
    if not comp:
        return False
    valor = str(versao or "").strip()
    try:
        path = _config_path()
        cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(_FALLBACK)
        if not isinstance(cfg, dict):
            return False
        if not isinstance(cfg.get("header"), dict):
            cfg["header"] = dict(_FALLBACK["header"])
        escolhas = cfg["header"].get("versao_escolhas")
        if not isinstance(escolhas, dict):
            escolhas = cfg["header"]["versao_escolhas"] = {}
        if valor:
            escolhas[comp] = valor
        else:
            escolhas.pop(comp, None)
        _gravar_atomico(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError):
        return False
    reload()
    return True
