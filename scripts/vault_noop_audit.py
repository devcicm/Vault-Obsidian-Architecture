#!/usr/bin/env python3
"""vault_noop_audit — AP-37: ninguna tool devuelve `ok: true` sin decir qué hizo.

El síntoma que originó esta norma: `vault_standard_upgrade --to latest` devolvía
`{"ok": true}` habiendo aplicado **cero** migraciones, porque `_version_index()`
no normalizaba la minor version. El bug vivió versiones enteras precisamente
porque la respuesta era indistinguible de un éxito real.

La generalización: una tool con side effects tiene que exponer un **indicador de
trabajo** — un campo cuyo valor distinga "hice N cosas" de "no hice nada".
`ok: true` a secas es una afirmación no falsable.

    python scripts/vault_noop_audit.py --check    # tools sin indicador
    python scripts/vault_noop_audit.py --strict   # exit 1 si la deuda CRECIÓ
    python scripts/vault_noop_audit.py --freeze   # recongela la baseline
    python scripts/vault_noop_audit.py --ejecutado  # mide el envelope emitido

## `--ejecutado`: el indicador declarado no es el emitido

El modo estático mira `declared_returns`. Un contrato que declara
`fixes_applied` y un envelope que no lo trae pasan igual, porque mide lo que
la tool promete y no lo que responde (AP-44). Medido el 2026-10-16 ejecutando
el ejemplo documentado de cada tool con side effects y comparando el árbol:
dos escribían y lo callaban (`vault_delta --snapshot`, `vault_graph_fix
--apply`). El banco reutiliza la copia desechable de `vault_smoke` y
clasifica cada tool en `medidas` (escribió y lo dijo), `sin_escritura` (su
ejemplo no escribe: el banco no la ve), `sin_invocacion` y `ofensores`.
Un banco sin ninguna medida no sale verde (AP-60). No es puerta: tarda lo
que tarda el smoke, y lo que no cubre lo publica con su cifra.

Desde el 2026-10-17 ejecuta **cada** línea del `example`, no solo la
primera —que casi siempre es la de lectura—, sobre un sandbox con el proyecto
del ejemplo dado de alta (`PROYECTO_DEL_EJEMPLO`) y con los ficheros que el
ejemplo presupone (`FICHEROS_DEL_EJEMPLO`). Con solo la primera línea medía 17
de 92; con todas y la preparación, 44, y destapó tres que escribían callando.
Las de la capacidad `gobernanza_del_estandar` no se ejecutan: escriben en el
repo, y se publican en `fuera_del_vault`.

## De baseline a guard duro (v39)

56 tools declaraban side effects y 55 no exponían indicador. Un guard que falla
en 55 sitios se desactiva el primer día — que es como mueren los guards. Por eso
la norma nació como baseline: congelaba la deuda conocida, que **solo podía
encoger**.

La deuda está **saldada**: la baseline quedó en 0 y con ella vacía este audit
es ya un guard duro — cualquier tool con side effects y sin indicador aparece
como `new_offenders` y `--strict` sale con 1. No hay nada que reintroducir.

Lo que lo hizo posible fue dejar de pedirle a cada tool que **afirmara** su
trabajo y pasar a **medirlo** donde ocurre: `vault_io.atomic_write_text()`
clasifica cada escritura (`created` / `updated` / `unchanged`) en un ledger
thread-local, y la tool solo expande `**write_report()` en su return. Un
`unchanged: 1` es una respuesta honesta que antes era indistinguible de un
`ok: true`.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_errors import emit_error, wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "noop-baseline.json"

# Campos que distinguen "hice N cosas" de "no hice nada". La lista se amplía
# deliberadamente, nunca por comodidad: añadir aquí un campo que siempre está
# presente (como `path` u `ok`) vacía la norma de contenido.
#
# `files_included` / `files_restored` entran en v39 por las dos tools base64,
# que son JS-native y no pueden usar el ledger de `vault_io.write_report()`.
# Son recuentos reales de archivos, no banderas: cero sigue significando cero.
# `versions_restored` sigue el mismo patrón para vault_undo (restauración de versiones).
WORK_INDICATORS = {
    "added",
    "applied",
    "changed",
    # Plural del anterior. Lo introdujo `vault_changelog_check --fijar-hash`,
    # que no devuelve un contador sino el detalle de lo que tocó (hash antes y
    # después, si corrigió la fecha). Sigue siendo un indicador de trabajo: sin
    # él no se distingue «fijé el hash» de «no había nada que fijar».
    "changes",
    "claims_checked",
    "count",
    "created",
    "deleted",
    "fixed",
    "files_included",
    "files_restored",
    "fixes_applied",
    "frozen",
    "healed",
    "indexed",
    "migrations_applied",
    "modified",
    "no_op",
    "removed",
    "skipped",
    "total",
    "updated",
    "versions_restored",
    "written",
}


def _tool_spec() -> Dict:
    from vault_io import resolve_tool_spec

    path = resolve_tool_spec()
    if not path or not Path(path).exists():
        raise RuntimeError("tool-spec.json no resoluble: no se puede auditar AP-37")
    return json.loads(Path(path).read_text(encoding="utf-8")).get("tools", {})


def offenders() -> List[Dict]:
    """Tools con side effects declarados y sin indicador de trabajo."""
    import vault_mcp_catalog

    spec = _tool_spec()
    out = []
    for name, entry in sorted(vault_mcp_catalog.TOOLS_CATALOG.items()):
        if not entry.get("side_effects"):
            continue
        contrato = spec.get(name)
        if contrato is None:
            out.append({"tool": name, "reason": "sin entrada en tool-spec.json",
                        "declared_returns": []})
            continue
        returns = list(contrato.get("declared_returns", []))
        if not (set(returns) & WORK_INDICATORS):
            out.append({"tool": name, "reason": "sin indicador de trabajo",
                        "declared_returns": sorted(returns)})
    return out


#: El proyecto que citan los ejemplos del catálogo. El sandbox no lo tiene dado
#: de alta y en el vault de quien copia el ejemplo sí (`vault_smoke`,
#: `_CATEGORIAS_DE_ENTRADA`): sin él, 26 ejemplos de escritura respondían
#: `PROJECT_NOT_FOUND` y el banco los contaba como «su ejemplo no escribe»
#: (medido el 2026-10-17). El banco lo da de alta una vez, con la propia
#: `vault_project --add`, como `tests/test_ejemplos_de_escritores.py`.
PROYECTO_DEL_EJEMPLO: Optional[Tuple[str, str]] = ("mi-api", "Mi API")

#: Lo que cada ejemplo da por existente, por tool. La clave es relativa al
#: vault, o al directorio desde el que se ejecuta el ejemplo si empieza por
#: `@trabajo/` (`overview.md` en `--content "@file:overview.md"`, el
#: `../mi-api` de `vault_onboard`). Se crea antes de la foto del árbol, así que
#: no cuenta como trabajo de la tool. No es un ejemplo nuevo: es el estado del
#: vault que el documentado presupone.
FICHEROS_DEL_EJEMPLO: Dict[str, Dict[str, str]] = {
    "vault_delete": {"07_Knowledge/old.md": "nota"},
    # Mover a `03_Decisions` es reclasificar (CN-02): el ejemplo presupone una
    # nota cuyo tipo pertenece allí, y una carpeta `old/` que mover.
    "vault_move": {"01_Projects/foo.md": "decision", "01_Projects/old/nota.md": "proyecto"},
    "vault_quarantine": {"07_Knowledge/rara.md": "nota"},
    # `--path "src/"` es la raíz del código, relativa a donde se ejecuta.
    "vault_drift_detect": {"@trabajo/src/app.py": "codigo"},
    # El escáner solo escribe si encuentra algo: el ejemplo presupone código
    # con un hallazgo, no un `src/` limpio ni ausente.
    "vault_security_scan": {"@trabajo/src/app.js": "codigo_con_secreto"},
    # Lo que los dos sanadores reparan: sin el defecto, su `--apply` no tiene
    # nada que escribir y el banco no los mide.
    "vault_fix_brackets": {"02_Observability/errors/foo.md": "corchetes"},
    "vault_frontmatter_heal": {"07_Knowledge/escalar-sin-escapar.md": "yaml_roto"},
    "vault_runbook_log": {"08_Runbooks/deploy.md": "nota"},
    "vault_supersede": {"10_Migrated/GUIA.md": "nota", "07_Knowledge/guia.md": "nota"},
    "vault_propagate": {"01_Projects/mi-api/overview.md": "nota"},
    "vault_diagram_export": {"06_Diagrams/foo.md": "diagrama"},
    "vault_undo": {"01_Projects/ans/status.md": "nota"},
    "vault_write": {"@trabajo/overview.md": "texto"},
    "vault_ingest": {"@trabajo/notas.md": "texto"},
    "vault_onboard": {"@trabajo/../mi-api/README.md": "texto"},
    "vault_migrate_docs": {"@trabajo/docs/guia.md": "texto"},
}

_CONTENIDOS = {
    "nota": ("---\ntitle: Nota del ejemplo\ntype: knowledge\nstatus: draft\n"
             "tags: [ejemplo]\n---\n\n# Nota del ejemplo\n\nCuerpo.\n"),
    "diagrama": ("---\ntitle: Diagrama del ejemplo\ntype: diagram\nstatus: draft\n"
                 "tags: [ejemplo]\n---\n\n```mermaid\ngraph TD\n  A --> B\n```\n"),
    "decision": ("---\ntitle: Decision del ejemplo\ntype: decision\nstatus: draft\n"
                 "tags: [ejemplo]\n---\n\n# Decision del ejemplo\n\nCuerpo.\n"),
    "proyecto": ("---\ntitle: Proyecto del ejemplo\ntype: project\nstatus: draft\n"
                 "tags: [ejemplo]\n---\n\n# Proyecto del ejemplo\n\nCuerpo.\n"),
    "corchetes": ("---\ntitle: Error del ejemplo\ntype: error\nstatus: draft\n"
                  "tags: [ejemplo]\n---\n\n# Error del ejemplo\n\nVer [[]] y [[[[guia]]]].\n"),
    "yaml_roto": ("---\ntitle: Overview: demo\ntype: knowledge\nstatus: draft\n"
                  "tags: [ejemplo]\n---\n\n# Overview\n\nCuerpo.\n"),
    "codigo": "def principal():\n    return 1\n",
    "codigo_con_secreto": 'const password = "hunter22";\nspawn(cmd, { shell: true });\n',
    # AP-11 pide tres líneas reales a `vault_write`, y `vault_ingest` descarta
    # los bloques de menos de `MIN_CHUNK_CHARS` (120): un texto de una línea
    # no es el que el ejemplo presupone.
    "texto": ("# Texto del ejemplo\n\n"
              "Este servicio expone la API publica del proyecto y valida cada peticion "
              "contra el esquema antes de tocar la base de datos.\n"
              "Los errores se devuelven con un codigo estable y un mensaje legible.\n"
              "El despliegue se hace con la imagen etiquetada por el commit.\n"),
}



#: Tools con side effects cuyo ejemplo documentado no escribe en la copia, con
#: el motivo medido el 2026-10-17 (banco v3). Sin esto `sin_escritura` era una
#: lista suelta: una tool nueva cuyo ejemplo no hace nada se sumaba sin que
#: nadie preguntara por qué. Ahora la que no está aquí deja el banco en rojo, y
#: la que está aquí y escribió también: la declaración ya no es cierta.
SIN_ESCRITURA_DECLARADA: Dict[str, str] = {
    "vault_code_sync": "el ejemplo sincroniza un repo que el proyecto del banco no tiene enlazado; sin repo no hay nada que copiar",
    "vault_diagram_export": "mi-api no tiene diagramas propios y la línea con --path solo devuelve la configuración de exportación",
    "vault_fuente_unica": "solo lectura por diseño (regla 7): mide divergencias de AP-05 y no escribe",
    "vault_history_compact": "la copia no tiene .history/ con versiones que compactar",
    "vault_merge": "--detect es de solo lectura y la línea de fusión cita el marcador /path/to/other-vault, que no existe",
    "vault_migrate_docs": "el ejemplo corre en dry-run: informa del plan de migración sin aplicarlo",
    "vault_migrate_rollback": "no hay informe de una migración previa que deshacer",
    "vault_propagate": "--queue-report solo lee la cola de propagación",
    "vault_restore": "la copia no tiene backups; sin --confirm true la tool rehúsa (CONFIRMACION_REQUERIDA)",
    "vault_standard_upgrade": "el sandbox ya está en la versión vigente del estándar: no hay nada que subir",
    "vault_tags": "la línea del ejemplo es --ledger, de solo lectura",
    "vault_undo": "la copia no tiene historial de cambios que deshacer",
}


def _preparar(tool: str):
    """El `preparar` de `vault_smoke.run_one` para los ficheros de una tool."""
    ficheros = FICHEROS_DEL_EJEMPLO.get(tool)
    if not ficheros:
        return None

    def preparar(vault: Path, destino: Path) -> Optional[Path]:
        trabajo = destino / "trabajo"
        trabajo.mkdir()
        for clave, clase in ficheros.items():
            if clave.startswith("@trabajo/"):
                ruta = (trabajo / clave[len("@trabajo/"):]).resolve()
            else:
                ruta = (vault / clave).resolve()
            # Nada fuera del directorio desechable (AP-36).
            ruta.relative_to(destino.resolve())
            if not ruta.exists():
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(_CONTENIDOS[clase], encoding="utf-8")
        return trabajo

    return preparar


def _sandbox_con_proyecto(destino: Path) -> Path:
    """Copia del sandbox con el proyecto del ejemplo dado de alta."""
    import os
    import shutil
    import subprocess

    import vault_smoke

    vault = destino / "vault"
    shutil.copytree(vault_smoke.SANDBOX, vault, ignore=shutil.ignore_patterns(".locks"))
    slug, titulo = PROYECTO_DEL_EJEMPLO
    if not (vault / "01_Projects" / slug).exists():
        env = {**os.environ, "VAULT_ROOT": str(vault), "VAULT_STRICT_ROOT": "1",
               "VAULT_AGENT": "vault-smoke", "VAULT_VOICE": "0", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [sys.executable, str(vault_smoke.SCRIPTS_DIR / "vault_project.py"),
             "--add", slug, "--title", titulo],
            cwd=str(vault_smoke.SCRIPTS_DIR), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=vault_smoke.SMOKE_TIMEOUT)
        if proc.returncode != 0:
            # Sin el proyecto, el banco volvería a contar como «no escribe» lo
            # que no encontró su proyecto: mejor no medir que medir eso.
            raise RuntimeError(f"vault_project --add {slug} falló: {proc.stdout[-300:]}"
                               f"{proc.stderr[-300:]}")
    return vault


_MOTIVO_DEL_ESTANDAR = (
    "capacidad gobernanza_del_estandar (vault_servicio): escriben en este repo "
    "—baselines, docs derivadas, el plano— y no en el vault, y no viajan en la "
    "wheel. El banco no las ejecuta: su `--freeze` o su `--fix` reescribirían "
    "el checkout, y la foto del árbol de la copia no las vería igual."
)


def _del_estandar() -> set:
    """Tools de la capacidad que mide el repo, no las notas (`vault_servicio`).

    El 2026-10-17, la primera ronda que ejecutó todas las líneas del ejemplo
    corrió `--freeze` y `--fix` de las del meta-toolkit y reescribió tres
    baselines, `AGENTS.md` y `docs/BLUEPRINT.md` del checkout. El criterio es
    el registro de capacidades, no una lista de aquí (AP-57).
    """
    import vault_servicio

    return {fila["tool"] for fila in vault_servicio.trazabilidad()
            if fila["capability"] == "gobernanza_del_estandar"}


def ejecutado(herramientas: Optional[Dict[str, Dict]] = None) -> Dict:
    """AP-37 sobre el envelope emitido, ejecutando cada línea del ejemplo.

    Cada línea `python …` del `example` corre en su propia copia desechable,
    con el proyecto del ejemplo dado de alta y los ficheros que presupone. Una
    tool es `medida` si alguna línea escribió y todas las que escribieron lo
    dijeron; `ofensor` si una escribió y calló; `sin_escritura` si ninguna
    escribió, con lo que respondió cada línea en `lineas_sin_escritura`.
    """
    import tempfile

    import vault_smoke

    if herramientas is None:
        import vault_mcp_catalog

        herramientas = vault_mcp_catalog.TOOLS_CATALOG
    medidas: List[str] = []
    sin_escritura: List[str] = []
    lineas_sin_escritura: Dict[str, List[Dict]] = {}
    sin_invocacion: List[Dict] = []
    ofensores: List[Dict] = []
    fuera_del_vault: List[str] = []
    del_estandar = _del_estandar()
    base = Path(tempfile.mkdtemp(prefix="vault-noop-"))
    try:
        origen = _sandbox_con_proyecto(base) if PROYECTO_DEL_EJEMPLO else None
        for name, entry in sorted(herramientas.items()):
            if not entry.get("side_effects"):
                continue
            if name in del_estandar:
                fuera_del_vault.append(name)
                continue
            lineas = vault_smoke.invocations(name)
            if not lineas:
                r = vault_smoke.run_one(name, arbol=True)
                sin_invocacion.append({"tool": name,
                                       "motivo": r.get("skipped") or r.get("problem")})
                continue
            escribio = False
            callo = None
            respuestas = []
            for argv in lineas:
                r = vault_smoke.run_one(name, arbol=True, argv=argv,
                                        preparar=_preparar(name), origen=origen)
                if not r.get("cambiadas"):
                    respuestas.append({"argv": argv[2:], "tool_ok": r.get("tool_ok"),
                                       "error_code": r.get("error_code"),
                                       "problem": r.get("problem")})
                    continue
                escribio = True
                if not set(r["returned"]) & WORK_INDICATORS and callo is None:
                    callo = {"tool": name, "argv": argv[2:], "cambiadas": r["cambiadas"],
                             "returned": r["returned"]}
            if callo:
                ofensores.append(callo)
            elif escribio:
                medidas.append(name)
            else:
                sin_escritura.append(name)
                lineas_sin_escritura[name] = respuestas
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)
    sin_motivo = [t for t in sin_escritura if t not in SIN_ESCRITURA_DECLARADA]
    declaradas_que_escriben = sorted(t for t in SIN_ESCRITURA_DECLARADA
                                     if t in medidas or t in {o["tool"] for o in ofensores})
    return {
        # AP-60: sin una sola medida el banco no ha visto nada; y una tool que
        # no escribe sin motivo declarado es una que nadie ha mirado.
        "ok": (not ofensores and bool(medidas) and not sin_motivo
               and not declaradas_que_escriben),
        "tool": "vault_noop_audit",
        "norm": "AP-37",
        "modo": "ejecutado",
        "total": (len(medidas) + len(sin_escritura) + len(sin_invocacion)
                  + len(ofensores) + len(fuera_del_vault)),
        "medidas": medidas,
        "sin_escritura": sin_escritura,
        "lineas_sin_escritura": lineas_sin_escritura,
        "sin_escritura_declarada": {t: SIN_ESCRITURA_DECLARADA[t] for t in sin_escritura
                                    if t in SIN_ESCRITURA_DECLARADA},
        "sin_escritura_sin_motivo": sin_motivo,
        "declaradas_que_escriben": declaradas_que_escriben,
        "sin_invocacion": sin_invocacion,
        "ofensores": ofensores,
        "fuera_del_vault": fuera_del_vault,
        "fuera_del_vault_motivo": _MOTIVO_DEL_ESTANDAR,
    }


def load_baseline() -> List[str]:
    if not BASELINE_PATH.exists():
        return []
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return sorted(data.get("tools", []))


def scan() -> Dict:
    actuales = offenders()
    nombres = {o["tool"] for o in actuales}
    baseline = set(load_baseline())

    nuevas = sorted(nombres - baseline)      # deuda que CRECIÓ: es un fallo
    resueltas = sorted(baseline - nombres)   # deuda saldada: hay que recongelar

    return {
        # `ok` solo mira las nuevas: la deuda histórica no bloquea, pero no crece.
        "ok": not nuevas,
        "tool": "vault_noop_audit",
        "norm": "AP-37",
        "offenders_total": len(actuales),
        "baseline_size": len(baseline),
        "new_offenders": nuevas,
        "resolved_since_baseline": resueltas,
        "offenders": actuales,
    }


def freeze(admitir_nuevos: bool = False) -> Dict:
    """Recongela, y se **niega** si eso haría crecer la deuda.

    `AGENTS.md` promete esta negativa para los tres guards con baseline, y de
    los tres era el único que no la tenía: reescribía la baseline con lo que
    hubiera. Con la lista hoy en cero, una tool nueva sin indicador más un
    `--freeze` de rutina la congelaba en silencio y la puerta seguía verde —
    la deuda entra por el sitio por el que nadie mira, que es el `--freeze`.
    """
    nombres = sorted(o["tool"] for o in offenders())
    nuevas = sorted(set(nombres) - set(load_baseline()))
    if nuevas and not admitir_nuevos:
        return emit_error(
            "vault_noop_audit", "DEBT_WOULD_GROW",
            f"{len(nuevas)} tool(s) sin precedente en la baseline: congelarlas "
            f"aumentaría la deuda en silencio. Si es deliberado, "
            f"`--freeze --admitir-nuevos`. Tools: {nuevas}",
        )
    vault_baseline.escribir(
        BASELINE_PATH, "tools", "AP-37",
        "Deuda conocida de tools con side effects que no exponen "
        "indicador de trabajo. Esta lista solo puede ENCOGER.",
        nombres, extra={"norm": "AP-37"},
    )
    return {
        "ok": True,
        "tool": "vault_noop_audit",
        "frozen": len(nombres),
        "path": str(BASELINE_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_noop_audit — AP-37: no-op silencioso"
    , allow_abbrev=False)
    parser.add_argument("--check", action="store_true", help="Reporta el estado de la deuda")
    parser.add_argument("--strict", action="store_true", help="Exit 1 si la deuda creció")
    parser.add_argument("--freeze", action="store_true", help="Recongela la baseline")
    parser.add_argument(
        "--admitir-nuevos", action="store_true",
        help="Permite que --freeze congele deuda sin precedente, listándola",
    )
    parser.add_argument(
        "--ejecutado", action="store_true",
        help="Ejecuta el ejemplo de cada tool con side effects y contrasta el envelope",
    )
    args = parser.parse_args()

    if args.ejecutado:
        salida = ejecutado()
        print(json.dumps(salida, ensure_ascii=False))
        return 0 if salida["ok"] or not args.strict else 1

    if args.freeze:
        salida = freeze(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(salida, ensure_ascii=False))
        return 0 if salida.get("ok") else 1

    result = scan()
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    # `--ejecutado` dura lo que el smoke; el límite es el suyo.
    sys.exit(wrap_main(main, "vault_noop_audit", timeout=3600))
