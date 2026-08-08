#!/usr/bin/env python3
"""
Vault Tags — Registro canonico de tags, auditoria y control de consistencia.

Construye y mantiene 00_System/tag-registry.json escaneando todos los frontmatter.
Detecta tags huerfanos, notas sin tags, y tags near-duplicados para evitar
proliferacion incontrolada. Genera 99_Index/tag-index.md con backlinks por tag.

El tag-registry es la lista controlada: antes de crear un tag nuevo, el agente
consulta vault_tags --suggest para ver si ya existe uno canonico equivalente.

Usage:
    python vault_tags.py                        # rebuildar registry + tag-index.md
    python vault_tags.py --audit                # reporte de salud de tags
    python vault_tags.py --suggest PATH         # sugerir tags existentes para una nota
    python vault_tags.py --rename OLD NEW       # renombrar tag en todas las notas
    python vault_tags.py --ledger               # bitacora de vocabulario (AP-39)
    python vault_tags.py --backfill-ledger      # anotar el vocabulario ya en uso (heal AP-39)
    python vault_tags.py --dry-run              # rebuildar sin escribir archivos
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from vault_errors import emit_error, wrap_main
from vault_lib import utcnow, parse_frontmatter_with_body
from vault_io import (
    atomic_write_json,
    atomic_write_text,
    assert_within_vault,
    file_lock,
    safe_wikilink,
)

from vault_registry import SECTIONS as _REGISTRY_SECTIONS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La configuración se lee del registro único, no con un default por punto
# de uso. Ver `vault_entorno.py`.
from vault_entorno import leer as _env

from vault.indices.enumeracion import NOMBRES_DE_INDICE  # noqa: E402
from vault.indices.enumeracion import es_nota_indexable  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402

#: Derivado de `vault_registry.SECTIONS`, no copiado: la lista literal que vivía
#: aquí se quedó en 18 carpetas y dejaba de escanear cada sección nueva del
#: estándar sin que nada fallara — AP-05 dentro del propio toolkit.
VAULT_SECTIONS = {s["folder"] for s in _REGISTRY_SECTIONS}

#: Se conserva el nombre publicado (no-derogación); el valor sale del dominio.
SKIP_NAMES = NOMBRES_DE_INDICE


# ── Rutas: funciones, no constantes ──────────────────────────────────────────
#
# Eran cinco constantes derivadas de `VAULT_ROOT` al importar el módulo, que es
# AP-49 en su forma literal: `set_vault_root()` no podía reapuntarlas porque ya
# estaban calculadas. Resueltas al usarse, dos vaults conviven en el mismo
# intérprete. Las rutas las da el repositorio del contexto Índices, que es
# también quien garantiza la contención (AP-36).


def _repo(root=None) -> RepositorioIndices:
    return RepositorioIndices(construir(root))


def _raiz() -> Path:
    return _repo().raiz


def _tag_registry() -> Path:
    return _repo().registro_etiquetas


def _tag_index_md() -> Path:
    return _repo().indice_etiquetas


def _vocab_dir() -> Path:
    """Bitácora de vocabulario (AP-39). Append-only y dentro del vault (AP-36)."""
    return _repo().dir_vocabulario


def _tag_ledger() -> Path:
    return _repo().bitacora_etiquetas


def _search_index() -> Path:
    return _repo().indice_busqueda


def _is_vault_note(path: Path) -> bool:
    """Criterio del contexto, sin los índices: `index.md` es navegación generada.

    Se conserva el nombre porque el módulo lo usa en tres sitios; el criterio ya
    no vive aquí sino en `vault/indices/enumeracion.py`, compartido con la
    reconstrucción del índice de búsqueda (AP-44).
    """
    return es_nota_indexable(path, _raiz(), VAULT_SECTIONS, incluir_indices=False)


def _parse_frontmatter_tags(content: str) -> List[str]:
    """Tags del frontmatter, con el mismo parser que usa el resto del toolkit.

    La versión anterior leía la línea `tags:` a mano y solo entendía la forma
    inline (`tags: [a, b]`): las listas YAML en bloque (`tags:\\n  - a`) le
    salían vacías. Como `vault_norms --audit` sí las ve, el audit reportaba
    términos que el registro y el heal no podían tocar — dos lectores del mismo
    campo discrepando, AP-05 otra vez.
    """
    fm, _ = parse_frontmatter_with_body(content)
    crudos = (fm or {}).get("tags") or []
    if isinstance(crudos, str):
        crudos = [t.strip() for t in crudos.split(",")]
    if not isinstance(crudos, list):
        return []
    return [str(t).strip() for t in crudos if str(t).strip()]


def _parse_frontmatter_title(content: str) -> str:
    if not content.startswith("---"):
        return ""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


# ───────────────────────────── AP-39 — vocabulario con memoria ──────────────
#
# Medido sobre 17 vaults reales: 1.180 tags distintos, 6.358 usos, **45% usados
# una sola vez** y 55 familias de casi-duplicados (`ci-cd`/`cicd`/`ci_cd`,
# `pattern`/`patterns`, `migracion`/`migración`). El ritmo de invención es plano
# a lo largo de tres meses (37% → 36% → 34% → 27% → 36%): nadie está aprendiendo
# el vocabulario de la sesión anterior porque nada lo recuerda por él.
#
# La causa no es el agente, es el camino de escritura: `vault_write` leía la
# clave `tags` de un registro que guarda `canonical_tags`, así que la sugerencia
# nunca se disparaba. Un tag inventado costaba exactamente lo mismo que uno
# reutilizado — cero.
#
# La regla de AP-39: **un tag nuevo se admite, pero se registra.** No se rechaza
# (rechazar empuja al agente a omitir tags y AP-26 acaba siendo lo que se
# incumple), y no se traduce a la fuerza (adivinar destruye el término que quizá
# era el correcto). Solo colapsa lo que es demostrablemente la misma palabra:
# acentos, mayúsculas, separadores y plural.

_TAG_SEPARADORES = re.compile(r"[\s_.:/\\]+")
_TAG_INVALIDOS = re.compile(r"[^a-z0-9-]+")


def normalize_tag(raw: str) -> str:
    """Forma normalizada de un tag: minúsculas, sin acentos, separado por `-`.

    Es la misma clase de normalización que `vault_norms.normalize_status`:
    colapsa variantes tipográficas del **mismo** término y nada más.
    """
    texto = unicodedata.normalize("NFD", str(raw or "").strip().lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = _TAG_SEPARADORES.sub("-", texto)
    texto = _TAG_INVALIDOS.sub("-", texto)
    texto = re.sub(r"-{2,}", "-", texto).strip("-")
    return texto


def singular_tag(tag: str) -> str:
    """Plural inglés/castellano → singular, solo en los casos inequívocos."""
    if len(tag) > 4 and tag.endswith("es") and not tag.endswith(("ses", "ees")):
        return tag[:-2]
    if len(tag) > 3 and tag.endswith("s") and not tag.endswith(("ss", "us", "is")):
        return tag[:-1]
    return tag


def canonical_tags() -> List[str]:
    """Tags canónicos del vault, aplanados desde las facetas del registro."""
    try:
        registro = json.loads(_tag_registry().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    canonicos = registro.get("canonical_tags")
    if isinstance(canonicos, dict):
        planos: List[str] = []
        for valores in canonicos.values():
            if isinstance(valores, list):
                planos.extend(str(v) for v in valores)
        return planos
    # Formato legacy `{"tags": {"<tag>": {...}}}` — se sigue leyendo.
    legacy = registro.get("tags")
    return sorted(legacy) if isinstance(legacy, dict) else []


def _canonical_index() -> Dict[str, str]:
    """{forma normalizada → tag canónico}, incluyendo la forma en singular."""
    indice: Dict[str, str] = {}
    for tag in canonical_tags():
        norma = normalize_tag(tag)
        if not norma:
            continue
        indice.setdefault(norma, tag)
        indice.setdefault(singular_tag(norma), tag)
    return indice


def resolve_tag(raw: str, indice: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """(tag resuelto, regla). regla ∈ canonical | normalized | singular | new."""
    indice = _canonical_index() if indice is None else indice
    norma = normalize_tag(raw)
    if not norma:
        return "", "empty"
    canonico = indice.get(norma)
    if canonico is not None:
        return canonico, ("canonical" if canonico == str(raw) else "normalized")
    canonico = indice.get(singular_tag(norma))
    if canonico is not None:
        return canonico, "singular"
    # Término nuevo: se admite tal cual (normalizado), y quien llama lo anota.
    return norma, "new"


def _load_ledger() -> Dict[str, Any]:
    try:
        return json.loads(_tag_ledger().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": "v1.0", "entries": []}


def record_new_tags(
    terminos: List[Dict[str, Any]], agent: str = "", note: str = ""
) -> int:
    """Anota términos introducidos en la bitácora append-only. Devuelve cuántos.

    Append-only a propósito: la bitácora responde *quién introdujo esta palabra,
    cuándo y en qué nota*. Reescribirla la convierte en un índice más, y de
    índices que se regeneran ya hay uno (`tag-index.md`).
    """
    if not terminos:
        return 0
    _vocab_dir().mkdir(parents=True, exist_ok=True)
    ahora = utcnow()
    with file_lock(_tag_ledger()):
        ledger = _load_ledger()
        ya = {e["tag"] for e in ledger["entries"]}
        nuevos = 0
        for t in terminos:
            if t["tag"] in ya:
                continue
            ledger["entries"].append({
                "tag": t["tag"],
                "raw": t.get("raw", t["tag"]),
                "first_note": t.get("note", note),
                "introduced_by": t.get("agent", agent) or "unknown",
                "introduced_at": ahora,
                "rule": t.get("rule", "new"),
            })
            ya.add(t["tag"])
            nuevos += 1
        if nuevos:
            atomic_write_json(_tag_ledger(), ledger)
    return nuevos


def apply_vocabulary(
    tags: List[str], note: str = "", agent: str = ""
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Punto de entrada de `vault_write`: (tags resueltos, términos nuevos).

    No escribe nada — anotar es responsabilidad de quien confirma la escritura,
    porque un tag registrado sobre una nota que al final no se escribió es
    memoria falsa.
    """
    indice = _canonical_index()
    resueltos: List[str] = []
    introducidos: List[Dict[str, Any]] = []
    for crudo in tags or []:
        resuelto, regla = resolve_tag(crudo, indice)
        if not resuelto:
            continue
        if resuelto not in resueltos:
            resueltos.append(resuelto)
        if regla == "new":
            introducidos.append({
                "tag": resuelto,
                "raw": str(crudo),
                "note": note,
                "agent": agent,
                "rule": "new",
            })
    return resueltos, introducidos


