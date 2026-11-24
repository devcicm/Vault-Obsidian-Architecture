"""Motor determinista de Code Review / PR Review guiado por el vault (Fase N2).

Hoja pura del kernel (stdlib + PyYAML + vault.kernel.*): no importa scripts ni
contextos superiores. Orquesta siete ejes sobre un `git diff` o una lista de
archivos fuente:
  1. Trazabilidad `@vault:` por archivo y simbolo + resolucion de reglas vivas
  2. Cobertura RDD (`REQ <-> metodo <-> test`) y operaciones de negocio `PAT-10`
  3. Seguridad y secretos acotados a lineas de codigo real (sin ruido en docstrings)
  4. Higiene estatica (`AP-51`, `except:` desnudo, funciones largas, deuda de tests)
  5. Drift documental e impacto transitivo en backlinks del vault
  6. Linters del repositorio (opcional bajo `--run-linters`)
  7. Veredicto determinista (`APPROVE` / `COMMENT` / `REQUEST_CHANGES`) y visor HTML clicable
"""

from __future__ import annotations

import ast
import io
import json
import re
import shutil
import subprocess
import tokenize
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import features_y_flujos, procesos_git, rutas
from .errores import construir_error
from .trazabilidad_codigo import (
    CODE_EXTS,
    construir_indice_notas_vault,
    construir_matriz_rdd,
    extract_all_vault_refs,
    extraer_nombre_declaracion_linea,
    renderizar_visor_html,
    resolver_referencia_vault,
)

# Regexes precompiladas a nivel de modulo (sin cuantificadores anidados).
_RE_DIFF_FILE = re.compile(r"^\+\+\+ b/(.+)$")
_RE_HUNK_HDR = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_RE_TEST_FILE = re.compile(r"(?:^|/)(?:test_[^/]+|[^/]+_test\.[^/]+|[^/]+\.(?:test|spec)\.[^/]+)$", re.IGNORECASE)

# Reglas de seguridad precisas (JS/TS y secretos). En Python se usa AST real.
_RE_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_GH_TOKEN = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
_RE_PRIV_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_RE_HARDCODED_SECRET = re.compile(
    r"\b(?:api_key|apikey|secret_key|client_secret|access_token|auth_token|db_password|password)\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]",
    re.IGNORECASE,
)
_RE_JS_EVAL = re.compile(r"(?<![.\w$])eval\s*\(")
_RE_JS_CHILD_EXEC = re.compile(r"\b(?:child_process\.exec|execSync)\s*\(")
_RE_JS_XSS = re.compile(r"\b(?:innerHTML\s*=|dangerouslySetInnerHTML)\b")
_RE_SQL_KEYWORDS = re.compile(
    r"\b(?:SELECT\s+\S.{0,80}\s+FROM|INSERT\s+INTO\s+[A-Za-z_]|UPDATE\s+[A-Za-z_][A-Za-z0-9_]*\s+SET|DELETE\s+FROM\s+[A-Za-z_])\b",
    re.IGNORECASE,
)
_RE_TODO_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")

_SECRET_VAR_NAMES = frozenset(
    {
        "api_key", "apikey", "secret_key", "client_secret", "access_token",
        "auth_token", "db_password", "password", "passwd", "private_key",
    }
)

_PLACEHOLDER_SECRETS = frozenset(
    {
        "changeme", "placeholder", "example", "your_api_key", "your-api-key",
        "xxxxxxxx", "test_token", "dummy_secret", "fake_secret", "redacted",
    }
)
_CRITICAL_PAT10_OPS = frozenset({"auth", "rule", "lifecycle", "workflow"})
_PY_EXTS = frozenset({".py"})
_JS_TS_EXTS = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})
_LINTER_EXTS_PY = frozenset({".py"})
_LINTER_EXTS_JS = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs"})


