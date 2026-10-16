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

from __future__ import annotations


import ast
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Set

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


def _dueno_del_alias(ruta: Path) -> str | None:
    """El módulo dueño si `ruta` es un alias del puente, o None.

    La forma del alias es la de la deuda #12: `import vault.<ctx>.<n> as _dueno`
    seguido de `sys.modules[__name__] = _dueno`, al nivel del módulo o en la
    rama `else` del alias de una tool con CLI. Se reconoce por esa
    asignación, no por el nombre del fichero: un módulo que solo importa de
    `vault/` delega, pero sigue teniendo código propio.
    """
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return None
    ligados: Dict[str, str] = {}
    # `ast.walk` y no `arbol.body`: el alias de una tool con CLI va dentro de
    # `if __name__ == "__main__": ... else: ...` (runpy en una rama).
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                if a.asname and a.name.startswith("vault."):
                    ligados[a.asname] = a.name
        elif isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Name):
            for t in nodo.targets:
                if (isinstance(t, ast.Subscript)
                        and ast.unparse(t) == "sys.modules[__name__]"
                        and nodo.value.id in ligados):
                    return ligados[nodo.value.id]
    return None


def _ruta_de_paquete(dueno: str) -> Path | None:
    """`vault.kernel.x` → su fichero: en el checkout, junto a `scripts/`;
    instalado, donde lo encuentre el import, sin importarlo."""
    candidato = DIRECTORIO.parent.joinpath(*dueno.split(".")).with_suffix(".py")
    if candidato.is_file():
        return candidato.resolve()
    import importlib.util

    try:
        spec = importlib.util.find_spec(dueno)
    except (ImportError, ValueError):
        return None
    return Path(spec.origin).resolve() if spec and spec.origin else None


@lru_cache(maxsize=1)
def _puente() -> Dict[str, Path]:
    """Alias de `scripts/` → fichero de su dueño. Se deriva del disco."""
    out: Dict[str, Path] = {}
    for p in DIRECTORIO.glob("*.py"):
        dueno = _dueno_del_alias(p)
        destino = _ruta_de_paquete(dueno) if dueno else None
        if destino is not None:
            out[p.stem] = destino
    return out


def fuente_de(modulo: str) -> Path:
    """El fichero que tiene el código de `modulo` (nombre de `scripts/`).

    Tras la deuda #12 un nombre de `scripts/` puede ser un alias sin código; un
    guard que lea `scripts/<m>.py` como fuente mide el alias y no al dueño. Un
    solo sitio resuelve eso (AP-57) y los guards lo consultan.
    """
    return _puente().get(modulo, (DIRECTORIO / f"{modulo}.py").resolve())


def codigo_de(ruta: Path) -> Path:
    """El fichero cuyo código hay que leer para medir `ruta`.

    Si `ruta` es un `scripts/<m>.py`, su código es el de `fuente_de(m)`: un
    alias migrado no tiene código propio. Cualquier otra ruta —incluidos los
    `.json` y `.md` que viven en `scripts/`— es su propio código. Los lectores por ruta (guards, escáneres, tests de propiedad) pasan
    por aquí en vez de decidir cada uno si `ruta` es alias (AP-57).
    """
    ruta = Path(ruta)
    if ruta.suffix == ".py" and ruta.parent.resolve() == DIRECTORIO:
        return fuente_de(ruta.stem)
    return ruta


def nombre_de(ruta: Path) -> str:
    """El nombre de `scripts/` por el que se conoce a `ruta`: el del alias si
    `ruta` es el dueño de uno, o su propio nombre."""
    ruta = Path(ruta).resolve()
    for alias, dueno in _puente().items():
        if dueno == ruta:
            return alias
    return ruta.stem


def _fichero_de_modulo(nombre: str) -> Path | None:
    """`vault.<ctx>.<m>` → su fichero, o el `__init__.py` si es un paquete."""
    ruta = _ruta_de_paquete(nombre)
    if ruta is not None and ruta.suffix == ".py" and ruta.is_file():
        return ruta
    init = DIRECTORIO.parent.joinpath(*nombre.split("."), "__init__.py")
    return init.resolve() if init.is_file() else None


def _contextos_importados(ruta: Path) -> List[Path]:
    """Los módulos de `vault/` fuera del kernel que `ruta` importa arriba.

    Solo nivel superior: un import diferido no es la tool partiéndose, es un
    préstamo puntual. El kernel se excluye porque es de todos: contarlo daría
    a cada tool la traza de las normas que el núcleo nombra.
    """
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []
    nombres: List[str] = []
    for nodo in arbol.body:
        if isinstance(nodo, ast.Import):
            nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.append(nodo.module)
            nombres += [f"{nodo.module}.{a.name}" for a in nodo.names]
    fuera: List[Path] = []
    for n in nombres:
        if not n.startswith("vault.") or n == "vault.kernel" or n.startswith("vault.kernel."):
            continue
        f = _fichero_de_modulo(n)
        if f is not None and f not in fuera:
            fuera.append(f)
    return fuera


