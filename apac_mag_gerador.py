"""Gerador de arquivo fiscal APAC-MAG (SIA/DATASUS).

Lê uma planilha Excel e gera o arquivo TXT de layout fixo no padrão
APAC-MAG do programa antigo, compatível bit-a-bit com o formato
confirmado no arquivo real APCEO26P.JUN (competência 202606).

Formato fiscal confirmado:
- header '01#APAC' + competencia + qtde APACs (6d) + checksum (4d)
  + orgao(36) + cgc(14) + destino(40) + indicador M/E + dtger(8) + versao(12), CRLF
- checksum = (soma APACs + soma procs + soma qtds) mod 1111 + 1111 (4 dígitos)
- bloco 14 = 536 chars + 1 espaço = 537
- bloco 06 = 06 + competencia + NUMERO COMPLETO (13d) + CID (sem padding)
- bloco 13 = 44 conteúdo + espaços até 97 (última linha sem padding, CRLF duplo)
- IBGE = 6 dígitos + espaço (330280 )
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Helpers de string e configuração: fonte única de verdade
# ---------------------------------------------------------------------------
from apac_mag.normalization import (
    date_to_ddmmaa,
    digits as _digits_fn,
    nascimento_to_aaaammdd,
    normalize_competence,
    pad_left,
    pad_right,
    resolve_block_value,
    resolve_competence,
    resolve_row_value,
    text,
    text_upper,
)
from apac_mag.config import get_defaults, get_header, get_versao

# ---------------------------------------------------------------------------
# Constantes de layout (imutáveis — não dependem de configuração)
# ---------------------------------------------------------------------------
EXCEL_FILE_NAME = "dados_completos_penna.xlsx"
TEST_FILE_NAME = "excel_teste.xlsx"
OUTPUT_FILE_NAME = "PENNA_COMPLETO_FINAL.txt"
TEST_OUTPUT_FILE_NAME = "teste_formatado.txt"
DATA_FOLDER_NAME = "dados"
OUTPUT_FOLDER_NAME = "Formatado"

BLOCK_01_WIDTH = 537   # corpo da APAC (tipo 14): 536 + 1 espaço
BLOCK_03_WIDTH = 97    # ações da APAC (tipo 13): 44 + 53 espaços
HEADER_ORGAO_RESP_WIDTH = 36  # campo do orgão no header (confirmado no arquivo real)

# ---------------------------------------------------------------------------
# Constantes do estabelecimento: lidas do penna_config.json em runtime.
# Os atributos de módulo abaixo mantêm retrocompatibilidade com
# apac_mag_remessa.py e apac_mag_validador.py que os importavam diretamente.
# ---------------------------------------------------------------------------

def _hdr() -> Dict[str, str]:
    return get_header()

def _dfl() -> Dict[str, str]:
    return get_defaults()


@property  # não é property real aqui; usamos função para lazy-load
def _lazy_header_orgao() -> str:
    return _hdr()["orgao_responsavel"]


# Aliases de módulo para retrocompatibilidade (avaliados na primeira leitura)
# Estes são avaliados uma vez e armazenam o valor; o config pode ser
# recarregado via apac_mag.config.reload() se necessário.
def _get_header_const(key: str) -> str:
    return get_header().get(key, "")


HEADER_ORGAO_RESP: str = ""        # preenchido abaixo
HEADER_CGC: str = ""
HEADER_DESTINO: str = ""
HEADER_DESTINO_INDICADOR: str = ""
HEADER_VERSAO: str = ""


def _init_header_consts() -> None:
    """Inicializa as constantes HEADER_* a partir do config em disco."""
    global HEADER_ORGAO_RESP, HEADER_CGC, HEADER_DESTINO
    global HEADER_DESTINO_INDICADOR, HEADER_VERSAO
    h = get_header()
    HEADER_ORGAO_RESP = h.get("orgao_responsavel", "")
    HEADER_CGC = h.get("cgc", "")
    HEADER_DESTINO = h.get("destino", "")
    HEADER_DESTINO_INDICADOR = h.get("destino_indicador", "M")
    HEADER_VERSAO = h.get("versao", "Versao 04.01")


_init_header_consts()

# DEFAULT_VALUES: dict vivo que reflete o config — mantido como variável de
# módulo para retrocompatibilidade com apac_mag_validador e apac_mag_remessa.
DEFAULT_VALUES: Dict[str, str] = _dfl()

# ---------------------------------------------------------------------------
# Colunas garantidas no DataFrame
# ---------------------------------------------------------------------------
COLUNAS_PLANILHA = (
    "Numero_Apac", "Numero_Apac_Anterior", "Cnes_Solicitante", "Cnes_Executante",
    "Inicio_Validade", "Fim_Validade", "Tipo_Apac", "Nacionalidade", "No_Prontuario",
    "Cpf_Paciente", "Cns_Paciente", "Situacao_De_Rua", "Nome_Paciente", "Nome_Da_Mae",
    "Nome_Do_Responsavel", "Nome_Profissional", "Cep", "Logradouro", "Rua", "Numero_Endereco",
    "Codigo_Logradouro", "Complemento", "Bairro", "Telefone", "Email", "Codigo_Municipio", "IBGE",
    "Nome_Municipio", "Raca", "Data_Nascimento", "Sexo", "Etnia", "Cod_Procedimento",
    "Cbo", "Quantidade", "Cns_Executante", "Equipe", "Equipe_Area", "Cnes_Terceiro", "Servico",
    "Classif", "Cid_Princ", "Cid_Secun", "Cid_Causas_Assoc", "Cnpj_Fornecedor",
    "Num_Nota_Fiscal", "Data_Identificacao", "Sec1_Cod_Procedimento", "Sec1_Cbo", "Sec1_Quantidade",
    "Sec2_Cod_Procedimento", "Sec2_Cbo", "Sec2_Quantidade", "Sec3_Cod_Procedimento",
    "Sec3_Cbo", "Sec3_Quantidade", "Sec4_Cod_Procedimento", "Sec4_Cbo", "Sec4_Quantidade",
    "Sec5_Cod_Procedimento", "Sec5_Cbo", "Sec5_Quantidade", "Sec6_Cod_Procedimento",
    "Sec6_Cbo", "Sec6_Quantidade", "Sec7_Cod_Procedimento", "Sec7_Cbo", "Sec7_Quantidade",
    "Sec8_Cod_Procedimento", "Sec8_Cbo", "Sec8_Quantidade", "Motivo_Saida",
    "Data_Alta_Obito", "Carater_Atend", "Medico_Cns", "Medico_Cpf", "Medico_Nome",
    "Data_Solicitacao", "Autorizador_Cns", "Autorizador_Cpf", "Autorizador_Nome",
    "Data_Autorizacao", "Cod_Orgao_Emiss",
)

# ---------------------------------------------------------------------------
# Helpers locais que ainda não têm equivalente em normalization
# (apenas lógica de negócio APAC-específica)
# ---------------------------------------------------------------------------

def normalize_name(value: Any) -> str:
    """Normaliza nome de coluna para comparação (usado em resolve_row_value)."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = s.replace(" ", "_").replace("-", "_").replace("/", "_")
    return re.sub(r"_+", "_", s)