def parsear_diff_unificado(diff_text: str) -> Dict[str, Dict[str, Any]]:
    """Parsea un `git diff -U0` y devuelve por archivo sus lineas anadidas y contadores."""
    archivos: Dict[str, Dict[str, Any]] = {}
    actual: Optional[str] = None
    linea_nueva = 0

    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            m_file = _RE_DIFF_FILE.match(raw)
            if m_file:
                actual = m_file.group(1).strip().replace("\\", "/")
                archivos.setdefault(
                    actual,
                    {"added_lines": {}, "added_count": 0, "removed_count": 0},
                )
            else:
                actual = None
            continue
        if actual is None:
            continue
        if raw.startswith("@@ "):
            m_hunk = _RE_HUNK_HDR.match(raw)
            if m_hunk:
                linea_nueva = int(m_hunk.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            archivos[actual]["added_lines"][linea_nueva] = raw[1:]
            archivos[actual]["added_count"] += 1
            linea_nueva += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            archivos[actual]["removed_count"] += 1
        elif not raw.startswith("\\"):
            linea_nueva += 1

    return archivos


def _simbolos_con_rangos(content: str, file_path: Path) -> List[Dict[str, Any]]:
    """Lista simbolos (funciones, metodos, clases) con su rango de lineas."""
    if file_path.suffix.lower() == ".py":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        out: List[Dict[str, Any]] = []

        def _vis(nodo: ast.AST, padre: str = "") -> None:
            for hijo in ast.iter_child_nodes(nodo):
                if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qname = f"{padre}.{hijo.name}" if padre else hijo.name
                    decs = [getattr(d, "lineno", hijo.lineno) for d in getattr(hijo, "decorator_list", [])]
                    start = min(decs) if decs else hijo.lineno
                    end = getattr(hijo, "end_lineno", hijo.lineno) or hijo.lineno
                    kind = "class" if isinstance(hijo, ast.ClassDef) else "method" if padre else "function"
                    llamadas: List[str] = []
                    if not isinstance(hijo, ast.ClassDef):
                        for sub in ast.walk(hijo):
                            if isinstance(sub, ast.Call):
                                if isinstance(sub.func, ast.Name):
                                    llamadas.append(sub.func.id)
                                elif isinstance(sub.func, ast.Attribute):
                                    llamadas.append(sub.func.attr)
                    out.append(
                        {
                            "name": hijo.name,
                            "qualified_name": qname,
                            "kind": kind,
                            "start_line": start,
                            "def_line": hijo.lineno,
                            "end_line": end,
                            "length": end - hijo.lineno + 1,
                            "calls": llamadas[:20],
                        }
                    )
                    if isinstance(hijo, ast.ClassDef):
                        _vis(hijo, qname)

        _vis(tree)
        return out

    # Deteccion lineal O(n) para lenguajes C-like / JS / TS / Go / Rust (AP-57: reusa kernel)
    lines = content.splitlines()
    out_gen: List[Dict[str, Any]] = []
    for idx, ln in enumerate(lines, 1):
        sym = extraer_nombre_declaracion_linea(ln)
        if sym:
            out_gen.append(
                {
                    "name": sym,
                    "qualified_name": sym,
                    "kind": "function",
                    "start_line": idx,
                    "def_line": idx,
                    "end_line": min(len(lines), idx + 40),
                    "length": 1,
                    "calls": [],
                }
            )
    return out_gen


def _lineas_codigo_real_python(content: str) -> Set[int]:
    """Devuelve numeros de linea Python que contienen tokens ejecutables (excluye comentarios y docstrings)."""
    doc_lines: Set[int] = set()
    try:
        tree = ast.parse(content)
        for nodo in ast.walk(tree):
            if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if nodo.body and isinstance(nodo.body[0], ast.Expr):
                    val = nodo.body[0].value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        s = getattr(val, "lineno", 0)
                        e = getattr(val, "end_lineno", s) or s
                        for ln in range(s, e + 1):
                            doc_lines.add(ln)
    except SyntaxError:
        pass

    code_lines: Set[int] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(content).readline)
        for tok in tokens:
            if tok.type in (
                tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING,
            ):
                continue
            ln = tok.start[0]
            if ln not in doc_lines:
                code_lines.add(ln)
    except (tokenize.TokenError, IndentationError):
        for idx, line in enumerate(content.splitlines(), 1):
            st = line.strip()
            if st and not st.startswith("#") and idx not in doc_lines:
                code_lines.add(idx)
    return code_lines


def _es_linea_comentario_generico(line: str) -> bool:
    st = line.strip()
    return not st or st.startswith("//") or st.startswith("/*") or st.startswith("*") or st.startswith("#") or st.startswith("--")


