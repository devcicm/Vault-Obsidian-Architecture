#!/usr/bin/env python3
"""Plano técnico del estándar: contextos acotados y sus fronteras.

Los 37 grupos del catálogo son una taxonomía de documentación —sirven para
encontrar una tool en `scripts/README.md`—, no fronteras de dominio. Nada dice
hoy quién puede importar a quién, y por eso los defectos de v39.5 y v39.6 son
todos el mismo: una capacidad implementada dos veces (AP-48), un side effect
fuera del vault, cinco módulos ejecutables en ningún registro. Se detectan de
uno en uno y después del hecho.

Siguiendo la regla 3 de `AGENTS.md` —registro canónico primero, doc después—
este plano **no es un documento**: es un registro con guard. `docs/ARQUITECTURA.md`
se deriva de aquí con `--blueprint`, y `--check` reconstruye el grafo de
importaciones por AST, no por una lista escrita a mano que envejecería sola.

La deuda actual arranca congelada en `arch-baseline.json` y **solo puede
encoger**, igual que `vault_noop_audit` y `vault_smoke`. Un guard que exigiera
cero fronteras cruzadas el primer día fallaría el primer día y se desactivaría.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vault_baseline
import vault_grafo_import

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
BASELINE_PATH = SCRIPTS_DIR / "arch-baseline.json"

#: Alcance declarado de los guards que leen código fuente de este repo.
#:
#: Hasta v40.9 cada guard escribía su propio `SCRIPTS_DIR.glob("vault_*.py")`
#: —siete veces en este módulo y una en cada audit— y publicaba un cero que solo
#: valía dentro de ese glob. `cli/`, que es donde el consumidor lee el error, no
#: lo medía nadie: doce envelopes sin `error_code` llevaban ahí desde siempre con
#: la puerta de AP-52 en verde. Un recorte de alcance no declarado no se ve como
#: un fallo; se ve como un cero, que es lo que lo hace caro.
#:
#: `mcp/python` entra hoy sin ningún módulo. Se declara igual: el día que alguien
#: ponga uno, entra medido en vez de entrar invisible.
ARBOLES_MEDIDOS: tuple[tuple[str, str], ...] = (
    ("scripts", "vault_*.py"),
    ("vault", "**/*.py"),
    ("cli", "*.py"),
    ("mcp/python", "**/*.py"),
)


@lru_cache(maxsize=None)
def _ast_de(ruta: Path) -> ast.Module:
    """Árbol AST de un módulo, cacheado por ruta+mtime+tamaño (v40.34).

    Antes cada analyzer re-parseaba los ~250 ficheros del alcance por su cuenta:
    `arch.check()` hacía doce barridos completos y tardaba ~10 s por invocación.
    La clave incluye `mtime_ns` y `size` para que un test que muta un fichero
    entre llamadas siga viendo el cambio (los tests de `test_arquitectura.py`
    editan módulos temporales y re-ejecutan los analyzers).

    Limitación (v40.34): en Windows, `st_mtime` tiene resolución de ~1 segundo.
    Si un archivo cambia y se revierte en menos de 1 segundo con tamaño idéntico,
    la caché puede devolver el AST antiguo. El hash de contenido como fallback
    se evaluará para v40.35 si el caso de uso se confirma.

    Re-lanza `SyntaxError`: los llamadores ya lo capturan y deciden qué hacer
    con el módulo que no parsea.
    """
    stat = ruta.stat()
    clave = (str(ruta), stat.st_mtime_ns, stat.st_size)
    return _ast_de_impl(clave, ruta)


@lru_cache(maxsize=None)
def _ast_de_impl(clave: tuple, ruta: Path) -> ast.Module:
    return ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))


#: Memo de UNA medición: solo vive mientras corre `check()`. Fuera de ella
#: cada analyzer mide de nuevo, porque los tests mutan registros y ficheros
#: entre llamadas y tienen que ver el cambio.
_MEMO_DE_MEDICION: "dict[str, object] | None" = None


def _una_vez_por_medicion(funcion):
    """Dentro de un `check()`, un analyzer sin argumentos se calcula una vez.

    `check()` pedía `cruces()` tres veces (directamente y a través de los dos
    presupuestos) y `_propiedades_de_sistema()` otras tres: el mismo árbol,
    medido tres veces en la misma llamada. Se devuelve una copia profunda para
    que ningún llamador pueda alterar lo que verá el siguiente.
    """
    import copy
    import functools

    @functools.wraps(funcion)
    def envoltura():
        memo = _MEMO_DE_MEDICION
        if memo is None:
            return funcion()
        if funcion.__name__ not in memo:
            memo[funcion.__name__] = funcion()
        return copy.deepcopy(memo[funcion.__name__])
    return envoltura


#: Recorridos ya hechos, por identidad del árbol. Guarda también el árbol para
#: que su `id` no pueda reutilizarse mientras la entrada viva.
_NODOS: dict[int, tuple[ast.AST, tuple[ast.AST, ...]]] = {}


def _nodos(arbol: ast.AST) -> tuple[ast.AST, ...]:
    """`_nodos(arbol)` materializado una sola vez por árbol (2026-10-28).

    `_ast_de` ya evitaba re-parsear, pero cada analyzer volvía a recorrer el
    árbol entero de los ~300 módulos: un `check()` hacía nueve millones de
    pasos de `ast.walk` y tardaba 14–18 s, y la suite lo invoca decenas de
    veces. Los árboles salen de la caché de `_ast_de` y nadie los muta, así
    que su recorrido tampoco cambia; un árbol nuevo (un fichero editado por un
    test) tiene otra identidad y se recorre de nuevo.
    """
    hit = _NODOS.get(id(arbol))
    if hit is not None and hit[0] is arbol:
        return hit[1]
    if len(_NODOS) > 4096:
        _NODOS.clear()
    nodos = tuple(ast.walk(arbol))
    _NODOS[id(arbol)] = (arbol, nodos)
    return nodos


def arboles_medidos() -> list[Path]:
    """Los módulos Python dentro del alcance declarado, sin duplicados."""
    vistos: dict[Path, None] = {}
    for rel, patron in ARBOLES_MEDIDOS:
        raiz = REPO_ROOT / rel
        if not raiz.is_dir():
            continue
        for ruta in raiz.glob(patron):
            if ruta.is_file():
                vistos[ruta.resolve()] = None
    return sorted(vistos)


def clave_de_modulo(ruta: Path) -> str:
    """Identidad de un módulo en las baselines.

    Bajo `scripts/` sigue siendo el nombre de fichero, que es lo que las tres
    baselines por firma de sitio ya llevan dentro: cambiarlo las reescribiría
    enteras y estrenaría como deuda nueva todo lo ya saldado. Fuera de
    `scripts/` se usa la ruta relativa, que además desambigua los homónimos
    —`vault/*/repositorio.py` son ocho ficheros distintos con el mismo nombre—.
    """
    ruta = ruta.resolve()
    try:
        rel = ruta.relative_to(REPO_ROOT)
    except ValueError:
        return ruta.name
    if rel.parent == Path("scripts"):
        return ruta.name
    # Deuda #12: el dueño de un alias de `scripts/` conserva la clave del alias.
    # Con la ruta, migrar un módulo con entradas las re-clavaba y salían como
    # deuda nueva más deuda resuelta; el nombre público es la identidad que la
    # no-derogación conserva.
    alias = alias_de_dueno(ruta)
    return f"{alias}.py" if alias else rel.as_posix()


def alias_de_dueno(ruta: Path) -> str | None:
    """El nombre de `scripts/` cuyo alias lleva a `ruta`, o None si no es dueño
    de ninguno. Lo decide `vault_grafo_import`, que deriva el puente del disco."""
    ruta = Path(ruta).resolve()
    alias = vault_grafo_import.nombre_de(ruta)
    return alias if vault_grafo_import.fuente_de(alias) == ruta else None


#: El paquete de dominio. El guard nació mirando solo `scripts/`, con lo que el
#: único código que existe para imponer fronteras era el único que podía
#: cruzarlas sin que saltara nada. Se vigila con la misma vara.
DOMINIO_DIR = REPO_ROOT / "vault"

#: El shared kernel. No es un contexto de dominio: es el vocabulario que todos
#: hablan (ruta, envelope, error, bloqueo, escritura atómica). Es el único al
#: que cualquiera puede depender, y por eso mismo no puede depender de nadie.
KERNEL = "kernel"

#: Los contextos acotados. Un módulo pertenece a exactamente uno.
#:
#: `lenguaje` es el lenguaje ubicuo: los términos que dentro de este contexto
#: significan una sola cosa. `puertos` son los nombres que otros contextos
#: pueden consumir; `prohibe` es la frontera que este contexto no cruza jamás.
#:
#: **`puertos` era una lista de nombres y ahora es un mapa `nombre → módulo:símbolo`.**
#: Como lista no la comprobaba nadie: de los 30 puertos declarados, 22 no
#: existían en ningún módulo. Eran los nombres del lenguaje ubicuo —`escribir_nota`,
#: `crear_backup`, `subgrafo`— escritos como si fueran API, mientras la API real
#: se llamaba `vault_write`, `vault_backup`, `vault_subgraph`. La frontera estaba
#: dibujada y no vigilada: un contexto podía «publicar» un puerto inexistente y
#: el blueprint lo imprimía igual. El nombre ubicuo se conserva —es la mitad del
#: valor del registro— pero ahora apunta al símbolo que lo implementa, y
#: `--check` falla si ese símbolo desaparece.
CONTEXTS: dict[str, dict] = {
    KERNEL: {
        "titulo": "Kernel",
        "lenguaje": ["ruta", "envelope", "error", "bloqueo", "escritura atómica"],
        # Los puertos se declaran donde el símbolo VIVE, no donde se reexporta
        # (v40.17). `vault_io` sigue exponiendo los cuatro nombres y ninguna tool
        # ha cambiado, pero un puerto que apunta al alias esconde justo el dato
        # que este registro existe para publicar: quién es el dueño.
        "puertos": {
            "get_vault_root": "vault_raiz:get_vault_root",
            "atomic_write_text": "vault_io:atomic_write_text",
            "wrap_main": "vault_errors:wrap_main",
            "file_lock": "vault_fs:file_lock",
        },
        "prohibe": ["depender de cualquier contexto de dominio"],
        "modulos": [
            "vault_io", "vault_errors", "vault_lib", "vault_regex",
            "vault_encoding", "vault_registry",
            "vault_errors_catalog", "vault_errors_trace",
            "vault_entorno", "vault_vocabulario",
            # v40.30 — cómo se lee la salida de un proceso hijo. Hoja: no
            # importa ningún `vault_*`. Es kernel por la misma razón que
            # `vault_encoding`: un criterio de codificación que estaba escrito
            # 23 veces en 13 módulos de cuatro contextos distintos.
            "vault_subproceso",
            # Las tres hojas del kernel (v40.17). No son un contexto nuevo: son
            # el mecanismo que `vault_io` mezclaba con su política — dónde está
            # el vault, cómo se escribe sin que nadie vea el fichero a medias, y
            # cuánto trabajo llevamos hecho. Separarlas sacó a `vault_errors_trace`
            # del componente fuertemente conexo de 15 módulos que era el núcleo.
            "vault_raiz", "vault_fs", "vault_ledger",
            # El fichero de baseline (v40.24): carga, escritura, contrato de
            # `objetivo` y la negativa a crecer. Aquí y no junto a
            # `vault_firma_sitio` en el meta-toolkit, aunque sean vecinas de
            # oficio, y la diferencia está en quién las consume: la firma solo
            # la piden audits del meta-toolkit, mientras que la baseline la
            # piden también tools que miden vaults —`vault_fuente_unica` es la
            # primera—, así que dejarla arriba estrenaba un cruce de contexto
            # por cada consumidor nuevo. Fan-out cero y ningún `vault_*`
            # importado: cumple la prohibición del núcleo sin excepción.
            "vault_baseline",
            # El escaneo del grafo de wikilinks, separado de `vault_lib`
            # porque era la parte que se movía (AP-59, K3): lo consumen
            # `vault_io` (núcleo) y los dos productores del grafo. Fan-out dos,
            # ambos del núcleo: `vault_lib` y `vault_regex`.
            "vault_escaneo_grafo",
            # El dueño único del grafo de imports (v40.20). Está aquí y no en el
            # meta-toolkit por una razón de dirección: lo consume `vault_arch`,
            # que está por encima, y un dueño de criterio que importa a sus
            # consumidores no es un dueño, es un nudo. Fan-out cero, solo stdlib.
            "vault_grafo_import",
            # El catálogo de normas y el vocabulario de `status` (v40.27). No es
            # una reclasificación de conveniencia para bajar una cifra: es que
            # hasta v40.26 este dato no se podía clasificar, porque compartía
            # fichero con el motor que lo audita. Partido, quedó con **fan-out
            # cero** —no importa ningún `vault_*`, solo `re` y `typing`—, que es
            # exactamente la forma de `vault_registry`, ya aquí. Y la
            # consecuencia de tenerlo en Gobernanza era medible: veintidós de
            # los sesenta y dos cruces del repo eran tools leyendo una tabla
            # constante, contadas como si cruzaran una frontera de negocio.
            # Leer una constante no es cruzar nada; el motor que decide con ella
            # sí, y ese se queda arriba.
            "vault_norms_catalog",
            # v40.28 — el primer recurso que sale del ranking de AP-62. Siete
            # caracteres que tres módulos iban a buscar dentro de la tool que
            # migra vaults. Fan-out cero por construcción, y su docstring dice
            # que el día que necesite importar algo deja de tener sitio aquí.
            "vault_version",
            # v40.28 — el segundo, y el que más pesaba: `FUNDAMENTALS` y
            # `cia_valores` los leían tres contextos distintos entrando por el
            # verificador que los usa. Declarar y decidir con lo declarado no
            # son el mismo módulo, aunque hayan nacido en el mismo fichero.
            "vault_fundamentals_catalog",
            # 2026-10-05 — el contrato de campos de una nota. Lee tres registros
            # del núcleo y nada más; lo consumen quien valida y quien completa.
            # Vivía como literal dentro de `vault_validate`.
            "vault_contrato_nota",
            # v40.28 — el tercero. `vault_audit` tiene el fan-out más alto del
            # ranking (8), y dos de sus consumidores solo querían un criterio y
            # una tabla. Que el criterio de «esto es documentación, no una
            # nota» viva donde se puede leer sin arrastrar el barrido del vault
            # importa por sí mismo: es la decisión que en v40.5 comparaba el
            # nombre exacto del manifiesto y falseaba decenas de enlaces rotos.
            "vault_audit_catalog",
            # v40.28 — el cuarto y último que se pudo cortar. La gramática de
            # Mermaid es texto a diagnóstico: no toca disco ni sabe qué es un
            # vault, así que `vault_onboard` y `vault_write` no tenían por qué
            # cruzar una frontera para validar una cadena que ya tenían.
            "vault_mermaid_reglas",
        ],
    },
    "autoria": {
        "titulo": "Autoría",
        "lenguaje": ["nota", "frontmatter", "slug", "sección", "alias"],
        "puertos": {
            "escribir_nota": "vault_write:vault_write",
            "anexar": "vault_append:vault_append",
            "mover": "vault_move:move_note",
            "fusionar": "vault_merge:vault_merge",
            "buscar": "vault_search:vault_search",
            "hablar": "vault/autoria/voz:speak",
            "tipo_por_carpeta": "vault_write:tipo_por_carpeta",
        },
        "prohibe": [],
        "modulos": [
            "vault_write", "vault_append", "vault_move", "vault_merge",
            "vault_read", "vault_diff", "vault_delta", "vault_list",
            "vault_search", "vault_knowledge_get", "vault_knowledge_save",
            "vault_bibliography_save", "vault_bug_save", "vault_diagram_save",
            "vault_diagram_export", "vault_env_save", "vault_flow_save",
            "vault_incident_save", "vault_infra_save", "vault_ncr_save",
            "vault_pattern_save", "vault_pattern_list", "vault_privacy_save",
            "vault_release_save", "vault_requirement_save", "vault_risk_save",
            "vault_runbook_save", "vault_runbook_log", "vault_slo_save",
            "vault_test_save", "vault_dataset", "vault_ai_decision",
            "vault_change_log", "vault_voice", "vault_fix_brackets",
            "vault_frontmatter_heal", "vault_frontmatter_completar", "vault_supersede",
            "vault_delete", "vault_undo",
            "vault_timeline", "vault_project_overview", "vault_project_status",
            "vault_qa_save", "vault_project",
            # v41.3 — estaba declarada en el núcleo desde el principio y AP-59
            # lo midió en v40.20: fan-in cero, ningún consumidor. Es una tool
            # que escribe notas de observabilidad, del mismo oficio que
            # `vault_slo_save` o `vault_incident_save`. Solo importa módulos
            # del núcleo, así que mudarla no estrena ningún cruce.
            "vault_log_error",
        ],
    },
    "grafo": {
        "titulo": "Grafo",
        "lenguaje": ["nodo", "arista", "wikilink", "huérfano", "componente"],
        "puertos": {
            "construir_grafo": "vault_graph:vault_graph",
            "resolver_wikilink": "vault_link_safety:validate_wikilinks",
            "impacto": "vault_impact:vault_impact",
            # Lo que el gancho del write path hace con cada nota (AP-47), con la
            # misma composición, para quien quiera refrescar una a mano.
            "refresco_de_grafo": "vault_graph:refrescar_nota_en_grafo",
        },
        "prohibe": [],
        "modulos": [
            "vault_graph", "vault_graph_fix", "vault_graph_inspect",
            "vault_graph_merge", "vault_relation_add", "vault_link_safety",
            "vault_impact", "vault_code_map", "vault_code_module",
            "vault_code_query", "vault_code_relation", "vault_code_sync",
            "vault_code_tag", "vault_infra_map", "vault_env_matrix",
        ],
    },
    "gobernanza": {
        "titulo": "Gobernanza",
        "lenguaje": [
            "norma", "guard", "enforcement", "severidad", "violación",
            "estado", "transición de estado", "fundamento", "hallazgo",
        ],
        "puertos": {
            "NORM_CATALOG": "vault_norms:NORM_CATALOG",
            "auditar": "vault_audit:vault_audit",
            "puntuar_calidad": "vault_quality_check:vault_quality_check",
            # Los tres registros que `AGENTS.md` declara fuente única de
            # verdad y que, sin embargo, se entraban a leer por fuera de la
            # superficie publicada. Un dato canónico que no es puerto es un
            # dato que se acaba copiando: es lo que pasó con la severidad.
            "vocabulario_de_estado": "vault_norms:STATUS_VOCAB",
            "vocabulario_de_dominio": "vault_norms:DOMAIN_STATUS_VOCABS",
            "valores_cia": "vault_fundamentals:cia_valores",
            # Los concentradores de la baseline de `off_port`, y la razón de
            # que aquella cifra engañara: doce `*_save` importando el mismo
            # helper de estado no son doce fugas por la frontera, son **un
            # puerto que el registro no nombraba**. El código llevaba razón y
            # el registro iba por detrás — el mismo hallazgo que hizo que
            # `puertos` dejara de ser una lista (ver la nota de arriba).
            #
            # Declararlos no relaja nada: los cuatro son públicos y el guard
            # rechaza desde v40.8 que un puerto nombre un símbolo privado.
            "lineas_de_estado": "vault_norms:status_frontmatter_lines",
            "referencias_de_norma": "vault_norms:compute_norm_refs",
            "normalizar_estado": "vault_norms:normalize_status",
            "transiciones_de_estado": "vault_norms:STATUS_TRANSITIONS",
            "registro_de_ciclo_de_vida": "vault_norms:LIFECYCLE_REGISTRY",
            "cuerpo_sin_marcadores": "vault_norms:cuerpo_sin_marcadores",
            "norma_por_codigo": "vault_norms:norma_por_codigo",
            # El motor que audita un vault contra el catálogo. Es la superficie
            # más pública que tiene gobernanza —`vault_sanacion` la llama para
            # las doce fases— y llevaba versiones sin declararse, así que ese
            # cruce contaba como fuga por la frontera. No lo era: es la razón
            # de que la frontera exista. Se declara **antes** de partir
            # `vault_norms` a propósito; hacerlo en el mismo commit habría
            # mezclado «este cruce siempre fue legítimo» con «este cruce cambió
            # de módulo», y con la baseline indexada por la cadena
            # `origen -> destino` no habría forma de saber cuál de las dos
            # cosas movió la cifra.
            "auditar_normas": "vault_norms:vault_norms_audit",
            # El audit que corre sobre un vault consumidor es una superficie
            # distinta de la fachada histórica, que además observa el propio
            # repositorio del estándar. El dueño vive en Gobernanza y la
            # sanación entra aquí para no arrastrar smoke ni cobertura meta.
            "auditar_runtime": "vault/gobernanza/auditoria_runtime:auditar_runtime",
            # El peso de cada norma en el healthIndex. Es la otra mitad
            # canónica de la severidad —el catálogo dice cuánto importa, esto
            # dice cuánto cuesta— y hasta v40.10 nadie las cruzaba: AP-22
            # llevaba seis versiones declarada `critical` y penalizada por
            # debajo de una `high`. Se publica como puerto para que el guard de
            # AP-55 lo lea en vez de copiarlo, que es como habría nacido la
            # tercera fuente de verdad sobre el mismo hecho.
            "penalizaciones": "vault_audit:PENALIZACIONES",
            # Qué cuenta como documentación del estándar y no como nota del
            # vault. Nació dentro de `vault_audit` en v40.5 —por contenido y no
            # por ubicación— y allí se quedó, así que el contraste de regla 7
            # medía los enlaces de ejemplo del manifiesto copiado como enlaces
            # rotos del consumidor. Se publica como puerto en vez de
            # reimplementarse: dos versiones del mismo criterio divergen el día
            # que una cambia, y ésta ya cambió una vez.
            "identidad_de_documentacion": "vault_audit:es_documentacion_del_estandar",
            "FUNDAMENTOS": "vault_fundamentals:FUNDAMENTALS",
            "validar_mermaid": "vault_mermaid_check:validate_mermaid",
            # El gancho de secretos lo llama el write path del kernel: es la
            # única forma que tiene gobernanza de intervenir antes de que una
            # escritura ocurra, así que es frontera de pleno derecho. Desde el
            # lote B de la deuda #12 (2026-10-09) el símbolo vive en
            # `vault/gobernanza/secret_scan`; `vault_secret_scan` es su alias y
            # un puerto se declara donde el símbolo vive (v40.17).
            "gancho_de_secretos": "vault/gobernanza/secret_scan:vault_write_hook",
            "hay_hallazgos_bloqueantes": "vault/gobernanza/secret_scan:has_blocking_findings",
        },
        "prohibe": [],
        "modulos": [
            # Dos de las tres mitades de lo que hasta v40.26 era un solo
            # fichero de 5.158 líneas. La tercera —`vault_norms_catalog`— se
            # fue al núcleo en v40.27, y el motivo está escrito allí: cuando
            # se partieron, en v40.26, todavía no se sabía cuál de las tres
            # tenía forma de hoja. Ahora se mide.
            "vault_norms", "vault_norms_engine",
            "vault_fuente_unica",
            "vault_audit", "vault_fundamentals",
            "vault_quality_check", "vault_validate", "vault_security_scan",
            "vault_secret_scan", "vault_drift_detect", "vault_mermaid_check",
            "vault_security_rules",
            # Estaba en Autoría. Lo que compone —el índice de calidad, el
            # registro de etiquetas y la nota de `02_Observability/`— lo
            # publica Gobernanza, y desde Autoría leer el índice era un cruce
            # de frontera que ningún test había ejecutado.
            "vault_quality_dashboard",
        ],
    },
    "indices": {
        "titulo": "Índices",
        "lenguaje": [
            "índice", "etiqueta", "término", "sección indexada", "coherencia",
        ],
        "puertos": {
            "reindexar": "vault_reindex:vault_reindex",
            "indice_maestro": "vault_master_index:vault_master_index",
            "vocabulario_de_tags": "vault_tags:canonical_tags",
            # AP-39, camino A/B del write path (auditoría 2026-10-24): la
            # resolución canónica ocurre ANTES de persistir — el frontmatter
            # necesita los tags canónicos para construirse — y el registro
            # append-only va DESPUÉS de la escritura confirmada: anotar antes
            # deja en la bitácora palabras de escrituras que fallaron.
            # `registrar_tags` combina las dos mitades para los escritores que
            # no necesitan la separación; `vault_write` las usa por contrato.
            "resolucion_de_vocabulario": "vault_tags:apply_vocabulary",
            "registro_de_nuevos_terminos": "vault_tags:record_new_tags",
            # El índice de sección lo dispara el write path del kernel desde
            # v39: es el punto por el que índices entra en cada escritura, y
            # llevaba tres versiones cruzando la frontera sin nombre.
            "indice_de_seccion": "vault_section_index:vault_section_index",
            # Por la misma puerta y en el mismo gancho (v40.34): la nota entra en
            # `search-index.json` escriba quien escriba (AP-47). Publicarlo aquí
            # y no importarlo desde cada escritor evita un cruce por escritor.
            "refresco_de_busqueda": "vault_section_index:refrescar_busqueda",
            "registrar_tags": "vault_tags:registrar_tags_de_nota",
            "tags_de_frontmatter": "vault_tags:tags_de_frontmatter",
            "ledger_de_backfill_de_tags": "vault_tags:vault_tags_backfill_ledger",
            "coherencia_de_indices": "vault_reindex:index_coherence",
            # Cruce C de la auditoría 2026-10-24: la sanación enumera por este
            # símbolo desde que dejó de llamar al privado (v40.9) — el
            # contrato de superficie faltaba, no el criterio, que vive en el
            # núcleo (`vault/kernel/enumeracion.py`).
            "enumeracion_indexable": "vault_reindex:notas_indexables",
        },
        "prohibe": [],
        "modulos": [
            "vault_master_index", "vault_reindex", "vault_section_index",
            "vault_tags", "vault_index", "vault_folder_registry", "vault_section",
        ],
    },
    "consulta": {
        "titulo": "Consulta",
        "lenguaje": ["intención", "subgrafo", "paquete de contexto", "preferencia"],
        "puertos": {
            "parsear_consulta": "vault_query_parse:vault_query_parse",
            "subgrafo": "vault_subgraph:vault_subgraph",
            "empaquetar_contexto": "vault_context_pack:vault_context_pack",
            # Fachada cohesiva: los cuatro verbos del contexto de sesión que
            # consume el servidor MCP. Se declaran como puertos hermanos en
            # vez de inventarles un envoltorio que nadie pidió.
            "contexto_de_sesion": "vault_mcp_context:get_context",
            "guardar_contexto": "vault_mcp_context:save_context",
            "cargar_contexto": "vault_mcp_context:load_context",
            "limpiar_contexto": "vault_mcp_context:clear_context",
        },
        "prohibe": ["base de datos", "embeddings", "servicio externo"],
        "modulos": [
            "vault_query_parse", "vault_subgraph", "vault_context_pack",
            "vault_model_profile", "vault_preferences", "vault_ingest",
            "vault_mcp_context", "vault_tokens", "vault_token_counter",
            "vault_token_service", "vault_compact_contracts",
        ],
    },
    "ciclo_de_vida": {
        "titulo": "Ciclo de vida",
        "lenguaje": ["versión", "migración", "sanación", "arranque"],
        "puertos": {
            # v40.28 — el dueño es `vault_version`, hoja del núcleo (AP-62). El
            # puerto se queda declarado aquí porque `vault_standard_upgrade`
            # sigue reexportándolo y el contrato publicado no cambia; lo que
            # cambia es que ya no hace falta cruzar para leerlo.
            "CURRENT_VERSION": "vault_standard_upgrade:CURRENT_VERSION",
            "inicializar": "vault_init:vault_init",
            "migrar": "vault_standard_upgrade:vault_standard_upgrade",
        },
        "prohibe": [],
        "modulos": [
            "vault_init", "vault_onboard", "vault_standard_upgrade",
            "vault_sanacion", "vault_migrate_docs", "vault_migrate_rollback",
            "vault_propagate", "vault_sdd_init", "vault_history_compact",
            "vault_arquitectura_en",
        ],
    },
    "durabilidad": {
        "titulo": "Durabilidad",
        "lenguaje": ["backup", "restauración", "cuarentena", "manifiesto"],
        "puertos": {
            "crear_backup": "vault_backup:vault_backup",
            "listar_backups": "vault_backup_list:vault_backup_list",
            "restaurar": "vault_restore:vault_restore",
            "poner_en_cuarentena": "vault_quarantine:vault_quarantine_add",
        },
        "prohibe": ["escribir fuera de la raíz del vault (AP-36)"],
        "modulos": [
            "vault_backup", "vault_backup_list", "vault_restore",
            "vault_quarantine",
        ],
    },
    "meta_toolkit": {
        "titulo": "Meta-toolkit",
        "lenguaje": ["catálogo", "contrato", "spec", "smoke", "conteo derivado"],
        "puertos": {
            "TOOLS_CATALOG": "vault_mcp_catalog:TOOLS_CATALOG",
            "GROUPS": "vault_mcp_catalog:GROUPS",
            "check_contracts": "vault_mcp_catalog:check_contracts",
            # v40.30 — se declara al hacer visible a `cli/`. No es un puerto
            # nuevo por conveniencia para que la puerta pase: `cli/registry.py`
            # lo consume desde siempre y su comentario ya nombraba a este
            # módulo como dueño, con `vault_mcp_catalog --check` vigilando que
            # las tres copias de la frontera de lenguaje no diverjan. Lo que
            # faltaba era decirlo aquí, y mientras `cli/` no tuvo contexto no
            # había dónde notarlo.
            "NATIVE_JS_TOOLS": "vault_mcp_catalog:NATIVE_JS_TOOLS",
            # La CLI consume esta proyección derivada para saber si una tool
            # tiene operación instalada real; no puede inferirlo del script.
            "distribution_metadata": "vault_mcp_catalog:distribution_metadata",
            # Los params que la tool acepta de verdad (argparse conciliado con lo
            # declarado). La CLI leía `TOOLS_CATALOG[t]["params"]` crudo, con 81
            # params que ningún script tiene; el dueño es el que publica el MCP.
            "reconciled_params": "vault_mcp_catalog:reconciled_params",
        },
        # Éste es el contexto que v39.6 dejó a medias: sus módulos ya están
        # anotados `internal` con motivo, pero nada impedía que uno tocase un
        # vault. Es el único contexto cuya frontera es una prohibición.
        # Enunciado corregido en v40.0. El anterior —«escribir en un vault»— era
        # literalmente falso desde el primer día: `vault_manifest` escribe
        # `00_System/tools-manifest.json` y `vault_spec_memory` escribe
        # `00_System/spec-memory.json`. Un enunciado que el código incumple y
        # que ningún guard lee es enforcement `manual`, que la regla 5 prohíbe.
        # Lo que sí es frontera, y ahora falla si se cruza: escribir notas o
        # datos del usuario en una sección de contenido.
        "prohibe": ["escribir en una sección de contenido: sus artefactos "
                    "derivados viven en 00_System/"],
        "modulos": [
            "vault_mcp", "vault_mcp_catalog", "vault_manifest", "vault_smoke",
            "vault_spec_catalog_check", "vault_spec_generate_catalog",
            "vault_spec_memory", "vault_spec_validate", "vault_test_runner",
            "vault_doc_counts", "vault_doc_sync", "vault_doc_staleness", "vault_noop_audit",
            "vault_blame_audit", "vault_error_contract", "vault_foreign_check",
            "vault_gate", "vault_arch", "vault_fix_all",
            # Hoja de datos del manifiesto (AP-58, v41.17): dueña de lo que
            # `vault_manifest` y `vault_spec_memory` compartían. Su sujeto es el
            # catálogo, no un vault — meta-toolkit por lo mismo que los dos.
            "vault_spec_data",
            # Fábrica de release (bump único de versión). Su sujeto es este
            # repo; no toca sección de contenido de vault alguno, y el único
            # escritor que delega (`tool-spec.json`) es `vault_manifest`.
            "vault_release",
            # Mide el changelog del manifiesto contra git (AP-53). Es
            # meta-toolkit por el mismo motivo que `vault_doc_counts`: su
            # sujeto es este repo, no un vault.
            "vault_changelog_check",
            # Firma estable de un sitio de código: la comparten los tres audits
            # con baseline. Vive aquí y no en el kernel porque no sabe nada de
            # vaults — solo de AST — y su único consumidor es el meta-toolkit.
            "vault_firma_sitio",
            # El pilar: qué servicio presta el estándar y qué capacidad realiza
            # cada grupo del catálogo. Es meta-toolkit porque su sujeto es el
            # catálogo —no un vault—: lee `GROUPS` por el puerto de
            # `vault_mcp_catalog` y no toca una nota en ninguna parte.
            "vault_servicio",
            # El plano. Ata los once registros canónicos y no reimplementa
            # ninguno: los puertos rotos los dice `vault_arch`, los contratos
            # `vault_mcp_catalog` y la trazabilidad `vault_servicio`. Un plano
            # que midiera por su cuenta sería AP-05 con formato de tabla.
            "vault_blueprint",
            "vault_norms_coherence",
            "vault_criterios",
            "vault_ciclos",
            # AP-59 (v40.20). Está aquí y no en el kernel a propósito, aunque
            # sea la tool que lo mide: consume `dependencias_del_kernel()` de
            # este mismo módulo, y un módulo del núcleo que importa al
            # meta-toolkit invertiría la dirección que la norma existe para
            # vigilar. Quien mide el núcleo se queda fuera de él.
            "vault_kernel",
            # AP-61 (v40.23). Meta-toolkit por el mismo motivo que los de
            # arriba: su sujeto es el código de este repo —los handlers de sus
            # `try`— y no una nota de nadie. No importa ninguna tool de
            # escritura; solo el recorrido de módulos de `vault_arch` y la
            # firma de sitio que ya comparten los otros audits con baseline.
            "vault_excepcion_declarada",
            # AP-62 (v40.28). Mide el arrastre productor/consumidor sobre el
            # grafo de este repo, así que es meta-toolkit por el mismo motivo
            # que `vault_ciclos` y `vault_kernel`: su sujeto es el código, no
            # una nota. Consume `_mapa_modulos()` de aquí y el fan-out de
            # `vault_grafo_import`, que es el dueño del grafo — medirlo por su
            # cuenta habría sido AP-57 en la tool que nace para vigilar
            # justamente que nadie pague por lo que no consume.
            "vault_recursos",
            # AP-68 (v41.19). Meta-toolkit por sujeto —mide este repo, no
            # ninguna nota— y con la misma diferencia que `vault_produccion`:
            # no mide el repo contra sus propios registros, sino que el proceso
            # que el repo lanza a git pase por su dueño. No importa ninguna tool
            # de escritura; consume `vault.kernel.procesos_git`, la hoja del
            # núcleo que es el criterio, para no reimplementarlo (AP-57).
            "vault_procesos_git",
            # v40.31. Meta-toolkit por sujeto —mide este repo, no ninguna nota—
            # pero con una diferencia respecto a todas sus vecinas: las demás
            # miden el repo contra sí mismo, y esta mide el repo contra lo que
            # le promete a quien lo instala. Es hoja: solo lee ficheros del
            # árbol (pyproject, la CI, INSTALL.md) y no importa ningún registro,
            # porque preguntarle al registro qué prometemos sería volver a
            # certificarnos con nuestro propio criterio (AP-44).
            "vault_produccion",
            # Publica `vault_contrato_nota` como un JSON Schema por versión en
            # `schemas/`. Meta-toolkit por sujeto: escribe en este repo, no en
            # ningún vault. El contrato es del núcleo; quien lo serializa, no.
            "vault_esquema",
            # Métricas de desarrollo y de producto con objetivo e histórico.
            # Meta-toolkit por sujeto: mide este repo y escribe en `scripts/`
            # y `docs/`, nunca en un vault.
            "vault_metricas",
            # Genera adaptadores de operaciones desde registros canónicos.
            # Meta-toolkit por sujeto: genera artefactos para la distribución.
            "vault_distribution_sync",
            # v41.12 — el auditor tool por tool (C0–C5) y su selector de
            # alcance. Meta-toolkit por el mismo motivo que `vault_smoke`:
            # su sujeto es el catálogo de este repo, no una nota de nadie.
            "vault_toolkit_audit", "vault_test_scope",
        ],
    },
    # v40.30 — el contexto que faltaba, y el hueco que su ausencia abría.
    #
    # `cli/` entró en `ARBOLES_MEDIDOS` en v40.9 con el motivo escrito arriba:
    # «donde el consumidor lee el error, no lo medía nadie». Pero el alcance se
    # amplió en el **descubrimiento de ficheros** y no en la **clasificación**:
    # `_mapa_modulos()` se construye solo desde `CONTEXTS`, así que
    # `mapa.get("registry")` devolvía `None` y las dos rutas de detección
    # —`cruces()` y el detector off-port— descartaban cada fichero de `cli/`
    # con `if origen is None: continue` antes de mirar un solo import.
    #
    # El resultado era el mismo fallo que motivó ampliar el alcance, una capa
    # más abajo: `cli/registry.py` importaba `vault_mcp_catalog` desde siempre y
    # ese cruce no salía ni en `crossings` ni en `off_port_sites`. Un fichero
    # medido que no puede clasificarse no está medido; publica un cero.
    #
    # No es un contexto de dominio y por eso no tiene puertos: es adaptador de
    # transporte, exactamente como `scripts/` y el `.mjs`, y el límite 4 ya lo
    # nombraba mientras el registro no lo conocía.
    "cli": {
        "titulo": "CLI",
        "lenguaje": ["comando", "registro de tools", "preflight", "envelope"],
        "puertos": {},
        "prohibe": ["decidir: traduce argumentos a llamadas y envelopes a "
                    "salida; la decisión vive en la tool"],
        "modulos": [
            "vault_cli", "registry", "resolver", "safety", "runner", "analyzer",
            "scheduler", "__main__",
        ],
    },
}

#: Los cuatro límites, en el mismo orden en que los declara el plano.
LIMITES = [
    "Kernel ← todos. Nadie más puede ser dependencia de todos.",
    "Contexto ↛ contexto. Se consume el puerto publicado, no el módulo ajeno.",
    "Meta-toolkit ↛ vault. No importa nada que escriba en un vault.",
    "Adaptadores ↛ dominio ajeno. `scripts/`, `cli/` y el `.mjs` traducen "
    "transporte; no deciden.",
    "Raíz de composición: `vault/kernel/adaptadores.py` es el único fichero que "
    "puede cruzar a cualquier contexto, porque su trabajo es cablearlos.",
]

#: La única excepción al límite 2, declarada por nombre y no escondida en el
#: guard. Cablear implica conocer a todos: el objeto que construye el
#: `VaultContext` tiene que resolver el catálogo de normas, el registro de
#: secciones y el escritor real. Lo que la excepción compra es que ese
#: conocimiento viva en **un** fichero en lugar de repartirse por el dominio; lo
#: que cuesta es que ese fichero hay que leerlo entero al revisarlo. Una
#: exención anónima habría hecho lo mismo sin dejar constancia.
RAIZ_COMPOSICION = "vault/kernel/adaptadores.py"

#: Vínculos de nivel de módulo que TIENEN que quedar congelados, declarados uno
#: a uno. AP-49 penaliza derivar del vault al importar porque la constante deja
#: de seguir al vault activo; aquí eso es justamente el requisito.
#:
#: `vault_raiz._VAULT_ROOT_DETECTADO` guarda el vault que la autodetección eligió
#: al cargar, para que `reset_vault_root()` tenga a dónde volver. Si siguiera al
#: vault activo no serviría de nada: sería una copia del sitio del que hay que
#: salir. La exención va por nombre y no por heurística —«los que empiecen por
#: guion bajo», por ejemplo— porque una heurística abre la puerta a que el
#: próximo vínculo congelado se cuele por parecerse.
#:
#: v40.17: era `vault_io._VAULT_ROOT_DETECTADO`. El vínculo no es nuevo ni ha
#: cambiado de forma — se mudó con el subsistema de raíz a su propia hoja. Se
#: anota el nombre viejo aquí, y no en el conjunto, porque el símbolo ya no
#: existe allí: una exención que no protege nada es ruido que se lee como deuda.
VINCULOS_INTENCIONALES = frozenset({
    "vault_raiz._VAULT_ROOT_DETECTADO",
})


# ── El mapa módulo → contexto ────────────────────────────────────────────────

def _mapa_modulos() -> dict[str, str]:
    mapa: dict[str, str] = {}
    for ctx, datos in CONTEXTS.items():
        for mod in datos["modulos"]:
            if mod in mapa:
                raise ValueError(
                    f"{mod} declarado en dos contextos: {mapa[mod]} y {ctx}. "
                    f"Un módulo pertenece a exactamente uno."
                )
            mapa[mod] = ctx
    return mapa


def contexto_de(modulo: str) -> str | None:
    return _mapa_modulos().get(modulo)


def _modulos_en_disco() -> list[str]:
    return sorted(p.stem for p in SCRIPTS_DIR.glob("vault_*.py"))


def _modulos_cli() -> dict[str, Path]:
    """Los ficheros de `cli/`, por su stem — la clave con que los ve el mapa.

    Existe porque `cruces()` recorría `_modulos_en_disco()` (que globa
    `scripts/vault_*.py`) y `_modulos_dominio()` (que recorre `vault/`), y
    entre las dos no quedaba nadie que abriera `cli/`. El detector off-port sí
    llegaba, por iterar `arboles_medidos()`, pero se frenaba un paso después en
    el mapa vacío: por eso el arreglo de v40.30 son las dos mitades —declarar
    el contexto y recorrer el árbol—, y no una sola.
    """
    raiz = REPO_ROOT / "cli"
    if not raiz.is_dir():
        return {}
    return {p.stem: p for p in sorted(raiz.glob("*.py"))
            if p.stem != "__init__"}


# ── El grafo de importaciones, por AST ───────────────────────────────────────

def _importaciones(ruta: Path) -> set[str]:
    """Los módulos `vault_*` que importa este fichero, estén donde estén.

    Cuentan los imports diferidos dentro de una función tanto como los de
    cabecera: un `import vault_norms` escondido en un `try:` cruza la frontera
    exactamente igual.

    superseded_by: vault_grafo_import.importaciones (v40.20). El cuerpo vivía
    aquí y `vault_ciclos._grafo` respondía a la misma pregunta con otro criterio
    —contaba los relativos y no filtraba por prefijo—: el mismo criterio escrito
    dos veces y sin dueño (AP-57). Las dos semánticas se conservan **con
    nombre** en el dueño; ésta es `PREFIJO_VAULT`, y no se fundió con la otra
    porque unificarlas cambiaría a la vez los cruces de aquí y las aristas de
    allá, estrenando deuda en dos baselines por un refactor.
    """
    return vault_grafo_import.importaciones(
        ruta, vault_grafo_import.PREFIJO_VAULT)


def _modulos_dominio() -> dict[str, str]:
    """Los módulos de `vault/`, mapeados por el nombre de su paquete.

    El paquete que existe para imponer fronteras era el único que podía
    cruzarlas sin que saltara nada: el guard nacía mirando solo `scripts/`. La
    convención es deliberada y sin registro paralelo (AP-05) — el directorio
    `vault/<contexto>/` **es** la declaración de a qué contexto pertenece, así
    que un paquete cuyo nombre no esté en `CONTEXTS` se reporta sin clasificar
    en vez de colarse.
    """
    if not DOMINIO_DIR.exists():
        return {}
    encontrados: dict[str, str] = {}
    for src in sorted(DOMINIO_DIR.rglob("*.py")):
        paquete = src.relative_to(DOMINIO_DIR).parts[0]
        if src.parent == DOMINIO_DIR:
            continue  # `vault/__init__.py`: la raíz del paquete no es contexto
        clave = f"vault/{src.relative_to(DOMINIO_DIR).as_posix()}"
        encontrados[clave] = paquete if paquete in CONTEXTS else ""
    return encontrados


def _destino_de_import(nodo: ast.AST, origen_rel: Path) -> set[str]:
    """A qué contextos apunta un import escrito dentro de `vault/`.

    Los imports relativos hay que resolverlos a mano: `from ..kernel.contexto
    import X` desde `vault/durabilidad/repositorio.py` apunta al kernel, y un
    `.` a su propio paquete. Ignorarlos dejaría ciego al guard justo en el
    código nuevo, que es donde más barato sale corregir.
    """
    if isinstance(nodo, ast.ImportFrom) and nodo.level:
        # level=1 es el propio paquete; level=2 sube a `vault/`.
        if nodo.level >= 2 and nodo.module:
            return {nodo.module.split(".")[0]}
        return {origen_rel.parts[0]}
    # Absoluto: `from vault.grafo.repositorio import X`. Es la forma que usan
    # los adaptadores de `scripts/`, y el guard nacía sin verla: un adaptador
    # podía cablear el dominio de otro contexto sin que saltara nada, que es
    # exactamente el punto ciego que el refactor existe para cerrar.
    if isinstance(nodo, ast.ImportFrom) and nodo.module:
        partes = nodo.module.split(".")
        if partes[0] == "vault" and len(partes) > 1:
            return {partes[1]}
    if isinstance(nodo, ast.Import):
        return {
            a.name.split(".")[1]
            for a in nodo.names
            if a.name.split(".")[0] == "vault" and "." in a.name
        }
    return set()


@_una_vez_por_medicion
def cruces() -> list[dict]:
    """Toda importación que cruza una frontera no declarada.

    No es cruce depender del kernel (límite 1) ni importar dentro del propio
    contexto. Todo lo demás lo es, y se reporta como `origen → destino` con los
    dos contextos, que es lo que hace falta para decidir qué puerto publicar.
    """
    mapa = _mapa_modulos()
    fuera = []
    for nombre in _modulos_en_disco():
        origen = mapa.get(nombre)
        if origen is None:
            continue
        for destino_mod in sorted(_importaciones(SCRIPTS_DIR / f"{nombre}.py")):
            destino = mapa.get(destino_mod)
            if destino is None or destino == origen or destino == KERNEL:
                continue
            # Un gancho del kernel es una frontera **declarada**, con su motivo
            # escrito, y `dependencias_del_kernel()` ya lo mide. Contarlo aquí
            # además lo dejaba escondido dentro de la baseline genérica: los
            # tres que existían entraron así, y el registro de ganchos quedaba
            # inservible —usarlo rompía una puerta que solo puede encoger—.
            if (nombre, destino_mod) in GANCHOS_DEL_KERNEL:
                continue
            fuera.append({
                "from": nombre, "from_context": origen,
                "to": destino_mod, "to_context": destino,
            })
        # Un adaptador que cablea el dominio de otro contexto cruza igual. El
        # caso legítimo existe —`vault_subgraph` lee el grafo, que es de
        # Grafo— pero tiene que verse: cablear en silencio es como se coló
        # AP-48.
        try:
            arbol_s = _ast_de(SCRIPTS_DIR / f"{nombre}.py")
        except SyntaxError:
            continue
        for nodo in _nodos(arbol_s):
            for destino in _destino_de_import(nodo, Path(nombre)):
                if destino in CONTEXTS and destino not in (origen, KERNEL):
                    # Mismo criterio que arriba: un gancho del kernel hacia el
                    # dominio de otro contexto es una frontera declarada.
                    if (nombre, f"vault/{destino}") in GANCHOS_DEL_KERNEL:
                        continue
                    fuera.append({
                        "from": nombre, "from_context": origen,
                        "to": f"vault/{destino}", "to_context": destino,
                    })

    # `cli/`, con la misma vara (v40.30). Estaba en `ARBOLES_MEDIDOS` desde
    # v40.9 y ninguna de las dos rutas de detección lo abría: el alcance se
    # amplió donde se buscan los ficheros y no donde se decide de qué contexto
    # vienen. Un adaptador de transporte cruza igual que una tool.
    for nombre, ruta in sorted(_modulos_cli().items()):
        origen = mapa.get(nombre)
        if origen is None:
            continue
        for destino_mod in sorted(_importaciones(ruta)):
            destino = mapa.get(destino_mod)
            if destino is None or destino == origen or destino == KERNEL:
                continue
            if (nombre, destino_mod) in GANCHOS_DEL_KERNEL:
                continue
            fuera.append({
                "from": f"cli/{nombre}", "from_context": origen,
                "to": destino_mod, "to_context": destino,
            })

    # El dominio, con la misma vara. Un módulo de `vault/x/` que importe
    # `vault_norms` cruza igual que si viviera en `scripts/`.
    for clave, origen in sorted(_modulos_dominio().items()):
        if not origen or clave == RAIZ_COMPOSICION:
            continue
        ruta = DOMINIO_DIR / clave[len("vault/"):]
        rel = ruta.relative_to(DOMINIO_DIR)
        # El cruce de un dueño se clava con el nombre de su alias, igual que
        # `clave_de_modulo`: migrarlo no estrena un cruce que ya estaba.
        clave = alias_de_dueno(ruta) or clave
        for destino_mod in sorted(_importaciones(ruta)):
            destino = mapa.get(destino_mod)
            if destino is None or destino == origen or destino == KERNEL:
                continue
            # Mismo criterio que en `scripts/` y `cli/`: el gancho de un dueño
            # migrado sigue siendo una frontera declarada, y lo mide
            # `dependencias_del_kernel()` con el nombre del alias.
            if (clave, destino_mod) in GANCHOS_DEL_KERNEL:
                continue
            fuera.append({
                "from": clave, "from_context": origen,
                "to": destino_mod, "to_context": destino,
            })
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for nodo in _nodos(arbol):
            for destino in _destino_de_import(nodo, rel):
                if destino in CONTEXTS and destino not in (origen, KERNEL):
                    if (clave, f"vault/{destino}") in GANCHOS_DEL_KERNEL:
                        continue
                    fuera.append({
                        "from": clave, "from_context": origen,
                        "to": f"vault/{destino}", "to_context": destino,
                    })
    return fuera


def dominio_sin_clasificar() -> list[str]:
    """Paquetes de `vault/` cuyo nombre no corresponde a ningún contexto."""
    return sorted(k for k, v in _modulos_dominio().items() if not v)


def usos_del_nombre_congelado() -> list[dict]:
    """El punto ciego de `vinculos_congelados()`: usar el NOMBRE `VAULT_ROOT`.

    `vinculos_congelados()` mide asignaciones de nivel de módulo, y esa medida
    dio 0 al terminar la migración de los ocho contextos. Pero veinte módulos
    seguían haciendo `from vault_io import VAULT_ROOT` y usándolo **dentro de
    funciones**: el guard los daba por limpios y seguían dependiendo del
    paliativo —que `set_vault_root()` les reescribiera el nombre por detrás—,
    que es justo lo que el refactor existe para no necesitar.

    El caso legítimo se declara con alias: `VAULT_ROOT as _DETECTED_ROOT` en
    `vault_norms` quiere la raíz **detectada**, no la efectiva, y decirlo con un
    alias es la diferencia entre pedirlo y arrastrarlo.

    Puerta dura, sin baseline: se midió cero al declararla.
    """
    hallazgos = []
    for nombre in sorted(_modulos_en_disco()):
        # Deuda #12: el código de un módulo migrado es el del dueño (AP-44).
        ruta = vault_grafo_import.codigo_de(SCRIPTS_DIR / f"{nombre}.py")
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for nodo in _nodos(arbol):
            if not isinstance(nodo, ast.ImportFrom) or nodo.module != "vault_io":
                continue
            for alias in nodo.names:
                if alias.name == "VAULT_ROOT" and alias.asname is None:
                    hallazgos.append({"module": nombre, "line": nodo.lineno})
    return hallazgos


def vinculos_congelados() -> list[dict]:
    """Asignaciones de nivel de módulo que derivan de `VAULT_ROOT` (AP-49).

    Solo cuenta el nivel de módulo: dentro de una función la misma expresión se
    evalúa en cada llamada y por tanto **sí** respeta `set_vault_root()`. Ese es
    exactamente el arreglo que la norma pide, así que marcarlo sería marcar la
    solución.

    Tampoco cuenta si la expresión llama a `get_vault_root()`: resolver tarde a
    través del kernel es la vía correcta aunque el resultado se guarde.
    """
    hallazgos = []
    for nombre in _modulos_en_disco():
        ruta = vault_grafo_import.codigo_de(SCRIPTS_DIR / f"{nombre}.py")
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for nodo in arbol.body:
            if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                continue
            valor = nodo.value
            if valor is None:
                continue
            usa_root = any(
                isinstance(n, ast.Name) and n.id == "VAULT_ROOT"
                for n in ast.walk(valor)
            )
            resuelve_tarde = any(
                isinstance(n, ast.Call) and (
                    getattr(n.func, "id", None) == "get_vault_root"
                    or getattr(n.func, "attr", None) == "get_vault_root"
                )
                for n in ast.walk(valor)
            )
            if not usa_root or resuelve_tarde:
                continue
            destinos = (
                [nodo.target] if isinstance(nodo, ast.AnnAssign) else nodo.targets
            )
            for d in destinos:
                if not isinstance(d, ast.Name):
                    continue
                if f"{nombre}.{d.id}" in VINCULOS_INTENCIONALES:
                    continue
                hallazgos.append({
                    "module": nombre, "binding": d.id, "line": nodo.lineno,
                })
    return hallazgos


def _clave(cruce: dict) -> str:
    return f"{cruce['from']} -> {cruce['to']}"


def sin_clasificar() -> list[str]:
    """Módulos en disco que ningún contexto reclama.

    Es la misma clase de hueco que la invariante 4 de `vault_mcp_catalog`: un
    módulo que no está en ningún registro no lo echa en falta nadie. Aquí es
    puerta dura desde el primer día, porque clasificar cuesta una línea.
    """
    mapa = _mapa_modulos()
    return [m for m in _modulos_en_disco() if m not in mapa]


# ── El puente `scripts/` → `_impl/` (deuda #12) ─────────────────────────────

def tiene_hogar(arbol: ast.AST, contexto: str) -> bool:
    """¿El módulo importa algo del paquete de su propio contexto?

    ADR-0002 declara el puente transitorio: se va cuando el código de
    `scripts/` viva en `vault/<contexto>/`. El criterio es sintáctico a
    propósito —un `from vault.<contexto>…` en cualquier sitio del fichero— y
    dice menos de lo que parece: importar un repositorio es empezar a delegar,
    no haber migrado. Distingue «aún no ha empezado» de «ya tiene dónde ir»,
    que es lo que hacía falta para que un módulo nuevo no entrara con toda su
    lógica en `scripts/` sin que nadie lo notara.
    """
    prefijo = f"vault.{contexto}"
    for nodo in _nodos(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and (
                nodo.module == prefijo or nodo.module.startswith(prefijo + ".")):
            return True
        if isinstance(nodo, ast.Import) and any(
                a.name == prefijo or a.name.startswith(prefijo + ".")
                for a in nodo.names):
            return True
    return False


FUERA_DE_LA_WHEEL = REPO_ROOT / "empaquetado" / "fuera-de-la-wheel.json"


def _modulos_fuera_de_la_wheel() -> list[str]:
    """La lista derivada; sin ella (repo parcial) no se excluye nada, y la
    cifra sale más alta, nunca más baja que la real."""
    try:
        return json.loads(FUERA_DE_LA_WHEEL.read_text(encoding="utf-8")).get("modulos", [])
    except FileNotFoundError:
        return []


def modulos_sin_hogar() -> list[str]:
    """Módulos de `scripts/` que no importan nada de `vault/<su contexto>/`.

    Es la cifra de la deuda #12, derivada en vez de escrita. Un contexto sin
    paquete en `vault/` no puede dar hogar a nadie y no cuenta: esos módulos
    no tienen adónde migrar todavía, y contarlos sería medir otra cosa.

    Tampoco cuenta lo que la wheel no lleva (`empaquetado/fuera-de-la-wheel.json`,
    derivado de la capacidad «gobernanza del estándar»): el puente mapea
    `scripts/` a `vault_toolkit/_impl/`, y un módulo que no viaja no lo cruza.
    Se lee la pasarela —el JSON que usa `empaquetado/construir.py`— y no
    `vault_servicio`, que es quien la deriva y la vigila.
    """
    paquetes = {d.name for d in DOMINIO_DIR.iterdir() if d.is_dir()} if DOMINIO_DIR.exists() else set()
    fuera = set(_modulos_fuera_de_la_wheel())
    sin_hogar = []
    for modulo in _modulos_en_disco():
        ctx = contexto_de(modulo)
        if ctx not in paquetes or modulo in fuera:
            continue
        if not tiene_hogar(_ast_de(SCRIPTS_DIR / f"{modulo}.py"), ctx):
            sin_hogar.append(modulo)
    return sin_hogar


#: El contrato del puente (ADR-0002, deuda #12), cerrado el 2026-10-16: en la
#: wheel, todo módulo de `scripts/` es alias de su dueño en `vault/<contexto>/`,
#: tiene hogar allí o es un ancla declarada aquí con su motivo. La baseline
#: `bridge_modules` congelaba lo que había y bloqueaba lo nuevo, pero
#: `--freeze` la reescribe sin negarse: un módulo sin hogar entraba
#: congelándolo. Este registro no lo escribe ningún freeze.
ANCLA_DEL_PUENTE: dict[str, str] = {
    "vault_grafo_import": (
        "Dice dónde está `scripts/` (`_impl/` en la wheel) con su propio "
        "`__file__`, y de su `DIRECTORIO` derivan el suyo los dueños que se "
        "mudaron a `vault/kernel/`. Mudarlo exigiría derivar ese directorio de "
        "dos formas —por el checkout y por el paquete instalado— en el sitio "
        "que existe para que nadie más lo derive. Lo fija "
        "`tests/test_puente_sin_hogar.py::test_el_ancla_del_puente_no_se_muda`."
    ),
    # Fábrica de release (v41.17). No es tool de catálogo ni viaja en la
    # wheel: bump único de los ficheros de versión de ESTE repo. No tiene
    # dónde ir en `vault/` ni lo tendrá — escribir version.py/banner/
    # pyproject es un trabajo del checkout, no una capacidad de memoria.
    "vault_release": (
        "Fábrica de release: bump único de los siete ficheros de versión de "
        "este repo. No es tool de catálogo (no cruza el puente porque no "
        "viaja en la wheel) y no tiene duño en vault/: su sujeto es el "
        "checkout, no una capacidad de memoria. Ancla declarada con motivo, "
        "no deuda congelada."
    ),
}


def contrato_del_puente(sin_hogar=None) -> dict:
    """Qué incumple el contrato del puente.

    `fuera_de_contrato`: módulos sin hogar que no son ancla. `ancla_con_hogar`:
    anclas declaradas que ya no están en el puente, y que por tanto mienten.
    """
    puente = set(modulos_sin_hogar() if sin_hogar is None else sin_hogar)
    anclas = set(ANCLA_DEL_PUENTE)
    return {"fuera_de_contrato": sorted(puente - anclas),
            "ancla_con_hogar": sorted(anclas - puente)}


#: Lo que cuenta como escribir. `mkdir` entra: crear una sección de contenido
#: es tocar el vault del usuario aunque no se deje un byte dentro.
#:
#: Hasta v41.3 incluía `write_report`, que lee el ledger de escrituras
#: (`vault_ledger`) y no escribe nada. `replace` sigue, pero no se decide por
#: el nombre: lo filtra `llamada_de_escritura`, porque también es `str.replace`.
#:
#: `escribir` y `escribir_json` son el puerto `Escritor` del kernel
#: (`ctx.escritor`), desde 2026-10-08: el residuo de la deuda #3 se saldó
#: mudando escrituras de `00_System/` al repositorio del dueño, que escribe por
#: el puerto, y una escritura que la guarda no viera al mudarse quedaría
#: escondida, no ordenada. Medido ese día: añadirlas no estrenó ningún hallazgo.
_LLAMADAS_DE_ESCRITURA = frozenset({
    "write_text", "write_bytes", "mkdir", "touch", "rename", "replace",
    "unlink", "rmtree", "atomic_write_text", "atomic_write_json",
    "escribir", "escribir_json",
})

#: Las escrituras cuyo destino es el primer argumento y no el receptor.
_ESCRITURAS_POR_ARGUMENTO = ("atomic_write", "escribir")


def llamada_de_escritura(nodo: ast.AST) -> str | None:
    """El nombre de la escritura que hace esta llamada, o None si no escribe.

    Única definición de «escribe» para las guardas de este módulo. `replace` se
    decide por la forma y no por el nombre: `str.replace(viejo, nuevo[, n])`
    lleva dos o más argumentos; `Path.replace(destino)` lleva uno —y si va
    con nombre, se llama `target`, no `tzinfo` como el de `datetime`—, y
    `os.replace(origen, destino)` se reconoce por el receptor.
    """
    if not isinstance(nodo, ast.Call):
        return None
    fn = nodo.func
    nombre = fn.attr if isinstance(fn, ast.Attribute) else (
        fn.id if isinstance(fn, ast.Name) else None)
    if nombre not in _LLAMADAS_DE_ESCRITURA:
        return None
    if nombre == "replace":
        if not isinstance(fn, ast.Attribute):
            return None
        es_os = isinstance(fn.value, ast.Name) and fn.value.id == "os"
        if not es_os and len(nodo.args) + len(nodo.keywords) != 1:
            return None
        # `datetime.replace(tzinfo=...)` también lleva uno; el de `Path` solo
        # puede llamarse `target`.
        if any(k.arg != "target" for k in nodo.keywords):
            return None
    return nombre


def _secciones_de_contenido() -> set[str]:
    """Las secciones que no son `00_System/`, leídas del registro canónico.

    No se listan aquí: `vault_registry.ORDERED_SECTIONS` ya es la fuente única
    (AP-05), y una copia se quedaría atrás en cuanto el estándar añadiera una.
    """
    import vault_registry

    return {s for s in vault_registry.ORDERED_SECTIONS if s != "00_System"}


def rutas_duplicadas() -> list[dict]:
    """El mismo fichero declarado en dos repositorios de dominio (AP-05).

    Salió dos veces seguidas en la migración y siempre igual: un contexto lee un
    fichero que otro escribe, y en vez de pedírselo lo vuelve a derivar. Antes
    de esta puerta, `quality-index.json` se calculaba en cuatro módulos de tres
    contextos y `search-index.json` iba camino de su cuarta copia en `vault/`.
    Lo caro no es la duplicación: es que el día que un fichero se mueva solo se
    entera el que lo escribe, y el que lo lee devuelve `{}` sin fallar.

    Se mira **solo** el paquete de dominio, y solo constantes de nivel de módulo
    con pinta de nombre de fichero. Un contexto que necesite una ruta ajena la
    pide a su dueño; ese cruce se declara en el baseline y se ve.
    """
    por_fichero: dict[str, list[str]] = {}
    for repo in sorted(DOMINIO_DIR.glob("*/repositorio.py")):
        arbol = _ast_de(repo)
        for nodo in arbol.body:
            if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1):
                continue
            destino = nodo.targets[0]
            if not (isinstance(destino, ast.Name)
                    and destino.id.startswith("FICHERO_")):
                continue
            valor = nodo.value
            if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                por_fichero.setdefault(valor.value, []).append(repo.parent.name)
    return [
        {"file": f, "contexts": sorted(ctxs)}
        for f, ctxs in sorted(por_fichero.items())
        if len(set(ctxs)) > 1
    ]


def _nombre_base(nodo: ast.AST) -> str | None:
    """El `Name` del que cuelga una expresión de ruta: `a / "x" / "y"` → `a`."""
    while True:
        if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
            nodo = nodo.left
        elif isinstance(nodo, ast.Call):
            nodo = nodo.func
        elif isinstance(nodo, ast.Attribute):
            nodo = nodo.value
        elif isinstance(nodo, ast.Name):
            return nodo.id
        else:
            return None


def _nombres_desechables(arbol: ast.AST) -> set[str]:
    """Los nombres que apuntan a un vault de usar y tirar, no al del usuario.

    `vault_smoke` y `vault_test_runner` levantan un vault entero en un temporal
    y lo borran: crean `10_Migrated/` y escriben notas dentro porque es la única
    forma de probar un contrato de verdad. Prohibírselo no protegería a nadie y
    volvería la puerta inútil el primer día.

    Se sigue el dato un salto: lo que sale de `mkdtemp`/`TemporaryDirectory`, y
    el parámetro que lo recibe cuando ese nombre se pasa a otra función del
    módulo. Un salto basta hoy y falla del lado seguro — si algún día no
    alcanza, el guard marca de más y obliga a mirar, que es el error correcto.
    """
    desechables: set[str] = set()
    funciones = {n.name: n for n in _nodos(arbol)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    for nodo in _nodos(arbol):
        origen = None
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            origen, destino = nodo.value, nodo.targets[0]
        elif isinstance(nodo, ast.withitem) and nodo.optional_vars is not None:
            origen, destino = nodo.context_expr, nodo.optional_vars
        if origen is None or not isinstance(destino, ast.Name):
            continue
        texto = ast.dump(origen)
        if "mkdtemp" in texto or "TemporaryDirectory" in texto:
            desechables.add(destino.id)

    for nodo in _nodos(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)):
            continue
        fn = funciones.get(nodo.func.id)
        if fn is None:
            continue
        for i, arg in enumerate(nodo.args):
            if isinstance(arg, ast.Name) and arg.id in desechables:
                if i < len(fn.args.args):
                    desechables.add(fn.args.args[i].arg)
    return desechables


# ── Quién escribe cada subruta de 00_System (deuda #3, v41.3) ────────────────

CARPETA_SISTEMA = "00_System"

#: Las subrutas de `00_System/` que ningún repositorio de dominio declara.
#:
#: El dueño del resto lo declaran los `FICHERO_*` de `vault/<ctx>/repositorio.py`
#: y se deriva (`_duenos_por_repositorio`); copiarlo aquí sería AP-05. Lo que
#: sigue no tiene repositorio que lo declare, y el dueño se fijó con un solo
#: criterio, para no inventar: **el único contexto que lo escribía** al medirlo
#: (2026-10-08). Un test exige que ninguna entrada de aquí aparezca también en
#: un repositorio.
SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO: dict[str, dict] = {
    ".tool-trace.json": {
        "dueno": KERNEL,
        "por_que": "La traza de cada llamada la escribe `vault_errors_trace`, "
                   "que sirve a todas las tools y por eso vive en el kernel.",
    },
    ".tool-tokens.json": {
        "dueno": KERNEL,
        "por_que": "El contador lo anota y lo reinicia `vault_errors_trace` "
                   "(`FICHERO_TOKENS`). Hasta 2026-10-08 lo declaraba Consulta, "
                   "que solo lo lee; lo reexporta anotado en `SUPERSEDED`.",
    },
    "scanner-degraded.jsonl": {
        "dueno": KERNEL,
        "por_que": "Lo anexa `vault_io` cuando el escáner de secretos se degrada, "
                   "fuera del write path a propósito. Salió el 2026-10-08, al "
                   "resolver la guarda las constantes del módulo: antes la "
                   "escritura se veía como subruta dinámica y no se medía.",
    },
    ".voice-counter": {
        "dueno": "autoria",
        "por_que": "Contador de `vault/autoria/voz.py`; nadie más lo escribe.",
    },
    ".trash": {
        "dueno": "autoria",
        "por_que": "La papelera de `vault_move`, único que mueve notas a ella.",
    },
    "change-log.md": {
        "dueno": "autoria",
        "por_que": "La vista legible que escribe `vault_change_log`. Su par "
                   "`.change-log.json` lo declara gobernanza en su repositorio "
                   "y, desde 2026-10-08, también lo escribe ella.",
    },
    "vault-ontology.json": {
        "dueno": "ciclo_de_vida",
        "por_que": "Lo siembra `vault_init` al crear el vault y nadie lo reescribe.",
    },
    "vault_context.json": {
        "dueno": "consulta",
        "por_que": "Lo escribe `vault_mcp_context`, que existe para la consulta.",
    },
    "tool-spec.json": {
        "dueno": "meta_toolkit",
        "por_que": "Lo escribe solo `vault_manifest --bootstrap`, por "
                   "`vault_io.tool_spec_path()`; `vault_mcp_catalog`, "
                   "`vault_compact_contracts`, `vault_sdd_init` y los "
                   "`vault_spec_*` lo leen. Medido y declarado el 2026-10-09. "
                   "Desde v41.3 la guarda ve esa escritura: sigue un nivel la "
                   "función importada cuyo `return` es ruta literal.",
    },
}

#: Funciones del repo que devuelven `<vault>/00_System` sin decirlo literal.
_FUNCIONES_DE_SISTEMA = frozenset({
    "_system_dir", "system_dir", "dir_sistema", "sistema", "_sistema",
    "_sys_dir", "tool_spec_path",
})


@_una_vez_por_medicion
def _propiedades_de_sistema() -> tuple[dict[str, str], dict[str, str]]:
    """Lo que declaran los repositorios: propiedad → subruta y subruta → dueño.

    Se lee la forma que usan todos —``return self.ctx.ruta(CARPETA_SISTEMA,
    FICHERO_X)``—, resolviendo las constantes del propio módulo. Una propiedad
    que en dos módulos apuntase a subrutas distintas no se usa para resolver
    escrituras: sería adivinar.
    """
    props: dict[str, set[str]] = {}
    duenos: dict[str, str] = {}
    for src in sorted(DOMINIO_DIR.glob("*/*.py")):
        arbol = _ast_de(src)
        consts = {
            n.targets[0].id: n.value.value for n in arbol.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
        }
        for fn in _nodos(arbol):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for r in ast.walk(fn):
                if not (isinstance(r, ast.Return) and isinstance(r.value, ast.Call)
                        and isinstance(r.value.func, ast.Attribute)
                        and r.value.func.attr == "ruta"):
                    continue
                vals = [consts.get(a.id) if isinstance(a, ast.Name)
                        else (a.value if isinstance(a, ast.Constant) else None)
                        for a in r.value.args]
                if len(vals) > 1 and vals[0] == CARPETA_SISTEMA and vals[1]:
                    subruta = vals[1].split("/")[0]
                    props.setdefault(fn.name, set()).add(subruta)
                    if src.name == "repositorio.py":
                        duenos.setdefault(subruta, src.parent.name)
    unicas = {p: next(iter(s)) for p, s in props.items() if len(s) == 1}
    return unicas, duenos


def _duenos_por_repositorio() -> dict[str, str]:
    return _propiedades_de_sistema()[1]


def duenos_de_sistema() -> dict[str, str]:
    """Subruta de `00_System/` → contexto dueño: lo derivado más lo declarado."""
    duenos = dict(_duenos_por_repositorio())
    for subruta, entrada in SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO.items():
        duenos.setdefault(subruta, entrada["dueno"])
    return duenos


def _subruta_de_sistema(nodo, nombres, funciones, props, prof=0, consts=None):
    """La primera componente bajo `00_System/` a la que apunta `nodo`.

    `"*"` es la carpeta misma (un `mkdir`), y `None` que no es una ruta de
    sistema o que no se puede decidir sin ejecutar.
    """
    if prof > 6:
        return None
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        if nodo.value == CARPETA_SISTEMA:
            return "*"
        if nodo.value.startswith(CARPETA_SISTEMA + "/"):
            return nodo.value[len(CARPETA_SISTEMA) + 1:].split("/")[0] or "*"
        return None
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
        if isinstance(nodo.right, ast.Constant) and nodo.right.value == CARPETA_SISTEMA:
            return "*"
        izq = _subruta_de_sistema(nodo.left, nombres, funciones, props, prof + 1, consts)
        if izq != "*":
            return izq
        if isinstance(nodo.right, ast.Constant) and isinstance(nodo.right.value, str):
            return nodo.right.value.split("/")[0]
        # Una constante del propio módulo es tan literal como el literal: si no
        # se resolviera, mudar `"x.json"` a `FICHERO_X` escondería la escritura.
        if isinstance(nodo.right, ast.Name) and (consts or {}).get(nodo.right.id):
            return consts[nodo.right.id].split("/")[0]
        return None  # la subruta es dinámica: no se decide
    if isinstance(nodo, ast.Name):
        return nombres.get(nodo.id)
    if isinstance(nodo, ast.Attribute):
        if nodo.attr in _FUNCIONES_DE_SISTEMA:
            return "*"
        if nodo.attr in props:
            return props[nodo.attr]
        if nodo.attr == "parent":
            return _subruta_de_sistema(nodo.value, nombres, funciones, props, prof + 1, consts)
        return None
    if isinstance(nodo, ast.Call):
        fn = nodo.func
        nombre = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else None)
        # Lo que se sabe de la función —del módulo o importada un nivel— gana
        # al colapso por nombre: `tool_spec_path` es la carpeta solo cuando no
        # se sabe de dónde viene.
        if isinstance(fn, ast.Name) and fn.id in funciones:
            return funciones[fn.id]
        if (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                and f"{fn.value.id}.{fn.attr}" in funciones):
            return funciones[f"{fn.value.id}.{fn.attr}"]
        if nombre in _FUNCIONES_DE_SISTEMA:
            return "*"
        if nombre in ("ruta", "joinpath"):
            cs = [a.value for a in nodo.args
                  if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if cs and cs[0] == CARPETA_SISTEMA:
                return cs[1].split("/")[0] if len(cs) > 1 else "*"
            base = (_subruta_de_sistema(fn.value, nombres, funciones, props, prof + 1, consts)
                    if isinstance(fn, ast.Attribute) else None)
            if base == "*":
                return cs[0].split("/")[0] if cs else None
            return base
        if nombre in ("with_suffix", "with_name", "resolve") and isinstance(fn, ast.Attribute):
            return _subruta_de_sistema(fn.value, nombres, funciones, props, prof + 1, consts)
    return None


def _constantes_de_texto(arbol: ast.AST) -> dict[str, str]:
    """`NOMBRE = "texto"` del nivel de módulo: lo que el módulo fija y no cambia."""
    cuerpo = arbol.body if isinstance(arbol, ast.Module) else []
    return {
        n.targets[0].id: n.value.value for n in cuerpo
        if isinstance(n, ast.Assign) and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
    }


def _nombres_de_modulo(ruta: Path) -> list[str]:
    """Cómo se importa un módulo medido: `vault_io`, `scripts.vault_io`, `vault.kernel.x`."""
    rel = ruta.resolve().relative_to(REPO_ROOT).with_suffix("")
    punteado = ".".join(rel.parts)
    return [rel.name, punteado] if rel.parts[0] == "scripts" else [punteado]


def _funciones_importadas(arbol: ast.AST, externas: dict[str, dict[str, str]]) -> dict[str, str]:
    """Nombre local → subruta, para lo que el módulo importa de otro módulo medido.

    `from m import f [as g]` da `g`; `import m [as a]` da `a.f` por cada `f`
    de `m`. Solo resuelve funciones cuyo `return` en su propio módulo ya es una
    ruta literal de `00_System/`: un nivel, sin seguir la cadena.
    """
    vistas: dict[str, str] = {}
    for nodo in _nodos(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
            funcs = externas.get(nodo.module, {})
            for a in nodo.names:
                if a.name in funcs:
                    vistas[a.asname or a.name] = funcs[a.name]
        elif isinstance(nodo, ast.Import):
            for a in nodo.names:
                for f_, sub in externas.get(a.name, {}).items():
                    vistas[f"{a.asname or a.name}.{f_}"] = sub
    return vistas


def _resolver_modulo(arbol: ast.AST, props: dict, funciones: dict[str, str]) -> dict[str, str]:
    """Punto fijo corto: nombres y `return` de funciones que apuntan a `00_System/`."""
    nombres: dict[str, str] = {}
    consts = _constantes_de_texto(arbol)
    forma = _forma_de_resolucion(arbol)
    for _ in range(3):
        for es_funcion, nombre, valores in forma:
            for valor in valores:
                s = _subruta_de_sistema(valor, nombres, funciones, props, consts=consts)
                if s:
                    (funciones if es_funcion else nombres).setdefault(nombre, s)
    return nombres


def _forma_de_resolucion(arbol: ast.AST) -> list[tuple[bool, str, list[ast.AST]]]:
    """Lo que `_resolver_modulo` mira del árbol, en el orden de `ast.walk`.

    `(False, nombre, [valor])` por cada `nombre = valor`, y `(True, función,
    [valores de return])` por cada función, con los `return` de sus anidadas
    —como los veía el recorrido anidado—. Hasta la auditoría del 2026-10-15 el
    punto fijo lo recorría en cada una de sus tres vueltas, y cada función
    otra vez dentro, en las dos llamadas por fichero. La forma no cambia entre
    vueltas ni entre llamadas: se calcula una vez por árbol, y `_ast_de` ya da
    un árbol nuevo cuando cambia el fichero.
    """
    hecho = _FORMAS.get(id(arbol))
    if hecho is not None and hecho[0] is arbol:
        return hecho[1]
    forma: list[tuple[bool, str, list[ast.AST]]] = []
    for nodo in _nodos(arbol):
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)):
            forma.append((False, nodo.targets[0].id, [nodo.value]))
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            forma.append((True, nodo.name, [
                r.value for r in ast.walk(nodo)
                if isinstance(r, ast.Return) and r.value is not None]))
    _FORMAS[id(arbol)] = (arbol, forma)
    return forma


#: id del árbol → (árbol, forma). Guarda el árbol para que un `id` reciclado
#: por el recolector no devuelva la forma de otro.
_FORMAS: dict[int, tuple[ast.AST, list[tuple[bool, str, list[ast.AST]]]]] = {}


def funciones_de_sistema_del_repo(props: dict | None = None) -> dict[str, dict[str, str]]:
    """Módulo → {función → subruta} de las funciones cuyo `return` es una ruta
    literal bajo `00_System/`, en todo el alcance medido.

    `"*"` no entra: que una función devuelva la carpeta ya lo dice el nombre
    (`_FUNCIONES_DE_SISTEMA`), y guardarlo solo serviría para colapsar igual.
    """
    if props is None:
        props = _propiedades_de_sistema()[0]
    indice: dict[str, dict[str, str]] = {}
    for ruta in arboles_medidos():
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        funciones: dict[str, str] = {}
        _resolver_modulo(arbol, props, funciones)
        literales = {
            n.name: funciones[n.name] for n in getattr(arbol, "body", [])
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and funciones.get(n.name, "*") != "*"
        }
        if literales:
            for nombre in _nombres_de_modulo(ruta):
                indice[nombre] = literales
    return indice


def escrituras_de_sistema_en(arbol: ast.AST, props: dict | None = None,
                             externas: dict[str, dict[str, str]] | None = None) -> list[tuple]:
    """`(línea, llamada, subruta)` de cada escritura bajo `00_System/` del árbol.

    Sigue el dato por asignaciones de nombre y por el `return` de funciones del
    propio módulo, con un punto fijo corto, y —si se le pasa `externas`, el
    índice de `funciones_de_sistema_del_repo`— un nivel más: la función
    importada de otro módulo cuyo `return` allí es una ruta literal (desde
    v41.3; así se ve `vault_manifest` escribiendo `tool-spec.json`). No ve rutas
    que llegan por parámetro ni las calculadas a más de un nivel: esa cobertura
    está declarada en la deuda `fronteras_de_escritura_por_contexto`, y el fallo
    es del lado de no marcar.
    """
    if props is None:
        props = _propiedades_de_sistema()[0]
    funciones: dict[str, str] = _funciones_importadas(arbol, externas or {})
    consts = _constantes_de_texto(arbol)
    nombres = _resolver_modulo(arbol, props, funciones)
    desechables = _nombres_desechables(arbol)
    hallazgos = []
    for nodo in _nodos(arbol):
        llamada = llamada_de_escritura(nodo)
        if not llamada:
            continue
        fn = nodo.func
        if llamada.startswith(_ESCRITURAS_POR_ARGUMENTO) or not isinstance(fn, ast.Attribute):
            objetivo = nodo.args[0] if nodo.args else None
        else:
            objetivo = fn.value
        if objetivo is None or _nombre_base(objetivo) in desechables:
            continue
        s = _subruta_de_sistema(objetivo, nombres, funciones, props, consts=consts)
        if s:
            hallazgos.append((nodo.lineno, llamada, s))
    return hallazgos


def escrituras_de_sistema() -> list[dict]:
    """Toda escritura con subruta decidible bajo `00_System/`, con su contexto.

    `"*"` —crear la carpeta— no se reporta: la crean seis contextos y no es de
    nadie en particular, es la raíz del sistema.
    """
    props = _propiedades_de_sistema()[0]
    externas = funciones_de_sistema_del_repo(props)
    dominio = _modulos_dominio()
    hallazgos = []
    for ruta in arboles_medidos():
        clave = clave_de_modulo(ruta)
        ctx = (dominio.get(clave) if clave.startswith("vault/")
               else contexto_de(Path(clave).stem))
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for linea, _llamada, s in escrituras_de_sistema_en(arbol, props, externas):
            if s != "*":
                hallazgos.append({"module": clave.removesuffix(".py"),
                                  "context": ctx or None, "path": s, "line": linea})
    return hallazgos


def escrituras_de_sistema_ajenas(escrituras: list[dict] | None = None) -> list[dict]:
    """Las escrituras de un contexto en una subruta que no es suya, o sin dueño."""
    duenos = duenos_de_sistema()
    if escrituras is None:
        escrituras = escrituras_de_sistema()
    return [
        {**e, "owner": duenos.get(e["path"])}
        for e in escrituras
        if duenos.get(e["path"]) != e["context"]
    ]


def _clave_escritura_de_sistema(e: dict) -> str:
    return f"{e['path']} <- {e['module']}"


#: Los tres puntos en los que el kernel llama HACIA el dominio, con su motivo.
#:
#: El kernel declara «no depender de ningún contexto de dominio» y sin embargo
#: cruza en tres sitios, todos por importación perezosa dentro de una función.
#: Estaban en la baseline genérica de cruces, anónimos y sin justificación: eso
#: es la misma forma que tenía la prohibición del Meta-toolkit antes de v40.0 —
#: una frontera declarada que ninguna medida distinguía de la deuda corriente.
#:
#: No se resuelven invirtiendo la dependencia, y el motivo es el mismo en los
#: tres: son **ganchos del write path**, y quien los invoca es el kernel porque
#: el kernel es el único sitio por el que pasan TODAS las escrituras. Registrar
#: el gancho desde el dominio exigiría que alguien importara ese contexto antes
#: de la primera escritura; el día que nadie lo hiciera, el escaneo de secretos
#: dejaría de correr **en silencio**. Cambiar un cruce declarado por un fallo
#: silencioso de seguridad es un mal negocio (AP-37).
#:
#: Lo que sí se exige: que estén enumerados aquí y que cada uno diga por qué.
#: Uno sin declarar rompe la puerta.
GANCHOS_DEL_KERNEL: dict[tuple[str, str], str] = {
    ("vault_fs", "vault_secret_scan"): (
        "Preflight anti-secretos del write path, en `vault_fs.guarda_secretos`. "
        "Tiene que correr en el único punto por el que pasan todas las "
        "escrituras, o no protege. v40.17: se mudó con el mecanismo desde "
        "`vault_io`; el gancho es el mismo y sigue siendo perezoso."
    ),
    ("vault_io", "vault_section_index"): (
        "`_auto_section_index`: el índice de sección se regenera tras escribir "
        "una nota, sin que cada tool tenga que acordarse (AP-47)."
    ),
    ("vault_io", "vault_tags"): (
        "`_auto_tag_ledger`: AP-39 exige registrar el término nuevo, y hasta "
        "v40.0 lo hacía un solo escritor de quince. Cablearlo en los catorce "
        "`*_save` cruzaría Autoría → Índices catorce veces y seguiría sin "
        "cubrir al decimoquinto (AP-43)."
    ),
    ("vault_io", "vault/grafo"): (
        "`_auto_grafo`: la nota escrita entra en `graph.json` en la misma "
        "escritura, escriba quien escriba (AP-47); antes `vault_subgraph` no "
        "la veía hasta la siguiente reconstrucción. Va al dominio y no a "
        "`vault_graph` porque `vault_graph` importa `vault_io` y el gancho "
        "estrenaría un ciclo (AP-58); el escaneo de `vault_lib` se inyecta."
    ),
    ("vault_vocabulario", "vault_norms_catalog"): (
        "`status` y los estados de dominio ya tienen registro canónico en "
        "Gobernanza. El registro de vocabularios los declara con `derivado_de` "
        "y los pide al llamarse: copiarlos aquí sería exactamente el AP-05 que "
        "este módulo existe para cerrar. La alternativa —mudarlo a Gobernanza— "
        "no elimina el cruce, lo mueve: lo leen Autoría, Consulta y Grafo, y "
        "Consulta → Gobernanza no está en el presupuesto de cruces. Se declara "
        "el cruce en vez de disimularlo."
    ),
    ("vault_vocabulario", "vault_fundamentals"): (
        "Los tres campos CIA salen de `CIA_TRIAD` por `cia_valores()`. Import "
        "perezoso y de solo lectura: ninguna decisión viaja de vuelta."
    ),
}

#: El presupuesto de cada gancho (v40.24). `GANCHOS_DEL_KERNEL` dice **por qué**
#: existe la vía de escape; esto dice **hasta cuándo** y **quién lo revisa**.
#:
#: Va en un registro aparte y no como valor de aquel a propósito: el motivo en
#: prosa es lo que consumen tres tests y el plano, y meterlo dentro de un dict
#: los habría roto a todos para colar un campo. Las claves de los dos registros
#: tienen que coincidir exactamente, y una puerta lo comprueba — dos registros
#: con la misma clave que divergen serían AP-05 en el sitio donde se declara la
#: excepción arquitectónica.
#:
#: Hasta v40.23 esto no existía y el hallazgo `gancho_sin_presupuesto` de
#: `vault_kernel` era informativo, con el motivo escrito: la vía de escape solo
#: podía crecer porque nada medía su pendiente. Un hallazgo que no se puede
#: saldar y bloquea la puerta solo enseña a ampliar baselines.
#:
#: `objetivo` tiene dos valores y significan cosas distintas:
#:   - `permanente` — es una decisión de arquitectura, no una deuda. Se revisa
#:     cada `cadencia_dias` para comprobar que el motivo **sigue siendo cierto**,
#:     no para eliminarlo.
#:   - `a_eliminar` — es deuda con fecha: exige `fecha_limite`.
#: Un gancho nuevo sin entrada aquí **bloquea**, y eso es todo lo que la puerta
#: exige. Que la fecha de revisión haya vencido se publica como informativo y no
#: rompe la puerta: un guard que se pone rojo por el paso del calendario falla
#: en un repo que nadie tocó, y el primer arreglo que enseña es mover la fecha.
PRESUPUESTO_DE_GANCHOS: dict[tuple[str, str], dict] = {
    ("vault_fs", "vault_secret_scan"): {
        "objetivo": "permanente",
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "dueno": "kernel",
        "por_que": (
            "Quitarlo desactivaría el preflight anti-secretos en silencio. La "
            "revisión comprueba que sigue habiendo un único punto de escritura, "
            "no si se puede eliminar."
        ),
    },
    ("vault_io", "vault_section_index"): {
        "objetivo": "permanente",
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "dueno": "kernel",
        "por_que": (
            "Regenerar el índice desde cada tool es AP-47 repetido quince "
            "veces. La revisión mira si el índice pasó a derivarse bajo demanda."
        ),
    },
    ("vault_io", "vault_tags"): {
        "objetivo": "permanente",
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "dueno": "kernel",
        "por_que": (
            "AP-39 exige registrar el término nuevo en el write path. La "
            "revisión mira si el ledger pasó a construirse por barrido."
        ),
    },
    ("vault_io", "vault/grafo"): {
        "objetivo": "permanente",
        "revisado": "2026-10-02",
        "cadencia_dias": 180,
        "dueno": "kernel",
        "por_que": (
            "Refrescar el grafo desde cada tool es AP-47 repetido en cada "
            "escritor. La revisión mira si el grafo pasó a derivarse bajo demanda."
        ),
    },
    ("vault_vocabulario", "vault_norms_catalog"): {
        "objetivo": "permanente",
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "dueno": "gobernanza",
        "por_que": (
            "Copiar el vocabulario aquí sería el AP-05 que el módulo existe "
            "para cerrar, y mudarlo a Gobernanza mueve el cruce sin quitarlo."
        ),
    },
    ("vault_vocabulario", "vault_fundamentals"): {
        "objetivo": "permanente",
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "dueno": "gobernanza",
        "por_que": (
            "Solo lectura de `CIA_TRIAD`: ninguna decisión viaja de vuelta."
        ),
    },
}


#: El presupuesto de cada **par de contextos** (v40.27). `arch-baseline.json` ya
#: impide que la deuda crezca; esto le pone **dirección**, que es lo que faltaba.
#:
#: El síntoma que lo motiva está medido: los cruces subieron de 48 a 62 en
#: veintiséis versiones sin que ninguna puerta se pusiera roja. Cada cruce nuevo
#: era individualmente razonable y el único trámite era `--freeze`, una acción
#: mecánica que nadie lee. Veinte de esos sesenta y dos resultaron ser tools
#: leyendo una tabla constante: llevaban versiones contadas como fronteras de
#: negocio porque nadie tuvo que responder nunca *si aquello era una frontera*.
#:
#: Por eso la unidad es el **par**, no el sitio. «Autoría depende de Gobernanza»
#: es una decisión de arquitectura que se toma una vez; que la ejerzan dos
#: módulos o quince es consecuencia, no decisión. Un sitio nuevo dentro de un par
#: ya presupuestado lo sigue frenando la baseline; un **par nuevo** exige una
#: entrada aquí, y escribirla obliga a contestar la pregunta que faltaba.
#:
#: `objetivo` toma tres valores:
#:   - `permanente` — es arquitectura. Se revisa para comprobar que el motivo
#:     **sigue siendo cierto**, no para eliminarlo.
#:   - `a_eliminar`  — es deuda con fecha: exige `fecha_limite`.
#:   - `en_estudio`  — hay una hipótesis escrita de por qué podría no ser un
#:     cruce, y no está verificada. Es un estado honesto y acotado, no un cajón:
#:     `hipotesis` es obligatoria, y decir «no lo sé» con la sospecha escrita es
#:     lo que hizo falta para encontrar el catálogo de normas.
#:
#: Igual que en `PRESUPUESTO_DE_GANCHOS`, la fecha vencida es **informativa**: un
#: guard que se pone rojo por el paso del calendario falla en un repo que nadie
#: tocó, y lo primero que enseña es a mover la fecha.
PRESUPUESTO_DE_CRUCES: dict[tuple[str, str], dict] = {}


def _cruce(origen, destino, objetivo, dueno, por_que, **extra):
    """Alta de una entrada del presupuesto, para que la tabla se lea."""
    entrada = {
        "objetivo": objetivo,
        "dueno": dueno,
        "revisado": "2026-08-14",
        "cadencia_dias": 180,
        "por_que": por_que,
    }
    entrada.update(extra)
    PRESUPUESTO_DE_CRUCES[(origen, destino)] = entrada


# --- Hacia Índices: el patrón sistémico, y el candidato a repetir v40.27 ------
#
# Once de los cuarenta y cuatro sitios apuntan a `indices`, y siempre por lo
# mismo: quien escribe una nota tiene que reindexarla. Eso no se parece a una
# dependencia de negocio, se parece a infraestructura — la misma forma que tenía
# `vault_norms_catalog` antes de medirla. La hipótesis está escrita y sin
# verificar a propósito: `vault_tags` lleva el ledger de AP-39 y `vault_reindex`
# escribe, así que fan-out cero no lo tienen, y mudarlos al núcleo sin comprobar
# eso sería bajar la cifra en vez de arreglar la estructura.
_HIP_INDICES = (
    "Once cruces piden lo mismo: reindexar tras escribir. Si `indices` resulta "
    "ser infraestructura y no un contexto de negocio, los once dejan de ser "
    "cruces igual que los veinte del catálogo de normas. Sin verificar: "
    "`vault_tags` y `vault_reindex` escriben, así que no tienen la forma de hoja "
    "que tenía el catálogo y el movimiento no es el mismo."
)
for _o in ("ciclo_de_vida", "autoria", "gobernanza"):
    _cruce(_o, "indices", "en_estudio", "indices",
           "Reindexado tras escritura.", hipotesis=_HIP_INDICES)

# --- Los adaptadores de DI: cablear es su oficio -----------------------------
#
# Nueve sitios son `vault/<contexto>/repositorio.py`. Un adaptador que cablea el
# dominio de otro contexto **tiene** que cruzar: es lo que lo hace un adaptador.
# Se declaran permanentes y se siguen contando, que es lo correcto: dejar de
# contarlos convertiría la capa de DI en un punto ciego, y esconder cableado es
# exactamente como se coló AP-48.
for _par in (("autoria", "grafo"), ("consulta", "ciclo_de_vida"),
             ("grafo", "gobernanza"), ("indices", "grafo")):
    _cruce(*_par, "permanente", "arquitectura",
           "Adaptador de DI: cablear el dominio de otro contexto es su oficio. "
           "Se cuenta igual — no contarlo dejaría la capa de DI ciega.")

# `vault_errors` es el único borde que ve todos los envelopes. Consume el
# puerto de presentación de Autoría, no la tool meta que audita su cobertura.
_cruce("kernel", "autoria", "permanente", "kernel",
       "El inyector común de envelopes llama al puerto `hablar` para que el "
       "recordatorio llegue a todas las tools. El servicio degrada a silencio "
       "si falla y no importa la fachada meta `vault_voice`.")

# --- Gobernanza mirando el vault, y el meta-toolkit mirando Gobernanza -------
_cruce("meta_toolkit", "gobernanza", "permanente", "meta_toolkit",
       "El meta-toolkit audita que este repo cumple lo que publica, y para eso "
       "tiene que leer las normas y el audit. Es la dirección correcta: quien "
       "verifica depende de lo verificado, nunca al revés.")
_cruce("ciclo_de_vida", "gobernanza", "permanente", "ciclo_de_vida",
       "Sanación y onboarding aplican las normas al vault del usuario. Sin este "
       "cruce las doce fases tendrían que reimplementar el criterio, que es "
       "AP-57.")
_cruce("gobernanza", "meta_toolkit", "a_eliminar", "gobernanza",
       "La FACHADA de mantenimiento (`vault_norms`) compone los controles del "
       "estándar (AP-40/42/43) importando `vault_mcp_catalog` y `vault_smoke`. "
       "El sitio del cruce se movió desde `vault_norms_engine` (commit 667a6a5, "
       "inversión TD-0003) para que el motor empaquetado no importe módulos que "
       "no viajan en la wheel; el adeudado es el MISMO y sigue vigente: lo que "
       "elimina es que el motor de normas sea quien pide el audit del catálogo. "
       "PENDIENTE DE RATIFICACIÓN DEL PROPIETARIO: (A) eliminar el cruce "
       "componiendo desde el meta-toolkit; (B) migrarlo a un owner con puerto "
       "declarado; (C) excepción formal con plazo y riesgo. Ver "
       "audits/architecture/QA-RC-03-CRUZES.md y las fichas DIV-01..DIV-10.",
       fecha_limite="2027-06-30")
# CERRADO en R22 (DEC-02, ruta B — puerto de controles). El par
# `gobernanza -> autoria` existia solo porque `vault_norms` importaba
# `vault_voice` para ejecutar AP-43. El puerto `vault.kernel.controles` lanza
# la superficie del dueno como proceso y la arista desaparecio del grafo
# (off_port 5 -> 0). La entrada se RETIRA de `PRESUPUESTO_DE_CRUCES` porque
# `presupuesto_de_cruces_huerfano()` y `test_arquitectura` exigen que un par
# resuelto no siga explicando una frontera que ya no existe; el registro de la
# decision queda en `audits/architecture/PLAN-B-MIGRACION-CRUZES.md` (R22) y
# en `audits/handoff/RESPUESTA-DEL-EJECUTOR.md`.

_cruce("autoria", "gobernanza", "permanente", "autoria",
       "Validar mermaid al escribir y registrar el cambio: la escritura no puede "
       "publicar una nota que el propio estándar rechazaría.")
_cruce("grafo", "gobernanza", "permanente", "grafo",
       "Adaptador del contexto Grafo hacia el dominio de Gobernanza.")

# --- El resto: cruces sueltos, uno por par -----------------------------------
_cruce("meta_toolkit", "ciclo_de_vida", "permanente", "meta_toolkit",
       "El checker del changelog necesita el camino de versión que define "
       "`vault_standard_upgrade`. Duplicarlo sería AP-05 sobre el número de "
       "versión, que es el dato más copiado del repo.")
_cruce("ciclo_de_vida", "meta_toolkit", "en_estudio", "ciclo_de_vida",
       "`vault_standard_upgrade` -> `vault_mcp_catalog` para sincronizar el "
       "catálogo al subir de versión.",
       hipotesis="Puede que la sincronización la deba disparar la puerta del "
                 "meta-toolkit y no el propio upgrade. Sin verificar.")
_cruce("autoria", "meta_toolkit", "en_estudio", "autoria",
       "`vault_voice` -> `vault_mcp_catalog`: la voz consulta el catálogo.",
       hipotesis="Mismo olor que `gobernanza -> meta_toolkit`: el catálogo lo "
                 "debería inyectar quien construye la voz. Sin verificar.")
_cruce("ciclo_de_vida", "autoria", "permanente", "ciclo_de_vida",
       "Onboarding puebla el vault escribiendo notas: pasa por el write path "
       "único (AP-46) en vez de escribir por su cuenta.")
_cruce("ciclo_de_vida", "grafo", "permanente", "ciclo_de_vida",
       "Propagar un cambio exige saber a qué alcanza, y el alcance lo mide el "
       "grafo. Reimplementarlo aquí sería AP-57.")
_cruce("grafo", "autoria", "permanente", "grafo",
       "Etiquetar código escribe la nota por el write path único (AP-46).")
_cruce("consulta", "autoria", "permanente", "consulta",
       "El paquete de contexto busca notas: la búsqueda tiene dueño en Autoría.")
_cruce("consulta", "grafo", "permanente", "consulta",
       "El subgrafo lee el grafo. Es el caso legítimo que el docstring de "
       "`cruces()` ya nombra.")
_cruce("meta_toolkit", "consulta", "permanente", "meta_toolkit",
       "El servidor MCP expone las tools de consulta: exponer es su oficio.")
_cruce("cli", "meta_toolkit", "permanente", "cli",
       "`cli/registry.py` lee `TOOLS_CATALOG` y `NATIVE_JS_TOOLS` para saber "
       "qué tools existen y cuáles viven en el `.mjs`. Un registro de comandos "
       "que no consulta el catálogo tendría que declarar las tools por su "
       "cuenta, que es AP-05 sobre el dato más derivado del repo. Permanente y "
       "por puerto: los dos símbolos están declarados en `meta_toolkit`. "
       "Aparece en v40.30 no porque el cruce sea nuevo —lleva ahí desde que "
       "existe la CLI— sino porque hasta ahora no había contexto `cli` que lo "
       "hiciera contable.")


def pares_sin_presupuesto() -> list[dict]:
    """Todo par de contextos que cruza sin haber declarado su dirección.

    Es la mitad que a `arch-baseline.json` le faltaba. La baseline contesta
    «¿cuánta deuda hay?» y se niega a crecer; esto contesta **«¿hacia dónde
    va?»**, que es la pregunta que nadie tuvo que responder mientras los cruces
    subían de 48 a 62.

    Bloquea a propósito. Un par nuevo es una decisión de arquitectura, y el coste
    de declararla —una entrada con dueño y motivo— es justo el trámite que hace
    falta para que alguien se pregunte si el cruce debería existir. Sin él, el
    único trámite era `--freeze`, que se teclea sin leer.
    """
    fuera = []
    for par in sorted({(c["from_context"], c["to_context"]) for c in cruces()}):
        if par in PRESUPUESTO_DE_CRUCES:
            continue
        fuera.append({
            "from_context": par[0], "to_context": par[1],
            "why": (
                "Par de contextos sin entrada en PRESUPUESTO_DE_CRUCES. Declara "
                "si depender así es arquitectura (`permanente`), deuda con fecha "
                "(`a_eliminar` + `fecha_limite`) o una sospecha por verificar "
                "(`en_estudio` + `hipotesis`)."
            ),
        })
    return fuera


def presupuesto_de_cruces_huerfano() -> list[dict]:
    """Entradas del presupuesto para pares que ya no cruzan.

    No es un error: es lo que pasa cuando un par se resuelve, y verlo es el
    punto. Se reporta como informativo para que la entrada se retire a
    conciencia —con la versión que la cerró— en vez de quedarse ahí explicando
    una frontera que ya no existe.
    """
    vivos = {(c["from_context"], c["to_context"]) for c in cruces()}
    return [
        {"from_context": a, "to_context": b, "objetivo": v["objetivo"]}
        for (a, b), v in sorted(PRESUPUESTO_DE_CRUCES.items())
        if (a, b) not in vivos
    ]


def dependencias_del_kernel() -> list[dict]:
    """El kernel llamando al dominio: solo las que no están declaradas.

    La frontera del kernel («nadie más puede ser dependencia de todos») era
    prosa en `CONTEXTS[KERNEL]["prohibe"]`. Aquí se mide.
    """
    mapa = _mapa_modulos()
    sin_declarar = []
    for nombre in sorted(CONTEXTS[KERNEL]["modulos"]):
        fichero = SCRIPTS_DIR / f"{nombre}.py"
        if not fichero.exists():
            continue
        # Deuda #12: el código de una hoja migrada es el del dueño (AP-44). Con
        # el alias, toda hoja del kernel ya en `vault/kernel/` salía sin
        # dependencias, y un import al dominio desde ella no rompía nada.
        for destino in sorted(_importaciones(vault_grafo_import.codigo_de(fichero))):
            ctx = mapa.get(destino)
            if ctx is None or ctx == KERNEL:
                continue
            if (nombre, destino) in GANCHOS_DEL_KERNEL:
                continue
            sin_declarar.append({
                "from": nombre, "to": destino, "to_context": ctx,
            })
    return sin_declarar


def escrituras_sin_lock(rutas: list[Path] | None = None) -> list[dict]:
    """AP-54 — el lock falla y se escribe igual.

    El patrón es siempre el mismo y se lee de un vistazo::

        try:
            with file_lock(f, timeout=5):
                escribir(f, atomico=True)
        except TimeoutError:
            escribir(f, atomico=False)   # <- aquí

    Quien escribe en el handler ha razonado que perder el dato es peor que
    escribirlo sin sincronizar. Es al revés: el `TimeoutError` significa que
    **otro lo tiene tomado ahora mismo**, así que esa escritura entra
    justo encima de la suya. No es una carrera improbable, es la única
    situación en la que ese código se ejecuta.

    Lo destapó `vault_sdd_init`, que se pasaba del timeout de 60 s de la tool.
    La lentitud era el síntoma visible —26 tomas del lock del fichero de trazas,
    13 fallidas, 65 s de espera— pero el fallo era que esas 13 acababan
    reescribiendo el trace sin lock. La causa de las esperas, la reentrancia
    del mismo hilo, se corrigió en `vault_io.file_lock`; esta norma vigila la
    reacción, que es la parte que se repite.

    El detector NO marca omitir la escritura (`pass`, `return`, un log): eso es
    la respuesta correcta y `vault_quality_check` ya la tenía.
    """
    hallazgos: list[dict] = []
    for ruta in (rutas if rutas is not None
                 else [vault_grafo_import.codigo_de(SCRIPTS_DIR / f"{m}.py")
                       for m in _modulos_en_disco()]):
        mod = vault_grafo_import.nombre_de(ruta)
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for nodo in _nodos(arbol):
            if not isinstance(nodo, ast.Try):
                continue
            # ¿El bloque protegido toma un file_lock?
            if not any(
                isinstance(c, ast.Call)
                and (c.func.attr if isinstance(c.func, ast.Attribute)
                     else getattr(c.func, "id", None)) == "file_lock"
                for stmt in nodo.body for c in ast.walk(stmt)
            ):
                continue
            for handler in nodo.handlers:
                if not _captura_timeout(handler):
                    continue
                for stmt in handler.body:
                    for c in ast.walk(stmt):
                        nombre = llamada_de_escritura(c)
                        if nombre:
                            hallazgos.append({
                                "module": mod,
                                "line": c.lineno,
                                "call": nombre,
                            })
    return hallazgos


def _captura_timeout(handler: ast.ExceptHandler) -> bool:
    """`except TimeoutError`, sola o dentro de una tupla. `except:` pelado cuenta."""
    t = handler.type
    if t is None:
        return True
    candidatos = t.elts if isinstance(t, ast.Tuple) else [t]
    for c in candidatos:
        nombre = c.attr if isinstance(c, ast.Attribute) else getattr(c, "id", None)
        if nombre in ("TimeoutError", "OSError", "Exception", "BaseException"):
            return True
    return False


def escrituras_prohibidas() -> list[dict]:
    """La frontera del Meta-toolkit, convertida en medida.

    Hasta v40.0 `prohibe` era prosa que ningún guard leía — el único contexto
    cuya frontera es una prohibición era también el único sin enforcement. Se
    busca por AST una llamada de escritura en cuyo árbol de argumentos aparezca
    el literal de una sección de contenido. Que sea por AST y no por texto
    importa: `vault_doc_counts` y este mismo módulo *nombran* secciones en
    docstrings y en mensajes sin escribir en ellas, y un grep las delataría
    todas en falso.
    """
    secciones = _secciones_de_contenido()
    hallazgos: list[dict] = []
    for mod in CONTEXTS["meta_toolkit"]["modulos"]:
        ruta = SCRIPTS_DIR / f"{mod}.py"
        if not ruta.exists():
            continue
        arbol = _ast_de(ruta)
        desechables = _nombres_desechables(arbol)
        for nodo in _nodos(arbol):
            nombre = llamada_de_escritura(nodo)
            if not nombre:
                continue
            fn = nodo.func
            objetivo = fn.value if isinstance(fn, ast.Attribute) else (
                nodo.args[0] if nodo.args else None)
            if _nombre_base(objetivo) in desechables:
                continue
            for hijo in ast.walk(nodo):
                if (isinstance(hijo, ast.Constant)
                        and isinstance(hijo.value, str)
                        and hijo.value in secciones):
                    hallazgos.append({
                        "module": mod,
                        "line": nodo.lineno,
                        "call": nombre,
                        "section": hijo.value,
                    })
                    break
    return hallazgos


def fantasmas() -> list[str]:
    """Módulos declarados en un contexto que ya no están en disco.

    Mira los tres árboles que pueden alojar un módulo declarado, no solo
    `scripts/`. Al declarar el contexto `cli` en v40.30 esta función dio por
    ausentes sus siete ficheros —existían todos— porque solo sabía globear
    `scripts/vault_*.py`: la misma forma del defecto que la tanda arregla, que
    es medir con un alcance más estrecho que el declarado.
    """
    en_disco = set(_modulos_en_disco()) | set(_modulos_cli())
    en_disco |= {k.rsplit("/", 1)[-1][:-3] for k in _modulos_dominio()}
    return sorted(m for m in _mapa_modulos() if m not in en_disco)


def _ruta_de_modulo(modulo: str) -> Path:
    """Ruta de un módulo publicado, ya sea script o paquete de dominio.

    Un script migrado es un alias en `sys.modules` (deuda #12): importarlo da el
    dueño de `vault/<ctx>/`, así que es el dueño lo que se lee. Leer el fichero
    del alias —que no define nada— daba por roto un puerto que sí existe.
    """
    if modulo.startswith("vault/"):
        return REPO_ROOT / f"{modulo}.py"
    return vault_grafo_import.fuente_de(modulo)


def _es_modulo_del_contexto(modulo: str, contexto: str) -> bool:
    """El destino publicado pertenece de verdad al contexto que lo anuncia."""
    if modulo in CONTEXTS[contexto]["modulos"]:
        return True
    if not modulo.startswith("vault/"):
        return False
    return _modulos_dominio().get(f"{modulo}.py") == contexto


def _simbolos_de_nivel_superior(modulo: str) -> set[str] | None:
    """Los nombres que `modulo` define en su nivel superior, por AST.

    Por AST y no por import: importar los 112 módulos para comprobar una
    frontera los ejecutaría a todos, y varios resuelven el vault al importarse.
    Un guard que necesita un vault montado para decir si una frontera existe no
    es un guard, es otra dependencia.
    """
    ruta = _ruta_de_modulo(modulo)
    if not ruta.exists():
        return None
    try:
        arbol = _ast_de(ruta)
    except SyntaxError:
        return None
    nombres: set[str] = set()
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.add(nodo.name)
        elif isinstance(nodo, ast.Assign):
            nombres.update(
                t.id for t in nodo.targets if isinstance(t, ast.Name)
            )
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.target, ast.Name):
            nombres.add(nodo.target.id)
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            nombres.update(a.asname or a.name.split(".")[0] for a in nodo.names)
    # PEP 562: un módulo puede publicar un símbolo perezosamente. Lo hace
    # `vault_compact_contracts` con `GROUPS` desde que dejó de fijarlo al
    # importarse, y ese puerto seguiría existiendo aunque el AST no lo vea.
    if "__getattr__" in nombres:
        nombres.add("*")
    return nombres


def puertos_rotos() -> list[dict]:
    """Puertos declarados cuyo `modulo:simbolo` no existe.

    Es la puerta que faltaba: `puertos` se imprimía en el blueprint y nadie
    comprobaba nada, así que 22 de los 30 nombrados no existían en ningún
    módulo. Sin baseline y en duro — la deuda se saldó al declararla, atando
    cada nombre ubicuo a su implementación, y una lista de excepciones vacía
    solo invita a estrenarla.
    """
    rotos: list[dict] = []
    for ctx, datos in CONTEXTS.items():
        for puerto, destino in datos["puertos"].items():
            modulo, _, simbolo = destino.partition(":")
            if not simbolo:
                rotos.append(
                    {"context": ctx, "port": puerto, "target": destino,
                     "reason": "el destino no tiene la forma modulo:simbolo"}
                )
                continue
            if simbolo.startswith("_"):
                # El motivo que faltaba, y el que hace honesta a la baseline de
                # `off_port`. Declarar un puerto encoge esa deuda sin tocar una
                # línea de dominio, así que sin esta comprobación bastaba con
                # escribir `vault_norms:_NORM_BY_CODE` aquí para que un cruce
                # por detrás dejara de reportarse. La medida se relajaría y el
                # número diría que mejoró: la tool certificándose a sí misma,
                # que es AP-44 aplicado al propio guard.
                #
                # Un nombre privado es, por definición, lo contrario de una
                # superficie publicada. Si otro contexto lo necesita, se
                # promueve a público — que es trabajo real — o no entra.
                rotos.append(
                    {"context": ctx, "port": puerto, "target": destino,
                     "reason": f"`{simbolo}` es privado: un puerto no puede "
                               f"nombrar un símbolo que empieza por `_`"}
                )
                continue
            if not _es_modulo_del_contexto(modulo, ctx):
                rotos.append(
                    {"context": ctx, "port": puerto, "target": destino,
                     "reason": f"`{modulo}` no es un módulo de `{ctx}`"}
                )
                continue
            simbolos = _simbolos_de_nivel_superior(modulo)
            if simbolos is None:
                rotos.append(
                    {"context": ctx, "port": puerto, "target": destino,
                     "reason": f"`{modulo}.py` no se pudo leer"}
                )
            elif simbolo not in simbolos and "*" not in simbolos:
                rotos.append(
                    {"context": ctx, "port": puerto, "target": destino,
                     "reason": f"`{modulo}` no define `{simbolo}`"}
                )
    return rotos


def _superficie_publica(contexto: str) -> set[str]:
    """Los símbolos por los que se puede entrar a `contexto`.

    El nombre ubicuo del puerto y el símbolo al que apunta valen los dos: quien
    importa escribe el segundo, y el primero existe para hablar del borde.
    """
    puertos = CONTEXTS[contexto]["puertos"]
    return set(puertos) | {d.partition(":")[2] for d in puertos.values()}


def cruces_fuera_de_puerto() -> list[dict]:
    """Imports entre contextos que no entran por la superficie publicada.

    El grafo de `cruces()` dice *qué módulo* depende de qué contexto; esto dice
    *por dónde*. Un contexto con tres puertos declarados y veintidós símbolos
    importados desde fuera no tiene tres puertos: tiene veintidós, y tres de
    ellos escritos en el registro.

    **El kernel queda fuera a propósito.** Es shared kernel, no un contexto
    acotado: existe precisamente para que cualquiera dependa de él, y sus
    cuatro `puertos` nombran el write path, no un permiso de acceso. Meterlo
    aquí convertiría 343 de los 392 hallazgos en ruido y enterraría los 49 que
    sí son fronteras cruzadas por detrás.

    **Las dos formas de entrar, no solo una.** Hasta v40.8 esto filtraba por
    `ast.ImportFrom` y nada más, así que `import vault_norms` seguido de
    `vault_norms._NORM_BY_CODE` era invisible: el símbolo no está en el nodo de
    import, hay que buscar los accesos `X.attr` por el árbol. El cero que
    publicaba la puerta era un cero sobre un subconjunto sintáctico, y el test
    que escribí para los símbolos privados pasaba porque el detector no podía
    ver lo que lo habría falsificado — AP-44 cometido por el propio guard.
    """
    mapa = _mapa_modulos()
    fuera: list[dict] = []
    for ruta in arboles_medidos():
        # Deuda #12: el dueño migrado responde por el nombre de su alias, que es
        # el que está en el mapa y en la baseline; por `ruta.stem` no estaba en
        # ninguno y sus cruces dejaban de medirse (AP-44).
        nombre = alias_de_dueno(ruta) or ruta.stem
        origen = mapa.get(nombre)
        if origen is None:
            continue
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue

        def _anotar(modulo: str, simbolo: str, nombre: str = nombre) -> None:
            destino = mapa.get(modulo.split(".")[0])
            if destino is None or destino == origen or destino == KERNEL:
                return
            if simbolo in _superficie_publica(destino):
                return
            fuera.append(
                {
                    "module": nombre,
                    "from_context": origen,
                    "to_context": destino,
                    "symbol": f"{modulo}.{simbolo}",
                }
            )

        # `from vault_x import y` — el símbolo está en el nodo.
        for nodo in _nodos(arbol):
            if isinstance(nodo, ast.ImportFrom):
                if nodo.module and nodo.module.startswith("vault_"):
                    for alias in nodo.names:
                        _anotar(nodo.module, alias.name)

        # `import vault_x [as vx]` — el símbolo no está en el nodo. Se ata el
        # nombre local al módulo y se buscan los accesos `vx.attr`. Sin esto la
        # forma más común de import queda sin medir.
        ligados: dict[str, str] = {}
        for nodo in _nodos(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    if alias.name.startswith("vault_"):
                        ligados[alias.asname or alias.name] = alias.name
        if ligados:
            for nodo in _nodos(arbol):
                if (
                    isinstance(nodo, ast.Attribute)
                    and isinstance(nodo.value, ast.Name)
                    and nodo.value.id in ligados
                ):
                    _anotar(ligados[nodo.value.id], nodo.attr)
    return fuera


#: Módulos a los que la regla de configuración no aplica. `vault_test_runner`
#: hace `os.environ.copy()` para *pasar* el entorno a un subproceso, que no es
#: leer configuración; `vault_smoke` hace lo mismo. Se enumera en vez de
#: detectarse por heurística porque una lista corta y explícita es auditable y
#: una heurística no.
_COPIAS_DE_ENTORNO_LEGITIMAS = frozenset({"vault_test_runner", "vault_smoke"})


def _cuantas_variables_declaradas() -> int:
    from vault_entorno import VARIABLES

    return len(VARIABLES)


def lecturas_de_entorno_sin_registro() -> list[dict]:
    """`os.environ[...]` con un nombre que `vault_entorno.py` no declara.

    Catorce variables se leían en once módulos, cada una con su default escrito
    en el punto de lectura y solo seis documentadas. AP-05 sobre configuración:
    el mismo dato —qué existe, de qué tipo, qué vale si falta— decidido en cada
    sitio. `VAULT_VOICE` ya divergía, comparándose contra `"verbose"` en un
    módulo y contra `"0"` con default `"1"` en otro.
    """
    from vault_entorno import VARIABLES

    hallazgos: list[dict] = []
    for ruta in arboles_medidos():
        if vault_grafo_import.nombre_de(ruta) in _COPIAS_DE_ENTORNO_LEGITIMAS:
            continue
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for nodo in _nodos(arbol):
            nombre = _nombre_de_variable_leida(nodo)
            if nombre is not None and nombre not in VARIABLES:
                hallazgos.append({"module": ruta.stem, "variable": nombre})
    return hallazgos


def _nombre_de_variable_leida(nodo: ast.AST) -> str | None:
    """El literal de `os.environ.get("X")` / `os.environ["X"]`, si lo hay."""
    if isinstance(nodo, ast.Call):
        f = nodo.func
        if (
            isinstance(f, ast.Attribute)
            and f.attr == "get"
            and isinstance(f.value, ast.Attribute)
            and f.value.attr == "environ"
            and nodo.args
            and isinstance(nodo.args[0], ast.Constant)
            and isinstance(nodo.args[0].value, str)
        ):
            return nodo.args[0].value
    if (
        isinstance(nodo, ast.Subscript)
        and isinstance(nodo.value, ast.Attribute)
        and nodo.value.attr == "environ"
        and isinstance(nodo.slice, ast.Constant)
        and isinstance(nodo.slice.value, str)
    ):
        return nodo.slice.value
    return None


#: El `.mjs` no puede importar el registro Python, así que se le deriva un
#: artefacto —igual que `tools-catalog.json`— y una puerta que falla si se
#: desfasa (AP-47). Antes declaraba sus cuatro variables por su cuenta, y
#: una de ellas ya divergía del registro en tipo y en default.
TABLA_ENTORNO_MJS = REPO_ROOT / "mcp" / "nodejs" / "env-table.json"


def tabla_de_entorno_derivada() -> dict:
    from vault_entorno import tabla

    return {
        "_comment": (
            "Derivado de scripts/vault_entorno.py. No se edita a mano: "
            "regenera con `python scripts/vault_arch.py --sync-env`."
        ),
        "variables": tabla(),
    }


def tabla_de_entorno_desfasada() -> bool:
    """`True` si el JSON del servidor ya no dice lo que dice el registro."""
    if not TABLA_ENTORNO_MJS.exists():
        return True
    try:
        actual = json.loads(TABLA_ENTORNO_MJS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    return actual != tabla_de_entorno_derivada()


_VOCABULARIO_PROPIETARIO = "vault_vocabulario"


def _vocabularios_declarados() -> dict:
    """Import perezoso, igual que el del entorno: el registro no se ata aquí."""
    from vault_vocabulario import VOCABULARIOS

    return VOCABULARIOS


def vocabularios_sin_dueno() -> list[dict]:
    """Un vocabulario cuyo contexto dueño no existe en `CONTEXTS`.

    Es la mitad del valor del registro: sin dueño, "quién manda sobre estos
    valores" vuelve a ser una pregunta sin respuesta y cada punto de uso la
    contesta por su cuenta.
    """
    from vault_vocabulario import VOCABULARIOS

    return [
        {"vocabulary": nombre, "context": voc.contexto}
        for nombre, voc in sorted(VOCABULARIOS.items())
        if voc.contexto not in CONTEXTS
    ]


def _literales_de_cadena(nodo: ast.AST) -> tuple[str, ...] | None:
    """Los elementos de una lista/tupla/set de cadenas literales, si lo es.

    **Las claves de un diccionario cuentan igual.** El detector solo miraba
    secuencias y por eso daba cero mientras quedaban tres copias vivas, las
    tres escritas como mapa: `CIA_WEIGHT = {"critical": 1.0, ...}` en
    `vault_context_pack`, `orden = {"critical": 0, ...}` en `vault_voice` y
    las descripciones por severidad de `vault_ncr_save`. Son la misma decisión
    copiada —qué valores existen y cuáles no— con un valor colgando de cada
    una; que el literal esté a la izquierda de los dos puntos no la cambia.

    Es el mismo defecto que el detector viene a impedir, cometido por el
    detector: se midió con la forma que se esperaba en vez de con la que hay
    (AP-44). Un guard que da cero porque no sabe mirar es peor que no tenerlo,
    porque el cero se lee como que no queda deuda.
    """
    if isinstance(nodo, ast.Dict):
        claves = [
            k.value for k in nodo.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        # Solo si **todas** las claves son cadenas literales: un mapa con
        # claves calculadas no es una lista de valores escrita a mano.
        if claves and len(claves) == len(nodo.keys):
            return tuple(claves)
        return None
    if not isinstance(nodo, (ast.List, ast.Tuple, ast.Set)):
        return None
    valores = []
    for e in nodo.elts:
        if not (isinstance(e, ast.Constant) and isinstance(e.value, str)):
            return None
        valores.append(e.value)
    return tuple(valores) if valores else None


def _nombre_llamado(func: ast.AST) -> str:
    """El nombre de lo que se llama, sea `mapa(...)` o `voc.mapa(...)`."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def copias_de_vocabulario() -> list[dict]:
    """AP-50: una lista literal que reproduce un vocabulario que el registro declara.

    Este es uno de los tres detectores de AP-50 —con
    `lecturas_de_entorno_sin_registro()` y `vocabularios_sin_dueno()`—, y a la
    vez su guard: `--check --strict` falla, así que la decisión duplicada no
    llega a merge. De ahí que AP-50 sea `guard+audit` con `vault_arch` en los
    dos campos.

    `critical | high | medium | low` estaba escrito a mano en catorce ficheros:
    cuatro `choices=` de argparse y diez constantes de módulo. Coincidían todas
    el día que se midió; la que se quede atrás cuando el registro cambie
    rechazará un valor válido o aceptará uno inventado, y ningún test lo notará.

    Se compara **como conjunto**: `("low", "high", ...)` en otro orden es la
    misma decisión copiada. Los módulos que son fuente —el registro y aquellos
    de los que deriva— quedan fuera: ahí el literal es la declaración.
    """
    from vault_vocabulario import VOCABULARIOS, valores as _valores

    # AP-50: la misma decisión escrita fuera de su dueño.
    por_conjunto: dict[frozenset, str] = {}
    fuentes = {_VOCABULARIO_PROPIETARIO}
    for nombre in VOCABULARIOS:
        origen = VOCABULARIOS[nombre].derivado_de
        if origen:
            fuentes.add(origen.partition(":")[0])
        conjunto = frozenset(_valores(nombre))
        # El primero gana: `severidad` antes que sus dos ampliaciones, que no
        # comparten conjunto con ella de todos modos.
        por_conjunto.setdefault(conjunto, nombre)

    hallazgos: list[dict] = []
    for ruta in arboles_medidos():
        # El dueño migrado (deuda #12) se reconoce por el nombre de su alias.
        if vault_grafo_import.nombre_de(ruta) in fuentes:
            continue
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        # `mapa("severidad", {...})` es la forma sancionada para los mapas cuyo
        # valor no se puede derivar —umbrales, transiciones, fichas de datos—.
        # El literal sigue ahí porque el dato es del punto de uso, pero las
        # claves quedan comprobadas contra el registro al importarse el módulo,
        # que es lo que el guard persigue. Marcarlo igual convertiría el único
        # camino correcto en un incumplimiento.
        declarados = {
            id(a) for n in _nodos(arbol)
            if isinstance(n, ast.Call)
            and _nombre_llamado(n.func).lstrip("_") == "mapa"
            for a in n.args
        }
        for nodo in _nodos(arbol):
            if id(nodo) in declarados:
                continue
            literales = _literales_de_cadena(nodo)
            if literales is None:
                continue
            nombre = por_conjunto.get(frozenset(literales))
            if nombre is not None:
                hallazgos.append(
                    {
                        "module": ruta.stem,
                        "line": nodo.lineno,
                        "vocabulary": nombre,
                    }
                )
    return hallazgos


def _clave_copia_de_vocabulario(x: dict) -> str:
    return f"{x['module']}:{x['vocabulary']}"


def _clave_fuera_de_puerto(x: dict) -> str:
    return f"{x['module']} -> {x['symbol']}"


# ── Baseline ─────────────────────────────────────────────────────────────────

def _leer_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"crossings": [], "note": ""}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


