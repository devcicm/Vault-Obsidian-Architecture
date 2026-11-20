#!/usr/bin/env python3

"""

Vault Test Save Tool -- Save test cases and test documentation (ISO/IEC/IEEE 29119-3)



Saves test cases to 15_Tests/{test_type}/{project}-{slug}.md.

Types: unit, integration, e2e, performance, security, acceptance

Status: not_run, pass, fail, blocked, skip



Usage:

    python vault_test_save.py --project "mi-api" --title "Login success" --test_type unit --description "Test successful login with valid credentials" --preconditions "User exists in DB" --steps '[{"step":1,"action":"Call login(user,pwd)","expected":"Returns AuthToken"}]' --expected_result "AuthToken with valid JWT"

    python vault_test_save.py --project "mi-api" --title "Auth API flow" --test_type integration --description "Full auth flow via HTTP" --related_requirement "REQ-001" --related_code "src/auth.py"

    python vault_test_save.py --project "mi-api" --title "Login performance" --test_type performance --description "Login endpoint under load" --preconditions "1000 concurrent users" --expected_result "p99 < 200ms"

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
from vault.kernel.contenido import nota_escalonada  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402



from vault.kernel.frontmatter_escritura import conservar_nota_generada  # noqa: E402

from vault_encoding import sanitize_content  # noqa: E402
from vault.kernel.normativa import calidad_iso  # noqa: E402

def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _tests_dir() -> Path:
    return _repo().seccion("15_Tests")


def _index_file() -> Path:
    return _repo().seccion("15_Tests") / ".tests-index.json"


TEST_TYPES = ["unit", "integration", "e2e", "performance", "security", "acceptance"]

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones

STATUSES = _opciones("test_result")


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
        return {"tests": []}


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def save_index(data: Dict[str, Any]) -> None:
    _tests_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_test_save(
    project: str,
    title: str,
    test_type: str,
    description: str,
    preconditions: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
    expected_result: Optional[str] = None,
    related_requirement: Optional[str] = None,
    related_code: Optional[List[str]] = None,
    status: str = "not_run",
    tags: Optional[List[str]] = None,
    test_level: Optional[str] = None,
    test_kinds: Optional[List[str]] = None,
    techniques: Optional[List[str]] = None,
    quality_characteristics: Optional[List[str]] = None,
    quality_in_use: Optional[List[str]] = None,
) -> Dict[str, Any]:
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    if test_type not in TEST_TYPES:
        return emit_error("vault_test_save", "INVALID_VALUE", f"test_type '{test_type}' not valid. Use: {TEST_TYPES}")

    if status not in STATUSES:
        return emit_error("vault_test_save", "INVALID_VALUE", f"status '{status}' not valid. Use: {STATUSES}")

    declarado = _declaraciones_iso(test_level, test_kinds, techniques,
                                   quality_characteristics, quality_in_use)
    if not declarado["ok"]:
        return declarado
    declarado = declarado["campos"]

    safe_project = slugify_strict(project)

    title_slug = slugify_strict(title)

    now = utcnow()

    # El lock abarca desde la lectura hasta la escritura, no solo la
    # escritura: este indice es tambien el contador del correlativo, y
    # reservar el numero fuera del tramo exclusivo hace que dos guardados
    # concurrentes obtengan el mismo id y el mismo nombre de fichero.
    with indice_compartido(_index_file(), {"tests": []}) as index:

        # Count existing tests for this project to get sequential ID

        project_tests = [t for t in index["tests"] if es_del(t.get("project"))]

        # O4: identidad por ruta (proyecto+título). Antes el correlativo se
        # recalculaba desde la longitud del registro y cada llamada anexaba una
        # entrada: re-guardar el mismo caso dejaba TEST-002 apuntando a la nota
        # de TEST-001. Con la nota ya conservada, la entrada tampoco se toca.
        filename = f"{safe_project}-{title_slug}.md"

        note_path = _tests_dir() / test_type / filename

        rel_previsto = str(note_path.relative_to(_raiz())).replace("\\", "/")

        existente = next((t for t in index["tests"]
                          if t.get("relPath") == rel_previsto), None)

        if existente is not None:
            test_id = str(existente.get("test_id") or "")
            note_id = str(existente.get("docId") or "") or str(uuid.uuid4())
        else:
            test_number = len(project_tests) + 1

            test_id = f"TEST-{test_number:03d}"

            note_id = str(uuid.uuid4())

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

        tags_list.extend([safe_project, "test", test_type, status])

        frontmatter = Frontmatter()

        frontmatter.set("id", note_id)

        frontmatter.set("test_id", test_id)

        frontmatter.set("title", title, texto=True)

        frontmatter.set("project", project, texto=True)

        frontmatter.set("test_type", test_type)

        # AP-27: el contrato de una nota de `15_Tests/` pide `type`, y el
        # canonico de esa seccion es `test` (vault_registry.SECTION_TYPES).
        # La tool escribia `test_type` y nada mas: sus notas salian del
        # contrato incumplido, y el audit lo media como `missing_type`
        # (medido en un vault real, 2026-10-21, al documentar con esta tool
        # cincoscripts de prueba que el agente habia ejecutado).
        frontmatter.set("type", "test")

        frontmatter.lineas(status_frontmatter_lines("vault_test_save", status))

        if related_requirement:
            frontmatter.set("related_requirement", related_requirement)

        # Optional ISO/IEC/IEEE 29119 and ISO/IEC 25010/25019 declarations:
        # written only when given, so a note without them is unchanged.
        for campo, valor in declarado.items():
            frontmatter.set(campo, valor)

        frontmatter.set("createdAt", now)

        frontmatter.set("updatedAt", now)

        if tags_list:
            frontmatter.set("tags", list(dict.fromkeys(tags_list)))

        frontmatter.set("cia_integrity", "medium")

        frontmatter.set("cia_availability", "medium")

        frontmatter.set("cia_sensitivity", "internal")

        frontmatter.set("agent", "system")


        body_sections = []

        body_sections.append(f"## Descripcion\n\n{description}")

        if preconditions:
            body_sections.append(f"## Pre-condiciones\n\n{preconditions}")

        if steps:
            rows = ["## Pasos\n", "| # | Accion | Resultado Esperado |", "|---|---|---|"]

            for s in steps:
                step_num = s.get("step", "")

                action = s.get("action", "")

                expected = s.get("expected", "")

                rows.append(f"| {step_num} | {action} | {expected} |")

            body_sections.append("\n".join(rows))

        if expected_result:
            body_sections.append(f"## Resultado Esperado\n\n{expected_result}")

        if related_requirement or related_code:
            rows = ["## Trazabilidad\n", "| Tipo | Referencia |", "|---|---|"]

            if related_requirement:
                rows.append(f"| Requerimiento | `{related_requirement}` |")

            for code_file in related_code or []:
                rows.append(f"| Codigo | `{code_file}` |")

            body_sections.append("\n".join(rows))

        # Status badge

        status_line = " | ".join(f"**{s}**" if s == status else s for s in STATUSES)

        body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

        # nota-escalonada S4: the lead says what the test is from its arguments.
        lead = f"{title} es una prueba {test_type} del proyecto {project}, en estado {status}."
        if related_requirement:
            lead += f" Verifica el requisito `{related_requirement}`."
        lead += " Esta nota se generó con `vault_test_save` y vive en la sección de pruebas del vault."
        falta = None if (steps or expected_result) else (
            "faltan los pasos o el resultado esperado de la prueba (`--steps`, `--expected_result`)")
        final_content = (frontmatter.render() + "\n\n" + nota_escalonada(title, lead, falta=falta)
                         + "\n" + "\n\n".join(body_sections))

        note_path.parent.mkdir(parents=True, exist_ok=True)

        contenido = conservar_nota_generada(
            note_path,
            sanitize_content(final_content, dry_run=False)[0],
            campos=("test_id",),
        )
        previo = ""
        if note_path.exists():
            try:
                previo = note_path.read_text(encoding="utf-8")
            except OSError:
                previo = ""
        sin_cambio = bool(previo) and contenido == previo

        atomic_write_text(note_path, contenido)

        entry = {
            "docId": note_id,
            "test_id": test_id,
            "project": project,
            "title": title,
            "test_type": test_type,
            "status": status,
            "related_requirement": related_requirement or "",
            "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
            "updatedAt": now,
        }

        if existente is not None:
            if not sin_cambio:
                index["tests"][index["tests"].index(existente)] = entry
        else:
            index["tests"].append(entry)


    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "test_id": test_id,
        "action": ("unchanged" if existente is not None and sin_cambio else
                   ("updated" if existente is not None else "created")),
    }


def _declaraciones_iso(
    test_level: Optional[str],
    test_kinds: Optional[List[str]],
    techniques: Optional[List[str]],
    quality_characteristics: Optional[List[str]],
    quality_in_use: Optional[List[str]],
) -> Dict[str, Any]:
    """Validate the optional 29119-1/-4 and 25010/25019 fields against their registry.

    Returns `{"ok": True, "campos": {field: canonical}}` with only the fields
    given, or the `INVALID_VALUE` envelope naming the first unknown term.
    """
    campos: Dict[str, Any] = {}
    pedidos = (
        ("test_level", calidad_iso.split_terms(test_level), "vocab"),
        ("test_kinds", calidad_iso.split_terms(test_kinds), "vocab"),
        ("techniques", calidad_iso.split_terms(techniques), "vocab"),
        ("quality_characteristics", calidad_iso.split_terms(quality_characteristics), "product"),
        ("quality_in_use", calidad_iso.split_terms(quality_in_use), "in_use"),
    )
    for campo, terminos, origen in pedidos:
        if not terminos:
            continue
        if origen == "vocab":
            canonicos, desconocidos = calidad_iso.resolve_terms(campo, terminos)
            validos = calidad_iso.vocabulary_ids(campo)
        else:
            canonicos, desconocidos = calidad_iso.resolve_quality(origen, terminos)
            validos = calidad_iso.characteristic_ids(origen)
        if campo == "test_level" and len(canonicos) > 1:
            desconocidos = desconocidos or terminos[1:]
        if desconocidos:
            return emit_error("vault_test_save", "INVALID_VALUE",
                              f"{campo} {desconocidos} not valid. Use: {validos}")
        campos[campo] = canonicos[0] if campo == "test_level" else canonicos
    return {"ok": True, "campos": campos}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Test Save Tool -- ISO/IEC/IEEE 29119-3 test case documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_test_save.py --project "mi-api" --title "Login success" --test_type unit --description "Test successful login with valid credentials" --preconditions "User exists in DB" --steps '[{"step":1,"action":"Call login(user,pwd)","expected":"Returns AuthToken"}]' --expected_result "AuthToken with valid JWT"



  python vault_test_save.py --project "mi-api" --title "Auth API flow" --test_type integration --description "Full auth flow via HTTP" --related_requirement "REQ-001" --related_code "src/auth.py"



  python vault_test_save.py --project "mi-api" --title "Login performance" --test_type performance --description "Login endpoint under load" --preconditions "1000 concurrent users" --expected_result "p99 < 200ms"



Notes:

  - test_type: unit | integration | e2e | performance | security | acceptance  (ISO/IEC/IEEE 29119-3)

  - status: not_run | pass | fail | blocked | skip

  - --related_code accepts comma-separated file paths

  - --steps JSON format: [{"step": 1, "action": "...", "expected": "..."}]

  - test_id is auto-generated as TEST-001, TEST-002, etc. per project

  - Optional, validated against vault/kernel/normativa/calidad_iso.py and
    written only when given (comma-separated; aliases resolve to the canonical id):
      --test_level  ISO/IEC/IEEE 29119-1 level: component | integration | system |
                    system_integration | acceptance  (unit -> component)
      --test_kinds  29119-1 test types (functional, performance, security, usability, ...)
      --techniques  29119-4 design techniques (equivalence_partitioning,
                    boundary_value_analysis, decision_table_testing,
                    state_transition_testing, scenario_testing, branch_testing,
                    statement_testing, error_guessing, exploratory_testing, ...)
      --quality_characteristics  ISO/IEC 25010:2023 characteristics or
                    characteristic.subcharacteristic (2011 names accepted:
                    usability, portability)
      --quality_in_use  ISO/IEC 25019:2023 characteristics (effectiveness,
                    efficiency, satisfaction, freedom_from_risk, context_coverage)
    Coverage per characteristic and tests per level/type/technique:
      vault_quality_check --iso-quality

""",
        allow_abbrev=False,
    )

    parser.add_argument("--project", type=proyecto_registrado("vault_test_save"), required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short test case title")

    parser.add_argument("--test_type", choices=TEST_TYPES, required=True, help=f"Test type: {TEST_TYPES}")

    parser.add_argument("--description", required=True, help="What is being tested")

    parser.add_argument(
        "--preconditions", help="Setup conditions required before running the test"
    )

    parser.add_argument(
        "--steps",
        help='JSON array of steps: [{"step":1,"action":"...","expected":"..."}]',
    )

    parser.add_argument("--expected_result", help="Overall expected outcome")

    parser.add_argument(
        "--related_requirement", help="Related requirement ID (e.g. REQ-001)"
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument(
        "--status", choices=STATUSES,
        default="not_run",
        help=f"Test status (default: not_run): {STATUSES}",
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    parser.add_argument("--test_level", help="ISO/IEC/IEEE 29119-1 test level (component, integration, system, system_integration, acceptance)")

    parser.add_argument("--test_kinds", help="Comma-separated ISO/IEC/IEEE 29119-1 test types (functional, performance, security, ...)")

    parser.add_argument("--techniques", help="Comma-separated ISO/IEC/IEEE 29119-4 test design techniques")

    parser.add_argument("--quality_characteristics", help="Comma-separated ISO/IEC 25010:2023 characteristics or characteristic.subcharacteristic")

    parser.add_argument("--quality_in_use", help="Comma-separated ISO/IEC 25019:2023 quality-in-use characteristics")

    args = parser.parse_args()

    def parse_json_arg(val: Optional[str], name: str) -> Optional[Any]:
        if not val:
            return None

        try:
            return json.loads(val)

        except json.JSONDecodeError as e:
            print(json.dumps(emit_error("vault_test_save", "ARG_JSON_INVALID", f"Invalid JSON in --{name}: {e}"), ensure_ascii=False))

            sys.exit(1)

    related_code_list: Optional[List[str]] = None

    if args.related_code:
        related_code_list = [
            f.strip() for f in args.related_code.split(",") if f.strip()
        ]

    steps = parse_json_arg(args.steps, "steps")

    result = vault_test_save(
        project=args.project,
        title=args.title,
        test_type=args.test_type,
        description=args.description,
        preconditions=args.preconditions,
        steps=steps,
        expected_result=args.expected_result,
        related_requirement=args.related_requirement,
        related_code=related_code_list,
        status=args.status,
        tags=args.tags,
        test_level=args.test_level,
        test_kinds=args.test_kinds,
        techniques=args.techniques,
        quality_characteristics=args.quality_characteristics,
        quality_in_use=args.quality_in_use,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_test_save"))