def to_text(value: Any) -> str:
    """Alias para text() — mantido para retrocompatibilidade."""
    return text(value)


def only_digits(value: Any, default: str = "0") -> str:
    """Alias para digits() com suporte a default — retrocompatibilidade."""
    d = _digits_fn(value)
    return d if d else default


def competence_from_row(row: Dict[str, Any]) -> str:
    """Competência (AAAAMM) analisada a partir do próprio formulário.

    Usa a coluna Competencia em qualquer formato reconhecível (AAAAMM,
    AAAAMMDD, DDMMAAAA, MM/AAAA, datetime) e, quando ela não existe,
    analisa as datas do formulário (autorização, solicitação, alta,
    validade) — o mês dos formularios. Sem identificação, devolve
    '000000' para preservar a largura fixa do layout.
    """
    return resolve_competence(row) or "000000"


def uf_from_row(row: Dict[str, Any], code: str = "") -> str:
    """Extrai o código da UF (2 dígitos) da linha."""
    value = resolve_row_value(row, "Codigo_UF", "Código_UF", "UF", "AP_CODUF")
    if not value:
        value = re.sub(r"\D", "", resolve_row_value(row, "Cod_Orgao_Emiss"))[:2]
    if not value:
        value = re.sub(r"\D", "", code)[:2]
    return value[-2:].zfill(2)


