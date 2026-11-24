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

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_lib import yaml_scalar, slugify_strict, utcnow
from vault_io import atomic_write_text, assert_within_vault, write_report
from vault_registry import section_default_type
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vault.kernel.frontmatter_escritura import conservar_nota_generada  # noqa: E402


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
from vault.kernel.contenido import nota_escalonada  # noqa: E402
from vault.kernel.redaccion import formatear_cita_apa  # noqa: E402
from vault.autoria.frontmatter import firmante as _agente  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _bibliography_dir() -> Path:
    return _repo().seccion("12_Bibliography")


def vault_bibliography_save(
    title: str,
    url: str,
    summary: str,
    source_type: str,
    project: Optional[str] = None,
    agent: Optional[str] = None,
    tags: Optional[List[str]] = None,
    author: Optional[str] = None,
    published_date: Optional[str] = None,
    citation_style: str = "apa",
) -> Dict[str, Any]:
    source_type = source_type.lower()

    if source_type not in SOURCE_TYPES:
        return emit_error("vault_bibliography_save", "INVALID_VALUE", f"source_type inválido: {source_type}. Válidos: {SOURCE_TYPES}")

    citation_style = (citation_style or "apa").strip().lower()
    if citation_style not in ("apa", "none"):
        return emit_error("vault_bibliography_save", "INVALID_VALUE", f"citation_style inválido: {citation_style}. Válidos: ['apa', 'none']")

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

    safe_slug = slugify_strict(title)[:60].strip("-")

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

    frontmatter_lines.set("title", title, texto=True)

    frontmatter_lines.set("id", note_id)

    frontmatter_lines.set("url", url)

    frontmatter_lines.set("source_type", source_type)

    if project:
        frontmatter_lines.set("project", project, texto=True)

    frontmatter_lines.set("type", section_default_type("12_Bibliography"))

    frontmatter_lines.set("status", "draft")

    frontmatter_lines.set("agent", _agente(agent))

    frontmatter_lines.set("accessed_at", now)

    if author and str(author).strip():
        frontmatter_lines.set("author", str(author).strip(), texto=True)

    if published_date and str(published_date).strip():
        frontmatter_lines.set("published_date", str(published_date).strip(), texto=True)

    citation_apa = ""
    if citation_style == "apa":
        citation_apa = formatear_cita_apa(
            title=title,
            url=url,
            author=author,
            published_date=published_date,
            accessed_at=now,
            source_type=source_type,
        )
        frontmatter_lines.set("citation_apa", citation_apa, texto=True)

    frontmatter_lines.set("createdAt", now)

    frontmatter_lines.set("updatedAt", now)

    # Hasta v40.35 iba `json.dumps(tags)` como valor: `Frontmatter` lo citaba
    # y `yaml.safe_load` leía el texto '["a"]', no una lista (AP-26).
    # Sin tags se escribe `tags: []`, no se omite: el contrato exige la clave
    # desde v37 y omitirla dejaba la nota inválida para vault_validate (AP-12).
    frontmatter_lines.set("tags", list(tags or []))

    frontmatter_lines.set("cia_integrity", "medium")

    frontmatter_lines.set("cia_availability", "low")

    frontmatter_lines.set("cia_sensitivity", "public")


    # nota-escalonada S4: the lead says what the source is from its arguments.
    lead = (f"{title} es una fuente de tipo {source_type} consultada en {url}. "
            "Esta nota guarda su resumen y se generó con `vault_bibliography_save` "
            "en la bibliografía del vault.")
    body = "\n" + nota_escalonada(title, lead) + "\n"

    body += f"**URL:** {url}  \n"

    body += f"**Tipo:** {source_type}  \n"

    body += f"**Consultado:** {now}  \n"

    if agent:
        body += f"**Agente:** {agent}  \n"

    body += "\n---\n\n## Resumen\n\n"

    body += summary + "\n"

    if citation_apa:
        body += f"\n## Referencia APA\n\n> {citation_apa}\n"

    content = frontmatter_lines.render() + body

    # Mismo cuerpo ⇒ misma nota (v41.12): el re-guardado idéntico solo movía
    # sellos (`accessed_at`, `**Consultado:**`, fecha de acceso en APA).
    content = conservar_nota_generada(
        note_path, content,
        campos=("accessed_at", "citation_apa"),
        patrones_cuerpo=(r"^\*\*Consultado:\*\* .*$", r"^> .*Consultado el \d{4}-\d{2}-\d{2} de .*$"),
    )

    atomic_write_text(note_path, content)

    result_out: Dict[str, Any] = {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "source_type": source_type,
        "title": title,
        "agent": agent,
    }
    if citation_apa:
        result_out["citation_apa"] = citation_apa
    return result_out


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
        allow_abbrev=False,
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

    parser.add_argument("--project", type=proyecto_registrado("vault_bibliography_save"), help="Project slug this reference applies to")

    parser.add_argument(
        "--agent", help="Agent identifier (claude, codex, gpt, gemini, deepseek, human)"
    )

    parser.add_argument("--tags", nargs="*", help="Classification tags")

    parser.add_argument("--author", help="Autor o entidad responsable de la fuente (opcional; no se inventa)")

    parser.add_argument("--published-date", dest="published_date", help="Fecha o año de publicación (ej. 2026-05-01 o 2026)")

    parser.add_argument(
        "--citation-style",
        dest="citation_style",
        choices=["apa", "none"],
        default="apa",
        help="Formato de referencia generado (default: apa)",
    )

    args = parser.parse_args()

    result = vault_bibliography_save(
        args.title,
        args.url,
        args.summary,
        args.source_type,
        args.project,
        args.agent,
        args.tags,
        author=args.author,
        published_date=args.published_date,
        citation_style=args.citation_style,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_bibliography_save"))
