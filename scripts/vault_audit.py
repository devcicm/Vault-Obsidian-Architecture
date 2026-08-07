#!/usr/bin/env python3

"""

Vault Audit — Health check for the active vault.



Blueprint: vault-obsidian-architecture.md § vault_audit(project?)



Usage:

    python vault_audit.py

    python vault_audit.py --project "mi-proyecto"

"""

import argparse

import hashlib

import json

import os

import re

import subprocess

import sys

from vault_registry import es_andamio
from vault_errors import wrap_main

from collections import defaultdict

from datetime import datetime, timezone

from difflib import SequenceMatcher

from pathlib import Path

from typing import Any, Dict, List, Optional, Set, Tuple


from vault_io import is_snapshot_path, normalize_stem as _normalize
from vault_regex import (
    detect_bracket_anomalies,
    RE_NESTED_OPEN_3,
    RE_NESTED_CLOSE_3,
    RE_EMPTY_LINK,
)
from vault_mermaid_check import scan_vault as _scan_mermaid

SCRIPTS_DIR = Path(__file__).parent


SKIP_FOLDERS = {"vault-backups", ".history"}

STALE_DAYS = 30

STUCK_PATTERN_DAYS = 7

STALE_PROJECT_DAYS = 14


VAULT_DQ_CACHE_MINUTES = int(os.environ.get("VAULT_DQ_CACHE_MINUTES", "30"))


# Archivos estructurales: auto-generados o de convención, no son "notas de contenido"

# Se excluyen de: orphans, stale, AP-17, duplicados

# Se INCLUYEN en: fuentes de backlinks, broken links detection

_STRUCTURAL_NAMES = frozenset({"index.md", "readme.md"})


PLACEHOLDER_PATTERNS = [
    "yyyy",
    "nombre",
    "link-a",
    "{slug}",
    "archivo",
    "patron",
    "imagen",
    "img",
    "prisma",
    "postgres",
    "express",
    "hexagonal",
    "jsonwebtoken",
]


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _tag_registry() -> Path:
    return _repo().registro_etiquetas


def _quality_index() -> Path:
    return _repo().indice_calidad


def _propagation_queue() -> Path:
    return _repo().cola_propagacion


def _is_skipped(path: Path) -> bool:
    path_str = str(path.relative_to(_raiz()))

    if ".vault-fix-backup-" in path_str:
        return True

    return any(skip in path_str for skip in SKIP_FOLDERS)


def _is_structural(path: Path) -> bool:
    return path.name.lower() in _STRUCTURAL_NAMES


def _get_active_notes(
    project: Optional[str] = None, include_structural: bool = False
) -> List[Path]:
    notes = []

    for n in _raiz().rglob("*.md"):
        if _is_skipped(n) or n.name.startswith("_"):
            continue

        if not include_structural and _is_structural(n):
            continue

        if project:
            rel = str(n.relative_to(_raiz()))

            if project not in rel:
                continue

        notes.append(n)

    return notes


from vault_lib import read_frontmatter


def _note_updated_at(path: Path) -> datetime:
    fm = read_frontmatter(path)

    for field in ("updatedAt", "updated_at", "createdAt"):
        val = fm.get(field, "")

        if val:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val[: len(fmt) - 2], fmt[: len(val[:19])])

                except ValueError:
                    continue

            try:
                return datetime.fromisoformat(val[:19])

            except ValueError:
                pass

    return datetime.fromtimestamp(path.stat().st_mtime)


def _extract_wiki_links(
    content: str, known: Optional[Set[str]] = None
) -> List[str]:
    """Wikilinks del contenido, descartando placeholders de plantilla.

    `known` son los stems normalizados de las notas que existen de verdad. Un
    enlace cuyo destino existe NO es un placeholder, por mucho que empiece por
    uno de los prefijos: `PLACEHOLDER_PATTERNS` casa por `startswith`, asi que
    `patron`, `nombre`, `imagen`, `express`... se tragaban todo enlace a una
    nota real cuyo nombre empezara asi. En el vault de BuilderX eso dejaba
    `patron-dsl-compilacion`, `patron-mcp-streaming` y
    `patron-blastmode-weavingmode` reportados como huerfanos con 6, 8 y 2
    enlaces entrantes respectivamente.

    Es AP-44: la tool decidia con criterio propio que algo no era un enlace, en
    vez de preguntarle al vault si el destino existe. Sin `known` el
    comportamiento es el de antes, que es el correcto para una plantilla vacia.
    """
    content_clean = re.sub(r"```[\s\S]*?```", "", content)

    content_clean = re.sub(r"`[^`]+`", "", content_clean)

    links = []

    for m in re.finditer(r"\[\[([^\]]+)\]\]", content_clean):
        link = m.group(1).strip()

        if "|" in link:
            link = link.split("|")[0].strip()

        if link.startswith("http") or link.startswith("#"):
            continue

        if not (known and _normalize(link) in known) and any(
            link.lower().startswith(ph) for ph in PLACEHOLDER_PATTERNS
        ):
            continue

        links.append(link)

    return links


def _normalize(s: str) -> str:
    """Normalize a stem for fuzzy comparison.

    Strips: case, dashes, underscores, spaces, dots, and the .md suffix.
    Matches vault_write._collect_ghost_links normalization so a wiki-link
    like `[[Mi Proyecto Demo]]` correctly resolves to `mi-proyecto-demo.md`.
    """
    return (
        s.lower()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace(".", "")
        .removesuffix("md")
    )


def _is_snapshot(p: Path) -> bool:
    """True si la nota vive en una instantanea congelada del vault.

    Relativo a `VAULT_ROOT`, no absoluto: con la ruta absoluta, un directorio
    ancestro FUERA del vault llamado `.trash` excluiria el vault entero en
    silencio. Fuera de la raiz no hay nada que excluir.
    """
    try:
        return is_snapshot_path(p.relative_to(_raiz()))
    except ValueError:  # pragma: no cover -- rglob siempre cuelga de la raiz
        return False


#: Notas que el audit no consiguió leer en esta ejecución. Ver `_leer_nota`.
_LECTURAS_FALLIDAS: List[Dict[str, str]] = []


def _reset_degradacion() -> None:
    """Vacía el registro al empezar un audit: es por ejecución, no por proceso."""
    _LECTURAS_FALLIDAS.clear()


def degradaciones() -> List[Dict[str, str]]:
    """Lecturas que fallaron en el último audit, para tests y para el envelope."""
    return list(_LECTURAS_FALLIDAS)


def _leer_nota(p: Path, *, errors: str = "ignore", binario: bool = False):
    """Lee una nota; si no puede, lo **registra** y devuelve `None`.

    Nueve sitios del audit hacían `except Exception: continue` sobre la lectura
    de una nota. Saltarse la nota es lo correcto —un audit no puede caerse porque
    un fichero esté bloqueado—, pero hacerlo **en silencio** invierte el
    resultado: cada nota ilegible es una nota que no aporta hallazgos, así que el
    `healthScore` **sube** cuanto menos se puede leer del vault. Un vault con
    permisos rotos se audita como un vault sano, que es AP-37 en su forma más
    cara: el fallo no se cuenta como fallo, se cuenta como éxito.

    No se cambia el comportamiento —se sigue saltando la nota—, se cambia lo que
    el envelope sabe: `degraded[]` dice sobre cuántas notas NO se pronunció el
    audit, y `healthScore` deja de ser una cifra sobre un universo desconocido.
    """
    try:
        return p.read_bytes() if binario else p.read_text(
            encoding="utf-8", errors=errors
        )
    except Exception as exc:  # noqa: BLE001 — el audit nunca se cae por una nota
        try:
            rel = str(p.relative_to(_raiz())).replace("\\", "/")
        except ValueError:
            rel = str(p)
        _LECTURAS_FALLIDAS.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
        return None


def _aliases_de(p: Path) -> List[str]:
    """Alias declarados en el frontmatter, tolerando forma escalar.

    Obsidian acepta `aliases: nombre` ademas de la lista; leer solo la lista
    dejaria fuera enlaces que el lector resuelve. Un frontmatter ilegible no es
    motivo para fallar un audit: se devuelve vacio.
    """
    try:
        fm = read_frontmatter(p) or {}
    except Exception:
        return []
    raw = fm.get("aliases") or fm.get("alias") or []
    if isinstance(raw, str):
        raw = [raw]
    return [a for a in raw if isinstance(a, str) and a.strip()]