def _ibge_code(row: Dict[str, Any]) -> str:
    """Código IBGE do município: 6 dígitos + espaço (sem DV), como no arquivo
    real do programa antigo (330280 ). Sem valor, usa o default do config."""
    raw = text(resolve_block_value(row, "Codigo_Municipio", resolve_block_value(row, "IBGE", "")))
    d = _digits_fn(raw)
    if len(d) < 6:
        d = _digits_fn(DEFAULT_VALUES.get("Codigo_Municipio", ""))
    if len(d) < 6:
        return " " * 7
    return d[:6] + " "


def _num_field(value: Any, width: int) -> str:
    """Campo numérico: zeros à esquerda quando há valor; brancos quando não há.
    Textos não numéricos (ex.: 'AMB') são descartados, como no sistema oficial."""
    d = _digits_fn(value)
    if not d:
        return " " * width
    return d.rjust(width, "0")


def _apac_num_varia(row: Dict[str, Any]) -> str:
    """Número da APAC nos blocos 06/13: NÚMERO COMPLETO de 13 dígitos.
    Confirmado no arquivo real APCEO26P.JUN do programa antigo."""
    return pad_left(resolve_block_value(row, "Numero_Apac", "0"), 13, "0")


# ---------------------------------------------------------------------------
# Serialização dos blocos de layout fixo
# ---------------------------------------------------------------------------

