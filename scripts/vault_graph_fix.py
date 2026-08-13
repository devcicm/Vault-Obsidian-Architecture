#!/usr/bin/env python3
"""vault_graph_fix — Auto-fix broken wiki-links using stem matching.

Strategies (in order):
  1. Exact stem match → link becomes [[<canonical-note>]]
  2. Lowercase fold match (case-insensitive stem)
  3. Fuzzy match with token Jaccard ≥ 0.7 (asks for confirmation if --interactive)
  4. Apply bracket fixes (nested brackets, whitespace) using vault_regex
  5. Apply path-anchored fix: [[carpeta/nota]] → [[nota]]

Safety:
  - Dry-run by default (--apply to actually write changes)
  - Atomic write via vault_io.atomic_write_text
  - Per-note backup via .history/ (via vault_io)
  - Backs up changes to 00_System/.graph-fixes/yyyy-mm-dd.json

Usage:
    # Dry-run (default)
    python scripts/vault_graph_fix.py --root /path/to/vault

    # Apply changes
    python scripts/vault_graph_fix.py --apply

    # Only fix brackets, not broken links
    python scripts/vault_graph_fix.py --apply --only brackets

    # Adjust fuzzy threshold
    python scripts/vault_graph_fix.py --apply --threshold 0.8
"""

from __future__ import annotations

import argparse
import difflib
import json
import hashlib
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from vault_io import (
    atomic_write_text,
    file_lock,
    get_vault_root,
    is_snapshot_path,  # dueño único de qué es una instantánea (AP-57)
    normalize_stem,
)
from vault_registry import ORDERED_SECTIONS
from vault_regex import (
    RE_WIKILINK,
    RE_WIKILINK_CON_ALIAS,
    fix_nested_brackets,
    fix_whitespace_in_links,
    extract_wiki_links_strict,
)
# Los dueños canónicos del criterio que decide si un enlace resuelve (AP-57).
from vault_lib import (
    indice_de_destinos,
    parse_frontmatter,
    resolver_destino_wikilink,
)
from vault_graph_inspect import (
    _SKIP_DIRS,
    _is_migrated,
    _load_notes,
    _stems_set,
    _detect_wikilink_syntax_errors,
    generate_report,
    _extract_title,
    _extract_tags,
    _normalize_for_hash,
    _strip_frontmatter as _vgi_strip_frontmatter,
)
from vault_errors import emit_error, wrap_main

#: Bloques de código: valla triple y `inline`. El criterio de qué es código y
#: no un enlace lo posee `vault_lib.strip_code_blocks` (AP-57), pero allí
#: **borra** el bloque, y aquí hace falta lo contrario: conservarlo intacto y
#: reescribir solo alrededor. Se comparte el patrón, no la operación.
_RE_CODIGO = re.compile(r"```[\s\S]*?```|`[^`\n]+`")


def _fuera_de_codigo(texto: str, fn) -> str:
    """Aplica `fn` solo a los tramos que no son código.

    Obsidian no resuelve un wikilink dentro de un fence: lo enseña tal cual.
    Una tool que **mide** y no lo excluye infla un número; esta tool
    **escribe**, así que reescribía el ejemplo de la nota que documenta la
    sintaxis — el dato se corrompe en vez de solo contarse mal.
    """
    trozos: list[str] = []
    fin = 0
    for m in _RE_CODIGO.finditer(texto):
        trozos.append(fn(texto[fin:m.start()]))
        trozos.append(m.group(0))
        fin = m.end()
    trozos.append(fn(texto[fin:]))
    return "".join(trozos)


_MIGRATION_DIR = "10_Migrated"

_FIX_LOG_DIR = "00_System/.graph-fixes"

_WIKILINK_RE = RE_WIKILINK_CON_ALIAS


def _split_clean_note(text: str) -> tuple[str, str | None]:
    """Split [[note]] or [[note|alias]] → (note, alias)."""
    match = _WIKILINK_RE.search(text)
    if not match:
        return text, None
    return match.group(1).strip(), match.group(2).strip() if match.group(2) else None


def _find_target(
    missing_stem: str,
    all_stems: dict[str, list[str]],
    threshold: float = 0.7,
) -> tuple[str, str] | None:
    """Find best match for missing stem. Returns (canonical_path, strategy) or None.

    Strategies tried: exact → lowercase fold → fuzzy Jaccard.
    """
    if missing_stem in all_stems:
        paths = all_stems[missing_stem]
        if len(paths) == 1:
            return paths[0], "exact"
        canonical = min(paths, key=lambda p: (len(p), p))
        return canonical, "exact_ambiguous"

    lower_map = defaultdict(list)
    for stem, paths in all_stems.items():
        lower_map[stem.lower()].extend(paths)

    if missing_stem.lower() in lower_map:
        paths = lower_map[missing_stem.lower()]
        canonical = min(paths, key=lambda p: (len(p), p))
        return canonical, "lowercase"

    target_words = set(missing_stem.replace("-", " ").split())
    best_sim = 0.0
    best_stem = None
    for stem in all_stems:
        stem_words = set(stem.replace("-", " ").split())
        if not stem_words:
            continue
        union = target_words | stem_words
        if not union:
            continue
        sim = len(target_words & stem_words) / len(union)
        if sim > best_sim:
            best_sim = sim
            best_stem = stem
    if best_stem and best_sim >= threshold:
        return all_stems[best_stem][0], f"fuzzy:{best_sim:.2f}"

    return None


