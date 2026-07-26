"""CLI consolidada del estándar Vault Obsidian Architecture.

Un único punto de entrada (`python -m cli`) sobre las 76 tools del catálogo.
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

__version__ = "39.0"
