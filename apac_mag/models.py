from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PatientRecord:
    cpf: str = ""
    cns: str = ""
    name: str = ""
    mother_name: str = ""
    responsible_name: str = ""
    birth_date: str = ""
    sex: str = ""
    race: str = ""
    ethnicity: str = ""
    cep: str = ""
    street: str = ""
    address_number: str = ""
    complement: str = ""
    neighborhood: str = ""
    municipality_code: str = ""
    municipality_name: str = ""
    phone: str = ""
    email: str = ""


@dataclass
class ProcedureRecord:
    code: str = ""
    cbo: str = ""
    quantity: str = ""
    service: str = ""
    classification: str = ""
    third_party_cnes: str = ""


@dataclass
class ApacRecord:
    apac_number: str = ""
    previous_apac_number: str = ""
    competence: str = ""
    issuing_uf: str = ""
    requesting_cnes: str = ""
    executing_cnes: str = ""
    validity_start: str = ""
    validity_end: str = ""
    apac_type: str = ""
    attendance_type: str = ""
    patient: PatientRecord = field(default_factory=PatientRecord)
    procedures: list[ProcedureRecord] = field(default_factory=list)
    primary_cid: str = ""
    secondary_cids: list[str] = field(default_factory=list)
    associated_cid: str = ""
    professional_name: str = ""
    professional_cns: str = ""
    professional_cpf: str = ""
    requester_name: str = ""
    requester_cns: str = ""
    authorizer_name: str = ""
    authorizer_cns: str = ""
    request_date: str = ""
    authorization_date: str = ""
    discharge_date: str = ""
    authorization_code: str = ""
    attendance_character: str = ""
    exit_reason: str = ""
    consultation_number: str = ""
    ine: str = ""
    street_code: str = ""
    street_situation: str = ""
    budget_source: str = ""
    parliamentary_amendment: str = ""
    source_row: Optional[int] = None
