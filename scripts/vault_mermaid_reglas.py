#!/usr/bin/env python3
"""vault_mermaid_reglas — la gramática de Mermaid, sin el vault debajo.

Hoja del núcleo: no importa ningún `vault_*`, solo `re` y `typing`.

## Por qué existe (AP-62, v40.28)

`validate_mermaid` es una función de texto a lista de errores: entra una cadena,
sale un diagnóstico, y no toca disco ni sabe qué es un vault. Vivía dentro de
`vault_mermaid_check`, que sí lo sabe —recorre ficheros, resuelve la raíz por
`RepositorioGobernanza` y tiene CLI—, así que `vault_onboard` y `vault_write`
cruzaban una frontera de contexto y se llevaban `vault_io` y `vault_errors`
detrás para validar una cadena que ya tenían en la mano.

Es el mismo corte que v40.27 hizo con el catálogo de normas y v40.28 con los
fundamentos y el audit: **el que sabe la regla y el que recorre el vault
aplicándola no son el mismo módulo**.

`vault_mermaid_check` los sigue reexportando: ningún llamador se rompe
(no-derogación).

## Qué NO va aquí

El recorrido. `check_file`, `scan_vault` y `fix_common_issues` se quedan en
`vault_mermaid_check`: leen ficheros, filtran snapshots y escriben. Y la
gramática de aquí es **deliberadamente parcial** —balance de llaves, prefijos
conocidos, formas de nodo—: no es un parser de Mermaid, y verde aquí no prueba
que Mermaid vaya a pintar el diagrama.
"""

import re
from typing import Any, Dict, List, Optional

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
#:
#: El `\b` inicial no cambia un solo hallazgo y es lo que separa lineal de
#: cuadrático. Sin él, `(\w+)` arranca en cada posición de una tirada de
#: caracteres de palabra, consume hasta el final y retrocede entera: 2.000
#: caracteres tardan 55 ms, 8.000 tardan 914 ms. Con el borde de palabra solo
#: hay un arranque viable y son 0,3 ms. Verificado idéntico sobre los 18.065
#: hallazgos de `vault-sandbox`, `/ans` y `/vcloud` (regla 7). El contenido lo
#: puede traer `vault_ingest` desde material que el estándar no escribió.
_NODE_SHAPES = re.compile(
    r"\b(\w+)\s*(?:\[\[.+?\]\]|\[\(.+?\)\]|\(\(.+?\)\)|\{\{.+?\}\}"
    r"|\[/.+?[/\\]\]|\[.+?\]|\(.+?\)|\{.+?\}|>.+?\])"
)

#: Un identificador suelto a cada lado de una flecha. Las etiquetas `-->|texto|`
#: se retiran antes de aplicarlo para que el texto no se lea como nodo.
_EDGE = re.compile(
    r"\b(\w[\w-]*)\s*(?:--+>?|==+>?|-\.-+>?|\.\.+>?|~~~)\s*(\w[\w-]*)"  # \b: ver _NODE_SHAPES
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

    Esa distinción es **AP-44** aplicada, y es el motivo de que esta tool figure
    como aplicadora de la norma: el criterio de «válido» lo pone el renderizador
    de Mermaid, que es quien va a dibujar el diagrama, no el gusto de este
    validador. Medir con el criterio propio habría invalidado bloques que
    Mermaid dibuja sin quejarse — la tool certificándose a sí misma.
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
    # El `\b` inicial: ver el comentario de `_NODE_SHAPES`. Sin él, 8.000
    # caracteres de palabra tardan 1.164 ms; con él, 0,30. Mismos hallazgos.
    relationship_pattern = re.compile(r"\b(\w+)\s*(--|-->|<--|<\|--|--\|>|<\|--\|>|\*--|--\*|<\|\.\.|\.\.\|>|\.\.)\s*(\w+)")

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
                "suggestion": "Revisar cantidad de { y }",
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
