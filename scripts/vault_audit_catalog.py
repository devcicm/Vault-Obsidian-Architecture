#!/usr/bin/env python3
"""vault_audit_catalog — lo que el audit **declara**, separado de lo que decide.

Hoja del núcleo: no importa ningún `vault_*`, solo `typing`.

## Por qué existe (AP-62, v40.28)

`vault_audit` tiene fan-out 8 —el más alto de los productores del ranking— y dos
de sus consumidores no querían nada de eso. `vault_foreign_check`, que es la
tool de la regla 7, lo importaba entero para preguntar «¿esta ruta es
documentación del estándar o una nota?»; `vault_norms_coherence`, para leer la
tabla de penalizaciones. Dos lecturas de un registro pagando el barrido completo
del vault.

El caso del criterio es además el que peor sentaba estar escondido ahí dentro.
Es una **decisión con dueño** —la que en v40.5 comparaba el nombre exacto del
manifiesto y aportaba decenas de enlaces rotos falsos en cuanto un consumidor
archivaba una copia con sufijo de versión— y las decisiones con dueño se leen
mejor donde se pueden leer sin arrastrar el motor que las aplica.

`vault_audit` los sigue reexportando: ningún llamador se rompe (no-derogación).

## Qué NO va aquí

El cálculo. `_tope_por_familia`, el `healthProfile` y el `healthIndex` derivan de
estas tablas y se quedan en `vault_audit`, que es quien recorre el vault. Aquí
solo está lo declarado.
"""

from typing import Any, Dict, List, Optional

# Documentación del estándar embarcada dentro de un vault. Sus wikilinks son
# **sintaxis de ejemplo** —`[[wiki-link]]`, `[[]]`, `[[nota]]`— no enlaces a
# notas que existan, así que contarlos como rotos es medir el manual y llamarlo
# vault.
#
# Esto ya se excluía, pero por **nombre exacto** (`vault-obsidian-architecture.md`),
# y esa igualdad se rompe sola: medido contra `vault-ans`, un vault ajeno al
# estándar, la copia `vault-obsidian-architecture.v27.backup.md` aportaba **45
# enlaces rotos falsos** y `docs/sdd/04-antipatterns.md` otros **30**. Setenta y
# cinco de 624 en un solo vault, y `broken_links` satura a los diez: el vault
# entero quedaba juzgado por su propia documentación. Los consumidores archivan
# el manifiesto con sufijo de versión, que es lo correcto por no-derogación —
# quien tenía que ceder era el criterio de medida (AP-44), no ellos.
#
# Se declara como registro y no como tres condiciones sueltas dentro del bucle:
# es una decisión con dueño, y el guard que la vigila necesita poder leerla.
# La entrada por nombre aplanado sale de un vault de fuera medido en v40.6
# (`vault-electron-fingerprint`, 139 notas, sellado en v34): el consumidor no
# guardó la referencia de tools en `scripts/`, la **aplanó** a
# `00_System/scripts-README.md`. El criterio la reconocía por ruta, así que sus
# ocho ejemplos de sintaxis —`[[nota]]`, `[[carpeta/nota]]`— contaban como
# enlaces rotos del vault; con el tope de `broken_links` saturando a diez, casi
# toda la penalización era falsa. Es el mismo defecto de v40.5 en otra forma:
# identidad por **ubicación** en vez de por identidad.
DOCUMENTACION_DEL_ESTANDAR: Dict[str, str] = {
    "vault-obsidian-architecture": "el manifiesto, con cualquier sufijo de versión o backup",
    "docs/sdd/": "los documentos SDD del estándar, que citan sintaxis de wikilink",
    "scripts/": "la referencia de tools, con ejemplos de CLI y de enlace",
    "scripts-readme": "la referencia de tools aplanada fuera de `scripts/`; "
                      "el nombre no basta como identidad y se exige la marca "
                      "del estándar en el contenido",
}

#: Lo que un documento del estándar dice de sí mismo. Se usa solo para la
#: entrada por nombre aplanado: `readme` es un nombre demasiado genérico para
#: valer como identidad, y excluir de más esconde enlaces rotos de verdad.
MARCA_DEL_ESTANDAR = "vault obsidian architecture"


