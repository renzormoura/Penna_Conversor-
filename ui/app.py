"""Lógica de orquestração da aplicação Penna (PennaApp).

Esta classe coordena o fluxo:
    1. Carregar planilha Excel
    2. Validar (gate de consistência APAC-MAG)
    3. Exportar TXT fiscal em CP1252
    4. Registrar remessa (comprovante + demonstrativo + histórico)

Não conhece detalhes de renderização — delega a UI para ui.components e
ui.theme. Pode ser testado sem instanciar janela, simulando root com mock.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
import threading
from pathlib import Path
from urllib.parse import unquote
from tkinter import BooleanVar, Button, Checkbutton, Entry, Frame, Label, StringVar, TclError, Tk, filedialog, messagebox

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None   # type: ignore
    TkinterDnD = None  # type: ignore

log = logging.getLogger("penna.ui")

# Falhas esperadas de widget/thread Tk (janela destruida, fora do loop principal).
_ERROS_TK = (TclError, RuntimeError)

from penna.layout import (
    carregar_planilha,
    competencia_da_planilha,
    exportar_txt,
    extensao_mes_competencia,
    forcar_extensao_mes,
    nome_saida_sugerido,
    normalize_output_name,  # noqa: F401 (re-exportado por apac_mag_gui)
)
from apac_mag_validador import (
    Ocorrencia,  # noqa: F401 — re-exported for external callers
    validar_planilha,
    resumo as resumo_ocorrencias,
)
from penna.config import ConfigInvalidaError, verificar_configuracao
import apac_mag_fichas
import apac_mag_remessa

from .theme import (
    COR_AZUL_ACTIVE,
    COR_AZUL_HOVER,
    COR_AZUL_PRINCIPAL,
    COR_AZUL_TINT,
    COR_BORDA,
    COR_BRANCO,
    COR_CARD,
    COR_ERRO,
    COR_FUNDO,
    COR_SUCESSO,
    COR_TEXTO_CORPO,
    COR_TEXTO_HINT,
    COR_TEXTO_MEDIO,
    COR_TEXTO_TITULO,
    DROP_HINT,
    MSG_AVISOS,
    MSG_BLOQUEIO,
    WINDOW_TITLE,
)
from .components import (
    HeaderCanvas,
    DropZone,
    PainelErros,
    SigtapSelector,
    LoadingOverlay,
)

# ---------------------------------------------------------------------------
# Helpers de I/O (sem estado; testáveis isoladamente)
# ---------------------------------------------------------------------------

def formatar_tamanho_bytes(tamanho: int) -> str:
    """Formata tamanho de arquivo em representação legível (B / KB / MB)."""
    if tamanho < 1024:
        return f"{tamanho} B"
    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.1f} KB"
    return f"{tamanho / (1024 * 1024):.1f} MB"


def parse_dropped_path(raw_value) -> str:
    """Normaliza o caminho recebido de um evento drag-and-drop.

    Trata variações: listas, paths entre chaves {}, file://, UNC (\\servidor),
    caminhos com aspas e barra invertida duplicada.
    """
    if isinstance(raw_value, (list, tuple)):
        raw_value = " ".join(str(item) for item in raw_value)

    value = str(raw_value).strip().replace("\0", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if not value:
        return ""

    candidates: list[str] = []
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        candidates = [p.strip() for p in re.split(r"}\s*\{", inner) if p.strip()]
    elif "\n" in value:
        candidates = [p.strip() for p in value.splitlines() if p.strip()]
    else:
        candidates = [value]

    def _clean(path: str) -> str:
        while path.startswith("{") and path.endswith("}"):
            path = path[1:-1].strip()
        if path.startswith("file://"):
            path = path[7:]
        path = path.strip().strip('"').strip("'")
        path = unquote(path)
        # Barras normais viram invertidas (contrato Windows do conversor)
        # ANTES da checagem de UNC: assim \\//servidor/pasta tambem e
        # reconhecido e preservado como \\\\servidor\\pasta.
        path = path.replace("/", "\\")
        if path.startswith("\\\\"):
            path = "\\\\" + path[2:].replace("\\\\", "\\")
        else:
            path = path.replace("\\\\", "\\")
        return path.strip()

    for candidate in candidates:
        cleaned = _clean(candidate)
        if cleaned and os.path.exists(cleaned):
            return cleaned

    # Fallback: retorna o primeiro candidato mesmo sem verificar existência
    return _clean(candidates[0]) if candidates else ""


def texto_regras_desativadas(regras) -> str:
    """Aviso de validacao parcial ("" quando todas as regras rodaram).

    Primeira linha = resumo curto (status); demais = quais regras ficaram de fora.
    """
    regras = list(regras or ())
    if not regras:
        return ""
    plural = "regras desativadas" if len(regras) != 1 else "regra desativada"
    return (f"{len(regras)} {plural} nesta validação (base ausente)."
            + "\n" + "\n".join(f"• {r}" for r in regras))


def convert_excel_to_txt(excel_path: Path, output_path: Path | None = None) -> Path:
    """Converte o Excel para TXT fiscal e retorna o caminho do arquivo gerado.

    Analisa de qual mês são os formularios e garante o final fixo do nome
    (extensão do mês, ex.: .JUN) — o nome em si é livre.
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {excel_path}")
    df = carregar_planilha(excel_path)
    if df.empty:
        raise ValueError("A planilha está vazia. Nenhuma linha foi exportada.")
    competencia = competencia_da_planilha(df)
    if output_path is None:
        output_dir = excel_path.parent / "Formatado"
        output_dir.mkdir(exist_ok=True, parents=True)
        output_path = output_dir / nome_saida_sugerido(excel_path, competencia)
    else:
        output_path = forcar_extensao_mes(Path(output_path), competencia)
        output_path.parent.mkdir(exist_ok=True, parents=True)
    exportar_txt(df, output_path)
    return output_path


