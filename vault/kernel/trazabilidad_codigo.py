"""Trazabilidad declarativa codigo <-> vault a nivel de archivo y simbolo (RDD + AP-72).

Hoja pura del kernel (stdlib + PyYAML): no importa scripts ni contextos
superiores. Permite anotar metodos, funciones o clases con una sola linea
`@vault:` apuntando a la ruta de la nota o a un codigo corto (`REQ-042`,
`QA-003`, `FLOW-007`, `BUG-012`, `NCR-005`, `ADR-0001` o `proyecto/REQ-042`)
y opcionalmente a un ancla de seccion (`REQ-042#redondeo`), manteniendo la
especificacion y las reglas de negocio dentro del vault en lugar de saturar
el codigo fuente con comentarios extensos.

Tambien construye la matriz de trazabilidad RDD (`REQ <-> metodo <-> test`)
cruzando `14_Requirements/`, el codigo fuente anotado y `15_Tests/`.
"""

from __future__ import annotations

import ast
import html as _html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

import yaml

from .enumeracion import notas_en_disco

# Extensiones de codigo fuente reconocidas para escaneo y etiquetado.
CODE_EXTS = frozenset(
    {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".cs", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".hpp",
        ".kt", ".swift", ".rb", ".php", ".dart", ".scala",
        ".sh", ".bash", ".zsh", ".sql", ".r",
    }
)

# Estilos de comentario por extension (compartidos con vault/grafo/enlace_codigo).
COMMENT_STYLES: Dict[str, str] = {
    ".cs": "line", ".ts": "line", ".tsx": "line", ".js": "line",
    ".jsx": "line", ".mjs": "line", ".cjs": "line", ".java": "line",
    ".cpp": "line", ".c": "line", ".h": "line", ".hpp": "line",
    ".go": "line", ".swift": "line", ".kt": "line", ".rs": "line",
    ".dart": "line", ".scala": "line", ".php": "line",
    ".py": "hash", ".rb": "hash", ".sh": "hash", ".bash": "hash",
    ".zsh": "hash", ".yml": "hash", ".yaml": "hash", ".r": "hash",
    ".html": "open_close", ".xml": "open_close", ".svg": "open_close",
    ".css": "block", ".scss": "block", ".sass": "block", ".less": "block",
    ".sql": "dash", ".md": "none",
}

VAULT_TAG_TEMPLATES: Dict[str, str] = {
    "line": "// @vault: {note_path}  — {title}",
    "hash": "# @vault: {note_path}  — {title}",
    "open_close": "<!-- @vault: {note_path}  — {title} -->",
    "block": "/* @vault: {note_path}  — {title} */",
    "dash": "-- @vault: {note_path}  — {title}",
}

# Patron retrocompatible de cabecera (sin sangria, con guion/raya de titulo).
VAULT_TAG_PATTERN = re.compile(
    r"^(?://|#|<!--|/\*|--)\s*@vault:\s*(\S+)\s*[—\-]+\s*(.*?)(?:\s*(?:-->|\*/))?\s*$",
    re.MULTILINE,
)

# Patron extendido: acepta cualquier sangria, titulo opcional y anclas `#seccion`.
# Sin cuantificadores anidados para cumplir el filtro anti-ReDoS.
VAULT_REF_ANY_PATTERN = re.compile(
    r"^([ \t]*)(?:///|//|#|<!--|/\*\*?|(?:\*(?![/]))|--)[ \t]*@vault:[ \t]*([^\s—–]+)"
    r"(?:[ \t]+(?:[—–]|-{1,2})[ \t]*(.*?))?(?:[ \t]*(?:-->|\*/))?[ \t]*$",
    re.MULTILINE,
)

# Patrones lineales O(n) (sin grupos repetidos que causen backtracking) para
# detectar declaraciones en lenguajes no Python.
_MODIFICADORES_DECLARACION = frozenset(
    {
        "export", "default", "public", "private", "protected", "internal",
        "static", "final", "abstract", "virtual", "override", "async",
        "inline", "extern", "unsafe", "readonly", "sealed", "partial",
    }
)
_PALABRAS_NAMESPACE = frozenset({"namespace", "package", "module"})
_PALABRAS_CLASE = frozenset({"class", "interface", "struct", "enum", "trait", "record", "type"})
_PALABRAS_DECLARACION = frozenset(
    {
        "function", "def", "fn", "func", "class", "interface", "struct",
        "enum", "trait", "record", "type", "module", "namespace", "package",
        "procedure", "view", "trigger",
    }
)
_RE_IDENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")
_RE_DECORATOR_OR_COMMENT = re.compile(
    r"^[ \t]*(?:@|\[[A-Za-z_]|//|#|/\*|\*|--|<!--)"
)
_RE_SHORT_CODE = re.compile(r"^([A-Za-z]{2,8})-(\d{1,6})$")
_RE_FILENAME_CODE_PREFIX = re.compile(r"^([a-z]{2,8})-(\d{1,6})(?:[-_.]|$)", re.IGNORECASE)
_RE_ADR_NUM_PREFIX = re.compile(r"^(\d{3,4})[-_]", re.IGNORECASE)
_RE_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_RE_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_RE_REQ_TOKEN = re.compile(r"\bREQ-(\d{1,5})\b", re.IGNORECASE)

