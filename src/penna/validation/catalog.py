r"""Catálogo de códigos de ocorrência e suas severidades.

Fontes oficiais (instalação real ``C:\APAC`` e backups ``.ZBF`` decodificados):

- RCONSIST.MAI/.JUN/.NOV/.OUT e R0201.NOV: códigos e mensagens reais;
- S_APAERR.dbf dos backups: log interno de ocorrências;
- LERNOTAS.TXT v03.17..03.26: regras de CPF/CNS/atributos;
- S_PA / S_PAHA / S_PAPA / S_CID / XUPSHA: regras SIGTAP por competência.
"""
from __future__ import annotations

from typing import Dict

from .model import AVS, ERR

CATALOGO_CODIGOS: Dict[str, str] = {
    # ---- ERR (bloqueiam a exportação) ----
    "000016": "PROC.(...) NAO PERMITIDO PARA IDADE MAX.DO USUARIO : n",
    "000024": "PROC.(...) DE APAC PMAE, NAO É PERMITIDO QTD.(     0) ZERO PROC.PRINC. OU SECUNDARIO.",
    "010022": "CEP (nnnnnnnnn) NAO ENCONTRADO",
    "010025": "DATA DE NASCIMENTO INVALIDA",
    "010027": "RACA (nn) INVALIDA",
    "010032": "LOGRADOURO (nnn) INVALIDO",
    "010042": "DATA DE SOLICITACAO (dd/mm/aaaa) ANTERIOR A DATA DE NASCIMENTO(dd/mm/aaaa)",
    "010083": "DATA DE ENCERRAMENTO (dd/mm/aaaa) MAIOR QUE DATA DE FIM (dd/mm/aaaa)",
    "010090": "<CAMPO>: DATA INVALIDA (valor)  [regra local do Penna]",
    "010091": "<CAMPO>: CARACTERE NAO SUPORTADO NO TXT (cp1252/controle)  [regra local do Penna]",
    # 000005 é estrutural (planilha vazia, competência inválida ou mista): sem
    # competência não há arquivo válido, então bloqueia mesmo sem amostra oficial.
    "000005": "COMPETENCIA / NUMERO APAC invalidos para exportacao (estrutural, sem amostra oficial)",
    # ---- AVS (avisos; o original exporta mesmo com eles) ----
    "010084": "NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE",
    "010092": "<CAMPO>: TEXTO MAIOR QUE A LARGURA DO LAYOUT, SERA TRUNCADO  [regra local do Penna]",
    "030001": "CNES EXECUTANTE(nnnnnnn) NAO ENCONTRADO",
    "030008": "PROCED.(...) EXIGE HABILITACAO NAO ENCONTRADA NO CNES(nnnnnnn)",
    "030009": "REGRA CONDICIONADA 0009 : PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS (AVS do R0201)",
    # ---- Códigos HIPOTESE: mensagens no padrão observado (LERNOTAS v03.25), sem
    #      amostra oficial do comportamento. Severidade = SEVERIDADE_HIPOTESE ----
    "000006": "PROC.(...) EXIGE PELO MENOS (n) PROC. SECUNDARIO OBRIGATORIO. (HIPOTESE)",
    "000007": "PROC.(...) NAO PERMITIDO PARA SEXO DO USUARIO (HIPOTESE)",
    "000008": "PROC.(...) QTD. ACIMA DO MAXIMO PERMITIDO : n (HIPOTESE)",
    "000009": "PROC. SECUNDARIO (x) NAO PERMITIDO PARA O PROC. PRINCIPAL (HIPOTESE)",
    "010040": "CID (xxxx) NAO ENCONTRADO (HIPOTESE)",
    "010041": "CID (xxxx) NAO PERMITIDO PARA O SEXO DO USUARIO (HIPOTESE)",
}

# Regras HIPOTESE (sem confirmação do comportamento oficial) só AVISAM: uma
# regra errada bloquearia exportações válidas. Ao confirmar uma regra com uma
# amostra real do RCONSIST, mude esta constante para "ERR" (ou mova o código
# para o grupo ERR acima).
SEVERIDADE_HIPOTESE = AVS

CODIGOS_HIPOTESE = ("000006", "000007", "000008", "000009", "010040", "010041")
CODIGOS_ERR = ("000005", "000016", "000024", "010022", "010025", "010027", "010032",
               "010042", "010083", "010090", "010091")

# Severidade de cada código (fonte única para documentação, relatórios e testes).
SEVERIDADE_PADRAO: Dict[str, str] = {
    cod: (ERR if cod in CODIGOS_ERR else SEVERIDADE_HIPOTESE if cod in CODIGOS_HIPOTESE else AVS)
    for cod in CATALOGO_CODIGOS
}