def registrar_tags_de_nota(
    tags: List[str], nota: str, agente: str = ""
) -> Dict[str, Any]:
    """Canoniza los tags de una nota recién escrita y anota los nuevos.

    Esto lo hacía **solo** `vault_write`, y hay quince escritores: los catorce
    `*_save` que llevan tags construyen su frontmatter y llaman directamente a
    `atomic_write_text`, saltándose el write path entero. El resultado es que
    AP-39 se cumplía en una de cada quince escrituras: el término entraba en el
    vault y la bitácora no se enteraba, así que la auditoría lo denunciaba
    después como vocabulario introducido sin dejar rastro — culpando a la nota
    de algo que era del escritor. Es AP-43 en su forma literal: norma sin
    refuerzo en el punto de uso.

    Se llama **después** de escribir, nunca antes: anotar primero dejaría en la
    bitácora palabras de escrituras que fallaron.

    Un fallo de la bitácora no tumba una escritura válida — devuelve
    `recorded: -1` y el audit de AP-39 lo recoge luego.
    """
    canonicos, nuevos = apply_vocabulary(list(tags or []))
    if not nuevos:
        return {"tags": canonicos, "vocabulary_introduced": [], "recorded": 0}

    agente = agente or _env("VAULT_AGENT")
    for t in nuevos:
        t["note"] = nota
        t["agent"] = agente
    try:
        anotados = record_new_tags(nuevos)
    except OSError:
        anotados = -1
    return {
        "tags": canonicos,
        "vocabulary_introduced": [t["tag"] for t in nuevos],
        "recorded": anotados,
    }


