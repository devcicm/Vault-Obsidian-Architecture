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

from vault_errors import emit_error, wrap_main
from vault_lib import yaml_scalar, slugify_strict, utcnow
from vault_io import atomic_write_text, assert_within_vault, write_report
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional


SOURCE_TYPES = ["web", "paper", "docs", "api", "book"]


TYPE_FOLDERS = {
    "web": "12_Bibliography/web",
    "paper": "12_Bibliography/papers",
    "docs": "12_Bibliography/docs",
    "api": "12_Bibliography/apis",
    "book": "12_Bibliography/books",
}


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _bibliography_dir() -> Path:
    return _repo().seccion("12_Bibliography")


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


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
        return emit_error("vault_bibliography_save", "INVALID_VALUE", f"source_type inválido: {source_type}. Válidos: {SOURCE_TYPES}")

    if not url.strip():
        return emit_error("vault_bibliography_save", "MISSING_REQUIRED_ARG", "url es requerida")

    if not summary.strip():
        return emit_error("vault_bibliography_save", "MISSING_REQUIRED_ARG", "summary es requerida")

    folder_rel = TYPE_FOLDERS[source_type]

    folder_path = (
        _raiz() / folder_rel.replace("/", "\\")
        if sys.platform == "win32"
        else _raiz() / folder_rel
    )

    folder_path = _raiz() / Path(folder_rel)

    folder_path.mkdir(parents=True, exist_ok=True)

    safe_slug = slugify(title)[:60]

    filename = f"{safe_slug}.md"

    note_path = folder_path / filename

    now = utcnow()

    note_id = str(uuid.uuid4())

    tags = tags or []

    try:
        assert_within_vault(note_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter_lines = Frontmatter()

    frontmatter_lines.set("title", title)

    frontmatter_lines.set("id", note_id)

    frontmatter_lines.set("url", url)

    frontmatter_lines.set("source_type", source_type)

    if project:
        frontmatter_lines.set("project", project)

    frontmatter_lines.set("agent", agent or 'system')

    frontmatter_lines.set("accessed_at", now)

    if tags:
        tags_str = json.dumps(tags, ensure_ascii=False)

        frontmatter_lines.set("tags", tags_str)

    frontmatter_lines.set("cia_integrity", "medium")

    frontmatter_lines.set("cia_availability", "low")

    frontmatter_lines.set("cia_sensitivity", "public")


    body = f"\n# {title}\n\n"

    body += f"**URL:** {url}  \n"

    body += f"**Tipo:** {source_type}  \n"

    body += f"**Consultado:** {now}  \n"

    if agent:
        body += f"**Agente:** {agent}  \n"

    body += "\n---\n\n## Resumen\n\n"

    body += summary + "\n"

    content = frontmatter_lines.render() + body

    atomic_write_text(note_path, content)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
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

    parser.add_argument(
        "--summary", required=True, help="Summary of what this source contributed"
    )

    parser.add_argument(
        "--source_type",
        required=True,
        choices=SOURCE_TYPES,
        help=f"Source type: {SOURCE_TYPES}",
    )

    parser.add_argument("--project", help="Project slug this reference applies to")

    parser.add_argument(
        "--agent", help="Agent identifier (claude, codex, gpt, gemini, deepseek, human)"
    )

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
