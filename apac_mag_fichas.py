"""Fichas do paciente em PDF — layout idêntico ao arquivo modelo.

A ficha é renderizada a partir do PRÓPRIO arquivo modelo
(``dados/modelo_ficha_oci_oftalmologia.xlsx``, aba ``OCI OFTALMOLOGIA``):
as mesmas linhas, mesclagens, larguras, alturas, bordas, fontes, cores,
cabeçalho e rodapé de impressão do Excel. Cada linha da planilha vira uma
ficha com os valores daquela linha preenchidos nas células do formulário e
os checklists (procedimentos, CIDs, motivo de saída) marcados com o que a
linha informa. Colunas da linha que não têm campo no formulário vão para a
página final "OUTROS DADOS DA LINHA", para nada da linha se perder.

Camadas (testável sem PDF):

* :func:`montar_ficha` — puro: ``row -> sobrescritas de célula + extras``;
* :func:`gerar_ficha_pdf` — renderiza o template com as sobrescritas;
* :func:`exportar_fichas` — varre o DataFrame e gera um PDF por linha.

Depende de ``openpyxl`` (leitura da planilha) e ``reportlab`` (PDF). Sem o
reportlab o módulo segue importável e a geração falha com mensagem clara — o
resto do programa (TXT) nunca é afetado.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from openpyxl.utils import column_index_from_string, get_column_letter

try:  # pragma: no cover - degradação graciosa quando reportlab ausente
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas as _canvas

    _REPORTLAB = True
except Exception:  # pragma: no cover
    _REPORTLAB = False

# ---------------------------------------------------------------------------
# Arquivo modelo
# ---------------------------------------------------------------------------
_NOME_TEMPLATE = "modelo_ficha_oci_oftalmologia.xlsx"
_FOLHA = "OCI OFTALMOLOGIA"
_PREFIXO_ORIGINAL = "MODELO_FATURAMENTO_OCI"
_QUEBRA_PAGINA = 69          # quebra do modelo (1..68 / 69..); a ficha usa 1 página
_NC = 29                     # colunas A..AC (intervalo usado da aba)
_CID_COL_DIR = 13            # coluna M: início do bloco direito da tabela de CIDs
_CONSULTAS_INI = 50          # título/nota da lista de consultas do encerramento
_CONSULTAS_FIM = 58

# Calibração da geometria contra a impressão do próprio modelo pelo Excel
# (medida por regressão sobre a impressão: resíduo < 0,4 pt nas colunas e
# ~1,5 pt nas linhas). Sem isso a ficha sai com colunas ~8% mais largas e
# linhas ~3% mais altas que o modelo impresso.
_TITULOS_SECAO = (
    "DADOS DO PACIENTE",
    "DADOS DO SOLICITANTE",
    "EMISSOR DA OCI",
    "PROCEDIMENTOS",
    "DIAGNOSE EM OFTALMOLOGIA",
    "ENCERRAMENTO DA APAC",
    "MÉDICO AUTORIZADOR DA APAC",
)

_PT_PX_COLUNA = 0.798        # pt por "pixel" de largura de coluna
_PAD_COLUNA = 0.234          # pt fixos por coluna
_FATOR_ALTURA = 0.968        # fator aplicado às alturas de linha

# Células com dados do paciente de exemplo — em branco quando o arquivo
# original (com fórmulas/amostra) é usado como fallback.
_CELULAS_DADOS = (
    "I2", "J3", "U3", "C5", "C9", "K9", "S9", "G10", "C12", "D12", "K12",
    "U12", "V12", "F13", "C15", "J15", "K15", "L15", "X15", "F16", "J16",
    "U16", "C21", "K21", "K22", "J23", "Q23", "H24", "G29", "V29", "F30",
    "N30", "N35", "T35", "R52", "R53", "J59", "W59", "F60", "V60", "I70",
    "J71", "U71", "C73", "I110", "H111",
)

# Tabelas de referência da aba REFEENCIAS do próprio modelo
_SEXOS = {"M": "MASCULINO", "F": "FEMININO"}
_RACAS = {
    "1": "BRANCO", "01": "BRANCO",
    "2": "PRETO", "02": "PRETO",
    "3": "PARDO", "03": "PARDO",
    "4": "INDIGENA", "04": "INDIGENA",
    "5": "AMARELO", "05": "AMARELO",
    "99": "SEM INFORMACAO",
}
_TIPOS_LOGRADOURO = {"8": "AV.", "81": "RUA", "31": "EST."}

# Células do modelo que carregam texto institucional (com acentos) — usadas
# como fallback quando o template slim (dados limpos) não tem o valor.
_CELULAS_COM_TEXTO_ORIGINAL = (
    "I2", "U3", "C5", "K21",
)

# Cores/medidas de impressão (espelham o modelo; ui/theme.py é o espelho da UI)
_GRADE_COR = "#D9D9D9"           # linhas de grade (como no Excel)
_GRADE_ESP = 0.55
_BORDA_ESP = {"thin": 0.6, "medium": 1.25, "hair": 0.35, "double": 1.25,
              "thick": 1.6, "dashed": 0.6, "mediumDashed": 1.25}
_INSET = 1.5                     # folga do texto dentro da célula (2 px do Excel)
# Índice de tema do arquivo -> posição no clrScheme do tema. Este modelo (como
# os arquivos escritos pelo Excel) usa a paleta da interface: 0 = fundo 1
# (lt1/branco), 1 = texto 1 (dk1/preto), 2 = fundo 2 (lt2), 3 = texto 2 (dk2)
# e 4..9 = accent1..6. Com 0 = branco as barras de seção saem corretas (o
# modelo usa fundo branco + borda grossa preta, não barra preta).
_TEMA_MAPA = (1, 0, 3, 2, 4, 5, 6, 7, 8, 9, 10, 11)


# ---------------------------------------------------------------------------
# Texto e formatação de valores da linha
# ---------------------------------------------------------------------------

def _texto(valor: Any) -> str:
    """Valor de célula/planilha -> string limpa."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    try:
        if valor != valor:  # NaN
            return ""
    except Exception:
        pass
    return str(valor).strip()


def formatar_procedimento(codigo: Any) -> str:
    """``0905010035`` -> ``09.05.01.003-5`` / 9 dígitos -> ``09.05.01.003``."""
    bruto = _texto(codigo)
    d = re.sub(r"\D", "", bruto)
    if len(d) == 10:
        return f"{d[0:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}-{d[9]}"
    if len(d) == 9:
        return f"{d[0:2]}.{d[2:4]}.{d[4:6]}.{d[6:9]}"
    return bruto


def _formatar_data(valor: Any) -> str:
    """Qualquer entrada de data conhecida -> ``d/m/aaaa`` (sem zero-padding,
    igual ao modelo Excel da ficha)."""
    s = _texto(valor)
    if not s:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$", s)
    if m:
        return f"{int(m.group(3))}/{int(m.group(2))}/{m.group(1)}"
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        return f"{int(m.group(1))}/{int(m.group(2))}/{m.group(3)}"
    if re.match(r"^\d{8}$", s):
        if 1900 <= int(s[:4]) <= 2100:      # AAAAMMDD (canônico do APAC)
            return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
        if 1900 <= int(s[4:]) <= 2100:      # DDMMAAAA (Excel)
            return f"{s[:2]}/{s[2:4]}/{s[4:]}"
    return s


def _formatar_cpf(valor: Any) -> str:
    d = re.sub(r"\D", "", _texto(valor))
    if len(d) == 11:
        return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"
    return _texto(valor)


def _formatar_competencia(valor: Any) -> str:
    s = _texto(valor)
    return f"{s[:4]}/{s[4:]}" if re.match(r"^\d{6}$", s) else s


def _formatar_cep(valor: Any) -> str:
    """CEP: 8 dígitos -> ``NNNNN-NNN`` (formato do formulário)."""
    digitos = re.sub(r"\D", "", _texto(valor))
    return (f"{digitos[:5]}-{digitos[5:]}" if len(digitos) == 8
            else _texto(valor))


def _formatar(coluna: str, valor: Any) -> str:
    v = _texto(valor)
    if not v:
        return ""
    if coluna.startswith("Data") or coluna in ("Inicio_Validade", "Fim_Validade"):
        return _formatar_data(v)
    if coluna.endswith("Cod_Procedimento"):
        return formatar_procedimento(v)
    if coluna in ("Cpf_Paciente", "Medico_Cpf", "Autorizador_Cpf"):
        return _formatar_cpf(v)
    if coluna == "Competencia":
        return _formatar_competencia(v)
    if coluna == "Cep":
        return _formatar_cep(v)
    return v


def _rotulo_coluna(coluna: str) -> str:
    """``Cid_Causas_Assoc`` -> ``CID CAUSAS ASSOC`` (página de extras)."""
    return re.sub(r"_+", " ", str(coluna)).strip().upper()


# ---------------------------------------------------------------------------
# Descrição do procedimento (S_PA, opcional)
# ---------------------------------------------------------------------------

