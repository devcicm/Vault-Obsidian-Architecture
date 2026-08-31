#!/usr/bin/env python3
"""
Vault Encoding — Módulo de saneamiento de encoding y normalización Unicode.

Este módulo proporciona funciones para:
- Normalización Unicode (NFC/NFD)
- Sanitización de texto generado por IA
- Limpieza de caracteres invisibles
- Manejo de encoding de archivos
- Nombres de archivo cross-platform

Usage:
    from vault_encoding import sanitize_content, normalize_to_nfc, sanitize_filename
"""

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Caracteres de control válidos (solo LF, CR, TAB)
VALID_CONTROL_CHARS = {"\n", "\r", "\t"}

# Mapeo de comillas tipográficas a ASCII
QUOTE_REPLACEMENTS = [
    ("\u201c", '"'),  # "
    ("\u201d", '"'),  # "
    ("\u2018", "'"),  # '
    ("\u2019", "'"),  # '
    ("\u201b", "'"),  # '
    ("\u201f", '"'),  # "
    ("\u00ab", '"'),  # «
    ("\u00bb", '"'),  # »
    ("\u2039", "'"),  # ‹
    ("\u203a", "'"),  # ›
]

# Guiones y espacios Unicode con ancho -> su equivalente ASCII.
# Registro canonico: `normalize_dashes` lo consume. Los de ancho cero no viven
# aqui sino en INVISIBLE_CHARS, que es quien los elimina.
DASH_REPLACEMENTS = [
    ("\u2013", "-", "en-dash"),
    ("\u2014", "--", "em-dash"),
    ("\u2010", "-", "hyphen"),
    ("\u2011", "-", "non-breaking hyphen"),
    ("\u2012", "-", "figure dash"),
    ("\u2009", " ", "thin space"),
    ("\u200a", " ", "hair space"),
    ("\u00a0", " ", "non-breaking space"),
]

# Caracteres invisibles a eliminar. Registro canonico: lo consumen tanto
# `remove_invisible_chars` (los quita) como `detect_issues` (los reporta).
# Tenerlo en un solo sitio es lo que impide que el detector senale un caracter
# que el sanitizador no sabe quitar - que es como estaba: detectaba 18, quitaba 13.
INVISIBLE_CHARS = [
    ("\u200b", "zero-width space"),
    ("\u200c", "zero-width non-joiner"),
    ("\u200d", "zero-width joiner"),
    ("\u200e", "left-to-right mark"),
    ("\u200f", "right-to-left mark"),
    ("\ufeff", "BOM"),
    ("\u00ad", "soft hyphen"),
    ("\u202a", "left-to-right embedding"),
    ("\u202b", "right-to-left embedding"),
    ("\u202c", "pop directional formatting"),
    ("\u202d", "left-to-right override"),
    ("\u202e", "right-to-left override"),
    ("\u2060", "word joiner"),
    ("\u2061", "function application"),
    ("\u2062", "invisible times"),
    ("\u2063", "invisible separator"),
    ("\u2064", "invisible plus"),
]

# Caracteres inválidos para nombres de archivo por SO
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'


def normalize_to_nfc(text: str) -> str:
    """Normaliza texto a forma NFC (compuesta).

    NFC es preferida para consistencia cross-platform.
    Ejemplo: 'é' (U+00E9) se mantiene como un solo carácter.

    Args:
        text: Texto a normalizar

    Returns:
        Texto normalizado a NFC
    """
    if not text:
        return text
    return unicodedata.normalize("NFC", text)


def normalize_to_nfd(text: str) -> str:
    """Normaliza texto a forma NFD (descompuesta).

    Útil para comparación donde se necesita ignorar acentos.
    Ejemplo: 'é' se convierte en 'e' + '´' (dos caracteres).

    Args:
        text: Texto a normalizar

    Returns:
        Texto normalizado a NFD
    """
    if not text:
        return text
    return unicodedata.normalize("NFD", text)


