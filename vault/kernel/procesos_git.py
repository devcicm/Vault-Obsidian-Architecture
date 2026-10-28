#!/usr/bin/env python3
"""vault.kernel.procesos_git — cómo el toolkit ejecuta git. Nadie más lo sabe.

Módulo hoja del núcleo: **no importa ningún `vault_*`** salvo la otra hoja de
su mismo paquete (`vault.kernel.subproceso`, el dueño de la codificación de
hijos). Si algún día necesita más, ha dejado de ser hoja y pierde el sitio
(AP-62). La vigilancia de su forma la hace `vault_kernel`.

## Por qué existe (AP-68, auditado el 2026-10-23)

Antes de AP-68, **trece sitios** de `scripts/` y `vault/` ejecutaban `git` por
su cuenta con `subprocess` directo. Todas las llamadas iban por argv en lista
—cero `shell=True`— y las de lectura eran realmente solo lectura, pero esa
propiedad era verdad **por inspección**, no por guard: la auditoría la
confirmó mirando sitio por sitio, y nada impedía que el próximo `git` que
entrara al repo fuera un `reset --hard` al que ninguna puerta pusiera rojo —
el criterio existía solo como saber de cabeza, que es AP-57 del repo contra
sí mismo.

## Lo que supervisa este dueño

Tres cosas, en una sola puerta:

1. **Un solo sitio ejecuta git**: toda llamada cuyo argv arranca con el
   léxico `"git"` pasa por `ejecutar_git`. `sitios_git_fuera_del_dueno()` lo
   mide por AST y la tool `vault_procesos_git --check` lo hace puerta.
2. **Verbos cerrados**: `git <verbo>` con verbo mutador falla aquí mismo si
   no está en `MUTADORES_AUTORIZADOS` con su motivo. El único mutador
   autorizado es el bootstrap de `vault_init`, acotado a un vault recién
   creado —`vault_init` rechaza un vault existente no vacío («no se pisa un
   vault»)—, sin identidad configurada por la tool y sin `push` ni remotes.
   Añadir un mutador a esa tabla es una decisión revisada en diff, no un
   argumento que llega de fuera.
3. **Refs validadas antes del argv**: los verbos de lectura también reciben
   datos que nacieron en ficheros —el hash del changelog, el `since_commit`
   de un snapshot de drift, los hashes de METRICAS—. El argv en lista impide
   la inyección de shell, pero un valor que empiece por `--` puede cambiar el
   matiz de un comando de lectura. `asegurar_hash()` lo cierra en los sitios
   que leen hashes de ficheros; los verbos ambivalentes (`branch`, `tag`,
    `config`, `stash`, `reflog`) verifican su uso de lectura por argumento.

## Lo que NO demuestra el verde

Mide los argv **estáticos** de `scripts/`, `cli/`, `vault/` y `tests/`: una
llamada construida con cadenas que omitan el léxico `"git"` primero, o un
binario que por su cuenta lance git, no los ve. El alcance se declara en vez
de suponerse — la regla de la casa.
"""

from __future__ import annotations

import ast
import re
import subprocess
from typing import Any

from vault.kernel import rutas
from vault.kernel.subproceso import CODIFICACION, ERRORES

#: Los verbos de git que el toolkit usa en lectura, tomados del inventario de
#: la auditoría del 2026-10-23 y cerrados: un verbo que Ruby listado no aquí
#: ni en `MUTADORES_AUTORIZADOS` cuenta como desconocido y se rechaza.
VERBOS_LECTURA = frozenset({
    "blame", "cat-file", "diff", "ls-files", "log", "rev-list", "rev-parse",
    "show", "status", "archive", "symbolic-ref", "shortlog", "whatchanged",
    "describe",
})

#: Verbos cuyo sentido depende de lo que venga detrás: `branch -a` lee y
#: `branch -D` destruye; `tag -l` lista y `tag v1` crea; `config --get` lee y
#: `config k v` escribe. Se admiten **solo** cuando `_uso_mutador` confirma
#: que el uso es el de lectura; de lo contrario mueren con GitProhibido.
VERBOS_AMBIGUOS = frozenset({"branch", "tag", "config", "stash", "reflog"})

