"""analyzer — escáner estático de antipatrones y condiciones de carrera.

No es un linter genérico. Busca los fallos que rompen específicamente las
garantías de este estándar: contención (AP-36), integridad bajo concurrencia y
trazabilidad. Cada hallazgo apunta a una norma real del registro
(`scripts/vault_norms.py`) o a un código propio `RC-*` / `PY-*` cuando no
existe norma equivalente — no se inventan códigos AP-XX.

Por qué importa el escáner de carreras: el scheduler asume que los artefactos
de `registry.GUARDED_ARTIFACTS` se escriben con `vault_io.file_lock` +
escritura atómica, y por eso los deja correr en paralelo. RC-01 y RC-02
verifican esa premisa. Si el escáner encuentra un escritor sin lock, la
premisa del paralelismo deja de ser válida — por eso `cli scan --races`
forma parte del ciclo, no es un extra.

Supresión puntual: comentario `# cli-scan: ignore <CODIGO>` en la línea.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .registry import GUARDED_ARTIFACTS, SCRIPTS_DIR

# El orden lo da el registro, no una copia. `severidad` ya vivía en
# `vault_vocabulario`; tenerlo aquí escrito a mano hacía que ampliar la
# escala en el registro dejase a `cli/` ordenando por una escala vieja sin
# que nada avisara. El import es seguro: `.registry` ya puso `scripts/` en
# `sys.path` una línea más arriba.
from vault_vocabulario import rango  # noqa: E402

# `mayor_primero=False` y `base=0`: aquí el número es la posición en la lista
# —`critical` es 0— porque el filtro compara `> limit` para descartar lo menos
# grave. Es el mismo orden declarado, leído del extremo contrario.
SEVERITY_ORDER = rango("severidad", base=0, mayor_primero=False)

CHECKS: Dict[str, Dict[str, str]] = {
    "RC-01": {"kind": "race", "severity": "critical",
              "title": "Artefacto compartido escrito sin file_lock"},
    "RC-02": {"kind": "race", "severity": "high",
              "title": "Escritura no atómica sobre artefacto del vault"},
    "RC-03": {"kind": "race", "severity": "high",
              "title": "TOCTOU: exists() seguido de escritura o borrado"},
    "RC-04": {"kind": "race", "severity": "critical",
              "title": "Read-modify-write de JSON sin lock (lost update)"},
    "RC-05": {"kind": "race", "severity": "medium",
              "title": "Estado mutable de módulo modificado en función"},
    "RC-06": {"kind": "race", "severity": "high",
              "title": "Lock por mkdir sin manejo de lock obsoleto"},
    "AP-36": {"kind": "antipattern", "severity": "critical",
              "title": "Ruta derivada de __file__ o del CWD, no del vault root"},
    "AP-01": {"kind": "antipattern", "severity": "high",
              "title": "Referencia a un script que no existe"},
    "PY-01": {"kind": "antipattern", "severity": "medium",
              "title": "Excepción silenciada sin registro"},
    "PY-02": {"kind": "antipattern", "severity": "medium",
              "title": "Entry point sin wrap_main (sin timeout ni trace)"},
    "PY-03": {"kind": "antipattern", "severity": "high",
              "title": "Argumento por defecto mutable (estado compartido)"},
    "PY-04": {"kind": "antipattern", "severity": "critical",
              "title": "subprocess con shell=True (inyección de comandos)"},
}

# vault_io implementa las primitivas — es el único autorizado a usarlas en crudo.
_PRIMITIVE_IMPLEMENTERS = {"vault_io.py"}
# Ficheros que no son tools: sus rutas relativas a __file__ son legítimas.
_META_FILES = {
    "vault_mcp_catalog.py", "vault_spec_generate_catalog.py",
    "vault_spec_validate.py", "vault_spec_catalog_check.py",
    "vault_manifest.py", "vault_errors_catalog.py", "vault_norms.py",
}

_WRITE_METHODS = {"write_text", "write_bytes", "write"}
_LOCK_NAMES = {"file_lock", "_local_lock_for", "lock"}
_ATOMIC = {"atomic_write_text", "atomic_write_json"}


@dataclass
class Issue:
    code: str
    file: str
    line: int
    severity: str
    kind: str
    message: str
    snippet: str = ""
    # Artefacto compartido implicado (RC-01/RC-04). El scheduler lo usa para
    # degradar ese artefacto a exclusivo en vez de fiarse de que tenga lock.
    artifact: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "code": self.code,
            "kind": self.kind,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "title": CHECKS[self.code]["title"],
            "message": self.message,
            "snippet": self.snippet,
        }
        if self.artifact:
            out["artifact"] = self.artifact
        return out


def _suppressed(lines: List[str], lineno: int, code: str) -> bool:
    if 0 < lineno <= len(lines):
        return f"cli-scan: ignore {code}" in lines[lineno - 1]
    return False


def _snippet(lines: List[str], lineno: int) -> str:
    if 0 < lineno <= len(lines):
        return lines[lineno - 1].strip()[:160]
    return ""


def _attr_chain(node: ast.AST) -> str:
    """Reconstruye 'a.b.c' desde un Attribute/Name anidado."""
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _parent_depth(node: ast.AST) -> int:
    """Cuenta .parent encadenados sobre una expresión."""
    depth = 0
    cur = node
    while isinstance(cur, ast.Attribute):
        if cur.attr == "parent":
            depth += 1
        cur = cur.value
    return depth


def _mentions_guarded(text: str) -> Optional[str]:
    for artifact in GUARDED_ARTIFACTS:
        leaf = artifact.split("/")[-1]
        if leaf in text:
            return artifact
    return None


class _Scanner(ast.NodeVisitor):
    def __init__(self, path: Path, source: str) -> None:
        self.path = path
        self.name = path.name
        self.lines = source.splitlines()
        self.issues: List[Issue] = []
        self._func_stack: List[ast.AST] = []
        self._module_mutables: Set[str] = set()

    # ── helpers ─────────────────────────────────────────────────────────────
    def _add(self, code: str, node: ast.AST, message: str,
             artifact: Optional[str] = None) -> None:
        lineno = getattr(node, "lineno", 0)
        if _suppressed(self.lines, lineno, code):
            return
        self.issues.append(Issue(
            code=code,
            file=self.name,
            line=lineno,
            severity=CHECKS[code]["severity"],
            kind=CHECKS[code]["kind"],
            message=message,
            snippet=_snippet(self.lines, lineno),
            artifact=artifact,
        ))

    def _enclosing_source(self) -> str:
        if not self._func_stack:
            return ""
        fn = self._func_stack[-1]
        start = getattr(fn, "lineno", 1) - 1
        end = getattr(fn, "end_lineno", len(self.lines))
        return "\n".join(self.lines[start:end])

    def _has_lock_in_scope(self) -> bool:
        src = self._enclosing_source()
        return any(name in src for name in _LOCK_NAMES)

    # ── módulo ──────────────────────────────────────────────────────────────
    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(
                stmt.value, (ast.Dict, ast.List, ast.Set)
            ):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        self._module_mutables.add(target.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._func_stack.append(node)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _check_mutable_defaults(self, node: ast.FunctionDef) -> None:
        for default in list(node.args.defaults) + [
            d for d in node.args.kw_defaults if d is not None
        ]:
            if isinstance(default, (ast.Dict, ast.List, ast.Set)):
                self._add(
                    "PY-03", default,
                    f"'{node.name}' tiene un argumento por defecto mutable: se "
                    "comparte entre todas las llamadas, incluidas las concurrentes",
                )

    # ── llamadas ────────────────────────────────────────────────────────────
    def visit_Call(self, node: ast.Call) -> None:
        fname = _call_name(node)
        chain = _attr_chain(node.func) if isinstance(node.func, ast.Attribute) else fname

        self._check_shell(node, fname)
        self._check_writes(node, fname, chain)
        self._check_cwd_paths(node, chain)
        self._check_mkdir_lock(node, chain)
        self._check_module_mutation(node, chain)

        self.generic_visit(node)

    def _check_shell(self, node: ast.Call, fname: str) -> None:
        if fname not in ("run", "Popen", "call", "check_output", "system"):
            return
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self._add("PY-04", node,
                          "shell=True interpola argumentos en un shell: un título "
                          "o ruta con metacaracteres se convierte en ejecución de comandos")

    def _check_writes(self, node: ast.Call, fname: str, chain: str) -> None:
        if self.name in _PRIMITIVE_IMPLEMENTERS:
            return

        if fname in _WRITE_METHODS or (fname == "open" and self._opens_for_write(node)):
            scope_src = self._enclosing_source()
            target_text = _snippet(self.lines, getattr(node, "lineno", 0))
            guarded = _mentions_guarded(scope_src) or _mentions_guarded(target_text)

            if guarded and not self._has_lock_in_scope():
                self._add("RC-01", node,
                          f"escribe '{guarded}' sin file_lock(): dos procesos "
                          "concurrentes pueden perder una de las dos escrituras",
                          artifact=guarded)
            elif not any(a in scope_src for a in _ATOMIC) and ".json" in target_text:
                self._add("RC-02", node,
                          "escritura directa sobre JSON del vault: usa "
                          "atomic_write_json() para que un fallo a media escritura "
                          "no deje el artefacto truncado")

        if fname in ("load", "loads") and chain.startswith("json"):
            scope_src = self._enclosing_source()
            guarded = _mentions_guarded(scope_src)
            writes_back = any(w in scope_src for w in _WRITE_METHODS | _ATOMIC)
            if guarded and writes_back and not self._has_lock_in_scope():
                self._add("RC-04", node,
                          f"lee y reescribe '{guarded}' sin lock: entre la lectura "
                          "y la escritura otro proceso puede haber modificado el "
                          "artefacto, y su cambio se pierde",
                          artifact=guarded)

    @staticmethod
    def _opens_for_write(node: ast.Call) -> bool:
        for arg in node.args[1:2]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return any(m in arg.value for m in ("w", "a", "+"))
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                return any(m in str(kw.value.value) for m in ("w", "a", "+"))
        return False

    def _check_cwd_paths(self, node: ast.Call, chain: str) -> None:
        if self.name in _PRIMITIVE_IMPLEMENTERS | _META_FILES:
            return
        if chain not in ("Path.cwd", "os.getcwd"):
            return
        # Resolver una ruta contra el CWD es legítimo para LEER (las tools de
        # código fuente mapean archivos del repo, que viven fuera del vault).
        # Solo es AP-36 si de ahí sale un destino de ESCRITURA.
        scope_src = self._enclosing_source()
        writes = any(f"{w}(" in scope_src for w in _WRITE_METHODS | _ATOMIC) or \
            "mkdir(" in scope_src
        if not writes:
            return
        self._add("AP-36", node,
                  "ruta de escritura derivada del directorio de trabajo: el destino "
                  "depende de dónde se invoque la tool. Deriva de "
                  "vault_io.get_vault_root()")

    def _check_mkdir_lock(self, node: ast.Call, chain: str) -> None:
        if self.name in _PRIMITIVE_IMPLEMENTERS:
            return
        if chain not in ("os.mkdir",):
            return
        scope_src = self._enclosing_source()
        if "lock" not in scope_src.lower():
            return
        if "stale" not in scope_src.lower() and "st_mtime" not in scope_src:
            self._add("RC-06", node,
                      "lock por mkdir sin detección de lock obsoleto: si el proceso "
                      "dueño muere, el lock queda tomado para siempre y bloquea a "
                      "todos los demás")

    def _check_module_mutation(self, node: ast.Call, chain: str) -> None:
        if not self._func_stack or "." not in chain:
            return
        base, _, method = chain.rpartition(".")
        if base in self._module_mutables and method in (
            "append", "extend", "update", "pop", "clear", "add", "remove", "setdefault"
        ):
            src = self._enclosing_source()
            if any(name in src for name in _LOCK_NAMES):
                return
            self._add("RC-05", node,
                      f"muta '{base}' (estado de módulo) desde una función sin "
                      "sincronización: dos hilos que la llamen a la vez compiten")

    # ── AP-36: rutas desde __file__ ─────────────────────────────────────────
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "parent" and self.name not in _PRIMITIVE_IMPLEMENTERS | _META_FILES:
            depth = _parent_depth(node)
            src = ast.unparse(node) if hasattr(ast, "unparse") else ""
            if depth >= 2 and "__file__" in src:
                self._add("AP-36", node,
                          f"{depth} niveles de .parent sobre __file__: la ruta "
                          "resultante queda FUERA del vault. Deriva de "
                          "vault_io.get_vault_root()")
        self.generic_visit(node)

    # ── TOCTOU ──────────────────────────────────────────────────────────────
    def visit_If(self, node: ast.If) -> None:
        test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
        if ".exists()" in test_src or "is_file()" in test_src:
            body_src = "\n".join(
                ast.unparse(s) if hasattr(ast, "unparse") else "" for s in node.body
            )
            risky = ("unlink(", "rmdir(", "rmtree(", "mkdir(", "write_text(",
                     "os.remove(", "os.replace(")
            hit = next((r for r in risky if r in body_src), None)
            if hit and "missing_ok" not in body_src and "exist_ok" not in body_src:
                self._add("RC-03", node,
                          f"comprueba existencia y luego ejecuta '{hit.rstrip('(')}': "
                          "entre ambas otro proceso puede crear o borrar el archivo. "
                          "Usa la operación directa con missing_ok/exist_ok o un lock")
        self.generic_visit(node)

    # ── excepciones silenciadas ─────────────────────────────────────────────
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
        )
        if only_pass and broad:
            self._add("PY-01", node,
                      "captura amplia con 'pass': un fallo de escritura se vuelve "
                      "invisible y la tool reporta éxito")
        self.generic_visit(node)


def _check_ghost_references(path: Path, source: str) -> List[Issue]:
    """AP-01/AP-04: menciones a scripts vault_*.py que no existen."""
    issues: List[Issue] = []
    lines = source.splitlines()
    seen: Set[str] = set()
    for match in re.finditer(r"\b(vault_[a-z0-9_]+)\.py\b", source):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        if (SCRIPTS_DIR / f"{name}.py").exists():
            continue
        if (SCRIPTS_DIR / "_archived" / f"{name}.py").exists():
            continue
        lineno = source[: match.start()].count("\n") + 1
        line_text = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        # Rutas de ejemplo a archivos temporales o de respaldo no son
        # referencias a tools: son argumentos de muestra en un docstring.
        if "/tmp/" in line_text or "_backup" in match.group(0):
            continue
        if _suppressed(lines, lineno, "AP-01"):
            continue
        issues.append(Issue(
            code="AP-01", file=path.name, line=lineno,
            severity=CHECKS["AP-01"]["severity"], kind="antipattern",
            message=f"referencia a '{name}.py', que no existe en scripts/ "
                    "ni en _archived/",
            snippet=_snippet(lines, lineno),
        ))
    return issues


def _check_entry_point(path: Path, source: str) -> List[Issue]:
    """PY-02: __main__ que no pasa por wrap_main (sin timeout ni trace)."""
    if "__main__" not in source or "argparse" not in source:
        return []
    tail = source[source.rfind("__main__"):]
    if "wrap_main" in tail:
        return []
    lines = source.splitlines()
    lineno = source[: source.rfind("__main__")].count("\n") + 1
    if _suppressed(lines, lineno, "PY-02"):
        return []
    return [Issue(
        code="PY-02", file=path.name, line=lineno,
        severity=CHECKS["PY-02"]["severity"], kind="antipattern",
        message="entry point sin wrap_main(): la tool queda sin timeout, sin "
                "envelope de error uniforme y sin registro en el trace log",
        snippet=_snippet(lines, lineno),
    )]


def scan_file(path: Path) -> List[Issue]:
    """Analiza un script. Un fallo de sintaxis se reporta, no se traga."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [Issue("PY-01", path.name, 0, "high", "antipattern",
                      f"no se pudo leer: {exc}")]

    issues: List[Issue] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Issue("PY-01", path.name, exc.lineno or 0, "critical", "antipattern",
                      f"error de sintaxis: {exc.msg}")]

    scanner = _Scanner(path, source)
    scanner.visit(tree)
    issues.extend(scanner.issues)
    issues.extend(_check_ghost_references(path, source))
    issues.extend(_check_entry_point(path, source))
    return issues


