#!/usr/bin/env python3
"""vault_recursos — el consumidor paga el fan-out del productor (AP-62).

## De dónde sale

v40.27 quitó veinte de los sesenta y dos cruces de contexto con un solo
movimiento, y el hallazgo que lo permitió no se buscó: se tropezó con él. De los
veinticuatro importadores de `vault_norms`, veintiuno solo querían una tabla
constante; entraban por una fachada que reexporta el motor y sus once
dependencias, y por el camino convertían **leer un recurso** en **cruzar una
frontera de negocio**.

La pregunta que quedó abierta era la única que importaba: ¿cuántas veces más
pasa esto? A mano no se contesta —hay 136 módulos— y contestarla a ojo una vez
no sirve, porque el patrón se rehace con cada import nuevo. Esta tool la
contesta midiendo, y el número que publica es derivado, no escrito.

## Qué cuenta como sitio de arrastre

Una arista `A -> B` es deuda cuando se dan las cuatro:

1. **B no está en el núcleo.** Leer del núcleo es gratis por definición: para
   eso está declarado. Si B ya es núcleo, no hay nada que arreglar.
2. **B tiene fan-out mayor que cero**, es decir, arrastra algo. Un productor que
   ya es hoja no le cuesta nada a nadie.
3. **Todo lo que A importa de B es un recurso**: una constante de nivel de
   módulo, o una función cuyo cuerpo no toca ninguna de las dependencias
   `vault_*` de B. Si A pide una sola cosa del motor, el import está justificado
   y no aparece aquí.
4. **A y B están en contextos distintos.** Ese es el daño medido: el cruce que
   la arquitectura cuenta y que no corresponde a ninguna decisión de negocio.

Las que cumplen 1-3 pero no la 4 se publican como `arrastre_intracontexto`. No
son deuda —dentro de un contexto los módulos se conocen— pero el día que uno de
los dos se mueva de contexto pasan a serlo, y el dato de que ya estaban ahí vale
más reconstruido nunca que reconstruido a posteriori.

## Cómo se salda, y cómo NO

Se salda **dándole al recurso un dueño con forma de hoja**: partir el productor
en catálogo y motor, mudar el catálogo al núcleo si de verdad tiene fan-out
cero, y repuntar a los consumidores al dueño. Es lo que hizo v40.27, y lo que
enseñó allí sigue valiendo: **partir el fichero por sí solo no movió una sola
cifra**. La arquitectura no cambió hasta que los importadores dejaron de entrar
por la fachada.

No se salda reclasificando el productor al núcleo sin medirle el fan-out —eso es
bajar la cifra en vez de arreglar la estructura, y `vault_kernel` (AP-59) lo
vería— ni ampliando la baseline, que solo puede encoger.

## Qué NO demuestra el verde

- **Mide `from X import y`, no `import X`.** Quien importa el módulo entero no
  declara qué usa, así que no se puede saber si le basta el recurso. Sale fuera
  del alcance y se publica en `importadores_opacos`.
- **La pureza se decide por AST, no por semántica.** Una función se considera
  pura si su cuerpo no nombra ninguna dependencia `vault_*` del módulo. Una que
  dependa de un global mutable del módulo pasará por pura y no lo es.
- **Las clases se dan por acopladas siempre.** Es la lectura conservadora: se
  prefiere no contar un sitio a contar uno que no lo es.
- Y no ve el acoplamiento que no pasa por un `import`: fichero compartido,
  variable de entorno, estado en disco.

Verde aquí significa que no creció el arrastre que se ve en el grafo estático.

    python scripts/vault_recursos.py --check --strict
    python scripts/vault_recursos.py --ranking   # candidatos por cruces que colapsan
    python scripts/vault_recursos.py --freeze    # solo puede encoger
"""

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

import vault_arch
import vault_baseline
import vault_grafo_import
from vault_errors import emit_error, wrap_main

BASELINE = Path(__file__).parent / "recursos-baseline.json"
DIRECTORIO = Path(__file__).parent

_ARBOLES: Dict[str, Optional[ast.Module]] = {}


