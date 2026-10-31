#!/usr/bin/env python3
"""vault_fix_all — regenera todos los artefactos derivados en el orden correcto.

## Por qué existe (v40.34)

Los registros canónicos del repo viven en Python; los documentos y JSON que se
derivan de ellos se regeneran con comandos sueltos. Hasta ahora cada uno se
ejecutaba a mano, y el orden importaba: `vault_arch --sync-env` depende de
`vault_entorno`, `vault_blueprint --blueprint` lee las baselines que
`--freeze-fields` acaba de escribir, y `vault_doc_counts --fix` cuenta los
tools del catálogo que `--sync` regenera. Un paso en orden equivocado deja el
repo con derivados stale y una puerta en rojo que no se explica sola.

Esto es infraestructura de mantenimiento, no una puerta más: no mide nada, solo
orquesta. No cambia ninguna regla del vault; cierra el loop de drift que hacía
que los derivados quedaran atrás tras cada cambio.

## El orden (y por qué)

El orden es el de `PASOS` y se lee ahí; aquí van las dependencias que lo
fijan, por nombre y no por número —el «1-7» que este docstring llevó hasta
v41.25 caducó en cuanto entraron `esquemas`, `metricas` y `caras_de_norma`
(AP-47):

- `tools_catalog` va primero: todo lo que cuenta tools o grupos después lee
  `tools-catalog.json`.
- `field_compat` congela la baseline de campos que `blueprint` publica.
- `arquitectura` y `blueprint` regeneran sus planos desde los registros.
- `doc_counts` reescribe las cifras desde los valores vivos, incluidos los
  que los pasos anteriores acaban de escribir.
- `caras_de_norma` va al final: apunta a funciones que el resto ya dejó en
  su sitio.

## Solo lo que cambió (`--staged`, v41.26)

El pre-commit corría los diez pasos en cada commit: unos 32 s medidos el
2026-10-31, más una segunda corrida `--dry-run` que no servía para nada. Y de
los últimos 297 commits, 126 no tocaban código y 45 solo tocaban tests. Cada
paso declara sus `insumos` —prefijos de ruta del repo— y con `--staged` se
omite el que no tiene ninguno en el staging. `None` es «siempre»: lo llevan
los pasos cuyos insumos son el repo entero (`blueprint`, `doc_counts`).

Lo que un paso escribe (`salidas`) cuenta como cambiado para los siguientes,
así que la cadena se propaga sola. Omitir no es certificar: las puertas de
nivel `rapida` del carril `dev` comprueban cada derivado, y un insumo que
falte aquí se ve allí en rojo, no en silencio. Sin git, `--staged` corre todo
y lo dice.

## Uso

    python vault_fix_all.py            # regenera todo
    python vault_fix_all.py --dry-run  # muestra el plan sin ejecutar
    python vault_fix_all.py --step N   # ejecuta solo el paso N de PASOS
    python vault_fix_all.py --staged   # solo los pasos con insumos en el staging

Devuelve un envelope con el resultado de cada paso: `ok` si todos terminaron con
exit 0. Un paso que falla no detiene los siguientes: el reporte lista cuáles
fallaron para que se vean todos de una vez.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_errors import emit_error
from vault_subproceso import ejecutar

from vault.kernel import procesos_git

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Cada paso es (nombre, [argv]). La lista de argv se une al intérprete actual
#: y al script que lo ejecuta: `[sys.executable, str(SCRIPTS_DIR / script), *args]`.
#: `insumos` son los prefijos de ruta que, si cambian, obligan a correrlo
#: (`None`: siempre); `salidas`, lo que escribe, que cuenta como cambiado para
#: los pasos que vienen detrás.
PASOS: List[Dict[str, Any]] = [
    {
        "nombre": "tools_catalog",
        "insumos": ("scripts/", "vault/", "cli/", "mcp/", "vault_toolkit/"),
        "salidas": ("mcp/nodejs/tools-catalog.json", "vault/meta_toolkit/tools-catalog.json"),
        "script": "vault_mcp_catalog.py",
        "args": ["--sync"],
        "por_que": "regenera tools-catalog.json desde el catálogo Python",
    },
    {
        "nombre": "env_table",
        "insumos": ("scripts/", "vault/", "mcp/"),
        "salidas": ("mcp/nodejs/env-table.json",),
        "script": "vault_arch.py",
        "args": ["--sync-env"],
        "por_que": "regenera env-table.json desde vault_entorno",
    },
    {
        "nombre": "field_compat",
        "insumos": ("scripts/", "vault/", "vault-sandbox/00_System/"),
        "salidas": ("scripts/field-compat-baseline.json",),
        "script": "vault_spec_catalog_check.py",
        "args": ["--freeze-fields"],
        "por_que": "congela los campos estables del tool-spec en la baseline",
    },
    {
        "nombre": "esquemas",
        "insumos": ("scripts/", "vault/", "schemas/"),
        "salidas": ("schemas/",),
        "script": "vault_esquema.py",
        "args": ["--sync"],
        "por_que": "regenera schemas/ desde vault_contrato_nota",
    },
    {
        "nombre": "metricas",
        "insumos": ("scripts/", "vault/", "docs/METRICAS.md"),
        "salidas": ("docs/METRICAS.md",),
        "script": "vault_metricas.py",
        "args": ["--doc"],
        "por_que": "regenera docs/METRICAS.md desde el registro y el histórico",
    },
    {
        "nombre": "arquitectura",
        "insumos": ("scripts/", "vault/", "cli/", "mcp/", "vault_toolkit/", "docs/ARQUITECTURA.md"),
        "salidas": ("docs/ARQUITECTURA.md",),
        "script": "vault_arch.py",
        "args": ["--blueprint"],
        "por_que": "regenera docs/ARQUITECTURA.md desde CONTEXTS",
    },
    {
        "nombre": "blueprint",
        "insumos": None,
        "salidas": ("docs/BLUEPRINT.md",),
        "script": "vault_blueprint.py",
        "args": ["--blueprint"],
        "por_que": "regenera docs/BLUEPRINT.md desde los registros",
    },
    {
        "nombre": "doc_counts",
        "insumos": None,
        "salidas": (),
        "script": "vault_doc_counts.py",
        "args": ["--fix"],
        "por_que": "reescribe las cifras de la documentación desde los valores vivos",
    },
    {
        "nombre": "doc_sync",
        "insumos": ("scripts/",),
        "salidas": ("scripts/README.md",),
        "script": "vault_doc_sync.py",
        "args": ["--fix"],
        "por_que": "regenera la tabla de índice de scripts/README.md",
    },
    {
        # v41.21. `guard.py` y `heal.py` de cada paquete de norma son
        # derivados: apuntan a las funciones que nombran la norma en su
        # cuerpo. Su dueño es el motor de normas, y hasta aquí el fixer no lo
        # llamaba — así que cambiar una tool que nombra su norma dejaba la
        # cara desfasada hasta que la suite lo decía (medido el 2026-10-23
        # con `--contrato` en vault_procesos_git: cinco tests en rojo por un
        # artefacto que el fixer decía cerrar).
        "nombre": "caras_de_norma",
        "insumos": ("scripts/", "vault/", "cli/", "normas/"),
        "salidas": ("normas/",),
        "modulo": "vault_norms_engine",
        "funcion": "escribir_caras_derivadas",
        "por_que": "regenera normas/*/guard.py y heal.py desde las funciones que "
                   "nombran cada norma (regla 3: doc derivada)",
    },
]


def _ejecutar_paso(paso: Dict[str, Any], paso_n: int) -> Dict[str, Any]:
    if paso.get("modulo"):
        # Un paso sin CLI: el dueño del artefacto expone una función, no un
        # script. El intérprete imprime su envelope para que el fixer lo
        # registre igual que los demás — un paso que no publica lo que hizo
        # es indistinguible de uno que no corrió (AP-37).
        cmd = [sys.executable, "-c",
               "import json,sys;"
               f"sys.path.insert(0, r'{REPO_ROOT / 'scripts'}');"
               f"import {paso['modulo']} as m;"
               f"print(json.dumps(m.{paso['funcion']}(), ensure_ascii=False))"]
    else:
        cmd = [sys.executable, str(REPO_ROOT / "scripts" / paso["script"]), *paso["args"]]
    try:
        r = ejecutar(
            cmd, cwd=str(REPO_ROOT),
            capture_output=True, timeout=180,
        )
    except (OSError, TimeoutError) as e:
        return {
            **emit_error(
                "vault_fix_all", "SERVICE_UNAVAILABLE",
                f"no se pudo ejecutar {paso.get('script') or paso.get('modulo')}: {e}",
            ),
            "paso": paso_n,
            "nombre": paso["nombre"],
            "por_que": paso["por_que"],
        }
    ok = r.returncode == 0
    salida = r.stdout.strip()
    detalle = None
    if salida:
        try:
            detalle = json.loads(salida)
        except ValueError:
            # No es JSON: se conserva como texto. Se limpia el carácter de
            # reemplazo UTF-8 (`\ufffd`) para que el envelope imprima en
            # consolas cp1252 (Windows) sin reventar.
            detalle = salida.replace("\ufffd", "?").replace("\u00a0", " ")[:300]
    return {
        "paso": paso_n,
        "nombre": paso["nombre"],
        "ok": ok,
        "por_que": paso["por_que"],
        "exit_code": r.returncode,
        "detalle": detalle,
    }


def ficheros_en_staging() -> Optional[List[str]]:
    """Lo que el commit en curso lleva, o `None` si git no lo dice."""
    try:
        r = procesos_git.ejecutar_git(
            REPO_ROOT, ["diff", "--cached", "--name-only", "-z"],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError, procesos_git.GitProhibido):
        return None
    if r.returncode != 0:
        return None
    return [f for f in r.stdout.split("\0") if f]


def _toca(cambiados: Set[str], prefijos: Tuple[str, ...]) -> bool:
    return any(f.startswith(p) for f in cambiados for p in prefijos)


def _seleccionar(pasos: List[Tuple[int, Dict[str, Any]]],
                 cambiados: Optional[List[str]]):
    """Parte `pasos` en los que corren y los omitidos, sin ejecutar nada.

    Lo que escribe un paso que corre cuenta como cambiado para los siguientes,
    así que la selección es la misma con y sin `--dry-run`: el plan publica lo
    que la corrida haría, no una lista distinta.
    """
    if cambiados is None:
        return pasos, []
    vistos = set(cambiados)
    corren: List[Tuple[int, Dict[str, Any]]] = []
    omitidos: List[Dict[str, Any]] = []
    for n, p in pasos:
        if p["insumos"] is not None and not _toca(vistos, p["insumos"]):
            omitidos.append({"paso": n, "nombre": p["nombre"],
                             "why": "ninguno de sus insumos está en el cambio"})
            continue
        corren.append((n, p))
        vistos.update(p["salidas"])
    return corren, omitidos


def fix_all(dry_run: bool = False, solo_paso: int | None = None,
            cambiados: Optional[List[str]] = None) -> Dict[str, Any]:
    """Ejecuta los pasos en orden y devuelve un envelope con el resultado.

    Con `cambiados` (rutas relativas al repo, con `/`) se omite cada paso
    cuyos insumos no aparecen ahí; sin él, corren todos.
    """
    pasos_a_correr = list(enumerate(PASOS, start=1))
    if solo_paso is not None:
        pasos_a_correr = [(n, p) for n, p in pasos_a_correr if n == solo_paso]
    pasos_a_correr, omitidos = _seleccionar(pasos_a_correr, cambiados)

    if dry_run:
        return {
            "ok": True,
            "tool": "vault_fix_all",
            "dry_run": True,
            "written": 0,
            "plan": [
                {"paso": n, "nombre": p["nombre"],
                 # Un paso es un script con args o un módulo con función: el
                 # plan publica lo que hay, no lo que el primero de los dos
                 # tenía (v41.21).
                 **({"script": p["script"], "args": p["args"]}
                    if p.get("script") else
                    {"modulo": p["modulo"], "funcion": p["funcion"]})}
                for n, p in pasos_a_correr
            ],
            "omitted": omitidos,
        }

    resultados = [_ejecutar_paso(p, n) for n, p in pasos_a_correr]
    fallidos = [r for r in resultados if not r["ok"]]
    return {
        "ok": not fallidos,
        "tool": "vault_fix_all",
        "omitted": omitidos,
        "written": len(resultados) - len(fallidos),
        "steps_total": len(resultados),
        "steps_ok": len(resultados) - len(fallidos),
        "steps_failed": len(fallidos),
        "results": resultados,
        "failed": [{"paso": r["paso"], "nombre": r["nombre"]} for r in fallidos],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_fix_all — regenera todos los artefactos derivados del registro"
    , allow_abbrev=False)
    ap.add_argument("--dry-run", action="store_true", help="muestra el plan sin ejecutar")
    ap.add_argument("--step", type=int, metavar="N",
                    help=f"ejecuta solo el paso N de PASOS (1-{len(PASOS)})")
    ap.add_argument("--staged", action="store_true",
                    help="omite los pasos sin insumos en el staging (lo usa el pre-commit); "
                         "sin git, corre todos y lo dice")
    args = ap.parse_args()

    cambiados = ficheros_en_staging() if args.staged else None
    result = fix_all(dry_run=args.dry_run, solo_paso=args.step, cambiados=cambiados)
    if args.staged:
        result["staged"] = cambiados is not None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
