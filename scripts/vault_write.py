#!/usr/bin/env python3

"""

Vault Write Tool — Core writing tool for Obsidian vault



Creates or updates any note with correct YAML frontmatter.

Implements versioning: copies previous version to .history/ before overwriting.

Updates search-index.json automatically.



Usage:

    python vault_write.py --folder "01_Projects/ans" --title "Status" --content "# Status\n\n..."

    python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags "architecture,backend" --meta '{"status": "accepted"}'

"""

import argparse

import json

import os

import re

import shutil

import sys

import vault_tags
from vault_errors import wrap_main

from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    atomic_update_json,
    assert_within_vault,
    normalize_stem,
    file_lock,
)
from vault_encoding import (
    sanitize_content,
    normalize_to_nfc,
    sanitize_filename,
    detect_issues,
)
from vault_regex import (
    detect_bracket_anomalies,
    detect_path_anchored,
    fix_nested_brackets,
    fix_whitespace_in_links,
    WIKILINK_MAX_LEN,
)
from vault_lib import (
    yaml_scalar,
    utcnow,
    strip_code_blocks,
    Config,
    parse_frontmatter_with_body,
    canonical_utc,
)
from vault_norms import (
    compute_norm_refs,
    normalize_status,
    STATUS_VOCAB,
    STATUS_TRANSITIONS,
)
from datetime import datetime, timezone

import uuid

from pathlib import Path

from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _history_dir() -> Path:
    return _repo().dir_historial


def _index_file() -> Path:
    return _repo().indice_busqueda


def _tag_registry() -> Path:
    return _repo().registro_etiquetas


def _check_content_gate(content: str, folder: str) -> bool:
    """Return True if content passes the strict content gate. 00_System is exempt.

    The gate requires:
    - ≥ 3 real lines (excluding blank, TODO-only, lone-dashes, lone-headings)
    - ≥ 10 real words across those lines (reject lorem-ipsum stubs and 1-word lines)
    - No line longer than 800 chars (reject minified blobs that hide emptiness)
    - Bracket balance: opens == closes for [[...]] (AP-24 prevention)
    - No empty [[]] wiki-links (AP-22 prevention, mild)

    Previous version (3 real lines) allowed trivial notes like:
        "ok
        test
        done"
    which produce orphan/empty notes that pollute the search index.
    """
    if folder.startswith("00_System"):
        return True
    real_lines = [
        l
        for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]
    if len(real_lines) < 3:
        return False
    # Word count: split on whitespace, ignore markdown markers and pipes
    words: List[str] = []
    for line in real_lines:
        # strip heading markers, bullets, table pipes
        cleaned = re.sub(r"^[#\-\*\s|>]+", "", line)
        for tok in cleaned.split():
            tok = tok.strip("`*~_[]()#").strip(".,;:!?")
            if tok and len(tok) > 1:
                words.append(tok)
    if len(words) < 10:
        return False
    # Reject minified blobs
    if any(len(l) > 800 for l in real_lines):
        return False
    # AP-21 prevention: reject path-anchored wiki-links [[folder/note]]
    path_anchored = detect_path_anchored(content)
    if path_anchored:
        return False

    # AP-24 prevention: detect bracket anomalies (nested, mixed, etc)
    anomalies = detect_bracket_anomalies(content)
    if anomalies:
        # Try auto-fix first
        fixed_content = fix_nested_brackets(content)
        fixed_content = fix_whitespace_in_links(fixed_content)
        # Check again after auto-fix
        remaining = detect_bracket_anomalies(fixed_content)
        # Filter out empty links (handled separately)
        remaining_non_empty = [r for r in remaining if r["type"] != "empty"]
        if remaining_non_empty:
            return False

    # AP-22 prevention (soft): reject notes with empty [[]] wiki-links.
    # These pass the strict gate otherwise but pollute the search index with
    # literal `[[]]` as text. Allow them only in spec/example documentation
    # where they're meaningful; for regular notes, reject.
    if folder.startswith("00_System"):
        return True
    clean = strip_code_blocks(content)
    if re.search(r"\[\[\s*\]\]", clean):
        return False
    return True


