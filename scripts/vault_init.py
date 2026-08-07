#!/usr/bin/env python3
"""
vault_init.py — Bootstrap de un vault fresco en un solo comando.

Hace lo que el README quickstart describe como 3-4 pasos, en uno solo:
  1. Crea las 17 carpetas estándar (00_System → 99_Index)
  2. Escribe 00_System/standard-version.json
  3. Aplica las migraciones pendientes (v20 → current)
  4. Auto-genera el índice de cada sección
  5. Crea 00_System/vault-hub.md y vault-commands.md si no existen
  6. Ejecuta vault_audit y reporta el health score inicial

Diseñado para que un consumer repo pueda ejecutar:

    mkdir vault-mi-proyecto
    cp -r Vault-Obsidian-Architecture/scripts ./
    python scripts/vault_init.py

Y termine con un vault navegable de inmediato, sin tener que recordar
la secuencia exacta de comandos del README.

Usage:
    python vault_init.py                  # versión por defecto (current)
    python vault_init.py --target v32     # migrar hasta v32 explícitamente
    python vault_init.py --no-audit       # omitir vault_audit final
    python vault_init.py --clean          # peligroso: borra el contenido actual
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import wrap_main
from vault_io import atomic_write_json, write_report
from vault_lib import yaml_scalar, utcnow
from vault_standard_upgrade import CURRENT_VERSION
from vault_registry import (
    standard_folders,
    EVENT_DRIVEN_SECTIONS,
    ORDERED_SECTIONS,
    SCAFFOLD_TYPE,
    section_description,
    section_tool_hint,
)


# Sections that get a scaffold primer on init. 00_System is excluded because
# vault-hub.md + vault-commands.md already provide structure. All other
# standard sections get a primer so the vault starts at 100/100.
# Todas menos `00_System`, que vault_init puebla con ficheros de identidad
# reales y no necesita andamio. Estaba escrita a mano y se quedó en 17: las
# cuatro secciones de v39 nacían vacías, y el andamio existe justamente para
# que una sección recién creada no arrastre la puntuación del vault.
# Fuera: `00_System`, que vault_init puebla con ficheros de identidad reales,
# y las dirigidas por eventos, cuyo vacío es estado correcto.
_SCAFFOLD_SECTIONS = [
    f
    for f in ORDERED_SECTIONS
    if f != "00_System" and f not in EVENT_DRIVEN_SECTIONS
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _create_scaffold_note(section: str) -> Dict[str, Any]:
    """Create a primer note in a section that explains its purpose and how to use it.

    The primer passes the strict content gate (>=3 real lines, >=10 real words)
    so the vault starts at healthScore 100/100 even before the user adds real
    content. Each primer is marked with `scaffold: true` in frontmatter so the
    user can identify and remove or replace it when real content is added.

    Returns: {"section": str, "path": str, "created": bool}
    """
    primer_path = _raiz() / section / f"00-{section.lower()}-primer.md"
    if primer_path.exists():
        return {
            "section": section,
            "path": str(primer_path.relative_to(_raiz())).replace("\\", "/"),
            "created": False,
        }

    description = section_description(section)
    tool_hint = (
        section_tool_hint(section) or f"vault_write --folder {section} --title <titulo>"
    )

    # Build content that is real documentation (passes content gate) but
    # explicitly says it's a primer. Real words count: 40+ per primer.
    content = f"""# {section} — Guía rápida

> Esta nota es un **scaffold generado por `vault_init`** para que el vault
> arranque en `healthScore 100/100`. Puedes **eliminarla** cuando la sección
> tenga contenido real, o **mantenerla** como referencia para el equipo.

## Propósito de esta sección

{description}

## Comando sugerido

```
python scripts/{tool_hint}
```

## Siguiente paso

1. Lee la guía completa en [[vault-hub|Hub del vault]].
2. Crea tu primera nota real con el comando sugerido arriba.
3. Cuando tengas contenido real en esta sección, elimina o renombra este scaffold.