def _arbol(modulo: str) -> Optional[ast.Module]:
    """El AST del módulo, cacheado. Un fichero ilegible no es un sitio limpio.

    Devuelve `None` y el llamador lo cuenta en `modulos_no_medidos`, que se
    publica: un módulo que la tool no pudo leer es un sitio donde una copia no
    se vería, y eso vale tanto como una copia (el criterio de alcance de
    `vault_criterios`).
    """
    if modulo in _ARBOLES:
        return _ARBOLES[modulo]
    ruta = DIRECTORIO / f"{modulo}.py"
    arbol: Optional[ast.Module] = None
    if ruta.is_file():
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            arbol = None
    _ARBOLES[modulo] = arbol
    return arbol


def _dependencias_nombradas(arbol: ast.Module) -> Set[str]:
    """Nombres que el módulo trae de otras tools del repo.

    Es la lista contra la que se decide si un símbolo es recurso: si el cuerpo
    del símbolo nombra alguno de estos, necesita el fan-out del módulo.
    """
    fuera: Set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and (nodo.module or "").startswith("vault"):
            fuera |= {a.asname or a.name for a in nodo.names}
        elif isinstance(nodo, ast.Import):
            fuera |= {(a.asname or a.name).split(".")[0]
                      for a in nodo.names if a.name.startswith("vault")}
    return fuera


def superficie(modulo: str) -> Dict[str, str]:
    """Qué ofrece el módulo: nombre -> `dato` | `puro` | `acoplado`.

    `dato` y `puro` son recursos —se pueden leer sin pagar el fan-out—;
    `acoplado` no. Las clases van a `acoplado` sin mirar el cuerpo, por la
    lectura conservadora que declara el docstring del módulo.

    **La pureza es transitiva, y esa es la parte que cuesta.** La primera
    versión de esta función solo miraba referencias *directas* a las
    dependencias importadas, y con ese criterio `vault_tags_backfill_ledger`
    salía «pura»: recorre el vault entero, pero lo hace a través de `_raiz()`,
    un helper local. Medir así es certificarse a uno mismo (AP-44) en la tool
    que nace precisamente para detectar que el consumidor no ve lo que paga.
    Así que se itera a punto fijo: un símbolo se contagia de `acoplado` si
    nombra a otro que ya lo está, y se repite hasta que nadie cambia.
    """
    arbol = _arbol(modulo)
    if arbol is None:
        return {}
    deps = _dependencias_nombradas(arbol)
    fuera: Dict[str, str] = {}
    referidos: Dict[str, Set[str]] = {}

    def _nombres(nodo: ast.AST) -> Set[str]:
        usados = {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)}
        usados |= {n.value.id for n in ast.walk(nodo)
                   if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
        return usados

    for nodo in arbol.body:
        if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            objetivos = (nodo.targets if isinstance(nodo, ast.Assign)
                         else [nodo.target])
            usados = _nombres(nodo)
            for o in objetivos:
                if isinstance(o, ast.Name):
                    fuera[o.id] = "acoplado" if (usados & deps) else "dato"
                    referidos[o.id] = usados
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            usados = _nombres(nodo)
            fuera[nodo.name] = "acoplado" if (usados & deps) else "puro"
            referidos[nodo.name] = usados
        elif isinstance(nodo, ast.ClassDef):
            fuera[nodo.name] = "acoplado"
            referidos[nodo.name] = set()

    # Punto fijo: el acoplamiento se propaga por quién nombra a quién.
    cambio = True
    while cambio:
        cambio = False
        sucios = {n for n, c in fuera.items() if c == "acoplado"}
        for nombre, usados in referidos.items():
            if fuera.get(nombre) != "acoplado" and (usados & sucios):
                fuera[nombre] = "acoplado"
                cambio = True
    return fuera


def simbolos_pedidos(origen: str, destino: str) -> Set[str]:
    """Qué le pide `origen` a `destino`. `*` = el módulo entero, sin declarar."""
    arbol = _arbol(origen)
    if arbol is None:
        return set()
    fuera: Set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == destino:
            fuera |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.Import):
            if any(a.name == destino for a in nodo.names):
                fuera.add("*")
    return fuera