def _content_gate_reason(content: str, folder: str) -> Optional[str]:
    """Return human-readable reason why content failed the gate, or None if it passes."""
    if folder.startswith("00_System"):
        return None
    real_lines = [
        l
        for l in content.split("\n")
        if l.strip()
        and not l.strip().startswith("TODO")
        and l.strip() not in ("-", "- ", "---")
        and not re.match(r"^#+\s*$", l.strip())
    ]
    if len(real_lines) < 3:
        return f"only {len(real_lines)} real line(s) (need ≥3)"
    words: List[str] = []
    for line in real_lines:
        cleaned = re.sub(r"^[#\-\*\s|>]+", "", line)
        for tok in cleaned.split():
            tok = tok.strip("`*~_[]()#").strip(".,;:!?")
            if tok and len(tok) > 1:
                words.append(tok)
    if len(words) < 10:
        return f"only {len(words)} real word(s) (need ≥10)"
    if any(len(l) > 800 for l in real_lines):
        return "line longer than 800 chars (minified blob?)"

    # AP-21: path-anchored wiki-links check
    path_anchored = detect_path_anchored(content)
    if path_anchored:
        return f"AP-21: path-anchored wiki-links detected: {path_anchored}. Use [[note-name]] without folder path."

    # AP-24 / AP-22 reasons — checked AFTER basic quality gates
    # First try auto-fix
    fixed_content = fix_nested_brackets(content)
    fixed_content = fix_whitespace_in_links(fixed_content)

    # Check for remaining anomalies
    anomalies = detect_bracket_anomalies(fixed_content)
    if anomalies:
        empty_anomalies = [a for a in anomalies if a["type"] == "empty"]
        non_empty_anomalies = [a for a in anomalies if a["type"] != "empty"]

        if non_empty_anomalies:
            examples = [a["example"] for a in non_empty_anomalies[:3]]
            return f"AP-24: bracket anomalies detected: {examples}. These will be auto-fixed on save."

    # Check empty links
    clean = strip_code_blocks(content)
    if re.search(r"\[\[\s*\]\]", clean):
        n = len(re.findall(r"\[\[\s*\]\]", clean))
        return (
            f"AP-22: {n} empty `[[]]` wiki-link(s). "
            "Empty wiki-links pollute the search index — remove them or replace with real targets."
        )
    return None


# Configuration


def _tag_suggestions(new_tags: List[str]) -> List[Dict[str, Any]]:
    """Return canonical similar tags for any new_tags not yet in registry. Non-blocking."""

    if not _tag_registry().exists():
        return []

    # AP-39 — leía `registry["tags"]`, una clave que el registro no tiene desde
    # que las facetas viven en `canonical_tags`. La sugerencia llevaba versiones
    # sin dispararse nunca, y por eso inventar un tag no costaba nada.
    canonical: set = set(vault_tags.canonical_tags())

    suggestions = []

    for tag in new_tags:
        if tag in canonical:
            continue

        for candidate in canonical:
            # simple similarity: exact prefix/substring

            a, b = tag.lower(), candidate.lower()

            if a == b:
                continue

            if a in b or b in a:
                score = 0.85

            else:
                common_prefix = sum(1 for x, y in zip(a, b) if x == y)

                if common_prefix >= 3:
                    score = 0.6 + (common_prefix / max(len(a), len(b))) * 0.2

                else:
                    score = sum(1 for x, y in zip(a, b) if x == y) / max(len(a), len(b))

            if score >= 0.6:
                suggestions.append(
                    {
                        "new_tag": tag,
                        "similar_canonical": candidate,
                        "score": round(score, 2),
                    }
                )

    return sorted(suggestions, key=lambda x: -x["score"])[:10]


