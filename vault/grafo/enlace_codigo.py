"""Enlace persistente entre un archivo de código y su nota del vault.

Este servicio pertenece a Grafo: @vault es una arista desde el archivo fuente
hacia la nota que lo documenta y code-tag-registry.json es su proyección
persistida. No conoce el parser ni la CLI histórica vault_code_tag; esos
adaptadores delegan aquí.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..kernel import construir
from .repositorio import RepositorioGrafo


# El estilo de comentario es una propiedad del enlace código↔nota, no de la
# herramienta legacy que lo expone. La fachada conserva los nombres privados
# históricos como aliases para sus operaciones @norm.
COMMENT_STYLES: Dict[str, str] = {
    ".cs": "line", ".ts": "line", ".tsx": "line", ".js": "line",
    ".jsx": "line", ".java": "line", ".cpp": "line", ".c": "line",
    ".h": "line", ".go": "line", ".swift": "line", ".kt": "line",
    ".rs": "line", ".dart": "line", ".py": "hash", ".rb": "hash",
    ".sh": "hash", ".bash": "hash", ".zsh": "hash", ".yml": "hash",
    ".yaml": "hash", ".r": "hash", ".html": "open_close",
    ".xml": "open_close", ".svg": "open_close", ".css": "block",
    ".scss": "block", ".sass": "block", ".less": "block", ".sql": "dash",
    ".md": "none",
}

VAULT_TAG_TEMPLATES = {
    "line": "// @vault: {note_path}  — {title}",
    "hash": "# @vault: {note_path}  — {title}",
    "open_close": "<!-- @vault: {note_path}  — {title} -->",
    "block": "/* @vault: {note_path}  — {title} */",
    "dash": "-- @vault: {note_path}  — {title}",
}

VAULT_TAG_PATTERN = re.compile(
    r"^(?://|#|<!--|/\*|--)\s*@vault:\s*(\S+)\s*[—\-]+\s*(.*?)(?:\s*(?:-->|\*/))?\s*$",
    re.MULTILINE,
)


def comment_style(file_path: Path) -> str:
    return COMMENT_STYLES.get(file_path.suffix.lower(), "line")


def line_offset(lines: List[str], line_index: int) -> int:
    return sum(len(line) for line in lines[:line_index])


def extract_vault_ref(content: str) -> Optional[Dict[str, str]]:
    """Extrae la arista @vault embebida, si existe."""
    match = VAULT_TAG_PATTERN.search(content)
    if not match:
        return None
    return {"note_path": match.group(1).strip(), "title": match.group(2).strip()}


def _repo(root: str | Path | None = None) -> RepositorioGrafo:
    return RepositorioGrafo(construir(root))


def _read_registry(repo: RepositorioGrafo) -> Dict[str, Any]:
    path = repo.registro_etiquetas_codigo
    if not path.exists():
        return {"version": "v30", "tags": {}}
    return repo.leer_json(path) or {"version": "v30", "tags": {}}


def _save_registry(repo: RepositorioGrafo, registry: Dict[str, Any]) -> None:
    registry["updated_at"] = repo.ctx.reloj.marca()
    repo.ctx.escritor.escribir_json(repo.registro_etiquetas_codigo, registry)


def link_vault(
    note_path_rel: str,
    file_path_str: str,
    title: str = "",
    *,
    root: str | Path | None = None,
    report: Callable[[], Dict[str, int]] | None = None,
) -> Dict[str, Any]:
    """Inserta o reemplaza el enlace @vault de un archivo fuente."""
    repo = _repo(root)
    file_path = Path(file_path_str)

    if not file_path.exists():
        return {
            "ok": False,
            "error_code": "FILE_NOT_FOUND",
            "detail": f"Source file not found: {file_path}",
        }

    style = comment_style(file_path)
    if style == "none":
        return {
            "ok": False,
            "error_code": "UNSUPPORTED_FORMAT",
            "detail": "Use frontmatter norm_refs for .md files.",
        }

    note_ref = note_path_rel.replace("\\", "/").removesuffix(".md")
    tag_title = (title or note_ref.split("/")[-1])[:60]
    template = VAULT_TAG_TEMPLATES.get(style, VAULT_TAG_TEMPLATES["line"])
    vault_comment = template.format(note_path=note_ref, title=tag_title)

    try:
        original = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(exc)}

    existing = VAULT_TAG_PATTERN.search(original)
    if existing and existing.group(1).strip() == note_ref:
        return {
            "ok": True,
            "action": "already_present",
            "file": str(file_path),
            "note": note_ref,
        }
    if existing:
        new_content = VAULT_TAG_PATTERN.sub(vault_comment, original, count=1)
        action = "replaced"
    else:
        lines = original.splitlines(keepends=True)
        insert_at = 1 if lines and lines[0].startswith("#!") else 0
        offset = line_offset(lines, insert_at)
        new_content = original[:offset] + vault_comment + "\n" + original[offset:]
        action = "linked"

    # El mismo lock protege archivo y proyección de registro. Nunca se leen y
    # escriben por separado: eso volvería a abrir la carrera AP-05.
    try:
        with repo.ctx.escritor.bloquear(repo.registro_etiquetas_codigo, timeout=30.0):
            repo.ctx.escritor.escribir(file_path, new_content)
            registry = _read_registry(repo)
            vault_key = f"vault:{note_ref.replace('/', ':')}"
            tags = registry.setdefault("tags", {})
            if vault_key not in tags:
                tags[vault_key] = {
                    "name": tag_title,
                    "description": f"Vault note: {note_ref}",
                    "files": [],
                    "vault_note": note_ref + ".md",
                    "created_at": repo.ctx.reloj.marca(),
                    "created_by": "vault_code_tag",
                    "tag_type": "vault_ref",
                }
            file_string = str(file_path)
            if file_string not in tags[vault_key].get("files", []):
                tags[vault_key].setdefault("files", []).append(file_string)
            _save_registry(repo, registry)
    except Exception as exc:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(exc)}

    return {
        "ok": True,
        **(report() if report else {}),
        "action": action,
        "file": str(file_path),
        "note": note_ref,
        "comment": vault_comment,
    }


def unlink_vault(
    file_path_str: str,
    *,
    root: str | Path | None = None,
) -> Dict[str, Any]:
    """Elimina el enlace @vault de un archivo fuente."""
    repo = _repo(root)
    file_path = Path(file_path_str)
    if not file_path.exists():
        return {
            "ok": False,
            "error_code": "FILE_NOT_FOUND",
            "detail": f"File not found: {file_path}",
        }
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(exc)}

    new_content, count = VAULT_TAG_PATTERN.subn("", content)
    if count == 0:
        return {"ok": True, "action": "not_found", "file": str(file_path)}
    try:
        with repo.ctx.escritor.bloquear(repo.registro_etiquetas_codigo, timeout=30.0):
            repo.ctx.escritor.escribir(file_path, new_content)
    except Exception as exc:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(exc)}
    return {"ok": True, "action": "unlinked", "file": str(file_path), "lines_removed": count}
