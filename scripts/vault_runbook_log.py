#!/usr/bin/env python3

"""

Vault Runbook Log Tool — Log runbook execution



Logs a runbook execution with outcome (success, failed, partial).

Appends to the runbook's execution history section and increments counter.



Usage:

    python vault_runbook_log.py --path "08_Runbooks/deploy/ans-deploy.md" --outcome "success" --notes "All steps completed"

    python vault_runbook_log.py --path "08_Runbooks/debug/mi-api-memory-leak.md" --outcome "partial" --duration "25 min" --notes "Leak still present after restart"

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, Optional


from vault_io import VAULT_ROOT, atomic_write_text, write_report


OUTCOMES = ["success", "failed", "partial"]

OUTCOME_ICONS = {"success": "✅", "failed": "❌", "partial": "⚠️"}


def parse_frontmatter(content: str) -> Dict[str, Any]:
    frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)

    if not frontmatter_match:
        return {}

    meta = {}

    for line in frontmatter_match.group(1).split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)

            key = key.strip()

            value = value.strip().strip("\"'")

            if value.startswith("[") or value.startswith("{"):
                try:
                    value = json.loads(value)

                except json.JSONDecodeError:
                    pass

            meta[key] = value

    return meta


def update_frontmatter_value(content: str, key: str, value: Any) -> str:
    lines = content.split("\n")

    updated = False

    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = f"{key}: {value}"

            updated = True

            break

    if not updated:
        for i, line in enumerate(lines):
            if line.startswith("---") and i > 0:
                lines.insert(i + 1, f"{key}: {value}")

                break

    return "\n".join(lines)


def vault_runbook_log(
    path: str,
    outcome: str,
    notes: Optional[str] = None,
    duration: Optional[str] = None,
) -> Dict[str, Any]:
    outcome = outcome.lower()

    if outcome not in OUTCOMES:
        return {
            "ok": False,
            "error": f"Outcome inválido: {outcome}. Válidos: {OUTCOMES}",
        }

    note_path = VAULT_ROOT / path

    if not note_path.exists():
        return {"ok": False, "error": f"Runbook not found: {path}"}

    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()

    meta = parse_frontmatter(content)

    executions = int(meta.get("executions", 0)) + 1

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    icon = OUTCOME_ICONS.get(outcome, "❓")

    log_entry = f"- {icon} **{outcome.upper()}** — {timestamp}"

    if duration:
        log_entry += f" ({duration})"

    if notes:
        log_entry += f"\n  - {notes}"

    history_pattern = r"(## Historial de Ejecuciones\n\n)(.*?)(?=\n## |\Z)"

    history_match = re.search(history_pattern, content, re.DOTALL)

    if history_match:
        existing = history_match.group(2).strip()

        if "Sin ejecuciones registradas." in existing:
            new_history = log_entry

        else:
            new_history = existing + "\n" + log_entry

        content = re.sub(
            history_pattern,
            r"\1" + new_history + r"\n",
            content,
            flags=re.DOTALL,
        )

    else:
        content += f"\n\n## Historial de Ejecuciones\n\n{log_entry}\n"

    content = update_frontmatter_value(content, "executions", executions)

    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el
    # saneado de encoding y el temp+replace viven ahí. Escribir en crudo los
    # esquivaba los tres (AP-36) y dejaba la nota a medias si el proceso moría.
    atomic_write_text(note_path, content)

    return {
        "ok": True,
        **write_report(),
        "path": path,
        "outcome": outcome,
        "executionNumber": executions,
        "message": f"Execution #{executions} logged as {outcome}",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Runbook Log Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_runbook_log.py --path "08_Runbooks/deploy/ans-deploy.md" --outcome "success" --notes "All steps completed"

  python vault_runbook_log.py --path "08_Runbooks/debug/mi-api-memory-leak.md" --outcome "partial" --duration "25 min" --notes "Leak still present"

  python vault_runbook_log.py --path "08_Runbooks/setup/node-installation.md" --outcome "failed" --notes "Missing dependency"

  python vault_runbook_log.py --path "08_Runbooks/deploy/ans-deploy.md" --outcome "success" --duration "10 min"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Outcomes validos: success, failed, partial

  - Incrementa automaticamente el contador de ejecuciones en el frontmatter

""",
    )

    parser.add_argument(
        "--path", required=True, help="Path to runbook (relative to vault root)"
    )

    parser.add_argument("--outcome", required=True, help=f"Outcome: {OUTCOMES}")

    parser.add_argument("--notes", help="Execution notes")

    parser.add_argument("--duration", help="Duration (e.g., '25 min')")

    args = parser.parse_args()

    result = vault_runbook_log(args.path, args.outcome, args.notes, args.duration)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_runbook_log"))