def _build_indexes(notes: List[Path]) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build backlink index and full-vault stem set for broken-link detection."""

    stem_map: Dict[str, str] = {}

    for n in notes:
        stem_map[_normalize(n.stem)] = n.stem

    all_stems: Set[str] = set()

    for n in _raiz().rglob("*.md"):
        # `.history` era la unica exclusion; `vault-backups/` y `.trash/` entraban,
        # y con ellas los enlaces de instantaneas congeladas. `is_snapshot_path`
        # centraliza el criterio en `vault_io` (AP-36): los side-effects viven
        # dentro del vault, asi que todo barrido debe saber distinguirlos.
        if not _is_snapshot(n):
            all_stems.add(_normalize(n.stem))
            # Register folder/stem paths: [[section/note]] resolves even if stem alone not unique
            try:
                rel = n.relative_to(_raiz())
                if len(rel.parts) >= 2:
                    folder_stem = "".join(list(rel.parts[:-1])) + rel.stem
                    all_stems.add(_normalize(folder_stem))
            except ValueError:
                pass
            # Obsidian resuelve `[[X]]` por nombre de fichero O por `aliases:`,
            # nunca por `title:`. Sin leer los alias, el audit declaraba roto todo
            # enlace que usara el nombre legible de una nota — 46 instancias en el
            # vault de BuilderX que Obsidian abre sin problema. Un contador que
            # no modela la resolucion real del lector manda a reescribir enlaces
            # que funcionan.
            for alias in _aliases_de(n):
                all_stems.add(_normalize(alias))

    backlinks: Dict[str, Set[str]] = defaultdict(set)

    for n in notes:
        content = _leer_nota(n)
        if content is None:
            continue

        for link in _extract_wiki_links(content, known=all_stems):
            target_key = _normalize(link)

            if target_key in stem_map:
                backlinks[stem_map[target_key]].add(n.stem)

    return backlinks, all_stems


def _detect_orphans(
    notes: List[Path], backlinks: Dict[str, Set[str]]
) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    orphans = []

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        if rel.startswith("00_System"):
            continue

        # Session notes are inherently orphan — each session is the start
        # of a new conversation. They are referenced by date, not by other
        # notes. Excluding them from orphan detection avoids false positives.
        if rel.startswith("04_Sessions/"):
            continue

        if backlinks.get(n.stem):
            continue

        # Scaffolds (vault_init primers) are placeholders by design —
        # they don't need inbound links. The user is expected to replace
        # them with real content; the nextActions block in the audit output
        # reminds them to do so. Excluding scaffolds avoids false-positive
        # orphan warnings on a freshly initialized vault.
        text = _leer_nota(n, errors="replace")
        if text is not None and es_andamio(text):
            continue

        fm = read_frontmatter(n)

        days_old = (now - _note_updated_at(n)).days

        orphans.append(
            {
                "path": rel,
                "title": fm.get("title", n.stem),
                "daysOld": days_old,
            }
        )

    return orphans


def _detect_stale(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    stale = []

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        if rel.startswith("00_System"):
            continue

        days = (now - _note_updated_at(n)).days

        if days > STALE_DAYS:
            fm = read_frontmatter(n)

            stale.append(
                {
                    "path": rel,
                    "title": fm.get("title", n.stem),
                    "daysSinceUpdate": days,
                }
            )

    return stale


def _detect_stuck_patterns(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    stuck = []

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        if "05_Patterns" not in rel:
            continue

        fm = read_frontmatter(n)

        status = fm.get("status", "").lower().replace("-", "_")

        if status not in ("en_progreso", "in_progress"):
            continue

        days = (now - _note_updated_at(n)).days

        if days > STUCK_PATTERN_DAYS:
            stuck.append(
                {
                    "path": rel,
                    "title": fm.get("title", n.stem),
                    "status": fm.get("status", "en_progreso"),
                    "daysSinceUpdate": days,
                }
            )

    return stuck


def _detect_stale_projects(notes: List[Path]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    stale_projects = []

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        if "01_Projects" not in rel or n.name != "status.md":
            continue

        days = (now - _note_updated_at(n)).days

        if days > STALE_PROJECT_DAYS:
            fm = read_frontmatter(n)

            stale_projects.append(
                {
                    "path": rel,
                    "title": fm.get("title", n.stem),
                    "daysSinceUpdate": days,
                }
            )

    return stale_projects


def _detect_broken_links(
    notes: List[Path], all_stems: Set[str]
) -> List[Dict[str, Any]]:
    broken = []

    # Pre-compute a set of relative paths for path-anchored link resolution.
    # Wiki-links like [[02_Observability/antipatterns/ap-foo]] should resolve
    # to a file at that relative path. The audit was treating them as broken
    # because stem-only normalization doesn't match the full path.
    all_paths: Set[str] = set()
    for n in _raiz().rglob("*.md"):
        if not _is_snapshot(n):
            rel = str(n.relative_to(_raiz())).replace("\\", "/")
            # Add both with and without .md extension
            all_paths.add(rel.lower())
            if rel.lower().endswith(".md"):
                all_paths.add(rel[:-3].lower())

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        # Spec/reference files contain wiki-link SYNTAX examples that are
        # documentation, not real links. Exclude them from broken-link detection.
        if (
            n.name == "vault-obsidian-architecture.md"
            or "/scripts/" in rel
            or rel.startswith("scripts/")
        ):
            continue

        content = _leer_nota(n)
        if content is None:
            continue

        for link in _extract_wiki_links(content, known=all_stems):
            if _normalize(link) in all_stems:
                continue

            # Try path-anchored resolution: the link might be a relative
            # file path that Obsidian can resolve. Check if a file exists
            # at this path (case-insensitive).
            link_normalized = link.lower().replace("\\", "/")
            if link_normalized in all_paths:
                continue

            broken.append({"from": rel, "link": link})

    return broken


#: Marcadores de convención de nomenclatura que distinguen DOS artefactos
#: distintos, no dos nombres del mismo. Cada uno es una convención de lenguaje,
#: no una preferencia de estilo: en C#/Java, `IRateLimitService` es el contrato y
#: `RateLimitService` la implementación; son dos cosas, y cada una merece su nota.
#:
#: (prefijo, sufijo) — uno de los dos, no ambos.
_MARCADORES_DE_CONVENCION: List[Tuple[str, str]] = [
    ("i", ""),  # C#/TypeScript: IFooService  vs FooService
    ("abstract", ""),  # Java: AbstractFooService vs FooService
    ("base", ""),  # BaseFooService vs FooService
    ("default", ""),  # DefaultFooService vs FooService
    ("", "impl"),  # Java: FooServiceImpl vs FooService
    ("", "implementation"),
    ("", "interface"),  # FooServiceInterface vs FooService
    ("mock", ""),  # dobles de prueba: MockFooService vs FooService
    ("fake", ""),
    ("stub", ""),
    ("null", ""),  # Null Object (GoF): NullFooService vs FooService
    ("noop", ""),
]
#: Lo que NO entra en la lista importa tanto como lo que entra. `Async`,
#: `Secure`, `Cached` y compañía describen una VARIANTE, no un rol dentro del
#: mismo contrato: `SecureApiKeyService` junto a `IApiKeyService` puede ser un
#: decorador legítimo o puede ser la nota duplicada que AP-17 existe para
#: encontrar, y eso lo decide una persona. Ampliar la lista hasta que no quede
#: ningún par sería silenciar la norma, no afinarla.


def _distintos_por_convencion(titulo_a: str, titulo_b: str) -> Optional[str]:
    """¿Los dos títulos son artefactos distintos por convención de nombres?

    Devuelve el marcador que los distingue, o None.

    Síntoma que lo motivó: `vault_onboard` contra un proyecto .NET real dio
    `canonicalShadow: 8`, todos del mismo par —interfaz e implementación—. AP-17
    compara títulos en minúsculas, y bajar la `I` de `IRateLimitService` borra
    justo el carácter que los distingue: la similitud sale ~0.98 SIEMPRE. No es
    un problema de umbral —bajarlo esconde el síntoma y ciega la norma— sino de
    criterio: se estaba midiendo con la normalización propia en vez de con la
    del dominio (AP-44). Cualquier proyecto .NET, Java o TypeScript dispara esto
    en proporción a su número de servicios.
    """
    a = re.sub(r"[^a-z0-9]", "", titulo_a.lower())
    b = re.sub(r"[^a-z0-9]", "", titulo_b.lower())
    if a == b:
        return None  # mismo nombre: eso sí es una sombra

    def _quitar(nombre: str) -> List[Tuple[str, str]]:
        """El nombre desnudo, con y sin marcador. Uno como mucho."""
        salidas = [(nombre, "")]
        for prefijo, sufijo in _MARCADORES_DE_CONVENCION:
            if prefijo and nombre.startswith(prefijo) and len(nombre) > len(prefijo):
                salidas.append((nombre[len(prefijo) :], f"{prefijo}*"))
            if sufijo and nombre.endswith(sufijo) and len(nombre) > len(sufijo):
                salidas.append((nombre[: -len(sufijo)], f"*{sufijo}"))
        return salidas

    # Se quita a los dos lados, no solo a uno: `ILoggerService` y
    # `MockLoggerService` son dos artefactos del mismo contrato y ninguno es
    # prefijo del otro.
    for desnudo_a, marca_a in _quitar(a):
        for desnudo_b, marca_b in _quitar(b):
            if desnudo_a == desnudo_b and (marca_a or marca_b):
                return " / ".join(m for m in (marca_a, marca_b) if m)
    return None


def _detect_canonical_shadow(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-17: detect pairs of notes with fuzzy title similarity >85% (SequenceMatcher ratio)."""

    # Exclude structural files — identical names across sections are by design, not duplicates

    _EXCLUDED_STEMS = {"index", "readme", "change-log", "changelog", "gitkeep"}

    pairs = []

    items = []

    for n in notes:
        if n.stem.lower() in _EXCLUDED_STEMS:
            continue

        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        # Spec/reference files have the same title by design (it's the spec).
        # Exclude them from canonical-shadow detection.
        if (
            n.name == "vault-obsidian-architecture.md"
            or "/scripts/" in rel
            or rel.startswith("scripts/")
        ):
            continue

        # Session notes have similar titles by design (e.g. "2026-06-13",
        # "2026-06-14"). They're daily logs, not duplicates.
        if rel.startswith("04_Sessions/"):
            continue

        # Scaffolds (vault_init primers) are templates by design — all have
        # similar titles and structure. Excluding them avoids false positives.
        text = _leer_nota(n, errors="replace")
        if text is not None and es_andamio(text):
            continue

        fm = read_frontmatter(n)

        title = fm.get("title", n.stem).lower()

        items.append((rel, title))

    seen: set = set()

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            rel_a, title_a = items[i]

            rel_b, title_b = items[j]

            if _distintos_por_convencion(title_a, title_b):
                continue

            ratio = SequenceMatcher(None, title_a, title_b).ratio()

            if ratio >= 0.85:
                key = tuple(sorted([rel_a, rel_b]))

                if key not in seen:
                    seen.add(key)

                    pairs.append(
                        {
                            "noteA": rel_a,
                            "noteB": rel_b,
                            "titleA": title_a,
                            "titleB": title_b,
                            "similarity": round(ratio, 3),
                        }
                    )

    return pairs


