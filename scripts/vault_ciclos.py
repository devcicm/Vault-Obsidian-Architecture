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
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
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


#: Los ciclos de `vault/` que existen a propósito, uno a uno y con su motivo.
#:
#: v40.30. `vault_ciclos` mide el grafo de `scripts/` —lo dice su docstring y lo
#: repite el de `vault_grafo_import`—, así que el paquete que existe para
#: imponer fronteras era el único cuyos ciclos no contaba nadie. Hay uno, es
#: deliberado y está comentado en el propio código; lo que faltaba no era
#: arreglarlo sino **vigilarlo**: un comentario no impide que mañana el ciclo
#: pase de dos módulos a cinco.
#:
#: No se midió ensanchando `vault_grafo_import.grafo()` a `vault/`. Ese grafo
#: alimenta también los umbrales de fan-in/fan-out que AP-59 deriva del escalón,
#: así que ensancharlo movería todos los umbrales del repo y rompería puertas
#: por un cambio de alcance — que es la lección que dejó v40.26. La medida vive
#: aquí, con su alcance declarado y sin tocar la del núcleo.
CICLOS_DEL_DOMINIO_ESPERADOS: Dict[str, str] = {
    "vault/kernel/adaptadores.py <-> vault/kernel/contexto.py": (
        "La raíz de composición y el contexto que construye. `contexto.py` "
        "difiere su import de `adaptadores` dentro de una función y lo dice en "
        "un comentario; `adaptadores` importa `VaultContext` en cabecera. Es el "
        "ciclo que cualquier raíz de composición tiene con lo que compone, y "
        "por eso `vault_arch` declara `adaptadores.py` como RAIZ_COMPOSICION: "
        "el único fichero que puede cruzar a cualquier contexto."
    ),
}


def _modulos_dominio() -> Dict[str, Path]:
    """Los ficheros de `vault/`, por su ruta relativa al repo."""
    raiz = DIRECTORIO.parent / "vault"
    if not raiz.is_dir():
        return {}
    return {
        str(p.relative_to(DIRECTORIO.parent)).replace("\\", "/"): p
        for p in sorted(raiz.rglob("*.py"))
    }


def ciclos_del_dominio() -> List[str]:
    """Pares de `vault/` que se importan mutuamente, en cualquier dirección.

    Se miden los pares y no los componentes porque el dato accionable es
    «quiénes se enredaron»: un componente de tamaño 5 se lee peor que los pares
    que lo forman, y para el tamaño ya está `largest_component` del grafo de
    `scripts/`.

    Cuenta el import diferido igual que el de cabecera. Meterlo dentro de una
    función es exactamente lo que AP-58 persigue, así que descontarlo aquí
    dejaría verde el caso que la norma existe para ver.
    """
    modulos = _modulos_dominio()
    if not modulos:
        return []
    # Módulo Python (`vault.kernel.contexto`) -> ruta, para resolver los
    # imports relativos a un fichero concreto.
    por_punto = {
        k[:-3].replace("/", ".").removesuffix(".__init__"): k for k in modulos
    }
    aristas: Dict[str, Set[str]] = {k: set() for k in modulos}
    for clave, ruta in modulos.items():
        paquete = clave[:-3].replace("/", ".").removesuffix(".__init__")
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            destinos: Set[str] = set()
            if isinstance(nodo, ast.ImportFrom):
                if nodo.level:
                    base = paquete.rsplit(".", nodo.level)[0]
                    destinos.add(f"{base}.{nodo.module}" if nodo.module else base)
                elif nodo.module and nodo.module.startswith("vault."):
                    destinos.add(nodo.module)
                # `from .paquete import modulo` — el destino puede ser el
                # submódulo y no el paquete, y sin esto el ciclo se pierde.
                for alias in nodo.names:
                    destinos |= {f"{d}.{alias.name}" for d in set(destinos)}
            elif isinstance(nodo, ast.Import):
                destinos |= {
                    a.name for a in nodo.names if a.name.startswith("vault.")
                }
            for d in destinos:
                if d in por_punto and por_punto[d] != clave:
                    aristas[clave].add(por_punto[d])
    pares = set()
    for a, salidas in aristas.items():
        for b in salidas:
            if a in aristas.get(b, set()):
                pares.add(" <-> ".join(sorted((a, b))))
    return sorted(pares)


def _baseline() -> List[str]:
    """superseded_by: vault_baseline.cargar (v40.24).

    El cuerpo que había aquí era el mismo que `vault_criterios._baseline` y
    `vault_kernel._baseline`, palabra por palabra, con el número de la norma
    cambiado — y sus comentarios se citaban entre sí como si eso lo justificara.
    Se conserva la función porque la llaman `check` y `freeze`, pero decide el
    dueño (AP-57).
    """
    return vault_baseline.cargar(BASELINE, "sitios", "AP-58")


def check() -> Dict[str, Any]:
    m = medir()
    firmas = set(m["deferred_cyclic"])
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    resueltos = sorted(base - firmas)
    # El dominio, con su propio alcance declarado (v40.30). No entra en la
    # baseline de AP-58: allí se congelan sitios de `scripts/` indexados por
    # firma, y aquí el dato es un par de módulos con su motivo escrito en
    # código. Un ciclo del dominio que no esté en la lista bloquea igual.
    dominio = ciclos_del_dominio()
    dominio_nuevos = [c for c in dominio if c not in CICLOS_DEL_DOMINIO_ESPERADOS]
    dominio_resueltos = [c for c in CICLOS_DEL_DOMINIO_ESPERADOS if c not in dominio]
    return {
        "ok": not nuevos and not dominio_nuevos,
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
        # `vault/` — el paquete que impone las fronteras era el único cuyos
        # ciclos no medía nadie, porque el grafo de `vault_grafo_import` solo
        # ve `scripts/` y ensancharlo movería los umbrales que AP-59 deriva de
        # su forma (la lección de v40.26).
        "domain_modules": len(_modulos_dominio()),
        "domain_cycles": dominio,
        "domain_cycles_expected": sorted(CICLOS_DEL_DOMINIO_ESPERADOS),
        "new_domain_cycles": dominio_nuevos,
        "resolved_domain_cycles": sorted(dominio_resueltos),
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
        return vault_baseline.negativa(
            "vault_ciclos", "freeze", "new_cyclic_deferrals", nuevos,
            "Invierte la dependencia. Si de verdad hay que congelar deuda "
            "nueva, `--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(
        BASELINE, "sitios", "AP-58",
        "Imports diferidos que esquivan un ciclo y ya estaban cuando nació "
        "AP-58. Solo puede encoger: un ciclo nuevo se invierte, no se congela. "
        "Las diferidas benignas no entran aquí a propósito — una baseline "
        "llena de ruido es una baseline que nadie revisa.",
        firmas)
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
