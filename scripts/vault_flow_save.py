#!/usr/bin/env python3

"""

Vault Flow Save Tool -- Save workflows, pipelines, lifecycles and dataflows



Saves structured flow documentation to 13_Flows/{type}/ with embedded Mermaid diagram.

Supports: workflow, pipeline, lifecycle, dataflow.



Mermaid diagram types by flow type:

  workflow  -> flowchart TD (multi-actor business process with decisions)

  pipeline  -> flowchart LR (CI/CD or data pipeline with stages)

  lifecycle -> stateDiagram-v2 (entity/component state machine)

  dataflow  -> flowchart TD (data transformation: source -> process -> destination)



Usage:

    python vault_flow_save.py --project "mi-api" --name "User Registration" --type workflow --description "Full user registration process" --mermaid "flowchart TD\\n  A[User] --> B[POST /register]"

    python vault_flow_save.py --project "ans" --name "CI Pipeline" --type pipeline --description "GitHub Actions build and deploy" --mermaid "flowchart LR\\n  A[Build] --> B[Test] --> C[Deploy]" --actors "GitHub Actions,Docker,K8s"

    python vault_flow_save.py --project "mi-api" --name "Order Lifecycle" --type lifecycle --description "Order entity state machine" --mermaid "stateDiagram-v2\\n  [*] --> Pending\\n  Pending --> Confirmed"

"""

import argparse

import json

import re

import sys

from vault_errors import emit_error, wrap_main
from vault_lib import yaml_scalar, slugify_strict, utcnow
from datetime import datetime, timezone
from vault_io import atomic_write_text, assert_within_vault, write_report
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


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


def _flows_dir() -> Path:
    return _repo().seccion("13_Flows")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


FLOW_TYPES = ["workflow", "pipeline", "lifecycle", "dataflow"]


MERMAID_HINTS = {
    "workflow": "flowchart TD",
    "pipeline": "flowchart LR",
    "lifecycle": "stateDiagram-v2",
    "dataflow": "flowchart TD",
}


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


