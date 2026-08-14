#!/usr/bin/env python3
"""vault_grafo_import — el dueño único del grafo de imports de `scripts/`.

## De dónde sale

Trece módulos de este repo parseaban imports por su cuenta con `ast`. Once son
usos puntuales, pero **los dos principales no coincidían**, y esa es la parte
cara: `vault_arch._importaciones` y `vault_ciclos._grafo` respondían a la misma
pregunta —«¿qué importa este módulo?»— con dos criterios distintos.

`vault_criterios` (AP-57) no podía verlo: solo mide módulos que nombran `*.md`.
Así que el criterio más básico de todo el análisis estructural del repo estaba
escrito dos veces, sin dueño y sin nadie comparándolo.

## Las dos proyecciones, y por qué NO se unifican aquí

Las dos semánticas se conservan **con nombre**, no se funden:

- `PREFIJO_VAULT` (la de `vault_arch`): filtra por el prefijo `vault_`, exige
  `level == 0` —ignora los imports relativos— y es **tolerante**: un módulo con
  `SyntaxError` devuelve el conjunto vacío.
- `MODULOS_LOCALES` (la de `vault_ciclos`): filtra por pertenencia real a
  `scripts/*.py`, **acepta imports relativos** (`from .foo import x` cuenta como
  `foo`) y es **estricta**: un módulo ilegible levanta `RuntimeError`, porque
  contarlo como módulo sin aristas lo sacaría de todo ciclo y saldría verde por
  no haber mirado (AP-51).

Fundirlas cambiaría los cruces de `vault_arch` y las aristas de `vault_ciclos`
—es decir, estrenaría deuda en dos baselines por un refactor que no arregla
nada—. Unificar el criterio es una decisión de diseño aparte y está declarada
como deuda. Lo que esta pieza cierra es el **dueño**: hay un solo sitio donde
se lee un `import`, y las diferencias que quedan son explícitas y tienen nombre.

## Qué NO demuestra tener este dueño

Mide el grafo **estático de módulos de `scripts/`**. No ve `importlib`, ni un
import construido con una cadena, ni el acoplamiento que pasa por el sistema de
ficheros o por una variable global compartida. Dos módulos pueden estar atados
sin que ningún `import` lo diga, y este módulo los verá sueltos.

## Por qué vive en el kernel y no importa nada

Fan-out cero, solo stdlib. Es la condición para que lo pueda consumir cualquiera
—incluido `vault_arch`, que está por encima— sin crear un ciclo. Un dueño de
criterio que importa a sus consumidores no es un dueño: es un nudo.
"""

import ast
from pathlib import Path
from typing import Dict, Iterable, Set

DIRECTORIO = Path(__file__).resolve().parent

#: La proyección de `vault_arch`: prefijo `vault_`, sin relativos, tolerante.
PREFIJO_VAULT = "prefijo_vault"

#: La proyección de `vault_ciclos`: pertenencia a `scripts/`, con relativos,
#: estricta ante un módulo ilegible.
MODULOS_LOCALES = "modulos_locales"

PROYECCIONES = (PREFIJO_VAULT, MODULOS_LOCALES)


def modulos() -> Set[str]:
    """Los módulos que existen en disco. El universo de `MODULOS_LOCALES`."""
    return {p.stem for p in DIRECTORIO.glob("*.py")}


def _nombres_importados(nodo: ast.AST, proyeccion: str) -> Iterable[str]:
    """Los nombres que este nodo de import trae, según la proyección.

    Las dos diferencias reales están aquí y en ningún otro sitio: qué se hace
    con `ast.ImportFrom` cuando `level != 0`, y si el nombre se recorta al
    primer segmento.
    """
    if isinstance(nodo, ast.Import):
        for alias in nodo.names:
            yield alias.name.split(".")[0]
        return
    if not isinstance(nodo, ast.ImportFrom):
        return
    if proyeccion == PREFIJO_VAULT:
        # `level == 0` deja fuera los relativos: `vault_arch` los ignora
        # a propósito, porque sus fronteras son entre módulos de nivel superior.
        if nodo.module and nodo.level == 0:
            yield nodo.module.split(".")[0]
        return
    # MODULOS_LOCALES cuenta el relativo: `from .foo import x` ata igual.
    yield (nodo.module or "").split(".")[0]


