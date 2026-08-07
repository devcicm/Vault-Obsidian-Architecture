#!/usr/bin/env python3

"""

Vault Knowledge Save Tool — Save domain knowledge



Saves knowledge to 07_Knowledge/ subfolders: glossary, api, concept, business-rule, config.

Forces correct subfolder based on category and adds proper metadata.



Usage:

    python vault_knowledge_save.py --category "api" --title "Stripe API" --content "## Stripe API\nPayment processing..."

    python vault_knowledge_save.py --category "glossary" --title "CQRS" --content "Command Query Responsibility Segregation..."

    python vault_knowledge_save.py --category "business-rule" --title "Password Policy" --content "Minimum 8 characters..." --project "ans"

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import yaml_scalar, utcnow, slugify
from vault_io import (
    write_report,
    atomic_write_text,
    assert_within_vault,
    safe_wikilink,
    update_section_index,
)
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


CATEGORIES = [
    "glossary",
    "api",
    "concept",
    "business-rule",
    "config",
    "dependency",
    "framework",
]

CATEGORY_FOLDERS = {
    "glossary": "glossary",
    "api": "apis",
    "concept": "concepts",
    "business-rule": "business-rules",
    "config": "configs",
    "dependency": "dependencies",
    "framework": "frameworks",
}


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _knowledge_dir() -> Path:
    return _repo().seccion("07_Knowledge")


def vault_knowledge_save(
    category: str,
    title: str,
    content: str,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
) -> Dict[str, Any]:
    category = category.lower().replace(" ", "-")

    if category not in CATEGORIES:
        return {
            "ok": False,
            "error": f"Categoría inválida: {category}. Válidas: {CATEGORIES}",
        }

    folder = _knowledge_dir() / CATEGORY_FOLDERS[category]

    safe_title = slugify(title)

    filename = f"{safe_title}.md"

    note_path = folder / filename

    timestamp = utcnow()

    try:
        assert_within_vault(note_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter = ["---"]

    frontmatter.append(f"title: {json.dumps(title)}")

    frontmatter.append(f"id: {str(uuid.uuid4())}")

    frontmatter.append(f"category: {yaml_scalar(category)}")

    frontmatter.append(f"createdAt: {timestamp}")

    frontmatter.append(f"updatedAt: {timestamp}")

    if project:
        frontmatter.append(f"project: {yaml_scalar(project)}")

    if tags:
        frontmatter.append(f"tags: {json.dumps(tags)}")

    if related:
        frontmatter.append(f"related: {json.dumps(related)}")

    frontmatter.append(f"cia_integrity: medium")

    frontmatter.append(f"cia_availability: medium")

    frontmatter.append(f"cia_sensitivity: internal")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")

    if category in ["dependency", "framework"]:
        body_sections = [f"## {title}\n"]

        body_sections.append(f"\n**Propósito:** {content}\n")

        if related:
            body_sections.append(
                f"\n**Por qué se eligió:** "
                + " ".join(f"[[{safe_wikilink(r)}]]" for r in related)
                + "\n"
            )

        if tags:
            body_sections.append(
                f"\n**Alternativas descartadas:** *(pendiente de documentar)*\n"
            )

        if project:
            body_sections.append(
                f"\n**Uso en el proyecto:** *(pendiente de documentar)*\n"
            )

        body_sections.append(f"\n**Caveats:** *(pendiente de documentar)*\n")

    else:
        body_sections = [content]

    if related and category not in ["dependency", "framework"]:
        body_sections.append(
            "\n## Relacionado\n\n"
            + " ".join(f"[[{safe_wikilink(r)}]]" for r in related)
        )

    final_content = "\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    folder.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)
    update_section_index("07_Knowledge")

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())),
        "category": category,
        "title": title,
        "message": f"Knowledge note saved to {CATEGORY_FOLDERS[category]}/",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Knowledge Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_knowledge_save.py --category "api" --title "Stripe API" --content "## Stripe API\\nPayment processing..."

  python vault_knowledge_save.py --category "glossary" --title "CQRS" --content "Command Query Responsibility Segregation..."

  python vault_knowledge_save.py --category "business-rule" --title "Password Policy" --content "Minimum 8 characters..." --project "ans"

  python vault_knowledge_save.py --category "concept" --scan-path "docs/concepts/" --project "mi-api"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Con --scan-path, --title y --content son opcionales

  - Se procesan archivos .md y .txt del directorio

""",
    )

    parser.add_argument("--category", required=True, help=f"Category: {CATEGORIES}")

    parser.add_argument(
        "--title", help="Note title (optional when --scan-path is used)"
    )

    parser.add_argument(
        "--content", help="Markdown content (optional when --scan-path is used)"
    )

    parser.add_argument("--project", help="Optional project association")

    parser.add_argument("--tags", nargs="*", help="Tags")

    parser.add_argument("--related", nargs="*", help="Related note titles")

    parser.add_argument(
        "--scan-path",
        help="Directory to scan for .md and .txt files and save each as a knowledge note",
    )

    args = parser.parse_args()

    # --scan-path mode

    if args.scan_path:
        scan_dir = Path(args.scan_path)

        if not scan_dir.exists():
            print(
                json.dumps(
                    {"ok": False, "error": f"scan-path not found: {args.scan_path}"}
                )
            )

            return 1

        files = list(scan_dir.rglob("*.md")) + list(scan_dir.rglob("*.txt"))

        saved = []

        skipped = []

        for f in files:
            try:
                file_content = f.read_text(encoding="utf-8")

            except Exception as e:
                skipped.append({"file": str(f), "reason": str(e)})

                continue

            title = f.stem.replace("-", " ").replace("_", " ").title()

            category = args.category or "concept"

            result = vault_knowledge_save(
                category,
                title,
                file_content,
                args.project,
                args.tags,
                args.related,
            )

            if result.get("ok"):
                saved.append(result["path"])

            else:
                skipped.append(
                    {"file": str(f), "reason": result.get("error", "unknown")}
                )

        scan_result = {
            "ok": True,
            "scanned": len(files),
            "saved": saved,
            "skipped": skipped,
        }

        print(json.dumps(scan_result, indent=2, ensure_ascii=False))

        return 0

    # Standard single-note mode

    if not args.title:
        parser.error("--title is required when --scan-path is not used")

    if not args.content:
        parser.error("--content is required when --scan-path is not used")

    result = vault_knowledge_save(
        args.category,
        args.title,
        args.content,
        args.project,
        args.tags,
        args.related,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_knowledge_save"))
