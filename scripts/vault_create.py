#!/usr/bin/env python3
"""
Vault Create - Crear notas desde CLI
"""

import json
import sys
from vault_errors import wrap_main
import argparse
import uuid
from pathlib import Path
from datetime import datetime


VAULT_ROOT = Path(__file__).parent.parent


def create_note(title: str, folder: str = "01_Projects", content: str = "", tags: list = None, status: str = None):
    """Crear una nota nueva"""

    # Generate slug
    slug = title.lower().replace(" ", "-").replace("_", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    # Generate frontmatter
    fm = f"""---
id: {str(uuid.uuid4())[:8]}
title: {title}
type: documentation
project: ans
tags: {tags or []}
createdAt: {datetime.now().isoformat()[:19]}Z
updatedAt: {datetime.now().isoformat()[:19]}Z
"""
    if status:
        fm += f"status: {status}\n"

    fm += "---\n\n"

    # Default content
    if not content:
        content = f"# {title}\n\nTODO: Add content here"

    # Full content
    full = fm + content

    # Save
    dest = VAULT_ROOT / folder / f"{slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(full, encoding="utf-8")

    return {"created": str(dest.relative_to(VAULT_ROOT)), "title": title}


def create_from_template(template: str, **kwargs):
    """Crear desde template"""

    templates = {
        "project": """# {title}

## Resumen
{template_description}

## Estado
- Estado: {status}
- Owner:
- Prioridad:

## Componentes
-

## Pendientes
- [ ]

## Referencias
- [[]]
""",
        "runbook": """# Runbook: {title}

## Resumen
{template_description}

## Prerequisitos
-

## Pasos
1.

## Verificación
-

## Rollback
-
""",
        "adr": """# ADR: {title}

## Estado
{propuesta} | Aceptado | Rechazado

## Contexto
Describe el contexto y el problema

## Opciones Evaluadas
### Opción 1:
- Pros:
- Contras:

### Opción 2:
- Pros:
- Contras:

## Decisión
Elegimos Opción N porque...

## Consecuencias
### Positivas
-

### Negativas
-

## Notas
""",
    }

    content = templates.get(template, templates["project"])
    return content.format(**kwargs)


def main():
    # Deprecation notice
    print(json.dumps({"_deprecation": {"use_instead": "vault_write", "since": "v26"}}), file=sys.stderr)
    parser = argparse.ArgumentParser(
        description="Vault Create - Crear notas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_create.py "Mi Proyecto" --folder "01_Projects/mi-proyecto"
  python vault_create.py "API Status" --folder "01_Projects/mi-api" --content "# API Status\\n\\nActivo" --tags api status
  python vault_create.py "Deploy API" --folder "08_Runbooks/deploy" --template runbook
  python vault_create.py "Elegir base de datos" --folder "03_Decisions" --template adr
  python vault_create.py "Nuevo servicio" --folder "01_Projects/mi-proyecto" --template project --status activo

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Templates disponibles: project, runbook, adr
  - Si no se especifica --content ni --template, se genera un esqueleto basico
""",
    )
    parser.add_argument("title", help="Titulo de la nota")
    parser.add_argument("--folder", "-f", default="01_Projects", help="Carpeta destino (e.g. 01_Projects/mi-api)")
    parser.add_argument("--content", "-c", default="", help="Contenido")
    parser.add_argument("--tags", "-t", nargs="*", default=[], help="Tags")
    parser.add_argument("--status", "-s", help="Status")
    parser.add_argument("--template", "-m", choices=["project", "runbook", "adr"], help="Template")
    parser.add_argument("--status-default", default="planificado", help="Status para ADR")

    args = parser.parse_args()

    content = args.content
    if args.template:
        content = create_from_template(
            args.template,
            title=args.title,
            template_description="Descripcion del proyecto/runbook",
            propuesta="[ ]",
            status=args.status_default,
        )

    result = create_note(title=args.title, folder=args.folder, content=content, tags=args.tags, status=args.status)

    print(f"Created: {result['created']}")
    print(f"Title: {result['title']}")


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_create"))
