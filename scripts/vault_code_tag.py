#!/usr/bin/env python3
"""
Vault Code Tag — Trazabilidad bidireccional código ↔ vault.

Dos tipos de etiqueta embebida en la cabecera de archivos fuente:

  @vault:  referencia a la nota vault que documenta este archivo
           → cierra el ciclo: el código sabe dónde está su documentación
  @norm:   referencia a norma del estándar (AP-XX, SP-XX, CN-XX) o código custom

Orden canónico de cabecera (siempre @vault primero):
  // @vault: 11_Code/my-api/auth-service   — AuthService (service)
  // @norm  AP-22      — Bracket sanity guard
  // @norm  SP-01      — Delete protocol

Flujo típico:
  1. vault_code_module --project my-api --file_path src/auth.ts ... --tag-source
     → crea nota en vault Y embebe @vault: en src/auth.ts automáticamente

  2. vault_code_tag --link-vault 11_Code/my-api/auth-service --file src/auth.ts
     → embebe @vault: manualmente si la nota ya existía

  3. vault_code_sync --project my-api
     → audita todos los módulos: detecta archivos sin @vault: y notas sin source_file

Usage:
    python vault_code_tag.py --define cr-0989 --name "Cola de prioridad" --description "FIFO con pesos"
    python vault_code_tag.py --apply cr-0989 --file "src/services/colas.cs"
    python vault_code_tag.py --apply AP-22 --file "scripts/vault_write.py" --name "Bracket sanity guard"
    python vault_code_tag.py --link-vault 11_Code/my-api/auth-service --file "src/auth.ts" --title "AuthService"
    python vault_code_tag.py --unlink-vault --file "src/auth.ts"
    python vault_code_tag.py --remove cr-0989 --file "src/services/colas.cs"
    python vault_code_tag.py --scan --file "src/services/colas.cs"
    python vault_code_tag.py --list
    python vault_code_tag.py --list --file "src/services/colas.cs"
    python vault_code_tag.py --tag-note cr-0989
"""

import argparse
import functools
import json
import re
import sys
import threading
from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_json, write_report, resolve_input_path, file_lock
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _code_tag_registry() -> Path:
    return _repo().registro_etiquetas_codigo


# ─── Formatos de comentario por extensión ─────────────────────────────────────

_COMMENT_STYLES: Dict[str, str] = {
    # estilo: line, open_close, hash, dash
    ".cs":    "line",
    ".ts":    "line",
    ".tsx":   "line",
    ".js":    "line",
    ".jsx":   "line",
    ".java":  "line",
    ".cpp":   "line",
    ".c":     "line",
    ".h":     "line",
    ".go":    "line",
    ".swift": "line",
    ".kt":    "line",
    ".rs":    "line",
    ".dart":  "line",
    ".py":    "hash",
    ".rb":    "hash",
    ".sh":    "hash",
    ".bash":  "hash",
    ".zsh":   "hash",
    ".yml":   "hash",
    ".yaml":  "hash",
    ".r":     "hash",
    ".html":  "open_close",
    ".xml":   "open_close",
    ".svg":   "open_close",
    ".css":   "block",
    ".scss":  "block",
    ".sass":  "block",
    ".less":  "block",
    ".sql":   "dash",
    ".md":    "none",  # vault notes use frontmatter norm_refs instead
}

_COMMENT_TEMPLATES = {
    "line":       "// @norm {code:<10} — {name}",
    "hash":       "# @norm {code:<10} — {name}",
    "open_close": "<!-- @norm {code:<10} — {name} -->",
    "block":      "/* @norm {code:<10} — {name} */",
    "dash":       "-- @norm {code:<10} — {name}",
}

# @vault: templates — note path without .md extension, aligned for readability
_VAULT_TAG_TEMPLATES = {
    "line":       "// @vault: {note_path}  — {title}",
    "hash":       "# @vault: {note_path}  — {title}",
    "open_close": "<!-- @vault: {note_path}  — {title} -->",
    "block":      "/* @vault: {note_path}  — {title} */",
    "dash":       "-- @vault: {note_path}  — {title}",
}

