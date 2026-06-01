#!/usr/bin/env python3
"""
Vault Bibliography Save Tool — Save external references consulted by the agent

Records web pages, papers, official docs, API references and books consulted
during a session. Establishes traceability for knowledge incorporated into the vault.

Usage:
    python vault_bibliography_save.py --title "Dining Philosophers" --url "https://en.wikipedia.org/wiki/Dining_philosophers_problem" --summary "Classic concurrency problem illustrating deadlock." --source_type web --agent claude
    python vault_bibliography_save.py --title "FastAPI Docs" --url "https://fastapi.tiangolo.com" --summary "Official FastAPI reference for dependency injection." --source_type docs --project my-api
"""

import argparse
import json
import re
import sys
from vault_errors import wrap_main
from vault_io import atomic_write_text, assert_within_vault, VAULT_ROOT
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


BIBLIOGRAPHY_DIR = VAULT_ROOT / "12_Bibliography"

SOURCE_TYPES = ["web", "paper", "docs", "api", "book"]

TYPE_FOLDERS = {
    "web": "12_Bibliography/web",
    "paper": "12_Bibliography/papers",
    "docs": "12_Bibliography/docs",
    "api": "12_Bibliography/apis",
    "book": "12_Bibliography/books",
}


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def vault_bibliography_save(
    title: str,
    url: str,
    summary: str,
    source_type: str,
    project: Optional[str] = None,
    agent: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    source_type = source_type.lower()

    if source_type not in SOURCE_TYPES:
        return {"ok": False, "error": f"source_type inválido: {source_type}. Válidos: {SOURCE_TYPES}"}

    if not url.strip():
        return {"ok": False, "error": "url es requerida"}

    if not summary.strip():
        return {"ok": False, "error": "summary es requerida"}

    folder_rel = TYPE_FOLDERS[source_type]
    folder_path = VAULT_ROOT / folder_rel.replace("/", "\\") if sys.platform == "win32" else VAULT_ROOT / folder_rel
    folder_path = VAULT_ROOT / Path(folder_rel)
    folder_path.mkdir(parents=True, exist_ok=True)

    safe_slug = slugify(title)[:60]
    filename = f"{safe_slug}.md"
    note_path = folder_path / filename

    now = _utcnow()
    note_id = str(uuid.uuid4())

    tags = tags or []

    try:
        assert_within_vault(note_path, VAULT_ROOT)
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "error": "INVALID_PATH", "message": str(exc)}

    frontmatter_lines = ["---"]
    frontmatter_lines.append(f"title: {title}")
    frontmatter_lines.append(f"id: {note_id}")
    frontmatter_lines.append(f"url: {url}")
    frontmatter_lines.append(f"source_type: {source_type}")
    if project:
        frontmatter_lines.append(f"project: {project}")
    frontmatter_lines.append(f"agent: {agent or 'system'}")
    frontmatter_lines.append(f"accessed_at: {now}")
    if tags:
        tags_str = json.dumps(tags, ensure_ascii=False)
        frontmatter_lines.append(f"tags: {tags_str}")
    frontmatter_lines.append(f"cia_integrity: medium")
    frontmatter_lines.append(f"cia_availability: low")
    frontmatter_lines.append(f"cia_sensitivity: public")
    frontmatter_lines.append("---")

    body = f"\n# {title}\n\n"
    body += f"**URL:** {url}  \n"
    body += f"**Tipo:** {source_type}  \n"
    body += f"**Consultado:** {now}  \n"
    if agent:
        body += f"**Agente:** {agent}  \n"
    body += "\n---\n\n## Resumen\n\n"
    body += summary + "\n"

    content = "\n".join(frontmatter_lines) + body

    atomic_write_text(note_path, content)

    return {
        "ok": True,
        "path": str(note_path.relative_to(VAULT_ROOT)).replace("\\", "/"),
        "source_type": source_type,
        "title": title,
        "agent": agent,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Bibliography Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_bibliography_save.py --title "Dining Philosophers" --url "https://en.wikipedia.org/wiki/Dining_philosophers_problem" --summary "Classic concurrency problem." --source_type web --agent claude
  python vault_bibliography_save.py --title "FastAPI Docs" --url "https://fastapi.tiangolo.com" --summary "Official FastAPI reference for dependency injection." --source_type docs --project my-api
  python vault_bibliography_save.py --title "Attention Is All You Need" --url "https://arxiv.org/abs/1706.03762" --summary "Transformer architecture paper." --source_type paper --tags ml transformers
  python vault_bibliography_save.py --title "Stripe API Reference" --url "https://stripe.com/docs/api" --summary "Stripe payment API reference." --source_type api --project mi-api

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Tipos validos: web, paper, docs, api, book
  - Establece trazabilidad del conocimiento incorporado al vault
""",
    )
    parser.add_argument("--title", required=True, help="Title of the source")
    parser.add_argument("--url", required=True, help="Full URL of the source")
    parser.add_argument("--summary", required=True, help="Summary of what this source contributed")
    parser.add_argument("--source_type", required=True, choices=SOURCE_TYPES, help=f"Source type: {SOURCE_TYPES}")
    parser.add_argument("--project", help="Project slug this reference applies to")
    parser.add_argument("--agent", help="Agent identifier (claude, codex, gpt, gemini, deepseek, human)")
    parser.add_argument("--tags", nargs="*", help="Classification tags")

    args = parser.parse_args()
    result = vault_bibliography_save(
        args.title,
        args.url,
        args.summary,
        args.source_type,
        args.project,
        args.agent,
        args.tags,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_bibliography_save"))
