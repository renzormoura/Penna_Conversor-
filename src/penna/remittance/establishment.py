"""Dados do estabelecimento e descrições das tabelas SIA usadas nos relatórios."""
from __future__ import annotations

from typing import Dict, List

from penna import reference
from penna.config import get_header
from penna.core import text_upper

from .formatting import digitos


def dados_estabelecimento() -> Dict[str, str]:
    """Órgão responsável e destino: S_SS do programa original, com fallback ao ``penna_config.json``."""
    h = get_header()
    dados = {
        "nome": text_upper(h.get("orgao_responsavel", "")),
        "sigla": "",
        "cgc": digitos(h.get("cgc", "")),
        "destino": text_upper(h.get("destino", "")),
        "indicador": h.get("destino_indicador", "M")[:1],
        "cnes": "",
    }
    registros = reference.carregar_tabela("S_SS")
    if registros:
        ss = registros[0]
        dados["nome"] = (ss.get("SS_UFNOME") or dados["nome"]).strip().upper()
        dados["sigla"] = (ss.get("SS_SIGL") or "").strip().upper()
        dados["cgc"] = digitos(ss.get("SS_CGC") or dados["cgc"])
        dados["destino"] = (ss.get("SS_NM") or dados["destino"]).strip().upper()
        dados["indicador"] = (ss.get("SS_IN") or dados["indicador"]).strip()[:1].upper()
        dados["cnes"] = digitos(ss.get("SS_UPS") or "")
    return dados


def descricoes_procedimentos() -> Dict[str, str]:
    """``{código de 9 dígitos: descrição}`` da S_PA (a primeira ocorrência vence)."""
    descricoes: Dict[str, str] = {}
    for r in reference.carregar_tabela("S_PA") or []:
        pid = (r.get("PA_ID") or "").strip()
        if pid and pid not in descricoes:
            descricoes[pid] = (r.get("PA_DC") or "").strip()
    return descricoes


def regras_do_procedimento(procedimento9: str) -> List[str]:
    """Regras condicionadas da S_PAREGR para o procedimento, ordenadas."""
    regras = {
        (r.get("REG_REGRA") or "").strip()
        for r in reference.carregar_tabela("S_PAREGR") or []
        if (r.get("REG_PA") or "").strip() == procedimento9
    }
    return sorted(regra for regra in regras if regra)