def _replace_wikilink(text: str, old_target: str, new_target: str) -> tuple[str, bool]:
    """Replace [[old_target]] (or with alias) with [[new_target]].
    Also handles the path-anchored variant [[path/old_target]] and the
    normalized-stem variant (old_target may be the stem, text may have dashes).
    """
    old_path_anchored = f"[[/{old_target}]]"
    new_text = text.replace(old_path_anchored, f"[[{new_target}]]")
    changed = new_text != text
    if not changed:
        escaped = re.escape(old_target)
        pattern = rf"\[\[{escaped}(\|[^\]]+)?\]\]"
        new_text = re.sub(pattern, f"[[{new_target}]]", text)
        changed = new_text != text
    if not changed:
        escaped = re.escape(old_target.lower())
        pattern = rf"\[\[{escaped}(\|[^\]]+)?\]\]"
        new_text = re.sub(
            pattern,
            lambda m: f"[[{new_target}]]{m.group(1) or ''}]",
            text,
            flags=re.IGNORECASE,
        )
        changed = new_text != text
    if not changed:
        from vault_io import normalize_stem as _ns

        for match in RE_WIKILINK.finditer(text):
            found_raw = match.group(1)
            if _ns(found_raw) == _ns(old_target):
                replaced = (
                    f"[[{new_target}{match.group(2) or ''}]]"
                    if False
                    else f"[[{new_target}]]"
                )
                new_text = text[: match.start()] + replaced + text[match.end() :]
                changed = True
                break
    return new_text, changed


def _fix_brackets_in_content(text: str) -> tuple[str, int]:
    """Apply bracket fixers from vault_regex. Returns (text, fixes_count)."""
    before = text
    text = fix_nested_brackets(text)
    nested_fixes = 1 if text != before else 0
    before = text
    text = fix_whitespace_in_links(text)
    ws_fixes = 1 if text != before else 0
    return text, nested_fixes + ws_fixes


def _fix_path_anchored(text: str, all_stems: dict[str, list[str]] | None = None) -> tuple[str, int]:
    """Despoja la carpeta de `[[carpeta/nota]]` → `[[nota]]`, con dos frenos.

    Obsidian **sí** resuelve un destino con carpeta: `[[containers/ct105]]`
    apunta a `containers/ct105.md` y a ningún otro. Despojar la carpeta a
    ciegas era el mismo error que v40.12 arregló en la medida —resolver por
    basename— pero cometido por una tool que **escribe**, y con el signo
    contrario: allí un enlace roto salía verde; aquí un enlace bueno se
    convierte en ambiguo. Con dos `ct105.md` en carpetas distintas, el destino
    que Obsidian elija después ya no es el que la nota decía.

    Así que solo se despoja cuando quitarlo no pierde información:

    1. El destino con carpeta **no** existe (el enlace ya estaba roto), y
    2. el basename es único en el vault (no hay a qué confundirse).

    Sin índice (`all_stems is None`) no se toca nada: no saber es motivo para
    no escribir, no para escribir igual.
    """
    pattern = r"\[\[([^\]]*\/[^\]]+)\]\]"
    fixes = 0

    rutas = set()
    por_stem: dict[str, int] = {}
    if all_stems:
        for stem, caminos in all_stems.items():
            por_stem[stem] = len(caminos)
            for c in caminos:
                rutas.add(str(Path(c).with_suffix("")).replace("\\", "/").lower())

    def _strip(match: re.Match) -> str:
        nonlocal fixes
        path = match.group(1)
        if "/" not in path or path.startswith("http"):
            return match.group(0)
        if all_stems is None:
            return match.group(0)
        destino = path.split("|")[0].split("#")[0].strip().removesuffix(".md")
        crudo = destino.strip("/").lower()
        if any(r == crudo or r.endswith("/" + crudo) for r in rutas):
            return match.group(0)  # resuelve tal cual: quitarlo solo puede romperlo
        note_only = path.rsplit("/", 1)[-1]
        if por_stem.get(normalize_stem(note_only), 0) != 1:
            return match.group(0)  # ambiguo o inexistente: no se adivina
        fixes += 1
        return f"[[{note_only}]]"

    new_text = re.sub(pattern, _strip, text)
    return new_text, fixes


