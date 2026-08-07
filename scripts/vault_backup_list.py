#!/usr/bin/env python3
"""Vault Backup List — adaptador de transporte del contexto Durabilidad.

Este fichero ya no decide nada. Parsea argv, construye el contexto, llama al
dominio (`vault/durabilidad/`) y escribe el envelope. La decisión —qué es una
copia, de dónde se leen, qué pasa si el registro no está, cuántas caben en el
límite— vive en el dominio y se prueba sin CLI ni disco de por medio.

La ruta y el nombre no cambian: `scripts/vault_backup_list.py` es lo que
resuelven el tool-spec, `cli/registry.py`, el runner del MCP y `vault_smoke`, y
mover un fichero de `scripts/` está fuera del alcance del refactor. Lo que
cambia es dónde está el código que piensa.

`--limit` estaba publicado en el catálogo con validadores y default, y sin
implementar (AP-42): la segunda línea del ejemplo documentado moría en
`unrecognized arguments`. Ahora existe, y el rango lo impone el dominio.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import wrap_main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.durabilidad.modelo import (  # noqa: E402
    LIMITE_DEFECTO, LIMITE_MAX, LIMITE_MIN, LimiteInvalido,
)
from vault.durabilidad.repositorio import RepositorioDurabilidad  # noqa: E402
from vault.kernel import construir  # noqa: E402


def vault_backup_list(limit: int = LIMITE_DEFECTO, root=None) -> Dict[str, Any]:
    """El envelope publicado, armado desde el dominio.

    `root` existe para poder ejercer esto en proceso con dos vaults distintos,
    que es el criterio con el que se acepta el piloto. Por defecto no se pasa y
    el contexto resuelve la raíz **en la llamada**, no al importar (AP-49).
    """
    repositorio = RepositorioDurabilidad(construir(root))
    total, backups = repositorio.registro().acotado(limit)
    return {
        "ok": True,
        "total": total,
        "backups": [b.a_envelope() for b in backups],
        "message": f"{total} backups found",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Backup List Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_backup_list.py
  python vault_backup_list.py --limit 5

Notas:
  - Lee .backup-registry.json del directorio vault-backups/ (dentro del vault)
  - Si no hay registry, escanea los directorios de backup directamente
  - Los backups se crean con vault_backup.py
  - --limit acota los devueltos; `total` sigue diciendo cuántos hay
""",
    )
    parser.add_argument(
        "--limit", type=int, default=LIMITE_DEFECTO,
        help=f"Cantidad máxima devuelta (default: {LIMITE_DEFECTO}, "
             f"rango {LIMITE_MIN}-{LIMITE_MAX})",
    )
    args = parser.parse_args()

    try:
        result = vault_backup_list(args.limit)
    except LimiteInvalido as e:
        parser.error(str(e))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_backup_list"))