_CACHE_PROC: Optional[Dict[str, str]] = None


def _desc_procedimentos() -> Dict[str, str]:
    """``{9 dígitos: descrição}`` do S_PED; {} quando a base não existe."""
    global _CACHE_PROC
    if _CACHE_PROC is not None:
        return _CACHE_PROC
    desc: Dict[str, str] = {}
    try:
        import apac_mag_bases

        for r in apac_mag_bases.carregar_tabela("S_PA") or []:
            pid = _texto(r.get("PA_ID"))
            if pid and pid not in desc:
                desc[pid] = _texto(r.get("PA_DC"))
    except Exception:
        pass
    _CACHE_PROC = desc
    return desc


def _procedimento_completo(display: str, modelo_proc: Optional[str] = None) -> str:
    """``09.05.01.003-5`` -> ``09.05.01.003-5 - OCI AVALIAÇÃO ...``.

    Prefere a descrição do próprio modelo (com acentos corretos) quando o
    código conhece a descrição do template; caso contrário usa a base S_PA
    (que pode vir sem acento).
    """
    if not display:
        return ""
    d = re.sub(r"\D", "", display)
    if modelo_proc and len(d) >= 9:
        try:
            pat = (rf"\b{d[:2]}\.{d[2:4]}\.{d[4:6]}\.{d[6:9]}"
                   rf"(?:-[A-Za-z0-9])?")
            m = re.search(pat, modelo_proc)
            if m:
                return modelo_proc
        except re.error:
            pass
    desc = _desc_procedimentos().get(d[:9], "") if len(d) >= 9 else ""
    return f"{display} - {desc}" if desc else display


def _nome_estabelecimento() -> str:
    """Nome do estabelecimento do penna_config.json (header.orgao_responsavel)."""
    try:
        from apac_mag.config import get_header

        return _texto((get_header() or {}).get("orgao_responsavel", ""))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Carregamento do template (uma vez por sessão)
# ---------------------------------------------------------------------------

def _bases_template() -> List[Path]:
    """Ordem de busca do modelo da ficha.

    No modo EXE (frozen) o local **ao lado do .exe** vem primeiro — mesmo
    padrão do ``penna_config.json``: é onde o cliente pode deixar/editar o
    modelo sem um novo build. Depois o bundle (``_MEIPASS``, onde o PyInstaller
    embute ``dados/modelo_ficha...xlsx``), o diretório do módulo e o CWD.
    """
    prefixos = [Path(sys._MEIPASS)] if getattr(sys, "_MEIPASS", None) else []
    aqui = Path(__file__).resolve().parent
    ao_lado = (
        [Path(sys.executable).resolve().parent]
        if getattr(sys, "frozen", False)
        else []
    )
    return [*ao_lado, *prefixos, aqui, Path.cwd()]


def _achar_template() -> Path:
    candidatos: List[Path] = []
    bases = _bases_template()
    for base in bases:
        candidatos.append(base / "dados" / _NOME_TEMPLATE)
    for base in bases:
        if getattr(sys, "_MEIPASS", None) and base == Path(sys._MEIPASS):
            continue
        candidatos.extend(sorted(base.glob(f"{_PREFIXO_ORIGINAL}*.xlsx")))
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    raise FileNotFoundError(
        f"arquivo modelo da ficha não encontrado (dados/{_NOME_TEMPLATE})"
    )


def _achar_template_original() -> Optional[Path]:
    """Caminho do modelo completo (com amostra/acentos) para fallback de textos."""
    for base in _bases_template():
        for cand in list(base.glob(f"{_PREFIXO_ORIGINAL}*.xlsx")) + list(base.glob("*oftalmologia*.xlsx")):
            if cand.name != _NOME_TEMPLATE and cand.exists():
                return cand
    return None


