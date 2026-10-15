"""AP-14 — la entrada del catálogo, en su paquete (deuda #10, lote AP-01..AP-20).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-14",
    "distinguido_de": {
        "AP-21": (
            "Las dos son wikilinks defectuosos, y el discriminador es a cuántas "
            "notas resuelve el destino con el criterio de Obsidian —nombre de "
            "fichero, sufijo de ruta y `aliases:`—. A ninguna: AP-14, el link "
            "está roto. A una, pero con una carpeta que el nombre solo no "
            "necesita, o a varias porque falta la carpeta que desambigua: AP-21, "
            "la forma del enlace no fija la identidad. Un `[[carpeta/nota]]` que "
            "resuelve a una sola nota cuyo nombre se repite no es ninguna de las "
            "dos. Solapan en un caso, la ruta escrita que no resuelve a ninguna "
            "nota: `vault_write` la rechaza como AP-21 (`path_anchored_wikilinks`) "
            "porque la carpeta es lo que se escribió, y `vault_audit` la cuenta en "
            "`brokenLinks` como AP-14 porque no tiene destino. Mover la nota no "
            "rompe ninguna de las dos: `vault_move` reescribe los `[[nota]]` y "
            "`[[carpeta/nota]]` entrantes."
        ),
        "AP-22": (
            "AP-22 es el `[[]]` o `[[ ]]`: entre los corchetes no hay nombre que "
            "buscar ni que resolver, y la reparación es borrarlo. AP-14 tiene un "
            "destino escrito que no resuelve a ninguna nota, y se repara creando "
            "la nota o corrigiendo el nombre. El discriminador es si entre los "
            "corchetes hay texto."
        ),
        "AP-25": (
            "Las dos son referencias que no resuelven. AP-14 vive en el grafo de "
            "Obsidian —wikilinks entre notas—; AP-25 vive dentro de un diagrama "
            "mermaid, donde el nodo citado no está definido. El discriminador es "
            "el espacio de nombres en el que se busca el destino."
        ),
        "AP-34": (
            "AP-14 es el wikilink sin destino; AP-34 es la relación tipada cuyo "
            "endpoint no existe. La misma ausencia en dos capas: la sintáctica "
            "del enlace y la semántica del grafo de predicados. Una nota puede "
            "tener AP-34 con todos sus wikilinks intactos."
        ),
        "SP-02": (
            "AP-14 es el defecto ya escrito: el link roto está en el vault. SP-02 "
            "es el protocolo que lo evita —buscar el destino antes de escribir el "
            "enlace—. Una se detecta auditando; la otra se cumple o no en el "
            "momento de escribir, y su incumplimiento solo se ve como AP-14 más "
            "tarde."
        ),
    },
    "name": "Wiki-links rotos o vacíos",
    "type": "antipattern",
    "category": "linking",
    "severity": "critical",
    "enforcement": "guard+audit",
    # Precisada en v41.2. Decía «[[]] vacíos, [[ ]] con espacio, … o links
    # con path (AP-21). Dos causas raíz: (a) wrong stem, (b) path-anchored»,
    # y la señal «vault_write rechaza [[]] y [[folder/nota]]». Desde v40.35
    # un [[carpeta/nota]] que resuelve no está roto (`ruta_necesaria`), el
    # [[]] es AP-22 y la ruta que sobra es AP-21. El «o vacíos» del nombre
    # queda por la no-derogación; el vacío lo mide AP-22.
    "description": (
        "El wiki-link tiene un destino escrito que no resuelve a ninguna nota: ni "
        "por nombre de fichero, ni por sufijo de ruta, ni por aliases:. La nota "
        "destino se renombró o se borró, o nunca existió. El agente sigue links "
        "que no llevan a nada. No son AP-14 el [[]] vacío (AP-22), los corchetes "
        "desbalanceados (AP-24) ni el [[carpeta/nota]] que resuelve (si la carpeta "
        "sobra, o el nombre resuelve a varias notas, es AP-21)."
    ),
    "signal": (
        "vault_audit y vault_graph reportan brokenLinks[] con norm_code AP-14; al "
        "escribir, vault_write avisa con ghost_links[] sin bloquear (SP-02)."
    ),
    "prevention": (
        "Al escribir, SP-02: buscar el destino antes de linkar. Al mover o "
        "renombrar, vault_move reescribe los enlaces entrantes [[nota]] y "
        "[[carpeta/nota]]. Lo que quede roto lo reportan vault_graph y vault_audit."
    ),
    "tools_enforcing": ["vault_write", "vault_move"],
    "tools_detecting": ["vault_audit", "vault_graph"],
    "introduced_version": "v19",
    "revisado_en": "2026-10-09",
}
