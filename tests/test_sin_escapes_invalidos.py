"""Ningún fuente Python del repo lleva una secuencia de escape inválida.

Hoy es un `SyntaxWarning` que se imprime en cada commit y nadie lee; Python lo
anuncia como `SyntaxError` futuro, y entonces el módulo dejaría de importarse en
la máquina de quien lo instale. Se coló en un docstring que citaba un regex.
"""

import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CARPETAS = ("scripts", "tests", "vault", "cli", "vault_toolkit", "mcp")


def _fuentes():
    for carpeta in CARPETAS:
        yield from sorted((REPO_ROOT / carpeta).rglob("*.py"))


def test_ningun_fuente_tiene_escapes_invalidos():
    rotos = []
    for ruta in _fuentes():
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            try:
                compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec")
            except SyntaxError as exc:
                rotos.append(f"{ruta.relative_to(REPO_ROOT).as_posix()}:{exc.lineno} {exc.msg}")
    assert rotos == []