_NORM_TAG_PATTERN = re.compile(
    r"^(?://|#|<!--|/\*|--)\s*@norm\s+(\S+)\s*[—\-]+\s*(.*?)(?:\s*(?:-->|\*/))?\s*$",
    re.MULTILINE,
)

# Matches: // @vault: 11_Code/project/module  — Title (type)
_VAULT_TAG_PATTERN = re.compile(
    r"^(?://|#|<!--|/\*|--)\s*@vault:\s*(\S+)\s*[—\-]+\s*(.*?)(?:\s*(?:-->|\*/))?\s*$",
    re.MULTILINE,
)


def _comment_style(file_path: Path) -> str:
    return _COMMENT_STYLES.get(file_path.suffix.lower(), "line")


def _format_norm_comment(code: str, name: str, style: str) -> str:
    tmpl = _COMMENT_TEMPLATES.get(style, _COMMENT_TEMPLATES["line"])
    return tmpl.format(code=code, name=name)


def _norm_block_pattern(style: str) -> re.Pattern:
    if style == "line":
        return re.compile(r"^(// @norm .+\n)+", re.MULTILINE)
    if style == "hash":
        return re.compile(r"^(# @norm .+\n)+", re.MULTILINE)
    if style == "open_close":
        return re.compile(r"^(<!-- @norm .+? -->\n)+", re.MULTILINE)
    if style == "block":
        return re.compile(r"^(/\* @norm .+? \*/\n)+", re.MULTILINE)
    if style == "dash":
        return re.compile(r"^(-- @norm .+\n)+", re.MULTILINE)
    return re.compile(r"(?!x)x")  # never matches fallback


# ─── Registry helpers ─────────────────────────────────────────────────────────

def _read_registry() -> Dict[str, Any]:
    if not _code_tag_registry().exists():
        return {"version": "v30", "tags": {}}
    try:
        return json.loads(_code_tag_registry().read_text(encoding="utf-8"))
    except Exception:
        return {"version": "v30", "tags": {}}


