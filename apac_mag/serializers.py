"""Serialização de ApacRecord para os blocos de layout fixo do SIA/DATASUS.

Este módulo é a fonte única de verdade para a serialização orientada a objetos
(ApacRecord → list[str]). O gerador de planilhas (apac_mag_gerador.py) usa sua
própria versão orientada a dict para compatibilidade com o fluxo legado; quando
a migração for concluída, ambos convergirão para este módulo.

Larguras CONFIRMADAS no arquivo real APCEO26P.JUN do programa antigo:
- bloco 14 = 536 chars + 1 espaço = 537 (BLOCK_01_WIDTH)
- bloco 06 = 06 + competência + número completo (13d) + CID (sem padding no fim)
- bloco 13 = 44 chars de conteúdo + espaços até 97 (BLOCK_03_WIDTH)
- IBGE do paciente = 6 dígitos + espaço (330280 )
- CRLF em todas as linhas; só a última linha do arquivo sai sem padding; arquivo termina com CRLF duplo
"""
from __future__ import annotations

import re

from .config import get_defaults
from .models import ApacRecord, ProcedureRecord
from .normalization import (
    date_to_txt,
    digits,
    normalize_competence,
    pad_left,
    pad_right,
    text,
    text_upper,
)
from .validation import validate_apac

# ---------------------------------------------------------------------------
# Constantes de layout (imutáveis)
# ---------------------------------------------------------------------------
BLOCK_01_WIDTH = 537  # corpo da APAC (tipo 14): 536 + 1 espaço
BLOCK_03_WIDTH = 97   # ações da APAC (tipo 13): 44 + 53 espaços


# ---------------------------------------------------------------------------
# Helpers internos de serialização (APAC-específicos, sem equivalente genérico)
# ---------------------------------------------------------------------------

def _upper(value: str | None) -> str:
    """Maiúsculas ASCII, preserva acentos — comportamento do programa antigo."""
    return text_upper(value)


def _competence_from_record(record: ApacRecord) -> str:
    """Extrai competência (AAAAMM) do ApacRecord."""
    raw = record.competence or normalize_competence(
        record.request_date or record.authorization_date or ""
    )
    d = digits(raw)
    return d[:6].ljust(6, "0")


def _uf_from_record(record: ApacRecord) -> str:
    """Extrai código da UF (2 dígitos) do ApacRecord."""
    d = digits(record.issuing_uf)
    return d[-2:].zfill(2) if d else "00"


def _apac_num_varia(record: ApacRecord) -> str:
    """Número da APAC nos blocos 06/13: 13 dígitos completos.
    Confirmado no arquivo real APCEO26P.JUN."""
    return pad_left(record.apac_number, 13, "0")


def _cns_field(value: str | None) -> str:
    """CNS obrigatório: zeros à esquerda quando ausente."""
    d = digits(value or "")
    return pad_left(d or "0", 15, "0")


def _cns_patient_field(value: str | None) -> str:
    """CNS do paciente: zeros quando informado, brancos quando ausente.
    Comportamento confirmado no arquivo real APCEO26P.JUN."""
    d = digits(value or "")
    return pad_left(d, 15, "0") if d else " " * 15


def _ibge_code(municipality_code: str, default_ibge: str) -> str:
    """Código IBGE: 6 dígitos + espaço (sem DV), como no arquivo real."""
    d = digits(municipality_code)
    if len(d) < 6:
        d = digits(default_ibge)
    if len(d) < 6:
        return " " * 7
    return d[:6] + " "


# ---------------------------------------------------------------------------
# Blocos de layout fixo
# ---------------------------------------------------------------------------

