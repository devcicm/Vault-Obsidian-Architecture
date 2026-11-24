"""vault.kernel.features_y_flujos — detector determinista de features, capacidades y flujos de valor.

Analiza repositorios de código (internos o externos al vault) sin LLM y sin dependencias
fuera de stdlib:
- Python mediante `ast` (endpoints HTTP, comandos CLI, tools MCP, servicios, algoritmos,
  grafo real de llamadas y puntos de decisión `if`/`raise`).
- JS/TS/Go/C#/Java/Rust mediante reglas conservadoras precompiladas (rutas HTTP,
  tools MCP, funciones exportadas y llamadas directas).

Cada hallazgo publica evidencia verificable (`file` POSIX relativo, `line`, `symbol`,
`kind`), traza la cadena de llamadas extremo a extremo (`steps`), infiere las etapas
del flujo de valor (`value_stream`) y genera un diagrama Mermaid `flowchart TD`
con etiquetas entrecomilladas válidas para AP-25.

Hoja pura del núcleo: solo stdlib, compartida por `grafo` (`vault_code_query`) y
`autoria` (`vault_flow_save`) sin cruces entre contextos de dominio.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

#: Carpetas omitidas por defecto al escanear un repositorio.
DIRECTORIOS_IGNORADOS: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "out",
    "bin",
    "obj",
    "coverage",
    ".history",
    ".locks",
    "vault-backups",
    "vault-sandbox",
    "tests",
    "test",
    "__tests__",
})

#: Extensiones soportadas y lenguaje asociado.
EXTENSIONES_LENGUAJE: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".cs": "csharp",
    ".java": "java",
    ".rs": "rust",
}

#: Verbos HTTP reconocidos en decoradores/routers.
_HTTP_VERBS: frozenset[str] = frozenset({
    "get", "post", "put", "patch", "delete", "head", "options", "route", "api_route",
})

#: Prefijos/palabras clave que señalan algoritmos o lógica de cálculo determinista.
_PREFIJOS_ALGORITMO: Tuple[str, ...] = (
    "calc", "calcular", "compute", "score", "rank", "detectar", "detect",
    "parse", "parsear", "validate", "validar", "encrypt", "decrypt",
    "hash", "solve", "resolver", "reconstruir", "eval", "evaluar",
    "normaliz", "classify", "clasificar", "extract", "extraer",
    "format", "formatear", "build_graph", "construir_grafo",
)

#: Palabras clave de capas arquitectónicas para el flujo de valor estándar.
_CAPAS_ARQUITECTURA: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("api/entrypoint", ("api", "route", "router", "endpoint", "controller", "cli", "mcp", "server", "http")),
    ("security/auth", ("auth", "token", "jwt", "session", "oauth", "crypto", "secret", "safety", "guard", "perm")),
    ("service/domain", ("service", "usecase", "handler", "workflow", "orchestr", "manager", "engine", "core", "domain")),
    ("algorithm/computation", ("calc", "pric", "score", "rank", "detect", "parse", "validat", "algo", "metric")),
    ("repository/data", ("repo", "store", "db", "dao", "model", "cache", "index", "persist", "io", "storage")),
)

#: Símbolos genéricos de stdlib / lenguaje que no representan pasos de negocio propios.
_LLAMADAS_BUILTIN: frozenset[str] = frozenset({
    "print", "len", "str", "int", "float", "bool", "dict", "list", "set", "tuple",
    "range", "enumerate", "zip", "sorted", "reversed", "min", "max", "sum", "any",
    "all", "round", "abs", "isinstance", "issubclass", "hasattr", "getattr", "setattr",
    "super", "type", "open", "next", "iter", "map", "filter", "repr", "format",
    "append", "extend", "update", "get", "items", "keys", "values", "strip", "split",
    "join", "replace", "lower", "upper", "startswith", "endswith", "encode", "decode",
    "read_text", "write_text", "exists", "is_file", "is_dir", "mkdir", "resolve",
    "json", "loads", "dumps", "console", "log", "Error", "ValueError", "TypeError",
    "RuntimeError", "KeyError", "PermissionError", "OSError", "Exception",
})

# Regexes precompiladas a nivel de módulo (sin cuantificadores anidados).
_RE_JS_ROUTE = re.compile(
    r"\b(?:app|router|server)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_RE_JS_MCP_TOOL = re.compile(
    r"\bserver\.tool\(\s*['\"]([^'\"]+)['\"]",
)
_RE_JS_FUNC = re.compile(
    r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
)
_RE_JS_ARROW = re.compile(
    r"\b(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>",
)
_RE_GO_FUNC = re.compile(
    r"\bfunc\s+(?:\([^)]*\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
)
_RE_GO_ROUTE = re.compile(
    r"\bHandleFunc\(\s*\"([^\"]+)\"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)",
)
_RE_CS_JAVA_ROUTE = re.compile(
    r"\[Http(Get|Post|Put|Patch|Delete)\(\s*\"([^\"]*)\"\s*\)\]|@(Get|Post|Put|Patch|Delete)Mapping\(\s*\"([^\"]*)\"\s*\)",
)
_RE_RUST_FN = re.compile(
    r"\b(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)",
)
_RE_CALL_SIMPLE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RE_IF_DECISION = re.compile(r"\bif\s*\(([^)]{1,80})\)")
_RE_THROW = re.compile(r"\bthrow\s+new\s+([A-Za-z_][A-Za-z0-9_]*)")
_RE_NON_ALNUM = re.compile(r"[^A-Za-z0-9_]+")


def _inferir_capa(archivo: str, simbolo: str, kind: str) -> str:
    if kind in ("http_endpoint", "cli_command", "mcp_tool"):
        return "api/entrypoint"
    if kind == "algorithm":
        return "algorithm/computation"
    muestra = f"{archivo} {simbolo}".lower()
    for capa, pistas in _CAPAS_ARQUITECTURA:
        if any(p in muestra for p in pistas):
            return capa
    return "service/domain"


def _limpiar_etiqueta_mermaid(texto: str, max_len: int = 56) -> str:
    limpio = " ".join(str(texto or "").replace('"', "'").replace("[", "(").replace("]", ")").split())
    if len(limpio) > max_len:
        return limpio[: max_len - 3] + "..."
    return limpio


def _listar_archivos(raiz: Path, max_archivos: int, incluir_tests: bool) -> List[Path]:
    if raiz.is_file():
        return [raiz] if raiz.suffix.lower() in EXTENSIONES_LENGUAJE else []
    ignorados = DIRECTORIOS_IGNORADOS - ({"tests", "test", "__tests__"} if incluir_tests else set())
    archivos: List[Path] = []
    for ruta in sorted(raiz.rglob("*")):
        if len(archivos) >= max_archivos:
            break
        if not ruta.is_file():
            continue
        if ruta.suffix.lower() not in EXTENSIONES_LENGUAJE:
            continue
        try:
            rel_parts = ruta.relative_to(raiz).parts[:-1]
        except ValueError:
            rel_parts = ruta.parts[:-1]
        if any(p in ignorados for p in rel_parts):
            continue
        archivos.append(ruta)
    return archivos


# ── Indexación Python AST ────────────────────────────────────────────────────

def _nombre_call_ast(nodo: ast.AST) -> Optional[str]:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    return None


def _decorador_info(dec: ast.AST) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve `(kind, http_method, route_or_name)` si un decorador declara entrypoint."""
    if not isinstance(dec, ast.Call):
        return None, None, None
    func = dec.func
    attr = func.attr.lower() if isinstance(func, ast.Attribute) else (func.id.lower() if isinstance(func, ast.Name) else "")
    primer_str: Optional[str] = None
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        primer_str = dec.args[0].value
    if attr in _HTTP_VERBS:
        metodo = "ROUTE" if attr in ("route", "api_route") else attr.upper()
        return "http_endpoint", metodo, primer_str or "/"
    if attr == "command":
        return "cli_command", None, primer_str
    if attr == "tool":
        return "mcp_tool", None, primer_str
    return None, None, None


