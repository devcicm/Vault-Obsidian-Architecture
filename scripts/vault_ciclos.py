#!/usr/bin/env python3
"""vault_ciclos — el ciclo que se esquiva con un import diferido (AP-58).

## De dónde sale

Este repo declaraba **cero ciclos de importación**, y era verdad leyendo solo
los `import` de nivel de módulo. El cero estaba fabricado: 92 imports metidos
dentro del cuerpo de una función, en 40 módulos. Mover un import hacia dentro es
el rompe-ciclos manual, y aplicado 92 veces deja de ser una excepción para
convertirse en la arquitectura — pero no aparece en ninguna medida, porque la
medida solo miraba el nivel superior.

Contando esas aristas aparece lo que había: un componente fuertemente conexo de
14 módulos que contiene el núcleo entero, y otro de 2. El de 14 es el que hacía
que `vault_errors_trace` —un escritor de trazas de bajo nivel— importase
`vault_io` entero, y el que obligaba a `cli/runner.py` a aislar cada tool en un
subproceso.

## Qué se cuenta como deuda, y por qué no las 92

Un import diferido no es un defecto por sí mismo: se difiere también por coste
de arranque, por dependencia opcional o porque solo hace falta en una rama rara.
Lo que sí es deuda es el que **esquiva un ciclo**: aquel cuyo destino puede
volver al origen siguiendo el grafo completo. Medido en v40.17: **30 de 92**.

Congelar las 92 habría dado un número más grande y una señal peor. Una baseline
llena de aristas benignas es ruido que nadie revisa, y el día que una de verdad
importante entre ahí no se distinguirá del resto. Se cuentan las 30; las otras
62 se publican como `deferred_benign` para que el dato no desaparezca.

## Qué NO demuestra el verde

Mide el grafo **estático de módulos de `scripts/`**. No ve `importlib`, ni un
import construido con una cadena, ni el acoplamiento que pasa por el sistema de
ficheros o por una variable global compartida. Dos módulos pueden estar atados
sin que ningún `import` lo diga, y esta tool los verá sueltos. Verde aquí
significa que no crecieron los ciclos que sabemos ver.

    python scripts/vault_ciclos.py --check --strict
    python scripts/vault_ciclos.py --freeze     # solo puede encoger
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))

import vault_grafo_import
from vault_errors import emit_error, wrap_main

BASELINE = Path(__file__).parent / "ciclos-baseline.json"
DIRECTORIO = Path(__file__).parent


def _modulos() -> Set[str]:
    """superseded_by: vault_grafo_import.modulos (v40.20).

    Se conserva porque lo llama `_completo()` y porque el contrato de lectura no
    cambia; el cuerpo ya no decide nada.
    """
    return vault_grafo_import.modulos()


def _grafo() -> Dict[str, Dict[str, Set[str]]]:
    """Aristas de import, separadas por dónde está el `import`.

    superseded_by: vault_grafo_import.grafo (v40.20). Hasta entonces el cuerpo
    vivía aquí y `vault_arch._importaciones` respondía a la misma pregunta con
    otro criterio —relativos y prefijo `vault_`—: el mismo criterio escrito dos
    veces, sin dueño y sin nadie comparándolo, que es AP-57 en el análisis
    estructural del propio repo. La proyección `MODULOS_LOCALES` es la de aquí,
    con su nombre y su semántica intactas.
    """
    return vault_grafo_import.grafo()


def _completo(g: Dict[str, Dict[str, Set[str]]]) -> Dict[str, Set[str]]:
    return {m: g["top"].get(m, set()) | g["diferido"].get(m, set())
            for m in _modulos()}


def _componentes(G: Dict[str, Set[str]]) -> List[List[str]]:
    """Tarjan iterativo. Recursivo reventaba la pila con 129 módulos."""
    idx: Dict[str, int] = {}
    low: Dict[str, int] = {}
    en_pila: Set[str] = set()
    pila: List[str] = []
    fuera: List[List[str]] = []
    contador = [0]

    def visitar(raiz: str) -> None:
        marco = [(raiz, iter(sorted(G.get(raiz, ()))))]
        idx[raiz] = low[raiz] = contador[0]
        contador[0] += 1
        pila.append(raiz)
        en_pila.add(raiz)
        while marco:
            n, it = marco[-1]
            for w in it:
                if w not in idx:
                    idx[w] = low[w] = contador[0]
                    contador[0] += 1
                    pila.append(w)
                    en_pila.add(w)
                    marco.append((w, iter(sorted(G.get(w, ())))))
                    break
                if w in en_pila:
                    low[n] = min(low[n], idx[w])
            else:
                marco.pop()
                if marco:
                    low[marco[-1][0]] = min(low[marco[-1][0]], low[n])
                if low[n] == idx[n]:
                    comp = []
                    while True:
                        w = pila.pop()
                        en_pila.discard(w)
                        comp.append(w)
                        if w == n:
                            break
                    if len(comp) > 1:
                        fuera.append(sorted(comp))

    for m in sorted(G):
        if m not in idx:
            visitar(m)
    return sorted(fuera, key=len, reverse=True)


def _alcanza(G: Dict[str, Set[str]], origen: str, destino: str) -> bool:
    vistos = {origen}
    pila = [origen]
    while pila:
        n = pila.pop()
        for w in G.get(n, ()):
            if w == destino:
                return True
            if w not in vistos:
                vistos.add(w)
                pila.append(w)
    return False


def medir() -> Dict[str, Any]:
    g = _grafo()
    G = _completo(g)
    ciclicas: List[str] = []
    benignas: List[str] = []
    for a in sorted(g["diferido"]):
        for b in sorted(g["diferido"][a]):
            # El destino vuelve al origen ⇒ este import está esquivando un ciclo.
            (ciclicas if _alcanza(G, b, a) else benignas).append(f"{a}->{b}")
    return {
        "componentes": _componentes(G),
        "deferred_cyclic": ciclicas,
        "deferred_benign": benignas,
        "deferred_total": len(ciclicas) + len(benignas),
        "top_level_edges": sum(len(v) for v in g["top"].values()),
        "modules": len(G),
    }


def _baseline() -> List[str]:
    if not BASELINE.exists():
        return []
    # AP-51: una baseline ilegible NO se lee como vacía. Eso estrenaría las 30
    # aristas como deuda nueva, y en `--freeze` las congelaría sin que nadie las
    # viera pasar. Mismo criterio que `vault_criterios` y `vault_fuente_unica`.
    try:
        crudo = BASELINE.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"baseline de AP-58 ilegible: {BASELINE} ({e})") from e
    try:
        return json.loads(crudo).get("sitios", [])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"baseline de AP-58 corrupta: {BASELINE} ({e})") from e


def check() -> Dict[str, Any]:
    m = medir()
    firmas = set(m["deferred_cyclic"])
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    resueltos = sorted(base - firmas)
    return {
        "ok": not nuevos,
        "tool": "vault_ciclos",
        "norm": "AP-58",
        "action": "check",
        "modules": m["modules"],
        "top_level_edges": m["top_level_edges"],
        "deferred_total": m["deferred_total"],
        "deferred_cyclic": sorted(firmas),
        "deferred_cyclic_total": len(firmas),
        # Se publican aunque no sean deuda: el día que una pase a cíclica, el
        # dato de que antes no lo era está aquí y no hay que reconstruirlo.
        "deferred_benign_total": len(m["deferred_benign"]),
        "components": [{"size": len(c), "modules": c} for c in m["componentes"]],
        "largest_component": len(m["componentes"][0]) if m["componentes"] else 0,
        "baseline_size": len(base),
        "new_cyclic_deferrals": nuevos,
        "resolved_since_baseline": resueltos,
        "hint": (
            "Se salda invirtiendo la dependencia —el de bajo nivel deja de "
            "pedirle el módulo entero al de alto—, no subiendo el import ni "
            "ampliando la baseline. Verde aquí no prueba que no haya "
            "acoplamiento: prueba que no crecieron los ciclos que se ven en el "
            "grafo estático de imports."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    m = medir()
    firmas = sorted(set(m["deferred_cyclic"]))
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    if nuevos and not admitir_nuevos:
        return {
            "ok": False, "tool": "vault_ciclos", "action": "freeze",
            "error_code": "DEBT_WOULD_GROW", "new_cyclic_deferrals": nuevos,
            "recovery": ("Invierte la dependencia. Si de verdad hay que congelar "
                         "deuda nueva, `--freeze --admitir-nuevos` la lista aquí."),
        }
    BASELINE.write_text(json.dumps({
        "description": (
            "Imports diferidos que esquivan un ciclo y ya estaban cuando nació "
            "AP-58. Solo puede encoger: un ciclo nuevo se invierte, no se "
            "congela. Las diferidas benignas no entran aquí a propósito — una "
            "baseline llena de ruido es una baseline que nadie revisa."
        ),
        "sitios": firmas,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"ok": True, "tool": "vault_ciclos", "action": "freeze",
            "frozen": len(firmas), "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_ciclos — ciclos esquivados con import diferido (AP-58)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and args.check:
        env = emit_error("vault_ciclos", "CONFLICTING_ARGS",
                         "--freeze y --check piden cosas distintas: o mide o congela")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    r = freeze(args.admitir_nuevos) if args.freeze else check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ciclos"))
