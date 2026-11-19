"""Criterio reusable de evidencia en cuerpos Markdown.

Es una hoja del toolkit: no conoce CLI, manifiesto, baselines ni checkout.
"""

from __future__ import annotations

import hashlib
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

#: La sección donde viven las decisiones: la que AP-07 mide, la que
#: `vault_write --adr` escribe y la que el adaptador de cliente manda leer.
CARPETA_DECISIONES = "03_Decisions"

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
    if not rel.startswith(CARPETA_DECISIONES + "/"):
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


#: El nombre de un ADR numerado: `adr-NNN-<slug>` (el número abre el stem).
_NUMERO_ADR = re.compile(r"^adr-(\d+)(?:-|$)", re.IGNORECASE)

#: Cifras del número de un ADR nuevo: `adr-007`, no `adr-7`.
CIFRAS_ADR = 3


def siguiente_numero_adr(stems) -> str:
    """El primer `adr-NNN` libre después del mayor que ya existe.

    Recibe los stems de `03_Decisions/` en vez de leer el disco: quien llama
    sabe dónde está el vault y bajo qué lock lo mira. Un hueco en la
    numeración no se rellena: el número de una decisión retirada no se
    reutiliza, porque otro documento puede seguir citándolo.
    """
    usados = [int(m.group(1)) for s in stems for m in [_NUMERO_ADR.match(str(s))] if m]
    return f"adr-{(max(usados) + 1 if usados else 1):0{CIFRAS_ADR}d}"


def plantilla_adr() -> str:
    """El esqueleto que se propone al escribir un ADR, derivado de las listas."""
    # El contexto abre y las opciones van antes de la decisión que eligen una:
    # es el orden en que se lee un porqué, no el de las listas.
    obligatorias = [n for n, _ in SECCIONES_ADR]
    orden = obligatorias[:1] + [n for n, _ in SECCIONES_ADR_RECOMENDADAS] + obligatorias[1:]
    return "\n\n".join(f"## {s}" for s in orden) + "\n"


# ── ISO/IEC/IEEE 42010: concerns and viewpoints of a decision ──────────────
#
# 42010 describes an architecture through its stakeholders' concerns: a
# viewpoint frames some concerns, and a view that conforms to it addresses
# them. An ADR records a decision and its why (AP-07); until now it could not
# say which concern it answers nor from which viewpoint it was taken, so
# nothing measured which concerns the architecture leaves unanswered.
#
# The fields are optional and additive: an ADR that does not declare them is
# written and read exactly as before. They are frontmatter, not body
# sections, so `plantilla_adr()` (the body skeleton AP-07 measures, shared by
# the audit guidance and the write-path hints) does not carry them;
# `pista_de_intereses()` names them where an ADR is written. The registry is
# small and declared, not calibrated; a value outside it is refused at write
# time instead of becoming a private vocabulary in each vault.

#: Frontmatter field with the concerns the decision addresses (a list).
CAMPO_INTERESES = "concerns"

#: Frontmatter field with the viewpoint the decision is taken from.
CAMPO_PUNTO_DE_VISTA = "viewpoint"

#: Concern → what it covers. Closed vocabulary of `concerns:`.
INTERESES_DE_ARQUITECTURA = {
    "seguridad": "confidencialidad, integridad y control de acceso",
    "rendimiento": "tiempos de respuesta, capacidad y uso de recursos",
    "mantenibilidad": "facilidad de cambiar, probar y entender el sistema",
    "disponibilidad": "continuidad del servicio y recuperación ante fallos",
    "coste": "coste de construir, operar y cambiar",
    "cumplimiento": "obligaciones legales, normativas y contractuales",
    "datos": "modelo, calidad, ciclo de vida y propiedad de los datos",
}