def es_documentacion_del_estandar(rel: str, contenido: Optional[str] = None) -> bool:
    """¿Esta ruta es documentación del estándar y no una nota del vault?

    `rel` es la ruta relativa a la raíz del vault, con `/` como separador.

    `contenido` es opcional y solo decide el caso aplanado. Sin él, la respuesta
    es la conservadora —**no** excluir—: el nombre del manifiesto es largo y
    único y se sostiene solo, pero un fichero llamado `scripts-README.md` puede
    ser perfectamente una nota que alguien escribió, y excluirla a ciegas
    escondería sus enlaces rotos de verdad.
    """
    ruta = rel.replace("\\", "/").lower()
    nombre = ruta.rsplit("/", 1)[-1]
    if nombre.startswith("vault-obsidian-architecture"):
        return True
    if any(ruta.startswith(pref) or f"/{pref}" in ruta
           for pref in ("docs/sdd/", "scripts/")):
        return True
    if nombre.startswith("scripts-readme") and contenido:
        return MARCA_DEL_ESTANDAR in contenido.lower()
    return False


#: Las familias de salud, con dueño y en un solo sitio.
#:
#: `healthScore` parte de 100 y resta 22 penalizaciones independientes cuyos
#: topes suman 285. Eso significa que **satura**: basta con estar mal en dos o
#: tres familias distintas para llegar a 0, y a partir de ahí un vault regular y
#: uno catastrófico puntúan igual. No es una hipótesis — `vault-sandbox/`, el
#: vault de referencia de este repo y recién reconstruido, puntúa 0.
#:
#: `healthScore` **no se toca**: lo leen los repos consumidores y cambiar lo que
#: significa un número publicado por debajo es peor que el defecto. Se le añade
#: al lado `healthProfile` —una lectura por familia, cada una normalizada contra
#: su propio tope— y `healthIndex`, la media de las familias, que solo llega a 0
#: si **todas** están al tope. Es la política de no-derogación aplicada a una
#: métrica: lo reemplazado se anota, no se borra.
FAMILIAS_DE_SALUD: Dict[str, str] = {
    "estructura": "carpetas, secciones e identidad de la nota",
    "conectividad": "enlaces entre notas: rotos, huérfanos, mal formados",
    "metadatos": "frontmatter — los campos por los que el vault se consulta",
    "grafo": "aristas tipadas y su vigencia",
    "contenido": "lo que la nota lleva dentro y no se puede renderizar",
    "ciclo_de_vida": "lo que caducó: notas, patrones y proyectos parados",
}

