"""AP-50 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-50",
    "name": "Decisión duplicada sin dueño declarado",
    "type": "antipattern",
    "category": "architecture",
    "severity": "high",
    "enforcement": "guard+audit",
    "description": (
        "La misma **decisión** —qué valores son válidos, cuál es el default, "
        "cómo se escapa un campo— se toma en más de un punto de uso sin que "
        "ningún registro declare quién manda. No es AP-05: aquel habla de un "
        "**dato** con dos fuentes, y se ve porque las dos copias divergen. "
        "Esto se ve cuando ya divergieron, que es tarde.\n\n"
        "Lo que lo hace caro es que cada copia parece correcta en su sitio. "
        "`SEVERITIES = ['critical', 'high', 'medium', 'low']` no está mal "
        "escrito en ninguno de los catorce ficheros donde se midió; está mal "
        "que sean catorce y que nada los compare. El día que el registro "
        "cambie, la copia que se quede atrás rechazará un valor válido o "
        "aceptará uno inventado, y ningún test lo notará porque cada fichero "
        "sigue siendo coherente consigo mismo.\n\n"
        "Medido en v40.1 por sus tres guards: **0 copias de vocabulario, 0 "
        "lecturas de entorno sin declarar, 0 vocabularios sin contexto "
        "dueño**. Eran 14 copias del vocabulario en 13 módulos —cuatro como "
        "`choices=` de argparse y diez como constante— y 13 variables de "
        "entorno con su default escrito en cada punto de lectura, de las que "
        "solo seis estaban documentadas. Dos ya habían divergido antes de "
        "que existiera el guard: `VAULT_VOICE` se comparaba contra "
        "`'verbose'` en un módulo y contra `'0'` con default `'1'` en otro, y "
        "`VAULT_MCP_LOG` estaba declarada como fichero de log mientras el "
        "único código que la lee la usa como nivel con default `'info'`.\n\n"
        "El dueño es la mitad que faltaba. `vault_norms.DOMAIN_STATUS_VOCABS` "
        "ya había resuelto esto para `status` en v39 y se quedó solo: "
        "compartir la constante evita la copia, pero no contesta quién decide "
        "cuándo cambia. Por eso cada entrada del registro declara el contexto "
        "acotado que manda sobre ella, y ese contexto tiene que existir en "
        "`vault_arch.CONTEXTS`."
    ),
    "signal": (
        "Un literal de lista o de tupla reproduce —en cualquier orden— un "
        "vocabulario que el registro ya declara; un `os.environ.get()` con "
        "un default escrito en el punto de lectura; un `choices=` de argparse "
        "con valores en duro; dos módulos que escriben el mismo campo con "
        "criterios de escapado distintos; un vocabulario declarado sin "
        "contexto dueño."
    ),
    "prevention": (
        "Registro canónico con dueño, consumidores derivados, guard sin "
        "baseline. Los vocabularios cerrados en `vault_vocabulario.py`, la "
        "configuración en `vault_entorno.py`, y `vault_arch --check` "
        "fallando si aparece una copia, una lectura sin declarar o un "
        "vocabulario huérfano. **Sin baseline a propósito**: las catorce "
        "copias se saldaron al declarar el registro, así que la puerta nace "
        "en cero y una baseline solo serviría para admitir la número quince. "
        "Lo que ya tiene registro canónico no se copia: se declara "
        "`derivado_de` y se resuelve al llamarse, nunca al importarse "
        "(AP-49). Un dato canónico que no es puerto de su contexto se acaba "
        "copiando — los tres registros que `AGENTS.md` declara fuente única "
        "de verdad se leían por fuera de la superficie publicada, y así "
        "nacieron las catorce copias."
    ),
    "tools_enforcing": ["vault_arch"],
    "tools_detecting": ["vault_arch"],
    "distinguido_de": {
        "AP-57": (
            "AP-50 mira **datos** duplicados —vocabularios, defaults, "
            "regex—: dos copias que divergen se ven al compararlas. AP-57 "
            "mira **criterios** enterrados en una condición, donde no hay "
            "dato que comparar y la divergencia solo aparece por el "
            "resultado equivocado."
        )
    },
    "introduced_version": "v40.1",
    "revisado_en": "2026-10-09",
}
