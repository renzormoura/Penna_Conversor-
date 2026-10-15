from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .columns import PATIENT_COLUMNS, REFERENCE_SHEETS
from .models import ApacRecord, PatientRecord, ProcedureRecord
from .normalization import digits, normalize_cpf, normalize_date, resolve_competence
from .serializers import serialize_apac
from .validation import validate_apac


def _as_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _digits(value) -> str:
    return re.sub(r"\D", "", _as_text(value))


def _ensure_database_columns(database: pd.DataFrame) -> pd.DataFrame:
    if database is None:
        return pd.DataFrame(columns=list(PATIENT_COLUMNS))

    frame = database.copy()
    for column in PATIENT_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame[list(PATIENT_COLUMNS)]
    frame = frame.where(frame.notna(), "")
    return frame


def find_patient_in_database(database: pd.DataFrame, cpf: str | None) -> dict | None:
    if database is None or database.empty:
        return None

    target = _digits(cpf)
    if not target:
        return None

    frame = _ensure_database_columns(database)
    for _, row in frame.iterrows():
        if _digits(row.get("Cpf_Paciente", "")) == target:
            return row.to_dict()

    return None


def merge_patient_into_procedure_row(procedure_row: dict, database: pd.DataFrame) -> dict:
    if not isinstance(procedure_row, dict):
        return procedure_row

    merged = dict(procedure_row)
    patient = find_patient_in_database(database, merged.get("Cpf_Paciente", ""))
    if patient is None:
        return merged

    for column in PATIENT_COLUMNS:
        value = _as_text(merged.get(column, ""))
        if not value:
            merged[column] = _as_text(patient.get(column, ""))

    return merged


def upsert_patient_in_database(database: pd.DataFrame, patient: dict) -> tuple[pd.DataFrame, bool]:
    frame = _ensure_database_columns(database)
    if not isinstance(patient, dict):
        return frame, False

    normalized = {str(key).strip(): _as_text(value) for key, value in patient.items()}
    cpf = _digits(normalized.get("Cpf_Paciente", ""))
    if not cpf:
        return frame, False

    normalized["Cpf_Paciente"] = cpf

    existing = frame[frame["Cpf_Paciente"].map(lambda value: _digits(value) == cpf)]
    if not existing.empty:
        index = existing.index[0]
        for column in frame.columns:
            if column in normalized and _as_text(normalized[column]):
                frame.at[index, column] = _as_text(normalized[column])
        return frame, False

    new_row = {column: normalized.get(column, "") for column in frame.columns}
    new_row["Cpf_Paciente"] = cpf
    frame = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
    return frame, True


