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
- **K3 — estabilidad.** Churn de `git log` **sobre comportamiento** (v41.3:
  un commit que solo cambia datos, docstrings o comentarios no cuenta; ver
  `huella_de_comportamiento`), contra la mediana del dominio
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
import ast
import hashlib
import json
import os
import statistics
import subprocess

import vault_subproceso
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from vault.kernel import procesos_git  # noqa: E402

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
#
# Vive en `vault/kernel/escalon.py` desde 2026-10-09: lo usa también el núcleo
# de un vault (`vault_audit`, deuda #11), y dos copias del criterio serían dos
# definiciones de «alto» (AP-57). Este nombre se conserva y es el mismo objeto.

if str(RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPO))

from vault.kernel.escalon import escalon  # noqa: E402


# ── K3: churn, y el `desconocido` que impide el cero fabricado ────────────────

def _hay_historia() -> bool:
    """Un clon de profundidad 1 —lo que hace `actions/checkout@v4` por defecto—
    daría un commit por fichero y K3 saldría verde por no haber mirado."""
    for args in (["rev-parse", "--git-dir"], ["rev-parse", "--is-shallow-repository"]):
        r = procesos_git.ejecutar_git(RAIZ_REPO, list(args),
                                      capture_output=True)
        if r.returncode != 0:
            return False
        if args[-1] == "--is-shallow-repository" and r.stdout.strip() == "true":
            return False
    return True


#: Commits que cambiaron el **comportamiento** de cada módulo (v41.3).
#: `None` = aún sin leer.
_CHURN: Optional[Dict[str, int]] = None
#: Commits que tocaron el fichero, sea lo que sea lo que cambiaran. Se
#: publica al lado del anterior y no decide nada.
_CHURN_BRUTO: Optional[Dict[str, int]] = None


def _churn_de_todos() -> Optional[Dict[str, int]]:
    """Un solo `git log`, no uno por módulo.

    Preguntarle a git fichero a fichero costaba 130 subprocesos y ~14 s, que es
    más de la mitad de lo que tarda la tanda entera de puertas. La medida es la
    misma: se recorre la historia una vez pidiendo los ficheros tocados por cada
    commit y se cuenta.
    """
    r = procesos_git.ejecutar_git(
        RAIZ_REPO, ["log", "--format=%H", "--name-only", "--", "scripts"],
        capture_output=True,
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
    """Commits que cambiaron el comportamiento de `scripts/<modulo>.py`.
    `None` = desconocido (AP-51).

    Un módulo que existe y nunca se tocó cuenta 0; uno cuya historia no se pudo
    leer cuenta `None`. La diferencia es toda la norma: el 0 fabricado saldría
    verde por no haber mirado. Qué cuenta como comportamiento lo dice
    `huella_de_comportamiento`; el recuento de todo commit es `churn_bruto`.
    """
    global _CHURN
    if _CHURN is None:
        _CHURN = _churn_de_comportamiento()
    if _CHURN is None:
        return None
    return _CHURN.get(modulo, 0)


def churn_bruto(modulo: str) -> Optional[int]:
    """Commits que tocaron `scripts/<modulo>.py`, cambiaran lo que cambiaran.

    Era la medida de K3 hasta v41.2. Se sigue publicando para que la distancia
    entre las dos cifras —cuánto se mueve un módulo solo en sus datos— quede a
    la vista y no se pueda esconder dentro del criterio.
    """
    global _CHURN_BRUTO
    if _CHURN_BRUTO is None:
        _CHURN_BRUTO = _churn_de_todos()
    if _CHURN_BRUTO is None:
        return None
    return _CHURN_BRUTO.get(modulo, 0)


# ── K3 sobre comportamiento: qué commits cambian el módulo y no solo sus datos ─
#
# v41.3. El churn bruto cuenta **cualquier** commit que toca el fichero, y eso
# convertía a un registro en inestable por hacer lo que es: crecer.
# `vault_norms_catalog` llegó a 23 commits contra un umbral de 23,24 y cada
# norma nueva lo habría cruzado, aunque 17 de esos 23 solo añadían o
# corregían entradas de `NORM_CATALOG` sin tocar una línea de lo que el
# catálogo **hace**. La norma afirma que el núcleo se mueve menos que lo que
# sostiene; lo que sus consumidores sufren al moverse es el comportamiento —sus
# funciones, sus clases, sus nombres—, no el contenido de una tabla.
#
# El criterio es del consumidor (AP-44), no de esta tool: la huella sale de
# `ast`, la misma lectura que hace el intérprete. Comentarios, docstrings y el
# **valor** de una asignación literal de nivel de módulo no cuentan; el
# **nombre** de esa asignación sí, así que crear o retirar una constante es un
# cambio. Un `re.compile`, una comprensión o cualquier llamada no son literales
# y cuentan siempre. Se aplica a los dos lados de la comparación —núcleo y
# dominio— con la misma vara: medir el núcleo en comportamiento contra un
# dominio en bruto sería regalarle margen.
#
# Qué NO ve: un literal que gobierna comportamiento (un umbral escrito como
# número) cambia sin contar. Es la frontera que la propia norma ya traza entre
# declarar y decidir, y el churn bruto sigue publicándose al lado.


def _es_literal(nodo: ast.AST) -> bool:
    if isinstance(nodo, ast.Constant):
        return True
    if isinstance(nodo, (ast.List, ast.Tuple, ast.Set)):
        return all(_es_literal(e) for e in nodo.elts)
    if isinstance(nodo, ast.Dict):
        return (all(k is None or _es_literal(k) for k in nodo.keys)
                and all(_es_literal(v) for v in nodo.values))
    if isinstance(nodo, ast.UnaryOp):
        return _es_literal(nodo.operand)
    return False


def _es_docstring(sentencia: ast.AST) -> bool:
    return (isinstance(sentencia, ast.Expr)
            and isinstance(sentencia.value, ast.Constant)
            and isinstance(sentencia.value.value, str))


def huella_de_comportamiento(fuente: bytes) -> str:
    """Lo que un commit tiene que cambiar para contar en K3. Pura.

    Un fichero que no parsea devuelve el hash de sus bytes: cualquier cambio
    suyo cuenta, que es la lectura conservadora.
    """
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError):
        return "bytes:" + hashlib.sha256(fuente).hexdigest()
    partes: List[str] = []
    for s in arbol.body:
        if _es_docstring(s):
            continue
        if isinstance(s, ast.Assign) and _es_literal(s.value):
            partes.append("dato:" + "|".join(ast.dump(t) for t in s.targets))
            continue
        if isinstance(s, ast.AnnAssign) and s.value is not None and _es_literal(s.value):
            partes.append("dato:" + ast.dump(s.target))
            continue
        for n in ast.walk(s):
            if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and n.body and _es_docstring(n.body[0])):
                n.body = n.body[1:] or [ast.Pass()]
        partes.append(ast.dump(s))
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


