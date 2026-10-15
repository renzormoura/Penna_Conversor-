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
# Parsing dos TXTs para o formato dict do apac_mag_bases
# ==============================================================================

def _ler_txt_zip(zf: zipfile.ZipFile, nome: str, encoding: str = "cp1252") -> List[str]:
    """Le linhas de um arquivo TXT dentro do ZIP."""
    try:
        with zf.open(nome) as f:
            return f.read().decode(encoding, errors="replace").splitlines()
    except Exception:
        return []


def _parsear_regras_condicionadas(linhas: List[str], competencia: str) -> List[Dict[str, str]]:
    """rl_procedimento_regra_cond.txt -> lista no formato S_PAREGR.

    Layout: CO_PROCEDIMENTO(10) CO_REGRA_CONDICIONADA(4)
    Campos devolvidos: REG_PA, REG_REGRA, REG_CMP
    """
    registros = []
    for linha in linhas:
        if len(linha) < 14:
            continue
        registros.append({
            "REG_PA":    linha[0:10].strip(),
            "REG_REGRA": linha[10:14].strip(),
            "REG_CMP":   competencia,
            "REG_CHKSM": "",
        })
    return registros


def _parsear_pares_compativeis(linhas: List[str], competencia: str) -> List[Dict[str, str]]:
    """rl_procedimento_compativel.txt -> lista no formato S_PAPA.

    Layout:
      CO_PROCEDIMENTO_PRINCIPAL(10) CO_REGISTRO_PRINCIPAL(2)
      CO_PROCEDIMENTO_COMPATIVEL(10) CO_REGISTRO_COMPATIVEL(2)
      TP_COMPATIBILIDADE(1) QT_PERMITIDA(4) DT_COMPETENCIA(6)

    TP_COMPATIBILIDADE:
      1 = principal/especial  2 = secundario (SIA)  outros = outros sistemas

    Campos devolvidos: PAPA_PRINC, PAPA_SECUN, PAPA_QTMAX, PAPA_CMP
    """
    registros = []
    for linha in linhas:
        if len(linha) < 35:
            continue
        # Aceita todos os tipos — o S_PAPA do APAC-MAG armazena todos os pares
        registros.append({
            "PAPA_PRINC": linha[0:10].strip(),
            "PAPA_SECUN": linha[12:22].strip(),
            "PAPA_QTMAX": linha[25:29].strip(),
            "PAPA_CMP":   linha[29:35].strip() or competencia,
        })
    return registros


def _parsear_habilitacoes(linhas: List[str], competencia: str) -> List[Dict[str, str]]:
    """rl_procedimento_habilitacao.txt -> lista no formato S_PAHA.

    Layout: CO_PROCEDIMENTO(10) CO_HABILITACAO(4) NU_GRUPO_HABILITACAO(4) DT_COMPETENCIA(6)
    Campos devolvidos: PAHA_PA, PAHA_HA, PAHA_CMP
    """
    registros = []
    for linha in linhas:
        if len(linha) < 14:
            continue
        registros.append({
            "PAHA_PA":  linha[0:10].strip(),
            "PAHA_HA":  linha[10:14].strip(),
            "PAHA_CMP": linha[18:24].strip() if len(linha) >= 24 else competencia,
        })
    return registros


def _parsear_procedimentos(linhas: List[str], competencia: str) -> List[Dict[str, str]]:
    """tb_procedimento.txt -> lista no formato S_PA.

    Layout relevante:
      CO_PROCEDIMENTO(10) NO_PROCEDIMENTO(250) TP_COMPLEXIDADE(1)
      TP_SEXO(1) QT_MAXIMA_EXECUCAO(4) QT_DIAS_PERMANENCIA(4)
      QT_PONTOS(4) VL_IDADE_MINIMA(4) VL_IDADE_MAXIMA(4)
      VL_SH(12) VL_SA(12) VL_SP(12) CO_FINANCIAMENTO(2)
      CO_RUBRICA(6) QT_TEMPO_PERMANENCIA(4) DT_COMPETENCIA(6)
    Campos devolvidos: PA_ID, PA_NOME, PA_SEXO, PA_QTMAX, PA_IDMIN, PA_IDMAX, PA_CMP
    """
    registros = []
    for linha in linhas:
        if len(linha) < 336:
            continue
        registros.append({
            "PA_ID":    linha[0:10].strip(),
            "PA_NOME":  linha[10:260].strip(),
            "PA_SEXO":  linha[261:262].strip(),
            "PA_QTMAX": linha[262:266].strip(),
            "PA_IDMIN": linha[274:278].strip(),
            "PA_IDMAX": linha[278:282].strip(),
            "PA_CMP":   linha[330:336].strip() or competencia,
        })
    return registros


def _parsear_cids(linhas: List[str], competencia: str) -> List[Dict[str, str]]:
    """tb_cid.txt -> lista no formato S_CID.

    Layout: CO_CID(4) NO_CID(100) TP_AGRAVO(1) TP_SEXO(1) TP_ESTADIO(1) ...
    Campos devolvidos: CD_COD, RESTRSEXO, CMP_INI, CMP_FIM
    """
    registros = []
    for linha in linhas:
        if len(linha) < 105:
            continue
        registros.append({
            "CD_COD":    linha[0:4].strip(),
            "RESTRSEXO": linha[105:106].strip(),
            "CMP_INI":   "000000",
            "CMP_FIM":   "999999",
        })
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
            paregr = _parsear_regras_condicionadas(
                _ler_txt_zip(zf, "rl_procedimento_regra_cond.txt"), competencia)
            papa = _parsear_pares_compativeis(
                _ler_txt_zip(zf, "rl_procedimento_compativel.txt"), competencia)
            paha = _parsear_habilitacoes(
                _ler_txt_zip(zf, "rl_procedimento_habilitacao.txt"), competencia)
            s_pa = _parsear_procedimentos(
                _ler_txt_zip(zf, "tb_procedimento.txt"), competencia)
            s_cid = _parsear_cids(
                _ler_txt_zip(zf, "tb_cid.txt"), competencia)
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
