#!/usr/bin/env python3
"""Plano técnico del estándar: contextos acotados y sus fronteras.

Los 37 grupos del catálogo son una taxonomía de documentación —sirven para
encontrar una tool en `scripts/README.md`—, no fronteras de dominio. Nada dice
hoy quién puede importar a quién, y por eso los defectos de v39.5 y v39.6 son
todos el mismo: una capacidad implementada dos veces (AP-48), un side effect
fuera del vault, cinco módulos ejecutables en ningún registro. Se detectan de
uno en uno y después del hecho.

Siguiendo la regla 3 de `CLAUDE.md` —registro canónico primero, doc después—
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
from pathlib import Path

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
    return rel.as_posix()


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
        "puertos": {
            "get_vault_root": "vault_io:get_vault_root",
            "atomic_write_text": "vault_io:atomic_write_text",
            "wrap_main": "vault_errors:wrap_main",
            "file_lock": "vault_io:file_lock",
        },
        "prohibe": ["depender de cualquier contexto de dominio"],
        "modulos": [
            "vault_io", "vault_errors", "vault_lib", "vault_regex",
            "vault_encoding", "vault_registry", "vault_log_error",
            "vault_errors_catalog", "vault_errors_trace",
            "vault_entorno", "vault_vocabulario",
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
            "hablar": "vault_voice:speak",
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
            "vault_frontmatter_heal",
            "vault_timeline", "vault_project_overview", "vault_project_status",
        ],
    },
    "grafo": {
        "titulo": "Grafo",
        "lenguaje": ["nodo", "arista", "wikilink", "huérfano", "componente"],
        "puertos": {
            "construir_grafo": "vault_graph:vault_graph",
            "resolver_wikilink": "vault_link_safety:validate_wikilinks",
            "impacto": "vault_impact:vault_impact",
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
            # Los tres registros que `CLAUDE.md` declara fuente única de
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
            # escritura ocurra, así que es frontera de pleno derecho.
            "gancho_de_secretos": "vault_secret_scan:vault_write_hook",
            "hay_hallazgos_bloqueantes": "vault_secret_scan:has_blocking_findings",
        },
        "prohibe": [],
        "modulos": [
            "vault_norms", "vault_fuente_unica",
            "vault_audit", "vault_fundamentals",
            "vault_quality_check", "vault_validate", "vault_security_scan",
            "vault_secret_scan", "vault_drift_detect", "vault_mermaid_check",
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
            # El índice de sección lo dispara el write path del kernel desde
            # v39: es el punto por el que índices entra en cada escritura, y
            # llevaba tres versiones cruzando la frontera sin nombre.
            "indice_de_seccion": "vault_section_index:vault_section_index",
            "registrar_tags": "vault_tags:registrar_tags_de_nota",
            "tags_de_frontmatter": "vault_tags:tags_de_frontmatter",
            "ledger_de_backfill_de_tags": "vault_tags:vault_tags_backfill_ledger",
            "coherencia_de_indices": "vault_reindex:index_coherence",
        },
        "prohibe": [],
        "modulos": [
            "vault_master_index", "vault_reindex", "vault_section_index",
            "vault_tags", "vault_index", "vault_folder_registry",
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
            "vault_preferences", "vault_ingest", "vault_mcp_context",
            "vault_tokens", "vault_token_counter", "vault_token_service",
            "vault_compact_contracts",
        ],
    },
    "ciclo_de_vida": {
        "titulo": "Ciclo de vida",
        "lenguaje": ["versión", "migración", "sanación", "arranque"],
        "puertos": {
            "CURRENT_VERSION": "vault_standard_upgrade:CURRENT_VERSION",
            "inicializar": "vault_init:vault_init",
            "migrar": "vault_standard_upgrade:vault_standard_upgrade",
        },
        "prohibe": [],
        "modulos": [
            "vault_init", "vault_onboard", "vault_standard_upgrade",
            "vault_sanacion", "vault_migrate_docs", "vault_migrate_rollback",
            "vault_propagate", "vault_sdd_init",
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
            "vault_doc_counts", "vault_doc_sync", "vault_noop_audit",
            "vault_blame_audit", "vault_error_contract", "vault_foreign_check",
            "vault_gate", "vault_arch",
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
#: `vault_io._VAULT_ROOT_DETECTADO` guarda el vault que la autodetección eligió
#: al cargar, para que `reset_vault_root()` tenga a dónde volver. Si siguiera al
#: vault activo no serviría de nada: sería una copia del sitio del que hay que
#: salir. La exención va por nombre y no por heurística —«los que empiecen por
#: guion bajo», por ejemplo— porque una heurística abre la puerta a que el
#: próximo vínculo congelado se cuele por parecerse.
VINCULOS_INTENCIONALES = frozenset({
    "vault_io._VAULT_ROOT_DETECTADO",
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


# ── El grafo de importaciones, por AST ───────────────────────────────────────

def _importaciones(ruta: Path) -> set[str]:
    """Los módulos `vault_*` que importa este fichero, estén donde estén.

    Se lee por AST y no por regex porque aquí importan los imports diferidos
    dentro de una función tanto como los de cabecera: un `import vault_norms`
    escondido en un `try:` cruza la frontera exactamente igual.
    """
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombres.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.add(nodo.module.split(".")[0])
    return {n for n in nombres if n.startswith("vault_")}


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
            arbol_s = ast.parse(
                (SCRIPTS_DIR / f"{nombre}.py").read_text(encoding="utf-8", errors="replace")
            )
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol_s):
            for destino in _destino_de_import(nodo, Path(nombre)):
                if destino in CONTEXTS and destino not in (origen, KERNEL):
                    fuera.append({
                        "from": nombre, "from_context": origen,
                        "to": f"vault/{destino}", "to_context": destino,
                    })

    # El dominio, con la misma vara. Un módulo de `vault/x/` que importe
    # `vault_norms` cruza igual que si viviera en `scripts/`.
    for clave, origen in sorted(_modulos_dominio().items()):
        if not origen or clave == RAIZ_COMPOSICION:
            continue
        ruta = DOMINIO_DIR / clave[len("vault/"):]
        rel = ruta.relative_to(DOMINIO_DIR)
        for destino_mod in sorted(_importaciones(ruta)):
            destino = mapa.get(destino_mod)
            if destino is None or destino == origen or destino == KERNEL:
                continue
            fuera.append({
                "from": clave, "from_context": origen,
                "to": destino_mod, "to_context": destino,
            })
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            for destino in _destino_de_import(nodo, rel):
                if destino in CONTEXTS and destino not in (origen, KERNEL):
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
        ruta = SCRIPTS_DIR / f"{nombre}.py"
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
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
        ruta = SCRIPTS_DIR / f"{nombre}.py"
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
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


#: Lo que cuenta como escribir. `mkdir` entra: crear una sección de contenido
#: es tocar el vault del usuario aunque no se deje un byte dentro.
_LLAMADAS_DE_ESCRITURA = frozenset({
    "write_text", "write_bytes", "mkdir", "touch", "rename", "replace",
    "unlink", "rmtree", "atomic_write_text", "atomic_write_json", "write_report",
})


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
        arbol = ast.parse(repo.read_text(encoding="utf-8"))
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
    funciones = {n.name: n for n in ast.walk(arbol)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    for nodo in ast.walk(arbol):
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

    for nodo in ast.walk(arbol):
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
    ("vault_io", "vault_secret_scan"): (
        "Preflight anti-secretos de `atomic_write_text`. Tiene que correr en el "
        "único punto por el que pasan todas las escrituras, o no protege."
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
    ("vault_errors", "vault_voice"): (
        "La voz del vault acompaña al error. Es presentación, no dominio, y el "
        "kernel la degrada a silencio si falla."
    ),
    ("vault_vocabulario", "vault_norms"): (
        "`status` y los estados de dominio ya tienen registro canónico en "
        "Gobernanza. El registro de vocabularios los declara con `derivado_de` "
        "y los pide al llamarse: copiarlos aquí sería exactamente el AP-05 que "
        "este módulo existe para cerrar. La alternativa —mudarlo a Gobernanza— "
        "no elimina el cruce, lo mueve: `vault_log_error` es kernel y consume "
        "la escala de severidad. Se declara el cruce en vez de disimularlo."
    ),
    ("vault_vocabulario", "vault_fundamentals"): (
        "Los tres campos CIA salen de `CIA_TRIAD` por `cia_valores()`. Import "
        "perezoso y de solo lectura: ninguna decisión viaja de vuelta."
    ),
}


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
        for destino in sorted(_importaciones(fichero)):
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
                 else [SCRIPTS_DIR / f"{m}.py" for m in _modulos_en_disco()]):
        mod = ruta.stem
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
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
                        if not isinstance(c, ast.Call):
                            continue
                        nombre = (c.func.attr if isinstance(c.func, ast.Attribute)
                                  else getattr(c.func, "id", None))
                        if nombre in _LLAMADAS_DE_ESCRITURA:
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
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        desechables = _nombres_desechables(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            fn = nodo.func
            nombre = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else None)
            if nombre not in _LLAMADAS_DE_ESCRITURA:
                continue
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
    """Módulos declarados en un contexto que ya no están en disco."""
    en_disco = set(_modulos_en_disco())
    return sorted(m for m in _mapa_modulos() if m not in en_disco)


def _simbolos_de_nivel_superior(modulo: str) -> set[str] | None:
    """Los nombres que `modulo` define en su nivel superior, por AST.

    Por AST y no por import: importar los 112 módulos para comprobar una
    frontera los ejecutaría a todos, y varios resuelven el vault al importarse.
    Un guard que necesita un vault montado para decir si una frontera existe no
    es un guard, es otra dependencia.
    """
    ruta = SCRIPTS_DIR / f"{modulo}.py"
    if not ruta.exists():
        return None
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
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
            if modulo not in datos["modulos"]:
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
        origen = mapa.get(ruta.stem)
        if origen is None:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

        def _anotar(modulo: str, simbolo: str) -> None:
            destino = mapa.get(modulo.split(".")[0])
            if destino is None or destino == origen or destino == KERNEL:
                return
            if simbolo in _superficie_publica(destino):
                return
            fuera.append(
                {
                    "module": ruta.stem,
                    "from_context": origen,
                    "to_context": destino,
                    "symbol": f"{modulo}.{simbolo}",
                }
            )

        # `from vault_x import y` — el símbolo está en el nodo.
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                if nodo.module and nodo.module.startswith("vault_"):
                    for alias in nodo.names:
                        _anotar(nodo.module, alias.name)

        # `import vault_x [as vx]` — el símbolo no está en el nodo. Se ata el
        # nombre local al módulo y se buscan los accesos `vx.attr`. Sin esto la
        # forma más común de import queda sin medir.
        ligados: dict[str, str] = {}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    if alias.name.startswith("vault_"):
                        ligados[alias.asname or alias.name] = alias.name
        if ligados:
            for nodo in ast.walk(arbol):
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
        if ruta.stem in _COPIAS_DE_ENTORNO_LEGITIMAS:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
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
        if ruta.stem in fuentes:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        # `mapa("severidad", {...})` es la forma sancionada para los mapas cuyo
        # valor no se puede derivar —umbrales, transiciones, fichas de datos—.
        # El literal sigue ahí porque el dato es del punto de uso, pero las
        # claves quedan comprobadas contra el registro al importarse el módulo,
        # que es lo que el guard persigue. Marcarlo igual convertiría el único
        # camino correcto en un incumplimiento.
        declarados = {
            id(a) for n in ast.walk(arbol)
            if isinstance(n, ast.Call)
            and _nombre_llamado(n.func).lstrip("_") == "mapa"
            for a in n.args
        }
        for nodo in ast.walk(arbol):
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

    return {
        "ok": not nuevos and not huerfanos and not ausentes and not vinc_nuevos
              and not prohibidas and not rutas_nuevas and not sin_lock
              and not kernel_sin_declarar and not nombre_crudo and not rotos
              and not puerto_nuevos and not entorno_sin_registro
              and not copias_vocab and not vocab_sin_dueno
              and not entorno_desfasado
              and not (strict and (saldados or vinc_saldados or rutas_saldadas
                                   or puerto_saldados)),
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
    BASELINE_PATH.write_text(
        json.dumps({
            "note": "Deuda estructural congelada. SOLO PUEDE ENCOGER: un cruce "
                    "nuevo es una frontera que se rompió y se arregla publicando "
                    "un puerto, no ampliando esta lista; un vínculo nuevo es "
                    "AP-49 y se arregla resolviendo tarde con get_vault_root().",
            "crossings": claves,
            "frozen_bindings": vinculos,
            "duplicate_paths": sorted(d["file"] for d in rutas_duplicadas()),
            "off_port_crossings": fuera_puerto,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
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
            "- **Puertos publicados:** "
            + ", ".join(
                f"`{p}` → `{d}`" for p, d in sorted(datos["puertos"].items())
            ),
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
            lineas += [
                f"Fronteras que hoy cruza ({len(salientes)}), deuda declarada:",
                "",
                "| Módulo | Importa | Contexto destino |",
                "|---|---|---|",
            ]
            lineas += [
                f"| `{c['from']}` | `{c['to']}` | {CONTEXTS[c['to_context']]['titulo']} |"
                for c in salientes
            ]
            lineas.append("")
    return "\n".join(lineas)


def main() -> int:
    ap = argparse.ArgumentParser(description="Plano técnico: contextos acotados")
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
        TABLA_ENTORNO_MJS.write_text(
            json.dumps(tabla_de_entorno_derivada(), indent=2,
                       ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
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
        destino.write_text(blueprint() + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "tool": "vault_arch",
                          "path": str(destino)}, ensure_ascii=False))
        return 0

    r = check(strict=args.strict)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
