#!/usr/bin/env python3

"""

Vault Pattern Save Tool — Register patterns with evolutionary state



Saves or updates a pattern with lifecycle tracking (planificado → en_progreso → implementado | deprecado | refactoring).

Auto-updates {proyecto}-patterns-index.md and tracks state transitions.



Usage:

    python vault_pattern_save.py --project "mi-api" --name "Repository" --type "code" --status "implementado"

    python vault_pattern_save.py --project "ans" --name "Circuit-Breaker" --type "code" --status "en_progreso" --files "src/resilience.py" --related "Retry"

"""



import argparse

import json

import os

import re

import sys

from vault_errors import wrap_main

from vault_io import atomic_write_text, atomic_write_json, assert_within_vault, VAULT_ROOT, safe_wikilink
import uuid

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional





def _utcnow() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")



PATTERNS_DIR = VAULT_ROOT / "05_Patterns"

INDEX_FILE = PATTERNS_DIR / "index.json"



PATTERN_TYPES = ["design", "architecture", "code", "integration"]

PATTERN_STATUSES = ["planificado", "en_progreso", "implementado", "deprecado", "refactoring"]



VALID_TRANSITIONS = {

    "planificado": ["en_progreso"],

    "en_progreso": ["implementado", "deprecado", "refactoring"],

    "implementado": ["deprecado", "refactoring", "en_progreso"],

    "deprecado": ["implementado", "en_progreso"],

    "refactoring": ["implementado", "en_progreso", "deprecado"],

}





def slugify(text: str) -> str:

    slug = text.lower()

    slug = re.sub(r"[^\w\s-]", "", slug)

    slug = re.sub(r"[\s_]+", "-", slug)

    slug = re.sub(r"^-+|-+$", "", slug)

    return slug





def get_pattern_path(project: str, name: str, pattern_type: str) -> Path:

    safe_name = slugify(name)

    safe_project = slugify(project)

    return PATTERNS_DIR / pattern_type / f"{safe_project}-{safe_name}.md"





def get_pattern_index_path(project: str) -> Path:

    return PATTERNS_DIR / f"{slugify(project)}-patterns-index.md"





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





def load_pattern_index() -> Dict[str, Any]:

    try:

        with open(INDEX_FILE, "r", encoding="utf-8") as f:

            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):

        return {"patterns": []}





def save_pattern_index(data: Dict[str, Any]) -> None:

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_json(INDEX_FILE, data)