def _cambios_de_todos() -> Optional[List[Tuple[str, str, str]]]:
    """`(módulo, blob_antes, blob_después)` por commit, de un solo `git log`."""
    r = procesos_git.ejecutar_git(
        RAIZ_REPO,
        ["log", "--format=%H", "--raw", "--no-abbrev", "--", "scripts"],
        capture_output=True,
    )
    if r.returncode != 0:
        return None
    return _cambios_de_raw(r.stdout)


def _cambios_de_raw(salida: str) -> List[Tuple[str, str, str]]:
    """`(módulo, blob_antes, blob_después)` de una salida `--raw --no-abbrev`.

    Una sola lectura para la historia y para el índice: si cada una parseara
    el formato por su cuenta, el aviso del pre-commit podría contar un cambio
    que la medida canónica no cuenta, o al revés.
    """
    cambios: List[Tuple[str, str, str]] = []
    for linea in salida.splitlines():
        if not linea.startswith(":"):
            continue
        meta, _, rutas = linea.partition("\t")
        ruta = rutas.split("\t")[-1]
        campos = meta.split()
        if (len(campos) >= 4 and ruta.startswith("scripts/")
                and ruta.endswith(".py") and ruta.count("/") == 1):
            cambios.append((ruta[len("scripts/"):-len(".py")], campos[2], campos[3]))
    return cambios


def _leer_blobs(ids: Sequence[str]) -> Optional[Dict[str, bytes]]:
    """Todos los blobs por un único `git cat-file --batch`."""
    entrada = "".join(f"{i}\n" for i in ids).encode("ascii")
    r = procesos_git.ejecutar_git(RAIZ_REPO, ["cat-file", "--batch"],
                                 # binario=True: la cabecera da el tamaño en
                                 # bytes y el cuerpo se mide en bytes; en modo
                                 # texto el pipe no cuadra (ver procesos_git).
                                 binario=True,
                                 input=entrada, capture_output=True)
    if r.returncode != 0:
        return None
    salida, pos, blobs = r.stdout, 0, {}
    for i in ids:
        fin = salida.index(b"\n", pos)
        cabecera = salida[pos:fin].split()
        pos = fin + 1
        if len(cabecera) < 3 or cabecera[-1] == b"missing":
            return None
        n = int(cabecera[2])
        blobs[i] = salida[pos:pos + n]
        pos += n + 1
    return blobs


