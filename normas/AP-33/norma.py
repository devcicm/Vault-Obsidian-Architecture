"""AP-33 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-33",
    "distinguido_de": {
        "AP-32": (
            "Las dos son predicados que la ontología no acepta tal cual. AP-32 es "
            "el predicado desconocido, sin equivalente canónico. AP-33 es el "
            "sinónimo: existe un canónico al que normalizar, y por eso se repara "
            "sin perder información. El discriminador es si hay destino de "
            "normalización."
        ),
    },
    "name": "Predicado no canonico — sinonimo no normalizado",
    "type": "antipattern",
    "category": "linking",
    "severity": "low",
    "enforcement": "audit",
    "description": (
        "Las relaciones de entidad usan `relationType` y las de codigo usan `type` "
        "para el mismo concepto semantico. Ademas, predicates que semanticamente "
        "son equivalentes deben unificarse: `imports` en codigo ≈ `depends_on` "
        "a nivel build-time. La ontologia define el mapeo de sinonimos."
    ),
    "signal": (
        "vault_graph_merge normaliza automaticamente y reporta normalized_predicates[] "
        "con el mapeo aplicado. vault_audit puede reportar instancias donde el "
        "predicate original no era canonico."
    ),
    "prevention": (
        "Al registrar relaciones, usar predicates del vocabulario canonico. "
        "La ontologia maneja el mapeo relationType→predicate y type→predicate "
        "automaticamente. No requiere accion manual."
    ),
    "tools_enforcing": [],
    "tools_detecting": ["vault_graph_merge"],
    "introduced_version": "v37",
}