def unsafe_artifacts(tools: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Artefactos compartidos que alguien escribe SIN lock, y quién lo hace.

    El scheduler trata `registry.GUARDED_ARTIFACTS` como seguros en paralelo
    porque asume que sus escritores usan `file_lock`. Esta función comprueba
    esa asunción sobre los scripts implicados en un lote concreto. Lo que
    salga de aquí deja de ser "guarded" y pasa a serializarse.

    Es la unión explícita entre el escáner y el planificador: la concurrencia
    no se concede por declaración, se concede por verificación.
    """
    if tools is None:
        targets = sorted(SCRIPTS_DIR.glob("vault_*.py"))
    else:
        targets = [SCRIPTS_DIR / f"{t}.py" for t in tools]

    found: Dict[str, List[str]] = {}
    for path in targets:
        if not path.exists():
            continue
        for issue in scan_file(path):
            if issue.code in ("RC-01", "RC-04") and issue.artifact:
                found.setdefault(issue.artifact, [])
                if path.stem not in found[issue.artifact]:
                    found[issue.artifact].append(path.stem)
    return found


def scan(paths: Optional[List[Path]] = None, *, kind: Optional[str] = None,
         min_severity: str = "low") -> Dict[str, Any]:
    """Escanea scripts y agrega los hallazgos."""
    targets = paths if paths is not None else sorted(SCRIPTS_DIR.glob("vault_*.py"))
    limit = SEVERITY_ORDER.get(min_severity, 3)

    all_issues: List[Issue] = []
    for path in targets:
        for issue in scan_file(path):
            if kind and issue.kind != kind:
                continue
            if SEVERITY_ORDER.get(issue.severity, 3) > limit:
                continue
            all_issues.append(issue)

    all_issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 3), i.file, i.line))

    by_code: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for issue in all_issues:
        by_code[issue.code] = by_code.get(issue.code, 0) + 1
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

    critical = by_severity.get("critical", 0)
    return {
        "ok": critical == 0,
        "tool": "cli.analyzer",
        "scanned_files": len(targets),
        "total_issues": len(all_issues),
        "by_severity": by_severity,
        "by_code": by_code,
        "issues": [i.to_dict() for i in all_issues],
    }