def slugify(title: str) -> str:
    """Convert title to kebab-case filename.

    Uses vault_encoding.sanitize_filename for cross-platform safety.
    """
    # Use the encoding module's sanitize_filename for proper handling
    # of Unicode, invisible chars, and cross-platform compatibility
    return sanitize_filename(title, max_length=200)


def _check_bracket_balance(content: str) -> Optional[str]:
    """AP-22: detect unbalanced [[ ]] brackets outside code blocks."""
    clean = strip_code_blocks(content)
    opens = len(re.findall(r"\[\[", clean))

    closes = len(re.findall(r"\]\]", clean))

    if opens != closes:
        return f"AP-22: corchetes desbalanceados — {opens} '[[' vs {closes} ']]'"

    empty = re.findall(r"\[\[\s*\]\]", clean)

    if empty:
        return f"AP-22: wiki-links vacios detectados: {empty[:3]}"

    return None


def _collect_ghost_links(wiki_links: List[str]) -> List[str]:
    """Return links whose target note does not exist anywhere in the vault (non-blocking)."""

    all_stems = {
        normalize_stem(p.stem)
        for p in _raiz().rglob("*.md")
        if ".history" not in str(p)
    }

    ghost = []

    for link in wiki_links:
        stem = link.split("|")[0].strip()
        if normalize_stem(stem) not in all_stems:
            ghost.append(link)

    return ghost


def generate_frontmatter(
    title: str,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
    existing_id: Optional[str] = None,
    existing_created: Optional[str] = None,
    norm_refs: Optional[List[str]] = None,
    folder: str = "",
) -> str:
    """Generate YAML frontmatter with v37-compliant metadata (type + status + CIA + agent + norm_refs)."""

    meta = dict(meta or {})

    # AP-38 — normalizar antes de escribir, no auditar después.
    #
    # CN-03 audita `status` contra `STATUS_VOCAB` desde v38, y aun así en el
    # parque real hay 54 valores distintos de los que solo el 6% es canónico.
    # El motivo es estructural: `status` llegaba aquí dentro de `meta` y salía
    # tal cual por el bucle genérico del final, sin pasar por ningún control, y
    # el audit que lo habría detectado no lo ejecuta nadie. Se corrige en el
    # único punto por el que pasa toda escritura.
    status_note = None
    if "status" in meta:
        canonico, status_note, _regla = normalize_status(meta["status"])
        if canonico is None:
            raise ValueError(
                f"status {meta['status']!r} no pertenece al vocabulario canónico "
                f"(CN-03) ni se puede derivar de él. Usa uno de "
                f"{sorted(STATUS_VOCAB)} — inventar un estado lo propaga a cada "
                f"nota que lo copie."
            )
        meta["status"] = canonico

    frontmatter = ["---"]

    frontmatter.append(f"title: {yaml_scalar(title)}")

    frontmatter.append(f"id: {existing_id or str(uuid.uuid4())}")

    frontmatter.append(f"createdAt: {existing_created or utcnow()}")

    frontmatter.append(f"updatedAt: {utcnow()}")

    if tags:
        frontmatter.append(f"tags: {json.dumps(tags)}")

    # v37: type auto-deduced from folder if not provided in meta
    if "type" not in meta and folder:
        deduced = _deduce_type_from_folder(folder)
        if deduced:
            frontmatter.append(f"type: {deduced}")

    # v37: status defaults to draft if not provided in meta.
    # v39: se emite siempre en esta posición — antes, un `status` que venía en
    # `meta` salía por el bucle genérico del final y quedaba detrás del CIA y de
    # `agent`. El campo era el mismo pero el orden no, y un formato que depende
    # de por dónde entró el dato no es un formato.
    frontmatter.append(f"status: {meta.pop('status', 'draft')}")

    # Lo que el valor original arrastraba y no era estado (progreso, versión en
    # que se resolvió, fecha) se conserva aquí en vez de perderse al normalizar.
    if status_note:
        frontmatter.append(f"status_note: {status_note}")

    if norm_refs:
        frontmatter.append(f"norm_refs: {json.dumps(norm_refs)}")

    # v27 CIA schema — defaults overridable via meta

    frontmatter.append(f"cia_integrity: {meta.pop('cia_integrity', 'medium')}")

    frontmatter.append(f"cia_availability: {meta.pop('cia_availability', 'medium')}")

    frontmatter.append(f"cia_sensitivity: {meta.pop('cia_sensitivity', 'internal')}")

    frontmatter.append(f"agent: {meta.pop('agent', 'system')}")

    for key, value in meta.items():
        if isinstance(value, str):
            frontmatter.append(f"{key}: {value}")

        else:
            frontmatter.append(f"{key}: {json.dumps(value)}")

    frontmatter.append("---")

    return "\n".join(frontmatter)


