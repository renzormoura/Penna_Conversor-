r"""Ciclo da remessa fiscal: registro, comprovante, demonstrativo e historico.

Reproduz as ferramentas de controle do programa antigo APAC-MAG:

- **RELEXP.prn** -> comprovante de remessa imprimivel (orgao responsavel,
  secretaria destino, arquivo gerado, registros gravados, PAC(s), carimbos);
- **S_CTR.dbf / S_HIST.dbf** -> registro de cada remessa e das APACs
  exportadas, usado para AVISAR sobre reenvio com o codigo oficial 010084
  ("NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE", log 202601);
- **R0201** -> demonstrativo completo por APAC (identificacao, paciente,
  CID, procedimentos com CBO/QTD, motivo de saida, autorizador).

Estrutura gravada no projeto (dados/remessas/):
    <AAAAMM>/<AAAAMMDD_HHMMSS>/
        remessa.json        metadados da remessa
        apacs.txt           numeros de APAC exportados (1 por linha)
        <arquivo>.txt       copia do TXT fiscal enviado
        Comprovante_*.PRN   comprovante no formato RELEXP
        Demonstrativo_*.TXT demonstrativo no estilo R0201
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Serialização e helpers do gerador (mantidos por dependência de build_patient_lines
# e das funções de checksum/header que são lógica de negócio do gerador)
from apac_mag_gerador import (
    _calcular_checksum,
    _competencia_header,
    build_patient_lines,
)
# Helpers de string: fonte única em penna.core
from penna.core import (
    digits as _digits_fn,
    resolve_row_value,
    text,
    text_upper,
)
# Configuração do estabelecimento: lida do penna_config.json
from penna.config import get_header
from penna import reference

# Aliases de retrocompatibilidade e acesso lazy ao config
def to_text(value: Any) -> str:
    return text(value)

PASTA_REMESSAS = Path(__file__).resolve().parent / "dados" / "remessas"


def _pasta_remessas_padrao() -> Path:
    """Pasta de remessas gravavel.

    No EXE onefile, PASTA_REMESSAS aponta para a pasta temporaria de
    extracao (_MEI...), que some ao fechar o programa — fazendo o
    historico de APACs sumir/reaparecer entre sessoes. Por isso o EXE
    grava primeiro no perfil do usuario (C:/Users/<user>/Penna/remessas),
    mantendo o historico estavel; rodando do codigo-fonte, grava no
    projeto (dados/remessas), como sempre.
    """
    if getattr(sys, "frozen", False):
        ordem = (Path.home() / "Penna" / "remessas", PASTA_REMESSAS)
    else:
        ordem = (PASTA_REMESSAS, Path.home() / "Penna" / "remessas")
    for pasta in ordem:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            return pasta
        except OSError:
            continue  # sem permissão na pasta do usuário: tenta a próxima
    return PASTA_REMESSAS

_MES_SIGLA = {
    "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR", "05": "MAI", "06": "JUN",
    "07": "JUL", "08": "AGO", "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ",
}

# Descricoes oficiais das regras condicionadas (impressas no R0201 do antigo)
DESCRICOES_REGRAS = {
    "0009": "PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS",
}


# ==============================================================================
# Helpers de formatacao (mesmo visual dos relatorios do antigo)
# ==============================================================================

def _digitos(valor: Any, padrao: str = "") -> str:
    d = _digits_fn(valor)
    return d if d else padrao


def _com_dv(codigo: str, digitos: int) -> str:
    """1234567890 -> '123456789-0' (padrao dos relatorios do antigo)."""
    codigo = _digitos(codigo)
    if len(codigo) <= digitos:
        return codigo
    return f"{codigo[:digitos]}-{codigo[digitos:]}"


def _fmt_data(valor: Any) -> str:
    """Formata dd/mm/aaaa a partir de DDMMAAAA (planilha) ou AAAAMMDD (layout)."""
    d = _digitos(valor)
    if len(d) == 8 and d.isdigit():
        if 1 <= int(d[:2]) <= 31 and 1 <= int(d[2:4]) <= 12:
            return f"{d[:2]}/{d[2:4]}/{d[4:]}"          # DDMMAAAA (planilha)
        if 1 <= int(d[4:6]) <= 12 and 1 <= int(d[6:8]) <= 31:
            return f"{d[6:8]}/{d[4:6]}/{d[:4]}"          # AAAAMMDD (layout)
    return to_text(valor)


def _fmt_cpf(cpf: str) -> str:
    d = _digitos(cpf)
    if len(d) != 11:
        return to_text(cpf)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def _fmt_cep(cep: str) -> str:
    d = _digitos(cep).zfill(8)[:8]
    return f"{d[:5]}-{d[5:]}"


def _fmt_cgc(cgc: str) -> str:
    d = _digitos(cgc).zfill(14)[:14]
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


_SEXO = {"M": "MASCULINO", "F": "FEMININO", "I": "INDETERMINADO"}
_RACA = {"01": "BRANCA", "02": "PRETA", "03": "PARDA", "04": "AMARELA", "05": "INDIGENA", "99": "SEM INFORMACAO"}
_MOTIVO = {"11": "ALTA CURADO"}


def _dados_estabelecimento() -> Dict[str, str]:
    """Config do estabelecimento: S_SS.DBF do antigo com fallback ao penna_config.json."""
    h = get_header()
    dados = {
        "nome": text_upper(h.get("orgao_responsavel", "")),
        "sigla": "",
        "cgc": _digitos(h.get("cgc", "")),
        "destino": text_upper(h.get("destino", "")),
        "indicador": h.get("destino_indicador", "M")[:1],
        "cnes": "",
    }
    try:
        registros = reference.carregar_tabela("S_SS")
        if registros:
            ss = registros[0]
            dados["nome"] = (ss.get("SS_UFNOME") or dados["nome"]).strip().upper()
            dados["sigla"] = (ss.get("SS_SIGL") or "").strip().upper()
            dados["cgc"] = _digitos(ss.get("SS_CGC") or dados["cgc"])
            dados["destino"] = (ss.get("SS_NM") or dados["destino"]).strip().upper()
            dados["indicador"] = (ss.get("SS_IN") or dados["indicador"]).strip()[:1].upper()
            dados["cnes"] = _digitos(ss.get("SS_UPS") or "")
    except Exception:
        pass
    return dados


def _descricoes_procedimentos() -> Dict[str, str]:
    desc: Dict[str, str] = {}
    try:
        registros = reference.carregar_tabela("S_PA")
        if registros:
            for r in registros:
                pid = (r.get("PA_ID") or "").strip()
                if pid and pid not in desc:
                    desc[pid] = (r.get("PA_DC") or "").strip()
    except Exception:
        pass
    return desc


def _regras_do_procedimento(procedimento9: str) -> List[str]:
    """Regras condicionadas registradas no S_PAREGR para o procedimento."""
    regras: List[str] = []
    try:
        registros = reference.carregar_tabela("S_PAREGR")
        if registros:
            for r in registros:
                if (r.get("REG_PA") or "").strip() == procedimento9:
                    regra = (r.get("REG_REGRA") or "").strip()
                    if regra and regra not in regras:
                        regras.append(regra)
    except Exception:
        pass
    return sorted(regras)


# ==============================================================================
# Resumo e registro da remessa
# ==============================================================================

def calcular_resumo(df: Any) -> Dict[str, Any]:
    """Contagens oficiais do TXT (igual ao RELEXP: registros gravados e PACs)."""
    linhas: List[str] = []
    for _, serie in df.iterrows():
        linhas.extend(build_patient_lines(dict(serie)))
    return {
        "competencia": _competencia_header(linhas),
        "qtde_apacs": sum(1 for l in linhas if l.startswith("14")),
        "registros": len(linhas) + 1,  # + header
        "checksum": _calcular_checksum(linhas),
    }


def registrar_remessa(
    txt_path: Path,
    df: Any,
    tipo: str = "1",
    substituida: str = "",
    pasta_base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Registra a remessa apos a exportacao (copia do TXT + metadados + APACs).

    tipo: 1-Normal, 2-Correcao, 3-Substituicao (padrao do RELEXP do antigo).
    Devolve o resumo gravado (usado pelo comprovante).
    """
    txt_path = Path(txt_path)
    resumo = calcular_resumo(df)
    competencia = resumo.get("competencia") or "SEMCOMP"
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(pasta_base) if pasta_base else _pasta_remessas_padrao()
    pasta = base / competencia / carimbo
    pasta.mkdir(parents=True, exist_ok=True)

    copia = pasta / txt_path.name
    try:
        shutil.copy2(txt_path, copia)
    except OSError:
        # Sem cópia o registro continua, mas não se mente no JSON: a chave
        # "copia" só aponta para um arquivo que existe de fato.
        copia = ""

    numeros: List[str] = []
    for _, serie in df.iterrows():
        numero = _digitos(resolve_row_value(dict(serie), "Numero_Apac"), "")
        if numero:
            numeros.append(numero.zfill(13)[:13])
    (pasta / "apacs.txt").write_text("\n".join(numeros) + ("\n" if numeros else ""), encoding="cp1252")

    registro = {
        **resumo,
        "arquivo": txt_path.name,
        "copia": str(copia),
        "pasta": str(pasta),
        "datahora": datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "substituida": substituida,
        "origem": "Penna",
    }
    (pasta / "remessa.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return registro


def apacs_exportadas(pasta_base: Optional[Path] = None) -> Set[str]:
    """Todos os numeros de APAC ja exportados (todas as competencias).

    Alimenta o aviso oficial 010084 do validador (reenvio de APAC).
    """
    base = Path(pasta_base) if pasta_base else _pasta_remessas_padrao()
    numeros: Set[str] = set()
    if not base.exists():
        return numeros
    # Dois layouts de pasta: <base>/<pasta>/apacs.txt (antigo) e
    # <base>/<competencia>/<carimbo>/apacs.txt (atual).
    for padrao in ("*/apacs.txt", "*/*/apacs.txt"):
        for apacs in base.glob(padrao):
            try:
                linhas = apacs.read_text(encoding="cp1252", errors="replace").splitlines()
            except OSError:
                continue  # arquivo ilegível: as demais remessas continuam contando
            for linha in linhas:
                numero = _digitos(linha)
                if numero:
                    numeros.add(numero.zfill(13)[:13])
    return numeros


# ==============================================================================
# Comprovante de remessa (formato RELEXP.prn)
# ==============================================================================

def gerar_comprovante(resumo: Dict[str, Any], destino: Optional[Path] = None) -> Path:
    """Gera o comprovante da remessa no formato do RELEXP.prn do antigo."""
    competencia = resumo.get("competencia", "")
    mes = competencia[4:6] if len(competencia) == 6 else ""
    ano = competencia[:4] if len(competencia) == 6 else ""
    est = _dados_estabelecimento()
    tipo_txt = {"1": "1-NORMAL", "2": "2-CORRECAO", "3": "3-SUBSTITUICAO"}.get(
        str(resumo.get("tipo", "1")), "1-NORMAL"
    )
    hoje = datetime.now().strftime("%d/%m/%Y")
    linha_estrelas = " " + "*" * 78
    linhas = [
        linha_estrelas,
        " MS/SAS/DATASUS/0301 SISTEMA DE INFORMACOES AMBULATORIAIS            DATA COMP.",
        f" {hoje}            COMPROVANTE DE REMESSA APAC-MAG               {mes}/{ano}",
        linha_estrelas,
        f"                                Tabela : {competencia}                               ",
        "",
        "  ORGAO RESPONSVEL PELA INFORMACAO ",
        "",
        f"  NOME   : {est['nome']}",
        "",
        f"  SIGLA  : {est['sigla']:<6}",
        "",
        f"  C.G.C. : {_fmt_cgc(est['cgc'])}",
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
        f"  IDENT. PROCESSAMENTO : {tipo_txt}",
    ]
    if str(resumo.get("tipo")) == "3":
        linhas.append(
            f"                           CAMPO CONTROLE DA REMESSA A SUBSTITUIR: {resumo.get('substituida', '') or '______'}"
        )
    linhas += [
        "",
        "",
        "",
    ]

    if destino is None:
        pasta = Path(resumo.get("pasta") or PASTA_REMESSAS)
        destino = pasta / f"Comprovante_{Path(resumo.get('arquivo', 'remessa')).stem}.PRN"
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(("\r\n".join(linhas)).encode("cp1252", errors="replace"))
    return destino


# ==============================================================================
# Demonstrativo por APAC (estilo R0201)
# ==============================================================================

def _secao_apac(serie: Dict[str, Any], numero_pagina: int,
                est: Dict[str, str], descricoes: Dict[str, str]) -> str:
    apac = _digitos(serie.get("Numero_Apac")).zfill(13)[:13]
    apac_fmt = _com_dv(apac, 12)
    cnes = _digitos(serie.get("Cnes_Executante"), est.get("cnes", "") or "0").zfill(7)[:7]
    sexo = _SEXO.get(to_text(serie.get("Sexo")).strip().upper()[:1], "")
    raca_cod = _digitos(serie.get("Raca")).zfill(2)[:2]
    raca = f"{raca_cod} {_RACA.get(raca_cod, '')}"
    proc_princ = _digitos(serie.get("Cod_Procedimento"))
    procedimentos = [(proc_princ, _digitos(serie.get("Cbo")), _digitos(serie.get("Quantidade")))]
    for idx in range(1, 10):
        codigo = _digitos(serie.get(f"Sec{idx}_Cod_Procedimento"))
        if codigo:
            procedimentos.append((codigo, _digitos(serie.get(f"Sec{idx}_Cbo")), _digitos(serie.get(f"Sec{idx}_Quantidade"))))

    linha_estrelas = " " + "*" * 78
    partes = [
        linha_estrelas,
        " MS/SAS/DATASUS      SISTEMA DE INFORMACOES AMBULATORIAIS            DATA COMP.",
        "               DEMONSTRATIVO DE APAC MAGNETICO (PENNA)               ",
        linha_estrelas,
        f" NUMERO DO APAC: {apac_fmt}                                       PAG.: {numero_pagina:>4}",
        "",
        " IDENTIFICACAO DA UPS/APAC",
        " -------------------------",
        "",
        f" CODIGO DA UNIDADE:             {_com_dv(cnes, 6)}",
        f" NOME/RAZAO SOCIAL UPS:         {est['nome']}",
        f" INICIO DA VALIDADE DA APAC:    {_fmt_data(serie.get('Inicio_Validade'))}",
        f" FIM DA VALIDADE DO APAC:       {_fmt_data(serie.get('Fim_Validade'))}",
        f" PROCEDIMENTO PRINCIPAL:        {_com_dv(proc_princ, 9)}",
        f" CNS DO PROFISSIONAL EXECUTANTE :{_digitos(serie.get('Cns_Executante'))}     EQUIPE INE: {to_text(serie.get('INE'))}",
        "",
        " IDENTIFICACAO DO PACIENTE",
        " -------------------------",
        "",
        f" CPF: {_fmt_cpf(_digitos(serie.get('Cpf_Paciente')))}   PRONTUARIO: {to_text(serie.get('No_Prontuario'))}",
        f" NOME:               {to_text(serie.get('Nome_Paciente')).upper()[:30]:<30} ",
        f" LOGRADOURO:         {(_digitos(serie.get('Codigo_Logradouro')) or _digitos(serie.get('Logradouro'))):>3}-{to_text(serie.get('Rua')).upper():<10}",
        f" ENDERECO:           {to_text(serie.get('Rua')).upper()[:30]:<30}",
        f" NUMERO:             {to_text(serie.get('Numero_Endereco')):<5}             COMPLEMENTO: {to_text(serie.get('Complemento'))[:10]}",
        f" CEP:                {_fmt_cep(_digitos(serie.get('Cep')))}                  BAIRRO: {to_text(serie.get('Bairro')).upper()[:30]}",
        f" MUNICIPIO:          {_digitos(serie.get('Codigo_Municipio')):<6} TEL.: ({_digitos(serie.get('Telefone'))[:2]:>2}){_digitos(serie.get('Telefone'))[2:]}",
        f" DATA DE NASCIMENTO: {_fmt_data(serie.get('Data_Nascimento'))}                   SEXO: {sexo}",
        f" UF DE NASCIMENTO OU NACIONALIDADE: {to_text(serie.get('Uf_Nascimento')):<3}       RACA: {raca}",
        f" NOME DA MAE: {to_text(serie.get('Nome_Da_Mae')).upper()[:30]}",
        f" NOME DO RES: {to_text(serie.get('Nome_Do_Responsavel') or serie.get('Nome_Paciente')).upper()[:30]}",
        f" E-MAIL: {to_text(serie.get('Email'))}",
        " ------------------------------------------------------------------",
        f" C.I.D. PRINCIPAL         {to_text(serie.get('Cid_Princ')).upper()[:4]} ",
        f"        SECUNDARIO            {to_text(serie.get('Cid_Secun')).upper()[:4]} ",
        " ------------------------------------------------------------------",
        " MEDICO SOLICITANTE:",
        f" CPF: {_fmt_cpf(_digitos(serie.get('Medico_Cpf')))}            NOME:   {to_text(serie.get('Nome_Profissional')).upper()[:30]}",
        f" CNS: {_digitos(serie.get('Medico_Cns'))}",
        "",
        " PROCEDIMENTOS REALIZADOS:",
        " -------------------------",
        " CODIGO            PROCEDIMENTO        CBO.    QTD.",
    ]
    for codigo, cbo, qtd in procedimentos:
        partes.append(
            f" {_com_dv(codigo, 9):<12}{descricoes.get(_digitos(codigo)[:9], '')[:24]:<24}{cbo:<8}{qtd.zfill(7) if qtd else '0000000'}"
        )
    for regra in _regras_do_procedimento(_digitos(proc_princ)[:9]):
        descricao = DESCRICOES_REGRAS.get(regra, "")
        partes.append(f" ATENCAO : REGRA CONDICIONADA {regra}{':' + ' ' + descricao if descricao else ''}")
    motivo = _digitos(serie.get("Motivo_Saida"), "11").zfill(2)[:2]
    partes += [
        f" MOTIVO DE SAIDA   : {motivo} / {_MOTIVO.get(motivo, ''):<20}",
        "",
        f" DATA DA OCORRENCIA: {_fmt_data(serie.get('Data_Alta_Obito'))}",
        "",
        f" AUTORIZADOR: {_fmt_cpf(_digitos(serie.get('Autorizador_Cpf')))}       {to_text(serie.get('Autorizador_Nome')).upper()[:30]}",
        f" CNS: {_digitos(serie.get('Autorizador_Cns'))}  COD.ORGAO EMISS.: {to_text(serie.get('Cod_Orgao_Emiss'))}",
        "",
    ]
    return "\r\n".join(partes)


def gerar_demonstrativo(df: Any, destino: Optional[Path] = None,
                        pasta_base: Optional[Path] = None) -> Path:
    """Gera o demonstrativo completo por APAC no estilo R0201 do antigo."""
    est = _dados_estabelecimento()
    descricoes = _descricoes_procedimentos()
    secoes: List[str] = []
    numero_pagina = 0
    primeira: Optional[Dict[str, Any]] = None
    for _, serie in df.iterrows():
        dados = dict(serie)
        if primeira is None:
            primeira = dados
        numero_pagina += 1
        secoes.append(_secao_apac(dados, numero_pagina, est, descricoes))

    if primeira is None:
        primeira = {}
    if destino is None:
        linhas: List[str] = []
        for _, serie in df.iterrows():
            linhas.extend(build_patient_lines(dict(serie)))
        competencia = _competencia_header(linhas)
        pasta = (Path(pasta_base) if pasta_base else _pasta_remessas_padrao()) / (competencia or "SEMCOMP") / "demonstrativo"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"Demonstrativo_{_digitos(primeira.get('Numero_Apac'), 'APAC')[:13]}.TXT"
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(("\r\n".join(secoes) + "\r\n").encode("cp1252", errors="replace"))
    return destino