def partes_de(tool: str, contextos: bool = True) -> List[Path]:
    """Los ficheros que forman `tool`: dónde puede estar la función que la cumple.

    Son tres, y los tres se derivan del disco:

    - el dueño de la tool (`fuente_de`, que sigue el alias del puente);
    - los hermanos `{tool}_*` que importa arriba: una tool sigue siendo una
      cuando su fichero se trocea (`vault_norms` → catálogo + motor);
    - los módulos de `vault/<ctx>/` fuera del kernel que importan la tool o
      sus hermanos: `vault_norms --audit` delega en
      `vault.gobernanza.auditoria_runtime`, y es allí donde nombra AP-10.

    Es el universo que comparten C2 de `vault_norms_coherence` y la cara
    `guard.py` de cada norma, para que «tiene traza» y «la detecta esta
    función» no se decidan con dos criterios (AP-57).

    `contextos=False` se queda en el dueño y sus hermanos: la cara `heal.py`
    lo usa porque el contexto al que delega una tool que repara puede ser el
    que solo detecta —`vault_norms` repara AP-46 en `heal_ap46` y la detecta
    en `auditar_runtime`—, y una cara de reparación que apunta a un detector
    afirma un heal que no existe.
    """
    base = fuente_de(tool)
    if not base.is_file():
        return []
    partes = [base]
    try:
        cuerpo = ast.parse(base.read_text(encoding="utf-8", errors="ignore")).body
    except SyntaxError:
        cuerpo = []
    for nodo in cuerpo:
        if (isinstance(nodo, ast.ImportFrom) and nodo.module
                and nodo.module.startswith(f"{tool}_")):
            hermano = fuente_de(nodo.module)
            if hermano.is_file() and hermano not in partes:
                partes.append(hermano)
    for p in (list(partes) if contextos else []):
        for ctx in _contextos_importados(p):
            if ctx not in partes:
                partes.append(ctx)
    return partes


def _cuerpo_sin_docstring(lineas: List[str], nodo: ast.AST) -> str:
    """Las líneas del cuerpo, comentarios incluidos, sin la docstring: un
    comentario que nombra la norma en la función que la cumple cuenta (capa 4),
    y la docstring que la menciona de pasada, no."""
    cuerpo = nodo.body
    if ast.get_docstring(nodo, clean=False) is not None:
        cuerpo = cuerpo[1:]
    if not cuerpo:
        return ""
    # El comentario que encabeza el cuerpo va antes de la primera sentencia y
    # el AST no lo ve: se sube por las líneas de comentario hasta la docstring
    # o la firma.
    inicio = cuerpo[0].lineno - 1
    while inicio > 0 and lineas[inicio - 1].lstrip().startswith("#"):
        inicio -= 1
    return "".join(lineas[inicio:nodo.end_lineno])


def funciones_que_nombran(ruta: Path, code: str) -> List[str]:
    """Las funciones de `ruta` que nombran `code` en su cuerpo, en orden.

    Es el criterio de «la norma se nombra en la función que la cumple»: una
    declaración a nivel de módulo —un registro, una tabla— no es una función
    que la cumpla. Solo la más interna: la externa contiene a la anidada y
    citarla sería señalar el módulo entero. `AP-1` no casa dentro de `AP-14`.
    """
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    patron = re.compile(rf"(?<![\w-]){re.escape(code)}(?!\d)")
    if not patron.search(texto):
        return []
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return []
    lineas = texto.splitlines(keepends=True)
    hit = [n for n in ast.walk(arbol)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and patron.search(_cuerpo_sin_docstring(lineas, n))]
    ids = {id(h) for h in hit}
    internas = [h for h in hit
                if not any(id(d) in ids for d in ast.walk(h) if d is not h)]
    vistos: List[str] = []
    for h in sorted(internas, key=lambda h: h.lineno):
        if h.name not in vistos:
            vistos.append(h.name)
    return vistos


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
            return _ast_cacheado(ruta, PREFIJO_VAULT)
        except SyntaxError:
            return None
    try:
        return _ast_cacheado(ruta, MODULOS_LOCALES)
    except (SyntaxError, UnicodeDecodeError) as e:
        raise RuntimeError(f"módulo ilegible al medir imports: {ruta.name}") from e


@lru_cache(maxsize=None)
def _arbol_firma(ruta: str, mtime_ns: int, size: int, proyeccion: str) -> ast.AST | None:
    """El árbol de `_arbol`, cacheado por firma del fichero (v40.34).

    `vault_arch._importaciones` y `vault_ciclos._grafo` llaman a `_arbol`
    cientos de veces por ejecución; cada llamada re-leía y re-parseaba el
    fichero. La firma incluye `mtime_ns` y `size` para que un test que muta un
    fichero entre llamadas siga viendo el cambio.

    Conserva la semántica de cada proyección: la tolerante lee con `replace` y
    devuelve `None` ante `SyntaxError`; la estricta lee sin `replace` para que
    un fichero ilegible levante `UnicodeDecodeError` y, con él, el `RuntimeError`
    de AP-51.
    """
    if proyeccion == PREFIJO_VAULT:
        try:
            return ast.parse(Path(ruta).read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return None
    return ast.parse(Path(ruta).read_text(encoding="utf-8"))


def _ast_cacheado(ruta: Path, proyeccion: str) -> ast.AST | None:
    """Envoltorio de `_arbol_firma` que computa la firma del fichero.

    Se separa del cuerpo cacheado para que la firma —dos `stat` por fichero, que
    cuestan— solo se calcule cuando el árbol de esa ruta no esté ya en caché.
    """
    st = ruta.stat()
    return _arbol_firma(str(ruta), st.st_mtime_ns, st.st_size, proyeccion)


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
        # Un alias de la deuda #12 no tiene imports propios: sus aristas son las
        # de su dueño. Leer `p` lo dejaba con fan-out 0 (AP-44).
        arbol = _arbol(codigo_de(p), MODULOS_LOCALES)
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
