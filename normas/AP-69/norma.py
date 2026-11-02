"""AP-69 — la entrada del catálogo, en su paquete.

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Las caras están en `porque.md`.
"""

NORMA = {
    "code": "AP-69",
    "name": "El test que construye a mano lo que ya tiene apoyo",
    "type": "antipattern",
    "category": "quality",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Un módulo de test reescribe por su cuenta lo que la suite ya "
        "resuelve en un sitio: el `sys.path` que el conftest prepara, el "
        "lanzador de una tool por subproceso, el texto de una nota pegado "
        "con `+ \"\\n\"`, un `+=` sobre una cadena, la captura de stdout a "
        "mano o un `time.sleep` para esperar a que algo pase. Ninguna copia "
        "es un fallo por separado; el agregado sí lo es.\n\n"
        "Medido el 2026-10-31 sobre los 555 módulos de `tests/`: 476 "
        "`sys.path.insert`, 239 lanzadores privados —`_run`, `_tool`, "
        "`_cli`, `_ejecutar`…—, 133 textos multilínea concatenados, 13 "
        "`time.sleep` y 3 buffers a mano. Cada lanzador decide el entorno, "
        "la codificación y el timeout del hijo; el día que uno de los tres "
        "cambia hay 239 sitios que tocar y ningún guard que lo diga.\n\n"
        "Es AP-57 dentro de la suite: el criterio de cómo se lanza una tool "
        "o cómo se escribe una nota de prueba está reescrito por fichero. Y "
        "es caro en el sitio donde más duele, el desarrollo: una suite cuyos "
        "tests no comparten apoyo no se puede acelerar en un sitio, solo en "
        "seiscientos."
    ),
    "signal": (
        "En un `tests/test_*.py`: `sys.path.insert`/`append`; una función "
        "que llama a `subprocess.run`/`check_output`/`Popen` con "
        "`sys.executable`; un `+` entre cadenas donde una lleva `\\n`; un "
        "`+=` de cadena; asignar `sys.stdout`/`sys.stderr` o "
        "`redirect_stdout`; `time.sleep`."
    ),
    "prevention": (
        "`vault_tests_higiene --check --strict` recorre por AST los "
        "`tests/test_*.py` y publica cada sitio de esas seis clases con su "
        "firma de sitio; la baseline solo encoge y congelar deuda nueva "
        "exige `--freeze --admitir-nuevos`, que la lista. Cada clase "
        "publica su sustituto: `tests/apoyo.py` (`correr_tool`, `entorno`, "
        "`nota`, `escribir_nota`, `ROOT`, `SCRIPTS`), el conftest para el "
        "path, `capsys` para la salida y esperar a la condición en vez de "
        "dormir.\n\n"
        "Límites declarados: no ve un lanzador que no pase `sys.executable` "
        "(el binario `vault`, `node`), ni un texto armado con `join` a "
        "trozos; `normas/*/test_*.py` queda fuera porque corre sin el "
        "conftest de `tests/` y sí necesita su propio path. Y verde no dice "
        "que la suite sea rápida: eso lo mide `perfil_suite`, por módulo."
    ),
    "tools_enforcing": ["vault_tests_higiene"],
    "tools_detecting": ["vault_tests_higiene"],
    "distinguido_de": {
        "AP-57": (
            "AP-57 mide el criterio de clasificar notas reescrito en módulos "
            "del toolkit (`vault_criterios`). AP-69 mide el andamiaje de la "
            "suite reescrito en módulos de test: los dos son el mismo "
            "defecto de forma, pero en código que se instala y en código que "
            "no, y por eso tienen guard y baseline distintos."
        ),
        "CN-05": (
            "CN-05 (`vault_clones`) busca cuerpos idénticos entre módulos. "
            "Los lanzadores de los tests casi nunca son idénticos —cambian "
            "el nombre, un `cwd`, un timeout— y por eso CN-05 no los ve: "
            "AP-69 los reconoce por lo que hacen, no por cómo están escritos."
        ),
        "AP-44": (
            "AP-44 exige medir con el criterio del consumidor. AP-69 no "
            "cambia qué mide un test, sino cómo se fabrica lo que mide: un "
            "test que pasa de su lanzador a `correr_tool` sigue lanzando el "
            "mismo proceso con el mismo criterio."
        ),
    },
    "introduced_version": "v41.26",
    "revisado_en": "2026-10-31",
}
