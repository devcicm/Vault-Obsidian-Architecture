#!/usr/bin/env python3
"""vault_ledger — fachada de `vault.kernel.ledger` (ADR-0002, deuda #12).

El dueño vive en `vault/kernel/ledger.py` desde 2026-10-09: segunda migración
del puente, tras `vault_subproceso`. Este nombre se conserva porque lo importan
`vault_io` y `vault_errors` (no-derogación), y reexporta los mismos objetos, no
una copia: el contador es thread-local y dos copias contarían en dos libros. En
el checkout añade la raíz del repo al path para encontrar `vault/`; instalado
(en `_impl`) `vault` ya es importable. Es la forma de `vault_subproceso`.
"""

import sys
from pathlib import Path

_repo_root = next(
    (p for p in Path(__file__).resolve().parents if (p / "vault").is_dir()),
    None,
)
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from vault.kernel.ledger import (  # noqa: E402
    EscrituraCancelada,
    _NO_ES_TRABAJO,
    _ledger,
    _record_write,
    _write_ledger,
    cancelacion_activa,
    cancelar_escrituras,
    descartar_cancelacion,
    exigir_escritura_permitida,
    record_raw_write,
    reanudar_escrituras,
    write_ledger_reset,
    write_report,
)

__all__ = [
    "record_raw_write",
    "write_ledger_reset",
    "write_report",
    # La valla de cancelación (hallazgo 3.6): el dueño de la escritura la
    # consulta, y `vault_errors` cierra la del hilo que se pasó de tiempo.
    "cancelar_escrituras",
    "descartar_cancelacion",
    "reanudar_escrituras",
    "cancelacion_activa",
    "exigir_escritura_permitida",
    "EscrituraCancelada",
]
