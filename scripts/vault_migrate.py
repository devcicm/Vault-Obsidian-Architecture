#!/usr/bin/env python3
"""
Vault Migration Script
Migrate documentation from any source to vault with classification.
"""

import sys
from vault_errors import wrap_main
import os
import re
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Tuple, List

from vault_io import VAULT_ROOT

# Generic structural keywords — expand via --keywords CLI arg for project-specific terms
DEFAULT_KEYWORDS: List[str] = ["deploy", "runner", "config", "api", "service", "guide", "spec"]


def classify_file(filepath: Path, keywords: List[str]) -> Tuple[str, int]:
    """Clasifica relevancia basada en keywords y patrones estructurales."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "excluded", 0

    keyword_count = sum(len(re.findall(kw, content, re.IGNORECASE)) for kw in keywords)
    name_lower = filepath.name.lower()

    # Structural signals — generic, not project-specific
    structural_signals = ["# config", "## architecture", "## deploy", "## api", "## setup"]
    if any(sig in content.lower() for sig in structural_signals):
        if keyword_count >= 3:
            return "direct", keyword_count

    if any(sig in name_lower for sig in ["guide", "config", "spec", "architecture"]):
        if keyword_count >= 2:
            return "indirect", keyword_count

    if "obsoleto" in name_lower or "deprecated" in name_lower or "crepita" in str(filepath):
        return "excluded", 0

    if keyword_count >= 4:
        return "direct", keyword_count
    elif keyword_count >= 2:
        return "indirect", 0
    else:
        return "excluded", 0


def detect_folder(filepath: Path, content: str, project: str) -> str:
    """Detecta carpeta destino según contenido y nombre de archivo."""
    name_lower = filepath.name.lower()

    if "architecture" in name_lower or "pattern" in name_lower:
        return "05_Patterns/architecture"
    if "deployment" in name_lower or "install" in name_lower or "setup" in name_lower:
        return "08_Runbooks/deploy"
    if "runbook" in name_lower or "workflow" in name_lower:
        return "08_Runbooks/deploy"
    if "api" in name_lower or "endpoint" in name_lower or "spec" in name_lower:
        return "07_Knowledge/apis"
    if "guide" in name_lower:
        return "07_Knowledge/configs"
    if "project" in name_lower or "evaluation" in name_lower:
        return f"01_Projects/{project}"
    if "agent" in name_lower or "ai_" in name_lower:
        return f"01_Projects/{project}"
    return f"01_Projects/{project}"


def convert_links(content: str) -> str:
    """Convierte [texto](archivo.md) a [[archivo]]"""
    content = re.sub(r"\[([^\]]+)\]\(([^)]+\.md)\)", r"[[\2]]", content)
    content = re.sub(r"!\[([^\]]+)\]\(([^)]+\.(png|jpg|jpeg|gif|svg))\)", r"![[\2]]", content)
    return content


def generate_frontmatter(title: str, tags: List[str], relevance: str, project: str) -> str:
    """Genera frontmatter YAML"""
    return f"""---
id: {str(uuid.uuid4())[:8]}
title: {title}
type: documentation
relevance: {relevance}
project: {project}
tags: {json.dumps(tags)}
createdAt: {datetime.now().isoformat()[:19]}Z
migratedFrom: docs/
---"""


def migrate(source_path: str, project: str, dry_run: bool = True, keywords: List[str] = None):
    """Migra documentación al vault"""
    source = Path(source_path)
    kw = keywords if keywords else DEFAULT_KEYWORDS

    if not source.exists():
        print(f"Error: {source_path} no existe")
        return

    results = {"direct": [], "indirect": [], "excluded": []}

    # Ensure directories exist
    for relevance in ["direct", "indirect", "excluded"]:
        (VAULT_ROOT / "10_Migrated" / relevance).mkdir(parents=True, exist_ok=True)

    # Find all md files
    md_files = list(source.rglob("*.md")) if source.is_dir() else [source]

    for md_file in md_files:
        relevance, count = classify_file(md_file, kw)

        if relevance == "excluded":
            results["excluded"].append((str(md_file.relative_to(source)), "Sin relevancia"))
            continue

        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            content = convert_links(content)

            title = md_file.stem.replace("-", " ").replace("_", " ").title()
            tags = [md_file.parent.name, "migrated"]
            folder = detect_folder(md_file, content, project)

            fm = generate_frontmatter(title, tags, relevance, project)
            full_content = fm + "\n\n" + content

            # Destino
            if dry_run:
                dest = VAULT_ROOT / f"DRY_RUN/{md_file.parent.name}-{md_file.name}"
            else:
                dest = VAULT_ROOT / f"10_Migrated/{relevance}/{md_file.parent.name}-{md_file.name}"

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(full_content, encoding="utf-8")

            results[relevance].append((str(md_file.relative_to(source)), folder))

        except Exception as e:
            print(f"Error: {md_file}: {e}")

    # Generate report
    report = f"""# Migration Report - {datetime.now().strftime("%Y-%m-%d")}

## Summary

| Category | Count |
|-----------|-------|
| Direct | {len(results["direct"])} |
| Indirect | {len(results["indirect"])} |
| Excluded | {len(results["excluded"])} |

## Direct (relevancia alta)
| Original | Destino |
|----------|---------|
"""
    for orig, folder in results["direct"]:
        report += f"| {orig} | {folder} |\n"

    report += """
## Indirect (reutilizables)
| Original | Destino |
|----------|---------|
"""
    for orig, folder in results["indirect"]:
        report += f"| {orig} | {folder} |\n"

    print(report)

    if dry_run:
        print("\n[DRY-RUN] No se escribió nada. Ejecuta con dry_run=False para migrar.")
    else:
        print(f"\nMigrated: {sum(len(v) for v in results.values())} files")


def main():
    # Deprecation notice
    print(json.dumps({"_deprecation": {"use_instead": "vault_migrate_docs", "since": "v26"}}), file=sys.stderr)
    import argparse
    parser = argparse.ArgumentParser(
        description="Vault Migration Script -- Migrate documentation to vault with classification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_migrate.py --source docs/ --project mi-api
  python vault_migrate.py --source docs/ --project mi-api --dry-run
  python vault_migrate.py --source /ruta/docs --project mi-api --keywords "django,celery,redis"
  python vault_migrate.py --source docs/ --project mi-api --no-dry-run

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Por defecto opera en modo dry-run (no escribe nada, solo reporta)
  - Clasifica archivos como 'direct' (alta relevancia), 'indirect' (reutilizable) o 'excluded'
  - Convierte links markdown [texto](archivo.md) a wiki-links [[archivo]]
  - Destino final: 10_Migrated/{direct|indirect}/
""",
    )
    parser.add_argument("--source", required=True, help="Directorio o archivo fuente a migrar")
    parser.add_argument("--project", required=True, help="Slug del proyecto destino (e.g. mi-api)")
    parser.add_argument("--keywords", help="Keywords adicionales separadas por coma (e.g. 'django,celery,redis')")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Simular sin escribir (default: True)")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Ejecutar migracion real")

    args = parser.parse_args()
    extra_kw = [k.strip() for k in args.keywords.split(",")] if args.keywords else []
    migrate(args.source, project=args.project, dry_run=args.dry_run, keywords=DEFAULT_KEYWORDS + extra_kw)


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_migrate"))
