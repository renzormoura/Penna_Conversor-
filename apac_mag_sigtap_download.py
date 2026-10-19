r"""Download e conversao das tabelas SIGTAP do FTP publico do DATASUS.

O DATASUS disponibiliza mensalmente arquivos ZIP da Tabela Unificada em:
    ftp://ftp2.datasus.gov.br/pub/sistemas/tup/downloads/
    TabelaUnificada_AAAAMM_vAAMMDDHHMM.zip  (~2 MB cada)

Cada ZIP contem arquivos TXT de largura fixa com os dados equivalentes
as tabelas DBF usadas pelo programa APAC-MAG:

    ZIP (SIGTAP)                        -> DBF do APAC-MAG
    rl_procedimento_regra_cond.txt      -> S_PAREGR  (regras condicionadas)
    rl_procedimento_compativel.txt      -> S_PAPA    (pares principal/secund.)
    rl_procedimento_habilitacao.txt     -> S_PAHA    (habilitacoes exigidas)
    tb_procedimento.txt                 -> S_PA      (catalogo de procedimentos)
    tb_cid.txt                          -> S_CID     (CIDs validos + restricao)

Este modulo:
  - lista as competencias disponiveis no FTP (listar_competencias_ftp)
  - lista as que ja estao em cache local (listar_competencias_cache)
  - baixa e parseia um ZIP em memoria, devolvendo dicts compativeis
    com apac_mag_bases (carregar_sigtap_competencia)
  - mantem um cache em memoria por competencia dentro do processo

Nao lanca excecao por falha de rede ou dado invalido: devolve None/{}
e o chamador desativa a regra (nunca falso positivo).
"""
from __future__ import annotations

import ftplib
import io
import re
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constantes do FTP
# ---------------------------------------------------------------------------

