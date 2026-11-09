#!/usr/bin/env python3
"""vault_insights — CLI del inventario por lotes (ADR-0002).

El dueño vive en `vault/gobernanza/insights.py` (contexto Gobernanza): el
inventario es lectura y comparación de metadatos, no una tool de agente, así
que no se publica en el catálogo MCP. Este adaptador solo hace lo que un
adaptador debe: leer argv, resolver la raíz y emitir el envelope.

Uso:

    python scripts/vault_insights.py
    python scripts/vault_insights.py --guardar C:/datos/vault-2026-11-09.json
    python scripts/vault_insights.py --comparar a.json b.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from vault_errors import emit_error, wrap_main  # noqa: E402
from vault_io import get_vault_root  # noqa: E402
from vault.gobernanza.insights import (  # noqa: E402
    SnapshotInvalido,
    comparar,
    guardar,
    inventario,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_insights — inventario de solo lectura y comparación "
                    "de snapshots",
        allow_abbrev=False)
    parser.add_argument("--guardar", metavar="RUTA",
                        help="Guarda el snapshot en RUTA (fuera del vault)")
    parser.add_argument("--comparar", nargs=2, metavar=("A", "B"),
                        help="Informe de diferencias entre dos snapshots")
    parser.add_argument("--force", action="store_true",
                        help="Con --guardar: sobrescribe un snapshot existente")
    args = parser.parse_args()

    raiz = get_vault_root()
    if not raiz or not Path(raiz).is_dir():
        print(json.dumps(emit_error(
            "vault_insights", "VAULT_NOT_FOUND",
            "no hay vault: define VAULT_ROOT o ejecuta desde uno"),
            ensure_ascii=False, indent=2))
        return 1

    try:
        if args.comparar:
            res = comparar(*args.comparar)
        else:
            datos = inventario(Path(raiz))
            res = (guardar(datos, args.guardar, Path(raiz), force=args.force)
                    if args.guardar else datos)
    except SnapshotInvalido as exc:
        print(json.dumps(emit_error("vault_insights", exc.causa, str(exc)),
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_insights"))
