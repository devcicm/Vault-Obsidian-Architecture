"""Enlace persistente entre un archivo de código (o símbolo) y su nota del vault.

Este servicio pertenece a Grafo: @vault es una arista desde el archivo fuente
(o desde un método/clase concreto) hacia la nota que lo documenta y
code-tag-registry.json es su proyección persistida. La semántica pura de
extracción, resolución por ID corto y matriz RDD vive en el núcleo
(`vault.kernel.trazabilidad_codigo`); este módulo gestiona el registro
persistido bajo lock.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..kernel import construir
from ..kernel.trazabilidad_codigo import (
    CODE_EXTS,
    COMMENT_STYLES,
    VAULT_REF_ANY_PATTERN,
    VAULT_TAG_PATTERN,
    VAULT_TAG_TEMPLATES,
    comment_style,
    construir_indice_notas_vault,
    construir_matriz_rdd,
    extract_all_vault_refs,
    insertar_vault_en_simbolo,
    line_offset,
    renderizar_visor_html,
    resolver_referencia_vault,
)
from .repositorio import RepositorioGrafo

__all__ = [
    "CODE_EXTS",
    "COMMENT_STYLES",
    "VAULT_REF_ANY_PATTERN",
    "VAULT_TAG_PATTERN",
    "VAULT_TAG_TEMPLATES",
    "comment_style",
    "construir_indice_notas_vault",
    "construir_matriz_rdd",
    "extract_all_vault_refs",
    "extract_vault_ref",
    "insertar_vault_en_simbolo",
    "line_offset",
    "link_symbol_vault",
    "link_vault",
    "renderizar_visor_html",
    "resolver_referencia_vault",
    "unlink_vault",
]


def extract_vault_ref(content: str) -> Optional[Dict[str, str]]:
    """Extrae la arista @vault embebida en cabecera, si existe."""
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


def _registrar_en_proyeccion(
    repo: RepositorioGrafo,
    note_ref: str,
    tag_title: str,
    file_path: Path,
    symbol: Optional[str] = None,
) -> None:
    registry = _read_registry(repo)
    vault_key = f"vault:{note_ref.replace('/', ':')}"
    tags = registry.setdefault("tags", {})
    if vault_key not in tags:
        tags[vault_key] = {
            "name": tag_title,
            "description": f"Vault note: {note_ref}",
            "files": [],
            "symbols": [],
            "vault_note": note_ref + ".md" if "/" in note_ref else note_ref,
            "created_at": repo.ctx.reloj.marca(),
            "created_by": "vault_code_tag",
            "tag_type": "vault_ref",
        }
    file_string = str(file_path)
    if file_string not in tags[vault_key].get("files", []):
        tags[vault_key].setdefault("files", []).append(file_string)
    if symbol:
        sym_entry = f"{file_string}::{symbol}"
        if sym_entry not in tags[vault_key].get("symbols", []):
            tags[vault_key].setdefault("symbols", []).append(sym_entry)
    _save_registry(repo, registry)


def link_vault(
    note_path_rel: str,
    file_path_str: str,
    title: str = "",
    *,
    root: str | Path | None = None,
    report: Callable[[], Dict[str, int]] | None = None,
) -> Dict[str, Any]:
    """Inserta o reemplaza el enlace @vault de cabecera en un archivo fuente."""
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
    except OSError as exc:
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
            _registrar_en_proyeccion(repo, note_ref, tag_title, file_path)
    except OSError as exc:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(exc)}

    return {
        "ok": True,
        **(report() if report else {}),
        "action": action,
        "file": str(file_path),
        "note": note_ref,
        "comment": vault_comment,
    }


def link_symbol_vault(
    note_path_rel: str,
    file_path_str: str,
    symbol: str,
    title: str = "",
    *,
    root: str | Path | None = None,
    report: Callable[[], Dict[str, int]] | None = None,
) -> Dict[str, Any]:
    """Inserta un enlace @vault encima de un método, función o clase respetando indentación."""
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

    try:
        original = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(exc)}

    note_ref = note_path_rel.replace("\\", "/").removesuffix(".md").strip()
    tag_title = (title or note_ref.split("/")[-1])[:60]

    new_content, action, line_no, comment_line = insertar_vault_en_simbolo(
        original,
        note_ref=note_ref,
        symbol=symbol,
        style=style,
        title=tag_title,
        file_path=file_path,
    )
    if action == "symbol_not_found":
        return {
            "ok": False,
            "error_code": "NOT_FOUND",
            "detail": f"Symbol '{symbol}' not found in {file_path}",
        }
    if action == "already_present":
        return {
            "ok": True,
            "action": "already_present",
            "file": str(file_path),
            "symbol": symbol,
            "line": line_no,
            "note": note_ref,
            "comment": comment_line,
        }

    try:
        with repo.ctx.escritor.bloquear(repo.registro_etiquetas_codigo, timeout=30.0):
            repo.ctx.escritor.escribir(file_path, new_content)
            _registrar_en_proyeccion(repo, note_ref, tag_title, file_path, symbol=symbol)
    except OSError as exc:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(exc)}

    return {
        "ok": True,
        **(report() if report else {}),
        "action": action,
        "file": str(file_path),
        "symbol": symbol,
        "line": line_no,
        "note": note_ref,
        "comment": comment_line,
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
    except OSError as exc:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(exc)}

    new_content, count = VAULT_TAG_PATTERN.subn("", content)
    if count == 0:
        return {"ok": True, "action": "not_found", "file": str(file_path)}
    try:
        with repo.ctx.escritor.bloquear(repo.registro_etiquetas_codigo, timeout=30.0):
            repo.ctx.escritor.escribir(file_path, new_content)
    except OSError as exc:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(exc)}
    return {"ok": True, "action": "unlinked", "file": str(file_path), "lines_removed": count}