FTP_HOST = "ftp2.datasus.gov.br"
FTP_DIR  = "/pub/sistemas/tup/downloads"
# padrao: TabelaUnificada_AAAAMM_vAAMMDDHHMM.zip
_RE_NOME = re.compile(r"TabelaUnificada_(\d{6})_v\d+\.zip", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Cache em memoria: competencia -> dict de tabelas parseadas
# ---------------------------------------------------------------------------
_cache_sigtap: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Diretorio de cache em disco
# ---------------------------------------------------------------------------

def _dir_cache() -> Path:
    """Pasta onde os ZIPs baixados sao guardados para reuso offline."""
    import os, sys
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    pasta = base / "dados" / "sigtap_cache"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


# ==============================================================================
# Listagem de competencias
# ==============================================================================

def listar_competencias_ftp(timeout: int = 10) -> List[str]:
    """Lista competencias disponiveis no FTP do DATASUS (AAAAMM).

    Devolve lista ordenada decrescente. [] em caso de erro de rede.
    """
    try:
        with ftplib.FTP(timeout=timeout) as ftp:
            ftp.connect(FTP_HOST, timeout=timeout)
            ftp.login()
            ftp.cwd(FTP_DIR)
            linhas: List[str] = []
            ftp.retrlines("LIST", linhas.append)
        competencias = []
        for linha in linhas:
            partes = linha.split()
            if not partes:
                continue
            nome = partes[-1]
            m = _RE_NOME.match(nome)
            if m:
                competencias.append(m.group(1))
        return sorted(set(competencias), reverse=True)
    except Exception:
        return []


def listar_competencias_cache() -> List[str]:
    """Competencias ja baixadas em disco (AAAAMM), ordenadas decrescente."""
    pasta = _dir_cache()
    comps = []
    for f in pasta.glob("TabelaUnificada_??????.zip"):
        m = re.match(r"TabelaUnificada_(\d{6})\.zip", f.name, re.IGNORECASE)
        if m:
            comps.append(m.group(1))
    return sorted(set(comps), reverse=True)


def _nome_arquivo_ftp(competencia: str, lista_ftp: Optional[List[str]] = None) -> Optional[str]:
    """Retorna o nome exato do arquivo ZIP no FTP para a competencia."""
    try:
        with ftplib.FTP(timeout=15) as ftp:
            ftp.connect(FTP_HOST, timeout=15)
            ftp.login()
            ftp.cwd(FTP_DIR)
            linhas: List[str] = []
            ftp.retrlines("LIST", linhas.append)
        for linha in linhas:
            partes = linha.split()
            if not partes:
                continue
            nome = partes[-1]
            m = _RE_NOME.match(nome)
            if m and m.group(1) == competencia:
                return nome
    except Exception:
        pass
    return None


# ==============================================================================
# Download
# ==============================================================================

def baixar_competencia(
    competencia: str,
    callback: Optional[Callable[[int, int], None]] = None,
    timeout: int = 30,
) -> Optional[Path]:
    """Baixa o ZIP da competencia e salva em cache local.

    callback(bytes_recebidos, bytes_total) chamado durante o download.
    Retorna o Path do ZIP salvo, ou None em caso de falha.
    """
    destino = _dir_cache() / f"TabelaUnificada_{competencia}.zip"
    if destino.exists() and destino.stat().st_size > 100_000:
        return destino  # ja em cache

    nome_ftp = _nome_arquivo_ftp(competencia)
    if not nome_ftp:
        return None

    try:
        buf = io.BytesIO()
        tamanho_total = 0

        with ftplib.FTP(timeout=timeout) as ftp:
            ftp.connect(FTP_HOST, timeout=timeout)
            ftp.login()
            ftp.cwd(FTP_DIR)

            # Tamanho do arquivo
            try:
                ftp.sendcmd("TYPE I")
                resp = ftp.sendcmd(f"SIZE {nome_ftp}")
                tamanho_total = int(resp.split()[-1])
            except Exception:
                tamanho_total = 0

            recebidos = 0

            def _bloco(dados: bytes) -> None:
                nonlocal recebidos
                buf.write(dados)
                recebidos += len(dados)
                if callback:
                    callback(recebidos, tamanho_total)

            ftp.retrbinary(f"RETR {nome_ftp}", _bloco, blocksize=65536)

        destino.write_bytes(buf.getvalue())
        return destino

    except Exception:
        return None


# ==============================================================================
# Parsing dos TXTs para o MESMO esquema das tabelas DBF do APAC-MAG
#
# Contrato (o que apac_mag_validador le das tabelas DBF):
#   - codigos de procedimento com 9 digitos, SEM o DV (o ZIP traz 10 com DV);
#   - S_PA: PA_IDADEMN/PA_IDADEMX em ANOS (999 = sem limite; o SIGTAP traz
#     MESES, 9999 = sem limite), PA_SEXO = M/F/A (SIGTAP: M/F/I),
#     PA_QTDMAX, PA_SECOBRI, PA_DC (descricao);
#   - S_CID: RESTRSEXO 1 = so masculino, 2 = so feminino, 5 = sem restricao
#     (SIGTAP: M/F/I); inclui as categorias de 3 caracteres (o SIGTAP so
#     lista subcategorias de 4, e o DBF tem as duas).
# As posicoes vem do arquivo <tabela>_layout.txt do proprio ZIP quando
# presente (Coluna,Tamanho,Inicio,Fim,Tipo); senao valem as padrao abaixo.
# ==============================================================================

def _ler_txt_zip(zf: zipfile.ZipFile, nome: str, encoding: str = "cp1252") -> List[str]:
    """Le linhas de um arquivo TXT dentro do ZIP ([] se ausente/ilegivel)."""
    try:
        with zf.open(nome) as f:
            return f.read().decode(encoding, errors="replace").splitlines()
    except (KeyError, OSError, zipfile.BadZipFile):
        return []


Layout = Dict[str, tuple]  # coluna -> (inicio0, fim0) para fatiar a linha

_LAYOUT_PADRAO: Dict[str, Layout] = {
    "tb_procedimento": {
        "CO_PROCEDIMENTO": (0, 10), "NO_PROCEDIMENTO": (10, 260),
        "TP_SEXO": (261, 262), "QT_MAXIMA_EXECUCAO": (262, 266),
        "VL_IDADE_MINIMA": (274, 278), "VL_IDADE_MAXIMA": (278, 282),
        "DT_COMPETENCIA": (330, 336),
    },
    "tb_cid": {"CO_CID": (0, 4), "TP_SEXO": (105, 106)},
    "rl_procedimento_compativel": {
        "CO_PROCEDIMENTO_PRINCIPAL": (0, 10), "CO_PROCEDIMENTO_COMPATIVEL": (12, 22),
        "QT_PERMITIDA": (25, 29), "DT_COMPETENCIA": (29, 35),
    },
    "rl_procedimento_habilitacao": {
        "CO_PROCEDIMENTO": (0, 10), "CO_HABILITACAO": (10, 14), "DT_COMPETENCIA": (18, 24),
    },
    "rl_procedimento_regra_cond": {"CO_PROCEDIMENTO": (0, 10), "CO_REGRA_CONDICIONADA": (10, 14)},
}


def _ler_layout(zf: zipfile.ZipFile, tabela: str) -> Layout:
    """Layout da tabela: <tabela>_layout.txt do ZIP sobre o padrao embutido."""
    layout: Layout = dict(_LAYOUT_PADRAO[tabela])
    alvo = f"{tabela}_layout.txt".lower()
    for nome in zf.namelist():
        if nome.lower().rsplit("/", 1)[-1] == alvo:
            for linha in _ler_txt_zip(zf, nome):
                partes = [p.strip() for p in linha.split(",")]
                if len(partes) >= 4 and partes[2].isdigit() and partes[3].isdigit():
                    layout[partes[0].upper()] = (int(partes[2]) - 1, int(partes[3]))
            break
    return layout


def _tabela(zf: zipfile.ZipFile, tabela: str) -> tuple:
    """(linhas, layout) de <tabela>.txt dentro do ZIP."""
    return _ler_txt_zip(zf, f"{tabela}.txt"), _ler_layout(zf, tabela)


def _campo(linha: str, layout: Layout, coluna: str) -> str:
    ini, fim = layout[coluna]
    return linha[ini:fim].strip()


def _cod9(valor: str) -> str:
    """Codigo de procedimento sem DV: '0905010035' -> '090501003'."""
    digitos = re.sub(r"\D", "", valor)
    return digitos[:9] if len(digitos) >= 10 else digitos


def _idade_em_anos(meses: str) -> str:
    """Idade do SIGTAP (meses; vazio/9999 = sem limite) -> anos do DBF (999)."""
    if not meses.isdigit() or int(meses) >= 9999:
        return "999"
    return str(int(meses) // 12)


def _sexo_pa(valor: str) -> str:
    """TP_SEXO do procedimento: M/F/I(gnorado) -> M/F/A (como no S_PA)."""
    valor = valor.upper()
    return valor if valor in ("M", "F") else "A"


def _sexo_cid(valor: str) -> str:
    """TP_SEXO do CID: M/F/I(gnorado) -> 1/2/5 (como o RESTRSEXO do S_CID)."""
    return {"M": "1", "F": "2"}.get(valor.upper(), "5")


def _parsear_regras_condicionadas(
    linhas: List[str], competencia: str, layout: Optional[Layout] = None
) -> List[Dict[str, str]]:
    """rl_procedimento_regra_cond.txt -> S_PAREGR (REG_PA, REG_REGRA, REG_CMP)."""
    lay = layout or _LAYOUT_PADRAO["rl_procedimento_regra_cond"]
    registros = []
    for linha in linhas:
        if len(linha) < 14:
            continue
        registros.append({
            "REG_PA":    _cod9(_campo(linha, lay, "CO_PROCEDIMENTO")),
            "REG_REGRA": _campo(linha, lay, "CO_REGRA_CONDICIONADA"),
            "REG_CMP":   competencia,
            "REG_CHKSM": "",
        })
    return registros


def _parsear_pares_compativeis(
    linhas: List[str], competencia: str, layout: Optional[Layout] = None
) -> List[Dict[str, str]]:
    """rl_procedimento_compativel.txt -> S_PAPA.

    Layout: principal(10) registro(2) compativel(10) registro(2)
    tp_compatibilidade(1) qt_permitida(4) competencia(6).
    Campos: PAPA_PRINC, PAPA_SECUN (9 digitos), PAPA_QTMAX, PAPA_CMP.
    """
    lay = layout or _LAYOUT_PADRAO["rl_procedimento_compativel"]
    registros = []
    for linha in linhas:
        if len(linha) < 35:
            continue
        # Aceita todos os tipos — o S_PAPA do APAC-MAG armazena todos os pares
        registros.append({
            "PAPA_PRINC": _cod9(_campo(linha, lay, "CO_PROCEDIMENTO_PRINCIPAL")),
            "PAPA_SECUN": _cod9(_campo(linha, lay, "CO_PROCEDIMENTO_COMPATIVEL")),
            "PAPA_QTMAX": _campo(linha, lay, "QT_PERMITIDA"),
            "PAPA_CMP":   _campo(linha, lay, "DT_COMPETENCIA") or competencia,
        })
    return registros


def _parsear_habilitacoes(
    linhas: List[str], competencia: str, layout: Optional[Layout] = None
) -> List[Dict[str, str]]:
    """rl_procedimento_habilitacao.txt -> S_PAHA (PAHA_PA 9 digitos, PAHA_HA, PAHA_CMP)."""
    lay = layout or _LAYOUT_PADRAO["rl_procedimento_habilitacao"]
    registros = []
    for linha in linhas:
        if len(linha) < 14:
            continue
        registros.append({
            "PAHA_PA":  _cod9(_campo(linha, lay, "CO_PROCEDIMENTO")),
            "PAHA_HA":  _campo(linha, lay, "CO_HABILITACAO"),
            "PAHA_CMP": _campo(linha, lay, "DT_COMPETENCIA") or competencia,
        })
    return registros


def _parsear_procedimentos(
    linhas: List[str], competencia: str, layout: Optional[Layout] = None
) -> List[Dict[str, str]]:
    """tb_procedimento.txt -> S_PA.

    Campos: PA_ID (9 digitos), PA_DV, PA_DC, PA_SEXO (M/F/A), PA_QTDMAX,
    PA_IDADEMN/PA_IDADEMX (ANOS; 999 = sem limite), PA_SECOBRI e PA_CMP.
    PA_SECOBRI vem vazio: o SIGTAP nao traz o indicador "secundario
    obrigatorio", e vazio mantem essa regra desativada (nunca falso positivo).
    """
    lay = layout or _LAYOUT_PADRAO["tb_procedimento"]
    minimo = max(fim for _, fim in lay.values())
    registros = []
    for linha in linhas:
        if len(linha) < minimo:
            continue
        codigo = re.sub(r"\D", "", _campo(linha, lay, "CO_PROCEDIMENTO"))
        registros.append({
            "PA_ID":      _cod9(codigo),
            "PA_DV":      codigo[9:10],
            "PA_DC":      _campo(linha, lay, "NO_PROCEDIMENTO"),
            "PA_SEXO":    _sexo_pa(_campo(linha, lay, "TP_SEXO")),
            "PA_QTDMAX":  _campo(linha, lay, "QT_MAXIMA_EXECUCAO") or "9999",
            "PA_IDADEMN": _idade_em_anos(_campo(linha, lay, "VL_IDADE_MINIMA")),
            "PA_IDADEMX": _idade_em_anos(_campo(linha, lay, "VL_IDADE_MAXIMA")),
            "PA_SECOBRI": "",
            "PA_CMP":     _campo(linha, lay, "DT_COMPETENCIA") or competencia,
        })
    return registros


def _parsear_cids(
    linhas: List[str], competencia: str, layout: Optional[Layout] = None
) -> List[Dict[str, str]]:
    """tb_cid.txt -> S_CID (CD_COD, RESTRSEXO 1/2/5, CMP_INI, CMP_FIM).

    O SIGTAP so lista subcategorias (4 caracteres, ex. A000); o DBF tambem
    traz a categoria de 3 (A00). Ela e sintetizada aqui, sem restricao de
    sexo, para CIDs de 3 caracteres da planilha nao virarem "nao encontrado".
    """
    lay = layout or _LAYOUT_PADRAO["tb_cid"]
    registros = []
    vistos = set()
    for linha in linhas:
        if len(linha) < 106:
            continue
        codigo = _campo(linha, lay, "CO_CID").upper()
        if not codigo:
            continue
        registros.append({
            "CD_COD":    codigo,
            "RESTRSEXO": _sexo_cid(_campo(linha, lay, "TP_SEXO")),
            "CMP_INI":   "000000",
            "CMP_FIM":   "999999",
        })
        vistos.add(codigo)
    for codigo in sorted({c[:3] for c in vistos if len(c) == 4} - vistos):
        registros.append({"CD_COD": codigo, "RESTRSEXO": "5",
                          "CMP_INI": "000000", "CMP_FIM": "999999"})
    return registros


# ==============================================================================
# Carregamento completo de uma competencia
# ==============================================================================

def carregar_sigtap_competencia(
    competencia: str,
    callback_download: Optional[Callable[[int, int], None]] = None,
) -> Optional[Dict[str, List[Dict[str, str]]]]:
    """Carrega as tabelas SIGTAP de uma competencia (download se necessario).

    Retorna dict com chaves:
        "S_PAREGR", "S_PAPA", "S_PAHA", "S_PA", "S_CID"
    Cada valor e uma lista de dicts no mesmo formato dos DBF do APAC-MAG.
    Retorna None se o download falhar.
    """
    with _cache_lock:
        if competencia in _cache_sigtap:
            return _cache_sigtap[competencia]

    zip_path = _dir_cache() / f"TabelaUnificada_{competencia}.zip"
    if not (zip_path.exists() and zip_path.stat().st_size > 100_000):
        zip_path = baixar_competencia(competencia, callback=callback_download) or zip_path

    if not (zip_path.exists() and zip_path.stat().st_size > 100_000):
        return None

    try:
        with zipfile.ZipFile(zip_path) as zf:
            linhas, lay = _tabela(zf, "rl_procedimento_regra_cond")
            paregr = _parsear_regras_condicionadas(linhas, competencia, lay)
            linhas, lay = _tabela(zf, "rl_procedimento_compativel")
            papa = _parsear_pares_compativeis(linhas, competencia, lay)
            linhas, lay = _tabela(zf, "rl_procedimento_habilitacao")
            paha = _parsear_habilitacoes(linhas, competencia, lay)
            linhas, lay = _tabela(zf, "tb_procedimento")
            s_pa = _parsear_procedimentos(linhas, competencia, lay)
            linhas, lay = _tabela(zf, "tb_cid")
            s_cid = _parsear_cids(linhas, competencia, lay)
    except Exception:
        return None

    resultado = {
        "S_PAREGR": paregr,
        "S_PAPA":   papa,
        "S_PAHA":   paha,
        "S_PA":     s_pa,
        "S_CID":    s_cid,
    }

    with _cache_lock:
        _cache_sigtap[competencia] = resultado

    return resultado


def limpar_cache_memoria() -> None:
    """Libera o cache em memoria (util ao trocar de competencia na UI)."""
    with _cache_lock:
        _cache_sigtap.clear()