def _save_registry(reg: Dict[str, Any]) -> None:
    from datetime import datetime, timezone
    reg["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _code_tag_registry().parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_code_tag_registry(), reg)


#: Profundidad de reentrada del lock del registro, por hilo.
_ANIDAMIENTO = threading.local()


def _bajo_lock_del_registro(fn):
    """Serializa leer-mutar-guardar el registro de tags de código.

    `_read_registry()` y `_save_registry()` son atómicos cada uno por su lado,
    pero entre los dos hay una ventana: dos procesos que definen tags distintos
    a la vez leen el mismo estado y el segundo escribe encima del primero — la
    definición del primero desaparece sin que nada lo diga. `atomic_write_json`
    garantiza que nadie vea el fichero a medias; no garantiza que nadie pierda
    una actualización.

    El lock envuelve la función entera, no las dos llamadas por separado, porque
    la lectura ocurre al principio y la escritura al final con lógica en medio;
    tomar el lock dentro de `_read_registry` y soltarlo en `_save_registry` lo
    filtraría en cada camino que sale sin guardar.

    Es el mismo criterio que `vault_tags.record_new_tags` ya aplicaba a la
    bitácora de vocabulario: dos acumuladores equivalentes tenían dos criterios
    distintos de concurrencia (AP-05).

    Reentrante a propósito: `--define` con `--files` llama a `_apply` por cada
    fichero, y `file_lock` no es reentrante —el `threading.Lock` interno se
    bloquearía contra sí mismo y la operación moriría por timeout a los 30 s—.
    El contador es por hilo, así que la exclusión entre hilos y entre procesos
    se mantiene intacta: lo único que se permite es que el hilo que YA tiene el
    lock vuelva a entrar.
    """
    @functools.wraps(fn)
    def envuelta(*args, **kwargs):
        if getattr(_ANIDAMIENTO, "profundidad", 0):
            return fn(*args, **kwargs)
        _code_tag_registry().parent.mkdir(parents=True, exist_ok=True)
        with file_lock(_code_tag_registry(), timeout=30.0):
            _ANIDAMIENTO.profundidad = 1
            try:
                return fn(*args, **kwargs)
            finally:
                _ANIDAMIENTO.profundidad = 0

    return envuelta


# ─── Core operations ──────────────────────────────────────────────────────────

@_bajo_lock_del_registro
def vault_code_tag_define(
    code: str,
    name: str,
    description: str = "",
    files: Optional[List[str]] = None,
    created_by: str = "claude",
) -> Dict[str, Any]:
    """Register a custom code tag. Optionally apply it to files immediately."""
    from datetime import datetime, timezone

    if not code or not name:
        return emit_error("vault_code_tag", "MISSING_REQUIRED_ARG",
                          "--define exige --code y --name")

    reg = _read_registry()
    tags = reg.setdefault("tags", {})

    code_lower = code.lower()

    if code_lower in tags:
        # Update existing
        tags[code_lower]["name"] = name
        if description:
            tags[code_lower]["description"] = description
        _save_registry(reg)
        action = "updated"
    else:
        tags[code_lower] = {
            "name": name,
            "description": description,
            "files": [],
            "vault_note": None,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "created_by": created_by,
        }
        _save_registry(reg)
        action = "created"

    applied = []
    errors = []
    if files:
        for f in files:
            result = vault_code_tag_apply(code_lower, f)
            if result.get("ok"):
                applied.append(f)
            else:
                errors.append({"file": f, "error": result.get("error")})

    return {
        "ok": True,
        **write_report(),
        "action": action,
        "code": code_lower,
        "name": name,
        "applied_to": applied,
        "errors": errors,
    }


@_bajo_lock_del_registro
def vault_code_tag_apply(
    code: str,
    file_path_str: str,
    name_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Embed @norm comment in the header of a code file."""
    code_lower = code.lower()
    file_path = Path(file_path_str)

    file_path = resolve_input_path(file_path)

    if not file_path.exists():
        return emit_error("vault_code_tag", "FILE_NOT_FOUND", f"No existe: {file_path}")

    style = _comment_style(file_path)
    if style == "none":
        return emit_error(
            "vault_code_tag", "INVALID_ACTION",
            "Para ficheros .md usa `vault_norms --apply` (norm_refs en frontmatter); vault_code_tag es para código fuente.",
        )

    # Resolve tag name
    reg = _read_registry()
    tag_entry = reg.get("tags", {}).get(code_lower)
    if name_override:
        tag_name = name_override
    elif tag_entry:
        tag_name = tag_entry["name"]
    else:
        # Unknown code — look in norm catalog
        try:
            from vault_norms import _NORM_BY_CODE
            norm = _NORM_BY_CODE.get(code.upper())
            tag_name = norm["name"] if norm else code.upper()
        except Exception:
            tag_name = code.upper()

    comment_line = _format_norm_comment(code_lower, tag_name, style)

    try:
        original = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return emit_error("vault_code_tag", "FILE_READ_ERROR", f"No se pudo leer {file_path}: {e}", exception=e)

    # Check if this norm is already annotated
    existing_tags = _extract_tags_from_content(original)
    if code_lower in [t["code"].lower() for t in existing_tags]:
        return {"ok": True, "action": "already_present", "file": str(file_path), "code": code_lower}

    # Find insertion point: after shebang, after encoding declaration, after file header comment block
    lines = original.splitlines(keepends=True)
    insert_at = 0

    # Skip shebang line
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    # Skip existing @norm block if present (append to it instead)
    block_pat = _norm_block_pattern(style)
    block_match = block_pat.search(original[_line_offset(lines, insert_at):])
    if block_match and block_match.start() == 0:
        # There's already a @norm block — find its end and append there
        block_end_offset = _line_offset(lines, insert_at) + block_match.end()
        new_content = original[:block_end_offset] + comment_line + "\n" + original[block_end_offset:]
    else:
        # No existing @norm block — insert fresh at insert_at position
        offset = _line_offset(lines, insert_at)
        new_content = original[:offset] + comment_line + "\n" + original[offset:]

    try:
        from vault_io import atomic_write_text
        atomic_write_text(file_path, new_content)
    except Exception as e:
        return emit_error("vault_code_tag", "FILE_WRITE_ERROR", f"No se pudo escribir {file_path}: {e}", exception=e)

    # Update registry
    if tag_entry is not None:
        file_str = str(file_path)
        if file_str not in tag_entry.get("files", []):
            tag_entry.setdefault("files", []).append(file_str)
            _save_registry(reg)
    else:
        # Auto-register unknown code with minimal info
        reg.setdefault("tags", {})[code_lower] = {
            "name": tag_name,
            "description": "",
            "files": [str(file_path)],
            "vault_note": None,
            "created_at": "",
            "created_by": "auto",
        }
        _save_registry(reg)

    return {
        "ok": True,
        **write_report(),
        "action": "applied",
        "file": str(file_path),
        "code": code_lower,
        "comment": comment_line,
    }


@_bajo_lock_del_registro
def vault_code_tag_remove(code: str, file_path_str: str) -> Dict[str, Any]:
    """Remove a @norm comment from a code file."""
    code_lower = code.lower()
    file_path = Path(file_path_str)
    file_path = resolve_input_path(file_path)

    if not file_path.exists():
        return emit_error("vault_code_tag", "FILE_NOT_FOUND", f"No existe: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return emit_error("vault_code_tag", "FILE_READ_ERROR", f"No se pudo leer {file_path}: {e}", exception=e)

    # Remove the specific @norm line for this code
    pattern = re.compile(
        r"^(?://|#|<!--|/\*|--)\s*@norm\s+" + re.escape(code_lower) + r"\b.*?\n",
        re.MULTILINE | re.IGNORECASE,
    )
    new_content, count = pattern.subn("", content)

    if count == 0:
        return {"ok": True, "action": "not_found", "file": str(file_path), "code": code_lower}

    from vault_io import atomic_write_text
    atomic_write_text(file_path, new_content)

    # Update registry
    reg = _read_registry()
    tag_entry = reg.get("tags", {}).get(code_lower)
    if tag_entry and str(file_path) in tag_entry.get("files", []):
        tag_entry["files"].remove(str(file_path))
        _save_registry(reg)

    return {"ok": True, "action": "removed", "file": str(file_path), "code": code_lower, "lines_removed": count}


def vault_code_tag_scan(file_path_str: str) -> Dict[str, Any]:
    """List all @vault: and @norm tags present in a code file."""
    file_path = Path(file_path_str)
    file_path = resolve_input_path(file_path)

    if not file_path.exists():
        return emit_error("vault_code_tag", "FILE_NOT_FOUND", f"No existe: {file_path}")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return emit_error("vault_code_tag", "FILE_READ_ERROR", f"No se pudo leer {file_path}: {e}", exception=e)

    # Extract @vault: reference (at most one per file)
    vault_ref = _extract_vault_ref_from_content(content)

    # Verify vault note exists if referenced
    vault_note_exists = False
    if vault_ref:
        note_path = _raiz() / (vault_ref["note_path"] + ".md")
        vault_note_exists = note_path.exists()

    # Extract @norm tags
    norm_tags = _extract_tags_from_content(content)
    reg = _read_registry()
    for t in norm_tags:
        entry = reg.get("tags", {}).get(t["code"].lower())
        if entry:
            t["description"] = entry.get("description", "")
            t["vault_note"] = entry.get("vault_note")

    return {
        "ok": True,
        **write_report(),
        "file": str(file_path),
        "vault_ref": vault_ref,
        "vault_note_exists": vault_note_exists,
        "norm_tags_total": len(norm_tags),
        "norm_tags": norm_tags,
        "linked": vault_ref is not None,
    }


def vault_code_tag_list(
    file_filter: Optional[str] = None,
    prefix_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """List all registered code tags, optionally filtered."""
    reg = _read_registry()
    tags = reg.get("tags", {})

    result = []
    for code, entry in tags.items():
        if prefix_filter and not code.lower().startswith(prefix_filter.lower()):
            continue
        if file_filter:
            files = entry.get("files", [])
            if not any(file_filter.lower() in f.lower() for f in files):
                continue
        result.append({
            "code": code,
            "name": entry.get("name", ""),
            "description": entry.get("description", ""),
            "files": entry.get("files", []),
            "vault_note": entry.get("vault_note"),
            "created_at": entry.get("created_at", ""),
        })

    result.sort(key=lambda x: x["code"])
    return {"ok": True, "total": len(result), "tags": result}


@_bajo_lock_del_registro
def vault_code_tag_note(code: str, agent: str = "claude") -> Dict[str, Any]:
    """Create a vault note in 11_Code/ documenting this code tag."""
    code_lower = code.lower()
    reg = _read_registry()
    entry = reg.get("tags", {}).get(code_lower)

    if not entry:
        return emit_error("vault_code_tag", "INVALID_ACTION",
                          f"El tag '{code_lower}' no está definido; defínelo antes con --define")

    name = entry.get("name", code_lower)
    description = entry.get("description", "")
    files = entry.get("files", [])

    file_links = "\n".join(f"- `{f}`" for f in files) if files else "- *(sin archivos asociados aún)*"

    content = f"""## Descripción

{description or '*(sin descripción)*'}

## Archivos anotados

{file_links}

## Cómo aplicar

Para añadir este tag a un archivo de código:
```
vault_code_tag --apply {code_lower} --file <ruta/al/archivo>
```

Para ver todos los tags en un archivo:
```
vault_code_tag --scan --file <ruta/al/archivo>
```

## Norma de referencia

Código: `{code_lower}`
Nombre: {name}
"""

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from vault_write import vault_write
        result = vault_write(
            folder="11_Code",
            title=f"{code_lower} — {name}",
            content=content,
            tags=["code-tag", code_lower.split("-")[0]],
            meta={"agent": agent, "status": "active"},
        )
    except Exception as e:
        return emit_error("vault_code_tag", "FILE_WRITE_ERROR", f"vault_write falló: {e}", exception=e)

    if result.get("ok"):
        note_path = result["path"]
        entry["vault_note"] = note_path
        _save_registry(reg)
        return {"ok": True, "vault_note": note_path, "code": code_lower}

    return result


# ─── @vault: link / unlink ────────────────────────────────────────────────────

@_bajo_lock_del_registro
def vault_code_tag_link_vault(
    note_path_rel: str,
    file_path_str: str,
    title: str = "",
) -> Dict[str, Any]:
    """Embed a @vault: reference in the header of a source file.

    The @vault: tag is always placed FIRST in the tag block (before @norm lines)
    to make the vault documentation reference the most prominent annotation.

    Args:
        note_path_rel: Path to vault note relative to vault root, WITHOUT .md extension
                       e.g. "11_Code/my-api/auth-service"
        file_path_str: Absolute or CWD-relative path to the source file
        title:         Short description shown after — in the tag (40 chars max)
    """
    file_path = Path(file_path_str)
    file_path = resolve_input_path(file_path)

    if not file_path.exists():
        return {"ok": False, "error_code": "FILE_NOT_FOUND",
                "detail": f"Source file not found: {file_path}"}

    style = _comment_style(file_path)
    if style == "none":
        return {"ok": False, "error_code": "UNSUPPORTED_FORMAT",
                "detail": "Use frontmatter norm_refs for .md files."}

    # Normalize note path: strip .md if accidentally included, use forward slashes
    note_ref = note_path_rel.replace("\\", "/").removesuffix(".md")
    tag_title = (title or note_ref.split("/")[-1])[:60]

    tmpl = _VAULT_TAG_TEMPLATES.get(style, _VAULT_TAG_TEMPLATES["line"])
    vault_comment = tmpl.format(note_path=note_ref, title=tag_title)

    try:
        original = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(e)}

    # If there's already a @vault: tag, replace it (idempotent)
    existing = _VAULT_TAG_PATTERN.search(original)
    if existing:
        if existing.group(1).strip() == note_ref:
            return {"ok": True, "action": "already_present",
                    "file": str(file_path), "note": note_ref}
        # Different vault reference — replace with new one
        new_content = _VAULT_TAG_PATTERN.sub(vault_comment, original, count=1)
        action = "replaced"
    else:
        # No @vault: yet — insert before any @norm block (or at top after shebang)
        lines = original.splitlines(keepends=True)
        insert_at = 1 if (lines and lines[0].startswith("#!")) else 0
        offset = _line_offset(lines, insert_at)
        new_content = original[:offset] + vault_comment + "\n" + original[offset:]
        action = "linked"

    try:
        from vault_io import atomic_write_text
        atomic_write_text(file_path, new_content)
    except Exception as e:
        return {"ok": False, "error_code": "WRITE_ERROR", "detail": str(e)}

    # Register in code-tag-registry under a synthetic key
    reg = _read_registry()
    vault_key = f"vault:{note_ref.replace('/', ':')}"
    tags = reg.setdefault("tags", {})
    if vault_key not in tags:
        from datetime import datetime, timezone
        tags[vault_key] = {
            "name": tag_title,
            "description": f"Vault note: {note_ref}",
            "files": [],
            "vault_note": note_ref + ".md",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "created_by": "vault_code_tag",
            "tag_type": "vault_ref",
        }
    file_str = str(file_path)
    if file_str not in tags[vault_key].get("files", []):
        tags[vault_key].setdefault("files", []).append(file_str)
    _save_registry(reg)

    return {
        "ok": True,
        **write_report(),
        "action": action,
        "file": str(file_path),
        "note": note_ref,
        "comment": vault_comment,
    }


@_bajo_lock_del_registro
def vault_code_tag_unlink_vault(file_path_str: str) -> Dict[str, Any]:
    """Remove the @vault: tag from a source file."""
    file_path = Path(file_path_str)
    file_path = resolve_input_path(file_path)

    if not file_path.exists():
        return {"ok": False, "error_code": "FILE_NOT_FOUND",
                "detail": f"File not found: {file_path}"}

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error_code": "READ_ERROR", "detail": str(e)}

    new_content, count = _VAULT_TAG_PATTERN.subn("", content)
    if count == 0:
        return {"ok": True, "action": "not_found", "file": str(file_path)}

    from vault_io import atomic_write_text
    atomic_write_text(file_path, new_content)
    return {"ok": True, "action": "unlinked", "file": str(file_path), "lines_removed": count}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_vault_ref_from_content(content: str) -> Optional[Dict[str, str]]:
    """Extract the @vault: reference from file content, if present."""
    m = _VAULT_TAG_PATTERN.search(content)
    if not m:
        return None
    return {"note_path": m.group(1).strip(), "title": m.group(2).strip()}


def _extract_tags_from_content(content: str) -> List[Dict[str, str]]:
    tags = []
    for m in _NORM_TAG_PATTERN.finditer(content):
        code = m.group(1).strip()
        name = m.group(2).strip()
        tags.append({"code": code, "name": name, "tag_type": "norm"})
    return tags


def _line_offset(lines: List[str], line_index: int) -> int:
    return sum(len(l) for l in lines[:line_index])


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Code Tag — aplica etiquetas @norm a archivos de código",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Definir una etiqueta personalizada
  python vault_code_tag.py --define cr-0989 --name "Cola de prioridad" --description "FIFO con pesos"

  # Aplicar a un archivo de código
  python vault_code_tag.py --apply cr-0989 --file "src/services/colas.cs"

  # Aplicar una norma del estándar (AP-XX, SP-XX, etc.) a código
  python vault_code_tag.py --apply AP-22 --file "scripts/vault_write.py"

  # Ver todos los @norm tags en un archivo
  python vault_code_tag.py --scan --file "src/services/colas.cs"

  # Eliminar un tag de un archivo
  python vault_code_tag.py --remove cr-0989 --file "src/services/colas.cs"

  # Listar todos los tags registrados
  python vault_code_tag.py --list

  # Listar tags de un archivo específico
  python vault_code_tag.py --list --file "colas.cs"

  # Listar tags con prefijo cr-
  python vault_code_tag.py --list --prefix cr

  # Crear nota en vault documentando el tag
  python vault_code_tag.py --tag-note cr-0989

Formatos de comentario por extensión:
  .cs .ts .js .java .go .cpp  →  // @norm cr-0989 — Cola de prioridad
  .py .rb .sh .yml .yaml      →  # @norm cr-0989 — Cola de prioridad
  .html .xml                  →  <!-- @norm cr-0989 — Cola de prioridad -->
  .css .scss                  →  /* @norm cr-0989 — Cola de prioridad */
  .sql                        →  -- @norm cr-0989 — Cola de prioridad
  .md                         →  ⚠ usar vault_norms --apply (frontmatter norm_refs)
""",
    )

    # Operations
    parser.add_argument("--define",       metavar="CODE",       help="Definir/actualizar una etiqueta @norm personalizada")
    parser.add_argument("--apply",        metavar="CODE",       help="Aplicar @norm a un archivo de código")
    parser.add_argument("--remove",       metavar="CODE",       help="Eliminar @norm de un archivo")
    parser.add_argument("--link-vault",   metavar="NOTE_PATH",  help="Embeber @vault: en archivo fuente (ruta nota sin .md)")
    parser.add_argument("--unlink-vault", action="store_true",  help="Eliminar @vault: de un archivo fuente")
    parser.add_argument("--scan",         action="store_true",  help="Listar @vault: y @norm en un archivo")
    parser.add_argument("--list",         action="store_true",  help="Listar todos los tags registrados")
    parser.add_argument("--tag-note",     metavar="CODE",       help="Crear nota en vault para este tag")

    # Parameters
    parser.add_argument("--file",        help="Ruta al archivo de código (absoluta o relativa al CWD)")
    parser.add_argument("--title",       help="Título para --link-vault (se muestra tras — en el tag)")
    parser.add_argument("--name",        help="Nombre descriptivo del tag (para --define o --apply)")
    parser.add_argument("--description", default="", help="Descripción detallada del tag")
    parser.add_argument("--files",       nargs="*", help="Lista de archivos para --define (aplica inmediatamente)")
    parser.add_argument("--prefix",      help="Filtrar --list por prefijo (ej: cr, impl, bus)")
    parser.add_argument("--agent",       default="claude", help="Agente que ejecuta la operación")

    args = parser.parse_args()

    if args.define:
        if not args.name:
            parser.error("--define requiere --name")
        result = vault_code_tag_define(
            code=args.define,
            name=args.name,
            description=args.description,
            files=args.files,
            created_by=args.agent,
        )
    elif args.apply:
        if not args.file:
            parser.error("--apply requiere --file")
        result = vault_code_tag_apply(
            code=args.apply,
            file_path_str=args.file,
            name_override=args.name,
        )
    elif args.link_vault:
        if not args.file:
            parser.error("--link-vault requiere --file")
        result = vault_code_tag_link_vault(
            note_path_rel=args.link_vault,
            file_path_str=args.file,
            title=args.title or "",
        )
    elif args.unlink_vault:
        if not args.file:
            parser.error("--unlink-vault requiere --file")
        result = vault_code_tag_unlink_vault(args.file)
    elif args.remove:
        if not args.file:
            parser.error("--remove requiere --file")
        result = vault_code_tag_remove(args.remove, args.file)
    elif args.scan:
        if not args.file:
            parser.error("--scan requiere --file")
        result = vault_code_tag_scan(args.file)
    elif args.list:
        result = vault_code_tag_list(
            file_filter=args.file,
            prefix_filter=args.prefix,
        )
    elif args.tag_note:
        result = vault_code_tag_note(args.tag_note, agent=args.agent)
    else:
        parser.print_help()
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_tag"))