def build_block_01(row: Dict[str, Any]) -> str:
    """Bloco tipo 14 — corpo da APAC (537 chars).

    Serializa todos os dados cadastrais do paciente e da autorização no
    formato confirmado no arquivo real APCEO26P.JUN.
    """
    dfl = DEFAULT_VALUES  # referência local para legibilidade

    numero_apac = pad_left(resolve_block_value(row, "Numero_Apac", "0"), 13, "0")
    competencia = competence_from_row(row)
    uf = uf_from_row(row, numero_apac)
    cnes = pad_left(resolve_block_value(row, "Cnes_Executante", dfl["Cnes_Executante"]), 7, "0")

    # Data de processamento (apa_pr): no programa antigo é o 1º dia da
    # competência (ex.: 202606 → 20260601, confirmado no APCEO26P.JUN).
    data_emissao = resolve_row_value(row, "Data_Emissao")
    if not data_emissao:
        data_emissao = competence_from_row(row)[:6] + "01"
    data_emissao = date_to_ddmmaa(data_emissao)

    inicio = date_to_ddmmaa(resolve_block_value(row, "Inicio_Validade", ""))
    fim = date_to_ddmmaa(resolve_block_value(row, "Fim_Validade", ""))
    tipo_atendimento = pad_left(resolve_row_value(row, "Tipo_Atendimento", "Tip_Atendimento") or "00", 2, "0")
    tipo = pad_left(resolve_block_value(row, "Tipo_Apac", dfl["Tipo_Apac"]), 1, "0")
    nome_paciente = pad_right(text_upper(resolve_block_value(row, "Nome_Paciente", "")), 30)
    nome_mae = pad_right(text_upper(resolve_block_value(row, "Nome_Da_Mae", "")), 30)
    endereco = pad_right(
        text_upper(resolve_block_value(row, "Rua", resolve_block_value(row, "Logradouro", ""))), 30
    )
    # Número do endereço: alinhado à ESQUERDA com espaços (arquivo real: '487  ')
    numero = pad_right(resolve_block_value(row, "Numero_Endereco", ""), 5)
    complemento = pad_right(resolve_block_value(row, "Complemento", ""), 10)
    cep = pad_left(resolve_block_value(row, "Cep", ""), 8, "0")
    ibge = _ibge_code(row)
    data_nasc = nascimento_to_aaaammdd(resolve_block_value(row, "Data_Nascimento", ""))
    # Sexo tem largura fixa 1: sem valor, ocupa a posição com espaço para não
    # deslocar os campos seguintes da linha.
    sexo = text_upper(resolve_block_value(row, "Sexo", ""))[:1] or " "
    nome_solicitante = pad_right(text_upper(resolve_block_value(row, "Nome_Profissional", "")), 30)
    codigo_proc = pad_left(resolve_block_value(row, "Cod_Procedimento", ""), 10, "0")
    codigo_cob = pad_left(resolve_block_value(row, "Motivo_Saida", dfl["Motivo_Saida"]), 2, "0")
    data_correcao = date_to_ddmmaa(resolve_block_value(row, "Data_Alta_Obito", ""))
    nome_diretor = pad_right(text_upper(resolve_block_value(row, "Autorizador_Nome", "")), 30)

    # CNS do paciente: brancos quando ausente (confirmado no APCEO26P.JUN)
    # CNS do responsável/diretor: zeros quando ausente
    cns_pac_d = _digits_fn(resolve_block_value(row, "Cns_Paciente", ""))
    cns_paciente = pad_left(cns_pac_d, 15, "0") if cns_pac_d else " " * 15
    cns_responsavel = pad_left(only_digits(resolve_block_value(row, "Medico_Cns", ""), "0"), 15, "0")
    cns_diretor = pad_left(only_digits(resolve_block_value(row, "Autorizador_Cns", ""), "0"), 15, "0")

    cid_causa = pad_right(text_upper(resolve_block_value(row, "Cid_Causas_Assoc", "")), 4)
    prontuario = pad_right(resolve_block_value(row, "No_Prontuario", ""), 10)
    cnes_solicitante = pad_left(resolve_block_value(row, "Cnes_Solicitante", cnes), 7, "0")
    data_solic = date_to_ddmmaa(resolve_block_value(row, "Data_Solicitacao", ""))
    data_aut = date_to_ddmmaa(resolve_block_value(row, "Data_Autorizacao", ""))
    codigo_orgao = pad_right(resolve_block_value(row, "Cod_Orgao_Emiss", dfl["Cod_Orgao_Emiss"]), 10)
    carater = pad_left(resolve_block_value(row, "Carater_Atend", dfl["Carater_Atend"]), 2, "0")
    apac_anterior = pad_left(
        only_digits(resolve_block_value(row, "Numero_Apac_Anterior", dfl["Numero_Apac_Anterior"]), "0"),
        13,
        "0",
    )
    # Raça/cor: obrigatória (01..05, 99 = sem informação)
    raca = pad_left(resolve_block_value(row, "Raca", "") or "99", 2, "0")
    # Campo responsável: quando vazio, antigo grava o nome do paciente
    # (confirmado no arquivo real)
    nome_responsavel = pad_right(
        text_upper(
            resolve_block_value(row, "Nome_Do_Responsavel") or resolve_block_value(row, "Nome_Paciente", "")
        ),
        30,
    )
    uf_nascimento = pad_right(resolve_row_value(row, "Uf_Nascimento", "UF_Nascimento") or "010", 3)
    etnia = pad_right(resolve_block_value(row, "Etnia", ""), 4)

    # Código do logradouro: planilha guarda o código da via em 'Logradouro'
    # (ex.: 081 = rua, 100 = travessa). Cai para Codigo_Logradouro se existir.
    codigo_logradouro = resolve_row_value(row, "Codigo_Logradouro", "Cod_Logradouro")
    if not codigo_logradouro:
        codigo_logradouro = _digits_fn(resolve_block_value(row, "Logradouro", ""))
    codigo_logradouro = pad_right(codigo_logradouro or "", 3)

    bairro = pad_right(text_upper(resolve_block_value(row, "Bairro", "")), 30)
    telefone = re.sub(r"\D", "", resolve_block_value(row, "Telefone", ""))
    ddd = pad_left(telefone[:2], 2, "0") if telefone else "  "
    telefone_num = pad_left(telefone[-9:], 9, "0") if telefone else "         "
    email = pad_right(resolve_block_value(row, "Email", ""), 40)

    # CNS do médico executante: cascata de fallbacks para não exportar zerado
    cns_exec_d = _digits_fn(resolve_block_value(row, "Cns_Executante", ""))
    if not cns_exec_d:
        cns_exec_d = _digits_fn(resolve_block_value(row, "Medico_Cns", ""))
    if not cns_exec_d:
        cns_exec_d = _digits_fn(dfl.get("Cns_Executante", ""))
    cns_exec = pad_left(cns_exec_d, 15, "0") if cns_exec_d else "0" * 15

    # CPF sem pontuação (AP_CPFPAC)
    cpf_pac = _num_field(resolve_block_value(row, "Cpf_Paciente", ""), 11)
    ine = pad_right(resolve_block_value(row, "INE", ""), 10)
    # Situação de rua: "S"/"N"; antigo grava "N" quando sem informação
    situacao_rua = pad_right(text_upper(resolve_block_value(row, "Situacao_De_Rua", "") or "N"), 1)
    fonte_orcamento = pad_right(resolve_block_value(row, "Fonte_Orcamentaria", ""), 2)
    emenda = pad_right(resolve_block_value(row, "Emenda_Parlamentar", ""), 1)

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
        + ine
        + situacao_rua
        + fonte_orcamento
        + emenda
    )
    return content.ljust(BLOCK_01_WIDTH)