class _Modelo:
    """Layout da aba OCI OFTALMOLOGIA: geometria, estilos e listas do formulário."""

    def __init__(self, caminho: Path) -> None:
        import openpyxl as _xl

        self.caminho = caminho
        self._slim = caminho.name == _NOME_TEMPLATE
        wb = _xl.load_workbook(caminho, data_only=True)
        if _FOLHA not in wb.sheetnames:
            raise ValueError(f"aba {_FOLHA!r} ausente em {caminho.name}")
        ws = wb[_FOLHA]
        self.ws = ws
        self._tema = self._ler_tema(wb)
        # válvula de escape: se template slim (dados limpos), tenta ler os
        # valores originais (com acentos) a partir do arquivo modelo completo
        self._valores_originais: dict = {}
        if self._slim:
            self._carregar_valores_originais()

        # --- geometria -----------------------------------------------------
        padrao = ws.sheet_format.defaultColWidth or 8.43
        self.larguras: List[float] = []          # pt, por coluna (1-based via índice)
        for i in range(1, _NC + 1):
            letra = get_column_letter(i)
            dim = ws.column_dimensions.get(letra)
            larg = dim.width if dim is not None and dim.width else padrao
            escondida = bool(dim is not None and dim.hidden)
            self.larguras.append(
                0.0 if escondida
                else round(larg * 7) * _PT_PX_COLUNA + _PAD_COLUNA)
        self.xs: List[float] = [0.0]
        for larg in self.larguras:
            self.xs.append(self.xs[-1] + larg)

        padrao_alt = ws.sheet_format.defaultRowHeight or 15.0
        self.alturas: List[float] = []           # pt, linha i (1-based)
        for i in range(1, (ws.max_row or 1) + 1):
            dim = ws.row_dimensions.get(i)
            if dim is not None and dim.hidden:
                self.alturas.append(0.0)
            else:
                self.alturas.append(
                    (dim.height if dim is not None and dim.height
                     else padrao_alt) * _FATOR_ALTURA)
        self.linhas_total = len(self.alturas)
        self.ys: List[float] = [0.0]
        for alt in self.alturas:
            self.ys.append(self.ys[-1] + alt)

        # --- margens/folha (papel A4, retrato) -----------------------------
        self.margem_esq = ws.page_margins.left * 72
        self.margem_dir = ws.page_margins.right * 72
        self.margem_topo = ws.page_margins.top * 72
        self.margem_base = ws.page_margins.bottom * 72
        self.alt_cabecalho = (ws.page_margins.header or 0) * 72
        self.alt_rodape = (ws.page_margins.footer or 0) * 72
        self.pagina = A4                          # paperSize 9 = A4 retrato
        self.cabecalho_centro = (ws.oddHeader.center.text or "")
        self.rodape_direita = (ws.oddFooter.right.text or "")

        # --- mesclagens ----------------------------------------------------
        self.merges: Dict[Tuple[int, int], Tuple[int, int, int, int]] = {}
        for faixa in ws.merged_cells.ranges:
            for r in range(faixa.min_row, faixa.max_row + 1):
                for c in range(faixa.min_col, faixa.max_col + 1):
                    self.merges[(r, c)] = (faixa.min_row, faixa.min_col,
                                           faixa.max_row, faixa.max_col)

        # --- células com valor ou estilo -----------------------------------
        self.celulas: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for row in ws.iter_rows(min_row=1, max_row=self.linhas_total,
                                min_col=1, max_col=_NC):
            for cel in row:
                info = self._ler_celula(cel)
                if info is not None:
                    self.celulas[(cel.row, cel.column)] = info
        if not self._slim:
            self._esvaziar_dados_da_amostra()

        # --- intervalo realmente impresso ("usado") ---------------------------
        # O Excel imprime só até a última coluna com conteúdo/estilo; desenhar
        # a grade além disso criava colunas vazias saindo da página.
        usadas = {coluna for (_, coluna), info in self.celulas.items()
                  if info.get("valor") or info.get("fill") or info.get("bordas")}
        usadas |= {faixa[3] for faixa in self.merges.values()}
        self.n_colunas = max(1, min(_NC, max(usadas) if usadas else _NC))

        # --- formatos condicionais (realces do modelo) ------------------------
        self.condicionais: List[Tuple[int, int, int, int, str, str]] = []
        self._carregar_formatos_condicionais()

        # --- blocos do formulário (título -> linhas) --------------------------
        self.secoes: List[Tuple[str, int, int]] = self._calcular_secoes()

        # --- escala de impressão (cabe em A4) ------------------------------
        # Escala máxima 1.0 (idêntica ao Excel impresso); cada ficha calcula a
        # sua escala efetiva para caber em uma página — ver _escala_da_ficha.
        self.escala = 1.0
        self.paginas: List[Tuple[int, int]] = self._calcular_paginas()

        # --- listas do formulário (checklists) -----------------------------
        self.proc_linhas: List[Tuple[int, str]] = []    # (linha, código9)
        for r in range(36, 46):
            cod = self._codigo(self.valor(r, 4))
            if cod:
                self.proc_linhas.append((r, cod))
        self.geral_linhas: List[Tuple[int, str]] = []   # (linha, código9)
        for r in (52, 53):
            cod = self._codigo(self.valor(r, 2))
            if cod:
                self.geral_linhas.append((r, cod))
        self.cid_esq: List[Tuple[int, str]] = []
        self.cid_dir: List[Tuple[int, str]] = []
        for r in range(75, 104):
            cod = self.valor(r, 3).upper()
            if re.match(r"^[A-Z]\d{2,3}$", cod):
                self.cid_esq.append((r, cod))
            cod = self.valor(r, 14).upper()
            if re.match(r"^[A-Z]\d{2,3}$", cod):
                self.cid_dir.append((r, cod))

    # ------------------------------------------------------------------
    @staticmethod
    def _ler_tema(wb) -> Dict[int, str]:
        bruto = wb.loaded_theme or b""
        if isinstance(bruto, bytes):
            bruto = bruto.decode("utf-8", "replace")
        cores: List[str] = []
        m = re.search(r"<a:clrScheme.*?</a:clrScheme>", bruto, re.S)
        if m:
            for filho in re.finditer(
                    r"<a:(dk1|lt1|dk2|lt2|accent[1-6]|hlink|folHlink)>"
                    r".*?(?:lastClr|val)=\"([0-9A-Fa-f]{6})\"", m.group(0), re.S):
                cores.append(filho.group(2).upper())
        return {_TEMA_MAPA[i]: cores[i] for i in range(min(len(cores),
                                                           len(_TEMA_MAPA)))}

    @staticmethod
    def _codigo(texto: str) -> str:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})\.(\d{3})-(\d)", texto or "")
        return "".join(m.groups())[:9] if m else ""

    def _ler_celula(self, cel) -> Optional[Dict[str, Any]]:
        tem_valor = cel.value is not None
        borda = cel.border
        lados = {s: getattr(borda, s) for s in ("left", "right", "top", "bottom")}
        tem_borda = any(l.style for l in lados.values())
        fill = cel.fill
        tem_fill = bool(fill.patternType)
        if not (tem_valor or tem_borda or tem_fill):
            return None
        info: Dict[str, Any] = {
            "valor": "" if not tem_valor else self._str_valor(cel.value),
            "fonte": (cel.font.name or "Calibri", float(cel.font.sz or 11),
                      bool(cel.font.b), bool(cel.font.i)),
            "cor_fonte": self._cor(cel.font.color) or "#000000",
            "al": (cel.alignment.horizontal, cel.alignment.vertical,
                   bool(cel.alignment.wrap_text)),
            "fill": self._cor(fill.fgColor) if tem_fill else None,
            "bordas": {},
        }
        for lado, obj in lados.items():
            if obj.style:
                info["bordas"][lado] = (obj.style, self._cor(obj.color) or "#000000")
        if not tem_valor and not info["bordas"] and not info["fill"]:
            return None
        return info

    @staticmethod
    def _str_valor(valor: Any) -> str:
        import datetime

        if isinstance(valor, (datetime.datetime, datetime.date)):
            return _formatar_data(valor.strftime("%Y%m%d"))
        return _texto(valor)

    def _cor(self, color) -> Optional[str]:
        if color is None or color.type is None:
            return None
        try:
            if color.type == "rgb" and isinstance(color.value, str):
                return "#" + color.value[-6:].upper()
            if color.type == "theme":
                hexa = self._tema.get(int(color.value))
                if not hexa:
                    return None
                t = float(color.tint or 0)
                return _aplicar_tint("#" + hexa, t)
            if color.type == "indexed":
                idx = int(color.value)
                if idx in (64, 65):  # automático → preto
                    return "#000000"
                # índices fora da tabela padrão (Palavra ≠ Excel 2016) —
                # retornam None
                if idx <= 0 or idx > 56:
                    return None
            return None
        except Exception:
            return None

    def _carregar_valores_originais(self) -> None:
        """Lê os valores com acentos do arquivo modelo completo (fallback).

        O template slim em ``dados/`` tem as células de amostra em branco.
        Para procedimentos e textos institucionais, usa o original completo
        como fonte dos textos com acentuação correta.
        """
        origem = _achar_template_original()
        if not origem or origem == self.caminho:
            return
        try:
            import openpyxl as _xl2
            wb = _xl2.load_workbook(origem, data_only=True)
            if _FOLHA not in wb.sheetnames:
                return
            ws = wb[_FOLHA]
            # C5: descrição da OCI principal (também estampa as células C36..C45
            # que no modelo repercutem o mesmo texto; usa-se para gerar o texto
            # completo com acentos quando o template slim está limpo)
            c5 = ws["C5"].value
            if c5:
                self._valores_originais["C5"] = str(c5)
            # DDI dos procedimentos secundários (D36..D45) usados pelo modelo
            for r in range(36, 46):
                cel = ws.cell(r, 4)
                if cel.value:
                    self._valores_originais[f"D{r}"] = str(cel.value)
            # C36..C45: texto completo da linha (com acento) quando o slim não
            # tem a coluna C preenchida (no modelo slim a coluna C é vazia)
            for r in range(36, 46):
                cel = ws.cell(r, 3)
                if cel.value:
                    self._valores_originais[f"C{r}"] = str(cel.value)
        except Exception:
            pass

    def valor(self, linha: int, coluna: int) -> str:
        cel = self.celulas.get((linha, coluna))
        v = cel["valor"] if cel else ""
        if not v:
            ref = f"{get_column_letter(coluna)}{linha}"
            v = self._valores_originais.get(ref, "")
        return v

    def _esvaziar_dados_da_amostra(self) -> None:
        for ref in _CELULAS_DADOS:
            cel = self.ws[ref]
            info = self.celulas.get((cel.row, cel.column))
            if info is not None:
                info["valor"] = ""
        for r in range(36, 46):
            info = self.celulas.get((r, 2))
            if info is not None:
                info["valor"] = "(       )"

    def _cor_dxf(self, fill) -> Optional[str]:
        """Cor do preenchimento de uma regra de formato condicional.

        Nos ``dxf`` o Excel grava a cor de fundo em ``bgColor``.
        """
        if fill is None:
            return None
        for cor in (fill.bgColor, fill.fgColor):
            if cor is not None and cor.type in ("rgb", "theme", "indexed"):
                valor = self._cor(cor)
                if valor and valor != "#000000":
                    return valor
        return None

    def _carregar_formatos_condicionais(self) -> None:
        """Regras de texto (``contém``) do modelo -> realce de preenchimento.

        O modelo imprime alguns realces ("Não aplica nessa OCI", "NNNNNN",
        "(NNN)") que não são preenchimento fixo: vêm de formatos
        condicionais. Ler as regras mantém a ficha igual à planilha.
        """
        for area_regra in self.ws.conditional_formatting:
            for regra in area_regra.rules:
                if regra.type != "containsText" or regra.dxf is None:
                    continue
                cor = self._cor_dxf(regra.dxf.fill)
                if not cor:
                    continue
                procurado = ""
                for termo in (regra.formula or []):
                    m = re.search(r'SEARCH\("([^"]*)"', str(termo))
                    if m:
                        procurado = _texto(m.group(1))
                        break
                if not procurado:
                    continue
                for area in area_regra.sqref.ranges:
                    self.condicionais.append((area.min_row, area.min_col,
                                              area.max_row, area.max_col,
                                              procurado.upper(), cor))

    def realce_condicional(self, linha: int, coluna: int,
                           texto: str) -> Optional[str]:
        """Cor de realce para o texto da célula, se alguma regra casar."""
        if not texto or not self.condicionais:
            return None
        alvo = str(texto).upper()
        for r1, c1, r2, c2, procurado, cor in self.condicionais:
            if r1 <= linha <= r2 and c1 <= coluna <= c2 \
                    and procurado in alvo:
                return cor
        return None

    def _calcular_secoes(self) -> List[Tuple[str, int, int]]:
        """Blocos do formulário: ``(título, primeira linha, última linha)``.

        Os títulos vêm do próprio modelo (colunas A..C).
        """
        marcas: List[Tuple[int, str]] = []
        for linha in range(1, self.linhas_total + 1):
            for coluna in range(1, 4):
                info = self.celulas.get((linha, coluna))
                if not info:
                    continue
                texto = (info.get("valor") or "").strip()
                if not texto:
                    continue
                if any(texto.upper().startswith(t)
                       for t in _TITULOS_SECAO) and not any(
                           texto.startswith(t) for _, t in marcas):
                    marcas.append((linha, texto))
                    break
        secoes: List[Tuple[str, int, int]] = []
        for i, (linha, titulo) in enumerate(marcas):
            fim = marcas[i + 1][0] - 1 if i + 1 < len(marcas) else self.linhas_total
            secoes.append((titulo, linha, fim))
        return secoes

    def _calcular_paginas(self) -> List[Tuple[int, int]]:
        """A ficha sai em UMA página: em vez de partir o formulário na linha
        da quebra do modelo, o desenho reduz a escala até tudo caber em A4."""
        return [(1, self.linhas_total)]

    def altura_visivel(self, ocultar: Set[int] = frozenset()) -> float:
        """Altura (unidades do modelo) das linhas que realmente saem na ficha."""
        return sum(alt for i, alt in enumerate(self.alturas, start=1)
                   if alt > 0 and i not in ocultar)

    # ------------------------------------------------------------------
    def valor(self, linha: int, coluna: int) -> str:
        cel = self.celulas.get((linha, coluna))
        return cel["valor"] if cel else ""

    def ancre(self, linha: int, coluna: int) -> Tuple[int, int]:
        """Célula âncora da mesclagem que contém (linha, coluna)."""
        faixa = self.merges.get((linha, coluna))
        return (faixa[0], faixa[1]) if faixa else (linha, coluna)

    def largura_total(self) -> float:
        return self.xs[-1]

    def colunas_para(self, sobrescritas: Dict[str, str]) -> int:
        """Maior coluna a desenhar: a usada no template + as sobrescritas."""
        ultima = self.n_colunas
        for ref in sobrescritas:
            m = re.match(r"^([A-Z]{1,2})\d+$", ref)
            if m:
                ultima = max(ultima, column_index_from_string(m.group(1)))
        return min(ultima, _NC)

    def altura_intervalo(self, r1: int, r2: int) -> float:
        r1 = max(1, r1)
        r2 = min(self.linhas_total, r2)
        return self.ys[r2] - self.ys[r1 - 1]