def vault_tags_backfill_ledger(dry_run: bool = False) -> Dict[str, Any]:
    """Heal de AP-39: anota en la bitácora el vocabulario ya en uso.

    Un vault que existía antes de AP-39 tiene términos introducidos por sesiones
    que nadie registró. Retro-anotarlos no inventa historia: usa el `agent` y el
    `created` de la nota donde el término aparece por primera vez, y marca la
    regla como `backfill` para que no se confunda con lo registrado en vivo.
    """
    indice = _canonical_index()
    vistos: Dict[str, Dict[str, Any]] = {}
    for md in sorted(_raiz().rglob("*.md")):
        if not _is_vault_note(md):
            continue
        try:
            contenido = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(md.relative_to(_raiz())).replace("\\", "/")
        agente = ""
        for linea in contenido.split("---", 2)[1].splitlines() if contenido.startswith("---") else []:
            if linea.startswith("agent:"):
                agente = linea.split(":", 1)[1].strip().strip("\"'")
                break
        for crudo in _parse_frontmatter_tags(contenido):
            resuelto, regla = resolve_tag(crudo, indice)
            if regla != "new" or not resuelto or resuelto in vistos:
                continue
            vistos[resuelto] = {
                "tag": resuelto,
                "raw": crudo,
                "note": rel,
                "agent": agente,
                "rule": "backfill",
            }

    if dry_run:
        ya = {e["tag"] for e in _load_ledger()["entries"]}
        pendientes = [t for t in sorted(vistos) if t not in ya]
        return {
            "ok": True,
            "dry_run": True,
            "would_record": len(pendientes),
            "tags": pendientes,
        }

    anotados = record_new_tags(list(vistos.values()))
    return {
        "ok": True,
        "created": anotados,
        "updated": 0,
        "written": anotados,
        "recorded": anotados,
        "scanned_terms": len(vistos),
        "path": str(_tag_ledger().relative_to(_raiz())).replace("\\", "/"),
    }