def medir() -> Dict[str, Any]:
    """Recorre el grafo y clasifica cada arista. Ningún efecto lateral."""
    mapa = vault_arch._mapa_modulos()
    fan_out = vault_grafo_import.fan_out()
    fan_in = vault_grafo_import.fan_in()

    cruzan: List[Dict[str, Any]] = []
    intra: List[str] = []
    opacos: List[str] = []
    no_medidos: List[str] = []

    for origen in sorted(mapa):
        if "/" in origen:
            continue                       # el paquete `vault/` va por otra puerta
        if _arbol(origen) is None:
            if (DIRECTORIO / f"{origen}.py").is_file():
                no_medidos.append(origen)
            continue
        for destino in sorted(fan_out.get(origen, ())):
            if destino not in mapa or "/" in destino:
                continue
            if mapa[destino] == vault_arch.KERNEL:
                continue                   # (1) leer del núcleo es gratis
            if not fan_out.get(destino):
                continue                   # (2) el productor ya es hoja
            pedidos = simbolos_pedidos(origen, destino)
            if not pedidos:
                continue
            if "*" in pedidos:
                opacos.append(f"{origen}->{destino}")
                continue
            ofrecido = superficie(destino)
            clases = {ofrecido.get(s, "acoplado") for s in pedidos}
            if not clases <= {"dato", "puro"}:
                continue                   # (3) pide algo del motor: justificado
            if mapa[origen] == mapa[destino]:
                intra.append(f"{origen}->{destino}")   # (4) no cruza
                continue
            cruzan.append({
                "sitio": f"{origen}->{destino}",
                "from_context": mapa[origen],
                "to_context": mapa[destino],
                "simbolos": sorted(pedidos),
                "fan_out_pagado": len(fan_out.get(destino, ())),
            })

    hojas = sorted(
        ({"modulo": m, "contexto": c, "fan_in": len(fan_in.get(m, ()))}
         for m, c in mapa.items()
         if c != vault_arch.KERNEL and "/" not in m
         and (DIRECTORIO / f"{m}.py").is_file()
         and not fan_out.get(m) and fan_in.get(m)),
        key=lambda h: (-h["fan_in"], h["modulo"]))

    return {
        "arrastre": cruzan,
        "arrastre_intracontexto": sorted(intra),
        "importadores_opacos": sorted(opacos),
        "modulos_no_medidos": sorted(no_medidos),
        "hojas_fuera_del_nucleo": hojas,
    }


def ranking() -> List[Dict[str, Any]]:
    """Los productores, ordenados por cuántos cruces colapsaría mudarlos.

    Es lo que convierte la medida en un plan: sin el orden, doce sitios sueltos
    no dicen por dónde empezar. El desempate es el fan-out que cada consumidor
    paga —a igualdad de cruces, primero el productor más pesado— y a igualdad de
    los dos, el nombre, para que la salida no dependa del orden del diccionario.
    """
    por_destino: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sitio in medir()["arrastre"]:
        por_destino[sitio["sitio"].split("->")[1]].append(sitio)
    fuera = [
        {
            "productor": destino,
            "cruces_que_colapsa": len(sitios),
            "fan_out_pagado": sitios[0]["fan_out_pagado"],
            "consumidores": [s["sitio"].split("->")[0] for s in sitios],
            "recursos": sorted({x for s in sitios for x in s["simbolos"]}),
        }
        for destino, sitios in por_destino.items()
    ]
    return sorted(fuera, key=lambda f: (-f["cruces_que_colapsa"],
                                        -f["fan_out_pagado"], f["productor"]))