_MODELO: Optional[_Modelo] = None


def carregar_modelo() -> _Modelo:
    """Carrega (e memoriza) o layout da ficha do arquivo modelo."""
    global _MODELO
    if _MODELO is None:
        _MODELO = _Modelo(_achar_template())
    return _MODELO


def _aplicar_tint(hexa: str, t: float) -> str:
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    if t >= 0:
        r, g, b = (int(v + (255 - v) * t) for v in (r, g, b))
    else:
        r, g, b = (int(v * (1 + t)) for v in (r, g, b))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


# ---------------------------------------------------------------------------
# Montagem da ficha (puro: linha -> sobrescritas de célula + extras)
# ---------------------------------------------------------------------------

def _caixa(texto: str, marcado: bool) -> str:
    """Marca o primeiro ``(      )`` do texto com um X, preservando o tamanho."""
    if not marcado:
        return texto
    m = re.search(r"\(\s*\)", texto)
    if not m:
        return texto
    interno = m.end() - m.start() - 2
    meio = max(int(interno / 2), 0)
    dentro = " " * meio + "X" + " " * max(interno - meio - 1, 0)
    return texto[:m.start()] + "(" + dentro + ")" + texto[m.end():]


def _caixa_do_codigo(texto: str, codigo: str) -> str:
    """Marca o checkbox que antecede ``codigo`` (ex.: motivo de saída 11)."""
    if not codigo or not texto:
        return texto
    m = re.search(r"\(\s*\)(\s*)" + re.escape(codigo) + r"(?!\d)", texto)
    if not m:
        return texto
    inicio = m.start()
    meio_txt = texto[inicio:m.end()]
    novo = _caixa(meio_txt, True)
    return texto[:inicio] + novo + texto[m.end():]


def _rotulo_celula(modelo: _Modelo, linha: int, coluna: int) -> str:
    """Texto do rótulo do campo (célula à esquerda ou acima, terminada em ':')."""
    for c in range(coluna - 1, 0, -1):
        info = modelo.celulas.get(modelo.ancre(linha, c))
        if not info:
            continue
        texto = (info.get("valor") or "").strip()
        if texto:
            return texto if texto.endswith(":") else ""
    for l in range(linha - 1, max(linha - 4, 0), -1):
        info = modelo.celulas.get(modelo.ancre(l, coluna))
        if not info:
            continue
        texto = (info.get("valor") or "").strip()
        if texto:
            return texto if texto.endswith(":") else ""
    return ""


def _montar_blocos(modelo: _Modelo, sobre: Dict[str, str],
                   adicionais: Optional[Dict[str, Sequence[Tuple[str, str, str]]]] = None,
                   ) -> List[Dict[str, Any]]:
    """Inventário do que cada seção do formulário imprime: ``(rótulo, valor)``.

    Percorre as seções do modelo na ordem em que aparecem, usando o valor da
    célula (sobrescrito pela linha do paciente, quando houver) e o rótulo que a
    antecede no próprio formulário. Assim os blocos refletem a ficha impressa,
    incluindo as listas fixas do modelo (procedimentos, CIDs, motivo de saída).
    """
    blocos: List[Dict[str, Any]] = []
    for titulo, r1, r2 in modelo.secoes:
        itens: List[Tuple[str, str, str]] = []
        for linha in range(r1, r2 + 1):
            for coluna in range(1, modelo.n_colunas + 1):
                info = modelo.celulas.get((linha, coluna))
                if info is None:
                    continue
                faixa = modelo.merges.get((linha, coluna))
                if faixa and (faixa[0], faixa[1]) != (linha, coluna):
                    continue                    # só a âncora da mesclagem
                ref = f"{get_column_letter(coluna)}{linha}"
                valor = str(sobre.get(ref, info["valor"]) or "").strip()
                if not valor or not any(ch.isalnum() for ch in valor):
                    continue
                if valor.endswith(":") and ref not in sobre:
                    continue                    # rótulo do próprio formulário
                itens.append((_rotulo_celula(modelo, linha, coluna) or ref,
                              valor, "texto"))
        itens.extend((adicionais or {}).get(titulo, ()))
        if itens:
            blocos.append({"titulo": titulo, "itens": itens})
    return blocos


def _linhas_em_branco(modelo: _Modelo, sobre: Dict[str, str],
                      ocultar: Set[int]) -> Set[int]:
    """Linhas do formulário sem nenhuma tinta: sem texto, sem borda e sem
    fundo colorido (e fora de mesclagem, que liga a linha às vizinhas).

    Apagá-las não muda um traço do desenho — só devolve o espaço em branco
    que elas ocupavam, que é o que faz a ficha caber em uma página.
    """
    brancas: Set[int] = set()
    for linha in range(1, modelo.linhas_total + 1):
        if modelo.alturas[linha - 1] <= 0 or linha in ocultar:
            continue
        if any(modelo.merges.get((linha, c))
               for c in range(1, modelo.n_colunas + 1)):
            continue
        tem_tinta = False
        for coluna in range(1, modelo.n_colunas + 1):
            info = modelo.celulas.get((linha, coluna))
            if not info:
                continue
            ref = f"{get_column_letter(coluna)}{linha}"
            texto = sobre.get(ref, info["valor"])
            fundo = str(info.get("fill") or "").lstrip("#").upper()
            if (texto and str(texto).strip()) or info["bordas"] \
                    or (fundo and fundo != "FFFFFF"):
                tem_tinta = True
                break
        if not tem_tinta:
            brancas.add(linha)
    return brancas