def _escanear_seguridad_python_ast(
    rel_path: str,
    content: str,
    added_lines: Dict[int, str],
) -> List[Dict[str, Any]]:
    """Escanea vulnerabilidades y secretos en Python por AST real (cero falsos positivos en mensajes/docstrings)."""
    hallazgos: List[Dict[str, Any]] = []
    added_set = set(added_lines.keys())
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return hallazgos

    # Identificar lineas de docstrings para no analizarlas como literales ejecutables
    doc_nodes: Set[int] = set()
    for nodo in ast.walk(tree):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if nodo.body and isinstance(nodo.body[0], ast.Expr) and isinstance(nodo.body[0].value, ast.Constant):
                doc_nodes.add(id(nodo.body[0].value))

    for nodo in ast.walk(tree):
        lineno = getattr(nodo, "lineno", 0)
        if lineno not in added_set:
            continue

        # 1. Llamadas peligrosas reales (AST Call, nunca texto dentro de strings)
        if isinstance(nodo, ast.Call):
            fn = nodo.func
            if isinstance(fn, ast.Name) and fn.id in ("eval", "exec"):
                hallazgos.append(
                    {
                        "code": "SEC_DYNAMIC_EXEC",
                        "severity": "blocker",
                        "file": rel_path,
                        "line": lineno,
                        "message": f"Llamada directa a `{fn.id}()` introducida en el diff (riesgo de inyeccion).",
                    }
                )
            elif isinstance(fn, ast.Attribute):
                obj_name = fn.value.id if isinstance(fn.value, ast.Name) else ""
                attr = fn.attr
                if obj_name == "os" and attr in ("system", "popen"):
                    hallazgos.append(
                        {
                            "code": "SEC_COMMAND_INJECTION",
                            "severity": "blocker",
                            "file": rel_path,
                            "line": lineno,
                            "message": f"Ejecucion de shell insegura `os.{attr}()`.",
                        }
                    )
                elif obj_name == "yaml" and attr == "load":
                    usa_safe = any(
                        kw.arg == "Loader"
                        and (
                            (isinstance(kw.value, ast.Name) and "Safe" in kw.value.id)
                            or (isinstance(kw.value, ast.Attribute) and "Safe" in kw.value.attr)
                        )
                        for kw in nodo.keywords
                    )
                    if not usa_safe:
                        hallazgos.append(
                            {
                                "code": "SEC_UNSAFE_YAML",
                                "severity": "blocker",
                                "file": rel_path,
                                "line": lineno,
                                "message": "Uso de `yaml.load()` sin `SafeLoader`; usar `yaml.safe_load()` (AP-44).",
                            }
                        )
                elif obj_name == "pickle" and attr in ("load", "loads"):
                    hallazgos.append(
                        {
                            "code": "SEC_UNSAFE_DESERIALIZATION",
                            "severity": "warning",
                            "file": rel_path,
                            "line": lineno,
                            "message": f"Deserializacion con `pickle.{attr}()` sobre datos potencialmente no confiables.",
                        }
                    )
            for kw in nodo.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    hallazgos.append(
                        {
                            "code": "SEC_COMMAND_INJECTION",
                            "severity": "blocker",
                            "file": rel_path,
                            "line": lineno,
                            "message": "Llamada con `shell=True` introducida en el diff.",
                        }
                    )
                elif kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    hallazgos.append(
                        {
                            "code": "SEC_TLS_DISABLED",
                            "severity": "warning",
                            "file": rel_path,
                            "line": lineno,
                            "message": "Verificacion TLS desactivada (`verify=False`).",
                        }
                    )

        # 2. SQL dinamico real en f-strings (`ast.JoinedStr`)
        elif isinstance(nodo, ast.JoinedStr):
            partes_const = " ".join(
                v.value for v in nodo.values if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
            tiene_expr = any(isinstance(v, ast.FormattedValue) for v in nodo.values)
            if tiene_expr and _RE_SQL_KEYWORDS.search(partes_const):
                hallazgos.append(
                    {
                        "code": "SEC_SQL_INJECTION",
                        "severity": "blocker",
                        "file": rel_path,
                        "line": lineno,
                        "message": "Consulta SQL construida con f-string interpolado; usar parametros preparados.",
                    }
                )

        # 3. Secretos literales en asignaciones o tokens reales (excluyendo regex/docstrings)
        elif isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            val_node = nodo.value
            if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str) and id(val_node) not in doc_nodes:
                sval = val_node.value.strip()
                targets: List[str] = []
                if isinstance(nodo, ast.Assign):
                    for t in nodo.targets:
                        if isinstance(t, ast.Name):
                            targets.append(t.id.lower())
                        elif isinstance(t, ast.Attribute):
                            targets.append(t.attr.lower())
                elif isinstance(nodo.target, ast.Name):
                    targets.append(nodo.target.id.lower())

                if _RE_AWS_KEY.search(sval) or _RE_GH_TOKEN.search(sval) or _RE_PRIV_KEY.search(sval):
                    # Omitir patrones regex que contienen expresiones regulares (`[0-9A-Z]`, `\b`)
                    if "[0-9" not in sval and "\\b" not in sval:
                        hallazgos.append(
                            {
                                "code": "SEC_SECRET",
                                "severity": "blocker",
                                "file": rel_path,
                                "line": lineno,
                                "message": "Posible credencial o clave privada hardcodeada en el diff.",
                            }
                        )
                elif len(sval) >= 8 and any(t in _SECRET_VAR_NAMES for t in targets):
                    vl = sval.lower()
                    if vl not in _PLACEHOLDER_SECRETS and not vl.startswith("${") and not vl.startswith("<"):
                        hallazgos.append(
                            {
                                "code": "SEC_SECRET",
                                "severity": "blocker",
                                "file": rel_path,
                                "line": lineno,
                                "message": "Posible secreto/contrasena literal hardcodeada en variable sensible.",
                            }
                        )

    return hallazgos


