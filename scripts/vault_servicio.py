#!/usr/bin/env python3
"""vault_servicio — el pilar: qué servicio de negocio presta este estándar, y qué lo realiza.

Este repo tenía diez registros canónicos —`CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`,
`GROUPS`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY`, el
`tool-spec.json` y la tabla de entorno— y ninguno decía **para qué**. Se podía
responder «esta tool, ¿en qué contexto vive?» y «esta norma, ¿qué severidad tiene?»,
pero no «esta tool, ¿a qué servicio sirve?». Sin esa respuesta, una tool nueva no
tiene contra qué justificarse y el catálogo crece por acumulación.

Dos registros y nada más. No es documentación: es de donde `vault_blueprint`
deriva las capas 1 y 2 del plano.

    python scripts/vault_servicio.py --list            # servicio y capacidades
    python scripts/vault_servicio.py --trace           # tool → grupo → capacidad → servicio
    python scripts/vault_servicio.py --check --strict  # la trazabilidad sin eslabón roto

## Por qué son tres capacidades y no dos

`CLAUDE.md` declara dos ejes: *escritura → gobernanza* (grupos 1–33) y
*consulta → contexto* (Grupo 34). Al clasificar los 37 grupos del catálogo contra
esa prosa aparecieron dos desajustes que no se pueden tapar sin mentir en el registro:

1. **El Grupo 35 (Normas, 13 tools) gobierna el estándar, no el vault del usuario.**
   `vault_gate`, `vault_doc_sync`, `vault_doc_counts`, `vault_changelog_check`,
   `vault_arch`, `vault_noop_audit`, `vault_blame_audit`, `vault_error_contract` y
   `vault_smoke` no tocan las notas de nadie: comprueban que este repo cumple lo que
   publica. Meterlos en «escritura → gobernanza» diría que sirven a la memoria del
   agente, y no es cierto. Es una **tercera capacidad**, y llevaba tiempo existiendo
   sin nombre — de hecho es la que más ha crecido en las últimas versiones.
2. **El Grupo 26 (Tokens) cae en el rango 1–33 pero sirve a la consulta.** Sus tres
   tools viven en el contexto `consulta` y existen para que un paquete de contexto
   quepa en una ventana. El rango numérico de `CLAUDE.md` es el orden en que los
   grupos se fueron añadiendo, no una clasificación.

El registro manda y la prosa se corrige: la alternativa —forzar 16 tools a un eje que
no sirven— es exactamente el fallo que este módulo existe para evitar.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import emit_error, wrap_main


# ── El servicio ──────────────────────────────────────────────────────────────

SERVICIO: Dict[str, Any] = {
    "id": "memoria_documental_gobernada",
    "titulo": "Memoria documental persistente y gobernada para agentes LLM",
    "declaracion": (
        "Dar a un agente LLM memoria documental persistente, auditable y gobernada "
        "sobre markdown plano: lo que el agente escribe queda normalizado, versionado "
        "y trazable, y lo que necesita recordar se le devuelve como contexto acotado."
    ),
    "restricciones": [
        {
            "id": "sin_base_de_datos",
            "texto": "Sin base de datos, sin embeddings y sin servicio externo.",
            "motivo": (
                "Es una decisión de producto, no una limitación pendiente de resolver: "
                "el vault debe seguir siendo legible y editable por una persona con un "
                "editor de texto, y sobrevivir a que este toolkit desaparezca."
            ),
            "declarada_en": "CLAUDE.md — Los dos ejes; vault_arch.CONTEXTS['consulta']['prohibe']",
        },
        {
            "id": "sin_dependencias",
            "texto": "Solo stdlib + PyYAML.",
            "motivo": (
                "Un agente instala el toolkit en el repo del usuario; cada dependencia "
                "es una razón para que no lo haga."
            ),
            "declarada_en": "CLAUDE.md — Qué contiene",
        },
        {
            "id": "no_derogacion",
            "texto": "Nada se elimina; lo reemplazado se anota `superseded_by:`.",
            "motivo": (
                "Los vaults consumidores leen contratos de este repo. Un campo que "
                "evapora rompe en silencio a quien lo leía."
            ),
            "declarada_en": "CLAUDE.md — regla 2; manifiesto § Política de no-derogación",
        },
    ],
}


# ── Las capacidades que lo realizan ──────────────────────────────────────────
#
# `grupos` son ids de la numeración de `scripts/README.md`, que es la fuente única
# que `vault_mcp_catalog.mapa_de_grupos()` deriva. **No hay una numeración propia
# de este módulo**: reintroducirla sería estrenar la divergencia que v40.8 cerró.

CAPACIDADES: Dict[str, Dict[str, Any]] = {
    "escritura_a_gobernanza": {
        "titulo": "Escritura → gobernanza",
        "resultado": (
            "Lo que el agente captura queda escrito una sola vez, normalizado contra "
            "las normas, versionado y auditable después."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
            18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 32, 33,
            36, 37,
        ],
    },
    "consulta_a_contexto": {
        "titulo": "Consulta → contexto",
        "resultado": (
            "Una pregunta del agente se convierte en un paquete de contexto acotado "
            "y presupuestado, recorriendo el grafo del vault sin índice externo."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [26, 34],
        "nota": (
            "El grupo 26 (Tokens) cae en el rango 1–33 que `CLAUDE.md` atribuye al "
            "primer eje, pero sus tres tools viven en el contexto `consulta` y existen "
            "para que el paquete quepa en la ventana. El rango es cronológico, no "
            "clasificatorio."
        ),
    },
    "gobernanza_del_estandar": {
        "titulo": "Gobernanza del estándar",
        "resultado": (
            "El estándar cumple lo que publica: registro canónico primero, doc "
            "derivada, guard que falla si divergen. Ninguna de estas tools toca las "
            "notas de un usuario."
        ),
        "sirve_a": "memoria_documental_gobernada",
        "grupos": [35],
        "nota": (
            "Tercera capacidad que `CLAUDE.md` no nombraba. Existía desde que se "
            "escribió la primera puerta; declararla es lo que impide que sus 13 tools "
            "se cuenten como si sirvieran a la memoria del agente."
        ),
    },
}


# ── Derivaciones ─────────────────────────────────────────────────────────────

def _mapa_de_grupos() -> Dict[str, Dict[str, Any]]:
    """`{tool: {"name": grupo, "id": group_id}}` — puerto de meta_toolkit."""
    from vault_mcp_catalog import mapa_de_grupos

    return mapa_de_grupos()


def capacidad_por_grupo() -> Dict[int, str]:
    """`{group_id: capacidad}`. Si un id se declara dos veces, gana el fallo, no el orden."""
    salida: Dict[int, str] = {}
    for nombre, datos in CAPACIDADES.items():
        for gid in datos["grupos"]:
            salida.setdefault(gid, nombre)
    return salida


def trazabilidad() -> List[Dict[str, Any]]:
    """La cadena completa, una fila por tool: tool → grupo → capacidad → servicio."""
    por_grupo = capacidad_por_grupo()
    filas = []
    for tool, datos in sorted(_mapa_de_grupos().items()):
        capacidad = por_grupo.get(datos["id"])
        filas.append(
            {
                "tool": tool,
                "group": datos["name"],
                "group_id": datos["id"],
                "capability": capacidad,
                "service": SERVICIO["id"] if capacidad else None,
            }
        )
    return filas


def check(strict: bool = False) -> Dict[str, Any]:
    """Trazabilidad exigida. Es lo que convierte esto en registro y no en prosa.

    Cuatro invariantes, ninguna con baseline: se miden en cero al declararlas
    porque los 37 grupos se clasifican en la misma tanda. Una baseline aquí
    permitiría añadir un grupo sin decidir a qué sirve, que es justo el vacío
    que este módulo cierra.
    """
    mapa = _mapa_de_grupos()
    ids_reales = {d["id"]: d["name"] for d in mapa.values()}
    por_grupo = capacidad_por_grupo()

    # 1. Todo grupo del catálogo pertenece a una capacidad.
    huerfanos = sorted(
        (
            {"group_id": gid, "group": nombre}
            for gid, nombre in ids_reales.items()
            if gid not in por_grupo
        ),
        key=lambda x: x["group_id"],
    )

    # 2. Ninguna capacidad reclama un grupo que no existe.
    inventados = sorted(
        (
            {"group_id": gid, "capability": cap}
            for gid, cap in por_grupo.items()
            if gid not in ids_reales
        ),
        key=lambda x: x["group_id"],
    )

    # 3. Ningún grupo en dos capacidades.
    duplicados = []
    vistos: Dict[int, str] = {}
    for nombre, datos in CAPACIDADES.items():
        for gid in datos["grupos"]:
            if gid in vistos:
                duplicados.append(
                    {"group_id": gid, "capabilities": [vistos[gid], nombre]}
                )
            else:
                vistos[gid] = nombre

    # 4. Toda capacidad tiene al menos una tool viva.
    tools_por_capacidad: Dict[str, int] = {c: 0 for c in CAPACIDADES}
    for fila in trazabilidad():
        if fila["capability"]:
            tools_por_capacidad[fila["capability"]] += 1
    vacias = sorted(c for c, n in tools_por_capacidad.items() if n == 0)

    # 5. Toda capacidad sirve a un servicio declarado.
    sin_servicio = sorted(
        c for c, d in CAPACIDADES.items() if d.get("sirve_a") != SERVICIO["id"]
    )

    ok = not (huerfanos or inventados or duplicados or vacias or sin_servicio)
    resultado = {
        "ok": ok,
        "tool": "vault_servicio",
        "service": SERVICIO["id"],
        "capabilities_total": len(CAPACIDADES),
        "groups_total": len(ids_reales),
        "tools_total": len(mapa),
        "tools_by_capability": tools_por_capacidad,
        "orphan_groups": huerfanos,
        "unknown_groups": inventados,
        "duplicated_groups": duplicados,
        "empty_capabilities": vacias,
        "capabilities_without_service": sin_servicio,
        "hint": (
            "Un grupo huérfano no se arregla ampliando una capacidad al azar: se "
            "decide a qué servicio sirve. Si no sirve a ninguno, la pregunta es por "
            "qué existe el grupo."
        ),
    }
    if strict and not ok:
        resultado["exit_code"] = 1
    return resultado


def listar() -> Dict[str, Any]:
    return {
        "ok": True,
        "tool": "vault_servicio",
        "service": SERVICIO,
        "capabilities": {
            nombre: {
                "titulo": datos["titulo"],
                "resultado": datos["resultado"],
                "groups": len(datos["grupos"]),
                "nota": datos.get("nota"),
            }
            for nombre, datos in CAPACIDADES.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Servicio de negocio del estándar y capacidades que lo realizan"
    )
    parser.add_argument("--list", action="store_true", help="servicio y capacidades")
    parser.add_argument("--trace", action="store_true", help="tool → capacidad → servicio")
    parser.add_argument("--check", action="store_true", help="trazabilidad exigida")
    parser.add_argument("--strict", action="store_true", help="exit 1 si falla")
    args = parser.parse_args()

    if args.trace:
        filas = trazabilidad()
        salida: Dict[str, Any] = {
            "ok": all(f["capability"] for f in filas),
            "tool": "vault_servicio",
            "rows": len(filas),
            "trace": filas,
        }
    elif args.list:
        salida = listar()
    elif args.check:
        salida = check(strict=args.strict)
    else:
        salida = listar()

    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 1 if (args.strict and not salida.get("ok")) else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_servicio"))