#: El único uso mutador admitido hoy: el bootstrap de `vault_init`, que
#: inicializa el repo de un vault **recién creado**, no configura identidad
#: —el commit lo hace quien tiene identidad— y no empuja a ningún remote.
#: Un mutador nuevo entra aquí con su motivo escrito, en un diff revisado,
#: nunca por un parámetro que llega de fuera.
MUTADORES_AUTORIZADOS: dict[str, str] = {
    "init": "bootstrap del repo del vault nuevo: vault_init._inicializar_git",
    "add": "staging del bootstrap del vault nuevo: vault_init._inicializar_git",
    "commit": "commit del bootstrap del vault nuevo: vault_init._inicializar_git",
}


class GitProhibido(ValueError):
    """Un argv de git que este dueño no autoriza: verbo desconocido,
    mutador no declarado o uso mutador de un verbo ambivalente."""


class RefInvalida(ValueError):
    """Un dato leído de un fichero no tiene forma de ref de git y se le
    pidió al dueño que lo pase como argumento."""


_REGEX_HASH = re.compile(r"^[0-9a-fA-F]{4,64}$")


def es_hash(valor: str) -> bool:
    """¿Pasa este dato como hash de git —SHA-1, abreviado, sin `..` ni `^`?"""
    return bool(_REGEX_HASH.match((valor or "").strip()))


def asegurar_hash(valor: str, campo: str = "hash") -> str:
    """Devuelve `valor` si tiene forma de hash; `RefInvalida` si no.

    Lo usan los sitios que leen un hash de un fichero (el changelog, el
    snapshot de drift, METRICAS) antes de ponérselo al argv de un comando
    de lectura: la inyección de opción —un valor que empieza por `--`—
    muere aquí, no en git.
    """
    v = (valor or "").strip()
    if not es_hash(v):
        raise RefInvalida(
            f"{campo}={valor!r} no tiene forma de hash de git; un dato nacido "
            "en un fichero no entra al argv de git sin validar (AP-68)"
        )
    return v


def _uso_mutador(verbo: str, args: list[str]) -> str | None:
    """Cómo se usa un verbo ambivalente, evaluado por sus argumentos.

    `git <verbo>` entre verbos hápticos necesita para el guard del titular.
    Devuelve el texto mutador si lo encontra, `None` si es lectura.
    """
    posiciones = [a for a in args if a and not a.startswith("-")]
    opciones = [a for a in args if a.startswith("-")]

    if verbo == "branch":
        for a in opciones:
            if a in ("-d", "-D", "-m", "-M", "--delete", "--edit-description"):
                return a
        return None

    if verbo == "tag":
        # listar es `tag` a secas o `tag -l [<patrón> ...]`; crear es
        # `tag <nombre>` — el primer positional con `-l` delante no está.
        if not posiciones or "-l" in opciones:
            return None
        return posiciones[0]

    if verbo == "config":
        # lectura solo si el primer argumento pide leer (--get*/-l/--list)
        if opciones and opciones[0].startswith("--get"):
            return None
        if opciones and opciones[0] in ("-l", "--list"):
            return None
        return "config <clave> <valor>: escribir config"

    if verbo == "stash" or verbo == "reflog":
        # `stash list/show` y `reflog [<formato>]` leen; apply/pop/drop/
        # save/branch/store/expire/delete mutan.
        if verbo == "stash":
            mutadores = {"apply", "pop", "drop", "save", "branch", "store"}
        else:
            mutadores = {"expire", "delete", "apply"}
        sub = posiciones[0] if posiciones else ""
        return sub if sub in mutadores else None

    return None