def vault_tags_ledger() -> Dict[str, Any]:
    """Lee la bitácora de vocabulario (AP-39)."""
    ledger = _load_ledger()
    entradas = ledger.get("entries", [])
    por_agente: Dict[str, int] = {}
    for e in entradas:
        por_agente[e.get("introduced_by", "unknown")] = (
            por_agente.get(e.get("introduced_by", "unknown"), 0) + 1
        )
    return {
        "ok": True,
        "path": str(_tag_ledger().relative_to(_raiz())).replace("\\", "/"),
        "introduced_total": len(entradas),
        "canonical_total": len(set(canonical_tags())),
        "by_agent": dict(sorted(por_agente.items(), key=lambda kv: -kv[1])),
        "entries": entradas,
    }


def _similarity_score(a: str, b: str) -> float:
    """Simple similarity: exact prefix/suffix overlap + shared chars ratio."""
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.85
    # common prefix length
    common = sum(1 for x, y in zip(a, b) if x == y)
    prefix = 0
    for x, y in zip(a, b):
        if x == y:
            prefix += 1
        else:
            break
    if prefix >= 3:
        return 0.6 + (prefix / max(len(a), len(b))) * 0.2
    return common / max(len(a), len(b))


def _find_similar_tags(
    new_tag: str, existing_tags: Set[str], threshold: float = 0.6
) -> List[Dict[str, Any]]:
    """Return existing tags similar to new_tag, sorted by similarity desc."""
    results = []
    for tag in existing_tags:
        score = _similarity_score(new_tag, tag)
        if score >= threshold and tag != new_tag:
            results.append({"tag": tag, "score": round(score, 2)})
    return sorted(results, key=lambda x: -x["score"])[:5]


