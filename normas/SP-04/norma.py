"""SP-04 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "SP-04",
    "distinguido_de": {
        "AP-36": (
            "AP-36 mira **adónde** escribe una tool: dentro del vault o fuera. "
            "SP-04 mira **quién** puede pedirle que escriba. Una tool contenida "
            "a la perfección sigue siendo un borrado remoto si cualquier página "
            "del navegador puede invocarla; y una sesión autenticada no vuelve "
            "legítima una ruta `../`. Hacen falta las dos."
        ),
    },
    "name": "Sesión MCP por HTTP sin credencial — cualquier proceso local la abre",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "critical",
    "enforcement": "guard",
    "description": (
        "El transporte HTTP/SSE del servidor MCP acepta sesiones sin token, "
        "responde con CORS abierto o atiende un `Host` que no es el suyo. "
        "Escuchar en 127.0.0.1 no lo impide: el navegador del usuario "
        "también vive ahí, y una página cualquiera podía abrir `/sse`, leer "
        "el `sessionId` e invocar `vault_delete` por `/message`. Desde "
        "v41.3 alcanza a todo servicio HTTP local del toolkit: "
        "`vault_token_service` tampoco pedía credencial, y un formulario "
        "de cualquier página podía hacerle `POST /stop` o leer un flujo "
        "con el texto del prompt guardado."
    ),
    "signal": (
        "`GET /sse` sin `Authorization: Bearer` devuelve 200; una petición "
        "con `Origin` o con un `Host` ajeno se atiende; `/health` sin token "
        "publica rutas; la respuesta de una sesión llega a otra; "
        "`vault_token_service` atiende `/status` o `/stop` sin token."
    ),
    "prevention": (
        "Token por `VAULT_MCP_TOKEN` o generado al arrancar (default "
        "cerrado), comparado en tiempo constante; `Origin` presente → 403; "
        "`Host` distinto de 127.0.0.1/localhost → 403 (DNS rebinding); sin "
        "CORS; cada respuesta solo a su sesión. stdio no abre puerto y no "
        "cambia. Lo ejerce `tests/test_mcp_http_seguridad.py` contra el "
        "servidor real, y `vault_produccion` (puerta 21) falla si la "
        "promesa `superficie_expuesta` se queda sin ese ejecutor. El "
        "servicio de tokens aplica las mismas tres comprobaciones con "
        "`VAULT_TOKEN_SERVICE_TOKEN` o un token generado que deja en el "
        "vault, junto al fichero de puerto, para su cliente; lo ejerce "
        "`tests/test_token_service_seguridad.py`."
    ),
    "tools_enforcing": ["vault_produccion", "vault_token_service"],
    "tools_detecting": [],
    "introduced_version": "v40.34",
}
