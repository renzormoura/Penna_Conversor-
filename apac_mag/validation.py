from __future__ import annotations

from dataclasses import dataclass, field

from .models import ApacRecord
from .normalization import digits


@dataclass
class ValidationIssue:
    code: str
    message: str
    field: str = ""


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_apac(record: ApacRecord) -> ValidationResult:
    result = ValidationResult()
    if not digits(record.apac_number):
        result.issues.append(ValidationIssue("APAC_REQUIRED", "Numero da APAC obrigatorio", "Numero_Apac"))
    if len(digits(record.apac_number)) != 13:
        result.issues.append(ValidationIssue("APAC_LENGTH", "Numero da APAC deve ter 13 digitos", "Numero_Apac"))
    if not record.patient.cpf and not record.patient.cns:
        result.issues.append(ValidationIssue("PATIENT_ID_REQUIRED", "Informe CPF ou CNS", "Cpf_Paciente"))
    if not record.patient.name:
        result.issues.append(ValidationIssue("PATIENT_NAME_REQUIRED", "Nome do paciente obrigatorio", "Nome_Paciente"))
    if not record.procedures or not record.procedures[0].code:
        result.issues.append(ValidationIssue("PROCEDURE_REQUIRED", "Procedimento principal obrigatorio", "Cod_Procedimento"))
    if len(record.procedures) > 10:
        result.issues.append(ValidationIssue("PROCEDURE_LIMIT", "A APAC aceita no maximo 10 procedimentos", "Cod_Procedimento"))
    return result