def _detect_malformed_wikilinks(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-22 / AP-24: detect notes with malformed wiki-link brackets.

    Returns a list of findings with:
      - path: relative path of the offending note
      - norm_code: AP-22 (empty [[]]) or AP-24 (imbalance: opens != closes,
        nested brackets, inverted, or stray brackets)
      - kind: empty | imbalance_open | imbalance_close | nested | inverted
      - opens / closes: bracket counts (after stripping code blocks)
      - snippets: list of {line, text} with the offending context (first 3)
      - examples: short strings demonstrating each problem (first 3)

    Excluded:
      - vault-obsidian-architecture.md (the spec itself documents [[...]] syntax)
      - /scripts/* (tools contain regex examples that legitimately use brackets)
      - .bak backups (side-effects of upgrades)
      - sandbox directories (test fixtures)
    """

    findings: List[Dict[str, Any]] = []

    # Patterns - using 3+ detection from vault_regex for better coverage
    RE_OPEN = re.compile(r"\[\[")
    RE_CLOSE = re.compile(r"\]\]")
    RE_EMPTY = RE_EMPTY_LINK  # Use vault_regex version
    RE_NESTED_OPEN = RE_NESTED_OPEN_3  # [[[ (3+ opens) - more sensitive
    RE_NESTED_CLOSE = RE_NESTED_CLOSE_3  # ]]] (3+ closes) - more sensitive
    # NOTE: "inverted" detection (]] … [[) is done via stack-based scanning
    # below — a naive regex here would false-positive on legitimate wiki-links
    # where `]]` from one link precedes `[[` of another link on a later line.

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        # Spec/reference files contain unbalanced bracket examples as part
        # of documenting the syntax. Exclude them.
        if (
            n.name == "vault-obsidian-architecture.md"
            or "/scripts/" in rel
            or rel.startswith("scripts/")
            or ".bak" in rel
            or ".vault-fix-backup-" in rel
            or "vault-sandbox" in rel
        ):
            continue

        content = _leer_nota(n)
        if content is None:
            continue

        # Strip code blocks and inline code so we don't count regex examples
        clean = re.sub(r"```[\s\S]*?```", "", content)
        clean = re.sub(r"`[^`\n]+`", "", clean)

        opens = len(RE_OPEN.findall(clean))
        closes = len(RE_CLOSE.findall(clean))
        empty_matches = list(RE_EMPTY.finditer(clean))
        nested_open = list(RE_NESTED_OPEN.finditer(clean))
        nested_close = list(RE_NESTED_CLOSE.finditer(clean))

        # Stack-based detection of stray closes (inverted order) and unclosed
        # opens. More reliable than a regex pattern across the full text,
        # which would false-positive on legitimate links where `]]` from one
        # link precedes `[[` of another link on a later line.
        stack_depth = 0
        stray_closes = 0
        stray_close_examples: List[str] = []
        i = 0
        while i < len(clean):
            if clean[i : i + 2] == "[[":
                stack_depth += 1
                i += 2
            elif clean[i : i + 2] == "]]":
                if stack_depth == 0:
                    stray_closes += 1
                    start = max(0, i - 12)
                    end = min(len(clean), i + 14)
                    stray_close_examples.append(clean[start:end].replace("\n", " "))
                else:
                    stack_depth -= 1
                i += 2
            else:
                i += 1
        leftover_opens = stack_depth

        # Detect when an imbalance is fully resolvable by nested-collapse fixes
        # (so we don't false-block apply mode for fixable pathologies).
        resolvable = (
            leftover_opens <= len(nested_open) * 2
            and stray_closes <= len(nested_close) * 2
        )

        # Collect all bracket problems found in this note (filled below).
        problems: List[Dict[str, Any]] = []

        # AP-22: empty [[]] (no info — safe to auto-fix)
        if empty_matches:
            examples = [m.group(0) for m in empty_matches[:3]]
            problems.append(
                {
                    "kind": "empty",
                    "norm_code": "AP-22",
                    "count": len(empty_matches),
                    "examples": examples,
                    "auto_fixable": True,
                    "fix_hint": "Eliminar `[[]]` (vacío sin info)",
                }
            )

        # AP-24: nested [[ [[ — auto-fixable (collapse)
        if nested_open:
            examples = [m.group(0) for m in nested_open[:3]]
            problems.append(
                {
                    "kind": "nested_open",
                    "norm_code": "AP-24",
                    "count": len(nested_open),
                    "examples": examples,
                    "auto_fixable": True,
                    "fix_hint": "Colapsar `[[[[` → `[[` (dobles corchetes anidados)",
                }
            )

        # AP-24: nested ]] ]] — auto-fixable (collapse)
        if nested_close:
            examples = [m.group(0) for m in nested_close[:3]]
            problems.append(
                {
                    "kind": "nested_close",
                    "norm_code": "AP-24",
                    "count": len(nested_close),
                    "examples": examples,
                    "auto_fixable": True,
                    "fix_hint": "Colapsar `]]]]` → `]]` (dobles corchetes anidados)",
                }
            )

        # AP-24: inverted ]] [[ detected via stack (manual review when unresolvable)
        if stray_closes > 0 and not resolvable:
            problems.append(
                {
                    "kind": "inverted",
                    "norm_code": "AP-24",
                    "count": stray_closes,
                    "examples": stray_close_examples[:3],
                    "auto_fixable": False,
                    "fix_hint": "Orden invertido `]]…[[` (stray close sin open previo). Probable copy-paste mal pegado.",
                }
            )
        elif stray_closes > 0 and resolvable:
            problems.append(
                {
                    "kind": "inverted_resolvable",
                    "norm_code": "AP-24",
                    "count": stray_closes,
                    "examples": stray_close_examples[:3],
                    "auto_fixable": True,
                    "fix_hint": "Stray closes se resolverán al colapsar `]]]]` con nested_close",
                }
            )

        # AP-24: leftover opens at EOF (manual review when unresolvable)
        if leftover_opens > 0 and not resolvable:
            problems.append(
                {
                    "kind": "unclosed_open",
                    "norm_code": "AP-24",
                    "count": leftover_opens,
                    "auto_fixable": False,
                    "fix_hint": f"{leftover_opens} `[[` sin cerrar al final del texto",
                }
            )
        elif leftover_opens > 0 and resolvable:
            problems.append(
                {
                    "kind": "unclosed_open_resolvable",
                    "norm_code": "AP-24",
                    "count": leftover_opens,
                    "auto_fixable": True,
                    "fix_hint": "Opens sin cerrar se resolverán al colapsar `[[[[` con nested_open",
                }
            )

        if not problems:
            continue

        # Collect snippets with line + context for the first 3 problems
        snippets: List[Dict[str, Any]] = []
        for prob in problems[:3]:
            pattern_str = prob.get("examples", [""])
            if not pattern_str or pattern_str == [""]:
                # For imbalance, find the first stray bracket
                if prob["kind"] in ("imbalance_open", "imbalance_close"):
                    target = "[[" if prob["kind"] == "imbalance_open" else "]]"
                    for i, line in enumerate(content.split("\n"), start=1):
                        if target in line:
                            snippets.append({"line": i, "text": line.strip()[:160]})
                            break
            else:
                first_ex = prob["examples"][0]
                for i, line in enumerate(content.split("\n"), start=1):
                    if first_ex in line:
                        snippets.append({"line": i, "text": line.strip()[:160]})
                        break

        # Pick primary norm_code (AP-24 wins over AP-22 if both present)
        primary_norm = (
            "AP-24" if any(p["norm_code"] == "AP-24" for p in problems) else "AP-22"
        )
        kinds = sorted({p["kind"] for p in problems})
        counts = {p["kind"]: p["count"] for p in problems}

        findings.append(
            {
                "path": rel,
                "from": rel,  # alias for consistency with brokenLinks output
                "norm_code": primary_norm,
                "kinds": kinds,
                "counts": counts,
                "opens": opens,
                "closes": closes,
                "auto_fixable": all(p["auto_fixable"] for p in problems),
                "snippets": snippets,
                "problems": problems,
            }
        )

    return findings


def _detect_cross_folder_duplicates(notes: List[Path]) -> List[Dict[str, Any]]:
    """AP-18: detect byte-identical content across different folders via MD5 hash."""

    hash_map: Dict[str, List[str]] = defaultdict(list)

    for n in notes:
        content = _leer_nota(n, binario=True)
        if content is None:
            continue

        digest = hashlib.md5(content).hexdigest()

        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        hash_map[digest].append(rel)

    duplicates = []

    for digest, paths in hash_map.items():
        if len(paths) > 1:
            # Only report cross-folder duplicates (different top-level dirs)

            folders = {p.split("/")[0] for p in paths}

            if len(folders) > 1:
                duplicates.append({"hash": digest, "files": paths})

    return duplicates


#: Secciones que solo existen cuando ocurre algo. Estar vacías es su estado
#: correcto mientras no haya pasado nada — no es cobertura pendiente.
_SECCIONES_POR_EVENTO = frozenset({"18_Bugs", "19_Audits", "20_Quarantine"})


def _detect_empty_indexes() -> List[Dict[str, Any]]:
    """AP-11/AP-03: detect section folders whose index.md has no real notes.



    Scans every top-level vault folder for real notes (excludes index.md / README.md).

    Reports folders that exist but have zero content notes — their index is a stub.

    """

    empty = []

    try:
        for section_dir in sorted(_raiz().iterdir()):
            if not section_dir.is_dir():
                continue

            name = section_dir.name

            if name.startswith(".") or name in ("scripts", ".history", "vault-backups"):
                continue

            # Skip backup directories created by vault_init --clean or
            # manual copies. These shouldn't be treated as vault sections.
            if name.endswith(".bak") or ".bak-" in name or name == "vault-sandbox":
                continue

            # Secciones dirigidas por eventos: se pueblan cuando ocurre el
            # evento, no al crear el vault. Contarlas como deuda empuja a
            # llenarlas —y llenarlas significa inventar bugs, auditorías y
            # cuarentenas que no han pasado, que es exactamente AP-45—. Un
            # vault sano recién creado tiene estas tres vacías; reprobarlo por
            # eso enfrentaba a dos normas del propio estándar entre sí.
            if name in _SECCIONES_POR_EVENTO:
                continue

            real_notes = [
                p
                for p in section_dir.rglob("*.md")
                if p.name.lower() not in ("index.md", "readme.md")
                and not any(part.startswith(".") for part in p.parts)
            ]

            index_md = section_dir / "index.md"

            if len(real_notes) == 0:
                empty.append(
                    {
                        "norm_code": "AP-03",
                        "folder": name,
                        "index_exists": index_md.exists(),
                        "note": "Seccion sin notas — index es stub sin contenido real",
                    }
                )

    except Exception:
        pass

    return empty


def _detect_mermaid_errors() -> List[Dict[str, Any]]:
    """AP-25: detect Mermaid diagram syntax errors.

    Uses vault_mermaid_check to scan all diagrams and collect errors.
    """
    errors = []
    try:
        result = _scan_mermaid()
        for res in result.get("results", []):
            if not res.get("valid", True):
                file_path = res.get("file", "")
                for block in res.get("blocks", []):
                    if not block.get("valid", True):
                        for err in block.get("errors", []):
                            errors.append(
                                {
                                    "norm_code": "AP-25",
                                    "path": file_path,
                                    "block_index": block.get("index", 0),
                                    "error_type": err.get("type", "unknown"),
                                    "message": err.get("message", ""),
                                    "suggestion": err.get("suggestion", ""),
                                }
                            )
    except Exception:
        pass
    return errors


def _detect_graph_knowledge_antipatterns() -> Dict[str, Any]:
    """AP-31/34/35: detect knowledge graph antipatterns in graph-enriched.json.

    Returns dict with:
      - ap31_typed_ratio: percentage of edges that are typed (non-wiki_link)
      - ap34_orphan_relations: list of typed relations with unresolved endpoints
      - ap35_silo_flags: silo detection flags
    """
    ENRICHED_FILE = _raiz() / "99_Index" / "graph-enriched.json"
    ENTITY_DIR = _raiz() / "06_Diagrams" / "entity"
    CODE_INDEX = _raiz() / "11_Code" / ".code-index.json"

    result: Dict[str, Any] = {
        "ap31_typed_ratio": 0.0,
        "ap31_penalty": 0,
        "ap34_orphan_relations": [],
        "ap35_silo_flags": {},
    }

    has_entity = ENTITY_DIR.exists() and list(ENTITY_DIR.glob("*relations.json"))
    has_code = CODE_INDEX.exists()

    if not has_entity and not has_code:
        return result

    try:
        silo_flags = {}
        entity_files = list(ENTITY_DIR.glob("*relations.json")) if ENTITY_DIR.exists() else []
        silo_flags["entity_files"] = len(entity_files)
        silo_flags["code_index_exists"] = has_code

        if ENRICHED_FILE.exists():
            from datetime import datetime, timezone as tz
            raw = ENRICHED_FILE.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raw = raw[3:]
            enriched = json.loads(raw.decode("utf-8"))
            last_merge = enriched.get("metadata", {}).get("merged_at", "")
            if last_merge:
                dt = datetime.fromisoformat(last_merge.replace("Z", "+00:00"))
                hours_old = (datetime.now(tz.utc) - dt).total_seconds() / 3600
                silo_flags["graph_enriched_hours_old"] = round(hours_old, 1)
                silo_flags["graph_enriched_stale"] = hours_old > 24
            else:
                silo_flags["graph_enriched_stale"] = True
        else:
            silo_flags["graph_enriched_exists"] = False
            silo_flags["graph_enriched_stale"] = True

        result["ap35_silo_flags"] = silo_flags

        if ENRICHED_FILE.exists():
            raw2 = ENRICHED_FILE.read_bytes()
            if raw2.startswith(b"\xef\xbb\xbf"):
                raw2 = raw2[3:]
            enriched = json.loads(raw2.decode("utf-8"))
            total = enriched.get("metadata", {}).get("total_edges", 0)
            typed = enriched.get("metadata", {}).get("typed_edges", 0)
            if total > 0:
                result["ap31_typed_ratio"] = round(typed / total, 3)
                if result["ap31_typed_ratio"] < 0.1 and (has_entity or has_code):
                    result["ap31_penalty"] = 5

            diagnostics = enriched.get("diagnostics", {})
            entity_diag = diagnostics.get("entity_relations", {})
            code_diag = diagnostics.get("code_relations", {})

            unresolved_entity = entity_diag.get("unresolved", 0)
            unresolved_code = code_diag.get("unresolved", 0)

            if unresolved_entity > 0:
                result["ap34_orphan_relations"].append({
                    "source": "entity",
                    "count": unresolved_entity,
                    "norm_code": "AP-34",
                    "description": f"{unresolved_entity} entity relations with unresolved endpoints",
                })
            if unresolved_code > 0:
                result["ap34_orphan_relations"].append({
                    "source": "code",
                    "count": unresolved_code,
                    "norm_code": "AP-34",
                    "description": f"{unresolved_code} code relations with unresolved endpoints",
                })
    except Exception:
        pass

    return result


def _frontmatter_de(bloque: str) -> Dict[str, Any]:
    """Frontmatter de un bloque YAML, con degradación a lectura por líneas.

    El audit tenía su propio mini-parser: `^(\\w[\\w_-]*):\\s*(.+)$` línea a
    línea. Un campo en forma de lista —

        tags:
          - bug
          - error

    — no casa, porque la línea `tags:` no tiene valor. El campo quedaba como
    ausente y AP-26 reportaba "sin tags" sobre notas correctamente etiquetadas:
    45 de ellas en BuilderX, a -2 puntos de health score cada una. El vocabulario
    en bloque es la forma que escriben `vault_write` y `vault_tags`, así que el
    audit no veía lo que el propio estándar produce.

    Se usa YAML primero. El regex se conserva como red: `yaml.safe_load` devuelve
    `{}` ante un frontmatter mal formado (un `title:` con dos puntos sin comillas
    basta), y en ese caso leer algo por líneas es mejor que declarar la nota
    entera sin metadatos.
    """
    datos: Dict[str, Any] = {}
    try:
        import yaml

        cargado = yaml.safe_load(bloque)
        if isinstance(cargado, dict):
            # A texto los tipos que YAML materializa y `json.dumps` no sabe
            # escribir: `date: 2026-07-12` sin comillas llega como
            # `datetime.date` y reventaba la serialización del informe entero.
            # El audit solo mira presencia y título, así que el texto basta.
            datos = {
                k: (v if isinstance(v, (str, int, float, bool, list, dict)) else str(v))
                for k, v in cargado.items()
                if v is not None
            }
    except Exception:
        datos = {}

    if datos:
        return datos

    for line in bloque.split("\n"):
        kv = re.match(r"^(\w[\w_-]*):\s*(.+)$", line)
        if kv:
            datos[kv.group(1)] = kv.group(2).strip()
    return datos


def _detect_missing_metadata(notes: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
    """AP-16/26/27/29/30: detect notes missing required frontmatter fields.

    Returns dict with lists for each missing field category.
    System notes (00_System/) and index.md are excluded from content checks.
    """
    missing_tags = []
    missing_agent = []
    missing_type = []
    missing_status = []
    missing_cia = []
    missing_updated = []
    missing_frontmatter = []
    for p in notes:
        raw = _leer_nota(p, errors="strict")
        if raw is None:
            continue
        rel = str(p.relative_to(_raiz())).replace("\\", "/")
        # Todo `99_Index/` es artefacto derivado — lo escriben `vault_reindex` y
        # `vault_tags` a partir de las notas, y se regenera entero en cada
        # ejecución. Exigirle tags o `type` a `tag-index.md` pide metadatos a un
        # informe: se perderían en la siguiente regeneración. Antes solo se
        # libraban los `index.md`, así que el índice de tags quedaba señalado.
        is_index = (
            rel.endswith("/index.md") or rel == "index.md" or rel.startswith("99_Index/")
        )
        is_system = rel.startswith("00_System/") or rel == "00_System"

        fm = {}
        m = re.match(r"^---\s*\n(.*?)\n---", raw, re.DOTALL)
        if m:
            fm = _frontmatter_de(m.group(1))
        else:
            if not is_index:
                missing_frontmatter.append({"path": rel, "title": p.stem})
            continue

        if not is_index and not is_system:
            tags_val = fm.get("tags", "")
            if not tags_val or tags_val in ("[]", "[ ]", ""):
                missing_tags.append({"path": rel, "title": fm.get("title", p.stem)})

            if not fm.get("type"):
                missing_type.append({"path": rel, "title": fm.get("title", p.stem)})

            if not fm.get("status"):
                missing_status.append({"path": rel, "title": fm.get("title", p.stem)})

            cia_fields = ["cia_integrity", "cia_availability", "cia_sensitivity"]
            missing_cia_local = [c for c in cia_fields if c not in fm]
            if missing_cia_local:
                missing_cia.append({"path": rel, "title": fm.get("title", p.stem), "missing": missing_cia_local})

        if not fm.get("agent"):
            missing_agent.append({"path": rel, "title": fm.get("title", p.stem)})

        if not fm.get("updatedAt"):
            missing_updated.append({"path": rel, "title": fm.get("title", p.stem)})

    return {
        "missing_tags": missing_tags,
        "missing_agent": missing_agent,
        "missing_type": missing_type,
        "missing_status": missing_status,
        "missing_cia": missing_cia,
        "missing_updated": missing_updated,
        "missing_frontmatter": missing_frontmatter,
    }


# ─────────────────────────────────────────────────────────────────────────────
# nextActions helpers — used by vault_audit to prescribe remediation
# ─────────────────────────────────────────────────────────────────────────────

# Pistas de tool con argumentos de ejemplo. El comentario anterior decía que
# esto «refleja el registro para que el comando siga siendo correcto aunque el
# registro cambie» — que es justo lo contrario de lo que hace un espejo: cuando
# el registro cambia, la copia se queda vieja y nadie se entera. Lo que aporta
# de verdad es el ejemplo de argumentos, así que se queda como capa de
# enriquecimiento y lo que no cubre lo pone el registro, no un genérico.
_SECTION_TOOL_HINT: Dict[str, str] = {
    "01_Projects": "vault_project_overview --project <slug> --description '...' --runtime 'Node.js 20'",
    "02_Observability": "vault_log_error --project <slug> --error '<msg>'",
    "03_Decisions": "vault_write --folder 03_Decisions --title 'ADR-001 <titulo>' --content '...'",
    "04_Sessions": "vault_write --folder 04_Sessions --title '$(date +%Y-%m-%d)' --content '...'",
    "05_Patterns": "vault_pattern_save --project <slug> --name <patron> --status planificado",
    "06_Diagrams": "vault_diagram_save --project <slug> --type erd --content '...'",
    "07_Knowledge": "vault_knowledge_save --project <slug> --title <concepto> --category concept",
    "08_Runbooks": "vault_runbook_save --project <slug> --title <runbook> --steps '...'",
    "09_Infrastructure": "vault_infra_save --project <slug> --name <servicio> --type server",
    "10_Migrated": "vault_migrate_docs --source <path>",
    "11_Code": "vault_code_module --project <slug> --file_path <path> --description '...'",
    "12_Bibliography": "vault_bibliography_save --title <ref> --type web --url '...'",
    "13_Flows": "vault_flow_save --project <slug> --title <flow> --type workflow",
    "14_Requirements": "vault_requirement_save --project <slug> --title 'REQ-001 ...'",
    "15_Tests": "vault_test_save --project <slug> --title <test> --type unit",
    "16_AI_Governance": "vault_ai_decision --project <slug> --title <decision> --decision_type architecture",
    # Sin entrada, `_suggest_command_for_folder` caía al genérico `vault_write`
    # para las cuatro secciones más nuevas: la acción sugerida saltaba la tool
    # con contrato y su guard. La sugerencia de un audit es la que el usuario
    # copia y pega, así que apuntar al camino sin gobernar es peor que no
    # sugerir nada.
    "17_Preferences": "vault_preferences --set --title <preferencia> --statement '...' --strength should",
    "18_Bugs": "vault_bug_save --project <slug> --title <bug> --severity high",
    "19_Audits": "vault_tags --audit",
    "20_Quarantine": "vault_quarantine --list",
}


def _suggest_command_for_folder(folder: str) -> str:
    """Return a copy-paste ready command for populating an empty section."""
    from vault_registry import section_tool_hint

    hint = _SECTION_TOOL_HINT.get(folder) or section_tool_hint(folder)
    if hint:
        return f"python scripts/{hint}"
    return f"python scripts/vault_write --folder {folder} --title '<titulo>' --content '...'"


def _detect_scaffold_only_sections(content_notes: List[Path]) -> List[str]:
    """Return sections that contain ONLY a vault_init primer (scaffold:true).

    These sections are at 100/100 thanks to the primer but the user should
    replace it with real content. Used by nextActions when score == 100.
    """
    sections_with_scaffold: Dict[str, bool] = {}
    sections_with_real: Dict[str, bool] = {}
    for n in content_notes:
        rel = n.relative_to(_raiz())
        if not rel.parts:
            continue
        section = rel.parts[0]
        text = _leer_nota(n, errors="replace")
        is_scaffold = text is not None and (
            es_andamio(text)
        )
        if is_scaffold:
            sections_with_scaffold[section] = True
        else:
            sections_with_real[section] = True
    result = []
    for sec, has_scaffold in sections_with_scaffold.items():
        if has_scaffold and not sections_with_real.get(sec, False):
            result.append(sec)
    return sorted(result)


def _get_roadmap_for_populated_vault(content_notes: List[Path]) -> List[Dict[str, Any]]:
    """When score == 100 AND no scaffolds, suggest what to document NEXT.

    This is the "what to do once everything is green" guidance: documented
    ADRs, runbooks, requirements, tests, SLOs, etc. Each item is ordered
    by the value it adds to the vault's coverage of the standard.
    """
    by_folder: Dict[str, int] = {}
    for n in content_notes:
        rel = n.relative_to(_raiz())
        if rel.parts:
            by_folder[rel.parts[0]] = by_folder.get(rel.parts[0], 0) + 1

    actions: List[Dict[str, Any]] = []
    # Progression: once green, the next valuable things to add.
    if by_folder.get("01_Projects", 0) < 3:
        actions.append(
            {
                "priority": "high",
                "category": "guidance",
                "description": "Documenta cada proyecto activo con `vault_project_overview` (mínimo 3 proyectos para cobertura significativa).",
                "command": "python scripts/vault_project_overview.py --project <slug> --description '...' --runtime '...'",
            }
        )
    if by_folder.get("03_Decisions", 0) < 2:
        actions.append(
            {
                "priority": "high",
                "category": "guidance",
                "description": "Registra tus decisiones arquitectónicas (ADRs). Mínimo 2 para mostrar el proceso.",
                "command": "python scripts/vault_write.py --folder 03_Decisions --title 'ADR-001 ...' --content '## Contexto\\n\\n## Opciones\\n\\n## Decision\\n\\n## Consecuencias'",
            }
        )
    if by_folder.get("08_Runbooks", 0) < 1:
        actions.append(
            {
                "priority": "medium",
                "category": "guidance",
                "description": "Crea al menos un runbook para el procedimiento más crítico (deploy, rollback, incident response).",
                "command": "python scripts/vault_runbook_save.py --project <slug> --title 'Deploy' --steps '...'",
            }
        )
    if by_folder.get("02_Observability", 0) < 1:
        actions.append(
            {
                "priority": "medium",
                "category": "guidance",
                "description": "Registra SLOs y métricas operacionales con `vault_slo_save` y `vault_log_error`.",
                "command": "python scripts/vault_slo_save.py --project <slug> --title 'API Availability' --sli 'requests < 500ms' --objective 99.9",
            }
        )
    if by_folder.get("14_Requirements", 0) < 1:
        actions.append(
            {
                "priority": "medium",
                "category": "guidance",
                "description": "Documenta los requerimientos formales (ISO 29148) con trazabilidad a tests y código.",
                "command": "python scripts/vault_requirement_save.py --project <slug> --title 'REQ-001 ...'",
            }
        )
    if by_folder.get("15_Tests", 0) < 1:
        actions.append(
            {
                "priority": "medium",
                "category": "guidance",
                "description": "Registra los casos de test formales (ISO 29119) con trazabilidad a requirements.",
                "command": "python scripts/vault_test_save.py --project <slug> --title 'Test: ...' --type unit",
            }
        )
    if by_folder.get("11_Code", 0) < 1:
        actions.append(
            {
                "priority": "medium",
                "category": "guidance",
                "description": "Documenta tus módulos de código siguiendo IEEE 1016 con `vault_code_module --tag-source` para inyectar trazabilidad bidireccional.",
                "command": "python scripts/vault_code_module.py --project <slug> --file_path <path> --description '...' --tag-source",
            }
        )
    if by_folder.get("16_AI_Governance", 0) < 1 and len(content_notes) > 20:
        actions.append(
            {
                "priority": "low",
                "category": "guidance",
                "description": "Una vez que el vault tenga >20 notas, registra decisiones de agentes IA (ISO 42001) en `16_AI_Governance/`.",
                "command": "python scripts/vault_ai_decision.py --project <slug> --title '<decision>' --decision_type architecture",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "low",
                "category": "guidance",
                "description": "Vault maduro. Siguiente: ejecuta `python scripts/vault_backup.py` para crear un snapshot con Merkle tree, y `python scripts/vault_drift_detect.py --path . --project <slug> --mode report` para detectar drift desde el último backup.",
            }
        )
    return actions


def _read_quality_index() -> Optional[Dict[str, Any]]:
    if not _quality_index().exists():
        return None

    try:
        return json.loads(_quality_index().read_text(encoding="utf-8"))

    except Exception:
        return None


def _dq_is_stale(qi: Dict[str, Any]) -> bool:
    generated_at = qi.get("generated_at", "")

    if not generated_at:
        return True

    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))

        age_minutes = (datetime.now(timezone.utc) - dt).total_seconds() / 60

        return age_minutes > VAULT_DQ_CACHE_MINUTES

    except Exception:
        return True


def _dq_is_locked() -> bool:
    lock_dir = _quality_index().parent / f".{_quality_index().name}.lock"

    return lock_dir.exists()


def _refresh_dq_if_needed() -> Dict[str, Any]:
    """Return dqHealth from current quality-index.json and trigger background refresh if stale."""

    qi = _read_quality_index()

    needs_refresh = (qi is None) or _dq_is_stale(qi)

    if needs_refresh and _dq_is_locked():
        dq_status = "update_in_progress"

    elif needs_refresh:
        # Fire quality_check in background — do NOT wait; read stale data immediately

        try:
            subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / "vault_quality_check.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            dq_status = "refreshing_in_background" if qi else "unavailable"

        except Exception:
            dq_status = "stale" if qi else "unavailable"

    else:
        dq_status = "fresh"

    overall = qi.get("overall_dq_score") if qi else None

    below = qi.get("notes_below_07") if qi else None

    generated_at = qi.get("generated_at") if qi else None

    generated_by = qi.get("generated_by") if qi else None

    dq_health: Dict[str, Any] = {
        "dq_status": dq_status,
        "threshold": 0.7,
    }

    if overall is not None:
        dq_health["overall_dq_score"] = overall

    if below is not None:
        dq_health["notes_below_threshold"] = below

    if generated_at:
        dq_health["generated_at"] = generated_at

    if generated_by:
        dq_health["generated_by"] = generated_by

    return dq_health


def _read_propagation_pending() -> List[Dict[str, Any]]:
    """Read propagation-queue.json and return pending items sorted by priority."""

    if not _propagation_queue().exists():
        return []

    try:
        data = json.loads(_propagation_queue().read_text(encoding="utf-8"))

        pending = data.get("pending", [])

        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        pending.sort(
            key=lambda e: (
                -risk_order.get(e.get("priority", "low"), 1),
                e.get("queued_at", ""),
            )
        )

        return [
            {
                "path": e["path"],
                "since": e.get("queued_at", ""),
                "priority": e.get("priority", "low"),
            }
            for e in pending
        ]

    except Exception:
        return []


def _cia_score_penalty(
    notes: List[Path],
    stale: List[Dict[str, Any]],
    propagation_pending: List[Dict[str, Any]],
) -> int:
    """Extra health score penalty from CIA-weighted stale notes and propagation_pending."""

    penalty = 0

    stale_paths = {s["path"] for s in stale}

    pending_paths = {p["path"] for p in propagation_pending}

    for n in notes:
        rel = str(n.relative_to(_raiz())).replace("\\", "/")

        fm = read_frontmatter(n)

        integrity = fm.get("cia_integrity", "medium").lower()

        if rel in stale_paths and integrity in ("critical",):
            penalty += 5

        if rel in pending_paths:
            penalty += 2

    return penalty


def _read_tag_health() -> Optional[Dict[str, Any]]:
    """Load tag-registry.json and return tag health summary. Returns None if registry absent."""

    if not _tag_registry().exists():
        return None

    try:
        registry = json.loads(_tag_registry().read_text(encoding="utf-8"))

    except Exception:
        return None

    tags = registry.get("tags", {})

    untagged = registry.get("untagged_notes", [])

    orphaned = [t for t, info in tags.items() if info.get("count", 0) == 0]

    tag_names = list(tags.keys())

    near_dupes = 0

    seen_pairs: set = set()

    for i, tag_a in enumerate(tag_names):
        for tag_b in tag_names[i + 1 :]:
            pair = tuple(sorted([tag_a, tag_b]))

            if pair in seen_pairs:
                continue

            a, b = tag_a.lower(), tag_b.lower()

            if a in b or b in a:
                score = 0.85

            else:
                common = sum(1 for x, y in zip(a, b) if x == y)

                score = common / max(len(a), len(b))

            if score >= 0.6:
                seen_pairs.add(pair)

                near_dupes += 1

    tag_health_score = 100

    tag_health_score -= len(orphaned) * 5

    tag_health_score -= near_dupes * 3

    tag_health_score -= min(len(untagged) * 2, 30)

    tag_health_score = max(0, tag_health_score)

    return {
        "total_tags": len(tags),
        "orphaned_tags": orphaned,
        "near_duplicate_pairs": near_dupes,
        "untagged_notes_count": len(untagged),
        "tag_health_score": tag_health_score,
        "registry_at": registry.get("updatedAt", "?"),
    }


def vault_audit(
    project: Optional[str] = None, refresh_dq: bool = False
) -> Dict[str, Any]:
    """

    Run health audit on the active vault.



    Args:

        project:    Optional project slug to filter audit scope.

        refresh_dq: If True, refresh quality-index.json if stale (VAULT_DQ_CACHE_MINUTES threshold).



    Returns:

        { healthScore, stats, issues, dqHealth?, propagationPending?, summary }

    """

    # El registro de lecturas fallidas es por auditoría, no por proceso: sin esto
    # una segunda llamada en el mismo intérprete arrastraría las degradaciones de
    # la primera y las contaría dos veces.
    _reset_degradacion()

    # content_notes: notas reales (excluye index.md/README.md)

    # all_notes: incluye estructurales — para que sus links cuenten como backlinks

    content_notes = _get_active_notes(project, include_structural=False)

    all_notes = _get_active_notes(project, include_structural=True)

    # Indexes construidos desde all_notes para que index.md contribuya backlinks

    backlinks, all_stems = _build_indexes(all_notes)

    orphans = _detect_orphans(content_notes, backlinks)

    stale = _detect_stale(content_notes)

    stuck_patterns = _detect_stuck_patterns(content_notes)

    stale_projects = _detect_stale_projects(content_notes)

    # broken_links en all_notes: index.md roto también importa (fix 2026-06-21: scope bug — antes pasaba content_notes)

    broken_links = _detect_broken_links(all_notes, all_stems)

    canonical_shadow = _detect_canonical_shadow(content_notes)

    cross_folder_dupes = _detect_cross_folder_duplicates(content_notes)

    malformed_wikilinks = _detect_malformed_wikilinks(all_notes)

    empty_indexes = _detect_empty_indexes()

    mermaid_errors = _detect_mermaid_errors()

    meta_issues = _detect_missing_metadata(content_notes)
    missing_tags = meta_issues["missing_tags"]
    missing_agent = meta_issues["missing_agent"]
    missing_type = meta_issues["missing_type"]
    missing_status = meta_issues["missing_status"]
    missing_cia = meta_issues["missing_cia"]
    missing_updated = meta_issues["missing_updated"]
    missing_frontmatter = meta_issues["missing_frontmatter"]

    # DQ + propagation data (loaded regardless of refresh_dq; only refresh triggers subprocess)

    dq_health = _refresh_dq_if_needed() if refresh_dq else None

    propagation_pending = _read_propagation_pending()

    # AP-31/34/35: Knowledge Graph antipatterns
    graph_knowledge = _detect_graph_knowledge_antipatterns()
    ap31_typed_ratio = graph_knowledge["ap31_typed_ratio"]
    ap31_penalty = graph_knowledge["ap31_penalty"]
    ap34_orphan_relations = graph_knowledge["ap34_orphan_relations"]
    ap35_silo_flags = graph_knowledge["ap35_silo_flags"]

    score = 100

    score -= min(30, len(orphans) * 2)

    score -= min(10, len(stale) * 1)

    score -= min(15, len(stuck_patterns) * 3)

    score -= min(25, len(stale_projects) * 5)

    score -= min(20, len(broken_links) * 2)

    score -= min(10, len(canonical_shadow) * 2)

    score -= min(10, len(cross_folder_dupes) * 3)

    # AP-22 (empty [[]]) penaliza menos que AP-24 (imbalance real).
    # Auto-fixables tienen penalización baja; imbalance real penaliza más.
    ap22_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-22")
    ap24_count = sum(1 for m in malformed_wikilinks if m.get("norm_code") == "AP-24")
    score -= min(5, ap22_count * 2)  # AP-22 leve (vacíos sin info)
    score -= min(15, ap24_count * 5)  # AP-24 grave (brackets rotos)

    score -= min(10, len(empty_indexes) * 2)

    # AP-25: Mermaid diagram errors
    score -= min(20, len(mermaid_errors) * 2)

    # AP-16: Missing agent attribution
    score -= min(10, len(missing_agent) * 1)

    # AP-26: Missing tags on content notes
    score -= min(15, len(missing_tags) * 2)

    # AP-27: Missing type field
    score -= min(10, len(missing_type) * 2)

    # AP-29: Missing status field
    score -= min(10, len(missing_status) * 1)

    # AP-30: Missing CIA fields
    score -= min(15, len(missing_cia) * 2)

    # Missing updatedAt
    score -= min(10, len(missing_updated) * 2)

    # AP-28: Missing frontmatter entirely
    score -= min(20, len(missing_frontmatter) * 3)

    # CIA integrity + propagation_pending adjustments

    score -= min(15, _cia_score_penalty(content_notes, stale, propagation_pending))

    # AP-31: Missing typed edges (untuned graph)
    score -= ap31_penalty

    # AP-34: Orphan typed relations (unresolved endpoints)
    ap34_count = sum(r.get("count", 0) for r in ap34_orphan_relations)
    score -= min(10, ap34_count * 2)

    # AP-35: Relationship silos (stale enriched graph)
    if ap35_silo_flags.get("graph_enriched_stale", False):
        score -= 5

    score = max(0, score)

    by_folder: Dict[str, int] = defaultdict(int)

    for n in content_notes:
        parts = n.relative_to(_raiz()).parts

        by_folder[parts[0] if parts else "root"] += 1

    summary_parts = [f"Score: {score}/100", f"{len(content_notes)} notas"]

    if orphans:
        summary_parts.append(f"{len(orphans)} huerfanas")

    if broken_links:
        cnt = len(broken_links)

        summary_parts.append(
            f"{cnt} link{'s' if cnt != 1 else ''} roto{'s' if cnt != 1 else ''}"
        )

    if stuck_patterns:
        summary_parts.append(f"{len(stuck_patterns)} patrones bloqueados")

    if stale_projects:
        summary_parts.append(f"{len(stale_projects)} proyectos sin actualizar")

    if canonical_shadow:
        summary_parts.append(f"{len(canonical_shadow)} pares AP-17")

    if cross_folder_dupes:
        summary_parts.append(f"{len(cross_folder_dupes)} duplicados AP-18")

    if malformed_wikilinks:
        ap22_count = sum(
            1 for m in malformed_wikilinks if m.get("norm_code") == "AP-22"
        )
        ap24_count = sum(
            1 for m in malformed_wikilinks if m.get("norm_code") == "AP-24"
        )
        parts = []
        if ap22_count:
            parts.append(f"{ap22_count} AP-22")
        if ap24_count:
            parts.append(f"{ap24_count} AP-24")
        summary_parts.append(
            f"{len(malformed_wikilinks)} brackets rotos ({', '.join(parts)})"
        )

    if empty_indexes:
        summary_parts.append(f"{len(empty_indexes)} secciones vacias AP-03")

    if mermaid_errors:
        summary_parts.append(f"{len(mermaid_errors)} errores Mermaid AP-25")

    if missing_tags:
        summary_parts.append(f"{len(missing_tags)} sin tags AP-26")

    if missing_agent:
        summary_parts.append(f"{len(missing_agent)} sin agent AP-16")

    if ap35_silo_flags.get("graph_enriched_stale", False):
        summary_parts.append("grafo enriquecido desactualizado AP-35")

    if ap34_orphan_relations:
        ap34_count = sum(r.get("count", 0) for r in ap34_orphan_relations)
        summary_parts.append(f"{ap34_count} relaciones huerfanas AP-34")

    result: Dict[str, Any] = {
        "ok": True,
        "healthScore": score,
        "stats": {
            "total": len(content_notes),
            "byFolder": dict(sorted(by_folder.items())),
        },
        # Notas sobre las que el audit NO se pronunció, por no poder leerlas.
        # Va junto al score y no enterrado en `issues` porque no es un hallazgo
        # del vault: es el alcance de la medida. Un `healthScore` de 95 con
        # `degraded` no vacío es un 95 sobre menos vault del que dice, y quien lo
        # lea tiene derecho a saberlo antes de decidir nada (AP-37).
        "degraded": degradaciones(),
        "issues": {
            "orphans": orphans,
            "stale": stale,
            "stuckPatterns": stuck_patterns,
            "staleProjects": stale_projects,
            "brokenLinks": [{"norm_code": "AP-14", **e} for e in broken_links],
            "canonicalShadow": [{"norm_code": "AP-17", **e} for e in canonical_shadow],
            "crossFolderDuplicates": [
                {"norm_code": "AP-18", **e} for e in cross_folder_dupes
            ],
            "malformedWikilinks": [
                {"norm_code": "AP-22", **e} for e in malformed_wikilinks
            ],
            "emptyIndexes": empty_indexes,
            "mermaidErrors": mermaid_errors,
            "missingTags": missing_tags,
            "missingAgent": missing_agent,
            "missingType": missing_type,
            "missingStatus": missing_status,
            "missingCIA": missing_cia,
            "missingUpdated": missing_updated,
            "missingFrontmatter": missing_frontmatter,
            "graphKnowledge": {
                "ap31_typedRatio": ap31_typed_ratio,
                "ap34_orphanTypedRelations": ap34_orphan_relations,
                "ap35_siloFlags": ap35_silo_flags,
            },
        },
        "norm_refs": {
            "AP-14": "Wiki-links rotos o vacios",
            "AP-16": "Missing agent attribution",
            "AP-17": "Canonical-shadow duplication",
            "AP-18": "Cross-folder content duplication",
            "AP-22": "Bracket sanity — wiki-links vacios",
            "AP-23": "Note complexity ceiling",
            "AP-24": "Bracket imbalance",
            "AP-25": "Mermaid diagram syntax errors",
            "AP-26": "Missing tags",
            "AP-27": "Missing type field",
            "AP-28": "Missing frontmatter block",
            "AP-29": "Missing status field",
            "AP-30": "Missing CIA classification fields",
            "AP-31": "Grafo sin tipos semanticos — sin predicates",
            "AP-34": "Relaciones tipadas huerfanas — endpoint inexistente",
            "AP-35": "Silos de relacion — sistemas de grafos aislados",
        },
        "summary": " · ".join(summary_parts),
    }

    # nextActions: lista prescriptiva y ejecutable de lo que el agente (o el
    # humano) debe hacer para mantener o recuperar 100/100. Cada acción tiene:
    #   - priority: high | medium | low
    #   - category: empty_section | broken_link | malformed_wikilink | orphan |
    #               stale | scaffold_present | guidance
    #   - description: qué pasa y por qué importa
    #   - command: comando CLI sugerido (si aplica) — copy-paste ready
    #   - norm: AP-XX al que aplica
    #
    # Esto convierte el audit de "diagnóstico" a "agente prescriptivo" — el
    # usuario (o un agente LLM leyendo el output) sabe exactamente qué ejecutar.
    next_actions: List[Dict[str, Any]] = []

    # Empty sections: sugerir el comando del tool owner
    for e in empty_indexes:
        folder = e["folder"]
        next_actions.append(
            {
                "priority": "high"
                if folder in ("01_Projects", "00_System")
                else "medium",
                "category": "empty_section",
                "folder": folder,
                "description": f"{folder} no tiene notas — la sección existe pero su contenido está vacío.",
                "command": _suggest_command_for_folder(folder),
                "norm": "AP-03",
            }
        )

    # Broken links: 3 opciones
    for bl in broken_links:
        target = bl.get("link", "")
        src = bl.get("from", "")
        # build a clean slug from the target for the suggested filename
        slug = target.lower().replace(" ", "-")
        next_actions.append(
            {
                "priority": "high",
                "category": "broken_link",
                "from": src,
                "link": target,
                "description": f"Wiki-link [[{target}]] en `{src}` no resuelve a ninguna nota del vault.",
                "remediation_options": [
                    f'Crear la nota destino: `python scripts/vault_write.py --folder "<carpeta>" --title "{target}" --content "..."`',
                    f"Editar `{src}` y corregir el link a una nota que sí exista.",
                    f"Eliminar el link de `{src}` si ya no aplica.",
                ],
                "norm": "AP-14",
            }
        )

    # Malformed wikilinks (AP-22 + AP-24)
    for ml in malformed_wikilinks:
        kinds = ml.get("kinds", [])
        auto_fixable = ml.get("auto_fixable", False)
        norm = ml.get("norm_code", "AP-22")
        path = ml.get("from", ml.get("path", ""))
        if auto_fixable:
            cmd = f"python scripts/vault_fix_brackets.py --apply {path}"
            desc_kind = ", ".join(kinds)
            next_actions.append(
                {
                    "priority": "medium",
                    "category": "malformed_wikilink",
                    "from": path,
                    "kinds": kinds,
                    "description": (
                        f"Brackets auto-arreglables ({desc_kind}) en `{path}`. "
                        "Ejecutar fix sin riesgo."
                    ),
                    "command": cmd,
                    "norm": norm,
                }
            )
        else:
            snippet = ""
            if ml.get("snippets"):
                s = ml["snippets"][0]
                snippet = f" Línea {s['line']}: `{s['text']}`."
            next_actions.append(
                {
                    "priority": "high",
                    "category": "malformed_wikilink",
                    "from": path,
                    "kinds": kinds,
                    "description": (
                        f"Brackets imbalanceados ({', '.join(kinds)}) en `{path}`."
                        f"{snippet} Revisar manualmente — fix automático NO seguro."
                    ),
                    "command": f"Revisar `{path}` y corregir `[[` / `]]` huérfanos.",
                    "norm": norm,
                }
            )

    # Orphans: notas sin backlinks
    for orph in orphans:
        next_actions.append(
            {
                "priority": "low",
                "category": "orphan",
                "path": orph.get("path", ""),
                "description": f"Nota `{orph.get('path', '')}` no tiene wiki-links entrantes — está huérfana.",
                "command": "Añadir un wiki-link desde otra nota del vault, o marcar la nota como reference (no necesita backlinks).",
                "norm": "AP-13",
            }
        )

    # Deleted nodes: detectar nodos eliminados que tenían inbound links
    graph_file = _raiz() / "99_Index" / "graph.json"
    if graph_file.exists():
        try:
            import json as json_module

            graph_data = json_module.loads(graph_file.read_text(encoding="utf-8"))

            for edge in graph_data.get("edges", []):
                if edge.get("to") == "__deleted__":
                    original_path = edge.get("from")
                    next_actions.append(
                        {
                            "priority": "high",
                            "category": "deleted_node",
                            "path": original_path,
                            "description": f"Nodo `{original_path}` fue eliminado pero tenía inbound links — hay enlaces huérfanos.",
                            "remediation_options": [
                                f"Restaurar la nota desde backup.",
                                f"Crear una nota vacía con el mismo nombre.",
                                f"Ejecutar `python scripts/vault_graph.py` para limpiar el grafo.",
                            ],
                            "norm": "AP-15",
                        }
                    )
        except Exception:
            pass

    # Moved nodes: detectar notas reubicadas
    move_log = _system_dir() / "move-log.json"
    if move_log.exists():
        try:
            move_data = json_module.loads(move_log.read_text(encoding="utf-8"))
            for move in move_data[-5:]:
                next_actions.append(
                    {
                        "priority": "low",
                        "category": "moved_node",
                        "from": move.get("from", ""),
                        "to": move.get("to", ""),
                        "description": f"Nota movida de `{move.get('from', '')}` a `{move.get('to', '')}`.",
                        "command": f"Ejecutar `python scripts/vault_graph.py` para actualizar el grafo.",
                        "norm": "AP-16",
                    }
                )
        except Exception:
            pass

    # AP-25: Mermaid diagram errors - suggest running mermaid check with fix
    if mermaid_errors:
        next_actions.append(
            {
                "priority": "high",
                "category": "mermaid_errors",
                "description": f"{len(mermaid_errors)} errores de sintaxis en diagramas Mermaid",
                "command": "python scripts/vault_mermaid_check.py --fix",
                "norm": "AP-25",
            }
        )

    # AP-16: Missing agent attribution - suggest adding agent field
    if missing_agent:
        agent_paths = [m["path"] for m in missing_agent[:5]]
        next_actions.append(
            {
                "priority": "medium",
                "category": "missing_agent",
                "description": f"{len(missing_agent)} notas sin campo 'agent' en frontmatter. Primeras: {agent_paths}",
                "command": "Agregar agent: deepseek (o el agente correspondiente) al frontmatter de cada nota faltante",
                "norm": "AP-16",
            }
        )

    # AP-26: Missing tags - suggest adding tags
    if missing_tags:
        tag_paths = [m["path"] for m in missing_tags[:5]]
        next_actions.append(
            {
                "priority": "high",
                "category": "missing_tags",
                "description": f"{len(missing_tags)} notas de contenido sin tags. Primeras: {tag_paths}",
                "command": "python scripts/vault_write.py --folder <folder> --title <title> --content @file:<path> --tags ans <category>",
                "norm": "AP-26",
            }
        )

    # AP-35: Relationship silos — suggest running vault_graph --typed
    if ap35_silo_flags.get("graph_enriched_stale", False):
        next_actions.append(
            {
                "priority": "high",
                "category": "graph_silos",
                "description": (
                    f"El grafo enriquecido esta ausente o desactualizado ({ap35_silo_flags.get('graph_enriched_hours_old', '?')}h). "
                    "Las relaciones semanticas de entity y code no estan integradas en el grafo de conocimiento (AP-35)."
                ),
                "command": "python scripts/vault_graph.py --typed",
                "norm": "AP-35",
            }
        )

    # AP-34: Orphan typed relations — unresolved endpoints
    if ap34_orphan_relations:
        for rel in ap34_orphan_relations:
            next_actions.append(
                {
                    "priority": "medium",
                    "category": "orphan_typed_relations",
                    "description": f"{rel['count']} {rel['source']} relations tienen endpoints no resueltos (AP-34).",
                    "command": "Verificar que las entidades/modulos referenciados existen como notas en el vault. Ejecutar vault_search para confirmar.",
                    "norm": "AP-34",
                }
            )

    # AP-31: Untyped graph — suggest running enrich
    if ap31_typed_ratio < 0.1 and ap31_penalty > 0:
        next_actions.append(
            {
                "priority": "medium",
                "category": "untyped_graph",
                "description": (
                    f"Solo {ap31_typed_ratio * 100:.1f}% de las aristas tienen predicate. "
                    "Ejecutar vault_graph --typed para enriquecer el grafo con relaciones semanticas (AP-31)."
                ),
                "command": "python scripts/vault_graph.py --typed",
                "norm": "AP-31",
            }
        )

    # Guidance cuando score == 100: qué documentar primero (siguiente paso)
    if score >= 100:
        # Detectar secciones que aún tienen solo el primer scaffold
        # para sugerir reemplazo por contenido real
        scaffold_reminders = _detect_scaffold_only_sections(content_notes)
        for sec in scaffold_reminders:
            next_actions.append(
                {
                    "priority": "high",
                    "category": "scaffold_present",
                    "folder": sec,
                    "description": f"{sec} solo tiene el primer scaffold — listo para reemplazar con contenido real.",
                    "command": _suggest_command_for_folder(sec),
                    "norm": "CN-01",
                }
            )
        if not next_actions:
            # Vault is at 100/100 and fully populated — provide a roadmap
            next_actions.extend(_get_roadmap_for_populated_vault(content_notes))

    if next_actions:
        result["nextActions"] = next_actions
        result["nextActionsCount"] = len(next_actions)

    if dq_health is not None:
        result["dqHealth"] = dq_health

    if propagation_pending:
        result["propagationPending"] = propagation_pending

    tag_health = _read_tag_health()

    if tag_health is not None:
        result["tagHealth"] = tag_health

    return result


def _audit_external_path(path: Path) -> Dict[str, Any]:
    """Audit .md files in an external directory path (not the vault)."""

    md_files = list(path.rglob("*.md"))

    total = len(md_files)

    no_frontmatter = []

    empty_files = []

    no_title = []

    for md_file in md_files:
        content = _leer_nota(md_file)
        if content is None:
            continue

        if len(content) < 100:
            empty_files.append(str(md_file))

        if not content.startswith("---"):
            no_frontmatter.append(str(md_file))

            no_title.append(str(md_file))

            continue

        parts = content.split("---", 2)

        if len(parts) < 3:
            no_frontmatter.append(str(md_file))

            no_title.append(str(md_file))

            continue

        has_title = False

        for line in parts[1].splitlines():
            if line.lower().startswith("title:") and line.split(":", 1)[1].strip():
                has_title = True

                break

        # also check for a # heading

        if not has_title:
            import re as _re

            if _re.search(r"^#\s+.+", parts[2], _re.MULTILINE):
                has_title = True

        if not has_title:
            no_title.append(str(md_file))

    return {
        "ok": True,
        "mode": "external_path",
        "path": str(path),
        "total": total,
        "noFrontmatter": no_frontmatter,
        "emptyFiles": empty_files,
        "noTitle": no_title,
        "summary": f"{total} files · {len(no_frontmatter)} without frontmatter · {len(empty_files)} empty · {len(no_title)} without title",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Audit -- blueprint: vault-obsidian-architecture.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_audit.py

  python vault_audit.py --project "mi-proyecto"

  python vault_audit.py --path "C:/repos/mi-api/docs"

  python vault_audit.py --project "ans" --path "src/docs"



Notas:

  - Sin --path audita el vault interno

  - Con --path audita una ruta externa al vault (reporta frontmatter, vacios, sin titulo)

""",
    )

    parser.add_argument("--project", help="Optional project slug to filter audit scope")

    parser.add_argument(
        "--path", help="External directory path to audit instead of vault"
    )

    parser.add_argument(
        "--refresh-dq",
        action="store_true",
        help="Refresh quality-index.json if stale and include dqHealth in output",
    )

    args = parser.parse_args()

    if args.path:
        ext_path = Path(args.path)

        if not ext_path.exists():
            print(json.dumps({"ok": False, "error": f"Path not found: {args.path}"}))

            return 1

        result = _audit_external_path(ext_path)

    else:
        result = vault_audit(args.project, refresh_dq=args.refresh_dq)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_audit"))