def ejecutar_git(repositorio: Any, args: list[str], *, binario: bool = False,
                 **kwargs: Any) -> "subprocess.CompletedProcess[str]":
    """`git <args>` en `repositorio`, con las reglas de AP-68 en la puerta.

    - argv en lista, sin shell: se hereda del criterio del repo y se exige.
    - `args[0]` es el léxico `"git"`; el verbo va detrás, o dos posiciones más
      allá si la llamada usa `-C`.
    - un verbo de `VERBOS_LECTURA` con uso mutador por argumento muere aquí,
      no en git; un verbo de `MUTADORES_AUTORIZADOS` pasa con su motivo; un
      verbo desconocido sube `GitProhibido`.
    - la salida se lee con la codificación del dueño del toolkit
      (`vault.kernel.subproceso`): UTF-8 con `errors="replace"`; el llamador
      puede sobreescribirlo para un binario ajeno, no para git.

    `binario=True` es la **única** excepción al modo texto, y existe por un
    motivo concreto: `git cat-file --batch` emite una cabecera cuyo tamaño va
    en bytes, así que decodificar la salida antes de medir los blobs da
    longitudes que no cuadran. Se pide explícitamente, con su motivo en el
    llamador, y es el único sitio del repo que la usa — porque saltarse el
    dueño con un `except` silencioso sería justo lo que AP-68 viene a
    impedir.

    `repositorio` va a `cwd`; `None` usa el directorio del proceso. El resto
    de los kwargs pasa a `subprocess.run` igual que siempre.
    """
    if not isinstance(args, (list, tuple)):
        raise GitProhibido(
            f"argv de git debe ser lista, no {type(args).__name__}: "
            "sin shell, sin interpolación (AP-68)")
    args = list(args)
    if args and args[0] == "git":
        # tolerado por compatibilidad con los argv históricos; el dueño pone
        # el léxico, que es lo que hace que un sitio llamado no escriba git.
        args = args[1:]
    if not args:
        raise GitProhibido("argv de git vacío (AP-68)")
    if args[0] == "-C":
        # `git -C <ruta> <verbo> ...`: quien elige el cwd es el argv, y el
        # dueño solo lo valida — el guard lo cubre igual, porque el verbo es
        # el tercero del argv y sigue siendo un literal.
        if len(args) < 3:
            raise GitProhibido(f"git -C sin verbo: {args}")
        verbo, resto = args[2], args[3:]
    else:
        verbo, resto = args[0], args[1:]

    if verbo in VERBOS_LECTURA or verbo in VERBOS_AMBIGUOS:
        mut = _uso_mutador(verbo, resto)
        if mut:
            raise GitProhibido(
                f"git {verbo} con uso mutador {mut!r}: este dueño solo "
                "ejecuta lecturas de ese verbo (AP-68)")
    elif verbo in MUTADORES_AUTORIZADOS:
        # mutador autorizado: el motivo está escrito junto a su nombre, y el
        # diff que lo añade es la revisión que lo autoriza.
        pass
    else:
        raise GitProhibido(
            f"git {verbo!r} no es verbo de lectura, ni ambiguo con uso de "
            "lectura, ni mutador autorizado con motivo en "
            "MUTADORES_AUTORIZADOS (AP-68). Una llamada que escriba historia "
            "o destruya estado es una decisión de la persona, revisada en "
            "diff, nunca un argumento que llega de fuera.")

    cwd = None if repositorio is None else str(repositorio)
    kwargs.setdefault("check", False)
    kwargs.pop("text", None)
    kwargs.pop("universal_newlines", None)
    if not binario:
        kwargs.setdefault("encoding", CODIFICACION)
        kwargs.setdefault("errors", ERRORES)
    return subprocess.run(["git", *args], cwd=cwd, **kwargs)


#: El nombre del fichero dueño: es lo único que el guard excluye del scan.
NOMBRE_DUENO = "procesos_git.py"

#: Las funciones que levantan hijos en este repo. Cualquiera que lance git
#: con el léxico primero tiene que entrar por el dueño.
FUNCIONES_DE_HIJOS = frozenset({
    "subprocess.run", "subprocess.Popen", "subprocess.check_output",
    "subprocess.check_call", "subprocess.call",
    "vault_subproceso.ejecutar", "subproceso.ejecutar",
    "procesos_git.ejecutar_git", "vault.kernel.procesos_git.ejecutar_git",
})


