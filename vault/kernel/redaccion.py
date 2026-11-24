"""vault.kernel.redaccion — contrato ejecutable de formas documentales, evidencia y citas APA.

Hoja pura del núcleo (solo stdlib). Define en un único sitio (AP-57):
- Las 7 formas documentales (`FORMAS_DE_DOCUMENTO`): `resumen`, `sintesis`, `informe`,
  `reporte`, `decision`, `auditoria`, `referencia`.
- Los 5 niveles epistémicos (`NIVELES_EPISTEMICOS`): `observado`, `inferencia`,
  `propuesta`, `decision`, `desconocido`.
- `evaluar_forma(texto, forma)`: evaluación determinista no destructiva de secciones
  recomendadas, marcadores epistémicos y presencia de evidencia (sin mutar ni inventar).
- `formatear_cita_apa(...)` y `auditar_cita_bibliografica(fm)`: citas APA 7ª edición
  que jamás fabrican autor ni fecha ausentes (AP-45: usa `s.f.` y mueve el título).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

#: Formas documentales canónicas reconocidas en `document_shape:` y `--shape`.
FORMAS_DE_DOCUMENTO: Tuple[str, ...] = (
    "resumen",
    "sintesis",
    "informe",
    "reporte",
    "decision",
    "auditoria",
    "referencia",
)

#: Niveles epistémicos para separar hechos medidos de hipótesis y decisiones.
NIVELES_EPISTEMICOS: Tuple[str, ...] = (
    "observado",
    "inferencia",
    "propuesta",
    "decision",
    "desconocido",
)

#: Secciones recomendadas y requisitos orientativos (reglas condicionales, no bloqueo rígido).
ESPECIFICACIONES_FORMA: Dict[str, Dict[str, Any]] = {
    "resumen": {
        "proposito": "Condensar una fuente o evento en idea principal y puntos clave.",
        "secciones_recomendadas": ("Idea principal", "Puntos clave"),
        "requiere_evidencia": False,
    },
    "sintesis": {
        "proposito": "Integrar multiples fuentes destacando convergencias y tensiones.",
        "secciones_recomendadas": ("Tema transversal", "Convergencias", "Tensiones", "Fuentes"),
        "requiere_evidencia": True,
    },
    "informe": {
        "proposito": "Comunicar hallazgos estructurados con evidencia y conclusiones accionables.",
        "secciones_recomendadas": ("Resumen ejecutivo", "Hallazgos", "Evidencia", "Conclusiones"),
        "requiere_evidencia": True,
    },
    "reporte": {
        "proposito": "Presentar datos medidos, metricas, fuente/corte y observaciones.",
        "secciones_recomendadas": ("Resumen de datos", "Metricas", "Fuente y corte", "Observaciones"),
        "requiere_evidencia": True,
    },
    "decision": {
        "proposito": "Fijar contexto, decision y consecuencias verificables (ADR).",
        "secciones_recomendadas": ("Contexto", "Decision", "Consecuencias"),
        "requiere_evidencia": False,
    },
    "auditoria": {
        "proposito": "Evaluar cumplimiento contra criterio verificable con alcance, hallazgos y riesgos.",
        "secciones_recomendadas": ("Alcance", "Hallazgos", "Evidencia", "Riesgos y remediacion"),
        "requiere_evidencia": True,
    },
    "referencia": {
        "proposito": "Documentar contrato, parametros o interfaz consultable sin prosa narrativa.",
        "secciones_recomendadas": ("Proposito", "Contrato", "Ejemplos"),
        "requiere_evidencia": False,
    },
}

_RE_ENCABEZADO = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_RE_ANIO = re.compile(r"\b(\d{4})\b")
_RE_FECHA_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_RE_WIKILINK = re.compile(r"\[\[[^\[\]\n]+\]\]")
_RE_URL = re.compile(r"https?://\S+")
_RE_TABLA_MD = re.compile(r"^\|.+\|\s*$", re.MULTILINE)
_RE_CODIGO_INLINE = re.compile(r"`[^`\n]+`")
_RE_MARCADORES = {
    "observado": re.compile(r"\bobservad[oa]s?\b", re.IGNORECASE),
    "inferencia": re.compile(r"\binferenci[ae]s?\b|\binferid[oa]s?\b", re.IGNORECASE),
    "propuesta": re.compile(r"\bpropuest[oa]s?\b", re.IGNORECASE),
    "decision": re.compile(r"\bdecisi[oó]n(?:es)?\b|\bdecidid[oa]s?\b", re.IGNORECASE),
    "desconocido": re.compile(r"\bdesconocid[oa]s?\b|\bsin\s+verificar\b", re.IGNORECASE),
}


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or ""))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.lower().split())


def evaluar_forma(texto: str, forma: str) -> Dict[str, Any]:
    """Evalúa un texto Markdown contra una forma documental sin mutar nada.

    Devuelve secciones presentes/faltantes, marcadores epistémicos detectados,
    evidencia observada y recomendaciones accionables.
    """
    forma_norm = _normalizar(forma)
    if forma_norm not in ESPECIFICACIONES_FORMA:
        raise ValueError(
            f"Forma documental invalida: {forma!r}. Validas: {list(FORMAS_DE_DOCUMENTO)}"
        )

    spec = ESPECIFICACIONES_FORMA[forma_norm]
    encabezados = [_normalizar(m.group(1)) for m in _RE_ENCABEZADO.finditer(texto or "")]

    presentes: List[str] = []
    faltantes: List[str] = []
    for sec in spec["secciones_recomendadas"]:
        sec_norm = _normalizar(sec)
        if any(sec_norm in h for h in encabezados):
            presentes.append(sec)
        else:
            faltantes.append(sec)

    marcadores = [
        nivel for nivel, patron in _RE_MARCADORES.items()
        if patron.search(texto or "")
    ]

    tiene_evidencia = bool(
        _RE_WIKILINK.search(texto or "")
        or _RE_URL.search(texto or "")
        or _RE_TABLA_MD.search(texto or "")
        or _RE_CODIGO_INLINE.search(texto or "")
    )

    recomendaciones: List[str] = []
    if faltantes:
        recomendaciones.append(
            f"Considera incluir secciones recomendadas para `{forma_norm}`: {', '.join(faltantes)}."
        )
    if spec["requiere_evidencia"] and not tiene_evidencia:
        recomendaciones.append(
            "Anade enlaces [[nota]], URL, tabla de datos o referencias de codigo que sostengan las afirmaciones."
        )
    if spec["requiere_evidencia"] and not marcadores:
        recomendaciones.append(
            "Distingue hechos de hipotesis usando marcadores como Observado, Inferencia o Propuesta."
        )

    return {
        "forma": forma_norm,
        "valida": (not faltantes) and (tiene_evidencia or not spec["requiere_evidencia"]),
        "secciones_presentes": presentes,
        "secciones_faltantes": faltantes,
        "marcadores_epistemicos": marcadores,
        "tiene_evidencia": tiene_evidencia,
        "recomendaciones": recomendaciones,
    }


def formatear_cita_apa(
    title: str,
    url: str = "",
    author: Optional[str] = None,
    published_date: Optional[str] = None,
    accessed_at: Optional[str] = None,
    source_type: str = "web",
) -> str:
    """Construye una referencia estilo APA 7ª ed. sin fabricar metadatos ausentes (AP-45).

    - Si falta `published_date` o no contiene año de 4 dígitos, usa `s.f.` (sin fecha).
    - Si falta `author`, coloca el título en posición de autor (regla APA 7).
    """
    titulo = " ".join(str(title or "").split()).rstrip(".")
    autor = " ".join(str(author or "").split()).rstrip(".")

    anio = "s.f."
    if published_date:
        m = _RE_ANIO.search(str(published_date))
        if m:
            anio = m.group(1)

    if autor:
        base = f"{autor}. ({anio}). {titulo}."
    else:
        base = f"{titulo}. ({anio})."

    url_limpia = str(url or "").strip()
    fecha_acceso = ""
    if accessed_at:
        ma = _RE_FECHA_ISO.search(str(accessed_at))
        if ma:
            fecha_acceso = ma.group(1)

    if url_limpia and fecha_acceso:
        return f"{base} Consultado el {fecha_acceso} de {url_limpia}"
    if url_limpia:
        return f"{base} {url_limpia}"
    return base


def auditar_cita_bibliografica(fm: Dict[str, Any]) -> Dict[str, Any]:
    """Inspecciona completitud de metadatos bibliográficos en frontmatter (solo lectura)."""
    author = str(fm.get("author") or "").strip()
    published = str(fm.get("published_date") or "").strip()
    url = str(fm.get("url") or "").strip()
    citation = str(fm.get("citation_apa") or "").strip()

    faltantes: List[str] = []
    if not author:
        faltantes.append("author")
    if not published:
        faltantes.append("published_date")
    if not url:
        faltantes.append("url")
    if not citation:
        faltantes.append("citation_apa")

    return {
        "complete": not faltantes,
        "has_author": bool(author),
        "has_published_date": bool(published),
        "has_url": bool(url),
        "has_citation_apa": bool(citation),
        "missing_fields": faltantes,
    }


__all__ = [
    "FORMAS_DE_DOCUMENTO",
    "NIVELES_EPISTEMICOS",
    "ESPECIFICACIONES_FORMA",
    "evaluar_forma",
    "formatear_cita_apa",
    "auditar_cita_bibliografica",
]
