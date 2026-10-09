"""AP-48 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-48",
    "distinguido_de": {
        "AP-46": (
            "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
            "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
            "es la forma general: la misma funcionalidad implementada dos veces, "
            "una por camino de acceso. Se declara así para que saldar AP-46 no se "
            "lea como haber saldado AP-48."
        ),
    },
    "name": "Implementación paralela por camino de acceso",
    "type": "antipattern",
    "category": "consistency",
    "severity": "critical",
    "enforcement": "guard+audit",
    "description": (
        "La misma tool publicada tiene dos implementaciones y cuál se ejecuta "
        "depende de por dónde entres. No es una fachada sobre un núcleo "
        "común: son dos cuerpos de código que nadie contrasta, con un solo "
        "nombre y un solo contrato publicado — así que el contrato describe "
        "como mucho a uno de los dos.\n\n"
        "Es AP-05 (múltiples fuentes de verdad) desplazado del dato al camino "
        "de ejecución, y se le parece poco en lo importante: dos definiciones "
        "de un vocabulario acaban divergiendo y alguien lo nota al leerlas, "
        "mientras que dos implementaciones divergen **en silencio** porque "
        "cada una tiene su propio público. La suite prueba una; el agente "
        "ejecuta la otra; las dos están verdes.\n\n"
        "Medido en v39.5 sobre el servidor MCP: nueve tools con backend "
        "nativo en Node, siete de ellas con script Python del mismo nombre. "
        "Ninguna de las siete compartía un solo campo de envelope con el "
        "contrato de `00_System/tool-spec.json` — `vault_fundamentals` "
        "devolvía `compliance_pct`/`passed` donde el contrato dice "
        "`path`/`total`. Y la divergencia peor no era de forma sino de "
        "efecto: la implementación nativa de `vault_graph` no escribía el "
        "grafo, así que un agente la llamaba, recibía `ok: true` y el índice "
        "se quedaba desfasado — AP-37 y AP-47 servidos por el único camino "
        "que un agente real usa. `vault_smoke` recorría las 91 tools del "
        "catálogo ejecutando el `.py`: probaba exactamente la implementación "
        "que el agente no toca."
    ),
    "signal": (
        "Una tool del catálogo tiene backend nativo en el servidor MCP **y** "
        "script en `scripts/`; el envelope que devuelve por MCP no cubre los "
        "`declared_returns` de su contrato; un side effect declarado en el "
        "contrato no ocurre por uno de los dos caminos."
    ),
    "prevention": (
        "Backend nativo solo para lo que **no tiene** implementación en "
        "Python; todo lo demás cae al runner, que es donde vive el contrato "
        "publicado. La implementación desplazada no se borra (no-derogación): "
        "se anota `superseded_by:` y se deja fuera del despacho. La regla se "
        "comprueba por comportamiento y no por lectura del código — se llama "
        "la tool por MCP y se contrasta el envelope contra el contrato, que "
        "es el criterio del consumidor y no el propio (AP-44)."
    ),
    "tools_enforcing": ["vault_mcp_catalog"],
    "tools_detecting": ["vault_norms", "vault_mcp_catalog"],
    "introduced_version": "v39.5",
}
