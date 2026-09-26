"""Parser canónico de frontmatter — frontera instalable.

Este módulo re-exporta desde scripts/vault_lib (dueño canónico del parsing).
No se reimplementa parsing en adaptadores o módulos de dominio.

Excepciones de dominio (definidas aquí, emitidas por el dueño canónico):
- FrontmatterParseError: frontmatter presente pero no parseable
- FrontmatterMissing: sin bloque delimitado
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from vault_toolkit.loading import import_toolkit_module

_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


def _lib():
    return import_toolkit_module("vault_lib", legacy_scripts=_SCRIPTS)


class FrontmatterParseError(ValueError):
    """El frontmatter está delimitado pero no pudo parsearse."""
    pass


class FrontmatterMissing(ValueError):
    """El documento no tiene bloque frontmatter delimitado."""
    pass


_FRONTBLOCK_RE = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Extrae campos YAML del frontmatter como dict.

    Retorna dict vacío si no hay bloque frontmatter válido.
    Lanza FrontmatterParseError si el delimitador existe pero el YAML no parsea.

    Raises:
        FrontmatterParseError: el delimitador existe pero el YAML no parsea.
    """
    stripped = content.lstrip("\ufeff")
    has_block = _FRONTBLOCK_RE.match(stripped) is not None
    result = _lib().parse_frontmatter(content)
    if result == {} and has_block:
        raise FrontmatterParseError("YAML inválido en frontmatter")
    return result


def parse_frontmatter_with_body(content: str) -> Tuple[Dict[str, Any], str]:
    """Extrae frontmatter y cuerpo de un documento Markdown.

    Returns:
        Tupla (frontmatter_dict, body_str).
        (dict vacío, contenido_original) si no hay frontmatter.

    Raises:
        FrontmatterParseError: el delimitador existe pero el YAML no parsea.
    """
    lib = _lib()
    fm, body = lib.parse_frontmatter_with_body(content)
    if fm == {}:
        stripped = content.lstrip("\ufeff")
        if _FRONTBLOCK_RE.match(stripped) is not None:
            raise FrontmatterParseError("YAML inválido en frontmatter")
    return fm, body


def parse_frontmatter_robust(content: str) -> Tuple[Dict[str, Any], str, bool, Optional[str]]:
    """Versión con Contract 4-tuple para consumidores que necesitan el indicador de parseo.

    Returns:
        (frontmatter, body, parse_ok, error_msg)
        parse_ok=False indica que el frontmatter está presente pero no parseó.
        error_msg describe la causa.
    """
    try:
        fm, body = parse_frontmatter_with_body(content)
        return fm, body, True, None
    except FrontmatterParseError as exc:
        return {}, content, False, str(exc)
    except Exception as exc:
        return {}, content, False, f"error inesperado: {type(exc).__name__}: {exc}"
