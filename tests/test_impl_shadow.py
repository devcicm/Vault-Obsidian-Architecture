"""Test: _impl se prefiere sobre vault_io.py falso en CWD.

El test construye el escenario en tmp_path: copia _impl/vault_io.py stub,
coloca un vault_io.py espurio en el CWD, y verifica que import_toolkit_module
carga desde _impl y no desde el CWD.

Solo se activa cuando vault_toolkit/_impl/vault_io.py existe (wheel instalada).
En source checkout se hace skip.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_impl_preferred_over_fake_cwd_vault_io(tmp_path):
    """Un vault_io.py falso en CWD no se carga cuando _impl/vault_io.py existe."""
    impl_vault_io = REPO_ROOT / "vault_toolkit" / "_impl" / "vault_io.py"

    if not impl_vault_io.exists():
        pytest.skip(f"_impl/vault_io.py no existe (source checkout): {impl_vault_io}")

    vault_toolkit = tmp_path / "vault_toolkit"
    vault_toolkit.mkdir()
    impl_dir = vault_toolkit / "_impl"
    impl_dir.mkdir()

    loading_src = REPO_ROOT / "vault_toolkit" / "loading.py"
    (vault_toolkit / "loading.py").write_text(
        loading_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (impl_dir / "vault_io.py").write_text(
        "STUB = 'from_impl'\nFAUX = 'NO_FAUX'\n",
        encoding="utf-8",
    )
    faux = tmp_path / "vault_io.py"
    faux.write_text(
        "FAUX = 'from_cwd'\nSTUB = 'NO_STUB'\n",
        encoding="utf-8",
    )

    tmp_path_str = str(tmp_path)

    code = (
        f"import sys; "
        f"sys.path.insert(0, {tmp_path_str!r}); "
        f"from vault_toolkit.loading import import_toolkit_module; "
        f"m = import_toolkit_module('vault_io', legacy_scripts=None); "
        f"print('file:', m.__file__, end=' '); "
        f"print('STUB:', getattr(m, 'STUB', 'NO_STUB'), end=''); "
        f"print('FAUX:', getattr(m, 'FAUX', 'NO_FAUX'), end='')"
    )

    env = {**__import__("os").environ}
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path_str,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = result.stdout.strip()
    assert "from_implNO_FAUX" in output, (
        f"esperado 'from_implNO_FAUX', obtenido {output!r}. "
        f"El modulo se cargo desde {tmp_path}/vault_io.py (CWD) en vez de "
        f"{tmp_path}/vault_toolkit/_impl/vault_io.py"
    )
