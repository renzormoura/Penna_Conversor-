"""Bloco 14: corpo da APAC (537 caracteres).

A ordem dos campos de :class:`ApacBody` **é** o layout posicional: ``render``
concatena na ordem de declaração. Cada seção (identificação, paciente,
endereço, profissionais, autorização) extrai seus campos da linha da planilha.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Any, Dict

from penna.config import get_defaults
from penna.core import (
    birth_date_to_txt,
    date_to_txt,
    digits,
    pad_left,
    pad_right,
    resolve_block_value,
    resolve_row_value,
    text_upper,
)

from .constants import BODY_WIDTH
from .derived import apac_number, competence_from_row, ibge_code, numeric_field, uf_from_row

Row = Dict[str, Any]
Defaults = Dict[str, str]


@dataclass(frozen=True)
class ApacBody:
    """Campos do bloco 14 na ordem exata do arquivo (cada valor já tem a largura fixa)."""

    competencia: str
    numero_apac: str
    uf: str
    cnes: str
    data_emissao: str
    inicio_validade: str
    fim_validade: str
    tipo_atendimento: str
    tipo_apac: str
    nome_paciente: str
    nome_mae: str
    endereco: str
    numero: str
    complemento: str
    cep: str
    ibge: str
    data_nascimento: str
    sexo: str
    nome_solicitante: str
    procedimento_principal: str
    motivo_saida: str
    data_alta_obito: str
    nome_autorizador: str
    cns_paciente: str
    cns_responsavel: str
    cns_autorizador: str
    cid_causa: str
    prontuario: str
    cnes_solicitante: str
    data_solicitacao: str
    data_autorizacao: str
    orgao_emissor: str
    carater_atendimento: str
    apac_anterior: str
    raca: str
    nome_responsavel: str
    uf_nascimento: str
    etnia: str
    codigo_logradouro: str
    bairro: str
    ddd: str
    telefone: str
    email: str
    cns_executante: str
    cpf_paciente: str
    ine: str
    situacao_rua: str
    fonte_orcamento: str
    emenda: str

    def render(self) -> str:
        """Linha do bloco 14, completada com espaços até 537 caracteres."""
        corpo = "14" + "".join(getattr(self, f.name) for f in fields(self))
        return corpo.ljust(BODY_WIDTH)


def _upper(row: Row, campo: str, largura: int) -> str:
    return pad_right(text_upper(resolve_block_value(row, campo, "")), largura)


def _identificacao(row: Row, dfl: Defaults) -> Dict[str, str]:
    numero = apac_number(row)
    cnes = pad_left(resolve_block_value(row, "Cnes_Executante", dfl["Cnes_Executante"]), 7, "0")
    competencia = competence_from_row(row)
    # Data de processamento: no programa antigo é o 1º dia da competência
    # (ex.: 202606 -> 20260601, confirmado no APCEO26P.JUN).
    emissao = resolve_row_value(row, "Data_Emissao") or competencia[:6] + "01"
    return {
        "competencia": competencia,
        "numero_apac": numero,
        "uf": uf_from_row(row, numero),
        "cnes": cnes,
        "data_emissao": date_to_txt(emissao),
        "inicio_validade": date_to_txt(resolve_block_value(row, "Inicio_Validade", "")),
        "fim_validade": date_to_txt(resolve_block_value(row, "Fim_Validade", "")),
        "tipo_atendimento": pad_left(resolve_row_value(row, "Tipo_Atendimento", "Tip_Atendimento") or "00", 2, "0"),
        "tipo_apac": pad_left(resolve_block_value(row, "Tipo_Apac", dfl["Tipo_Apac"]), 1, "0"),
        "cnes_solicitante": pad_left(resolve_block_value(row, "Cnes_Solicitante", cnes), 7, "0"),
        "orgao_emissor": pad_right(resolve_block_value(row, "Cod_Orgao_Emiss", dfl["Cod_Orgao_Emiss"]), 10),
        "carater_atendimento": pad_left(resolve_block_value(row, "Carater_Atend", dfl["Carater_Atend"]), 2, "0"),
        "apac_anterior": pad_left(
            digits(resolve_block_value(row, "Numero_Apac_Anterior", dfl["Numero_Apac_Anterior"])) or "0", 13, "0"
        ),
        "fonte_orcamento": pad_right(resolve_block_value(row, "Fonte_Orcamentaria", ""), 2),
        "emenda": pad_right(resolve_block_value(row, "Emenda_Parlamentar", ""), 1),
    }


def _paciente(row: Row) -> Dict[str, str]:
    nome = _upper(row, "Nome_Paciente", 30)
    cns = digits(resolve_block_value(row, "Cns_Paciente", ""))
    return {
        "nome_paciente": nome,
        "nome_mae": _upper(row, "Nome_Da_Mae", 30),
        "data_nascimento": birth_date_to_txt(resolve_block_value(row, "Data_Nascimento", "")),
        # Largura 1: sem valor ocupa a posição com espaço para não deslocar o restante.
        "sexo": text_upper(resolve_block_value(row, "Sexo", ""))[:1] or " ",
        # CNS do paciente ausente: brancos (confirmado no APCEO26P.JUN).
        "cns_paciente": pad_left(cns, 15, "0") if cns else " " * 15,
        "raca": pad_left(resolve_block_value(row, "Raca", "") or "99", 2, "0"),
        # Responsável vazio: o antigo grava o nome do paciente (confirmado no arquivo real).
        "nome_responsavel": pad_right(
            text_upper(resolve_block_value(row, "Nome_Do_Responsavel") or resolve_block_value(row, "Nome_Paciente", "")),
            30,
        ),
        "uf_nascimento": pad_right(resolve_row_value(row, "Uf_Nascimento", "UF_Nascimento") or "010", 3),
        "etnia": pad_right(resolve_block_value(row, "Etnia", ""), 4),
        "cpf_paciente": numeric_field(resolve_block_value(row, "Cpf_Paciente", ""), 11),
        "situacao_rua": pad_right(text_upper(resolve_block_value(row, "Situacao_De_Rua", "") or "N"), 1),
        "prontuario": pad_right(resolve_block_value(row, "No_Prontuario", ""), 10),
    }


def _endereco(row: Row) -> Dict[str, str]:
    # A planilha guarda o código da via em 'Logradouro' (081 = rua, 100 = travessa);
    # Codigo_Logradouro, se existir, prevalece.
    codigo_via = resolve_row_value(row, "Codigo_Logradouro", "Cod_Logradouro") or digits(
        resolve_block_value(row, "Logradouro", "")
    )
    telefone = re.sub(r"\D", "", resolve_block_value(row, "Telefone", ""))
    return {
        "endereco": pad_right(
            text_upper(resolve_block_value(row, "Rua", resolve_block_value(row, "Logradouro", ""))), 30
        ),
        # Número alinhado à ESQUERDA com espaços (arquivo real: '487  ').
        "numero": pad_right(resolve_block_value(row, "Numero_Endereco", ""), 5),
        "complemento": pad_right(resolve_block_value(row, "Complemento", ""), 10),
        "cep": pad_left(resolve_block_value(row, "Cep", ""), 8, "0"),
        "ibge": ibge_code(row),
        "codigo_logradouro": pad_right(codigo_via or "", 3),
        "bairro": _upper(row, "Bairro", 30),
        "ddd": pad_left(telefone[:2], 2, "0") if telefone else "  ",
        "telefone": pad_left(telefone[-9:], 9, "0") if telefone else " " * 9,
        "email": pad_right(resolve_block_value(row, "Email", ""), 40),
    }


def _cns_obrigatorio(valor: str) -> str:
    """CNS de profissional: zeros quando ausente."""
    return pad_left(digits(valor) or "0", 15, "0")


def _profissionais(row: Row, dfl: Defaults) -> Dict[str, str]:
    # CNS do executante: cascata de fallbacks para nunca exportar zerado sem necessidade.
    cns_exec = (
        digits(resolve_block_value(row, "Cns_Executante", ""))
        or digits(resolve_block_value(row, "Medico_Cns", ""))
        or digits(dfl.get("Cns_Executante", ""))
    )
    return {
        "nome_solicitante": _upper(row, "Nome_Profissional", 30),
        "cns_responsavel": _cns_obrigatorio(resolve_block_value(row, "Medico_Cns", "")),
        "cns_executante": pad_left(cns_exec, 15, "0") if cns_exec else "0" * 15,
        "ine": pad_right(resolve_block_value(row, "INE", ""), 10),
    }


def _autorizacao(row: Row) -> Dict[str, str]:
    return {
        "nome_autorizador": _upper(row, "Autorizador_Nome", 30),
        "cns_autorizador": _cns_obrigatorio(resolve_block_value(row, "Autorizador_Cns", "")),
        "data_solicitacao": date_to_txt(resolve_block_value(row, "Data_Solicitacao", "")),
        "data_autorizacao": date_to_txt(resolve_block_value(row, "Data_Autorizacao", "")),
    }


def _atendimento(row: Row, dfl: Defaults) -> Dict[str, str]:
    return {
        "procedimento_principal": pad_left(resolve_block_value(row, "Cod_Procedimento", ""), 10, "0"),
        "motivo_saida": pad_left(resolve_block_value(row, "Motivo_Saida", dfl["Motivo_Saida"]), 2, "0"),
        "data_alta_obito": date_to_txt(resolve_block_value(row, "Data_Alta_Obito", "")),
        "cid_causa": _upper(row, "Cid_Causas_Assoc", 4),
    }


def body_from_row(row: Row) -> ApacBody:
    """Monta o bloco 14 de uma linha da planilha (config lido a cada linha, sem estado global)."""
    dfl = get_defaults()
    campos: Dict[str, str] = {}
    for secao in (
        _identificacao(row, dfl),
        _paciente(row),
        _endereco(row),
        _profissionais(row, dfl),
        _autorizacao(row),
        _atendimento(row, dfl),
    ):
        campos.update(secao)
    return ApacBody(**campos)


def build_body_block(row: Row) -> str:
    """Linha completa do bloco 14 (537 caracteres)."""
    return body_from_row(row).render()