> **Más comandos:** ver [[vault-commands|Comandos del vault]].
"""
    frontmatter = (
        "---\n"
        f"title: {yaml_scalar(section)} — Guía rápida\n"
        f"id: {section.lower()}-primer\n"
        f"createdAt: {utcnow()}\n"
        f"updatedAt: {utcnow()}\n"
        f"cia_integrity: medium\n"
        f"cia_availability: medium\n"
        f"cia_sensitivity: internal\n"
        f"agent: vault_init\n"
        f'tags: ["primer", "scaffold", "onboarding"]\n'
        f"scaffold: true\n"
        # `SCAFFOLD_TYPE`, no el literal: `vault_registry.is_scaffold_note()`
        # decide con esa misma constante qué nota es andamio y cuál contenido.
        # Escrito a mano aquí, el escritor y el lector del mismo campo podían
        # dejar de coincidir sin que nada lo notara.
        f"type: {SCAFFOLD_TYPE}\n"
        # Sin `status`, el propio `vault_audit` marcaba como incompleta cada nota
        # que este generador acaba de escribir: 18 primers de 18 en el vault de
        # BuilderX. El generador del estándar producía notas que su auditoría
        # reprueba, y el usuario no tenía forma de saber que la deuda no era suya.
        # `template` — y no `draft` — porque un primer es andamiaje estable, no un
        # borrador en camino a otra cosa; es además el valor que AP-03 y AP-07
        # eximen de exigencias de contenido y estructura de ADR.
        f"status: template\n"
        f'norm_refs: ["CN-01"]\n'
        "---\n"
        "\n"
    )
    primer_path.parent.mkdir(parents=True, exist_ok=True)
    primer_path.write_text(frontmatter + content, encoding="utf-8")
    return {
        "section": section,
        "path": str(primer_path.relative_to(_raiz())).replace("\\", "/"),
        "created": True,
    }


def vault_init(
    target_version: str = CURRENT_VERSION, run_audit: bool = True, clean: bool = False
) -> dict:
    """Inicializa un vault fresco en VAULT_ROOT.

    Returns a structured result suitable for both CLI JSON output and tests.
    """
    result = {
        "ok": True,
        **write_report(),
        "vault_root": str(_raiz()).replace("\\", "/"),
        "target_version": target_version,
        "steps": [],
    }

    # Safety: refuse to run if VAULT_ROOT looks wrong (sandbox not detected)
    if not _raiz().exists() or not _raiz().is_dir():
        result["ok"] = False
        result["error"] = (
            f"VAULT_ROOT does not exist or is not a directory: {_raiz()}"
        )
        return result

    # Step 0: --clean wipes existing content (only if explicitly asked)
    if clean and _raiz().exists():
        wiped = []
        for entry in _raiz().iterdir():
            if entry.name == ".locks":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            wiped.append(entry.name)
        result["steps"].append({"step": "clean", "wiped": wiped})

    # Step 1: create all 17 standard folders
    folders_created = []
    for folder in standard_folders():
        folder_path = _raiz() / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            folders_created.append(folder)
        # always ensure .gitkeep
        gitkeep = folder_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
    result["steps"].append(
        {
            "step": "folders",
            "created": folders_created,
            "total": len(standard_folders()),
        }
    )

    # Step 1.5: create a primer note in each content section so the vault
    # starts at healthScore 100/100. Each primer has real content (passes
    # the strict content gate) and explains what the section is for. They
    # are marked scaffold: true so the user can identify and remove them
    # as they add real content.
    scaffolds_created = []
    for section in _SCAFFOLD_SECTIONS:
        try:
            res = _create_scaffold_note(section)
            if res.get("created"):
                scaffolds_created.append(res)
        except Exception as exc:
            # scaffold failure must never block init
            result["steps"].append(
                {"step": "scaffold_error", "section": section, "error": str(exc)}
            )
    result["steps"].append(
        {
            "step": "scaffolds",
            "created": scaffolds_created,
            "total": len(_SCAFFOLD_SECTIONS),
        }
    )

    # Step 2: run vault_standard_upgrade --init <target>
    # We invoke the script as a subprocess to reuse its full logic
    import subprocess

    scripts_dir = Path(__file__).parent
    upgrade_script = scripts_dir / "vault_standard_upgrade.py"
    if upgrade_script.exists():
        proc = subprocess.run(
            [
                sys.executable,
                str(upgrade_script),
                "--init",
                target_version,
                "--agent",
                "vault_init",
            ],
            capture_output=True,
            text=True,
        )
        try:
            upgrade_data = json.loads(proc.stdout)
            result["steps"].append({"step": "init", "output": upgrade_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {"step": "init", "raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
            )

    # Step 3: run vault_master_index which also indexes all sections
    master_script = scripts_dir / "vault_master_index.py"
    if master_script.exists():
        proc = subprocess.run(
            [sys.executable, str(master_script)],
            capture_output=True,
            text=True,
        )
        try:
            master_data = json.loads(proc.stdout)
            result["steps"].append({"step": "master_index", "output": master_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {
                    "step": "master_index",
                    "raw_stdout": proc.stdout,
                    "raw_stderr": proc.stderr,
                }
            )

    # Step 4: run vault_reindex --graph to populate graph.json + search-index.json + hash-index.json
    reindex_script = scripts_dir / "vault_reindex.py"
    if reindex_script.exists():
        proc = subprocess.run(
            [sys.executable, str(reindex_script), "--graph"],
            capture_output=True,
            text=True,
        )
        try:
            reindex_data = json.loads(proc.stdout)
            result["steps"].append({"step": "reindex", "output": reindex_data})
        except json.JSONDecodeError:
            result["steps"].append(
                {
                    "step": "reindex",
                    "raw_stdout": proc.stdout,
                    "raw_stderr": proc.stderr,
                }
            )

    # Step 4.5: write tag-registry.json with canonical tags
    tag_registry_path = _raiz() / "00_System" / "tag-registry.json"
    if not tag_registry_path.exists():
        tag_registry = {
            "version": "v1.0",
            "generated_at": utcnow(),
            "canonical_tags": {
                "project": ["ans", "builderx", "homelab"],
                "section": ["flow", "pattern", "runbook", "code", "diagram", "infrastructure", "knowledge", "decision", "test", "requirement", "alert", "metric", "slo", "incident"],
                "domain": ["mcp", "toon", "ansible", "ssh", "proxmox", "docker", "deploy", "pipeline", "ci-cd", "mikrotik", "runner", "proxy", "vault"],
                "type": ["dataflow", "lifecycle", "workflow", "pipeline-flow", "architecture", "concept", "api", "config", "guide", "reference"],
                "quality": ["verified", "stub", "draft", "informacion-decrepita", "deprecated"],
                "migration": ["migrated", "direct", "indirect", "excluded"],
                "agent": ["deepseek", "mavis", "opencode", "system", "vault_init"],
            },
        }
        tag_registry_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(tag_registry_path, tag_registry)
        result["steps"].append({"step": "tag_registry", "output": "tag-registry.json created"})

    # Step 4.6: write ontology.json into the vault (copy from scripts/vault_ontology.json)
    ontology_src = Path(__file__).parent / "vault_ontology.json"
    ontology_dst = _raiz() / "00_System" / "vault-ontology.json"
    if ontology_src.exists() and not ontology_dst.exists():
        ontology_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ontology_src, ontology_dst)
        result["steps"].append({"step": "ontology", "output": "vault-ontology.json copied to vault"})

    # Step 5: optional vault_audit
    if run_audit:
        audit_script = scripts_dir / "vault_audit.py"
        if audit_script.exists():
            proc = subprocess.run(
                [sys.executable, str(audit_script)],
                capture_output=True,
                text=True,
            )
            try:
                audit_data = json.loads(proc.stdout)
                result["steps"].append({"step": "audit", "output": audit_data})
                result["healthScore"] = audit_data.get("healthScore")
                result["noteCount"] = audit_data.get("stats", {}).get("total", 0)
            except json.JSONDecodeError:
                result["steps"].append(
                    {
                        "step": "audit",
                        "raw_stdout": proc.stdout,
                        "raw_stderr": proc.stderr,
                    }
                )

    # Step 6: report on hub notes
    hub_note = _raiz() / "00_System" / "vault-hub.md"
    commands_note = _raiz() / "00_System" / "vault-commands.md"
    result["hub_notes"] = {
        "hub": str(hub_note.relative_to(_raiz())).replace("\\", "/")
        if hub_note.exists()
        else None,
        "commands": str(commands_note.relative_to(_raiz())).replace("\\", "/")
        if commands_note.exists()
        else None,
    }

    # Promote healthScore + noteCount to top-level so the spec contract is satisfied.
    # They are computed in step 5 (audit) and step 4 (reindex).
    if "healthScore" not in result:
        for step in result["steps"]:
            if step.get("step") == "audit":
                out = step.get("output", {})
                if isinstance(out, dict):
                    result["healthScore"] = out.get("healthScore")
                    result["noteCount"] = out.get("stats", {}).get("total", 0)
                    break

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Init — bootstrap a fresh vault in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Ejemplos:
  # Bootstrap con la versión actual del estándar
  python vault_init.py

  # Migrar a una versión específica
  python vault_init.py --target v38.1

  # Bootstrap sin ejecutar vault_audit al final
  python vault_init.py --no-audit

  # Bootstrap desde cero (BORRA el contenido actual — usar con cuidado)
  python vault_init.py --clean

Notas:
  - VAULT_ROOT se detecta automáticamente
  - Crea las carpetas estándar del registro, aplica migraciones, indexa todo,
    genera hub/commands notes y reporta el health score.
  - --clean borra TODO el contenido del vault actual excepto .locks
        """,
    )
    parser.add_argument(
        "--target",
        default=CURRENT_VERSION,
        help=(
            "Versión objetivo del estándar. Por defecto, la versión actual "
            f"({CURRENT_VERSION}): fijarla a mano dejaba el vault sellado con "
            "una versión antigua y las carpetas de las migraciones posteriores "
            "sin crear."
        ),
    )
    parser.add_argument(
        "--no-audit", action="store_true", help="Skip final vault_audit run"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe existing vault content before init (DANGEROUS)",
    )
    args = parser.parse_args()

    result = vault_init(
        target_version=args.target,
        run_audit=not args.no_audit,
        clean=args.clean,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_init"))