def montar_ficha(row: Any) -> Dict[str, Any]:
    """Converte a linha da planilha no preenchimento da ficha do modelo.

    Retorna:

    * ``sobrescritas`` — ``{coordenada: texto}`` aplicado sobre o template
      (células de dados marcadas nos checklists inclusive);
    * ``cobertos`` — colunas da linha refletidas na ficha;
    * ``extras`` — colunas restantes (página final "OUTROS DADOS DA LINHA");
    * ``blocos`` — seções do formulário (``titulo`` + ``itens``
      ``(rótulo, valor, tipo)``) e a página final "OUTROS DADOS DA LINHA".

    Toda a linha é coberta: ``cobertos | {colunas de extras} == row.keys()``.
    """
    modelo = carregar_modelo()
    valores: Dict[str, str] = {}
    try:
        for chave, valor in dict(row).items():
            valores[_texto(chave)] = _texto(valor)
    except Exception:
        pass

    cobertos: Set[str] = set()
    exibidos: Set[str] = set()
    sobre: Dict[str, str] = {}
    # O formulário tem listas fixas (procedimentos, CIDs): imprimir as opções
    # que o paciente não tem só ocupa espaço. ``ocultar`` são as linhas que
    # saem da ficha e ``suprimir`` as células que não devem ser desenhadas
    # (a metade sem marcação de uma linha de CID que fica na ficha).
    ocultar: Set[int] = set()
    suprimir: Set[Tuple[int, int]] = set()

    def definir(coords: Sequence[str], valor: str) -> str:
        texto = _texto(valor)
        for ref in coords:
            sobre[ref] = texto
        if texto:
            exibidos.add(texto)
        return texto

    def pegar(*colunas: str) -> str:
        """Primeiro valor não vazio. Vazio e vencedor entram em ``cobertos``;
        candidatos com valor que NÃO venceu ficam de fora (vão para extras)."""
        vencedor = None
        for coluna in colunas:
            if valores.get(coluna, "") and vencedor is None:
                vencedor = coluna
        for coluna in colunas:
            if coluna == vencedor or not valores.get(coluna, ""):
                cobertos.add(coluna)
        if vencedor:
            return _formatar(vencedor, valores[vencedor])
        return ""    # ----------------------------------------------------------- cabeçalho
    estab = _nome_estabelecimento()
    cnes_exec = pegar("Cnes_Executante")
    definir(("I2", "I70"), f"{cnes_exec} {estab}".strip())
    definir(("J3", "J71"), pegar("Numero_Apac"))
    definir(("U3", "U71"), pegar("Cod_Orgao_Emiss"))
    # OCI: usar a descrição do próprio modelo (com acentos corretos) quando
    # o procedimento da linha conhece a descrição do template; senão, base
    # S_PA (que pode vir sem acento).
    proc_bruto = pegar("Cod_Procedimento")
    # OCI: preferir a descrição do próprio modelo (com acentos corretos);
    # o template slim tem C5 vazio; usamos o original completo como
    # fonte do texto com acentuação correta.
    modelo_proc = modelo._valores_originais.get("C5") or ""
    # fallback: se C5 também não tem, tenta a coluna C da primeira linha de
    # procedimento secundário do modelo original (C36 contém o mesmo texto em
    # alguns modelos) ou o texto da célula D36 (descrição do procedimento)
    if not modelo_proc:
        modelo_proc = modelo._valores_originais.get("C36") or ""
    if not modelo_proc:
        for r in range(36, 46):
            v = modelo._valores_originais.get(f"C{r}") or modelo.valor(r, 4)
            if v:
                modelo_proc = v
                break
    if not modelo_proc:
        modelo_proc = modelo._valores_originais.get("D36") or ""
    definir(("C5", "C73"), _procedimento_completo(proc_bruto, modelo_proc)) 

    # ------------------------------------------------------- dados paciente
    definir(("C9",), pegar("Cns_Paciente"))
    definir(("K9",), pegar("Cpf_Paciente"))
    definir(("S9",), pegar("Telefone"))
    definir(("G10",), pegar("Nome_Paciente"))

    sexo_bruto = valores.get("Sexo", "")
    if sexo_bruto:
        cobertos.add("Sexo")
        definir(("C12",), sexo_bruto[:1].upper())
        definir(("D12",), _SEXOS.get(sexo_bruto[:1].upper(), ""))
    else:
        cobertos.add("Sexo")

    definir(("K12",), pegar("Data_Nascimento"))

    raca_bruta = valores.get("Raca", "")
    cobertos.add("Raca")
    if raca_bruta:
        definir(("U12",), raca_bruta)
        definir(("V12",), _RACAS.get(raca_bruta, ""))

    definir(("F13",), pegar("Nome_Da_Mae"))

    cobertos.add("Cep")
    definir(("C15",), _formatar_cep(valores.get("Cep", "")))

    # logradouro: código da via (J15), tipo (K15) e nome (L15)
    cod_via = (valores.get("Codigo_Logradouro", "")
               or re.sub(r"\D", "", valores.get("Logradouro", "")))
    rua = valores.get("Rua", "")
    if not rua and valores.get("Logradouro", "") and not cod_via:
        rua = valores.get("Logradouro", "")
    cobertos.update(("Codigo_Logradouro", "Logradouro", "Rua"))
    tipo = _TIPOS_LOGRADOURO.get(cod_via, "")
    if not tipo and rua:
        m = re.match(r"^((?:RUA|AV\.?|AVENIDA|EST\.?|ESTRADA|TRAVESSA|ALAMEDA)"
                     r"(?:\s+[A-Z]\.)?)\s+(.*)$", rua, re.I)
        if m:
            tipo = m.group(1).upper()
            rua = m.group(2)
        else:
            tipo = ""
    elif tipo and rua.upper().startswith(tipo.rstrip(".")):
        resto = rua[len(tipo.rstrip(".")):].strip(" .-")
        rua = resto
    definir(("J15",), cod_via if not cod_via.isdigit() or len(cod_via) <= 3
            else cod_via)
    definir(("K15",), tipo)
    definir(("L15",), rua)
    definir(("X15",), pegar("Numero_Endereco"))
    definir(("F16",), pegar("Complemento"))
    definir(("J16",), pegar("Bairro"))
    definir(("U16",), pegar("Nome_Municipio", "Codigo_Municipio", "IBGE"))

    # ---------------------------------------------------- dados solicitante
    definir(("C21",), pegar("Cnes_Solicitante"))
    definir(("K21",), estab)
    definir(("K22",), pegar("Nome_Profissional", "Medico_Nome", "Autorizador_Nome"))
    definir(("J23",), pegar("Medico_Cns", "Autorizador_Cns"))
    cbo = pegar("Cbo")
    definir(("Q23",), cbo)
    definir(("H24",), pegar("Data_Solicitacao"))

    # ------------------------------------------------------ emissor da OCI
    definir(("G29",), pegar("Medico_Nome", "Autorizador_Nome", "Nome_Profissional"))
    definir(("V29",), pegar("Data_Emissao", "Data_Autorizacao"))
    definir(("F30",), pegar("Medico_Cns", "Autorizador_Cns"))
    definir(("N30",), cbo)
    cnes_terceiro = valores.get("Cnes_Terceiro", "")
    cobertos.add("Cnes_Terceiro")
    definir(("N35",), cnes_terceiro or "PROPRIO")
    definir(("T35",), cbo)

    # ------------------------------------------------------- procedimentos
    # código -> quantidade; colunas da linha que o formulário reflete
    entradas: Dict[str, Dict[str, str]] = {}

    def registrar(col_cod: str, col_cbo: str, col_qtd: str) -> None:
        cod = valores.get(col_cod, "")
        cod9 = re.sub(r"\D", "", cod)[:9]
        if not cod9:
            return
        entradas[cod9] = {"qtd": valores.get(col_qtd, ""),
                          "cols": f"{col_cod}|{col_cbo}|{col_qtd}"}

    registrar("Cod_Procedimento", "Cbo", "Quantidade")
    for i in range(1, 9):
        registrar(f"Sec{i}_Cod_Procedimento", f"Sec{i}_Cbo", f"Sec{i}_Quantidade")

    def cobrir_trio(cod9: str) -> str:
        entrada = entradas.get(cod9)
        if not entrada:
            return ""
        for coluna in entrada["cols"].split("|"):
            cobertos.add(coluna)
        return entrada["qtd"]

    for linha, cod9 in modelo.proc_linhas:
        if cod9 not in entradas:
            ocultar.add(linha)      # procedimento que o paciente não fez
            continue
        original = modelo.valor(linha, 2) or "(       )"
        definir((f"B{linha}",), _caixa(original, True))
        qtd = cobrir_trio(cod9)
        if qtd:
            definir((f"W{linha}",), qtd)

    for linha, cod9 in modelo.geral_linhas:
        if cod9 not in entradas:
            ocultar.add(linha)      # consulta/procedimento não realizado
            continue
        original = modelo.valor(linha, 2)
        definir((f"B{linha}",), _caixa(original, True))
        definir((f"R{linha}",), cbo)
        qtd = cobrir_trio(cod9)
        if qtd:
            definir((f"V{linha}",), qtd)

    # Nenhuma consulta da lista feita? Então a seção inteira sai — título e
    # nota de uma lista vazia só ocupariam espaço.
    if modelo.geral_linhas and all(r in ocultar for r, _ in modelo.geral_linhas):
        ocultar.update(range(_CONSULTAS_INI, _CONSULTAS_FIM + 1))

    # Por último, as linhas de puro espaço em branco do próprio formulário
    # (nada é desenhado nelas): também saem, para a ficha caber em 1 página.
    ocultar |= _linhas_em_branco(modelo, sobre, ocultar)

    # ----------------------------------------------------------- diagnósticos
    def codigos_cid(coluna: str) -> List[str]:
        return [c for c in re.split(r"[,;/\s]+", valores.get(coluna, "")) if c]

    cids_marcados: Set[str] = set()
    for coluna in ("Cid_Princ", "Cid_Secun", "Cid_Causas_Assoc"):
        cods = [c.upper() for c in codigos_cid(coluna)]
        if not cods:
            cobertos.add(coluna)
            continue
        if all(c in {c for _, c in modelo.cid_esq} | {c for _, c in modelo.cid_dir}
               for c in cods):
            cids_marcados.update(cods)
            cobertos.add(coluna)
    # A tabela de CIDs é um catálogo do modelo (H00..H59, C69x); a ficha fica
    # só com o(s) CID(s) do paciente — a linha em que ele está marcado. As
    # demais linhas saem, e a metade sem marcação não é desenhada.
    cid_esq = dict(modelo.cid_esq)
    cid_dir = dict(modelo.cid_dir)
    for linha in sorted(set(cid_esq) | set(cid_dir)):
        cod_esq = cid_esq.get(linha, "")
        cod_dir = cid_dir.get(linha, "")
        marcado_esq = bool(cod_esq) and cod_esq in cids_marcados
        marcado_dir = bool(cod_dir) and cod_dir in cids_marcados
        if not (marcado_esq or marcado_dir):
            ocultar.add(linha)
            continue
        if marcado_esq:
            original = modelo.valor(linha, 2) or "(      )"
            definir((f"B{linha}",), _caixa(original, True))
        else:
            suprimir.update((linha, col)
                            for col in range(2, _CID_COL_DIR))
        if marcado_dir:
            original = modelo.valor(linha, 13) or "(      )"
            definir((f"M{linha}",), _caixa(original, True))
        else:
            suprimir.update((linha, col)
                            for col in range(_CID_COL_DIR,
                                             modelo.n_colunas + 1))

    # ---------------------------------------------------------- encerramento
    definir(("J59",), pegar("Medico_Nome", "Autorizador_Nome", "Nome_Profissional"))
    definir(("W59",), cbo)
    definir(("F60",), pegar("Medico_Cns", "Autorizador_Cns"))
    definir(("V60",), pegar("Data_Alta_Obito"))

    motivo = valores.get("Motivo_Saida", "")
    cobertos.add("Motivo_Saida")
    if motivo:
        texto65 = modelo.valor(65, 2)
        texto66 = modelo.valor(66, 2)
        if motivo in {"11", "12", "14", "15"}:
            definir(("B65",), _caixa_do_codigo(texto65, motivo))
        elif motivo == "18":
            definir(("B66",), _caixa_do_codigo(texto66, motivo))
        else:
            cobertos.discard("Motivo_Saida")   # sem campo no formulário

    # -------------------------------------------- assinatura do autorizador
    definir(("I110",), pegar("Autorizador_Cns", "Medico_Cns"))
    definir(("H111",), pegar("Data_Autorizacao"))

    # --------------------------------- colunas cujo valor já está visível
    for coluna, bruto in valores.items():
        if bruto and _formatar(coluna, bruto) in exibidos:
            cobertos.add(coluna)

    # Só vai para a página final o que tem informação e não coube no
    # formulário (coluna vazia não é informação — vazio nem é listado).
    extras_cols = [coluna for coluna in valores
                   if coluna not in cobertos]
    # validade: o formulário não tem o par — se um vai para os extras,
    # os dois vão juntos (nunca fica “fim de validade” órfão na ficha)
    if any(c in extras_cols for c in ("Inicio_Validade", "Fim_Validade")):
        for coluna in ("Inicio_Validade", "Fim_Validade"):
            if coluna not in extras_cols:
                extras_cols.append(coluna)
    extras_cols.sort(key=lambda coluna: list(valores).index(coluna))
    # Coluna vazia não é informação: o que o paciente não tem não é listado
    # (só ocuparia espaço na ficha, que agora tem de caber em uma página).
    extras: List[Tuple[str, str, str]] = []
    for coluna in extras_cols:
        valor = _formatar(coluna, valores.get(coluna, "")).strip()
        if not valor:
            continue
        extras.append((_rotulo_coluna(coluna) + ":", valor, "curto"))

    # sexo/raça: o formulário imprime código e descrição lado a lado
    # ("F" + "FEMININO"); no bloco o par aparece junto, como se lê na ficha.
    pares: List[Tuple[str, str, str]] = []
    for rotulo, ref_a, ref_b in (("SEXO", "C12", "D12"),
                                 ("RAÇA/COR", "U12", "V12")):
        junto = " - ".join(p for p in (sobre.get(ref_a, ""),
                                        sobre.get(ref_b, "")) if p)
        if junto:
            pares.append((rotulo, junto, "texto"))
    blocos: List[Dict[str, Any]] = _montar_blocos(
        modelo, sobre, {"DADOS DO PACIENTE": pares})
    if extras:
        blocos.append({"titulo": "OUTROS DADOS DA LINHA", "itens": extras})
    # Caso especial: linha vazia não deve explodir - mantém blocos
    if not blocos and not valores:
        blocos.append({"titulo": "OUTROS DADOS DA LINHA", "itens": []})

    return {"sobrescritas": sobre, "cobertos": cobertos, "extras": extras,
            "blocos": blocos, "ocultar": ocultar, "suprimir": suprimir}


