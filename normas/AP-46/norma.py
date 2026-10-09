"""AP-46 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-46",
    "distinguido_de": {
        "AP-12": (
            "AP-12 es el síntoma medido en las notas: dos notas del mismo tipo "
            "con frontmatter distinto. AP-46 es la causa medida en el código: no "
            "hay escritor único de frontmatter. Se separan porque el vault puede "
            "quedar coherente a mano con la causa intacta."
        ),
        "AP-48": (
            "AP-46 es el caso particular de AP-48 sobre el frontmatter: cada tool "
            "lo escribe a su manera en vez de pasar por un escritor único. AP-48 "
            "es la forma general: la misma funcionalidad implementada dos veces, "
            "una por camino de acceso. Se declara así para que saldar AP-46 no se "
            "lea como haber saldado AP-48."
        ),
    },
    "name": "Frontmatter a mano — cada tool es su propio escritor",
    "type": "antipattern",
    "category": "consistency",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "Veintiséis tools montan el frontmatter concatenando líneas y tres "
        "importan el write path canónico. Cada concatenación es un segundo autor "
        "del formato sin guard detrás: el bloque se cierra o no, `type:` está o "
        "no, la fecha lleva el formato de quien la escribió. El fallo no se ve "
        "al escribir —la tool devuelve `ok: true` porque el fichero se creó— "
        "sino al auditar, y para entonces la nota ya es el dato. Es el mismo "
        "patrón que produjo 22 implementaciones de `slugify` y tres verdades "
        "para la lista de secciones: una fuente única declarada en la "
        "documentación y N implementaciones en el código. `vault_migrate_docs` "
        "cortaba el documento por la línea 7 y llevaba versiones publicándose "
        "así, con el bloque de frontmatter sin cerrar."
    ),
    "signal": (
        "Notas con `---` de apertura que nunca cierra o cuyo bloque no parsea "
        "con `yaml.safe_load`; notas sin `type:` recién escritas por una tool; "
        "tools que construyen listas de líneas de frontmatter en vez de llamar "
        "al write path; el generador aprueba y `vault_audit` reporta "
        "`missingFrontmatter` sobre lo que él mismo acaba de escribir."
    ),
    "prevention": (
        "El write path valida lo que escribe releyendo el resultado, no "
        "confiando en cómo se construyó: `atomic_write_text` rechaza un bloque "
        "de frontmatter que abre y no cierra o que no parsea, y registra el que "
        "parsea pero sale sin `type:`. Así el guard alcanza a las 26 tools sin "
        "reescribir ninguna, y la adopción de `vault_write` puede ser gradual. "
        "Verificar con el criterio del consumidor —`yaml.safe_load`, no un "
        "regex por líneas— es AP-44 aplicado al generador."
    ),
    "tools_enforcing": ["vault_io.atomic_write_text", "vault_write"],
    # AP-46 es una norma sobre **tools**, no sobre notas: dice que veintiséis
    # tools montan el frontmatter a mano. `vault_audit` audita notas y no
    # puede verlo. Quien lo mide es `vault_norms`.
    "tools_detecting": ["vault_norms"],
    "introduced_version": "v39.3",
}
