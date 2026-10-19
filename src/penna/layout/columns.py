"""Colunas canônicas da planilha de entrada (contrato do conversor)."""
from __future__ import annotations

_SECUNDARIOS = tuple(
    f"Sec{i}_{campo}" for i in range(1, 9) for campo in ("Cod_Procedimento", "Cbo", "Quantidade")
)

COLUNAS_PLANILHA = (
    "Numero_Apac", "Numero_Apac_Anterior", "Cnes_Solicitante", "Cnes_Executante",
    "Inicio_Validade", "Fim_Validade", "Tipo_Apac", "Nacionalidade", "No_Prontuario",
    "Cpf_Paciente", "Cns_Paciente", "Situacao_De_Rua", "Nome_Paciente", "Nome_Da_Mae",
    "Nome_Do_Responsavel", "Nome_Profissional", "Cep", "Logradouro", "Rua", "Numero_Endereco",
    "Codigo_Logradouro", "Complemento", "Bairro", "Telefone", "Email", "Codigo_Municipio", "IBGE",
    "Nome_Municipio", "Raca", "Data_Nascimento", "Sexo", "Etnia", "Cod_Procedimento",
    "Cbo", "Quantidade", "Cns_Executante", "Equipe", "Equipe_Area", "Cnes_Terceiro", "Servico",
    "Classif", "Cid_Princ", "Cid_Secun", "Cid_Causas_Assoc", "Cnpj_Fornecedor",
    "Num_Nota_Fiscal", "Data_Identificacao",
    *_SECUNDARIOS,
    "Motivo_Saida", "Data_Alta_Obito", "Carater_Atend", "Medico_Cns", "Medico_Cpf", "Medico_Nome",
    "Data_Solicitacao", "Autorizador_Cns", "Autorizador_Cpf", "Autorizador_Nome",
    "Data_Autorizacao", "Cod_Orgao_Emiss",
)