def build_block_02(row: Dict[str, Any]) -> str:
    """Bloco tipo 06 — CID principal.

    Formato real: 06 + competencia + numero completo (13d) + CID (sem padding).
    O sistema antigo grava o CID exatamente como digitado (ex.: 'H40' = 3 chars).
    """
    cid = re.sub(r"[^A-Z0-9]", "", text_upper(resolve_block_value(row, "Cid_Princ", "")))[:4]
    if not cid:
        return ""
    return "06" + competence_from_row(row) + _apac_num_varia(row) + cid


def build_block_03(row: Dict[str, Any], code_field: str, cbo_field: str, q_field: str, motivo: str) -> str:
    """Bloco tipo 13 — procedimento/ação (97 chars, último sem padding).

    Formato real: 13 + competencia + numero (13d) + procedimento (10d)
    + CBO (6d) + quantidade (7d) = 44 chars + espaços até 97.
    O sistema antigo NÃO exporta CNPJ/NF/CID/Serviço/Classificação/Equipe/Terceiro.
    """
    code = pad_left(resolve_block_value(row, code_field, ""), 10, "0")
    cbo = pad_left(resolve_block_value(row, cbo_field, ""), 6, "0")
    qtd = pad_left(resolve_block_value(row, q_field, ""), 7, "0")
    bloco = "13" + competence_from_row(row) + _apac_num_varia(row) + code + cbo + qtd
    return bloco.ljust(BLOCK_03_WIDTH)


