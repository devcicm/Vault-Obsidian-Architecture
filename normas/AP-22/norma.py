"""AP-22 — la entrada del catálogo, en su paquete (deuda #10, lote AP-21..AP-40).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-22",
    "name": "Wiki-link vacío — [[]] sin destino",
    "type": "antipattern",
    "category": "linking",
    # Era `critical`, y contradecía al código que la aplica. `vault_audit`
    # pesa AP-22 con 2/unidad (tope 5) y AP-24 con 5/unidad (tope 15), y
    # escribe al lado por qué: «AP-22 es auto-fixable; AP-24 rompe el enlace
    # de verdad». Dos registros canónicos afirmando lo contrario sobre cuál
    # es peor. Manda el que se ejecuta (regla 3): un `[[]]` vacío no pierde
    # información y se elimina solo. Corregido en v40.10 junto con el guard
    # que compara los dos órdenes (`vault_norms_coherence`, AP-55).
    "severity": "medium",
    "enforcement": "guard+audit",
    "description": (
        "Wiki-link vacío: `[[]]` o `[[ ]]` sin destino, fuera de bloques de "
        "código. No hay información que perder, así que la reparación es "
        "eliminarlo. vault_write bloquea (hard stop). El aviso ghost_links[] por "
        "un destino que no existe no es de esta norma sino de SP-02."
    ),
    "signal": "vault_write rechaza con error_code: malformed_wikilinks. vault_audit reporta malformedWikilinks[] con norm_code AP-22.",
    "prevention": (
        "Nunca escribir [[]] vacíos: lo que aún no tiene nota destino se escribe "
        "en texto plano (SP-02). vault_fix_brackets --only empty elimina los que "
        "ya están."
    ),
    "tools_enforcing": ["vault_write"],
    "tools_detecting": ["vault_audit", "vault_fix_brackets"],
    # El desbalance de corchetes **no** es esta norma, es AP-24. La
    # `description` de AP-22 lo reclamaba —«corchetes [[ sin ]] matching»—
    # desde v34.2, cuando nació AP-24, y durante seis versiones las dos
    # normas dijeron cubrir el mismo defecto mientras el código ya las
    # separaba sin ambigüedad. El discriminador es observable, no una
    # cuestión de criterio, y por eso se declara aquí en vez de explicarse.
    "distinguido_de": {
        "AP-14": (
            "AP-22 es el `[[]]` o `[[ ]]`: entre los corchetes no hay nombre que "
            "buscar ni que resolver, y la reparación es borrarlo. AP-14 tiene un "
            "destino escrito que no resuelve a ninguna nota, y se repara creando "
            "la nota o corrigiendo el nombre. El discriminador es si entre los "
            "corchetes hay texto."
        ),
        "SP-02": (
            "SP-02 es el protocolo de buscar el destino antes de escribir el "
            "enlace, y su aviso es `ghost_links[]`. Un `[[]]` no tiene destino "
            "que buscar, así que SP-02 no lo previene ni lo avisa: AP-22 lo para "
            "`vault_write` al escribir (`malformed_wikilinks`) y lo repara "
            "`vault_fix_brackets`. El discriminador es si hay un nombre que "
            "verificar."
        ),
        "AP-24": (
            "AP-22 es el link vacío `[[]]`: no hay destino que recuperar y la "
            "reparación no pierde nada. AP-24 es el desbalance —apertura sin "
            "cierre, cierre sin apertura, anidamiento—: hay un destino escrito "
            "que el desbalance vuelve inalcanzable. `vault_audit` los separa por "
            "`norm_code` y, cuando una nota tiene ambos, publica AP-24 como "
            "primario."
        )
    },
    "introduced_version": "v29",
    "revisado_en": "2026-10-09",
}
