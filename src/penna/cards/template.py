"""Leitura do modelo ``.xlsx`` da ficha: localização, geometria, estilos e listas."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from openpyxl.utils import column_index_from_string
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from penna import paths

from ._reportlab import A4
from .constants import CELULAS_DADOS, FATOR_ALTURA, FOLHA, NC, NOME_TEMPLATE, PAD_COLUNA, PREFIXO_ORIGINAL, PT_PX_COLUNA, TEMA_MAPA, TITULOS_SECAO
from .text import valor_texto, formatar_data

# ---------------------------------------------------------------------------
# Carregamento do template (uma vez por sessão)
# ---------------------------------------------------------------------------

def bases_template() -> List[Path]:
    """Ordem de busca do modelo da ficha.

    No executável, o local **ao lado do .exe** vem primeiro (mesmo padrão do
    ``penna_config.json``: o cliente pode deixar/editar o modelo sem novo build);
    depois o bundle embutido (``dados/modelo_ficha...xlsx``) ou a raiz do projeto
    e, por fim, o diretório de trabalho.
    """
    ao_lado = [paths.executable_dir()] if paths.is_frozen() else []
    return [*ao_lado, paths.project_root(), Path.cwd()]


def achar_template() -> Path:
    candidatos: List[Path] = []
    bases = bases_template()
    for base in bases:
        candidatos.append(base / "dados" / NOME_TEMPLATE)
    for base in bases:
        if paths.is_frozen() and base == paths.project_root():
            continue  # o bundle só embute o modelo enxuto
        candidatos.extend(sorted(base.glob(f"{PREFIXO_ORIGINAL}*.xlsx")))
    for caminho in candidatos:
        if caminho.exists():
            return caminho
    raise FileNotFoundError(
        f"arquivo modelo da ficha não encontrado (dados/{NOME_TEMPLATE})"
    )


def achar_template_original() -> Optional[Path]:
    """Caminho do modelo completo (com amostra/acentos) para fallback de textos."""
    for base in bases_template():
        for cand in list(base.glob(f"{PREFIXO_ORIGINAL}*.xlsx")) + list(base.glob("*oftalmologia*.xlsx")):
            if cand.name != NOME_TEMPLATE and cand.exists():
                return cand
    return None


class Modelo:
    """Layout da aba OCI OFTALMOLOGIA: geometria, estilos e listas do formulário."""

    def __init__(self, caminho: Path) -> None:
        import openpyxl as _xl

        self.caminho = caminho
        self._slim = caminho.name == NOME_TEMPLATE
        wb = _xl.load_workbook(caminho, data_only=True)
        if FOLHA not in wb.sheetnames:
            raise ValueError(f"aba {FOLHA!r} ausente em {caminho.name}")
        ws = wb[FOLHA]
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
        for i in range(1, NC + 1):
            letra = get_column_letter(i)
            dim = ws.column_dimensions.get(letra)
            larg = dim.width if dim is not None and dim.width else padrao
            escondida = bool(dim is not None and dim.hidden)
            self.larguras.append(
                0.0 if escondida
                else round(larg * 7) * PT_PX_COLUNA + PAD_COLUNA)
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
                     else padrao_alt) * FATOR_ALTURA)
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
                                min_col=1, max_col=NC):
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
        self.n_colunas = max(1, min(NC, max(usadas) if usadas else NC))

        # --- formatos condicionais (realces do modelo) ------------------------
        self.condicionais: List[Tuple[int, int, int, int, str, str]] = []
        self._carregar_formatos_condicionais()

        # --- blocos do formulário (título -> linhas) --------------------------
        self.secoes: List[Tuple[str, int, int]] = self._calcular_secoes()

        # --- escala de impressão (cabe em A4) ------------------------------
        # Escala máxima 1.0 (idêntica ao Excel impresso); cada ficha calcula a
        # sua escala efetiva para caber em uma página — ver escala_da_ficha.
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
        return {TEMA_MAPA[i]: cores[i] for i in range(min(len(cores),
                                                           len(TEMA_MAPA)))}

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
            return formatar_data(valor.strftime("%Y%m%d"))
        return valor_texto(valor)

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
        except (AttributeError, TypeError, ValueError, IndexError):
            return None

    def _carregar_valores_originais(self) -> None:
        """Lê os valores com acentos do arquivo modelo completo (fallback).

        O template slim em ``dados/`` tem as células de amostra em branco.
        Para procedimentos e textos institucionais, usa o original completo
        como fonte dos textos com acentuação correta.
        """
        origem = achar_template_original()
        if not origem or origem == self.caminho:
            return
        try:
            import openpyxl as _xl2
            wb = _xl2.load_workbook(origem, data_only=True)
            if FOLHA not in wb.sheetnames:
                return
            ws = wb[FOLHA]
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
        except (OSError, KeyError, ValueError, zipfile.BadZipFile, InvalidFileException):
            pass  # modelo original ilegível: segue só com o template enxuto

    def _esvaziar_dados_da_amostra(self) -> None:
        for ref in CELULAS_DADOS:
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
                        procurado = valor_texto(m.group(1))
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
                       for t in TITULOS_SECAO) and not any(
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
        return min(ultima, NC)

    def altura_intervalo(self, r1: int, r2: int) -> float:
        r1 = max(1, r1)
        r2 = min(self.linhas_total, r2)
        return self.ys[r2] - self.ys[r1 - 1]


_MODELO: Optional[Modelo] = None


def carregar_modelo() -> Modelo:
    """Carrega (e memoriza) o layout da ficha do arquivo modelo."""
    global _MODELO
    if _MODELO is None:
        _MODELO = Modelo(achar_template())
    return _MODELO


def _aplicar_tint(hexa: str, t: float) -> str:
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    if t >= 0:
        r, g, b = (int(v + (255 - v) * t) for v in (r, g, b))
    else:
        r, g, b = (int(v * (1 + t)) for v in (r, g, b))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)