def build_secondary_block(row: Dict[str, Any], index: int) -> str:
    """Bloco tipo 13 para procedimento secundário (Sec1..Sec9)."""
    code_field = f"Sec{index}_Cod_Procedimento"
    if not resolve_block_value(row, code_field, ""):
        return ""
    return build_block_03(row, code_field, f"Sec{index}_Cbo", f"Sec{index}_Quantidade", "Motivo_Saida")


def build_patient_lines(row: Dict[str, Any]) -> List[str]:
    """Gera todos os blocos (14, 06, 13) para uma linha da planilha."""
    linhas: List[str] = []

    b01 = build_block_01(row)
    if b01.strip():
        linhas.append(b01)

    b02 = build_block_02(row)
    if b02.strip():
        linhas.append(b02)

    b_princ = build_block_03(row, "Cod_Procedimento", "Cbo", "Quantidade", "Motivo_Saida")
    if b_princ.strip():
        linhas.append(b_princ)

    for index in range(1, 10):
        b_sec = build_secondary_block(row, index)
        if b_sec.strip():
            linhas.append(b_sec)

    return [linha for linha in linhas if linha.strip()]


# ---------------------------------------------------------------------------
# Header e checksum
# ---------------------------------------------------------------------------

def _competencia_header(linhas: List[str]) -> str:
    """Competência do header: analisada nos blocos 14 do arquivo.

    Pula blocos com '000000' (linha sem mês identificável) e usa o primeiro
    bloco que traz a competência real dos formularios.
    """
    for linha in linhas:
        if linha.startswith("14"):
            competencia = linha[2:8]
            if competencia and competencia != "000000":
                return competencia
    return competence_from_row({})


def _calcular_checksum(linhas: List[str]) -> str:
    """Checksum do header (validado no arquivo real APCEO26P.JUN, '1155').

    Fórmula: (soma APACs + soma procs + soma qtds) mod 1111 + 1111, 4 dígitos.
    """
    total = 0
    for linha in linhas:
        tipo = linha[:2]
        if tipo == "14":
            total += int(linha[8:21])
        elif tipo == "13":
            total += int(linha[21:31])
            qtd = re.sub(r"\D", "", linha[37:44]) or "0"
            total += int(qtd)
    return str(total % 1111 + 1111)


def _montar_header(linhas: List[str]) -> str:
    """Header '01#APAC...' com 134 chars, idêntico ao programa antigo.

    A versão final (campo de 12 chars) vem da escolha por mês
    (config.get_versao): header.versao_por_mes[competência] quando o
    usuário definiu, senão header.versao — sempre cortada/ajustada a 12
    para preservar o layout.
    """
    # Relê o config a cada geração para refletir mudanças em runtime
    h = get_header()
    qtde_apacs = sum(1 for linha in linhas if linha.startswith("14"))
    competencia = _competencia_header(linhas)
    dt_geracao = pd.Timestamp.today().strftime("%Y%m%d")
    versao = pad_right(get_versao(competencia), 12)
    return (
        "01"
        + "#APAC"
        + competencia
        + str(qtde_apacs).rjust(6, "0")
        + _calcular_checksum(linhas)
        + pad_right(text_upper(h["orgao_responsavel"]), HEADER_ORGAO_RESP_WIDTH)
        + _digits_fn(h["cgc"]).rjust(14, "0")
        + pad_right(text_upper(h["destino"]), 40)
        + h["destino_indicador"][:1]
        + dt_geracao
        + versao
    )


# ---------------------------------------------------------------------------
# Mês da competência -> extensão fixa do arquivo final (APCEO26P.JUN)
# ---------------------------------------------------------------------------

MESES_SIGLA = {
    "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR", "05": "MAI", "06": "JUN",
    "07": "JUL", "08": "AGO", "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ",
}


def sigla_mes_competencia(competencia: Any) -> str:
    """'202606' -> 'JUN'; '' quando a competência não identifica o mês."""
    comp = normalize_competence(competencia)
    if not comp:
        return ""
    return MESES_SIGLA.get(comp[4:6], "")


