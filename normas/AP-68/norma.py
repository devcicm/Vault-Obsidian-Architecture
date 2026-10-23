"""AP-68 — la entrada del catálogo, en su paquete.

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Las caras están en `porque.md`.
"""

NORMA = {
    "code": "AP-68",
    "name": "El git que ejecuta el toolkit, sin dueño",
    "type": "antipattern",
    "category": "security",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Un proceso del toolkit lanza `git` sin que nadie decida qué puede "
        "lanzar. El síntoma no es el `git` en sí —leer el historial es "
        "legítimo y lo hacen las tools que contrastan contra él— sino que "
        "**la frontera depende del criterio de quien escribió la línea**: "
        "cualquiera puede escribir `subprocess.run([\"git\", ...])` con un "
        "verbo mutador, y lo que evita el daño es el ojo de quien revisa, no "
        "una norma.\n\n"
        "La auditoría del 2026-10-23 sobre «¿ejecuta alguna tool git sin "
        "supervisión?» dio un veredicto tranquilizador y, aun así,.sin "
        "sustento: de **24 sitios** que levantaban git, doce eran lecturas "
        "reales y uno —el bootstrap de `vault_init`— el único mutador, "
        "acotado a un vault recién creado, sin `push` ni identidad "
        "configurada. Todo era verdad, y todo estaba **solo en la "
        "inspección** de quien miró. Al día siguiente un `git clean -fdx` en "
        "una tool habría entrado sin que ninguna puerta se pusiera roja.\n\n"
        "Lo que lo hace caro no es el verbo: es que la propiedad «este repo "
        "no borra historia ajena» era un **saber de cabeza**, la forma más "
        "fácil de perder. Es AP-57 aplicado al repo contra sí mismo — el "
        "criterio escrito trece veces y vigilado por nadie— y por eso se "
        "enforza con un dueño, no con un recordatorio."
    ),
    "signal": (
        "Un `subprocess.run([\"git\", ...])`, un `vault_subproceso.ejecutar("
        "[\"git\", ...])` o un equivalente en cualquier módulo que no sea "
        "`vault/kernel/procesos_git.py`; un verbo mutador (`reset`, "
        "`checkout`, `clean`, `push`, `pull`, `gc`) sin motivo escrito; un "
        "hash leído de un fichero —changelog, snapshot, METRICAS— que entra "
        "al argv sin validar; un `shell=True` con git en la cadena."
    ),
    "prevention": (
        "`vault_procesos_git --check --strict` recorre por AST `scripts/`, "
        "`cli/`, `vault/` y `mcp/` y publica toda llamada que levante git "
        "con el léxico `\"git\"` primero —literal, concatenado o por "
        "variable—, que tiene que ser cero. El runtime lo aplica "
        "`vault.kernel.procesos_git.ejecutar_git`, el dueño: rechaza verbo "
        "desconocido, verbo mutador sin motivo en `MUTADORES_AUTORIZADOS`, "
        "el uso mutador de un verbo ambiguo (`branch -D`, `tag <nombre>`, "
        "`config k v`, `stash apply`, `reflog expire`) y todo argv que no "
        "sea lista. Y `asegurar_hash` cierra la inyección de opción: un "
        "valor que empieza por `--`, nacido en un fichero, muere antes de "
        "llegar al argv.\n\n"
        "Se salda **moviendo la llamada al dueño**, nunca ampliando una "
        "lista. Si de verdad hace falta un mutador nuevo, se autoriza en "
        "`MUTADORES_AUTORIZADOS` con su motivo escrito, y el diff que lo "
        "añade es exactamente la revisión que el criterio no daba.\n\n"
        "Límites declarados: la puerta no ve un argv armado con `\" \".join"
        "(...)` o con un f-string, ni un binario que lance git por su "
        "cuenta; los `tests/` quedan fuera del alcance **y por qué** — un "
        "test necesita git crudo para fabricar el repositorio con el que "
        "mide, y medir una tool con su propio ejecutor sería certificarse a "
        "sí mismo (AP-44). El runtime, en cambio, no depende del análisis "
        "estático: aunque un sitio se escondiera del AST, su llamada "
        "seguiría teniendo que pasar por el dueño para ejecutarse."
    ),
    "tools_enforcing": ["vault_procesos_git"],
    "tools_detecting": ["vault_procesos_git"],
    "distinguido_de": {
        "AP-44": (
            "AP-44 es el criterio con el que se mide; AP-68 es quién puede "
            "lanzar el proceso que mide. Aquí no se compara lo que una tool "
            "afirma con lo que hay —eso es AP-44— sino que el acto de "
            "pedirle algo a git no quede en manos de la línea que lo pide."
        ),
        "AP-36": (
            "AP-36 encierra **dónde** se escribe lo que el toolkit produce "
            "(siempre dentro del vault). AP-68 encierra **qué puede "
            "ejecutarse** contra el repositorio. Una tool puede respetar "
            "las dos y aun así pedir un `git reset --hard`: por eso hacen "
            "falta las dos."
        ),
        "AP-53": (
            "AP-53 obliga a contrastar el historial afirmado con git — "
            "`vault_changelog_check` es su guard. AP-68 vigila cómo se pide "
            "ese git: el changelog lee, valida el hash y no muta nada. Los "
            "dos se tocan en la misma función y por eso van declarados aquí "
            "como distintas."
        ),
    },
    "introduced_version": "v41.19",
    "revisado_en": "2026-10-22",
}