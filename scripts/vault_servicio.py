#!/usr/bin/env python3
"""vault_servicio — el pilar: qué servicio de negocio presta este estándar, y qué lo realiza.

Este repo tenía diez registros canónicos —`CONTEXTS`, `NORM_CATALOG`, `FUNDAMENTALS`,
`GROUPS`, `VOCABULARIOS`, `PUERTAS`, `STATUS_VOCAB`, `LIFECYCLE_REGISTRY`, el
`tool-spec.json` y la tabla de entorno— y ninguno decía **para qué**. Se podía
responder «esta tool, ¿en qué contexto vive?» y «esta norma, ¿qué severidad tiene?»,
pero no «esta tool, ¿a qué servicio sirve?». Sin esa respuesta, una tool nueva no
tiene contra qué justificarse y el catálogo crece por acumulación.

Tres registros y nada más. No es documentación: es de donde `vault_blueprint`
deriva las capas 1 y 2 del plano.

    python scripts/vault_servicio.py --list            # servicio, capacidades y naturalezas
    python scripts/vault_servicio.py --trace           # tool → grupo → capacidad → servicio
    python scripts/vault_servicio.py --naturalezas     # qué construye, qué documenta, qué custodia
    python scripts/vault_servicio.py --check --strict  # la trazabilidad sin eslabón roto

## Dos ejes, dos preguntas distintas

`CAPACIDADES` responde **a qué sirve** una tool y se declara por grupo.
`NATURALEZAS` responde **sobre qué actúa** y se declara por tool, porque la
confusión que existe para separar —construir el vault frente a documentarlo—
ocurre *dentro* de los grupos y no entre ellos. Ver el comentario de `NATURALEZAS`.
Los dos ejes se cruzan en un solo punto verificable (`meta_estandar` ⟺
`gobernanza_del_estandar`) y `check()` exige que no discrepen.

## Por qué son tres capacidades y no dos

`CLAUDE.md` declara dos ejes: *escritura → gobernanza* (grupos 1–33) y
*consulta → contexto* (Grupo 34). Al clasificar los 37 grupos del catálogo contra
esa prosa aparecieron dos desajustes que no se pueden tapar sin mentir en el registro:

1. **El Grupo 35 (Normas) gobierna el estándar, no el vault del usuario.**
   Cuántas tools son lo dice `--trace`, no esta línea: escribirlo aquí a mano
   es AP-47, y de hecho ya se quedó en 13 mientras el grupo crecía a 17 —el
   número viajó copiado a `docs/BLUEPRINT.md` y a `CLAUDE.md`, cada uno con
   una cifra distinta y las tres verdes.
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
            "escribió la primera puerta; declararla es lo que impide que sus tools "
            "se cuenten como si sirvieran a la memoria del agente."
        ),
    },
}


# ── La naturaleza de cada tool ───────────────────────────────────────────────
#
# Segundo eje, **ortogonal** a la capacidad y con otra granularidad a propósito:
# la capacidad se declara por grupo, la naturaleza por **tool**. No es un capricho
# de diseño, es dónde está el problema — la mezcla ocurre *dentro* de los grupos:
#
#   * el grupo 1 (Core) tiene `vault_write` (documentación) junto a `vault_read`,
#     `vault_search` y `vault_list` (consulta) y `vault_move` (construcción);
#   * el grupo 15 (Índices) es construcción pura, el 6 (Salud) es custodia pura,
#     y ambos caen en la misma capacidad;
#   * `vault_ingest` escribe notas —documentación— viviendo en la capacidad de
#     consulta, que es justo lo que `CLAUDE.md` avisa cuando dice que es «la única
#     con superficie de escritura».
#
# Un eje por grupo no separa nada de eso. Por eso este es por tool.
#
# Qué responde: **¿esta tool le da forma al vault, escribe su contenido, lo
# mantiene correcto, lo lee, o mide este repo?** Confundir las dos primeras es el
# error que el usuario nombró: pedir «documenta esto» y recibir una reestructuración,
# o llamar a una tool de construcción creyendo que va a capturar contenido.
#
# Son cinco y no dos porque es lo que da la medida. Forzar 99 tools a
# construcción/documentación exigiría afirmar que `vault_backup` construye y que
# `vault_read` documenta — la misma clase de mentira que la medida desmintió en
# v40.9 con los dos ejes de capacidad. Cuando el registro y el deseo discrepan,
# manda el registro.

NATURALEZAS: Dict[str, Dict[str, Any]] = {
    "construccion": {
        "titulo": "Construcción y diseño del vault",
        "actua_sobre": "la estructura: carpetas, índices, ubicación y forma del vault",
        "distincion": (
            "Le da forma al continente, no al contenido. Si la tool decide **dónde** "
            "vive una nota o qué carpetas existen, es construcción aunque acabe "
            "escribiendo markdown."
        ),
        "tools": [
            "vault_folder_registry", "vault_init", "vault_master_index",
            "vault_merge", "vault_migrate_docs", "vault_migrate_rollback",
            "vault_move", "vault_onboard", "vault_reindex", "vault_sanacion",
            "vault_sdd_init", "vault_section_index", "vault_standard_upgrade",
        ],
    },
    "documentacion": {
        "titulo": "Documentación",
        "actua_sobre": "el contenido: lo que la nota dice",
        "distincion": (
            "Captura conocimiento en notas. Si la tool decide **qué dice** una nota "
            "y no dónde vive, es documentación. Es la capacidad de memoria "
            "propiamente dicha: sin estas tools el vault sería un esqueleto vacío."
        ),
        "tools": [
            "vault_ai_decision", "vault_append", "vault_bibliography_save",
            "vault_bug_save", "vault_change_log", "vault_code_map",
            "vault_code_module", "vault_code_relation", "vault_diagram_export",
            "vault_diagram_save", "vault_env_matrix", "vault_env_save",
            "vault_flow_save", "vault_incident_save", "vault_infra_map",
            "vault_infra_save", "vault_ingest", "vault_knowledge_save",
            "vault_log_error", "vault_ncr_save", "vault_pattern_save",
            "vault_privacy_save", "vault_project_overview", "vault_project_status",
            "vault_relation_add", "vault_release_save", "vault_requirement_save",
            "vault_risk_save", "vault_runbook_log", "vault_runbook_save",
            "vault_slo_save", "vault_test_save", "vault_timeline", "vault_write",
        ],
    },
    "custodia": {
        "titulo": "Custodia",
        "actua_sobre": "lo ya escrito: corrección, integridad y durabilidad",
        "distincion": (
            "No decide qué dice ni dónde vive: comprueba que siga siendo cierto y "
            "recuperable. Audits, validadores, auto-fixes, backups y cuarentena. "
            "Meterlas en construcción —porque «arreglan»— o en documentación "
            "—porque «escriben»— es lo que hace que un agente llame a un auto-fix "
            "cuando quería capturar contenido."
        ),
        "tools": [
            "vault_audit", "vault_backup", "vault_backup_base64",
            "vault_backup_list", "vault_code_sync", "vault_delta",
            "vault_drift_detect", "vault_fix_brackets", "vault_frontmatter_heal",
            "vault_fuente_unica", "vault_fundamentals",
            "vault_graph_fix", "vault_graph_inspect", "vault_graph_merge",
            "vault_mermaid_check", "vault_propagate", "vault_quality_check",
            "vault_quarantine", "vault_restore", "vault_restore_base64",
            "vault_security_scan", "vault_tags", "vault_validate",
        ],
    },
    "consulta": {
        "titulo": "Consulta",
        "actua_sobre": "nada — devuelve lo que ya hay",
        "distincion": (
            "Sin superficie de escritura sobre las notas. Es la única naturaleza que "
            "se puede correr sobre un vault ajeno sin pedir permiso, y por eso "
            "conviene tenerla nombrada y no deducida (regla 7)."
        ),
        "tools": [
            "vault_context_pack", "vault_code_query", "vault_diff", "vault_graph",
            "vault_impact", "vault_knowledge_get", "vault_list",
            "vault_pattern_list", "vault_preferences", "vault_query_parse",
            "vault_read", "vault_search", "vault_subgraph", "vault_token_counter",
            "vault_token_service", "vault_tokens",
        ],
    },
    "meta_estandar": {
        "titulo": "Meta-estándar",
        "actua_sobre": "este repositorio, no el vault de nadie",
        "distincion": (
            "No abre ningún vault de usuario. Miden que el estándar cumpla lo que "
            "publica. Coincide exactamente con la capacidad `gobernanza_del_estandar`, "
            "y `check()` lo exige: si un día divergen, una de las dos clasificaciones "
            "está mintiendo."
        ),
        "tools": [
            "vault_arch", "vault_blame_audit", "vault_blueprint",
            "vault_changelog_check", "vault_code_tag", "vault_doc_counts",
            "vault_doc_sync", "vault_error_contract", "vault_foreign_check",
            "vault_gate", "vault_noop_audit", "vault_norms",
            "vault_norms_coherence", "vault_criterios", "vault_ciclos",
            "vault_kernel", "vault_servicio",
            "vault_smoke", "vault_voice",
        ],
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


def naturaleza_por_tool() -> Dict[str, str]:
    """`{tool: naturaleza}`. Si una tool se declara dos veces, gana el fallo."""
    salida: Dict[str, str] = {}
    for nombre, datos in NATURALEZAS.items():
        for tool in datos["tools"]:
            salida.setdefault(tool, nombre)
    return salida


def trazabilidad() -> List[Dict[str, Any]]:
    """La cadena completa, una fila por tool: tool → grupo → capacidad → servicio.

    `nature` va en la misma fila y no en una tabla aparte porque la pregunta que
    contesta —«esto construye o documenta»— se hace sobre una tool concreta, en el
    momento de elegirla.
    """
    por_grupo = capacidad_por_grupo()
    por_tool = naturaleza_por_tool()
    filas = []
    for tool, datos in sorted(_mapa_de_grupos().items()):
        capacidad = por_grupo.get(datos["id"])
        filas.append(
            {
                "tool": tool,
                "group": datos["name"],
                "group_id": datos["id"],
                "capability": capacidad,
                "nature": por_tool.get(tool),
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

    # ── El eje de naturaleza, por tool ───────────────────────────────────────
    # Mismas invariantes y por el mismo motivo: sin baseline. Una baseline aquí
    # dejaría añadir una tool sin decidir si construye o documenta, que es
    # exactamente la confusión que el eje existe para impedir.
    por_tool = naturaleza_por_tool()

    # 6. Toda tool del catálogo tiene naturaleza.
    sin_naturaleza = sorted(t for t in mapa if t not in por_tool)

    # 7. Ninguna naturaleza reclama una tool que no está en el catálogo.
    naturaleza_inventada = sorted(t for t in por_tool if t not in mapa)

    # 8. Ninguna tool en dos naturalezas.
    naturaleza_duplicada = []
    vistas: Dict[str, str] = {}
    for nombre, datos in NATURALEZAS.items():
        for tool in datos["tools"]:
            if tool in vistas:
                naturaleza_duplicada.append(
                    {"tool": tool, "natures": [vistas[tool], nombre]}
                )
            else:
                vistas[tool] = nombre

    # 9. Toda naturaleza tiene al menos una tool viva.
    tools_por_naturaleza: Dict[str, int] = {n: 0 for n in NATURALEZAS}
    for tool, nat in por_tool.items():
        if tool in mapa:
            tools_por_naturaleza[nat] += 1
    naturalezas_vacias = sorted(n for n, c in tools_por_naturaleza.items() if c == 0)

    # 10. Los dos ejes no se contradicen donde coinciden.
    #     `meta_estandar` y `gobernanza_del_estandar` son la misma frontera vista
    #     desde dos preguntas distintas: «¿a qué sirve?» y «¿sobre qué actúa?».
    #     Que coincidan no es redundancia — es la única pareja verificable que
    #     tienen los dos ejes, y si un día divergen una de las dos miente.
    desacuerdos = []
    for fila in trazabilidad():
        es_meta_nat = fila["nature"] == "meta_estandar"
        es_meta_cap = fila["capability"] == "gobernanza_del_estandar"
        if es_meta_nat != es_meta_cap:
            desacuerdos.append(
                {
                    "tool": fila["tool"],
                    "nature": fila["nature"],
                    "capability": fila["capability"],
                }
            )

    ok = not (
        huerfanos or inventados or duplicados or vacias or sin_servicio
        or sin_naturaleza or naturaleza_inventada or naturaleza_duplicada
        or naturalezas_vacias or desacuerdos
    )
    resultado = {
        "ok": ok,
        "tool": "vault_servicio",
        "service": SERVICIO["id"],
        "capabilities_total": len(CAPACIDADES),
        "natures_total": len(NATURALEZAS),
        "groups_total": len(ids_reales),
        "tools_total": len(mapa),
        "tools_by_capability": tools_por_capacidad,
        "tools_by_nature": tools_por_naturaleza,
        "orphan_groups": huerfanos,
        "unknown_groups": inventados,
        "duplicated_groups": duplicados,
        "empty_capabilities": vacias,
        "capabilities_without_service": sin_servicio,
        "tools_without_nature": sin_naturaleza,
        "unknown_tools_in_natures": naturaleza_inventada,
        "duplicated_natures": naturaleza_duplicada,
        "empty_natures": naturalezas_vacias,
        "axis_disagreements": desacuerdos,
        "hint": (
            "Un grupo huérfano no se arregla ampliando una capacidad al azar: se "
            "decide a qué servicio sirve. Si no sirve a ninguno, la pregunta es por "
            "qué existe el grupo. Una tool sin naturaleza es la misma pregunta en el "
            "otro eje: ¿le da forma al vault, escribe su contenido, lo mantiene, lo "
            "lee, o mide este repo?"
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
        "natures": {
            nombre: {
                "titulo": datos["titulo"],
                "actua_sobre": datos["actua_sobre"],
                "distincion": datos["distincion"],
                "tools": len(datos["tools"]),
            }
            for nombre, datos in NATURALEZAS.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Servicio de negocio del estándar y capacidades que lo realizan"
    )
    parser.add_argument("--list", action="store_true", help="servicio y capacidades")
    parser.add_argument("--trace", action="store_true", help="tool → capacidad → servicio")
    parser.add_argument(
        "--naturalezas", action="store_true",
        help="tools agrupadas por naturaleza (construcción / documentación / …)",
    )
    parser.add_argument("--check", action="store_true", help="trazabilidad exigida")
    parser.add_argument("--strict", action="store_true", help="exit 1 si falla")
    args = parser.parse_args()

    if args.naturalezas:
        salida = {
            "ok": True,
            "tool": "vault_servicio",
            "natures_total": len(NATURALEZAS),
            "natures": {
                nombre: {
                    "titulo": datos["titulo"],
                    "actua_sobre": datos["actua_sobre"],
                    "distincion": datos["distincion"],
                    "tools": sorted(datos["tools"]),
                }
                for nombre, datos in NATURALEZAS.items()
            },
        }
    elif args.trace:
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
