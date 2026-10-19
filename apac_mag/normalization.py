"""Funções puras de normalização e formatação de strings.

Este módulo é a única fonte de verdade para helpers de string do projeto.
Todos os outros módulos (gerador, validador, remessa) devem
importar daqui — nunca redefinir localmente.

Regras:
- Nenhuma função lança exceção: valores inválidos retornam string vazia ou
  o padrão especificado.
- Nenhuma função tem efeito colateral (I/O, estado global).
- Compatível com Python 3.10+.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict


# ==============================================================================
# Primitivas de conversão
# ==============================================================================

def text(value: Any) -> str:
    """Converte qualquer valor para str limpa (sem None/NaN/espaços extras)."""
    if value is None:
        return ""
    # pandas NaN / float NaN
    if isinstance(value, float):
        import math
        if math.isnan(value):
            return ""
    s = str(value).strip()
    # pandas stringifica NaN como "nan" e None como "None"
    if s in ("nan", "None", "NaT"):
        return ""
    return s


def digits(value: Any) -> str:
    """Remove todos os caracteres não numéricos."""
    return re.sub(r"\D", "", text(value))


def text_upper(value: Any) -> str:
    """Maiúsculas apenas para ASCII (A-Z); acentos preservados.

    Comportamento do programa antigo APAC-MAG, confirmado no arquivo real
    APCEO26P.JUN (ex.: 'JO\\xe3O VIEIRA' — 'ã' não vira 'Ã').
    """
    return "".join(ch.upper() if ch.isascii() else ch for ch in text(value))


# ==============================================================================
# Padding (alinhamento de campos de largura fixa)
# ==============================================================================

def pad_right(value: Any, width: int, fill: str = " ") -> str:
    """Alinha à esquerda, trunca ou preenche com `fill` até `width` chars."""
    s = text(value)
    return s[:width].ljust(width, fill)


def pad_left(value: Any, width: int, fill: str = "0") -> str:
    """Alinha à direita, trunca ou preenche com `fill` até `width` chars."""
    s = text(value)
    return s[:width].rjust(width, fill)


# ==============================================================================
# Normalização de campos de domínio
# ==============================================================================

def normalize_cpf(value: Any) -> str:
    """CPF: 11 dígitos sem pontuação; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(11) if raw else ""


def normalize_cns(value: Any) -> str:
    """CNS: 15 dígitos; vazio se não houver dígitos."""
    raw = digits(value)
    return raw.zfill(15) if raw else ""


def normalize_code(value: Any, width: int) -> str:
    """Código numérico: zero-padding à esquerda até `width`."""
    raw = digits(value)
    return raw.zfill(width) if raw else ""


def _data_real(aaaammdd: str) -> bool:
    try:
        date(int(aaaammdd[:4]), int(aaaammdd[4:6]), int(aaaammdd[6:8]))
        return True
    except ValueError:
        return False


def normalize_date(value: Any) -> str:
    """Normaliza data para AAAAMMDD (formato do layout). Vazio se invalida.

    Fonte unica para gerador, validador e leitura da planilha. Aceita:
    - datetime / date nativo
    - ISO, com ou sem hora ('2026-06-15', '2026-06-15 00:00:00', '...T10:30')
    - DD/MM/AAAA (separadores '/', '-' ou '.')
    - DDMMAAAA ('24011958') e AAAAMMDD ('19580124'), 8 digitos
    - AAAAMM (6 digitos): assume dia 01
    Datas que nao existem no calendario (31/02) devolvem ''.
    """
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m%d")
    raw_text = text(value)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$", raw_text)
    if m:
        candidato = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
        return candidato if _data_real(candidato) else ""
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$", raw_text)
    if m:
        candidato = f"{m.group(3)}{int(m.group(2)):02d}{int(m.group(1)):02d}"
        return candidato if _data_real(candidato) else ""
    raw = digits(raw_text)
    if len(raw) == 8:
        # AAAAMMDD primeiro (layout); senao DDMMAAAA.
        if raw[:2] in ("19", "20") and _data_real(raw):
            return raw
        ddmm = raw[4:] + raw[2:4] + raw[:2]
        if ddmm[:2] in ("18", "19", "20", "21") and _data_real(ddmm):
            return ddmm
        return ""
    if len(raw) == 6 and raw[:2] in ("19", "20") and 1 <= int(raw[4:]) <= 12:
        return raw + "01"
    return ""


def _ano_mes(ano: str, mes: str) -> str:
    """'2026' + '06' -> '202606'; fora do padrão de data -> ''."""
    if (
        len(ano) == 4
        and ano.isdigit()
        and ano[:2] in ("19", "20")
        and mes.isdigit()
        and 1 <= int(mes) <= 12
    ):
        return ano + mes
    return ""


