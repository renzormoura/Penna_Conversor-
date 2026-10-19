"""Janela principal do Penna: monta a tela e conduz o fluxo do usuário.

A regra de negócio fica em ``penna.services`` (validação, exportação e textos) e a
execução em segundo plano em :mod:`penna.ui.tasks`; aqui só há tela e diálogos.

Fluxo: carregar a planilha -> validar (gate de consistência) -> escolher destinos
-> exportar (TXT, remessa e fichas).
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import BooleanVar, Button, Checkbutton, Entry, Frame, Label, StringVar, filedialog, messagebox
from typing import Optional

import tkinter as tk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None   # type: ignore[assignment]
    TkinterDnD = None  # type: ignore[assignment]

from penna import paths
from penna.config import ConfigInvalidaError, verificar_configuracao
from penna.layout import extensao_mes_competencia, nome_saida_sugerido
from penna.services import export as exportacao
from penna.services import validation as validacao
from penna.services.export import PlanoExportacao, ResultadoExportacao
from penna.services.files import eh_planilha_excel, formatar_tamanho_bytes, parse_dropped_path
from penna.services.messages import mensagem_exportacao, status_exportacao
from penna.services.validation import PlanilhaValidada, texto_regras_desativadas
from penna.validation import resumo as resumo_ocorrencias

from .tasks import ERROS_TK, TaskRunner
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
from .widgets.dropzone import DropZone
from .widgets.error_panel import PainelErros
from .widgets.header import HeaderCanvas
from .widgets.sigtap_selector import SigtapSelector

log = logging.getLogger("penna.ui")

STATUS_PRONTO = "Sistema pronto. Selecione ou arraste a planilha Excel."
FONTE = "Segoe UI"
COR_CAMPO_BORDA = "#cbd5e1"
COR_PASSO_FUNDO = "#fafbfc"


@dataclass
class _Execucao:
    """Estado de uma execução (validação -> destinos -> exportação)."""

    excel_path: Path
    df: object
    competencia: str
    extensao: str
    n_avs: int
    aviso_desativadas: str
    plano: PlanoExportacao


def _botao_destacado(parent, texto: str, comando, largura: int, **extra) -> Button:
    """Botão azul da marca com hover."""
    botao = Button(
        parent, text=texto, command=comando, width=largura, bg=COR_AZUL_PRINCIPAL, fg="white",
        relief="flat", cursor="hand2", activebackground=COR_AZUL_HOVER, activeforeground="white", bd=0, **extra,
    )
    botao.bind("<Enter>", lambda _: botao.configure(bg=COR_AZUL_HOVER))
    botao.bind("<Leave>", lambda _: botao.configure(bg=COR_AZUL_PRINCIPAL))
    return botao


class PennaApp:
    """Aplicação Penna.

    ``root``: widget raiz do tkinter (``Tk`` ou ``Frame``). ``embed``: ``True`` quando
    montada dentro de um shell externo (sem cabeçalho nem janela própria).
    """

    def __init__(self, root, embed: bool = False) -> None:
        self.embed = embed
        self.root = root
        self.drop_label: DropZone | None = None
        self._conversao_ativa = False
        self._painel_erros: PainelErros | None = None
        self._tasks = TaskRunner(root, lambda msg: self._set_status(msg, tipo="erro"))

        self._configurar_janela()
        self.file_var = StringVar(value="")
        self.status_var = StringVar(value=STATUS_PRONTO)

        if not embed:
            self.header = HeaderCanvas(root)
            self.header.pack(fill="x")
        self._construir_barra_de_status()
        card = self._construir_card()
        self._construir_dropzone(card)
        self._construir_campo_arquivo(card)
        self._construir_seletor_sigtap(card)
        self._construir_opcoes_exportacao(card)
        self._construir_acao(card)
        self._container_rodape = Frame(card, bg=COR_CARD)
        self._container_rodape.pack(fill="x", pady=(4, 0))
        self._montar_card_fluxo()
        self._registrar_atalhos()

        if not embed:
            self.root.after(150, self.try_load_argument_file)

    # ------------------------------------------------------------------ tela

    def _configurar_janela(self) -> None:
        self.root.configure(bg=COR_FUNDO)
        if self.embed:
            return
        self.root.title(WINDOW_TITLE)
        self.root.geometry("780x640")
        self.root.minsize(700, 560)
        self._aplicar_icone_janela()

    def _aplicar_icone_janela(self) -> None:
        raiz = paths.project_root()
        for nome in ("penna.ico", "apac_icon.ico"):
            if (raiz / nome).exists():
                try:
                    self.root.iconbitmap(default=str(raiz / nome))
                    break
                except ERROS_TK:
                    pass
        for nome in ("penna.png", "penna_header.png", "penna.icon.png", "apac_icon_header.png", "apac_icon.png"):
            if (raiz / nome).exists():
                try:
                    self._window_icon_photo = tk.PhotoImage(file=str(raiz / nome))
                    self.root.iconphoto(True, self._window_icon_photo)
                    return
                except ERROS_TK:
                    pass

    def _construir_barra_de_status(self) -> None:
        self.status_bar = Frame(self.root, bg=COR_BRANCO, height=32,
                                highlightthickness=1, highlightbackground=COR_BORDA, bd=0)
        self.status_bar.pack(side="bottom", fill="x")
        interno = Frame(self.status_bar, bg=COR_BRANCO)
        interno.pack(fill="both", expand=True, padx=20, pady=5)
        self.status_dot = tk.Canvas(interno, width=12, height=12, bg=COR_BRANCO, highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self._dot_item = self.status_dot.create_oval(2, 2, 10, 10, fill=COR_AZUL_PRINCIPAL, outline="")
        self.status_label = Label(interno, textvariable=self.status_var, bg=COR_BRANCO,
                                  fg=COR_TEXTO_CORPO, font=(FONTE, 9), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        Label(interno, text="Padrão Penna / SUS • Layout Fixo • Consistência APAC-MAG",
              bg=COR_BRANCO, fg=COR_TEXTO_HINT, font=(FONTE, 8), anchor="e").pack(side="right")

    def _construir_card(self) -> Frame:
        card = Frame(self.root, bg=COR_CARD, highlightthickness=1, highlightbackground=COR_BORDA,
                     bd=0, padx=24, pady=20)
        card.pack(fill="both", expand=True, padx=24, pady=(16, 12))
        return card

    def _construir_dropzone(self, card: Frame) -> None:
        texto = DROP_HINT if DND_FILES is not None else "Arraste ou clique para selecionar o arquivo Excel"
        self.drop_label = DropZone(card, texto, on_click_callback=self.open_file_dialog)
        self.drop_label.pack(fill="x", pady=(0, 16))
        self._registrar_dnd()

    def _construir_campo_arquivo(self, card: Frame) -> None:
        campo = Frame(card, bg=COR_CARD)
        campo.pack(fill="x", pady=(0, 14))
        Label(campo, text="ARQUIVO EXCEL SELECIONADO:", bg=COR_CARD, fg=COR_TEXTO_CORPO,
              font=(FONTE, 8, "bold")).pack(anchor="w", pady=(0, 4))
        linha = Frame(campo, bg=COR_CARD)
        linha.pack(fill="x")
        self.path_entry = Entry(linha, textvariable=self.file_var, font=(FONTE, 10), relief="flat", bd=0,
                                highlightthickness=1, highlightbackground=COR_CAMPO_BORDA,
                                highlightcolor=COR_AZUL_PRINCIPAL, bg=COR_BRANCO, fg=COR_TEXTO_TITULO)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 10))
        self.path_entry.bind("<FocusIn>", lambda _: self.path_entry.configure(highlightbackground=COR_AZUL_PRINCIPAL))
        self.path_entry.bind("<FocusOut>", lambda _: self.path_entry.configure(highlightbackground=COR_CAMPO_BORDA))

        _botao_destacado(linha, "Selecionar", self.open_file_dialog, 12,
                         font=(FONTE, 9, "bold")).pack(side="left", ipady=5)
        colar = Button(linha, text="Colar caminho", command=self.paste_path_from_clipboard, width=13,
                       bg=COR_FUNDO, fg=COR_TEXTO_CORPO, relief="flat", cursor="hand2",
                       font=(FONTE, 9, "bold"), activebackground=COR_BORDA, activeforeground=COR_TEXTO_CORPO,
                       bd=0, highlightthickness=1, highlightbackground=COR_CAMPO_BORDA)
        colar.pack(side="left", padx=(10, 0), ipady=5)
        colar.bind("<Enter>", lambda _: colar.configure(bg="#edf2f7"))
        colar.bind("<Leave>", lambda _: colar.configure(bg=COR_FUNDO))

    def _construir_seletor_sigtap(self, card: Frame) -> None:
        moldura = Frame(card, bg=COR_CARD)
        moldura.pack(fill="x", pady=(0, 10))
        self.sigtap_sel = SigtapSelector(moldura, on_change=self._on_sigtap_change)
        self.sigtap_sel.pack(side="left")

    def _construir_opcoes_exportacao(self, card: Frame) -> None:
        """O usuário escolhe o que sai no EXECUTAR: só TXT, só fichas (PDF) ou ambos."""
        moldura = Frame(card, bg=COR_CARD)
        moldura.pack(fill="x", pady=(0, 10))
        Label(moldura, text="OPÇÕES DE EXPORTAÇÃO:", bg=COR_CARD, fg=COR_TEXTO_CORPO,
              font=(FONTE, 9, "bold")).pack(side="left", padx=(0, 14))
        self.var_exportar_txt = BooleanVar(value=True)
        self.var_exportar_fichas = BooleanVar(value=True)
        for rotulo, variavel in (("TXT fiscal", self.var_exportar_txt), ("Fichas (PDF)", self.var_exportar_fichas)):
            Checkbutton(
                moldura, text=rotulo, variable=variavel, bg=COR_CARD, fg=COR_TEXTO_CORPO,
                activebackground=COR_CARD, activeforeground=COR_AZUL_PRINCIPAL, selectcolor=COR_BRANCO,
                font=(FONTE, 9), cursor="hand2", relief="flat", bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))

    def _construir_acao(self, card: Frame) -> None:
        moldura = Frame(card, bg=COR_CARD)
        moldura.pack(fill="x", pady=(4, 16))
        Label(moldura, text="O nome do arquivo é livre; a extensão do mês\n(ex.: .JUN) é fixada pela competência detectada.",
              bg=COR_CARD, fg=COR_TEXTO_MEDIO, font=(FONTE, 8, "italic"), justify="left").pack(side="left")
        executar = _botao_destacado(moldura, "EXECUTAR", self.run_conversion, 18,
                                    font=(FONTE, 11, "bold"), padx=20, pady=8)
        executar.configure(activebackground=COR_AZUL_ACTIVE)
        executar.pack(side="right")

    def _registrar_atalhos(self) -> None:
        alvo = self.root.winfo_toplevel() if self.embed else self.root

        def ctrl_o(_=None):
            if self.embed and not self.root.winfo_ismapped():
                return None
            self.open_file_dialog()
            return "break"

        alvo.bind("<Control-o>", ctrl_o)

    def _registrar_dnd(self) -> None:
        if DND_FILES is None or self.drop_label is None:
            if self.drop_label is not None:
                self.drop_label.configure(text="Clique aqui para selecionar a planilha Excel")
            return
        if self.embed:
            try:
                TkinterDnD._require(self.root.winfo_toplevel())
            except (*ERROS_TK, AttributeError):
                pass
        for alvo in (self.root, self.drop_label):
            try:
                alvo.drop_target_register(DND_FILES)
                alvo.dnd_bind("<<Drop>>", self.on_drop)
                alvo.dnd_bind("<<DragEnter>>", self.on_drag_enter)
                alvo.dnd_bind("<<DragLeave>>", self.on_drag_leave)
            except (*ERROS_TK, AttributeError):
                pass

    # ------------------------------------------------------- rodapé do card

    def _montar_card_fluxo(self) -> None:
        for filho in self._container_rodape.winfo_children():
            filho.destroy()
        self._painel_erros = None

        moldura = Frame(self._container_rodape, bg=COR_PASSO_FUNDO,
                        highlightthickness=1, highlightbackground=COR_BORDA, bd=0)
        moldura.pack(fill="x")
        cabecalho = Frame(moldura, bg=COR_PASSO_FUNDO)
        cabecalho.pack(fill="x", padx=16, pady=(10, 8))
        Label(cabecalho, text="FLUXO DE OPERAÇÃO", font=(FONTE, 8, "bold"),
              fg=COR_AZUL_PRINCIPAL, bg=COR_PASSO_FUNDO).pack(side="left")

        passos = Frame(moldura, bg=COR_PASSO_FUNDO)
        passos.pack(fill="x", padx=12, pady=(0, 12))
        for numero, titulo, descricao in (
            ("1", "Carregar", "Arraste a planilha ou clique em Selecionar."),
            ("2", "Conferir", "Verifique o caminho completo exibido."),
            ("3", "Executar", "Marque TXT e/ou Fichas (PDF) e clique em EXECUTAR."),
            ("4", "Exportar", "TXT: escolha o nome (extensão do mês é automática); fichas: escolha a pasta."),
        ):
            coluna = Frame(passos, bg=COR_PASSO_FUNDO)
            coluna.pack(side="left", fill="both", expand=True, padx=4)
            topo = Frame(coluna, bg=COR_PASSO_FUNDO)
            topo.pack(anchor="w")
            Label(topo, text=numero, font=(FONTE, 8, "bold"), fg=COR_AZUL_PRINCIPAL,
                  bg=COR_AZUL_TINT, width=2, height=1).pack(side="left", padx=(0, 6))
            Label(topo, text=titulo, font=(FONTE, 8, "bold"), fg=COR_TEXTO_TITULO,
                  bg=COR_PASSO_FUNDO).pack(side="left")
            Label(coluna, text=descricao, font=(FONTE, 8), fg=COR_TEXTO_MEDIO, bg=COR_PASSO_FUNDO,
                  justify="left", wraplength=145).pack(anchor="w", pady=(3, 0))

    def _mostrar_painel_erros(self, ocorrencias) -> None:
        self._painel_erros = PainelErros(self._container_rodape, ocorrencias, ao_fechar=self._montar_card_fluxo)
        self._painel_erros.pack(fill="x")

    def _set_status(self, mensagem: str, tipo: str = "info") -> None:
        cor_ponto, cor_texto = {
            "sucesso": (COR_SUCESSO, COR_SUCESSO),
            "erro": (COR_ERRO, COR_ERRO),
        }.get(tipo, (COR_AZUL_PRINCIPAL, COR_TEXTO_CORPO))
        self.status_var.set(mensagem)
        self.status_dot.itemconfig(self._dot_item, fill=cor_ponto)
        self.status_label.configure(fg=cor_texto)

    def _anunciar_competencia(self, competencia: str) -> None:
        """Mostra no cabeçalho da janela o mês analisado nos formulários."""
        header = getattr(self, "header", None)
        if header is None or not competencia:
            return
        texto = f"COMPETÊNCIA {competencia[:4]}/{competencia[4:6]}"
        extensao = extensao_mes_competencia(competencia)
        if extensao:
            texto += f" • {extensao[1:]}"
        try:
            header.set_competencia(texto)
        except ERROS_TK:
            pass

    # --------------------------------------------------------------- SIGTAP

    def _sincronizar_sigtap_planilha(self, competencia: str) -> None:
        """Automático: o seletor foca e baixa a base do mês da planilha.

        Sem isto, planilha de um mês diferente seguiria validada nas bases locais
        de outro mês, e ninguém baixaria o mês correspondente. Erros do seletor
        nunca derrubam a validação nem a exportação.
        """
        seletor = getattr(self, "sigtap_sel", None)
        if seletor is None or not competencia:
            return
        try:
            seletor.sincronizar_com_planilha(competencia)
        except Exception:  # noqa: BLE001  fronteira: o seletor nunca derruba o fluxo
            log.exception("falha ao sincronizar o seletor SIGTAP com a planilha")

    def _on_sigtap_change(self, competencia: str) -> None:
        """O seletor mudou a competência (ou o download concluiu): revalida a planilha carregada."""
        caminho = self.file_var.get().strip()
        # nunca no meio de uma conversão, para não abortar o TXT
        if caminho and Path(caminho).exists() and not self._conversao_ativa:
            self.test_load()

    def _escolha_sigtap_manual(self) -> str:
        """Competência escolhida no combobox (somente na thread principal)."""
        try:
            return self.sigtap_sel.get_competencia()
        except (*ERROS_TK, AttributeError):
            return ""

    def _opcoes_exportacao(self) -> tuple:
        """``(TXT, Fichas PDF)`` marcados; objetos sem as variáveis caem em só TXT."""
        try:
            return bool(self.var_exportar_txt.get()), bool(self.var_exportar_fichas.get())
        except (*ERROS_TK, AttributeError):
            return True, False

    # ------------------------------------------------------ eventos de arquivo

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
            atual = self.file_var.get()
            if atual:
                self.drop_label.set_state_loaded(Path(atual).name)
            else:
                self.drop_label.set_state_idle()
        self._set_status(STATUS_PRONTO)
        return "break"

    def set_file(self, file_path: str) -> None:
        file_path = parse_dropped_path(file_path)
        if not file_path:
            return
        if not os.path.exists(file_path):
            messagebox.showerror("Arquivo inválido", "Selecione um arquivo Excel válido.")
            return
        self.file_var.set(file_path)
        header = getattr(self, "header", None)
        if header is not None:  # nova planilha: o mês anunciado será o dela
            try:
                header.set_competencia("")
            except ERROS_TK:
                pass
        nome = Path(file_path).name
        try:
            tamanho = formatar_tamanho_bytes(os.path.getsize(file_path))
        except OSError:
            tamanho = ""
        # Relatório anterior descartado; o sistema valida sozinho e só abre painel em erro bloqueante.
        self._montar_card_fluxo()
        self._set_status(f"Arquivo carregado: {nome}", tipo="sucesso")
        if self.drop_label is not None:
            try:
                self.drop_label.set_state_loaded(nome, tamanho)
            except ERROS_TK:
                pass
        self.test_load()

    def paste_path_from_clipboard(self) -> None:
        try:
            self.set_file(self.root.clipboard_get())
            if self.file_var.get():
                self._set_status("Caminho colado com sucesso.", tipo="sucesso")
        except Exception:  # noqa: BLE001  fronteira: qualquer falha vira aviso ao usuário
            log.exception("falha ao colar o caminho da area de transferencia")
            messagebox.showwarning("Sem caminho", "Nenhum caminho válido na área de transferência.")

    def on_drop(self, event) -> str:
        try:
            bruto = getattr(event, "data", "")
            widget = getattr(event, "widget", None)
            if not bruto and widget is not None and hasattr(widget, "selection_get"):
                try:
                    bruto = widget.selection_get()
                except ERROS_TK:
                    pass
            if not bruto and len(sys.argv) > 1:
                bruto = " ".join(sys.argv[1:])
            if isinstance(bruto, (list, tuple)):
                bruto = " ".join(str(p) for p in bruto)
            if not bruto:
                self._set_status("Nenhum arquivo recebido no arraste.", tipo="erro")
                return "break"
            caminho = parse_dropped_path(bruto)
            if not caminho:
                limpo = bruto.strip().strip("{}\"'").replace("/", "\\").replace("\\\\", "\\")
                if os.path.exists(limpo):
                    caminho = limpo
            if caminho:
                self.set_file(caminho)
                return "break"
        except Exception:  # noqa: BLE001  fronteira de evento de arrastar-e-soltar
            log.exception("falha ao tratar o arquivo solto na janela")
        messagebox.showwarning("Arquivo não aceito", "Arraste um arquivo real do Explorer ou use Selecionar.")
        return "break"

    def open_file_dialog(self) -> None:
        escolhido = filedialog.askopenfilename(
            title="Selecione o Arquivo Excel",
            filetypes=[("Arquivos Excel", "*.xlsx *.xlsm *.xls")],
        )
        if escolhido:
            self.set_file(escolhido)

    # ---------------------------------------------------------------- tarefas

    def _iniciar_tarefa(self, titulo: str, detalhe: str, funcao, ao_concluir) -> None:
        """Executa ``funcao(progresso)`` em thread com tela de carregamento (ver ``TaskRunner``)."""
        self._tasks.iniciar(titulo, detalhe, funcao, ao_concluir)

    def test_load(self) -> None:
        """Pré-validação da planilha carregada, sem gerar arquivo: painel só para erro bloqueante."""
        caminho = self.file_var.get().strip()
        if not caminho:
            return
        excel_path = Path(caminho)
        if not eh_planilha_excel(excel_path):
            return
        escolha = self._escolha_sigtap_manual()

        def ao_concluir(res: dict) -> None:
            if res.get("cancelada"):
                return
            if not res.get("ok"):
                self._set_status(f"Erro ao ler a planilha: {res.get('erro')}", tipo="erro")
                return
            validada: PlanilhaValidada = res["valor"]
            n_err, n_avs = resumo_ocorrencias(validada.ocorrencias)
            self._montar_card_fluxo()  # descarta qualquer relatório anterior
            self._anunciar_competencia(validada.competencia)
            self._sincronizar_sigtap_planilha(validada.competencia)
            if n_err:
                self._mostrar_painel_erros(validada.ocorrencias)
                self._set_status(f"{n_err} erro(s) bloqueante(s): corrija antes de EXECUTAR.", tipo="erro")
            elif n_avs:
                self._set_status(f"Planilha pronta: {n_avs} aviso(s), nenhum erro bloqueante.")
            else:
                self._set_status("Planilha pronta: consistência sem erros.", tipo="sucesso")

        self._iniciar_tarefa(
            "Verificando a planilha…", excel_path.name,
            lambda progresso: validacao.validar_arquivo(excel_path, escolha, progresso),
            ao_concluir,
        )

    # --------------------------------------------------------------- EXECUTAR

    def _configuracao_ok(self) -> bool:
        """Gate de configuração: sem identidade do estabelecimento nada é gerado."""
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
            return False
        return True

    def _planilha_escolhida(self) -> Optional[Path]:
        """Caminho da planilha se estiver tudo certo para executar; senão avisa e devolve ``None``."""
        caminho = self.file_var.get().strip()
        if not caminho:
            messagebox.showwarning("Arquivo não informado", "Arraste um Excel ou selecione antes de executar.")
            return None
        excel_path = Path(caminho)
        if not eh_planilha_excel(excel_path):
            messagebox.showerror("Arquivo inválido", "Selecione um arquivo Excel válido (.xlsx, .xlsm ou .xls).")
            return None
        return excel_path

    def run_conversion(self) -> None:
        """Gate de consistência -> exportação -> registro de remessa.

        Validação e exportação rodam em thread com tela de carregamento; os diálogos
        e os retornos de UI acontecem na thread principal.
        """
        if self._conversao_ativa:
            return
        if not self._configuracao_ok():
            return
        excel_path = self._planilha_escolhida()
        if excel_path is None:
            return
        quer_txt, quer_fichas = self._opcoes_exportacao()
        if not (quer_txt or quer_fichas):
            messagebox.showwarning(
                "Nenhuma exportação selecionada",
                "Marque o TXT, as Fichas (PDF) ou ambos em OPÇÕES DE EXPORTAÇÃO antes de executar.",
            )
            return

        self._conversao_ativa = True
        self._set_status("Conferindo a consistência da planilha...")
        escolha = self._escolha_sigtap_manual()
        self._iniciar_tarefa(
            "Conferindo a consistência…", "validação APAC-MAG da planilha",
            lambda progresso: validacao.validar_arquivo(excel_path, escolha, progresso),
            lambda res: self._ao_validar(res, excel_path, quer_txt, quer_fichas),
        )

    def _ao_validar(self, res: dict, excel_path: Path, quer_txt: bool, quer_fichas: bool) -> None:
        if res.get("cancelada"):
            self._conversao_ativa = False
            return
        if not res.get("ok"):
            self._conversao_ativa = False
            erro = res.get("erro")
            self._set_status(f"Erro ao ler a planilha: {erro}", tipo="erro")
            messagebox.showerror("Erro na leitura", f"Não foi possível ler a planilha:\n{erro}")
            return

        validada: PlanilhaValidada = res["valor"]
        n_err, n_avs = resumo_ocorrencias(validada.ocorrencias)
        aviso_desativadas = texto_regras_desativadas(getattr(validada.ocorrencias, "regras_desativadas", ()))

        if n_err > 0:
            self._montar_card_fluxo()
            self._mostrar_painel_erros(validada.ocorrencias)
            resumo_desativadas = f" {aviso_desativadas.splitlines()[0]}" if aviso_desativadas else ""
            self._set_status(
                f"Consistência reprovada: {n_err} erro(s), {n_avs} aviso(s). Nenhum arquivo gerado.{resumo_desativadas}",
                tipo="erro",
            )
            self._conversao_ativa = False
            messagebox.showwarning("Consistência reprovada", MSG_BLOQUEIO.format(n_err=n_err))
            return

        # Avisos não abrem o relatório: o rodapé volta ao fluxo e eles seguem no status e no diálogo final.
        self._montar_card_fluxo()
        competencia = validada.competencia
        extensao = extensao_mes_competencia(competencia)
        self._anunciar_competencia(competencia)
        # Mesmo em EXECUTAR: se o mês ainda não baixou, o download começa agora (e revalida ao concluir).
        self._sincronizar_sigtap_planilha(competencia)

        plano = self._perguntar_destinos(excel_path, competencia, extensao, quer_txt, quer_fichas)
        if plano is None:
            return
        self._exportar(_Execucao(excel_path, validada.df, competencia, extensao, n_avs, aviso_desativadas, plano))

    def _cancelar_execucao(self, mensagem: str, tipo: str = "info") -> None:
        self._conversao_ativa = False
        self._set_status(mensagem, tipo=tipo)

    def _pedir_destino_txt(self, excel_path: Path, competencia: str, extensao: str) -> str:
        tipos = [("Arquivo TXT", "*.txt"), ("Todos os arquivos", "*.*")]
        if extensao:
            tipos.insert(0, (f"Exportação Penna — extensão do mês {extensao}", f"*{extensao}"))
            titulo = (f"Salvar arquivo TXT — competência {competencia[:4]}/{competencia[4:6]}"
                      f" (extensão {extensao} fixa)")
        else:
            titulo = "Salvar arquivo TXT"
        return filedialog.asksaveasfilename(
            title=titulo, filetypes=tipos, defaultextension=extensao or ".txt",
            initialfile=nome_saida_sugerido(excel_path, competencia),
        )

    def _perguntar_destinos(self, excel_path: Path, competencia: str, extensao: str,
                            quer_txt: bool, quer_fichas: bool) -> Optional[PlanoExportacao]:
        """Diálogos de destino (TXT e pasta das fichas); ``None`` se o usuário cancelar ou falhar."""
        destino_txt: Optional[Path] = None
        if quer_txt:
            try:
                escolhido = self._pedir_destino_txt(excel_path, competencia, extensao)
            except (OSError, *ERROS_TK) as exc:
                self._cancelar_execucao(f"Erro na conversão: {exc}", tipo="erro")
                messagebox.showerror("Erro na conversão", f"Não foi possível gerar o TXT:\n{exc}")
                return None
            if not escolhido:
                self._cancelar_execucao("Conversão cancelada: nenhum arquivo gerado.")
                return None
            destino_txt = Path(escolhido)

        pasta_fichas: Optional[Path] = None
        if quer_fichas:
            try:  # uma ficha PDF por linha da planilha: escolha da pasta destino
                escolhida = filedialog.askdirectory(title="Escolha a pasta para salvar as fichas (PDF)")
            except (OSError, *ERROS_TK) as exc:
                self._cancelar_execucao(f"Erro na conversão: {exc}", tipo="erro")
                messagebox.showerror("Erro na conversão", f"Não foi possível gerar as fichas:\n{exc}")
                return None
            if not escolhida:
                self._cancelar_execucao("Conversão cancelada: nenhum arquivo gerado.")
                return None
            pasta_fichas = Path(escolhida)
        return PlanoExportacao(quer_txt, quer_fichas, destino_txt, pasta_fichas)

    def _exportar(self, exe: _Execucao) -> None:
        plano = exe.plano
        if plano.txt and plano.fichas:
            titulo, detalhe = "Gerando TXT e fichas…", "TXT fiscal + fichas em PDF"
        elif plano.fichas:
            titulo, detalhe = "Gerando as fichas em PDF…", f"{len(exe.df)} ficha(s) em {plano.pasta_fichas.name}"
        else:
            titulo, detalhe = "Gerando o arquivo TXT…", "aguarde a gravação do arquivo"
        self._iniciar_tarefa(
            titulo, detalhe,
            lambda progresso: exportacao.exportar(
                exe.df, exe.excel_path, plano, exe.competencia, exe.extensao, progresso),
            lambda res: self._ao_exportar(res, exe),
        )

    def _ao_exportar(self, res: dict, exe: _Execucao) -> None:
        self._conversao_ativa = False
        if res.get("cancelada"):
            return
        if not res.get("ok"):
            erro = res.get("erro")
            self._set_status(f"Erro na conversão: {erro}", tipo="erro")
            messagebox.showerror("Erro na conversão", f"Não foi possível gerar a exportação:\n{erro}")
            return
        resultado: ResultadoExportacao = res["valor"]
        self._set_status(
            status_exportacao(resultado, exe.n_avs, exe.competencia, exe.extensao, exe.aviso_desativadas),
            tipo="sucesso",
        )
        messagebox.showinfo(
            "Exportação concluída",
            mensagem_exportacao(
                resultado, exe.n_avs, exe.competencia, exe.extensao,
                exe.plano.destino_txt, exe.plano.pasta_fichas, exe.aviso_desativadas, MSG_AVISOS,
            ),
        )