# ---------------------------------------------------------------------------
# Nomes de arquivo
# ---------------------------------------------------------------------------

_RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
               *(f"LPT{i}" for i in range(1, 10))}


def _seguro(texto: str) -> str:
    texto = re.sub(r'[\\/:*?"<>|]', " ", texto)
    return re.sub(r"\s+", " ", texto).strip(" .")


def nome_arquivo_ficha(row: Any, indice: int, usados: Optional[Set[str]] = None) -> str:
    """Nome seguro ``NomePaciente_NumeroApac.pdf`` (com desempate)."""
    valores = dict(row) if row is not None else {}
    nome = _seguro(_texto(valores.get("Nome_Paciente")))
    apac = re.sub(r"\D", "", _texto(valores.get("Numero_Apac")))
    base = "_".join(parte for parte in (nome, apac) if parte)
    base = base[:80].strip(" ._")
    if not base or base.upper() in _RESERVADOS:
        base = base if base and base.upper() not in _RESERVADOS else f"ficha_{indice:03d}"
    nome_final = f"{base}.pdf"
    if usados is not None:
        tentativa = 2
        while nome_final.lower() in usados:
            nome_final = f"{base}_{tentativa}.pdf"
            tentativa += 1
        usados.add(nome_final.lower())
    return nome_final


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

_FONTES_ARQUIVO = {
    ("Calibri", False, False): "calibri.ttf",
    ("Calibri", True, False): "calibrib.ttf",
    ("Calibri", False, True): "calibrii.ttf",
    ("Calibri", True, True): "calibribi.ttf",
    ("Arial", False, False): "arial.ttf",
    ("Arial", True, False): "arialbd.ttf",
    ("Arial", False, True): "ariali.ttf",
    ("Arial", True, True): "arialbi.ttf",
}
_FONTE_CACHE: Dict[Tuple[str, bool, bool], str] = {}


def _fonte(nome: str, negrito: bool, italico: bool) -> str:
    chave = (nome or "Calibri", bool(negrito), bool(italico))
    if chave in _FONTE_CACHE:
        return _FONTE_CACHE[chave]
    nome_pdf = "Helvetica"
    try:
        arquivo = _FONTES_ARQUIVO.get(chave) or _FONTES_ARQUIVO.get(
            (chave[0], chave[1], False))
        if arquivo:
            caminho = Path("C:/Windows/Fonts") / arquivo
            if caminho.exists():
                alias = f"Penna-{chave[0]}-{int(chave[1])}{int(chave[2])}"
                pdfmetrics.registerFont(__import__(
                    "reportlab.pdfbase.ttfonts", fromlist=["TTFont"]
                ).TTFont(alias, str(caminho)))
                nome_pdf = alias
    except Exception:
        nome_pdf = "Helvetica" if not chave[1] else "Helvetica-Bold"
    _FONTE_CACHE[chave] = nome_pdf
    return nome_pdf


def _preparar_texto(texto: str, nome_pdf: str) -> str:
    texto = texto.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    texto = "".join(ch for ch in texto if ord(ch) >= 32)
    if nome_pdf.startswith("Helvetica"):
        texto = texto.encode("cp1252", errors="replace").decode("cp1252")
    return texto


# ---------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------

def _exigir_reportlab() -> None:
    if not _REPORTLAB:
        raise RuntimeError(
            "biblioteca 'reportlab' não instalada — instale com "
            "'pip install reportlab' para gerar as fichas em PDF."
        )


def _celula_padrao() -> Dict[str, Any]:
    """Estilo padrão para célula alvo de sobrescrita sem estilo no template."""
    return {
        "valor": "",
        "fonte": ("Calibri", 11.0, False, False),
        "cor_fonte": "#000000",
        "al": (None, None, False),
        "fill": None,
        "bordas": {},
    }


def _medir(texto: str, nome_pdf: str, tamanho: float) -> float:
    try:
        return pdfmetrics.stringWidth(texto, nome_pdf, tamanho)
    except Exception:
        return len(texto) * tamanho * 0.5


def _quebrar(texto: str, nome_pdf: str, tamanho: float, largura: float) -> List[str]:
    """Quebra de linha por palavra (como o wrap_text do Excel)."""
    if not texto:
        return [""]
    linhas: List[str] = []
    atual = ""
    for palavra in texto.split(" "):
        tentativa = f"{atual} {palavra}".strip()
        if atual and _medir(tentativa, nome_pdf, tamanho) > largura:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
        while _medir(atual, nome_pdf, tamanho) > largura and len(atual) > 1:
            # palavra única mais larga que a célula: corta
            corte = len(atual)
            while corte > 1 and _medir(atual[:corte], nome_pdf, tamanho) > largura:
                corte -= 1
            linhas.append(atual[:corte])
            atual = atual[corte:]
    if atual or not linhas:
        linhas.append(atual)
    return linhas


