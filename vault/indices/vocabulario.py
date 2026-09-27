"""Lectura estable del vocabulario de etiquetas del runtime (AP-39).

El registro y su bitácora pertenecen a Índices. Esta hoja sólo normaliza y lee
esos artefactos; ``vault_tags`` conserva las decisiones de CLI y las escrituras.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List

from ..kernel.normalizacion import plegar_diacriticos_latinos
from .repositorio import RepositorioIndices

_TAG_SEPARADORES = re.compile(r"[\s_.:/\\\\]+")
#: Letras y dígitos de cualquier alfabeto. Hasta v40.34 era ``[^a-z0-9-]`` y una
#: etiqueta en japonés o cirílico salía vacía (``"日本語"`` → ``""``).
_TAG_INVALIDOS = re.compile(r"[^\w-]+")


def normalizar_etiqueta(raw: str) -> str:
    """Forma estable: minúsculas, sin acentos latinos y con guiones.

    NFKC primero para que ``"ﬁle"`` sea ``"file"`` y ``"Ｍi"`` sea ``"mi"`` (antes
    salían ``"le"`` e ``"i"``); los diacríticos se pliegan solo sobre base latina,
    así ``"Straße"`` → ``"strasse"`` sin convertir ``"ブログ"`` en ``"フロク"``.
    """
    texto = unicodedata.normalize("NFKC", str(raw or "")).casefold().strip()
    texto = plegar_diacriticos_latinos(texto)
    texto = _TAG_SEPARADORES.sub("-", texto)
    texto = _TAG_INVALIDOS.sub("-", texto)
    return re.sub(r"-{2,}", "-", texto).strip("-")


def singularizar_etiqueta(tag: str) -> str:
    """Plural inequívoco inglés/castellano a singular."""
    if len(tag) > 4 and tag.endswith("es") and not tag.endswith(("ses", "ees")):
        return tag[:-2]
    if len(tag) > 3 and tag.endswith("s") and not tag.endswith(("ss", "us", "is")):
        return tag[:-1]
    return tag


def etiquetas_canonicas(repo: RepositorioIndices) -> List[str]:
    """Tags canónicos, admitiendo el formato de registro histórico."""
    try:
        registro = json.loads(repo.registro_etiquetas.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    canonicos = registro.get("canonical_tags")
    if isinstance(canonicos, dict):
        planos: List[str] = []
        for valores in canonicos.values():
            if isinstance(valores, list):
                planos.extend(str(v) for v in valores)
        return planos
    legacy = registro.get("tags")
    return sorted(legacy) if isinstance(legacy, dict) else []


def cargar_bitacora(repo: RepositorioIndices) -> Dict[str, Any]:
    """Bitácora AP-39; ausente o ilegible equivale a una vacía."""
    try:
        datos = json.loads(repo.bitacora_etiquetas.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": "v1.0", "entries": []}
    return datos if isinstance(datos, dict) else {"version": "v1.0", "entries": []}
