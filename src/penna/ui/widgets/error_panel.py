"""Listagem RCONSIST rolável, com controle de tamanho da fonte."""
from __future__ import annotations

import tkinter as tk
from tkinter import TclError
from tkinter import Button, Frame, Label

from ..theme import (
    COR_CARD,
    COR_ERRO,
    COR_ERRO_BG,
    COR_SUCESSO,
    COR_SUCESSO_BG,
    COR_TEXTO_CORPO,
    COR_TEXTO_MEDIO,
)


class PainelErros(tk.Frame):
    """Listagem de ocorrências no formato RCONSIST com rolamento por roda do mouse.

    Exibida NO LUGAR do card de fluxo quando a planilha tem inconsistências.
    ERR = vermelho (bloqueia exportação), AVS = laranja (apenas aviso).
    """

    TAM_FONTE_INI = 9
    ALTURA_LINHA  = 22

    def __init__(self, master, ocorrencias, ao_fechar=None, fonte_tamanho: int = 9) -> None:
        # Importação local para evitar dependência circular no nível de módulo
        from penna.validation import resumo as resumo_ocorrencias

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
        except (TclError, RuntimeError):
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
                    except (TclError, RuntimeError):
                        pass

    def focus_set(self):
        self.canvas.focus_set()
        return super().focus_set()
