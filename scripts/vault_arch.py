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
CONTEXTS: dict[str, dict] = {
    KERNEL: {
        "titulo": "Kernel",
        "lenguaje": ["ruta", "envelope", "error", "bloqueo", "escritura atómica"],
        "puertos": ["get_vault_root", "atomic_write_text", "wrap_main", "file_lock"],
        "prohibe": ["depender de cualquier contexto de dominio"],
        "modulos": [
            "vault_io", "vault_errors", "vault_lib", "vault_regex",
            "vault_encoding", "vault_registry", "vault_log_error",
            "vault_errors_catalog", "vault_errors_trace",
        ],
    },
    "autoria": {
        "titulo": "Autoría",
        "lenguaje": ["nota", "frontmatter", "slug", "sección", "alias"],
        "puertos": ["escribir_nota", "anexar", "mover", "fusionar"],
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
            "vault_timeline", "vault_project_overview", "vault_project_status",
        ],
    },
    "grafo": {
        "titulo": "Grafo",
        "lenguaje": ["nodo", "arista", "wikilink", "huérfano", "componente"],
        "puertos": ["construir_grafo", "resolver_wikilink", "impacto"],
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
        "lenguaje": ["norma", "guard", "enforcement", "severidad", "violación"],
        "puertos": ["NORM_CATALOG", "auditar", "puntuar_calidad"],
        "prohibe": [],
        "modulos": [
            "vault_norms", "vault_audit", "vault_fundamentals",
            "vault_quality_check", "vault_validate", "vault_security_scan",
            "vault_secret_scan", "vault_drift_detect", "vault_mermaid_check",
        ],
    },
    "indices": {
        "titulo": "Índices",
        "lenguaje": ["índice", "etiqueta", "término", "sección indexada"],
        "puertos": ["reindexar", "indice_maestro", "vocabulario_de_tags"],
        "prohibe": [],
        "modulos": [
            "vault_master_index", "vault_reindex", "vault_section_index",
            "vault_tags", "vault_index", "vault_folder_registry",
        ],
    },
    "consulta": {
        "titulo": "Consulta",
        "lenguaje": ["intención", "subgrafo", "paquete de contexto", "preferencia"],
        "puertos": ["parsear_consulta", "subgrafo", "empaquetar_contexto"],
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
        "puertos": ["CURRENT_VERSION", "inicializar", "migrar"],
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
        "puertos": ["crear_backup", "listar_backups", "restaurar", "poner_en_cuarentena"],
        "prohibe": ["escribir fuera de la raíz del vault (AP-36)"],
        "modulos": [
            "vault_backup", "vault_backup_list", "vault_restore",
            "vault_quarantine",
        ],
    },
    "meta_toolkit": {
        "titulo": "Meta-toolkit",
        "lenguaje": ["catálogo", "contrato", "spec", "smoke", "conteo derivado"],
        "puertos": ["TOOLS_CATALOG", "GROUPS", "check_contracts"],
        # Éste es el contexto que v39.6 dejó a medias: sus módulos ya están
        # anotados `internal` con motivo, pero nada impedía que uno tocase un
        # vault. Es el único contexto cuya frontera es una prohibición.
        "prohibe": ["escribir en un vault: opera sobre el estándar, no sobre datos"],
        "modulos": [
            "vault_mcp", "vault_mcp_catalog", "vault_manifest", "vault_smoke",
            "vault_spec_catalog_check", "vault_spec_generate_catalog",
            "vault_spec_memory", "vault_spec_validate", "vault_test_runner",
            "vault_doc_counts", "vault_doc_sync", "vault_noop_audit",
            "vault_arch",
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
            fuera.append({
                "from": nombre, "from_context": origen,
                "to": destino_mod, "to_context": destino,
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


def fantasmas() -> list[str]:
    """Módulos declarados en un contexto que ya no están en disco."""
    en_disco = set(_modulos_en_disco())
    return sorted(m for m in _mapa_modulos() if m not in en_disco)


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

    return {
        "ok": not nuevos and not huerfanos and not ausentes and not vinc_nuevos
              and not (strict and (saldados or vinc_saldados)),
        "tool": "vault_arch",
        "contexts": len(CONTEXTS),
        "modules": len(_mapa_modulos()),
        "domain_modules": len(_modulos_dominio()),
        "crossings_total": len(actuales),
        "baseline_total": len(base),
        "new_crossings": nuevos,
        "settled_crossings": saldados,
        "unclassified_modules": huerfanos,
        "declared_but_missing": ausentes,
        # AP-49 — vínculo resuelto en tiempo de import.
        "frozen_bindings_total": len(vinculos),
        "frozen_bindings_baseline": len(base_vinc),
        "new_frozen_bindings": vinc_nuevos,
        "settled_frozen_bindings": vinc_saldados,
        "crossings": actuales,
    }


def freeze() -> dict:
    claves = sorted({_clave(c) for c in cruces()})
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
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "tool": "vault_arch", "frozen": len(claves),
            "frozen_bindings": len(vinculos), "path": str(BASELINE_PATH)}


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
            f"- **Puertos publicados:** {', '.join(datos['puertos'])}",
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
    args = ap.parse_args()

    if args.map:
        ctx = contexto_de(args.map)
        print(json.dumps({
            "ok": ctx is not None, "tool": "vault_arch", "module": args.map,
            "context": ctx, "title": CONTEXTS[ctx]["titulo"] if ctx else None,
        }, ensure_ascii=False))
        return 0 if ctx else 1

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
