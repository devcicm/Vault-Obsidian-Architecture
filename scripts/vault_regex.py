#!/usr/bin/env python3
"""
Vault Regex — Módulo de validación y sanitización de patrones regex.

Proporciona funciones para:
- Detección de anomalías en corchetes [[ ]]
- Sanitización de contenido de wiki-links
- Detección de path-anchored links (AP-21)
- Auto-corrección de patrones problemáticos
- Validación de caracteres en links

Usage:
    from vault_regex import (
        detect_bracket_anomalies,
        sanitize_wikilink_content,
        detect_path_anchored,
        fix_nested_brackets,
        is_valid_link_content,
    )
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# CONSTANTS
# ============================================================

WIKILINK_MAX_LEN = 200
WIKILINK_MIN_LEN = 1

# Unicode bracket variants (similar to [ ])
UNICODE_OPEN_BRACKETS = ["〔", "｛", "〖", "﹛", "｟", "❰", "❮"]
UNICODE_CLOSE_BRACKETS = ["〕", "｝", "〗", "﹜", "｠", "❱", "❯"]
UNICODE_BRACKETS = set(UNICODE_OPEN_BRACKETS + UNICODE_CLOSE_BRACKETS)

# ============================================================
# REGEX PATTERNS
# ============================================================

# Anomalías de corchetes - 3 o más
RE_NESTED_OPEN_3 = re.compile(r"\[\[\[+")  # [[[, [[[[, etc
RE_NESTED_CLOSE_3 = re.compile(r"\]\]\]+")  # ]]], ]]]], etc

# Anomalías mixtas (orden invertido)
# Los ejemplos van descritos, no literales. Escritos como `# ][[` el compilador
# emite `FutureWarning: Possible nested set` —lee los corchetes del comentario—
# y en la version de Python que lo convierta en error, este modulo deja de
# importarse. Es el modulo que valida cada wikilink de cada vault: no se rompe
# por un comentario.
RE_MIXED_BRACKETS = re.compile(
    r"""
    (\]\[) |           # cierra-abre
    (\]\[\[) |         # cierra-abre-abre
    (\]\]\[) |         # cierra-cierra-abre
    (\[\[\]) |         # abre-abre-cierra
    (\]\[\]) |         # cierra-abre-cierra
    (\[\]\[) |         # abre-cierra-abre
    (\[\]\])            # abre-cierra-cierra
