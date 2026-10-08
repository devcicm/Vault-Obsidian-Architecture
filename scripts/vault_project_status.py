#!/usr/bin/env python3

"""

Vault Project Status Tool — Update project status



Updates project status.md and appends to changelog.md.



States: en_desarrollo | en_revision | bloqueado | completado | archivado | en_produccion



Usage:

    python vault_project_status.py --project ans --status en_produccion --summary "Lanzado v1.0"

"""

import argparse

import json

import sys

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_norms_catalog import status_frontmatter_lines
from vault_lib import parse_frontmatter, utcnow
import uuid

from pathlib import Path


# Configuration
from vault_io import assert_within_vault, atomic_write_text, get_vault_root
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


# Valid states

VALID_STATES = [
    "en_desarrollo",
    "en_revision",
    "bloqueado",
    "completado",
    "archivado",
    "en_produccion",
]


def vault_project_status(
    project: str, status: str, summary: str, modified_files: list = None
) -> dict:
    """

    Update project status.md and changelog.md.



    Args:

        project: Project slug

        status: New status

        summary: What was done

        modified_files: List of files modified

    """

    if status not in VALID_STATES:
        return emit_error("vault_project_status", "INVALID_VALUE", f"Invalid status: {status}. Valid: {VALID_STATES}")

    project_path = get_vault_root() / "01_Projects" / project

    # AP-36: se contiene ANTES del `mkdir`. La escritura atómica ya rechazaba
    # `--project ../../x`, pero el directorio se creaba primero, fuera del
    # vault, en la rama que luego se declaraba fallida (medido 2026-10-01).
    try:
        assert_within_vault(project_path, get_vault_root() / "01_Projects")
    except ValueError as exc:
        return emit_error("vault_project_status", "INVALID_PATH",
                          f"El proyecto '{project}' no es un nombre dentro de 01_Projects: {exc}")

    status_file = project_path / "status.md"

    changelog_file = project_path / "changelog.md"

    # Ensure project folder exists

    project_path.mkdir(parents=True, exist_ok=True)

    now = utcnow()

    # Read existing status.md to preserve id and createdAt

    existing_id = None

    existing_created = None

    if status_file.exists():
        try:
            existing_content = status_file.read_text(encoding="utf-8")

            # AP-44: con YAML, como lo lee el consumidor. Partir líneas por
            # `:` devolvía `id: 'x' # copiado` como `x' # copiado` y la nota
            # cambiaba de identidad en la primera actualización.
            existentes = parse_frontmatter(existing_content)
            if existentes.get("id") is not None:
                existing_id = str(existentes["id"])
            if existentes.get("createdAt") is not None:
                existing_created = str(existentes["createdAt"])

        except (OSError, UnicodeDecodeError) as exc:
            # AP-51: callarse aquí acuñaba un id nuevo y reescribía la nota
            # que no se había podido leer.
            return emit_error("vault_project_status", "FILE_READ_ERROR",
                              f"No se pudo leer {status_file.name}: {exc}")

    # El changelog también se lee antes de escribir nada: leerlo después de
    # reescribir status.md dejaba la actualización a medias si fallaba.
    try:
        existing = (changelog_file.read_text(encoding="utf-8")
                    if changelog_file.exists() else "# Changelog\n\n")
    except (OSError, UnicodeDecodeError) as exc:
        return emit_error("vault_project_status", "FILE_READ_ERROR",
                          f"No se pudo leer {changelog_file.name}: {exc}")

    note_id = existing_id or str(uuid.uuid4())

    created_at = existing_created or now

    # AP-46: el bloque lo escribe su dueño. Crudo, `Alfa #1` dejaba
    # `project: Alfa` —` #` abre un comentario— y la nota quedaba atribuida
    # a otro proyecto (medido 2026-10-01). El bloque llevaba una línea en
    # blanco entre campos; YAML las ignora y el dueño no las escribe, así que
    # el frontmatter queda compacto con los mismos datos.
    fm = (
        Frontmatter()
        .set("title", f"{project} — Status")
        .set("id", note_id)
        .set("project", project, texto=True)
        # `status` canónico + `project_state` con el valor de dominio intacto.
        .lineas(status_frontmatter_lines("vault_project_status", status))
        .set("createdAt", created_at)
        .set("updatedAt", now)
        .set("tags", ["status", project])
    )

    status_content = f"""{fm.render()}



# {project} — Status



**Última actualización:** {now}

**Estado:** {status.upper()}

**Resumen:** {summary}



---



## Detalles



- **Estado anterior:** _[Registrado en historial]_

- **Fecha del cambio:** {now}

- **Resumen del cambio:** {summary}



---



## Archivos modificados



{chr(10).join(f"- `{f}`" for f in (modified_files or [])) or "_Ninguno_"}

"""

    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el
    # saneado de encoding y el temp+replace viven ahí. Escribir en crudo los
    # esquivaba los tres (AP-36) y dejaba la nota a medias si el proceso moría.
    atomic_write_text(status_file, status_content)

    # Append to changelog.md

    changelog_entry = f"""



### {now} — {status.upper()}



**{summary}**



{f"- Archivos: {', '.join(modified_files)}" if modified_files else ""}

"""

    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el
    # saneado de encoding y el temp+replace viven ahí. Escribir en crudo los
    # esquivaba los tres (AP-36) y dejaba la nota a medias si el proceso moría.
    atomic_write_text(changelog_file, existing + changelog_entry)

    return {
        "ok": True,
        "project": project,
        "status": status,
        "path": str(status_file.relative_to(get_vault_root())).replace("\\", "/"),
        "changelogPath": str(changelog_file.relative_to(get_vault_root())).replace("\\", "/"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Project Status Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_project_status.py --project ans --status en_produccion --summary "Lanzado v1.0"

  python vault_project_status.py --project mi-api --status en_desarrollo --summary "Sprint 3 iniciado"

  python vault_project_status.py --project backend --status bloqueado --summary "Esperando acceso a BD" --files "src/db.py"

  python vault_project_status.py --project ans --status completado --summary "Feature X terminada"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Estados validos: en_desarrollo, en_revision, bloqueado, completado, archivado, en_produccion

  - Actualiza status.md y agrega entrada a changelog.md del proyecto

""",
        allow_abbrev=False,
    )

    parser.add_argument("--project", type=proyecto_registrado("vault_project_status"), required=True)

    parser.add_argument("--status", required=True, choices=VALID_STATES,
                        help="Nuevo estado del proyecto")

    parser.add_argument("--summary", required=True,
                        help="Resumen del cambio; va a status.md y a una entrada de changelog.md")

    parser.add_argument("--files", nargs="*", help="Modified files")

    args = parser.parse_args()

    result = vault_project_status(args.project, args.status, args.summary, args.files)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_project_status"))
