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
