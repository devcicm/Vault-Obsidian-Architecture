#!/usr/bin/env python3
"""test_scope — dueño de `scripts/vault_test_scope.py` (ADR-0002, deuda #12).

Aquí vive la implementación desde v41.12; el nombre en `scripts/` se conserva
(no-derogación) como alias en `sys.modules`, igual que `vault_firma_sitio`.

—— los tests que toca un cambio.

En un repo de 5.943 tests, cerrar un cambio puntual no exige correr la suite
entera: exige correr solo los tests que llegan a lo que el cambio modifica.
Correr todo para cada puntería es la deriva que este arnés detiene — una suite
en serie de horas solo es económica para quien no corre nada.

El grafo de dependencia se mide, no se adivina:

1. Para cada fichero Python del repo (`scripts/`, `vault/`, `normas/`, `cli/`,
   `tests/`) se extrae con `ast` lo que importa o nomra:
   - imports anidados incluidos (los hay dentro de funciones desde AP-58),
   - literales que nombran un script (`"vault_write.py"`): un test que lo lanza
     en subprocess también depende del fichero que lo edita;
   - literales que nombran una tool del catálogo (`"vault_write"`): un test que
     la parametriza por nombre también toca su script.
2. El alcance de un fichero cambiado es su clausura inversa: qué ficheros de
   test llegan a él transitivamente por imports, más los que lo nombran por
   literal. Un test no es fuente de nadie: la marcha se corta ahí.
3. Un fichero que no es Python (`AGENTS.md`, `docs/PUERTAS.md`, un JSON) llega
   a los ficheros que lo **nombran** en un literal, por ruta o por nombre: un
   test que lo lee depende de él igual que el que importa un módulo.

## Cuándo no hay subconjunto honesto (el carril `merge`)

Seleccionar de menos en silencio es peor que no seleccionar: el verde del
subconjunto se lee como verde de la suite. Por eso `decidir()` no devuelve
solo tests, devuelve un **carril** (`vault.meta_toolkit.carriles`), y manda a
`merge` —la suite entera— cuando el cambio toca:

- la configuración de la suite (`conftest.py`, `pyproject.toml`): llega a todos
  los tests sin que ninguno la importe;
- un módulo del kernel (`vault/kernel/`, o un script que `vault_arch` declara
  en el contexto `kernel`): con profundidad 2 la clausura de un módulo que
  todo importa es arbitraria;
- código que el mapa no alcanza (un `.py` o `.mjs` nuevo o borrado que nadie
  nombra): no hay criterio para decir qué tests lo ejercitan.

Un fichero de texto que nadie nombra **no** fuerza `merge`: sale en
`sin_lector`. Lo que lo recorre por directorio lo vigilan las puertas
rápidas (`vault_doc_counts`, `vault_doc_sync`), que el carril `dev` corre.

Es un arnés de desarrollo, no una tool del catálogo: su consumidor es quien
cierra un cambio en este repo, no un vault ajeno. Ya hoy hay scripts fuera del
registro por este motivo — esa es la precedencia que sigue.

Ejemplos:

  # Lo que se va a commitear (árbol contra HEAD y no versionados), y correrlo:
  # es el carril `dev`, que mide el commit y no la rama.
  python vault_test_scope.py --changed --correr

  # Lo cambiado en toda la rama contra main (suele ser medio repo: la rama
  # entera la juzga el carril `merge`, no este):
  python vault_test_scope.py --changed main

  # El alcance de un fichero:
  python vault_test_scope.py --for scripts/vault_smoke.py

  # El alcance de una tool del catálogo (su script + lo que importa):
  python vault_test_scope.py --for-tool vault_smoke

  # Salida JSON para una herramienta:
  python vault_test_scope.py --for scripts/vault_mermaid_check.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from vault.kernel.procesos_git import ejecutar_git
from vault.meta_toolkit.carriles import SUITE_COMPLETA

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_DIRS = ("scripts", "vault", "normas", "cli", "tests")

#: Ficheros que llegan a todos los tests sin que ninguno los importe.
CONFIGURACION_DE_LA_SUITE = ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
#: Sufijos de código: si el mapa no lo alcanza, no hay subconjunto que defender.
SUFIJOS_DE_CODIGO = (".py", ".mjs", ".js", ".cjs")
#: Bordes que se recortan de un token de literal antes de buscarlo como ruta.
_BORDES = "`'\"()[]{}<>,;"


def _resolve_module(nombre: str, desde: Path, repo_root: Path) -> Optional[Path]:
    """Resuelve un nombre de módulo a un fichero del repo, o None si es externo."""
    if not nombre:
        return None
    parts = nombre.split(".")
    candidates = [
        repo_root.joinpath(*parts).with_suffix(".py"),
        repo_root.joinpath(*parts) / "__init__.py",
        desde.parent / f"{parts[0]}.py",
        # Los tests hacen sys.path(.../scripts) e importan plano: `vault_a`.
        repo_root / "scripts" / f"{parts[0]}.py",
        repo_root / "cli" / f"{parts[0]}.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _refs_de_fichero(path: Path, repo_root: Path) -> Tuple[Set[Path], Set[str]]:
    """(ficheros que importa, literales de texto del fichero)."""
    try:
        tree = ast.parse(path.read_bytes())
    except (OSError, SyntaxError):
        return set(), set()

    imports: Set[Path] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_module(alias.name, path, repo_root)
                if resolved:
                    imports.add(resolved)
        elif isinstance(node, ast.ImportFrom):
            base = "." * max(node.level, 0) + (node.module or "")
            for nombre in (base, *(f"{base}.{a.name}" for a in node.names)):
                resolved = _resolve_module(nombre, path, repo_root)
                if resolved:
                    imports.add(resolved)

    literales: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literales.add(node.value)
    return imports, literales


def _tokens_de_literal(literal: str) -> List[str]:
    """`scripts/vault_io.py`, `./vault_io`, `python scripts/vault_x.py --a` → tokens."""
    return literal.replace("\\", "/").replace(":", " ").replace("=", " ").split()


def _normaliza(token: str) -> str:
    return token.removeprefix("./").removesuffix(".py")


def _mapear_literales(literales: Iterable[str], claves: Set[str],
                      nombres_tools: Set[str]) -> Set[str]:
    """Claves (posix relativos al repo) que los literales del test nombran.

    El candidato debe existir con el sufijo que las claves llevan
    (`scripts/vault_smoke.py`): buscar `scripts/<stem>` a secas era cerrar
    una rama que ninguna clave satisface — el defecto que el primer smoke de
    esta script destapó.
    """
    refs: Set[str] = set()
    for literal in literales:
        for token in _tokens_de_literal(literal):
            normalizada = _normaliza(token)
            nombre = normalizada.rsplit("/", 1)[-1]
            candidatos = [
                normalizada,
                f"scripts/{nombre}.py",
                f"cli/{nombre}.py",
            ]
            if token in nombres_tools:
                candidatos += [f"scripts/{token}.py", f"cli/{token}.py"]
            acierto = next((c for c in candidatos if c in claves), None)
            if acierto:
                refs.add(acierto)
    return refs


def construir_mapa(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """Ficheros del repo → sus referencias, más los nombres de tool del catálogo."""
    ficheros: Dict[str, str] = {}  # posix relativo → Path
    for dir_ in SOURCE_DIRS:
        root = repo_root / dir_
        if not root.is_dir():
            continue
        for py_file in root.rglob("*.py"):
            ficheros[py_file.relative_to(repo_root).as_posix()] = py_file
    claves = set(ficheros)

    nombres_tools: Set[str] = set()
    try:
        # Sin sys.path.insert (el boundary de la wheel lo prohíbe): ejecutada
        # como CLI, `sys.path[0]` ya es `scripts/`; en la wheel el cargador
        # pone `_impl` primero; en un repo sintético sin catálogo el except
        # ImportError mantiene el mapa correcto.
        import vault_mcp_catalog as mc

        for name, entry in mc.TOOLS_CATALOG.items():
            nombres_tools.add(name)
            script = entry.get("script")
            if script:
                nombres_tools.add(Path(script).stem)
    except ImportError:
        # Un repo sintético (tmp_path) no tiene catálogo y no importa: los
        # literales de tool no existen y el mapa sigue siendo correcto.
        pass

    edges: Dict[str, Set[str]] = {}
    nombrados: Dict[str, Set[str]] = {}  # token de literal → ficheros que lo dicen
    for clave, path in ficheros.items():
        imports, literales = _refs_de_fichero(path, repo_root)
        refs: Set[str] = set()
        for imported in imports:
            try:
                refs.add(imported.relative_to(repo_root).as_posix())
            except ValueError:
                continue
        refs |= _mapear_literales(literales, claves, nombres_tools)
        edges[clave] = refs
        for literal in literales:
            for token in _tokens_de_literal(literal):
                token = token.strip(_BORDES)
                if "." in token:
                    nombrados.setdefault(token, set()).add(clave)
    return {"ficheros": ficheros, "edges": edges, "nombrados": nombrados}


def lectores(ruta: str, mapa: Dict[str, Any]) -> Set[str]:
    """Ficheros cuyo código nombra `ruta` en un literal: por ruta o por nombre.

    Por nombre a secas (`"PUERTAS.md"`) porque así lo escribe quien compone la
    ruta con `/`: `ROOT / "docs" / "PUERTAS.md"`. Un nombre repetido
    (`README.md`) trae lectores de más, que es el lado seguro.
    """
    nombrados: Dict[str, Set[str]] = mapa.get("nombrados", {})
    ruta = ruta.replace("\\", "/")
    return set(nombrados.get(ruta, ())) | set(nombrados.get(ruta.rsplit("/", 1)[-1], ()))


def _es_test(clave: str) -> bool:
    return clave.startswith("tests/") and Path(clave).name.startswith("test_")


def alcance(ficheros_cambiados: Iterable[str], mapa: Dict[str, Any],
            profundidad: int = 2) -> List[str]:
    """Clausura inversa acotada: tests que llegan a lo cambiado en ≤ `profundidad` saltos.

    Sin acotar, la transitivity muere de razón: `vault_norms` es una fachada que
    `vault_norms_engine` reexporta y que docenas de scripts y tests tocan, así
    que cualquier closure completa llega a lo mismo desde cualquier fichero de
    `scripts/`. `profundidad` default 2 lo corta donde el cambio es visible:
    los tests que tocan el fichero, más los tests de sus dependientes de
    primer orden. `profundidad=None` abre la marcha completa.
    """
    edges: Dict[str, Set[str]] = mapa["edges"]

    reverse: Dict[str, Set[str]] = {}
    for padre, hijos in edges.items():
        for hijo in hijos:
            reverse.setdefault(hijo, set()).add(padre)

    tests: Set[str] = set()
    visitadas: Set[str] = set()
    cambiados = list(ficheros_cambiados)
    por_visitar: List[Tuple[str, int]] = [(f, 0) for f in cambiados if f in edges]
    # Un fichero de test cambiado es su propio alcance: ningún cierre inverso
    # llega a un test (nadie lo importa), y correr los tests que un cambio
    # toca empieza por él. Medido con `--for tests/…` la primera versión
    # devolvía 0 tests: defecto del propio instrumento en C1.
    for f, _ in list(por_visitar):
        if _es_test(f):
            tests.add(f)
    # Lo que no es nodo del mapa (texto, JSON, `.mjs`) entra por quien lo nombra:
    # esos lectores son sus dependientes de primer orden.
    for f in cambiados:
        if f in edges:
            continue
        for lector in lectores(f, mapa):
            if _es_test(lector):
                tests.add(lector)
            else:
                por_visitar.append((lector, 1))
    while por_visitar:
        current, salto = por_visitar.pop()
        if current in visitadas:
            continue
        visitadas.add(current)
        if profundidad is not None and salto >= profundidad:
            continue
        for dependiente in reverse.get(current, ()):
            if dependiente in visitadas:
                continue
            if _es_test(dependiente):
                tests.add(dependiente)
                continue  # un test no importa a nadie: la marcha se corta ahí.
            por_visitar.append((dependiente, salto + 1))
    return sorted(tests)


def cambios(base: Optional[str] = None, repo_root: Path = REPO_ROOT) -> List[str]:
    """Todo fichero cambiado: los no versionados y el diff del árbol contra `base`.

    `git diff --name-only <base>` compara el árbol de trabajo —commits de la
    rama y lo aún sin commitear— con `base`. La forma anterior,
    `diff HEAD <base>`, comparaba dos commits y dejaba fuera lo sin commitear
    en cuanto se pedía una base: justo lo que se está a punto de cerrar.
    """
    consultas = [["ls-files", "--others", "--exclude-standard"],
                 ["diff", "--name-only", base or "HEAD"]]
    fuera: Set[str] = set()
    for consulta in consultas:
        try:
            out = ejecutar_git(repo_root, consulta, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in (out.stdout or "").splitlines():
            token = line.strip()
            if token and "/.history/" not in token:
                fuera.add(token)
    return sorted(fuera)


def ficheros_cambiados(base: Optional[str] = None,
                       repo_root: Path = REPO_ROOT) -> List[str]:
    """Ficheros cambiados del working tree (y no versionados), extensiones .py."""
    return [c for c in cambios(base, repo_root) if c.endswith(".py")]


def _modulos_del_kernel() -> Set[str]:
    """Stems que `vault_arch` declara en el contexto `kernel` (vacío sin él)."""
    try:
        import vault_arch
    except ImportError:
        # Repo sintético o wheel sin el meta-toolkit: queda el prefijo
        # `vault/kernel/`, que no necesita registro.
        return set()
    return set(vault_arch.CONTEXTS[vault_arch.KERNEL]["modulos"])


def _motivo_de_merge(f: str, mapa: Dict[str, Any], kernel: Set[str]) -> Optional[str]:
    nombre = f.rsplit("/", 1)[-1]
    if nombre == "conftest.py" or f in CONFIGURACION_DE_LA_SUITE:
        return "configuracion_de_la_suite"
    if f.startswith("vault/kernel/") or (
            f.startswith("scripts/") and Path(nombre).stem in kernel):
        return "kernel"
    if (f.endswith(SUFIJOS_DE_CODIGO) and f not in mapa["edges"]
            and not lectores(f, mapa)):
        return "codigo_sin_mapa"
    return None


def decidir(cambiados: Iterable[str], mapa: Dict[str, Any],
            profundidad: Optional[int] = 2) -> Dict[str, Any]:
    """El carril que pide el cambio y, si es `dev`, sus tests.

    `merge` no es un fallo del selector: es el selector diciendo que para este
    cambio no hay subconjunto honesto, en vez de devolver uno.
    """
    cambiados = sorted(set(cambiados))
    kernel = _modulos_del_kernel()
    motivos = [{"fichero": f, "motivo": m} for f in cambiados
               if (m := _motivo_de_merge(f, mapa, kernel))]
    sin_lector = [f for f in cambiados
                  if f not in mapa["edges"] and not f.endswith(SUFIJOS_DE_CODIGO)
                  and not lectores(f, mapa)]
    return {
        "carril": "merge" if motivos else "dev",
        "tests": alcance(cambiados, mapa, profundidad),
        "motivos_merge": motivos,
        "sin_lector": sin_lector,
    }


def comando(decision: Dict[str, Any]) -> List[str]:
    """El pytest del carril: la suite de `merge` tal cual, o el subconjunto con sus opciones."""
    if decision["carril"] == "merge":
        return ["python", *SUITE_COMPLETA]
    i = SUITE_COMPLETA.index("tests/")
    return ["python", *SUITE_COMPLETA[:i], *decision["tests"], *SUITE_COMPLETA[i + 1:]]


def script_de_tool(nombre: str) -> Optional[str]:
    try:
        import vault_mcp_catalog as mc

        entry = mc.TOOLS_CATALOG.get(nombre) or {}
        script = entry.get("script")
        return f"scripts/{script}" if script else None
    except ImportError:
        # Sin catálogo no hay script que nombrar: None es el contrato de la
        # función, no un vacío indistinguible (AP-51).
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Los tests afectados por un cambio (la alternativa a la suite entera).",
        allow_abbrev=False)
    parser.add_argument("--for", dest="rutas", nargs="*",
                        help="ficheros sobre cuyo alcance preguntar")
    parser.add_argument("--for-tool", dest="tool",
                        help="una tool del catálogo: su script como objetivo")
    parser.add_argument("--changed", nargs="?", const="HEAD",
                        help="alcance del working tree, opcionalmente contra BASE git")
    parser.add_argument("--depth", type=int, default=2,
                        help="saltos inversos que se recorren (default 2: tests que "
                             "tocan el fichero + tests de sus dependientes directos)")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument("--correr", action="store_true",
                        help="ejecuta el pytest del carril decidido (en `merge`, la suite "
                             "entera) y devuelve su exit code")
    args = parser.parse_args()

    if not (args.rutas or args.tool or args.changed is not None):
        parser.error("pide --for, --for-tool o --changed")

    objetivos: List[str] = list(args.rutas or [])
    if args.tool:
        script = script_de_tool(args.tool)
        if script is None:
            import vault_errors

            envelope = vault_errors.emit_error(
                "vault_test_scope", "TOOL_NOT_IN_SPEC",
                message=f"sin script para {args.tool} (¿está en el catálogo?)")
            sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(envelope, ensure_ascii=False))
            return 1
        objetivos.append(script)
    if args.changed is not None:
        base = None if args.changed == "HEAD" else args.changed
        objetivos.extend(cambios(base))

    mapa = construir_mapa()
    decision = decidir(objetivos, mapa, args.depth)
    command = comando(decision)
    tests = decision["tests"]
    datos = {
        "ok": True,
        "carril": decision["carril"],
        "motivos_merge": decision["motivos_merge"],
        "sin_lector": decision["sin_lector"],
        "tests": tests,
        "n": len(tests),
        "command": " ".join(command),
        "objetivos": sorted(set(objetivos)),
        "hint": ("carril merge = este cambio no tiene subconjunto honesto (ver "
                 "motivos_merge): corre la suite entera. 0 tests en dev = el cambio "
                 "no tiene cubrimiento directo."),
    }
    sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps(datos, ensure_ascii=False, indent=2))
    else:
        print(f"carril {decision['carril']}: {datos['command']}")
        for m in decision["motivos_merge"]:
            print(f"  merge por {m['motivo']}: {m['fichero']}")
        if decision["carril"] == "dev" and not tests:
            print("(sin tests directos)")
    if not args.correr or (decision["carril"] == "dev" and not tests):
        return 0
    sys.stdout.flush()
    return subprocess.run([sys.executable, *command[1:]], cwd=str(REPO_ROOT)).returncode


if __name__ == "__main__":
    sys.exit(main())
