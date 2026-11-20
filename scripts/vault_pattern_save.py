#!/usr/bin/env python3

"""

Vault Pattern Save Tool — Register patterns with evolutionary state



Saves or updates a pattern with lifecycle tracking (planificado → en_progreso → implementado | deprecado | refactoring).

Auto-updates {proyecto}-patterns-index.md and tracks state transitions.



Usage:

    python vault_pattern_save.py --project "mi-api" --name "Repository" --type "code" --status "implementado"

    python vault_pattern_save.py --project "ans" --name "Circuit-Breaker" --type "code" --status "en_progreso" --files "src/resilience.py" --related "Retry"

    python vault_pattern_save.py --rebuild-index

"""

import argparse

import json

import os

import re

import sys

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_norms_catalog import status_frontmatter_lines
from vault_lib import yaml_scalar, utcnow, slugify
from vault_lib import parse_frontmatter
from vault_io import (
    indice_compartido,
    file_lock,
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    safe_wikilink,
)
import uuid

from pathlib import Path

from typing import Any, Dict, List, Optional


PATTERN_TYPES = ["design", "architecture", "code", "integration"]

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import mapa as _mapa, opciones as _opciones

PATTERN_STATUSES = _opciones("pattern_state")


VALID_TRANSITIONS = _mapa("pattern_state", {
    "planificado": ["en_progreso"],
    "en_progreso": ["implementado", "deprecado", "refactoring"],
    "implementado": ["deprecado", "refactoring", "en_progreso"],
    "deprecado": ["implementado", "en_progreso"],
    "refactoring": ["implementado", "en_progreso", "deprecado"],
})


def estado_de_la_nota(meta: Dict[str, Any]) -> Optional[str]:
    """The pattern's own state, the key of `VALID_TRANSITIONS`.

    Since AP-38 `status` holds the canonical note lifecycle (`planned`) and
    the pattern state lives in `pattern_state` (`planificado`). The guard read
    `status`, found no transitions from `planned` and froze every pattern after
    its first save (QA-FL-01, 2026-11-17). Notes written before AP-38 carry the
    domain value in `status` itself, so that is read only when it is one.
    """
    if meta.get("pattern_state") is not None:
        return str(meta["pattern_state"])
    legado = meta.get("status")
    return legado if legado in PATTERN_STATUSES else None


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.contenido import nota_escalonada  # noqa: E402
from vault.autoria.frontmatter import Frontmatter  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _patterns_dir() -> Path:
    return _repo().seccion("05_Patterns")


def _index_file() -> Path:
    return _repo().indice_de_seccion("05_Patterns")


def get_pattern_path(project: str, name: str, pattern_type: str) -> Path:
    safe_name = slugify(name)

    safe_project = slugify(project)

    return _patterns_dir() / pattern_type / f"{safe_project}-{safe_name}.md"


def get_pattern_index_path(project: str) -> Path:
    return _patterns_dir() / f"{slugify(project)}-patterns-index.md"


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def load_pattern_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"patterns": []}


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def save_pattern_index(data: Dict[str, Any]) -> None:
    _index_file().parent.mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def _seccion(texto: str, titulo: str) -> Optional[str]:
    """The body of a `## <titulo>` section this tool wrote, or None."""
    encontrada = re.search(
        rf"^## {re.escape(titulo)}\n\n(.*?)(?=\n## |\n+---\n\*Última actualización|\Z)",
        texto, re.DOTALL | re.MULTILINE,
    )
    if not encontrada or not encontrada.group(1).strip():
        return None
    return encontrada.group(1).strip()