_IGNORED_VAULT_DIRS = frozenset({"00_System", "99_Index", ".history", ".trash", ".git"})
_IGNORED_SOURCE_DIRS = frozenset(
    {
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", "target", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    }
)
_FRONTMATTER_ID_KEYS = (
    "req_id", "qa_id", "bug_id", "ncr_id", "flow_id", "adr_id", "doc_id", "id",
)
_STALE_NOTE_STATUSES = frozenset({"superseded", "deprecated", "obsolete", "archived"})
_KEYWORDS_NO_SYMBOL = frozenset(
    {
        "if", "for", "foreach", "while", "switch", "catch", "return", "else",
        "elif", "using", "lock", "checked", "unchecked", "fixed", "synchronized",
    }
)
_PRIORITY_SECTIONS = (
    "reglas", "rules", "criterios de aceptacion", "acceptance criteria",
    "decision", "invariantes", "descripcion", "description", "especificacion",
    "specification", "contexto", "context", "requisitos", "requirements",
)


def comment_style(file_path: Path) -> str:
    return COMMENT_STYLES.get(file_path.suffix.lower(), "line")


def line_offset(lines: List[str], line_index: int) -> int:
    return sum(len(line) for line in lines[:line_index])


def _slug_anchor(text: str) -> str:
    limpio = text.strip().lower()
    # Normalizacion basica de acentos comunes en espanol
    tabla = str.maketrans("áéíóúüñ", "aeiouun")
    limpio = limpio.translate(tabla)
    return _RE_NON_ALNUM.sub("-", limpio).strip("-")


def _parse_frontmatter_and_body(text: str) -> Tuple[Dict[str, Any], str]:
    """Lee el frontmatter con yaml.safe_load (AP-44) y devuelve (meta, cuerpo)."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text
    raw_yaml = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    try:
        parsed = yaml.safe_load(raw_yaml)
    except (yaml.YAMLError, RecursionError):  # AP-61: mismo criterio que vault_lib.parse_frontmatter
        return {}, body
    return (parsed if isinstance(parsed, dict) else {}), body


def _normalizar_codigo(codigo: str) -> str:
    """Normaliza REQ-42 / req-042 -> REQ-042 y ADR-1 -> ADR-0001 para emparejar."""
    m = _RE_SHORT_CODE.match(codigo.strip())
    if not m:
        return codigo.strip().upper()
    pref = m.group(1).upper()
    num = int(m.group(2))
    ancho = 4 if pref == "ADR" else 3
    return f"{pref}-{num:0{ancho}d}"


def _codigo_sin_ceros(codigo: str) -> str:
    m = _RE_SHORT_CODE.match(codigo.strip())
    if not m:
        return codigo.strip().upper()
    return f"{m.group(1).upper()}-{int(m.group(2))}"


def _simbolos_python(content: str) -> List[Dict[str, Any]]:
    """Extrae definiciones Python con rango de lineas (incluyendo decoradores)."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    simbolos: List[Dict[str, Any]] = []

    def _visitar(nodo: ast.AST, padre: str = "") -> None:
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nombre = f"{padre}.{hijo.name}" if padre else hijo.name
                dec_lines = [getattr(d, "lineno", hijo.lineno) for d in getattr(hijo, "decorator_list", [])]
                start = min(dec_lines) if dec_lines else hijo.lineno
                end = getattr(hijo, "end_lineno", hijo.lineno) or hijo.lineno
                kind = "class" if isinstance(hijo, ast.ClassDef) else "method" if padre else "function"
                simbolos.append(
                    {
                        "name": hijo.name,
                        "qualified_name": nombre,
                        "kind": kind,
                        "def_line": hijo.lineno,
                        "start_line": start,
                        "end_line": end,
                    }
                )
                if isinstance(hijo, ast.ClassDef):
                    _visitar(hijo, nombre)

    _visitar(tree)
    simbolos.sort(key=lambda s: (s["start_line"], s["def_line"]))
    return simbolos


def _extraer_identificador_calificado(texto: str) -> Optional[str]:
    """Extrae un identificador simple o calificado (`Foo.Bar`, `Foo::Bar`, `Foo\\Bar`) en O(n)."""
    s = texto.lstrip()
    if not s:
        return None
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isalnum() or ch in ("_", ".", "\\"):
            i += 1
        elif ch == ":" and i + 1 < n and s[i + 1] == ":":
            i += 2
        else:
            break
    cand = s[:i].rstrip(".\\:")
    if not cand or not (cand[0].isalpha() or cand[0] == "_"):
        return None
    segs = cand.replace("::", ".").replace("\\", ".").split(".")
    if all(seg and (seg[0].isalpha() or seg[0] == "_") for seg in segs):
        return cand
    return None


def extraer_declaracion_linea(
    linea: str,
    siguiente_linea: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Extrae `(nombre, kind)` de namespace/clase/funcion/metodo en O(n) sin backtracking."""
    s = linea.strip()
    if not s or _RE_DECORATOR_OR_COMMENT.match(s):
        return None
    tokens = s.split()
    idx = 0
    while idx < len(tokens) and tokens[idx].lower() in _MODIFICADORES_DECLARACION:
        idx += 1
    if idx >= len(tokens):
        return None
    kw = tokens[idx].lower()

    # 1. `namespace Foo.Bar`, `package com.acme`, `class Bar`, `function foo`, `func (r *Srv) Baz`, `def calc`
    if kw in _PALABRAS_DECLARACION:
        resto = " ".join(tokens[idx + 1 :]).lstrip()
        if kw in _PALABRAS_NAMESPACE:
            nombre_ns = _extraer_identificador_calificado(resto)
            if nombre_ns and nombre_ns not in _KEYWORDS_NO_SYMBOL:
                return nombre_ns, "namespace"
            return None
        if resto.startswith("(") and ")" in resto:
            resto = resto.split(")", 1)[1].lstrip()
        m = _RE_IDENT.match(resto)
        if m and m.group(1) not in _KEYWORDS_NO_SYMBOL:
            kind = "class" if kw in _PALABRAS_CLASE else "function"
            return m.group(1), kind
        return None

    # 2. `const foo = (...) =>` / `let foo = async (...) =>`
    if kw in ("const", "let", "var") and idx + 1 < len(tokens) and "=>" in s:
        m = _RE_IDENT.match(tokens[idx + 1])
        if m and m.group(1) not in _KEYWORDS_NO_SYMBOL:
            return m.group(1), "function"
        return None

    # 3. Metodo C#/Java/TS/Go/C++ con firma:
    #    - K&R: `public decimal CalcularIva(decimal monto) {`
    #    - Allman (llave en linea siguiente): `public decimal CalcularIva(decimal monto)` + `{`
    #    - Expression-bodied (C#): `public decimal CalcularIva(decimal m) => ...;`
    if "(" in s and ";" not in s.split("(", 1)[0]:
        antes_paren = s.split("(", 1)[0].rstrip()
        despues_paren = s.split("(", 1)[1]
        es_kr = s.endswith("{")
        es_allman = (
            ")" in despues_paren
            and "=" not in antes_paren
            and not s.endswith(";")
            and siguiente_linea is not None
            and siguiente_linea.lstrip().startswith("{")
        )
        es_expr_body = (
            ")" in despues_paren
            and "=>" in despues_paren.split(")", 1)[1]
            and len(antes_paren.split()) >= 2
            and "=" not in antes_paren
        )
        if (es_kr or es_allman or es_expr_body) and antes_paren:
            ultimo = antes_paren.split()[-1]
            # Limpiar genericos simples como `Calcular<T>`
            if "<" in ultimo:
                ultimo = ultimo.split("<", 1)[0]
            m = _RE_IDENT.match(ultimo)
            if m and m.group(1) not in _KEYWORDS_NO_SYMBOL:
                return m.group(1), "method"
    return None


def extraer_nombre_declaracion_linea(
    linea: str,
    siguiente_linea: Optional[str] = None,
) -> Optional[str]:
    """Extrae el nombre de namespace/clase/funcion/metodo en una linea en tiempo O(n)."""
    decl = extraer_declaracion_linea(linea, siguiente_linea=siguiente_linea)
    return decl[0] if decl else None


def _simbolo_siguiente_generico(
    lines: List[str], after_line_1based: int
) -> Optional[Tuple[str, str, int]]:
    """Busca la declaracion inmediata tras un comentario @vault: (una linea en blanco corta el enlace)."""
    n = len(lines)
    for idx in range(after_line_1based, min(n, after_line_1based + 12)):
        linea = lines[idx]
        if not linea.strip():
            # Una linea en blanco separa cabecera de archivo de la primera declaracion
            return None
        if _RE_DECORATOR_OR_COMMENT.match(linea):
            continue
        sig = lines[idx + 1] if idx + 1 < n else None
        decl = extraer_declaracion_linea(linea, siguiente_linea=sig)
        if decl:
            return decl[0], decl[1], idx + 1
        # Si encontramos otra sentencia real que no es declaracion, no adivinar (AP-45).
        return None
    return None


def _simbolo_para_linea(
    lines: List[str],
    line_1based: int,
    py_symbols: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Asocia un tag `@vault:` en `line_1based` al simbolo contiguo (sin linea en blanco en medio)."""
    if py_symbols is not None:
        next_code_line: Optional[int] = None
        for idx in range(line_1based, min(len(lines), line_1based + 15)):
            s = lines[idx].strip()
            if not s:
                # Linea en blanco: tag de cabecera de archivo, no pegado al simbolo siguiente
                return None
            if s.startswith("#"):
                continue
            next_code_line = idx + 1
            break
        if next_code_line is not None:
            for sym in py_symbols:
                if sym["start_line"] == next_code_line or sym["def_line"] == next_code_line:
                    return sym
        return None

    hit = _simbolo_siguiente_generico(lines, line_1based)
    if hit is None:
        return None
    nombre, kind, def_line = hit
    return {
        "name": nombre,
        "qualified_name": nombre,
        "kind": kind,
        "def_line": def_line,
        "start_line": def_line,
    }


def extract_all_vault_refs(
    content: str,
    file_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Extrae TODAS las referencias `@vault:` (cabecera y por simbolo, con cualquier sangria)."""
    lines = content.splitlines()
    es_py = file_path is not None and file_path.suffix.lower() == ".py"
    py_symbols = _simbolos_python(content) if es_py else None

    primera_linea_codigo = len(lines) + 1
    for i, ln in enumerate(lines, 1):
        st = ln.strip()
        if not st or st.startswith("#!") or _RE_DECORATOR_OR_COMMENT.match(ln):
            continue
        primera_linea_codigo = i
        break

    refs: List[Dict[str, Any]] = []
    for match in VAULT_REF_ANY_PATTERN.finditer(content):
        line_no = content.count("\n", 0, match.start()) + 1
        line_start_pos = content.rfind("\n", 0, match.start()) + 1
        indent = match.group(1)
        raw_ref = match.group(2).strip().rstrip(",;)")
        title = (match.group(3) or "").strip()

        if "#" in raw_ref:
            ref_target, anchor = raw_ref.split("#", 1)
            anchor = anchor.strip() or None
        else:
            ref_target, anchor = raw_ref, None

        sym_info = _simbolo_para_linea(lines, line_no, py_symbols=py_symbols)
        # Un tag sin sangria en la cabecera (antes de cualquier codigo, y sin simbolo
        # inmediatamente pegado o en linea <= 3 cuando hay codigo debajo) es de archivo.
        if indent == "" and line_no < primera_linea_codigo and sym_info is None:
            scope = "file"
        elif indent == "" and line_no <= 2 and sym_info is None:
            scope = "file"
        elif sym_info is not None:
            scope = "symbol"
        else:
            scope = "file" if indent == "" and line_no < primera_linea_codigo else "inline"

        tag_pos = match.group(0).find("@vault:")
        tag_char_start = match.start() + (tag_pos if tag_pos >= 0 else 0)
        ref_char_end = match.end(2)

        refs.append(
            {
                "line": line_no,
                "indent": indent,
                "raw_ref": raw_ref,
                "ref_target": ref_target,
                "anchor": anchor,
                "title": title,
                "scope": scope,
                "symbol": sym_info["qualified_name"] if sym_info else None,
                "symbol_short": sym_info["name"] if sym_info else None,
                "symbol_kind": sym_info["kind"] if sym_info else None,
                "symbol_line": sym_info["def_line"] if sym_info else None,
                "span": {
                    "line": line_no,
                    "col_start": tag_char_start - line_start_pos + 1,
                    "col_end": ref_char_end - line_start_pos + 1,
                    "char_start": tag_char_start,
                    "char_end": ref_char_end,
                },
            }
        )
    return refs


def construir_indice_notas_vault(vault_root: Path) -> Dict[str, Any]:
    """Indexa notas del vault por ruta relativa y por codigos cortos (REQ-NNN, ADR-NNNN, etc.)."""
    raiz = vault_root.resolve()
    by_rel: Dict[str, Dict[str, Any]] = {}
    by_code: Dict[str, List[Dict[str, Any]]] = {}

    if not raiz.is_dir():
        return {"root": raiz, "by_rel": by_rel, "by_code": by_code}

    secciones = [
        d.name
        for d in raiz.iterdir()
        if d.is_dir() and d.name not in _IGNORED_VAULT_DIRS and not d.name.startswith(".")
    ]
    for md in notas_en_disco(raiz, secciones, incluir_indices=False):
        try:
            rel_parts = md.relative_to(raiz).parts
        except ValueError:
            continue
        if not rel_parts or any(p in _IGNORED_VAULT_DIRS for p in rel_parts):
            continue

        rel_str = "/".join(rel_parts)
        rel_no_ext = rel_str[:-3] if rel_str.lower().endswith(".md") else rel_str

        try:
            raw = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fm, _body = _parse_frontmatter_and_body(raw)

        entry = {
            "path": rel_str,
            "rel_no_ext": rel_no_ext,
            "abs_path": md,
            "stem": md.stem,
            "project": str(fm.get("project") or "").strip(),
            "title": str(fm.get("title") or md.stem).strip(),
            "type": str(fm.get("type") or "").strip(),
            "status": str(fm.get("status") or "").strip().lower(),
            "superseded_by": fm.get("superseded_by"),
            "frontmatter": fm,
        }
        by_rel[rel_no_ext.lower()] = entry

        codigos = set()
        for key in _FRONTMATTER_ID_KEYS:
            val = fm.get(key)
            if isinstance(val, str) and val.strip():
                codigos.add(val.strip().upper())
                codigos.add(_normalizar_codigo(val))
                codigos.add(_codigo_sin_ceros(val))

        m_pref = _RE_FILENAME_CODE_PREFIX.match(md.stem)
        if m_pref:
            raw_code = f"{m_pref.group(1).upper()}-{m_pref.group(2)}"
            codigos.add(raw_code)
            codigos.add(_normalizar_codigo(raw_code))
            codigos.add(_codigo_sin_ceros(raw_code))

        # Decisiones en 03_Decisions/ con nombre 0001-algo.md -> ADR-0001
        if rel_parts[0] == "03_Decisions":
            m_adr = _RE_ADR_NUM_PREFIX.match(md.stem)
            if m_adr:
                raw_adr = f"ADR-{m_adr.group(1)}"
                codigos.add(_normalizar_codigo(raw_adr))
                codigos.add(_codigo_sin_ceros(raw_adr))

        for c in codigos:
            by_code.setdefault(c, []).append(entry)

    return {"root": raiz, "by_rel": by_rel, "by_code": by_code}


def _extraer_secciones_markdown(body: str) -> List[Tuple[str, str, str]]:
    """Devuelve lista de (heading, slug, contenido) de un cuerpo Markdown."""
    secciones: List[Tuple[str, str, str]] = []
    actual_h: Optional[str] = None
    actual_slug: str = ""
    buf: List[str] = []
    for line in body.splitlines():
        m = _RE_HEADING.match(line)
        if m:
            if actual_h is not None:
                secciones.append((actual_h, actual_slug, "\n".join(buf).strip()))
            actual_h = m.group(2).strip()
            actual_slug = _slug_anchor(actual_h)
            buf = []
        else:
            if actual_h is not None:
                buf.append(line)
    if actual_h is not None:
        secciones.append((actual_h, actual_slug, "\n".join(buf).strip()))
    return secciones


def _extraer_extracto_reglas(
    body: str,
    anchor: Optional[str] = None,
    max_chars: int = 1200,
) -> Tuple[str, Optional[bool], Optional[str]]:
    """Extrae la seccion pedida por `#ancla` o las secciones de reglas/criterios de la nota."""
    secciones = _extraer_secciones_markdown(body)
    if anchor:
        objetivo = _slug_anchor(anchor)
        # Primera pasada: coincidencia exacta de slug (ej: `## Redondeo` antes que H1 con palabra redondeo)
        for heading, slug, contenido in secciones:
            if slug == objetivo:
                texto = f"## {heading}\n{contenido}".strip()
                return texto[:max_chars], True, heading
        # Segunda pasada: coincidencia parcial
        for heading, slug, contenido in secciones:
            if objetivo in slug:
                texto = f"## {heading}\n{contenido}".strip()
                return texto[:max_chars], True, heading
        return body.strip()[:max_chars], False, None

    elegidas: List[str] = []
    for heading, slug, contenido in secciones:
        if not contenido:
            continue
        if any(p in slug.replace("-", " ") for p in _PRIORITY_SECTIONS):
            elegidas.append(f"## {heading}\n{contenido}")
    if elegidas:
        return "\n\n".join(elegidas).strip()[:max_chars], None, None
    return body.strip()[:max_chars], None, None


def resolver_referencia_vault(
    vault_root: Path,
    ref_target: str,
    anchor: Optional[str] = None,
    project: Optional[str] = None,
    indice: Optional[Dict[str, Any]] = None,
    incluir_contenido: bool = True,
    max_chars: int = 1200,
) -> Dict[str, Any]:
    """Resuelve una referencia `@vault:` (ruta relativa o ID corto) contra el vault."""
    idx = indice if indice is not None else construir_indice_notas_vault(vault_root)
    raiz: Path = idx["root"]

    objetivo = ref_target.strip().replace("\\", "/")
    if "#" in objetivo and anchor is None:
        objetivo, anchor = objetivo.split("#", 1)
        anchor = anchor.strip() or None

    proyecto_explicito = project
    objetivo_limpio = objetivo[:-3] if objetivo.lower().endswith(".md") else objetivo

    candidatos: List[Dict[str, Any]] = []

    # 1. Coincidencia exacta por ruta relativa (segura dentro del vault)
    por_ruta = idx["by_rel"].get(objetivo_limpio.lower())
    if por_ruta is not None:
        candidatos = [por_ruta]
    else:
        # 1b. Comprobacion directa en disco con proteccion contra traversal
        candidato_disco = (raiz / f"{objetivo_limpio}.md").resolve()
        try:
            candidato_disco.relative_to(raiz)
            dentro = True
        except ValueError:
            dentro = False
        if dentro and candidato_disco.is_file():
            rel_str = str(candidato_disco.relative_to(raiz)).replace("\\", "/")
            fm, _ = _parse_frontmatter_and_body(candidato_disco.read_text(encoding="utf-8", errors="ignore"))
            candidatos = [
                {
                    "path": rel_str,
                    "rel_no_ext": rel_str[:-3],
                    "abs_path": candidato_disco,
                    "stem": candidato_disco.stem,
                    "project": str(fm.get("project") or "").strip(),
                    "title": str(fm.get("title") or candidato_disco.stem).strip(),
                    "type": str(fm.get("type") or "").strip(),
                    "status": str(fm.get("status") or "").strip().lower(),
                    "superseded_by": fm.get("superseded_by"),
                    "frontmatter": fm,
                }
            ]

    # 2. Forma `proyecto/REQ-042` -> acota proyecto y busca por codigo corto
    if not candidatos and "/" in objetivo_limpio:
        parte_proj, parte_cod = objetivo_limpio.rsplit("/", 1)
        if _RE_SHORT_CODE.match(parte_cod):
            proyecto_explicito = parte_proj.strip()
            objetivo_limpio = parte_cod.strip()

    # 3. Coincidencia por codigo corto (REQ-042, ADR-0001, QA-003, FLOW-007, UUID...)
    if not candidatos:
        claves = [
            objetivo_limpio.upper(),
            _normalizar_codigo(objetivo_limpio),
            _codigo_sin_ceros(objetivo_limpio),
        ]
        vistos = set()
        for clave in claves:
            for item in idx["by_code"].get(clave, []):
                if item["path"] not in vistos:
                    vistos.add(item["path"])
                    candidatos.append(item)

        if len(candidatos) > 1 and proyecto_explicito:
            proj_l = proyecto_explicito.lower()
            filtrados = [
                c for c in candidatos
                if c["project"].lower() == proj_l or f"/{proj_l}/" in f"/{c['path'].lower()}"
            ]
            if filtrados:
                candidatos = filtrados

    if not candidatos:
        return {
            "ref_target": ref_target,
            "anchor": anchor,
            "resolved": False,
            "status": "not_found",
            "path": None,
            "candidates": [],
        }

    if len(candidatos) > 1:
        return {
            "ref_target": ref_target,
            "anchor": anchor,
            "resolved": False,
            "status": "ambiguous",
            "path": None,
            "candidates": [c["path"] for c in sorted(candidatos, key=lambda x: x["path"])],
        }

    nota = candidatos[0]
    note_status = nota["status"] or "unknown"
    superseded_by = nota.get("superseded_by")
    if note_status == "superseded" or (isinstance(superseded_by, str) and superseded_by.strip()):
        estado_res = "superseded"
    elif note_status in _STALE_NOTE_STATUSES:
        estado_res = note_status
    else:
        estado_res = "ok"

    abs_resolved = nota["abs_path"].resolve()
    vault_name = raiz.name
    rel_no_ext = nota["rel_no_ext"]
    obsidian_file = f"{rel_no_ext}#{anchor}" if anchor else rel_no_ext
    obsidian_uri = f"obsidian://open?vault={quote(vault_name)}&file={quote(obsidian_file)}"
    file_uri = abs_resolved.as_uri()
    web_anchor = f"#vault-note-{_slug_anchor(rel_no_ext)}"

    resultado: Dict[str, Any] = {
        "ref_target": ref_target,
        "anchor": anchor,
        "resolved": True,
        "status": estado_res,
        "path": nota["path"],
        "title": nota["title"],
        "note_type": nota["type"],
        "note_status": note_status,
        "project": nota["project"],
        "superseded_by": superseded_by,
        "stale": estado_res in _STALE_NOTE_STATUSES,
        "links": {
            "relative_path": nota["path"],
            "file_uri": file_uri,
            "obsidian_uri": obsidian_uri,
            "web_anchor": web_anchor,
            "section_anchor": anchor,
        },
    }

    if incluir_contenido:
        try:
            raw = nota["abs_path"].read_text(encoding="utf-8", errors="ignore")
            fm, body = _parse_frontmatter_and_body(raw)
        except OSError:
            fm, body = nota["frontmatter"], ""
        extracto, anchor_found, matched_heading = _extraer_extracto_reglas(
            body, anchor=anchor, max_chars=max_chars
        )
        resultado["rules_excerpt"] = extracto
        resultado["body_markdown"] = body.strip()[:6000]
        resultado["anchor_found"] = anchor_found
        resultado["matched_heading"] = matched_heading
        if fm.get("req_id"):
            resultado["req_id"] = fm.get("req_id")
        if fm.get("norm_refs"):
            resultado["norm_refs"] = fm.get("norm_refs")

    return resultado


def localizar_linea_simbolo(
    content: str,
    symbol: str,
    file_path: Optional[Path] = None,
) -> Optional[Tuple[int, str]]:
    """Devuelve `(linea_insercion_1based, indent)` justo encima del simbolo (y sus decoradores)."""
    lines = content.splitlines()
    objetivo = symbol.strip()
    es_py = file_path is not None and file_path.suffix.lower() == ".py"

    if es_py:
        simbolos = _simbolos_python(content)
        coincidencias = [
            s for s in simbolos
            if s["qualified_name"] == objetivo or s["name"] == objetivo
        ]
        if coincidencias:
            elegido = coincidencias[0]
            linea_1b = elegido["start_line"]
            linea_txt = lines[linea_1b - 1] if 1 <= linea_1b <= len(lines) else ""
            indent = linea_txt[: len(linea_txt) - len(linea_txt.lstrip(" \t"))]
            return linea_1b, indent

    # Fallback multilenguaje O(n) (TS/JS/C#/Java/Go/Rust/PHP/C++/Ruby/SQL):
    # Soporta namespaces (`Facturacion.Impuestos`, `App::Billing`, `App\Billing`),
    # clases (`FacturaService`), calificados (`FacturaService.CalcularIva`) y metodos.
    def _linea_con_atributos(linea_1b: int) -> Tuple[int, str]:
        ins = linea_1b
        while ins > 1:
            prev = lines[ins - 2].strip()
            if prev.startswith("@") or (prev.startswith("[") and prev.endswith("]")):
                ins -= 1
            else:
                break
        base_ln = lines[ins - 1]
        indent = base_ln[: len(base_ln) - len(base_ln.lstrip(" \t"))]
        return ins, indent

    objetivo_simple = objetivo.rsplit(".", 1)[-1].rsplit("::", 1)[-1].rsplit("\\", 1)[-1]
    fallback_line: Optional[int] = None
    clase_actual: Optional[str] = None
    n_lines = len(lines)
    for i, ln in enumerate(lines, 1):
        sig = lines[i] if i < n_lines else None
        decl = extraer_declaracion_linea(ln, siguiente_linea=sig)
        if not decl:
            continue
        sym, kind = decl
        if kind == "class":
            clase_actual = sym
        if sym == objetivo:
            return _linea_con_atributos(i)
        if clase_actual and kind in ("method", "function") and f"{clase_actual}.{sym}" == objetivo:
            return _linea_con_atributos(i)
        if fallback_line is None and sym == objetivo_simple:
            fallback_line = i
    if fallback_line is not None:
        return _linea_con_atributos(fallback_line)
    return None


def insertar_vault_en_simbolo(
    content: str,
    note_ref: str,
    symbol: str,
    style: str,
    title: str = "",
    file_path: Optional[Path] = None,
) -> Tuple[str, str, Optional[int], Optional[str]]:
    """Inserta `@vault:` encima de un simbolo concreto respetando indentacion (idempotente).

    Devuelve `(nuevo_contenido, accion, linea_1based, comentario_insertado)` donde
    `accion` es `"linked"`, `"already_present"` o `"symbol_not_found"`.
    """
    loc = localizar_linea_simbolo(content, symbol, file_path=file_path)
    if loc is None:
        return content, "symbol_not_found", None, None

    insert_line_1b, indent = loc
    note_clean = note_ref.replace("\\", "/").removesuffix(".md").strip()
    tag_title = (title or note_clean.split("/")[-1])[:60]
    template = VAULT_TAG_TEMPLATES.get(style, VAULT_TAG_TEMPLATES["line"])
    comment_body = template.format(note_path=note_clean, title=tag_title)
    comment_line = f"{indent}{comment_body}"

    lines = content.splitlines(keepends=True)
    # Verificar idempotencia en los comentarios contiguos inmediatamente encima del simbolo
    check_idx = insert_line_1b - 2
    while check_idx >= 0:
        prev_txt = lines[check_idx].strip()
        if not prev_txt:
            break
        m = VAULT_REF_ANY_PATTERN.match(lines[check_idx].rstrip("\r\n"))
        if m and m.group(2).strip().lower() == note_clean.lower():
            return content, "already_present", check_idx + 1, lines[check_idx].rstrip("\r\n")
        if _RE_DECORATOR_OR_COMMENT.match(lines[check_idx]):
            check_idx -= 1
            continue
        break

    offset = line_offset(lines, insert_line_1b - 1)
    nuevo = content[:offset] + comment_line + "\n" + content[offset:]
    return nuevo, "linked", insert_line_1b, comment_line


def construir_matriz_rdd(
    vault_root: Path,
    scan_roots: Sequence[Path],
    project: Optional[str] = None,
    indice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye la matriz de trazabilidad RDD: REQ-NNN <-> metodos @vault: <-> tests."""
    idx = indice if indice is not None else construir_indice_notas_vault(vault_root)
    raiz: Path = idx["root"]
    proj_l = project.lower() if project else None

    # 1. Recolectar requerimientos en 14_Requirements/
    reqs: Dict[str, Dict[str, Any]] = {}
    for entry in idx["by_rel"].values():
        if not entry["path"].startswith("14_Requirements/"):
            continue
        if proj_l and entry["project"].lower() != proj_l and f"/{proj_l}/" not in f"/{entry['path'].lower()}":
            continue
        fm = entry["frontmatter"]
        req_id = str(fm.get("req_id") or "").strip().upper()
        if not req_id:
            m = _RE_FILENAME_CODE_PREFIX.match(entry["stem"])
            if m and m.group(1).lower() == "req":
                req_id = _normalizar_codigo(f"REQ-{m.group(2)}")
        if not req_id:
            continue
        req_norm = _normalizar_codigo(req_id)
        declared_code = fm.get("related_code") or []
        if isinstance(declared_code, str):
            declared_code = [c.strip() for c in declared_code.split(",") if c.strip()]
        reqs[req_norm] = {
            "req_id": req_norm,
            "title": entry["title"],
            "status": entry["status"] or "draft",
            "priority": str(fm.get("priority") or ""),
            "project": entry["project"],
            "note": entry["path"],
            "declared_code": list(declared_code),
            "methods": [],
            "tests": [],
        }

    # 2. Enlazar tests en 15_Tests/ que referencian REQ-NNN
    for entry in idx["by_rel"].values():
        if not entry["path"].startswith("15_Tests/"):
            continue
        if proj_l and entry["project"].lower() != proj_l and f"/{proj_l}/" not in f"/{entry['path'].lower()}":
            continue
        fm = entry["frontmatter"]
        found_reqs = set()
        for field in ("related_requirement", "related_requirements", "requirements"):
            val = fm.get(field)
            if isinstance(val, str):
                for m in _RE_REQ_TOKEN.finditer(val):
                    found_reqs.add(_normalizar_codigo(f"REQ-{m.group(1)}"))
            elif isinstance(val, list):
                for item in val:
                    for m in _RE_REQ_TOKEN.finditer(str(item)):
                        found_reqs.add(_normalizar_codigo(f"REQ-{m.group(1)}"))
        try:
            body_txt = entry["abs_path"].read_text(encoding="utf-8", errors="ignore")
        except OSError:
            body_txt = ""
        for m in _RE_REQ_TOKEN.finditer(body_txt):
            found_reqs.add(_normalizar_codigo(f"REQ-{m.group(1)}"))

        for rid in sorted(found_reqs):
            if rid in reqs:
                reqs[rid]["tests"].append(
                    {
                        "note": entry["path"],
                        "title": entry["title"],
                        "test_type": str(fm.get("test_type") or ""),
                    }
                )

    # 3. Escanear codigo fuente para metodos/archivos etiquetados con @vault:
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        iter_files = [scan_root] if scan_root.is_file() else scan_root.rglob("*")
        for src in iter_files:
            if not src.is_file() or src.suffix.lower() not in CODE_EXTS:
                continue
            if any(part in _IGNORED_SOURCE_DIRS for part in src.parts):
                continue
            try:
                content = src.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "@vault:" not in content:
                continue
            refs = extract_all_vault_refs(content, file_path=src)
            for ref in refs:
                res = resolver_referencia_vault(
                    raiz,
                    ref["ref_target"],
                    anchor=ref["anchor"],
                    project=project,
                    indice=idx,
                    incluir_contenido=False,
                )
                if not res["resolved"] or not res["path"]:
                    continue
                nota_path = res["path"]
                for rdata in reqs.values():
                    if rdata["note"] == nota_path:
                        rdata["methods"].append(
                            {
                                "file": str(src),
                                "line": ref["line"],
                                "symbol": ref["symbol"],
                                "scope": ref["scope"],
                                "anchor": ref["anchor"],
                            }
                        )

    # 4. Clasificar estado de cobertura RDD por requerimiento
    items: List[Dict[str, Any]] = []
    with_methods = 0
    with_tests = 0
    full_cov = 0
    uncovered_approved = 0
    for rid in sorted(reqs.keys()):
        item = reqs[rid]
        has_m = bool(item["methods"])
        has_t = bool(item["tests"])
        if has_m:
            with_methods += 1
        if has_t:
            with_tests += 1
        if has_m and has_t:
            state = "verified_full"
            full_cov += 1
        elif has_m:
            state = "implemented_untested"
        elif has_t:
            state = "tested_unlinked"
        else:
            state = "uncovered"
            if item["status"] in ("approved", "implemented", "verified"):
                uncovered_approved += 1
        item["coverage_state"] = state
        items.append(item)

    return {
        "total_requirements": len(items),
        "with_code_methods": with_methods,
        "with_tests": with_tests,
        "full_coverage": full_cov,
        "uncovered_approved": uncovered_approved,
        "requirements": items,
    }


def _sanitizar_json_para_script(payload: Any) -> str:
    """Serializa JSON seguro para incrustar en <script> evitando </script> injection."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def renderizar_visor_html(
    titulo: str,
    archivos: Sequence[Dict[str, Any]],
    resumen: Optional[Dict[str, Any]] = None,
) -> str:
    """Genera un visor web HTML5 autocontenido (offline, 0 dependencias) con tags `@vault:` clicables.

    Cada elemento de `archivos` recibe:
      - `path`: ruta visible del archivo de codigo
      - `content`: texto fuente del archivo
      - `references`: lista de referencias resueltas (con `line`, `raw_ref`, `symbol`, `status`,
        `resolved`, `path`, `title`, `rules_excerpt`, `body_markdown`, `links`, `superseded_by`)
      - `changed_lines` (opcional): conjunto/lista de numeros de linea resaltadas del diff

    Al hacer clic en cualquier etiqueta `@vault: ...` en el navegador, se abre
    el panel lateral con la nota viva del vault, sus reglas, estado de vigencia
    y enlace directo `obsidian://` y `file://`.
    """
    notas_catalogo: Dict[str, Dict[str, Any]] = {}
    bloques_archivos: List[str] = []

    for f_idx, item in enumerate(archivos):
        fpath = str(item.get("path") or f"archivo-{f_idx + 1}")
        content = str(item.get("content") or "")
        refs = list(item.get("references") or [])
        changed = set(item.get("changed_lines") or [])

        refs_por_linea: Dict[int, List[Tuple[str, Dict[str, Any]]]] = {}
        for r_idx, ref in enumerate(refs):
            ref_id = f"ref-{f_idx}-{r_idx}"
            notas_catalogo[ref_id] = {
                "ref_id": ref_id,
                "raw_ref": ref.get("raw_ref") or ref.get("ref_target") or "",
                "symbol": ref.get("symbol"),
                "line": ref.get("line"),
                "resolved": bool(ref.get("resolved")),
                "status": ref.get("status") or "unknown",
                "note_path": ref.get("path"),
                "title": ref.get("title") or ref.get("raw_ref") or "",
                "note_status": ref.get("note_status") or "",
                "superseded_by": ref.get("superseded_by"),
                "anchor": ref.get("anchor"),
                "matched_heading": ref.get("matched_heading"),
                "rules_excerpt": ref.get("rules_excerpt") or "",
                "body_markdown": ref.get("body_markdown") or ref.get("rules_excerpt") or "",
                "links": ref.get("links") or {},
                "candidates": ref.get("candidates") or [],
            }
            ln = int(ref.get("line") or 0)
            if ln > 0:
                refs_por_linea.setdefault(ln, []).append((ref_id, ref))

        lineas_html: List[str] = []
        for idx_ln, texto_ln in enumerate(content.splitlines(), 1):
            cls_ln = "code-line changed" if idx_ln in changed else "code-line"
            escaped = _html.escape(texto_ln)
            if idx_ln in refs_por_linea:
                for ref_id, ref in refs_por_linea[idx_ln]:
                    raw_ref = str(ref.get("raw_ref") or ref.get("ref_target") or "")
                    st = str(ref.get("status") or "unknown")
                    badge_cls = (
                        "vault-chip ok"
                        if st == "ok"
                        else "vault-chip warn"
                        if ref.get("resolved")
                        else "vault-chip err"
                    )
                    chip = (
                        f'<button type="button" class="{badge_cls}" '
                        f'data-ref-id="{_html.escape(ref_id)}" '
                        f'data-vault-ref="{_html.escape(raw_ref)}" '
                        f'title="Abrir nota del vault: {_html.escape(str(ref.get("path") or raw_ref))}">'
                        f"@vault: {_html.escape(raw_ref)}</button>"
                    )
                    patron_esc = _html.escape(f"@vault: {raw_ref}")
                    if patron_esc in escaped:
                        escaped = escaped.replace(patron_esc, chip, 1)
                    else:
                        escaped = f"{escaped} {chip}"
            lineas_html.append(
                f'<div class="{cls_ln}" data-line="{idx_ln}">'
                f'<span class="ln">{idx_ln}</span><span class="src">{escaped}</span></div>'
            )

        bloques_archivos.append(
            f'<section class="file-card">'
            f'<header class="file-hdr"><strong>{_html.escape(fpath)}</strong>'
            f'<span class="meta">{len(refs)} @vault refs</span></header>'
            f'<div class="code-body">{"".join(lineas_html)}</div>'
            f"</section>"
        )

    resumen_html = ""
    if resumen:
        pills = []
        for k, v in resumen.items():
            pills.append(
                f'<span class="pill"><b>{_html.escape(str(k))}:</b> {_html.escape(str(v))}</span>'
            )
        resumen_html = f'<div class="summary-bar">{"".join(pills)}</div>'

    payload_json = _sanitizar_json_para_script(notas_catalogo)
    titulo_esc = _html.escape(titulo)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{titulo_esc}</title>
<style>
  :root {{ --bg:#0d1117; --panel:#161b22; --border:#30363d; --fg:#e6edf3; --muted:#8b949e; --ok:#2ea043; --warn:#d29922; --err:#f85149; --accent:#58a6ff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--fg); display:grid; grid-template-columns:1fr 420px; min-height:100vh; }}
  main {{ padding:20px; overflow:auto; }}
  aside {{ background:var(--panel); border-left:1px solid var(--border); padding:20px; position:sticky; top:0; height:100vh; overflow:auto; }}
  h1 {{ margin:0 0 12px; font-size:1.25rem; }}
  .summary-bar {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }}
  .pill {{ background:var(--panel); border:1px solid var(--border); padding:4px 10px; border-radius:999px; font-size:.82rem; }}
  .file-card {{ border:1px solid var(--border); border-radius:8px; margin-bottom:18px; overflow:hidden; background:#0b0f14; }}
  .file-hdr {{ display:flex; justify-content:space-between; padding:10px 14px; background:var(--panel); border-bottom:1px solid var(--border); font-size:.9rem; }}
  .file-hdr .meta {{ color:var(--muted); }}
  .code-body {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.84rem; line-height:1.5; }}
  .code-line {{ display:grid; grid-template-columns:52px 1fr; padding:0 10px; white-space:pre-wrap; word-break:break-word; }}
  .code-line.changed {{ background:rgba(46,160,67,0.12); }}
  .ln {{ color:var(--muted); user-select:none; text-align:right; padding-right:12px; }}
  .vault-chip {{ display:inline-block; font:inherit; cursor:pointer; padding:1px 8px; border-radius:6px; border:1px solid transparent; font-weight:600; }}
  .vault-chip.ok {{ background:rgba(46,160,67,0.18); color:#7ee787; border-color:var(--ok); }}
  .vault-chip.warn {{ background:rgba(210,153,34,0.2); color:#f2cc60; border-color:var(--warn); }}
  .vault-chip.err {{ background:rgba(248,81,73,0.2); color:#ff7b72; border-color:var(--err); }}
  .vault-chip:hover {{ filter:brightness(1.2); }}
  .note-meta {{ font-size:.82rem; color:var(--muted); margin:8px 0 12px; }}
  .note-links a {{ color:var(--accent); margin-right:12px; font-size:.85rem; text-decoration:none; }}
  .note-links a:hover {{ text-decoration:underline; }}
  .note-body {{ white-space:pre-wrap; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.82rem; background:#0d1117; border:1px solid var(--border); padding:12px; border-radius:6px; margin-top:12px; }}
  .status-tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:.75rem; font-weight:700; text-transform:uppercase; }}
  .status-tag.ok {{ background:var(--ok); color:#fff; }}
  .status-tag.warn {{ background:var(--warn); color:#000; }}
  .status-tag.err {{ background:var(--err); color:#fff; }}
  @media (max-width: 960px) {{ body {{ grid-template-columns:1fr; }} aside {{ position:static; height:auto; border-left:none; border-top:1px solid var(--border); }} }}
</style>
</head>
<body>
<main>
  <h1>{titulo_esc}</h1>
  {resumen_html}
  {"".join(bloques_archivos)}
</main>
<aside id="vault-drawer" aria-live="polite">
  <h2>Nota del Vault</h2>
  <p class="note-meta">Haz clic en cualquier etiqueta <code>@vault:</code> del código para abrir aquí las reglas de negocio, criterios y enlaces directos de esa nota.</p>
</aside>
<script id="vault-refs-data" type="application/json">{payload_json}</script>
<script>
(function() {{
  const data = JSON.parse(document.getElementById("vault-refs-data").textContent || "{{}}");
  const drawer = document.getElementById("vault-drawer");
  function esc(s) {{
    return String(s || "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}}[c]));
  }}
  function renderNote(refId) {{
    const n = data[refId];
    if (!n) return;
    const stCls = n.status === "ok" ? "ok" : (n.resolved ? "warn" : "err");
    const links = n.links || {{}};
    let linksHtml = "";
    if (links.obsidian_uri) linksHtml += `<a href="${{esc(links.obsidian_uri)}}">Abrir en Obsidian</a>`;
    if (links.file_uri) linksHtml += `<a href="${{esc(links.file_uri)}}">Abrir archivo .md</a>`;
    const sup = n.superseded_by ? `<div><strong>Superseded by:</strong> ${{esc(n.superseded_by)}}</div>` : "";
    const sym = n.symbol ? `<div><strong>Símbolo:</strong> <code>${{esc(n.symbol)}}</code> (L${{esc(n.line)}})</div>` : "";
    const body = n.resolved ? (n.rules_excerpt || n.body_markdown || "(sin contenido)") : ("Nota no resuelta (" + n.status + "). " + (n.candidates && n.candidates.length ? "Candidatas: " + n.candidates.join(", ") : ""));
    drawer.innerHTML = `
      <span class="status-tag ${{stCls}}">${{esc(n.status)}}</span>
      <h2>${{esc(n.title || n.raw_ref)}}</h2>
      <div class="note-meta">
        <div><strong>Referencia:</strong> <code>@vault: ${{esc(n.raw_ref)}}</code></div>
        ${{sym}}
        ${{n.note_path ? `<div><strong>Nota:</strong> <code>${{esc(n.note_path)}}</code></div>` : ""}}
        ${{n.note_status ? `<div><strong>Estado nota:</strong> ${{esc(n.note_status)}}</div>` : ""}}
        ${{sup}}
      </div>
      <div class="note-links">${{linksHtml}}</div>
      <div class="note-body">${{esc(body)}}</div>`;
  }}
  document.addEventListener("click", (ev) => {{
    const btn = ev.target.closest(".vault-chip");
    if (!btn) return;
    renderNote(btn.getAttribute("data-ref-id"));
  }});
  const firstKey = Object.keys(data)[0];
  if (firstKey) renderNote(firstKey);
}})();
</script>
</body>
</html>
"""

