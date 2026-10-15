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

import copy
import json
import os
import sys
import tempfile
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
    except OSError:
        return False


def _materializar_config(destino: Path) -> bool:
    """Copia o config de fábrica (bundle) para um local editável do usuário.

    Roda UMA vez, no primeiro uso do EXE, quando não existe config editável.
    Em caso de falha (sem permissão, disco cheio), degrada graciosamente:
    o sistema segue com o config embutido e devolve False.
    """
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        origem = None
        for nome in ("penna_config.json", "penna_config.example.json"):
            if meipass and (Path(meipass) / nome).exists():
                origem = Path(meipass) / nome
                break
        if origem is not None:
            conteudo = origem.read_text(encoding="utf-8")
        else:
            conteudo = json.dumps(_FALLBACK, ensure_ascii=False, indent=2) + "\n"
        _gravar_atomico(destino, conteudo)
        return True
    except OSError:
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

# Histórico de fábrica da versão do cabeçalho por competência (AAAAMM ->
# "Versao XX.XX"), conferido nos TXTs do programa antigo. Versionado aqui
# (e espelhado em penna_config.example.json) para valer mesmo sem config.
_VERSAO_POR_MES_FABRICA: Dict[str, str] = {
    "202510": "Versao 03.18",
    "202511": "Versao 03.18",
    "202512": "Versao 03.18",
    "202601": "Versao 03.19",
    "202602": "Versao 03.21",
    "202603": "Versao 03.21",
    "202605": "Versao 04.01",
    "202606": "Versao 04.01",
}

# Valores de fábrica: identidade do estabelecimento é PLACEHOLDER INVÁLIDO
# de propósito — nunca um prestador real. Enquanto o config não for
# preenchido, a exportação é bloqueada (ver verificar_configuracao).
_NAO_CONFIGURADO = "NAO CONFIGURADO"

_FALLBACK: Dict[str, Any] = {
    "header": {
        "orgao_responsavel": _NAO_CONFIGURADO,
        "cgc": "00000000000000",
        "destino": _NAO_CONFIGURADO,
        "destino_indicador": "M",
        "versao": "Versao 04.01",
        "versao_por_mes": dict(_VERSAO_POR_MES_FABRICA),
        # Escolhas do usuário pela interface (sobrepondo o histórico).
        "versao_escolhas": {},
    },
    "defaults": {
        "Codigo_Municipio": "0000000",
        "Cns_Executante": "000000000000000",
        "Numero_Apac_Anterior": "000000000000/0",
        "Cnes_Solicitante": "0000000",
        "Cnes_Executante": "0000000",
        "Tipo_Apac": "003",
        "Nacionalidade": "10",
        "No_Prontuario": "",
        "Cns_Paciente": "",
        "Situacao_De_Rua": "N",
        "Complemento": "",
        "Motivo_Saida": "11",
        "Carater_Atend": "01",
        "Cod_Orgao_Emiss": _NAO_CONFIGURADO,
    },
}

# Campos que identificam o estabelecimento: com o valor de fábrica, o
# arquivo sairia com identidade inválida.
_CAMPOS_IDENTIDADE = (
    ("header", "orgao_responsavel"),
    ("header", "cgc"),
    ("header", "destino"),
    ("defaults", "Cnes_Executante"),
    ("defaults", "Cod_Orgao_Emiss"),
    ("defaults", "Codigo_Municipio"),
)


class ConfigInvalidaError(RuntimeError):
    """Config ausente, corrompido ou ainda com valores de fábrica."""

    def __init__(self, problemas: list[str]):
        self.problemas = list(problemas)
        super().__init__("\n".join(self.problemas))


# Cache interno (singleton por processo)
_cache: Dict[str, Any] | None = None
# Problema de leitura do arquivo ("" = leu bem); usado pelo gate de exportação.
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


def _load() -> Dict[str, Any]:
    global _cache, _erro_leitura
    if _cache is not None:
        return _cache

    path = _config_path()
    usuario: Dict[str, Any] = {}
    _erro_leitura = ""
    if path.exists():
        try:
            lido = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(lido, dict):
                raise ValueError("o conteúdo não é um objeto JSON")
            usuario = lido
        except (OSError, ValueError) as exc:  # JSONDecodeError é ValueError
            _erro_leitura = f"penna_config.json em {path} não pôde ser lido ({exc})."
            warnings.warn(f"{_erro_leitura} Usando valores de fábrica.", stacklevel=3)
    else:
        _erro_leitura = f"penna_config.json não encontrado (buscado em {path})."
        warnings.warn(f"{_erro_leitura} Usando valores de fábrica.", stacklevel=3)

    # header/defaults sempre completos: chave ausente cai no valor de fábrica.
    cfg = _mesclar(_FALLBACK, usuario)
    for secao in ("header", "defaults"):
        if not isinstance(cfg.get(secao), dict):
            cfg[secao] = copy.deepcopy(_FALLBACK[secao])
    _cache = cfg
    return _cache


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_config() -> Dict[str, Any]:
    """Retorna a configuração completa (dict), já mesclada com a de fábrica."""
    return _load()


def get_header() -> Dict[str, str]:
    """Retorna a seção 'header' (orgao_responsavel, cgc, destino, etc.)."""
    return dict(_load()["header"])


def get_defaults() -> Dict[str, str]:
    """Retorna a seção 'defaults' (Cnes_Executante, Tipo_Apac, etc.)."""
    return dict(_load()["defaults"])


def problemas_configuracao() -> list[str]:
    """Motivos pelos quais o config não serve para gerar o TXT (vazio = ok)."""
    cfg = _load()
    problemas: list[str] = []
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
    """Levanta ConfigInvalidaError quando o config não está pronto para exportar."""
    problemas = problemas_configuracao()
    if problemas:
        raise ConfigInvalidaError(problemas)


def _comp_chave(competencia: Any) -> str:
    """Normaliza a competência para a chave do mapa ('2026/06' -> '202606').

    '' quando o valor não identifica um mês (ex.: '000000').
    """
    from apac_mag.normalization import normalize_competence
    return normalize_competence(competencia)


def get_versao(competencia: Any = "") -> str:
    """Versão do cabeçalho '01#APAC...' para a competência informada.

    Ordem de resolução:
      1. header.versao_escolhas[AAAAMM] — escolha do usuário na interface;
      2. header.versao_por_mes[AAAAMM]   — histórico/mês (config de fábrica);
      3. header.versao                   — padrão automático.
    Sem competência identificada, usa o passo 3.
    """
    h = _load()["header"]
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


def _gravar_atomico(path: Path, conteudo: str) -> None:
    """Grava via arquivo temporário na mesma pasta + os.replace (tudo ou nada)."""
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
            cfg = copy.deepcopy(_FALLBACK)
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
        _gravar_atomico(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError):
        return False
    reload()
    return True


def reload() -> None:
    """Força o recarregamento do arquivo (útil em testes)."""
    global _cache
    _cache = None
    _load()
