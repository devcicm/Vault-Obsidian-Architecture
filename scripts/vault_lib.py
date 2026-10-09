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

from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)
from vault.kernel.regex import strip_code_blocks as _strip_code_blocks
strip_code_blocks = _strip_code_blocks
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
    mismo repo, en inglés (regla 7 de AGENTS.md, corolario de AP-44).
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


def clave_de_nombre(nombre: Any) -> str:
    """Clave de identidad por nombre de nota (respaldo de vault.kernel.normalizacion)."""
    texto = fold_accents(str(nombre)).lower().strip().removesuffix(".md")
    for separador in ("-", "_", " ", "."):
        texto = texto.replace(separador, "")
    return texto


# Dueño desde v40.35: vault.kernel.normalizacion (frontera instalable), que además
# separa la clave de ruta de la de equivalencia. Las tres definiciones de arriba
# quedan como respaldo para cuando `vault` no es importable, igual que
# parse_frontmatter; tests/test_slug_canonico.py verifica que dan lo mismo.
try:
    from vault.kernel.normalizacion import (  # noqa: F811
        fold_accents, slugify, slugify_strict, clave_de_nombre,
    )
except ImportError:
    pass


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

    Returns empty dict if no valid frontmatter block is found or if parsing fails.
    """
    # Delegación completa en vault.kernel.frontmatter_parsing (frontera instalable).
    # vault.kernel captura ValueError/yaml.YAMLError/RecursionError y los expone
    # como FrontmatterParseError. Esta fachada los convierte en {} por
    # compatibilidad backward. El fallback local solo se activa si vault.kernel
    # no está disponible (ImportError).
    try:
        from vault.kernel.frontmatter_parsing import (
            parse_frontmatter as _parse, FrontmatterParseError,
        )
        return _parse(content)
    except ImportError:
        pass
    except FrontmatterParseError:
        return {}
    import yaml as _yaml
    content = content.lstrip("﻿")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return {}
    try:
        raw = _yaml.safe_load(match.group(1))
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            return {}
        return _coerce_dates(raw)
    except (_yaml.YAMLError, RecursionError, ValueError):
        return {}


def parse_frontmatter_with_body(content: str) -> Tuple[Dict[str, Any], str]:
    """Extract frontmatter dict and body string from markdown content.

    Returns ({}, content) if no frontmatter block is found or if parsing fails.
    """
    # Delegación — ver parse_frontmatter. AP-61.
    try:
        from vault.kernel.frontmatter_parsing import (
            parse_frontmatter_with_body as _parse, FrontmatterParseError,
        )
        return _parse(content)
    except ImportError:
        pass
    except FrontmatterParseError:
        return {}, content
    import yaml as _yaml
    content = content.lstrip("﻿")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        raw = _yaml.safe_load(match.group(1))
        if raw is None:
            return {}, match.group(2)
        if not isinstance(raw, dict):
            return {}, match.group(2)
        fm = _coerce_dates(raw)
        return fm, match.group(2)
    except (_yaml.YAMLError, RecursionError, ValueError):
        return {}, content


# superseded_by: vault.kernel.frontmatter_parsing.yaml_scalar (v40.34, AP-57).
# El cuerpo era idéntico al de `vault.autoria.frontmatter`: dos dueños del mismo
# criterio de escapado, que es como empezó la divergencia que esa función
# existe para cerrar. Se conserva el nombre: lo importan veinte tools.
from vault.kernel.frontmatter_parsing import yaml_scalar  # noqa: E402,F401
# AP-56 (v40.34): la línea `clave: valor` montada a mano pasa por aquí.
from vault.kernel.frontmatter_parsing import valor_de_frontmatter  # noqa: E402,F401
# AP-57 (2026-10-01): dónde acaba el bloque lo decide el kernel, por líneas.
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402,F401
# AP-44 (2026-10-08): leer un campo suelto también lo decide el kernel (deuda #5).
from vault.kernel.frontmatter_parsing import (  # noqa: E402,F401
    cargar_bloque_tolerante, campos_de_texto,
)


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

    # AP-61: `read_text` declara OSError, pero lo que lanza una nota guardada
    # en ANSI/Latin-1 —habitual en Windows— es UnicodeDecodeError (ValueError).
    # Sin nombrarla, una sola nota así tumbaba `vault_audit` entero con
    # UNEXPECTED_ERROR. Quien necesite distinguir ilegible de vacía lee la nota
    # con su propio registro de degradación (vault_audit._leer_nota).
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return parse_frontmatter(content)


# ============================================================
# UTILIDADES DE TEXTO
# ============================================================


def extract_wikilinks(content: str) -> List[str]:
    """Extract [[wiki-links]] from content. Returns list of link targets."""
    return RE_WIKILINK.findall(content)


def extract_wikilinks_with_context(content: str) -> List[Tuple[str, int, str]]:
    """Extract wiki-links with line number and surrounding context.

    Returns:
        List of (link_target, line_number, line_content)
    """
    results = []
    for i, line in enumerate(content.split("\n"), 1):
        links = RE_WIKILINK.findall(line)
        for link in links:
            results.append((link, i, line.strip()))
    return results


def resolver_destino_wikilink(bruto: str, desde: "Path | None" = None) -> str:
    """Cómo se busca el destino de un wikilink, como lo buscaría Obsidian.

    **Dueño canónico del criterio (AP-57).** Vivía privado en
    `vault_foreign_check._resolver`, que es AP-57 esperando a repetirse: el día
    que una segunda tool necesite resolver un destino, o lo importa de aquí o
    escribe la quinta copia del mismo `if`.

    Se quitan el alias de visualización (`|`) y el ancla (`#`), que no son
    parte del destino, y una ruta relativa se resuelve contra la carpeta de la
    nota que enlaza — `[[../containers/ct220]]` desde `09_Infrastructure/db/`
    apunta a `09_Infrastructure/containers/ct220`, no a un fichero llamado
    `..`. Sin `desde`, una ruta relativa no se puede resolver y se devuelve
    normalizada: no saber no es lo mismo que resolver a la raíz.
    """
    crudo = bruto.split("|")[0].split("#")[0].strip().replace("\\", "/")
    crudo = crudo.removesuffix(".md")
    if not crudo:
        return ""
    if crudo.startswith("./") or crudo.startswith("../"):
        if desde is None:
            return crudo.strip("/").lower()
        partes: List[str] = list(desde.parent.parts)
        for tramo in crudo.split("/"):
            if tramo == "..":
                if partes:
                    partes.pop()
            elif tramo not in (".", ""):
                partes.append(tramo)
        return "/".join(partes).lower()
    return crudo.strip("/").lower()


def indice_de_destinos(relativas, aliases=None) -> set:
    """Todo lo que resuelve en un vault: sufijos de ruta y `aliases:`.

    **Dueño canónico del criterio (AP-57).** Obsidian resuelve por **nombre de
    fichero** y por `aliases:`; `title:` no entra, porque no lo mira.

    Y un destino con carpeta no se resuelve tirando la carpeta: la ruta escrita
    tiene que casar como **sufijo** de la del fichero, así que
    `[[containers/ct105]]` NO lo resuelve un `ct105.md` que viva en otra
    carpeta. Comparar solo el basename daba por bueno lo que el consumidor
    pinta roto —13 de 16 en el vault de control—, y ese es el peor sentido del
    error: la medida sale verde.

    `relativas` son rutas relativas a la raíz del vault (`Path` o `str`).
    """
    return set(indice_de_nombres(relativas, {"": aliases or []}))


def indice_de_nombres(relativas, aliases_por_ruta=None) -> Dict[str, List[str]]:
    """Cada destino que resuelve en el vault → **todas** las notas que lo resuelven.

    El mismo criterio que `indice_de_destinos` —sufijos de ruta y `aliases:`,
    nunca `title:`—, pero sin tirar la información que decide si un nombre es
    una identidad: cuántas notas responden a él. Un mapa destino → ruta con
    `if clave not in mapa` se quedaba con la que el recorrido del disco diera
    primero y escondía a la otra (AP-17). Las listas salen ordenadas, así que
    el resultado no depende de ese recorrido.

    `aliases_por_ruta` mapea ruta relativa → lista de alias de esa nota.
    """
    indice: Dict[str, set] = {}
    for r in relativas:
        rel = str(r).replace("\\", "/")
        partes = Path(rel).with_suffix("").parts
        for i in range(len(partes)):
            indice.setdefault("/".join(partes[i:]).lower(), set()).add(rel)
    for rel, aliases in (aliases_por_ruta or {}).items():
        for a in aliases or []:
            if isinstance(a, str) and a.strip():
                indice.setdefault(a.strip().lower(), set()).add(str(rel).replace("\\", "/"))
    return {destino: sorted(rutas) for destino, rutas in indice.items()}


def resolver_wikilink(
    bruto: str, desde: "Path | None", indice: Dict[str, List[str]]
) -> Tuple[str, List[str]]:
    """`(ruta, candidatos)`: la nota del enlace si es una sola, y quién responde.

    Con un candidato, `ruta` es ese candidato. Con dos o más el enlace es
    **ambiguo** y `ruta` sale vacía: elegir uno sería inventar la identidad que
    el vault no fija, y la carpeta en el enlace (`[[09_Infra/overview]]`) es lo
    que la fija. Sin candidatos, el enlace está roto.
    """
    candidatos = indice.get(resolver_destino_wikilink(bruto, desde), [])
    return (candidatos[0] if len(candidatos) == 1 else "", list(candidatos))



def resolver_sustitucion(
    valor: Any, desde: "Path | None", indice: Dict[str, List[str]]
) -> Tuple[str, List[str]]:
    """`(ruta, candidatos)` del `superseded_by:` de una nota, como un wikilink.

    **Dueño canónico del criterio (AP-57).** Lo leen quien escribe la
    anotación (`vault_supersede`) y quien la salda (`vault_audit`, AP-17): si
    cada uno la leyera a su manera, la tool escribiría una decisión que el audit
    no ve. Acepta `[[destino]]` y el destino desnudo; resuelve con
    `resolver_wikilink`, así que un `title:` no resuelve (AP-44) y un destino
    ambiguo sale sin ruta.
    """
    if not isinstance(valor, str) or not valor.strip():
        return "", []
    bruto = valor.strip()
    if bruto.startswith("[[") and bruto.endswith("]]"):
        bruto = bruto[2:-2]
    return resolver_wikilink(bruto, desde, indice)


def ruta_necesaria(bruto: str, desde: "Path | None", indice: Dict[str, List[str]]) -> bool:
    """AP-21 precisado: ¿la carpeta de `[[carpeta/nota]]` fija una identidad?

    **Dueño canónico del criterio (AP-57).** Hasta v40.34 AP-21 prohibía toda
    ruta en un enlace alegando que Obsidian solo resuelve por nombre. No es
    así: Obsidian resuelve el sufijo de ruta y, con su formato por defecto
    («ruta más corta posible»), escribe él mismo `[[demo/overview]]` cuando
    `overview` se repite. Prohibirlo dejaba un solo enlace posible para dos
    notas del mismo nombre — `[[overview]]`, que es ambiguo.

    La carpeta es legítima solo si hace falta: el enlace resuelve a **una**
    nota y el nombre solo resuelve a **varias**. Una ruta que no resuelve
    (los 160 enlaces rotos de ANS que originaron AP-21) o que sobra porque el
    nombre ya es único sigue siendo AP-21.
    """
    destino = resolver_destino_wikilink(bruto, desde)
    if "/" not in destino:
        return False
    ruta, _ = resolver_wikilink(bruto, desde, indice)
    return bool(ruta) and len(indice.get(destino.rsplit("/", 1)[-1], [])) >= 2


def destino_mas_corto(relativa: str, indice: Dict[str, List[str]]) -> str:
    """El destino más corto que resuelve a `relativa` y a ninguna otra nota.

    Es el formato «ruta más corta posible» de Obsidian: el nombre si es único,
    y si no, tantas carpetas como hagan falta. Con eso un índice nunca escribe
    un enlace ambiguo, y tampoco una ruta que `ruta_necesaria` rechazaría.
    """
    rel = str(relativa).replace("\\", "/")
    partes = Path(rel).with_suffix("").parts
    for i in range(len(partes) - 1, -1, -1):
        destino = "/".join(partes[i:])
        if indice.get(destino.lower(), []) == [rel]:
            return destino
    # Una nota que el índice no conoce no tiene identidad que fijar: se enlaza
    # por nombre, como antes de v40.35, y no por una ruta que nadie verificó.
    return partes[-1]


def inventario_de_nombres(
    raiz: Path, es_instantanea: Callable[[Path], bool]
) -> Tuple[List[Path], Dict[str, List[str]]]:
    """Notas del vault (rutas relativas) y sus `aliases:`, sin instantáneas.

    Es la entrada de `indice_de_nombres` para quien mide identidad sobre el
    vault entero —el write path (SP-02, AP-21) y los índices—: si cada uno
    hiciera su recorrido, uno vería una nota que el otro no y la misma ruta
    saldría única para el índice y ambigua para el guard. `es_instantanea` se
    inyecta porque su dueño es `vault_io.is_snapshot_path` y este módulo no
    depende de `vault_io`.
    """
    import yaml

    relativas: List[Path] = []
    alias_por_ruta: Dict[str, List[str]] = {}
    for p in Path(raiz).rglob("*.md"):
        rel = p.relative_to(raiz)
        if es_instantanea(rel):
            continue
        relativas.append(rel)
        try:
            fm = read_frontmatter(p)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            # Un frontmatter que no se lee no aporta aliases, pero el fichero
            # sigue siendo un destino válido por su ruta: ya está en
            # `relativas`. Las tres concretas y no `Exception`, que convertiría
            # cualquier fallo propio en «esta nota no tiene aliases» (AP-51).
            continue
        alias_por_ruta[rel.as_posix()] = [
            a for a in (fm or {}).get("aliases") or [] if isinstance(a, str)
        ]
    return relativas, alias_por_ruta


def colisiones_de_nombre(relativas) -> List[Dict[str, Any]]:
    """Grupos de notas cuyo nombre colapsa a la misma `clave_de_nombre` (AP-17).

    Es la identidad, no la resolución: `Mi Proyecto.md` y `mi-proyecto.md`
    son dos enlaces distintos para Obsidian, pero el mismo nombre para quien
    lee el vault, y cualquier tool que identifique por nombre los confunde.
    """
    grupos: Dict[str, List[str]] = {}
    for r in relativas:
        rel = str(r).replace("\\", "/")
        grupos.setdefault(clave_de_nombre(Path(rel).stem), []).append(rel)
    return [
        {"clave": clave, "paths": sorted(rutas)}
        for clave, rutas in sorted(grupos.items())
        if len(rutas) > 1
    ]


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
    # El dueño del puerto es `vault_raiz` (hoja). Pedírselo a `vault_io` cerraba
    # el ciclo vault_lib <-> vault_io por un solo nombre (AP-58).
    from vault_raiz import get_vault_root

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
