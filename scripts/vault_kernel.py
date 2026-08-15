#!/usr/bin/env python3
"""vault_kernel — el núcleo se declara pero nadie lo mide (AP-59).

## De dónde sale

`vault_arch.CONTEXTS['kernel']['modulos']` es una **lista de nombres escrita a
mano**. Dice cuál es el núcleo de este repo y ninguna puerta la contrasta contra
nada. Es la misma clase de afirmación que AP-47 persigue en las cifras y AP-57 en
los criterios, cometida en el sitio más caro: si la pertenencia al kernel está
mal, `vault_arch` mide sus fronteras contra un mapa equivocado y sale verde.

Que la lista esté hoy **bien elegida** no cambia el problema. Al medir para
v40.20 se comprobó que los cuatro de cabecera son los correctos y que K1 ya
estaba verde — y aun así aparecieron tres módulos del kernel que no se comportan
como núcleo. Nadie los había visto porque nadie miraba.

## Las tres invariantes

- **K1 — el núcleo no depende del dominio.** *No se mide aquí.* Se **delega** en
  `vault_arch.dependencias_del_kernel()`, que ya lo hace bien, y se publica su
  resultado junto al conteo de `GANCHOS_DEL_KERNEL`. Reimplementarla sería AP-44
  en la tool que existe para trazar el núcleo: mediría su propia pureza con su
  propio criterio.
- **K2 — fan-in alto, fan-out bajo.** Del dueño único del grafo,
  `vault_grafo_import`. Esta tool no parsea un solo `import`.
- **K3 — estabilidad.** Churn de `git log`, contra la mediana del dominio
  **separada por el ratio que la propia cola alta deja ver** (v40.23). Contra
  la mediana pelada, un módulo del núcleo cruzaba el umbral por seguir vivo —el
  churn es acumulado y nunca baja—, y eso mide edad, no forma. Sin historia de
  git el valor es `desconocido`, **nunca** `0`: un cero fabricado saldría verde
  por no haber mirado, que es AP-51.

## Los umbrales se derivan del escalón, no se escriben

La distribución de fan-in del repo tiene un corte limpio (113, 83, 60 ‖ 27, 26,
20, …) y la de fan-out del kernel también (11 ‖ 5, 4, 2, …). El umbral es el
valor por encima de la **mayor caída relativa** y se publica en el envelope en
cada ejecución, con su ratio, para que sea auditable. Un literal aquí sería AP-47
en la tool que persigue los números a mano.

Consecuencia asumida: el umbral **puede oscilar** al crecer el repo. Por eso lo
que se congela en la baseline es la **pertenencia** —qué módulo incumple qué
invariante— y no el umbral.

## Qué NO demuestra el verde

Mide el grafo estático de imports, y hereda todas sus cegueras (`importlib`, un
import por cadena, el acoplamiento por fichero o por variable global). Y mide
**forma**, no propósito: un módulo puede tener fan-in altísimo y no ser núcleo de
nada, solo un cajón de utilidades que todo el mundo toca. Verde aquí significa
que la lista declarada no contradice a la forma medida.

    python scripts/vault_kernel.py --check --strict
    python scripts/vault_kernel.py --trace vault_context_pack
    python scripts/vault_kernel.py --freeze     # solo puede encoger
"""

import argparse
import json
import statistics
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import vault_baseline
import vault_grafo_import
from vault_arch import (
    CONTEXTS,
    GANCHOS_DEL_KERNEL,
    KERNEL,
    PRESUPUESTO_DE_GANCHOS,
    dependencias_del_kernel,
)
from vault_errors import emit_error, wrap_main

BASELINE = Path(__file__).parent / "kernel-baseline.json"
DIRECTORIO = Path(__file__).parent
RAIZ_REPO = DIRECTORIO.parent


# ── El escalón: un solo criterio de umbral, usado por K2 en sus dos caras ─────

