from __future__ import annotations

import unittest

import pandas as pd

from apac_mag.models import ApacRecord, PatientRecord, ProcedureRecord
from apac_mag.serializers import serialize_apac
from apac_mag.workbook import (
    build_apac_record_from_row,
    export_valid_apacs_from_workbook,
    find_patient_in_database,
    merge_patient_into_procedure_row,
    upsert_patient_in_database,
)


class TestExcelPatientFlow(unittest.TestCase):
    def test_find_patient_in_database_by_cpf(self):
        database = pd.DataFrame(
            [{
                "Cpf_Paciente": "12345678909",
                "Cns_Paciente": "123456789012345",
                "Nome_Paciente": "Maria da Silva",
                "Nome_Da_Mae": "Joana Silva",
                "Data_Nascimento": "19900101",
                "Sexo": "F",
                "Cep": "01000000",
            }]
        )

        patient = find_patient_in_database(database, "123.456.789-09")

        self.assertIsNotNone(patient)
        self.assertEqual(patient["Nome_Paciente"], "Maria da Silva")
        self.assertEqual(patient["Cpf_Paciente"], "12345678909")

    def test_merge_patient_into_procedure_row_uses_excel_database_data(self):
        database = pd.DataFrame(
            [{
                "Cpf_Paciente": "12345678909",
                "Cns_Paciente": "123456789012345",
                "Nome_Paciente": "Maria da Silva",
                "Nome_Da_Mae": "Joana Silva",
                "Data_Nascimento": "19900101",
                "Sexo": "F",
                "Cidade": "São Paulo",
            }]
        )
        procedure_row = {"Cpf_Paciente": "123.456.789-09", "Nome_Paciente": ""}

        filled = merge_patient_into_procedure_row(procedure_row, database)

        self.assertEqual(filled["Nome_Paciente"], "Maria da Silva")
        self.assertEqual(filled["Data_Nascimento"], "19900101")

    def test_upsert_patient_in_database_adds_new_patient_when_missing(self):
        database = pd.DataFrame(columns=["Cpf_Paciente", "Nome_Paciente", "Nome_Da_Mae", "Data_Nascimento"])
        patient = {"Cpf_Paciente": "98765432100", "Nome_Paciente": "Pedro Souza", "Nome_Da_Mae": "Ana Souza", "Data_Nascimento": "19850312"}

        updated, created = upsert_patient_in_database(database, patient)

        self.assertTrue(created)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated.iloc[0]["Nome_Paciente"], "Pedro Souza")

    def test_serialize_apac_matches_legacy_txt_contract(self):
        record = ApacRecord(
            apac_number="1234567890123",
            competence="202602",
            issuing_uf="SP",
            requesting_cnes="4234316",
            executing_cnes="4234316",
            validity_start="20260201",
            validity_end="20260228",
            apac_type="003",
            attendance_type="01",
            patient=PatientRecord(
                cpf="12345678909",
                cns="123456789012345",
                name="Maria da Silva",
                mother_name="Joana Silva",
                responsible_name="Joao Silva",
                birth_date="19900101",
                sex="F",
                cep="01000000",
                street="Avenida Paulista",
                address_number="1000",
                complement="",
                neighborhood="Bela Vista",
                municipality_code="3550308",
                municipality_name="Sao Paulo",
                phone="11999999999",
                email="maria@email.com",
            ),
            procedures=[
                ProcedureRecord(code="040102", cbo="225142", quantity="1", service="", classification="", third_party_cnes="")
            ],
            primary_cid="A00",
            professional_name="Dr. Teste",
            professional_cns="123456789012345",
            authorizer_name="Ana Autoriza",
            authorizer_cns="123456789012345",
            request_date="20260201",
            authorization_date="20260201",
            discharge_date="20260205",
            attendance_character="01",
            exit_reason="11",
            consultation_number="",
            ine="",
            street_code="",
            street_situation="N",
            budget_source="",
            parliamentary_amendment="",
        )

        blocks = serialize_apac(record)

        self.assertGreaterEqual(len(blocks), 3)
        # bloco 14: 536 + 1 espaco = 537 (confirmado no APCEO26P.JUN)
        self.assertEqual(len(blocks[0]), 537)
        # bloco 06 real: 06 + competencia + NUMERO COMPLETO (13d) + CID
        self.assertEqual(blocks[1], "062026021234567890123A00")
        self.assertEqual(len(blocks[2]), 97)
        self.assertFalse(any(";" in block for block in blocks))
        self.assertTrue(all(block.strip() for block in blocks))

    def test_build_apac_record_from_excel_row(self):
        database = pd.DataFrame([
            {
                "Cpf_Paciente": "12345678909",
                "Cns_Paciente": "123456789012345",
                "Nome_Paciente": "Maria da Silva",
                "Nome_Da_Mae": "Joana Silva",
                "Data_Nascimento": "19900101",
                "Sexo": "F",
                "Cep": "01000000",
                "Logradouro": "Avenida Paulista",
                "Numero_Endereco": "1000",
                "Bairro": "Bela Vista",
                "Codigo_Municipio": "3550308",
                "Nome_Municipio": "Sao Paulo",
                "Telefone": "11999999999",
                "Email": "maria@email.com",
            }
        ])
        row = {
            "Numero_Apac": "1234567890123",
            "Competencia": "202602",
            "Codigo_UF": "35",
            "Cnes_Executante": "4234316",
            "Cnes_Solicitante": "4234316",
            "Inicio_Validade": "20260201",
            "Fim_Validade": "20260228",
            "Tipo_Apac": "003",
            "Tipo_Atendimento": "01",
            "Cpf_Paciente": "123.456.789-09",
            "Nome_Paciente": "",
            "Cod_Procedimento": "040102",
            "Cbo": "225142",
            "Quantidade": "1",
            "Cid_Princ": "A00",
            "Nome_Profissional": "Dr. Teste",
            "Medico_Cns": "123456789012345",
            "Autorizador_Nome": "Ana Autoriza",
            "Autorizador_Cns": "123456789012345",
            "Data_Solicitacao": "20260201",
            "Data_Autorizacao": "20260201",
            "Motivo_Saida": "11",
            "Carater_Atend": "01",
            "Situacao_De_Rua": "N",
        }

        record = build_apac_record_from_row(row, database)

        self.assertEqual(record.patient.cpf, "12345678909")
        self.assertEqual(record.patient.name, "Maria da Silva")
        self.assertEqual(record.procedures[0].code, "040102")

    def test_export_valid_apacs_from_workbook_breaks_into_legacy_blocks(self):
        database = pd.DataFrame([
            {
                "Cpf_Paciente": "12345678909",
                "Nome_Paciente": "Maria da Silva",
                "Nome_Da_Mae": "Joana Silva",
                "Data_Nascimento": "19900101",
                "Sexo": "F",
                "Cep": "01000000",
                "Logradouro": "Avenida Paulista",
                "Numero_Endereco": "1000",
                "Bairro": "Bela Vista",
                "Codigo_Municipio": "3550308",
                "Nome_Municipio": "Sao Paulo",
                "Telefone": "11999999999",
                "Email": "maria@email.com",
            }
        ])
        workbook = {
            "banco_de_dados": database,
            "procedimento_mes": pd.DataFrame([
                {
                    "Numero_Apac": "1234567890123",
                    "Competencia": "202602",
                    "Codigo_UF": "35",
                    "Cnes_Executante": "4234316",
                    "Cnes_Solicitante": "4234316",
                    "Inicio_Validade": "20260201",
                    "Fim_Validade": "20260228",
                    "Tipo_Apac": "003",
                    "Tipo_Atendimento": "01",
                    "Cpf_Paciente": "123.456.789-09",
                    "Nome_Paciente": "",
                    "Cod_Procedimento": "040102",
                    "Cbo": "225142",
                    "Quantidade": "1",
                    "Cid_Princ": "A00",
                    "Nome_Profissional": "Dr. Teste",
                    "Medico_Cns": "123456789012345",
                    "Autorizador_Nome": "Ana Autoriza",
                    "Autorizador_Cns": "123456789012345",
                    "Data_Solicitacao": "20260201",
                    "Data_Autorizacao": "20260201",
                    "Motivo_Saida": "11",
                    "Carater_Atend": "01",
                    "Situacao_De_Rua": "N",
                }
            ]),
        }

        lines = export_valid_apacs_from_workbook(workbook)

        self.assertTrue(lines)
        # larguras do arquivo real: bloco 14 = 537, bloco 06 = variavel,
        # bloco 13 = 44 + espacos ate 97
        self.assertTrue(all(len(line) in (537, 24, 97) for line in lines))
        self.assertFalse(any(";" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