def _escanear_seguridad_lineas(
    rel_path: str,
    ext: str,
    content: str,
    added_lines: Dict[int, str],
) -> List[Dict[str, Any]]:
    """Escanea seguridad y secretos sobre codigo real (AST en Python; reglas acotadas en otros lenguajes)."""
    if ext in _PY_EXTS:
        return _escanear_seguridad_python_ast(rel_path, content, added_lines)

    hallazgos: List[Dict[str, Any]] = []
    for lineno in sorted(added_lines.keys()):
        texto = added_lines[lineno]
        if _es_linea_comentario_generico(texto):
            continue

        if _RE_AWS_KEY.search(texto) or _RE_GH_TOKEN.search(texto) or _RE_PRIV_KEY.search(texto):
            hallazgos.append(
                {
                    "code": "SEC_SECRET",
                    "severity": "blocker",
                    "file": rel_path,
                    "line": lineno,
                    "message": "Posible credencial o clave privada hardcodeada en el diff.",
                }
            )
            continue

        m_sec = _RE_HARDCODED_SECRET.search(texto)
        if m_sec:
            val_l = m_sec.group(1).strip().lower()
            if val_l not in _PLACEHOLDER_SECRETS and not val_l.startswith("${") and not val_l.startswith("<"):
                hallazgos.append(
                    {
                        "code": "SEC_SECRET",
                        "severity": "blocker",
                        "file": rel_path,
                        "line": lineno,
                        "message": "Posible secreto/contrasena literal hardcodeada en codigo.",
                    }
                )

        if ext in _JS_TS_EXTS:
            # Excluye RegExp.prototype.exec() — solo eval() global o child_process.exec/execSync
            if _RE_JS_EVAL.search(texto) or _RE_JS_CHILD_EXEC.search(texto):
                hallazgos.append(
                    {
                        "code": "SEC_DYNAMIC_EXEC",
                        "severity": "blocker",
                        "file": rel_path,
                        "line": lineno,
                        "message": "Uso de eval()/child_process.exec introducido en el diff.",
                    }
                )
            if _RE_JS_XSS.search(texto):
                hallazgos.append(
                    {
                        "code": "SEC_XSS",
                        "severity": "warning",
                        "file": rel_path,
                        "line": lineno,
                        "message": "Asignacion directa a `innerHTML`/`dangerouslySetInnerHTML` (riesgo XSS).",
                    }
                )

    return hallazgos


def _escanear_higiene_python(
    rel_path: str,
    content: str,
    added_lines: Dict[int, str],
) -> List[Dict[str, Any]]:
    """Detecta antipatrones de higiene (AP-51, except desnudo, funciones muy largas) en lineas tocadas."""
    hallazgos: List[Dict[str, Any]] = []
    added_set = set(added_lines.keys())
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return hallazgos

    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.ExceptHandler) and nodo.lineno in added_set:
            if nodo.type is None:
                hallazgos.append(
                    {
                        "code": "HYGIENE_BARE_EXCEPT",
                        "severity": "warning",
                        "file": rel_path,
                        "line": nodo.lineno,
                        "message": "`except:` desnudo captura SystemExit/KeyboardInterrupt; especificar excepciones concretas.",
                    }
                )
            elif isinstance(nodo.type, ast.Name) and nodo.type.id == "Exception":
                if len(nodo.body) == 1 and isinstance(nodo.body[0], (ast.Pass, ast.Continue)):
                    hallazgos.append(
                        {
                            "code": "AP-51",
                            "severity": "warning",
                            "file": rel_path,
                            "line": nodo.lineno,
                            "message": "Handler amplio `except Exception: pass/continue` oculta fallos silenciosamente (AP-51).",
                        }
                    )
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(nodo, "end_lineno", nodo.lineno) or nodo.lineno
            largo = end - nodo.lineno + 1
            if largo > 120 and any(nodo.lineno <= ln <= end for ln in added_set):
                hallazgos.append(
                    {
                        "code": "HYGIENE_LONG_FUNCTION",
                        "severity": "info",
                        "file": rel_path,
                        "line": nodo.lineno,
                        "symbol": nodo.name,
                        "message": f"Funcion `{nodo.name}` tocada tiene {largo} lineas (>120); evaluar extraccion modular.",
                    }
                )

    for lineno, texto in sorted(added_lines.items()):
        if _RE_TODO_MARKER.search(texto) and "#" in texto:
            hallazgos.append(
                {
                    "code": "HYGIENE_TODO",
                    "severity": "info",
                    "file": rel_path,
                    "line": lineno,
                    "message": f"Marcador pendiente introducido: {texto.strip()[:90]}",
                }
            )
    return hallazgos