# El mapa sección→tipo vivía aquí completo y era la cuarta copia del mismo
# dato; las otras tres (dos auditores y el grafo) se habían quedado en 18, 14 y
# 14 secciones, y dos de ellas se contradecían. Ahora lo declara el registro y
# esto solo lo consume: `SECTION_TYPES[seccion][0]` es exactamente lo que este
# write path escribía, valor por valor.


def _deduce_type_from_folder(folder: str) -> str:
    """Derive type field value from the vault section folder."""
    if not folder:
        return ""
    from vault_registry import section_default_type

    top = folder.split("/")[0].split("\\")[0]
    return section_default_type(top)


def extract_wiki_links(content: str) -> List[str]:
    """Extract wiki-links [[note]] from content."""

    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)


def update_search_index(
    vault_path: str, title: str, content: str, tags: List[str], is_new: bool = True
) -> None:
    """Update search index with new or updated note (lock-protected read-modify-write)."""

    _index_file().parent.mkdir(parents=True, exist_ok=True)

    body = content.split("---", 2)[-1] if content.startswith("---") else content

    preview = body.strip()[:200].replace("\n", " ")

    note_entry = {
        "path": vault_path,
        "title": title,
        "preview": preview,
        "tags": tags,
        "updatedAt": utcnow(),
    }

    def _update(index: Dict[str, Any]) -> Dict[str, Any]:
        notes = index.get("notes", [])

        for i, note in enumerate(notes):
            if note.get("path") == vault_path:
                notes[i] = note_entry

                return index

        notes.append(note_entry)

        index["notes"] = notes

        return index

    atomic_update_json(_index_file(), {"notes": []}, _update)