#: Viewpoint → what its views show and the concerns it frames (42010: a
#: viewpoint frames concerns). Closed vocabulary of `viewpoint:`.
PUNTOS_DE_VISTA = {
    "logico": {"que": "módulos, responsabilidades y dependencias",
               "enmarca": ("mantenibilidad", "rendimiento", "coste")},
    "despliegue": {"que": "nodos, entornos y cómo se instala y escala",
                   "enmarca": ("disponibilidad", "rendimiento", "coste")},
    "datos": {"que": "entidades, almacenes y flujos de datos",
              "enmarca": ("datos", "cumplimiento", "seguridad")},
    "seguridad": {"que": "fronteras de confianza, identidades y controles",
                  "enmarca": ("seguridad", "cumplimiento")},
    "operacion": {"que": "monitorización, incidentes y mantenimiento en marcha",
                  "enmarca": ("disponibilidad", "mantenibilidad", "coste")},
}


def problemas_de_intereses(fm) -> list:
    """42010: what `concerns:`/`viewpoint:` say that the registry does not know.

    Empty when neither field is declared: both are optional. The writer
    refuses with these messages and the report lists them for notes written
    by hand.
    """
    fm = fm or {}
    problemas = []
    if CAMPO_INTERESES in fm:
        valor = fm[CAMPO_INTERESES]
        if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
            problemas.append(f"`{CAMPO_INTERESES}` tiene que ser una lista de textos")
        else:
            fuera = [v for v in valor if v not in INTERESES_DE_ARQUITECTURA]
            if fuera:
                problemas.append(
                    f"{CAMPO_INTERESES} {fuera} fuera de {sorted(INTERESES_DE_ARQUITECTURA)} "
                    "(ISO/IEC/IEEE 42010)")
    if CAMPO_PUNTO_DE_VISTA in fm:
        valor = fm[CAMPO_PUNTO_DE_VISTA]
        if not isinstance(valor, str) or valor not in PUNTOS_DE_VISTA:
            problemas.append(
                f"{CAMPO_PUNTO_DE_VISTA} {valor!r} fuera de {sorted(PUNTOS_DE_VISTA)} "
                "(ISO/IEC/IEEE 42010)")
    return problemas


def intereses_fuera_del_punto_de_vista(fm) -> list:
    """The declared concerns that the declared viewpoint does not frame.

    Empty when either field is missing or invalid: correspondence is only
    measured between known values.
    """
    fm = fm or {}
    intereses = fm.get(CAMPO_INTERESES)
    punto = fm.get(CAMPO_PUNTO_DE_VISTA)
    marco = PUNTOS_DE_VISTA.get(punto) if isinstance(punto, str) else None
    if marco is None or not isinstance(intereses, list):
        return []
    return [i for i in intereses
            if i in INTERESES_DE_ARQUITECTURA and i not in marco["enmarca"]]


def pista_de_intereses() -> str:
    """How an ADR declares its concerns and viewpoint, for the write-path hint."""
    return (f"Opcional (ISO/IEC/IEEE 42010): --meta '{{\"{CAMPO_INTERESES}\": [...], "
            f"\"{CAMPO_PUNTO_DE_VISTA}\": \"...\"}}' con {CAMPO_INTERESES} de "
            f"{sorted(INTERESES_DE_ARQUITECTURA)} y {CAMPO_PUNTO_DE_VISTA} de "
            f"{sorted(PUNTOS_DE_VISTA)}.")


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


# ── AP-07 at the mutation boundary: what "closing" means for a decision ────
#
# The audit reads every ADR; the guard only refuses what a write makes
# definitive. An open decision (`draft`, `review`) may still be incomplete
# while it is discussed; once its status leaves the open regime it is what an
# agent consults, so its why must be written. The regime is derived by
# `vault_registry.regimen_de_estado` and passed by the caller, as for AP-64.

#: Regimes in which a decision no longer goes back to draft.
REGIMENES_DE_CIERRE = ("cerrado", "terminal")

#: States that announce themselves as scaffolding (AP-03 rules them).
_ESTADOS_DE_ANDAMIO = ("stub", "template")


def secciones_faltantes_al_cerrar(fm, cuerpo: str, regimen: str) -> list:
    """AP-07: the mandatory sections a closed decision lacks, or `[]`.

    Empty for an open decision and for scaffolding: the guard asks for the
    why only when the decision is definitive.
    """
    estado = str((fm or {}).get("status") or "").strip().lower()
    if regimen not in REGIMENES_DE_CIERRE or estado in _ESTADOS_DE_ANDAMIO:
        return []
    return secciones_adr_faltantes(cuerpo)


