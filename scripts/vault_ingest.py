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

from cli import safety  # noqa: E402

from vault_errors import wrap_main  # noqa: E402
from vault_io import (  # noqa: E402
    assert_within_vault,
    atomic_write_text,
    update_section_index,
)
from vault_lib import slugify, strip_code_blocks, utcnow, yaml_scalar  # noqa: E402

# Secciones que esta tool NO puede alimentar: son artefactos generados o
# propiedad exclusiva de otras tools. Ingerir texto libre ahí rompería la
# regla de un-solo-dueño-por-carpeta de vault_registry.
FORBIDDEN_SECTIONS = frozenset({"00_System", "99_Index", "17_Preferences"})

MIN_CHUNK_CHARS = 120
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

# Ruido léxico frecuente en texto técnico que pasa el filtro de mayúsculas sin
# ser una entidad del dominio.
_ENTITY_STOPWORDS = {
    "The", "This", "That", "These", "Those", "There", "When", "Where", "What",
    "With", "From", "Para", "Este", "Esta", "Estos", "Cuando", "Donde", "Como",
    "Nota", "Note", "Ver", "See", "TODO", "FIXME", "OK",
}



sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402


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
        heading = re.match(r"^(#{1,3})\s+(.+?)\s*#*$", line)
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


def _extract_entities(text: str) -> Dict[str, List[str]]:
    """Extracción determinista: solo lo que el propio texto marca como entidad.

    No se infiere nada por semejanza. Un falso positivo aquí acaba siendo un
    wikilink roto o una nota fantasma, que es peor que no extraer.
    """
    # El wikilink dentro de un fence es código que el texto enseña, no un
    # destino: Obsidian no lo resuelve. Extraerlo de ahí convertía un
    # `[[ejemplo]]` de documentación en un enlace real en `related:` y en el
    # cuerpo, es decir, en una nota fantasma creada por la propia ingesta.
    # El dueño del criterio es `vault_lib.strip_code_blocks` (AP-57).
    sin_codigo = strip_code_blocks(text)
    wikilinks = re.findall(r"\[\[([^\]|#]+)", sin_codigo)
    tags = re.findall(r"(?<!\w)#([A-Za-z][\w/-]{1,30})", text)
    urls = re.findall(r"https?://[^\s<>()\"']+", text)
    code = re.findall(r"`([A-Za-z_][\w.]{2,40})`", text)
    paths = re.findall(r"\b[\w./-]+\.(?:md|py|js|ts|json|yaml|yml)\b", text)

    # Nombres propios: dos o más palabras capitalizadas seguidas. Con una sola
    # el ruido supera la señal, así que se descartan.
    proper = [
        m for m in re.findall(r"\b(?:[A-Z][a-z]{2,}\s){1,3}[A-Z][a-z]{2,}\b", text)
        if m.split()[0] not in _ENTITY_STOPWORDS
    ]
    # Siglas técnicas: 2–6 mayúsculas (MCP, ADR, HTTP, CIA).
    acronyms = [a for a in re.findall(r"\b[A-Z]{2,6}\b", text)
                if a not in _ENTITY_STOPWORDS]

    def dedup(items: List[str], limit: int) -> List[str]:
        return list(dict.fromkeys(i.strip() for i in items if i.strip()))[:limit]

    return {
        "wikilinks": dedup(wikilinks, 30),
        "tags": dedup([t.lower() for t in tags], 20),
        "urls": dedup(urls, 20),
        "code_refs": dedup(code, 20),
        "paths": dedup(paths, 20),
        "proper_nouns": dedup(proper, 20),
        "acronyms": dedup(acronyms, 20),
    }


