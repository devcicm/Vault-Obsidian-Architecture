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

Es un arnés de desarrollo, no una tool del catálogo: su consumidor es quien
cierra un cambio en este repo, no un vault ajeno. Ya hoy hay scripts fuera del
registro por este motivo — esa es la precedencia que sigue.

Ejemplos:

  # El alcance del árbol de trabajo contra HEAD (y los no versionados):
  python vault_test_scope.py --changed

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_DIRS = ("scripts", "vault", "normas", "cli", "tests")


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
    return {"ficheros": ficheros, "edges": edges}


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
    por_visitar: List[Tuple[str, int]] = [(f, 0) for f in ficheros_cambiados
                                          if f in edges]
    # Un fichero de test cambiado es su propio alcance: ningún cierre inverso
    # llega a un test (nadie lo importa), y correr los tests que un cambio
    # toca empieza por él. Medido con `--for tests/…` la primera versión
    # devolvía 0 tests: defecto del propio instrumento en C1.
    for f, _ in list(por_visitar):
        if f.startswith("tests/") and Path(f).name.startswith("test_"):
            tests.add(f)
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
            if dependiente.startswith("tests/") and Path(dependiente).name.startswith("test_"):
                tests.add(dependiente)
                continue  # un test no importa a nadie: la marcha se corta ahí.
            por_visitar.append((dependiente, salto + 1))
    return sorted(tests)


def ficheros_cambiados(base: Optional[str] = None,
                       repo_root: Path = REPO_ROOT) -> List[str]:
    """Ficheros cambiados del working tree (y no versionados), extensiones .py."""
    commands = [["git", "ls-files", "--others", "--exclude-standard"]]
    commands.append(["git", "diff", "--name-only", "HEAD"] + (
        [base] if base and base != "HEAD" else []))
    fuera: Set[str] = set()
    for command in commands:
        try:
            out = subprocess.run(command, capture_output=True, text=True,
                                 cwd=str(repo_root), timeout=60,
                                 encoding="utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in (out.stdout or "").splitlines():
            token = line.strip()
            if token.endswith(".py") and "/.history/" not in token:
                fuera.add(token)
    return sorted(fuera)


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
        objetivos.extend(ficheros_cambiados(base))

    mapa = construir_mapa()
    tests = alcance(set(objetivos), mapa, args.depth)
    command = ["python", "-m", "pytest", *tests, "-q", "-n", "auto", "--tb=short"]
    datos = {
        "ok": True,
        "tests": tests,
        "n": len(tests),
        "command": " ".join(command),
        "objetivos": sorted(set(objetivos)),
        "hint": ("0 tests = el cambio no tiene cubrimiento directo: si el cambio "
                 "toca contratos, la suite de cierre (L2) se decide por ola."),
    }
    if args.json:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(datos, ensure_ascii=False, indent=2))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(datos["command"])
        if not tests:
            print("(sin tests directos: decisión de L2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
