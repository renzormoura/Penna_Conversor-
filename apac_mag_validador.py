r"""Validador pre-exportacao do Excel -> TXT fiscal (gate do faturamento).

Reproduz a checagem que o programa antigo APAC-MAG (DATASUS/SIA) fazia ao
processar o arquivo: enquanto houver ocorrencia do tipo ERR, o arquivo fiscal
NAO pode ser gerado. As ocorrencias seguem o mesmo formato do relatorio
RCONSIST do sistema antigo:

    CMPT.  NUM.APAC      TIPO SEQ.   COD.   DESCRICAO
    202511 3325700656553 ERR  000001 000024 PROC.(0905010035) DE APAC PMAE...

Regras de numeracao copiadas do antigo:
    - SEQ numerico (000001, 000002...) REINICIA a cada APAC;
    - ocorrencias de corpo usam o rotulo CORPO (RCONSIST.JUN: "ERR  CORPO  010025");
    - avisos de habilitacao usam o rotulo HABILI (RCONSIST.OUT) e avisos de
      CNES usam o rotulo CNES (log S_APAERR 202602);
    - ERR bloqueia a exportacao; AVS (aviso) e listado mas permite gerar
      (evidencia: competencia 202510 com 1012 AVS foi exportada normalmente).

Fontes oficiais (instalacao real C:\APAC e backups .ZBF decodificados):
    - RCONSIST.MAI/.JUN/.NOV/.OUT, R0201.NOV -> codigos e mensagens reais;
    - S_APAERR.dbf dos backups               -> log interno de ocorrencias;
    - LERNOTAS.TXT v03.17..03.26             -> regras de CPF/CNS/atributos;
    - S_PA / S_PAHA / S_PAPA / S_CID / XUPSHA -> regras SIGTAP por competencia.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

import apac_mag_bases as bases
import apac_mag_remessa

# Helpers de string: fonte única em penna.core
from penna.core import (
    normalize_date,
    digits as _digits_fn,
    birth_date_to_txt,
    resolve_competence,
    resolve_row_value,
    text,
    text_upper,
)
# Configuração do estabelecimento (defaults e CNES padrão, lidos no uso)
from penna.config import get_defaults


# Aliases de retrocompatibilidade (outros módulos importavam estes nomes)
def to_text(value: Any) -> str:
    return text(value)

def only_digits(value: Any, default: str = "0") -> str:
    d = _digits_fn(value)
    return d if d else default

# ==============================================================================
# Codigos de erro oficiais observados no programa antigo
# ==============================================================================

# Procedimento principal da planilha OCI (APAC PMAE na mensagem 000024).
_APAC_PMAE = "0905010035"

# Fallback (lista fixa) do AVS 030008 quando nao ha base XUPSHA/S_PAHA:
# procedimentos que geraram o aviso real no RCONSIST.OUT/log 202510 contra o
# CNES 4234316. Com as bases presentes, a regra passa a usar S_PAHA x XUPSHA.
_PROCEDS_EXIGEM_HABILITACAO = {"0211060020", "0211060127", "0211060232", "0301010072"}

def _cnes_padrao() -> str:
    """CNES executante do estabelecimento, lido do config no momento do uso."""
    return (get_defaults().get("Cnes_Executante") or "").zfill(7)

# Racas validas do campo AP_RACA (01..05 informadas, 99 = sem informacao).
_RACAS_VALIDAS = {"01", "02", "03", "04", "05", "99"}

# CEPs de garantia quando a base S_CEP.DBF nao esta disponivel (municipio).
_CEPS_GARANTIDOS = {"26700000"}

CATALOGO_CODIGOS: Dict[str, str] = {
    # ---- ERR (bloqueiam a exportacao) ----
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
    # 000005 e estrutural (planilha vazia, competencia invalida/mista): sem
    # competencia nao ha arquivo valido, entao bloqueia mesmo sem amostra oficial.
    "000005": "COMPETENCIA / NUMERO APAC invalidos para exportacao (estrutural, sem amostra oficial)",
    # ---- AVS (avisos; o antigo exporta mesmo com eles) ----
    "010084": "NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE",
    "010092": "<CAMPO>: TEXTO MAIOR QUE A LARGURA DO LAYOUT, SERA TRUNCADO  [regra local do Penna]",
    "030001": "CNES EXECUTANTE(nnnnnnn) NAO ENCONTRADO",
    "030008": "PROCED.(...) EXIGE HABILITACAO NAO ENCONTRADA NO CNES(nnnnnnn)",
    "030009": "REGRA CONDICIONADA 0009 : PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS (AVS do R0201)",
    # ---- Codigos HIPOTESE: mensagens no padrao observado (LERNOTAS v03.25),
    #      sem amostra oficial do comportamento. Severidade = SEVERIDADE_HIPOTESE ----
    "000006": "PROC.(...) EXIGE PELO MENOS (n) PROC. SECUNDARIO OBRIGATORIO. (HIPOTESE)",
    "000007": "PROC.(...) NAO PERMITIDO PARA SEXO DO USUARIO (HIPOTESE)",
    "000008": "PROC.(...) QTD. ACIMA DO MAXIMO PERMITIDO : n (HIPOTESE)",
    "000009": "PROC. SECUNDARIO (x) NAO PERMITIDO PARA O PROC. PRINCIPAL (HIPOTESE)",
    "010040": "CID (xxxx) NAO ENCONTRADO (HIPOTESE)",
    "010041": "CID (xxxx) NAO PERMITIDO PARA O SEXO DO USUARIO (HIPOTESE)",
}

# Regras HIPOTESE (sem confirmacao do comportamento oficial) so AVISAM: uma
# regra errada bloquearia exportacoes validas. Depois de confirmar uma regra
# com uma amostra real do RCONSIST, mude esta constante para "ERR" (ou mova o
# codigo para o grupo ERR acima).
SEVERIDADE_HIPOTESE = "AVS"

_CODIGOS_HIPOTESE = ("000006", "000007", "000008", "000009", "010040", "010041")
_CODIGOS_ERR = ("000005", "000016", "000024", "010022", "010025", "010027", "010032",
                "010042", "010083", "010090", "010091")

# Severidade de cada codigo (fonte unica para docs/relatorios e testes).
SEVERIDADE_PADRAO: Dict[str, str] = {
    cod: ("ERR" if cod in _CODIGOS_ERR else SEVERIDADE_HIPOTESE if cod in _CODIGOS_HIPOTESE else "AVS")
    for cod in CATALOGO_CODIGOS
}


class ResultadoValidacao(list):
    """Lista de Ocorrencia (compativel com o retorno antigo) + metadados.

    regras_desativadas: regras que nao rodaram por falta da base de dados
    (ex.: "CEP (S_CEP)"), para a UI avisar que a validacao foi parcial.
    """

    def __init__(self, itens: Iterable[Any] = (), regras_desativadas: Iterable[str] = ()):
        super().__init__(itens)
        self.regras_desativadas: List[str] = list(regras_desativadas)


@dataclass(frozen=True)
class Ocorrencia:
    """Uma linha do relatorio de consistencia (formato RCONSIST)."""

    cmpt: str
    num_apac: str
    tipo: str            # "ERR" (bloqueia) ou "AVS" (aviso, permite exportar)
    seq: str             # "000001"... ou rotulo textual ("CORPO", "HABILI", "CNES")
    cod: str
    descricao: str

    @property
    def bloqueia(self) -> bool:
        return self.tipo == "ERR"


def formatar_linha_rconsist(o: Ocorrencia) -> str:
    """Formata a ocorrencia exatamente como a linha do RCONSIST do antigo."""
    return f" {o.cmpt} {o.num_apac} {o.tipo:<4} {o.seq:<6} {o.cod} {o.descricao}"


def tem_erros(ocorrencias: Iterable[Ocorrencia]) -> bool:
    """True quando existe ao menos uma ocorrencia ERR (bloqueia a geracao)."""
    return any(o.tipo == "ERR" for o in ocorrencias)


def resumo(ocorrencias: Iterable[Ocorrencia]) -> tuple:
    """Devolve (quantidade_err, quantidade_avs)."""
    itens = list(ocorrencias)
    n_err = sum(1 for o in itens if o.tipo == "ERR")
    return n_err, len(itens) - n_err


# ==============================================================================
# Bases do programa antigo (via apac_mag_bases; ausencia desativa a regra)
# ==============================================================================

_ceps_cache: Optional[Set[str]] = None
_ceps_carregado = False


def carregar_base_ceps() -> Optional[Set[str]]:
    """S_CEP.DBF do programa antigo (1.6 milhao de CEPs); None se ausente."""
    global _ceps_cache, _ceps_carregado
    if _ceps_carregado:
        return _ceps_cache
    _ceps_carregado = True
    registros = bases.carregar_tabela("S_CEP")
    if not registros:
        _ceps_cache = None
        return None
    _ceps_cache = {r.get("CEP", "") for r in registros if r.get("CEP")} | _CEPS_GARANTIDOS
    return _ceps_cache


def carregar_catalogo_procedimentos(
    competencia: str = "", sigtap_competencia: Optional[str] = None
) -> Optional[Dict[str, Dict[str, str]]]:
    """S_PA indexado por codigo, na versao vigente na competencia da planilha.

    Usa a competencia mais alta <= `competencia` (nunca uma futura). Sem
    competencia, cai na mais recente da tabela. None desativa as regras
    (tabela ausente ou sem versao vigente para o mes).
    """
    registros = bases.carregar_tabela("S_PA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    if competencia:
        registros = bases.filtrar_por_competencia(registros, "PA_CMP", competencia)
    else:
        mais_recente = max((r.get("PA_CMP", "") for r in registros), default="")
        registros = [r for r in registros if r.get("PA_CMP", "") == mais_recente]
    catalogo = {r["PA_ID"]: r for r in registros if r.get("PA_ID")}
    return catalogo or None


def _pares_secundarios(
    competencia: str, sigtap_competencia: Optional[str] = None
) -> Optional[Dict[str, Dict[str, str]]]:
    """S_PAPA da competencia -> {principal: {secundario: qtmax}}; None se ausente."""
    registros = bases.carregar_tabela("S_PAPA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    vigentes = bases.filtrar_por_competencia(registros, "PAPA_CMP", competencia)
    pares: Dict[str, Dict[str, str]] = {}
    for r in vigentes:
        principal = (r.get("PAPA_PRINC") or "").strip()
        secundario = (r.get("PAPA_SECUN") or "").strip()
        if principal and secundario:
            pares.setdefault(principal, {})[secundario] = (r.get("PAPA_QTMAX") or "").strip()
    return pares


def _habilitacoes_exigidas(
    competencia: str, sigtap_competencia: Optional[str] = None
) -> Optional[Dict[str, set]]:
    """S_PAHA da competencia -> {procedimento: {HA...}}; None se ausente."""
    registros = bases.carregar_tabela("S_PAHA", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    vigentes = bases.filtrar_por_competencia(registros, "PAHA_CMP", competencia)
    exigidas: Dict[str, set] = {}
    for r in vigentes:
        proc = (r.get("PAHA_PA") or "").strip()
        ha = (r.get("PAHA_HA") or "").strip()
        if proc and ha:
            exigidas.setdefault(proc, set()).add(ha)
    return exigidas


def _cids_validos_de(
    registros: Optional[List[Dict[str, str]]], competencia: str
) -> Optional[Set[str]]:
    """Registros do S_CID -> conjunto de codigos vigentes na competencia."""
    if not registros:
        return None
    vigentes = bases.filtrar_por_faixa(registros, "CMP_INI", "CMP_FIM", competencia)
    return {((r.get("CD_COD") or "").strip().upper()) for r in vigentes if r.get("CD_COD")}


def _cids_validos(
    competencia: str, sigtap_competencia: Optional[str] = None
) -> Optional[Set[str]]:
    """S_CID da competencia -> conjunto de codigos validos; None se ausente."""
    registros = bases.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
    return _cids_validos_de(registros, competencia)


def _indice_restricoes_sexos(
    registros: Optional[List[Dict[str, str]]]
) -> Optional[Dict[str, str]]:
    """Indice {CD_COD: RESTRSEXO} montado UMA vez por validacao.

    Substitui a varredura O(n) da lista por linha (a mesma primeira ocorrencia
    vence, igual ao `for` original). Devolve None quando nao ha registros.
    """
    if not registros:
        return None
    indice: Dict[str, str] = {}
    for r in registros:
        cod = (r.get("CD_COD") or "").strip().upper()
        if cod and cod not in indice:
            indice[cod] = (r.get("RESTRSEXO") or "").strip()
    return indice


def _restricao_sexo_cid(
    cod: str,
    registros: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = None,
    sigtap_competencia: Optional[str] = None,
) -> Optional[str]:
    """RESTRSEXO do S_CID para o codigo (1 = so masculino, 2 = so feminino).

    `registros` aceita a lista de registros (formato original) ou o indice
    {CD_COD: RESTRSEXO} pre-construido no ctx da validacao (lookup O(1)).
    """
    if registros is None:
        registros = bases.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
    if not registros:
        return None
    if isinstance(registros, dict):
        if cod not in registros:
            return None
        return (registros[cod] or "").strip()
    for r in registros:
        if ((r.get("CD_COD") or "").strip().upper()) == cod:
            return (r.get("RESTRSEXO") or "").strip()
    return None


def _regras_condicionadas(
    competencia: str, sigtap_competencia: Optional[str] = None
) -> Dict[str, set]:
    """S_PAREGR da competencia -> {procedimento: {regra...}}."""
    registros = bases.carregar_tabela("S_PAREGR", sigtap_competencia=sigtap_competencia)
    if not registros:
        return {}
    vigentes = bases.filtrar_por_competencia(registros, "REG_CMP", competencia)
    regras: Dict[str, set] = {}
    for r in vigentes:
        proc = (r.get("REG_PA") or "").strip()
        regra = (r.get("REG_REGRA") or "").strip()
        if proc and regra:
            regras.setdefault(proc, set()).add(regra)
    return regras


# ==============================================================================
# Helpers de dados da linha
# ==============================================================================

# Campos de data gravados no TXT (alem do nascimento, validado a parte).
_CAMPOS_DATA_TXT = ("Inicio_Validade", "Fim_Validade", "Data_Solicitacao",
                    "Data_Autorizacao", "Data_Alta_Obito", "Data_Emissao")


# Campos de texto do TXT com largura fixa (campo da planilha -> largura do layout).
# Acima disso o gerador trunca em silencio (pad_right); aqui vira aviso.
_LARGURA_TEXTO_TXT = {
    "Nome_Paciente": 30, "Nome_Da_Mae": 30, "Nome_Do_Responsavel": 30, "Rua": 30,
    "Numero_Endereco": 5, "Complemento": 10, "Bairro": 30, "Email": 40,
    "Nome_Profissional": 30, "Autorizador_Nome": 30, "Cid_Causas_Assoc": 4,
    "No_Prontuario": 10, "Cod_Orgao_Emiss": 10, "INE": 10, "Etnia": 4,
}


def _caractere_invalido_no_txt(valor: str) -> str:
    """Primeiro caractere que o TXT cp1252 nao suporta ('' se nenhum).

    Controle (quebra de linha/tab) desmonta o layout fixo; fora do cp1252 o
    gerador antigo gravava '?' no lugar, corrompendo o dado fiscal.
    """
    for ch in valor:
        if ord(ch) < 32 or ord(ch) == 127:
            return repr(ch)
        try:
            ch.encode("cp1252")
        except UnicodeEncodeError:
            return ch
    return ""


def _data_real(aaaammdd: str) -> bool:
    if len(aaaammdd) != 8 or not aaaammdd.isdigit():
        return False
    try:
        date(int(aaaammdd[:4]), int(aaaammdd[4:6]), int(aaaammdd[6:8]))
        return True
    except ValueError:
        return False


def _parse_data(valor: Any) -> str:
    """AAAAMMDD pela mesma normalizacao do gerador ("" quando invalida)."""
    return normalize_date(valor)


def _formatar_data(aaaammdd: str) -> str:
    if len(aaaammdd) != 8:
        return aaaammdd
    return f"{aaaammdd[6:8]}/{aaaammdd[4:6]}/{aaaammdd[0:4]}"


def _competencia(row: Dict[str, Any]) -> str:
    """Competência (AAAAMM) analisada no formulário — mesma regra do gerador
    (coluna Competencia em qualquer formato, senão as datas do formulário).
    Vazio quando o mês não pode ser identificado (bloqueia como 000005)."""
    return resolve_competence(row)


def _procedimentos_da_linha(row: Dict[str, Any]) -> List[tuple]:
    """Lista (codigo10, quantidade) do principal e dos secundarios preenchidos."""
    itens: List[tuple] = []
    principal = only_digits(resolve_row_value(row, "Cod_Procedimento"), "")
    if principal:
        itens.append((principal.rjust(10, "0"), only_digits(resolve_row_value(row, "Quantidade"), "0")))
    for index in range(1, 10):
        codigo = only_digits(resolve_row_value(row, f"Sec{index}_Cod_Procedimento"), "")
        if not codigo:
            continue
        qtd = only_digits(resolve_row_value(row, f"Sec{index}_Quantidade"), "0")
        itens.append((codigo.rjust(10, "0"), qtd))
    return itens


def _idade_anos(nasc_aaaammdd: str, competencia: str) -> int:
    try:
        ano_nasc, mes_nasc = int(nasc_aaaammdd[:4]), int(nasc_aaaammdd[4:6])
        ano_ref, mes_ref = int(competencia[:4]), int(competencia[4:6])
    except (ValueError, IndexError):
        return -1
    idade = ano_ref - ano_nasc
    if mes_ref < mes_nasc:
        idade -= 1
    return idade


class _Coletor:
    """Acumula ocorrencias no padrao do antigo (SEQ reinicia por APAC;
    rotulos CORPO/HABILI/CNES nao recebem numero)."""

    def __init__(self) -> None:
        self.itens: List[Ocorrencia] = []
        self._chave_atual: Optional[tuple] = None
        self._contador = 0

    def adicionar(self, cmpt: str, num_apac: str, tipo: str, rotulo_seq: str,
                  cod: str, descricao: str) -> None:
        chave = (cmpt, num_apac)
        if chave != self._chave_atual:
            self._chave_atual = chave
            self._contador = 0
        if rotulo_seq:
            seq = rotulo_seq
        else:
            self._contador += 1
            seq = f"{self._contador:06d}"
        self.itens.append(Ocorrencia(cmpt, num_apac, tipo, seq, cod, descricao))


# ==============================================================================
# Validacao por linha
# ==============================================================================

def _validar_linha(row: Dict[str, Any], coletor: _Coletor, ctx: Dict[str, Any]) -> None:
    # Competencia ja calculada pelo loop de validar_planilha (ctx["_cmpt"]);
    # o fallback cobre chamadas diretas de testes/ferramentas.
    cmpt = ctx["_cmpt"] if "_cmpt" in ctx else _competencia(row)
    num_apac = only_digits(resolve_row_value(row, "Numero_Apac"), "")
    texto_apac = to_text(resolve_row_value(row, "Numero_Apac")).strip()

    # --- NUMERO DA APAC (HIPOTESE 000005) ---
    if not num_apac or set(num_apac) == {"0"}:
        coletor.adicionar(cmpt, "", "ERR", "CORPO", "000005",
                          f"NUMERO DA APAC ({texto_apac or 'VAZIO'}) INVALIDO PARA EXPORTACAO")
        return  # sem APAC as demais regras por proc perdem o sentido

    # --- HISTORICO DE REMESSA (010084: APAC ja exportada) ---
    # Avisa, nao bloqueia: o historico e o proprio registro local do Penna e
    # a correcao/substituicao reenvia os mesmos numeros legitimamente; quem
    # barra duplicidade de verdade e o site do DATASUS. ERR aqui impedia
    # reexportar a planilha na mesma sessao apos uma exportacao bem-sucedida.
    historico = ctx.get("historico_apacs")
    if historico is not None and num_apac in historico:
        coletor.adicionar(cmpt, num_apac, "AVS", "CORPO", "010084",
                          "NUMERO APAC: ENCONTRADO NO HISTORICO DE APAC DO SITE")

    # --- CNES executante (AVS 030001) ---
    cnes = only_digits(resolve_row_value(row, "Cnes_Executante", get_defaults().get("Cnes_Executante", "")), "")
    cnes7 = cnes.zfill(7)[:7]
    if cnes7 != _cnes_padrao():
        coletor.adicionar(cmpt, num_apac, "AVS", "CNES", "030001",
                          f"CNES EXECUTANTE({cnes7}) NAO ENCONTRADO")

    # --- DATA DE NASCIMENTO (ERR 010025) ---
    nasc = birth_date_to_txt(resolve_row_value(row, "Data_Nascimento", ""))
    nasc_valida = _data_real(nasc)
    if not nasc_valida:
        coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010025", "DATA DE NASCIMENTO INVALIDA")

    # --- DATAS DO TXT: preenchida e invalida bloqueia (ERR 010090, regra local) ---
    for campo in _CAMPOS_DATA_TXT:
        bruto = resolve_row_value(row, campo)
        if bruto and not _parse_data(bruto):
            coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010090",
                              f"{campo.upper()}: DATA INVALIDA ({bruto})")

    # --- TEXTOS DO TXT: caractere nao suportado (ERR 010091) e largura (AVS 010092) ---
    for campo, largura in _LARGURA_TEXTO_TXT.items():
        valor = resolve_row_value(row, campo)
        if not valor:
            continue
        ruim = _caractere_invalido_no_txt(valor)
        if ruim:
            coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010091",
                              f"{campo.upper()}: CARACTERE NAO SUPORTADO NO TXT ({ruim})")
        if len(valor) > largura:
            coletor.adicionar(cmpt, num_apac, "AVS", "CORPO", "010092",
                              f"{campo.upper()}: TEXTO COM {len(valor)} CARACTERES, "
                              f"MAXIMO {largura} (SERA TRUNCADO)")

    # --- CEP (ERR 010022; base S_CEP.DBF do antigo) ---
    if ctx.get("base_ceps") is not None:
        cep_digitos = only_digits(resolve_row_value(row, "Cep", ""), "")
        cep8 = cep_digitos.zfill(8)[:8] if cep_digitos else "00000000"
        if cep8 not in ctx["base_ceps"]:
            coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010022",
                              f"CEP ({cep8}) NAO ENCONTRADO")

    # --- RACA (ERR 010027) ---
    raca_digitos = only_digits(resolve_row_value(row, "Raca", ""), "")
    raca = raca_digitos.zfill(2)[:2] if raca_digitos else "99"
    if raca not in _RACAS_VALIDAS:
        coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010027", f"RACA ({raca}) INVALIDA")

    # --- LOGRADOURO (ERR 010032) ---
    codigo_logr = to_text(resolve_row_value(row, "Codigo_Logradouro", "Cod_Logradouro")).strip()
    if not codigo_logr:
        codigo_logr = to_text(resolve_row_value(row, "Logradouro", "")).strip()
    if not codigo_logr or not codigo_logr.isdigit() or len(codigo_logr) > 3:
        coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010032",
                          f"LOGRADOURO ({codigo_logr}) INVALIDO")

    # --- DATA DE SOLICITACAO x NASCIMENTO (ERR 010042) ---
    dtsolic = _parse_data(resolve_row_value(row, "Data_Solicitacao", ""))
    if nasc_valida and dtsolic and dtsolic < nasc:
        coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010042",
                          f"DATA DE SOLICITACAO ({_formatar_data(dtsolic)}) "
                          f"ANTERIOR A DATA DE NASCIMENTO({_formatar_data(nasc)})")

    # --- DATA DE ENCERRAMENTO x FIM DA VALIDADE (ERR 010083) ---
    dtocorr = _parse_data(resolve_row_value(row, "Data_Alta_Obito", ""))
    dtfim = _parse_data(resolve_row_value(row, "Fim_Validade", ""))
    if dtocorr and dtfim and dtocorr > dtfim:
        coletor.adicionar(cmpt, num_apac, "ERR", "CORPO", "010083",
                          f"DATA DE ENCERRAMENTO ({_formatar_data(dtocorr)}) "
                          f"MAIOR QUE DATA DE FIM ({_formatar_data(dtfim)})")

    # --- PROCEDIMENTOS ---
    itens = _procedimentos_da_linha(row)
    catalogo_pa: Optional[Dict[str, Dict[str, str]]] = ctx.get("catalogo_pa")
    pares = ctx.get("pares_secundarios")
    exigidas = ctx.get("habilitacoes_exigidas")
    habilitacoes_cnes = ctx.get("habilitacoes_cnes")
    sexo_paciente = text_upper(resolve_row_value(row, "Sexo", ""))[:1]

    # QTD zero (ERR 000024; mensagem literal do RCONSIST.NOV).
    if any(proc == _APAC_PMAE for proc, _ in itens):
        for proc, qtd in itens:
            if (qtd or "0").lstrip("0") == "":
                qtd_zero = ((qtd or "0").lstrip("0") or "0").rjust(6)
                coletor.adicionar(
                    cmpt, num_apac, "ERR", "", "000024",
                    f"PROC.({proc}) DE APAC PMAE, NAO É PERMITIDO "
                    f"QTD.({qtd_zero}) ZERO PROC.PRINC. OU SECUNDARIO.",
                )

    # --- Regras SIGTAP por procedimento (S_PA / S_PAPA / S_PAHA / S_CID) ---
    for idx_item, (proc, qtd) in enumerate(itens):
        chave = proc[:9]
        pa = None
        if catalogo_pa is not None:
            pa = catalogo_pa.get(chave) or catalogo_pa.get(chave.lstrip("0").zfill(9))

        # IDADE MIN/MAX (ERR 000016; S_PA: PA_IDADEMN/PA_IDADEMX)
        if pa is not None and nasc_valida and cmpt:
            idade = _idade_anos(nasc, cmpt)
            if idade >= 0:
                try:
                    idade_max = int(pa.get("PA_IDADEMX", "999") or 999)
                    idade_min = int(pa.get("PA_IDADEMN", "999") or 999)
                except ValueError:
                    idade_max = idade_min = 999
                if idade_max < 999 and idade > idade_max:
                    coletor.adicionar(cmpt, num_apac, "ERR", "", "000016",
                                      f"PROC.({proc}) NAO PERMITIDO PARA IDADE MAX.DO USUARIO : {idade_max}")
                elif idade_min < 999 and idade < idade_min:
                    coletor.adicionar(cmpt, num_apac, "ERR", "", "000016",
                                      f"PROC.({proc}) NAO PERMITIDO PARA IDADE MIN.DO USUARIO : {idade_min}")

        # SEXO RESTRITO (HIPOTESE 000007; S_PA: PA_SEXO = M/F/A)
        if pa is not None and sexo_paciente in ("M", "F", "I"):
            sexo_pa = (pa.get("PA_SEXO") or "").strip().upper()
            if sexo_pa in ("M", "F") and sexo_paciente != sexo_pa and sexo_paciente != "I":
                coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "", "000007",
                                  f"PROC.({proc}) NAO PERMITIDO PARA SEXO DO USUARIO")

        # QUANTIDADE MAXIMA (HIPOTESE 000008; S_PA: PA_QTDMAX)
        if pa is not None:
            try:
                qtd_max = int(pa.get("PA_QTDMAX", "9999") or 9999)
            except ValueError:
                qtd_max = 9999
            qtd_num = int((qtd or "0").lstrip("0") or 0)
            if qtd_max < 9999 and qtd_num > qtd_max:
                coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "", "000008",
                                  f"PROC.({proc}) QTD. ACIMA DO MAXIMO PERMITIDO : {qtd_max}")

        # SECUNDARIO OBRIGATORIO (HIPOTESE 000006; S_PA: PA_SECOBRI = S)
        if idx_item == 0 and pa is not None and (pa.get("PA_SECOBRI") or "").strip().upper() == "S":
            if len(itens) < 2:
                coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "", "000006",
                                  f"PROC.({proc}) EXIGE PELO MENOS (1) PROC. SECUNDARIO OBRIGATORIO.")

        # HABILITACAO (AVS 030008; S_PAHA x XUPSHA, fallback lista fixa)
        if exigidas is not None and habilitacoes_cnes is not None and proc[:9] in exigidas:
            necessarias = exigidas[proc[:9]]
            if necessarias and not (habilitacoes_cnes & necessarias):
                coletor.adicionar(cmpt, num_apac, "AVS", "HABILI", "030008",
                                  f"PROCED.({proc}) EXIGE HABILITACAO NAO ENCONTRADA NO CNES({cnes7})")
        elif exigidas is None and habilitacoes_cnes is None and proc in _PROCEDS_EXIGEM_HABILITACAO:
            coletor.adicionar(cmpt, num_apac, "AVS", "HABILI", "030008",
                              f"PROCED.({proc}) EXIGE HABILITACAO NAO ENCONTRADA NO CNES({cnes7})")

        # PAR PRINCIPAL/SECUNDARIO (HIPOTESE 000009; S_PAPA)
        if pares is not None and idx_item > 0:
            principal9 = itens[0][0][:9]
            if principal9 in pares:
                permitidos = pares[principal9]
                permitidos_sem_dv = {p.lstrip("0") for p in permitidos}
                if chave not in permitidos and chave.lstrip("0") not in permitidos_sem_dv:
                    coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "", "000009",
                                      f"PROC. SECUNDARIO ({proc}) NAO PERMITIDO PARA O PROC. PRINCIPAL ({itens[0][0]})")
                else:
                    qtmax_txt = permitidos.get(chave) or ""
                    if not qtmax_txt:
                        for p, qt in permitidos.items():
                            if p.lstrip("0") == chave.lstrip("0"):
                                qtmax_txt = qt
                                break
                    try:
                        qtmax = int((qtmax_txt or "9999").lstrip("0") or 9999)
                    except ValueError:
                        qtmax = 9999
                    qtd_num = int((qtd or "0").lstrip("0") or 0)
                    if qtmax < 9999 and qtd_num > qtmax:
                        coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "", "000008",
                                          f"PROC.({proc}) QTD. ACIMA DO MAXIMO PERMITIDO : {qtmax}")

    # Regra condicionada 0009 (AVS, mensagem impressa no R0201 do antigo)
    regras = ctx.get("regras_condicionadas") or {}
    principal9 = itens[0][0][:9] if itens else ""
    if "0009" in regras.get(principal9, set()) and len(itens) > 1:
        tem_valor_sec = any(qtd.lstrip("0") for _, qtd in itens[1:])
        if tem_valor_sec:
            coletor.adicionar(cmpt, num_apac, "AVS", "CORPO", "030009",
                              "REGRA CONDICIONADA 0009 : PROCEDIMENTO PRINCIPAL IMPEDE VALOR NOS SECUNDARIOS")

    # --- CID PRINCIPAL (S_CID: existencia + restricao de sexo) ---
    cid = text_upper(resolve_row_value(row, "Cid_Princ", "")).replace(" ", "")[:4]
    if cid:
        cids = ctx.get("cids_validos")
        if cids is not None:
            # aceita categoria (3 digitos) quando a subcategoria digitada nao existe
            if cid not in cids and cid[:3] not in cids:
                coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "CORPO", "010040",
                                  f"CID ({cid}) NAO ENCONTRADO")
            else:
                registros_cid = ctx.get("cids_restricoes")
                if registros_cid is None:
                    registros_cid = ctx.get("cids_registros")
                restricao = _restricao_sexo_cid(cid[:3], registros_cid)
                sexo_esperado = {"1": "M", "2": "F"}.get(restricao or "", "")
                if sexo_esperado and sexo_paciente in ("M", "F") and sexo_paciente != sexo_esperado:
                    coletor.adicionar(cmpt, num_apac, SEVERIDADE_HIPOTESE, "CORPO", "010041",
                                      f"CID ({cid}) NAO PERMITIDO PARA O SEXO DO USUARIO")


# ==============================================================================
# Entrada principal
# ==============================================================================

def _regras_desativadas(ctx: Dict[str, Any], sigtap_ativo: bool) -> List[str]:
    """Regras que NAO rodaram por falta de base (validacao parcial).

    As regras SIGTAP desligadas de proposito (usar_sigtap=False) nao entram.
    """
    faltando: List[str] = []
    if ctx.get("base_ceps") is None:
        faltando.append("CEP inexistente (S_CEP)")
    if not ctx.get("catalogo_pa"):
        faltando.append("idade, sexo, quantidade e secundario obrigatorio (S_PA)")
    if sigtap_ativo:
        if ctx.get("pares_secundarios") is None:
            faltando.append("par principal/secundario (S_PAPA)")
        if ctx.get("habilitacoes_exigidas") is None or ctx.get("habilitacoes_cnes") is None:
            faltando.append("habilitacao do CNES (S_PAHA/XUPSHA)")
        if ctx.get("cids_validos") is None:
            faltando.append("CID valido e restricao de sexo (S_CID)")
        if not ctx.get("regras_condicionadas"):
            faltando.append("regra condicionada (S_PAREGR)")
    return faltando


def validar_planilha(
    df: Any,
    base_ceps: Optional[Set[str]] = None,
    catalogo_pa: Optional[Dict[str, Dict[str, str]]] = None,
    usar_remessa: bool = True,
    pasta_remessas: Optional[Path] = None,
    usar_sigtap: bool = True,
    pares_secundarios: Optional[Dict[str, Dict[str, str]]] = None,
    habilitacoes_exigidas: Optional[Dict[str, set]] = None,
    habilitacoes_cnes: Optional[set] = None,
    cids_validos: Optional[Set[str]] = None,
    cids_registros: Optional[List[Dict[str, str]]] = None,
    regras_condicionadas: Optional[Dict[str, set]] = None,
    historico_apacs: Optional[Set[str]] = None,
    sigtap_competencia: Optional[str] = None,
) -> ResultadoValidacao:
    """Valida TODAS as linhas da planilha carregada (apac_mag_gerador.carregar_planilha).

    Devolve as ocorrencias no formato do RCONSIST. A geracao do TXT so pode
    prosseguir quando NAO houver ocorrencia do tipo ERR (AVS nao bloqueia,
    mesmo comportamento do programa antigo).

    Os parametros permitem injetar bases em testes (inclusive um dicionario
    vazio para desativar a regra); sem eles, as bases SIA sao carregadas uma
    unica vez (C:/APAC ou dados/bases_sia). usar_sigtap=False desativa de uma
    vez as regras S_PAPA/S_PAHA/S_PA(extras)/S_CID (mantendo idade e CEP).

    sigtap_competencia: quando informado (ex.: "202606"), usa o ZIP do SIGTAP
    baixado como fallback caso as tabelas DBF locais nao cubram esse mes.
    """
    if df is None:
        return ResultadoValidacao([Ocorrencia("", "", "ERR", "CORPO", "000005",
                                              "PLANILHA VAZIA - NENHUMA APAC PARA EXPORTAR")])

    linhas = [dict(serie) for _, serie in df.iterrows()]
    if not linhas:
        return ResultadoValidacao([Ocorrencia("", "", "ERR", "CORPO", "000005",
                                              "PLANILHA VAZIA - NENHUMA APAC PARA EXPORTAR")])

    coletor = _Coletor()
    competencia_ref = _competencia(linhas[0])
    competencias_divergentes: Set[str] = set()

    # Bases compartilhadas (uma unica leitura por execucao)
    if base_ceps is None:
        base_ceps = carregar_base_ceps()
    if catalogo_pa is None:
        catalogo_pa = carregar_catalogo_procedimentos(competencia_ref, sigtap_competencia)
    if usar_sigtap and competencia_ref:
        if pares_secundarios is None:
            pares_secundarios = _pares_secundarios(competencia_ref, sigtap_competencia)
        if habilitacoes_exigidas is None:
            habilitacoes_exigidas = _habilitacoes_exigidas(competencia_ref, sigtap_competencia)
        if habilitacoes_cnes is None:
            habilitacoes_cnes = bases.carregar_habilitacoes_cnes(_cnes_padrao(), competencia_ref)
        if cids_registros is None:
            # Uma unica carga do S_CID alimenta existencia E restricao de sexo
            # (antes: 1 carga no inicio + 1 varredura O(n) por linha).
            cids_registros = bases.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)
        if cids_validos is None:
            cids_validos = _cids_validos_de(cids_registros, competencia_ref)
        if regras_condicionadas is None:
            regras_condicionadas = _regras_condicionadas(competencia_ref, sigtap_competencia)
    else:
        pares_secundarios = pares_secundarios if pares_secundarios is not None else None
        habilitacoes_exigidas = None if habilitacoes_exigidas is None else habilitacoes_exigidas
        habilitacoes_cnes = None if habilitacoes_cnes is None else habilitacoes_cnes
        cids_validos = None if cids_validos is None else cids_validos
        regras_condicionadas = regras_condicionadas if regras_condicionadas is not None else {}
    if historico_apacs is None and usar_remessa:
        historico_apacs = apac_mag_remessa.apacs_exportadas(pasta_remessas)
    # Com cids_validos definido (injetado ou derivado), a restricao de sexo
    # tambem precisa dos registros: carrega 1x aqui, nunca dentro do loop.
    if cids_registros is None and cids_validos is not None:
        cids_registros = bases.carregar_tabela("S_CID", sigtap_competencia=sigtap_competencia)

    cids_restricoes = _indice_restricoes_sexos(cids_registros)

    ctx: Dict[str, Any] = {
        "base_ceps": base_ceps,
        "catalogo_pa": catalogo_pa,
        "pares_secundarios": pares_secundarios,
        "habilitacoes_exigidas": habilitacoes_exigidas,
        "habilitacoes_cnes": habilitacoes_cnes,
        "cids_validos": cids_validos,
        "cids_registros": cids_registros,
        "cids_restricoes": cids_restricoes,
        "regras_condicionadas": regras_condicionadas or {},
        "historico_apacs": historico_apacs,
    }

    for row in linhas:
        cmpt = _competencia(row)
        ctx["_cmpt"] = cmpt  # calculada 1x por linha (o _validar_linha reutiliza)
        if competencia_ref and cmpt and cmpt != competencia_ref and cmpt not in competencias_divergentes:
            competencias_divergentes.add(cmpt)
            num_linha = only_digits(resolve_row_value(row, "Numero_Apac"), "")
            coletor.adicionar(competencia_ref, num_linha, "ERR", "CORPO", "000005",
                              f"COMPETENCIA ({cmpt}) DIFERENTE DA COMPETENCIA ({competencia_ref}) DO ARQUIVO")
        _validar_linha(row, coletor, ctx)

    if not competencia_ref:
        coletor.adicionar("", "", "ERR", "CORPO", "000005",
                          "COMPETENCIA (VAZIA) INVALIDA PARA EXPORTACAO")

    return ResultadoValidacao(
        coletor.itens,
        _regras_desativadas(ctx, usar_sigtap and bool(competencia_ref)),
    )
