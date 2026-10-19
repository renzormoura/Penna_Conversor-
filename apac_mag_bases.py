r"""Acesso as bases de dados SIA do programa antigo APAC-MAG (DATASUS).

O programa antigo valida a producao contra tabelas SIGTAP em formato DBF
(dBase III) — avulsas na pasta de instalacao ou comprimidas em .ZBF (zip)
nos backups mensais. Este modulo centraliza a leitura dessas tabelas para o
PENNA (validador, remessa e futuras ferramentas), com esta ordem de busca:

    1. pasta override (PENNA_APAC_DIR, padrao C:/APAC) -> NOME.DBF;
    2. backups mensais do override -> BACKUP/<AAAAMM>/NOME.ZBF (mais recente);
    3. copia versionada do projeto -> dados/bases_sia/NOME.DBF ou NOME.ZBF;
    4. tabelas parseadas do ZIP SIGTAP (baixado via apac_mag_sigtap_download).

O cache e por (tabela, caminho, mtime): reler o arquivo so quando ele mudar.
Nenhuma funcao lanca excecao por tabela ausente/corrompida: devolvem None e
o chamador desativa a regra correspondente (nunca falso positivo).

Uso com competencia SIGTAP especifica (opcional):
    carregar_tabela("S_PAREGR", sigtap_competencia="202606")
    # -> busca DBF local primeiro; se ausente, usa o ZIP do SIGTAP baixado.
"""
from __future__ import annotations

import os
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

# Pasta de instalacao do programa antigo (override para testes/homologacao)
DIR_ANTIGO = Path(os.environ.get("PENNA_APAC_DIR", "C:/APAC"))
# Copia versionada das tabelas dentro do projeto
DIR_LOCAL = Path(__file__).resolve().parent / "dados" / "bases_sia"

_cache: Dict[tuple, Any] = {}


# ==============================================================================
# Leitor DBF III (o mesmo formato binario usado pelo programa antigo)
# ==============================================================================

def ler_dbf(data: bytes) -> Optional[List[Dict[str, str]]]:
    """Le os registros de um DBF III a partir dos bytes. None se invalido."""
    try:
        if len(data) < 33 or data[:1] != b"\x03":
            return None
        nrec = struct.unpack("<I", data[4:8])[0]
        hlen = struct.unpack("<H", data[8:10])[0]
        rlen = struct.unpack("<H", data[10:12])[0]
        if hlen < 33 or rlen <= 1:
            return None
        fields: List[tuple] = []
        i = 32
        while i < hlen and data[i] != 0x0D:
            name = data[i : i + 11].split(b"\0")[0].decode("ascii", "replace")
            flen = data[i + 16]
            if flen <= 0:
                return None
            fields.append((name, flen))
            i += 32
        if not fields:
            return None
        registros: List[Dict[str, str]] = []
        off = hlen
        for _ in range(nrec):
            rec = data[off : off + rlen]
            if len(rec) < rlen or rec[0:1] not in (b" ", b"*"):
                break
            valores: Dict[str, str] = {}
            pos = 1
            for name, flen in fields:
                valores[name] = rec[pos : pos + flen].decode("cp850", "replace").strip()
                pos += flen
            registros.append(valores)
            off += rlen
        return registros
    except (struct.error, ValueError, IndexError):
        return None  # DBF truncado/corrompido: tabela indisponivel (regra desativada)


def ler_arquivo_dbf(path: Path) -> Optional[List[Dict[str, str]]]:
    try:
        return ler_dbf(Path(path).read_bytes())
    except OSError:
        return None


def ler_zbf(path: Path) -> Optional[List[Dict[str, str]]]:
    """Le um backup .ZBF do antigo (zip com o DBF dentro)."""
    try:
        with zipfile.ZipFile(path) as z:
            nome = z.namelist()[0]
            return ler_dbf(z.read(nome))
    except (zipfile.BadZipFile, OSError, IndexError, KeyError, RuntimeError,
            NotImplementedError, zlib.error):
        return None


# ==============================================================================
# Carregamento com cache e ordem de busca padrao
# ==============================================================================

# Cache de candidatos: chave -> (assinatura das pastas, caminhos).
# Evita refazer milhares de globs (BACKUP/*/*.ZBF) a cada carregar_tabela.
_caminhos_cache: Dict[tuple, tuple] = {}