def _extraer_decisiones_ast(nodo: ast.AST, max_items: int = 4) -> List[str]:
    decisiones: List[str] = []
    for sub in ast.walk(nodo):
        if len(decisiones) >= max_items:
            break
        if isinstance(sub, ast.If):
            try:
                cond = ast.unparse(sub.test) if hasattr(ast, "unparse") else "condicion"
            except Exception:
                cond = "condicion"
            accion = "branch"
            for stmt in sub.body[:2]:
                if isinstance(stmt, ast.Raise):
                    exc = _nombre_call_ast(stmt.exc.func) if isinstance(stmt.exc, ast.Call) else (
                        stmt.exc.id if isinstance(stmt.exc, ast.Name) else "Error"
                    )
                    accion = f"raise {exc or 'Error'}"
                    break
                if isinstance(stmt, ast.Return):
                    accion = "return"
                    break
            decisiones.append(f"if {cond[:48]} -> {accion}")
    return decisiones


def _extraer_llamadas_ast(nodo: ast.AST) -> List[str]:
    llamadas: List[str] = []
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Call):
            nombre = _nombre_call_ast(sub.func)
            if nombre and nombre not in _LLAMADAS_BUILTIN and nombre not in llamadas:
                llamadas.append(nombre)
    return llamadas


def _indexar_python(rel: str, texto: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return [], []

    simbolos: List[Dict[str, Any]] = []
    extras_cli: List[Dict[str, Any]] = []

    # Detectar subcomandos argparse (`sub.add_parser("cmd")`)
    for sub in ast.walk(arbol):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "add_parser":
            if sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                cmd_name = sub.args[0].value.strip()
                if cmd_name:
                    extras_cli.append({
                        "symbol": f"cli:{cmd_name}",
                        "name": f"CLI {cmd_name}",
                        "kind": "cli_command",
                        "file": rel,
                        "line": getattr(sub, "lineno", 1),
                        "language": "python",
                        "inputs": [],
                        "summary": f"Subcomando CLI '{cmd_name}' registrado en argparse.",
                        "calls": [],
                        "decisions": [],
                        "http_method": None,
                        "route_path": cmd_name,
                    })

    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            simbolos.append(_construir_simbolo_python(rel, nodo, clase=None))
        elif isinstance(nodo, ast.ClassDef):
            for item in nodo.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    simbolos.append(_construir_simbolo_python(rel, item, clase=nodo.name))

    return simbolos, extras_cli


def _construir_simbolo_python(
    rel: str,
    nodo: ast.AST,
    clase: Optional[str],
) -> Dict[str, Any]:
    assert isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
    nombre_func = nodo.name
    simbolo = f"{clase}.{nombre_func}" if clase else nombre_func
    args = [a.arg for a in nodo.args.args if a.arg not in ("self", "cls")]
    doc = (ast.get_docstring(nodo) or "").strip().splitlines()
    resumen = doc[0].strip() if doc else ""
    llamadas = _extraer_llamadas_ast(nodo)
    decisiones = _extraer_decisiones_ast(nodo)

    kind: Optional[str] = None
    http_method: Optional[str] = None
    route_path: Optional[str] = None
    for dec in nodo.decorator_list:
        dk, hm, rp = _decorador_info(dec)
        if dk:
            kind, http_method, route_path = dk, hm, rp
            break

    return {
        "symbol": simbolo,
        "short_name": nombre_func,
        "class_name": clase,
        "file": rel,
        "line": nodo.lineno,
        "language": "python",
        "inputs": args,
        "summary": resumen,
        "calls": llamadas,
        "decisions": decisiones,
        "explicit_kind": kind,
        "http_method": http_method,
        "route_path": route_path,
    }


# ── Indexación conservadora multi-lenguaje (JS/TS/Go/C#/Java/Rust) ───────────

def _extraer_bloque_llaves(texto: str, pos_inicio: int, max_chars: int = 2400) -> str:
    fragmento = texto[pos_inicio : pos_inicio + max_chars]
    llave = fragmento.find("{")
    if llave == -1:
        return fragmento[:400]
    nivel = 0
    for idx in range(llave, len(fragmento)):
        ch = fragmento[idx]
        if ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                return fragmento[llave : idx + 1]
    return fragmento[llave:]


def _linea_en(texto: str, offset: int) -> int:
    return texto.count("\n", 0, offset) + 1


def _extraer_calls_y_decisiones_texto(cuerpo: str, propio: str) -> Tuple[List[str], List[str]]:
    llamadas: List[str] = []
    for m in _RE_CALL_SIMPLE.finditer(cuerpo):
        n = m.group(1)
        if n != propio and n not in _LLAMADAS_BUILTIN and n not in llamadas:
            llamadas.append(n)
    decisiones: List[str] = []
    for m in _RE_IF_DECISION.finditer(cuerpo):
        if len(decisiones) >= 4:
            break
        cond = " ".join(m.group(1).split())[:48]
        tr = _RE_THROW.search(cuerpo[m.end() : m.end() + 100])
        accion = f"throw {tr.group(1)}" if tr else "branch"
        decisiones.append(f"if {cond} -> {accion}")
    return llamadas, decisiones


def _indexar_multilenguaje(rel: str, lenguaje: str, texto: str) -> List[Dict[str, Any]]:
    simbolos: List[Dict[str, Any]] = []
    vistos: Set[Tuple[str, int]] = set()

    if lenguaje in ("javascript", "typescript"):
        for m in _RE_JS_ROUTE.finditer(texto):
            metodo = m.group(1).upper()
            ruta = m.group(2)
            linea = _linea_en(texto, m.start())
            cuerpo = _extraer_bloque_llaves(texto, m.end())
            calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, ruta)
            slug = _RE_NON_ALNUM.sub("_", ruta).strip("_") or "root"
            simbolos.append({
                "symbol": f"{metodo.lower()}_{slug}",
                "short_name": slug,
                "class_name": None,
                "file": rel,
                "line": linea,
                "language": lenguaje,
                "inputs": [],
                "summary": f"Ruta HTTP {metodo} {ruta}.",
                "calls": calls,
                "decisions": decisions,
                "explicit_kind": "http_endpoint",
                "http_method": metodo,
                "route_path": ruta,
            })
        for m in _RE_JS_MCP_TOOL.finditer(texto):
            tool_name = m.group(1)
            linea = _linea_en(texto, m.start())
            cuerpo = _extraer_bloque_llaves(texto, m.end())
            calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, tool_name)
            simbolos.append({
                "symbol": tool_name,
                "short_name": tool_name,
                "class_name": None,
                "file": rel,
                "line": linea,
                "language": lenguaje,
                "inputs": [],
                "summary": f"Tool MCP '{tool_name}'.",
                "calls": calls,
                "decisions": decisions,
                "explicit_kind": "mcp_tool",
                "http_method": None,
                "route_path": tool_name,
            })
        for regex in (_RE_JS_FUNC, _RE_JS_ARROW):
            for m in regex.finditer(texto):
                nombre = m.group(1)
                linea = _linea_en(texto, m.start())
                if (nombre, linea) in vistos:
                    continue
                vistos.add((nombre, linea))
                cuerpo = _extraer_bloque_llaves(texto, m.end())
                calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, nombre)
                args = [a.strip().split(":")[0].strip() for a in m.group(2).split(",") if a.strip()]
                simbolos.append({
                    "symbol": nombre,
                    "short_name": nombre,
                    "class_name": None,
                    "file": rel,
                    "line": linea,
                    "language": lenguaje,
                    "inputs": args,
                    "summary": "",
                    "calls": calls,
                    "decisions": decisions,
                    "explicit_kind": None,
                    "http_method": None,
                    "route_path": None,
                })
    elif lenguaje == "go":
        for m in _RE_GO_ROUTE.finditer(texto):
            ruta, handler = m.group(1), m.group(2)
            simbolos.append({
                "symbol": handler,
                "short_name": handler,
                "class_name": None,
                "file": rel,
                "line": _linea_en(texto, m.start()),
                "language": "go",
                "inputs": [],
                "summary": f"Handler HTTP {ruta} -> {handler}.",
                "calls": [handler],
                "decisions": [],
                "explicit_kind": "http_endpoint",
                "http_method": "ROUTE",
                "route_path": ruta,
            })
        for m in _RE_GO_FUNC.finditer(texto):
            nombre = m.group(1)
            cuerpo = _extraer_bloque_llaves(texto, m.end())
            calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, nombre)
            simbolos.append({
                "symbol": nombre,
                "short_name": nombre,
                "class_name": None,
                "file": rel,
                "line": _linea_en(texto, m.start()),
                "language": "go",
                "inputs": [],
                "summary": "",
                "calls": calls,
                "decisions": decisions,
                "explicit_kind": None,
                "http_method": None,
                "route_path": None,
            })
    elif lenguaje in ("csharp", "java"):
        for m in _RE_CS_JAVA_ROUTE.finditer(texto):
            metodo = (m.group(1) or m.group(3) or "ROUTE").upper()
            ruta = m.group(2) if m.group(2) is not None else (m.group(4) or "/")
            cuerpo = _extraer_bloque_llaves(texto, m.end())
            calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, ruta)
            slug = _RE_NON_ALNUM.sub("_", ruta).strip("_") or "root"
            simbolos.append({
                "symbol": f"{metodo.lower()}_{slug}",
                "short_name": slug,
                "class_name": None,
                "file": rel,
                "line": _linea_en(texto, m.start()),
                "language": lenguaje,
                "inputs": [],
                "summary": f"Endpoint {metodo} {ruta}.",
                "calls": calls,
                "decisions": decisions,
                "explicit_kind": "http_endpoint",
                "http_method": metodo,
                "route_path": ruta,
            })
    elif lenguaje == "rust":
        for m in _RE_RUST_FN.finditer(texto):
            nombre = m.group(1)
            cuerpo = _extraer_bloque_llaves(texto, m.end())
            calls, decisions = _extraer_calls_y_decisiones_texto(cuerpo, nombre)
            simbolos.append({
                "symbol": nombre,
                "short_name": nombre,
                "class_name": None,
                "file": rel,
                "line": _linea_en(texto, m.start()),
                "language": "rust",
                "inputs": [],
                "summary": "",
                "calls": calls,
                "decisions": decisions,
                "explicit_kind": None,
                "http_method": None,
                "route_path": None,
            })
    return simbolos


