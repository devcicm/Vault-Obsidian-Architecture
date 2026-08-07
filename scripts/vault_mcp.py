#!/usr/bin/env python3
"""
Vault MCP — Orquestador Central del Vault.

Provee:
- Catálogo de 69 tools con validators
- Contexto persistido del vault
- Búsqueda de tools por propósito
- Ejecución de tools con validación
- Recomendaciones de siguientes acciones

Usage:
    python vault_mcp.py status
    python vault_mcp.py catalog
    python vault_mcp.py find "crear nota"
    python vault_mcp.py show vault_write
    python vault_mcp.py exec vault_write --params '{"folder":"01_Projects","title":"Test","content":"..."}'
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import wrap_main
from vault_io import get_vault_root

from vault_mcp_catalog import (
    TOOLS_CATALOG,
    GROUPS,
    get_tool,
    get_group_tools,
    get_all_groups,
    find_tools_by_purpose,
    get_related_tools,
)
from vault_mcp_context import (
    get_context,
    save_context,
    load_context,
    clear_context,
)


SCRIPTS_DIR = Path(__file__).parent


class VaultMCP:
    """Orquestador central del vault."""

    def __init__(self, persist_context: bool = True):
        self.context = get_context(persist=persist_context)
        self.catalog = TOOLS_CATALOG

    def catalog(self, group: Optional[str] = None) -> Dict[str, Any]:
        """Lista todas las tools o filtra por grupo."""
        if group:
            tools = get_group_tools(group)
            return {
                "ok": True,
                "group": group,
                "count": len(tools),
                "tools": [{"name": t["name"], "purpose": t["purpose"]} for t in tools],
            }

        groups_summary = []
        for g, tool_names in GROUPS.items():
            groups_summary.append({"group": g, "count": len(tool_names)})

        return {
            "ok": True,
            "total_tools": len(self.catalog),
            "groups": groups_summary,
            "command": "Use --group to filter by group",
        }

    def find(self, query: str) -> Dict[str, Any]:
        """Busca tools por propósito o palabra clave."""
        results = find_tools_by_purpose(query)
        return {
            "ok": True,
            "query": query,
            "count": len(results),
            "results": [
                {"name": r["name"], "group": r["group"], "purpose": r["purpose"]}
                for r in results
            ],
        }

    def show(self, tool_name: str) -> Dict[str, Any]:
        """Muestra detalle completo de una tool."""
        tool = get_tool(tool_name)
        if not tool:
            return {"ok": False, "error": f"Tool {tool_name} not found"}

        return {
            "ok": True,
            "name": tool["name"],
            "script": tool["script"],
            "group": tool["group"],
            "purpose": tool["purpose"],
            "params": tool["params"],
            "guards": tool["guards"],
            "side_effects": tool["side_effects"],
            "example": tool["example"],
            "related": tool.get("related", []),
        }

    def status(self) -> Dict[str, Any]:
        """Retorna estado actual del vault."""
        status = self.context.get_status()
        return {
            "ok": True,
            "vault": str(get_vault_root().name),
            "version": status["version"],
            "health_score": status["health_score"],
            "last_operation": status["last_operation"],
            "session_changes": status["session_changes_count"],
            "open_issues": status["open_issues_count"],
            "next_actions": self.context.get_next_actions(),
        }

    def health(self) -> Dict[str, Any]:
        """Ejecuta vault_audit y actualiza el contexto."""
        try:
            result = subprocess.run(
                ["python", "vault_audit.py"],
                cwd=str(SCRIPTS_DIR),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                health_score = audit_data.get("healthScore")
                self.context.set_health_score(health_score)

                next_actions = []
                for action in audit_data.get("nextActions", []):
                    if isinstance(action, str):
                        next_actions.append(action)
                    elif isinstance(action, dict):
                        next_actions.append(action.get("command", ""))

                self.context.set_next_actions(next_actions)

                return {
                    "ok": True,
                    "health_score": health_score,
                    "next_actions": next_actions,
                }
            else:
                return {
                    "ok": False,
                    "error": "vault_audit failed",
                    "details": result.stderr,
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def next_actions(self) -> Dict[str, Any]:
        """Retorna próximas acciones recomendadas."""
        actions = self.context.get_next_actions()
        if not actions:
            self.health()
            actions = self.context.get_next_actions()

        return {"ok": True, "count": len(actions), "actions": actions}

    def session(self) -> Dict[str, Any]:
        """Resumen de cambios en la sesión actual."""
        changes = self.context.get_session_changes()
        return {
            "ok": True,
            "session_started": self.context.data.get("session", {}).get("started_at"),
            "changes_count": len(changes),
            "changes": changes,
        }

    def validate(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida parámetros sin ejecutar la tool."""
        tool = get_tool(tool_name)
        if not tool:
            return {"ok": False, "error": f"Tool {tool_name} not found"}

        errors = []
        for param_name, spec in tool["params"].items():
            value = params.get(param_name)

            if spec.get("required") and not value:
                errors.append(f"Parámetro requerido: {param_name}")
                continue

            if value is None:
                continue

            for validator in spec.get("validators", []):
                if validator == "not_empty" and not value:
                    errors.append(f"{param_name} no puede estar vacío")
                elif validator.startswith("max_length:"):
                    max_len = int(validator.split(":")[1])
                    if len(value) > max_len:
                        errors.append(f"{param_name} excede {max_len} caracteres")
                elif validator.startswith("min_length:"):
                    min_len = int(validator.split(":")[1])
                    if len(value) < min_len:
                        errors.append(
                            f"{param_name} debe tener al menos {min_len} caracteres"
                        )
                elif validator.startswith("min_lines:"):
                    min_lines = int(validator.split(":")[1])
                    lines = [l for l in value.split("\n") if l.strip()]
                    if len(lines) < min_lines:
                        errors.append(
                            f"{param_name} debe tener al menos {min_lines} líneas"
                        )
                elif validator.startswith("min_words:"):
                    min_words = int(validator.split(":")[1])
                    words = value.split()
                    if len(words) < min_words:
                        errors.append(
                            f"{param_name} debe tener al menos {min_words} palabras"
                        )
                elif validator == "no_empty_bullets":
                    import re

                    if re.search(r"^\s*-\s*$", value, re.MULTILINE):
                        errors.append(f"{param_name} contiene bullets vacíos")
                elif validator.startswith("enum:"):
                    options = validator.split(":")[1].split(",")
                    if value not in options:
                        errors.append(f"{param_name} debe ser uno de: {options}")

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "tool": tool_name,
            "params": params,
        }

    def exec(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta una tool con validación."""
        validation = self.validate(tool_name, params)
        if not validation["ok"]:
            return validation

        tool = get_tool(tool_name)
        script_name = tool["script"]

        try:
            args = ["python", script_name]
            for key, value in params.items():
                if isinstance(value, bool):
                    if value:
                        args.append(f"--{key}")
                elif isinstance(value, list):
                    args.append(f"--{key}")
                    args.extend(str(v) for v in value)
                elif value is not None:
                    args.append(f"--{key}")
                    args.append(str(value))

            result = subprocess.run(
                args,
                cwd=str(SCRIPTS_DIR),
                capture_output=True,
                text=True,
                timeout=120,
            )

            output = result.stdout
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError:
                output = {"raw": result.stdout}

            if result.returncode == 0:
                path = params.get("path") or params.get(
                    "folder", ""
                ) + "/" + params.get("title", "unknown")
                self.context.record_operation(tool_name, path, ok=True, details=output)
                self.context.add_session_change(path, tool_name)

                return {"ok": True, "tool": tool_name, "output": output}
            else:
                self.context.record_operation(
                    tool_name,
                    params.get("path", "unknown"),
                    ok=False,
                    details={"error": result.stderr},
                )
                return {
                    "ok": False,
                    "error": "Tool execution failed",
                    "details": result.stderr,
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def context_save(self) -> Dict[str, Any]:
        """Fuerza guardado del contexto."""
        return save_context()

    def context_load(self) -> Dict[str, Any]:
        """Carga contexto desde JSON."""
        return load_context()


def main():
    parser = argparse.ArgumentParser(
        description="Vault MCP - Orquestador Central",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ver estado del vault
  python vault_mcp.py status

  # Listar todas las tools
  python vault_mcp.py catalog

  # Listar tools de un grupo
  python vault_mcp.py catalog --group Core

  # Buscar tools por propósito
  python vault_mcp.py find "crear nota"

  # Ver detalle de una tool
  python vault_mcp.py show vault_write

  # Ejecutar health check
  python vault_mcp.py health

  # Ver próximas acciones
  python vault_mcp.py next

  # Ver cambios de sesión
  python vault_mcp.py session

  # Validar parámetros (sin ejecutar)
  python vault_mcp.py validate vault_write --params '{"folder":"01_Projects","title":"Test","content":"# Test"}'

  # Ejecutar una tool
  python vault_mcp.py exec vault_write --params '{"folder":"01_Projects","title":"Test","content":"# Test"}'

  # Guardar contexto
  python vault_mcp.py context-save

  # Cargar contexto
  python vault_mcp.py context-load

  # Gestión de carpetas
  python vault_mcp.py folders
  python vault_mcp.py folders --scan

  # Mermaid
  python vault_mcp.py mermaid-validate
  python vault_mcp.py mermaid-validate --path "06_Diagrams/foo.md"
  python vault_mcp.py mermaid-fix

  # Diagramas
  python vault_mcp.py diagram-export --path "06_Diagrams/foo.md" --zoom 2.0

  # Reubicación
  python vault_mcp.py move --from "01_Projects/foo.md" --to "03_Decisions/foo.md"

  # Grafo
  python vault_mcp.py graph-status
  python vault_mcp.py graph-clean
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog", help="Lista tools")
    catalog_parser.add_argument("--group", help="Filtrar por grupo")

    subparsers.add_parser("find", help="Busca tools por propósito").add_argument(
        "query", help="Palabra clave"
    )

    subparsers.add_parser("show", help="Muestra detail de tool").add_argument(
        "tool", help="Nombre de tool"
    )

    subparsers.add_parser("status", help="Estado del vault")

    subparsers.add_parser("health", help="Ejecuta vault_audit")

    subparsers.add_parser("next", help="Próximas acciones")

    subparsers.add_parser("session", help="Resumen de sesión")

    validate_parser = subparsers.add_parser("validate", help="Valida parámetros")
    validate_parser.add_argument("tool", help="Nombre de tool")
    validate_parser.add_argument("--params", help="JSON con parámetros", default="{}")

    exec_parser = subparsers.add_parser("exec", help="Ejecuta tool")
    exec_parser.add_argument("tool", help="Nombre de tool")
    exec_parser.add_argument("--params", help="JSON con parámetros", default="{}")

    subparsers.add_parser("context-save", help="Guarda contexto")

    subparsers.add_parser("context-load", help="Carga contexto")

    # Gestión de carpetas
    subparsers.add_parser("folders", help="Carpetas personalizadas")
    folders_parser = subparsers.add_parser("folders", help="Carpetas registradas")
    folders_parser.add_argument(
        "--scan", action="store_true", help="Escanear carpetas nuevas"
    )
    folders_parser.add_argument("--list", action="store_true", help="Listar carpetas")
    folders_parser.add_argument(
        "--cleanup", action="store_true", help="Limpiar carpetas huérfanas"
    )

    # Mermaid
    mermaid_parser = subparsers.add_parser(
        "mermaid-validate", help="Valida diagramas Mermaid"
    )
    mermaid_parser.add_argument("--path", help="Archivo específico")
    mermaid_parser.add_argument("--project", help="Proyecto específico")
    mermaid_parser.add_argument("--json", action="store_true", help="Salida JSON")

    mermaid_fix_parser = subparsers.add_parser(
        "mermaid-fix", help="Auto-corrección de Mermaid"
    )
    mermaid_fix_parser.add_argument("--path", help="Archivo específico")
    mermaid_fix_parser.add_argument(
        "--dry-run", action="store_true", help="Simular sin aplicar"
    )

    # Diagramas export
    diagram_parser = subparsers.add_parser("diagram-export", help="Exporta diagramas")
    diagram_parser.add_argument("--path", help="Archivo a exportar")
    diagram_parser.add_argument("--project", help="Proyecto a exportar")
    diagram_parser.add_argument("--output", help="Carpeta de salida")
    diagram_parser.add_argument("--zoom", type=float, default=1.0, help="Zoom")
    diagram_parser.add_argument("--filter", help="Filtrar por tipo")

    # Move
    move_parser = subparsers.add_parser("move", help="Reubica notas")
    move_parser.add_argument("--from", dest="from_path", help="Nota origen")
    move_parser.add_argument("--to", dest="to_path", help="Nota destino")
    move_parser.add_argument("--folder", help="Carpeta origen")
    move_parser.add_argument("--to-folder", dest="to_folder", help="Carpeta destino")
    move_parser.add_argument("--dry-run", action="store_true", help="Simular")
    move_parser.add_argument("--impact", action="store_true", help="Analizar impacto")

    # Graph
    subparsers.add_parser("graph-status", help="Estado del grafo")
    subparsers.add_parser("graph-clean", help="Limpia nodos huérfanos")

    args = parser.parse_args()

    mcp = VaultMCP()

    if args.command == "catalog":
        result = mcp.catalog(args.group if hasattr(args, "group") else None)
    elif args.command == "find":
        result = mcp.find(args.query)
    elif args.command == "show":
        result = mcp.show(args.tool)
    elif args.command == "status":
        result = mcp.status()
    elif args.command == "health":
        result = mcp.health()
    elif args.command == "next":
        result = mcp.next_actions()
    elif args.command == "session":
        result = mcp.session()
    elif args.command == "validate":
        params = json.loads(args.params) if args.params != "{}" else {}
        result = mcp.validate(args.tool, params)
    elif args.command == "exec":
        params = json.loads(args.params) if args.params != "{}" else {}
        result = mcp.exec(args.tool, params)
    elif args.command == "context-save":
        result = mcp.context_save()
    elif args.command == "context-load":
        result = mcp.context_load()
    elif args.command == "folders":
        if args.scan:
            result = mcp.exec("vault_folder_registry", {"scan": True})
        elif args.list:
            result = mcp.exec("vault_folder_registry", {"list": True})
        elif args.cleanup:
            result = mcp.exec("vault_folder_registry", {"cleanup": True})
        else:
            result = mcp.exec("vault_folder_registry", {})
    elif args.command == "mermaid-validate":
        params = {}
        if args.path:
            params["path"] = args.path
        if args.project:
            params["project"] = args.project
        if args.json:
            params["json"] = True
        result = mcp.exec("vault_mermaid_check", params)
    elif args.command == "mermaid-fix":
        params = {}
        if args.path:
            params["path"] = args.path
        if args.dry_run:
            params["dry_run"] = True
        result = mcp.exec("vault_mermaid_check", params)
    elif args.command == "diagram-export":
        params = {}
        if args.path:
            params["path"] = args.path
        if args.project:
            params["project"] = args.project
        if args.output:
            params["output"] = args.output
        if args.zoom:
            params["zoom"] = args.zoom
        if args.filter:
            params["filter"] = args.filter
        result = mcp.exec("vault_diagram_export", params)
    elif args.command == "move":
        if args.impact:
            params = {
                "impact": True,
                "from_path": args.from_path,
                "to_path": args.to_path,
            }
            result = mcp.exec("vault_move", params)
        elif args.folder:
            params = {"folder": args.folder, "to_folder": args.to_folder}
            if args.dry_run:
                params["dry_run"] = True
            result = mcp.exec("vault_move", params)
        else:
            params = {"from_path": args.from_path, "to_path": args.to_path}
            if args.dry_run:
                params["dry_run"] = True
            result = mcp.exec("vault_move", params)
    elif args.command == "graph-status":
        result = mcp.exec("vault_graph", {})
    elif args.command == "graph-clean":
        result = {
            "ok": True,
            "message": "Ejecutar vault_graph para limpiar nodos huérfanos",
        }
    else:
        result = {"ok": False, "error": "Unknown command"}

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_mcp"))