def _mtime_dir(path: Path) -> Optional[float]:
    """mtime do diretorio (None se inacessivel)."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _assinatura_pastas(bases_dir: List[Path]) -> tuple:
    """Assinatura das pastas de busca: muda sempre que entra/sai arquivo.

    Criar/apagar um .DBF na pasta base ou um mes em BACKUP altera o mtime do
    diretorio correspondente — e invalida o cache de candidatos. Alterar o
    CONTEUDO de um arquivo nao muda a lista de candidatos (o proprio
    carregar_tabela continua checando mtime por caminho).
    """
    partes: List[Any] = []
    for base in bases_dir:
        partes.append(_mtime_dir(base))
        backup = base / "BACKUP"
        meses: List[tuple] = []
        try:
            for item in sorted(backup.iterdir()):
                if item.is_dir():
                    meses.append((item.name, _mtime_dir(item)))
        except OSError:
            meses = []
        partes.append(tuple(meses))
    return tuple(partes)


def _caminhos_candidatos(nome: str, diretorio: Optional[Path]) -> List[Path]:
    """Caminhos onde a tabela pode estar, na ordem de prioridade.

    Memorizado por (nome, diretório) e invalidado pela assinatura das pastas.
    """
    nome = nome.upper()
    bases = [Path(diretorio)] if diretorio else [DIR_ANTIGO, DIR_LOCAL]
    chave = (nome, tuple(str(base) for base in bases))
    assinatura = _assinatura_pastas(bases)
    memo = _caminhos_cache.get(chave)
    if memo is not None and memo[0] == assinatura:
        return memo[1]
    candidatos: List[Path] = []
    for base in bases:
        for sufixo in (".DBF", ".dbf", ".ZBF", ".zbf"):
            candidatos.append(base / (nome + sufixo))
        # backups mensais .ZBF (mais recente primeiro)
        if (base / "BACKUP").exists():
            for backup in sorted((base / "BACKUP").glob(f"*/{nome}.ZBF"), reverse=True):
                candidatos.append(backup)
            for backup in sorted((base / "BACKUP").glob(f"*/{nome}.zbf"), reverse=True):
                candidatos.append(backup)
    _caminhos_cache[chave] = (assinatura, candidatos)
    return candidatos


def carregar_tabela(
    nome: str,
    diretorio: Optional[Path] = None,
    sigtap_competencia: Optional[str] = None,
) -> Optional[List[Dict[str, str]]]:
    """Carrega uma tabela SIA (ex.: 'S_PA', 'S_PAPA', 'S_CEP') com cache.

    Ordem de busca:
      1. DBF/ZBF local (PENNA_APAC_DIR / dados/bases_sia / diretorio override)
      2. ZIP SIGTAP baixado via apac_mag_sigtap_download (apenas quando
         sigtap_competencia for informado e a tabela nao existir localmente)

    Devolve None quando a tabela nao foi encontrada em nenhum local.
    """
    chave_base = ("tabela", str(Path(diretorio) if diretorio else ""), nome.upper())
    for caminho in _caminhos_candidatos(nome, diretorio):
        if not caminho.exists():
            continue
        try:
            mtime = caminho.stat().st_mtime
        except OSError:
            continue
        chave = chave_base + (str(caminho),)
        em_cache = _cache.get(chave)
        if em_cache is not None and em_cache[0] == mtime:
            return em_cache[1]
        if caminho.suffix.lower() == ".zbf":
            registros = ler_zbf(caminho)
        else:
            registros = ler_arquivo_dbf(caminho)
        if registros:
            _cache[chave] = (mtime, registros)
            return registros

    # --- Fallback: ZIP SIGTAP (apenas tabelas suportadas) ---
    if sigtap_competencia:
        registros = _carregar_de_sigtap(nome.upper(), sigtap_competencia)
        if registros:
            return registros

    return None


# Tabelas que o modulo SIGTAP sabe fornecer (mapeamento nome -> chave no dict)
_SIGTAP_TABELAS = {
    "S_PAREGR": "S_PAREGR",
    "S_PAPA":   "S_PAPA",
    "S_PAHA":   "S_PAHA",
    "S_PA":     "S_PA",
    "S_CID":    "S_CID",
}


def _carregar_de_sigtap(
    nome: str, competencia: str
) -> Optional[List[Dict[str, str]]]:
    """Tenta obter a tabela a partir do ZIP SIGTAP ja em cache de disco.

    Nao faz download automatico — isso e responsabilidade da UI.
    Retorna None se o ZIP nao estiver disponivel ou a tabela nao for suportada.
    """
    chave_sigtap = _SIGTAP_TABELAS.get(nome)
    if not chave_sigtap:
        return None
    try:
        from apac_mag_sigtap_download import carregar_sigtap_competencia
    except ImportError:
        return None
    # carregar_sigtap_competencia nao lanca por rede/ZIP invalido (devolve None)
    dados = carregar_sigtap_competencia(competencia)
    return dados.get(chave_sigtap) if dados else None


def competencia_disponivel_local(competencia: str) -> bool:
    """Verifica se as tabelas SIGTAP principais existem localmente para
    a competencia dada (via DBF/ZBF no PENNA_APAC_DIR ou dados/bases_sia).

    Usado pela UI para decidir se precisa oferecer download.
    """
    tabelas_chave = ["S_PAREGR", "S_PAPA", "S_PAHA"]
    for nome in tabelas_chave:
        regs = carregar_tabela(nome)
        if regs is None:
            return False
        from apac_mag_bases import filtrar_por_competencia
        campos = {"S_PAREGR": "REG_CMP", "S_PAPA": "PAPA_CMP", "S_PAHA": "PAHA_CMP"}
        vigentes = filtrar_por_competencia(regs, campos[nome], competencia)
        if not vigentes:
            return False
    return True


# ==============================================================================
# Seleção por competência
# ==============================================================================

def _maior_valor(registros: List[Dict[str, str]], campo: str, competencia: str) -> Optional[str]:
    maior: Optional[str] = None
    for r in registros:
        valor = (r.get(campo) or "").strip()
        if not valor:
            continue
        if valor <= competencia and (maior is None or valor > maior):
            maior = valor
    return maior


def filtrar_por_competencia(
    registros: List[Dict[str, str]], campo: str, competencia: str
) -> List[Dict[str, str]]:
    """Registros com o campo-competencia mais alto ainda <= competencia.

    Replica o BDSIA: cada competencia regrava a tabela; a regra da APAC e a
    da tabela vigente na competencia dela (nunca de uma competencia futura).
    """
    if not registros or not competencia:
        return []
    vigente = _maior_valor(registros, campo, competencia)
    if vigente is None:
        return []
    return [r for r in registros if (r.get(campo) or "").strip() == vigente]


def filtrar_por_faixa(
    registros: List[Dict[str, str]], campo_ini: str, campo_fim: str, competencia: str
) -> List[Dict[str, str]]:
    """Registros cuja faixa [ini, fim] cobre a competencia (S_CID/S_DEPARA)."""
    if not registros or not competencia:
        return []
    saida = []
    for r in registros:
        ini = (r.get(campo_ini) or "").strip() or "000000"
        fim = (r.get(campo_fim) or "").strip() or "999999"
        if ini <= competencia <= fim:
            saida.append(r)
    return saida


# ==============================================================================
# Habilitacoes do CNES (XUPSHA do TXTCNES, por competencia)
# ==============================================================================

def carregar_habilitacoes_cnes(
    cnes: str, competencia: str, diretorio: Optional[Path] = None
) -> Optional[set]:
    """Habilitacoes (HA) ativas do CNES na competencia, via XUPSHA.DBF.

    Busca em dados/bases_sia, TXTCNES/<competencia>/ e TXTCNES/*/ (mais
    recente). Devolve None quando nenhuma base XUPSHA existir (regra fica
    desativada para nao gerar falso positivo).
    """
    cnes7 = (cnes or "").zfill(7)[:7]
    candidatos: List[Path] = []
    if diretorio:
        candidatos.append(Path(diretorio) / "XUPSHA.DBF")
    candidatos.append(DIR_LOCAL / "XUPSHA.DBF")
    if DIR_ANTIGO.exists():
        pasta_txt = DIR_ANTIGO / "TXTCNES"
        if competencia:
            candidatos.append(pasta_txt / competencia / "XUPSHA.DBF")
        for pasta in sorted(pasta_txt.glob("*/XUPSHA.DBF"), reverse=True):
            candidatos.append(pasta)
    registros: Optional[List[Dict[str, str]]] = None
    for caminho in candidatos:
        if caminho.exists():
            registros = ler_arquivo_dbf(caminho)
            if registros is not None:
                break
    if not registros:
        return None
    ativas = set()
    for r in registros:
        if (r.get("UPSHA_UPS") or "").zfill(7)[:7] != cnes7:
            continue
        ini = (r.get("UPSHA_INI") or "").strip() or "000000"
        fim = (r.get("UPSHA_FIM") or "").strip() or "999999"
        if not competencia or (ini <= competencia <= fim):
            ha = (r.get("UPSHA_HA") or "").strip()
            if ha:
                ativas.add(ha)
    return ativas
