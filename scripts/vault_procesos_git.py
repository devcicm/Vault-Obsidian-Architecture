#!/usr/bin/env python3
"""vault_procesos_git — el git del toolkit pasa por un dueño, y el dueño mira (AP-68).

## De dónde sale

Auditoría del 2026-10-23 sobre la pregunta «¿ejecuta alguna tool git sin
supervisión?». El veredicto fue que no —doce sitios de lectura, un único
mutador acotado al bootstrap de `vault_init`, cero `shell=True`, cero
`--force`— pero que **nadie lo verificaba**: la propiedad era verdad por
inspección de una tarde, no por guard. Mañana un `git clean -fdx` en una tool
entraría sin que ninguna puerta se pusoera roja.

Esa es la forma exacta de AP-57 aplicada al repo contra sí mismo: el criterio
existe, está escrito en las trece llamadas, y no lo vigila nadie.

## Qué mide esta puerta

`vault.kernel.procesos_git.sitios_git_fuera_del_dueno()` recorre por AST
`scripts/`, `cli/`, `vault/` y `mcp/` buscando toda llamada que levante git con
el léxico `"git"` primero —literal, concatenado o por variable—, y exige que
**no quede ninguna fuera de `vault/kernel/procesos_git.py`**. El runtime de la
propiedad lo aplica `ejecutar_git`, que rechaza verbos mutadores no declarados
con motivo; esta puerta mide la cobertura de esa puerta, que es lo que un
`subprocess.run(["git", ...])` nuevo podría saltarse sin que nadie lo notara.

## Qué NO demuestra el verde

Los `tests/` no entran, y el motivo está escrito en el guard: un test necesita
git crudo para fabricar el repositorio con el que va a medir, y medir una tool
con su propio ejecutor sería certificarse a sí mismo (AP-44). Tampoco ve un
argv armado con `" ".join(...)` o un f-string, ni un binario que lance git por
su cuenta. El alcance se declara en vez de suponerse.

    python scripts/vault_procesos_git.py --check
    python scripts/vault_procesos_git.py --check --strict
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault_errors import emit_error, wrap_main

from vault.kernel.procesos_git import (  # noqa: E402
    MUTADORES_AUTORIZADOS,
    VERBOS_AMBIGUOS,
    VERBOS_LECTURA,
    sitios_git_fuera_del_dueno,
)


def check() -> Dict[str, Any]:
    """Toda llamada a git que no pasa por `vault.kernel.procesos_git`.

    AP-68: el criterio es «un solo sitio ejecuta git». No es una baseline —no
    hay deuda que congelar, porque la deuda era cero cuando nació la norma y
    lo que se mide es si vuelve a aparecer—: un sitio fuera del dueño es
    deuda **nueva** por definición, y se salda mudando esa llamada al dueño.
    """
    sitios: List[str] = sitios_git_fuera_del_dueno(raiz_repo=str(Path(__file__).resolve().parent.parent))
    return {
        "ok": not sitios,
        "tool": "vault_procesos_git",
        "norm": "AP-68",
        "action": "check",
        "sites": sitios,
        "sites_total": len(sitios),
        "verbos_lectura": sorted(VERBOS_LECTURA),
        "verbos_ambiguos": sorted(VERBOS_AMBIGUOS),
        "mutadores_autorizados": MUTADORES_AUTORIZADOS,
        "alcance": {
            "raices": ["scripts", "cli", "vault", "mcp"],
            "excluidos": ["tests"],
            "motivo_tests": (
                "un test necesita git crudo para fabricar el repositorio con "
                "el que mide; medir una tool con su propio ejecutor sería "
                "certificarse a sí mismo (AP-44)"
            ),
            "no_ves": [
                "argv armado con join/f-string en vez de literal",
                "un binario que lance git por su cuenta",
            ],
        },
        "hint": (
            "Se salda moviendo la llamada al dueño: "
            "`from vault.kernel.procesos_git import ejecutar_git` y "
            "`ejecutar_git(repo, [\"log\", ...])`. Si de verdad hace falta un "
            "mutador nuevo, se autoriza en MUTADORES_AUTORIZADOS con su "
            "motivo escrito —y el diff que lo añade es la revisión—; no "
            "subiendo esta puerta ni ampliándola."
        ),
    }


def contrato() -> Dict[str, Any]:
    """Publica el criterio del dueño: qué verbos se admiten y con qué motivo.

    AP-68 no es solo una puerta que dice «no»: es una lista cerrada, y una
    lista cerrada sin publicar es indistinguible de un capricho. Esta es la
    mitad que hace la norma usable por quien llega después — qué puede pedir,
    qué no, y por qué el mutador que sí está autorizado lo está.
    """
    return {
        "ok": True,
        "tool": "vault_procesos_git",
        "norm": "AP-68",
        "action": "contrato",
        "verbos_lectura": sorted(VERBOS_LECTURA),
        "verbos_ambiguos": sorted(VERBOS_AMBIGUOS),
        "mutadores_autorizados": MUTADORES_AUTORIZADOS,
        "hint": (
            "Los ambivalentes se admiten solo con su uso de lectura: "
            "`branch -a` sí, `branch -D` no; `tag -l` sí, `tag v1` no; "
            "`config --get` sí, `config k v` no. Un mutador nuevo entra en "
            "MUTADORES_AUTORIZADOS con su motivo escrito, y ese diff es su "
            "revisión."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_procesos_git — el git del toolkit pasa por un dueño (AP-68)",
        allow_abbrev=False,
    )
    ap.add_argument("--check", action="store_true",
                    help="Lista los sitios que levantan git fuera del dueño")
    ap.add_argument("--contrato", action="store_true",
                    help="Publica qué verbos admite el dueño y con qué motivo")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 si hay algún sitio fuera del dueño")
    args = ap.parse_args()

    if args.contrato:
        print(json.dumps(contrato(), ensure_ascii=False))
        return 0

    if not args.check:
        env = emit_error(
            "vault_procesos_git", "MISSING_REQUIRED_ARG",
            "sin --check esta tool no tiene nada que hacer: no escribe nada, "
            "no decide nada, solo mide",
            pista="python scripts/vault_procesos_git.py --check --strict",
        )
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_procesos_git"))