def _huellas(blobs: Dict[str, bytes]) -> Dict[str, str]:
    """En paralelo: parsear ~2.400 versiones en serie cuesta ~15 s, más que el
    resto de la tanda de puertas. Si el pool no arranca, en serie: más lento,
    nunca un resultado distinto."""
    ids = sorted(blobs)
    try:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
            valores = list(pool.map(huella_de_comportamiento,
                                    (blobs[i] for i in ids), chunksize=32))
    except (OSError, RuntimeError):
        valores = [huella_de_comportamiento(blobs[i]) for i in ids]
    return dict(zip(ids, valores))


def _ruta_huellas() -> Optional[Path]:
    """Dónde se guardan las huellas ya calculadas: dentro del directorio de git.

    No se versiona, desaparece con el clon y la comparten los worktrees
    (`--git-common-dir`). Sin git no hay historia que medir ni que guardar.
    """
    r = procesos_git.ejecutar_git(RAIZ_REPO, ["rev-parse", "--git-common-dir"],
                                 capture_output=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    base = Path(r.stdout.strip())
    return (base if base.is_absolute() else RAIZ_REPO / base) / "vault-kernel-huellas.json"


def _clave_de_huella() -> str:
    """Qué invalida lo guardado: el código de la huella y el intérprete.

    `ast.dump` cambia entre versiones de Python, así que una huella de 3.12 no
    es comparable con una de 3.14 aunque el blob sea el mismo.
    """
    import inspect
    fuente = "".join(inspect.getsource(f) for f in (
        _es_literal, _es_docstring, huella_de_comportamiento))
    return hashlib.sha256(f"{sys.version_info[:2]}\n{fuente}".encode("utf-8")).hexdigest()


def _huellas_guardadas(ruta: Optional[Path], clave: str) -> Dict[str, str]:
    """Lo guardado con esta clave. Ilegible u otra clave: nada, y se recalcula.

    Recalcular da la misma cifra que leer —la huella es pura—, así que aquí
    un vacío no esconde nada: solo cuesta tiempo (no es el vacío de AP-51).
    """
    if ruta is None or not ruta.is_file():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(datos, dict) or datos.get("clave") != clave:
        return {}
    huellas = datos.get("huellas")
    return dict(huellas) if isinstance(huellas, dict) else {}


def _guardar_huellas(ruta: Optional[Path], clave: str, huellas: Dict[str, str]) -> None:
    """Escritura atómica; si falla, la próxima medida recalcula y nada más."""
    if ruta is None:
        return
    tmp = ruta.with_name(f"{ruta.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps({"clave": clave, "huellas": huellas}), encoding="utf-8")
        os.replace(tmp, ruta)
    except OSError:
        tmp.unlink(missing_ok=True)


def _huellas_de(ids: Sequence[str]) -> Optional[Dict[str, str]]:
    """La huella de cada blob, calculando solo las que no estaban guardadas.

    Hasta la auditoría del 2026-10-15 se leían y parseaban todas las versiones
    históricas en cada ejecución: ~2.400 blobs y 12,7 s de 13,8, creciendo con
    cada commit aunque el trabajo nuevo fuese uno. Un blob es inmutable y su
    huella pura, así que lo ya calculado no se vuelve a calcular.
    """
    ruta, clave = _ruta_huellas(), _clave_de_huella()
    guardadas = _huellas_guardadas(ruta, clave)
    faltan = [i for i in ids if i not in guardadas]
    if faltan:
        blobs = _leer_blobs(faltan)
        if blobs is None:
            return None
        guardadas.update(_huellas(blobs))
        _guardar_huellas(ruta, clave, guardadas)
    return {i: guardadas[i] for i in ids}


def _churn_de_comportamiento() -> Optional[Dict[str, int]]:
    cambios = _cambios_de_todos()
    if cambios is None:
        return None
    # El blob nulo de git —el «antes» de un alta, el «después» de una baja—
    # se reconoce por ser todo ceros, no por su longitud: SHA-256 lo alarga.
    ids = sorted({b for _, a, d in cambios for b in (a, d) if set(b) != {"0"}})
    huella = _huellas_de(ids)
    if huella is None:
        return None
    cuenta: Dict[str, int] = {}
    for modulo, antes, despues in cambios:
        if huella.get(antes) != huella.get(despues):
            cuenta[modulo] = cuenta.get(modulo, 0) + 1
    return cuenta


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
    brutos = {m: (churn_bruto(m) if con_historia else None) for m in kernel}
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
        "churn_bruto": brutos,
        "churn_criterio": "comportamiento",
        "modules": len(G),
    }


# ── K3 sobre el commit en curso: aviso, no medida ─────────────────────────────
#
# Deuda #15, decidida el 2026-10-08. `churn()` cuenta con `git log` y por eso
# la puerta que corre antes de commitear no ve el commit que se está haciendo:
# el que cruza el umbral pasa en verde y el siguiente —aunque no toque el
# módulo— hereda el rojo. Contar el índice dentro de `churn()` lo arreglaría a
# costa de que la misma medida diera cifras distintas antes y después de
# commitear, y la CI mide después. Así que la cifra canónica no cambia: el
# índice se lee aparte, con el mismo criterio de comportamiento, y solo para
# avisar a quien commitea de que va a cruzar el umbral.


def _cambios_del_indice() -> Optional[List[Tuple[str, str, str]]]:
    r = procesos_git.ejecutar_git(
        RAIZ_REPO,
        ["diff", "--cached", "--raw", "--no-abbrev", "--", "scripts"],
        capture_output=True,
    )
    if r.returncode != 0:
        return None
    return _cambios_de_raw(r.stdout)


def aviso_del_indice() -> Dict[str, Any]:
    """Módulos del kernel que el commit en curso haría cruzar el umbral de K3.

    Solo lectura y nunca bloquea: es un aviso del pre-commit, no una puerta.
    Un módulo que ya está por encima no se repite aquí —ese ya lo ve la
    puerta—; el aviso es para el que **cruza** con este commit.
    """
    base = {"tool": "vault_kernel", "action": "aviso_indice"}
    cambios = _cambios_del_indice()
    if cambios is None:
        return {**base, "ok": True, "avisos": [], "indice_leido": False,
                "hint": "no se pudo leer el índice de git: sin aviso, y eso "
                        "no dice que el commit no cruce el umbral"}
    m = medir()
    kernel = set(m["kernel"])
    umbral = m["umbral_churn"]
    del_kernel = [c for c in cambios if c[0] in kernel]
    ids = sorted({b for _, a, d in del_kernel for b in (a, d) if set(b) != {"0"}})
    blobs = _leer_blobs(ids) if ids else {}
    if blobs is None:
        return {**base, "ok": True, "avisos": [], "indice_leido": False,
                "hint": "no se pudieron leer los blobs del índice: sin aviso, "
                        "y eso no dice que el commit no cruce el umbral"}
    huella = {i: huella_de_comportamiento(b) for i, b in blobs.items()}
    avisos: List[Dict[str, Any]] = []
    for modulo, antes, despues in del_kernel:
        if huella.get(antes) == huella.get(despues):
            continue
        c = m["churn"].get(modulo)
        if c is None or umbral is None or not (c < umbral <= c + 1):
            continue
        avisos.append({
            "module": modulo, "churn": c, "churn_tras_el_commit": c + 1,
            "umbral_churn": umbral,
            "why": (f"este commit cambia el comportamiento de un módulo del "
                    f"núcleo y lo lleva de {c} a {c + 1} ≥ {umbral}: la "
                    "puerta pasa ahora y el commit siguiente heredará el rojo"),
        })
    return {
        **base, "ok": True, "avisos": avisos, "indice_leido": True,
        "hint": ("Aviso, no medida: la cifra canónica de K3 sigue siendo la "
                 "de `git log`, la que mide la CI después del commit. Si el "
                 "módulo de verdad tiene que cambiar, el arreglo es darle "
                 "forma de núcleo o sacarlo del kernel, no ampliar la baseline."),
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
        "churn_criterion": m["churn_criterio"],
        "raw_churn": m["churn_bruto"],
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
        env = emit_error("vault_kernel", "MODULE_NOT_FOUND",
                         f"no existe scripts/{modulo}.py",
                         pista="usa el stem del módulo, sin ruta ni extensión")
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
        description="vault_kernel — el núcleo derivado y trazado (AP-59)", allow_abbrev=False)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--trace", metavar="MODULO",
                    help="camino más corto de un módulo hasta el núcleo")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--admitir-nuevos", action="store_true")
    ap.add_argument("--aviso-indice", action="store_true",
                    help="avisa si el commit en curso haría cruzar el umbral "
                         "de K3 a un módulo del núcleo; nunca falla")
    args = ap.parse_args()

    if args.freeze and (args.check or args.trace):
        env = emit_error("vault_kernel", "CONFLICTING_ARGS",
                         "--freeze y --check/--trace piden cosas distintas",
                         pista="elige uno")
        print(json.dumps(env, ensure_ascii=False))
        return 1

    if args.aviso_indice:
        print(json.dumps(aviso_del_indice(), ensure_ascii=False))
        return 0
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