def extensao_mes_competencia(competencia: Any) -> str:
    """'202606' -> '.JUN': o final fixo do nome do arquivo final."""
    sigla = sigla_mes_competencia(competencia)
    return f".{sigla}" if sigla else ""


def forcar_extensao_mes(caminho: Any, competencia: Any) -> Path:
    """Garante que o arquivo final termine com a extensão do mês.

    O nome é livre (escolha do usuário); o final é fixo pelo mês da
    competência: 'meu.txt' -> 'meu.JUN', 'meu.JUL' -> 'meu.JUN'.
    Sem competência identificada, o nome é devolvido intacto.
    """
    extensao = extensao_mes_competencia(competencia)
    if not extensao:
        return Path(caminho)
    path = Path(caminho)
    try:
        return path.with_suffix(extensao)
    except ValueError:
        return path.parent / (path.name + extensao)


def competencia_da_planilha(df: Any) -> str:
    """Mês dos formularios: primeira competência identificada nas linhas."""
    try:
        for _, serie in df.iterrows():
            competencia = resolve_competence(dict(serie))
            if competencia:
                return competencia
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# I/O: leitura da planilha e exportação do TXT
# ---------------------------------------------------------------------------

def _avisar_apacs_sem_numero(df: pd.DataFrame) -> List[int]:
    """Numeração vem SEMPRE da coluna Numero_Apac (regra: o gerador NÃO
    inventa números). Normaliza a coluna e devolve as linhas (base 2) sem
    número válido — quem exibe o aviso é o chamador (CLI/status bar).

    Efeito colateral necessário: garante Numero_Apac como string.
    """
    if "Numero_Apac" not in df.columns:
        df["Numero_Apac"] = ""
    df["Numero_Apac"] = df["Numero_Apac"].where(df["Numero_Apac"].notna(), "").astype(str)

    return [
        pos
        for pos, numero in enumerate(df["Numero_Apac"], start=2)
        if not re.sub(r"\D", "", numero) or set(re.sub(r"\D", "", numero)) == {"0"}
    ]


def carregar_planilha(caminho: Path) -> pd.DataFrame:
    """Lê o Excel e garante todas as colunas esperadas como strings."""
    df = pd.read_excel(caminho, dtype=str, engine="openpyxl", keep_default_na=False)
    for coluna in COLUNAS_PLANILHA:
        if coluna not in df.columns:
            df[coluna] = ""
    # Garante que células vazias sejam strings vazias (não NaN)
    for coluna in DEFAULT_VALUES:
        if coluna in df.columns:
            df[coluna] = df[coluna].fillna("")
    return df.fillna("")


def exportar_txt(df: pd.DataFrame, caminho_saida: Path) -> pd.DataFrame:
    """Gera o arquivo TXT fiscal em CP1252 no padrão APAC-MAG."""
    _avisar_apacs_sem_numero(df)
    linhas: List[str] = []

    for _, row in df.iterrows():
        linhas.extend(build_patient_lines(row.to_dict()))

    linhas = [linha for linha in linhas if linha.strip()]

    # Formato do programa antigo (APCEO26P.JUN):
    # - todas as linhas terminam com CRLF
    # - última linha de bloco 13 fica sem padding (44 chars)
    # - arquivo termina com CRLF duplo
    if linhas:
        if linhas[-1].startswith("13") and len(linhas[-1]) == BLOCK_03_WIDTH:
            linhas[-1] = linhas[-1][:44]
        linhas.insert(0, _montar_header(linhas))

    texto = "".join(linha + "\r\n" for linha in linhas) + "\r\n"
    caminho_saida.write_bytes(texto.encode("cp1252", errors="replace"))
    _salvar_numeracao_usada(df)
    return df


def exportar_txt_com_numeracao(df: pd.DataFrame, caminho_saida: Path) -> pd.DataFrame:
    """Exporta o TXT e devolve o DataFrame (retrocompatibilidade)."""
    exportar_txt(df, caminho_saida)
    return df


