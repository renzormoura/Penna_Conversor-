"""Texto e formatação de valores da linha para a ficha."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from penna import reference
from penna.core import format_cpf as formatar_cpf
from penna.config import get_header

# ---------------------------------------------------------------------------
# Texto e formatação de valores da linha
# ---------------------------------------------------------------------------

def valor_texto(valor: Any) -> str:
    """Valor de célula/planilha -> string limpa."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    try:
        if valor != valor:  # NaN
            return ""
    except (TypeError, ValueError):  # ex.: arrays, sem igualdade escalar
        pass
    return str(valor).strip()


def formatar_procedimento(codigo: Any) -> str:
    """``0905010035`` -> ``09.05.01.003-5`` / 9 dígitos -> ``09.05.01.003``."""
    bruto = valor_texto(codigo)
    d = re.sub(r"\D", "", bruto)
    if len(d) == 10:
        return f"{d[0:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}-{d[9]}"
    if len(d) == 9:
        return f"{d[0:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}"
    return bruto


def formatar_data(valor: Any) -> str:
    """Qualquer entrada de data conhecida -> ``d/m/aaaa`` (sem zero-padding,
    igual ao modelo Excel da ficha)."""
    s = valor_texto(valor)
    if not s:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$", s)
    if m:
        return f"{int(m.group(3))}/{int(m.group(2))}/{m.group(1)}"
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        return f"{int(m.group(1))}/{int(m.group(2))}/{m.group(3)}"
    if re.match(r"^\d{8}$", s):
        if 1900 <= int(s[:4]) <= 2100:      # AAAAMMDD (canônico do APAC)
            return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
        if 1900 <= int(s[4:]) <= 2100:      # DDMMAAAA (Excel)
            return f"{s[:2]}/{s[2:4]}/{s[4:]}"
    return s


def _formatar_competencia(valor: Any) -> str:
    s = valor_texto(valor)
    return f"{s[:4]}/{s[4:]}" if re.match(r"^\d{6}$", s) else s


def formatar_cep(valor: Any) -> str:
    """CEP: 8 dígitos -> ``NNNNN-NNN`` (formato do formulário)."""
    digitos = re.sub(r"\D", "", valor_texto(valor))
    return (f"{digitos[:5]}-{digitos[5:]}" if len(digitos) == 8
            else valor_texto(valor))


def formatar(coluna: str, valor: Any) -> str:
    v = valor_texto(valor)
    if not v:
        return ""
    if coluna.startswith("Data") or coluna in ("Inicio_Validade", "Fim_Validade"):
        return formatar_data(v)
    if coluna.endswith("Cod_Procedimento"):
        return formatar_procedimento(v)
    if coluna in ("Cpf_Paciente", "Medico_Cpf", "Autorizador_Cpf"):
        return formatar_cpf(v)
    if coluna == "Competencia":
        return _formatar_competencia(v)
    if coluna == "Cep":
        return formatar_cep(v)
    return v


def rotulo_coluna(coluna: str) -> str:
    """``Cid_Causas_Assoc`` -> ``CID CAUSAS ASSOC`` (página de extras)."""
    return re.sub(r"_+", " ", str(coluna)).strip().upper()


# ---------------------------------------------------------------------------
# Descrição do procedimento (S_PA, opcional)
# ---------------------------------------------------------------------------

_CACHE_PROC: Optional[Dict[str, str]] = None


def _desc_procedimentos() -> Dict[str, str]:
    """``{9 dígitos: descrição}`` do S_PED; {} quando a base não existe."""
    global _CACHE_PROC
    if _CACHE_PROC is not None:
        return _CACHE_PROC
    desc: Dict[str, str] = {}
    for r in reference.carregar_tabela("S_PA") or []:
        pid = valor_texto(r.get("PA_ID"))
        if pid and pid not in desc:
            desc[pid] = valor_texto(r.get("PA_DC"))
    _CACHE_PROC = desc
    return desc


def procedimento_completo(display: str, modelo_proc: Optional[str] = None) -> str:
    """``09.05.01.003-5`` -> ``09.05.01.003-5 - OCI AVALIAÇÃO ...``.

    Prefere a descrição do próprio modelo (com acentos corretos) quando o
    código conhece a descrição do template; caso contrário usa a base S_PA
    (que pode vir sem acento).
    """
    if not display:
        return ""
    d = re.sub(r"\D", "", display)
    if modelo_proc and len(d) >= 9:
        try:
            pat = (rf"\b{d[:2]}\.{d[2:4]}\.{d[4:6]}\.{d[6:9]}"
                   rf"(?:-[A-Za-z0-9])?")
            m = re.search(pat, modelo_proc)
            if m:
                return modelo_proc
        except re.error:
            pass
    desc = _desc_procedimentos().get(d[:9], "") if len(d) >= 9 else ""
    return f"{display} - {desc}" if desc else display


def nome_estabelecimento() -> str:
    """Nome do estabelecimento do penna_config.json (header.orgao_responsavel)."""
    return valor_texto(get_header().get("orgao_responsavel", ""))
