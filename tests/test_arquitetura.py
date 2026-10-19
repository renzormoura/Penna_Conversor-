"""Regras de dependência entre os pacotes de ``penna`` (a arquitetura, executável).

Cada pacote só pode importar dos pacotes listados abaixo; qualquer import novo fora
da lista quebra este teste. A direção é sempre das camadas altas para as baixas.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "src" / "penna"

# pacote -> pacotes de penna que ele pode importar (além dele mesmo)
PERMITIDO = {
    "paths": set(),
    "core": set(),
    "config": {"paths", "core"},
    "reference": {"paths"},
    "layout": {"config", "core"},
    "validation": {"config", "core", "layout", "reference", "remittance"},
    "remittance": {"config", "core", "layout", "reference", "paths"},
    "cards": {"config", "paths", "reference"},
    "services": {"cards", "layout", "reference", "remittance", "validation"},
    "ui": {"config", "layout", "paths", "services", "validation", "reference"},
}


def _pacote_de(arquivo: Path) -> str:
    rel = arquivo.relative_to(RAIZ)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _imports_de_penna(arquivo: Path) -> set:
    """Pacotes de primeiro nível de ``penna`` importados no arquivo (inclusive tardios)."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    destinos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            partes = no.module.split(".")
            if partes[0] == "penna":
                if len(partes) > 1:
                    destinos.add(partes[1])
                else:  # from penna import config, paths, ...
                    destinos.update(alias.name for alias in no.names)
        elif isinstance(no, ast.Import):
            for alias in no.names:
                partes = alias.name.split(".")
                if partes[0] == "penna" and len(partes) > 1:
                    destinos.add(partes[1])
    return destinos


class TestDirecaoDasDependencias(unittest.TestCase):
    def test_todo_pacote_esta_declarado(self):
        existentes = {_pacote_de(a) for a in RAIZ.rglob("*.py") if a.stem not in ("__init__", "__main__")
                      or a.parent != RAIZ}
        existentes -= {"__main__"}
        self.assertLessEqual(existentes, set(PERMITIDO), "pacote novo sem regra de dependência")

    def test_imports_respeitam_as_camadas(self):
        violacoes = []
        for arquivo in sorted(RAIZ.rglob("*.py")):
            pacote = _pacote_de(arquivo)
            if pacote not in PERMITIDO:
                continue
            for destino in _imports_de_penna(arquivo) - {pacote}:
                if destino not in PERMITIDO[pacote]:
                    violacoes.append(f"{arquivo.relative_to(RAIZ)} importa penna.{destino}")
        self.assertEqual(violacoes, [])

    def test_nucleo_nao_depende_de_tk_nem_de_pandas(self):
        for arquivo in (RAIZ / "core").rglob("*.py"):
            fonte = arquivo.read_text(encoding="utf-8")
            for proibido in ("tkinter", "pandas", "openpyxl", "reportlab"):
                self.assertNotIn(f"import {proibido}", fonte, f"{arquivo.name} importa {proibido}")


if __name__ == "__main__":
    unittest.main()
