#!/usr/bin/env python3

"""

Vault Validate — Validates frontmatter, folder structure, and index integrity.



Blueprint: vault-obsidian-architecture.md § vault_validate(path?, folder?, check?)



Usage:

    python vault_validate.py --check all

    python vault_validate.py --path "07_Knowledge/api.md" --check frontmatter

    python vault_validate.py --folder "01_Projects" --check frontmatter

    python vault_validate.py --check structure

    python vault_validate.py --check indexes

"""


import argparse

import json

import re

import sys

from vault_registry import ORDERED_SECTIONS, es_artefacto_derivado
from vault_encoding import strip_bom
from vault_errors import wrap_main
from vault_fundamentals import cia_valores

import yaml

from pathlib import Path

from typing import Any, Dict, List, Optional


# El vocabulario CIA lo declara `vault_fundamentals.CIA_TRIAD`, que es la fuente
# única del marco según CLAUDE.md. Aquí estaba copiado a mano: coincidía, pero
# nada lo obligaba, y una tercera copia vivía dentro de `_check_fundamentals`.
CIA_INTEGRITY_VALUES = cia_valores("cia_integrity")

CIA_AVAILABILITY_VALUES = cia_valores("cia_availability")

CIA_SENSITIVITY_VALUES = cia_valores("cia_sensitivity")


# Se congeló en v33 con diez secciones y nunca creció: un vault sin `11_Code`
# ni `18_Bugs` pasaba la validación como completo, porque «requerido» aquí
# significaba lo que era requerido hace siete versiones. Ahora lo dice el
# registro, así que una sección nueva es exigible el mismo día que existe.
REQUIRED_FOLDERS = list(ORDERED_SECTIONS)


REQUIRED_INDEXES = [

    "99_Index/search-index.json",

    "99_Index/graph.json",

]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _validate_cia_fields(data: Dict[str, Any]) -> List[str]:

    """Validate optional CIA fields if present. Returns list of error messages."""

    errors: List[str] = []

    if "cia_integrity" in data:

        v = str(data["cia_integrity"]).lower()

        if v not in CIA_INTEGRITY_VALUES:

            errors.append(f"cia_integrity '{v}' must be one of: {sorted(CIA_INTEGRITY_VALUES)}")

    if "cia_availability" in data:

        v = str(data["cia_availability"]).lower()

        if v not in CIA_AVAILABILITY_VALUES:

            errors.append(f"cia_availability '{v}' must be one of: {sorted(CIA_AVAILABILITY_VALUES)}")

    if "cia_sensitivity" in data:

        v = str(data["cia_sensitivity"]).lower()

        if v not in CIA_SENSITIVITY_VALUES:

            errors.append(f"cia_sensitivity '{v}' must be one of: {sorted(CIA_SENSITIVITY_VALUES)}")

    if "dq_validated_at" in data:

        val = str(data["dq_validated_at"])

        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", val):

            errors.append(f"dq_validated_at '{val}' must be ISO 8601 (YYYY-MM-DDTHH:MM:SS...)")

    # F7 AUTENTICIDAD: agent field (AP-16) — if present, must be non-empty

    if "agent" in data:

        val = str(data["agent"]).strip()

        if not val:

            errors.append("agent field present but empty (F7 AUTENTICIDAD requires non-empty value)")

    return errors


