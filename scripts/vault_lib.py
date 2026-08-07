#!/usr/bin/env python3
"""
Vault Lib — Biblioteca centralizada de utilidades para tools del vault.

Este módulo proporciona funciones centralizadas para:
- Gestión de tiempo (utcnow)
- Utilidades de texto (strip code blocks, extract wikilinks)
- Utilerías JSON (read/write/update)
- Constantes globales
- Validación de contenido

Usage:
    from vault_lib import utcnow, strip_code_blocks, Config
"""

import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================
# SLUGIFY
# ============================================================


def fold_accents(text: str) -> str:
    """Transliterate accented latin letters to ASCII: 'Índice' -> 'Indice'.

    Descompone en NFKD y descarta las marcas combinantes (categoría Mn). La 'ñ'
    se conserva como 'n' por esta vía; 'ß' y 'ø' no descomponen, así que van en
    la tabla explícita.

    No es cosmético: el que borra los acentos en vez de transliterarlos produce
    nombres ilegibles ('Características' -> 'caracter-sticas') y wikilinks que
    heredan el destrozo. Salió al correr el onboarding contra un proyecto real
    en español — `vault-sandbox/` no podía exhibirlo porque lo genera este
    mismo repo, en inglés (regla 7 de CLAUDE.md, corolario de AP-44).
    """
    explicit = {"ß": "ss", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L"}
    text = "".join(explicit.get(ch, ch) for ch in text)
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def slugify(text: str) -> str:
    """Convert text to URL-safe slug (lowercase, hyphens, no special chars).

    Fuente única del estándar para derivar un nombre de fichero de un título.
    Ningún módulo declara su propia versión: `tests/test_slug_canonico.py` lo
    verifica. Existían 26 implementaciones en dos familias divergentes —una
    conservaba los acentos en el nombre de fichero, la otra los borraba— y
    ambas eran incorrectas por motivos distintos.
    """
    slug = fold_accents(text).lower()
    # `\w` en modo unicode a propósito: tras plegar los acentos, lo que quede
    # fuera de ASCII es un alfabeto sin equivalente (CJK, cirílico) y borrarlo
    # dejaría el slug vacío. Se conserva; lo que se quita es puntuación.
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def slugify_strict(text: str) -> str:
    """Strict slug: no leading/trailing hyphens, no consecutive hyphens."""
    return re.sub(r"-{2,}", "-", slugify(text)).strip("-")


# ============================================================
# CONSTANTES DE CONFIGURACIÓN
# ============================================================


class Config:
    """Constantes globales del vault."""

    # Límites de contenido
    MAX_LINE_LENGTH = 800
    MIN_NOTE_LINES = 3
    MIN_NOTE_WORDS = 10
    MAX_NOTE_LINES_AP23 = 500

    # Días para stale detection
    STALE_DAYS = 30
    STUCK_PATTERN_DAYS = 7
    STALE_PROJECT_DAYS = 14
    DQ_CACHE_MINUTES = 30

    # Paths centralizados
    SEARCH_INDEX = "99_Index/search-index.json"
    QUALITY_INDEX = "00_System/quality-index.json"
    TAG_REGISTRY = "00_System/tag-registry.json"
    HISTORY_DIR = ".history"
    STANDARD_VERSION = "00_System/standard-version.json"

    # Thresholds
    SIMILARITY_RATIO = 0.85
    EMPTY_BULLET_RATIO = 0.5

    # Categorías de salud
    DQ_DIMENSIONS = [
        "completeness",
        "uniqueness",
        "consistency",
        "timeliness",
        "validity",
        "accuracy",
    ]

    CIA_SCOPE = ["confidentiality", "integrity", "availability"]


# ============================================================
# GESTIÓN DE TIEMPO
# ============================================================


def utcnow() -> str:
    """Return current UTC time as ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def canonical_utc(value) -> str:
    """Devuelve un instante en el formato con el que el estándar lo escribe.

    `utcnow()` emite `2026-07-30T07:42:40.000Z`, pero PyYAML lee ese escalar como
    `datetime` y `_coerce_dates` lo devuelve como `2026-07-30T07:42:40+00:00`.
    Los dos son el mismo momento y ISO 8601 válido, así que ningún guard de
    contenido se queja — y aun así el campo cambia de forma cada vez que una nota
    se relee y se reescribe. Un formato que depende de cuántas veces pasó por el
    parser no es un formato: leer y volver a escribir tiene que ser idempotente.
    """
    texto = str(value or "").strip()
    if not texto:
        return ""
    if texto.endswith("Z") and "." in texto[10:]:
        return texto  # ya es la forma canónica
    candidato = texto[:-1] + "+00:00" if texto.endswith("Z") else texto
    try:
        dt = datetime.fromisoformat(candidato)
    except ValueError:
        return texto  # no se reconoce: se conserva tal cual, no se inventa
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def utcnow_compact() -> str:
    """Return UTC as compact string: YYYYMMDD-HHMMSS."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def utcnow_filename() -> str:
    """Return UTC as filename-safe string: YYYY-MM-DD-HHMMSS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")


def utcnow_date() -> str:
    """Return UTC date only: YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utcnow_iso() -> str:
    """Return UTC as full ISO 8601 with timezone."""
    return datetime.now(timezone.utc).isoformat()[:19] + "Z"


# ============================================================
# FRONTMATTER UTILITIES
# ============================================================


def _coerce_dates(obj: Any) -> Any:
    """Recursively convert datetime/date values to ISO strings (v38).

    PyYAML's safe_load auto-parses ISO date/datetime scalars into datetime
    objects. Downstream tools then subscript them (`x[...]`) or JSON-dump them,
    raising TypeError ('datetime is not subscriptable' / 'not JSON
    serializable'). Coercing to ISO strings at the frontmatter boundary makes
    every tool tolerant regardless of how a note's dates were written — no data
    migration required. Idempotent; leaves non-date values untouched.
    """
    if isinstance(obj, datetime) or isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _coerce_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_dates(v) for v in obj]
    return obj


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Extract frontmatter YAML fields as a dict from markdown content.

    Supports multiline values (indented continuation). Returns empty dict
    if no valid frontmatter block is found.
    """
    import yaml  # optional dependency

    # Notas editadas con herramientas Windows pueden llegar con BOM (﻿);
    # sin esto el frontmatter completo se pierde silenciosamente.
    content = content.lstrip("﻿")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return {}
    try:
        return _coerce_dates(yaml.safe_load(match.group(1)) or {})
    except yaml.YAMLError:
        return {}


def parse_frontmatter_with_body(content: str) -> Tuple[Dict[str, Any], str]:
    """Extract frontmatter dict and body string from markdown content.

    Returns ({}, content) if no frontmatter block is found.
    """
    import yaml

    content = content.lstrip("﻿")  # ver parse_frontmatter — BOM de Windows
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        fm = _coerce_dates(yaml.safe_load(match.group(1)) or {})
        return fm, match.group(2)
    except yaml.YAMLError:
        return {}, content


def yaml_scalar(value: Any) -> str:
    """Un escalar YAML seguro para meter tras `clave: ` en un frontmatter.

    Veinticuatro tools construyen su frontmatter concatenando f-strings, y ocho
    de ellas se acordaban de pasar el título por `json.dumps`. Las otras
    dieciséis producían YAML inválido en cuanto el valor llevaba `: ` —
    `title: Overview: demo` no es un mapeo— o empezaba por un carácter que YAML
    reserva (`%`, `#`, `*`, `&`). El fichero se escribía sin error y la nota
    perdía **todo** el frontmatter al leerse: sin id, sin tags, sin tipo.

    No cita por si acaso: cita solo si hace falta. El criterio es el del
    consumidor (AP-44) — se comprueba que el parser real devuelva exactamente
    el mismo texto, y solo si no, se cita. Así lo que hoy se escribe sin
    comillas se sigue escribiendo igual, byte a byte.
    """
    import yaml

    # Una lista o un dict ya viajan como JSON —que es YAML de flujo válido— y
    # así es como se escriben hoy `tags:` y `norm_refs:`. Compararlos como
    # texto los citaría, convirtiendo una lista en una cadena.
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return json.dumps(value)

    texto = str(value)
    try:
        vuelta = yaml.safe_load(f"k: {texto}")
        if isinstance(vuelta, dict) and vuelta.get("k") == texto:
            return texto
    except yaml.YAMLError:
        pass
    return json.dumps(texto, ensure_ascii=False)


def serialize_frontmatter(frontmatter: Dict[str, Any]) -> str:
    """Serialize a dict to YAML frontmatter block (including --- delimiters).

    Returns '' if the dict is empty.
    """
    if not frontmatter:
        return ""
    import yaml

    lines = [
        "---",
        yaml.dump(_coerce_dates(frontmatter), default_flow_style=False, allow_unicode=True).strip(),
        "---",
    ]
    return "\n".join(lines) + "\n"


def read_frontmatter(path: Path) -> Dict[str, Any]:
    """Read file at path and return its frontmatter as a dict."""
    import yaml

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_frontmatter(content)


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================


def strip_code_blocks(content: str) -> str:
    """Remove ``` blocks and `inline` code from content."""
    clean = re.sub(r"```[\s\S]*?```", "", content)
    clean = re.sub(r"`[^`\n]+`", "", clean)
    return clean


def extract_wikilinks(content: str) -> List[str]:
    """Extract [[wiki-links]] from content. Returns list of link targets."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def extract_wikilinks_with_context(content: str) -> List[Tuple[str, int, str]]:
    """Extract wiki-links with line number and surrounding context.

    Returns:
        List of (link_target, line_number, line_content)
    """
    results = []
    for i, line in enumerate(content.split("\n"), 1):
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", line)
        for link in links:
            results.append((link, i, line.strip()))
    return results


def normalize_path(path: str) -> str:
    """Normalize path separators for cross-platform consistency."""
    return path.replace("\\", "/")


def truncate_text(text: str, max_len: int = 200) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def is_empty_line(line: str) -> bool:
    """Check if line is empty or just whitespace."""
    return not line.strip()


def is_bullet_line(line: str) -> bool:
    """Check if line is a bullet point."""
    return bool(re.match(r"^\s*[-*+]\s+", line))


# ============================================================
# UTILIDADES JSON
# ============================================================


def read_json(path: Path) -> Dict[str, Any]:
    """Read and parse JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Dict[str, Any], indent: int = 2) -> None:
    """Write JSON to file with proper formatting."""
    path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8"
    )


