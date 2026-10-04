"""Criterio reusable de evidencia en cuerpos Markdown.

Es una hoja del toolkit: no conoce CLI, manifiesto, baselines ni checkout.
"""

from __future__ import annotations

import re

_MARCADORES_PENDIENTE = re.compile(
    r"^[ \t]{0,16}(?:[-*+]\s+|>\s*)?[_*]{0,2}\s*(?:"
    r"pendientes?|todo|fixme|tbd|t\.b\.d\.?"
    r"|por (?:definir|documentar|completar|determinar)"
    r"|sin (?:datos|contenido|informaci[oó]n|detectar|detectados?|detectadas?)"
    r"|no (?:detectados?|detectadas?|disponible|aplica)"
    r"|desconocidos?|desconocidas?|n/a"
    r")\s*[_*]{0,2}\s*[.:;!]?\s*[_*]{0,2}\s*$",
    re.IGNORECASE,
)
_APARTE_PENDIENTE = re.compile(
    r"^\s*(?:[-*+]\s+|>\s*)?([_*]{1,2})\s*(?:pendientes?|todo|tbd|por (?:definir|documentar|completar))"
    r"\b.*\1\s*$",
    re.IGNORECASE,
)
_LINEA_ANDAMIO = re.compile(
    r"^\s*(?:#{1,6}\s|-{3,}\s*$|\*{3,}\s*$|\|[\s|:-]*\|\s*$|[-*+]\s*$|>\s*$|<!--)"
)


def cuerpo_sin_marcadores(body: str) -> str:
    """Retira andamiaje y marcadores; conserva únicamente afirmaciones."""
    if not body:
        return ""
    limpio = re.sub(r"```[^\n]*\n\s*```", "", body)
    limpio = re.sub(
        r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[\s|:-]+\|[ \t]*$(?!\n[ \t]*\|)",
        "",
        limpio,
        flags=re.MULTILINE,
    )
    utiles = [
        ln for ln in limpio.splitlines()
        if ln.strip()
        and not _LINEA_ANDAMIO.match(ln)
        and not _MARCADORES_PENDIENTE.match(ln)
        and not _APARTE_PENDIENTE.match(ln)
    ]
    return "\n".join(utiles).strip()


_H1 = re.compile(r"^ {0,3}#[ \t]+\S")


def con_titulo(titulo: str, cuerpo: str) -> str:
    """CN-04: el cuerpo de una nota abre con su título como H1.

    Medido el 2026-10-04 en la QA de producto: `vault_write`,
    `vault_knowledge_save` y `vault_ai_decision` escribían el título solo en
    el frontmatter, y la nota abierta fuera de Obsidian —un editor de texto,
    un visor de Markdown, un diff— empezaba en la primera frase o en una línea
    de metadatos, sin decir qué era. El vault tiene que seguir siendo legible
    sin la herramienta que lo generó.

    Un cuerpo que ya abre con un H1 se respeta tal cual: quien lo escribió
    eligió su título. `#etiqueta` no es un encabezado y no cuenta.
    """
    for linea in cuerpo.splitlines():
        if linea.strip():
            if _H1.match(linea):
                return cuerpo
            break
    titulo = " ".join(str(titulo or "").split())
    if not titulo:
        return cuerpo
    return f"# {titulo}\n\n{cuerpo.lstrip(chr(10))}"
