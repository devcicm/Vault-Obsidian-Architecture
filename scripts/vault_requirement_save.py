#!/usr/bin/env python3

"""

Vault Requirement Save Tool -- Save software requirements (ISO/IEC/IEEE 29148)



Saves requirements to 14_Requirements/{project}/ with traceability to code.

Types: functional, non-functional, constraint, assumption

Priority: must-have, should-have, nice-to-have (MoSCoW)

Status: draft -> reviewed -> approved -> implemented -> verified -> obsolete



Usage:

    python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have

    python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'

    python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"

"""

import argparse

import json

import re

import sys

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_norms_catalog import status_frontmatter_lines
from vault_lib import yaml_scalar, slugify_strict, utcnow
from datetime import datetime, timezone
from vault_io import (
    indice_compartido,
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
)
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.contenido import con_titulo  # noqa: E402
from vault.kernel.frontmatter_escritura import conservar_nota_generada  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402


from vault_encoding import sanitize_content  # noqa: E402

def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _req_dir() -> Path:
    return _repo().seccion("14_Requirements")


def _index_file() -> Path:
    return _repo().seccion("14_Requirements") / ".requirements-index.json"


REQ_TYPES = ["functional", "non-functional", "constraint", "assumption"]

PRIORITIES = ["must-have", "should-have", "nice-to-have", "wont-have"]

STATUSES = ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"]


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def load_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"requirements": []}


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def save_index(data: Dict[str, Any]) -> None:
    _req_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_requirement_save(
    project: str,
    title: str,
    description: str,
    req_type: str,
    priority: str,
    acceptance_criteria: Optional[List[str]] = None,
    source: Optional[str] = None,
    status: str = "draft",
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    if req_type not in REQ_TYPES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"req_type '{req_type}' not valid. Use: {REQ_TYPES}")

    if priority not in PRIORITIES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"priority '{priority}' not valid. Use: {PRIORITIES}")

    if status not in STATUSES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"status '{status}' not valid. Use: {STATUSES}")

    safe_project = slugify_strict(project)

    title_slug = slugify_strict(title)

    now = utcnow()

    # El lock abarca desde la lectura hasta la escritura, no solo la
    # escritura: este indice es tambien el contador del correlativo, y
    # reservar el numero fuera del tramo exclusivo hace que dos guardados
    # concurrentes obtengan el mismo id y el mismo nombre de fichero.
    with indice_compartido(_index_file(), {"requirements": []}) as index:

        # Count existing requirements for this project to get sequential ID

        project_reqs = [r for r in index["requirements"] if es_del(r.get("project"))]

        # Identidad del requerimiento (O4): proyecto + slug del título. Antes
        # CADA llamada reservaba el correlativo siguiente, así que re-guardar
        # el mismo requerimiento abría req-002 con el mismo título y el
        # contrato declaraba `unchanged`: el C3 lo midió al ejecutarse por fin
        # el ejemplo (el barrido anterior simulaba su rechazo). Es la misma
        # identidad que `vault_knowledge_save` ya aplica.
        existente = next(
            (r for r in project_reqs
             if slugify_strict(str(r.get("title") or "")) == title_slug),
            None,
        )

        if existente is not None:
            req_id = str(existente.get("req_id") or "")
            note_id = str(existente.get("docId") or "") or str(uuid.uuid4())
            rel_previo = str(existente.get("relPath") or "")
            note_path = _raiz() / rel_previo if rel_previo else (
                _req_dir() / safe_project / f"req-{req_id[-3:]}-{title_slug}.md")
            filename = note_path.name
        else:
            req_number = len(project_reqs) + 1

            req_id = f"REQ-{req_number:03d}"

            note_id = str(uuid.uuid4())

            filename = f"req-{req_number:03d}-{title_slug}.md"

            note_path = _req_dir() / safe_project / filename

        try:
            assert_within_vault(note_path, _raiz())

        except ValueError as exc:
            return {
                "ok": False,
                "error_code": "INVALID_PATH",
                "error": "INVALID_PATH",
                "message": str(exc),
            }

        tags_list = list(tags or [])

        tags_list.extend([safe_project, "requirement", req_type, priority])

        cia_integrity = "high" if priority == "must-have" else "medium"

        frontmatter = Frontmatter()

        frontmatter.set("id", note_id)

        frontmatter.set("req_id", req_id)

        frontmatter.set("title", title, texto=True)

        frontmatter.set("project", project, texto=True)

        frontmatter.set("req_type", req_type)

        frontmatter.set("priority", priority)

        frontmatter.lineas(status_frontmatter_lines("vault_requirement_save", status))

        frontmatter.set("createdAt", now)

        frontmatter.set("updatedAt", now)

        if tags_list:
            frontmatter.set("tags", list(dict.fromkeys(tags_list)))

        frontmatter.set("cia_integrity", cia_integrity)

        frontmatter.set("cia_availability", "medium")

        frontmatter.set("cia_sensitivity", "internal")

        frontmatter.set("agent", "system")


        body_sections = []

        body_sections.append(f"## Descripcion\n\n{description}")

        if acceptance_criteria:
            lines = ["## Criterios de Aceptacion\n"]

            for i, criterion in enumerate(acceptance_criteria, 1):
                lines.append(f"{i}. {criterion}")

            body_sections.append("\n".join(lines))

        if related_code:
            rows = ["## Trazabilidad\n", "| Archivo | Rol |", "|---|---|"]

            for code_file in related_code:
                rows.append(f"| `{code_file}` | implementacion |")

            body_sections.append("\n".join(rows))

        if source:
            body_sections.append(f"## Fuente\n\n{source}")

        # Status badge

        status_line = " | ".join(f"**{s}**" if s == status else s for s in STATUSES)

        body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

        final_content = frontmatter.render() + "\n\n" + con_titulo(title, "\n\n".join(body_sections))

        previo = ""
        if note_path.exists():
            try:
                previo = note_path.read_text(encoding="utf-8")
            except OSError:
                previo = ""

        # Mismo cuerpo ⇒ misma nota: id, `req_id` y sellos no son el
        # requerimiento. Re-guardar lo idéntico no toca la nota (ni dispara la
        # cascada de índices y grafo).
        final_content = conservar_nota_generada(
            note_path, sanitize_content(final_content, dry_run=False)[0])

        sin_cambio = bool(previo) and final_content == previo

        if not sin_cambio:
            note_path.parent.mkdir(parents=True, exist_ok=True)

            atomic_write_text(note_path, final_content)

            entry = {
                "docId": note_id,
                "req_id": req_id,
                "project": project,
                "title": title,
                "req_type": req_type,
                "priority": priority,
                "status": status,
                "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
                "related_code": related_code or [],
                "updatedAt": now,
            }

            if existente is not None:
                for i, r in enumerate(index["requirements"]):
                    if r is existente:
                        index["requirements"][i] = entry
                        break
            else:
                index["requirements"].append(entry)


    if sin_cambio:
        accion = "unchanged"
    elif existente is not None:
        accion = "updated"
    else:
        accion = "created"

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "req_id": req_id,
        "action": accion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Requirement Save Tool -- ISO/IEC/IEEE 29148 requirement documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have



  python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'



  python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"



