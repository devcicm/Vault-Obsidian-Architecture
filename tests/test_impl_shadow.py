"""Test: _impl se prefiere sobre vault_io.py falso en CWD.

El test construye el escenario completo en un venv aislado: copia vault_toolkit/
al site-packages del venv (con su _impl/ y loading.py), coloca un vault_io.py
espurio en el CWD del subprocess, y verifica que import_toolkit_module carga
desde _impl y no desde el CWD. El _impl/ se crea donde el código lo busca:
como subdirectorio de Path(__file__).resolve().parent de loading.py.

Se usa un venvtmp_path factory propio para garantizar isolation completa.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path
import shutil

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_impl_preferred_over_fake_cwd_vault_io(tmp_path_factory):
    """Un vault_io.py falso en CWD no se carga cuando _impl/vault_io.py existe."""
    venv_path = tmp_path_factory.mktemp("impl_shadow_venv")
    if venv_path.exists():
        shutil.rmtree(venv_path)
    venv.create(venv_path, with_pip=False, clear=False)

    venv_lib = venv_path / "Lib" if sys.platform != "darwin" else venv_path / "lib"
    venv_site = venv_lib / "site-packages"

    vault_tk_src = REPO_ROOT / "vault_toolkit"
    vault_tk_dest = venv_site / "vault_toolkit"
    shutil.copytree(vault_tk_src, vault_tk_dest, dirs_exist_ok=True)

    impl_dir = vault_tk_dest / "_impl"
    impl_dir.mkdir(parents=True, exist_ok=True)
    (impl_dir / "vault_io.py").write_text(
        "STUB = 'from_impl'\nFAUX = 'NO_FAUX'\n",
        encoding="utf-8",
    )

    faux_cwd = tmp_path_factory.mktemp("faux_cwd")
    faux_vault_io = faux_cwd / "vault_io.py"
    faux_vault_io.write_text(
        "FAUX = 'from_cwd'\nSTUB = 'NO_STUB'\n",
        encoding="utf-8",
    )

    env = {"PATH": str(venv_path / ("Scripts" if sys.platform == "win32" else "bin")), "SYSTEMROOT": ""}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)

    code = (
        f"import sys; sys.path.insert(0, {str(faux_cwd)!r}); "
        "from vault_toolkit.loading import import_toolkit_module; "
        "m = import_toolkit_module('vault_io', legacy_scripts=None); "
        "print(getattr(m, 'STUB', 'NO_STUB'), end=''); "
        "print(getattr(m, 'FAUX', 'NO_FAUX'), end='')"
    )

    python_exec = venv_path / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    result = subprocess.run(
        [str(python_exec), "-c", code],
        cwd=str(faux_cwd),
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
        f"El modulo se cargo desde CWD en vez de _impl/"
    )


def test_sin_impl_ni_legacy_no_cae_al_import_desnudo(tmp_path, monkeypatch):
    """El caso negativo: ni `_impl` ni `legacy_scripts` lo tienen → ImportError.

    Un módulo del mismo nombre en `sys.path` (el CWD, por ejemplo) no puede
    colarse como respaldo: eso es justo la sombra que el loader existe para
    evitar. Con `legacy_scripts` señalando a un directorio sin el módulo, igual.
    """
    import pytest

    from vault_toolkit.loading import import_toolkit_module

    nombre = "vault_sombra_sin_dueno_b6"
    (tmp_path / f"{nombre}.py").write_text("SOMBRA = True\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    vacio = tmp_path / "legacy_vacio"
    vacio.mkdir()

    for legacy in (None, vacio):
        with pytest.raises(ImportError, match="no encontrado en _impl"):
            import_toolkit_module(nombre, legacy_scripts=legacy)
    assert nombre not in sys.modules