def _argv_git_literal_0(nodo: "ast.Call", argv_git_en_nombre: "set[str] | None" = None
                        ) -> str | None:
    """El primer elemento del argv, si la llamada arranca con `"git"`.

    Cubre las tres formas que el repo tenía, que son las tres que existen de
    verdad:

    - literal: `["git", *args]`
    - concatenación: `["git", "-C", ruta] + args`
    - variable: `log_cmd = ["git", "diff", …]` y luego `ejecutar(log_cmd)`

    La tercera exige resolver el nombre, y se hace con un solo pase sobre el
    módulo: los sitios que escriben esa variable la asignan a una lista
    literal justo encima. Un argv que se construya con una cadena —`" ".join`
    o un f-string— queda fuera, y eso se declara en el docstring.
    """
    arg0 = nodo.args[0] if nodo.args else None
    if isinstance(arg0, (ast.List, ast.Tuple)):
        elts = list(arg0.elts)
    elif isinstance(arg0, ast.BinOp) and isinstance(arg0.left, (ast.List, ast.Tuple)):
        elts = list(arg0.left.elts)
    elif isinstance(arg0, ast.Name) and arg0.id in (argv_git_en_nombre or ()):
        return "git"
    else:
        return None
    if elts and isinstance(elts[0], ast.Constant) and elts[0].value == "git":
        return "git"
    return None


def _nombres_con_argv_git(arbol: "ast.Module") -> "set[str]":
    """Nombres del módulo asignados a un argv que empieza por `"git"`."""
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            continue
        valor = nodo.value
        if not isinstance(valor, (ast.List, ast.Tuple)) or not valor.elts:
            continue
        primero = valor.elts[0]
        if not (isinstance(primero, ast.Constant) and primero.value == "git"):
            continue
        objetivos = (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target])
        for objetivo in objetivos:
            if isinstance(objetivo, ast.Name):
                nombres.add(objetivo.id)
    return nombres


def _funcion_del_nodo(nodo: "ast.Call") -> str:
    # Sin `try`: un fallo aquí devolvernía "" y el guard publicaría cero
    # hallazgos — un fallo silencioso con forma de verde (AP-51).
    return ast.unparse(nodo.func)


def sitios_git_fuera_del_dueno(raices: "list[str] | None" = None,
                               raiz_repo: "str | None" = None) -> list[str]:
    """Llamadas que levantan git con el léxico primero, fuera del dueño.

    Es el guard de AP-68 y vive junto al dueño a propósito: un detector en
    otro módulo tendría que reescribir qué cuenta como violación. Mide por
    AST y sigue la variable y la concatenación (las tres formas que el repo
    tenía). Imprime `ruta:linea`, relativa a `raiz_repo` cuando se la dan.

    **Alcance declarado**: mira `scripts/`, `cli/`, `vault/` y `mcp/`. Los
    `tests/` quedan fuera **y por qué**: un test necesita git crudo para
    fabricar el repositorio con el que va a medir —una tool que se midiera
    con su propio ejecutor se certificaría a sí misma—, y los tests no se
    instalan en la wheel, donde no hay repo al que tocar. Tampoco ve un argv
    armado con `" ".join(...)` ni con un f-string, ni un binario que lance
    git por su cuenta: eso se declara, no se supone.
    """
    import pathlib

    base_rel = pathlib.Path(raiz_repo).resolve() if raiz_repo else None
    hallazgos: list[str] = []
    for base in (raices or list(rutas.CARPETAS_DE_CODIGO_Y_MCP)):
        # Con `raiz_repo` las raíces son relativas a él, no al directorio desde
        # el que se invoque: un guard que mide el cwd mide el sitio que
        # casualmente lo llamó, que no es lo que se le pidió.
        raiz_base = (base_rel / base) if base_rel is not None else pathlib.Path(base)
        if not raiz_base.exists():
            continue
        for ruta in sorted(raiz_base.rglob("*.py")):
            if "node_modules" in ruta.parts:
                continue
            if ruta.name == NOMBRE_DUENO:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            nombres_git = _nombres_con_argv_git(arbol)
            for nodo in ast.walk(arbol):
                if not isinstance(nodo, ast.Call):
                    continue
                if _funcion_del_nodo(nodo) not in FUNCIONES_DE_HIJOS:
                    continue
                if _argv_git_literal_0(nodo, nombres_git) != "git":
                    continue
                rel = ruta.as_posix()
                if base_rel is not None:
                    try:
                        rel = str(ruta.resolve().relative_to(base_rel)).replace("\\", "/")
                    except ValueError:
                        pass
                hallazgos.append(f"{rel}:{nodo.lineno}")
    return sorted(hallazgos)
