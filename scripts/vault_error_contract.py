#!/usr/bin/env python3
"""vault_error_contract — AP-52: el error se emite fuera del contrato del catálogo.

Salió de la caracterización maliciosa: invocar cada tool de forma malformada y
mirar **cómo** falla, no si falla. Dos sondas sobre las 94 tools —invocación
vacía y flag desconocido— dejaron el grueso limpio (45/45 de las tools con
`required_args` rechazan por argparse) y destaparon otra cosa:

    $ python scripts/vault_merge.py
    {"ok": false, "error": "action='merge' requires --source"}

Ese envelope es correcto como frase y roto como contrato. `vault_errors.emit_error`
produce `error_code`, `category`, `severity`, `recovery` y `timestamp` a partir de
`ERROR_CATALOG`; un `{"ok": False, "error": "..."}` escrito a mano no produce
ninguno. El consumidor que hace `switch (envelope.error_code)` —que es el modo en
que el servidor MCP y `cli/` deciden si reintentar, abortar o pedir permiso— no ve
nada, y un fallo con recuperación conocida se vuelve un fallo opaco.

Es AP-05 sobre el **contrato de error**: hay un registro que declara cómo se
nombra y se recupera cada fallo, y 158 sitios que deciden por su cuenta. Y es
AP-51 vista desde el otro lado: allí el fallo se disfrazaba de dato; aquí llega
como fallo, pero desnudo de todo lo que lo hace accionable.

    python scripts/vault_error_contract.py --check    # sitios fuera de contrato
    python scripts/vault_error_contract.py --strict   # exit 1 si la deuda CRECIÓ
    python scripts/vault_error_contract.py --freeze   # recongela la baseline

## Por qué nace con baseline

158 sitios en 60 módulos. Misma razón que AP-37 (que empezó en 55 y llegó a 0) y
que AP-51: un guard que falla en 158 sitios se desactiva el primer día, y un
guard desactivado no protege nada. La baseline **solo puede encoger**.

## Qué se mide, y qué se acepta no ver

Se mide la **forma del literal**: un `dict` con `"ok": False` que además lleva
`error`, `message` o `tool` —es decir, algo con pinta de envelope— y no lleva
`error_code`. No se mide si ese dict llega de verdad a stdout, porque eso exige
seguir el valor por el flujo del programa y un análisis a medias produciría
falsos negativos silenciosos, que es peor que un falso positivo visible.

La consecuencia se declara en vez de esconderse: **algunos sitios contados son
envelopes internos que nunca se imprimen.** Están en la baseline, no bloquean, y
cuando alguien salde su módulo los verá y decidirá. Un guard que promete
precisión que no tiene es la clase de afirmación no falsable que AP-37 persigue.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from vault_errors import wrap_main

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE_PATH = SCRIPTS_DIR / "error-contract-baseline.json"

#: Claves que delatan que el dict es un envelope de salida y no una estructura
#: interna cualquiera que casualmente tiene un `ok`.
MARCAS_DE_ENVELOPE = {"error", "message", "tool"}

#: `vault_errors*` define el contrato; sus literales SON la definición, no una
#: infracción de ella. Excluirse a sí misma es lo mismo que hace
#: `vault_blame_audit`, y por el mismo motivo.
EXCLUIDOS = ("vault_errors",)


def _valor_de(nodo: ast.Dict, clave: str):
    for k, v in zip(nodo.keys, nodo.values):
        if isinstance(k, ast.Constant) and k.value == clave:
            return v
    return None


def _claves(nodo: ast.Dict) -> set:
    return {
        k.value for k in nodo.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    }


def offenders() -> List[Dict]:
    """Envelopes de error que no pasan por `ERROR_CATALOG`.

    La clave es `modulo:linea`, no un contador por módulo: una baseline por
    conteo se salda arreglando un sitio y estrenando otro, que es justo la
    regresión que esto existe para ver.
    """
    fuera = []
    for path in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        if path.name == Path(__file__).name or path.name.startswith(EXCLUIDOS):
            continue
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Dict):
                continue
            claves = _claves(nodo)
            if "error_code" in claves:
                continue
            if not (MARCAS_DE_ENVELOPE & claves):
                continue
            ok = _valor_de(nodo, "ok")
            if not (isinstance(ok, ast.Constant) and ok.value is False):
                continue
            fuera.append({
                "site": f"{path.name}:{nodo.lineno}",
                "module": path.name,
                "line": nodo.lineno,
                "keys": sorted(claves),
            })
    return fuera


def load_baseline() -> List[str]:
    if not BASELINE_PATH.exists():
        return []
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return sorted(data.get("sites", []))


def scan() -> Dict:
    actuales = offenders()
    sitios = {o["site"] for o in actuales}
    baseline = set(load_baseline())

    nuevos = sorted(sitios - baseline)      # la deuda CRECIÓ: es un fallo
    resueltos = sorted(baseline - sitios)   # deuda saldada: hay que recongelar

    return {
        # `ok` solo mira los nuevos: la deuda histórica no bloquea, pero no crece.
        "ok": not nuevos,
        "tool": "vault_error_contract",
        "norm": "AP-52",
        "offenders_total": len(actuales),
        "baseline_size": len(baseline),
        "modules_affected": len({o["module"] for o in actuales}),
        "new_offenders": nuevos,
        "resolved_since_baseline": resueltos,
        "offenders": actuales,
    }


def freeze() -> Dict:
    sitios = sorted(o["site"] for o in offenders())
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "norm": "AP-52",
                "description": (
                    "Deuda conocida de envelopes de error construidos a mano, "
                    "sin error_code / category / severity / recovery del "
                    "ERROR_CATALOG. Incluye algunos envelopes internos que "
                    "nunca se imprimen: la medida es de forma, no de flujo. "
                    "Esta lista solo puede ENCOGER."
                ),
                "sites": sitios,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "tool": "vault_error_contract",
        "frozen": len(sitios),
        "path": str(BASELINE_PATH),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_error_contract — AP-52: el error emitido fuera del contrato del catálogo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python scripts/vault_error_contract.py --check
  python scripts/vault_error_contract.py --check --strict
  python scripts/vault_error_contract.py --freeze     # tras saldar deuda

Qué cuenta como infracción:

  return {"ok": False, "error": "falta --source"}     -> SI. El consumidor no
                                                         puede decidir si
                                                         reintentar: no hay
                                                         error_code ni recovery.

  print(json.dumps(emit_error(tool, "MISSING_ARG")))  -> NO. Sale del catálogo
                                                         con codigo, categoria,
                                                         severidad y recovery.
""",
    )
    parser.add_argument("--check", action="store_true",
                        help="Reporta el estado de la deuda")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 si la deuda creció")
    parser.add_argument("--freeze", action="store_true",
                        help="Recongela la baseline tras saldar deuda")
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
    sys.exit(wrap_main(main, "vault_error_contract"))
