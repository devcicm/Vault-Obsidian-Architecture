#!/usr/bin/env python3
"""Vault Backup — adaptador de transporte del contexto Durabilidad.

Crea un snapshot completo del vault en `<vault>/vault-backups/` con manifiesto,
huella Merkle sellada y entrada en el registro. Este fichero ya no decide nada:
la decisión —qué entra al snapshot, qué se hashea, con qué regla y cómo se
comprueba— vive en `vault/durabilidad/snapshot.py` y se prueba sin CLI.

La ruta y el nombre no cambian: `scripts/vault_backup.py` es lo que resuelven el
tool-spec, `cli/registry.py`, el runner del MCP y `vault_smoke`.

Usage:
    python vault_backup.py
    python vault_backup.py --label "antes-de-migracion"
    python vault_backup.py --verify vault-2026-08-06-101500-antes-de-migracion
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from vault_errors import emit_fallo, wrap_main
from vault_io import write_report

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.durabilidad.snapshot import ServicioSnapshot  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402


def vault_backup(label: Optional[str] = None, root=None) -> Dict[str, Any]:
    """El envelope publicado, armado desde el dominio.

    `write_report()` se añade **aquí** y no en el dominio: cuenta lo que el
    kernel escribió atómicamente, que es una medida del transporte. El trabajo
    de la operación —cuántos ficheros se copiaron— lo declara el dominio en
    `files_copied`, porque `shutil` no pasa por el ledger (AP-37).
    """
    cuerpo = ServicioSnapshot(construir(root)).crear(label)
    return {"ok": True, **write_report(), **cuerpo}


def vault_backup_verify(backup_name: str, root=None) -> Dict[str, Any]:
    """Verifica la huella de un snapshot.

    El `except` está aquí y no dentro del dominio porque esta función **es** la
    frontera: el dominio nombra la causa —cuál de los tres estados del
    manifiesto impide verificar— y el adaptador la convierte en `error_code` y
    `recovery`. Ver `vault/kernel/fallos.py` (v40.29).
    """
    try:
        return ServicioSnapshot(construir(root)).verificar(backup_name)
    except FalloDeDominio as e:
        return emit_fallo("vault_backup", e)


def main():
    parser = argparse.ArgumentParser(
        description="Vault Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_backup.py
  python vault_backup.py --label "antes-de-migracion"
  python vault_backup.py --label "sprint-3-checkpoint"
  python vault_backup.py --verify vault-2026-08-06-101500-antes-de-migracion

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Crea snapshot completo en VAULT_ROOT/vault-backups/ con .manifest.json + merkle_root
  - Registra el backup en .backup-registry.json para vault_backup_list.py
  - --verify recomputa el arbol Merkle con el algoritmo que sella el manifiesto
  - files_copied dice cuantos ficheros se copiaron; created/updated/written
    cuentan solo lo que escribio el kernel de forma atomica
""",
    )
    parser.add_argument("--label", help="Optional label (e.g., 'antes-de-migracion')")
    parser.add_argument(
        "--verify",
        metavar="BACKUP_NAME",
        help="Verificar integridad de un backup existente",
    )
    args = parser.parse_args()
    if args.verify:
        result = vault_backup_verify(args.verify)
    else:
        result = vault_backup(args.label)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_backup"))
