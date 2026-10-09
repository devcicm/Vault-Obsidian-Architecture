"""Criterio reusable de evidencia en cuerpos Markdown.

Es una hoja del toolkit: no conoce CLI, manifiesto, baselines ni checkout.
"""

from __future__ import annotations

import re
import unicodedata

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


def abre_con_h1(cuerpo: str) -> bool:
    """CN-04, el criterio: la primera línea con texto del cuerpo es un H1.

    Lo usan quien escribe (`con_titulo`) y quien audita lo ya escrito
    (`vault_audit`, desde v41.2): un solo criterio, para que una nota que el
    write path da por titulada no salga sin título en la auditoría (AP-57).
    El BOM inicial no cuenta y `#etiqueta` no es un encabezado.
    """
    for linea in (cuerpo or "").lstrip("﻿").splitlines():
        if linea.strip():
            return bool(_H1.match(linea))
    return False


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

    El BOM inicial se descarta antes de mirar: un contenido copiado de un
    fichero guardado como UTF-8 con BOM abre con `\\ufeff# Título`, el patrón
    no lo reconocía y `vault_knowledge_save` dejaba dos H1 (regla 7 contra
    /ans, 2026-10-04). Detrás del frontmatter el BOM no marca nada.
    """
    cuerpo = cuerpo.lstrip("﻿")
    if abre_con_h1(cuerpo):
        return cuerpo
    titulo = " ".join(str(titulo or "").split())
    if not titulo:
        return cuerpo
    return f"# {titulo}\n\n{cuerpo.lstrip(chr(10))}"


# ── AP-07: qué es un ADR y qué secciones le faltan ──────────────────────────
#
# Hasta v41.3 el criterio estaba escrito cuatro veces y ninguna coincidía con
# otra: `vault_norms_scan` exigía a la vez «contexto» y «context», «opciones» y
# «options», así que un ADR completo en castellano salía siempre incompleto, y
# decidía por la subcadena `adr` en la ruta; la auditoría lo decidía por `type`;
# la guía de `vault_audit` y la plantilla de `vault_onboard` proponían cada una
# su lista. Un agente que consultara la norma recibía cuatro respuestas.
#
# Medido contra /ans (regla 7, 2026-10-08): los diez ADR reales tienen
# contexto, decisión y consecuencias; ocho de diez no tienen «Opciones». Por
# eso «Opciones» se recomienda y no se exige: exigirla habría marcado como
# incompletas decisiones que sí registran el porqué.

#: Valores de `type` que declaran una decisión arquitectónica.
TIPOS_ADR = ("decision", "adr")

#: Sección obligatoria → términos que la reconocen en un encabezado, sin tildes
#: y en minúscula. Cuenta la subcadena: «Contexto detectado» es Contexto.
SECCIONES_ADR = (
    ("Contexto", ("contexto", "context")),
    ("Decisión", ("decision",)),
    ("Consecuencias", ("consecuencia", "consequence")),
)

#: Recomendadas: su ausencia se informa, no hace incompleto al ADR.
SECCIONES_ADR_RECOMENDADAS = (
    ("Opciones", ("opcion", "option", "alternativa", "alternative")),
)

#: Primer de sección (`00-03_decisions-primer`): guía de uso de la carpeta.
_PRIMER = re.compile(r"^\d{2}-\d{2}_.*-primer$")

_ENCABEZADO = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def es_adr(rel: str, tipo: str = "", stem: str = "") -> bool:
    """AP-07: la nota es un ADR al que exigirle sus secciones.

    Solo dentro de `03_Decisions/`: una ruta con «adr» en otra sección no es una
    decisión por llamarse así. Dentro, quedan fuera el índice y los primers de
    sección, y toda nota que **declare** un `type` ajeno a la decisión. Sin
    `type` sigue siendo ADR: omitir el campo no es la vía de escape del guard.
    """
    rel = rel.replace("\\", "/")
    if not rel.startswith("03_Decisions/"):
        return False
    stem = (stem or rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]).lower()
    if stem == "index" or _PRIMER.match(stem):
        return False
    tipo = str(tipo or "").strip().lower()
    return not tipo or tipo in TIPOS_ADR or stem.startswith("adr-")


def _faltan(cuerpo: str, secciones) -> list:
    encabezados = [_sin_tildes(h) for h in _ENCABEZADO.findall(cuerpo or "")]
    return [
        nombre for nombre, terminos in secciones
        if not any(t in h for h in encabezados for t in terminos)
    ]


def secciones_adr_faltantes(cuerpo: str) -> list:
    """Secciones obligatorias de AP-07 sin encabezado que las nombre, en orden."""
    return _faltan(cuerpo, SECCIONES_ADR)


def secciones_adr_recomendadas_faltantes(cuerpo: str) -> list:
    """Secciones recomendadas de AP-07 que el ADR no tiene."""
    return _faltan(cuerpo, SECCIONES_ADR_RECOMENDADAS)


def plantilla_adr() -> str:
    """El esqueleto que se propone al escribir un ADR, derivado de las listas."""
    # El contexto abre y las opciones van antes de la decisión que eligen una:
    # es el orden en que se lee un porqué, no el de las listas.
    obligatorias = [n for n, _ in SECCIONES_ADR]
    orden = obligatorias[:1] + [n for n, _ in SECCIONES_ADR_RECOMENDADAS] + obligatorias[1:]
    return "\n\n".join(f"## {s}" for s in orden) + "\n"


# ── AP-64: quién responde del porqué de una decisión cerrada ───────────────
#
# Un ADR aprobado es lo que un agente consulta antes de actuar. Si nadie
# responde de él, el agente no distingue una decisión que tomó una persona de
# una que otro agente escribió y dio por buena. Medido contra /ans (regla 7,
# 2026-10-08): ninguno de sus ADR aceptados declara quién responde de él.
#
# El régimen del estado no se decide aquí: lo deriva
# `vault_registry.regimen_de_estado` y lo pasa quien llama, para que esta hoja
# siga sin importar a nadie.

#: El único valor estándar de `agent` (AP-16) que es una persona.
AGENTE_HUMANO = "human"


def falta_de_responsable(fm, regimen: str) -> str:
    """AP-64: por qué esta decisión cerrada no tiene quien responda de ella.

    Devuelve el motivo, o `""` si no hay falta. Solo se exige a una decisión
    en régimen `cerrado` que no sea plantilla: una abierta aún se discute y una
    terminal ya no se consulta como vigente. Es falta no declarar
    `responsable`, y también declarar como responsable al mismo agente no
    humano que la escribió: eso es firmarse el propio porqué.
    """
    fm = fm or {}
    if regimen != "cerrado" or str(fm.get("status") or "").strip().lower() == "template":
        return ""
    responsable = " ".join(str(fm.get("responsable") or "").split()).lower()
    if not responsable:
        return "decisión cerrada sin `responsable`: nadie responde de su porqué"
    agente = str(fm.get("agent") or "").strip().lower()
    if agente and agente != AGENTE_HUMANO and responsable == agente:
        return (f"el responsable es el mismo agente que la escribió ({agente}): "
                "una decisión cerrada la responde una persona")
    return ""


def meta_adr() -> dict:
    """El frontmatter con que se propone escribir un ADR (AP-07, AP-64).

    Nace en `draft`: quien lo redacta —persona o agente— no lo aprueba al
    escribirlo. Al cerrarlo se añade `responsable:` con la persona que responde
    de su porqué. La plantilla no lo rellena: un valor de relleno pasaría AP-64
    sin que nadie respondiera de nada.
    """
    return {"type": "adr", "status": "draft"}


# ── AP-65: decisión de IA de impacto alto sin evaluación de impacto ────────
#
# ISO/IEC 42001 pide registrar qué decidió un sistema de IA y por qué; ISO/IEC
# 42005 añade a quién afecta. `vault_ai_decision` registraba lo primero y no
# lo segundo. La escala de impacto es la `severidad` de `vault_vocabulario` y
# quien llama pasa los niveles que exigen evaluación, para que esta hoja siga
# sin importar a nadie.

#: Dónde viven las decisiones de IA (`vault_ai_decision`). El ámbito es del
#: criterio, no de cada detector: dos detectores con su propio prefijo son
#: dos criterios (AP-57).
SECCION_DECISIONES_IA = "16_AI_Governance"

#: Lo que una decisión de IA declara en `impact_assessment`.
EVALUACION_ESTADOS = ("no_exigida", "completa", "pendiente")


def niveles_de_impacto_exigidos(escala) -> tuple:
    """Los niveles que exigen evaluación: los dos más altos de `escala`.

    `escala` va de mayor a menor, como la declara `vault_vocabulario`
    (`severidad`). Quien escribe y quien audita llaman aquí con la misma
    escala; ninguno corta la lista por su cuenta.
    """
    return tuple(escala[:2])


def estado_de_evaluacion(impact_level: str, affected, exigidos) -> str:
    """`completa` si nombra a quién afecta; `pendiente` si se exigía y no lo hace.

    Una decisión de impacto alto que no dice a quién afecta registra el qué y
    el porqué, pero no el coste para otros. No se rechaza al escribir —un
    registro incompleto vale más que ninguno—; se declara, y AP-65 lo audita.
    """
    if [a for a in (affected or []) if str(a).strip()]:
        return "completa"
    return "pendiente" if str(impact_level or "").strip().lower() in exigidos else "no_exigida"


def falta_de_evaluacion_de_impacto(rel: str, fm, exigidos) -> str:
    """AP-65: por qué esta decisión de IA no tiene su evaluación de impacto.

    Devuelve el motivo, o `""` si no hay falta. Solo mira notas de
    `16_AI_Governance/` que declaran `impact_level` en uno de los niveles
    `exigidos` y no son plantilla. Es
    falta todo `impact_assessment` distinto de `completa`, también su
    ausencia: una decisión escrita antes de v41.3 no lo declara, y que no lo
    declare no dice que alguien la evaluase.
    """
    fm = fm or {}
    if str(rel or "").replace("\\", "/").split("/", 1)[0] != SECCION_DECISIONES_IA:
        return ""
    nivel = str(fm.get("impact_level") or "").strip().lower()
    if nivel not in exigidos or str(fm.get("status") or "").strip().lower() == "template":
        return ""
    estado = str(fm.get("impact_assessment") or "").strip().lower()
    if estado == "completa":
        return ""
    return (f"decisión de IA de impacto `{nivel}` sin evaluación de impacto completa "
            f"(`impact_assessment: {estado or '—'}`): no dice a quién afecta")