def _calcular_impacto_vault(
    vault_root: Path,
    changed_rel_files: Sequence[str],
    resolved_note_paths: Set[str],
    indice: Dict[str, Any],
) -> Dict[str, Any]:
    """Identifica notas del vault impactadas directamente y via backlinks (1 salto)."""
    directas: Set[str] = set(resolved_note_paths)
    norm_changed = [f.replace("\\", "/").lower() for f in changed_rel_files]

    for entry in indice["by_rel"].values():
        fm = entry["frontmatter"]
        for key in ("source_file", "file_path"):
            val = str(fm.get(key) or "").replace("\\", "/").lower()
            if val and any(val == c or val.endswith("/" + c) or c.endswith("/" + val) for c in norm_changed):
                directas.add(entry["path"])
        rel_code = fm.get("related_code")
        if isinstance(rel_code, str):
            rc_list = [x.strip().replace("\\", "/").lower() for x in rel_code.split(",") if x.strip()]
        elif isinstance(rel_code, list):
            rc_list = [str(x).strip().replace("\\", "/").lower() for x in rel_code if str(x).strip()]
        else:
            rc_list = []
        if rc_list and any(
            any(rc == c or rc.endswith("/" + c) or c.endswith("/" + rc) for c in norm_changed)
            for rc in rc_list
        ):
            directas.add(entry["path"])

    # Backlinks transitivos desde 99_Index/graph.json (si existe)
    transitivas: Set[str] = set()
    graph_path = vault_root / "99_Index" / "graph.json"
    if directas and graph_path.is_file():
        try:
            g = json.loads(graph_path.read_text(encoding="utf-8", errors="ignore"))
            edges = g.get("edges") or g.get("links") or []
            directas_stems = {Path(p).stem.lower() for p in directas}
            for e in edges:
                src = str(e.get("source") or e.get("from") or "").replace("\\", "/")
                dst = str(e.get("target") or e.get("to") or "").replace("\\", "/")
                if dst in directas or Path(dst).stem.lower() in directas_stems:
                    if src and src not in directas:
                        transitivas.add(src)
        except (OSError, ValueError, TypeError):
            pass

    return {
        "direct_notes": sorted(directas),
        "backlink_impacted_notes": sorted(transitivas)[:25],
        "total_impacted": len(directas) + len(transitivas),
    }


