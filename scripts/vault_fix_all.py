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

1. `vault_mcp_catalog --sync` — regenera `tools-catalog.json` desde el catálogo
   Python. Todo lo que cuenta tools/grupos después lee este JSON.
2. `vault_arch --sync-env` — regenera `env-table.json` desde `vault_entorno`.
3. `vault_spec_catalog_check --freeze-fields` — congela los campos estables del
   tool-spec en la baseline. El blueprint muestra esta baseline.
4. `vault_arch --blueprint` — regenera `docs/ARQUITECTURA.md` desde CONTEXTS.
5. `vault_blueprint --blueprint` — regenera `docs/BLUEPRINT.md` desde los
   registros (incluida la baseline del paso 3).
6. `vault_doc_counts --fix` — reescribe las cifras de la documentación desde los
   valores vivos (tools, scripts, tests).
7. `vault_doc_sync --fix` — regenera la tabla de índice de `scripts/README.md`
   desde `GROUPS`.

## Uso

    python vault_fix_all.py            # regenera todo
    python vault_fix_all.py --dry-run  # muestra el plan sin ejecutar
    python vault_fix_all.py --step N   # ejecuta solo el paso N (1-7)

Devuelve un envelope con el resultado de cada paso: `ok` si todos terminaron con
exit 0. Un paso que falla no detiene los siguientes: el reporte lista cuáles
fallaron para que se vean todos de una vez.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_errors import emit_error
from vault_subproceso import ejecutar

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Cada paso es (nombre, [argv]). La lista de argv se une al intérprete actual
#: y al script que lo ejecuta: `[sys.executable, str(SCRIPTS_DIR / script), *args]`.
PASOS: List[Dict[str, Any]] = [
    {
        "nombre": "tools_catalog",
        "script": "vault_mcp_catalog.py",
        "args": ["--sync"],
        "por_que": "regenera tools-catalog.json desde el catálogo Python",
    },
    {
        "nombre": "env_table",
        "script": "vault_arch.py",
        "args": ["--sync-env"],
        "por_que": "regenera env-table.json desde vault_entorno",
    },
    {
        "nombre": "field_compat",
        "script": "vault_spec_catalog_check.py",
        "args": ["--freeze-fields"],
        "por_que": "congela los campos estables del tool-spec en la baseline",
    },
    {
        "nombre": "esquemas",
        "script": "vault_esquema.py",
        "args": ["--sync"],
        "por_que": "regenera schemas/ desde vault_contrato_nota",
    },
    {
        "nombre": "metricas",
        "script": "vault_metricas.py",
        "args": ["--doc"],
        "por_que": "regenera docs/METRICAS.md desde el registro y el histórico",
    },
    {
        "nombre": "arquitectura",
        "script": "vault_arch.py",
        "args": ["--blueprint"],
        "por_que": "regenera docs/ARQUITECTURA.md desde CONTEXTS",
    },
    {
        "nombre": "blueprint",
        "script": "vault_blueprint.py",
        "args": ["--blueprint"],
        "por_que": "regenera docs/BLUEPRINT.md desde los registros",
    },
    {
        "nombre": "doc_counts",
        "script": "vault_doc_counts.py",
        "args": ["--fix"],
        "por_que": "reescribe las cifras de la documentación desde los valores vivos",
    },
    {
        "nombre": "doc_sync",
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


def fix_all(dry_run: bool = False, solo_paso: int | None = None) -> Dict[str, Any]:
    """Ejecuta los pasos en orden y devuelve un envelope con el resultado."""
    pasos_a_correr = list(enumerate(PASOS, start=1))
    if solo_paso is not None:
        pasos_a_correr = [(n, p) for n, p in pasos_a_correr if n == solo_paso]

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
        }

    resultados = [_ejecutar_paso(p, n) for n, p in pasos_a_correr]
    fallidos = [r for r in resultados if not r["ok"]]
    return {
        "ok": not fallidos,
        "tool": "vault_fix_all",
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
    ap.add_argument("--step", type=int, metavar="N", help="ejecuta solo el paso N (1-7)")
    args = ap.parse_args()

    result = fix_all(dry_run=args.dry_run, solo_paso=args.step)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