def vault_flow_save(
    project: str,
    name: str,
    flow_type: str,
    description: str,
    mermaid: str,
    steps: Optional[List[Dict[str, Any]]] = None,
    actors: Optional[str] = None,
    triggers: Optional[str] = None,
    pre_conditions: Optional[str] = None,
    post_conditions: Optional[str] = None,
    related_code: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    flow_type = flow_type.lower()

    if flow_type not in FLOW_TYPES:
        return emit_error("vault_flow_save", "INVALID_VALUE", f"Flow type '{flow_type}' not valid. Use: {FLOW_TYPES}")

    safe_project = slugify(project)

    safe_name = slugify(name)

    now = utcnow()

    note_id = str(uuid.uuid4())

    flow_dir = _flows_dir() / flow_type

    note_path = flow_dir / f"{safe_project}-{safe_name}.md"

    # Preserve id and createdAt if note exists

    created_at = now

    if note_path.exists():
        with open(note_path, "r", encoding="utf-8") as f:
            existing = f.read()

        m = re.match(r"^---\n(.*?)\n---", existing, re.DOTALL)

        if m:
            for line in m.group(1).split("\n"):
                if line.startswith("id:"):
                    note_id = line.split(":", 1)[1].strip()

                elif line.startswith("createdAt:"):
                    created_at = line.split(":", 1)[1].strip()

        action = "updated"

    else:
        action = "created"

    tag_list = list(tags or [])

    tag_list.extend([safe_project, "flow", flow_type])

    actors_list = [a.strip() for a in actors.split(",")] if actors else []

    related_list = [r.strip() for r in related_code.split(",")] if related_code else []

    try:
        assert_within_vault(note_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter = Frontmatter()
    frontmatter.set("id", note_id)
    frontmatter.set("title", name)
    frontmatter.set("project", project)
    frontmatter.set("flow_type", flow_type)
    frontmatter.set("type", "flow")
    frontmatter.set("createdAt", created_at)
    frontmatter.set("updatedAt", now)
    frontmatter.set("tags", list(dict.fromkeys(tag_list)))
    frontmatter.set("cia_integrity", "medium")
    frontmatter.set("cia_availability", "medium")
    frontmatter.set("cia_sensitivity", "internal")
    frontmatter.set("agent", "system")

    body = []

    body.append(f"**Proyecto:** `{project}`  |  **Tipo:** `{flow_type}`\n")

    body.append(f"## Descripcion\n\n{description}")

    meta_rows = []

    if triggers:
        meta_rows.append(f"| **Trigger** | {triggers} |")

    if actors_list:
        meta_rows.append(
            f"| **Actores** | {', '.join(f'`{a}`' for a in actors_list)} |"
        )

    if pre_conditions:
        meta_rows.append(f"| **Pre-condicion** | {pre_conditions} |")

    if post_conditions:
        meta_rows.append(f"| **Post-condicion** | {post_conditions} |")

    if related_list:
        links = ", ".join(f"`{r}`" for r in related_list)

        meta_rows.append(f"| **Codigo relacionado** | {links} |")

    if meta_rows:
        meta_block = ["## Metadata\n", "| Campo | Valor |", "|---|---|"] + meta_rows

        body.append("\n".join(meta_block))

    # Mermaid diagram

    body.append(f"## Diagrama\n\n```mermaid\n{mermaid}\n```")

    # Steps table

    if steps:
        step_rows = [
            "## Pasos\n",
            "| # | Nombre | Actor | Accion |",
            "|---|---|---|---|",
        ]

        for s in steps:
            step_rows.append(
                f"| {s.get('step', '')} | {s.get('name', '')} | `{s.get('actor', '')}` | {s.get('action', '')} |"
            )

        body.append("\n".join(step_rows))

    final_content = frontmatter.render() + "\n\n" + "\n\n".join(body)

    flow_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_text(note_path, final_content)

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "type": flow_type,
        "action": action,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Flow Save Tool -- workflows, pipelines, lifecycles, dataflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""

Tipos de flow y diagrama Mermaid recomendado:

  workflow  -> {MERMAID_HINTS["workflow"]}  (proceso de negocio multi-actor)

  pipeline  -> {MERMAID_HINTS["pipeline"]}  (CI/CD o data pipeline con etapas)

  lifecycle -> {MERMAID_HINTS["lifecycle"]}  (maquina de estados de entidad/componente)

  dataflow  -> {MERMAID_HINTS["dataflow"]}  (transformacion de datos)


Ejemplos:

  # Workflow de negocio

  python vault_flow_save.py --project "mi-api" --name "User Registration" --type workflow \\

    --description "Full registration process with email verification" \\

    --mermaid "flowchart TD\\n  A[User fills form] --> B[POST /register]\\n  B --> C{{Email exists?}}\\n  C -->|No| D[Create user]\\n  C -->|Yes| E[Return 409]" \\

    --actors "User,API,Database,EmailService" \\

    --triggers "User accesses /register" \\

    --steps '[{{"step":1,"name":"Submit form","actor":"User","action":"POST /register"}},{{"step":2,"name":"Validate email","actor":"API","action":"Check DB uniqueness"}}]'


  # Pipeline CI/CD

  python vault_flow_save.py --project "ans" --name "Deploy Pipeline" --type pipeline \\

    --description "GitHub Actions build test deploy" \\

    --mermaid "flowchart LR\\n  Build --> Test --> DockerBuild --> Deploy" \\

    --actors "GitHub Actions,Docker,Kubernetes"


  # Ciclo de vida de entidad

  python vault_flow_save.py --project "mi-api" --name "Order Lifecycle" --type lifecycle \\

    --description "Order state machine from creation to fulfillment" \\

    --mermaid "stateDiagram-v2\\n  [*] --> Pending\\n  Pending --> Confirmed : payment_ok\\n  Confirmed --> Shipped : warehouse_ok\\n  Shipped --> [*] : delivered"


  # Dataflow

  python vault_flow_save.py --project "ans" --name "Log Processing" --type dataflow \\

    --description "Raw logs to structured metrics" \\

    --mermaid "flowchart TD\\n  A[Raw Logs] --> B[Parser]\\n  B --> C[Aggregator]\\n  C --> D[(TimeSeries DB)]"


Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Las notas se guardan en 13_Flows/{{type}}/{{project}}-{{name}}.md

  - --steps acepta JSON array: [{{"step":1,"name":"...","actor":"...","action":"..."}}]

  - --related_code acepta rutas separadas por coma: "src/auth.py,src/user.py"

""",
    )

    parser.add_argument("--project", required=True, help="Project slug")

    parser.add_argument("--name", required=True, help="Flow name")

    parser.add_argument(
        "--type", required=True, dest="flow_type", help=f"Flow type: {FLOW_TYPES}"
    )

    parser.add_argument(
        "--description", required=True, help="What this flow does (1-3 lines)"
    )

    parser.add_argument(
        "--mermaid", required=True, help="Mermaid diagram source (without backticks)"
    )

    parser.add_argument(
        "--steps",
        help='JSON array: [{"step":1,"name":"...","actor":"...","action":"..."}]',
    )

    parser.add_argument(
        "--actors", help="Comma-separated list of actors/systems involved"
    )

    parser.add_argument("--triggers", help="What initiates this flow")

    parser.add_argument(
        "--pre_conditions", help="Required state before the flow starts"
    )

    parser.add_argument(
        "--post_conditions", help="Guaranteed state after the flow completes"
    )

    parser.add_argument(
        "--related_code", help="Comma-separated file paths of related source code"
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    args = parser.parse_args()

    steps = None

    if args.steps:
        try:
            steps = json.loads(args.steps)

        except json.JSONDecodeError as e:
            print(json.dumps(emit_error("vault_flow_save", "ARG_JSON_INVALID", f"Invalid JSON in --steps: {e}"), ensure_ascii=False))

            return 1

    result = vault_flow_save(
        args.project,
        args.name,
        args.flow_type,
        args.description,
        args.mermaid,
        steps,
        args.actors,
        args.triggers,
        args.pre_conditions,
        args.post_conditions,
        args.related_code,
        args.tags,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_flow_save"))