#: El registro que manda sobre el cálculo. Antes eran 22 `score -= min(...)`
#: escritos a mano en el cuerpo de `vault_audit()`: los topes vivían solo ahí,
#: nadie podía sumarlos sin leerse la función, y agrupar por familia exigía
#: copiarlos a un segundo sitio (AP-05). Ahora el cuerpo itera este registro.
#:
#: `por_unidad` es lo que resta cada ocurrencia; `tope`, el máximo que la
#: entrada puede restar por sí sola. Las entradas con `por_unidad: 1` reciben
#: una penalización ya calculada por su detector.
PENALIZACIONES: List[Dict[str, Any]] = [
    {"id": "orphans", "familia": "conectividad", "norma": None, "por_unidad": 2, "tope": 30,
     "metrica_sin_norma": (
         "Una nota sin enlaces entrantes no incumple nada: puede ser una entrada "
         "recién escrita, o una raíz legítima. Lo que mide es alcanzabilidad del "
         "grafo, y por eso pesa en el healthIndex sin que exista un anti-patrón "
         "que declarar incumplido.")},
    {"id": "stale", "familia": "ciclo_de_vida", "norma": None, "por_unidad": 1, "tope": 10,
     "metrica_sin_norma": (
         "Que una nota lleve tiempo sin tocarse no es un defecto: una decisión "
         "cerrada envejece bien. Es una señal de actualidad, ponderada por CIA, "
         "no una norma que se pueda cumplir o incumplir.")},
    {"id": "stuck_patterns", "familia": "ciclo_de_vida", "norma": None, "por_unidad": 3, "tope": 15,
     "metrica_sin_norma": (
         "Un patrón detenido en el mismo estado mide el proceso del equipo, no "
         "la forma del vault. Convertirlo en norma exigiría fijar un plazo "
         "canónico de avance, que este estándar no tiene por qué imponer.")},
    {"id": "stale_projects", "familia": "ciclo_de_vida", "norma": None, "por_unidad": 5, "tope": 25,
     "metrica_sin_norma": (
         "Mismo caso que `stuck_patterns` y por el mismo motivo: un proyecto "
         "parado es un hecho del proyecto, no un incumplimiento del vault.")},
    {"id": "broken_links", "familia": "conectividad", "norma": "AP-14", "por_unidad": 2, "tope": 20},
    {"id": "canonical_shadow", "familia": "estructura", "norma": "AP-17", "por_unidad": 2, "tope": 10},
    {"id": "cross_folder_dupes", "familia": "estructura", "norma": "AP-18", "por_unidad": 3, "tope": 10},
    # AP-22 (wikilink vacío) es auto-fixable; AP-24 (brackets rotos) rompe el
    # enlace de verdad. Por eso pesan distinto: la diferencia es deliberada.
    {"id": "ap22", "familia": "conectividad", "norma": "AP-22", "por_unidad": 2, "tope": 5},
    {"id": "ap24", "familia": "conectividad", "norma": "AP-24", "por_unidad": 5, "tope": 15},
    {"id": "empty_indexes", "familia": "estructura", "norma": "AP-03", "por_unidad": 2, "tope": 10},
    {"id": "mermaid_errors", "familia": "contenido", "norma": "AP-25", "por_unidad": 2, "tope": 20},
    {"id": "missing_agent", "familia": "metadatos", "norma": "AP-16", "por_unidad": 1, "tope": 10},
    {"id": "missing_tags", "familia": "metadatos", "norma": "AP-26", "por_unidad": 2, "tope": 15},
    {"id": "missing_type", "familia": "metadatos", "norma": "AP-27", "por_unidad": 2, "tope": 10},
    {"id": "missing_status", "familia": "metadatos", "norma": "AP-29", "por_unidad": 1, "tope": 10},
    {"id": "missing_cia", "familia": "metadatos", "norma": "AP-30", "por_unidad": 2, "tope": 15},
    # La asimetría se declara en vez de disimularse: sus cinco hermanas de
    # familia —agent, tags, type, status, cia— tienen norma propia y esta no.
    # No se le inventa una para tapar el hueco; queda escrito que el catálogo
    # cubre cinco de los seis campos por los que el vault se consulta.
    {"id": "missing_updated", "familia": "metadatos", "norma": None, "por_unidad": 2, "tope": 10,
     "metrica_sin_norma": (
         "`updatedAt` ausente no tiene anti-patrón propio, a diferencia de sus "
         "cinco hermanas de familia. `vault_validate` sí lo exige como campo "
         "requerido, pero eso lo aplica AP-12 por clase de nota, no por campo: "
         "atribuirle AP-12 a esta penalización afirmaría una cobertura que la "
         "norma no da. Hueco declarado, no resuelto.")},
    {"id": "missing_frontmatter", "familia": "metadatos", "norma": "AP-28", "por_unidad": 3, "tope": 20},
    {"id": "cia_penalty", "familia": "metadatos", "norma": None, "por_unidad": 1, "tope": 15,
     "metrica_sin_norma": (
         "No cuenta ocurrencias de un defecto: recibe una penalización ya "
         "calculada que pondera las demás por la criticidad declarada de la "
         "nota. Es el factor de riesgo del healthIndex —una nota `critical` "
         "desactualizada cuesta más que una `low`—, y un factor no se incumple.")},
    {"id": "ap31", "familia": "grafo", "norma": "AP-31", "por_unidad": 1, "tope": 20},
    {"id": "ap34", "familia": "grafo", "norma": "AP-34", "por_unidad": 2, "tope": 10},
    {"id": "ap35", "familia": "grafo", "norma": "AP-35", "por_unidad": 5, "tope": 5},
]