""",
    re.VERBOSE,
)

# ── El extractor de wikilinks: un dueño, no nueve (AP-50, v40.7) ────────────
#
# Este patrón estaba escrito a mano en nueve módulos —`vault_graph`,
# `vault_graph_fix` (×2), `vault_graph_merge`, `vault_lib` (×2),
# `vault_link_safety`, `vault_move`, `vault_write` y `vault_foreign_check`— y
# la copia traía dos defectos que solo se ven al juntarlas:
#
# 1. **Cuadrático.** La clase `[^\]|]` acepta `[`, así que en una tirada de
#    corchetes el motor arranca en cada posición, consume hasta el final y
#    retrocede. Medido: 2.000 corchetes 94 ms, 8.000 → 1,3 s, 32.000 → 20 s.
#    Excluir `[` de la clase lo deja en 0,4 ms para 32.000, y **además acierta
#    más**: sobre el manifiesto y `04-antipatterns.md`, que hablan de corchetes
#    rotos, la versión vieja inventaba "enlaces" que abarcaban párrafos
#    enteros. Un wikilink no contiene `[`; el que lo parecía estaba roto.
#    Entrada alcanzable: `vault_ingest` acepta material que no escribió el
#    estándar, y todos los extractores lo recorren después.
#
# 2. **`#` divergente.** Ocho copias extraían `Nota#Sección` como destino —un
#    fichero que no existe—; solo `vault_foreign_check`, la tool de la regla 7,
#    resolvía a `Nota`. No es casualidad: es la única que se ejecutó contra
#    vaults ajenos, donde los enlaces a encabezado son sintaxis normal. Hoy no
#    muerde (0 casos en `vault-sandbox`, `/ans` y `/vcloud`), y por eso se
#    conserva **cada variante con su semántica**: la que resuelve el ancla es
#    `RE_WIKILINK_DESTINO`, no se impone al resto en esta tanda.
#: El patrón como cadena, para quien necesita componerlo con un prefijo
#: —`vault_migrate_rollback` lo ancla a una fila de tabla y a una flecha— y de
#: otro modo lo volvería a escribir a mano, que es de donde venían las nueve
#: copias.
PATRON_WIKILINK = r"\[\[([^\]|\[]+)(?:\|[^\]\[]+)?\]\]"
RE_WIKILINK = re.compile(PATRON_WIKILINK)
#: Igual, pero capturando también el alias en el grupo 2.
RE_WIKILINK_CON_ALIAS = re.compile(r"\[\[([^\]|\[]+)(?:\|([^\]\[]+))?\]\]")
#: Resuelve el ancla de encabezado: `[[Nota#Sección]]` → `Nota`.
RE_WIKILINK_DESTINO = re.compile(r"\[\[([^\]|#\[]+)(?:[#|][^\]\[]*)?\]\]")

# Empty links
RE_EMPTY_LINK = re.compile(r"\[\[\s*\]\]")
RE_EMPTY_WITH_SPACES = re.compile(r"\[\[\s+\]\]")

# Path-anchored (AP-21) — solo el segmento target (antes de `|`); un "/" en el alias es válido
RE_PATH_ANCHORED = re.compile(r"\[\[/|\[\[[^\]|]*\/")

# Contenido inválido en wiki-links
RE_INVALID_LINK_CHARS = re.compile(r"[\x00-\x1f<>\"\\|]")
RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Whitespace excesivo dentro de links
RE_EXCESSIVE_WHITESPACE = re.compile(r"\[\[\s{2,}")
RE_TRAILING_WHITESPACE = re.compile(r"\[\s+\]\]")

# Leading/trailing brackets en contenido
RE_LEADING_BRACKET = re.compile(r"^\[+")
RE_TRAILING_BRACKET = re.compile(r"\]+$")

# ------------------------------------------------------------
# Valores tipados — la parte decidible de AP-05
# ------------------------------------------------------------
# AP-05 («el mismo dato con valores distintos en varias notas») es la única
# norma `critical` que estuvo sin detector desde v19, y el motivo estaba
# escrito en su `cobertura_descubierta`: decidir qué es «el mismo dato» sin
# embeddings es un problema abierto.
#
# Lo es en general. NO lo es para un valor **tipado**: una IP, una URL, un
# puerto o un semver no se parecen a otro dato, se comparan con él. Ahí la
# identidad no hay que adivinarla — la da la clave bajo la que está escrito, y
# la divergencia es una desigualdad de cadenas.
#
# Viven aquí y no en `vault_fuente_unica` porque AP-50 dice que un patrón
# tiene un dueño único, y escribir el detector de una norma cometiendo otra
# habría sido empezar torcido.

#: IPv4. Los cuatro octetos se validan aparte (`es_ipv4`): un regex que además
#: acota 0-255 es ilegible y aquí la legibilidad importa más que el rechazo.
RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

#: URL con esquema explícito. Sin esquema no se distingue de una ruta.
RE_URL = re.compile(r"\bhttps?://[^\s\"'<>\]),]+", re.IGNORECASE)

#: Semver, con `v` opcional y prerelease/build ignorados a propósito:
#: `1.2.3` y `1.2.3-rc1` son valores distintos y deben compararse distintos.
RE_SEMVER = re.compile(r"\bv?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b")

#: `clave: valor` al principio de línea o de item de lista. Es el único sitio
#: donde un dato lleva su identidad escrita al lado; en prosa no la lleva, y
#: eso es el límite declarado de la medida, no un caso pendiente.
#:
#: Los espacios se escriben `[^\S\n]` y no `\s` a propósito: `\s` incluye el
#: salto de línea, así que una clave con el valor vacío —lo que deja
#: `strip_code_blocks` al quitar un `` `comando` `` inline— seguía leyendo y se
#: **comía la línea siguiente** como su valor. `Despliegue:` con la orden entre
#: comillas invertidas hacía desaparecer el `host_ip:` de debajo, y la nota
#: quedaba fuera de AP-05 sin que nada lo dijera. Verde por no mirar, y en el
#: caso más común de este toolkit: una nota que cita un comando.
RE_CLAVE_VALOR = re.compile(
    r"^[^\S\n]*(?:[-*][^\S\n]+)?([A-Za-z][\w .\-/]{0,40}?)[^\S\n]*:[^\S\n]*(\S.*?)[^\S\n]*$",
    re.MULTILINE,
)


def es_ipv4(texto: str) -> bool:
    """¿Es una IPv4 con los cuatro octetos en rango?

    `1.2.3.4` sí; `999.1.1.1` no, y tampoco `10.0.0` — que es lo que separa una
    IP de un semver mal escrito o de un número de versión de cuatro partes.
    """
    partes = texto.split(".")
    if len(partes) != 4:
        return False
    return all(p.isdigit() and len(p) <= 3 and 0 <= int(p) <= 255 for p in partes)


def tipo_de_valor(valor: str) -> Optional[str]:
    """Qué clase de dato comparable es este valor, si es alguno.

    Devuelve `"ipv4" | "url" | "semver" | "puerto"`, o `None` cuando el valor
    no es de un tipo que se pueda comparar sin interpretarlo. `None` es la
    respuesta correcta y la más frecuente: una descripción, un estado o un
    título divergen entre notas legítimamente, y medirlos sería el ruido que
    hace que un guard deje de leerse.

    El orden importa. `192.168.1.10` casa también con el regex de semver si se
    prueba antes, así que IPv4 se decide primero y con los octetos validados.
    """
    v = valor.strip().strip("`\"'")
    if not v:
        return None
    if RE_IPV4.fullmatch(v) and es_ipv4(v):
        return "ipv4"
    if RE_URL.fullmatch(v):
        return "url"
    if RE_SEMVER.fullmatch(v):
        return "semver"
    if v.isdigit() and 1 <= int(v) <= 65535 and len(v) >= 2:
        return "puerto"
    return None

# ============================================================
# DETECTION FUNCTIONS
# ============================================================


def detect_bracket_anomalies(text: str) -> List[Dict[str, str]]:
    """Detecta anomalías en secuencias de corchetes.

    Encuentra:
    - 3+ corchetes abiertos seguidos: [[[
    - 3+ corchetes cerrados seguidos: ]]]
    - Secuencias mezcladas: ][, ][[, ]][, [[], ][]
    - Links vacíos: [[]]

    Args:
        text: Texto a analizar

    Returns:
        Lista de anomalías encontradas con tipo, posición y ejemplo
    """
    anomalies = []

    # Strip code blocks para no detectar en ejemplos de código
    clean = re.sub(r"```[\s\S]*?```", "", text)
    clean = re.sub(r"`[^`\n]+`", "", clean)

    # Detectar 3+ opens
    for m in RE_NESTED_OPEN_3.finditer(clean):
        count = len(m.group(0)) - 1  # -1 porque [[ cuenta como 1
        anomalies.append(
            {
                "type": "nested_open",
                "count": count,
                "example": m.group(0),
                "position": m.start(),
            }
        )

    # Detectar 3+ closes
    for m in RE_NESTED_CLOSE_3.finditer(clean):
        count = len(m.group(0)) - 1
        anomalies.append(
            {
                "type": "nested_close",
                "count": count,
                "example": m.group(0),
                "position": m.start(),
            }
        )

    # Detectar secuencias mezcladas
    for m in RE_MIXED_BRACKETS.finditer(clean):
        example = m.group(0)
        anomalies.append(
            {
                "type": "mixed",
                "example": example,
                "position": m.start(),
            }
        )

    # Detectar empty links
    for m in RE_EMPTY_LINK.finditer(clean):
        anomalies.append(
            {
                "type": "empty",
                "example": m.group(0),
                "position": m.start(),
            }
        )

    return anomalies


def detect_path_anchored(text: str) -> List[str]:
    """Detecta path-anchored wiki-links (AP-21).

    Encuentra:
    - [[/note]] - path que empieza con /
    - [[folder/note]] - path con /
    - [[./note]] - path relativo

    Args:
        text: Texto a analizar

    Returns:
        Lista de path-anchored links encontrados
    """
    clean = re.sub(r"```[\s\S]*?```", "", text)
    clean = re.sub(r"`[^`\n]+`", "", clean)

    matches = RE_PATH_ANCHORED.findall(clean)
    return matches


def is_valid_link_content(text: str) -> bool:
    """Valida que el contenido de un wiki-link sea válido.

    Args:
        text: Contenido del link (sin [[ ]])

    Returns:
        True si el contenido es válido
    """
    if not text or not text.strip():
        return False

    # Verificar longitud
    if len(text) > WIKILINK_MAX_LEN:
        return False

    # Verificar caracteres de control
    if RE_CONTROL_CHARS.search(text):
        return False

    # Verificar caracteres inválidos
    if RE_INVALID_LINK_CHARS.search(text):
        return False

    # Verificar que no sea solo whitespace
    if not text.strip():
        return False

    # Verificar que no contenga corchetes en el contenido
    if "[" in text or "]" in text:
        return False

    # Verificar que no contenga corchetes unicode
    for char in text:
        if char in UNICODE_BRACKETS:
            return False

    return True


def validate_wikilink(text: str) -> Tuple[bool, Optional[str]]:
    """Valida un wiki-link completo.

    Args:
        text: Texto a validar (puede incluir [[ ]] o no)

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    # Extraer contenido si tiene [[ ]]
    content = text
    if text.startswith("[[") and text.endswith("]]"):
        content = text[2:-2]
        # Extraer solo el target (antes de |)
        if "|" in content:
            content = content.split("|")[0]

    content = content.strip()

    # Validar longitud
    if len(content) > WIKILINK_MAX_LEN:
        return False, f"Wiki-link exceeds {WIKILINK_MAX_LEN} chars"

    if len(content) < WIKILINK_MIN_LEN:
        return False, "Wiki-link is empty"

    # Validar contenido
    if not is_valid_link_content(content):
        return False, "Wiki-link contains invalid characters"

    return True, None


# ============================================================
# SANITIZATION FUNCTIONS
# ============================================================


def sanitize_wikilink_content(text: str) -> str:
    """Sanitiza el contenido interno de un wiki-link.

    - Elimina espacios extras al inicio/final
    - Colapsa múltiples espacios a uno solo
    - Elimina caracteres de control
    - Normaliza a NFC

    Args:
        text: Contenido del link a sanitizar

    Returns:
        Contenido sanitizado
    """
    if not text:
        return "nota-sin-titulo"

    result = text.strip()

    # Colapsar múltiples espacios
    result = re.sub(r"\s+", " ", result)

    # Eliminar caracteres de control
    result = RE_CONTROL_CHARS.sub("", result)

    # Eliminar corchetes si se infiltraron
    result = result.replace("[", "").replace("]", "")

    # Eliminar pipe si se infiltró
    result = result.replace("|", "")

    # Eliminar caracteres inválidos
    result = RE_INVALID_LINK_CHARS.sub("", result)

    # Normalizar a NFC
    import unicodedata

    result = unicodedata.normalize("NFC", result)

    return result or "nota-sin-titulo"


def fix_nested_brackets(text: str) -> str:
    """Auto-corrección: colapsa corchetes anidados.

    - [[[[ -> [[
    - ]]]] -> ]]
    - [[[ -> [[
    - ]]] -> ]]

    Args:
        text: Texto a corregir

    Returns:
        Texto corregido
    """
    result = text

    # Colapsar 3+ opens a 2 opens [[
    result = RE_NESTED_OPEN_3.sub("[[", result)

    # Colapsar 3+ closes a 2 closes ]]
    result = RE_NESTED_CLOSE_3.sub("]]", result)

    # Corregir ][ a ][ (invertido) - eliminar el close que precede al open
    # ][[[ -> [[[ (primero ]
    result = re.sub(r"\]\[\[", "[[", result)

    # ]][[ -> ]]] (último [ se elimina)
    result = re.sub(r"\]\]\[", "]]", result)

    # [[] -> [[ (] al final se elimina)
    result = re.sub(r"\[\[\]", "[[", result)

    # ]]] -> ]] (3 a 2)
    result = re.sub(r"\]\]\](?!\])", "]]", result)

    return result


def fix_whitespace_in_links(text: str) -> str:
    """Auto-corrección: limpia whitespace excesivo en links.

    - [[  nota  ]] -> [[nota]]
    - [[]] -> NO corregir (esto es un error real)

    Args:
        text: Texto a corregir

    Returns:
        Texto corregido
    """
    result = text

    # NO eliminar empty links - eso es un error que debe rechazarse
    # Solo limpiar whitespace en links no-vacíos

    # Primero, proteger los empty links
    empty_placeholders = []
    for m in RE_EMPTY_LINK.finditer(result):
        placeholder = f"__EMPTY_LINK_{len(empty_placeholders)}__"
        empty_placeholders.append((placeholder, m.group(0)))
        result = result.replace(m.group(0), placeholder)

    # Limpiar whitespace excesivo en links no-vacíos
    # [[  nota  ]] -> [[nota]]
    result = re.sub(r"\[\[\s+", "[[", result)
    result = re.sub(r"\s+\]\]", "]]", result)

    # Colapsar múltiples espacios dentro del link
    result = re.sub(
        r"\[\[([^\]]+)\]\]",
        lambda m: "[[" + re.sub(r"\s+", " ", m.group(1)) + "]]",
        result,
    )

    # Restaurar empty links (para que puedan ser detectados como error)
    for placeholder, original in empty_placeholders:
        result = result.replace(placeholder, original)

    return result


def fix_all_brackets(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Aplica todas las correcciones de corchetes.

    Args:
        text: Texto a corregir

    Returns:
        Tupla (texto_corregido, lista_de_fixes_aplicados)
    """
    fixes = []
    original = text

    # 1. Corregir nested brackets
    text = fix_nested_brackets(text)
    if text != original:
        fixes.append({"type": "nested_brackets", "fixed": True})

    # 2. Corregir whitespace
    text = fix_whitespace_in_links(text)
    if text != original:
        fixes.append({"type": "whitespace", "fixed": True})

    return text, fixes


# ============================================================
# EXTRACTION FUNCTIONS
# ============================================================


def extract_wiki_links_strict(content: str) -> List[str]:
    """Extrae wiki-links con validación estricta.

    Filtra:
    - Links vacíos
    - Links con caracteres inválidos
    - Links que exceden longitud máxima

    Args:
        content: Contenido del archivo

    Returns:
        Lista de links válidos
    """
    # Extraer todos los raw links
    raw_pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
    raw_links = re.findall(raw_pattern, content)

    valid_links = []
    for link in raw_links:
        link = link.strip()

        # Saltar vacíos
        if not link:
            continue

        # Saltar si excede longitud
        if len(link) > WIKILINK_MAX_LEN:
            continue

        # Validar contenido
        if not is_valid_link_content(link):
            continue

        valid_links.append(link)

    return valid_links


# ============================================================
# VALIDATION WRAPPER
# ============================================================


def validate_and_fix(
    text: str,
    allow_path_anchored: bool = False,
    allow_empty: bool = False,
    allow_nested: bool = False,
) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """Valida y auto-corrige texto con problemas de corchetes.

    Args:
        text: Texto a validar
        allow_path_anchored: Si True, permite [[folder/note]]
        allow_empty: Si True, permite [[]]
        allow_nested: Si True, permite [[[, etc

    Returns:
        Tupla (texto_procesado, fixes_aplicados, errores_encontrados)
    """
    fixes = []
    errors = []

    # 1. Detectar path-anchored
    path_anchored = detect_path_anchored(text)
    if path_anchored and not allow_path_anchored:
        errors.append(f"AP-21: path-anchored links detected: {path_anchored}")

    # 2. Detectar anomalías
    anomalies = detect_bracket_anomalies(text)

    # Separar empty de otras anomalías
    empty_links = [a for a in anomalies if a["type"] == "empty"]
    other_anomalies = [a for a in anomalies if a["type"] != "empty"]

    if empty_links and not allow_empty:
        errors.append(f"AP-22: {len(empty_links)} empty wiki-link(s) detected")

    if other_anomalies and not allow_nested:
        examples = [a["example"] for a in other_anomalies[:3]]
        errors.append(f"AP-24: bracket anomalies detected: {examples}")

    # 3. Auto-corrección si hay anomalías
    if other_anomalies:
        original = text
        text, applied_fixes = fix_all_brackets(text)
        fixes.extend(applied_fixes)

        # Verificar si se resolvió
        remaining = detect_bracket_anomalies(text)
        remaining_non_empty = [r for r in remaining if r["type"] != "empty"]

        if remaining_non_empty:
            examples = [r["example"] for r in remaining_non_empty[:3]]
            errors.append(f"AP-24: could not auto-fix all anomalies: {examples}")

    return text, fixes, errors


# ============================================================
# ALIASES FOR COMPATIBILITY
# ============================================================

fix_brackets = fix_nested_brackets
clean_whitespace = fix_whitespace_in_links
validate_link = is_valid_link_content
