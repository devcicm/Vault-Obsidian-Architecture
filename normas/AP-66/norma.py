"""AP-66 — la entrada del catálogo, en su paquete.

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. El porqué de cada cara está en `porque.md`.
"""

NORMA = {
    "code": "AP-66",
    "name": "El coste crece con lo que no es trabajo",
    "type": "antipattern",
    "category": "process",
    "severity": "medium",
    "enforcement": "guard",
    "description": (
        "Una tool cuyo tiempo crece con algo distinto de lo que mide: la "
        "historia del repo, la profundidad del árbol, el número de veces que "
        "se la llama. La auditoría del 2026-10-15 midió las puertas en 132 s "
        "y encontró cinco sitios así: `vault_baseline.pendiente` lanzaba un "
        "`git show` por cada commit que había listado `git log`, "
        "`vault_grafo_import` recorría el árbol entero dentro de su propio "
        "recorrido, `vault_arch` resolvía cada módulo repitiendo el mismo "
        "barrido, `vault_kernel` reparseaba la historia entera en cada "
        "ejecución y `vault_blueprint` volvía a leer cada cuerpo de test. "
        "Ninguno fallaba: daban el resultado correcto cada vez más tarde, y "
        "una puerta lenta es una puerta que se deja de ejecutar."
    ),
    "signal": (
        "Un bucle cuyo iterable sale de un proceso y cuyo cuerpo lanza otro "
        "(`proceso_por_linea_de_proceso`), o `ast.walk(X)` dentro de un "
        "bucle sobre `ast.walk(X)` con el mismo `X` "
        "(`recorrido_dentro_de_su_recorrido`). Las dos se reconocen sin "
        "ejecutar; `vault_arch --check` las publica en `growing_costs`."
    ),
    "prevention": (
        "Un proceso por lote y no por elemento (`git cat-file --batch` en vez "
        "de un `git show` por commit); una pasada por árbol con su resultado "
        "memorizado; y, para la repetición que solo existe en ejecución, un "
        "test que cuente el trabajo —procesos lanzados, árboles recorridos— "
        "y no el tiempo, que depende de la máquina.\n\n"
        "Límites declarados: el detector no ve la repetición dinámica "
        "—reparsear lo mismo en cada llamada, una caché que no acierta— ni "
        "un bucle sobre los ficheros del repo que lanza un proceso por "
        "fichero, que es lineal en lo medido y a veces legítimo. Esos casos "
        "los vigilan los tests de trabajo de cada arreglo, no la puerta."
    ),
    "tools_enforcing": ["vault_arch"],
    "tools_detecting": ["vault_arch"],
    "distinguido_de": {
        "AP-37": (
            "AP-37 pregunta si una tool dice cuánto trabajo hizo; AP-66, si "
            "su coste crece con ese trabajo o con otra cosa."
        ),
    },
    "revisado_en": "2026-10-15",
}
