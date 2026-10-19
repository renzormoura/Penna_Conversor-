"""Constantes do modelo da ficha, geometria e tabelas de referência."""
from __future__ import annotations

NOME_TEMPLATE = "modelo_ficha_oci_oftalmologia.xlsx"
FOLHA = "OCI OFTALMOLOGIA"
PREFIXO_ORIGINAL = "MODELO_FATURAMENTO_OCI"
_QUEBRA_PAGINA = 69          # quebra do modelo (1..68 / 69..); a ficha usa 1 página
NC = 29                     # colunas A..AC (intervalo usado da aba)
CID_COL_DIR = 13            # coluna M: início do bloco direito da tabela de CIDs
CONSULTAS_INI = 50          # título/nota da lista de consultas do encerramento
CONSULTAS_FIM = 58

# Calibração da geometria contra a impressão do próprio modelo pelo Excel
# (medida por regressão sobre a impressão: resíduo < 0,4 pt nas colunas e
# ~1,5 pt nas linhas). Sem isso a ficha sai com colunas ~8% mais largas e
# linhas ~3% mais altas que o modelo impresso.
TITULOS_SECAO = (
    "DADOS DO PACIENTE",
    "DADOS DO SOLICITANTE",
    "EMISSOR DA OCI",
    "PROCEDIMENTOS",
    "DIAGNOSE EM OFTALMOLOGIA",
    "ENCERRAMENTO DA APAC",
    "MÉDICO AUTORIZADOR DA APAC",
)

PT_PX_COLUNA = 0.798        # pt por "pixel" de largura de coluna
PAD_COLUNA = 0.234          # pt fixos por coluna
FATOR_ALTURA = 0.968        # fator aplicado às alturas de linha

# Células com dados do paciente de exemplo — em branco quando o arquivo
# original (com fórmulas/amostra) é usado como fallback.
CELULAS_DADOS = (
    "I2", "J3", "U3", "C5", "C9", "K9", "S9", "G10", "C12", "D12", "K12",
    "U12", "V12", "F13", "C15", "J15", "K15", "L15", "X15", "F16", "J16",
    "U16", "C21", "K21", "K22", "J23", "Q23", "H24", "G29", "V29", "F30",
    "N30", "N35", "T35", "R52", "R53", "J59", "W59", "F60", "V60", "I70",
    "J71", "U71", "C73", "I110", "H111",
)

# Tabelas de referência da aba REFEENCIAS do próprio modelo
SEXOS = {"M": "MASCULINO", "F": "FEMININO"}
RACAS = {
    "1": "BRANCO", "01": "BRANCO",
    "2": "PRETO", "02": "PRETO",
    "3": "PARDO", "03": "PARDO",
    "4": "INDIGENA", "04": "INDIGENA",
    "5": "AMARELO", "05": "AMARELO",
    "99": "SEM INFORMACAO",
}
TIPOS_LOGRADOURO = {"8": "AV.", "81": "RUA", "31": "EST."}

# Células do modelo que carregam texto institucional (com acentos) — usadas
# como fallback quando o template slim (dados limpos) não tem o valor.
_CELULAS_COM_TEXTO_ORIGINAL = (
    "I2", "U3", "C5", "K21",
)

# Cores/medidas de impressão (espelham o modelo; ui/theme.py é o espelho da UI)
GRADE_COR = "#D9D9D9"           # linhas de grade (como no Excel)
GRADE_ESP = 0.55
BORDA_ESP = {"thin": 0.6, "medium": 1.25, "hair": 0.35, "double": 1.25,
              "thick": 1.6, "dashed": 0.6, "mediumDashed": 1.25}
INSET = 1.5                     # folga do texto dentro da célula (2 px do Excel)
# Índice de tema do arquivo -> posição no clrScheme do tema. Este modelo (como
# os arquivos escritos pelo Excel) usa a paleta da interface: 0 = fundo 1
# (lt1/branco), 1 = texto 1 (dk1/preto), 2 = fundo 2 (lt2), 3 = texto 2 (dk2)
# e 4..9 = accent1..6. Com 0 = branco as barras de seção saem corretas (o
# modelo usa fundo branco + borda grossa preta, não barra preta).
TEMA_MAPA = (1, 0, 3, 2, 4, 5, 6, 7, 8, 9, 10, 11)
