"""Parser canónico de frontmatter — frontera instalable.

Este módulo es la implementación de referencia para parsing de frontmatter
dentro del paquete. No depende de scripts/ — es instalable como paquete.

El parser maneja:
- BOM de Windows (strip antes de procesar)
- Delimitadores con espacios opcionales (---, ---  , ---    )
- YAML multilínea con indentación
- RecursionError por anidamiento excesivo (dato externo, no controlable)
- Validación: el YAML parseado debe ser un dict (no lista, no escalar)

Excepciones de dominio:
- FrontmatterParseError: frontmatter presente pero no parseable o no es un dict
- FrontmatterMissing: sin bloque delimitado
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

import yaml


def yaml_scalar(value: Any) -> str:
    """Un escalar YAML seguro para meter tras `clave: ` en un frontmatter.

    **Dueño único** desde v40.34 (AP-57): `vault_lib` y `vault.autoria.frontmatter`
    lo reexportan. Vive aquí porque el escape se decide con el mismo parser que
    lee el frontmatter, y en el núcleo ninguno de los dos consumidores cruza
    una frontera para alcanzarlo.

    Veinticuatro tools construían su frontmatter concatenando f-strings, y ocho
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
    except (yaml.YAMLError, RecursionError):  # AP-61 - ver parse_frontmatter
        pass
    return json.dumps(texto, ensure_ascii=False)


class FrontmatterParseError(ValueError):
    """El frontmatter está delimitado pero no pudo parsearse o no es un dict."""
    pass


class FrontmatterMissing(ValueError):
    """El documento no tiene bloque frontmatter delimitado."""
    pass


_FRONTBLOCK_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def _coerce_dates(obj: Any) -> Any:
    """Convierte datetime/date a string ISO. Idempotente."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _coerce_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_dates(v) for v in obj]
    return obj


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Extrae campos YAML del frontmatter como dict.

    Retorna dict vacío si no hay bloque frontmatter válido.
    Lanza FrontmatterParseError si el delimitador existe pero el YAML
    no parsea o no es un dict.

    Raises:
        FrontmatterParseError: el delimitador existe pero el YAML
            no parsea o el resultado no es un dict.
    """
    stripped = content.lstrip("\ufeff")
    match = _FRONTBLOCK_RE.match(stripped)
    if not match:
        return {}
    try:
        raw_fm = yaml.safe_load(match.group(1))
    except (yaml.YAMLError, RecursionError) as exc:
        raise FrontmatterParseError(f"YAML inválido en frontmatter") from exc
    except ValueError as exc:
        raise FrontmatterParseError(f"valor YAML no convertible: {exc}") from exc

    if raw_fm is None:
        raw_fm = {}
    elif not isinstance(raw_fm, dict):
        raise FrontmatterParseError(
            f"frontmatter no es un dict (es {type(raw_fm).__name__}); "
            f"verificar que el bloque YAML contiene pares clave: valor"
        )

    try:
        return _coerce_dates(raw_fm)
    except RecursionError as exc:
        raise FrontmatterParseError(f"anidamiento excesivo en frontmatter") from exc


def parse_frontmatter_with_body(content: str) -> Tuple[Dict[str, Any], str]:
    """Extrae frontmatter y cuerpo de un documento Markdown.

    Returns:
        Tupla (frontmatter_dict, body_str).
        (dict vacío, contenido_original) si no hay frontmatter.

    Raises:
        FrontmatterParseError: el delimitador existe pero el YAML
            no parsea o el resultado no es un dict.
    """
    stripped = content.lstrip("\ufeff")
    match = _FRONTBLOCK_RE.match(stripped)
    if not match:
        return {}, content
    try:
        raw_fm = yaml.safe_load(match.group(1))
    except (yaml.YAMLError, RecursionError) as exc:
        raise FrontmatterParseError(f"YAML inválido en frontmatter") from exc
    except ValueError as exc:
        raise FrontmatterParseError(f"valor YAML no convertible: {exc}") from exc

    if raw_fm is None:
        raw_fm = {}
    elif not isinstance(raw_fm, dict):
        raise FrontmatterParseError(
            f"frontmatter no es un dict (es {type(raw_fm).__name__}); "
            f"verificar que el bloque YAML contiene pares clave: valor"
        )

    try:
        fm = _coerce_dates(raw_fm)
    except RecursionError as exc:
        raise FrontmatterParseError(f"anidamiento excesivo en frontmatter") from exc
    body = match.group(2)
    return fm, body


def parse_frontmatter_robust(content: str) -> Tuple[Dict[str, Any], str, bool, Optional[str]]:
    """Versión con Contract 4-tuple para consumidores que necesitan el indicador de parseo.

    Returns:
        (frontmatter, body, parse_ok, error_msg)
        parse_ok=False indica que el frontmatter está presente pero no parseó
        o no es un dict. error_msg describe la causa.
    """
    try:
        fm, body = parse_frontmatter_with_body(content)
        return fm, body, True, None
    except FrontmatterParseError as exc:
        return {}, content, False, str(exc)
    except Exception as exc:
        return {}, content, False, f"error inesperado: {type(exc).__name__}: {exc}"