def build_apac_record_from_row(row: dict, database: pd.DataFrame) -> ApacRecord:
    resolved = merge_patient_into_procedure_row(dict(row), database)
    patient_data = find_patient_in_database(database, resolved.get("Cpf_Paciente", "")) or {}

    patient = PatientRecord(
        cpf=normalize_cpf(resolved.get("Cpf_Paciente", patient_data.get("Cpf_Paciente", ""))),
        cns=_digits(resolved.get("Cns_Paciente", patient_data.get("Cns_Paciente", ""))),
        name=_as_text(resolved.get("Nome_Paciente", patient_data.get("Nome_Paciente", ""))),
        mother_name=_as_text(resolved.get("Nome_Da_Mae", patient_data.get("Nome_Da_Mae", ""))),
        responsible_name=_as_text(resolved.get("Nome_Do_Responsavel", patient_data.get("Nome_Do_Responsavel", ""))),
        # Planilha grava DDMMAAAA; converte para AAAAMMDD (layout apa_datanascim)
        birth_date=normalize_date(resolved.get("Data_Nascimento", patient_data.get("Data_Nascimento", ""))),
        sex=_as_text(resolved.get("Sexo", patient_data.get("Sexo", ""))),
        cep=_digits(resolved.get("Cep", patient_data.get("Cep", ""))),
        street=_as_text(resolved.get("Rua", resolved.get("Logradouro", patient_data.get("Logradouro", "")))),
        address_number=_as_text(resolved.get("Numero_Endereco", patient_data.get("Numero_Endereco", ""))),
        complement=_as_text(resolved.get("Complemento", patient_data.get("Complemento", ""))),
        neighborhood=_as_text(resolved.get("Bairro", patient_data.get("Bairro", ""))),
        municipality_code=_digits(resolved.get("Codigo_Municipio", patient_data.get("Codigo_Municipio", ""))),
        municipality_name=_as_text(resolved.get("Nome_Municipio", patient_data.get("Nome_Municipio", ""))),
        phone=_digits(resolved.get("Telefone", patient_data.get("Telefone", ""))),
        email=_as_text(resolved.get("Email", patient_data.get("Email", ""))),
    )

    procedures = [
        ProcedureRecord(
            code=_digits(resolved.get("Cod_Procedimento", "")),
            cbo=_digits(resolved.get("Cbo", "")),
            quantity=_digits(resolved.get("Quantidade", "")),
            service=_as_text(resolved.get("Servico", "")),
            classification=_as_text(resolved.get("Classif", "")),
            third_party_cnes=_digits(resolved.get("Cnes_Terceiro", "")),
        )
    ]

    record = ApacRecord(
        apac_number=_digits(resolved.get("Numero_Apac", "")),
        previous_apac_number=_as_text(resolved.get("Numero_Apac_Anterior", "")),
        competence=resolve_competence(resolved),
        issuing_uf=_digits(resolved.get("Codigo_UF", "")),
        requesting_cnes=_digits(resolved.get("Cnes_Solicitante", "")),
        executing_cnes=_digits(resolved.get("Cnes_Executante", "")),
        validity_start=_digits(resolved.get("Inicio_Validade", "")),
        validity_end=_digits(resolved.get("Fim_Validade", "")),
        apac_type=_digits(resolved.get("Tipo_Apac", "")),
        attendance_type=_digits(resolved.get("Tipo_Atendimento", "")),
        patient=patient,
        procedures=procedures,
        primary_cid=_as_text(resolved.get("Cid_Princ", "")),
        secondary_cids=[],
        associated_cid=_as_text(resolved.get("Cid_Causas_Assoc", "")),
        professional_name=_as_text(resolved.get("Nome_Profissional", "")),
        professional_cns=_digits(resolved.get("Medico_Cns", "")),
        professional_cpf=_digits(resolved.get("Medico_Cpf", "")),
        requester_name=_as_text(resolved.get("Nome_Profissional", "")),
        requester_cns=_digits(resolved.get("Cns_Executante", "")),
        authorizer_name=_as_text(resolved.get("Autorizador_Nome", "")),
        authorizer_cns=_digits(resolved.get("Autorizador_Cns", "")),
        request_date=_digits(resolved.get("Data_Solicitacao", "")),
        authorization_date=_digits(resolved.get("Data_Autorizacao", "")),
        discharge_date=_digits(resolved.get("Data_Alta_Obito", "")),
        authorization_code=_as_text(resolved.get("Cod_Orgao_Emiss", "")),
        attendance_character=_digits(resolved.get("Carater_Atend", "")),
        exit_reason=_digits(resolved.get("Motivo_Saida", "")),
        consultation_number=_as_text(resolved.get("No_Prontuario", "")),
        ine=_as_text(resolved.get("INE", "")),
        street_code=_as_text(resolved.get("Codigo_Logradouro", "")),
        street_situation=_as_text(resolved.get("Situacao_De_Rua", "")),
        budget_source=_as_text(resolved.get("Fonte_Orcamentaria", "")),
        parliamentary_amendment=_as_text(resolved.get("Emenda_Parlamentar", "")),
    )
    return record


def export_valid_apacs_from_workbook(workbook: dict[str, pd.DataFrame]) -> list[str]:
    database = workbook.get("banco_de_dados", pd.DataFrame())
    procedure_sheet = workbook.get("procedimento_mes", pd.DataFrame())
    if procedure_sheet.empty:
        return []

    # Numeracao vem SEMPRE da coluna Numero_Apac da planilha (o gerador nao
    # inventa numeros; regra do usuario).
    lines: list[str] = []
    for _, row in procedure_sheet.iterrows():
        record = build_apac_record_from_row(row.to_dict(), database)
        validation = validate_apac(record)
        if validation.is_valid:
            lines.extend(serialize_apac(record))

    return lines


def load_main_workbook(path: Path) -> dict[str, pd.DataFrame]:
    workbook = Path(path)
    if not workbook.exists():
        raise FileNotFoundError(f"Arquivo principal nao encontrado: {workbook}")
    sheets = pd.read_excel(workbook, sheet_name=None, dtype=str, keep_default_na=False)
    missing = [sheet for sheet in REFERENCE_SHEETS if sheet not in sheets]
    if missing:
        raise ValueError(f"Abas obrigatorias ausentes: {', '.join(missing)}")
    return sheets
