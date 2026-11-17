#!/usr/bin/env python3
"""
vault_ingest.py — Ingesta gobernada de conversaciones, ficheros y URLs.

Hasta ahora todo lo que entraba al vault lo escribía una tool específica con un
contrato estrecho (`vault_log_error`, `vault_knowledge_save`, `vault_write`).
Falta lo contrario: un texto largo y sin forma —una conversación, un README, una
página— del que hay que extraer lo que merece persistir.

Ese es exactamente el camino por el que un vault se envenena. Por eso aquí el
pre-vuelo anti-poison **no es opcional ni desactivable**: es la primera etapa
del pipeline, y si encuentra algo bloqueante no se escribe nada. Un texto de
origen externo es entrada no confiable, sin excepciones.

Pipeline:

    fuente → pre-vuelo (cli.safety) → segmentación → extracción de entidades
           → propuesta de notas → [--commit] escritura atómica + índice

Por defecto es **dry-run**: emite la propuesta y no toca el vault. Escribir
lotes de notas derivadas de texto sin revisar es cómo se degrada la calidad de
un vault, así que la escritura exige `--commit` explícito.

Usage:
    python vault_ingest.py --file notas-reunion.md --section 07_Knowledge
    python vault_ingest.py --text "..." --section 03_Decisions --commit
    python vault_ingest.py --file README.md --section 07_Knowledge --dry-run
    cat conversacion.txt | python vault_ingest.py --stdin --section 04_Sessions
"""

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vault.consulta import safety  # noqa: E402

from vault_errors import emit_error, wrap_main  # noqa: E402
from vault_io import (  # noqa: E402
    assert_within_vault,
    atomic_write_text,
    tomar_lock,
    update_section_index,
)
from vault_lib import slugify, strip_code_blocks, utcnow  # noqa: E402

# Secciones que esta tool NO puede alimentar: son artefactos generados o
# propiedad exclusiva de otras tools. Ingerir texto libre ahí rompería la
# regla de un-solo-dueño-por-carpeta de vault_registry.
FORBIDDEN_SECTIONS = frozenset({"00_System", "99_Index", "17_Preferences"})

MIN_CHUNK_CHARS = 120
_LOCK_TIMEOUT = 10.0
DEFAULT_MAX_NOTES = 20

#: Tope de lo que se ingiere de una vez, en caracteres.
#:
#: `--url` ya traía un tope duro de 5.000.000 de bytes y `--text` uno de
#: 200.000 caracteres, este último impuesto por `safety.MAX_ARG_LENGTH` sobre
#: argv. `--file` y `--stdin` no tenían ninguno: el mismo contenido entraba
#: controlado por una puerta y sin control por otra, que es la asimetría que
#: convierte un tope en decorativo. Se declara aquí para las cuatro, alineado
#: con el de red, y se puede subir con `--max-chars` cuando la ingesta grande
#: es deliberada —lo que hace falta es que sea una decisión, no un descuido—.
#:
#: No es una defensa contra retroceso catastrófico: `safety.scan_content` es
#: lineal (6,4 M de caracteres en 1,3 s, medido). Es el tope de recurso que
#: falta para que la superficie de escritura no acepte lo ilimitado.
DEFAULT_MAX_CHARS = 5_000_000

# superseded_by: vault.kernel.normativa.conceptos.ENTIDADES_STOPWORDS (2026-11-16).
# The entity rule gained a second consumer (the AP-71 lint in `vault_audit`),
# so it moved to a kernel owner both contexts can import (AP-57). The name is
# kept (no-derogation) and points at the owner's value.
from vault.kernel.normativa.conceptos import (  # noqa: E402
    ENTIDADES_STOPWORDS as _ENTITY_STOPWORDS,
    CLASES_DE_CONCEPTO,
    extraer_entidades,
    resolver_concepto,
)

#: Raw source layer (Karpathy L1): where `--archivar-fuente` keeps the verbatim
#: source, inside the section that already means "imported as it arrived"
#: (`vault_registry.SECTION_DOCUMENTACION["10_Migrated"]`). Immutability is not
#: switched on here: declaring a section immutable is the owner's decision
#: (`00_System/inmutable.json`), never a side effect of ingesting.
CARPETA_FUENTES = "10_Migrated/fuentes"

#: AP-15: only text sources are archived. A binary does not belong in the vault
#: as a note, and `--file` is the only door where the extension is known.
_SUFIJOS_DE_TEXTO = frozenset({".md", ".markdown", ".txt"})

#: Where a page touched by an ingest receives its proposed append.
SECCION_DE_MENCIONES = "Menciones"



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.errores import completar_envelope  # noqa: E402

