"""AP-17 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-17",
    "distinguido_de": {
        "AP-63": (
            "AP-17 necesita un canónico declarado del que la sombra se desvía. "
            "AP-63 es el proyecto sin canónico: dos carpetas o dos nombres sin "
            "que nadie diga cuál manda, y se corrige registrando, no fusionando."
        ),
        "AP-02": (
            "AP-02 son varias versiones del mismo documento conviviendo, cada una "
            "con su nombre. AP-17 es la duplicación canónico-sombra: hay un "
            "canónico declarado y una copia que lo sigue mal. El discriminador es "
            "si existe un canónico designado."
        ),
        "AP-18": (
            "AP-17 tiene canónico y sombra: una de las dos manda. AP-18 es "
            "duplicación entre carpetas sin jerarquía declarada —dos copias de "
            "igual rango—, y por eso su reparación empieza por decidir cual es la "
            "canónica, que AP-17 ya tiene decidido."
        ),
    },
    "name": "Canonical-shadow duplication",
    "type": "antipattern",
    "category": "structure",
    "severity": "medium",
    "enforcement": "audit",
    "description": (
        "Par de notas con SequenceMatcher ratio ≥ 0.85 en títulos. "
        "Típicamente una nota thin creada cuando ya existía la canónica rica. "
        "Penalización vault_audit: −2 por par. Desde v41.3 también la "
        "identidad declarada: un `aliases:` que es el nombre de fichero o "
        "el alias de otra nota, o el mismo conjunto de `files:`."
    ),
    "signal": (
        "vault_audit reporta canonicalShadow[] con similarity ≥ 0.85 "
        "(motivo `titulo`, pesa) y canonicalShadowIdentity[] (motivo "
        "`alias` o `files`, informativo)."
    ),
    "prevention": (
        "PAT-3: buscar con vault_search() antes de crear. Si existe una nota similar, "
        "enriquecer en lugar de crear. Si ya existen las dos, vault_supersede anota "
        "superseded_by en la que no manda, sin borrarla."
    ),
    "tools_enforcing": ["vault_supersede"],
    "tools_detecting": ["vault_audit"],
    "cobertura_parcial": (
        "`vault_audit._detect_canonical_shadow` mide dos formas decidibles: "
        "la del título (`SequenceMatcher` ≥ 0.85) y, desde v41.3, la "
        "identidad que la nota declara —`aliases:` y `files:`, con el "
        "criterio de resolución de Obsidian (AP-44)—. Lo que sigue sin "
        "medir son dos notas sobre lo mismo con títulos, nombres y código "
        "distintos: verlo pide comparar contenido, que el servicio descarta "
        "sin embeddings. La identidad se informa sin pesar: contra las "
        "copias de ocho consumidores dio cero pares."
    ),
    "introduced_version": "v25",
}