def normalize_competence(value: Any) -> str:
    """Competência (AAAAMM) analisando o formato real da célula.

    Aceita os formatos encontrados nas planilhas do programa antigo:
    - AAAAMM          '202606'
    - AAAAMMDD        '20260601' / datetime '2026-06-01 00:00:00'
    - DDMMAAAA        '01062026' / '01/06/2026'
    - MM/AAAA         '06/2026'
    Vazio quando o valor não permite identificar ano e mês (em vez de
    devolver 6 dígitos que não são a competência).
    """
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m")
    raw = digits(value)
    if len(raw) >= 8:
        return _ano_mes(raw[:4], raw[4:6]) or _ano_mes(raw[4:8], raw[2:4])
    if len(raw) == 6:
        return _ano_mes(raw[:4], raw[4:6]) or _ano_mes(raw[2:6], raw[:2])
    return ""


# ==============================================================================
# Normalização de datas específicas do layout APAC
# ==============================================================================

def nascimento_to_aaaammdd(value: Any) -> str:
    """Data de nascimento → AAAAMMDD.

    A planilha grava DDMMAAAA (ex.: 24011958 = 24/01/1958). A detecção:
    se os 4 últimos dígitos formam um ano plausível (18xx/19xx/20xx/21xx)
    e dia/mês são válidos, converte; datas já em AAAAMMDD são mantidas.
    """
    raw = digits(value)
    if len(raw) != 8:
        return date_to_txt(value)
    dia, mes, ano = raw[:2], raw[2:4], raw[4:]
    if ano[:2] in ("18", "19", "20", "21") and 1 <= int(dia) <= 31 and 1 <= int(mes) <= 12:
        return ano + mes + dia
    return raw


def date_to_txt(value: Any) -> str:
    """Data para campo AAAAMMDD do TXT; '00000000' se vazia ou invalida.

    A invalida e barrada antes pelo validador; este e so o ultimo recurso.
    """
    return normalize_date(value) or "00000000"


# ==============================================================================
# Resolução de valores de linha (DataFrame → dict)
# ==============================================================================

# Memo por processo: as mesmas chaves de coluna (dezenas no máximo) são
# normalizadas centenas de milhares de vezes durante uma validação.
_NORMALIZE_CACHE: Dict[str, str] = {}


def _normalize_key(key: str) -> str:
    """Normaliza nome de coluna para comparação case/acento-insensitive.

    Função pura com memo interna (mesmo resultado sempre); o cache vive só
    em memória e é limitado aos nomes de coluna já vistos.
    """
    hit = _NORMALIZE_CACHE.get(key)
    if hit is not None:
        return hit
    s = key.strip().lower()
    s = s.replace(" ", "_").replace("-", "_").replace("/", "_")
    s = re.sub(r"_+", "_", s)
    _NORMALIZE_CACHE[key] = s
    return s


def resolve_row_value(row: Dict[str, Any], *candidates: str) -> str:
    """Retorna o primeiro valor não-vazio entre os candidatos de coluna.

    Faz comparação normalizada (case-insensitive, ignora acentos de chave)
    para tolerar variações de digitação nos nomes das colunas da planilha.
    Valores "nan", "None", "" são considerados vazios.
    """
    _EMPTY = {"", "nan", "none"}
    for candidate in candidates:
        # Tentativa direta (O(1), caminho feliz)
        v = text(row.get(candidate, ""))
        if v.lower() not in _EMPTY:
            return v
        # Tentativa normalizada (O(n) — só entra quando necessário)
        norm = _normalize_key(candidate)
        for key, val in row.items():
            if _normalize_key(str(key)) == norm:
                v = text(val)
                if v.lower() not in _EMPTY:
                    return v
    return ""


def resolve_block_value(row: Dict[str, Any], field_name: str, default: str = "") -> str:
    """Atalho sobre resolve_row_value com suporte a default."""
    value = resolve_row_value(row, field_name)
    return value if value != "" else default


# ==============================================================================
# Competência do formulário (fonte única: gerador + validador + interface)
# ==============================================================================

CAMPOS_COMPETENCIA = ("Competencia", "Competência", "AP_CMP")

# Datas do próprio formulário, em ordem de preferência quando a coluna
# Competencia não existe/está vazia — é o mês de quem preencheu a APAC.
CAMPOS_DATA_COMPETENCIA = (
    "Data_Autorizacao",
    "Data_Solicitacao",
    "Data_Alta_Obito",
    "Fim_Validade",
    "Inicio_Validade",
)


def resolve_competence(row: Dict[str, Any]) -> str:
    """Competência (AAAAMM) analisada a partir do próprio formulário.

    1) coluna Competencia, em qualquer formato reconhecível;
    2) sem ela, as datas do formulário (autorização, solicitação, alta e
       validade) — o mês dos formularios;
    3) vazio quando nada identifica o mês (nunca inventa competência).
    """
    comp = normalize_competence(resolve_row_value(row, *CAMPOS_COMPETENCIA))
    if comp:
        return comp
    for campo in CAMPOS_DATA_COMPETENCIA:
        comp = normalize_competence(resolve_row_value(row, campo))
        if comp:
            return comp
    return ""
