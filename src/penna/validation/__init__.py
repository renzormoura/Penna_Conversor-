"""Gate de consistência pré-exportação (relatório no formato RCONSIST do APAC-MAG).

Enquanto houver ocorrência ERR o TXT fiscal não pode ser gerado; AVS é listado
e permite gerar. As regras vivem em :mod:`penna.validation.rules` e rodam no
motor de :mod:`penna.validation.engine`.
"""
from .catalog import CATALOGO_CODIGOS, SEVERIDADE_HIPOTESE, SEVERIDADE_PADRAO
from .engine import regras_desativadas, validar_planilha
from .lookups import carregar_base_ceps, carregar_catalogo_procedimentos
from .model import Ocorrencia, ResultadoValidacao, formatar_linha_rconsist, resumo, tem_erros

__all__ = [
    "CATALOGO_CODIGOS",
    "SEVERIDADE_HIPOTESE",
    "SEVERIDADE_PADRAO",
    "Ocorrencia",
    "ResultadoValidacao",
    "carregar_base_ceps",
    "carregar_catalogo_procedimentos",
    "formatar_linha_rconsist",
    "regras_desativadas",
    "resumo",
    "tem_erros",
    "validar_planilha",
]