def _scan_all_notes() -> Tuple[Dict[str, List[str]], List[str]]:
    """Scan vault notes → {tag: [paths]}, [untagged_paths]."""
    tag_map: Dict[str, List[str]] = defaultdict(list)
    untagged: List[str] = []

    for note_path in sorted(_raiz().rglob("*.md")):
        if not _is_vault_note(note_path):
            continue
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            continue
        rel = str(note_path.relative_to(_raiz())).replace("\\", "/")
        tags = _parse_frontmatter_tags(content)
        if tags:
            for tag in tags:
                tag_map[tag].append(rel)
        else:
            untagged.append(rel)

    return dict(tag_map), untagged


def _generate_tag_index_md(tag_map: Dict[str, List[str]], untagged: List[str]) -> str:
    now = utcnow()
    lines = [
        "---",
        "title: Tag Index",
        f"updatedAt: {now}",
        "type: index",
        "cia_integrity: low",
        "cia_availability: low",
        "cia_sensitivity: internal",
        "agent: system",
        "---",
        "",
        "# Tag Index",
        "",
        f"_{len(tag_map)} tags · {sum(len(v) for v in tag_map.values())} referencias · {len(untagged)} notas sin tag_",
        "",
    ]

    for tag in sorted(tag_map.keys(), key=str.lower):
        notes = sorted(tag_map[tag])
        lines.append(f"## `{tag}` ({len(notes)})")
        lines.append("")
        for note_path in notes:
            stem = Path(note_path).stem
            lines.append(f"- [[{safe_wikilink(stem)}]]")
        lines.append("")

    if untagged:
        lines.append("## Sin tags")
        lines.append("")
        for note_path in sorted(untagged):
            stem = Path(note_path).stem
            lines.append(f"- [[{safe_wikilink(stem)}]] — `{note_path}`")
        lines.append("")

    return "\n".join(lines)


def vault_tags_rebuild(dry_run: bool = False) -> Dict[str, Any]:
    tag_map, untagged = _scan_all_notes()

    registry = {
        "updatedAt": utcnow(),
        "total_tags": len(tag_map),
        "total_tagged_notes": sum(len(v) for v in tag_map.values()),
        "total_untagged_notes": len(untagged),
        "tags": {
            tag: {"notes": sorted(paths), "count": len(paths)}
            for tag, paths in sorted(tag_map.items())
        },
        "untagged_notes": sorted(untagged),
    }

    tag_index_content = _generate_tag_index_md(tag_map, untagged)

    if not dry_run:
        _raiz().joinpath("00_System").mkdir(parents=True, exist_ok=True)
        _raiz().joinpath("99_Index").mkdir(parents=True, exist_ok=True)
        # Lock the paired writes so concurrent rebuilds cannot interleave and leave
        # the registry (JSON) and the human index (MD) describing different states.
        with file_lock(_tag_registry()):
            atomic_write_json(_tag_registry(), registry)
            atomic_write_text(_tag_index_md(), tag_index_content)

    return {
        "ok": True,
        "total_tags": len(tag_map),
        "total_tagged_notes": sum(len(v) for v in tag_map.values()),
        "total_untagged_notes": len(untagged),
        "tag_registry": str(_tag_registry().relative_to(_raiz())).replace("\\", "/"),
        "tag_index": str(_tag_index_md().relative_to(_raiz())).replace("\\", "/"),
        "dry_run": dry_run,
    }