_RE_VAULT_INGEST_1 = re.compile('^(#{1,3})\\s+(.+?)\\s*#*$')


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _read_source(args: argparse.Namespace) -> Dict[str, Any]:
    """Obtiene el texto y su procedencia. La procedencia se conserva siempre:
    sin ella, la nota resultante es un dato huérfano (PAT-5)."""
    if args.text:
        return {"ok": True, "text": args.text, "origin": "inline", "source": "--text"}

    # El tope se pasa a la lectura, no sólo se comprueba después: leer entero
    # un fichero de diez gigas para luego rechazarlo por grande es agotar la
    # memoria antes de llegar al guard. Se lee `tope + 1` —el carácter de más
    # es lo que permite a `_check_size` distinguir "justo en el tope" de
    # "truncado"— y el veredicto lo sigue dando un único sitio.
    tope = getattr(args, "max_chars", DEFAULT_MAX_CHARS)

    if args.stdin:
        return {"ok": True, "text": sys.stdin.read(tope + 1), "origin": "stdin",
                "source": "stdin"}

    if args.file:
        path = Path(args.file).expanduser()
        if not path.is_file():
            return {"ok": False, "error_code": "SOURCE_NOT_FOUND",
                    "error": f"No existe el fichero: {args.file}"}
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                return {"ok": True, "text": fh.read(tope + 1),
                        "origin": "file", "source": str(path)}
        except OSError as exc:
            return {"ok": False, "error_code": "SOURCE_UNREADABLE", "error": str(exc)}

    if args.url:
        # La red está apagada por defecto a propósito. El estándar es
        # "sin servicio externo"; traer bytes de internet a un vault es una
        # decisión del usuario, no un default de la tool.
        if not args.allow_network:
            return {
                "ok": False,
                "error_code": "NETWORK_DISABLED",
                "error": "Descargar una URL requiere --allow-network explícito",
                "hint": "Descarga el contenido y usa --file, o pasa --allow-network",
            }
        import urllib.request

        if not args.url.lower().startswith(("http://", "https://")):
            return {"ok": False, "error_code": "INVALID_URL",
                    "error": "Solo se admiten URLs http(s)"}
        try:
            with urllib.request.urlopen(args.url, timeout=20) as response:
                # El mismo tope que las otras tres puertas. Estaba escrito aquí
                # a mano como 5_000_000 y era el único que existía.
                raw = response.read(tope + 1)
        except Exception as exc:
            return {"ok": False, "error_code": "FETCH_FAILED", "error": str(exc)}
        return {"ok": True, "text": raw.decode("utf-8", errors="replace"),
                "origin": "url", "source": args.url}

    return {"ok": False, "error_code": "NO_SOURCE",
            "error": "Indica una fuente: --file, --text, --stdin o --url"}


