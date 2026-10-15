"""SP-02 — la entrada del catálogo, en su paquete (deuda #10, lote PAT+SP+CN).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "SP-02",
    "distinguido_de": {
        "AP-14": (
            "AP-14 es el defecto ya escrito: el link roto está en el vault. SP-02 "
            "es el protocolo que lo evita —buscar el destino antes de escribir el "
            "enlace—. Una se detecta auditando; la otra se cumple o no en el "
            "momento de escribir, y su incumplimiento solo se ve como AP-14 más "
            "tarde."
        ),
        "AP-22": (
            "SP-02 es el protocolo de buscar el destino antes de escribir el "
            "enlace, y su aviso es `ghost_links[]`. Un `[[]]` no tiene destino "
            "que buscar, así que SP-02 no lo previene ni lo avisa: AP-22 lo para "
            "`vault_write` al escribir (`malformed_wikilinks`) y lo repara "
            "`vault_fix_brackets`. El discriminador es si hay un nombre que "
            "verificar."
        ),
    },
    "name": "Forward-link verification — buscar antes de linkar",
    "type": "antipattern",
    "category": "session-protocol",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Antes de escribir [[nombre-nota]] en contenido, verificar que la nota destino "
        "ya existe: vault_search(query:'nombre-nota'). Si no hay resultado, escribir "
        "en texto plano hasta que la nota exista. "
        "vault_write advierte con ghost_links[] (no bloquea) si el target no existe."
    ),
    "signal": "vault_write retorna ghost_links[] en la respuesta de éxito.",
    "prevention": "vault_search() antes de cada [[wiki-link]] nuevo. No crear links especulativos.",
    "tools_enforcing": ["vault_write"],
    "tools_detecting": ["vault_graph", "vault_audit"],
    "introduced_version": "v30",
    "revisado_en": "2026-10-09",
}
