"""Hoja canónica del protocolo de sesión del agente y de los perfiles que salen de él.

Hasta v41.2 el protocolo vivía solo en el manifiesto (§ Protocolo de sesión para
LLMs remotos, de v22): no nombraba el camino de recordar —`vault_context_pack` y
`vault_preferences`, de v39— y por MCP el agente recibía todas las tools `runtime`
sin saber cuáles usa una sesión. Aquí cada paso declara la tool, para qué sirve y
de dónde sale; el manifiesto lo describe y un test falla si deja de nombrar una.

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
    "cierre": {
        "titulo": "Al cerrar la sesión",
        "pasos": [
            {
                "tool": "vault_drift_detect",
                "uso": "--mode report",
                "para": "ver qué cambió en el proyecto sin quedar documentado",
                "fuente": "manifiesto § Protocolo de inicio de sesión, PASO 5",
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