#: Sitio congelado -> por qué no se salda. Una deuda que se congela sin motivo
#: escrito es una deuda que nadie vuelve a mirar; el test de esta tool exige que
#: todo lo que quede en la baseline aparezca aquí. Salir de la baseline no pide
#: borrar la entrada: el motivo sigue explicando qué se decidió y cuándo.
EXENCIONES: Dict[str, str] = {
    "vault_standard_upgrade->vault_mcp_catalog": (
        "v40.28 — el corte normal (partir el productor en catálogo y motor) no "
        "se sostiene aquí: `vault_spec_generate_catalog --write` **reescribe "
        "vault_mcp_catalog.py entero** desde tool-spec.json, así que el catálogo "
        "volvería a la fachada en la primera regeneración y la deuda reaparecería "
        "sin que nadie lo notase. El fan-out pagado es además 1, y es un `import "
        "vault_io` diferido dentro de `check_contracts` que no llega a ejecutarse "
        "al leer GROUPS. Se salda cuando el generador sepa escribir en dos "
        "ficheros, no antes."
    ),
    "vault_voice->vault_mcp_catalog": (
        "v40.28 — el mismo productor y el mismo motivo que la entrada de "
        "`vault_standard_upgrade`. Los dos consumidores solo leen GROUPS y "
        "TOOLS_CATALOG."
    ),
}


def _baseline() -> List[str]:
    return vault_baseline.cargar(BASELINE, "sitios", "AP-62")


def check() -> Dict[str, Any]:
    m = medir()
    firmas = {s["sitio"] for s in m["arrastre"]}
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    resueltos = sorted(base - firmas)
    return {
        "ok": not nuevos,
        "tool": "vault_recursos",
        "norm": "AP-62",
        "action": "check",
        "drag_sites": sorted(firmas),
        "drag_total": len(firmas),
        "baseline_size": len(base),
        "new_drag_sites": nuevos,
        "resolved_since_baseline": resueltos,
        # Lo congelado, con su motivo al lado. Si algún sitio de la baseline no
        # lo tiene, sale aquí y el test de la tool falla.
        "frozen_with_reason": {s: EXENCIONES[s] for s in sorted(base)
                               if s in EXENCIONES},
        "frozen_without_reason": sorted(s for s in base if s not in EXENCIONES),
        "ranking": ranking(),
        # Publicados y no bloqueantes, por el motivo escrito en el docstring.
        "intra_context_drag_total": len(m["arrastre_intracontexto"]),
        "opaque_importers_total": len(m["importadores_opacos"]),
        "leaves_outside_kernel": m["hojas_fuera_del_nucleo"],
        "modules_unmeasured": m["modulos_no_medidos"],
        "hint": (
            "Se salda dándole al recurso un dueño con forma de hoja: partir el "
            "productor en catálogo y motor y repuntar a los consumidores al "
            "dueño. Partir el fichero solo no mueve la cifra —lo enseñó "
            "v40.27—; la mueve que los importadores dejen de entrar por la "
            "fachada. Reclasificar el productor al núcleo sin medirle el "
            "fan-out lo vería AP-59, y la baseline solo encoge."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    firmas = sorted({s["sitio"] for s in medir()["arrastre"]})
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_recursos", "freeze", "new_drag_sites", nuevos,
            "Dale al recurso un dueño con forma de hoja. Si de verdad hay que "
            "congelar deuda nueva, `--freeze --admitir-nuevos` la lista aquí.")
    vault_baseline.escribir(
        BASELINE, "sitios", "AP-62",
        "Aristas donde el consumidor cruza un contexto para leer un recurso que "
        "no necesita el fan-out del productor, y que ya estaban cuando nació "
        "AP-62. Solo puede encoger: un arrastre nuevo se salda partiendo el "
        "productor, no congelándolo. El arrastre intracontexto no entra aquí a "
        "propósito — no es deuda mientras los dos módulos compartan contexto.",
        firmas)
    return {"ok": True, "tool": "vault_recursos", "action": "freeze",
            "frozen": len(firmas), "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_recursos — arrastre productor/consumidor (AP-62)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--ranking", action="store_true",
                    help="candidatos ordenados por cruces que colapsan")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and args.check:
        env = emit_error("vault_recursos", "CONFLICTING_ARGS",
                         "--freeze y --check piden cosas distintas: o mide o congela")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    if args.ranking:
        r = {"ok": True, "tool": "vault_recursos", "action": "ranking",
             "ranking": ranking()}
    elif args.freeze:
        r = freeze(args.admitir_nuevos)
    else:
        r = check()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 1 if args.strict and not r["ok"] else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_recursos"))
