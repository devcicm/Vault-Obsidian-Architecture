"""AP-42 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-42",
    "distinguido_de": {
        "AP-04": (
            "AP-04 mide la nota: describe como entregado algo que no lo está. "
            "AP-42 mide la tool: está publicada en el catálogo y nunca se "
            "ejecutó. El discriminador es el sujeto medido —texto frente a "
            "artefacto ejecutable—, y por eso una la detecta el audit de "
            "contenido y la otra el smoke."
        ),
    },
    "name": "Tool publicada sin haberse ejecutado nunca",
    "type": "antipattern",
    "category": "process",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Una tool se publica en el catálogo MCP porque responde a `--help` y "
        "porque su entrada existe. `--help` demuestra que el argparse se "
        "construye: no que el módulo importe sus dependencias, ni que el ejemplo "
        "documentado sea aceptado por la CLI, ni que la salida sea el JSON que el "
        "contrato promete. La primera medición dio 41 de 87 tools cuyo ejemplo "
        "documentado no llegaba a emitir un JSON con `ok` —36 de ellas porque el "
        "ejemplo del catálogo usaba flags que la CLI rechazaba, exactamente el "
        "defecto de AP-40 trasladado a la superficie de documentación."
    ),
    "signal": (
        "Ejemplos del catálogo o del README que salen con exit 2 y "
        "'unrecognized arguments'; tools cuya salida es texto para humanos sin "
        "modo JSON; tools que no aparecen en ningún test ni en ninguna ejecución."
    ),
    "prevention": (
        "vault_smoke ejecuta el ejemplo documentado de cada tool contra una copia "
        "desechable del vault de pruebas y exige tres cosas: que termine, que su "
        "salida sea JSON y que ese JSON tenga `ok`. Un `ok: false` bien formado "
        "aprueba: lo que se persigue es el fallo mudo. La baseline solo puede "
        "encoger y quedó en 0, así que es un guard duro desde el primer día. Las "
        "tools sin invocación posible (un servicio HTTP que no retorna) se "
        "declaran en SIN_SMOKE con su motivo, nunca se omiten en silencio."
    ),
    "tools_enforcing": ["vault_smoke"],
    "tools_detecting": ["vault_smoke", "vault_norms"],
    "introduced_version": "v39",
}