def escalon(valores: Sequence[int]) -> Tuple[Optional[int], Optional[float]]:
    """El valor por encima de la mayor caída relativa de la distribución.

    Devuelve `(umbral, ratio)`. Se ignoran los ceros: una caída a cero tiene
    ratio infinito y se llevaría siempre el máximo, dejando el umbral pegado al
    valor más pequeño distinto de cero.

    Se usa el **mismo** cálculo para el fan-in y para el fan-out. Dos criterios
    de umbral en la misma tool serían dos definiciones de «alto» sin dueño, que
    es el defecto que v40.20 vino a cerrar en el grafo de imports.
    """
    v = sorted({x for x in valores if x > 0}, reverse=True)
    if len(v) < 2:
        return None, None
    i = max(range(len(v) - 1), key=lambda j: v[j] / v[j + 1])
    return v[i], round(v[i] / v[i + 1], 3)


# ── K3: churn, y el `desconocido` que impide el cero fabricado ────────────────

def _hay_historia() -> bool:
    """Un clon de profundidad 1 —lo que hace `actions/checkout@v4` por defecto—
    daría un commit por fichero y K3 saldría verde por no haber mirado."""
    for args in (["rev-parse", "--git-dir"], ["rev-parse", "--is-shallow-repository"]):
        r = subprocess.run(["git", *args], cwd=RAIZ_REPO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return False
        if args[-1] == "--is-shallow-repository" and r.stdout.strip() == "true":
            return False
    return True


#: Recuento de commits por módulo, de una sola pasada. `None` = aún sin leer.
_CHURN: Optional[Dict[str, int]] = None


def _churn_de_todos() -> Optional[Dict[str, int]]:
    """Un solo `git log`, no uno por módulo.

    Preguntarle a git fichero a fichero costaba 130 subprocesos y ~14 s, que es
    más de la mitad de lo que tarda la tanda entera de puertas. La medida es la
    misma: se recorre la historia una vez pidiendo los ficheros tocados por cada
    commit y se cuenta.
    """
    r = subprocess.run(
        ["git", "log", "--format=%H", "--name-only", "--", "scripts"],
        cwd=RAIZ_REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return None
    cuenta: Dict[str, int] = {}
    for linea in r.stdout.splitlines():
        linea = linea.strip()
        if linea.startswith("scripts/") and linea.endswith(".py"):
            m = linea[len("scripts/"):-len(".py")]
            cuenta[m] = cuenta.get(m, 0) + 1
    return cuenta


def churn(modulo: str) -> Optional[int]:
    """Commits que tocaron `scripts/<modulo>.py`. `None` = desconocido (AP-51).

    Un módulo que existe y nunca se tocó cuenta 0; uno cuya historia no se pudo
    leer cuenta `None`. La diferencia es toda la norma: el 0 fabricado saldría
    verde por no haber mirado.
    """
    global _CHURN
    if _CHURN is None:
        _CHURN = _churn_de_todos()
    if _CHURN is None:
        return None
    return _CHURN.get(modulo, 0)


# ── La medida ────────────────────────────────────────────────────────────────

#: Los dos valores de `objetivo` y qué exige cada uno. Vive aquí y no en
#: `vault_arch` porque es criterio de medida —qué presupuesto vale—, no
#: declaración: `vault_arch` dice qué ganchos hay, esta tool dice si están
#: presupuestados.
_OBJETIVOS = {"permanente": (), "a_eliminar": ("fecha_limite",)}


def _presupuesto_invalido(p: Optional[Dict[str, Any]]) -> List[str]:
    """Por qué este presupuesto no vale. Lista vacía = vale.

    Ausente y mal escrito devuelven lo mismo a propósito: los dos dejan la vía
    de escape sin fecha ni dueño, que es lo único que el hallazgo mide. Un
    presupuesto a medias que pasara la puerta sería peor que no declararlo,
    porque parecería declarado.
    """
    if p is None:
        return ["sin entrada en PRESUPUESTO_DE_GANCHOS"]
    problemas: List[str] = []
    objetivo = p.get("objetivo")
    if objetivo not in _OBJETIVOS:
        problemas.append(f"`objetivo` debe ser uno de {sorted(_OBJETIVOS)}")
    else:
        for campo in _OBJETIVOS[objetivo]:
            if not p.get(campo):
                problemas.append(f"`objetivo: {objetivo}` exige `{campo}`")
    for campo in ("revisado", "dueno", "por_que"):
        if not str(p.get(campo, "")).strip():
            problemas.append(f"falta `{campo}`")
    cadencia = p.get("cadencia_dias")
    if not isinstance(cadencia, int) or cadencia <= 0:
        problemas.append("`cadencia_dias` debe ser un entero > 0")
    for campo in ("revisado", "fecha_limite"):
        valor = p.get(campo)
        if valor is None:
            continue
        try:
            datetime.strptime(str(valor), "%Y-%m-%d")
        except ValueError:
            problemas.append(f"`{campo}` debe ser `YYYY-MM-DD`")
    return problemas


def _vence(p: Dict[str, Any]) -> str:
    """Cuándo tocaba revisar: `revisado + cadencia_dias`, derivado.

    No se escribe en el registro porque sería el mismo dato dos veces y con la
    forma que más fácil diverge (AP-05): mover `revisado` sin mover el
    vencimiento dejaría la revisión hecha y la fecha caducada.
    """
    base = datetime.strptime(str(p["revisado"]), "%Y-%m-%d").date()
    return (base + timedelta(days=int(p["cadencia_dias"]))).isoformat()


def _dominio() -> Set[str]:
    fuera: Set[str] = set()
    for ctx, datos in CONTEXTS.items():
        if ctx != KERNEL:
            fuera |= set(datos.get("modulos", ()))
    return fuera


def medir() -> Dict[str, Any]:
    G = vault_grafo_import.completo()
    fi = vault_grafo_import.fan_in(G)
    fo = vault_grafo_import.fan_out(G)
    kernel = sorted(CONTEXTS[KERNEL]["modulos"])
    dominio = sorted(m for m in _dominio() if m in G)

    u_in, r_in = escalon([len(s) for s in fi.values()])
    u_out, r_out = escalon([len(fo.get(m, ())) for m in kernel])

    con_historia = _hay_historia()
    churns = {m: (churn(m) if con_historia else None)
              for m in kernel + dominio}
    del_dominio = [c for m in dominio if (c := churns.get(m)) is not None]
    mediana = statistics.median(del_dominio) if del_dominio else None
    # K3 también deriva su umbral, como K2 y el fan-in. Hasta v40.23 comparaba
    # contra la mediana pelada y era el único de los tres criterios sin margen:
    # el churn es acumulado y nunca baja, así que cualquier módulo del núcleo
    # acababa cruzando la mediana con solo seguir vivo — `vault_lib` la cruzó
    # con el commit de v40.23, de 9 a 10 frente a una mediana de 9. Eso
    # convierte antigüedad en defecto, y la norma no afirma eso: afirma que el
    # núcleo **se mueve menos que lo que sostiene**.
    #
    # El escalón se usa aquí como **ratio**, no como corte, y el motivo se
    # midió: la distribución de churn no tiene escalón. Su cola alta es
    # continua (52, 47, 37, 33, 28, …) y el derivador devuelve ratio ~1.27,
    # que no es una caída; aplicado como corte absoluto daría 47 y dejaría la
    # invariante sin marcar a nadie —incluidos los tres que ya están en la
    # baseline—, que es fabricar verde. Aplicado sobre la mitad de abajo daría
    # 2 y marcaría el núcleo entero. Lo que sí tiene significado es cuánto se
    # separa de la mediana, y ese factor sale de la misma distribución en vez
    # de escribirse a mano.
    # El ratio se deriva de la **cola alta** —los que se mueven más que la
    # mediana—, que es sobre quien K3 pregunta. Sobre la distribución entera el
    # derivador se llevaría la caída de 2 a 1, que ocurre entre los módulos que
    # apenas se tocan y no dice nada de la estabilidad del núcleo.
    cola_alta = [c for c in del_dominio if mediana is not None and c > mediana]
    r_churn = escalon(cola_alta)[1] if cola_alta else None
    # Con menos de dos valores en la cola no hay ratio que derivar. El umbral
    # cae entonces a la mediana pelada —el criterio de v40.22— en vez de quedar
    # en `None`: sin umbral la invariante no mide nada, y no medir es peor que
    # medir estrecho. Solo ocurre en un dominio diminuto.
    if mediana is None:
        u_churn = None
    elif r_churn is None:
        u_churn = mediana
    else:
        u_churn = round(mediana * r_churn, 2)

    hallazgos: List[Dict[str, Any]] = []

    def anota(tipo: str, modulo: str, dato: Any, porque: str) -> None:
        hallazgos.append({"finding": tipo, "module": modulo,
                          "value": dato, "why": porque})

    for m in kernel:
        entrada, salida = len(fi.get(m, ())), len(fo.get(m, ()))
        if entrada == 0:
            anota("kernel_sin_consumidores", m, entrada,
                  "está declarado en el núcleo y nadie lo importa: o le falta "
                  "el consumidor que justificaba ponerlo ahí, o no es núcleo")
        if u_out is not None and salida >= u_out:
            anota("kernel_impuro", m, salida,
                  f"fan-out {salida} ≥ el escalón {u_out} del propio kernel: "
                  "un módulo del que todos dependen y que depende de muchos "
                  "propaga cada cambio hacia arriba")
        c = churns.get(m)
        if c is not None and u_churn is not None and c >= u_churn:
            anota("kernel_inestable", m, c,
                  f"{c} commits ≥ el escalón {u_churn} del dominio (mediana "
                  f"{mediana}): el núcleo debería moverse menos que lo que "
                  "sostiene")

    for m in dominio:
        entrada, salida = len(fi.get(m, ())), len(fo.get(m, ()))
        if u_in is not None and entrada >= u_in and (u_out is None or salida < u_out):
            anota("nucleo_no_declarado", m, entrada,
                  f"fan-in {entrada} ≥ el escalón {u_in} y fan-out bajo: se "
                  "comporta como núcleo sin estar declarado en él")

    # v40.24: deja de ser informativo. Hasta v40.23 este hallazgo se emitía
    # para los seis ganchos y nunca entraba en `firmas`, porque el mecanismo
    # que lo cerraba —declarar hasta cuándo vive la vía de escape y quién la
    # revisa— no existía, y un hallazgo que no se puede saldar bloqueando la
    # puerta solo enseña a ampliar baselines. Ahora existe
    # (`vault_arch.PRESUPUESTO_DE_GANCHOS`), así que el hallazgo apunta a lo
    # único que sigue sin respuesta: un gancho **sin presupuesto declarado**.
    # Los seis de hoy lo tienen, de modo que esto nace en cero y lo que dispara
    # es el séptimo — que es cuando la vía de escape crecería sin que nadie
    # hubiera dicho hasta cuándo.
    for (origen, destino) in sorted(GANCHOS_DEL_KERNEL):
        problemas = _presupuesto_invalido(PRESUPUESTO_DE_GANCHOS.get((origen, destino)))
        if problemas:
            anota("gancho_sin_presupuesto", f"{origen}->{destino}", problemas,
                  "la vía de escape del kernel solo puede crecer si nadie dice "
                  "hasta cuándo vive: declárala en "
                  "`vault_arch.PRESUPUESTO_DE_GANCHOS` con objetivo, cadencia "
                  "y dueño")

    # Vencido NO es lo mismo que sin declarar, y por eso va aparte: un guard
    # que se pone rojo por el paso del calendario falla en un repo que nadie
    # tocó, y el primer arreglo que enseña es mover la fecha. Se publica para
    # que la revisión se pueda pedir; no bloquea.
    ganchos = [
        {"finding": "gancho_por_revisar", "module": f"{o}->{d}",
         "revisado": PRESUPUESTO_DE_GANCHOS[(o, d)]["revisado"],
         "vence": _vence(PRESUPUESTO_DE_GANCHOS[(o, d)]),
         "why": "la revisión pactada de esta vía de escape ya tocaba"}
        for (o, d) in sorted(GANCHOS_DEL_KERNEL)
        if (o, d) in PRESUPUESTO_DE_GANCHOS
        and not _presupuesto_invalido(PRESUPUESTO_DE_GANCHOS[(o, d)])
        and _vence(PRESUPUESTO_DE_GANCHOS[(o, d)]) < date.today().isoformat()
    ]

    return {
        "kernel": kernel,
        "hallazgos": hallazgos,
        "informativos": ganchos,
        "k1_dependencias_sin_declarar": dependencias_del_kernel(),
        "k1_ganchos_declarados": len(GANCHOS_DEL_KERNEL),
        "umbral_fan_in": u_in, "umbral_fan_in_ratio": r_in,
        "umbral_fan_out": u_out, "umbral_fan_out_ratio": r_out,
        "churn_disponible": con_historia,
        "churn_mediana_dominio": mediana,
        "umbral_churn": u_churn, "umbral_churn_ratio": r_churn,
        "fan_in": {m: len(fi.get(m, ())) for m in kernel},
        "fan_out": {m: len(fo.get(m, ())) for m in kernel},
        "churn": {m: churns.get(m) for m in kernel},
        "modules": len(G),
    }


def firma(h: Dict[str, Any]) -> str:
    """Indexada por **nombre de módulo**, no por línea ni por hash de código.

    La pertenencia al kernel es estable por naturaleza: renombrar un módulo del
    núcleo es un acto deliberado y debe estrenar la deuda. Un hash del cuerpo
    haría que cualquier edición del módulo reapareciese como hallazgo nuevo, y
    el churn del núcleo es justo lo que K3 mide.
    """
    return f"{h['finding']}::{h['module']}"


# ── Baseline: solo puede encoger ─────────────────────────────────────────────

def _baseline() -> List[str]:
    """superseded_by: vault_baseline.cargar (v40.24).

    Tercera copia literal del mismo cuerpo. Se conserva la función porque la
    llaman `check` y `freeze`; el criterio lo decide el dueño (AP-57).
    """
    return vault_baseline.cargar(BASELINE, "sitios", "AP-59")


def check() -> Dict[str, Any]:
    m = medir()
    firmas = {firma(h) for h in m["hallazgos"]}
    base = set(_baseline())
    nuevos = sorted(firmas - base)
    resueltos = sorted(base - firmas)
    # K1 no se reimplementa, pero sí se hace bloqueante aquí: si `vault_arch`
    # encuentra una dependencia del kernel sin declarar, el núcleo dejó de ser
    # núcleo y ninguna baseline debería absorberlo.
    k1 = m["k1_dependencias_sin_declarar"]
    return {
        "ok": not nuevos and not k1,
        "tool": "vault_kernel",
        "norm": "AP-59",
        "action": "check",
        "modules": m["modules"],
        "kernel_size": len(m["kernel"]),
        "kernel": m["kernel"],
        "k1_undeclared_kernel_deps": k1,
        "k1_declared_hooks": m["k1_ganchos_declarados"],
        "threshold_fan_in": m["umbral_fan_in"],
        "threshold_fan_in_ratio": m["umbral_fan_in_ratio"],
        "threshold_fan_out": m["umbral_fan_out"],
        "threshold_fan_out_ratio": m["umbral_fan_out_ratio"],
        "churn_available": m["churn_disponible"],
        "churn_median_domain": m["churn_mediana_dominio"],
        "threshold_churn": m["umbral_churn"],
        "threshold_churn_ratio": m["umbral_churn_ratio"],
        "fan_in": m["fan_in"], "fan_out": m["fan_out"], "churn": m["churn"],
        "findings": m["hallazgos"],
        "findings_total": len(firmas),
        "informational": m["informativos"],
        "baseline_size": len(base),
        "new_findings": nuevos,
        "resolved_since_baseline": resueltos,
        "hint": (
            "Los umbrales se derivan del escalón de la distribución y se "
            "publican arriba: no se ajustan para pasar. Un hallazgo se salda "
            "sacando el módulo del kernel o dándole la forma de núcleo "
            "(fan-out abajo, consumidores reales), no ampliando la baseline. "
            "Verde aquí no prueba que la lista sea la correcta: prueba que no "
            "contradice a la forma que el grafo de imports deja ver."
        ),
    }


def trace(modulo: str) -> Dict[str, Any]:
    """Camino más corto de un módulo hasta el núcleo: si toco esto, ¿qué se cae?

    Mismo idioma que `vault_servicio --trace`.
    """
    G = vault_grafo_import.completo()
    if modulo not in G:
        env = emit_error("vault_kernel", "NOT_FOUND",
                         f"no existe scripts/{modulo}.py")
        env["recovery"] = "usa el stem del módulo, sin ruta ni extensión"
        return env
    kernel = set(CONTEXTS[KERNEL]["modulos"])
    previo: Dict[str, Optional[str]] = {modulo: None}
    cola = [modulo]
    destino = modulo if modulo in kernel else None
    while cola and destino is None:
        siguiente = []
        for n in cola:
            for w in sorted(G.get(n, ())):
                if w in previo:
                    continue
                previo[w] = n
                if w in kernel:
                    destino = w
                    break
                siguiente.append(w)
            if destino:
                break
        cola = siguiente
    camino: List[str] = []
    if destino is not None:
        n: Optional[str] = destino
        while n is not None:
            camino.append(n)
            n = previo[n]
        camino.reverse()
    # Una fuga en el camino es un módulo del kernel que sale al dominio por un
    # gancho: el punto por el que un cambio de arriba vuelve a bajar.
    ganchos = {o for (o, _) in GANCHOS_DEL_KERNEL}
    fugas = [m for m in camino if m in ganchos]
    return {
        "ok": destino is not None,
        "tool": "vault_kernel",
        "action": "trace",
        "module": modulo,
        "in_kernel": modulo in kernel,
        "path": camino,
        "reaches": destino,
        "depth_to_kernel": (len(camino) - 1) if camino else None,
        "leaks_on_path": fugas,
        "hint": (
            "El camino son aristas de import, diferidas incluidas. Profundidad "
            "0 significa que el módulo ES kernel. Sin camino, el módulo no "
            "depende del núcleo por ningún import estático — lo que no impide "
            "que dependa de él por fichero o por variable global."
        ),
    }


def freeze(admitir_nuevos: bool = False) -> Dict[str, Any]:
    m = medir()
    firmas = sorted({firma(h) for h in m["hallazgos"]})
    base = set(_baseline())
    nuevos = sorted(set(firmas) - base)
    if nuevos and not admitir_nuevos:
        return vault_baseline.negativa(
            "vault_kernel", "freeze", "new_findings", nuevos,
            "Saca el módulo del kernel o dale forma de núcleo. Si de verdad "
            "hay que congelar deuda nueva, `--freeze --admitir-nuevos` la "
            "lista aquí.")
    vault_baseline.escribir(
        BASELINE, "sitios", "AP-59",
        "Módulos del kernel que no se comportan como núcleo y ya estaban "
        "cuando nació AP-59. Indexada por nombre de módulo. Solo puede "
        "encoger: un hallazgo nuevo se arregla, no se congela. Los ganchos del "
        "kernel tampoco entran aquí, y desde v40.24 ya no por falta de "
        "mecanismo: llevan `objetivo` propio en "
        "`vault_arch.GANCHOS_DEL_KERNEL` y el hallazgo es bloqueante.",
        firmas)
    return {"ok": True, "tool": "vault_kernel", "action": "freeze",
            "frozen": len(firmas),
            "admitted_new": nuevos if admitir_nuevos else []}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="vault_kernel — el núcleo derivado y trazado (AP-59)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--trace", metavar="MODULO",
                    help="camino más corto de un módulo hasta el núcleo")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    args = ap.parse_args()

    if args.freeze and (args.check or args.trace):
        env = emit_error("vault_kernel", "CONFLICTING_ARGS",
                         "--freeze y --check/--trace piden cosas distintas")
        env["recovery"] = "elige uno"
        print(json.dumps(env, ensure_ascii=False))
        return 1

    if args.trace:
        r = trace(args.trace)
    elif args.freeze:
        r = freeze(args.admitir_nuevos)
    else:
        r = check()
    print(json.dumps(r, ensure_ascii=False))
    return 1 if args.strict and not r.get("ok") else 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_kernel"))