def normalize_quotes(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Convierte comillas tipográficas a ASCII.

    Reemplaza:
    - " " (U+201C/D) → "
    - ' ' (U+2018/9) → '
    - « » (U+00AB/B) → "

    Args:
        text: Texto a sanitizar

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []
    result = text

    for old, new in QUOTE_REPLACEMENTS:
        if old in result:
            count = result.count(old)
            fixes.append(
                {"type": "smart_quotes", "from": old, "to": new, "count": count}
            )
            result = result.replace(old, new)

    return result, fixes


def normalize_dashes(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Convierte guiones Unicode a ASCII.

    Reemplaza:
    - – (en-dash U+2013) → -
    - — (em-dash U+2014) → --
    - ‑ (non-breaking hyphen) → -

    Args:
        text: Texto a sanitizar

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []
    result = text

    for old, new, name in DASH_REPLACEMENTS:
        if old in result:
            count = result.count(old)
            fixes.append(
                {
                    "type": "unicode_dash",
                    "from": old,
                    "to": new,
                    "name": name,
                    "count": count,
                }
            )
            result = result.replace(old, new)

    return result, fixes


def remove_invisible_chars(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Elimina caracteres invisibles problemáticos.

    Elimina:
    - Zero-width spaces (U+200B, U+200C, U+200D)
    - Directional marks (U+200E, U+200F)
    - BOM (U+FEFF)
    - Soft hyphen (U+00AD)

    Args:
        text: Texto a sanitizar

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []
    result = text

    for char, name in INVISIBLE_CHARS:
        if char in result:
            count = result.count(char)
            fixes.append(
                {
                    "type": "invisible_char",
                    "char": repr(char),
                    "name": name,
                    "count": count,
                }
            )
            result = result.replace(char, "")

    return result, fixes


def normalize_newlines(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Normaliza newlines a formato Unix (LF).

    Convierte:
    - CRLF (\r\n) → LF (\n)
    - CR (\r) → LF (\n)

    Args:
        text: Texto a normalizar

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []

    # Primero convertir CRLF a LF
    if "\r\n" in text:
        count = text.count("\r\n")
        fixes.append({"type": "newline", "from": "CRLF", "to": "LF", "count": count})
        text = text.replace("\r\n", "\n")

    # Luego convertir CR aislado a LF
    if "\r" in text:
        count = text.count("\r")
        fixes.append({"type": "newline", "from": "CR", "to": "LF", "count": count})
        text = text.replace("\r", "\n")

    return text, fixes


def remove_control_chars(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Elimina caracteres de control inválidos.

    Mantiene: LF (\n), CR (\r), TAB (\t)
    Elimina: todos los demás caracteres de control (U+0000 a U+001F)

    Args:
        text: Texto a sanitizar

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []
    result = []

    for char in text:
        if char in VALID_CONTROL_CHARS:
            result.append(char)
        elif ord(char) >= 32 or char in "\n\r\t":
            result.append(char)
        else:
            fixes.append(
                {"type": "control_char", "char": repr(char), "code": hex(ord(char))}
            )

    return "".join(result), fixes


def strip_bom(text: str) -> Tuple[str, bool]:
    """Elimina BOM UTF-8 del inicio del texto.

    Args:
        text: Texto a procesar

    Returns:
        Tupla (texto_sin_bom, was_bom_present)
    """
    BOM = "\ufeff"
    if text.startswith(BOM):
        return text[len(BOM) :], True
    return text, False


def sanitize_content(
    text: str, dry_run: bool = False
) -> Tuple[str, List[Dict[str, Any]]]:
    """Pipeline completo de sanitización de contenido.

    Aplica en orden:
    1. Normalización Unicode a NFC
    2. Conversión de comillas tipográficas
    3. Conversión de guiones Unicode
    4. Eliminación de caracteres invisibles
    5. Normalización de newlines
    6. Eliminación de caracteres de control inválidos

    Args:
        text: Texto a sanitizar
        dry_run: Si True, retorna el texto original sin cambios

    Returns:
        Tupla (texto_sanitizado, lista_fixes)
    """
    if not text:
        return text, []

    fixes = []

    if dry_run:
        return text, fixes

    # 1. Normalización NFC
    original = text
    text = normalize_to_nfc(text)
    if text != original:
        fixes.append(
            {"step": "normalize_nfc", "description": "Normalización Unicode a NFC"}
        )

    # 2. Normalizar comillas
    text, quote_fixes = normalize_quotes(text)
    fixes.extend([{**f, "step": "normalize_quotes"} for f in quote_fixes])

    # 3. Normalizar guiones
    text, dash_fixes = normalize_dashes(text)
    fixes.extend([{**f, "step": "normalize_dashes"} for f in dash_fixes])

    # 4. Eliminar caracteres invisibles
    text, invisible_fixes = remove_invisible_chars(text)
    fixes.extend([{**f, "step": "remove_invisible"} for f in invisible_fixes])

    # 5. Normalizar newlines
    text, newline_fixes = normalize_newlines(text)
    fixes.extend([{**f, "step": "normalize_newlines"} for f in newline_fixes])

    # 6. Eliminar caracteres de control
    text, control_fixes = remove_control_chars(text)
    fixes.extend([{**f, "step": "remove_control"} for f in control_fixes])

    return text, fixes


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitiza nombre de archivo para ser válido cross-platform.

    - Elimina caracteres inválidos por SO
    - Trunca si es muy largo
    - Normaliza a NFC
    - Reemplaza espacios con guiones

    Args:
        name: Nombre original
        max_length: Longitud máxima del nombre

    Returns:
        Nombre de archivo seguro
    """
    if not name:
        return "untitled"

    # Normalizar a NFC
    result = normalize_to_nfc(name)

    # Eliminar caracteres invisibles primero
    result, _ = remove_invisible_chars(result)

    # Eliminar caracteres inválidos para文件名
    result = re.sub(INVALID_FILENAME_CHARS, "", result)

    # Reemplazar espacios y guiones bajos con guiones
    result = re.sub(r"[\s_]+", "-", result)

    # Eliminar guiones múltiples
    result = re.sub(r"-+", "-", result)

    # Eliminar guiones al inicio y final
    result = result.strip("-")

    # Truncar si es muy largo
    if len(result) > max_length:
        # Preservar extensión si existe
        if "." in result:
            name_part, ext = result.rsplit(".", 1)
            max_name_len = max_length - len(ext) - 1
            result = name_part[:max_name_len] + "." + ext
        else:
            result = result[:max_length]

    # Si resultado vacío, usar nombre por defecto
    return result or "untitled"


def decode_safely(bytes_content: bytes) -> Tuple[str, str]:
    """Decodifica bytes a string con detección de encoding.

    Intenta:
    1. UTF-8
    2. UTF-8 with BOM (utf-8-sig)
    3. Latin-1 (fallback)

    Args:
        bytes_content: Contenido en bytes

    Returns:
        Tupla (contenido_decodificado, encoding_usado)
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1"]

    for encoding in encodings:
        try:
            content = bytes_content.decode(encoding)
            return content, encoding
        except UnicodeDecodeError:
            continue

    # Fallback final con replacement
    content = bytes_content.decode("utf-8", errors="replace")
    return content, "utf-8-replaced"


def detect_issues(text: str) -> List[Dict[str, Any]]:
    """Detecta problemas de encoding en el texto.

    Args:
        text: Texto a analizar

    Returns:
        Lista de problemas detectados
    """
    if not text:
        return []

    issues = []

    # Detectar comillas tipográficas
    for old, new in QUOTE_REPLACEMENTS:
        if old in text:
            issues.append(
                {
                    "type": "smart_quotes",
                    "char": old,
                    "description": f"Comilla tipográfica {repr(old)}",
                }
            )

    # Detectar guiones Unicode
    dash_chars = {
        "\u2013": "en-dash",
        "\u2014": "em-dash",
        "\u2011": "non-breaking hyphen",
    }
    for char, name in dash_chars.items():
        if char in text:
            issues.append(
                {"type": "unicode_dash", "char": char, "description": f"Guión {name}"}
            )

    # Detectar caracteres invisibles
    for char, _nombre in INVISIBLE_CHARS:
        if char in text:
            issues.append(
                {
                    "type": "invisible_char",
                    "char": repr(char),
                    "description": "Carácter invisible",
                }
            )

    # Detectar BOM
    if text.startswith("\ufeff"):
        issues.append({"type": "bom", "description": "BOM UTF-8 presente"})

    # Detectar newlines mixtos
    has_crlf = "\r\n" in text
    has_cr = "\r" in text and "\r\n" not in text
    if has_crlf or has_cr:
        issues.append(
            {
                "type": "newline_inconsistency",
                "description": "Inconsistencia de newlines",
            }
        )

    # Detectar NFD vs NFC inconsistente
    nfd_text = normalize_to_nfd(text)
    if nfd_text != text:
        # Verificar si hay caracteres combinados
        for i, (c1, c2) in enumerate(zip(text, nfd_text)):
            if c1 != c2:
                issues.append(
                    {
                        "type": "nfd_char",
                        "char": c1,
                        "description": "Carácter en forma NFD detectado",
                    }
                )
                break

    return issues


def log_encoding_fixes(
    fixes: List[Dict[str, Any]], path: Path, tool: str = "encoding_sanitizer"
) -> None:
    """Registra cambios de encoding realizados automáticamente.

    v36: Unified trace file location — writes to 00_System/.tool-trace.json
    (the canonical location managed by vault_errors.log_trace with file_lock
    and dedup window). The previous location VAULT_ROOT/.tool-trace.json
    produced a parallel file that vault_errors.query_trace never read, causing
    observability gaps. We delegate to vault_errors.log_trace which handles
    all concurrency and dedup concerns.
    """
    from datetime import datetime, timezone

    try:
        from vault_errors import log_trace

        entry = {
            "tool": tool,
            "category": "encoding_fix",
            "path": str(path),
            "fixes": fixes,
            "fix_count": len(fixes),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "severity": "info",
            "ok": True,
        }
        log_trace(entry)
    except Exception:
        pass  # AP-37: trace log failure must never block the encoding sanitization itself


# Alias para compatibilidad
normalize_text = normalize_to_nfc
sanitize_text = sanitize_content
clean_filename = sanitize_filename