def update_json(path: Path, updater: Callable[[Dict], Dict]) -> Dict[str, Any]:
    """Read JSON, apply updater function, write back.

    Args:
        path: Path to JSON file
        updater: Function that takes dict and returns modified dict

    Returns:
        Updated dict
    """
    data = read_json(path)
    updated = updater(data)
    write_json(path, updated)
    return updated


def merge_json(path: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge updates into existing JSON file."""

    def merger(existing: Dict) -> Dict:
        result = existing.copy()
        result.update(updates)
        return result

    return update_json(path, merger)


# ============================================================
# UTILIDADES DE VALIDACIÓN
# ============================================================


def count_real_lines(content: str) -> List[str]:
    """Extract non-empty, non-TODO, non-heading lines."""
    return [
        l
        for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]


def count_words(real_lines: List[str]) -> int:
    """Count meaningful words from lines, stripping markdown markers."""
    words: List[str] = []
    for line in real_lines:
        cleaned = re.sub(r"^[#\-\*\s|>]+", "", line)
        for tok in cleaned.split():
            tok = tok.strip("`*~_[]()#").strip(".,;:!?")
            if tok and len(tok) > 1:
                words.append(tok)
    return len(words)


def validate_content_basic(content: str) -> Tuple[bool, str]:
    """Basic content validation.

    Returns:
        (is_valid, reason_if_invalid)
    """
    real_lines = count_real_lines(content)

    if len(real_lines) < Config.MIN_NOTE_LINES:
        return (
            False,
            f"only {len(real_lines)} real line(s) (need ≥{Config.MIN_NOTE_LINES})",
        )

    word_count = count_words(real_lines)
    if word_count < Config.MIN_NOTE_WORDS:
        return False, f"only {word_count} real word(s) (need ≥{Config.MIN_NOTE_WORDS})"

    if any(len(l) > Config.MAX_LINE_LENGTH for l in real_lines):
        return (
            False,
            f"line longer than {Config.MAX_LINE_LENGTH} chars (minified blob?)",
        )

    return True, ""


# ============================================================
# UTILIDADES DE FORMATO
# ============================================================


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts


# ============================================================
# UTILIDADES DE RUTAS
# ============================================================


def get_vault_path(name: str) -> Path:
    """Get common vault paths by name.

    Args:
        name: One of: search_index, quality_index, tag_registry, history, standard_version
    """
    from vault_io import get_vault_root

    paths = {
        "search_index": get_vault_root() / Config.SEARCH_INDEX,
        "quality_index": get_vault_root() / Config.QUALITY_INDEX,
        "tag_registry": get_vault_root() / Config.TAG_REGISTRY,
        "history": get_vault_root() / Config.HISTORY_DIR,
        "standard_version": get_vault_root() / Config.STANDARD_VERSION,
    }
    if name not in paths:
        raise ValueError(f"Unknown vault path: {name}")
    return paths[name]


# ============================================================
# UTILIDADES DE DEBUG
# ============================================================


def dump_structure(obj: Any, max_depth: int = 3, _depth: int = 0) -> str:
    """Dump object structure for debugging."""
    if _depth >= max_depth:
        return "..."

    if isinstance(obj, dict):
        lines = ["{"]
        for k, v in list(obj.items())[:5]:
            lines.append(f"  {k}: {dump_structure(v, max_depth, _depth + 1)}")
        if len(obj) > 5:
            lines.append(f"  ... ({len(obj) - 5} more)")
        lines.append("}")
        return "\n".join(lines)

    elif isinstance(obj, list):
        if len(obj) > 5:
            return f"[{', '.join(str(x) for x in obj[:3])}, ... ({len(obj)} items)]"
        return str(obj)

    else:
        return str(obj)