def vault_tags_audit() -> Dict[str, Any]:
    if not _tag_registry().exists():
        return emit_error(
            "vault_tags", "INDEX_NOT_FOUND",
            "No existe `tag-registry.json`; genéralo ejecutando `vault_tags.py` primero.",
        )

    try:
        registry = json.loads(_tag_registry().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return emit_error("vault_tags", "FILE_READ_ERROR",
                          f"No se pudo leer el registro de tags: {e}", exception=e)

    tags = registry.get("tags", {})
    untagged = registry.get("untagged_notes", [])

    # Orphaned: tags that exist in registry but no current notes use them
    orphaned = [t for t, info in tags.items() if info.get("count", 0) == 0]

    # Near-duplicates: pairs of tags with high similarity
    tag_names = list(tags.keys())
    near_dupes: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for i, tag_a in enumerate(tag_names):
        for tag_b in tag_names[i + 1 :]:
            pair = tuple(sorted([tag_a, tag_b]))
            if pair in seen_pairs:
                continue
            score = _similarity_score(tag_a, tag_b)
            if score >= 0.6:
                seen_pairs.add(pair)
                near_dupes.append(
                    {
                        "tag_a": tag_a,
                        "tag_b": tag_b,
                        "score": round(score, 2),
                        "counts": {
                            "a": tags[tag_a]["count"],
                            "b": tags[tag_b]["count"],
                        },
                    }
                )
    near_dupes.sort(key=lambda x: -x["score"])

    # Singleton tags (count == 1, not linked elsewhere)
    singletons = [t for t, info in tags.items() if info.get("count", 1) == 1]

    health_score = 100
    health_score -= len(orphaned) * 5
    health_score -= len(near_dupes) * 3
    health_score -= min(len(untagged) * 2, 30)
    health_score = max(0, health_score)

    return {
        "ok": True,
        "health_score": health_score,
        "total_tags": registry.get("total_tags", 0),
        "total_tagged_notes": registry.get("total_tagged_notes", 0),
        "total_untagged_notes": len(untagged),
        "orphaned_tags": orphaned,
        "near_duplicate_pairs": near_dupes[:10],
        "singleton_tags": singletons[:20],
        "untagged_notes": untagged[:20],
        "summary": (
            f"Score {health_score}/100 · {len(tags)} tags · "
            f"{len(orphaned)} huerfanos · {len(near_dupes)} near-dupes · "
            f"{len(untagged)} notas sin tag"
        ),
        "registry_at": registry.get("updatedAt", "?"),
    }


def vault_tags_suggest(note_path_str: str) -> Dict[str, Any]:
    note_path = _raiz() / Path(note_path_str)
    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except (FileNotFoundError, PermissionError) as e:
        return emit_error("vault_tags", "FILE_READ_ERROR",
                          f"No se pudo leer el registro de tags: {e}", exception=e)

    existing_tags = set(_parse_frontmatter_tags(content))
    title = _parse_frontmatter_title(content)

    if not _tag_registry().exists():
        return emit_error(
            "vault_tags", "INDEX_NOT_FOUND",
            "No existe `tag-registry.json`; genéralo ejecutando `vault_tags.py` primero.",
        )

    try:
        registry = json.loads(_tag_registry().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return emit_error("vault_tags", "FILE_READ_ERROR",
                          f"No se pudo leer el registro de tags: {e}", exception=e)

    canonical_tags: Set[str] = set(registry.get("tags", {}).keys())

    words = re.findall(r"[a-zA-ZÀ-ɏ]{3,}", title + " " + " ".join(existing_tags))
    words = [w.lower() for w in words]

    candidates: Dict[str, float] = {}
    for word in words:
        for similar in _find_similar_tags(word, canonical_tags, threshold=0.5):
            tag = similar["tag"]
            score = similar["score"]
            if tag not in existing_tags:
                candidates[tag] = max(candidates.get(tag, 0), score)

    suggestions = [
        {
            "tag": tag,
            "score": round(score, 2),
            "count": registry["tags"].get(tag, {}).get("count", 0),
        }
        for tag, score in sorted(candidates.items(), key=lambda x: -x[1])
        if tag not in existing_tags
    ][:10]

    return {
        "ok": True,
        "path": note_path_str,
        "current_tags": sorted(existing_tags),
        "suggestions": suggestions,
        "canonical_tag_count": len(canonical_tags),
    }


def _update_search_index_tags(
    old_tag: str, new_tag: str, updated_paths: List[str]
) -> None:
    """Patch search-index.json so renamed tags are reflected without a full reindex."""
    if not _search_index().exists():
        return
    try:
        index = json.loads(_search_index().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    path_set = set(updated_paths)
    changed = False
    for note in index.get("notes", []):
        if note.get("path") in path_set and old_tag in note.get("tags", []):
            note["tags"] = [new_tag if t == old_tag else t for t in note["tags"]]
            changed = True
    if changed:
        atomic_write_json(_search_index(), index)


def vault_tags_rename(
    old_tag: str, new_tag: str, dry_run: bool = False
) -> Dict[str, Any]:
    if not old_tag or not new_tag:
        return emit_error("vault_tags", "MISSING_REQUIRED_ARG",
                          "`old_tag` y `new_tag` son obligatorios para renombrar")

    updated_notes: List[str] = []
    skipped: List[str] = []

    for note_path in _raiz().rglob("*.md"):
        if not _is_vault_note(note_path):
            continue
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            skipped.append(str(note_path))
            continue

        tags = _parse_frontmatter_tags(content)
        if old_tag not in tags:
            continue

        new_tags = [new_tag if t == old_tag else t for t in tags]
        new_tags_json = json.dumps(new_tags)
        # Replace tags line in frontmatter
        new_content = re.sub(
            r"^(tags:\s*).*$",
            f"tags: {new_tags_json}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if new_content != content:
            rel = str(note_path.relative_to(_raiz())).replace("\\", "/")
            if not dry_run:
                atomic_write_text(note_path, new_content)
            updated_notes.append(rel)

    if not dry_run and updated_notes:
        vault_tags_rebuild(dry_run=False)
        _update_search_index_tags(old_tag, new_tag, updated_notes)

    return {
        "ok": True,
        "old_tag": old_tag,
        "new_tag": new_tag,
        "updated_count": len(updated_notes),
        "updated_notes": updated_notes,
        "skipped": skipped,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Tags — registro canonico de tags y auditoria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_tags.py                     # rebuildar registry + tag-index.md
  python vault_tags.py --audit             # reporte de salud de tags
  python vault_tags.py --suggest "01_Projects/mi-api/overview.md"
  python vault_tags.py --rename "api-rest" "rest-api"
  python vault_tags.py --ledger            # quien introdujo cada termino (AP-39)
  python vault_tags.py --dry-run           # simular sin escribir

Notas:
  - Tag registry: 00_System/tag-registry.json
  - Tag index: 99_Index/tag-index.md (con [[wiki-links]] por tag)
  - vault_write resuelve los tags contra el registry antes de escribir (AP-39)
  - Bitacora append-only: 19_Audits/vocabulary/tag-ledger.json
  - vault_audit incluye tag_health en su output cuando el registry existe
""",
    )
    parser.add_argument("--audit", action="store_true", help="Reporte de salud de tags")
    parser.add_argument(
        "--suggest", metavar="PATH", help="Sugerir tags canonicos para una nota"
    )
    parser.add_argument(
        "--rename",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Renombrar tag en todas las notas",
    )
    parser.add_argument(
        "--backfill-ledger",
        action="store_true",
        help="Heal AP-39: anotar en la bitacora el vocabulario ya en uso",
    )
    parser.add_argument(
        "--ledger",
        action="store_true",
        help="Bitacora de vocabulario: que termino se introdujo, quien y cuando (AP-39)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simular sin escribir archivos"
    )

    args = parser.parse_args()

    if args.backfill_ledger:
        result = vault_tags_backfill_ledger(dry_run=args.dry_run)
    elif args.ledger:
        result = vault_tags_ledger()
    elif args.audit:
        result = vault_tags_audit()
    elif args.suggest:
        result = vault_tags_suggest(args.suggest)
    elif args.rename:
        result = vault_tags_rename(args.rename[0], args.rename[1], dry_run=args.dry_run)
    else:
        result = vault_tags_rebuild(dry_run=args.dry_run)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_tags"))
