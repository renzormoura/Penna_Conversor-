"""Componentes de UI reutilizáveis do Penna.

Contém os widgets customizados que compõem a interface:
    HeaderCanvas  — cabeçalho minimalista com ícone e badge
    DropZone      — área de arraste/clique com estados visuais (idle/dragover/loaded)
    PainelErros   — listagem RCONSIST rolável com controles de fonte

Todos os componentes dependem apenas de tkinter e de ui.theme.
Nenhum deles conhece lógica de negócio (gerador, validador, remessa).
"""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Button, Frame, Label

try:
    import tkinter as tk
except Exception:
    tk = None  # type: ignore

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from .theme import (
    COR_AZUL_ACTIVE,
    COR_AZUL_BORDA,
    COR_AZUL_DASH,
    COR_AZUL_HOVER,
    COR_AZUL_PRINCIPAL,
    COR_AZUL_TINT,
    COR_BORDA,
    COR_BRANCO,
    COR_CARD,
    COR_ERRO,
    COR_ERRO_BG,
    COR_FUNDO,
    COR_SUCESSO,
    COR_SUCESSO_BG,
    COR_SUCESSO_BORDA,
    COR_TEXTO_CORPO,
    COR_TEXTO_HINT,
    COR_TEXTO_MEDIO,
    COR_TEXTO_TITULO,
)

# ---------------------------------------------------------------------------
# Helpers de ícone (sem estado global)
# ---------------------------------------------------------------------------