def _desenhar_pagina(c, modelo: _Modelo, sobrescritas: Dict[str, str],
                     r1: int, r2: int,
                     ocultar: Set[int] = frozenset(),
                     suprimir: Set[Tuple[int, int]] = frozenset(),
                     escala: Optional[float] = None) -> float:
    """Desenha as linhas ``r1..r2`` do modelo e devolve o ``y`` (unidades do
    modelo) onde o conteúdo terminou — o bloco de extras começa dali.

    ``ocultar`` são linhas que o paciente não usa (listas fixas do
    formulário): elas saem da ficha e as linhas seguintes sobem, encolhendo
    a página. ``suprimir`` são células que não devem ser desenhadas (a
    metade sem marcação de uma linha de CID que fica na ficha). ``escala``
    reduz o formulário até ele caber numa página A4 (ver _escala_da_ficha).
    """
    larg_pag, alt_pag = modelo.pagina
    if escala is None:
        escala = modelo.escala
    xs = modelo.xs
    nc = modelo.colunas_para(sobrescritas)

    c.saveState()
    util_w = larg_pag - modelo.margem_esq - modelo.margem_dir
    desloc = max(util_w - xs[nc] * escala, 0.0) / 2.0
    c.translate(modelo.margem_esq + desloc, 0)
    c.scale(escala, escala)
    topo = (alt_pag - modelo.margem_topo) / escala

    # posições compactadas: linha oculta não ocupa altura, então cada linha
    # visível sobe o que as ocultas acima dela ocupavam.
    visiveis = {r for r in range(r1, r2 + 1)
                if modelo.alturas[r - 1] > 0 and r not in ocultar}
    pos: Dict[int, Tuple[float, float]] = {}
    y_atual = topo
    for linha in range(r1, r2 + 1):
        if linha in visiveis:
            pos[linha] = (y_atual, y_atual - modelo.alturas[linha - 1])
            y_atual = pos[linha][1]
        else:
            pos[linha] = (y_atual, y_atual)

    def y_topo(linha: int) -> float:
        return pos[linha][0]

    def y_base(linha: int) -> float:
        return pos[linha][1]

    def faixa_y(faixa: Tuple[int, int, int, int]):
        """(x0, x1, y1, y0) de uma mesclagem, pulando as linhas ocultas."""
        vis = [r for r in range(max(faixa[0], r1), min(faixa[2], r2) + 1)
               if r in visiveis]
        if not vis:
            return None
        return xs[faixa[1] - 1], xs[faixa[3]], y_topo(vis[0]), y_base(vis[-1])

    # 1) só as bordas das células do modelo (o Excel imprime as bordas, não as
    # linhas de grade da planilha — grade completa "sujava" a ficha)

    # 2/3) fundos e bordas
    padrao = _celula_padrao()
    desenhadas: Set[Tuple[int, int]] = set()
    for linha in range(r1, r2 + 1):
        if linha not in visiveis:
            continue
        for coluna in range(1, nc + 1):
            if (linha, coluna) in suprimir:
                continue
            info = modelo.celulas.get((linha, coluna))
            if info is None and f"{get_column_letter(coluna)}{linha}" in sobrescritas:
                info = padrao      # alvo de sobrescrita sem estilo no template
            faixa = modelo.merges.get((linha, coluna))
            if faixa:
                if (linha, coluna) != (faixa[0], faixa[1]):
                    continue
                caixa = faixa_y(faixa)
                if caixa is None:
                    continue
                x0, x1, y1, y0 = caixa
            else:
                x0, x1 = xs[coluna - 1], xs[coluna]
                y1, y0 = y_topo(linha), y_base(linha)
            if info is None:
                continue
            fundo = info["fill"]
            if modelo.condicionais:
                ref = f"{get_column_letter(coluna)}{linha}"
                realce = modelo.realce_condicional(
                    linha, coluna, sobrescritas.get(ref, info["valor"]))
                if realce:
                    fundo = realce
            if fundo:
                c.setFillColor(HexColor(fundo))
                c.rect(x0, y0, x1 - x0, y1 - y0, stroke=0, fill=1)
            for lado, (estilo, cor) in info["bordas"].items():
                esp = _BORDA_ESP.get(estilo, 0.6)
                c.setStrokeColor(HexColor(cor))
                c.setLineWidth(esp)
                if lado == "left":
                    c.line(x0, y0, x0, y1)
                elif lado == "right":
                    c.line(x1, y0, x1, y1)
                elif lado == "top":
                    c.line(x0, y1, x1, y1)
                else:
                    c.line(x0, y0, x1, y0)
            desenhadas.add((linha, coluna))

    # 4) textos
    for linha in range(r1, r2 + 1):
        if linha not in visiveis:
            continue
        for coluna in range(1, nc + 1):
            if (linha, coluna) not in desenhadas:
                continue
            info = modelo.celulas.get((linha, coluna)) or padrao
            texto = sobrescritas.get(f"{get_column_letter(coluna)}{linha}",
                                     info["valor"])
            if not texto:
                continue
            faixa = modelo.merges.get((linha, coluna))
            if faixa:
                caixa = faixa_y(faixa)
                if caixa is None:
                    continue
                x0, x1, y1, y0 = caixa
            else:
                x0, x1 = xs[coluna - 1], xs[coluna]
                y1, y0 = y_topo(linha), y_base(linha)
            nome, tam, negrito, italico = info["fonte"]
            nome_pdf = _fonte(nome, negrito, italico)
            texto = _preparar_texto(texto, nome_pdf)
            al_h, al_v, wrap = info["al"]
            cor_txt = info["cor_fonte"]
            larg = x1 - x0
            alt = y1 - y0

            # texto transbordando para células vazias à direita (Excel) —
            # vizinha vazia no template E sem valor escrito por cima: o
            # Excel corta o texto na borda da célula que recebeu dado
            # (ex.: rótulo QUANTIDADE: transborda para a caixa da quantidade)
            if not wrap and not faixa:
                fim = coluna + 1
                bloqueada = False
                while fim < nc:
                    if (linha, fim) in modelo.merges:
                        bloqueada = True
                        break
                    vizinha = modelo.celulas.get((linha, fim))
                    if vizinha is not None and vizinha["valor"]:
                        bloqueada = True
                        break
                    if sobrescritas.get(
                            f"{get_column_letter(fim)}{linha}"):
                        bloqueada = True
                        break
                    fim += 1
                # parou em célula ocupada: corta na borda esquerda dela;
                # sem bloqueio, segue até o fim da folha (como no Excel)
                larg = (xs[fim - 1] if bloqueada else xs[fim]) - x0

            espaco = max(larg - 2 * _INSET, 4)
            linhas_txt = (_quebrar(texto, nome_pdf, tam, espaco) if wrap
                          else [texto])
            if not wrap and _medir(texto, nome_pdf, tam) > espaco:
                linhas_txt = [texto]          # cortado pelo clip abaixo

            ascent = tam * 0.78
            descent = tam * 0.22
            leading = tam * 1.22
            altura_txt = leading * len(linhas_txt)
            if al_v == "top":
                primeira = y1 - _INSET - ascent
            elif al_v == "center":
                primeira = y1 - (alt - altura_txt) / 2 - ascent
            else:  # bottom (padrão do Excel)
                ultima = y0 + _INSET + descent
                primeira = ultima - (len(linhas_txt) - 1) * leading

            # área de corte: a célula + vizinhas vazias (transbordamento)
            x_corte = x0 + larg
            c.saveState()
            caminho = c.beginPath()
            caminho.rect(x0 - 0.5, y0 - 0.5, (x_corte - x0) + 1,
                         (y1 - y0) + 1)
            c.clipPath(caminho, stroke=0, fill=0)
            c.setFillColor(HexColor(cor_txt))
            c.setFont(nome_pdf, tam)
            for i, linha_txt in enumerate(linhas_txt):
                base = primeira + i * leading
                if base < y0 - 1:
                    break
                if al_h == "center":
                    x_txt = x0 + (larg - _medir(linha_txt, nome_pdf, tam)) / 2
                elif al_h == "right":
                    x_txt = x1 - _INSET - _medir(linha_txt, nome_pdf, tam)
                else:
                    x_txt = x0 + _INSET
                c.drawString(x_txt, base, linha_txt)
            c.restoreState()

    c.restoreState()
    # fim do conteúdo visível: onde o bloco de extras (se houver) começa
    return y_base(max(visiveis)) if visiveis else topo