def _salvar_numeracao_usada(df: pd.DataFrame, caminho: Optional[Path] = None) -> None:
    """Grava a numeração usada em CSV de acompanhamento (pasta Formatado)."""
    try:
        destino = caminho or (Path(__file__).resolve().parent / OUTPUT_FOLDER_NAME / "numeracao_apac_usada.csv")
        destino.parent.mkdir(exist_ok=True, parents=True)
        colunas = [c for c in ("Numero_Apac", "Nome_Paciente", "Cpf_Paciente", "Cod_Procedimento") if c in df.columns]
        if not colunas or df.empty:
            return
        df[colunas].copy().to_csv(destino, index=False, encoding="utf-8-sig", sep=";")
    except (OSError, ValueError, KeyError):
        # Registro de numeração é de acompanhamento: nunca interrompe a exportação.
        pass


def localizar_planilha(base_dir: Path) -> Path:
    """Localiza a planilha de entrada na ordem de prioridade."""
    for desktop in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"):
        candidate = desktop / "base exemplo.xlsx"
        if candidate.exists():
            return candidate

    pasta_dados = base_dir / DATA_FOLDER_NAME
    if pasta_dados.exists():
        for nome in (TEST_FILE_NAME, EXCEL_FILE_NAME):
            c = pasta_dados / nome
            if c.exists():
                return c
        candidatos = list(pasta_dados.rglob("*.xlsx")) + list(pasta_dados.rglob("*.xlsm"))
        if candidatos:
            return candidatos[0]

    raiz = base_dir / EXCEL_FILE_NAME
    if raiz.exists():
        return raiz

    return pasta_dados / EXCEL_FILE_NAME


# ---------------------------------------------------------------------------
# Entry point CLI
# ---------------------------------------------------------------------------

def main() -> None:
    base_dir = Path(__file__).resolve().parent
    caminho_excel = localizar_planilha(base_dir)
    pasta_saida = base_dir / OUTPUT_FOLDER_NAME
    pasta_saida.mkdir(exist_ok=True, parents=True)

    if caminho_excel.name.lower() == TEST_FILE_NAME.lower():
        nome_saida = TEST_OUTPUT_FILE_NAME
    elif caminho_excel.name.lower() == "base exemplo.xlsx":
        nome_saida = "base_exemplo_formatado.txt"
    else:
        nome_saida = OUTPUT_FILE_NAME
    caminho_saida = pasta_saida / nome_saida

    print("Iniciando geracao do Penna...")
    if not caminho_excel.exists() or caminho_excel.is_dir():
        print(f"Erro: planilha nao encontrada em {base_dir / DATA_FOLDER_NAME}.")
        print(f"Coloque {EXCEL_FILE_NAME} ou {TEST_FILE_NAME} na pasta '{DATA_FOLDER_NAME}'.")
        return

    try:
        df = carregar_planilha(caminho_excel)
        if df.empty:
            print("Atencao: planilha vazia. Nenhuma linha exportada.")
            caminho_saida.write_text("", encoding="latin-1")
            return
        problematicas = _avisar_apacs_sem_numero(df)
        if problematicas:
            exemplo = ", ".join(str(p) for p in problematicas[:10])
            sufixo = "..." if len(problematicas) > 10 else ""
            print(f"ATENCAO: {len(problematicas)} linha(s) sem Numero_Apac valido: {exemplo}{sufixo}")
            print("  Essas APACs serao exportadas com numero zerado. Preencha a coluna.")
        exportar_txt(df, caminho_saida)
        print(f"Processo concluido. Arquivo: {caminho_saida}")
    except Exception as exc:
        print(f"Erro durante a geracao: {exc}")
        print("Verifique os nomes das colunas na planilha.")


if __name__ == "__main__":
    main()