# ── AP-73: the raw source layer (Karpathy L1) ───────────────────────────────
#
# `vault_ingest --archivar-fuente` keeps the source verbatim; the model reads
# it and never edits it. Which note is an archived source, and how its body is
# fingerprinted, is decided here once: the write owner refuses the rewrite,
# the archiver records the fingerprint and the audit compares it.

#: Where archived sources live, inside the section that means "imported as it
#: arrived" (`vault_registry.SECTION_DOCUMENTACION["10_Migrated"]`).
CARPETA_FUENTES = "10_Migrated/fuentes"

#: Frontmatter field with the fingerprint of the body as it was archived. The
#: older `sha256` is the hash of the raw text before the write owner sanitized
#: it, so it cannot tell a sanitized byte from an edit.
CAMPO_HUELLA_FUENTE = "sha256_cuerpo"


def es_fuente_archivada(rel: str, fm) -> bool:
    """AP-73: the note is an archived raw source that is never rewritten."""
    fm = fm or {}
    rel = str(rel).replace("\\", "/")
    return (rel.startswith(CARPETA_FUENTES + "/")
            and str(fm.get("type") or "").strip().lower() == "migrated"
            and str(fm.get("status") or "").strip().lower() == "archived")


def huella_de_cuerpo(cuerpo: str) -> str:
    """The fingerprint of a note body: line endings, BOM and outer blanks aside.

    Those three are what reading and writing change without anyone editing
    (the parser drops the leading blank, a Windows editor writes CRLF).
    """
    texto = (cuerpo or "").replace("\r\n", "\n").lstrip("﻿").strip()
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def estado_de_fuente_archivada(fm, cuerpo: str) -> str:
    """AP-73: `intacta`, `alterada`, or `sin_huella` when nothing was recorded.

    Without a recorded fingerprint the source cannot be called intact: it is
    reported as unverifiable rather than guessed.
    """
    registrada = str((fm or {}).get(CAMPO_HUELLA_FUENTE) or "").strip().lower()
    if not registrada:
        return "sin_huella"
    return "intacta" if registrada == huella_de_cuerpo(cuerpo) else "alterada"


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


# ── Nota escalonada: el lead y la profundidad (nota-escalonada S4) ─────────
#
# Measured on 2026-11-19: the vault the onboarding generates for a third party
# had a median of 5 content lines and 28 words per note, and nothing in it
# told a reader without context what a note was before its detail. The
# owner's reference (`notas data.txt`) is the Wikipedia article: a lead that
# works as an executive summary, then the synthesis, then the report, and the
# short report only as a linked event record. The generators compose that
# note with `nota_escalonada` and the audit measures it with
# `profundidad_de_nota`: one criterion for the writer and the reader (AP-57).

#: The layers below the lead, in reading order: synthesis, report, references.
CAPAS_ESCALONADAS = ("Contexto", "Detalle", "Fuentes")

#: A lead stands alone with at least two sentences and twenty real words: one
#: sentence names the thing, the second says why it matters or where it is.
LEAD_MIN_ORACIONES = 2
LEAD_MIN_PALABRAS = 20

_RE_MARCAS_DE_LINEA = re.compile(r"^[#\-\*\s|>]+")
_RE_ENLACE_WIKI = re.compile(r"\[\[[^\]\n]+\]\]")
_RE_FIN_DE_ORACION = re.compile(r"(?<=[.!?])\s+")
#: Lines in the lead zone that are not prose: provenance quotes, `**Key:**`
#: metadata, lists, tables and HTML comments.
_NO_ES_PROSA = re.compile(r"^\s*(?:>|\*\*[^*\n]+:\*\*|[-*+]\s|\d+[.)]\s|\||<!--)")


def lineas_reales(texto: str) -> list:
    """The content gate's real lines: no blanks, TODO-only, lone dashes or bare headings."""
    return [
        linea for linea in (texto or "").split("\n")
        if linea.strip()
        and not linea.strip().startswith("TODO")
        and linea.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", linea.strip())
    ]