def vault_write(
    folder: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """

    Create or update a note in the vault.



    Args:

        folder: Relative path to vault root (e.g., "01_Projects/ans")

        title: Note title - also determines filename via slugify

        content: Complete Markdown content

        tags: Tags for search and indexing

        meta: Additional frontmatter fields



    Returns:

        Dict with path, id, and operation details

    """

    tags = tags or []

    meta = meta or {}

    # Content gate: new notes must pass strict content quality gate (00_System exempt)

    if not _check_content_gate(content, folder):
        reason = _content_gate_reason(content, folder) or "insufficient content"

        return {
            "ok": False,
            "error_code": "content_too_short",
            "error": "content_too_short",
            "norm_code": "AP-11",
            "norm_name": "Skeleton files — frontmatter válido, contenido vacío",
            "message": "AP-11: content rejected - "
            + reason
            + ". If content is not ready, do not create the note.",
        }

    # AP-20 guard: deceptive skeleton — reject if >50% of bullets are empty

    bullets = re.findall(r"^\s*[-*]\s*(.*)", content, re.MULTILINE)

    if bullets:
        empty_bullets = [
            b
            for b in bullets
            if not b.strip() or b.strip() in ("[]", "[[]]", "-", "[ ]")
        ]

        if len(empty_bullets) / len(bullets) > 0.5:
            return {
                "ok": False,
                "error_code": "content_empty_list",
                "error": "content_empty_list",
                "norm_code": "AP-20",
                "norm_name": "Deceptive skeleton (empty-list)",
                "message": f"AP-20: >{int(len(empty_bullets) / len(bullets) * 100)}% of bullets are empty. Fill content before saving.",
            }

    # AP-21 guard: path-anchored wiki-links — reject [[folder/note]] patterns

    path_links = re.findall(r"\[\[[^\]]*\/[^\]]*\]\]", content)

    if path_links:
        return {
            "ok": False,
            "error_code": "path_anchored_wikilinks",
            "error": "path_anchored_wikilinks",
            "norm_code": "AP-21",
            "norm_name": "Path-anchored wiki-links",
            "message": f"AP-21: path-anchored wiki-links detected: {path_links}. Use [[note-name]] without folder path.",
        }

    # AP-22 guard: unbalanced or empty wiki-link brackets

    bracket_error = _check_bracket_balance(content)

    if bracket_error:
        return {
            "ok": False,
            "error_code": "malformed_wikilinks",
            "error": "malformed_wikilinks",
            "norm_code": "AP-22",
            "norm_name": "Bracket sanity — corchetes desbalanceados o vacíos",
            "message": bracket_error,
        }

    # Mermaid guard: validate syntax in ```mermaid blocks
    mermaid_pattern = r"```mermaid\s*\n(.*?)```"
    mermaid_blocks = re.findall(mermaid_pattern, content, re.DOTALL)
    if mermaid_blocks:
        try:
            from vault_mermaid_check import validate_mermaid

            for block in mermaid_blocks:
                errors = validate_mermaid(block)
                if errors:
                    error_types = [e["type"] for e in errors]
                    return {
                        "ok": False,
                        "error_code": "mermaid_syntax_error",
                        "error": "mermaid_syntax_error",
                        "norm_code": "AP-25",
                        "norm_name": "Mermaid syntax errors",
                        "message": f"AP-25: Errores en diagrama Mermaid: {error_types}. Corregir antes de guardar.",
                        "details": errors[:3],
                    }
        except ImportError:
            pass

    # AP-26 guard: tags required for content notes (not index/system)
    is_index = title.lower().strip() in ("index", "índice", "indice") or "/index" in folder
    is_system = folder.startswith("00_System")
    if not tags and not is_index and not is_system:
        return {
            "ok": False,
            "error_code": "missing_tags",
            "error": "missing_tags",
            "norm_code": "AP-26",
            "norm_name": "Missing tags — toda nota de contenido requiere al menos un tag",
            "message": "AP-26: tags required for content notes. "
            "Provide at least one tag via --tags. Index and system notes exempt.",
        }

    # AP-39: resolver el vocabulario ANTES de escribir. Colapsa lo que es la
    # misma palabra (acentos, mayúsculas, separadores, plural) contra el
    # registro canónico; un término que no está no se rechaza — se admite y se
    # anota más abajo, una vez la escritura está confirmada.
    tags, new_terms = vault_tags.apply_vocabulary(tags)

    # AP-16 guard: agent field required
    if not meta.get("agent") and not is_system:
        agent_env = _env("VAULT_AGENT")
        if agent_env:
            meta["agent"] = agent_env
        else:
            return {
                "ok": False,
                "error_code": "missing_agent",
                "error": "missing_agent",
                "norm_code": "AP-16",
                "norm_name": "Missing agent attribution",
                "message": "AP-16: agent field required for content notes. "
                "Set --meta '{\"agent\":\"my-agent\"}' or VAULT_AGENT env var. "
                "System notes (00_System/) exempt.",
            }

    # Determine filename and validate path stays inside vault

    filename = f"{slugify(title)}.md"

    vault_path = _raiz() / folder / filename

    try:
        assert_within_vault(vault_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    existing_id = None

    existing_created = None

    existing_status = None

    existing_content = ""

    # If note exists, backup to history

    if vault_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")

        history_filename = (
            f"{folder.replace('/', '__')}__{slugify(title)}-{timestamp}.md"
        )

        history_path = _history_dir() / history_filename

        _history_dir().mkdir(parents=True, exist_ok=True)

        existing_content = vault_path.read_text(encoding="utf-8")

        atomic_write_text(history_path, existing_content)

        # AP-41 — la identidad de la nota se lee AQUÍ, en la rama en la que la
        # nota existe.
        #
        # Esta extracción vivía en el `else` de abajo, es decir en la rama en la
        # que la nota **no** existe y `existing_content` es la cadena vacía: la
        # regex no encontraba nada nunca. Consecuencia medida en el sandbox: cada
        # actualización acuñaba un `id` nuevo y reseteaba `createdAt`, así que la
        # nota perdía su identidad en cada escritura y ninguna referencia por id
        # sobrevivía. El campo estaba en el frontmatter, el código para leerlo
        # estaba escrito, y no se ejecutaba jamás.
        fm_previo, _ = parse_frontmatter_with_body(existing_content)
        fm_previo = fm_previo or {}
        existing_id = str(fm_previo.get("id") or "") or None
        # `createdAt` vuelve del parser como `...+00:00` cuando en disco estaba
        # como `...000Z`: se re-canoniza para que releer y reescribir no cambie
        # la forma del campo.
        existing_created = canonical_utc(fm_previo.get("createdAt")) or None
        existing_status = str(fm_previo.get("status") or "") or None

    # Check if note exists in a different folder (auto-move suggestion)
    else:
        search_index = _raiz() / "99_Index" / "search-index.json"
        if search_index.exists():
            try:
                import json as json_module

                index_data = json_module.loads(search_index.read_text(encoding="utf-8"))
                note_stem = slugify(title)
                for note in index_data.get("notes", []):
                    if note.get("stem") == note_stem:
                        current_path = note.get("path", "")
                        if current_path and current_path != f"{folder}/{note_stem}.md":
                            return {
                                "ok": False,
                                "error_code": "note_moved",
                                "error": "note_moved",
                                "message": f"La nota existe en: {current_path}. Usar vault_move para reubicarla o especificar otra carpeta.",
                                "suggestion": f'python scripts/vault_move.py --from "{current_path}" --to "{folder}/{note_stem}.md"',
                                "current_path": current_path,
                            }
            except Exception:
                pass

        # La extracción del frontmatter previo estaba aquí, dentro de la rama en
        # la que la nota no existe: no había nada que extraer. Vive ahora en la
        # rama de arriba (AP-41), con el parser compartido en vez de una regex
        # propia — dos lectores del mismo campo es lo que ya costó una vez.

    # ── AP-41: la máquina de estados se verifica, no solo se declara ──────────
    #
    # `STATUS_TRANSITIONS` estaba escrita y bien formada desde v38, y su único
    # consumidor en todo el repo era su propio test de coherencia: nadie la
    # recorría. Un estado que no controla su transición es una etiqueta, no un
    # ciclo de vida — `archived` podía volver a `draft` sin que nada lo viera.
    if existing_status:
        # Una actualización que no menciona `status` no lo está cambiando. Antes
        # caía al default `draft` de generate_frontmatter, así que tocar una nota
        # `verified` para corregir una frase la degradaba a borrador en silencio.
        if "status" not in meta:
            meta["status"] = existing_status
        else:
            previo, _n, _r = normalize_status(existing_status)
            destino, _n2, _r2 = normalize_status(meta["status"])
            # Si el estado previo no es canónico (deuda anterior a AP-38) no hay
            # máquina que recorrer: se deja pasar y lo reporta el audit.
            if previo and destino and previo != destino:
                permitidos = STATUS_TRANSITIONS.get(previo, set())
                if destino not in permitidos:
                    return {
                        "ok": False,
                        "error_code": "illegal_status_transition",
                        "error": "illegal_status_transition",
                        "norm_code": "AP-41",
                        "norm_name": "Máquina de estados declarada sin verificar",
                        "message": (
                            f"AP-41: transición {previo!r} -> {destino!r} no está en "
                            f"STATUS_TRANSITIONS. Desde {previo!r} solo se puede pasar a "
                            f"{sorted(permitidos) or ['(ninguno: estado terminal)']}. "
                            f"Si el salto es correcto, la que está mal es la máquina: "
                            f"corrígela en vault_norms.STATUS_TRANSITIONS, no la nota."
                        ),
                        "from_status": previo,
                        "to_status": destino,
                        "allowed": sorted(permitidos),
                    }

    # Create folder if not exists

    vault_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute applicable norm_refs before generating frontmatter

    wiki_links = extract_wiki_links(content)

    norm_refs = compute_norm_refs(folder, content, wiki_links)

    # AP-23 advisory: note exceeds complexity ceiling

    line_count = len(content.split("\n"))

    ap23_warning = line_count > 500

    # Generate frontmatter and write file (with file lock to prevent concurrent write data loss)

    # El id se decide aquí, una sola vez, y es el que va al frontmatter Y al
    # resultado. Antes `generate_frontmatter` acuñaba un uuid4 y el resultado
    # acuñaba otro: el id que la tool devolvía no era el de la nota, así que
    # cualquier agente que lo guardara guardaba una referencia inexistente.
    nota_id = existing_id or str(uuid.uuid4())

    frontmatter = generate_frontmatter(
        title, tags, meta, nota_id, existing_created, norm_refs, folder
    )

    final_content = f"{frontmatter}\n\n{content}"

    with file_lock(vault_path, timeout=10.0):
        atomic_write_text(vault_path, final_content)

        # Update search index (inside lock for consistency)

        update_search_index(
            str(vault_path.relative_to(_raiz())),
            title,
        content,
        tags,
        is_new=(existing_id is None),
    )

    # Regenerate section index in background — fire-and-forget, never blocks write

    try:
        import subprocess

        _section_index_script = Path(__file__).parent / "vault_section_index.py"

        if _section_index_script.exists():
            subprocess.Popen(
                [
                    sys.executable,
                    str(_section_index_script),
                    "--folder",
                    folder.split("/")[0],
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    except Exception:
        pass

    # AP-39: la nota ya está en disco, así que el término existe de verdad.
    # Anotarlo antes habría dejado en la bitácora palabras de escrituras que
    # fallaron — memoria de algo que nunca se escribió.
    rel_path = str(vault_path.relative_to(_raiz())).replace("\\", "/")
    introduced = 0
    if new_terms:
        for t in new_terms:
            t["note"] = rel_path
            t["agent"] = meta.get("agent", "") or _env("VAULT_AGENT")
        try:
            introduced = vault_tags.record_new_tags(new_terms)
        except OSError:
            # La bitácora no puede tumbar una escritura válida: se registra el
            # fallo en el resultado y el audit de AP-39 lo recoge después.
            introduced = -1

    tag_suggestions = _tag_suggestions(tags)

    ghost_links = _collect_ghost_links(wiki_links)

    result: Dict[str, Any] = {
        "ok": True,
        **write_report(),
        "path": rel_path,
        "id": nota_id,
        "filename": filename,
        "tags": tags,
        "wikiLinks": wiki_links,
        "norm_refs": norm_refs,
        "created": existing_id is None,
        "message": f"Note {'created' if existing_id is None else 'updated'} successfully",
    }

    if existing_status and meta.get("status") and existing_status != meta["status"]:
        result["status_transition"] = f"{existing_status} -> {meta['status']}"

    if ap23_warning:
        result["ap23_warning"] = (
            f"AP-23: note has {line_count} lines — consider splitting into sub-notes (threshold: 500)"
        )

    if ghost_links:
        result["ghost_links"] = ghost_links

    if tag_suggestions:
        result["tag_suggestions"] = tag_suggestions

    if new_terms:
        result["vocabulary_introduced"] = [t["tag"] for t in new_terms]
        result["vocabulary_recorded"] = introduced

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Vault Write Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_write.py --folder "01_Projects/mi-api" --title "Status" --content "# Status\\n\\nActivo"

  python vault_write.py --folder "03_Decisions" --title "ADR-001" --tags arch backend --meta '{"status":"accepted"}'

  python vault_write.py --folder "03_Decisions" --title "ADR-001" --content "..." --meta-file meta.json

  python vault_write.py --folder "07_Knowledge/concepts" --scan-path "docs/concepts/"



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Con --scan-path, --title y --content son opcionales

  - Solo se procesan archivos .md en --scan-path

""",
    )

    parser.add_argument(
        "--folder", required=True, help="Folder path relative to vault root"
    )

    parser.add_argument(
        "--title", help="Note title (optional when --scan-path is used)"
    )

    parser.add_argument(
        "--content",
        help="Markdown content (use @file:path to read from file; optional when --scan-path is used)",
    )

    parser.add_argument("--tags", nargs="*", help="Tags for search")

    parser.add_argument(
        "--meta", type=json.loads, help="Additional frontmatter as JSON"
    )

    parser.add_argument(
        "--meta-file",
        help="Path to JSON file with additional frontmatter (avoids shell quoting issues)",
    )

    parser.add_argument(
        "--scan-path",
        help="Directory to scan for .md files and write each one to --folder",
    )

    args = parser.parse_args()

    # --scan-path mode: scan directory for .md files

    if args.scan_path:
        scan_dir = Path(args.scan_path)

        if not scan_dir.exists():
            print(
                json.dumps(
                    {"ok": False, "error": f"scan-path not found: {args.scan_path}"}
                )
            )

            return 1

        md_files = list(scan_dir.rglob("*.md"))

        written = []

        skipped = []

        meta = args.meta

        if args.meta_file:
            with open(args.meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

        for md_file in md_files:
            try:
                file_content = md_file.read_text(encoding="utf-8")

            except Exception as e:
                skipped.append({"file": str(md_file), "reason": str(e)})

                continue

            # Extract title from first # Heading or use filename

            heading_match = re.search(r"^#\s+(.+)$", file_content, re.MULTILINE)

            title = (
                heading_match.group(1).strip()
                if heading_match
                else md_file.stem.replace("-", " ").replace("_", " ").title()
            )

            # Check if note already exists

            filename = f"{slugify(title)}.md"

            vault_path = _raiz() / args.folder / filename

            if vault_path.exists():
                skipped.append(
                    {"file": str(md_file), "reason": "already exists in vault"}
                )

                continue

            result = vault_write(args.folder, title, file_content, args.tags, meta)

            if result["ok"]:
                written.append(result["path"])

            else:
                skipped.append(
                    {"file": str(md_file), "reason": result.get("error", "unknown")}
                )

        scan_result = {
            "ok": True,
            "scanned": len(md_files),
            "written": written,
            "skipped": skipped,
        }

        print(json.dumps(scan_result, indent=2, ensure_ascii=False))

        return 0

    # Standard single-note mode

    if not args.title:
        parser.error("--title is required when --scan-path is not used")

    if not args.content:
        parser.error("--content is required when --scan-path is not used")

    # Read content from file if @file:path

    if args.content.startswith("@file:"):
        file_path = Path(args.content[6:])

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

    else:
        content = args.content

    # Sanitize title and content to fix encoding issues from IA or cross-platform
    title = args.title
    if title:
        title, title_fixes = sanitize_content(title, dry_run=False)
        if title_fixes:
            result = {
                "ok": False,
                "error": "encoding_issue_in_title",
                "message": "El título contiene caracteres problemáticos que fueron corregidos.",
                "fixes": title_fixes,
                "suggestion": f"Usa el título corregido: {title}",
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1

    if content:
        content, content_fixes = sanitize_content(content, dry_run=False)
        # Log fixes but continue (content fixes are auto-applied)
        if content_fixes:
            pass  # Already logged in sanitize_content -> atomic_write_text

    meta = args.meta

    if args.meta_file:
        with open(args.meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

    result = vault_write(args.folder, title, content, args.tags, meta)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_write"))
