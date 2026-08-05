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
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "noop-baseline.json"

# Campos que distinguen "hice N cosas" de "no hice nada". La lista se amplía
# deliberadamente, nunca por comodidad: añadir aquí un campo que siempre está
# presente (como `path` u `ok`) vacía la norma de contenido.
#
# `files_included` / `files_restored` entran en v39 por las dos tools base64,
# que son JS-native y no pueden usar el ledger de `vault_io.write_report()`.
# Son recuentos reales de archivos, no banderas: cero sigue significando cero.
WORK_INDICATORS = {
    "added",
    "applied",
    "changed",
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


def freeze() -> Dict:
    nombres = sorted(o["tool"] for o in offenders())
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "norm": "AP-37",
                "description": (
                    "Deuda conocida de tools con side effects que no exponen "
                    "indicador de trabajo. Esta lista solo puede ENCOGER."
                ),
                "tools": nombres,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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
    )
    parser.add_argument("--check", action="store_true", help="Reporta el estado de la deuda")
    parser.add_argument("--strict", action="store_true", help="Exit 1 si la deuda creció")
    parser.add_argument("--freeze", action="store_true", help="Recongela la baseline")
    args = parser.parse_args()

    if args.freeze:
        print(json.dumps(freeze(), ensure_ascii=False))
        return 0

    result = scan()
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_noop_audit"))
