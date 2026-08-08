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

from vault_errors import emit_error, wrap_main
from vault_firma_sitio import (
    cargar_baseline,
    escribir_baseline,
    firmar_todos,
    mapa_de_qualnames,
)

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


DESCRIPCION = (
    "Deuda conocida de envelopes de error construidos a mano, sin error_code / "
    "category / severity / recovery del ERROR_CATALOG. Incluye algunos "
    "envelopes internos que nunca se imprimen: la medida es de forma, no de "
    "flujo. Indexada por firma de sitio (módulo::función::hash del código "
    "normalizado), no por línea. Esta lista solo puede ENCOGER."
)


def offenders() -> List[Dict]:
    """Envelopes de error que no pasan por `ERROR_CATALOG`.

    La clave es la **firma** del sitio, no un contador por módulo: una baseline
    por conteo se salda arreglando un sitio y estrenando otro, que es justo la
    regresión que esto existe para ver. `line` sigue en el envelope como dato
    para ir al sitio, pero ya no es la identidad.
    """
    fuera = []
    for path in sorted(SCRIPTS_DIR.glob("vault_*.py")):
        if path.name == Path(__file__).name or path.name.startswith(EXCLUIDOS):
            continue
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        qualnames = mapa_de_qualnames(arbol)
        encontrados = []
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
            encontrados.append((nodo, sorted(claves)))
        encontrados.sort(key=lambda par: (par[0].lineno, par[0].col_offset))
        firmas = firmar_todos(
            (path.name, qualnames.get(id(n), ""), n) for n, _ in encontrados
        )
        for (nodo, claves), firma in zip(encontrados, firmas):
            fuera.append({
                "firma": firma,
                "module": path.name,
                "line": nodo.lineno,
                "site": f"{path.name}:{nodo.lineno}",  # informativo
                "keys": claves,
            })
    return fuera


def load_baseline() -> List[str]:
    """Las claves congeladas, ordenadas.

    superseded_by: `vault_firma_sitio.cargar_baseline`, que además devuelve el
    esquema y los datos crudos. Se conserva —no-derogación— porque su contrato
    sigue siendo válido: una lista de claves comparable con los sitios vivos.
    Lo que cambió es qué **es** una clave: antes `módulo:línea`, ahora la firma.
    """
    firmas, _, _ = cargar_baseline(BASELINE_PATH)
    return sorted(firmas)


def scan() -> Dict:
    actuales = offenders()
    firmas = {o["firma"] for o in actuales}
    baseline, esquema, _ = cargar_baseline(BASELINE_PATH)

    if esquema < 2:
        return emit_error(
            "vault_error_contract", "MIGRATION_REQUIRED",
            "La baseline está indexada por línea (esquema 1). Migra con "
            "`python scripts/vault_error_contract.py --migrate` antes de "
            "auditar: leerla como vacía estrenaría la deuda entera como nueva.",
        )

    nuevos = sorted(firmas - baseline)      # la deuda CRECIÓ: es un fallo
    resueltos = sorted(baseline - firmas)   # deuda saldada: hay que recongelar

    return {
        # `ok` solo mira los nuevos: la deuda histórica no bloquea, pero no crece.
        "ok": not nuevos,
        "tool": "vault_error_contract",
        "norm": "AP-52",
        "schema": esquema,
        "offenders_total": len(actuales),
        "baseline_size": len(baseline),
        "modules_affected": len({o["module"] for o in actuales}),
        "new_offenders": nuevos,
        "resolved_since_baseline": resueltos,
        "offenders": actuales,
    }


def freeze(admitir_nuevos: bool = False) -> Dict:
    """Recongela. Se niega a congelar deuda nueva salvo que se le exija.

    Con el índice por línea, `--freeze` legítimo y `--freeze` que esconde deuda
    recién estrenada se tecleaban igual, y lo único que los separaba era que
    alguien verificase tres condiciones a mano. Ahora el desplazamiento no
    genera falsos nuevos, así que un sitio nuevo es un sitio nuevo.
    """
    actuales = offenders()
    baseline, esquema, previos = cargar_baseline(BASELINE_PATH)
    firmas = {o["firma"] for o in actuales}
    nuevos = sorted(firmas - baseline)

    if nuevos and not admitir_nuevos and esquema >= 2:
        return emit_error(
            "vault_error_contract", "DEBT_WOULD_GROW",
            f"{len(nuevos)} sitio(s) sin precedente en la baseline: congelarlos "
            f"aumentaría la deuda en silencio. Si es deliberado, "
            f"`--freeze --admitir-nuevos`. Sitios: {nuevos}",
        )

    sitios = [{"firma": o["firma"], "visto_en": o["site"]} for o in actuales]
    escribir_baseline(BASELINE_PATH, "AP-52", DESCRIPCION, sitios, previos)
    return {
        "ok": True,
        "tool": "vault_error_contract",
        "frozen": len(sitios),
        "admitted_new": nuevos if admitir_nuevos else [],
        "path": str(BASELINE_PATH),
    }


def migrate() -> Dict:
    """Traduce la baseline v1 (por línea) a v2 (por firma), sin cambiar la deuda.

    Se niega si el conjunto de `módulo:línea` que ve ahora no coincide exacto
    con el congelado: migrar sobre un árbol divergente metería la deuda nueva
    en el formato nuevo como si siempre hubiera estado ahí.
    """
    _, esquema, previos = cargar_baseline(BASELINE_PATH)
    if esquema >= 2:
        return {"ok": True, "tool": "vault_error_contract",
                "already": True, "schema": esquema}

    actuales = offenders()
    v1_previa = sorted(s for s in previos.get("sites", []) if isinstance(s, str))
    v1_actual = sorted(set(o["site"] for o in actuales))
    if v1_previa != v1_actual:
        return emit_error(
            "vault_error_contract", "MIGRATION_MISMATCH",
            "La baseline v1 no coincide con lo que se mide ahora: "
            f"{len(v1_previa)} congelados vs {len(v1_actual)} actuales. "
            "Deja el árbol en verde con la v1 antes de migrar.",
        )

    sitios = [{"firma": o["firma"], "visto_en": o["site"]} for o in actuales]
    escribir_baseline(BASELINE_PATH, "AP-52", DESCRIPCION, sitios, previos)
    return {
        "ok": True, "tool": "vault_error_contract", "migrated": len(sitios),
        "from_schema": esquema, "to_schema": 2, "path": str(BASELINE_PATH),
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
    parser.add_argument("--admitir-nuevos", action="store_true",
                        help="Con --freeze: congela también sitios sin precedente")
    parser.add_argument("--migrate", action="store_true",
                        help="Traduce una baseline v1 (por línea) a v2 (por firma)")
    args = parser.parse_args()

    if args.migrate:
        resultado = migrate()
        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("ok") else 1

    if args.freeze:
        resultado = freeze(admitir_nuevos=args.admitir_nuevos)
        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("ok") else 1

    result = scan()
    print(json.dumps(result, ensure_ascii=False))
    if args.strict and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_error_contract"))