def _block_01(record: ApacRecord) -> str:
    """Bloco tipo 14 — corpo da APAC (537 chars)."""
    dfl = get_defaults()
    patient = record.patient

    numero_apac = pad_left(record.apac_number, 13, "0")
    competencia = _competence_from_record(record)
    uf = _uf_from_record(record)
    cnes = pad_left(record.executing_cnes or dfl["Cnes_Executante"], 7, "0")

    # Data de processamento: no antigo é o 1º dia da competência
    data_emissao = date_to_txt(record.authorization_date or record.request_date or (competencia + "01"))
    inicio = date_to_txt(record.validity_start)
    fim = date_to_txt(record.validity_end)
    tipo_atendimento = pad_left(record.attendance_type or "00", 2, "0")
    tipo = pad_left(record.apac_type or dfl["Tipo_Apac"], 1, "0")
    nome_paciente = pad_right(_upper(patient.name), 30)
    nome_mae = pad_right(_upper(patient.mother_name), 30)
    endereco = pad_right(_upper(patient.street or ""), 30)
    numero = pad_right(patient.address_number, 5)
    complemento = pad_right(patient.complement, 10)
    cep = pad_left(patient.cep, 8, "0")
    ibge = _ibge_code(patient.municipality_code, dfl.get("Codigo_Municipio", ""))
    data_nasc = date_to_txt(patient.birth_date)
    # Sexo: espaço quando ausente para não deslocar os campos seguintes
    sexo = _upper(patient.sex)[:1] or " "
    nome_solicitante = pad_right(_upper(record.professional_name or record.requester_name), 30)
    codigo_proc = pad_left(record.procedures[0].code if record.procedures else "", 10, "0")
    codigo_cob = pad_left(record.exit_reason or dfl["Motivo_Saida"], 2, "0")
    data_correcao = date_to_txt(record.discharge_date)
    nome_diretor = pad_right(_upper(record.authorizer_name), 30)
    # CNS: paciente=brancos quando ausente; profissional/diretor=zeros quando ausente
    cns_paciente = _cns_patient_field(patient.cns)
    cns_responsavel = _cns_field(record.professional_cns)
    cns_diretor = _cns_field(record.authorizer_cns)
    cid_causa = pad_right(_upper(record.associated_cid), 4)
    prontuario = pad_right(record.consultation_number, 10)
    cnes_solicitante = pad_left(record.requesting_cnes or cnes, 7, "0")
    data_solic = date_to_txt(record.request_date)
    data_aut = date_to_txt(record.authorization_date)
    codigo_orgao = pad_right(record.authorization_code or dfl["Cod_Orgao_Emiss"], 10)
    carater = pad_left(record.attendance_character or dfl["Carater_Atend"], 2, "0")
    apac_anterior = pad_left(
        digits(record.previous_apac_number or dfl["Numero_Apac_Anterior"]) or "0",
        13,
        "0",
    )
    # Raça/cor: 01..05, 99 = sem informação
    raca = pad_left(digits(patient.race) or "99", 2, "0")
    # Responsável: quando ausente, usa nome do paciente (comportamento do antigo)
    nome_responsavel = pad_right(_upper(patient.responsible_name or patient.name), 30)
    uf_nascimento = pad_right("010", 3)
    etnia = pad_right(_upper(patient.ethnicity), 4)
    codigo_logradouro = pad_right(text(record.street_code), 3)
    bairro = pad_right(_upper(patient.neighborhood), 30)
    telefone = re.sub(r"\D", "", patient.phone or "")
    ddd = pad_left(telefone[:2], 2, "0") if telefone else "  "
    telefone_num = pad_left(telefone[-9:], 9, "0") if telefone else "         "
    email = pad_right(patient.email, 40)
    # CNS executante: cascata → profissional → padrão config
    cns_exec_d = digits(record.professional_cns)
    if not cns_exec_d:
        cns_exec_d = digits(dfl.get("Cns_Executante", ""))
    cns_exec = pad_left(cns_exec_d, 15, "0") if cns_exec_d else "0" * 15
    # CPF sem pontuação (AP_CPFPAC)
    cpf_pac_d = digits(patient.cpf)
    cpf_pac = cpf_pac_d.rjust(11, "0") if cpf_pac_d else " " * 11
    ine_value = pad_right(record.ine, 10)
    situacao_rua = pad_right(_upper(record.street_situation) or dfl["Situacao_De_Rua"], 1)
    fonte_orcamento = pad_right(record.budget_source, 2)
    emenda = pad_right(record.parliamentary_amendment, 1)

    content = (
        "14"
        + competencia
        + numero_apac
        + uf
        + cnes
        + data_emissao
        + inicio
        + fim
        + tipo_atendimento
        + tipo
        + nome_paciente
        + nome_mae
        + endereco
        + numero
        + complemento
        + cep
        + ibge
        + data_nasc
        + sexo
        + nome_solicitante
        + codigo_proc
        + codigo_cob
        + data_correcao
        + nome_diretor
        + cns_paciente
        + cns_responsavel
        + cns_diretor
        + cid_causa
        + prontuario
        + cnes_solicitante
        + data_solic
        + data_aut
        + codigo_orgao
        + carater
        + apac_anterior
        + raca
        + nome_responsavel
        + uf_nascimento
        + etnia
        + codigo_logradouro
        + bairro
        + ddd
        + telefone_num
        + email
        + cns_exec
        + cpf_pac
        + ine_value
        + situacao_rua
        + fonte_orcamento
        + emenda
    )
    return content.ljust(BLOCK_01_WIDTH)


