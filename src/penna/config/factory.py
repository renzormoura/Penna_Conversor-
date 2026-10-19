"""Valores de fábrica da configuração do estabelecimento.

A identidade do estabelecimento (órgão, CGC, destino, CNES, município) é
PLACEHOLDER INVÁLIDO de propósito: nunca um prestador real. Enquanto o
``penna_config.json`` não for preenchido, a exportação é bloqueada
(ver :func:`penna.config.settings.verificar_configuracao`).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

NAO_CONFIGURADO = "NAO CONFIGURADO"

# Histórico de fábrica da versão do cabeçalho por competência (AAAAMM ->
# "Versao XX.XX"), conferido nos TXTs do programa original. Espelhado em
# penna_config.example.json; vale mesmo sem config.
VERSAO_POR_MES_FABRICA: Dict[str, str] = {
    "202510": "Versao 03.18",
    "202511": "Versao 03.18",
    "202512": "Versao 03.18",
    "202601": "Versao 03.19",
    "202602": "Versao 03.21",
    "202603": "Versao 03.21",
    "202605": "Versao 04.01",
    "202606": "Versao 04.01",
}

FALLBACK: Dict[str, Any] = {
    "header": {
        "orgao_responsavel": NAO_CONFIGURADO,
        "cgc": "00000000000000",
        "destino": NAO_CONFIGURADO,
        "destino_indicador": "M",
        "versao": "Versao 04.01",
        "versao_por_mes": dict(VERSAO_POR_MES_FABRICA),
        # Escolhas do usuário pela interface (prevalecem sobre o histórico).
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
        "Cod_Orgao_Emiss": NAO_CONFIGURADO,
    },
}

# Campos que identificam o estabelecimento: com o valor de fábrica, o
# arquivo sairia com identidade inválida.
CAMPOS_IDENTIDADE: Tuple[Tuple[str, str], ...] = (
    ("header", "orgao_responsavel"),
    ("header", "cgc"),
    ("header", "destino"),
    ("defaults", "Cnes_Executante"),
    ("defaults", "Cod_Orgao_Emiss"),
    ("defaults", "Codigo_Municipio"),
)