#: Las llamadas que lanzan un proceso. `ejecutar` es el envoltorio del kernel
#: (`vault/kernel/subproceso.py`); las de `subprocess` cuentan solo con el
#: módulo delante, para no confundir `run` con cualquier método homónimo.
_LANZA_PROCESO_SUBPROCESS = frozenset({"run", "check_output", "check_call", "call", "Popen"})


def _lanza_proceso(nodo: ast.AST) -> bool:
    if not isinstance(nodo, ast.Call):
        return False
    f = nodo.func
    if isinstance(f, ast.Attribute):
        if f.attr == "ejecutar":
            return True
        return (f.attr in _LANZA_PROCESO_SUBPROCESS
                and isinstance(f.value, ast.Name) and f.value.id == "subprocess")
    return isinstance(f, ast.Name) and f.id == "ejecutar"


def _es_ast_walk(nodo: ast.AST) -> ast.AST | None:
    """El argumento de `ast.walk(X)`, o `None` si `nodo` no es esa llamada."""
    if (isinstance(nodo, ast.Call) and nodo.args
            and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "walk"
            and isinstance(nodo.func.value, ast.Name) and nodo.func.value.id == "ast"):
        return nodo.args[0]
    return None


def _bucles(arbol: ast.AST):
    """(iterable, cuerpo) de cada `for` y de cada generador de una comprensión."""
    for nodo in _nodos(arbol):
        if isinstance(nodo, (ast.For, ast.AsyncFor)):
            yield nodo, nodo.iter, nodo.body
        elif isinstance(nodo, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            cuerpo = [nodo.key, nodo.value] if isinstance(nodo, ast.DictComp) else [nodo.elt]
            for gen in nodo.generators:
                yield nodo, gen.iter, cuerpo + list(gen.ifs)


def costes_que_crecen_en(arbol: ast.AST) -> list[dict]:
    """AP-66 sobre un árbol: las dos formas reconocibles sin ejecutar.

    - `proceso_por_linea_de_proceso`: un bucle cuyo iterable sale de un
      proceso y cuyo cuerpo lanza otro. Es `pendiente` antes de 0238503: un
      `git show` por cada commit que había listado `git log`, así que el coste
      crecía con la historia del repo y no con la baseline que se medía.
    - `recorrido_dentro_de_su_recorrido`: `ast.walk(X)` dentro del cuerpo de un
      bucle sobre `ast.walk(X)`, con el mismo `X`. Cuadrático en el tamaño del
      árbol para responder algo que cabe en una pasada. Recorrer el subárbol de
      cada nodo no se marca: es lineal en lo que se mide.

    Lo que no ve —la repetición que solo existe en ejecución, como reparsear
    lo mismo en cada llamada o un bucle sobre los ficheros del repo— lo vigilan
    los tests que cuentan trabajo de cada arreglo, no este detector.
    """
    hallazgos: list[dict] = []
    funciones = [n for n in _nodos(arbol)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for funcion in funciones or [arbol]:
        de_proceso = {
            t.id
            for n in ast.walk(funcion)
            if isinstance(n, ast.Assign) and _lanza_proceso(n.value)
            for t in n.targets if isinstance(t, ast.Name)
        }
        for bucle, iterable, cuerpo in _bucles(funcion):
            nombres = {n.id for n in ast.walk(iterable) if isinstance(n, ast.Name)}
            iter_de_proceso = bool(nombres & de_proceso) or any(
                _lanza_proceso(n) for n in ast.walk(iterable))
            if iter_de_proceso and any(
                    _lanza_proceso(n) for s in cuerpo for n in ast.walk(s)):
                hallazgos.append({"kind": "proceso_por_linea_de_proceso",
                                  "function": getattr(funcion, "name", None),
                                  "line": bucle.lineno})
                continue
            recorrido = _es_ast_walk(iterable)
            if recorrido is None:
                continue
            raiz = ast.dump(recorrido)
            if any(ast.dump(x) == raiz for s in cuerpo for n in ast.walk(s)
                   for x in [_es_ast_walk(n)] if x is not None):
                hallazgos.append({"kind": "recorrido_dentro_de_su_recorrido",
                                  "function": getattr(funcion, "name", None),
                                  "line": bucle.lineno})
    # Una función anidada se visita dos veces —como sí misma y dentro de la
    # que la contiene—; el sitio es uno.
    unicos = {(h["kind"], h["line"]): h for h in hallazgos}
    return sorted(unicos.values(), key=lambda h: (h["line"], h["kind"]))


def costes_que_crecen(rutas: list[Path] | None = None) -> list[dict]:
    """AP-66 — el coste crece con lo que no es trabajo, en todo el alcance medido.

    Sin baseline: se midió cero al declararla, porque los cinco sitios que la
    auditoría del 2026-10-15 encontró se arreglaron antes. Una lista vacía de
    excepciones solo invitaría a estrenarla.
    """
    hallazgos: list[dict] = []
    for ruta in (rutas if rutas is not None else arboles_medidos()):
        try:
            arbol = _ast_de(ruta)
        except SyntaxError:
            continue
        for h in costes_que_crecen_en(arbol):
            hallazgos.append({"module": clave_de_modulo(ruta), **h})
    return hallazgos


def _una_medicion(funcion):
    """Abre el memo de `_una_vez_por_medicion` mientras corre `funcion`."""
    import functools

    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        global _MEMO_DE_MEDICION
        previo = _MEMO_DE_MEDICION
        _MEMO_DE_MEDICION = {} if previo is None else previo
        try:
            return funcion(*args, **kwargs)
        finally:
            _MEMO_DE_MEDICION = previo
    return envoltura


@_una_medicion
def check(strict: bool = False) -> dict:
    base = set(_leer_baseline().get("crossings", []))
    actuales = cruces()
    claves = {_clave(c) for c in actuales}
    nuevos = sorted(claves - base)
    saldados = sorted(base - claves)
    huerfanos = sin_clasificar() + dominio_sin_clasificar()
    ausentes = fantasmas()

    base_vinc = set(_leer_baseline().get("frozen_bindings", []))
    vinculos = vinculos_congelados()
    claves_v = {f"{v['module']}.{v['binding']}" for v in vinculos}
    vinc_nuevos = sorted(claves_v - base_vinc)
    vinc_saldados = sorted(base_vinc - claves_v)

    # Puerta dura desde el primer día, sin baseline: se midió cero al
    # declararla. Congelar deuda tiene sentido cuando existe; aquí no la hay,
    # y una lista de excepciones vacía solo invita a estrenarla.
    prohibidas = escrituras_prohibidas()

    # AP-54, con el mismo criterio: se midió cero al declararla porque el único
    # sitio que lo hacía —`vault_errors_trace`— se corrigió al encontrarlo. No
    # hay deuda que congelar, y una lista vacía de excepciones solo invita a
    # estrenarla.
    sin_lock = escrituras_sin_lock()

    # La frontera del kernel, con la misma vara: los tres ganchos del write path
    # están declarados con su motivo; cualquier otro cruce kernel → dominio es
    # un fallo de la puerta, no deuda que congelar.
    kernel_sin_declarar = dependencias_del_kernel()

    # El punto ciego que quedó al saldar AP-49: usar el nombre importado.
    nombre_crudo = usos_del_nombre_congelado()

    # La frontera, comprobada en vez de declarada: todo puerto apunta a un
    # símbolo que existe en un módulo del propio contexto.
    rotos = puertos_rotos()

    # Y por dónde se entra, no solo a qué contexto: 49 símbolos importados por
    # fuera de la superficie publicada. Con baseline —como `vault_noop_audit`—
    # porque exigir cero el primer día haría nacer la puerta en rojo, y una
    # puerta en rojo se desactiva.
    base_puerto = set(_leer_baseline().get("off_port_crossings", []))
    fuera_puerto = cruces_fuera_de_puerto()
    claves_p = {_clave_fuera_de_puerto(x) for x in fuera_puerto}
    puerto_nuevos = sorted(claves_p - base_puerto)
    puerto_saldados = sorted(base_puerto - claves_p)

    # La configuración, con la misma vara que las fronteras: toda variable que
    # el estándar lee está declarada. En duro y sin baseline — se saldó al
    # declararla, moviendo las catorce al registro.
    entorno_sin_registro = lecturas_de_entorno_sin_registro()

    # Ésta sí arranca con baseline: al declararla había cinco duplicados
    # heredados de las fases anteriores. Exigir cero el primer día habría hecho
    # que la puerta naciera en rojo, y una puerta en rojo se desactiva.
    base_rutas = set(_leer_baseline().get("duplicate_paths", []))
    duplicadas = rutas_duplicadas()
    claves_r = {d["file"] for d in duplicadas}
    rutas_nuevas = sorted(claves_r - base_rutas)
    rutas_saldadas = sorted(base_rutas - claves_r)

    # Sin baseline a propósito: las catorce copias se saldaron al declarar
    # el registro, así que la puerta puede nacer en cero. Una baseline aquí
    # solo serviría para admitir la número quince.
    entorno_desfasado = tabla_de_entorno_desfasada()
    copias_vocab = copias_de_vocabulario()
    vocab_sin_dueno = vocabularios_sin_dueno()

    # Sin baseline, y por el mismo motivo que las copias de vocabulario: los 21
    # pares se declararon al estrenar el registro, así que la puerta nace en
    # cero. Una baseline aquí solo serviría para admitir el par número 22 sin
    # decidir nada, que es exactamente el trámite que este registro sustituye.
    sin_presupuesto = pares_sin_presupuesto()
    presupuesto_huerfano = presupuesto_de_cruces_huerfano()

    # Quién escribe cada subruta de `00_System/` (deuda #3, v41.3). Con
    # baseline por decisión del usuario (2026-10-08): los cruces que ya
    # existían arrancan congelados y solo encogen; uno nuevo bloquea.
    base_sis = set(_leer_baseline().get("system_writes", []))
    ajenas_sis = escrituras_de_sistema_ajenas()
    claves_s = {_clave_escritura_de_sistema(e) for e in ajenas_sis}
    sis_nuevas = sorted(claves_s - base_sis)
    sis_saldadas = sorted(base_sis - claves_s)

    # Deuda #12 — el puente de ADR-0002. Con baseline: los módulos que ya
    # estaban en `scripts/` sin hogar arrancan congelados y solo encogen; uno
    # nuevo bloquea, porque su sitio es `vault/<contexto>/` desde el principio.
    base_puente = set(_leer_baseline().get("bridge_modules", []))
    puente = set(modulos_sin_hogar())
    puente_nuevos = sorted(puente - base_puente)
    puente_saldados = sorted(base_puente - puente)
    contrato_puente = contrato_del_puente(puente)

    # AP-66, sin baseline: se midió cero al declararla.
    crecen = costes_que_crecen()

    return {
        "ok": not nuevos and not huerfanos and not ausentes and not vinc_nuevos
              and not sin_presupuesto
              and not prohibidas and not rutas_nuevas and not sin_lock
              and not kernel_sin_declarar and not nombre_crudo and not rotos
              and not puerto_nuevos and not entorno_sin_registro
              and not copias_vocab and not vocab_sin_dueno
              and not entorno_desfasado and not sis_nuevas and not puente_nuevos
              and not contrato_puente["fuera_de_contrato"]
              and not contrato_puente["ancla_con_hogar"]
              and not crecen
              and not (strict and (saldados or vinc_saldados or rutas_saldadas
                                   or puerto_saldados or sis_saldadas
                                   or puente_saldados)),
        "tool": "vault_arch",
        "contexts": len(CONTEXTS),
        "modules": len(_mapa_modulos()),
        "domain_modules": len(_modulos_dominio()),
        # Claves, no sitios: `baseline_total` cuenta claves `origen -> destino`,
        # y publicar el total en sitios ponía dos cifras contiguas que no se
        # pueden restar —60 contra 58 sin una sola deuda nueva—. Es el mismo
        # defecto que se arregló en `off_port` en v40.8 y que quedó vivo en la
        # medida hermana. `crossings_sites` conserva el dato de antes.
        "crossings_total": len(claves),
        "crossings_sites": len(actuales),
        "baseline_total": len(base),
        "new_crossings": nuevos,
        "settled_crossings": saldados,
        "unclassified_modules": huerfanos,
        "declared_but_missing": ausentes,
        # La prohibición del Meta-toolkit, ya ejecutable.
        "forbidden_writes": prohibidas,
        # AP-54: el lock falló y se escribió igual, encima de quien lo tenía.
        "unsynced_writes": sin_lock,
        # La frontera del kernel: ganchos declarados vs. cruces sin justificar.
        "kernel_hooks": len(GANCHOS_DEL_KERNEL),
        "undeclared_kernel_deps": kernel_sin_declarar,
        # La dirección de cada frontera, no solo su cantidad (v40.27).
        "crossing_budget_pairs": len(PRESUPUESTO_DE_CRUCES),
        "crossing_budget_by_goal": {
            objetivo: sum(
                1 for v in PRESUPUESTO_DE_CRUCES.values()
                if v["objetivo"] == objetivo
            )
            for objetivo in ("permanente", "a_eliminar", "en_estudio")
        },
        "unbudgeted_context_pairs": sin_presupuesto,
        # Informativo: una entrada que sobrevive al par que explicaba. Se retira
        # a conciencia, con la versión que lo cerró — borrarla en silencio no se
        # distingue de una que nadie volvió a mirar.
        "stale_crossing_budget": presupuesto_huerfano,
        # AP-49, su otra mitad: el nombre `VAULT_ROOT` importado sin alias.
        "raw_vault_root_imports": nombre_crudo,
        # La frontera vigilada: puertos declarados vs. puertos que existen.
        "ports_total": sum(len(c["puertos"]) for c in CONTEXTS.values()),
        "broken_ports": rotos,
        # Y por dónde se cruza: símbolos importados fuera de la superficie.
        #
        # `len(claves_p)` y no `len(fuera_puerto)`: la baseline se guarda por
        # clave `módulo -> símbolo`, así que contar sitios publicaba dos cifras
        # contiguas que no se podían restar. Daban 48 y 47 sin que hubiera
        # deuda nueva — `vault_io` importa `vault_section_index` dos veces en
        # el mismo fichero y las dos colapsan en una clave. El detalle por
        # sitio sigue entero en `crossings`.
        "off_port_total": len(claves_p),
        "off_port_sites": len(fuera_puerto),
        "off_port_baseline": len(base_puerto),
        "new_off_port_crossings": puerto_nuevos,
        "settled_off_port_crossings": puerto_saldados,
        # AP-05 sobre configuración: variables leídas sin declarar.
        "env_vars_declared": _cuantas_variables_declaradas(),
        "undeclared_env_reads": entorno_sin_registro,
        # AP-47 — el artefacto que consume el servidor MCP, al día.
        "mjs_env_table_stale": entorno_desfasado,
        # AP-05 sobre vocabulario: valores copiados en vez de consumidos.
        "vocabularies_declared": len(_vocabularios_declarados()),
        "vocabulary_copies": copias_vocab,
        "vocabularies_without_owner": vocab_sin_dueno,
        # AP-05 — el mismo fichero declarado en dos repositorios de dominio.
        "duplicate_paths_total": len(duplicadas),
        "duplicate_paths_baseline": len(base_rutas),
        "new_duplicate_paths": rutas_nuevas,
        "settled_duplicate_paths": rutas_saldadas,
        # AP-49 — vínculo resuelto en tiempo de import.
        "frozen_bindings_total": len(vinculos),
        "frozen_bindings_baseline": len(base_vinc),
        "new_frozen_bindings": vinc_nuevos,
        "settled_frozen_bindings": vinc_saldados,
        # Deuda #3 — un contexto que escribe la subruta de `00_System/` de otro.
        # Por clave `subruta <- módulo`, como las demás baselines por clave.
        "system_paths_owned": len(duenos_de_sistema()),
        "system_writes_total": len(claves_s),
        "system_writes_baseline": len(base_sis),
        "new_system_writes": sis_nuevas,
        "settled_system_writes": sis_saldadas,
        "foreign_system_writes": ajenas_sis,
        # Deuda #12 — módulos de `scripts/` sin hogar en `vault/<contexto>/`.
        "bridge_modules_total": len(puente),
        "bridge_modules_baseline": len(base_puente),
        "new_bridge_modules": puente_nuevos,
        "settled_bridge_modules": puente_saldados,
        # El contrato del puente, sin baseline: lo que no es ancla ni tiene
        # hogar bloquea aunque se haya congelado.
        "bridge_anchor": sorted(ANCLA_DEL_PUENTE),
        "bridge_contract_violations": contrato_puente["fuera_de_contrato"],
        "stale_bridge_anchor": contrato_puente["ancla_con_hogar"],
        # AP-66 — un bucle cuyo coste crece con algo que no es lo medido.
        "growing_costs": crecen,
        "crossings": actuales,
    }


def freeze() -> dict:
    claves = sorted({_clave(c) for c in cruces()})
    fuera_puerto = sorted(
        {_clave_fuera_de_puerto(x) for x in cruces_fuera_de_puerto()}
    )
    vinculos = sorted({
        f"{v['module']}.{v['binding']}" for v in vinculos_congelados()
    })
    # Lo que el escritor no conoce, se conserva (v40.30): `excepcion_de_alcance`
    # la escribe una persona para dejar dicho por qué la lista creció una vez, y
    # un `--freeze` que la borrase dejaría el fichero indistinguible de uno donde
    # nadie declaró nada. Desde v40.36 lo conserva `vault_baseline.escribir`,
    # que guarda todas las claves ajenas y no solo esa (AP-57).
    vault_baseline.escribir(
        BASELINE_PATH, "crossings", "vault_arch",
        "Deuda estructural congelada. SOLO PUEDE ENCOGER: un cruce "
        "nuevo es una frontera que se rompió y se arregla publicando "
        "un puerto, no ampliando esta lista; un vínculo nuevo es "
        "AP-49 y se arregla resolviendo tarde con get_vault_root().",
        claves,
        extra={
            "frozen_bindings": vinculos,
            "duplicate_paths": sorted(d["file"] for d in rutas_duplicadas()),
            "off_port_crossings": fuera_puerto,
            "system_writes": sorted({_clave_escritura_de_sistema(e)
                                     for e in escrituras_de_sistema_ajenas()}),
            "bridge_modules": modulos_sin_hogar(),
        },
        campo_descripcion="note",
    )
    return {"ok": True, "tool": "vault_arch", "frozen": len(claves),
            "frozen_bindings": len(vinculos),
            "frozen_off_port": len(fuera_puerto), "path": str(BASELINE_PATH)}


# ── El plano derivado ────────────────────────────────────────────────────────

def blueprint() -> str:
    r = check()
    por_ctx: dict[str, list[dict]] = {}
    for c in r["crossings"]:
        por_ctx.setdefault(c["from_context"], []).append(c)

    lineas = [
        "# Arquitectura del estándar — contextos acotados",
        "",
        "> Documento derivado. Se genera con `python scripts/vault_arch.py "
        "--blueprint`; la fuente es `CONTEXTS` en `scripts/vault_arch.py`. "
        "No se edita a mano.",
        "",
        f"**{r['contexts']} contextos**, **{r['modules']} módulos** clasificados, "
        f"**{r['crossings_total']} fronteras cruzadas** pendientes de publicar puerto.",
        "",
        "## Los límites",
        "",
    ]
    lineas += [f"{i}. {t}" for i, t in enumerate(LIMITES, 1)]
    lineas += ["", "## Mapa de contextos", "", "```mermaid", "graph TD"]
    for ctx, datos in CONTEXTS.items():
        lineas.append(f'    {ctx}["{datos["titulo"]}"]')
    for ctx in CONTEXTS:
        if ctx != KERNEL:
            lineas.append(f"    {ctx} --> {KERNEL}")
    vistos = set()
    for c in r["crossings"]:
        par = (c["from_context"], c["to_context"])
        if par not in vistos:
            vistos.add(par)
            lineas.append(f"    {par[0]} -.->|cruce| {par[1]}")
    lineas += ["```", ""]

    for ctx, datos in CONTEXTS.items():
        lineas += [
            f"## {datos['titulo']}",
            "",
            f"- **Lenguaje ubicuo:** {', '.join(datos['lenguaje'])}",
            (
                "- **Puertos publicados:** "
                + ", ".join(
                    f"`{p}` → `{d}`" for p, d in sorted(datos["puertos"].items())
                )
            ).rstrip(),
        ]
        if datos["prohibe"]:
            lineas.append(f"- **No cruza:** {'; '.join(datos['prohibe'])}")
        lineas += [
            f"- **Módulos ({len(datos['modulos'])}):** "
            + ", ".join(f"`{m}`" for m in sorted(datos["modulos"])),
            "",
        ]
        salientes = por_ctx.get(ctx, [])
        if salientes:
            # Una fila por frontera, no por sitio: `cruces()` da una entrada por
            # cada import, y `vault_subgraph` salía tres veces con la misma fila
            # y el título contaba sitios donde decía fronteras. Los sitios se
            # conservan como cifra en la fila; el dato está en `crossings_sites`.
            fronteras = {}
            for c in salientes:
                clave = (c["from"], c["to"], c["to_context"])
                fronteras[clave] = fronteras.get(clave, 0) + 1
            lineas += [
                f"Fronteras que hoy cruza ({len(fronteras)}), deuda declarada:",
                "",
                "| Módulo | Importa | Contexto destino |",
                "|---|---|---|",
            ]
            lineas += [
                f"| `{origen}` | `{destino}`{f' ({n} imports)' if n > 1 else ''} "
                f"| {CONTEXTS[ctx_destino]['titulo']} |"
                for (origen, destino, ctx_destino), n in fronteras.items()
            ]
            lineas.append("")
    return "\n".join(lineas)


def main() -> int:
    ap = argparse.ArgumentParser(description="Plano técnico: contextos acotados", allow_abbrev=False)
    ap.add_argument("--check", action="store_true", help="guard de fronteras")
    ap.add_argument("--strict", action="store_true",
                    help="además exige que la baseline se haya actualizado al encoger")
    ap.add_argument("--freeze", action="store_true", help="congela la deuda actual")
    ap.add_argument("--blueprint", action="store_true",
                    help="emite docs/ARQUITECTURA.md")
    ap.add_argument("--map", metavar="MODULO", help="a qué contexto pertenece")
    ap.add_argument("--env", action="store_true",
                    help="la tabla de configuración derivada del registro")
    ap.add_argument("--sync-env", action="store_true",
                    help="regenera mcp/nodejs/env-table.json desde el registro")
    ap.add_argument("--vocab", action="store_true",
                    help="los vocabularios cerrados y su contexto dueño")
    args = ap.parse_args()

    if args.map:
        ctx = contexto_de(args.map)
        print(json.dumps({
            "ok": ctx is not None, "tool": "vault_arch", "module": args.map,
            "context": ctx, "title": CONTEXTS[ctx]["titulo"] if ctx else None,
        }, ensure_ascii=False))
        return 0 if ctx else 1

    if args.env:
        from vault_entorno import tabla

        print(json.dumps({"ok": True, "tool": "vault_arch",
                          "variables": tabla()},
                         indent=2, ensure_ascii=False))
        return 0

    if args.sync_env:
        TABLA_ENTORNO_MJS.write_bytes((json.dumps(tabla_de_entorno_derivada(), indent=2,
                       ensure_ascii=False) + "\n").encode("utf-8"))
        print(json.dumps({"ok": True, "tool": "vault_arch",
                          "path": str(TABLA_ENTORNO_MJS)}, ensure_ascii=False))
        return 0

    if args.vocab:
        from vault_vocabulario import tabla

        print(json.dumps({"ok": True, "tool": "vault_arch",
                          "vocabularies": tabla()},
                         indent=2, ensure_ascii=False))
        return 0

    if args.freeze:
        print(json.dumps(freeze(), ensure_ascii=False))
        return 0

    if args.blueprint:
        destino = REPO_ROOT / "docs" / "ARQUITECTURA.md"
        destino.write_bytes((blueprint() + "\n").encode("utf-8"))
        print(json.dumps({"ok": True, "tool": "vault_arch",
                          "path": str(destino)}, ensure_ascii=False))
        return 0

    r = check(strict=args.strict)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
