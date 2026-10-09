"""AP-54 — la entrada del catálogo, en su paquete (deuda #10, lote AP-41..AP-63).

Solo datos: `vault_norms_catalog` lee este fichero con `ast.literal_eval` y no
lo importa, así que aquí no cabe ni un import ni una expresión que haya que
ejecutar. Movida tal cual desde `NORM_CATALOG` el 2026-10-09; las caras están en
`porque.md`.
"""

NORMA = {
    "code": "AP-54",
    "name": "El lock falla y se escribe igual",
    "type": "antipattern",
    "category": "integrity",
    "severity": "high",
    "enforcement": "guard",
    "description": (
        "Un bloque toma un `file_lock`, no lo consigue, y en el handler "
        "escribe de todos modos sin sincronizar. El razonamiento que lleva "
        "ahi es que perder el dato es peor que escribirlo sin lock. Es al "
        "revés, y por una razón que se ve al leer el `TimeoutError`: ese "
        "error significa que **otro lo tiene tomado ahora mismo**. La "
        "escritura del handler no es una carrera improbable, es la unica "
        "situacion en la que ese codigo llega a ejecutarse, y entra justo "
        "encima de la de quien si consiguio el lock.\n\n"
        "Medido en v40.7 en `vault_sdd_init`, que se pasaba del timeout de "
        "60s de la tool y moria dejando `docs/sdd/` a medio escribir "
        "despues de haber anunciado `Drift status: PASS`. La medida: **26 "
        "tomas del lock del fichero de trazas, 13 fallidas, 65,14s de "
        "espera pura** —13 x 5s exactos—. Esas 13 acababan reescribiendo el "
        "trace sin lock mientras el llamante externo lo estaba "
        "reemplazando.\n\n"
        "La causa de las esperas era distinta de la norma y se corrigio "
        "aparte: `file_lock` no era reentrante, asi que un hilo que volvia "
        "a pedir un lock que el mismo sostenia esperaba el timeout entero "
        "contra si mismo. Conviene separar las dos cosas —la causa se "
        "arregla una vez en el kernel; la reaccion es la que se repite en "
        "cada llamante y la que esta norma vigila.\n\n"
        "Omitir la escritura al fallar el lock **no** es esta norma: es la "
        "respuesta correcta, y `vault_quality_check` ya la tenia."
    ),
    "signal": (
        "Un `except TimeoutError` (o un handler mas amplio) alrededor de un "
        "`with file_lock(...)` cuyo cuerpo contiene una llamada de "
        "escritura; una tool que se pasa de su timeout sin trabajo que lo "
        "justifique; un fichero de indice o de trazas con entradas perdidas."
    ),
    "prevention": (
        "Al fallar el lock, descartar la escritura o propagar el error — "
        "nunca escribir sin sincronizar. `vault_arch --check --strict` "
        "reporta el patron en `unsynced_writes`."
    ),
    "tools_enforcing": ["vault_arch"],
    "tools_detecting": ["vault_arch"],
    "distinguido_de": {
        "AP-58": (
            "AP-54 habla de escrituras sin sincronizar; AP-58, de la "
            "dirección de los imports. No se confunden por el tema sino "
            "por el remedio: los dos se arreglan moviendo una "
            "responsabilidad de sitio, y por eso conviene decir cuál toca. "
            "Un ciclo puede vivir entero dentro de un contexto acotado sin "
            "cruzar ninguna frontera — el componente de 14 módulos está "
            "casi todo dentro del kernel."
        )
    },
    "introduced_version": "v40.7",
}
