#!/usr/bin/env python3
"""
Vault Project Overview Tool — Consolidate project overview from vault indices

Creates or updates 01_Projects/{slug}/overview.md with a structural overview
of the project: stack, dependencies, frameworks, ADRs, patterns, and infrastructure.
Automatically collects data from vault indices filtered by project tag.

Usage:
    python vault_project_overview.py --project "ans" --description "MCP Server for Ansible automation" --runtime "Python 3.10"
    python vault_project_overview.py --project "ans"
"""

import argparse
import json
import uuid
import re
import sys
from vault_errors import wrap_main
from vault_lib import utcnow, slugify
from pathlib import Path
from typing import Any, Dict, List, Optional


from vault_io import VAULT_ROOT, atomic_write_text, safe_wikilink

INDEX_FILE = VAULT_ROOT / "99_Index" / "search-index.json"


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


def get_notes_by_project(project: str) -> List[Dict[str, Any]]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    project_lower = project.lower()
    notes = []

    for note in index.get("notes", []):
        tags = note.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        project_tag = next((t for t in tags if project_lower in t.lower()), None)
        if project_tag:
            note["_projectTag"] = project_tag
            notes.append(note)

    return notes


def collect_frameworks(project: str) -> List[Dict[str, str]]:
    notes = get_notes_by_project(project)
    frameworks = []
    for note in notes:
        if "07_Knowledge/frameworks/" in note.get("path", ""):
            frameworks.append(
                {
                    "path": note["path"],
                    "title": note.get("title", ""),
                }
            )
    return frameworks


def collect_dependencies(project: str) -> List[Dict[str, str]]:
    notes = get_notes_by_project(project)
    deps = []
    for note in notes:
        if "07_Knowledge/dependencies/" in note.get("path", ""):
            deps.append(
                {
                    "path": note["path"],
                    "title": note.get("title", ""),
                }
            )
    return deps


def collect_decisions(project: str) -> List[Dict[str, str]]:
    notes = get_notes_by_project(project)
    decisions = []
    for note in notes:
        if note.get("path", "").startswith("03_Decisions/"):
            decisions.append(
                {
                    "path": note["path"],
                    "title": note.get("title", ""),
                }
            )
    return decisions


def collect_patterns(project: str) -> List[Dict[str, str]]:
    patterns_dir = VAULT_ROOT / "05_Patterns"
    if not patterns_dir.exists():
        return []

    patterns = []
    for pattern_type in ["design", "architecture", "code", "integration"]:
        type_dir = patterns_dir / pattern_type
        if not type_dir.exists():
            continue
        for note_path in type_dir.glob("*.md"):
            try:
                with open(note_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, PermissionError):
                continue

            meta = parse_frontmatter(content)
            if meta.get("project", "").lower() == project.lower():
                status = meta.get("status", "")
                if status != "deprecado":
                    patterns.append(
                        {
                            "path": str(note_path.relative_to(VAULT_ROOT)),
                            "title": note_path.stem.replace(f"{slugify(project)}-", ""),
                            "status": status,
                            "type": pattern_type,
                        }
                    )
    return patterns


def collect_infrastructure(project: str) -> List[Dict[str, str]]:
    notes = get_notes_by_project(project)
    infra = []
    for note in notes:
        if "09_Infrastructure/" in note.get("path", ""):
            infra.append(
                {
                    "path": note["path"],
                    "title": note.get("title", ""),
                }
            )
    return infra


