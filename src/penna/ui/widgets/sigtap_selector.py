"""Seletor da competência SIGTAP, com download automático da base."""
from __future__ import annotations

import tkinter as tk
from tkinter import TclError

from ..theme import (
    COR_AZUL_HOVER,
    COR_AZUL_PRINCIPAL,
    COR_BRANCO,
    COR_ERRO,
    COR_FUNDO,
    COR_TEXTO_CORPO,
    COR_TEXTO_HINT,
    COR_TEXTO_MEDIO,
)


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
        except ImportError:
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
            from penna.reference.sigtap import (
                listar_competencias_ftp,
                listar_competencias_cache,
            )
            local = set(listar_competencias_cache())
            ftp   = listar_competencias_ftp(timeout=8)
        except OSError:
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
            except (TclError, RuntimeError):
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
        except (TclError, RuntimeError):
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
            from penna.reference.sigtap import baixar_competencia

            def _cb(recebidos: int, total: int) -> None:
                if self._cancelado:
                    return
                pct = int(recebidos * 100 / total) if total else 0
                try:
                    self.after(0, lambda p=pct, r=recebidos, t=total: self._atualizar_progresso(p, r, t))
                except (TclError, RuntimeError):
                    pass

            resultado = baixar_competencia(comp, callback=_cb)
            try:
                self.after(0, lambda ok=(resultado is not None): self._download_concluido(comp, ok))
            except (TclError, RuntimeError):
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