def validate_frontmatter(note_path: Path) -> Dict[str, Any]:

    """Validate YAML frontmatter of a single note. Returns {valid, error?, data?}.

    Aquí se miden dos normas, y conviene no confundirlas:

    - **AP-28** es el caso degenerado: no hay bloque de frontmatter en absoluto
      (`No frontmatter block`, `Frontmatter not closed`, o un bloque que no es
      un mapping YAML). Sin bloque no hay ningún campo que discutir.
    - **AP-12** es la inconsistencia entre notas del mismo tipo, y se aplica
      exigiendo el **mismo** conjunto `required` a toda nota de la misma clase
      —contenido, índice derivado, `00_System/`— en vez de campo a campo. Que
      la clase decida el conjunto es lo que impide que dos notas hermanas
      lleguen a tener frontmatter distinto y las dos pasen.

    `vault_audit` mide los campos uno por uno como AP-16/26/27/29/30; esa es
    otra medida y no sustituye a esta.
    """

    try:

        content = note_path.read_text(encoding="utf-8", errors="ignore")

    except Exception as e:

        return {"valid": False, "error": str(e)}


    # Un BOM delante del `---` no impide leer el frontmatter: ni Obsidian ni
    # `yaml.safe_load` sobre el bloque ya recortado lo notan, y el kernel tiene
    # `strip_bom` precisamente para esto. Sin quitarlo, `startswith("---")` era
    # falso y once notas del vault de pruebas —con frontmatter completo y
    # legible— salían como «No frontmatter block». AP-44: la comprobación medía
    # con su criterio, no con el del consumidor.

    content, _ = strip_bom(content)


    rel_path = str(note_path.relative_to(_raiz())).replace("\\", "/")
    is_index = es_artefacto_derivado(rel_path)

    if not content.startswith("---"):

        # Un artefacto derivado se escribe sin frontmatter: lo genera una tool
        # —`vault_section_index`, `vault_change_log`, `vault_compact_contracts`—
        # que no le pone ninguno. Exigírselo hacía que el estándar reprobara 65
        # ficheros que acababa de escribir él mismo (AP-44: medir con criterio
        # propio). Tres líneas más abajo esta misma función ya los exceptúa de
        # los campos de trazabilidad — la excepción existía, solo llegaba tarde.
        # Cuáles son lo dice `vault_registry`, no esta función.
        if is_index:
            return {"valid": True, "data": {}, "derived": True}
        return {"valid": False, "error": "No frontmatter block"}


    parts = content.split("---", 2)

    if len(parts) < 3:

        return {"valid": False, "error": "Frontmatter not closed"}


    try:

        data = yaml.safe_load(parts[1])

    except (yaml.YAMLError, RecursionError) as e:

        # AP-61: `RecursionError` no hereda de `YAMLError` y el parser de PyYAML
        # es recursivo — el porqué completo está en el dueño canónico del
        # criterio, `vault_lib.parse_frontmatter`. Aquí no se delega en él
        # porque esta función devuelve el motivo del rechazo (`{"valid": …,
        # "error": …}`) y el dueño devuelve `{}` sin decir por qué.
        return {"valid": False, "error": f"YAML parse error: {e}"}


    if not isinstance(data, dict):

        return {"valid": False, "error": "Frontmatter is not a YAML mapping"}


    # v37: required fields expanded
    required = ["id", "title", "createdAt", "updatedAt"]

    # For content notes (not system/index), require traceability fields
    is_system = rel_path.startswith("00_System/") or rel_path == "00_System"

    if not is_index and not is_system:
        required += ["cia_integrity", "cia_availability", "cia_sensitivity", "agent"]

    missing = [f for f in required if f not in data]
    # `tags` se comprobaba tres líneas antes de que `missing` existiera:
    # `UnboundLocalError` en la primera nota de contenido sin tags, y la tool
    # entera devolvía UNEXPECTED_ERROR sin validar ni una. Nunca falló en los
    # tests porque sus notas de fixture siempre llevan tags — el vault de
    # pruebas, no.
    if not is_index and not is_system and "tags" not in data:
        missing.append("tags")
    if missing:
        return {"valid": False, "error": f"Missing required fields: {missing}", "data": data}


    cia_errors = _validate_cia_fields(data)

    if cia_errors:

        return {"valid": False, "error": f"CIA field errors: {'; '.join(cia_errors)}", "data": data}


    return {"valid": True, "data": data}


