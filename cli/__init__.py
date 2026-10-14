"""CLI consolidada del estándar Vault Obsidian Architecture.

Un único punto de entrada (`python -m cli`) sobre las tools del catálogo.
No reimplementa ninguna tool: las descubre, las valida, las planifica y las
ejecuta. La fuente de verdad sigue siendo `scripts/vault_mcp_catalog.py` +
`<vault>/00_System/tool-spec.json`.

Módulos (fragmentos, buscables por separado):
    registry.py   índice de tools — grupo, propósito, params, side-effects
    safety.py     validación de argumentos y guardas anti-poison
    scheduler.py  modelo de recursos y planificación de ejecución concurrente
    runner.py     ejecución aislada de una tool, envelope JSON normalizado
    analyzer.py   escáner estático de antipatrones y condiciones de carrera
    vault_cli.py  parser y despacho de comandos
"""

__all__ = ["__version__"]


def _version_del_estandar() -> str:
    """La versión sale de `vault_version.CURRENT_VERSION`, no de un literal.

    Aquí ponía `"39.0"` mientras el estándar iba por v40.34: `--version`,
    `doctor` y el banner anunciaban otra versión. Se carga por ruta —es una
    hoja sin imports— para no tocar `sys.path` al importar el paquete.
    """
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    # Deuda #12: el dueño vive en el kernel; `scripts/vault_version.py` es un alias.
    ruta = Path(__file__).resolve().parent.parent / "vault" / "kernel" / "version.py"
    spec = spec_from_file_location("_cli_vault_version", ruta)
    modulo = module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.CURRENT_VERSION.lstrip("v")


__version__ = _version_del_estandar()