# ---------------------------------------------------------------------------
# PennaApp — coordenação da aplicação
# ---------------------------------------------------------------------------

class PennaApp:
    """Aplicação Penna: orquestra UI e lógica de negócio.

    Parâmetros:
        root   — widget raiz do tkinter (Tk ou Frame)
        embed  — True quando montado dentro de um shell externo (penna_app)
    """

    def __init__(self, root, embed: bool = False) -> None:
        self.embed = embed
        self.root = root
        self.drop_label: DropZone | None = None
        # Tela de carregamento: tarefas pesadas rodam em thread e o overlay
        # (LoadingOverlay) mostra a etapa atual enquanto a janela segue viva.
        self._tarefa_seq = 0
        self._tarefa_overlay: LoadingOverlay | None = None
        self._tarefa_holder: dict | None = None
        self._tarefa_cb = None
        self._conversao_ativa = False

        if not embed:
            self.root.title(WINDOW_TITLE)
            self.root.geometry("780x640")
            self.root.minsize(700, 560)
            self.root.configure(bg=COR_FUNDO)
            self._aplicar_icone_janela()
        else:
            self.root.configure(bg=COR_FUNDO)

        self.file_var = StringVar(value="")
        self.status_var = StringVar(value="Sistema pronto. Selecione ou arraste a planilha Excel.")

        # 1. Cabeçalho (apenas no modo standalone)
        if not embed:
            self.header = HeaderCanvas(root)
            self.header.pack(fill="x")

        # 2. Rodapé de status
        self.status_bar = Frame(root, bg=COR_BRANCO, height=32,
                                highlightthickness=1, highlightbackground=COR_BORDA, bd=0)
        self.status_bar.pack(side="bottom", fill="x")
        bar_inner = Frame(self.status_bar, bg=COR_BRANCO)
        bar_inner.pack(fill="both", expand=True, padx=20, pady=5)
        self.status_dot = tk.Canvas(bar_inner, width=12, height=12,
                                    bg=COR_BRANCO, highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self._dot_item = self.status_dot.create_oval(2, 2, 10, 10, fill=COR_AZUL_PRINCIPAL, outline="")
        self.status_label = Label(bar_inner, textvariable=self.status_var,
                                  bg=COR_BRANCO, fg=COR_TEXTO_CORPO,
                                  font=("Segoe UI", 9), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        Label(bar_inner, text="Padrão Penna / SUS • Layout Fixo • Consistência APAC-MAG",
              bg=COR_BRANCO, fg=COR_TEXTO_HINT, font=("Segoe UI", 8), anchor="e").pack(side="right")

        # 3. Card principal
        card = Frame(root, bg=COR_CARD, highlightthickness=1, highlightbackground=COR_BORDA,
                     bd=0, padx=24, pady=20)
        card.pack(fill="both", expand=True, padx=24, pady=(16, 12))

        # 4. DropZone
        drop_text = DROP_HINT if DND_FILES is not None else "Arraste ou clique para selecionar o arquivo Excel"
        self.drop_label = DropZone(card, drop_text, on_click_callback=self.open_file_dialog)
        self.drop_label.pack(fill="x", pady=(0, 16))

        self._registrar_dnd()

        # 5. Campo de caminho + botões Selecionar / Colar
        field_frame = Frame(card, bg=COR_CARD)
        field_frame.pack(fill="x", pady=(0, 14))
        Label(field_frame, text="ARQUIVO EXCEL SELECIONADO:",
              bg=COR_CARD, fg=COR_TEXTO_CORPO, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        path_box = Frame(field_frame, bg=COR_CARD)
        path_box.pack(fill="x")
        self.path_entry = Entry(path_box, textvariable=self.file_var,
                                font=("Segoe UI", 10), relief="flat", bd=0,
                                highlightthickness=1, highlightbackground="#cbd5e1",
                                highlightcolor=COR_AZUL_PRINCIPAL,
                                bg=COR_BRANCO, fg=COR_TEXTO_TITULO)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        self.path_entry.bind("<FocusIn>",
                             lambda _: self.path_entry.configure(highlightbackground=COR_AZUL_PRINCIPAL))
        self.path_entry.bind("<FocusOut>",
                             lambda _: self.path_entry.configure(highlightbackground="#cbd5e1"))

        select_btn = Button(path_box, text="Selecionar", command=self.open_file_dialog,
                            width=12, bg=COR_AZUL_PRINCIPAL, fg="white", relief="flat",
                            cursor="hand2", font=("Segoe UI", 9, "bold"),
                            activebackground=COR_AZUL_HOVER, activeforeground="white", bd=0)
        select_btn.pack(side="left", ipady=5)
        select_btn.bind("<Enter>", lambda _: select_btn.configure(bg=COR_AZUL_HOVER))
        select_btn.bind("<Leave>", lambda _: select_btn.configure(bg=COR_AZUL_PRINCIPAL))

        paste_btn = Button(path_box, text="Colar caminho", command=self.paste_path_from_clipboard,
                           width=13, bg="#f8fafc", fg=COR_TEXTO_CORPO, relief="flat",
                           cursor="hand2", font=("Segoe UI", 9, "bold"),
                           activebackground="#e2e8f0", activeforeground=COR_TEXTO_CORPO,
                           bd=0, highlightthickness=1, highlightbackground="#cbd5e1")
        paste_btn.pack(side="left", padx=(10, 0), ipady=5)
        paste_btn.bind("<Enter>", lambda _: paste_btn.configure(bg="#edf2f7"))
        paste_btn.bind("<Leave>", lambda _: paste_btn.configure(bg="#f8fafc"))

        # 6. Seletor de competência SIGTAP
        sigtap_frame = Frame(card, bg=COR_CARD)
        sigtap_frame.pack(fill="x", pady=(0, 10))
        self.sigtap_sel = SigtapSelector(
            sigtap_frame,
            on_change=self._on_sigtap_change,
        )
        self.sigtap_sel.pack(side="left")

        # 6b. (seletor de versão do cabeçalho removido: a versão do mês é
        # resolvida automaticamente pelo penna_config.json — ver config.get_versao)

        # 6c. Opções de exportação: o usuário escolhe o que sai no EXECUTAR
        # (apenas TXT, apenas fichas em PDF — uma por linha — ou ambas)
        opcoes_frame = Frame(card, bg=COR_CARD)
        opcoes_frame.pack(fill="x", pady=(0, 10))
        Label(opcoes_frame, text="OPÇÕES DE EXPORTAÇÃO:", bg=COR_CARD,
              fg=COR_TEXTO_CORPO, font=("Segoe UI", 9, "bold")
              ).pack(side="left", padx=(0, 14))
        self.var_exportar_txt = BooleanVar(value=True)
        self.var_exportar_fichas = BooleanVar(value=True)
        for texto_opcao, variavel in (
            ("TXT fiscal", self.var_exportar_txt),
            ("Fichas (PDF)", self.var_exportar_fichas),
        ):
            Checkbutton(
                opcoes_frame, text=texto_opcao, variable=variavel,
                bg=COR_CARD, fg=COR_TEXTO_CORPO, activebackground=COR_CARD,
                activeforeground=COR_AZUL_PRINCIPAL, selectcolor=COR_BRANCO,
                font=("Segoe UI", 9), cursor="hand2", relief="flat", bd=0,
                highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

        # 7. Botão EXECUTAR
        action_frame = Frame(card, bg=COR_CARD)
        action_frame.pack(fill="x", pady=(4, 16))
        Label(action_frame,
              text="O nome do arquivo é livre; a extensão do mês\n(ex.: .JUN) é fixada pela competência detectada.",
              bg=COR_CARD, fg=COR_TEXTO_MEDIO, font=("Segoe UI", 8, "italic"), justify="left"
              ).pack(side="left")
        exec_btn = Button(action_frame, text="EXECUTAR", command=self.run_conversion,
                          width=18, bg=COR_AZUL_PRINCIPAL, fg="white",
                          font=("Segoe UI", 11, "bold"), relief="flat", bd=0,
                          activebackground=COR_AZUL_ACTIVE, activeforeground="white",
                          padx=20, pady=8, cursor="hand2")
        exec_btn.pack(side="right")
        exec_btn.bind("<Enter>", lambda _: exec_btn.configure(bg=COR_AZUL_HOVER))
        exec_btn.bind("<Leave>", lambda _: exec_btn.configure(bg=COR_AZUL_PRINCIPAL))

        # 8. Container do rodapé do card (fluxo ou painel de erros)
        self._container_rodape = Frame(card, bg=COR_CARD)
        self._container_rodape.pack(fill="x", pady=(4, 0))
        self._painel_erros: PainelErros | None = None
        self._montar_card_fluxo()

        # Ctrl+O
        alvo = self.root.winfo_toplevel() if embed else self.root
        is_embed = embed

        def _ctrl_o(_=None):
            if is_embed and not self.root.winfo_ismapped():
                return None
            self.open_file_dialog()
            return "break"

        alvo.bind("<Control-o>", _ctrl_o)

        if not embed:
            self.root.after(150, self.try_load_argument_file)

    # ---------------------------------------------------------------------------
    # DnD
    # ---------------------------------------------------------------------------

    def _registrar_dnd(self) -> None:
        if DND_FILES is None or self.drop_label is None:
            if self.drop_label is not None:
                self.drop_label.configure(text="Clique aqui para selecionar a planilha Excel")
            return
        if self.embed:
            try:
                TkinterDnD._require(self.root.winfo_toplevel())
            except (*_ERROS_TK, AttributeError):
                pass
        for target in (self.root, self.drop_label):
            try:
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<Drop>>", self.on_drop)
                target.dnd_bind("<<DragEnter>>", self.on_drag_enter)
                target.dnd_bind("<<DragLeave>>", self.on_drag_leave)
            except (*_ERROS_TK, AttributeError):
                pass

    # ---------------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------------

    def _montar_card_fluxo(self) -> None:
        for filho in self._container_rodape.winfo_children():
            filho.destroy()
        self._painel_erros = None

        steps_container = Frame(self._container_rodape, bg="#fafbfc",
                                highlightthickness=1, highlightbackground=COR_BORDA, bd=0)
        steps_container.pack(fill="x")
        head = Frame(steps_container, bg="#fafbfc")
        head.pack(fill="x", padx=16, pady=(10, 8))
        Label(head, text="FLUXO DE OPERAÇÃO", font=("Segoe UI", 8, "bold"),
              fg=COR_AZUL_PRINCIPAL, bg="#fafbfc").pack(side="left")

        steps_row = Frame(steps_container, bg="#fafbfc")
        steps_row.pack(fill="x", padx=12, pady=(0, 12))
        for num, titulo, desc in (
            ("1", "Carregar",  "Arraste a planilha ou clique em Selecionar."),
            ("2", "Conferir",  "Verifique o caminho completo exibido."),
            ("3", "Executar",  "Marque TXT e/ou Fichas (PDF) e clique em EXECUTAR."),
            ("4", "Exportar",  "TXT: escolha o nome (extensão do mês é automática); fichas: escolha a pasta."),
        ):
            col = Frame(steps_row, bg="#fafbfc")
            col.pack(side="left", fill="both", expand=True, padx=4)
            top_p = Frame(col, bg="#fafbfc")
            top_p.pack(anchor="w")
            Label(top_p, text=num, font=("Segoe UI", 8, "bold"),
                  fg=COR_AZUL_PRINCIPAL, bg=COR_AZUL_TINT if True else "",
                  width=2, height=1).pack(side="left", padx=(0, 6))
            Label(top_p, text=titulo, font=("Segoe UI", 8, "bold"),
                  fg=COR_TEXTO_TITULO, bg="#fafbfc").pack(side="left")
            Label(col, text=desc, font=("Segoe UI", 8), fg=COR_TEXTO_MEDIO,
                  bg="#fafbfc", justify="left", wraplength=145).pack(anchor="w", pady=(3, 0))

    def _set_status(self, mensagem: str, tipo: str = "info") -> None:
        self.status_var.set(mensagem)
        if tipo == "sucesso":
            self.status_dot.itemconfig(self._dot_item, fill=COR_SUCESSO)
            self.status_label.configure(fg=COR_SUCESSO)
        elif tipo == "erro":
            self.status_dot.itemconfig(self._dot_item, fill=COR_ERRO)
            self.status_label.configure(fg=COR_ERRO)
        else:
            self.status_dot.itemconfig(self._dot_item, fill=COR_AZUL_PRINCIPAL)
            self.status_label.configure(fg=COR_TEXTO_CORPO)

    def _anunciar_competencia(self, competencia: str) -> None:
        """Mostra no cabeçalho da janela o mês analisado nos formularios."""
        header = getattr(self, "header", None)
        if header is None or not competencia:
            return
        texto = f"COMPETÊNCIA {competencia[:4]}/{competencia[4:6]}"
        extensao = extensao_mes_competencia(competencia)
        if extensao:
            texto += f" • {extensao[1:]}"
        try:
            header.set_competencia(texto)
        except _ERROS_TK:
            pass

    def _sincronizar_sigtap_planilha(self, competencia: str) -> None:
        """Automático: o seletor foca e baixa a base do mês da planilha.

        Usuário reclamou que planilha de um mês diferente não era aceita:
        sem isto, o modo Automático deixava a validação nas bases locais de
        outro mês e ninguém baixava o mês correspondente. Erros do seletor
        nunca derrubam a validação/exportação.
        """
        sel = getattr(self, "sigtap_sel", None)
        if sel is None or not competencia:
            return
        try:
            sel.sincronizar_com_planilha(competencia)
        except Exception:
            log.exception('falha ao sincronizar o seletor SIGTAP com a planilha')

    def _mostrar_painel_erros(self, ocorrencias) -> None:
        self._painel_erros = PainelErros(
            self._container_rodape, ocorrencias,
            ao_fechar=self._fechar_painel_erros,
        )
        self._painel_erros.pack(fill="x")

    def _ocultar_painel_erros(self) -> None:
        if self._painel_erros is not None and self._painel_erros.winfo_exists():
            self._painel_erros.destroy()
        self._painel_erros = None

    def _fechar_painel_erros(self) -> None:
        self._montar_card_fluxo()

    def _on_sigtap_change(self, competencia: str) -> None:
        """Chamado pelo SigtapSelector quando a competência muda ou o download conclui."""
        # Se houver uma planilha carregada, revalida automaticamente
        # (nunca no meio de uma conversão, para não abortar o TXT)
        file_path = self.file_var.get().strip()
        if file_path and Path(file_path).exists() and not self._conversao_ativa:
            self.test_load()

    def _escolha_sigtap_manual(self) -> str:
        """Lê a competência escolhida no combobox (somente thread principal)."""
        try:
            return self.sigtap_sel.get_competencia()
        except (*_ERROS_TK, AttributeError):
            return ""

    def _opcoes_exportacao(self) -> tuple:
        """(TXT, Fichas PDF) marcados em OPÇÕES DE EXPORTAÇÃO.

        Objetos-falsos sem as variáveis caem no comportamento antigo
        (somente TXT); nunca derruba a conversão.
        """
        try:
            return (bool(self.var_exportar_txt.get()),
                    bool(self.var_exportar_fichas.get()))
        except (*_ERROS_TK, AttributeError):
            return (True, False)

    @staticmethod
    def _resolver_sigtap(escolhido: str, competencia_planilha: str = "") -> str:
        """Resolve a competência SIGTAP sem tocar na UI (seguro em thread).

        - Seleção manual: usa exatamente o que o usuário escolheu.
        - 'Automático': tenta usar o cache SIGTAP do mês da planilha quando
          disponível, evitando o fallback para o mês anterior dos DBF locais.
        """
        if escolhido:
            # Usuário escolheu um mês específico — respeita sem questionar
            return escolhido
        if not competencia_planilha:
            return ""
        try:
            from penna.reference.sigtap import listar_competencias_cache
            if competencia_planilha in listar_competencias_cache():
                return competencia_planilha
        except (ImportError, OSError):
            pass
        return ""

    def _sigtap_competencia(self, competencia_planilha: str = "") -> str:
        """Retorna a competência SIGTAP a usar na validação (thread principal)."""
        return self._resolver_sigtap(self._escolha_sigtap_manual(), competencia_planilha)

    def _aplicar_icone_janela(self) -> None:
        base = getattr(sys, "_MEIPASS", None)
        here = Path(__file__).resolve().parent.parent
        prefixos = ([Path(base)] if base else []) + [here]
        for prefix in prefixos:
            for name in ("penna.ico", "apac_icon.ico"):
                p = prefix / name
                if p.exists():
                    try:
                        self.root.iconbitmap(default=str(p))
                        break
                    except _ERROS_TK:
                        pass
            else:
                continue
            break
        for prefix in prefixos:
            for name in ("penna.png", "penna_header.png", "penna.icon.png",
                         "apac_icon_header.png", "apac_icon.png"):
                p = prefix / name
                if p.exists():
                    try:
                        self._window_icon_photo = tk.PhotoImage(file=str(p))
                        self.root.iconphoto(True, self._window_icon_photo)
                        return
                    except _ERROS_TK:
                        pass

    # ---------------------------------------------------------------------------
    # Eventos de arquivo
    # ---------------------------------------------------------------------------

    def try_load_argument_file(self) -> None:
        if len(sys.argv) > 1:
            self.set_file(" ".join(sys.argv[1:]))
            if self.file_var.get():
                self._set_status("Arquivo carregado por argumento do sistema.", tipo="sucesso")

    def on_drag_enter(self, _event) -> str:
        if self.drop_label is not None:
            self.drop_label.set_state_dragover()
        self._set_status("Solte o arquivo Excel para carregá-lo.")
        return "break"

    def on_drag_leave(self, _event) -> str:
        if self.drop_label is not None:
            p = self.file_var.get()
            if p:
                self.drop_label.set_state_loaded(Path(p).name)
            else:
                self.drop_label.set_state_idle()
        self._set_status("Sistema pronto. Selecione ou arraste a planilha Excel.")
        return "break"

    def set_file(self, file_path: str) -> None:
        file_path = parse_dropped_path(file_path)
        if not file_path:
            return
        if not os.path.exists(file_path):
            messagebox.showerror("Arquivo inválido", "Selecione um arquivo Excel válido.")
            return
        self.file_var.set(file_path)
        # Nova planilha: o mês anunciado no cabeçalho será o dela
        header = getattr(self, "header", None)
        if header is not None:
            try:
                header.set_competencia("")
            except _ERROS_TK:
                pass
        file_name = Path(file_path).name
        tamanho_str = ""
        try:
            tamanho_str = formatar_tamanho_bytes(os.path.getsize(file_path))
        except OSError:
            pass
        # Relatório anterior é descartado e o sistema valida sozinho:
        # sem abrir painel para aviso, apenas em erro bloqueante.
        self._montar_card_fluxo()
        self._set_status(f"Arquivo carregado: {file_name}", tipo="sucesso")
        if self.drop_label is not None:
            try:
                self.drop_label.set_state_loaded(file_name, tamanho_str)
            except _ERROS_TK:
                pass
        self.test_load()

    def paste_path_from_clipboard(self) -> None:
        try:
            if tk is None:
                raise RuntimeError("tkinter indisponível")
            self.set_file(self.root.clipboard_get())
            if self.file_var.get():
                self._set_status("Caminho colado com sucesso.", tipo="sucesso")
        except Exception:
            log.exception('falha ao colar o caminho da area de transferencia')
            messagebox.showwarning("Sem caminho", "Nenhum caminho válido na área de transferência.")

    def on_drop(self, event) -> str:
        try:
            raw = getattr(event, "data", "")
            if not raw and hasattr(event, "widget"):
                w = getattr(event, "widget", None)
                if w is not None and hasattr(w, "selection_get"):
                    try:
                        raw = w.selection_get()
                    except _ERROS_TK:
                        pass
            if not raw and len(sys.argv) > 1:
                raw = " ".join(sys.argv[1:])
            if isinstance(raw, (list, tuple)):
                raw = " ".join(str(p) for p in raw)
            if not raw:
                self._set_status("Nenhum arquivo recebido no arraste.", tipo="erro")
                return "break"
            path = parse_dropped_path(raw)
            if not path and raw:
                c = raw.strip().strip("{}\"'").replace("/", "\\").replace("\\\\", "\\")
                if os.path.exists(c):
                    path = c
            if path:
                self.set_file(path)
                return "break"
        except Exception:
            log.exception('falha ao tratar o arquivo solto na janela')
        messagebox.showwarning("Arquivo não aceito",
                               "Arraste um arquivo real do Explorer ou use Selecionar.")
        return "break"

    def open_file_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o Arquivo Excel",
            filetypes=[("Arquivos Excel", "*.xlsx *.xlsm *.xls")],
        )
        if path:
            self.set_file(path)

    # ---------------------------------------------------------------------------
    # Conversão principal
    # ---------------------------------------------------------------------------    # ---------------------------------------------------------------------------
    # Tarefas em segundo plano (tela de carregamento)
    # ---------------------------------------------------------------------------

    def _fechar_overlay(self) -> None:
        """Fecha a tela de carregamento, se houver."""
        overlay = self._tarefa_overlay
        self._tarefa_overlay = None
        if overlay is not None:
            try:
                overlay.fechar()
            except _ERROS_TK:
                pass

    def _iniciar_tarefa(self, titulo: str, detalhe: str, funcao, ao_concluir) -> None:
        """Executa ``funcao(progresso)`` em thread com tela de carregamento.

        - ``progresso(titulo, detalhe)`` pode ser chamado da própria thread
          para atualizar o texto do overlay em tempo real.
        - ``ao_concluir(resultado)`` SEMPRE roda na thread principal, com
          ``{"ok": True, "valor": ...}`` ao concluir ou ``{"cancelada": True}``
          quando outra tarefa substitui esta antes do resultado chegar.
        """
        # Tarefa anterior ainda sem resultado entregue: encerra e avisa o dono
        cb_antiga = self._tarefa_cb
        if cb_antiga is not None:
            self._fechar_overlay()
            try:
                cb_antiga({"ok": False, "cancelada": True})
            except Exception:
                log.exception('callback da tarefa cancelada falhou')

        self._tarefa_seq += 1
        seq = self._tarefa_seq
        holder: dict = {}
        self._tarefa_holder = holder
        self._tarefa_cb = ao_concluir

        overlay = LoadingOverlay(self.root, titulo, detalhe=detalhe)
        self._tarefa_overlay = overlay
        overlay.tornar_modal()

        def progresso(titulo_fase: str, detalhe_fase: str = "") -> None:
            fase = (titulo_fase, detalhe_fase)
            holder["fase"] = fase
            holder.setdefault("fases", []).append(fase)

        def runner() -> None:
            try:
                valor = funcao(progresso)
                holder.update({"fim": True, "ok": True, "valor": valor})
            except Exception as exc:
                log.exception('tarefa em segundo plano falhou')
                holder.update({"fim": True, "ok": False, "erro": exc})

        try:
            threading.Thread(target=runner, daemon=True, name="penna-tarefa").start()
        except RuntimeError as exc:
            # Sem thread não há como processar: devolve o erro imediatamente
            self._fechar_overlay()
            self._tarefa_cb = None
            ao_concluir({"ok": False, "erro": exc})
            return

        ultima_fase: list = [None]

        def poll() -> None:
            if seq != self._tarefa_seq:
                return  # outra tarefa assumiu; o overlay novo já está no ar
            if not holder.get("fim"):
                fase = holder.get("fase")
                if fase is not None and fase != ultima_fase[0]:
                    ultima_fase[0] = fase
                    try:
                        overlay.set_mensagem(fase[0], detalhe=fase[1])
                    except _ERROS_TK:
                        pass
                try:
                    self.root.after(80, poll)
                except _ERROS_TK:
                    pass
                return
            self._fechar_overlay()
            self._tarefa_cb = None
            try:
                ao_concluir(holder)
            except Exception as exc:
                log.exception('callback de conclusao da tarefa falhou')
                self._set_status(f"Erro: {exc}", tipo="erro")

        try:
            self.root.after(80, poll)
        except _ERROS_TK:
            pass

    # ---------------------------------------------------------------------------
    # Conversão principal
    # ---------------------------------------------------------------------------

    def _tarefa_validacao(self, excel_path: Path, escolha_sigtap, progresso):
        """Pipeline único de validação (pré-validação e conversão).

        Roda dentro da thread da tarefa: lê a planilha, descobre a competência
        dos formulários, resolve a base SIGTAP e valida. Devolve
        ``(df, competencia_planilha, ocorrencias)``.
        """
        progresso("Lendo a planilha…", excel_path.name)
        df = carregar_planilha(excel_path)
        competencia_planilha = competencia_da_planilha(df)
        sigtap = self._resolver_sigtap(escolha_sigtap, competencia_planilha)
        progresso("Conferindo a consistência…",
                  "aplicando as regras APAC-MAG — pode levar alguns segundos")
        ocorrencias = validar_planilha(df, sigtap_competencia=sigtap or None)
        return df, competencia_planilha, ocorrencias

    def run_conversion(self) -> None:
        """Gate de consistência → exportação → registro de remessa.

        Validação e exportação rodam em thread com tela de carregamento;
        o diálogo "Salvar" e os retornos de UI acontecem na thread principal.
        """
        if self._conversao_ativa:
            return  # já há conversão em andamento
        try:
            verificar_configuracao()
        except ConfigInvalidaError as exc:
            self._set_status("Configuração do estabelecimento inválida. Nada foi gerado.", tipo="erro")
            messagebox.showerror(
                "Configuração inválida",
                "O penna_config.json está ausente, corrompido ou ainda com valores de "
                "fábrica. Sem ele o arquivo sairia com a identidade de outro "
                "estabelecimento, então a exportação foi bloqueada.\n\n"
                + "\n".join(f"• {p}" for p in exc.problemas)
                + "\n\nCorrija o arquivo (modelo: penna_config.example.json) e reabra o programa.",
            )
            return
        file_path = self.file_var.get().strip()
        if not file_path:
            messagebox.showwarning("Arquivo não informado",
                                   "Arraste um Excel ou selecione antes de executar.")
            return
        excel_path = Path(file_path)
        if not excel_path.exists() or excel_path.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
            messagebox.showerror("Arquivo inválido",
                                 "Selecione um arquivo Excel válido (.xlsx, .xlsm ou .xls).")
            return

        # Opções de exportação: o que o usuário marcou é o que sai
        quer_txt, quer_fichas = self._opcoes_exportacao()
        if not (quer_txt or quer_fichas):
            messagebox.showwarning(
                "Nenhuma exportação selecionada",
                "Marque o TXT, as Fichas (PDF) ou ambos em "
                "OPÇÕES DE EXPORTAÇÃO antes de executar.",
            )
            return

        self._conversao_ativa = True
        self._set_status("Conferindo a consistência da planilha...")
        escolha_sigtap = self._escolha_sigtap_manual()

        def ao_validar(res: dict) -> None:
            if res.get("cancelada"):
                self._conversao_ativa = False
                return
            if not res.get("ok"):
                self._conversao_ativa = False
                exc = res.get("erro")
                self._set_status(f"Erro ao ler a planilha: {exc}", tipo="erro")
                messagebox.showerror("Erro na leitura",
                                     f"Não foi possível ler a planilha:\n{exc}")
                return

            df, competencia_planilha, ocorrencias = res["valor"]
            n_err, n_avs = resumo_ocorrencias(ocorrencias)
            aviso_desativadas = texto_regras_desativadas(
                getattr(ocorrencias, "regras_desativadas", ()))

            if n_err > 0:
                self._montar_card_fluxo()
                self._mostrar_painel_erros(ocorrencias)
                self._set_status(
                    f"Consistência reprovada: {n_err} erro(s), {n_avs} aviso(s). Nenhum arquivo gerado."
                    + (f" {aviso_desativadas.splitlines()[0]}" if aviso_desativadas else ""),
                    tipo="erro",
                )
                self._conversao_ativa = False
                messagebox.showwarning("Consistência reprovada", MSG_BLOQUEIO.format(n_err=n_err))
                return

            # Avisos não abrem o relatório: o rodapé volta ao fluxo e o aviso
            # segue apenas no status/dialogo do fim da conversão.
            self._montar_card_fluxo()

            # Analisa de qual mês são os formularios: o mês entra no cabeçalho
            # do TXT e fixa o final do nome do arquivo (ex.: .JUN).
            competencia = competencia_planilha
            extensao = extensao_mes_competencia(competencia)
            self._anunciar_competencia(competencia)
            # Mesmo em EXECUTAR: se o mês ainda não baixou, o download da
            # base correspondente começa agora (e revalida ao concluir).
            self._sincronizar_sigtap_planilha(competencia)

            output_path = None
            if quer_txt:
                try:
                    filetypes: list[tuple[str, str]] = [("Todos os arquivos", "*.*")]
                    if extensao:
                        filetypes.insert(0, ("Arquivo TXT", "*.txt"))
                        filetypes.insert(
                            0,
                            (f"Exportação Penna — extensão do mês {extensao}", f"*{extensao}"),
                        )
                        titulo = (f"Salvar arquivo TXT — competência {competencia[:4]}/{competencia[4:6]}"
                                  f" (extensão {extensao} fixa)")
                    else:
                        filetypes.insert(0, ("Arquivo TXT", "*.txt"))
                        titulo = "Salvar arquivo TXT"
                    output_path = filedialog.asksaveasfilename(
                        title=titulo,
                        filetypes=filetypes,
                        defaultextension=extensao or ".txt",
                        initialfile=nome_saida_sugerido(excel_path, competencia),
                    )
                except (OSError, *_ERROS_TK) as exc:
                    self._conversao_ativa = False
                    self._set_status(f"Erro na conversão: {exc}", tipo="erro")
                    messagebox.showerror("Erro na conversão", f"Não foi possível gerar o TXT:\n{exc}")
                    return
                if not output_path:
                    self._conversao_ativa = False
                    self._set_status("Conversão cancelada: nenhum arquivo gerado.")
                    return

            escolhido = Path(output_path) if output_path else None

            pasta_fichas = None
            if quer_fichas:
                # Uma ficha PDF por linha da planilha: escolha da pasta destino
                try:
                    pasta_fichas = filedialog.askdirectory(
                        title="Escolha a pasta para salvar as fichas (PDF)",
                    )
                except (OSError, *_ERROS_TK) as exc:
                    self._conversao_ativa = False
                    self._set_status(f"Erro na conversão: {exc}", tipo="erro")
                    messagebox.showerror("Erro na conversão",
                                         f"Não foi possível gerar as fichas:\n{exc}")
                    return
                if not pasta_fichas:
                    self._conversao_ativa = False
                    self._set_status("Conversão cancelada: nenhum arquivo gerado.")
                    return
                pasta_fichas = Path(pasta_fichas)

            def ao_exportar(res2: dict) -> None:
                if res2.get("cancelada"):
                    self._conversao_ativa = False
                    return
                self._conversao_ativa = False
                if not res2.get("ok"):
                    exc = res2.get("erro")
                    self._set_status(f"Erro na conversão: {exc}", tipo="erro")
                    messagebox.showerror("Erro na conversão",
                                         f"Não foi possível gerar a exportação:\n{exc}")
                    return
                final_path, comprovante, demonstrativo, aviso_remessa, fichas = res2["valor"]

                rotulo_mes = ""
                if extensao:
                    rotulo_mes = f" — competência {competencia[:4]}/{competencia[4:6]}"
                # Só o que foi selecionado em OPÇÕES DE EXPORTAÇÃO aparece
                partes: list[str] = []
                if final_path is not None:
                    partes.append(final_path.name)
                if fichas:
                    partes.append(f"{len(fichas)} ficha(s) PDF")
                rotulo = " + ".join(partes) or "nenhum arquivo"
                resumo_desativadas = (f" — {aviso_desativadas.splitlines()[0]}"
                                      if aviso_desativadas else "")
                if n_avs:
                    self._set_status(
                        f"Exportação com {n_avs} aviso(s){rotulo_mes}: {rotulo}{resumo_desativadas}",
                        tipo="sucesso",
                    )
                else:
                    self._set_status(f"Exportação gerada{rotulo_mes}: {rotulo}{resumo_desativadas}",
                                     tipo="sucesso")

                mensagem = "Exportação concluída:"
                if final_path is not None:
                    mensagem += f"\n\nTXT gerado:\n{final_path}"
                    if extensao:
                        mensagem += (f"\n\nCompetência {competencia[:4]}/{competencia[4:6]} — "
                                     f"extensão {extensao} fixada pelo mês dos formulários.")
                    if escolhido is not None and final_path.name != escolhido.name:
                        mensagem += f"\nNome ajustado: {escolhido.name} → {final_path.name}"
                    if comprovante is not None:
                        mensagem += f"\n\nComprovante:\n{comprovante}"
                        if demonstrativo is not None:
                            mensagem += f"\n\nDemonstrativo:\n{demonstrativo}"
                    if aviso_remessa:
                        # A remessa nunca bloqueia a exportação, mas o aviso não
                        # pode sumir: o histórico de APACs depende dela.
                        mensagem += ("\n\nAviso: histórico de remessa não registrado "
                                     f"({aviso_remessa}).")
                if fichas:
                    mensagem += (f"\n\nFichas (PDF): {len(fichas)} arquivo(s) em:\n"
                                 f"{pasta_fichas}")
                if n_avs:
                    mensagem += f"\n\n{MSG_AVISOS.format(n_avs=n_avs)}"
                if aviso_desativadas:
                    mensagem += f"\n\n{aviso_desativadas}"
                messagebox.showinfo("Exportação concluída", mensagem)

            def tarefa_exportar(progresso) -> tuple:
                final = None
                comprovante = demonstrativo = None
                aviso_remessa = ""
                if quer_txt:
                    progresso("Gerando o TXT fiscal…",
                              f"extensão {extensao or '.txt'} — competência "
                              f"{competencia[:4]}/{competencia[4:6]}")
                    final = convert_excel_to_txt(excel_path, escolhido)
                    progresso("Registrando a remessa…",
                              "comprovante, demonstrativo e histórico")
                    try:
                        resumo_remessa = apac_mag_remessa.registrar_remessa(final, df)
                        comprovante = apac_mag_remessa.gerar_comprovante(resumo_remessa)
                        demonstrativo = apac_mag_remessa.gerar_demonstrativo(df)
                    except Exception as exc:
                        log.exception('registro da remessa falhou (exportacao segue)')
                        # remessa nunca bloqueia a exportação — mas o erro é
                        # reportado ao usuário (vira aviso na mensagem final)
                        aviso_remessa = str(exc) or type(exc).__name__
                fichas: list[Path] = []
                if quer_fichas:
                    # Uma ficha PDF por linha (layout da aba OCI do modelo)
                    progresso("Gerando as fichas em PDF…", f"{len(df)} paciente(s)")
                    fichas = apac_mag_fichas.exportar_fichas(
                        df, pasta_fichas, progresso=progresso)
                return final, comprovante, demonstrativo, str(aviso_remessa), fichas

            if quer_txt and quer_fichas:
                titulo_tarefa, detalhe_tarefa = ("Gerando TXT e fichas…",
                                                 "TXT fiscal + fichas em PDF")
            elif quer_fichas:
                titulo_tarefa, detalhe_tarefa = ("Gerando as fichas em PDF…",
                                                 f"{len(df)} ficha(s) em {pasta_fichas.name}")
            else:
                titulo_tarefa, detalhe_tarefa = ("Gerando o arquivo TXT…",
                                                 "aguarde a gravação do arquivo")

            self._iniciar_tarefa(
                titulo_tarefa,
                detalhe_tarefa,
                tarefa_exportar,
                ao_exportar,
            )

        def tarefa_validar(progresso) -> tuple:
            return self._tarefa_validacao(excel_path, escolha_sigtap, progresso)

        self._iniciar_tarefa(
            "Conferindo a consistência…",
            "validação APAC-MAG da planilha",
            tarefa_validar,
            ao_validar,
        )

    def test_load(self) -> None:
        """Valida a planilha carregada sem gerar arquivo (pré-validação).

        Roda em thread com tela de carregamento; ao concluir, o relatório
        anterior é descartado (painel só para erro bloqueante).
        """
        file_path = self.file_var.get().strip()
        if not file_path:
            return
        excel_path = Path(file_path)
        if not excel_path.exists() or excel_path.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
            return
        escolha_sigtap = self._escolha_sigtap_manual()

        def tarefa_validar(progresso) -> tuple:
            _, competencia_planilha, ocorrencias = self._tarefa_validacao(
                excel_path, escolha_sigtap, progresso)
            return competencia_planilha, ocorrencias

        def ao_concluir(res: dict) -> None:
            if res.get("cancelada"):
                return
            if not res.get("ok"):
                self._set_status(f"Erro ao ler a planilha: {res.get('erro')}", tipo="erro")
                return
            competencia_planilha, ocorrencias = res["valor"]
            n_err, n_avs = resumo_ocorrencias(ocorrencias)
            self._montar_card_fluxo()  # descarta qualquer relatório anterior
            self._anunciar_competencia(competencia_planilha)
            self._sincronizar_sigtap_planilha(competencia_planilha)
            if n_err:
                self._mostrar_painel_erros(ocorrencias)
                self._set_status(f"{n_err} erro(s) bloqueante(s): corrija antes de EXECUTAR.", tipo="erro")
            elif n_avs:
                self._set_status(f"Planilha pronta: {n_avs} aviso(s), nenhum erro bloqueante.")
            else:
                self._set_status("Planilha pronta: consistência sem erros.", tipo="sucesso")

        self._iniciar_tarefa(
            "Verificando a planilha…",
            excel_path.name,
            tarefa_validar,
            ao_concluir,
        )


# Alias de retrocompatibilidade
ApacMagApp = PennaApp


# ---------------------------------------------------------------------------
# Entry point standalone
# ---------------------------------------------------------------------------

def configurar_logging() -> None:
    """Log em arquivo (o EXE nao tem console): %LOCALAPPDATA%\PennaConversor\penna.log.

    Guarda so tracebacks de falhas inesperadas, com rotacao. Falha ao criar o
    arquivo nunca impede o programa de abrir.
    """
    pasta = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "PennaConversor"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            pasta / "penna.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger("penna")
    raiz.setLevel(logging.INFO)
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in raiz.handlers):
        raiz.addHandler(handler)


def main() -> None:
    """Inicia o Penna em modo standalone (TkinterDnD quando disponível)."""
    configurar_logging()
    root = TkinterDnD.Tk() if TkinterDnD is not None else Tk()
    app = PennaApp(root)

    if len(sys.argv) > 1:
        app.set_file(" ".join(sys.argv[1:]))
    else:
        for desktop in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"):
            candidate = desktop / "base exemplo.xlsx"
            if candidate.exists():
                app.set_file(str(candidate))
                if app.file_var.get():
                    app._set_status("base exemplo.xlsx carregado do Desktop.", tipo="sucesso")
                break

    root.mainloop()


if __name__ == "__main__":
    main()
