"""Comprovante de remessa no formato do RELEXP.prn do programa original."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import establishment, formatting
from .locations import project_remittances_dir

ESTRELAS = " " + "*" * 78
TIPOS_REMESSA = {"1": "1-NORMAL", "2": "2-CORRECAO", "3": "3-SUBSTITUICAO"}


def montar_comprovante(resumo: Dict[str, Any], est: Dict[str, str], hoje: str) -> List[str]:
    """Linhas do comprovante a partir do resumo da remessa e dos dados do estabelecimento."""
    competencia = resumo.get("competencia", "")
    mes = competencia[4:6] if len(competencia) == 6 else ""
    ano = competencia[:4] if len(competencia) == 6 else ""
    tipo = str(resumo.get("tipo", "1"))
    linhas = [
        ESTRELAS,
        " MS/SAS/DATASUS/0301 SISTEMA DE INFORMACOES AMBULATORIAIS            DATA COMP.",
        f" {hoje}            COMPROVANTE DE REMESSA APAC-MAG               {mes}/{ano}",
        ESTRELAS,
        f"                                Tabela : {competencia}                               ",
        "",
        "  ORGAO RESPONSVEL PELA INFORMACAO ",
        "",
        f"  NOME   : {est['nome']}",
        "",
        f"  SIGLA  : {est['sigla']:<6}",
        "",
        f"  C.G.C. : {formatting.cgc(est['cgc'])}",
        "",
        "",
        "  Carimbo e",
        "  Assinatura : ___________________",
        "",
        "",
        "  SECRETARIA DE SAUDE DESTINO DOS A.P.A.C.(s) ",
        "",
        f"  NOME  : {est['destino']} ",
        "",
        f"  ORGAO (M)UNICIPAL OU (E)STADUAL : {est['indicador']}",
        "",
        "",
        "  Setor de                                       Carimbo e",
        "  Recebimento : __________ Data : ___/___/_____  Assinatura : ________________",
        "",
        "",
        "  ARQUIVO DE APAC(s) GERADO",
        "",
        f"                  NOME : {resumo.get('arquivo', '')}",
        "",
        f"    REGISTROS GRAVADOS : {int(resumo.get('registros', 0)):05d}",
        "",
        f"                PAC(s) : {int(resumo.get('qtde_apacs', 0)):06d}",
        "",
        f"  IDENT. PROCESSAMENTO : {TIPOS_REMESSA.get(tipo, '1-NORMAL')}",
    ]
    if tipo == "3":
        linhas.append(
            "                           CAMPO CONTROLE DA REMESSA A SUBSTITUIR: "
            f"{resumo.get('substituida', '') or '______'}"
        )
    return [*linhas, "", "", ""]


def gerar_comprovante(resumo: Dict[str, Any], destino: Optional[Path] = None) -> Path:
    """Grava o comprovante da remessa (CP1252) e devolve o caminho."""
    linhas = montar_comprovante(resumo, establishment.dados_estabelecimento(), datetime.now().strftime("%d/%m/%Y"))
    if destino is None:
        pasta = Path(resumo.get("pasta") or project_remittances_dir())
        destino = pasta / f"Comprovante_{Path(resumo.get('arquivo', 'remessa')).stem}.PRN"
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes("\r\n".join(linhas).encode("cp1252", errors="replace"))
    return destino