def _block_02(record: ApacRecord) -> str:
    """Bloco tipo 06 — CID principal.

    Formato real: 06 + competência + número completo (13d) + CID (sem padding).
    O antigo grava o CID exatamente como digitado (ex.: 'H40' = 3 chars).
    """
    cid = re.sub(r"[^A-Z0-9]", "", _upper(record.primary_cid))[:4]
    if not cid:
        return ""
    return "06" + _competence_from_record(record) + _apac_num_varia(record) + cid


def _block_03(record: ApacRecord, procedure: ProcedureRecord) -> str:
    """Bloco tipo 13 — procedimento/ação (97 chars).

    Formato real: 13 + competência + número (13d) + procedimento (10d)
    + CBO (6d) + quantidade (7d) = 44 chars de conteúdo + espaços até 97.
    Todos os blocos saem com padding: no arquivo real, apenas a ULTIMA
    linha do ARQUIVO fica sem os espaços (o escritor faz esse corte —
    regra já aplicada por apac_mag_gerador.exportar_txt).
    O antigo NÃO exporta CNPJ/NF/CID/Serviço/Classificação/Equipe/Terceiro.
    """
    code = pad_left(procedure.code, 10, "0")
    cbo = pad_left(procedure.cbo, 6, "0")
    qtd = pad_left(procedure.quantity, 7, "0")
    content = "13" + _competence_from_record(record) + _apac_num_varia(record) + code + cbo + qtd
    return content.ljust(BLOCK_03_WIDTH)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def serialize_apac(record: ApacRecord) -> list[str]:
    """Serializa um ApacRecord para a lista de blocos de layout fixo.

    Levanta ValueError se o registro não passar na validação estrutural
    (apac_mag/validation.py). Para geração em lote, valide antes com
    validate_apac() e trate os erros individualmente.

    Retorna:
        list[str]: blocos prontos para concatenar com CRLF (sem terminadores).
        Todos os blocos tipo 13 vêm com padding até 97 chars; o escritor do
        arquivo remove os espaços apenas da última linha do arquivo final,
        conforme o formato do programa antigo.
    """
    result = validate_apac(record)
    if not result.is_valid:
        messages = "; ".join(issue.message for issue in result.issues)
        raise ValueError(f"ApacRecord inválido: {messages}")

    blocks: list[str] = []

    b01 = _block_01(record)
    if b01.strip():
        blocks.append(b01)

    b02 = _block_02(record)
    if b02.strip():
        blocks.append(b02)

    procs = [p for p in record.procedures if p and p.code]
    for procedure in procs:
        b03 = _block_03(record, procedure)
        if b03.strip():
            blocks.append(b03)

    return [b for b in blocks if b.strip()]
