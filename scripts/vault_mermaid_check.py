#!/usr/bin/env python3

"""
Vault Mermaid Check — Validación completa de diagramas Mermaid.

Detecta errores de sintaxis en bloques ```mermaid``` y proporciona
sugerencias de corrección. Soporta: flowchart, sequenceDiagram,
classDiagram, stateDiagram, erDiagram, gantt, pie.

Usage:
    python vault_mermaid_check.py
    python vault_mermaid_check.py --path "06_Diagrams/foo.md"
    python vault_mermaid_check.py --fix
    python vault_mermaid_check.py --project "mi-api"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import wrap_main
from vault_io import is_snapshot_path, VAULT_ROOT


SCRIPTS_DIR = Path(__file__).parent


MERMAID_TYPES = {
    "flowchart": [
        "flowchart TD",
        "flowchart LR",
        "flowchart RL",
        "flowchart TB",
        "flowchart BT",
        "graph TD",
        "graph LR",
        "graph RL",
        "graph TB",
        "graph BT",
    ],
    "sequenceDiagram": ["sequenceDiagram"],
    "classDiagram": ["classDiagram", "classDiagram-v2"],
    "stateDiagram": ["stateDiagram", "stateDiagram-v2"],
    "erDiagram": ["erDiagram"],
    "gantt": ["gantt"],
    "pie": ["pie"],
}


def detect_mermaid_type(diagram: str) -> Optional[str]:
    """Detecta el tipo de diagrama Mermaid."""
    diagram = diagram.strip().split("\n")[0]
    for mtype, prefixes in MERMAID_TYPES.items():
        for prefix in prefixes:
            if diagram.startswith(prefix):
                return mtype
    return None


#: Formas de nodo de flowchart, en CUALQUIER posición de la línea.
#:
#: Antes cada patrón iba anclado con `^` y el bucle hacía `continue` tras el
#: primer acierto. Consecuencias, ambas vistas en BuilderX:
#:
#:   * `F --> G[Output HTML]` define G a la derecha de la flecha. Con el ancla,
#:     esa definición no se veía nunca.
#:   * `A[Agente] --> B[MCP Server]` sí casaba por la izquierda, pero el
#:     `continue` saltaba el escaneo de aristas de esa misma línea, así que ni
#:     se definía B ni se registraba la arista.
#:
#: Resultado: 23 de 23 hallazgos `undefined_node` del vault eran falsos, y cada
#: uno restaba 2 puntos de health score por AP-25. Un diagrama correcto no puede
#: hundir la métrica del vault.
_NODE_SHAPES = re.compile(
    r"(\w+)\s*(?:\[\[.+?\]\]|\[\(.+?\)\]|\(\(.+?\)\)|\{\{.+?\}\}"
    r"|\[/.+?[/\\]\]|\[.+?\]|\(.+?\)|\{.+?\}|>.+?\])"
)

#: Un identificador suelto a cada lado de una flecha. Las etiquetas `-->|texto|`
#: se retiran antes de aplicarlo para que el texto no se lea como nodo.
_EDGE = re.compile(
    r"(\w[\w-]*)\s*(?:--+>?|==+>?|-\.-+>?|\.\.+>?|~~~)\s*(\w[\w-]*)"
)

_EDGE_LABEL = re.compile(r"\|[^|]*\|")

#: Texto entrecomillado dentro de una forma de nodo — nunca es estructura.
_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")


def validate_flowchart(diagram: str) -> List[Dict[str, Any]]:
    """Valida diagrama flowchart.

    Nota sobre `unlabeled_node`: en Mermaid un identificador suelto (`cli -->
    core`) es un nodo perfectamente válido — se dibuja con su propio id como
    etiqueta. No es un error de sintaxis y por tanto no invalida el bloque; se
    reporta como aviso porque un id sin etiqueta documenta peor.
    """
    errors: List[Dict[str, Any]] = []
    lines = diagram.strip().split("\n")

    defined_nodes: set = set()
    referenced_nodes: set = set()

    for line in lines:
        line = line.strip()
        if not line or line.startswith(("flowchart", "graph", "%%", "subgraph", "end")):
            continue

        for m in _NODE_SHAPES.finditer(line):
            defined_nodes.add(m.group(1))

        # El texto de las etiquetas no son nodos. Se retira DESPUÉS de extraer
        # las definiciones y antes de buscar aristas: sin esto, el rombo
        # `NAV{"kind == navbar?"}` producía dos nodos fantasma, porque `==` es
        # una flecha válida y el contenido de la etiqueta se leía como grafo.
        sin_etiquetas = _EDGE_LABEL.sub(" ", _QUOTED.sub(" ", line))
        for m in _EDGE.finditer(sin_etiquetas):
            referenced_nodes.add(m.group(1))
            referenced_nodes.add(m.group(2))

    for node in sorted(referenced_nodes - defined_nodes):
        errors.append(
            {
                "type": "unlabeled_node",
                "severity": "info",
                "message": f"Nodo '{node}' se dibuja con su id porque no tiene etiqueta",
                "suggestion": f"Opcional, para legibilidad: {node}[Label]",
                "line": None,
            }
        )

    return errors


def validate_sequence(diagram: str) -> List[Dict[str, Any]]:
    """Valida diagrama sequenceDiagram."""
    errors = []
    lines = diagram.strip().split("\n")

    participants = set()
    defined_actors = set()

    participant_pattern = re.compile(r"^\s*participant\s+(\w+)")
    actor_pattern = re.compile(r"^\s*actor\s+(\w+)")

    for line in lines:
        line = line.strip()
        if line.startswith("sequenceDiagram"):
            continue

        m = participant_pattern.match(line)
        if m:
            participants.add(m.group(1))
            continue

        m = actor_pattern.match(line)
        if m:
            defined_actors.add(m.group(1))
            continue

    return errors


def validate_class(diagram: str) -> List[Dict[str, Any]]:
    """Valida classDiagram."""
    errors = []
    lines = diagram.strip().split("\n")

    defined_classes = set()
    relationship_pattern = re.compile(r"(\w+)\s*(--|-->|<--|<\|--|--\|>|<\|--\|>|\*--|--\*|<\|\.\.|\.\.\|>|\.\.)\s*(\w+)")

    class_pattern = re.compile(r"^\s*class\s+(\w+)")

    for line in lines:
        line = line.strip()
        if line.startswith("classDiagram"):
            continue

        m = class_pattern.match(line)
        if m:
            defined_classes.add(m.group(1))

        m2 = relationship_pattern.match(line)
        if m2:
            if m2.group(1) not in defined_classes:
                errors.append({
                    "type": "undefined_class",
                    "message": f"Class '{m2.group(1)}' referenced but not defined via 'class' keyword",
                    "suggestion": f"Add 'class {m2.group(1)}' to the diagram",
                })

    return errors


def validate_state(diagram: str) -> List[Dict[str, Any]]:
    """Valida stateDiagram."""
    errors = []
    lines = diagram.strip().split("\n")

    defined_states = set()
    referenced_states = set()

    state_pattern = re.compile(r"^\s*(\w+)\s*\{")
    transition_pattern = re.compile(r"(\w+)\s*-->?\s*(\w+)")

    for line in lines:
        line = line.strip()
        if line.startswith("stateDiagram"):
            continue

        m = state_pattern.match(line)
        if m:
            defined_states.add(m.group(1))
            continue

        for m in transition_pattern.finditer(line):
            referenced_states.add(m.group(1))
            referenced_states.add(m.group(2))

    undefined = referenced_states - defined_states
    for state in undefined:
        errors.append(
            {
                "type": "undefined_state",
                "message": f"Estado '{state}' referenciado pero no definido",
                "suggestion": f"Definir estado: {state} {{}}",
                "line": None,
            }
        )

    return errors


def validate_er(diagram: str) -> List[Dict[str, Any]]:
    """Valida erDiagram."""
    errors = []
    lines = diagram.strip().split("\n")

    defined_entities = set()
    relations = []

    entity_pattern = re.compile(r"^\s*(\w+)\s+\{")
    relation_pattern = re.compile(
        r"(\w+)\s+(\|\|\-\-\|o|o\-\-\||\|\-\-\|o|o\-\-\|\||\|\-\-\|\||\|\|\-\-\||o\-\-\-o)\s*(\w+)"
    )

    for line in lines:
        line = line.strip()
        if line.startswith("erDiagram"):
            continue

        m = entity_pattern.match(line)
        if m:
            defined_entities.add(m.group(1))
            continue

        m = relation_pattern.match(line)
        if m:
            relations.append((m.group(1), m.group(3)))

    for from_ent, to_ent in relations:
        if from_ent not in defined_entities:
            errors.append(
                {
                    "type": "undefined_entity",
                    "message": f"Entidad '{from_ent}' no definida",
                    "suggestion": f"Definir entidad: {from_ent} {{}}",
                    "line": None,
                }
            )
        if to_ent not in defined_entities:
            errors.append(
                {
                    "type": "undefined_entity",
                    "message": f"Entidad '{to_ent}' no definida",
                    "suggestion": f"Definir entidad: {to_ent} {{}}",
                    "line": None,
                }
            )

    return errors


def validate_gantt(diagram: str) -> List[Dict[str, Any]]:
    """Valida gantt."""
    errors = []
    lines = diagram.strip().split("\n")

    has_title = False
    has_sections = False
    has_tasks = False

    for line in lines:
        line = line.strip()
        if line.startswith("gantt"):
            continue
        if line.startswith("title "):
            has_title = True
        if line.startswith("section "):
            has_sections = True
        if re.match(r"^\w+.*:\s*\w+", line):
            has_tasks = True

    return errors


def validate_pie(diagram: str) -> List[Dict[str, Any]]:
    """Valida pie."""
    errors = []
    lines = diagram.strip().split("\n")

    has_data = False

    data_pattern = re.compile(r'^\s*"[^"]+"\s*:\s*\d+')

    for line in lines:
        line = line.strip()
        if line.startswith("pie"):
            continue
        if data_pattern.match(line):
            has_data = True

    if not has_data:
        errors.append(
            {
                "type": "no_data",
                "message": "Diagrama pie sin datos",
                "suggestion": 'Agregar datos: "Label" : valor',
                "line": None,
            }
        )

    return errors


def validate_mermaid(diagram: str) -> List[Dict[str, Any]]:
    """Valida diagrama Mermaid completo."""
    errors = []

    mtype = detect_mermaid_type(diagram)
    if not mtype:
        errors.append(
            {
                "type": "unknown_type",
                "message": "Tipo de diagrama no reconocido",
                "suggestion": "Usar: flowchart, sequenceDiagram, classDiagram, stateDiagram, erDiagram, gantt, pie",
                "line": None,
            }
        )
        return errors

    brace_count = diagram.count("{") - diagram.count("}")
    if brace_count != 0:
        errors.append(
            {
                "type": "mismatched_braces",
                "message": f"Desbalance de llaves: {brace_count} {'falta' if brace_count > 0 else 'sobra'}",
                "suggestion": "Revisar количество de { y }",
                "line": None,
            }
        )

    bracket_count = diagram.count("[") - diagram.count("]")
    if bracket_count % 2 != 0:
        errors.append(
            {
                "type": "mismatched_brackets",
                "message": f"Desbalance de corchetes: {bracket_count} sin pareja",
                "suggestion": "Revisar cantidad de [ y ]",
                "line": None,
            }
        )

    if mtype == "flowchart":
        errors.extend(validate_flowchart(diagram))
    elif mtype == "sequenceDiagram":
        errors.extend(validate_sequence(diagram))
    elif mtype == "classDiagram":
        errors.extend(validate_class(diagram))
    elif mtype == "stateDiagram":
        errors.extend(validate_state(diagram))
    elif mtype == "erDiagram":
        errors.extend(validate_er(diagram))
    elif mtype == "gantt":
        errors.extend(validate_gantt(diagram))
    elif mtype == "pie":
        errors.extend(validate_pie(diagram))

    return errors


def check_file(path: Path) -> Dict[str, Any]:
    """Verifica un archivo por bloques Mermaid."""
    result = {
        "file": str(path),
        "valid": True,
        "blocks": [],
        "errors": [],
    }

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        result["valid"] = False
        result["errors"].append({"type": "read_error", "message": str(e)})
        return result

    pattern = r"```mermaid\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    for idx, diagram in enumerate(matches):
        block_result = {
            "index": idx,
            "type": detect_mermaid_type(diagram),
            "valid": True,
            "errors": [],
        }

        todos = validate_mermaid(diagram)
        # Un aviso no invalida el diagrama. AP-25 penaliza -2 por cada entrada
        # de `errors`, así que mezclar avisos con errores de sintaxis convierte
        # una preferencia de estilo en una caída del health score.
        errors = [e for e in todos if e.get("severity") != "info"]
        avisos = [e for e in todos if e.get("severity") == "info"]
        if avisos:
            block_result["warnings"] = avisos
        if errors:
            block_result["valid"] = False
            block_result["errors"] = errors
            result["valid"] = False
            result["errors"].extend(errors)

        result["blocks"].append(block_result)

    return result


def scan_vault(
    path: Optional[Path] = None, project: Optional[str] = None
) -> Dict[str, Any]:
    """Escanea el vault por diagramas Mermaid."""
    search_root = path or VAULT_ROOT

    if project:
        search_root = VAULT_ROOT / "01_Projects" / project

    files_checked = 0
    results = []

    for md in search_root.rglob("*.md"):
        # `is_snapshot_path` sustituye al `".history" in str(md)` anterior, que
        # dejaba pasar `vault-backups/` y `.trash/`: 46 de los 69 errores AP-25
        # de BuilderX vivían en instantáneas congeladas. Peor con `--fix`, que
        # reescribía diagramas dentro de una copia de seguridad.
        # Relativo a la raíz del barrido: con la ruta absoluta, un directorio
        # ancestro FUERA del vault que se llamara `.trash` excluiría el vault
        # entero en silencio.
        try:
            rel_md = md.relative_to(search_root)
        except ValueError:  # pragma: no cover — rglob siempre cuelga de la raíz
            rel_md = md
        if is_snapshot_path(rel_md) or md.name.startswith("_"):
            continue
        files_checked += 1
        result = check_file(md)
        if result["blocks"]:
            results.append(result)

    total_errors = sum(len(r["errors"]) for r in results)
    all_valid = all(r["valid"] for r in results)

    return {
        "ok": all_valid,
        "files_checked": files_checked,
        "files_with_diagrams": len(results),
        "total_errors": total_errors,
        "results": results,
    }


def fix_common_issues(diagram: str) -> Tuple[str, List[str]]:
    """Intenta corregir errores comunes automáticamente."""
    fixes = []
    result = diagram

    result = re.sub(r"\{\s*\{", "{", result)
    result = re.sub(r"\}\s*\}", "}", result)
    if result != diagram:
        fixes.append("Colapsó llaves anidadas")

    result = re.sub(r"\[\s*\[", "[", result)
    result = re.sub(r"\]\s*\]", "]", result)
    if result != diagram:
        fixes.append("Colapsó corchetes anidados")

    return result, fixes


def main():
    parser = argparse.ArgumentParser(
        description="Vault Mermaid Check - Valida diagramas Mermaid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_mermaid_check.py
  python vault_mermaid_check.py --path "06_Diagrams/foo.md"
  python vault_mermaid_check.py --project "mi-api"
  python vault_mermaid_check.py --fix
  python vault_mermaid_check.py --path "06_Diagrams/foo.md" --fix
        """,
    )

    parser.add_argument("--path", type=str, help="Archivo específico a verificar")
    parser.add_argument("--project", type=str, help="Proyecto a verificar")
    parser.add_argument("--fix", action="store_true", help="Intentar auto-corrección")
    parser.add_argument("--json", action="store_true", help="Salida JSON")

    args = parser.parse_args()

    if args.path:
        path = VAULT_ROOT / args.path
        if not path.exists():
            print(
                json.dumps(
                    {"ok": False, "error": f"Archivo no encontrado: {args.path}"}
                )
            )
            return 1
        result = check_file(path)
    elif args.project:
        result = scan_vault(project=args.project)
    else:
        result = scan_vault()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("ok", True):
            print(
                f"✓ Validación exitosa: {result.get('files_with_diagrams', 0)} diagramas revisados"
            )
            return 0
        else:
            print(f"✗ Errores encontrados: {result.get('total_errors', 0)}")
            for res in result.get("results", []):
                if not res["valid"]:
                    print(f"\nArchivo: {res['file']}")
                    for block in res.get("blocks", []):
                        if not block["valid"]:
                            for err in block.get("errors", []):
                                print(f"  - {err['type']}: {err['message']}")
                                if err.get("suggestion"):
                                    print(f"    Sugerencia: {err['suggestion']}")
            return 1

    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_mermaid_check"))
