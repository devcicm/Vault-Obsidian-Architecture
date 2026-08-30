#!/usr/bin/env python3
"""
vault_doc_staleness — verifica que los artefactos derivados existen y son válidos.

Comprueba que los JSON derivados de los catálogos Python existen, contienen JSON
válido y no están huérfanos (existencia vs. contenido obsoleto).

    python vault_doc_staleness.py --check      # informe sin exit code
    python vault_doc_staleness.py --check --strict  # exit 1 si falta alguno

Artefactos verificados:
  - 00_System/data-framework.json       ← vault_fundamentals --framework
  - 00_System/norm-registry.json       ← vault_norms --rebuild
  - 00_System/data-fundamentals.json   ← vault_fundamentals (default)
  - 00_System/tool-contracts.json      ← vault_compact_contracts
  - 00_System/quality-index.json       ← vault_quality_check
  - 00_System/tag-registry.json       ← vault_tags
  - 00_System/standard-version.json    ← vault_init / vault_standard_upgrade
"""

import argparse
import json
import sys
from pathlib import Path

from vault_errors import emit_error, wrap_main

SYSTEM_DIR = Path(__file__).resolve().parent.parent / "vault-sandbox" / "00_System"

ARTIFACTS = {
    "data-framework.json": "vault_fundamentals --framework",
    "norm-registry.json": "vault_norms --rebuild",
    "data-fundamentals.json": "vault_fundamentals",
    "tool-contracts.json": "vault_compact_contracts",
    "quality-index.json": "vault_quality_check",
    "tag-registry.json": "vault_tags",
    "standard-version.json": "vault_init / vault_standard_upgrade",
}


def _check() -> dict:
    missing = []
    invalid = []
    ok = []

    for fname, source in ARTIFACTS.items():
        path = SYSTEM_DIR / fname
        if not path.exists():
            missing.append({"file": fname, "source": source})
        else:
            try:
                json.loads(path.read_text(encoding="utf-8"))
                ok.append(fname)
            except (json.JSONDecodeError, OSError) as exc:
                invalid.append({"file": fname, "error": str(exc)})

    stale = missing + invalid

    return {
        "ok": len(stale) == 0,
        "tool": "vault_doc_staleness",
        "total": len(ARTIFACTS),
        "present": len(ok),
        "missing": len(missing),
        "invalid": len(invalid),
        "missing_files": missing,
        "invalid_files": invalid,
        "present_files": ok,
        "fix": (
            "Regenerar con: python scripts/vault_fundamentals.py --framework && "
            "python scripts/vault_norms.py --rebuild && "
            "python scripts/vault_compact_contracts.py && "
            "python scripts/vault_quality_check.py && "
            "python scripts/vault_tags.py"
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verifica que los artefactos derivados existen y son JSON válido.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check", action="store_true", help="Modo comprobación")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 si falta o está corrupto algún artefacto",
    )
    args = parser.parse_args()

    result = _check()

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.strict and not result["ok"]:
        return 1
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_doc_staleness"))