def _cabecalho_rodape(c, modelo: _Modelo, numero: int) -> None:
    larg_pag, alt_pag = modelo.pagina
    c.saveState()
    # cabeçalho central do modelo (topo) — Calibri 9, como no Excel
    if modelo.cabecalho_centro:
        nome_pdf = _fonte("Calibri", False, False)
        c.setFillColor(black)
        c.setFont(nome_pdf, 9)
        linhas = [ln for ln in str(modelo.cabecalho_centro).split("\n") if ln]
        base = alt_pag - modelo.alt_cabecalho - 9 * 1.2
        for ln in linhas:
            ln = _preparar_texto(ln, nome_pdf)
            c.drawCentredString(larg_pag / 2, base, ln)
            base -= 9 * 1.2
    # rodapé direito "Página N" (rodapé do modelo)
    rodape = str(modelo.rodape_direita or "").replace("&P", str(numero))
    if rodape:
        nome_pdf = _fonte("Calibri", False, False)
        c.setFillColor(black)
        c.setFont(nome_pdf, 9)
        c.drawRightString(larg_pag - modelo.margem_dir,
                          modelo.alt_rodape * 0.55,
                          _preparar_texto(rodape, nome_pdf))
    c.restoreState()


_EXTRA_TITULO_ALT = 15.75    # altura do título do bloco de extras
_EXTRA_LINHA_ALT = 15.75     # altura de cada linha de pares rótulo/valor
_EXTRA_GAP = 8.0             # respiro entre o formulário e o bloco de extras


def _altura_extras(extras: Sequence[Tuple[str, str, str]]) -> float:
    """Altura do bloco "OUTROS DADOS DA LINHA" (unidades do modelo)."""
    if not extras:
        return 0.0
    n_linhas = max((len(extras) + 1) // 2, 1)
    return _EXTRA_TITULO_ALT + n_linhas * _EXTRA_LINHA_ALT


def _escala_da_ficha(modelo: _Modelo, ficha: Dict[str, Any]) -> float:
    """Escala que faz a ficha INTEIRA caber em uma página A4.

    O formulário do modelo ocupa duas páginas impressas (quebra na linha
    ``_QUEBRA_PAGINA``) e as listas fixas do paciente ainda encolhem parte
    dele. Reduzir a escala (nunca amplia) mantém ficha + extras em UMA
    página, sem partir o documento.
    """
    larg_pag, alt_pag = modelo.pagina
    util_w = larg_pag - modelo.margem_esq - modelo.margem_dir
    util_h = alt_pag - modelo.margem_topo - modelo.margem_base
    altura = modelo.altura_visivel(ficha["ocultar"])
    if ficha["extras"]:
        altura += _EXTRA_GAP + _altura_extras(ficha["extras"])
    if altura <= 0:
        return modelo.escala
    nc = modelo.colunas_para(ficha["sobrescritas"])
    escala = min(util_h / altura, util_w / modelo.xs[nc])
    return min(modelo.escala, escala)


def _desenhar_extras(c, modelo: _Modelo, extras: Sequence[Tuple[str, str, str]],
                     escala: float, y_topo: float, nc: int) -> None:
    """Uma vez só, na mesma página: colunas da linha sem campo no formulário.

    Desenhado na mesma transformação (origem + escala) do formulário, logo
    abaixo do conteúdo que ``_desenhar_pagina`` deixou.
    """
    larg_pag = modelo.pagina[0]
    util = modelo.xs[nc]

    c.saveState()
    desloc = max(larg_pag - modelo.margem_esq - modelo.margem_dir
                 - util * escala, 0.0) / 2.0
    c.translate(modelo.margem_esq + desloc, 0)
    c.scale(escala, escala)

    # grade de 4 colunas (2 pares rótulo/valor por linha)
    larguras = [util * 0.20, util * 0.30, util * 0.20, util * 0.30]
    xs = [0.0]
    for w in larguras:
        xs.append(xs[-1] + w)

    altura_titulo = _EXTRA_TITULO_ALT
    altura_linha = _EXTRA_LINHA_ALT
    itens = list(extras)
    n_linhas = max((len(itens) + 1) // 2, 1)
    y_titulo = y_topo - altura_titulo
    y_fim = y_titulo - altura_linha * n_linhas

    # título da seção (mesma linguagem do formulário)
    c.setFillColor(white)
    c.rect(xs[0], y_titulo, util, altura_titulo, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(1.25)
    c.rect(xs[0], y_titulo, util, altura_titulo, stroke=1, fill=0)
    nome_titulo = _fonte("Calibri", True, False)
    c.setFillColor(HexColor("#000000"))
    c.setFont(nome_titulo, 11)
    c.drawString(xs[0] + 6, y_titulo + 4,
                 _preparar_texto("OUTROS DADOS DA LINHA — informação da linha "
                                 "sem campo no formulário da ficha", nome_titulo))

    # grade das linhas (por cima, como a planilha)
    c.setStrokeColor(HexColor(_GRADE_COR))
    c.setLineWidth(_GRADE_ESP)
    yy = y_titulo
    while yy >= y_fim - 0.1:
        c.line(xs[0], yy, xs[-1], yy)
        yy -= altura_linha
    for x in xs:
        c.line(x, y_fim, x, y_titulo)

    # pares rótulo/valor
    nome_rot = _fonte("Calibri", True, False)
    nome_val = _fonte("Calibri", False, False)
    for i, (rotulo, valor, _) in enumerate(itens):
        par = i % 2
        linha_y = y_titulo - (i // 2 + 1) * altura_linha
        x_rot = xs[par * 2]
        x_val = xs[par * 2 + 1]
        c.setFillColor(HexColor("#000000"))
        c.setFont(nome_rot, 9.5)
        rotulo_txt = _preparar_texto(str(rotulo), nome_rot)
        while _medir(rotulo_txt, nome_rot, 9.5) > larguras[par * 2] - 6 \
                and len(rotulo_txt) > 4:
            rotulo_txt = rotulo_txt[:-2]
        c.drawString(x_rot + 3, linha_y + 4.5, rotulo_txt)
        c.setFont(nome_val, 9.5)
        valor_txt = _preparar_texto(str(valor), nome_val)
        while _medir(valor_txt, nome_val, 9.5) > larguras[par * 2 + 1] - 6 \
                and len(valor_txt) > 4:
            valor_txt = valor_txt[:-2]
        c.drawString(x_val + 3, linha_y + 4.5, valor_txt)

    c.restoreState()


def gerar_ficha_pdf(row: Any, caminho: Path) -> Path:
    """Gera o PDF da ficha de uma linha e devolve o caminho gravado."""
    _exigir_reportlab()
    modelo = carregar_modelo()
    ficha = montar_ficha(row)
    caminho = Path(caminho)
    caminho.parent.mkdir(exist_ok=True, parents=True)

    nome_paciente = _texto(dict(row).get("Nome_Paciente")) if row is not None else ""
    c = _canvas.Canvas(str(caminho), pagesize=modelo.pagina)
    # Codificação de fonte = UTF-8 (sobrescreve o default WinAnsi/Cp1252 do
    # reportlab) para que os glyphs acentuados que o PDF já contém sejam
    # extraídos pelo pdfminer / dumppdf com o texto correto.
    c._doc.userencode = False
    c.setTitle(f"Ficha da OCI - {nome_paciente or 'Paciente'}"[:120])
    c.setAuthor("Penna Conversor")
    c.setSubject("Ficha da OCI (APAC)")

    # Uma página: o formulário inteiro em escala reduzida e, abaixo dele, o
    # bloco de OUTROS DADOS DA LINHA (quando a linha tem algo fora do
    # formulário) em vez de uma segunda página.
    escala = _escala_da_ficha(modelo, ficha)
    nc = modelo.colunas_para(ficha["sobrescritas"])
    ultima = len(modelo.paginas) - 1
    numero = 1
    for i, (r1, r2) in enumerate(modelo.paginas):
        y_fim = _desenhar_pagina(c, modelo, ficha["sobrescritas"], r1, r2,
                                 ficha["ocultar"], ficha["suprimir"], escala)
        if i == ultima and ficha["extras"]:
            _desenhar_extras(c, modelo, ficha["extras"], escala,
                             y_fim - _EXTRA_GAP, nc)
        _cabecalho_rodape(c, modelo, numero)
        c.showPage()
        numero += 1
    c.save()
    return caminho


def exportar_fichas(df: Any, pasta_destino: Path,
                    progresso=None) -> List[Path]:
    """Gera UMA ficha PDF por linha do DataFrame na pasta escolhida.

    ``progresso(titulo, detalhe)`` é opcional (mesmo contrato da tela de
    carregamento usada pela UI). Devolve a lista de PDFs gravados.
    """
    _exigir_reportlab()
    destino = Path(pasta_destino)
    destino.mkdir(exist_ok=True, parents=True)

    linhas: List[Dict[str, str]] = []
    for _, serie in df.iterrows():
        row = {str(chave): _texto(valor) for chave, valor in serie.to_dict().items()}
        if any(row.values()):
            linhas.append(row)

    total = len(linhas)
    usados: Set[str] = set()
    gerados: List[Path] = []
    for indice, row in enumerate(linhas, start=1):
        arquivo = nome_arquivo_ficha(row, indice, usados)
        caminho = gerar_ficha_pdf(row, destino / arquivo)
        gerados.append(caminho)
        if progresso is not None:
            progresso(f"Gerando fichas em PDF… {indice}/{total}",
                      row.get("Nome_Paciente") or caminho.name)
    return gerados
