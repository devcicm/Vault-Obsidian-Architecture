"""Persistencia y recuperación directa de conocimiento Markdown.

Este módulo es la implementación estable del par ``vault_knowledge_save`` /
``vault_knowledge_get``. El índice de búsqueda histórico es una proyección:
la autoridad para recuperar conocimiento es el Markdown de ``07_Knowledge``.
Por eso esta frontera recibe la raíz explícitamente y no importa ``scripts``.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

import yaml

from .frontmatter import Frontmatter
from ..kernel.errores import construir_error
from ..kernel.escritura import escritura_atomica


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


def _validate_frontmatter(text: str) -> None:
    if not text.startswith("---\n"):
        raise ValueError("FRONTMATTER_MISSING")
    parts = text.split("---", 2)
    if len(parts) != 3 or not isinstance(yaml.safe_load(parts[1]), Mapping):
        raise ValueError("FRONTMATTER_PARSE_ERROR")


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
    """Persiste una nota canónica; el adaptador legacy puede inyectar su I/O."""
    category = category.lower().replace(" ", "-")
    if category not in CATEGORIES:
        return construir_error("vault_knowledge_save", "INVALID_VALUE", f"Categoría inválida: {category}. Válidas: {list(CATEGORIES)}")
    try:
        runtime = Path(root).resolve()
        if not runtime.is_dir():
            raise ValueError("runtime inexistente o no es directorio")
        filename = _slug(title)
        if not filename:
            raise ValueError("el título no produce un nombre de nota válido")
        path = _contained(runtime, runtime / "07_Knowledge" / CATEGORY_FOLDERS[category] / f"{filename}.md")
        text = _render(category, title, content, project, tags, related)
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


def _split_markdown(text: str) -> tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}, text
    try:
        data = yaml.safe_load(parts[1]) or {}
    except (yaml.YAMLError, RecursionError):
        return {}, text
    return (data if isinstance(data, dict) else {}), parts[2]


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


def recuperar_conocimiento(root: Union[str, Path], query: str, category: Optional[str] = None,
                            project: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Recupera desde Markdown, sin hacer de un índice una autoridad."""
    try:
        runtime = Path(root).resolve()
        directory = _contained(runtime, runtime / "07_Knowledge")
        if not runtime.is_dir() or not directory.is_dir():
            raise ValueError("runtime sin 07_Knowledge")
    except ValueError as exc:
        return construir_error("vault_knowledge_get", "VAULT_NOT_FOUND", str(exc))
    matches = []
    for path in directory.rglob("*.md"):
        try:
            metadata, body = _split_markdown(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        score = _score(metadata, body, query, category, project)
        if score:
            matches.append((score, path, metadata, body))
    matches.sort(key=lambda item: (-item[0], item[1].as_posix()))
    results = [
        {"path": path.relative_to(runtime).as_posix(), "title": str(data.get("title", path.stem)),
         "category": str(data.get("category", "")), "score": score}
        for score, path, data, _ in matches[:limit]
    ]
    response: Dict[str, Any] = {"ok": True, "query": query, "category": category,
                                "project": project, "total": len(matches), "results": results}
    if len(matches) == 1 and matches[0][0] >= 60:
        score, path, data, body = matches[0]
        response.update({"autoRead": True,
                         "topMatch": {"path": path.relative_to(runtime).as_posix(),
                                      "title": str(data.get("title", path.stem)), "score": score},
                         "topContent": body.strip()})
    return response
