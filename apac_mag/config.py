r"""Carregamento da configuração do estabelecimento (penna_config.json).

Produto PENNA CONVERSOR. Modo EXE (frozen): o config do usuário é procurado
na pasta do EXE (standalone/portable) e em %LOCALAPPDATA%\PennaConversor
(instalado em Program Files, onde a pasta do EXE não é gravável). Se não
existir em nenhum, uma cópia de fábrica é MATERIALIZADA no primeiro local
gravável — garantindo que o cliente sempre tenha um arquivo editável.
Modo desenvolvimento: raiz do projeto e diretório de trabalho.
Ao não encontrar nada, aplica valores de fallback — o sistema continua
funcionando, mas emite um aviso para lembrar o operador de configurar.

Uso típico:
    from apac_mag.config import get_config, get_defaults, get_header

    cfg = get_config()
    defaults = get_defaults()   # dict com Cnes_Executante, Tipo_Apac, etc.
    header  = get_header()      # dict com orgao_responsavel, cgc, etc.
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Localização do arquivo de configuração
# ---------------------------------------------------------------------------

def _candidatos_editaveis() -> list[Path]:
    """Locais ONDE O USUÁRIO PODE EDITAR o config (apenas modo EXE/frozen).

    1. Pasta do EXE (modo standalone/portable — arquivo solto ao lado)
    2. %LOCALAPPDATA%\\PennaConversor\\ (modo instalado em Program Files,
       onde a pasta do EXE não é gravável)
    """
    if not getattr(sys, "frozen", False):
        return []
    candidatos = [Path(sys.executable).resolve().parent / "penna_config.json"]
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidatos.append(Path(localappdata) / "PennaConversor" / "penna_config.json")
    return candidatos


def _pode_escrever(destino: Path) -> bool:
    """True quando é possível criar o arquivo (e a pasta pai) em `destino`."""
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        teste = destino.parent / ".penna_teste_escrita"
        teste.write_bytes(b"t")
        teste.unlink()
        return True
    except Exception:
        return False


def _materializar_config(destino: Path) -> bool:
    """Copia o config de fábrica (bundle) para um local editável do usuário.

    Roda UMA vez, no primeiro uso do EXE, quando não existe config editável.
    Em caso de falha (sem permissão, disco cheio), degrada graciosamente:
    o sistema segue com o config embutido e devolve False.
    """
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        origem = Path(meipass) / "penna_config.json" if meipass else None
        if origem is not None and origem.exists():
            conteudo = origem.read_bytes()
        else:
            conteudo = json.dumps(_FALLBACK, ensure_ascii=False, indent=2).encode("utf-8")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        return True
    except Exception:
        return False


def _config_path() -> Path:
    """Retorna o caminho do penna_config.json.

    Modo EXE (frozen):
    1. Config editável do usuário: pasta do EXE → %LOCALAPPDATA%\\PennaConversor;
       se não existir em nenhum, materializa uma cópia de fábrica no primeiro
       local gravável (cliente sempre tem um arquivo para editar).
    2. Fallback: bundle (_MEIPASS) — config de fábrica somente leitura.

    Modo desenvolvimento:
    3. Raiz do projeto (um nível acima do pacote apac_mag/)
    4. Diretório de trabalho atual
    """
    editaveis = [p for p in _candidatos_editaveis() if p.exists()]
    if not editaveis:
        # Nenhum config editável ainda: materializa no primeiro local gravável
        for candidato in _candidatos_editaveis():
            if _pode_escrever(candidato) and _materializar_config(candidato):
                return candidato

    for p in editaveis:
        if p.exists():
            return p

    meipass = getattr(sys, "_MEIPASS", None)
    candidates: list[Path] = []
    if meipass:
        candidates.append(Path(meipass) / "penna_config.json")
    raiz_projeto = Path(__file__).resolve().parent.parent / "penna_config.json"
    candidates.append(raiz_projeto)
    candidates.append(Path.cwd() / "penna_config.json")
    for p in candidates:
        if p.exists():
            return p
    return raiz_projeto  # padrão para escrita futura


# ---------------------------------------------------------------------------
# Valores de fallback (usados quando o JSON não existe)
# ---------------------------------------------------------------------------

_FALLBACK: Dict[str, Any] = {
    "header": {
        "orgao_responsavel": "CENTRO DE ESPECIALIDADES OFTALCEOF",
        "cgc": "11111111000111",
        "destino": "SECRETARIA MUNICIPAL DE SAUDE DE MENDES",
        "destino_indicador": "M",
        "versao": "Versao 04.01",
        # Histórico por competência (AAAAMM -> "Versao XX.XX"): valores
        # de fábrica conferidos nos TXTs do programa antigo.
        "versao_por_mes": {},
        # Escolhas do usuário pela interface (sobrepondo o histórico).
        "versao_escolhas": {},
    },
    "defaults": {
        "Codigo_Municipio": "3302809",
        "Cns_Executante": "123456789012345",
        "Numero_Apac_Anterior": "000000000000/0",
        "Cnes_Solicitante": "4234316",
        "Cnes_Executante": "4234316",
        "Tipo_Apac": "003",
        "Nacionalidade": "10",
        "No_Prontuario": "",
        "Cns_Paciente": "",
        "Situacao_De_Rua": "N",
        "Complemento": "",
        "Motivo_Saida": "11",
        "Carater_Atend": "01",
        "Cod_Orgao_Emiss": "M330280001",
    },
}

# Cache interno (singleton por processo)
_cache: Dict[str, Any] | None = None


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache

    path = _config_path()
    if path.exists():
        try:
            _cache = json.loads(path.read_text(encoding="utf-8"))
            return _cache
        except Exception as exc:
            warnings.warn(
                f"penna_config.json encontrado em {path} mas não pôde ser lido ({exc}). "
                "Usando valores padrão.",
                stacklevel=3,
            )
    else:
        warnings.warn(
            f"penna_config.json não encontrado (buscado em {path}). "
            "Usando valores padrão do estabelecimento original. "
            "Crie o arquivo para configurar outro prestador.",
            stacklevel=3,
        )

    _cache = _FALLBACK
    return _cache


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_config() -> Dict[str, Any]:
    """Retorna a configuração completa (dict)."""
    return _load()


def get_header() -> Dict[str, str]:
    """Retorna a seção 'header' (orgao_responsavel, cgc, destino, etc.)."""
    return dict(_load().get("header", _FALLBACK["header"]))


def get_defaults() -> Dict[str, str]:
    """Retorna a seção 'defaults' (Cnes_Executante, Tipo_Apac, etc.)."""
    return dict(_load().get("defaults", _FALLBACK["defaults"]))


def _comp_chave(competencia: Any) -> str:
    """Normaliza a competência para a chave do mapa ('2026/06' -> '202606').

    '' quando o valor não identifica um mês (ex.: '000000').
    """
    try:
        from apac_mag.normalization import normalize_competence
        return normalize_competence(competencia)
    except Exception:
        return ""


def get_versao(competencia: Any = "") -> str:
    """Versão do cabeçalho '01#APAC...' para a competência informada.

    Ordem de resolução:
      1. header.versao_escolhas[AAAAMM] — escolha do usuário na interface;
      2. header.versao_por_mes[AAAAMM]   — histórico/mês (config de fábrica);
      3. header.versao                   — padrão automático.
    Sem competência identificada, usa o passo 3.
    """
    h = _load().get("header", _FALLBACK["header"])
    comp = _comp_chave(competencia)
    if comp:
        escolhas = h.get("versao_escolhas") or {}
        valor = str(escolhas.get(comp, "") or "").strip()
        if valor:
            return valor
        mapa = h.get("versao_por_mes") or {}
        valor = str(mapa.get(comp, "") or "").strip()
        if valor:
            return valor
    padrao = str(h.get("versao") or "").strip()
    return padrao or _FALLBACK["header"]["versao"]


def set_versao_mes(competencia: Any, versao: str) -> bool:
    """Grava (ou remove, com `versao=''`) a ESCOLHA do usuário para o mês.

    A escolha vai para header.versao_escolhas[AAAAMM] e sobrepõe o
    histórico (versao_por_mes) e o padrão (versao) enquanto existir;
    removê-la volta ao automático daquele mês. Persiste no
    penna_config.json editável e recarrega o cache — a escolha sobrevive
    a reinícios. Devolve False quando a competência é inválida ou o
    arquivo não pôde ser lido/gravado (nunca lança exceção).
    """
    comp = _comp_chave(competencia)
    if not comp:
        return False
    valor = str(versao or "").strip()
    try:
        path = _config_path()
        if path.exists():
            cfg = json.loads(path.read_text(encoding="utf-8"))
        else:
            cfg = json.loads(json.dumps(_FALLBACK))
        if not isinstance(cfg, dict):
            return False
        if not isinstance(cfg.get("header"), dict):
            cfg["header"] = dict(_FALLBACK["header"])
        mapa = cfg["header"].get("versao_escolhas")
        if not isinstance(mapa, dict):
            mapa = {}
            cfg["header"]["versao_escolhas"] = mapa
        if valor:
            mapa[comp] = valor
        else:
            mapa.pop(comp, None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return False
    reload()
    return True


def reload() -> None:
    """Força o recarregamento do arquivo (útil em testes)."""
    global _cache
    _cache = None
    _load()
