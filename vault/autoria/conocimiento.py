"""Persistencia y recuperación directa de conocimiento Markdown.

Este módulo es la implementación estable del par ``vault_knowledge_save`` /
``vault_knowledge_get``. El índice de búsqueda histórico es una proyección:
la autoridad para recuperar conocimiento es el Markdown de ``07_Knowledge``.
Por eso esta frontera recibe la raíz explícitamente y no importa ``scripts``.
"""

from __future__ import annotations

import errno
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

import yaml

from .frontmatter import Frontmatter
from ..kernel.errores import construir_error
from ..kernel.escritura import escritura_atomica
from ..kernel.frontmatter_parsing import (
    FrontmatterParseError,
    parse_frontmatter_robust as _canon_parse_fm,
    parse_frontmatter_with_body,
)


CATEGORIES = (
    "glossary", "api", "concept", "business-rule", "config", "dependency", "framework",
)
CATEGORY_FOLDERS = {
    "glossary": "glossary", "api": "apis", "concept": "concepts",
    "business-rule": "business-rules", "config": "configs",
    "dependency": "dependencies", "framework": "frameworks",
}


def _slug(text: str) -> str:
    explicit = {"ß": "ss", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L"}
    text = "".join(explicit.get(char, char) for char in text)
    folded = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    ).lower()
    return re.sub(r"-{2,}", "-", re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", folded))).strip("-")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _contained(root: Path, path: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("INVALID_PATH: el destino cae fuera del runtime") from exc
    return path


class _FileLock:
    """Bloqueo exclusivo por nota, mismo patrón que vault_fs.file_lock.

    Crea .locks/<slug>.lock dentro del vault para evitar dependencias
    entre fronteras y no asumir que la carpeta de la nota ya existe.
    """

    def __init__(self, note_path: Path, timeout: float = 30.0) -> None:
        self._note_path = note_path
        self._lock_root = note_path.parent / ".locks"
        self._lock = self._lock_root / f"{note_path.stem}.lock"
        self._timeout = timeout

    def acquire(self) -> None:
        self._lock_root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                os.mkdir(self._lock)
                return
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"timeout acquiring lock for {self._note_path} after {self._timeout}s"
                    )
                time.sleep(0.05)

    def release(self) -> None:
        try:
            os.rmdir(self._lock)
        except OSError:
            pass

    def __enter__(self) -> "_FileLock":
        self.acquire()
        return self

    def __exit__(self, *_: Any) -> None:
        self.release()


def _validate_frontmatter(text: str) -> None:
    """Lanza ValueError si el texto no tiene frontmatter parseable."""
    try:
        parse_frontmatter_with_body(text)
    except FrontmatterParseError as exc:
        raise ValueError(f"FRONTMATTER_PARSE_ERROR: {exc}") from exc


def _atomic_write(path: Path, text: str) -> None:
    """Valida la nota y delega el mecanismo al primitive compartido."""
    _validate_frontmatter(text)
    escritura_atomica(path, text, encoding="utf-8")


def _render(category: str, title: str, content: str, project: Optional[str],
            tags: Optional[List[str]], related: Optional[List[str]]) -> str:
    timestamp = _timestamp()
    frontmatter = Frontmatter()
    frontmatter.set("title", title)
    frontmatter.set("id", str(uuid.uuid4()))
    frontmatter.set("category", category)
    frontmatter.set("createdAt", timestamp)
    frontmatter.set("updatedAt", timestamp)
    if project:
        frontmatter.set("project", project)
    if tags:
        frontmatter.set("tags", tags)
    if related:
        frontmatter.set("related", related)
    frontmatter.set("cia_integrity", "medium")
    frontmatter.set("cia_availability", "medium")
    frontmatter.set("cia_sensitivity", "internal")
    frontmatter.set("agent", "system")
    if category in ("dependency", "framework"):
        parts = [f"## {title}\n", f"\n**Propósito:** {content}\n", "\n**Caveats:** *(pendiente de documentar)*\n"]
        body = "\n".join(parts)
    else:
        body = content
    if related and category not in ("dependency", "framework"):
        body += "\n\n## Relacionado\n\n" + " ".join(f"[[{item}]]" for item in related)
    return frontmatter.render() + "\n\n" + body