def carregar_icone_foto(altura_alvo: int = 44):
    """Carrega o ícone oficial com antialiasing LANCZOS.

    Busca candidatos na pasta do EXE (PyInstaller) e no diretório raiz do
    projeto. Retorna PhotoImage ou None se nenhum arquivo for encontrado.
    """
    candidates: list[Path] = []
    base = getattr(sys, "_MEIPASS", None)
    # Raiz do projeto: dois níveis acima de ui/components.py
    here = Path(__file__).resolve().parent.parent
    for prefix in ([Path(base)] if base else []) + [here]:
        for name in ("penna.png", "penna_header.png", "penna.icon.png",
                     "apac_icon.png", "apac_icon_header.png"):
            candidates.append(prefix / name)

    for path in candidates:
        if path.exists():
            try:
                if Image is not None and ImageTk is not None:
                    img = Image.open(path).convert("RGBA")
                    bbox = img.getbbox()
                    if bbox:
                        img = img.crop(bbox)
                    w, h = img.size
                    ratio = altura_alvo / max(1, h)
                    novo_w = max(1, round(w * ratio))
                    img = img.resize((novo_w, altura_alvo), Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(img)
                elif tk is not None:
                    return tk.PhotoImage(file=str(path))
            except Exception:
                pass
    return None


def desenhar_pena_vetorial(canvas, ox: int, oy: int,
                           escala: float = 0.65,
                           cor: str = COR_AZUL_PRINCIPAL) -> None:
    """Desenho vetorial de fallback da pena no azul oficial."""
    p = lambda x, y: (ox + x * escala, oy + y * escala)
    corpo = [p(36, 2), p(48, 24), p(47, 48), p(26, 72), p(8, 54), p(9, 26), p(21, 8)]
    canvas.create_polygon(corpo, smooth=True, fill=cor, outline="")
    canvas.create_line(
        [p(36, 5), p(39, 30), p(30, 54), p(25, 69)],
        smooth=True, width=max(2, round(2.5 * escala)), fill="#ffffff", capstyle="round",
    )


# ---------------------------------------------------------------------------
# HeaderCanvas
# ---------------------------------------------------------------------------

class HeaderCanvas(tk.Canvas):
    """Cabeçalho minimalista: fundo branco, faixa azul no topo, ícone e badge."""

    def __init__(self, master, **kw):
        super().__init__(master, height=76, highlightthickness=0, bd=0, bg=COR_BRANCO, **kw)
        self._icon_photo = carregar_icone_foto(altura_alvo=42)
        self._competencia = ""
        self.bind("<Configure>", lambda _: self._render())
        self._render()

    def set_competencia(self, texto: str) -> None:
        """Exibe no cabeçalho o mês analisado nos formularios (ex.:
        'COMPETÊNCIA 2026/06 • JUN'). Texto vazio limpa a exibição."""
        self._competencia = texto or ""
        self._render()

    def _render(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 400)
        h = 76

        self.create_rectangle(0, 0, w, h, fill=COR_BRANCO, outline="")
        self.create_rectangle(0, 0, w, 3, fill=COR_AZUL_PRINCIPAL, outline="")
        self.create_line(0, h - 1, w, h - 1, fill=COR_BORDA, width=1)

        if self._icon_photo is not None:
            self.create_image(44, 40, image=self._icon_photo)
        else:
            desenhar_pena_vetorial(self, 28, 16, escala=0.68, cor=COR_AZUL_PRINCIPAL)

        self.create_text(76, 29, text="PENNA",
                         font=("Segoe UI", 18, "bold"), fill=COR_TEXTO_TITULO, anchor="w")

        bx1, by1, bx2, by2 = 168, 20, 262, 38
        self.create_rectangle(bx1, by1, bx2, by2, fill=COR_AZUL_TINT, outline=COR_AZUL_BORDA, width=1)
        self.create_text((bx1 + bx2) // 2, (by1 + by2) // 2,
                         text="PENNA FISCAL", font=("Segoe UI", 8, "bold"), fill=COR_AZUL_PRINCIPAL)

        self.create_text(76, 52, text="Gerador e Validador de Arquivo Fiscal • SUS",
                         font=("Segoe UI", 9), fill=COR_TEXTO_MEDIO, anchor="w")

        if w >= 660:
            rx, pill_w, pill_h = w - 24, 126, 24
            py1 = (h - pill_h) // 2 + 1
            py2 = py1 + pill_h
            self.create_rectangle(rx - pill_w, py1, rx, py2, fill=COR_FUNDO, outline=COR_BORDA, width=1)
            dot_cx = rx - pill_w + 12
            dot_cy = (py1 + py2) // 2
            self.create_oval(dot_cx - 4, dot_cy - 4, dot_cx + 4, dot_cy + 4,
                             fill=COR_SUCESSO, outline="")
            self.create_text(rx - pill_w + 24, dot_cy, text="Sistema Pronto",
                             font=("Segoe UI", 8, "bold"), fill=COR_TEXTO_CORPO, anchor="w")

            if self._competencia:
                self.create_text(rx, py2 + 11, text=self._competencia,
                                 font=("Segoe UI", 8, "bold"),
                                 fill=COR_AZUL_PRINCIPAL, anchor="e")


# ---------------------------------------------------------------------------
# DropZone
# ---------------------------------------------------------------------------

class DropZone(tk.Canvas):
    """Área de arraste/clique com três estados visuais: idle, dragover, loaded."""

    def __init__(self, master, hint_text: str, on_click_callback=None, **kw):
        super().__init__(master, height=144, highlightthickness=0, bd=0,
                         bg=COR_BRANCO, cursor="hand2", **kw)
        self._hint = hint_text
        self._text = hint_text
        self._state = "idle"
        self._file_name = ""
        self._file_size = ""
        self._on_click = on_click_callback
        self.bind("<Configure>", lambda _: self._render())
        self.bind("<Button-1>", self._handle_click)
        self._render()

    def _handle_click(self, _event) -> None:
        if self._on_click is not None:
            self._on_click()

    # ---- Mutações de estado públicas ----

    def set_state_idle(self, hint_text: str | None = None) -> None:
        self._state = "idle"
        if hint_text:
            self._hint = self._text = hint_text
        self._render()

    def set_state_dragover(self) -> None:
        self._state = "dragover"
        self._render()

    def set_state_loaded(self, file_name: str, file_size: str = "") -> None:
        self._state = "loaded"
        self._file_name = file_name
        self._file_size = file_size
        self._render()

    # ---- configure retrocompat (aceita `text=` sem quebrar) ----

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        text_val = kw.pop("text", None)
        kw.pop("bg", None)
        kw.pop("fg", None)
        kw.pop("relief", None)
        kw.pop("bd", None)
        if text_val is not None:
            s = str(text_val)
            if "Arquivo recebido" in s:
                parts = s.splitlines()
                self._state = "loaded"
                self._file_name = parts[-1] if len(parts) > 1 else s
            elif "SOLTE" in s.upper():
                self._state = "dragover"
            else:
                self._state = "idle"
                self._text = s
        if kw:
            try:
                super().configure(**kw)
            except Exception:
                pass
        self._render()

    config = configure

    def _render(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 260)
        h, m = 144, 5
        cx, cy = w // 2, h // 2

        if self._state == "dragover":
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_AZUL_TINT, outline=COR_AZUL_PRINCIPAL, width=2)
            self._draw_upload_icon(cx, cy, COR_AZUL_PRINCIPAL)
            self.create_text(cx, cy + 8, text="Solte a planilha Excel aqui",
                             font=("Segoe UI", 12, "bold"), fill=COR_AZUL_PRINCIPAL)
            self.create_text(cx, cy + 30, text="O arquivo será carregado instantaneamente",
                             font=("Segoe UI", 9), fill=COR_AZUL_PRINCIPAL)

        elif self._state == "loaded":
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_SUCESSO_BG, outline=COR_SUCESSO_BORDA, width=1.5)
            badge_y = cy - 26
            self.create_oval(cx - 15, badge_y - 15, cx + 15, badge_y + 15,
                             fill=COR_SUCESSO, outline="")
            self.create_line(cx - 6, badge_y, cx - 2, badge_y + 4, cx + 7, badge_y - 5,
                             fill=COR_BRANCO, width=2.5, capstyle="round", joinstyle="round")
            name = self._file_name
            if len(name) > 65:
                name = name[:32] + "..." + name[-28:]
            self.create_text(cx, cy + 8, text=name,
                             font=("Segoe UI", 11, "bold"), fill=COR_TEXTO_TITULO)
            extra = f" ({self._file_size})" if self._file_size else ""
            self.create_text(cx, cy + 30,
                             text=f"Planilha pronta para conversão{extra} • Clique para trocar",
                             font=("Segoe UI", 9), fill=COR_SUCESSO)

        else:  # idle
            self.create_rectangle(m, m, w - m, h - m,
                                  fill=COR_BRANCO, outline=COR_AZUL_DASH, width=1.5, dash=(6, 4))
            self._draw_upload_icon(cx, cy, COR_AZUL_PRINCIPAL, small=True)
            self.create_text(cx, cy + 6, text="Arraste e solte o arquivo Excel aqui",
                             font=("Segoe UI", 11, "bold"), fill=COR_TEXTO_TITULO)
            self.create_text(cx, cy + 26, text="ou clique nesta área para selecionar",
                             font=("Segoe UI", 9), fill=COR_TEXTO_MEDIO)
            self.create_text(cx, cy + 44, text="Suporta formatos .xlsx, .xlsm e .xls",
                             font=("Segoe UI", 8), fill=COR_TEXTO_HINT)

    def _draw_upload_icon(self, cx: int, cy: int, cor: str, small: bool = False) -> None:
        """Ícone de upload (seta para cima + bandeja)."""
        w_line = 2 if small else 2.5
        top = cy - 38 if small else cy - 40
        mid = cy - 18
        self.create_line(cx - 18, cy - 24, cx - 18, cy - 12,
                         cx + 18, cy - 12, cx + 18, cy - 24,
                         fill=cor, width=2, capstyle="round", joinstyle="round")
        self.create_line(cx, top, cx, mid, fill=cor, width=w_line, capstyle="round")
        self.create_line(cx - 7, cy - 26, cx, mid, cx + 7, cy - 26,
                         fill=cor, width=w_line, capstyle="round", joinstyle="round")


