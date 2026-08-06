#!/usr/bin/env python3
"""Vault Restore — adaptador de transporte del contexto Durabilidad.

Restaura el vault desde un snapshot. **Operación destructiva**: exige
`--confirm true`. Este fichero ya no decide nada — qué se borra, qué nunca se
borra y de dónde se lee el snapshot vive en `vault/durabilidad/restauracion.py`,
donde se puede probar sin arriesgar un vault real.

La ruta y el nombre no cambian: `scripts/vault_restore.py` es lo que resuelven
el tool-spec, `cli/registry.py`, el runner del MCP y `vault_smoke`.

Usage:
    python vault_restore.py --backup_name "vault-2026-05-06-143022-antes-de-migracion" --confirm true
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import wrap_main
from vault_io import write_report

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.durabilidad.restauracion import ServicioRestauracion  # noqa: E402
from vault.kernel import construir  # noqa: E402

#: La ubicación anterior a v38.1: hermana del repo, FUERA de todo vault. Se
#: sigue consultando **solo para leer** porque hay copias reales ahí de las que
#: alguien puede necesitar salir; no-derogación. Se resuelve aquí, en el
#: adaptador, porque es un detalle de despliegue de este repo y no una regla del
#: dominio: otro consumidor tiene otra disposición de directorios.
LEGACY_BACKUP_ROOT = Path(__file__).resolve().parent.parent.parent / "vault-backups"


def vault_restore(backup_name: str, confirm: bool = False, root=None) -> Dict[str, Any]:
    servicio = ServicioRestauracion(construir(root), raiz_legacy=LEGACY_BACKUP_ROOT)
    resultado = servicio.restaurar(backup_name, confirm)
    if not resultado.get("ok", True):
        return resultado
    _reindexar_si_procede()
    return {"ok": True, **write_report(), **resultado}


def _reindexar_si_procede() -> None:
    """Reintento de reindexado heredado, conservado tal cual.

    Apunta a `<vault>/../data/vault/scripts/vault_index.py`, que es la
    disposición de un consumidor y no la de este repo: aquí no existe y por
    tanto no dispara nunca. Se conserva porque quitarlo sería derogar
    comportamiento de un despliegue que no puedo comprobar desde aquí, y queda
    anotado porque un no-op silencioso sin anotar es exactamente AP-37.
    """
    import subprocess

    try:
        raiz = construir().raiz
        script = raiz.parent / "data" / "vault" / "scripts" / "vault_index.py"
        if script.exists():
            subprocess.run([sys.executable, str(script)],
                           capture_output=True, timeout=60)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Vault Restore Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_restore.py --backup_name "vault-2026-05-06-143022-antes-de-migracion" --confirm true
  python vault_restore.py --backup_name "vault-2026-05-01-120000" --confirm false

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Operacion DESTRUCTIVA -- reemplaza todo el contenido del vault
  - vault-backups/ NUNCA se borra: contiene el snapshot que se esta leyendo
  - Ejecutar vault_backup.py primero para preservar estado actual
  - --confirm false (default) solo muestra info sin restaurar
""",
    )
    parser.add_argument("--backup_name", required=True, help="Exact backup name")
    parser.add_argument(
        "--confirm", type=lambda x: x.lower() == "true", default=False,
        help="Must be true",
    )

    args = parser.parse_args()
    result = vault_restore(args.backup_name, args.confirm)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_restore"))