def palabras_reales(texto: str) -> list:
    """The content gate's real words (AP-11/AP-20), lifted from `vault_write`.

    Heading markers, bullets, quotes and table pipes do not count, and neither
    do one-character tokens: the rule `vault_write` has applied since v38.
    """
    palabras = []
    for linea in lineas_reales(texto):
        for token in _RE_MARCAS_DE_LINEA.sub("", linea).split():
            token = token.strip("`*~_[]()#").strip(".,;:!?")
            if token and len(token) > 1:
                palabras.append(token)
    return palabras


def lead_de(cuerpo: str) -> str:
    """The note's lead: the prose between its H1 (if any) and its first heading.

    Provenance quotes, `**Key:**` metadata, lists, tables and pending markers
    are not a lead: they tell the reader where a note comes from or what it
    lists, not what it is.
    """
    lineas = (cuerpo or "").lstrip("﻿").splitlines()
    i = 0
    while i < len(lineas) and not lineas[i].strip():
        i += 1
    if i < len(lineas) and _H1.match(lineas[i]):
        i += 1
    prosa = []
    for linea in lineas[i:]:
        if _ENCABEZADO.match(linea):
            break
        if (not linea.strip() or _NO_ES_PROSA.match(linea) or _LINEA_ANDAMIO.match(linea)
                or _MARCADORES_PENDIENTE.match(linea) or _APARTE_PENDIENTE.match(linea)):
            continue
        prosa.append(linea.strip())
    return " ".join(prosa)


def _oraciones(texto: str) -> int:
    return sum(1 for trozo in _RE_FIN_DE_ORACION.split(texto.strip()) if palabras_reales(trozo))


def profundidad_de_nota(cuerpo: str) -> dict:
    """How far a note goes from its lead to its detail.

    `nivel`: 0 without a self-sufficient lead; 1 lead only; 2 lead and
    `Contexto` or `Detalle`; 3 that and `Fuentes`.
    """
    lead = lead_de(cuerpo)
    palabras_lead = len(palabras_reales(lead))
    oraciones = _oraciones(lead) if lead else 0
    tiene_lead = oraciones >= LEAD_MIN_ORACIONES and palabras_lead >= LEAD_MIN_PALABRAS
    titulos = [_sin_tildes(m.group(1)) for m in _ENCABEZADO.finditer(cuerpo or "")
               if m.group(0).lstrip().startswith("## ")]
    capas = [capa for capa in CAPAS_ESCALONADAS
             if any(t == _sin_tildes(capa) or t.startswith(_sin_tildes(capa) + " ") for t in titulos)]
    nivel = 0
    if tiene_lead:
        nivel = 1
        if "Contexto" in capas or "Detalle" in capas:
            nivel = 3 if "Fuentes" in capas else 2
    return {
        "tiene_lead": tiene_lead,
        "lead_oraciones": oraciones,
        "lead_palabras": palabras_lead,
        "capas": capas,
        "secciones": len(titulos),
        "lineas_reales": len(lineas_reales(cuerpo_sin_marcadores(cuerpo))),
        "palabras_reales": len(palabras_reales(cuerpo_sin_marcadores(cuerpo))),
        "enlaces": len(_RE_ENLACE_WIKI.findall(cuerpo or "")),
        "nivel": nivel,
    }


def nota_escalonada(titulo: str, lead: str, contexto: str = None, detalle: str = None,
                    fuentes: str = None, falta: str = None) -> str:
    """Compose a layered note: H1, lead, what is missing, and the layers that have content.

    A layer without content is not written (AP-45: no filler). What is missing
    is written as a pending marker (`> _Pendiente: ..._`), so the reader sees
    it and the evidence criterion (`cuerpo_sin_marcadores`) does not count it.
    """
    partes = [" ".join(str(lead or "").split())]
    if falta and str(falta).strip():
        motivo = " ".join(str(falta).split()).rstrip(".")
        partes.append(f"> _Pendiente: {motivo}._")
    for capa, texto in zip(CAPAS_ESCALONADAS, (contexto, detalle, fuentes)):
        if texto and str(texto).strip():
            partes.append(f"## {capa}\n\n{str(texto).strip()}")
    return con_titulo(titulo, "\n\n".join(p for p in partes if p) + "\n")