# ---------------------------------------------------------------------------
# PainelErros
# ---------------------------------------------------------------------------

class PainelErros(tk.Frame):
    """Listagem de ocorrências no formato RCONSIST com rolamento por roda do mouse.

    Exibida NO LUGAR do card de fluxo quando a planilha tem inconsistências.
    ERR = vermelho (bloqueia exportação), AVS = laranja (apenas aviso).
    """

    TAM_FONTE_INI = 9
    ALTURA_LINHA  = 22

    def __init__(self, master, ocorrencias, ao_fechar=None, fonte_tamanho: int = 9) -> None:
        # Importação local para evitar dependência circular no nível de módulo
        from apac_mag_validador import resumo as resumo_ocorrencias

        super().__init__(master, bg=COR_CARD,
                         highlightthickness=1, highlightbackground=COR_ERRO, bd=0)
        self._ao_fechar = ao_fechar
        self._tam_fonte = max(6, int(fonte_tamanho))

        n_err, n_avs = resumo_ocorrencias(ocorrencias)

        # ---- Cabeçalho ----
        topo = Frame(self, bg=COR_ERRO_BG)
        topo.pack(fill="x", padx=1, pady=(1, 0))
        self.lbl_titulo = Label(
            topo,
            text=f"RELATÓRIO DA CONSISTÊNCIA — {n_err} erro(s) bloqueante(s), {n_avs} aviso(s)",
            bg=COR_ERRO_BG, fg=COR_ERRO, font=("Segoe UI", 10, "bold"), anchor="w",
        )
        self.lbl_titulo.pack(side="left", fill="x", expand=True, padx=12, pady=(8, 0))

        for texto, _ in (
            ("AVISO", ""),
            ("A-", ""),
            ("A+", ""),
            ("OCULTAR", ""),
        ):
            cor_fg = COR_TEXTO_CORPO if texto == "AVISO" else COR_ERRO
            btn = Button(
                topo, text=texto, command=lambda t=texto: self._acao_botao(t),
                bg=COR_ERRO_BG, fg=cor_fg, relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI", 8, "bold"), padx=6,
            )
            side = "left" if texto == "AVISO" else "right"
            padx = (6, 0) if texto == "AVISO" else (0, 6)
            btn.pack(side=side, padx=padx, pady=8)

        # ---- Cabeçalho de colunas RCONSIST ----
        colunas = Frame(self, bg=COR_CARD)
        colunas.pack(fill="x", padx=12)
        for col in ("CMPT.", "NUM.APAC", "TIPO", "SEQ.", "COD.", "DESCRIÇÃO"):
            Label(colunas, text=col, bg=COR_CARD, fg=COR_TEXTO_MEDIO,
                  font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left", padx=(0, 18))

        # ---- Lista rolável ----
        self.canvas = tk.Canvas(self, bg=COR_CARD, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(2, 4))
        scrollbar.pack(side="right", fill="y", pady=(2, 4))

        self.frame_lista = Frame(self.canvas, bg=COR_CARD)
        self._janela_lista = self.canvas.create_window((0, 0), window=self.frame_lista, anchor="nw")
        self.frame_lista.bind("<Configure>", self._ao_redimensionar_lista)
        self.canvas.bind("<Configure>", self._ajustar_largura)

        cor_tipo = {"ERR": COR_ERRO, "AVS": "#b45309"}
        for ocor in ocorrencias:
            linha = Frame(self.frame_lista, bg=COR_CARD)
            linha.pack(fill="x")
            rotulo_seq = ocor.seq if ocor.seq else "—"
            for val, largura in (
                (ocor.cmpt, 6), (ocor.num_apac, 13), (ocor.tipo, 4), (rotulo_seq, 6), (ocor.cod, 6)
            ):
                Label(
                    linha, text=val, bg=COR_CARD,
                    fg=cor_tipo.get(ocor.tipo, COR_TEXTO_CORPO),
                    font=("Segoe UI", self._tam_fonte, "bold" if ocor.tipo == "ERR" else "normal"),
                    width=largura, anchor="w",
                ).pack(side="left", pady=3)
            Label(
                linha, text=ocor.descricao, bg=COR_CARD, fg=COR_TEXTO_CORPO,
                font=("Segoe UI", self._tam_fonte), anchor="w",
            ).pack(side="left", fill="x", expand=True, pady=3)

        if n_avs and n_err == 0:
            Label(
                self.frame_lista,
                text="Somente avisos (AVS): o arquivo pode ser gerado, igual ao sistema antigo.",
                bg=COR_SUCESSO_BG, fg=COR_SUCESSO, font=("Segoe UI", 9, "bold"), anchor="w",
            ).pack(fill="x", pady=(6, 2))

        self.canvas.bind_all("<MouseWheel>", self._rolar_roda)
        self.canvas.bind_all("<Button-4>", self._rolar_roda)
        self.canvas.bind_all("<Button-5>", self._rolar_roda)
        self.bind("<Destroy>", self._desligar_roda)

    # ---- Rolamento ----

    def _rolar_roda(self, event) -> str:
        delta = getattr(event, "delta", 0)
        num = getattr(event, "num", None)
        if delta:
            passos = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        elif num == 4:
            passos = -1
        elif num == 5:
            passos = 1
        else:
            passos = 0
        if passos:
            self.canvas.yview_scroll(passos, "units")
        return "break"

    def _desligar_roda(self, _=None) -> None:
        try:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        except Exception:
            pass

    def _ao_redimensionar_lista(self, _=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _ajustar_largura(self, event) -> None:
        self.canvas.itemconfigure(self._janela_lista, width=event.width)

    # ---- Ações dos botões ----

    def _acao_botao(self, texto: str) -> None:
        if texto == "A-":
            self.alterar_fonte(-1)
        elif texto == "A+":
            self.alterar_fonte(1)
        elif texto == "OCULTAR" and self._ao_fechar is not None:
            self._ao_fechar()

    def alterar_fonte(self, delta: int) -> None:
        novo = min(20, max(6, self._tam_fonte + delta))
        if novo == self._tam_fonte:
            return
        self._tam_fonte = novo
        for widget in self.frame_lista.winfo_children():
            if isinstance(widget, Frame):
                for filho in widget.winfo_children():
                    try:
                        partes = list(filho.cget("font"))
                        partes[1] = novo
                        filho.configure(font=tuple(partes))
                    except Exception:
                        pass

    def focus_set(self):
        self.canvas.focus_set()
        return super().focus_set()


# ---------------------------------------------------------------------------
# SigtapSelector
# ---------------------------------------------------------------------------

class SigtapSelector(tk.Frame):
    """Barra compacta para selecionar e baixar a competência SIGTAP.

    Exibe:
      • Label "Base SIGTAP:"
      • Combobox com meses disponíveis (local + FTP)
      • Indicador de status (local ✓ / FTP ↓ / sem dados)
      • Botão "Baixar" (aparece apenas quando o mês não está em cache local)
      • Barra de progresso durante o download

    A competência selecionada fica em `self.competencia_var` (StringVar).
    O callback `on_change(competencia: str)` é chamado quando muda.

    Uso em PennaApp:
        self.sigtap_sel = SigtapSelector(frame, on_change=self._on_sigtap_change)
        competencia = self.sigtap_sel.competencia_var.get()
    """

    _COR_OK    = "#059669"   # verde — disponível localmente
    _COR_FTP   = "#d97706"   # laranja — só no FTP, precisa baixar
    _COR_VAZIO = "#94a3b8"   # cinza — nenhuma base
    _LARGURA_COMBO = 10      # caracteres do combobox
    AUTOMATICO = "Automático"  # valor do combobox = detecção do mês da planilha
    AUTOMATICO = "Automático"  # valor do combobox = detecção do mês da planilha

    def __init__(self, master, on_change=None, **kw):
        super().__init__(master, bg=COR_FUNDO, **kw)
        self._on_change = on_change
        self._competencias_ftp: list[str] = []
        self._competencias_local: set[str] = set()
        self._download_thread = None
        self._cancelado = False
        # Estado do foco automático (mês da planilha em "Automático")
        self._ftp_pronto = False          # listas local/FTP já aplicadas
        self._comp_planilha = ""          # mês detectado na planilha carregada
        self._foco_do_usuario = False     # True: usuário escolheu um mês à mão
        self._auto_baixadas: set[str] = set()  # downloads automáticos já feitos
        self._baixando = False            # download (auto ou manual) em voo

        try:
            import tkinter.ttk as ttk
            self._ttk = ttk
        except Exception:
            self._ttk = None

        self._construir()
        # Carregar listas em background para não bloquear a UI
        self._atualizar_listas_async()

    # ------------------------------------------------------------------
    # Construção dos widgets
    # ------------------------------------------------------------------

    def _construir(self) -> None:
        tk.Label(
            self, text="Base SIGTAP:", bg=COR_FUNDO,
            fg=COR_TEXTO_CORPO, font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self.competencia_var = tk.StringVar(value="Automático")

        if self._ttk:
            self.combo = self._ttk.Combobox(
                self, textvariable=self.competencia_var,
                width=self._LARGURA_COMBO, state="readonly",
                font=("Segoe UI", 9),
            )
        else:
            self.combo = tk.OptionMenu(self, self.competencia_var, "Automático")

        self.combo.pack(side="left", padx=(0, 6))
        self.combo.bind("<<ComboboxSelected>>", self._ao_selecionar)

        # Indicador de status (ícone + texto)
        self._dot = tk.Canvas(
            self, width=10, height=10, bg=COR_FUNDO,
            highlightthickness=0, bd=0,
        )
        self._dot.pack(side="left", padx=(0, 3))
        self._dot_item = self._dot.create_oval(1, 1, 9, 9, fill=self._COR_VAZIO, outline="")

        self._lbl_status = tk.Label(
            self, text="carregando…", bg=COR_FUNDO,
            fg=COR_TEXTO_HINT, font=("Segoe UI", 8),
        )
        self._lbl_status.pack(side="left", padx=(0, 8))

        # Botão Baixar (oculto por padrão)
        self._btn_baixar = tk.Button(
            self, text="⬇ Baixar", command=self._iniciar_download,
            bg=COR_AZUL_PRINCIPAL, fg=COR_BRANCO,
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI", 8, "bold"), padx=8, pady=2,
            activebackground=COR_AZUL_HOVER, activeforeground=COR_BRANCO,
        )
        # não empacota ainda — aparece só quando necessário

        # Barra de progresso (oculta por padrão)
        if self._ttk:
            self._progress = self._ttk.Progressbar(
                self, orient="horizontal", length=120, mode="determinate",
            )
        else:
            self._progress = None

        self._lbl_progresso = tk.Label(
            self, text="", bg=COR_FUNDO,
            fg=COR_TEXTO_MEDIO, font=("Segoe UI", 8),
        )

    # ------------------------------------------------------------------
    # Carregamento das listas (assíncrono)
    # ------------------------------------------------------------------

    def _atualizar_listas_async(self) -> None:
        import threading
        t = threading.Thread(target=self._carregar_listas, daemon=True)
        t.start()

    def _carregar_listas(self) -> None:
        try:
            from apac_mag_sigtap_download import (
                listar_competencias_ftp,
                listar_competencias_cache,
            )
            local = set(listar_competencias_cache())
            ftp   = listar_competencias_ftp(timeout=8)
        except Exception:
            local = set()
            ftp   = []

        self._competencias_local = local
        self._competencias_ftp   = ftp

        # Montar lista para o combobox: "Automático" + todas do FTP (mais recentes primeiro)
        todas = sorted(set(ftp) | local, reverse=True)
        opcoes = ["Automático"] + [self._fmt(c) for c in todas]

        # `after` de outra thread só cola com o loop Tcl principal ativo:
        # com rede rápida o retorno chega antes da janela entrar no loop.
        # Em vez de perder a atualização (e o foco do mês da planilha),
        # tenta de novo por alguns segundos.
        import time
        for _ in range(100):
            try:
                self.after(0, lambda: self._aplicar_listas(opcoes, todas))
                break
            except Exception:
                time.sleep(0.05)

    def _fmt(self, comp: str) -> str:
        """'202606' -> '2026/06'"""
        if len(comp) == 6 and comp.isdigit():
            return f"{comp[:4]}/{comp[4:]}"
        return comp

    def _parse(self, texto: str) -> str:
        """'2026/06' -> '202606'  (ou 'Automático' -> '')"""
        return texto.replace("/", "").strip() if texto not in ("Automático", "") else ""

    def _aplicar_listas(self, opcoes: list, todas: list) -> None:
        try:
            if self._ttk and hasattr(self.combo, "configure"):
                self.combo.configure(values=opcoes)
        except Exception:
            pass
        self._ftp_pronto = True
        # Foco do mês da planilha que chegou enquanto as listas carregavam
        self._reaplicar_foco()
        # Atualiza status para a opção atual
        self._atualizar_status(self._parse(self.competencia_var.get()))

    # ------------------------------------------------------------------
    # Atualização de status visual
    # ------------------------------------------------------------------

    def _atualizar_status(self, comp: str) -> None:
        """comp = '' para Automático, 'AAAAMM' para um mês específico."""
        if not comp:
            self._dot.itemconfigure(self._dot_item, fill=self._COR_OK)
            self._lbl_status.configure(
                text="bases locais (automático)", fg=COR_TEXTO_MEDIO,
            )
            self._ocultar_botao_baixar()
            return

        em_local = comp in self._competencias_local
        em_ftp   = comp in self._competencias_ftp

        if em_local:
            self._dot.itemconfigure(self._dot_item, fill=self._COR_OK)
            self._lbl_status.configure(text="disponível (cache local)", fg=self._COR_OK)
            self._ocultar_botao_baixar()
        elif em_ftp:
            self._dot.itemconfigure(self._dot_item, fill=self._COR_FTP)
            self._lbl_status.configure(text="disponível no FTP — baixe para usar", fg=self._COR_FTP)
            self._mostrar_botao_baixar()
        else:
            self._dot.itemconfigure(self._dot_item, fill=self._COR_VAZIO)
            self._lbl_status.configure(text="não encontrado no FTP", fg=COR_TEXTO_HINT)
            self._ocultar_botao_baixar()

    def _mostrar_botao_baixar(self) -> None:
        if not self._btn_baixar.winfo_ismapped():
            self._btn_baixar.pack(side="left", padx=(0, 4))

    def _ocultar_botao_baixar(self) -> None:
        if self._btn_baixar.winfo_ismapped():
            self._btn_baixar.pack_forget()
        self._ocultar_progresso()

    def _mostrar_progresso(self) -> None:
        if self._progress and not self._progress.winfo_ismapped():
            self._progress.pack(side="left", padx=(0, 4))
        if not self._lbl_progresso.winfo_ismapped():
            self._lbl_progresso.pack(side="left")

    def _ocultar_progresso(self) -> None:
        if self._progress and self._progress.winfo_ismapped():
            self._progress.pack_forget()
        if self._lbl_progresso.winfo_ismapped():
            self._lbl_progresso.pack_forget()

    # ------------------------------------------------------------------
    # Callbacks de interação
    # ------------------------------------------------------------------

    def _ao_selecionar(self, _event=None) -> None:
        comp = self._parse(self.competencia_var.get())
        # Escolha do usuário: "Automático" à mão reativa a detecção do mês da
        # planilha; um mês escolhido à mão não é mais sobrescrito pelo foco.
        self._comp_planilha = "" if not comp else self._comp_planilha
        self._foco_do_usuario = bool(comp)
        self._atualizar_status(comp)
        if self._on_change:
            self._on_change(comp)

    # ------------------------------------------------------------------
    # Foco automático no mês da planilha
    # ------------------------------------------------------------------

    def sincronizar_com_planilha(self, comp: str) -> None:
        """Automático: foca o mês da planilha e baixa a base dele de cara.

        Chamado pela app toda vez que uma planilha é validada/executada:

        - escolha manual de mês no combobox é respeitada sem questionar;
        - com as listas ainda carregando, o foco é aplicado quando elas chegam;
        - mês em cache: só foca; mês só no FTP: o download começa sozinho
          (uma única vez por mês) e ``on_change`` revalida ao concluir;
        - mês ausente do FTP: volta para "Automático" avisando que seguem
          as bases locais.
        """
        comp = str(comp or "").strip()
        if not (len(comp) == 6 and comp.isdigit()):
            return
        if self._foco_do_usuario:
            return  # usuário escolheu um mês à mão — não mexe
        self._comp_planilha = comp
        if not self._ftp_pronto:
            return  # _aplicar_listas conclui e reaplica o foco
        self._aplicar_foco_planilha()

    def _reaplicar_foco(self) -> None:
        if self._comp_planilha and not self._foco_do_usuario:
            self._aplicar_foco_planilha()

    def _aplicar_foco_planilha(self) -> None:
        comp = self._comp_planilha
        if not comp or self._foco_do_usuario:
            return
        if comp in self._competencias_local:
            self.competencia_var.set(self._fmt(comp))
            self._atualizar_status(comp)
            return
        if comp in self._competencias_ftp:
            self.competencia_var.set(self._fmt(comp))
            self._atualizar_status(comp)
            self._baixar_automatico(comp)
            return
        # O FTP não tem mais esse mês: seguem as bases locais, avisando.
        self._comp_planilha = ""
        self.competencia_var.set(self.AUTOMATICO)
        self._atualizar_status("")
        self._lbl_status.configure(
            text=f"mês {self._fmt(comp)} sem base no FTP — bases locais",
            fg=COR_TEXTO_HINT,
        )

    def _baixar_automatico(self, comp: str) -> None:
        """Inicia o download da competência uma única vez (modo automático)."""
        if comp in self._auto_baixadas or self._baixando:
            return
        self._auto_baixadas.add(comp)
        self._iniciar_download()

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _iniciar_download(self) -> None:
        comp = self._parse(self.competencia_var.get())
        if not comp or self._baixando:
            return
        self._cancelado = False
        self._baixando = True
        self._btn_baixar.configure(state="disabled", text="baixando…")
        self._mostrar_progresso()
        if self._progress:
            self._progress.configure(value=0)
        self._lbl_progresso.configure(text="0%")

        import threading

        def _worker():
            from apac_mag_sigtap_download import baixar_competencia

            def _cb(recebidos: int, total: int) -> None:
                if self._cancelado:
                    return
                pct = int(recebidos * 100 / total) if total else 0
                try:
                    self.after(0, lambda p=pct, r=recebidos, t=total: self._atualizar_progresso(p, r, t))
                except Exception:
                    pass

            resultado = baixar_competencia(comp, callback=_cb)
            try:
                self.after(0, lambda ok=(resultado is not None): self._download_concluido(comp, ok))
            except Exception:
                pass

        self._download_thread = threading.Thread(target=_worker, daemon=True)
        self._download_thread.start()

    def _atualizar_progresso(self, pct: int, recebidos: int, total: int) -> None:
        if self._progress:
            self._progress.configure(value=pct)
        kb = recebidos // 1024
        total_kb = total // 1024 if total else 0
        texto = f"{kb} KB" if not total_kb else f"{kb}/{total_kb} KB  {pct}%"
        self._lbl_progresso.configure(text=texto)

    def _download_concluido(self, comp: str, sucesso: bool) -> None:
        self._baixando = False
        self._btn_baixar.configure(state="normal", text="⬇ Baixar")
        self._ocultar_progresso()

        if sucesso:
            self._competencias_local.add(comp)
            self._dot.itemconfigure(self._dot_item, fill=self._COR_OK)
            self._lbl_status.configure(text="download concluído ✓", fg=self._COR_OK)
            self._ocultar_botao_baixar()
            # Notifica a app para revalidar se necessário
            if self._on_change:
                self._on_change(comp)
        else:
            # Falhou: permite nova tentativa automática na próxima validação
            self._auto_baixadas.discard(comp)
            self._lbl_status.configure(
                text="falha no download — verifique a conexão", fg=COR_ERRO,
            )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_competencia(self) -> str:
        """Retorna a competência selecionada ('AAAAMM') ou '' para Automático."""
        return self._parse(self.competencia_var.get())

    def set_competencia(self, comp: str) -> None:
        """Define a competência programaticamente ('AAAAMM' ou '' para Automático)."""
        texto = self._fmt(comp) if comp else "Automático"
        self.competencia_var.set(texto)
        self._atualizar_status(comp)

    def destruir(self) -> None:
        """Cancela qualquer download em andamento e destroi o widget."""
        self._cancelado = True
        self.destroy()


# ---------------------------------------------------------------------------
# VersaoSelector
# ---------------------------------------------------------------------------

def normalizar_versao(texto) -> str:
    """'04.01' -> 'Versao 04.01'; 'versao 03.21' -> 'Versao 03.21'.

    '' para vazio. Não valida o formato (isso é da UI/negócio) — apenas
    canoniza a grafia para o campo de 12 chars do cabeçalho.
    """
    t = str(texto or "").strip()
    if not t:
        return ""
    if t.lower().startswith("versao"):
        return "Versao" + t[6:]
    return f"Versao {t}"


class VersaoSelector(tk.Frame):
    """Seletor da versão do cabeçalho '01#APAC...' por mês/competência.

    Exibe:
      • Label "Versão do cabeçalho:"
      • Combobox editável: "Automático" + versões conhecidas
      • Dica com a versão efetiva da competência atual

    "Automático" emite on_change('') — a UI remove a escolha do mês no
    penna_config.json e vale o padrão. Um valor concreto é normalizado
    ('03.21' -> 'Versao 03.21') e emitido via on_change(valor). A
    persistência é responsabilidade da UI (PennaApp), que conhece a
    competência em uso.
    """

    AUTOMATICO = "Automático"
    VERSOES_CONHECIDAS = (
        "Versao 03.18",
        "Versao 03.19",
        "Versao 03.21",
        "Versao 03.26",
        "Versao 04.01",
    )

    def __init__(self, master, on_change=None, **kw):
        bg = kw.pop("bg", COR_FUNDO)
        super().__init__(master, bg=bg, **kw)
        self._on_change = on_change
        self._bg = bg
        self._competencia = ""

        try:
            import tkinter.ttk as ttk
            self._ttk = ttk
        except Exception:
            self._ttk = None

        self._construir()

    # ------------------------------------------------------------------
    # Construção dos widgets
    # ------------------------------------------------------------------

    def _construir(self) -> None:
        tk.Label(
            self, text="Versão do cabeçalho:", bg=self._bg,
            fg=COR_TEXTO_CORPO, font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 4))

        self.versao_var = tk.StringVar(value=self.AUTOMATICO)
        valores = (self.AUTOMATICO,) + self.VERSOES_CONHECIDAS

        if self._ttk:
            self.combo = self._ttk.Combobox(
                self, textvariable=self.versao_var,
                values=list(valores), width=14, state="normal",
                font=("Segoe UI", 9),
            )
        else:
            self.combo = tk.OptionMenu(
                self, self.versao_var, *valores, command=self._ao_mudar,
            )

        self.combo.pack(side="left", padx=(0, 8))
        self.combo.bind("<<ComboboxSelected>>", self._ao_mudar)
        self.combo.bind("<Return>", self._ao_mudar)
        self.combo.bind("<FocusOut>", self._ao_mudar)

        self._lbl_dica = tk.Label(
            self, text="mês ainda não identificado", bg=self._bg,
            fg=COR_TEXTO_HINT, font=("Segoe UI", 8),
        )
        self._lbl_dica.pack(side="left")

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def get_competencia(self) -> str:
        """Competência sob a seleção atual ('AAAAMM') ou '' se desconhecida."""
        return self._competencia

    def set_competencia(self, comp: str) -> None:
        """Define o mês em foco; um mês novo volta para 'Automático'."""
        comp = str(comp or "").strip()
        if comp != self._competencia:
            self._competencia = comp
            self.versao_var.set(self.AUTOMATICO)
        self._atualizar_dica()

    def confirmar(self) -> None:
        """Grava texto digitado ainda não confirmado (não faz nada em
        'Automático' — remover a escolha só acontece por ação explícita)."""
        texto = str(self.versao_var.get() or "").strip()
        if texto and texto != self.AUTOMATICO:
            self._emitir()

    def restaurar_automatico(self) -> None:
        """Volta o combobox para 'Automático' (ex.: após texto inválido)."""
        self.versao_var.set(self.AUTOMATICO)
        self._atualizar_dica()

    # ------------------------------------------------------------------
    # Interação
    # ------------------------------------------------------------------

    def _ao_mudar(self, _event=None) -> None:
        self._emitir()

    def _emitir(self) -> None:
        texto = str(self.versao_var.get() or "").strip()
        if not texto or texto == self.AUTOMATICO:
            self.versao_var.set(self.AUTOMATICO)
            valor = ""
        else:
            valor = normalizar_versao(texto)
            self.versao_var.set(valor)
        self._atualizar_dica()
        if self._on_change:
            self._on_change(valor)

    def _atualizar_dica(self) -> None:
        comp = self._competencia
        if not comp or len(comp) != 6:
            self._lbl_dica.configure(text="mês ainda não identificado")
            return
        try:
            from apac_mag.config import get_versao
            efetiva = get_versao(comp)
        except Exception:
            efetiva = "—"
        rotulo = f"{comp[:4]}/{comp[4:6]} → {efetiva}"
        if str(self.versao_var.get() or "").strip() not in ("", self.AUTOMATICO):
            rotulo += " (definido)"
        self._lbl_dica.configure(text=rotulo)


# ---------------------------------------------------------------------------
# LoadingOverlay
# ---------------------------------------------------------------------------

class LoadingOverlay(tk.Toplevel):
    """Janela de carregamento centralizada sobre a janela principal.

    Exibe um spinner animado, uma mensagem principal e uma mensagem
    de detalhe que podem ser atualizadas em tempo real via `set_mensagem()`.

    Uso:
        overlay = LoadingOverlay(root, "Gerando arquivo...")
        overlay.tornar_modal()   # best-effort: bloqueia a janela principal
        # ... trabalho pesado em outra thread, com set_mensagem() por etapa ...
        overlay.fechar()
    """

    _RAIO      = 18      # raio do spinner
    _ESPESSURA = 4       # largura do arco
    _PASSOS    = 12      # segmentos do spinner
    _INTERVALO = 60      # ms por frame

    def __init__(self, parent, mensagem: str = "Processando…", detalhe: str = "") -> None:
        super().__init__(parent)
        self._parent = parent
        self._angulo = 0
        self._ativo  = True
        self._after_id = None

        # Janela sem decoração, sempre no topo
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COR_BRANCO)

        # Sombra leve via borda
        outer = tk.Frame(
            self, bg=COR_BORDA,
            highlightthickness=0, bd=0,
        )
        outer.pack(padx=1, pady=1)

        inner = tk.Frame(outer, bg=COR_BRANCO, padx=40, pady=32)
        inner.pack()

        # Spinner canvas
        d = (self._RAIO + self._ESPESSURA) * 2 + 4
        self._canvas = tk.Canvas(
            inner, width=d, height=d,
            bg=COR_BRANCO, highlightthickness=0, bd=0,
        )
        self._canvas.pack(pady=(0, 18))
        self._desenhar_spinner(0)

        # Mensagem principal
        self._lbl_msg = tk.Label(
            inner, text=mensagem,
            bg=COR_BRANCO, fg=COR_TEXTO_TITULO,
            font=("Segoe UI", 12, "bold"),
            wraplength=280,
        )
        self._lbl_msg.pack()

        # Detalhe
        self._lbl_detalhe = tk.Label(
            inner, text=detalhe or "",
            bg=COR_BRANCO, fg=COR_TEXTO_MEDIO,
            font=("Segoe UI", 9),
            wraplength=280,
        )
        self._lbl_detalhe.pack(pady=(4, 0))

        self._centralizar()
        self.lift()
        self.focus_set()
        self._animar()

    # ------------------------------------------------------------------
    # Posicionamento
    # ------------------------------------------------------------------

    def _centralizar(self) -> None:
        self.update_idletasks()
        pw = self._parent.winfo_width()
        ph = self._parent.winfo_height()
        px = self._parent.winfo_rootx()
        py = self._parent.winfo_rooty()
        w  = self.winfo_reqwidth()
        h  = self.winfo_reqheight()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Spinner
    # ------------------------------------------------------------------

    def _desenhar_spinner(self, angulo_inicio: int) -> None:
        self._canvas.delete("all")
        cx = cy = self._RAIO + self._ESPESSURA + 2
        r  = self._RAIO

        # Trilha cinza suave
        self._canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=0, extent=359,
            style="arc", outline=COR_BORDA,
            width=self._ESPESSURA,
        )

        # Arco azul animado (270° de extensão)
        self._canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=angulo_inicio, extent=270,
            style="arc", outline=COR_AZUL_PRINCIPAL,
            width=self._ESPESSURA,
        )

    def _animar(self) -> None:
        if not self._ativo:
            return
        self._angulo = (self._angulo + 12) % 360
        self._desenhar_spinner(self._angulo)
        try:
            self._after_id = self.after(self._INTERVALO, self._animar)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def set_mensagem(self, mensagem: str, detalhe: str = "") -> None:
        """Atualiza o texto exibido sem fechar o overlay."""
        try:
            self._lbl_msg.configure(text=mensagem)
            self._lbl_detalhe.configure(text=detalhe or "")
            self._centralizar()
            self.update_idletasks()
        except Exception:
            pass

    def tornar_modal(self) -> None:
        """Bloqueia a interação com a janela principal enquanto visível.

        Best-effort: se o grab falhar (janela ainda não mapeada), o
        overlay segue apenas informativo — o fluxo continua correto.
        """
        def _grab() -> None:
            try:
                if self.winfo_exists():
                    self.grab_set()
            except Exception:
                pass
        try:
            self.after(30, _grab)
        except Exception:
            pass

    def fechar(self) -> None:
        """Para a animação e fecha o overlay."""
        self._ativo = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            self._parent.focus_set()
        except Exception:
            pass