def _destinos_que_resuelven(root: Path, relativas: list[str]) -> set[str]:
    """Lo que Obsidian resuelve de verdad: sufijos de ruta y `aliases:`.

    Se construye con `vault_lib.indice_de_destinos`, que es el dueño canónico
    del criterio (AP-57). Esta tool no lo usaba y pagaba el precio en las dos
    direcciones: `_stems_set` indexa por `title:` —que Obsidian no mira— y no
    consulta `aliases:` en ningún punto.

    De las dos, la que hace daño es la segunda, porque esta tool **escribe**:
    un `[[Change Log]]` que resuelve por alias no estaba en el índice, se daba
    por roto, caía al fuzzy con umbral 0.7 y se reescribía apuntando a otra
    nota. Un enlace que funcionaba quedaba en disco apuntando a otro sitio.
    """
    aliases: list[str] = []
    for rel in relativas:
        try:
            fm = parse_frontmatter((root / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        crudos = fm.get("aliases") or fm.get("alias") or []
        if isinstance(crudos, str):
            crudos = [crudos]
        if isinstance(crudos, list):
            aliases.extend(a for a in crudos if isinstance(a, str))
    return indice_de_destinos(relativas, aliases)


def _process_note(
    path: str,
    info: dict[str, Any],
    all_stems: dict[str, list[str]],
    threshold: float,
    resuelven: set[str] | None = None,
) -> dict[str, Any]:
    """Process a single note. Returns fix report for that note."""
    text = info["body"]
    original = text
    fixes: list[dict[str, Any]] = []
    resuelven = resuelven or set()

    existing_stems = set(all_stems.keys())
    # AP-57: los candidatos se buscan **fuera** del código. Un `[[ejemplo]]`
    # dentro de un fence es texto que Obsidian enseña, no un enlace que
    # resuelve, y esta tool escribe: proponerlo como roto acababa reescribiendo
    # la nota que documenta la sintaxis.
    for match in list(re.finditer(r"\[\[([^\]|]+)", _RE_CODIGO.sub("", text))):
        # Antes de proponer nada: si el enlace resuelve con el criterio del
        # consumidor, no está roto y esta tool no lo toca. Es la única
        # comprobación que puede impedir que una reparación rompa lo que
        # funcionaba, y por eso va delante de todo lo demás.
        if resolver_destino_wikilink(match.group(1), desde=Path(path)) in resuelven:
            continue
        target_stem = normalize_stem(match.group(1))
        if target_stem and target_stem not in existing_stems:
            result = _find_target(target_stem, all_stems, threshold)
            if result:
                canonical_path, strategy = result
                new_text, changed = _fuera_de_codigo(
                    text,
                    lambda t: _replace_wikilink(
                        t, match.group(1), Path(canonical_path).stem)[0],
                ), False
                changed = new_text != text
                if changed:
                    fixes.append(
                        {
                            "type": "broken_link",
                            "from": match.group(1),
                            "to": Path(canonical_path).stem,
                            "strategy": strategy,
                            "canonical_path": canonical_path,
                        }
                    )
                    text = new_text

    new_text, bracket_fixes = _fix_brackets_in_content(text)
    if bracket_fixes:
        fixes.append({"type": "brackets", "count": bracket_fixes})
        text = new_text

    path_fixes = 0

    def _anchored(t: str) -> str:
        nonlocal path_fixes
        r, n = _fix_path_anchored(t, all_stems)
        path_fixes += n
        return r

    new_text = _fuera_de_codigo(text, _anchored)
    if path_fixes:
        fixes.append({"type": "path_anchored", "count": path_fixes})
        text = new_text

    return {
        "note": path,
        "fixes": fixes,
        "changed": text != original,
        "new_content": text if text != original else None,
    }


def fix_vault(
    root: Path,
    threshold: float = 0.7,
    only: str | None = None,
) -> dict[str, Any]:
    """Compute all fixes. Returns report. Does NOT write unless caller passes apply=True."""
    notes = _load_notes(root, include_migrated=False)
    all_notes_full = _load_notes(root, include_migrated=True)
    stems = _stems_set(all_notes_full)
    inverted_stems: dict[str, list[str]] = defaultdict(list)
    for stem, path in stems.items():
        inverted_stems[stem].append(path)
    resuelven = _destinos_que_resuelven(root, sorted(all_notes_full))

    note_reports: list[dict[str, Any]] = []
    for path in sorted(notes):
        info = notes[path]
        if only == "brackets":
            original = info["body"]
            new_text, count = _fix_brackets_in_content(original)
            if count:
                note_reports.append(
                    {
                        "note": path,
                        "fixes": [{"type": "brackets", "count": count}],
                        "changed": True,
                        "new_content": new_text,
                    }
                )
        elif only == "path_anchored":
            original = info["body"]
            new_text, count = _fix_path_anchored(original)
            if count:
                note_reports.append(
                    {
                        "note": path,
                        "fixes": [{"type": "path_anchored", "count": count}],
                        "changed": True,
                        "new_content": new_text,
                    }
                )
        else:
            note_reports.append(
                _process_note(path, info, inverted_stems, threshold, resuelven)
            )

    note_reports = [r for r in note_reports if r["changed"]]

    # Sello de la versión sobre la que se calculó el arreglo. `apply_fix` pega
    # un cuerpo calculado aquí sobre un frontmatter releído allí, y entre las
    # dos cosas puede pasar cualquier escritura: sin este sello la nota editada
    # entretanto se sobrescribía con una versión anterior y el informe decía
    # `applied`. Con él, la discrepancia se ve y la nota se salta.
    for r in note_reports:
        r["source_sha"] = _sha_del_fichero(root / r["note"])

    total_brackets = sum(
        sum(f["count"] for f in r["fixes"] if f["type"] == "brackets")
        for r in note_reports
    )
    total_path_anchored = sum(
        sum(f["count"] for f in r["fixes"] if f["type"] == "path_anchored")
        for r in note_reports
    )
    total_broken = sum(
        sum(1 for f in r["fixes"] if f["type"] == "broken_link") for r in note_reports
    )

    return {
        "ok": True,
        "tool": "vault_graph_fix",
        "vault_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        "scope": "excluding-10_Migrated",
        "summary": {
            "notes_to_modify": len(note_reports),
            "broken_links_fixed": total_broken,
            "bracket_fixes": total_brackets,
            "path_anchored_fixes": total_path_anchored,
        },
        "fixes": note_reports,
    }


def _sha_del_fichero(path: Path) -> str:
    """Hash del contenido tal y como está en disco, o "" si no se puede leer."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def apply_fix(report: dict[str, Any], root: Path) -> dict[str, Any]:
    """Apply report['fixes'] by writing modified notes atomically."""
    log_dir = root / _FIX_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    existing_log = []
    if log_path.exists():
        try:
            existing_log = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            existing_log = []

    applied = 0
    errors = []
    for fix in report["fixes"]:
        if not fix["new_content"]:
            continue
        target = root / fix["note"]
        try:
            # AP-54: leer, recomponer y escribir son tres pasos sobre el mismo
            # fichero. Sin lock, otra tool que escriba entremedias pierde su
            # cambio sin dejar rastro — y `--fix` masivo es justo cuando varias
            # corren a la vez.
            with file_lock(target):
                existing_text = target.read_text(encoding="utf-8")
                esperado = fix.get("source_sha")
                if esperado and _sha_del_fichero(target) != esperado:
                    errors.append({
                        "note": fix["note"],
                        "error": ("la nota cambió entre el análisis y la escritura: "
                                  "aplicar el arreglo revertiría esa edición"),
                        "error_code": "STALE_REPORT",
                    })
                    continue
                stripped = _strip_frontmatter(existing_text)
                body_part = existing_text.replace(stripped, "", 1) if stripped else ""
                new_full = body_part + fix["new_content"]
                atomic_write_text(target, new_full)
            applied += 1
        except Exception as exc:
            errors.append({"note": fix["note"], "error": str(exc)})

    existing_log.append(
        {
            "applied_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
            "report_summary": report["summary"],
            "applied_count": applied,
            "errors": errors,
        }
    )
    atomic_write_text(log_path, json.dumps(existing_log, indent=2, ensure_ascii=False))

    return {
        "applied": applied,
        "errors": errors,
        "log_file": str(log_path.relative_to(root)).replace("\\", "/"),
    }


def _strip_frontmatter(content: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    return content[match.end() :].strip() if match else content


def _load_notes_for_classify(root: Path) -> dict[str, dict[str, Any]]:
    """Load all notes INCLUDING 00_System/ but EXCLUDING 10_Migrated/.

    Used by classify to find resolution candidates in system notes.
    """
    notes: dict[str, dict[str, Any]] = {}
    for md in sorted(root.rglob("*.md")):
        try:
            rel = md.relative_to(root)
        except ValueError:
            continue
        rel_str = str(rel).replace("\\", "/")
        parts = rel.parts
        # AP-57: qué es una instantánea congelada lo decide `vault_io`, no esta
        # lista. La local ya había divergido —tenía las tres carpetas de
        # `SNAPSHOT_DIRS` copiadas a mano— y esta tool **escribe**, así que una
        # divergencia aquí no infla una medida: repara dentro de una
        # instantánea, que es precisamente dejar de serlo.
        if is_snapshot_path(rel):
            continue
        skip_set = {"99_Index", "vault-sandbox", ".obsidian"}
        if any(p in skip_set for p in parts):
            continue
        if rel.name.startswith("."):
            continue
        if rel_str.startswith("10_Migrated/"):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        body = _vgi_strip_frontmatter(text)
        body_hash = hashlib.sha256(
            _normalize_for_hash(body).encode("utf-8")
        ).hexdigest()
        notes[rel_str] = {
            "body": body,
            "title": _extract_title(text) or rel.stem,
            "tags": _extract_tags(text),
            "body_hash": body_hash,
        }
    return notes


# ============================================================================
# CLASSIFICATION — categorize broken links by auto-fix viability
# ============================================================================

_REDUNDANT_PREFIXES = (
    "ansans",
    "ansmcp",
    "ansvault",
    "ans-",
    "mcp-",
    "vault-",
    "ans_",
    "mcp_",
    "vault_",
)


def _strip_redundant_prefix(stem: str) -> str | None:
    """If stem has a known redundant prefix, return the stripped version."""
    s = stem.lower()
    for prefix in sorted(_REDUNDANT_PREFIXES, key=len, reverse=True):
        if s.startswith(prefix) and len(s) > len(prefix) + 2:
            stripped = s[len(prefix) :]
            if stripped:
                return stripped
    return None


def _tokens(s: str) -> list[str]:
    """Tokens comparables de un stem o de una ruta-stem.

    Normaliza los dos lados igual. Antes no lo hacía: el target llegaba
    colapsado sin separadores (`apbarenumbercssunits`, tal como aparece en la
    clave del wikilink roto) y el candidato los conservaba
    (`numbers-without-css-units`), asi que la interseccion de tokens era vacia
    en TODAS las comparaciones y el termino Jaccard del score valia 0.000
    siempre. El 20% del score que llevaba la semantica no pesaba nada.
    """
    return [t for t in re.split(r"[^0-9a-z]+", s.lower()) if t]


def _jaccard_tokens(a: str, b: str) -> float:
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return 0.0
    # Un stem colapsado ("apbarenumbercssunits") es un token gigante que no
    # interseca con nada. Se expande buscando dentro de el los tokens del otro
    # lado: es la unica forma de comparar los dos formatos de slug que conviven
    # en un vault preexistente. Se expande cada lado contra el otro, porque el
    # token colapsado puede venir acompanado de los de la carpeta.
    ta_exp, tb_exp = _expandir(ta, tb), _expandir(tb, ta)
    return len(ta_exp & tb_exp) / len(ta_exp | tb_exp)


def _expandir(tokens: set[str], vocabulario: set[str]) -> set[str]:
    """Sustituye cada token largo por los del vocabulario que contiene."""
    fuera: set[str] = set()
    for t in tokens:
        dentro = {v for v in vocabulario if len(v) >= 3 and v != t and v in t}
        fuera |= dentro or {t}
    return fuera


def _seq_ratio(a: str, b: str) -> float:
    """Similitud de secuencia real, sensible al orden.

    La version anterior era `sum(1 for ch in a if ch in b)`: contaba cuantos
    caracteres de `a` aparecian en CUALQUIER posicion de `b`, sin orden ni
    multiplicidad. Eso no mide parecido, mide solapamiento de alfabeto — y dos
    slugs en minusculas comparten casi todo el alfabeto. Peor: cuanto mas largo
    el candidato, mas caracteres distintos contiene y mas alto puntuaba, asi que
    el ranking tendia a recomendar la nota de titulo mas largo del vault. Un par
    sin ninguna relacion llegaba a 0.913, por encima del umbral de auto-fix.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # El target puede venir con prefijo de carpeta ("02observability/anti.../x")
    # y el candidato ser solo el stem. Se compara tambien el ultimo segmento
    # para no castigar esa asimetria, y se toma el mejor de los dos.
    variantes = {a, a.rsplit("/", 1)[-1]}
    return max(
        difflib.SequenceMatcher(None, v, b.rsplit("/", 1)[-1]).ratio() for v in variantes
    )


# Deliberadamente pequeno: la seccion desempata, no decide. Un bono grande
# convertiria "esta en la carpeta correcta" en "es la nota correcta".
_BONO_SECCION = 0.08


def _seccion_del_target(target_stem: str) -> str | None:
    """Seccion numerada que el propio enlace roto declara, si la trae.

    Un wikilink roto de la forma `02observability/antipatterns/algo` dice a que
    seccion apuntaba. Es la senal mas fiable que queda cuando el stem ya no
    existe, y el scorer la ignoraba: solo comparaba stems.
    """
    if "/" not in target_stem:
        return None
    # El segmento llega colapsado ("02observability"), asi que el numero no es
    # un token propio: hay que leer los digitos iniciales.
    m = re.match(r"(\d{2})", target_stem.split("/", 1)[0].strip().lower())
    return m.group(1) if m else None


def _bonificar_por_seccion(target_stem: str, candidates: list[dict[str, Any]]) -> None:
    """Sube el score de los candidatos que viven en la seccion que pedia el enlace.

    Encontrado sanando BuilderX: dos enlaces rotos apuntaban cada uno a la nota
    del otro — `02observability/antipatterns/apvalidatoradvisory...` se resolvia
    al ADR y `03decisions/adr...validatoradvisory...` al antipatron. Los dos
    stems se parecen entre si mas que a su propio destino, asi que sin mirar la
    seccion el cruce es inevitable. La bonificacion es pequena a proposito:
    rompe empates y cruces, no fabrica coincidencias donde no hay parecido.
    """
    seccion = _seccion_del_target(target_stem)
    if not seccion:
        return
    for c in candidates:
        prefijo = c["path"].split("/", 1)[0]
        if prefijo.split("_", 1)[0] == seccion:
            c["score"] = round(min(0.99, c["score"] + _BONO_SECCION), 3)
            c["strategy"] = f"{c['strategy']}+seccion"


def _classify_broken(
    target_stem: str,
    active_stems: dict[str, list[str]],
    migrated_stems: dict[str, list[str]],
    # `partial_match` es un cajon de REVISION, no de escritura: quien decide
    # aplicar es `--auto-apply-partial`, con su propio umbral (0.75+). Por eso
    # aqui conviene ser generoso: un candidato de mas se descarta leyendolo, uno
    # de menos es un enlace recuperable que se pierde. El 0.60 heredado estaba
    # calibrado contra el scorer viejo, que inflaba todo por solapamiento de
    # alfabeto; con similitud de secuencia real la escala bajo y ese mismo 0.60
    # empezo a tirar coincidencias buenas a `no_match`.
    threshold_partial: float = 0.45,
    threshold_exact: float = 0.85,
) -> dict[str, Any]:
    """Classify a broken link target. Returns category, candidates, recommended_stem."""
    candidates: list[dict[str, Any]] = []

    if target_stem in active_stems:
        for path in active_stems[target_stem]:
            candidates.append(
                {
                    "stem": target_stem,
                    "path": path,
                    "score": 1.0,
                    "strategy": "exact_active",
                }
            )

    stripped = _strip_redundant_prefix(target_stem)
    if stripped and stripped in active_stems:
        for path in active_stems[stripped]:
            candidates.append(
                {
                    "stem": stripped,
                    "path": path,
                    "score": 1.0,
                    "strategy": "prefix_strip",
                }
            )
    elif stripped:
        for stem, paths in active_stems.items():
            if stem == stripped or stripped in stem or stem in stripped:
                seq_ratio = _seq_ratio(stripped, stem)
                jac = _jaccard_tokens(stripped, stem)
                score = 0.8 * seq_ratio + 0.2 * jac
                if score >= 0.7:
                    for path in paths:
                        candidates.append(
                            {
                                "stem": stem,
                                "path": path,
                                "score": min(0.99, round(score + 0.05, 3)),
                                "strategy": "prefix_strip_fuzzy",
                            }
                        )

    if target_stem in migrated_stems:
        for path in migrated_stems[target_stem]:
            candidates.append(
                {
                    "stem": target_stem,
                    "path": path,
                    "score": 1.0,
                    "strategy": "exact_migrated",
                }
            )

    for stem, paths in active_stems.items():
        if any(c["stem"] == stem for c in candidates):
            continue
        seq_ratio = _seq_ratio(target_stem, stem)
        jac = _jaccard_tokens(target_stem, stem)
        score = 0.8 * seq_ratio + 0.2 * jac
        # Sin tope superior. Estaba `score < threshold_exact`, que descartaba un
        # candidato por ser DEMASIADO parecido: en BuilderX,
        # `apvalidatoradvisorynotblocking` puntuaba 0.864 contra su propia nota
        # `ap-validator-advisory-not-blocking` y caia en esa zona muerta, asi
        # que ganaba un ADR distinto con 0.615 y los enlaces se cruzaban. La
        # categoria `exact_candidate` existe precisamente para los >= 0.85: con
        # el tope puesto era inalcanzable por esta via y nunca se emitia.
        if score >= threshold_partial:
            for path in paths:
                candidates.append(
                    {
                        "stem": stem,
                        "path": path,
                        "score": round(score, 3),
                        "strategy": "fuzzy",
                    }
                )

    if not candidates:
        return {
            "category": "no_match",
            "candidates": [],
            "recommended_stem": None,
        }

    _bonificar_por_seccion(target_stem, candidates)
    candidates.sort(key=lambda c: -c["score"])
    best = candidates[0]

    for c in candidates:
        if "\u2014" in c["stem"] or "\u2013" in c["stem"]:
            raw_stem = Path(c["path"]).stem
            if raw_stem and not ("\u2014" in raw_stem or "\u2013" in raw_stem):
                c["stem"] = raw_stem

    if best["score"] >= threshold_exact:
        if best["strategy"] == "exact_migrated":
            category = "points_to_migrated"
        else:
            category = "exact_candidate"
    elif best["score"] >= threshold_partial:
        category = "partial_match"
    else:
        category = "no_match"

    active_first = [c for c in candidates if not c["path"].startswith("10_Migrated/")]
    if active_first and category == "points_to_migrated":
        best = active_first[0]
        category = (
            "exact_candidate" if best["score"] >= threshold_exact else "partial_match"
        )

    return {
        "category": category,
        "candidates": candidates[:5],
        "recommended_stem": best["stem"],
    }


def classify_all_broken(
    notes_active: dict[str, dict[str, Any]],
    notes_full: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Classify every unique broken target in the active vault.

    Resolves against ALL non-migrated notes including 00_System/ — the inspector
    excludes 00_System/ from broken-link detection by convention, but for the
    purpose of finding resolutions, we treat 00_System notes as valid targets
    and label them with a `system_resolvable: True` flag.
    """
    active_stems: dict[str, list[str]] = defaultdict(list)
    migrated_stems: dict[str, list[str]] = defaultdict(list)
    system_stems: dict[str, list[str]] = defaultdict(list)

    def _add_stems(index: dict[str, list[str]], path: str, info: dict[str, Any]) -> None:
        # AP-44 se cumple aquí: se indexa por el criterio del consumidor real
        # —Obsidian resuelve `[[…]]` por nombre de fichero— y no solo por el
        # que esta tool preferiría. Por eso se indexan AMBOS stems, el del
        # título y el del filename (espeja `_stems_set` en
        # vault_graph_inspect): con solo el del título, un enlace escrito
        # contra el nombre del fichero saldría roto siendo válido, y la tool
        # se estaría certificando con su propia normalización.
        for stem in {
            normalize_stem(info["title"] or Path(path).stem),
            normalize_stem(Path(path).stem),
        }:
            if stem and path not in index[stem]:
                index[stem].append(path)

    for path, info in notes_full.items():
        if not path.startswith("00_System/"):
            continue
        _add_stems(system_stems, path, info)

    for path, info in notes_full.items():
        if path.startswith("10_Migrated/") or path.startswith("00_System/"):
            continue
        _add_stems(active_stems, path, info)

    for path, info in notes_full.items():
        if not path.startswith("10_Migrated/"):
            continue
        _add_stems(migrated_stems, path, info)

    resolvable_stems: dict[str, list[str]] = {**active_stems, **system_stems}

    broken_targets: dict[str, list[str]] = defaultdict(list)
    resolvable_set = set(resolvable_stems)
    for path, info in notes_active.items():
        body = info["body"]
        for link in extract_wiki_links_strict(body):
            target_stem = normalize_stem(link)
            if target_stem and target_stem not in resolvable_set:
                broken_targets[target_stem].append(path)

    classified: dict[str, dict[str, Any]] = {}
    for target in sorted(broken_targets):
        cls = _classify_broken(target, active_stems, migrated_stems)
        for c in cls.get("candidates", []):
            if c["path"].startswith("00_System/"):
                c["system_resolvable"] = True
        classified[target] = cls
        classified[target]["referenced_by"] = broken_targets[target][:20]
        classified[target]["referenced_by_count"] = len(broken_targets[target])

    return classified


# ============================================================================
# INTERACTIVE WIZARD
# ============================================================================


def wizard_pick(
    target_stem: str,
    candidates: list[dict[str, Any]],
    referenced_by_count: int,
    stdin: Any = None,
    stdout: Any = None,
) -> dict[str, str] | None:
    """Show candidates for one broken stem, ask user to choose.

    Returns {"action": "fix"|"skip"|"stub", "stem": ..., "path": ...} or None on EOF.
    """
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    stdout.write(
        f"\n[Broken link] [[{target_stem}]]  (referenced by {referenced_by_count} note(s))\n"
    )
    if not candidates:
        stdout.write("  No candidates found.\n")
        stdout.write("  Options: [s]kip (keep broken) | [t]ub (create stub note)\n")
    else:
        stdout.write("  Candidates:\n")
        for i, c in enumerate(candidates, 1):
            stdout.write(
                f"    [{i}] {c['stem']:<40} -> {c['path']:<60} "
                f"score={c['score']:.2f} ({c['strategy']})\n"
            )
        stdout.write("  Options: [1-N] pick | [s]kip | [t]ub | [q]uit wizard\n")

    try:
        choice = stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if not choice:
        return {"action": "skip"}
    if choice in ("s", "skip"):
        return {"action": "skip"}
    if choice in ("q", "quit"):
        return None
    if choice in ("t", "stub"):
        return {"action": "stub"}
    if candidates:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return {
                    "action": "fix",
                    "stem": candidates[idx]["stem"],
                    "path": candidates[idx]["path"],
                }
        except ValueError:
            pass
    stdout.write("  (invalid choice — skipping)\n")
    return {"action": "skip"}


# ============================================================================
# STUB CREATION
# ============================================================================

# AP-36: los stubs de mantenimiento van a la sección dedicada de mantenimiento,
# no a 04_Sessions — son artefactos de triage, no notas de sesión.
_STUBS_DIR = "02_Observability/maintenance/stubs"


def _stub_already_exists(root: Path, target_stem: str) -> bool:
    """Avoid creating a stub that collides with a real note."""
    if (root / _STUBS_DIR / f"{target_stem}.md").exists():
        return True
    # Trece secciones escritas a mano en un orden que ya no dice nada: si la
    # nota real vivía en `14_Requirements` o en cualquiera de las cuatro de
    # v39, la colisión no se veía y el stub se creaba encima de contenido real.
    # Es el peor sitio posible para una lista incompleta — la comprobación
    # existe precisamente para no pisar nada.
    for sub in ORDERED_SECTIONS:
        if (root / sub / f"{target_stem}.md").exists():
            return True
    return False


def _create_stub(
    root: Path,
    target_stem: str,
    referenced_by: list[str],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Create an empty stub note flagging it as a graph-fix artifact."""
    if _stub_already_exists(root, target_stem):
        return {"stem": target_stem, "created": False, "reason": "already_exists"}

    stubs_dir = root / _STUBS_DIR
    stubs_dir.mkdir(parents=True, exist_ok=True)
    path = stubs_dir / f"{target_stem}.md"
    now = datetime.now(timezone.utc).isoformat()[:19] + "Z"

    ref_list = "\n".join(f"- `[[{p}]]`" for p in referenced_by[:20])
    if len(referenced_by) > 20:
        ref_list += f"\n- ... and {len(referenced_by) - 20} more"

    body = f"""---
id: stub-{target_stem}-{now[:10]}
title: {target_stem}
type: stub
createdAt: {now}
updatedAt: {now}
created_by: vault_graph_fix
classification: {classification["category"]}
referenced_by_count: {len(referenced_by)}
cia_integrity: low
cia_availability: low
cia_sensitivity: internal
tags: [stub, graph-fix, needs-review]
---

# {target_stem}

> **Stub note** — auto-created by `vault_graph_fix` on {now[:10]}.
> No canonical note exists for this target stem.
> Referenced by:
{ref_list}

## Recommended action

- **If this stem should resolve to an existing note**: edit the source notes
  and replace `[[{target_stem}]]` with the correct target, then delete this stub.
- **If this stem should become a real note**: rename this stub to its proper
  folder, fill content, remove the `stub` and `graph-fix` tags.
- **If this stem is a placeholder** (e.g., appears in docs as `[[nota]]`):
  edit the docs to use code-fence escaping — ` [[{target_stem}]] ` inside a
  triple-backtick block — or rephrase the example to avoid the false link.
"""
    atomic_write_text(path, body)
    return {
        "stem": target_stem,
        "created": True,
        "path": str(path.relative_to(root)).replace("\\", "/"),
    }


# ============================================================================
# APPLY CLASSIFIED DECISIONS
# ============================================================================


def _destino_escribible(decision: dict[str, Any], target_stem: str) -> str:
    """Nombre de nota tal como hay que escribirlo dentro de `[[...]]`.

    Prioriza el nombre real del fichero (`path`), que es lo unico que Obsidian
    sabe resolver. Solo cae al `stem` normalizado si no hay ruta, y en ese caso
    conserva el target original antes que escribir una forma colapsada.
    """
    ruta = decision.get("path") or (decision.get("classification", {}) or {}).get("path")
    if ruta:
        return Path(ruta).stem
    stem = decision.get("stem")
    return stem if stem and "-" in stem else target_stem


def apply_classified_fixes(
    decisions: dict[str, dict[str, Any]],
    notes_active: dict[str, dict[str, Any]],
    root: Path,
) -> dict[str, Any]:
    """Apply decisions: {target_stem: {action, stem, path, referenced_by, classification}}.

    Optimized: group all fixes by source NOTE, then write each note once
    applying all its fixes (replaces N writes per note with 1 write).
    """
    applied_notes: set[str] = set()
    fixed_count = 0
    skip_count = 0
    stub_results: list[dict[str, Any]] = []

    note_fixes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for target_stem, decision in decisions.items():
        action = decision.get("action", "skip")
        if action == "skip":
            skip_count += 1
            continue
        if action == "stub":
            referenced_by = decision.get("referenced_by", [])
            classification = decision.get("classification", {"category": "no_match"})
            stub_results.append(
                _create_stub(root, target_stem, referenced_by, classification)
            )
            continue
        if action == "fix":
            # El destino que se ESCRIBE sale del nombre real del fichero, no de
            # la clave normalizada. `stem` viene de `active_stems`, cuyas claves
            # estan colapsadas sin separadores: escribirlo producia
            # `[[adrmodeloaccioncanonicoydeudacomponentes]]` para el fichero
            # `adr-modelo-accion-canonico-y-deuda-componentes.md`. Obsidian no
            # resuelve eso, pero la propia tool lo daba por reparado porque al
            # comprobar normaliza los dos lados — se autoenganaba, y cada
            # "arreglo" dejaba un enlace roto nuevo.
            new_target_stem = _destino_escribible(decision, target_stem)
            for source_path in decision.get("referenced_by", []):
                note_fixes[source_path].append((target_stem, new_target_stem))

    for source_path, fixes in note_fixes.items():
        note_info = notes_active.get(source_path)
        if not note_info:
            continue
        full_path = root / source_path
        try:
            existing = full_path.read_text(encoding="utf-8")
        except OSError:
            continue
        stripped = _vgi_strip_frontmatter(existing)
        front = existing.replace(stripped, "", 1) if stripped != existing else ""
        body = stripped
        note_changes = 0
        for old_target, new_target in fixes:
            new_body, changed = _replace_wikilink(body, old_target, new_target)
            if changed:
                body = new_body
                note_changes += 1
        if note_changes == 0:
            continue
        atomic_write_text(full_path, front + body)
        fixed_count += note_changes
        applied_notes.add(source_path)

    log_dir = root / _FIX_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = (
        log_dir
        / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}-classified.json"
    )
    log = {
        "applied_at": datetime.now(timezone.utc).isoformat()[:19] + "Z",
        "notes_modified": len(applied_notes),
        "links_fixed": fixed_count,
        "stubs_created": sum(1 for s in stub_results if s.get("created")),
        "stubs_skipped_existing": sum(1 for s in stub_results if not s.get("created")),
        "links_skipped": skip_count,
        "stubs": stub_results,
    }
    atomic_write_text(log_path, json.dumps(log, indent=2, ensure_ascii=False))

    return {
        "applied_notes": len(applied_notes),
        "links_fixed": fixed_count,
        "stubs_created": log["stubs_created"],
        "stubs_skipped_existing": log["stubs_skipped_existing"],
        "links_skipped": skip_count,
        "log_file": str(log_path.relative_to(root)).replace("\\", "/"),
    }


# ============================================================================
# MAIN — extended CLI
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix broken wiki-links + bracket/path issues + wizard + stubs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Vault root (default: VAULT_ROOT)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes (default: dry-run)",
    )
    parser.add_argument(
        "--auto-apply-partial",
        type=float,
        metavar="THRESHOLD",
        default=None,
        help="Auto-apply partial_match with score >= THRESHOLD (e.g., 0.75). "
        "Lower-confidence partials are skipped (logged for review).",
    )
    parser.add_argument(
        "--only", choices=["brackets", "path_anchored"], help="Only run one fixer"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Fuzzy match threshold (default: 0.7)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON (default)")

    parser.add_argument(
        "--classify",
        action="store_true",
        help="Classify all broken links and emit JSON; no writes",
    )
    parser.add_argument(
        "--auto-fix-safe",
        action="store_true",
        help="Auto-resolve exact_candidate and points_to_migrated without prompting",
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Interactive wizard for partial_match links (uses stdin/stdout)",
    )
    parser.add_argument(
        "--stubs",
        action="store_true",
        help="Create stub notes in 04_Sessions/stubs/ for no_match targets",
    )
    parser.add_argument(
        "--stubs-all",
        action="store_true",
        help="Create stubs for ALL unfixed broken links (overrides default skip)",
    )
    args = parser.parse_args()

    # stdout may be a StringIO under wrap_main capture (no reconfigure) — guard it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root = Path(args.root).resolve() if args.root else get_vault_root()
    if args.root:
        # AP-36: la observabilidad (traces/locks) debe escribir en el vault objetivo
        from vault_io import set_vault_root
        set_vault_root(root)
    if not root.exists():
        print(json.dumps(emit_error("vault_graph_fix", "VAULT_NOT_FOUND", f"Vault root not found: {root}"), ensure_ascii=False))
        return 1

    if args.classify:
        notes_active = _load_notes(root, include_migrated=False)
        notes_full = _load_notes_for_classify(root)
        notes_migrated = {
            p: info
            for p, info in _load_notes(root, include_migrated=True).items()
            if p.startswith("10_Migrated/")
        }
        notes_full.update(notes_migrated)
        classified = classify_all_broken(notes_active, notes_full)
        distribution: dict[str, int] = defaultdict(int)
        for c in classified.values():
            distribution[c["category"]] += 1
        result = {
            "ok": True,
            "tool": "vault_graph_fix.classify",
            "vault_root": str(root),
            "summary": {
                "total_broken_targets": len(classified),
                "by_category": dict(distribution),
            },
            "classified": classified,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if (
        args.auto_fix_safe
        or args.wizard
        or args.stubs
        or args.stubs_all
        or args.auto_apply_partial is not None
    ):
        notes_active = _load_notes(root, include_migrated=False)
        notes_full = _load_notes_for_classify(root)
        notes_migrated = {
            p: info
            for p, info in _load_notes(root, include_migrated=True).items()
            if p.startswith("10_Migrated/")
        }
        notes_full.update(notes_migrated)
        classified = classify_all_broken(notes_active, notes_full)
        decisions: dict[str, dict[str, Any]] = {}

        for target, cls in classified.items():
            cat = cls["category"]
            ref_by = cls.get("referenced_by", [])
            ref_count = cls.get("referenced_by_count", len(ref_by))

            if cat in ("exact_candidate", "points_to_migrated"):
                if args.auto_fix_safe and cls.get("candidates"):
                    best = cls["candidates"][0]
                    decisions[target] = {
                        "action": "fix",
                        "stem": best["stem"],
                        "path": best["path"],
                        "referenced_by": ref_by,
                        "classification": cls,
                    }
                else:
                    decisions[target] = {
                        "action": "skip",
                        "referenced_by": ref_by,
                        "classification": cls,
                    }
            elif cat == "partial_match":
                best_score = (
                    cls["candidates"][0]["score"] if cls.get("candidates") else 0
                )
                threshold = args.auto_apply_partial
                if args.wizard:
                    pick = wizard_pick(target, cls["candidates"], ref_count)
                    if pick is None:
                        decisions[target] = {
                            "action": "skip",
                            "referenced_by": ref_by,
                            "classification": cls,
                        }
                    else:
                        pick["referenced_by"] = ref_by
                        pick["classification"] = cls
                        decisions[target] = pick
                elif (
                    threshold is not None
                    and best_score >= threshold
                    and cls.get("candidates")
                ):
                    best = cls["candidates"][0]
                    decisions[target] = {
                        "action": "fix",
                        "stem": best["stem"],
                        "path": best["path"],
                        "referenced_by": ref_by,
                        "classification": cls,
                    }
                else:
                    decisions[target] = {
                        "action": "skip",
                        "referenced_by": ref_by,
                        "classification": cls,
                    }
            else:
                if args.stubs_all or args.stubs:
                    decisions[target] = {
                        "action": "stub",
                        "referenced_by": ref_by,
                        "classification": cls,
                    }
                else:
                    decisions[target] = {
                        "action": "skip",
                        "referenced_by": ref_by,
                        "classification": cls,
                    }

        if args.apply:
            apply_result = apply_classified_fixes(decisions, notes_active, root)
            output = {
                "ok": True,
                "tool": "vault_graph_fix.classified",
                "decisions_count": len(decisions),
                "apply_result": apply_result,
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
            return 0
        else:
            preview = {
                "ok": True,
                "tool": "vault_graph_fix.classify",
                "decisions_count": len(decisions),
                "would_apply": {
                    "fix": sum(
                        1 for d in decisions.values() if d.get("action") == "fix"
                    ),
                    "stub": sum(
                        1 for d in decisions.values() if d.get("action") == "stub"
                    ),
                    "skip": sum(
                        1 for d in decisions.values() if d.get("action") == "skip"
                    ),
                },
                "decisions": decisions,
            }
            print(json.dumps(preview, indent=2, ensure_ascii=False))
            return 0

    report = fix_vault(root=root, threshold=args.threshold, only=args.only)

    if args.apply:
        apply_result = apply_fix(report, root)
        report["apply_result"] = apply_result
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if apply_result["errors"] == [] else 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_graph_fix"))
