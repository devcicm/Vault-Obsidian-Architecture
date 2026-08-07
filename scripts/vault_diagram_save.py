#!/usr/bin/env python3

"""

Vault Diagram Save Tool — Save diagrams in the vault



Saves Mermaid, ASCII, or PlantUML diagrams with proper frontmatter.

Categorizes into: entity, component, sequence, dependency, flow.



Usage:

    python vault_diagram_save.py --project "mi-api" --title "User Flow" --diagram_type "mermaid" --category "flow" --content "graph TD\n  A[Start] --> B[End]"

    python vault_diagram_save.py --project "ans" --title "Architecture" --diagram_type "mermaid" --category "component" --description "System components"

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import slugify_strict, utcnow
from vault_io import atomic_write_text, assert_within_vault, write_report
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional


CATEGORIES = [
    "entity",
    "component",
    "sequence",
    "dependency",
    "flow",
    "state",
    "lifecycle",
]

DIAGRAM_TYPES = ["mermaid", "ascii", "plantuml"]


CATEGORY_NOTES = {
    "entity": "ERD / entidad-relacion",
    "component": "Componentes del sistema / arquitectura",
    "sequence": "Diagramas de secuencia / interacciones",
    "dependency": "Grafos de dependencias",
    "flow": "Flujos generales y decisiones de proceso",
    "state": "Maquinas de estado / state machines (stateDiagram-v2)",
    "lifecycle": "Ciclos de vida de entidades o componentes",
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


def _diagrams_dir() -> Path:
    return _repo().seccion("06_Diagrams")


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def get_category_folder(category: str) -> Path:
    return _diagrams_dir() / category


def get_diagram_path(
    project: str, title: str, category: str, diagram_type: str
) -> Path:
    safe_project = slugify(project)

    safe_title = slugify(title)

    ext = "md"

    return get_category_folder(category) / f"{safe_project}-{safe_title}.md"


def vault_diagram_save(
    project: str,
    title: str,
    diagram_type: str,
    category: str,
    content: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    diagram_type = diagram_type.lower()

    category = category.lower()

    # Agents often pass Mermaid content with literal \n escape sequences

    # (via JSON tool calls or CLI). Convert to real newlines so diagrams render.

    content = content.replace("\\n", "\n")

    if diagram_type not in DIAGRAM_TYPES:
        return {
            "ok": False,
            "error": f"Tipo inválido: {diagram_type}. Válidos: {DIAGRAM_TYPES}",
        }

    if category not in CATEGORIES:
        # CATEGORY_NOTES existía sin que nadie lo leyera: el error listaba los
        # slugs a secas y el agente tenía que adivinar cuál le tocaba. Aquí es
        # donde esa descripción vale, así que aquí es donde se consume.
        return {
            "ok": False,
            "error": f"Categoría inválida: {category}. Válidas: {CATEGORIES}",
            "categories": {c: CATEGORY_NOTES.get(c, "") for c in CATEGORIES},
        }

    timestamp = utcnow()

    safe_project = slugify(project)

    safe_title = slugify(title)

    filename = f"{safe_project}-{safe_title}.md"

    diagram_path = get_diagram_path(project, title, category, diagram_type)

    try:
        assert_within_vault(diagram_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter = ["---"]

    frontmatter.append(f"title: {title}")

    frontmatter.append(f"id: {str(uuid.uuid4())}")

    frontmatter.append(f"project: {project}")

    frontmatter.append(f"diagramType: {diagram_type}")

    frontmatter.append(f"category: {category}")

    frontmatter.append(f"createdAt: {timestamp}")

    frontmatter.append(f"updatedAt: {timestamp}")

    frontmatter.append(f"cia_integrity: medium")

    frontmatter.append(f"cia_availability: medium")

    frontmatter.append(f"cia_sensitivity: internal")

    frontmatter.append(f"agent: system")

    frontmatter.append("---")

    body_sections = []

    if description:
        body_sections.append(f"## Descripción\n\n{description}")

    body_sections.append("## Diagrama\n\n")

    if diagram_type == "mermaid":
        body_sections.append(f"```mermaid\n{content}\n```")

    elif diagram_type == "plantuml":
        body_sections.append(f"```plantuml\n{content}\n```")

    else:
        body_sections.append(f"```\n{content}\n```")

    final_content = "\n\n".join(frontmatter) + "\n\n" + "\n\n".join(body_sections)

    diagram_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(diagram_path, final_content)

    return {
        "ok": True,
        **write_report(),
        "path": str(diagram_path.relative_to(_raiz())),
        "type": diagram_type,
        "category": category,
        "message": f"Diagram '{title}' saved to {category}/",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Diagram Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_diagram_save.py --project "mi-api" --title "User Flow" --diagram_type "mermaid" --category "flow" --content "graph TD\\n  A[Start] --> B[End]"

  python vault_diagram_save.py --project "ans" --title "Architecture" --diagram_type "mermaid" --category "component" --description "System components"

  python vault_diagram_save.py --project "backend" --title "DB Schema" --diagram_type "mermaid" --category "entity" --content "erDiagram\\n  USER ||--o{ ORDER : places"

  python vault_diagram_save.py --project "mi-api" --title "Deploy Sequence" --diagram_type "mermaid" --category "sequence" --content "sequenceDiagram\\n  Client->>Server: Request"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Tipos de diagrama: mermaid, ascii, plantuml

  - Categorias: entity, component, sequence, dependency, flow, state, lifecycle

  - Para maquinas de estado usar --category state con contenido stateDiagram-v2

  - Para ciclos de vida usar --category lifecycle

""",
    )

    parser.add_argument("--project", required=True, help="Project name")

    parser.add_argument("--title", required=True, help="Diagram title")

    parser.add_argument("--diagram_type", required=True, help=f"Type: {DIAGRAM_TYPES}")

    parser.add_argument("--category", required=True, help=f"Category: {CATEGORIES}")

    parser.add_argument(
        "--content", required=True, help="Diagram content (code without backticks)"
    )

    parser.add_argument("--description", help="Optional description")

    args = parser.parse_args()

    result = vault_diagram_save(
        args.project,
        args.title,
        args.diagram_type,
        args.category,
        args.content,
        args.description,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_diagram_save"))