def _ejecutar_linters_opcionales(
    repo_root: Path,
    changed_abs_files: Sequence[Path],
) -> List[Dict[str, Any]]:
    """Ejecuta linters disponibles (ruff/eslint) sobre archivos tocados sin inventar resultados."""
    resultados: List[Dict[str, Any]] = []
    py_files = [str(p) for p in changed_abs_files if p.suffix.lower() in _LINTER_EXTS_PY and p.is_file()]
    js_files = [str(p) for p in changed_abs_files if p.suffix.lower() in _LINTER_EXTS_JS and p.is_file()]

    if py_files:
        ruff = shutil.which("ruff")
        if ruff:
            try:
                proc = subprocess.run(
                    [ruff, "check", "--output-format", "concise", *py_files[:40]],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                lineas = [l for l in proc.stdout.splitlines() if l.strip()]
                resultados.append(
                    {
                        "linter": "ruff",
                        "status": "passed" if proc.returncode == 0 else "failed",
                        "exit_code": proc.returncode,
                        "files_checked": len(py_files[:40]),
                        "issues_sample": lineas[:20],
                    }
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                resultados.append({"linter": "ruff", "status": "error", "detail": str(exc)})
        else:
            resultados.append({"linter": "ruff", "status": "skipped", "reason": "not_installed"})

    if js_files:
        eslint = shutil.which("eslint")
        if eslint:
            try:
                proc = subprocess.run(
                    [eslint, "--format", "compact", *js_files[:40]],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                lineas = [l for l in proc.stdout.splitlines() if l.strip()]
                resultados.append(
                    {
                        "linter": "eslint",
                        "status": "passed" if proc.returncode == 0 else "failed",
                        "exit_code": proc.returncode,
                        "files_checked": len(js_files[:40]),
                        "issues_sample": lineas[:20],
                    }
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                resultados.append({"linter": "eslint", "status": "error", "detail": str(exc)})
        else:
            resultados.append({"linter": "eslint", "status": "skipped", "reason": "not_installed"})

    return resultados


def _obtener_diff_git(
    repo_root: Path,
    base: Optional[str],
    head: Optional[str],
    staged: bool,
) -> Tuple[str, str, Optional[str]]:
    """Obtiene el diff unificado git (-U0) fallando cerrado ante errores de git (AP-51/AP-60)."""
    if base:
        ref_head = head or "HEAD"
        rango = f"{base}..{ref_head}"
        proc = procesos_git.ejecutar_git(
            repo_root, ["diff", "-U0", rango], capture_output=True, timeout=30
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or f"git diff {rango} fallo").strip()
            return "", f"git:{rango}", err
        return proc.stdout, f"git:{rango}", None

    if staged:
        proc = procesos_git.ejecutar_git(
            repo_root, ["diff", "-U0", "--cached"], capture_output=True, timeout=30
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "git diff --cached fallo").strip()
            return "", "git:staged", err
        return proc.stdout, "git:staged", None

    proc = procesos_git.ejecutar_git(
        repo_root, ["diff", "-U0", "HEAD"], capture_output=True, timeout=30
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout, "git:working-tree", None

    proc_last = procesos_git.ejecutar_git(
        repo_root, ["diff", "-U0", "HEAD~1..HEAD"], capture_output=True, timeout=30
    )
    if proc_last.returncode == 0 and proc_last.stdout.strip():
        return proc_last.stdout, "git:HEAD~1..HEAD", None

    if proc.returncode != 0 and proc_last.returncode != 0:
        err = (proc.stderr or proc_last.stderr or "No es un repositorio git valido").strip()
        return "", "git:error", err

    return "", "git:clean", None


def ejecutar_code_review(
    vault_root: Path,
    repo_root: Path,
    *,
    project: Optional[str] = None,
    base: Optional[str] = None,
    head: Optional[str] = None,
    staged: bool = False,
    files: Optional[Sequence[str]] = None,
    run_linters: bool = False,
    include_rdd: bool = True,
    generar_html: bool = False,
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de 7 ejes de Code Review / PR Review."""
    repo = repo_root.resolve()
    indice = construir_indice_notas_vault(vault_root)

    # 1. Determinar archivos y lineas a revisar
    diff_por_archivo: Dict[str, Dict[str, Any]] = {}
    review_scope = ""
    if files:
        review_scope = f"files:{len(files)}"
        for f_str in files:
            p = Path(f_str)
            abs_p = p.resolve() if p.is_absolute() else (repo / p).resolve()
            if not abs_p.is_file():
                continue
            try:
                rel = str(abs_p.relative_to(repo)).replace("\\", "/")
            except ValueError:
                rel = str(abs_p).replace("\\", "/")
            txt = abs_p.read_text(encoding="utf-8", errors="ignore")
            added = {i: ln for i, ln in enumerate(txt.splitlines(), 1)}
            diff_por_archivo[rel] = {
                "abs_path": abs_p,
                "added_lines": added,
                "added_count": len(added),
                "removed_count": 0,
            }
    else:
        diff_txt, review_scope, git_error = _obtener_diff_git(
            repo, base=base, head=head, staged=staged
        )
        if git_error is not None:
            return construir_error(
                "vault_code_review",
                "INVALID_ACTION",
                f"No se pudo obtener el diff git ({review_scope}): {git_error}",
            )
        parsed = parsear_diff_unificado(diff_txt)
        for rel, info in parsed.items():
            abs_p = (repo / rel).resolve()
            info["abs_path"] = abs_p
            diff_por_archivo[rel] = info

    findings: List[Dict[str, Any]] = []
    applicable_rules: List[Dict[str, Any]] = []
    touched_symbols: List[Dict[str, Any]] = []
    files_summary: List[Dict[str, Any]] = []
    resolved_note_paths: Set[str] = set()
    html_files_payload: List[Dict[str, Any]] = []
    prod_code_changed = 0
    test_files_changed = 0
    changed_abs_list: List[Path] = []

    for rel, info in sorted(diff_por_archivo.items()):
        abs_p: Path = info["abs_path"]
        ext = abs_p.suffix.lower()
        is_code = ext in CODE_EXTS
        is_test = bool(_RE_TEST_FILE.search(rel))
        if is_test:
            test_files_changed += 1
        elif is_code:
            prod_code_changed += 1

        if not abs_p.is_file():
            files_summary.append(
                {
                    "file": rel,
                    "status": "deleted_or_missing",
                    "added": info["added_count"],
                    "removed": info["removed_count"],
                }
            )
            continue

        changed_abs_list.append(abs_p)
        content = abs_p.read_text(encoding="utf-8", errors="ignore")
        added_lines: Dict[int, str] = info["added_lines"]
        added_set = set(added_lines.keys())

        # Eje 1: Extraccion y resolucion de todas las etiquetas @vault: (cabecera + simbolos)
        refs = extract_all_vault_refs(content, file_path=abs_p) if is_code else []
        file_has_header_vault = any(r["scope"] == "file" for r in refs)
        symbol_refs_map: Dict[str, List[Dict[str, Any]]] = {}
        file_resolved_refs: List[Dict[str, Any]] = []

        for ref in refs:
            res = resolver_referencia_vault(
                vault_root,
                ref["ref_target"],
                anchor=ref["anchor"],
                project=project,
                indice=indice,
                incluir_contenido=True,
            )
            item = {
                "file": rel,
                "line": ref["line"],
                "scope": ref["scope"],
                "symbol": ref["symbol"],
                "raw_ref": ref["raw_ref"],
                "span": ref.get("span"),
                **res,
            }
            file_resolved_refs.append(item)
            if ref["symbol"]:
                symbol_refs_map.setdefault(ref["symbol"], []).append(item)
                if ref.get("symbol_short"):
                    symbol_refs_map.setdefault(ref["symbol_short"], []).append(item)

            if not res["resolved"]:
                findings.append(
                    {
                        "code": "AP-72",
                        "severity": "blocker",
                        "file": rel,
                        "line": ref["line"],
                        "symbol": ref["symbol"],
                        "message": f"Referencia `@vault: {ref['raw_ref']}` no resuelve ({res['status']}).",
                        "candidates": res.get("candidates", []),
                    }
                )
            else:
                if res["path"]:
                    resolved_note_paths.add(res["path"])
                applicable_rules.append(
                    {
                        "file": rel,
                        "line": ref["line"],
                        "symbol": ref["symbol"],
                        "raw_ref": ref["raw_ref"],
                        "note_path": res["path"],
                        "title": res.get("title"),
                        "status": res["status"],
                        "note_status": res.get("note_status"),
                        "superseded_by": res.get("superseded_by"),
                        "rules_excerpt": res.get("rules_excerpt"),
                        "links": res.get("links"),
                    }
                )
                if res.get("stale"):
                    findings.append(
                        {
                            "code": "STALE_VAULT_REF",
                            "severity": "warning",
                            "file": rel,
                            "line": ref["line"],
                            "symbol": ref["symbol"],
                            "message": (
                                f"Referencia `@vault: {ref['raw_ref']}` apunta a nota `{res['path']}` "
                                f"en estado `{res['status']}`"
                                + (f" (sustituida por `{res['superseded_by']}`)." if res.get("superseded_by") else ".")
                            ),
                        }
                    )
                elif ref["anchor"] and res.get("anchor_found") is False:
                    findings.append(
                        {
                            "code": "ANCHOR_NOT_FOUND",
                            "severity": "warning",
                            "file": rel,
                            "line": ref["line"],
                            "symbol": ref["symbol"],
                            "message": f"Ancla `#{ref['anchor']}` no existe en `{res['path']}`.",
                        }
                    )

        # Eje 2: Simbolos tocados + PAT-10 + cobertura RDD
        simbolos = _simbolos_con_rangos(content, abs_p) if is_code else []
        file_touched_syms: List[str] = []
        for sym in simbolos:
            lineas_sym_tocadas = sorted(ln for ln in added_set if sym["start_line"] <= ln <= sym["end_line"])
            if not lineas_sym_tocadas:
                continue
            ops = features_y_flujos.clasificar_operaciones_negocio(
                rel, sym["qualified_name"], sym["kind"], calls=sym.get("calls", ())
            )
            refs_del_sym = symbol_refs_map.get(sym["qualified_name"]) or symbol_refs_map.get(sym["name"]) or []
            has_doc = bool(refs_del_sym) or file_has_header_vault
            sym_entry = {
                "file": rel,
                "symbol": sym["qualified_name"],
                "kind": sym["kind"],
                "line": sym["def_line"],
                "changed_lines_count": len(lineas_sym_tocadas),
                "business_operations": ops,
                "vault_refs": [r["raw_ref"] for r in refs_del_sym],
                "documented": has_doc,
            }
            touched_symbols.append(sym_entry)
            file_touched_syms.append(sym["qualified_name"])

            if not is_test and sym["kind"] != "class" and not has_doc:
                ops_criticas = [op for op in ops if op in _CRITICAL_PAT10_OPS]
                if ops_criticas:
                    findings.append(
                        {
                            "code": "MISSING_BUSINESS_DOC_REF",
                            "norm": "PAT-10",
                            "severity": "warning",
                            "file": rel,
                            "line": sym["def_line"],
                            "symbol": sym["qualified_name"],
                            "business_operations": ops_criticas,
                            "message": (
                                f"Metodo de negocio `{sym['qualified_name']}` ({', '.join(ops_criticas)}) "
                                "no tiene etiqueta `@vault:` vinculada a su requisito o ADR."
                            ),
                            "suggested_command": (
                                f"python {rutas.SCRIPTS}/vault_code_tag.py --link-vault REQ-001 "
                                f"--file \"{rel}\" --symbol \"{sym['name']}\""
                            ),
                        }
                    )

        # Eje 3: Seguridad acotada a lineas anadidas de codigo real
        if is_code and added_lines:
            findings.extend(_escanear_seguridad_lineas(rel, ext, content, added_lines))

        # Eje 4: Higiene estatica (Python)
        if ext in _PY_EXTS and added_lines:
            findings.extend(_escanear_higiene_python(rel, content, added_lines))

        files_summary.append(
            {
                "file": rel,
                "is_code": is_code,
                "is_test": is_test,
                "added": info["added_count"],
                "removed": info["removed_count"],
                "vault_refs_count": len(refs),
                "touched_symbols": file_touched_syms,
            }
        )

        if generar_html and is_code:
            html_files_payload.append(
                {
                    "path": rel,
                    "content": content,
                    "references": file_resolved_refs,
                    "changed_lines": sorted(added_set),
                }
            )

    # Alerta de deuda de tests cuando se modifica codigo de produccion sin tocar pruebas
    if prod_code_changed > 0 and test_files_changed == 0 and not files:
        findings.append(
            {
                "code": "NO_TESTS_TOUCHED",
                "severity": "warning",
                "file": "",
                "line": 0,
                "message": (
                    f"El cambio modifica {prod_code_changed} archivo(s) de codigo fuente "
                    "sin anadir ni actualizar ningun archivo de pruebas."
                ),
            }
        )

    # Eje 5: Drift e impacto documental en el vault
    vault_impact = _calcular_impacto_vault(
        vault_root, list(diff_por_archivo.keys()), resolved_note_paths, indice
    )

    # Eje 6: Linters opcionales
    linters_report = _ejecutar_linters_opcionales(repo, changed_abs_list) if run_linters else []
    for lrep in linters_report:
        if lrep.get("status") == "failed":
            findings.append(
                {
                    "code": "LINTER_FAILED",
                    "severity": "blocker",
                    "file": "",
                    "line": 0,
                    "message": f"Linter `{lrep['linter']}` fallo (exit={lrep.get('exit_code')}).",
                    "issues_sample": lrep.get("issues_sample", []),
                }
            )

    # Matriz RDD acotada a los archivos revisados (si hay requisitos en el vault)
    rdd_summary: Optional[Dict[str, Any]] = None
    if include_rdd:
        rdd_full = construir_matriz_rdd(vault_root, changed_abs_list, project=project, indice=indice)
        if rdd_full["total_requirements"] > 0:
            rdd_summary = rdd_full

    # Eje 7: Veredicto determinista
    blockers = sum(1 for f in findings if f.get("severity") == "blocker")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    infos = sum(1 for f in findings if f.get("severity") == "info")

    if blockers > 0:
        verdict = "REQUEST_CHANGES"
    elif warnings > 0:
        verdict = "COMMENT"
    elif len(files_summary) == 0:
        # Honestidad (AP-45/AP-60): sin archivos revisados no se certifica APPROVE
        verdict = "NO_DATA"
    else:
        verdict = "APPROVE"

    resumen = {
        "scope": review_scope,
        "verdict": verdict,
        "files_reviewed": len(files_summary),
        "symbols_touched": len(touched_symbols),
        "applicable_rules": len(applicable_rules),
        "blockers": blockers,
        "warnings": warnings,
        "infos": infos,
        "impacted_vault_notes": vault_impact["total_impacted"],
    }

    html_content = (
        renderizar_visor_html(
            titulo=f"Code Review — {project or repo.name} ({review_scope})",
            archivos=html_files_payload,
            resumen=resumen,
        )
        if generar_html
        else None
    )

    return {
        "ok": True,
        "verdict": verdict,
        "review_scope": review_scope,
        "repo": str(repo),
        "project": project,
        "summary": resumen,
        "files": files_summary,
        "touched_symbols": touched_symbols,
        "applicable_rules": applicable_rules,
        "findings": findings,
        "vault_impact": vault_impact,
        "rdd_traceability": rdd_summary,
        "linters": linters_report,
        "html_content": html_content,
    }