def _en_funcion(arbol: ast.AST) -> Set[int]:
    """Los `id()` de los nodos que cuelgan de alguna función.

    Un import aquí dentro es el rompe-ciclos manual, y la distinción entre
    estar dentro o fuera **es** lo que mide AP-58. Se calcula por identidad de
    nodo y no por número de línea porque un decorador o un `if` de por medio
    desplazan la línea sin cambiar la pertenencia.
    """
    dentro: Set[int] = set()
    for f in ast.walk(arbol):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                dentro.add(id(n))
    return dentro


def _arbol(ruta: Path, proyeccion: str) -> ast.AST | None:
    """Devuelve None solo donde la proyección tolerante lo permite.

    AP-51: en `MODULOS_LOCALES` un fichero ilegible **no** se lee como un módulo
    sin imports. Ese silencio lo sacaría de todos los ciclos y el cero saldría
    fabricado, que es el defecto que AP-58 existe para impedir.
    """
    if proyeccion == PREFIJO_VAULT:
        try:
            return ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return None
    try:
        return ast.parse(ruta.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as e:
        raise RuntimeError(f"módulo ilegible al medir imports: {ruta.name}") from e


def importaciones(ruta: Path, proyeccion: str = PREFIJO_VAULT) -> Set[str]:
    """Los módulos que importa este fichero, estén el `import` donde esté.

    Cuenta los imports diferidos dentro de una función igual que los de
    cabecera: un `import vault_norms` escondido en un `try:` cruza la frontera
    exactamente igual. Quien necesite distinguirlos usa `grafo()`.
    """
    if proyeccion not in PROYECCIONES:
        raise ValueError(f"proyección desconocida: {proyeccion!r}")
    arbol = _arbol(ruta, proyeccion)
    if arbol is None:
        return set()
    universo = None if proyeccion == PREFIJO_VAULT else modulos()
    fuera: Set[str] = set()
    for nodo in ast.walk(arbol):
        for nombre in _nombres_importados(nodo, proyeccion):
            if proyeccion == PREFIJO_VAULT:
                if nombre.startswith("vault_"):
                    fuera.add(nombre)
            elif nombre in universo and nombre != ruta.stem:
                fuera.add(nombre)
    return fuera


def grafo() -> Dict[str, Dict[str, Set[str]]]:
    """Aristas de import separadas por dónde está el `import`.

    `top` es lo que ve cualquier lector; `diferido` es lo que el rompe-ciclos
    manual escondió dentro de una función. La distinción ES la medida: sin ella
    el grafo sale acíclico y la pregunta no se puede ni formular.

    Proyección `MODULOS_LOCALES`: es la que necesita el análisis de ciclos.
    """
    mods = modulos()
    top: Dict[str, Set[str]] = {}
    dif: Dict[str, Set[str]] = {}
    for p in sorted(DIRECTORIO.glob("*.py")):
        arbol = _arbol(p, MODULOS_LOCALES)
        assert arbol is not None  # MODULOS_LOCALES levanta, nunca devuelve None
        dentro = _en_funcion(arbol)
        top.setdefault(p.stem, set())
        dif.setdefault(p.stem, set())
        for n in ast.walk(arbol):
            for nombre in _nombres_importados(n, MODULOS_LOCALES):
                if nombre in mods and nombre != p.stem:
                    destino = dif if id(n) in dentro else top
                    destino[p.stem].add(nombre)
    return {"top": top, "diferido": dif}


def completo(g: Dict[str, Dict[str, Set[str]]] | None = None) -> Dict[str, Set[str]]:
    """El grafo con las dos clases de arista fundidas: quién puede llegar a quién."""
    g = g if g is not None else grafo()
    return {m: g["top"].get(m, set()) | g["diferido"].get(m, set())
            for m in modulos()}


def fan_out(G: Dict[str, Set[str]] | None = None) -> Dict[str, Set[str]]:
    """De quién depende cada módulo. Bajo = barato de mover."""
    return dict(G if G is not None else completo())


def fan_in(G: Dict[str, Set[str]] | None = None) -> Dict[str, Set[str]]:
    """Quién depende de cada módulo. Alto = caro de romper.

    Se deriva invirtiendo `fan_out` en vez de recorrer el disco otra vez: dos
    recorridos con dos criterios es exactamente el defecto que este módulo cierra.
    """
    G = G if G is not None else completo()
    fuera: Dict[str, Set[str]] = {m: set() for m in G}
    for origen, destinos in G.items():
        for d in destinos:
            fuera.setdefault(d, set()).add(origen)
    return fuera
