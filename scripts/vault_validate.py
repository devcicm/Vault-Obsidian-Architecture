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
from vault_errors import wrap_main
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

VAULT_ROOT = Path(__file__).parent.parent

CIA_INTEGRITY_VALUES = {"critical", "high", "medium", "low"}
CIA_AVAILABILITY_VALUES = {"high", "medium", "low"}
CIA_SENSITIVITY_VALUES = {"public", "internal", "restricted"}

REQUIRED_FOLDERS = [
    "00_System",
    "01_Projects",
    "02_Observability",
    "03_Decisions",
    "04_Sessions",
    "05_Patterns",
    "06_Diagrams",
    "07_Knowledge",
    "08_Runbooks",
    "09_Infrastructure",
    "10_Migrated",
]

REQUIRED_INDEXES = [
    "99_Index/search-index.json",
    "99_Index/graph.json",
]


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
    """Validate YAML frontmatter of a single note. Returns {valid, error?, data?}."""
    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"valid": False, "error": str(e)}

    if not content.startswith("---"):
        return {"valid": False, "error": "No frontmatter block"}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"valid": False, "error": "Frontmatter not closed"}

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return {"valid": False, "error": f"YAML parse error: {e}"}

    if not isinstance(data, dict):
        return {"valid": False, "error": "Frontmatter is not a YAML mapping"}

    missing = [f for f in ("id", "title") if f not in data]
    if missing:
        return {"valid": False, "error": f"Missing required fields: {missing}", "data": data}

    cia_errors = _validate_cia_fields(data)
    if cia_errors:
        return {"valid": False, "error": f"CIA field errors: {'; '.join(cia_errors)}", "data": data}

    return {"valid": True, "data": data}


def check_frontmatter(path: Optional[str], folder: Optional[str]) -> Dict[str, Any]:
    """Run frontmatter validation on one note, a folder, or the whole vault."""
    if path:
        note = VAULT_ROOT / path
        result = validate_frontmatter(note)
        if result["valid"]:
            return {"valid": [path], "invalid": []}
        return {"valid": [], "invalid": [{"path": path, "error": result["error"]}]}

    if folder:
        notes = list((VAULT_ROOT / folder).rglob("*.md"))
    else:
        notes = [
            n for n in VAULT_ROOT.rglob("*.md")
            if ".history" not in str(n) and not n.name.startswith("_")
        ]

    valid: List[str] = []
    invalid: List[Dict[str, str]] = []

    for note in notes:
        result = validate_frontmatter(note)
        rel = str(note.relative_to(VAULT_ROOT))
        if result["valid"]:
            valid.append(rel)
        else:
            invalid.append({"path": rel, "error": result["error"]})

    return {"valid": valid, "invalid": invalid}


def check_structure() -> Dict[str, Any]:
    """Verify that the standard numbered folders exist."""
    missing = [f for f in REQUIRED_FOLDERS if not (VAULT_ROOT / f).exists()]
    return {"expected": len(REQUIRED_FOLDERS), "missing": missing}


def check_indexes() -> Dict[str, Any]:
    """Verify that required JSON indexes are present and readable."""
    invalid: List[str] = []
    for idx in REQUIRED_INDEXES:
        path = VAULT_ROOT / idx
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