def vault_project_overview(
    project: str,
    description: Optional[str] = None,
    runtime: Optional[str] = None,
    extra_sections: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    safe_project = slugify(project)
    project_dir = VAULT_ROOT / "01_Projects" / safe_project
    project_dir.mkdir(parents=True, exist_ok=True)

    overview_path = project_dir / "overview.md"
    timestamp = utcnow()

    existing_description = ""
    existing_runtime = ""

    if overview_path.exists():
        with open(overview_path, "r", encoding="utf-8") as f:
            content = f.read()

        meta = parse_frontmatter(content)
        existing_description = meta.get("description", "")
        body = content.split("---", 2)[-1] if content.startswith("---") else content
        runtime_match = re.search(r"\*\*Runtime:\*\* (.+)", body)
        if runtime_match:
            existing_runtime = runtime_match.group(1).strip()

    final_description = description or existing_description
    final_runtime = runtime or existing_runtime

    frameworks = collect_frameworks(project)
    dependencies = collect_dependencies(project)
    decisions = collect_decisions(project)
    patterns = collect_patterns(project)
    infrastructure = collect_infrastructure(project)

    frontmatter = ["---"]
    frontmatter.append(f"title: Overview: {project}")
    frontmatter.append(f"id: {str(uuid.uuid4())}")
    frontmatter.append(f"project: {project}")
    frontmatter.append(f"type: project-overview")
    frontmatter.append(f"createdAt: {timestamp}")
    frontmatter.append(f"updatedAt: {timestamp}")
    frontmatter.append(f"tags: {json.dumps([safe_project, 'project', 'overview'])}")
    frontmatter.append("cia_integrity: medium")
    frontmatter.append("cia_availability: medium")
    frontmatter.append("cia_sensitivity: internal")
    frontmatter.append("status: draft")
    frontmatter.append("agent: system")
    frontmatter.append("---")

    body_sections = [f"# Overview: {project}\n"]

    if final_description:
        body_sections.append(f"## Descripción\n\n{final_description}\n")

    total = len(dependencies) + len(frameworks) + len(decisions) + len(patterns)
    body_sections.append(
        f"_Actualizado: {timestamp[:10]} · deps: {len(dependencies)} · frameworks: {len(frameworks)} · ADRs: {len(decisions)} · patrones: {len(patterns)}_\n"
    )

    if final_runtime:
        body_sections.append(f"## Stack técnico\n\n- **Runtime:** {final_runtime}\n")

    if frameworks:
        body_sections.append("## Frameworks\n")
        for fw in frameworks:
            stem = Path(fw["path"]).stem
            body_sections.append(
                f"- [[{safe_wikilink(stem)}|{safe_wikilink(fw['title'])}]]"
            )
        body_sections.append("")

    if dependencies:
        body_sections.append(f"## Dependencias ({len(dependencies)})\n")
        for dep in dependencies:
            stem = Path(dep["path"]).stem
            body_sections.append(
                f"- [[{safe_wikilink(stem)}|{safe_wikilink(dep['title'])}]]"
            )
        body_sections.append("")

    if decisions:
        body_sections.append(f"## Decisiones técnicas (ADR) ({len(decisions)})\n")
        for dec in decisions:
            stem = Path(dec["path"]).stem
            body_sections.append(
                f"- [[{safe_wikilink(stem)}|{safe_wikilink(dec['title'])}]]"
            )
        body_sections.append("")

    if patterns:
        body_sections.append(f"## Patrones activos ({len(patterns)})\n")
        for pat in patterns:
            stem = Path(pat["path"]).stem
            title = pat["title"]
            status = pat.get("status", "")
            body_sections.append(
                f"- [[{safe_wikilink(stem)}|{safe_wikilink(title)}]] · `{status}`"
            )
        body_sections.append("")

    sections_written = []

    if final_runtime:
        sections_written.append("Stack técnico")
    if frameworks:
        sections_written.append("Frameworks")
    if dependencies:
        sections_written.append("Dependencias")
    if decisions:
        sections_written.append("Decisiones técnicas")
    if patterns:
        sections_written.append("Patrones activos")

    if infrastructure:
        body_sections.append(f"## Infraestructura ({len(infrastructure)})\n")
        for inf in infrastructure:
            stem = Path(inf["path"]).stem
            body_sections.append(
                f"- [[{safe_wikilink(stem)}|{safe_wikilink(inf['title'])}]]"
            )
        body_sections.append("")
        sections_written.append("Infraestructura")

    if extra_sections:
        for section_title, section_content in extra_sections.items():
            body_sections.append(f"## {section_title}\n\n{section_content}\n")
            sections_written.append(section_title)

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    atomic_write_text(overview_path, final_content)

    return {
        "ok": True,
        "path": str(overview_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "sections": sections_written,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Project Overview Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_project_overview.py --project "ans" --description "MCP Server for Ansible automation" --runtime "Python 3.10"
  python vault_project_overview.py --project "ans"
  python vault_project_overview.py --project "mi-api" --description "REST API backend" --runtime "Node.js 20"
  python vault_project_overview.py --project "mi-api" --extra_sections '{"API Keys":"Ver vault_env_save para gestion de secretos"}'

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Consolida automaticamente frameworks, deps, ADRs, patrones e infra filtrados por proyecto
  - Genera o actualiza 01_Projects/{slug}/overview.md
""",
    )
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--description", help="Project description")
    parser.add_argument("--runtime", help="Runtime (e.g., 'Python 3.10')")

    parser.add_argument(
        "--extra_sections", help='Extra sections as JSON object: {"Title": "content"}'
    )
    args = parser.parse_args()

    extra_sections = None
    if args.extra_sections:
        try:
            extra_sections = json.loads(args.extra_sections)
        except json.JSONDecodeError:
            pass

    result = vault_project_overview(
        args.project, args.description, args.runtime, extra_sections
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_project_overview"))
