"""Caso de uso: ler a planilha e validá-la (pré-validação e etapa inicial da exportação)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from penna.layout import carregar_planilha, competencia_da_planilha
from penna.reference import sigtap
from penna.validation import ResultadoValidacao, validar_planilha

Progresso = Callable[[str, str], None]


@dataclass(frozen=True)
class PlanilhaValidada:
    """Planilha lida, a competência dos formulários e o relatório de consistência."""

    df: Any
    competencia: str
    ocorrencias: ResultadoValidacao


def resolver_sigtap(escolhido: str, competencia_planilha: str = "") -> str:
    """Competência SIGTAP a usar, sem tocar na UI (segura em thread).

    - seleção manual: exatamente o que o usuário escolheu;
    - Automático: o ZIP do mês da planilha, se já estiver em cache, para evitar
      o fallback ao mês anterior dos DBF locais.
    """
    if escolhido:
        return escolhido
    if not competencia_planilha:
        return ""
    try:
        em_cache = sigtap.listar_competencias_cache()
    except OSError:  # pasta de cache inacessível: segue com as bases locais
        return ""
    return competencia_planilha if competencia_planilha in em_cache else ""


def validar_arquivo(excel_path: Path, escolha_sigtap: str, progresso: Progresso) -> PlanilhaValidada:
    """Lê a planilha, descobre a competência, resolve a base SIGTAP e valida.

    Roda dentro da thread da tarefa; ``progresso(titulo, detalhe)`` atualiza a tela de carregamento.
    """
    progresso("Lendo a planilha…", excel_path.name)
    df = carregar_planilha(excel_path)
    competencia = competencia_da_planilha(df)
    sigtap = resolver_sigtap(escolha_sigtap, competencia)
    progresso("Conferindo a consistência…", "aplicando as regras APAC-MAG — pode levar alguns segundos")
    return PlanilhaValidada(df, competencia, validar_planilha(df, sigtap_competencia=sigtap or None))


def texto_regras_desativadas(regras: Iterable[str] | None) -> str:
    """Aviso de validação parcial (``""`` quando todas as regras rodaram).

    Primeira linha: resumo curto (status); as demais listam as regras que ficaram de fora.
    """
    regras = list(regras or ())
    if not regras:
        return ""
    plural = "regras desativadas" if len(regras) != 1 else "regra desativada"
    return f"{len(regras)} {plural} nesta validação (base ausente).\n" + "\n".join(f"• {r}" for r in regras)
