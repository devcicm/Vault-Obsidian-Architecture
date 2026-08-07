#!/usr/bin/env python3
"""
vault_bug_save.py — El ciclo del defecto, entero y enlazado (18_Bugs/).

Por qué existe una sección para bugs habiendo ya `02_Observability/errors`:
un error es un **evento observado** —esto falló, aquí está el stack trace— y un
bug es un **defecto que se persigue hasta cerrarlo**. Son cosas distintas y
tienen ciclos de vida distintos.

Sin esta sección, el ciclo se repartía: el síntoma acababa en
`02_Observability/errors`, la causa raíz en `07_Knowledge` y la corrección en
`03_Decisions` — tres notas sin nada que las uniera. El juicio de que "este
defecto lo causó aquella decisión" existía en la cabeza de quien lo vio y se
perdía al cerrar la sesión. Aquí la relación es una arista explícita:

    18_Bugs/open/<bug>          --caused_by-->  18_Bugs/root-causes/<causa>
    18_Bugs/fixed/<bug>         --verified_by-> 15_Tests/<caso>

La fase determina la subcarpeta, así que el estado no puede mentir sobre dónde
vive la nota: `--status fixed` con una nota en `open/` es imposible por
construcción.

Usage:
    python vault_bug_save.py --project mi-api --title "Token numérico coercionado" \\
        --symptom "El literal 0.5 llega al CSS como '0.5px' y el layout salta" \\
        --status open --severity high --repro "Abrir el editor y arrastrar el slider"

    python vault_bug_save.py --project mi-api --title "Coerción de unidades CSS" \\
        --phase root-cause --symptom "..." --causes "token-numeric-coercion"

    python vault_bug_save.py --project mi-api --title "Token numérico coercionado" \\
        --status fixed --symptom "..." --fix "Normalizar en el serializador" \\
        --verified_by "15_Tests/unit/mi-api-token-units.md"
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_norms import status_frontmatter_lines
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    safe_wikilink,
)
from vault_lib import yaml_scalar, slugify_strict, utcnow


#: Fases del defecto. El nombre es la subcarpeta: la fase y la ubicación no
#: pueden divergir porque son el mismo dato leído dos veces.
PHASES = ["open", "root-cause", "fixed"]

_PHASE_FOLDER = {"open": "open", "root-cause": "root-causes", "fixed": "fixed"}

#: Vocabulario de dominio del defecto. Declarado en
#: vault_norms.DOMAIN_STATUS_VOCABS (AP-38): `status` sale canónico y estos
#: valores viven en `bug_state`, sin perderse ni competir por el campo.
BUG_STATES = ["open", "confirmed", "in_fix", "fixed", "wont_fix", "duplicate"]

SEVERITIES = ["critical", "high", "medium", "low"]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _bugs_dir() -> Path:
    return _repo().seccion("18_Bugs")


def _index_file() -> Path:
    return _repo().seccion("18_Bugs") / ".bugs-index.json"


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)[:60]


def load_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"bugs": []}


def vault_bug_save(
    project: str,
    title: str,
    symptom: str,
    phase: str = "open",
    status: str = "open",
    severity: str = "medium",
    repro: Optional[str] = None,
    root_cause: Optional[str] = None,
    fix: Optional[str] = None,
    causes: Optional[List[str]] = None,
    caused_by: Optional[List[str]] = None,
    verified_by: Optional[str] = None,
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    agent: Optional[str] = None,
) -> Dict[str, Any]:
    if phase not in PHASES:
        return {
            "ok": False,
            "error_code": "INVALID_PHASE",
            "error": f"phase '{phase}' no válida. Usa: {PHASES}",
        }
    if status not in BUG_STATES:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "error": f"status '{status}' no válido. Usa: {BUG_STATES}",
        }
    if severity not in SEVERITIES:
        return {
            "ok": False,
            "error_code": "INVALID_SEVERITY",
            "error": f"severity '{severity}' no válida. Usa: {SEVERITIES}",
        }
    if not (symptom or "").strip():
        return {
            "ok": False,
            "error_code": "EMPTY_SYMPTOM",
            "error": (
                "El síntoma no puede estar vacío: un bug sin síntoma observable "
                "no es reproducible y no se puede cerrar"
            ),
        }

    # AP-16 — atribución. Quién vio el defecto es parte del defecto.
    import os

    agent = agent or _env("VAULT_AGENT")
    if not agent:
        return {
            "ok": False,
            "error_code": "missing_agent",
            "norm_code": "AP-16",
            "error": "missing_agent",
            "message": (
                "AP-16: se requiere atribución de agente. Usa --agent <nombre> "
                "o exporta VAULT_AGENT."
            ),
        }

    safe_project = slugify(project)
    now = utcnow()
    index = load_index()

    bug_number = len(index["bugs"]) + 1
    bug_id = f"BUG-{bug_number:03d}"
    note_id = str(uuid.uuid4())

    note_path = _bugs_dir() / _PHASE_FOLDER[phase] / f"{safe_project}-{slugify(title)}.md"
    try:
        assert_within_vault(note_path, _raiz())
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": str(exc)}

    tags_list = list(dict.fromkeys([*(tags or []), safe_project, "bug", severity]))

    frontmatter = ["---"]
    frontmatter.append(f"title: {json.dumps(title, ensure_ascii=False)}")
    frontmatter.append(f"id: {note_id}")
    frontmatter.append(f"bug_id: {bug_id}")
    frontmatter.append("type: bug")
    frontmatter.append(f"project: {yaml_scalar(project)}")
    frontmatter.append(f"phase: {phase}")
    frontmatter.extend(status_frontmatter_lines("vault_bug_save", status))
    frontmatter.append(f"severity: {severity}")
    # Aristas tipadas: la causalidad es un predicado, no un `related` genérico.
    # Es la diferencia entre "estas dos notas se mencionan" y "esta explica
    # aquella", y solo la segunda sirve para navegar hacia atrás desde el
    # síntoma hasta el origen.
    if causes:
        frontmatter.append(f"causes: {json.dumps(causes, ensure_ascii=False)}")
    if caused_by:
        frontmatter.append(f"caused_by: {json.dumps(caused_by, ensure_ascii=False)}")
    if verified_by:
        frontmatter.append(f"verified_by: {yaml_scalar(verified_by)}")
    frontmatter.append(f"createdAt: {now}")
    frontmatter.append(f"updatedAt: {now}")
    frontmatter.append(f"tags: {json.dumps(tags_list, ensure_ascii=False)}")
    # Un defecto abierto compromete la integridad de lo que documenta el vault:
    # por eso no hereda el `medium` por defecto mientras siga abierto.
    frontmatter.append(
        f"cia_integrity: {'high' if status in ('open', 'confirmed', 'in_fix') else 'medium'}"
    )
    frontmatter.append("cia_availability: medium")
    frontmatter.append("cia_sensitivity: internal")
    frontmatter.append(f"agent: {agent}")
    frontmatter.append("---")

    cuerpo = [f"## Síntoma\n\n{symptom.strip()}"]
    if repro:
        cuerpo.append(f"## Reproducción\n\n{repro.strip()}")
    if root_cause:
        cuerpo.append(f"## Causa raíz\n\n{root_cause.strip()}")
    if fix:
        cuerpo.append(f"## Corrección\n\n{fix.strip()}")

    if causes or caused_by or verified_by or related_code:
        filas = ["## Trazabilidad\n", "| Predicado | Referencia |", "|---|---|"]
        for destino in causes or []:
            filas.append(f"| causa | {safe_wikilink(destino)} |")
        for destino in caused_by or []:
            filas.append(f"| causado por | {safe_wikilink(destino)} |")
        if verified_by:
            filas.append(f"| verificado por | {safe_wikilink(verified_by)} |")
        for archivo in related_code or []:
            filas.append(f"| código | `{archivo}` |")
        cuerpo.append("\n".join(filas))

    fases = " | ".join(f"**{p}**" if p == phase else p for p in PHASES)
    cuerpo.append(f"## Ciclo\n\n{fases}")

    note_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(note_path, "\n".join(frontmatter) + "\n\n" + "\n\n".join(cuerpo))

    rel = str(note_path.relative_to(_raiz())).replace("\\", "/")
    index["bugs"].append({
        "docId": note_id,
        "bug_id": bug_id,
        "project": project,
        "title": title,
        "phase": phase,
        "status": status,
        "severity": severity,
        "relPath": rel,
        "updatedAt": now,
    })
    _bugs_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(_index_file(), index)

    return {
        "ok": True,
        **write_report(),
        "path": rel,
        "bug_id": bug_id,
        "phase": phase,
        "action": "created",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_bug_save — ciclo del defecto en 18_Bugs/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python vault_bug_save.py --project mi-api --title "Token numérico coercionado" \\
      --symptom "El literal 0.5 llega al CSS como '0.5px'" --status open --severity high

  python vault_bug_save.py --project mi-api --title "Coerción de unidades CSS" \\
      --phase root-cause --symptom "..." --causes token-numeric-coercion

Notas:
  - phase: open | root-cause | fixed  → determina la subcarpeta destino
  - status: vocabulario de dominio (bug_state); `status` se emite canónico (AP-38)
  - --causes / --caused_by son aristas tipadas del grafo, no `related` genérico
""",
    )
    parser.add_argument("--project", required=True, help="Slug del proyecto")
    parser.add_argument("--title", required=True, help="Título breve del defecto")
    parser.add_argument("--symptom", required=True, help="Qué se observa que falla")
    parser.add_argument("--phase", default="open", choices=PHASES)
    parser.add_argument("--status", default="open", choices=BUG_STATES)
    parser.add_argument("--severity", default="medium", choices=SEVERITIES)
    parser.add_argument("--repro", help="Pasos de reproducción")
    parser.add_argument("--root-cause", dest="root_cause", help="Causa raíz")
    parser.add_argument("--fix", help="Corrección aplicada")
    parser.add_argument("--causes", nargs="*", help="Notas que este defecto causa")
    parser.add_argument("--caused-by", dest="caused_by", nargs="*", help="Notas que lo causan")
    parser.add_argument("--verified-by", dest="verified_by", help="Test que lo verifica")
    parser.add_argument("--related-code", dest="related_code", help="Archivos separados por coma")
    parser.add_argument("--tags", nargs="*", help="Tags adicionales")
    parser.add_argument("--agent", help="Agente que registra (AP-16)")

    args = parser.parse_args()

    codigo = None
    if args.related_code:
        codigo = [f.strip() for f in args.related_code.split(",") if f.strip()]

    result = vault_bug_save(
        project=args.project,
        title=args.title,
        symptom=args.symptom,
        phase=args.phase,
        status=args.status,
        severity=args.severity,
        repro=args.repro,
        root_cause=args.root_cause,
        fix=args.fix,
        causes=args.causes,
        caused_by=args.caused_by,
        verified_by=args.verified_by,
        related_code=codigo,
        tags=args.tags,
        agent=args.agent,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_bug_save"))
