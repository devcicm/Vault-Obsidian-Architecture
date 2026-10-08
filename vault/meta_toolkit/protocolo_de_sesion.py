"""Hoja canónica del protocolo de sesión del agente y de los perfiles que salen de él.

Hasta v41.2 el protocolo vivía solo en el manifiesto (§ Protocolo de sesión para
LLMs remotos, de v22): no nombraba el camino de recordar —`vault_context_pack` y
`vault_preferences`, de v39— y por MCP el agente recibía todas las tools `runtime`
sin saber cuáles usa una sesión. Aquí cada paso declara la tool, para qué sirve y
de dónde sale; el manifiesto lo describe y un test falla si deja de nombrar una.
Un paso que necesita un valor que solo el agente conoce (`<slug>`) declara en
`cuando` en qué sesiones se da.

Un perfil es un subconjunto del catálogo que un cliente MCP puede pedir
(`VAULT_MCP_PERFIL`). **No se escribe a mano**: `agente` es la unión de las tools
que nombra el protocolo. Sin imports fuera de `typing` —el catálogo MCP lo lee al
generar `tools-catalog.json`—.
"""

from typing import Any, Dict, List

PROTOCOLO_DE_SESION: Dict[str, Dict[str, Any]] = {
    "inicio": {
        "titulo": "Al empezar la sesión",
        "pasos": [
            {
                "tool": "vault_standard_upgrade",
                "uso": "--check",
                "para": "saber si el vault está en la versión del estándar que el agente espera",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 0",
            },
            {
                "tool": "vault_reindex",
                "uso": "--check",
                "para": "no buscar sobre un índice vacío o desfasado",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 1",
            },
            {
                "tool": "vault_validate",
                "uso": "--check structure",
                "para": "que no haya notas fuera de una sección (AP-15, CN-02)",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 2",
            },
            {
                "tool": "vault_audit",
                "uso": "",
                "para": "anotar la salud de partida para compararla al cerrar",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 3",
            },
            {
                "tool": "vault_preferences",
                "uso": "--context",
                "para": "cargar entero el contexto estable del usuario: cómo quiere que se trabaje",
                "fuente": "manifiesto § 17_Preferences: «se carga entera al inicio de sesión» (v39)",
            },
            {
                "tool": "vault_drift_detect",
                "uso": "--project <slug> --mode snapshot",
                "para": "fijar el estado del repo contra el que el cierre mide el drift",
                "fuente": "vault_drift_detect --mode snapshot: «Run with --mode report at "
                          "end of session»; ERROR_CATALOG['DRIFT_SNAPSHOT_MISSING']",
                "cuando": "la sesión trabaja sobre un proyecto registrado con su repo enlazado "
                          "(vault_project --add / --link)",
            },
        ],
    },
    "recordar": {
        "titulo": "Para recordar",
        "pasos": [
            {
                "tool": "vault_context_pack",
                "uso": "--query",
                "para": "convertir una pregunta en un paquete de contexto acotado al presupuesto",
                "fuente": "vault_servicio.CAPACIDADES['consulta_a_contexto'] (v39)",
            },
            {
                "tool": "vault_search",
                "uso": "--query",
                "para": "comprobar que una nota existe antes de enlazarla",
                "fuente": "SP-02; manifiesto § Reglas para LLMs remotos, regla 4",
            },
            {
                "tool": "vault_read",
                "uso": "--path",
                "para": "leer entera una nota que el paquete o la búsqueda señalan",
                "fuente": "pista de vault_search: «Use vault_read(path) to get full note content»",
            },
        ],
    },
    "escribir": {
        "titulo": "Para escribir",
        "pasos": [
            {
                "tool": "vault_write",
                "uso": "--folder --title --content --tags",
                "para": "toda escritura de nota: valida contrato, sección y enlaces",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 4",
            },
        ],
    },
    "borrar": {
        "titulo": "Para borrar",
        "pasos": [
            {
                "tool": "vault_delete",
                "uso": "--path --reason",
                "para": "borrar dejando la entrada del change-log antes (SP-01)",
                "fuente": "SP-01; vault_delete registra el borrado por sí misma",
            },
        ],
    },
    "operacion_masiva": {
        "titulo": "Antes de una operación masiva",
        "pasos": [
            {
                "tool": "vault_delta",
                "uso": "--snapshot",
                "para": "tener contra qué medir el impacto de la operación",
                "fuente": "SP-03",
            },
        ],
    },
    # Medido el 2026-10-07 con el perfil por MCP: un agente que recibe un error
    # y sigue su `recovery.tool` necesita poder llamarla. `recupera` nombra el
    # código del catálogo cuya pista es este paso, y un test lo comprueba.
    "recuperar": {
        "titulo": "Para seguir una pista de recuperación",
        "pasos": [
            {
                "tool": "vault_section",
                "uso": "--list",
                "para": "ver en qué secciones del vault se puede escribir",
                "fuente": "ERROR_CATALOG['INVALID_FOLDER'].recovery",
                "recupera": ["INVALID_FOLDER"],
            },
            {
                "tool": "vault_project",
                "uso": "--list",
                "para": "ver los proyectos registrados, que vault_drift_detect exige",
                "fuente": "ERROR_CATALOG['PROJECT_NOT_FOUND'].recovery",
                "recupera": ["PROJECT_NOT_FOUND"],
            },
        ],
    },
    "cierre": {
        "titulo": "Al cerrar la sesión",
        "pasos": [
            {
                "tool": "vault_drift_detect",
                "uso": "--project <slug> --mode report",
                "para": "ver qué cambió en el proyecto sin quedar documentado",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 5; "
                          "--project obligatorio desde AP-63",
                "cuando": "la sesión trabaja sobre un proyecto registrado con su repo enlazado "
                          "(vault_project --add / --link)",
            },
            {
                "tool": "vault_reindex",
                "uso": "--graph",
                "para": "dejar índice y grafo con el estado final",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 5",
            },
            {
                "tool": "vault_audit",
                "uso": "",
                "para": "que la salud no quede por debajo de la de partida",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 5",
            },
        ],
    },
}