def guardar_conocimiento(
    root: Union[str, Path],
    category: str,
    title: str,
    content: str,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    related: Optional[List[str]] = None,
    *,
    writer: Optional[Callable[[Path, str], None]] = None,
    report: Optional[Callable[[], Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Persiste una nota canónica; el adaptador legacy puede inyectar su I/O.

    FL-01: verificación de identidad antes de escribir.
    Identidad = category + slug(título). Si existe una nota con el mismo slug
    y distinto project → IDENTITY_CONFLICT. Proyecto ausente en ambas
    escrituras → actualización intencional (misma identidad).
    """
    category = category.lower().replace(" ", "-")
    if category not in CATEGORIES:
        return construir_error(
            "vault_knowledge_save", "INVALID_VALUE",
            f"Categoría inválida: {category}. Válidas: {list(CATEGORIES)}"
        )
    try:
        runtime = Path(root).resolve()
        if not runtime.is_dir():
            raise ValueError("runtime inexistente o no es directorio")
        filename = _slug(title)
        if not filename:
            raise ValueError("el título no produce un nombre de nota válido")
        path = _contained(
            runtime,
            runtime / "07_Knowledge" / CATEGORY_FOLDERS[category] / f"{filename}.md"
        )
    except ValueError as exc:
        return construir_error("vault_knowledge_save", "FILE_WRITE_ERROR", str(exc))

    text = _render(category, title, content, project, tags, related)

    with _FileLock(path, timeout=30.0):
        existing_project = None
        existing_legible = False

        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8")
                fm, _ = _canon_parse_fm(raw)
                existing_project = fm.get("project")
                existing_legible = True
            except UnicodeDecodeError:
                return construir_error(
                    "vault_knowledge_save", "IDENTITY_CONFLICT",
                    f"archivo no legible: {path.name}",
                    extra={"path": path.relative_to(runtime).as_posix()}
                )
            except FrontmatterParseError:
                existing_legible = False

        if existing_legible and (existing_project or None) != (project or None):
            return construir_error(
                "vault_knowledge_save", "IDENTITY_CONFLICT",
                f"el slug '{filename}' ya existe con project='{existing_project}'",
                extra={
                    "path": path.relative_to(runtime).as_posix(),
                    "conflict_project": existing_project,
                    "attempted_project": project,
                }
            )

        try:
            (writer or _atomic_write)(path, text)
        except (OSError, ValueError) as exc:
            return construir_error("vault_knowledge_save", "FILE_WRITE_ERROR", str(exc))

    payload: Dict[str, Any] = {
        "ok": True,
        "path": path.relative_to(runtime).as_posix(),
        "category": category,
        "title": title,
        "message": f"Knowledge note saved to {CATEGORY_FOLDERS[category]}/",
    }
    if report:
        payload = {**payload, **dict(report())}
    return payload


def _score(metadata: Mapping[str, Any], body: str, query: str,
           category: Optional[str], project: Optional[str]) -> int:
    if category and str(metadata.get("category", "")).lower() != category.lower():
        return 0
    if project and str(metadata.get("project", "")).lower() != project.lower():
        return 0
    query = query.lower()
    title = str(metadata.get("title", "")).lower()
    body_lower = body.lower()
    score = 40 if query in title else 0
    score += 20 if query in body_lower else 0
    for word in query.split():
        score += 4 if word in title else 0
        score += 1 if word in body_lower else 0
    return score


def recuperar_conocimiento(
    root: Union[str, Path],
    query: str,
    category: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Recupera desde Markdown, sin hacer de un índice una autoridad."""
    try:
        runtime = Path(root).resolve()
        directory = _contained(runtime, runtime / "07_Knowledge")
        if not runtime.is_dir() or not directory.is_dir():
            raise ValueError("runtime sin 07_Knowledge")
    except ValueError as exc:
        return construir_error("vault_knowledge_get", "VAULT_NOT_FOUND", str(exc))

    matches: List[tuple[int, Path, Dict[str, Any], str]] = []
    unreadable: List[Dict[str, Any]] = []

    for path in directory.rglob("*.md"):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            unreadable.append({"path": path.relative_to(runtime).as_posix(), "reason": str(exc)})
            continue

        fm, body, parse_ok, error_msg = _canon_parse_fm(raw)
        if not parse_ok:
            unreadable.append({"path": path.relative_to(runtime).as_posix(), "reason": error_msg})
            continue

        score = _score(fm, body, query, category, project)
        if score:
            matches.append((score, path, fm, body))

    matches.sort(key=lambda item: (-item[0], item[1].as_posix()))
    results = [
        {
            "path": path.relative_to(runtime).as_posix(),
            "title": str(data.get("title", path.stem)),
            "category": str(data.get("category", "")),
            "score": score,
        }
        for score, path, data, _ in matches[:limit]
    ]

    warnings: List[str] = []
    if unreadable:
        warnings.append(
            f"Notas no procesables ({len(unreadable)}): "
            + ", ".join(u["path"] for u in unreadable)
        )

    response: Dict[str, Any] = {
        "ok": True,
        "query": query,
        "category": category,
        "project": project,
        "total": len(matches),
        "results": results,
        "warnings": warnings,
    }

    if unreadable:
        response["unreadable_files"] = unreadable
        response["unreadable_count"] = len(unreadable)

    if len(matches) == 1 and matches[0][0] >= 60:
        score, path, data, body = matches[0]
        response.update({
            "autoRead": True,
            "topMatch": {
                "path": path.relative_to(runtime).as_posix(),
                "title": str(data.get("title", path.stem)),
                "score": score,
            },
            "topContent": body.strip(),
        })

    return response