Notes:

  - req_type: functional | non-functional | constraint | assumption  (ISO/IEC/IEEE 29148)

  - priority: must-have | should-have | nice-to-have | wont-have    (MoSCoW)

  - status: draft | reviewed | approved | implemented | verified | obsolete

  - --related_code accepts comma-separated file paths

  - req_id is auto-generated as REQ-001, REQ-002, etc. per project

""",
        allow_abbrev=False,
    )

    parser.add_argument("--project", type=proyecto_registrado("vault_requirement_save"), required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short requirement title")

    parser.add_argument(
        "--description", required=True, help="Full requirement description"
    )

    parser.add_argument(
        "--type", choices=REQ_TYPES, dest="req_type", required=True, help=f"Requirement type: {REQ_TYPES}"
    )

    parser.add_argument(
        "--priority", choices=PRIORITIES, required=True, help=f"MoSCoW priority: {PRIORITIES}"
    )

    parser.add_argument(
        "--acceptance_criteria", help="JSON array of acceptance criteria strings"
    )

    parser.add_argument(
        "--source", help="Origin of the requirement (stakeholder, document, etc.)"
    )

    parser.add_argument(
        "--status", choices=STATUSES,
        default="draft",
        help=f"Requirement status (default: draft): {STATUSES}",
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    args = parser.parse_args()

    def parse_json_arg(val: Optional[str], name: str) -> Optional[Any]:
        if not val:
            return None

        try:
            return json.loads(val)

        except json.JSONDecodeError as e:
            print(json.dumps(emit_error("vault_requirement_save", "ARG_JSON_INVALID", f"Invalid JSON in --{name}: {e}"), ensure_ascii=False))

            sys.exit(1)

    related_code_list: Optional[List[str]] = None

    if args.related_code:
        related_code_list = [
            f.strip() for f in args.related_code.split(",") if f.strip()
        ]

    acceptance_criteria = parse_json_arg(
        args.acceptance_criteria, "acceptance_criteria"
    )

    result = vault_requirement_save(
        project=args.project,
        title=args.title,
        description=args.description,
        req_type=args.req_type,
        priority=args.priority,
        acceptance_criteria=acceptance_criteria,
        source=args.source,
        status=args.status,
        related_code=related_code_list,
        tags=args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_requirement_save"))
