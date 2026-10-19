"""Larguras e constantes do layout fixo do TXT APAC-MAG (conferidas no arquivo real).

Estrutura do arquivo:

- ``01#APAC``  cabeçalho (134 caracteres);
- ``14``       corpo da APAC: 536 caracteres + 1 espaço = 537;
- ``06``       CID principal: tipo + competência + nº da APAC (13) + CID (sem padding);
- ``13``       procedimento: 44 caracteres de conteúdo + espaços até 97;
- todas as linhas terminam em CRLF; a última ``13`` fica sem padding (44) e o
  arquivo termina com CRLF duplo.
"""
from __future__ import annotations

BODY_WIDTH = 537            # bloco 14
ACTION_WIDTH = 97           # bloco 13 completo
ACTION_CONTENT_WIDTH = 44   # bloco 13 sem padding
HEADER_ORGAO_WIDTH = 36
HEADER_DESTINO_WIDTH = 40
HEADER_VERSAO_WIDTH = 12

COMPETENCIA_INDEFINIDA = "000000"  # preserva a largura quando o mês não é identificável
MAX_PROCEDIMENTOS_SECUNDARIOS = 9

# Largura dos campos de texto do bloco 14 (coluna da planilha -> largura). Acima
# disso o gerador trunca; o validador avisa (010092).
LARGURA_TEXTO = {
    "Nome_Paciente": 30, "Nome_Da_Mae": 30, "Nome_Do_Responsavel": 30, "Rua": 30,
    "Numero_Endereco": 5, "Complemento": 10, "Bairro": 30, "Email": 40,
    "Nome_Profissional": 30, "Autorizador_Nome": 30, "Cid_Causas_Assoc": 4,
    "No_Prontuario": 10, "Cod_Orgao_Emiss": 10, "INE": 10, "Etnia": 4,
}