def _build_note(
    chunk: Dict[str, str],
    entities: Dict[str, List[str]],
    section: str,
    subfolder: Optional[str],
    source: str,
    origin: str,
    agent: str,
    extra_tags: List[str],
) -> Dict[str, Any]:
    title = chunk["title"]
    slug = slugify(title)
    rel_folder = f"{section}/{subfolder}" if subfolder else section
    rel_path = f"{rel_folder}/{slug}.md"

    # AP-26: tags obligatorios. 'ingested' es el marcador que permite auditar
    # después todo lo que entró por esta vía y revisarlo en bloque.
    tags = sorted({"ingested", origin, *extra_tags, *entities["tags"][:5]})
    related = entities["wikilinks"][:10]

    frontmatter = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"id: {uuid.uuid4()}",
        "type: ingested",
        "status: draft",  # nunca 'active': lo ingerido se revisa antes de valer
        f"tags: {json.dumps(tags, ensure_ascii=False)}",
        f"related: {json.dumps(related, ensure_ascii=False)}",
        f'createdAt: "{utcnow()}"',
        f'updatedAt: "{utcnow()}"',
        f"source: {json.dumps(source, ensure_ascii=False)}",
        # AP-56: ni `origin` ni `agent` son valores controlados por esta tool
        # —vienen del invocante—, y un `agent: si: claro` rompía el YAML de la
        # nota entera. `yaml_scalar` solo cita cuando el parser real no
        # devolvería el mismo texto.
        f"ingest_origin: {yaml_scalar(origin)}",
        # AP-30 se cumple aquí, y por eso `vault_ingest` la aplica en vez de
        # solo detectarla: la tríada CIA se escribe en el mismo acto que crea la
        # nota, así que por esta vía no puede entrar una nota sin clasificar.
        # Integridad baja mientras no se revise: el rerank de context_pack la
        # ordenará por detrás del conocimiento verificado, que es lo correcto.
        "cia_integrity: low",
        "cia_availability: medium",
        "cia_sensitivity: internal",
        f"agent: {yaml_scalar(agent)}",
        "---",
    ]

    body = [f"# {title}", "", chunk["body"].strip(), ""]
    if related:
        body += ["## Relacionado", ""] + [f"- [[{r}]]" for r in related] + [""]
    body += ["## Procedencia", "",
             f"- Origen: `{origin}`", f"- Fuente: `{source}`",
             "- Estado: `draft` — requiere revisión antes de darse por válido", ""]

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
) -> Dict[str, Any]:
    """Ingiere un texto y propone (o escribe) las notas derivadas."""
    text = text or ""
    if not text.strip():
        return {"ok": False, "error_code": "EMPTY_SOURCE",
                "error": "La fuente no contiene texto"}

    section = section.strip("/")
    if section in FORBIDDEN_SECTIONS:
        return {
            "ok": False,
            "error_code": "FORBIDDEN_SECTION",
            "error": f"'{section}' no admite ingesta: es sección generada o de otra tool",
            "forbidden": sorted(FORBIDDEN_SECTIONS),
        }

    try:
        from vault_registry import standard_folders

        if section not in standard_folders():
            return {"ok": False, "error_code": "UNKNOWN_SECTION",
                    "error": f"'{section}' no es una sección del estándar",
                    "valid": list(standard_folders())}
    except ImportError:
        pass

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
    chunks = _segment(text)
    if not chunks:
        return {"ok": False, "error_code": "NO_CONTENT",
                "error": f"Ningún bloque supera {MIN_CHUNK_CHARS} caracteres útiles"}

    truncated = len(chunks) > max_notes
    chunks = chunks[:max_notes]
    entities = _extract_entities(text)

    proposals: List[Dict[str, Any]] = []
    seen_paths: Set[str] = set()
    for chunk in chunks:
        note = _build_note(chunk, entities, section, subfolder, source, origin,
                           agent, tags or [])
        # Dos encabezados iguales producirían el mismo slug y una nota
        # sobrescribiría a la otra en silencio.
        if note["path"] in seen_paths:
            base, ext = note["path"].rsplit(".", 1)
            note["path"] = f"{base}-{len(seen_paths)}.{ext}"
        seen_paths.add(note["path"])
        proposals.append(note)

    # ── etapa 3: escritura, solo si se pidió ─────────────────────────────────
    written: List[str] = []
    skipped: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []
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
        "stats": {
            "chars": len(text),
            "chunks": len(proposals),
            "truncated": truncated,
            "entity_count": sum(len(v) for v in entities.values()),
        },
        "hint": None if commit else "Revisa `proposed` y repite con --commit para escribir",
    }


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

Notas:
  - Dry-run por defecto: escribir exige --commit
  - El pre-vuelo anti-poison NO es desactivable
  - Las notas entran con status: draft y cia_integrity: low hasta revisarse
  - Nunca sobrescribe una nota existente
  - AP-16: requiere --agent o VAULT_AGENT
""",
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

    args = parser.parse_args()

    source = _check_size(_read_source(args), args.max_chars)
    if not source.get("ok"):
        print(json.dumps(source, indent=2, ensure_ascii=False))
        return 1

    result = vault_ingest(
        text=source["text"], section=args.section, source=source["source"],
        origin=source["origin"], subfolder=args.subfolder,
        commit=args.commit and not args.dry_run, max_notes=args.max_notes,
        tags=args.tags, agent=args.agent,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ingest"))