def vault_pattern_save(
    project: str,
    name: str,
    pattern_type: str,
    status: str,
    description: Optional[str] = None,
    files: Optional[List[str]] = None,
    related_patterns: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    pattern_type = pattern_type.lower()

    status = status.lower().replace(" ", "_")

    if pattern_type not in PATTERN_TYPES:
        return emit_error("vault_pattern_save", "INVALID_VALUE", f"Tipo inválido: {pattern_type}. Válidos: {PATTERN_TYPES}")

    if status not in PATTERN_STATUSES:
        return emit_error("vault_pattern_save", "INVALID_VALUE", f"Estado inválido: {status}. Válidos: {PATTERN_STATUSES}")

    safe_project = slugify(project)

    safe_name = slugify(name)

    pattern_path = get_pattern_path(project, name, pattern_type)

    existing_id = None

    existing_status = None

    existing_tags: List[Any] = []

    # The creation date is a fact of the note, not of this save: every re-save
    # used to overwrite it with now (W1 advisory, 2026-11-17).
    existing_created = None

    evolution_entries = []

    if pattern_path.exists():
        with open(pattern_path, "r", encoding="utf-8") as f:
            existing_content = f.read()

        meta = parse_frontmatter(existing_content)

        existing_id = meta.get("id")

        # The raw text, not the parsed value: YAML turns it into a datetime
        # and `str()` would rewrite it in another format.
        creada = re.search(r"^createdAt:[ \t]*(.+?)[ \t]*$", existing_content.split("\n---", 1)[0], re.M)
        existing_created = creada.group(1).strip("'\"") if creada and meta.get("createdAt") else None

        existing_status = estado_de_la_nota(meta)

        if isinstance(meta.get("tags"), list):
            existing_tags = meta["tags"]

        # The note is rewritten whole, so what it already documents is carried
        # over unless this save restates it. Without this, advancing the state
        # with `--status` alone (possible again since QA-FL-01) dropped the
        # description, files, related patterns and notes.
        if description is None:
            description = _seccion(existing_content, "Descripción")

        if notes is None:
            notes = _seccion(existing_content, "Notas")

        if files is None and isinstance(meta.get("files"), list):
            files = [str(f) for f in meta["files"]]

        if related_patterns is None and isinstance(meta.get("relatedPatterns"), list):
            related_patterns = [str(r) for r in meta["relatedPatterns"]]

        evo_match = re.search(
            r"## Evolución\n(.*?)(?=\n## |\Z)", existing_content, re.DOTALL
        )

        if evo_match:
            # Only the list items: the section is the last one, so the match
            # also runs over the `---` footer, which then piled up inside the
            # history on every save.
            evolution_entries = [
                linea for linea in evo_match.group(1).strip().split("\n")
                if linea.startswith("- ")
            ]

    timestamp = utcnow()

    if existing_status and existing_status != status:
        if status not in VALID_TRANSITIONS.get(existing_status, []):
            return emit_error("vault_pattern_save", "INVALID_VALUE", f"Transición inválida: {existing_status} → {status}. Válidas desde {existing_status}: {VALID_TRANSITIONS.get(existing_status, [])}")

        transition_entry = f"- **{existing_status}** → **{status}** ({timestamp})"

        if transition_entry not in evolution_entries:
            evolution_entries.append(transition_entry)

    wiki_links = []

    if related_patterns:
        for rp in related_patterns:
            slug = f"{safe_project}-{slugify(rp)}"

            wiki_links.append(f"[[{slug}|{safe_wikilink(rp)}]]")

    try:
        assert_within_vault(pattern_path, _raiz())

    except ValueError as exc:
        return {
            "ok": False,
            "error_code": "INVALID_PATH",
            "error": "INVALID_PATH",
            "message": str(exc),
        }

    frontmatter = Frontmatter()

    frontmatter.set("title", name, texto=True)

    frontmatter.set("id", existing_id or str(uuid.uuid4()))

    frontmatter.set("project", project, texto=True)

    frontmatter.set("type", pattern_type)

    frontmatter.lineas(status_frontmatter_lines("vault_pattern_save", status))

    # AP-26 asks every content note for at least one tag, and this product's
    # own audit flagged every pattern note (QA-FL-09). The tags come from what
    # the note already declares, as in `vault_diagram_save`; the ones a person
    # added to the note survive a re-save.
    frontmatter.set(
        "tags", sorted({*map(str, existing_tags), safe_project, pattern_type, "pattern"})
    )

    frontmatter.set("createdAt", existing_created or timestamp)

    frontmatter.set("updatedAt", timestamp)

    if files:
        frontmatter.set("files", files)

    if related_patterns:
        frontmatter.set("relatedPatterns", related_patterns)

    frontmatter.set("cia_integrity", "medium")

    frontmatter.set("cia_availability", "medium")

    frontmatter.set("cia_sensitivity", "internal")

    frontmatter.set("agent", "system")


    body_sections = []

    if description:
        body_sections.append(f"## Descripción\n\n{description}")

    if files:
        body_sections.append("## Archivos\n\n" + "\n".join(f"- `{f}`" for f in files))

    if wiki_links:
        body_sections.append("## Patrones Relacionados\n\n" + " ".join(wiki_links))

    if notes:
        body_sections.append(f"## Notas\n\n{notes}")

    if evolution_entries:
        # The transition of this save is already in `evolution_entries`;
        # appending it here as well wrote every transition twice.
        body_sections.append("\n".join(["## Evolución\n", *evolution_entries]))

    body_sections.append(f"\n---\n*Última actualización: {timestamp}*")

    # nota-escalonada S4: the lead says what the pattern is from its arguments;
    # the problem it solves is the user's to tell, so it stays pending.
    lead = f"{name} es un patrón de tipo {pattern_type} del proyecto {project}, en estado {status}."
    if files:
        lead += f" Se aplica en {len(files)} archivos, listados en la sección Archivos."
    lead += " Esta nota se generó con `vault_pattern_save` y vive en la sección de patrones del vault."
    falta = None if description else (
        "falta describir qué problema resuelve el patrón y por qué se eligió (`--description`)")
    final_content = (frontmatter.render() + "\n\n" + nota_escalonada(name, lead, falta=falta)
                     # As `con_titulo` did: the body's own leading blank lines go.
                     + "\n" + "\n\n".join(body_sections).lstrip("\n"))

    pattern_path.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_text(pattern_path, final_content)

    # Aqui el upsert es leer-modificar-escribir sobre un indice compartido: sin
    # tramo exclusivo, dos guardados concurrentes leen la misma lista, cada uno
    # anade la suya, gana el segundo y la primera entrada desaparece con las dos
    # tools devolviendo `ok: true`.
    with indice_compartido(_index_file(), {"patterns": []}) as index:
        pattern_entry = {
            "path": str(pattern_path.relative_to(_raiz())).replace("\\", "/"),
            "pattern": name,
            "project": project,
            "type": pattern_type,
            "status": status,
            "updatedAt": timestamp,
        }

        for i, entry in enumerate(index["patterns"]):
            if entry["path"] == pattern_entry["path"]:
                index["patterns"][i] = pattern_entry

                break

        else:
            index["patterns"].append(pattern_entry)

    transition = (
        f"{existing_status} → {status}"
        if existing_status and existing_status != status
        else None
    )

    return {
        "ok": True,
        **write_report(),
        "path": str(pattern_path.relative_to(_raiz())).replace("\\", "/"),
        "status": status,
        "transition": transition,
    }


#: Why a note under `05_Patterns/` stays out of a rebuilt index.
_SIN_ESTADO = "no pattern_state in the pattern vocabulary"
_SIN_TIPO = "type is not a pattern type"
_SIN_NOMBRE = "no title or project"


def _entrada_de_la_nota(ruta: Path) -> Dict[str, Any]:
    """The index entry a pattern note declares, or the reason it declares none.

    Only what the note's frontmatter says, in the shape `vault_pattern_save`
    writes: no field is guessed. `status` in the index is the pattern state,
    as on every save.
    """
    meta = parse_frontmatter(ruta.read_text(encoding="utf-8", errors="replace"))
    estado = estado_de_la_nota(meta)
    if estado not in PATTERN_STATUSES:
        return {"reason": _SIN_ESTADO}
    if meta.get("type") not in PATTERN_TYPES:
        return {"reason": _SIN_TIPO}
    if not meta.get("title") or not meta.get("project"):
        return {"reason": _SIN_NOMBRE}
    entrada = {
        "path": str(ruta.relative_to(_raiz())).replace(chr(92), "/"),
        "pattern": str(meta["title"]),
        "project": str(meta["project"]),
        "type": meta["type"],
        "status": estado,
    }
    if meta.get("updatedAt"):
        entrada["updatedAt"] = str(meta["updatedAt"])
    return entrada


def vault_pattern_rebuild_index() -> Dict[str, Any]:
    """Rebuild `05_Patterns/index.json` from the pattern notes (QA-FL-PAT).

    The index is derived: every entry is what a note's frontmatter declares.
    A vault that has the notes but lost the index (or never had one, after a
    copy or a migration) had no way back, because only a save wrote it, and
    only with its own entry. `vault_pattern_list` points its `INDEX_NOT_FOUND`
    recovery here. Notes the pattern module does not recognise are reported in
    `skipped` with their reason, never indexed by guessing; the section's own
    `index.md` is not a note.
    """
    carpeta = _patterns_dir()
    destino = _index_file()
    patterns: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    notas = sorted(carpeta.rglob("*.md")) if carpeta.is_dir() else []
    for ruta in notas:
        if ruta.name.lower() == "index.md":
            continue
        entrada = _entrada_de_la_nota(ruta)
        if "reason" in entrada:
            skipped.append({"path": str(ruta.relative_to(_raiz())).replace(chr(92), "/"),
                            "reason": entrada["reason"]})
        else:
            patterns.append(entrada)

    destino.parent.mkdir(parents=True, exist_ok=True)
    # A full replacement, not an upsert: the lock keeps a concurrent save from
    # interleaving, and nothing from the previous file is read or kept.
    with file_lock(destino, timeout=30.0):
        atomic_write_json(destino, {"patterns": patterns})

    return {
        "ok": True,
        **write_report(),
        "action": "rebuild-index",
        "index": str(destino.relative_to(_raiz()).as_posix()),
        "indexed": len(patterns),
        "skipped": skipped,
    }


_OBLIGATORIOS = ("project", "name", "type", "status")
_DEL_GUARDADO = (*_OBLIGATORIOS, "description", "files", "related", "notes")


def _validar_modo(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """A save needs its four fields; a rebuild takes none of a save's."""
    if args.rebuild_index:
        sobran = [f"--{c}" for c in _DEL_GUARDADO if getattr(args, c) is not None]
        if sobran:
            parser.error(f"--rebuild-index takes no other argument: {', '.join(sobran)}")
        return
    faltan = [f"--{c}" for c in _OBLIGATORIOS if getattr(args, c) is None]
    if faltan:
        parser.error(f"the following arguments are required: {', '.join(faltan)}")


def main():
    parser = argparse.ArgumentParser(
        description="Vault Pattern Save Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_pattern_save.py --project "mi-api" --name "Repository" --type "code" --status "implementado"

  python vault_pattern_save.py --project "ans" --name "Circuit-Breaker" --type "code" --status "en_progreso" --files "src/resilience.py" --related "Retry"

  python vault_pattern_save.py --project "ans" --name "Hexagonal" --type "architecture" --status "planificado" --description "Ports and adapters"

  python vault_pattern_save.py --project "mi-api" --name "CQRS" --type "design" --status "implementado" --notes "Ver ADR-003"

  python vault_pattern_save.py --rebuild-index



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Tipos validos: design, architecture, code, integration

  - Estados validos: planificado, en_progreso, implementado, deprecado, refactoring

  - Las transiciones de estado se validan y se registran en el historial de evolucion

  - Al volver a guardar, lo que no se repite (--description, --files, --related, --notes) se conserva

  - --rebuild-index reconstruye 05_Patterns/index.json desde las notas de patron
    (las que declaran pattern_state); las que no reconoce salen en `skipped`

""",
        allow_abbrev=False,
    )

    # Required for a save, refused with --rebuild-index: argparse cannot say
    # "required unless", so `_validar_modo` enforces it with argparse's words.
    parser.add_argument("--project", type=proyecto_registrado("vault_pattern_save"), help="Project name (required to save)")

    parser.add_argument("--name", help="Pattern name (required to save)")

    parser.add_argument("--type", choices=PATTERN_TYPES, help=f"Pattern type (required to save): {PATTERN_TYPES}")

    parser.add_argument(
        "--status", choices=PATTERN_STATUSES, help=f"Pattern status (required to save): {PATTERN_STATUSES}"
    )

    parser.add_argument("--description", help="Pattern description")

    parser.add_argument("--files", nargs="*", help="Files implementing this pattern")

    parser.add_argument("--related", nargs="*", help="Related pattern names")

    parser.add_argument("--notes", help="Additional notes")

    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild 05_Patterns/index.json from the pattern notes; takes no other argument",
    )

    args = parser.parse_args()

    _validar_modo(parser, args)

    if args.rebuild_index:
        result = vault_pattern_rebuild_index()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    result = vault_pattern_save(
        args.project,
        args.name,
        args.type,
        args.status,
        args.description,
        args.files,
        args.related,
        args.notes,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_pattern_save"))