def vault_pattern_save(

    project: str,

    name: str,

    pattern_type: str,

    status: str,

    description: Optional[str] = None,

    files: Optional[List[str]] = None,

    related_patterns: Optional[List[str]] = None,

    notes: Optional[str] = None,

) -> Dict[str, Any]:

    pattern_type = pattern_type.lower()

    status = status.lower().replace(" ", "_")



    if pattern_type not in PATTERN_TYPES:

        return {"ok": False, "error": f"Tipo inválido: {pattern_type}. Válidos: {PATTERN_TYPES}"}



    if status not in PATTERN_STATUSES:

        return {"ok": False, "error": f"Estado inválido: {status}. Válidos: {PATTERN_STATUSES}"}



    safe_project = slugify(project)

    safe_name = slugify(name)

    pattern_path = get_pattern_path(project, name, pattern_type)

    existing_id = None

    existing_status = None

    evolution_entries = []



    if pattern_path.exists():

        with open(pattern_path, "r", encoding="utf-8") as f:

            existing_content = f.read()

        meta = parse_frontmatter(existing_content)

        existing_id = meta.get("id")

        existing_status = meta.get("status")



        evo_match = re.search(r"## Evolución\n(.*?)(?=\n## |\Z)", existing_content, re.DOTALL)

        if evo_match:

            evolution_entries = evo_match.group(1).strip().split("\n")



    timestamp = _utcnow()



    if existing_status and existing_status != status:

        if status not in VALID_TRANSITIONS.get(existing_status, []):

            return {

                "ok": False,

                "error": f"Transición inválida: {existing_status} → {status}. Válidas desde {existing_status}: {VALID_TRANSITIONS.get(existing_status, [])}",

            }

        transition_entry = f"- **{existing_status}** → **{status}** ({timestamp})"

        if transition_entry not in evolution_entries:

            evolution_entries.append(transition_entry)



    wiki_links = []

    if related_patterns:

        for rp in related_patterns:

            slug = f"{safe_project}-{slugify(rp)}"
            wiki_links.append(f"[[{slug}|{safe_wikilink(rp)}]]")



    try:

        assert_within_vault(pattern_path, VAULT_ROOT)

    except ValueError as exc:

        return {"ok": False, "error_code": "INVALID_PATH", "error": "INVALID_PATH", "message": str(exc)}



    frontmatter = ["---"]

    frontmatter.append(f"title: {json.dumps(name)}")

    frontmatter.append(f"id: {existing_id or str(uuid.uuid4())}")

    frontmatter.append(f"project: {project}")

    frontmatter.append(f"type: {pattern_type}")

    frontmatter.append(f"status: {status}")

    frontmatter.append(f"createdAt: {timestamp}")

    frontmatter.append(f"updatedAt: {timestamp}")



    if files:

        frontmatter.append(f"files: {json.dumps(files)}")

    if related_patterns:

        frontmatter.append(f"relatedPatterns: {json.dumps(related_patterns)}")



    frontmatter.append(f"cia_integrity: medium")

    frontmatter.append(f"cia_availability: medium")

    frontmatter.append(f"cia_sensitivity: internal")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")



    body_sections = []



    if description:

        body_sections.append(f"## Descripción\n\n{description}")



    if files:

        body_sections.append("## Archivos\n\n" + "\n".join(f"- `{f}`" for f in files))



    if wiki_links:

        body_sections.append("## Patrones Relacionados\n\n" + " ".join(wiki_links))



    if notes:

        body_sections.append(f"## Notas\n\n{notes}")



    if evolution_entries or (existing_status and existing_status != status):

        evo_section = ["## Evolución\n"]

        for entry in evolution_entries:

            evo_section.append(entry)

        if existing_status and existing_status != status:

            evo_section.append(f"- **{existing_status}** → **{status}** ({timestamp})")

        body_sections.append("\n".join(evo_section))



    body_sections.append(f"\n---\n*Última actualización: {timestamp}*")



    final_content = "\n\n".join(["\n".join(frontmatter)] + body_sections)



    pattern_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(pattern_path, final_content)



    index = load_pattern_index()

    pattern_entry = {

        "path": str(pattern_path.relative_to(VAULT_ROOT)),

        "pattern": name,

        "project": project,

        "type": pattern_type,

        "status": status,

        "updatedAt": timestamp,

    }



    for i, entry in enumerate(index["patterns"]):

        if entry["path"] == pattern_entry["path"]:

            index["patterns"][i] = pattern_entry

            break

    else:

        index["patterns"].append(pattern_entry)



    save_pattern_index(index)



    transition = (

        f"{existing_status} → {status}"

        if existing_status and existing_status != status

        else None

    )



    return {

        "ok": True,

        "path": str(pattern_path.relative_to(VAULT_ROOT)).replace("\\", "/"),

        "status": status,

        "transition": transition,

    }





def main():

    parser = argparse.ArgumentParser(

        description="Vault Pattern Save Tool",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog="""

Ejemplos:

  python vault_pattern_save.py --project "mi-api" --name "Repository" --type "code" --status "implementado"

  python vault_pattern_save.py --project "ans" --name "Circuit-Breaker" --type "code" --status "en_progreso" --files "src/resilience.py" --related "Retry"

  python vault_pattern_save.py --project "ans" --name "Hexagonal" --type "architecture" --status "planificado" --description "Ports and adapters"

  python vault_pattern_save.py --project "mi-api" --name "CQRS" --type "design" --status "implementado" --notes "Ver ADR-003"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Tipos validos: design, architecture, code, integration

  - Estados validos: planificado, en_progreso, implementado, deprecado, refactoring

  - Las transiciones de estado se validan y se registran en el historial de evolucion

""",

    )

    parser.add_argument("--project", required=True, help="Project name")

    parser.add_argument("--name", required=True, help="Pattern name")

    parser.add_argument("--type", required=True, help=f"Pattern type: {PATTERN_TYPES}")

    parser.add_argument("--status", required=True, help=f"Pattern status: {PATTERN_STATUSES}")

    parser.add_argument("--description", help="Pattern description")

    parser.add_argument("--files", nargs="*", help="Files implementing this pattern")

    parser.add_argument("--related", nargs="*", help="Related pattern names")

    parser.add_argument("--notes", help="Additional notes")



    args = parser.parse_args()

    result = vault_pattern_save(

        args.project,

        args.name,

        args.type,

        args.status,

        args.description,

        args.files,

        args.related,

        args.notes,

    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1





if __name__ == "__main__":

    sys.exit(wrap_main(main, "vault_pattern_save"))