def check_frontmatter(path: Optional[str], folder: Optional[str]) -> Dict[str, Any]:

    """Run frontmatter validation on one note, a folder, or the whole vault."""

    if path:

        note = _raiz() / path

        result = validate_frontmatter(note)

        if result["valid"]:

            return {"valid": [path], "invalid": []}

        return {"valid": [], "invalid": [{"path": path, "error": result["error"]}]}


    if folder:

        notes = list((_raiz() / folder).rglob("*.md"))

    else:

        # Solo las secciones canónicas. Barrer el vault entero con `rglob` desde
        # la raíz mete en el informe cualquier markdown que conviva con él
        # —`docs/`, notas de trabajo, un README— y los reprueba por no llevar
        # frontmatter, que es justo lo que no se les pide: no son notas del
        # vault. En el vault de pruebas eran 13 de las 26 «No frontmatter
        # block», todas de `docs/sdd/`. Qué cuenta como nota lo decide
        # `ORDERED_SECTIONS` (AP-05), no el disco.

        notes = [

            n

            for seccion in REQUIRED_FOLDERS

            for n in (_raiz() / seccion).rglob("*.md")

            if ".history" not in str(n) and not n.name.startswith("_")

        ]


    valid: List[str] = []

    invalid: List[Dict[str, str]] = []


    for note in notes:

        result = validate_frontmatter(note)

        rel = str(note.relative_to(_raiz()))

        if result["valid"]:

            valid.append(rel)

        else:

            invalid.append({"path": rel, "error": result["error"]})


    return {"valid": valid, "invalid": invalid}


def check_structure() -> Dict[str, Any]:

    """Verify that the standard numbered folders exist."""

    missing = [f for f in REQUIRED_FOLDERS if not (_raiz() / f).exists()]

    return {"expected": len(REQUIRED_FOLDERS), "missing": missing}


def check_indexes() -> Dict[str, Any]:

    """Verify that required JSON indexes are present and readable."""

    invalid: List[str] = []

    for idx in REQUIRED_INDEXES:

        path = _raiz() / idx

        if not path.exists():

            invalid.append(f"{idx} (missing)")

        else:

            try:

                json.loads(path.read_text(encoding="utf-8"))

            except Exception:

                invalid.append(f"{idx} (unreadable)")

    return {"required": len(REQUIRED_INDEXES), "invalid": invalid}


def vault_validate(

    path: Optional[str] = None,

    folder: Optional[str] = None,

    check: str = "all",

) -> Dict[str, Any]:

    """

    Validate frontmatter, folder structure, and index integrity.



    Args:

        path:   Relative path to a specific note (frontmatter check only).

        folder: Relative path to a folder — validates all notes inside.

        check:  "frontmatter" | "structure" | "indexes" | "all"



    Returns:

        {

          "valid":     [...],           # present when check includes frontmatter

          "invalid":   [{path, error}], # present when check includes frontmatter

          "structure": {expected, missing},

          "indexes":   {required, invalid}

        }

    """

    result: Dict[str, Any] = {"ok": True}


    if check in ("frontmatter", "all"):

        fm = check_frontmatter(path, folder)

        result["valid"] = fm["valid"]

        result["invalid"] = fm["invalid"]

        if fm["invalid"]:

            result["ok"] = False


    if check in ("structure", "all"):

        st = check_structure()

        result["structure"] = st

        if st["missing"]:

            result["ok"] = False


    if check in ("indexes", "all"):

        idx = check_indexes()

        result["indexes"] = idx

        if idx["invalid"]:

            result["ok"] = False


    return result


def main():

    parser = argparse.ArgumentParser(

        description="Vault Validate -- blueprint: vault-obsidian-architecture.md",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_validate.py --check all

  python vault_validate.py --path "07_Knowledge/api.md" --check frontmatter

  python vault_validate.py --folder "01_Projects" --check frontmatter

  python vault_validate.py --check structure

  python vault_validate.py --check indexes



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - --check all valida frontmatter, estructura de carpetas e indices JSON

  - Campos CIA opcionales validados si presentes: cia_integrity (critical|high|medium|low),

    cia_availability (high|medium|low), cia_sensitivity (public|internal|restricted),

    dq_validated_at (ISO 8601 — escrito por vault_quality_check, no editar a mano)

""",

    )

    parser.add_argument("--path", help="Relative path to a specific note")

    parser.add_argument("--folder", help="Relative path to a folder to validate")

    parser.add_argument(

        "--check",

        choices=["frontmatter", "structure", "indexes", "all"],

        default="all",

        help="What to validate (default: all)",

    )


    args = parser.parse_args()

    result = vault_validate(args.path, args.folder, args.check)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_validate"))