def _check_size(leido: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    """El tope se aplica igual venga por donde venga (ver DEFAULT_MAX_CHARS).

    Va después de leer y antes del preflight: se rechaza por tamaño sin haber
    interpretado el contenido, que es el orden que quiere una superficie de
    escritura.
    """
    if not leido.get("ok"):
        return leido
    n = len(leido["text"])
    if n > max_chars:
        return {
            "ok": False,
            "error_code": "SOURCE_TOO_LARGE",
            "error": (f"La fuente trae {n} caracteres y el tope es "
                      f"{max_chars} (origen: {leido.get('origin')})"),
            "recovery": ("Parte la fuente, o sube el tope con "
                         "--max-chars si la ingesta grande es deliberada"),
        }
    return leido


def _preflight(text: str, source: str) -> Dict[str, Any]:
    """Etapa 1, no negociable: el texto externo se escanea antes de mirarlo."""
    findings = safety.scan_content(text, "ingest:content")
    findings += safety.scan_content(source, "ingest:source")
    blocking = [f for f in findings if f.severity in ("critical", "high")]
    return {
        "ok": not blocking,
        "findings": [f.to_dict() for f in findings],
        "blocking": [f.to_dict() for f in blocking],
    }


def _segment(text: str) -> List[Dict[str, str]]:
    """Parte el texto por encabezados markdown; si no hay, por bloques.

    Segmentar por encabezado respeta la estructura que el autor ya dio. Cuando
    no la hay, agrupar párrafos es mejor que trocear por longitud fija: un
    corte arbitrario produce notas que empiezan a media idea.
    """
    lines = text.splitlines()
    chunks: List[Dict[str, str]] = []
    title: Optional[str] = None
    buffer: List[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body and len(body) >= MIN_CHUNK_CHARS:
            chunks.append({"title": title or _derive_title(body), "body": body})

    for line in lines:
        heading = _RE_VAULT_INGEST_1.match(line)
        if heading:
            flush()
            title = heading.group(2).strip()
            buffer = []
        else:
            buffer.append(line)
    flush()

    if not chunks:
        body = text.strip()
        if len(body) >= MIN_CHUNK_CHARS:
            chunks.append({"title": _derive_title(body), "body": body})
    return chunks


def _derive_title(body: str) -> str:
    """Primera frase con sentido, acotada. Un título largo se vuelve un slug
    ilegible y rompe la navegación del vault."""
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "sin-titulo")
    first = re.sub(r"^[#>*\-\s]+", "", first)
    first = re.split(r"(?<=[.!?])\s", first)[0]
    return first[:70].strip() or "sin-titulo"


#: superseded_by: vault.kernel.normativa.conceptos.extraer_entidades (2026-11-16).
#: Same rule, one owner: the AP-71 lint reads it too. Kept as a name so the
#: tests and callers that use it keep working (no-derogation).
_extract_entities = extraer_entidades


def _wikilink_de(ruta: str) -> str:
    """`07_Knowledge/a.md` -> `[[07_Knowledge/a]]`: the path form a wikilink takes."""
    return f"[[{ruta[:-3] if ruta.endswith('.md') else ruta}]]"


def _ruta_de_fuente_archivada(text: str, source: str, origin: str) -> str:
    """Content-addressed: the same source archived twice is the same file."""
    import hashlib

    stem = Path(source).stem if origin == "file" else "fuente"
    nombre = slugify(stem)[:60] or "fuente"
    huella = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{CARPETA_FUENTES}/{nombre}-{huella}.md"


def _motivo_para_no_archivar(text: str, source: str, origin: str) -> Optional[str]:
    """AP-15: why this source cannot enter the raw layer, or None."""
    if "\x00" in text:
        return "AP-15: la fuente contiene bytes nulos (binario); no se archiva como nota"
    if origin == "file" and Path(source).suffix.lower() not in _SUFIJOS_DE_TEXTO:
        return (f"AP-15: solo se archivan fuentes de texto "
                f"({', '.join(sorted(_SUFIJOS_DE_TEXTO))}); la fuente es "
                f"{Path(source).suffix or 'sin extensión'}")
    return None


def _nota_de_fuente(text: str, source: str, origin: str, agent: str) -> str:
    """The archived source: provenance frontmatter, then the source verbatim."""
    import hashlib

    stem = Path(source).stem if origin == "file" else source
    cabecera = (
        Frontmatter()
        .set("title", f"Fuente: {stem}", texto=True)
        .set("id", str(uuid.uuid4()))
        .set("type", "migrated")
        # A raw source is a record of what arrived; it is not revised, so
        # `archived` (STATUS_VOCAB) and not `draft`.
        .set("status", "archived")
        .set("tags", sorted({"ingested", "fuente", origin}))
        .set("createdAt", utcnow(), texto=True)
        .set("updatedAt", utcnow(), texto=True)
        .set("source", source, texto=True)
        .set("ingest_origin", origin, texto=True)
        .set("sha256", hashlib.sha256(text.encode("utf-8")).hexdigest(), texto=True)
        .set("cia_integrity", "medium")
        .set("cia_availability", "medium")
        .set("cia_sensitivity", "internal")
        .set("agent", agent, texto=True)
        .render()
    )
    return cabecera + "\n\n" + text


def _indice_del_vault() -> Dict[str, List[str]]:
    """Names every note answers to (file name and `aliases:`), Obsidian's way.

    The enumeration and the resolver are the kernel's (AP-57): the same
    criterion `vault_audit` uses to decide that a link resolves.
    """
    from vault.kernel.enumeracion import notas_en_disco
    from vault_lib import indice_de_nombres, parse_frontmatter

    raiz = _raiz()
    relativas: List[str] = []
    aliases: Dict[str, List[str]] = {}
    for ruta in notas_en_disco(raiz, _repo().ctx.secciones.ordenadas(),
                               incluir_indices=False):
        rel = ruta.relative_to(raiz).as_posix()
        relativas.append(rel)
        try:
            alias = (parse_frontmatter(ruta.read_text(encoding="utf-8")) or {}).get("aliases")
        except (OSError, UnicodeDecodeError):
            continue
        if isinstance(alias, str):
            alias = [alias]
        if isinstance(alias, list):
            aliases[rel] = [a for a in alias if isinstance(a, str)]
    return indice_de_nombres(relativas, aliases)


def _paginas_afectadas(
    entities: Dict[str, List[str]],
    proposals: List[Dict[str, Any]],
    source: str,
) -> List[Dict[str, Any]]:
    """Karpathy's ingest step 2: the existing pages this source touches.

    An entity that resolves to exactly one existing note gets a proposed
    append pointing at the derived notes that mention it. Ambiguous names are
    skipped: picking one would invent an identity the vault does not fix.
    With `--commit` they are applied by `_aplicar_paginas`, through the
    `bitacora_cambios` port, whose owner is `vault_append` (lock, `updatedAt`,
    its own change-log row): importing it here would open a consulta ->
    autoria crossing (`vault_arch`).
    """
    from vault_lib import resolver_wikilink

    indice = _indice_del_vault()
    propias = {n["path"] for n in proposals}
    fecha = utcnow()[:10]
    filas: List[Dict[str, Any]] = []
    vistas: Set[str] = set()
    candidatas = [(e, resolver_concepto(e, indice))
                  for clase in CLASES_DE_CONCEPTO for e in entities[clase]]
    candidatas += [(w, resolver_wikilink(w, None, indice)[1]) for w in entities["wikilinks"]]
    for entidad, rutas in candidatas:
        if len(rutas) != 1 or rutas[0] in propias or rutas[0] in vistas:
            continue
        menciones = [n["path"] for n in proposals if entidad in n["content"]] or \
            [n["path"] for n in proposals]
        texto = (f"- Ingesta {fecha} desde `{source}`: menciona **{entidad}** en "
                 + ", ".join(_wikilink_de(p) for p in menciones))
        vistas.add(rutas[0])
        filas.append({
            "path": rutas[0],
            "entity": entidad,
            "section": SECCION_DE_MENCIONES,
            "append": texto,
            "command": ["vault_append", "--path", rutas[0], "--section",
                        SECCION_DE_MENCIONES, "--content", texto],
        })
    return filas


def _aplicar_paginas(paginas: List[Dict[str, Any]]) -> bool:
    """Apply each proposed append through the port; True only if all applied.

    `vault_append` appends under the note's lock and never rewrites what is
    there. A row that fails keeps `applied: false` and the owner's error code;
    a missing producer is said once per row, not hidden (AP-51).
    """
    if not paginas:
        return False
    from vault.runtime import bitacora_de_cambios

    try:
        bitacora = bitacora_de_cambios()
    except Exception as exc:
        bitacora, motivo = None, f"bitacora_cambios ({type(exc).__name__})"
    else:
        motivo = "nadie atiende el puerto bitacora_cambios: no se aplicó"
    for fila in paginas:
        if bitacora is None:
            fila.update(applied=False, error=motivo)
            continue
        try:
            r = bitacora.anexar(fila["path"], fila["append"], fila["section"], False)
        except Exception as exc:
            fila.update(applied=False, error=f"bitacora_cambios ({type(exc).__name__})")
            continue
        if isinstance(r, dict) and r.get("ok"):
            fila["applied"] = True
        else:
            codigo = r.get("error_code") if isinstance(r, dict) else None
            fila.update(applied=False, error=codigo or "vault_append rechazó el anexo")
    return all(f.get("applied") for f in paginas)


def _notas_del_paquete(pack: Dict[str, Any]) -> List[str]:
    """The pack's included notes that exist in this vault, in pack order."""
    rutas: List[str] = []
    for fila in pack.get("included") or []:
        ruta = fila.get("path") if isinstance(fila, dict) else None
        if not isinstance(ruta, str) or not ruta.endswith(".md"):
            continue
        destino = _raiz() / ruta
        try:
            assert_within_vault(destino, _raiz())
        except ValueError:
            continue
        if destino.is_file() and ruta not in rutas:
            rutas.append(ruta)
    return rutas


def _archivar(rel: str, contenido: str) -> Dict[str, Any]:
    """Write the raw source once. Same lock and same never-overwrite rule as
    the derived notes: the name is content-addressed, so an existing file is
    this same source archived before, not something to replace."""
    full = _raiz() / rel
    try:
        assert_within_vault(full, _raiz())
    except ValueError as exc:
        return {"written": False, "failed": str(exc)}
    full.parent.mkdir(parents=True, exist_ok=True)
    lock = tomar_lock(full, _LOCK_TIMEOUT)
    if lock is None:
        return {"written": False,
                "failed": "NOTE_LOCKED: otro escritor tiene la fuente; no se archivó"}
    with lock:
        if full.exists():
            return {"written": False, "reason": "ya existe"}
        try:
            atomic_write_text(full, contenido)
        except OSError as exc:
            return {"written": False, "failed": f"{type(exc).__name__}: {exc}"}
    update_section_index(rel.split("/", 1)[0])
    return {"written": True}


def _build_note(
    chunk: Dict[str, str],
    entities: Dict[str, List[str]],
    section: str,
    subfolder: Optional[str],
    source: str,
    origin: str,
    agent: str,
    extra_tags: List[str],
    fuente_archivada: Optional[str] = None,
    citadas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    title = chunk["title"]
    slug = slugify(title)
    rel_folder = f"{section}/{subfolder}" if subfolder else section
    rel_path = f"{rel_folder}/{slug}.md"

    # AP-26: tags obligatorios. 'ingested' es el marcador que permite auditar
    # después todo lo que entró por esta vía y revisarlo en bloque.
    tags = sorted({"ingested", origin, *extra_tags, *entities["tags"][:5]})
    # Un borrador guardado desde un paquete cita lo que el paquete incluyó: esa
    # es su procedencia, no las entidades del texto de la respuesta.
    related = ([c[:-3] for c in citadas] if citadas is not None
               else entities["wikilinks"][:10])

    # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
    # Los instantes van con `texto=True` porque esta nota siempre los citó: el
    # lector recibe `str`, y pasarlos a crudo le cambiaría el tipo.
    frontmatter = [
        Frontmatter()
        .set("title", title, texto=True)
        .set("id", str(uuid.uuid4()))
        .set("type", "ingested")
        .set("status", "draft")  # nunca 'active': lo ingerido se revisa antes de valer
        .set("tags", tags)
        .set("related", related)
        .set("createdAt", utcnow(), texto=True)
        .set("updatedAt", utcnow(), texto=True)
        # With the raw layer on, `source` is the archived original as a
        # wikilink (Karpathy L1): the note can be traced to what it came from
        # inside the vault, not to a path on someone's disk.
        .set("source", _wikilink_de(fuente_archivada) if fuente_archivada else source,
             texto=True)
        # AP-56: ni `origin` ni `agent` son valores controlados por esta tool
        # —vienen del invocante—, y un `agent: si: claro` rompía el YAML de la
        # nota entera.
        .set("ingest_origin", origin, texto=True)
        # AP-30 se cumple aquí, y por eso `vault_ingest` la aplica en vez de
        # solo detectarla: la tríada CIA se escribe en el mismo acto que crea la
        # nota, así que por esta vía no puede entrar una nota sin clasificar.
        # Integridad baja mientras no se revise: el rerank de context_pack la
        # ordenará por detrás del conocimiento verificado, que es lo correcto.
        .set("cia_integrity", "low")
        .set("cia_availability", "medium")
        .set("cia_sensitivity", "internal")
        .set("agent", agent, texto=True)
        .render()
    ]

    body = [f"# {title}", "", chunk["body"].strip(), ""]
    if citadas is not None:
        body += ["## Notas del paquete", ""] + [f"- {_wikilink_de(c)}" for c in citadas] + [""]
    elif related:
        body += ["## Relacionado", ""] + [f"- [[{r}]]" for r in related] + [""]
    body += ["## Procedencia", "",
             f"- Origen: `{origin}`", f"- Fuente: `{source}`"]
    if fuente_archivada:
        body.append(f"- Fuente archivada: {_wikilink_de(fuente_archivada)}")
    body += ["- Estado: `draft` — requiere revisión antes de darse por válido", ""]

    return {
        "path": rel_path,
        "title": title,
        "tags": tags,
        "related": related,
        "chars": len(chunk["body"]),
        "content": "\n".join(frontmatter) + "\n\n" + "\n".join(body),
    }


def vault_ingest(
    text: str,
    section: str,
    source: str,
    origin: str,
    subfolder: Optional[str] = None,
    commit: bool = False,
    max_notes: int = DEFAULT_MAX_NOTES,
    tags: Optional[List[str]] = None,
    agent: Optional[str] = None,
    archivar_fuente: bool = False,
    pack: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ingiere un texto y propone (o escribe) las notas derivadas.

    `archivar_fuente` keeps the verbatim source in `10_Migrated/fuentes/` and
    links each derived note to it (Karpathy's raw layer). `pack` is a
    `vault_context_pack` envelope: the text is then the answer to its query and
    becomes ONE draft that cites the pack's notes (saving answers back).
    """
    text = text or ""
    if not text.strip():
        return {"ok": False, "error_code": "EMPTY_SOURCE",
                "error": "La fuente no contiene texto"}
    if archivar_fuente:
        motivo = _motivo_para_no_archivar(text, source, origin)
        if motivo:
            return emit_error("vault_ingest", "INVALID_INPUT", motivo)

    section = section.strip("/")
    if section in FORBIDDEN_SECTIONS:
        return {
            "ok": False,
            "error_code": "FORBIDDEN_SECTION",
            "error": f"'{section}' no admite ingesta: es sección generada o de otra tool",
            "forbidden": sorted(FORBIDDEN_SECTIONS),
        }

    # CN-02 con el criterio del dueño, el mismo que `vault_write`. Hasta v41.2
    # se comparaba con `standard_folders()` y una sección propia dada de alta
    # con `vault_section --add` devolvía UNKNOWN_SECTION: admitía notas por
    # una tool de escritura y no por la otra.
    try:
        from vault_registry import motivo_de_destino_invalido, secciones_del_vault

        motivo = motivo_de_destino_invalido(section, _raiz())
        if motivo:
            return {"ok": False, "error_code": "UNKNOWN_SECTION",
                    "error": (f"CN-02: --section {section!r}: {motivo}. Las secciones del "
                              "vault las enseña vault_section --list; una propia se "
                              "declara con vault_section --add"),
                    "valid": [s for s in secciones_del_vault(_raiz())
                              if s not in FORBIDDEN_SECTIONS
                              and motivo_de_destino_invalido(s, _raiz()) is None]}
    except ImportError:
        pass
    except ValueError as exc:
        # Un `secciones.json` ilegible no se lee como «no hay propias» (AP-51).
        return {"ok": False, "error_code": "DATA_FILE_CORRUPT", "error": str(exc)}

    # ── etapa 1: pre-vuelo, obligatorio ──────────────────────────────────────
    preflight = _preflight(text, source)
    if not preflight["ok"]:
        return {
            "ok": False,
            "error_code": "POISON_DETECTED",
            "error": "La fuente contiene patrones de inyección; no se ingirió nada",
            "preflight": preflight,
            "note": "Este bloqueo no es desactivable por diseño",
        }

    # AP-16: atribución. Lo ingerido debe poder rastrearse hasta quién lo trajo.
    agent = agent or _env("VAULT_AGENT")
    if not agent:
        return {
            "ok": False, "error_code": "missing_agent", "norm_code": "AP-16",
            "error": "missing_agent",
            "message": "AP-16: usa --agent <nombre> o exporta VAULT_AGENT.",
        }

    # ── etapa 2: segmentación y entidades ────────────────────────────────────
    citadas: Optional[List[str]] = None
    if pack is not None:
        # A saved answer is one page: segmenting it would split the synthesis
        # the agent just wrote. Its provenance is the pack, so the pack's
        # notes have to exist here; citing nothing is not a synthesis.
        citadas = _notas_del_paquete(pack)
        if not citadas:
            return emit_error(
                "vault_ingest", "INVALID_INPUT",
                "--desde-pack: el paquete no incluye ninguna nota de este vault; "
                "genera el paquete con vault_context_pack sobre el mismo vault")
        consulta = str(pack.get("query") or "").strip() or _derive_title(text)
        chunks = [{"title": f"Síntesis: {consulta}"[:120], "body": text.strip()}]
    else:
        chunks = _segment(text)
    if not chunks:
        return {"ok": False, "error_code": "NO_CONTENT",
                "error": f"Ningún bloque supera {MIN_CHUNK_CHARS} caracteres útiles"}

    truncated = len(chunks) > max_notes
    chunks = chunks[:max_notes]
    entities = _extract_entities(text)
    fuente_archivada = (_ruta_de_fuente_archivada(text, source, origin)
                        if archivar_fuente else None)

    proposals: List[Dict[str, Any]] = []
    seen_paths: Set[str] = set()
    for chunk in chunks:
        note = _build_note(chunk, entities, section, subfolder, source, origin,
                           agent, tags or [], fuente_archivada=fuente_archivada,
                           citadas=citadas)
        # Dos encabezados iguales producirían el mismo slug y una nota
        # sobrescribiría a la otra en silencio. El sufijo se busca libre: el
        # de `len(seen_paths)` sin recomprobar podía caer sobre una ruta ya
        # propuesta («Alfa 2», «Alfa», «Alfa» → dos `alfa-2`) (AP-18).
        if note["path"] in seen_paths:
            base, ext = note["path"].rsplit(".", 1)
            n = 1
            while f"{base}-{n}.{ext}" in seen_paths:
                n += 1
            note["path"] = f"{base}-{n}.{ext}"
        seen_paths.add(note["path"])
        proposals.append(note)

    # Affected pages are enrichment: an unreadable section registry must not
    # turn an ingest into a standard section into a failure (the write path
    # still refuses the own-section targets it cannot verify).
    from vault.kernel.fallos import FalloDeDominio

    paginas_omitidas: Optional[str] = None
    try:
        paginas = _paginas_afectadas(entities, proposals, source)
    except FalloDeDominio as exc:
        paginas, paginas_omitidas = [], exc.causa

    # ── etapa 3: escritura, solo si se pidió ─────────────────────────────────
    written: List[str] = []
    skipped: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []
    archivo: Optional[Dict[str, Any]] = (
        {"path": fuente_archivada, "written": False} if fuente_archivada else None)
    if commit and archivo is not None:
        archivo.update(_archivar(fuente_archivada, _nota_de_fuente(text, source, origin, agent)))
        if archivo.get("failed"):
            failed.append({"path": fuente_archivada, "reason": archivo["failed"]})
    if commit:
        for note in proposals:
            full = _raiz() / note["path"]
            try:
                assert_within_vault(full, _raiz())
            except ValueError as exc:
                skipped.append({"path": note["path"], "reason": str(exc)})
                continue
            if full.exists():
                # Nunca se pisa una nota existente: lo ingerido es material sin
                # revisar y no puede sustituir a lo que ya está en el vault.
                skipped.append({"path": note["path"], "reason": "ya existe"})
                continue
            full.parent.mkdir(parents=True, exist_ok=True)
            # F1: el `exists()` de arriba y la escritura no eran atómicos. Un
            # `vault_write` —que escribe bajo el lock de la nota— o una segunda
            # ingesta que creara la misma ruta entre medias quedaba pisada con
            # material sin revisar. Se toma el mismo lock y se vuelve a mirar.
            lock = tomar_lock(full, _LOCK_TIMEOUT)
            if lock is None:
                failed.append({"path": note["path"],
                               "reason": "NOTE_LOCKED: otro escritor tiene la nota; no se escribió"})
                continue
            with lock:
                if full.exists():
                    skipped.append({"path": note["path"], "reason": "ya existe"})
                    continue
                try:
                    atomic_write_text(full, note["content"])
                except OSError as exc:
                    # Una excepción en la nota k dejaba en disco las k-1 anteriores
                    # **y** se llevaba por delante el `update_section_index`: el vault
                    # quedaba con notas que ningún índice mencionaba, y la tool no
                    # devolvía ninguna de las dos cosas. Aquí el fallo de una nota es
                    # una fila del informe (`failed`), no la desaparición del lote.
                    failed.append({"path": note["path"], "reason": f"{type(exc).__name__}: {exc}"})
                    continue
            written.append(note["path"])
        # Fuera del bucle y sin condicionar a que no hubiera fallos: si se
        # escribió aunque sea una, el índice tiene que reflejarlo.
        if written:
            update_section_index(section)

    aplicadas = False
    registro: Dict[str, Any] = {}
    if commit:
        # Karpathy's ingest touches the pages it affects: applied only with
        # --commit, through the port (owner `vault_append`, never overwrites).
        aplicadas = _aplicar_paginas(paginas)
        # One `ingested` row per pass that wrote something. A pass that only
        # skipped existing notes changed nothing, and logs nothing.
        if written or (archivo or {}).get("written"):
            from vault.runtime import anotar_operacion

            registro = anotar_operacion(
                "ingested", section,
                f"vault_ingest: {len(written)} nota(s) desde {origin}", agent)

    return {
        # No `True` fijo: un lote con notas caídas no es un éxito, y devolverlo
        # como tal presentaba el fallo de la tool como ausencia en el dato (AP-51).
        "ok": not failed,
        "committed": commit,
        "failed": failed,
        "source": source,
        "origin": origin,
        "section": section,
        "preflight": {"findings": preflight["findings"], "blocking": []},
        "entities": entities,
        "proposed": [{k: v for k, v in n.items() if k != "content"} for n in proposals],
        "written": written,
        "skipped": skipped,
        "archived_source": archivo,
        # Dry-run: proposals, each with the `vault_append` that applies it.
        # --commit: applied through the port; each row says `applied`, and this
        # flag is true only when every proposal was appended. Never an
        # overwrite; an ambiguous name proposes nothing.
        "affected_pages": paginas,
        "affected_pages_applied": aplicadas,
        **({"affected_pages_skipped": paginas_omitidas} if paginas_omitidas else {}),
        # `change_log` ({id, action}) or `change_log_error` (sanitized).
        **registro,
        "stats": {
            "chars": len(text),
            "chunks": len(proposals),
            "truncated": truncated,
            "entity_count": sum(len(v) for v in entities.values()),
        },
        "hint": None if commit else "Revisa `proposed` y repite con --commit para escribir",
    }


def _leer_pack(ruta: str) -> Dict[str, Any]:
    """The `vault_context_pack` envelope saved by the agent, or an error."""
    path = Path(ruta).expanduser()
    if not path.is_file():
        return emit_error("vault_ingest", "FILE_NOT_FOUND", f"--desde-pack: no existe {ruta}")
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return emit_error("vault_ingest", "JSON_PARSE_ERROR",
                          f"--desde-pack: no es un JSON legible: {type(exc).__name__}")
    if not isinstance(datos, dict) or datos.get("ok") is not True             or not isinstance(datos.get("included"), list):
        return emit_error("vault_ingest", "INVALID_INPUT",
                          "--desde-pack: se espera el envelope ok de vault_context_pack "
                          "con su lista `included`")
    return datos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_ingest — ingesta gobernada con pre-vuelo anti-poison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Propuesta (no escribe nada)
  python vault_ingest.py --file notas-reunion.md --section 07_Knowledge

  # Escribir de verdad
  python vault_ingest.py --file notas-reunion.md --section 07_Knowledge --commit

  # Desde una conversacion por stdin
  cat conversacion.txt | python vault_ingest.py --stdin --section 04_Sessions

  # Desde una URL (red apagada por defecto)
  python vault_ingest.py --url https://ejemplo/doc --section 07_Knowledge --allow-network

  # Capa cruda: guarda la fuente literal en 10_Migrated/fuentes/ y la cita
  python vault_ingest.py --file notas-reunion.md --section 07_Knowledge --archivar-fuente --commit

  # Guardar una buena respuesta como borrador que cita el paquete de contexto
  python vault_ingest.py --text "<respuesta>" --section 07_Knowledge --desde-pack pack.json --commit

Notas:
  - Dry-run por defecto: escribir exige --commit
  - El pre-vuelo anti-poison NO es desactivable
  - Las notas entran con status: draft y cia_integrity: low hasta revisarse
  - Nunca sobrescribe una nota existente
  - AP-16: requiere --agent o VAULT_AGENT
  - --archivar-fuente no declara inmutable 10_Migrated: eso lo decide el dueño
  - Las paginas existentes que nombra la fuente se PROPONEN (affected_pages);
    se aplican con el vault_append que trae cada propuesta
""",
        allow_abbrev=False,
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", help="Fichero de origen")
    source_group.add_argument("--text", help="Texto literal")
    source_group.add_argument("--stdin", action="store_true", help="Lee de stdin")
    source_group.add_argument("--url", help="URL http(s) (requiere --allow-network)")

    parser.add_argument("--section", required=True,
                        help="Sección destino (ej. 07_Knowledge)")
    parser.add_argument("--subfolder", help="Subcarpeta dentro de la sección")
    parser.add_argument("--commit", action="store_true",
                        help="Escribe de verdad (por defecto es dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Explícito; es el comportamiento por defecto")
    parser.add_argument("--max-notes", type=int, default=DEFAULT_MAX_NOTES,
                        help=f"Tope de notas derivadas (default: {DEFAULT_MAX_NOTES})")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=("Tope de caracteres de la fuente, igual para "
                              f"--file/--stdin/--text/--url (default: "
                              f"{DEFAULT_MAX_CHARS})"))
    parser.add_argument("--tags", nargs="*", help="Tags adicionales")
    parser.add_argument("--allow-network", action="store_true",
                        help="Permite descargar --url")
    parser.add_argument("--agent", help="Agente que ejecuta (AP-16)")
    parser.add_argument("--archivar-fuente", action="store_true",
                        help=("Guarda la fuente literal en 10_Migrated/fuentes/ y "
                              "enlaza las notas con source: [[...]] (solo texto, AP-15)"))
    parser.add_argument("--desde-pack", metavar="PACK_JSON",
                        help=("Envelope de vault_context_pack: el texto es la respuesta "
                              "a su consulta y se guarda como UN borrador que cita sus notas"))

    args = parser.parse_args()

    source = _check_size(_read_source(args), args.max_chars)
    if not source.get("ok"):
        source = completar_envelope("vault_ingest", source)
        print(json.dumps(source, indent=2, ensure_ascii=False))
        return 1

    pack = None
    if args.desde_pack:
        pack = _leer_pack(args.desde_pack)
        if not pack.get("ok"):
            print(json.dumps(completar_envelope("vault_ingest", pack), indent=2,
                             ensure_ascii=False))
            return 1

    result = vault_ingest(
        text=source["text"], section=args.section,
        source=args.desde_pack if pack else source["source"],
        origin="pack" if pack else source["origin"], subfolder=args.subfolder,
        commit=args.commit and not args.dry_run, max_notes=args.max_notes,
        tags=args.tags, agent=args.agent,
        archivar_fuente=args.archivar_fuente, pack=pack,
    )
    # D5: un solo sitio lleva los envelopes a mano a la forma canónica.
    result = completar_envelope("vault_ingest", result)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ingest"))
