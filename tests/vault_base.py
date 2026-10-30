"""Un vault inicializado una vez por proceso, copiado a cada test que lo necesita.

`vault_init` cuesta entre 10 y 25 s según la carga y 37 módulos lo repetían en
cada test. Aquí se corre una vez por worker y por variante; cada test recibe una
copia suya, así que ninguno ve lo que escribió otro.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parent.parent
_BASES: Dict[Tuple[str, ...], Path] = {}


def _correr(raiz: Path, script: str, *argv: str) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{script}.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=True)


def vault_base(*proyectos: str) -> Path:
    """Raíz de un vault ya inicializado, con `proyectos` dados de alta."""
    if proyectos not in _BASES:
        raiz = Path(tempfile.mkdtemp(prefix="vault_base_")) / "vault"
        raiz.mkdir()  # con VAULT_STRICT_ROOT=1 la raíz tiene que existir
        _correr(raiz, "vault_init")
        for nombre in proyectos:
            _correr(raiz, "vault_project", "--add", nombre)
        _BASES[proyectos] = raiz
    return _BASES[proyectos]


def copiar_vault(destino: Path, *proyectos: str) -> Path:
    """Copia de la base a `destino` (que no debe existir)."""
    shutil.copytree(vault_base(*proyectos), destino)
    return destino
