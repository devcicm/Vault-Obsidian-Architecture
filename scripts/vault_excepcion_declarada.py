#!/usr/bin/env python3
"""vault_excepcion_declarada — el guard cae con el dato que vino a medir (AP-61).

## De dónde sale

`RecursionError` **no hereda de `yaml.YAMLError`**. El parser de PyYAML es
recursivo y el frontmatter es dato externo, así que `x: [[[[[…` —doce caracteres
de escribir— desborda la pila DENTRO de `safe_load`. Un `except yaml.YAMLError`
alrededor de esa llamada parece contener el fallo y no lo contiene: la excepción
sube entera y **una sola nota hostil tumba el barrido completo del vault**, no
la lectura de esa nota.

`vault_lib.parse_frontmatter` lo resolvió en su día y lo dejó escrito. Lo que
nadie estaba mirando es que el mismo `try` estaba copiado en otros doce sitios
—`vault_foreign_check`, que es la tool de la regla 7; `vault_fuente_unica`, que
corre contra vaults ajenos con `--root`; los cuatro heal de AP-46; los cinco de
`vault_frontmatter_heal`— y ninguno se enteró de la corrección. Un criterio
copiado envejece por su lado (AP-57); aquí además envejeció hacia el lado que
deja caer la tool.

## Qué se mide, exactamente

Un handler es infractor cuando **captura la excepción declarada de una librería
y deja escapar la que esa librería lanza de verdad**. Los pares están en
`RIESGOS`, con la llamada que los dispara: hoy `yaml.safe_load` / `yaml.load`,
que declaran `YAMLError` y también lanzan `RecursionError`. El registro es la
superficie de crecimiento: un par nuevo es una fila, no una tool nueva.

## Qué NO demuestra el verde

Solo ve el `try` cuyo **cuerpo** contiene la llamada de riesgo escrita a la
vista. Un `safe_load` detrás de un helper —`leer_yaml(p)`— queda fuera, y es la
forma correcta de escribirlo, así que este guard tiene un sesgo declarado: mide
mejor el código que peor está escrito. Tampoco valida que la contención sea
*correcta*, solo que la excepción esté nombrada.

    python scripts/vault_excepcion_declarada.py --check --strict
    python scripts/vault_excepcion_declarada.py --freeze     # solo puede encoger
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
from vault_arch import arboles_medidos, clave_de_modulo
from vault_errors import emit_error, wrap_main
from vault_firma_sitio import firmar_todos, mapa_de_qualnames

BASELINE = Path(__file__).parent / "excepcion-declarada-baseline.json"

#: Cada fila: la llamada que hay que ver en el `try`, la excepción que la
#: librería **declara**, y la que lanza de verdad sin heredar de la anterior.
#: `dueño` es quien ya tiene el criterio escrito, para que la corrección sea
#: delegar y no copiar (AP-57).
RIESGOS = (
    {
        "llamadas": ("safe_load", "yaml.load"),
        "declarada": "YAMLError",
        "escapa": "RecursionError",
        "dueño": "vault_lib.parse_frontmatter",
        "por_que": (
            "el parser de PyYAML es recursivo y RecursionError no hereda de "
            "YAMLError: un frontmatter muy anidado sube por encima del handler"
        ),
    },
)


def _tipos(handler: ast.ExceptHandler) -> List[str]:
    """Los nombres capturados, tal como están escritos.

    Se compara por texto —`yaml.YAMLError` y `YAMLError` valen igual— porque el
    alias con que se importó no cambia qué se está capturando, y resolverlo
    exigiría un análisis de imports que aquí no aporta nada.
    """
    tipo = handler.type
    if tipo is None:
        return ["bare"]
    if isinstance(tipo, ast.Tuple):
        return [ast.unparse(e) for e in tipo.elts]
    return [ast.unparse(tipo)]


def offenders() -> List[Dict[str, Any]]:
    """Handlers que capturan la declarada y dejan escapar la que sí llega."""
    fuera: List[Dict[str, Any]] = []
    for path in arboles_medidos():
        if path.name == Path(__file__).name:
            continue
        try:
            arbol = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        nombre = clave_de_modulo(path)
        qualnames = mapa_de_qualnames(arbol)
        encontrados = []
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Try):
                continue
            cuerpo = "\n".join(ast.unparse(s) for s in nodo.body)
            for riesgo in RIESGOS:
                if not any(l in cuerpo for l in riesgo["llamadas"]):
                    continue
                for handler in nodo.handlers:
                    tipos = _tipos(handler)
                    captura = any(riesgo["declarada"] in t for t in tipos)
                    contiene = any(riesgo["escapa"] in t for t in tipos)
                    if captura and not contiene:
                        encontrados.append((handler, riesgo))
        encontrados.sort(key=lambda par: par[0].lineno)
        firmas = firmar_todos(
            (nombre, qualnames.get(id(h), ""), h) for h, _ in encontrados
        )
        for (handler, riesgo), firma in zip(encontrados, firmas):
            fuera.append({
                "firma": firma,
                "module": nombre,
                "line": handler.lineno,
                "site": f"{nombre}:{handler.lineno}",  # informativo
                "declared": riesgo["declarada"],
                "escapes": riesgo["escapa"],
                "owner": riesgo["dueño"],
            })
    return fuera


DESCRIPCION = (
    "Handlers que capturan la excepción declarada de una librería y dejan "
    "escapar la que esa librería lanza de verdad (AP-61). Indexada por firma "
    "de sitio, no por línea. Esta lista solo puede ENCOGER. Nace vacía: los "
    "doce sitios que había se corrigieron en v40.23 en vez de congelarse."
)


def check() -> Dict[str, Any]:
    actuales = offenders()
    firmas = {o["firma"] for o in actuales}
    # `vault_firma_sitio.cargar_baseline` lee la lista bajo `sites`, y esta
    # baseline la escribe bajo `sitios`. Nació vacía en v40.23, así que el
    # desajuste no dio la cara: el primer `--freeze` habría escrito firmas que
    # `check` no encontraría, y todo lo congelado saldría como nuevo en la
    # ejecución siguiente. Es exactamente el caso raro por el que la carga tiene
    # dueño desde v40.24 — la clave se declara aquí y se lee una sola vez.
    base = vault_baseline.firmas(BASELINE, "sitios", "AP-61")
    nuevos = sorted(firmas - base)
    return {
        "ok": not nuevos,
        "tool": "vault_excepcion_declarada",
        "norm": "AP-61",
        "action": "check",
        "risks_measured": [r["escapa"] for r in RIESGOS],
        "sites": sorted(o["site"] for o in actuales),
        "sites_total": len(actuales),
        "baseline_size": len(base),
        "new_sites": nuevos,
        "resolved_since_baseline": sorted(base - firmas),
        "hint": (
            "Se salda delegando en el dueño que ya lo contuvo —"
            + ", ".join(r["dueño"] for r in RIESGOS)
            + "— o nombrando la excepción que escapa y citando al dueño en un "
            "comentario. Verde aquí no prueba que la tool aguante cualquier "
            "dato: prueba que ningún handler nombra la excepción equivocada en "
            "un `try` donde la llamada de riesgo está a la vista."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    actuales = offenders()
    firmas = sorted({o["firma"] for o in actuales})
    base = vault_baseline.firmas(BASELINE, "sitios", "AP-61")
    nuevos = sorted(set(firmas) - base)
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_excepcion_declarada", "freeze", "new_sites", nuevos,
            "Contén la excepción que escapa. Si de verdad hay que congelar "
            "deuda nueva, `--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(BASELINE, "sitios", "AP-61", DESCRIPCION, firmas,
                            extra={"schema": 2})
    return {"ok": True, "tool": "vault_excepcion_declarada", "action": "freeze",
            "frozen": len(firmas),
            "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_excepcion_declarada — la excepción que escapa (AP-61)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and args.check:
        env = emit_error("vault_excepcion_declarada", "CONFLICTING_ARGS",
                         "--freeze y --check piden cosas distintas: o mide o congela")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = freeze(args.admitir_nuevos) if args.freeze else check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_excepcion_declarada"))