#: Códigos del catálogo cuya `recovery.tool` no está en el perfil `agente`, con
#: el motivo por el que un agente que solo tiene el perfil no los recibe.
#: Medido el 2026-10-07; un test falla si aparece uno sin clasificar o si uno
#: de estos deja de salir del perfil. Si una tool del perfil empieza a emitir
#: alguno, la respuesta es meter su tool en `recuperar` o cambiar la pista.
PISTAS_FUERA_DEL_PERFIL: Dict[str, str] = {
    "AP19_SHADOW_INDEX": "declarado en el catálogo y sin emisor: ninguna tool lo devuelve",
    "BACKUP_NOT_FOUND": "lo traduce BACKUP_NO_ENCONTRADO, de vault.durabilidad "
                        "(restaurar y verificar snapshots), fuera del perfil",
    "CIRCULAR_WIKILINK": "declarado en el catálogo y sin emisor: ninguna tool lo devuelve",
    "SERVICE_UNAVAILABLE": "lo emiten vault_token_counter y vault_fix_all, fuera del perfil",
}


def _tools_del_protocolo() -> List[str]:
    return sorted({p["tool"] for m in PROTOCOLO_DE_SESION.values() for p in m["pasos"]})


#: Perfiles que un cliente MCP puede pedir. Cada uno es una derivación, no una lista.
PERFILES: Dict[str, Dict[str, Any]] = {
    "agente": {
        "titulo": "Las tools que nombra el protocolo de sesión",
        "deriva": _tools_del_protocolo,
    },
}


def tools_del_perfil(nombre: str) -> List[str]:
    """Las tools del perfil, ordenadas. Un perfil desconocido es `KeyError`, no `[]`."""
    return sorted(PERFILES[nombre]["deriva"]())