# ── Clasificación de features y trazado de flujos de valor ───────────────────

def _clasificar_feature(
    sim: Dict[str, Any],
    indice_por_nombre: Dict[str, List[Dict[str, Any]]],
) -> Optional[str]:
    if sim.get("explicit_kind"):
        return str(sim["explicit_kind"])
    short = str(sim.get("short_name") or "")
    if short.startswith("_") or short in ("__init__", "__repr__", "__str__"):
        return None
    if short == "main":
        return "cli_command"
    low = short.lower()
    if any(low.startswith(p) for p in _PREFIJOS_ALGORITMO):
        return "algorithm"
    llamadas_internas = [c for c in sim.get("calls", []) if c in indice_por_nombre]
    archivo_low = str(sim.get("file") or "").lower()
    es_modulo_servicio = any(
        k in archivo_low for k in ("service", "usecase", "handler", "controller", "workflow", "orchestr", "manager")
    )
    if es_modulo_servicio and len(llamadas_internas) >= 1:
        return "service_capability"
    if len(llamadas_internas) >= 2:
        return "service_capability"
    return None


def _resolver_callee(
    callee: str,
    archivo_origen: str,
    indice_por_nombre: Dict[str, List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    candidatos = indice_por_nombre.get(callee) or []
    if not candidatos:
        return None
    mismo_archivo = [c for c in candidatos if c["file"] == archivo_origen]
    if mismo_archivo:
        return mismo_archivo[0]
    return candidatos[0]


def _construir_mermaid_flujo(
    titulo: str,
    trigger: str,
    pasos: List[Dict[str, Any]],
) -> str:
    lineas = ["flowchart TD"]
    lineas.append(f'  N0["{_limpiar_etiqueta_mermaid(trigger)}"]')
    nodos_id: Dict[str, str] = {}
    contador = 1

    def _id_de(clave_nodo: str, etiqueta: str) -> str:
        nonlocal contador
        if clave_nodo not in nodos_id:
            nid = f"N{contador}"
            contador += 1
            nodos_id[clave_nodo] = nid
            lineas.append(f'  {nid}["{_limpiar_etiqueta_mermaid(etiqueta)}"]')
        return nodos_id[clave_nodo]

    if not pasos:
        nid = _id_de(titulo, titulo)
        lineas.append(f"  N0 --> {nid}")
        return "\n".join(lineas)

    aristas_vistas: Set[Tuple[str, str]] = set()
    for idx, paso in enumerate(pasos):
        origen = paso["from_symbol"]
        destino = paso["to_symbol"]
        id_origen = "N0" if idx == 0 else _id_de(origen, f"{paso.get('from_actor', '')}: {origen}")
        etiqueta_dest = f"{paso['actor']}: {destino}"
        id_dest = _id_de(destino, etiqueta_dest)
        if id_origen != id_dest and (id_origen, id_dest) not in aristas_vistas:
            aristas_vistas.add((id_origen, id_dest))
            lineas.append(f"  {id_origen} --> {id_dest}")
    return "\n".join(lineas)


def _trazar_flujo_de_feature(
    feat: Dict[str, Any],
    indice_por_nombre: Dict[str, List[Dict[str, Any]]],
    max_profundidad: int,
) -> Dict[str, Any]:
    pasos: List[Dict[str, Any]] = []
    decisiones_totales: List[str] = list(feat.get("decisions") or [])
    actores: List[str] = [Path(feat["file"]).stem]
    capas: List[str] = [_inferir_capa(feat["file"], feat["symbol"], feat["kind"])]
    archivos_relacionados: List[str] = [feat["file"]]

    visitados: Set[Tuple[str, str]] = {(feat["file"], feat["symbol"])}

    def _visitar(actual: Dict[str, Any], profundidad: int) -> None:
        if profundidad >= max_profundidad:
            return
        actor_origen = Path(actual["file"]).stem
        for callee in actual.get("calls", []):
            destino = _resolver_callee(callee, actual["file"], indice_por_nombre)
            if destino is None:
                continue
            clave_dest = (destino["file"], destino["symbol"])
            actor_dest = Path(destino["file"]).stem
            if actor_dest not in actores:
                actores.append(actor_dest)
            if destino["file"] not in archivos_relacionados:
                archivos_relacionados.append(destino["file"])
            capa_dest = _inferir_capa(destino["file"], destino["symbol"], destino.get("explicit_kind") or "service_capability")
            if capa_dest not in capas:
                capas.append(capa_dest)
            pasos.append({
                "step": len(pasos) + 1,
                "name": destino["short_name"],
                "from_symbol": actual["symbol"],
                "from_actor": actor_origen,
                "to_symbol": destino["symbol"],
                "actor": actor_dest,
                "file": destino["file"],
                "line": destino["line"],
                "action": destino.get("summary") or f"Ejecuta {destino['symbol']}({', '.join(destino.get('inputs') or [])})",
                "decisions": list(destino.get("decisions") or []),
            })
            for d in destino.get("decisions") or []:
                if d not in decisiones_totales:
                    decisiones_totales.append(d)
            if clave_dest not in visitados:
                visitados.add(clave_dest)
                _visitar(destino, profundidad + 1)

    _visitar(feat, 0)

    if feat["kind"] == "http_endpoint":
        trigger = f"HTTP {feat.get('http_method') or 'ROUTE'} {feat.get('route_path') or '/'}"
    elif feat["kind"] == "cli_command":
        trigger = f"CLI {feat.get('route_path') or feat['symbol']}"
    elif feat["kind"] == "mcp_tool":
        trigger = f"MCP tool {feat.get('route_path') or feat['symbol']}"
    else:
        trigger = f"Call {feat['symbol']}({', '.join(feat.get('inputs') or [])})"

    mermaid = _construir_mermaid_flujo(feat["name"], trigger, pasos)
    return {
        "name": feat["name"],
        "kind": feat["kind"],
        "entry_symbol": feat["symbol"],
        "entry_file": feat["file"],
        "entry_line": feat["line"],
        "steps_count": len(pasos),
        "steps": pasos,
        "related_code": archivos_relacionados,
        "value_stream": {
            "trigger": trigger,
            "stages": capas,
            "actors": actores,
            "decisions": decisiones_totales[:8],
            "outcome": feat.get("summary") or f"Completa el flujo de {feat['symbol']}.",
        },
        "mermaid": mermaid,
    }


def _nombre_feature(sim: Dict[str, Any], kind: str) -> str:
    if kind == "http_endpoint" and sim.get("route_path"):
        return f"{sim.get('http_method') or 'HTTP'} {sim['route_path']} ({sim['symbol']})"
    if kind == "cli_command" and sim.get("route_path"):
        return f"CLI {sim['route_path']}"
    if kind == "mcp_tool" and sim.get("route_path"):
        return f"MCP {sim['route_path']}"
    return sim["symbol"]


def _coincide_filtro(feat: Dict[str, Any], filtro: Optional[str]) -> bool:
    if not filtro:
        return True
    q = filtro.strip().lower()
    if not q:
        return True
    campos = (
        feat.get("name", ""),
        feat.get("symbol", ""),
        feat.get("route_path") or "",
        feat.get("file", ""),
        feat.get("kind", ""),
    )
    return any(q in str(c).lower() for c in campos)


def detectar_features_y_flujos(
    ruta_objetivo: Path,
    filtro_feature: Optional[str] = None,
    max_archivos: int = 2000,
    max_profundidad: int = 5,
    incluir_tests: bool = False,
) -> Dict[str, Any]:
    """Detecta features, capacidades, algoritmos y flujos de valor en `ruta_objetivo`.

    Solo lectura y 100% determinista. Devuelve rutas POSIX relativas al objetivo
    (sin fugar rutas absolutas de la máquina).
    """
    raiz = Path(ruta_objetivo).resolve()
    archivos = _listar_archivos(raiz, max_archivos=max_archivos, incluir_tests=incluir_tests)
    base_rel = raiz.parent if raiz.is_file() else raiz

    todos_simbolos: List[Dict[str, Any]] = []
    extras_cli: List[Dict[str, Any]] = []

    for archivo in archivos:
        rel = archivo.relative_to(base_rel).as_posix()
        lenguaje = EXTENSIONES_LENGUAJE[archivo.suffix.lower()]
        try:
            texto = archivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if lenguaje == "python":
            sims, clis = _indexar_python(rel, texto)
            todos_simbolos.extend(sims)
            extras_cli.extend(clis)
        else:
            todos_simbolos.extend(_indexar_multilenguaje(rel, lenguaje, texto))

    indice_por_nombre: Dict[str, List[Dict[str, Any]]] = {}
    for s in todos_simbolos:
        short = str(s.get("short_name") or s.get("symbol") or "")
        if short:
            indice_por_nombre.setdefault(short, []).append(s)

    features: List[Dict[str, Any]] = []
    flujos: List[Dict[str, Any]] = []
    callees_cubiertos: Set[Tuple[str, str]] = set()

    # Orden de prioridad: primero entrypoints reales (HTTP, MCP, CLI), luego servicios y algoritmos.
    prioridad = {"http_endpoint": 0, "mcp_tool": 1, "cli_command": 2, "service_capability": 3, "algorithm": 4}
    candidatos: List[Dict[str, Any]] = []
    for s in todos_simbolos:
        kind = _clasificar_feature(s, indice_por_nombre)
        if not kind:
            continue
        item = {
            **s,
            "kind": kind,
            "name": _nombre_feature(s, kind),
        }
        candidatos.append(item)

    for cli_item in extras_cli:
        candidatos.append({
            **cli_item,
            "short_name": cli_item["symbol"],
            "explicit_kind": "cli_command",
        })

    candidatos.sort(key=lambda x: (prioridad.get(x["kind"], 9), x["file"], x["line"]))

    for feat in candidatos:
        if not _coincide_filtro(feat, filtro_feature):
            continue
        features.append({
            "name": feat["name"],
            "kind": feat["kind"],
            "symbol": feat["symbol"],
            "file": feat["file"],
            "line": feat["line"],
            "language": feat["language"],
            "inputs": feat.get("inputs", []),
            "http_method": feat.get("http_method"),
            "route_path": feat.get("route_path"),
            "summary": feat.get("summary", ""),
            "decisions": feat.get("decisions", []),
        })

        # Trazar flujo completo para entrypoints y servicios raíz que no son simples sub-pasos de un entrypoint ya trazado.
        es_entrypoint = feat["kind"] in ("http_endpoint", "mcp_tool", "cli_command")
        clave_feat = (feat["file"], feat["symbol"])
        tiene_cadena = any(c in indice_por_nombre for c in feat.get("calls", []))
        if es_entrypoint or (tiene_cadena and clave_feat not in callees_cubiertos):
            flujo = _trazar_flujo_de_feature(feat, indice_por_nombre, max_profundidad=max_profundidad)
            flujos.append(flujo)
            for paso in flujo["steps"]:
                callees_cubiertos.add((paso["file"], paso["to_symbol"]))

    resumen_tipos: Dict[str, int] = {}
    for f in features:
        resumen_tipos[f["kind"]] = resumen_tipos.get(f["kind"], 0) + 1

    return {
        "target": raiz.name,
        "files_scanned": len(archivos),
        "symbols_indexed": len(todos_simbolos),
        "features_count": len(features),
        "flows_count": len(flujos),
        "summary_by_kind": resumen_tipos,
        "features": features,
        "flows": flujos,
    }
