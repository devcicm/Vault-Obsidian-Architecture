#!/usr/bin/env python3
"""
Vault Diff Tool — Compare note versions or two arbitrary files.

Compares current note vs .history/ (default) or two explicit paths.
Returns structured hunks with line numbers, similarity ratio and stats.

Usage:
    python vault_diff.py --path "01_Projects/ans/overview.md"
    python vault_diff.py --path "01_Projects/ans/overview.md" --version "2"
    python vault_diff.py --compare "scripts/vault_errors.py" --with "scripts/vault_errors_v2.py"
    python vault_diff.py --path "01_Projects/ans/overview.md" --stat
    python vault_diff.py --hash "01_Projects/ans/overview.md"
"""

import argparse
import difflib
import hashlib
import json
import sys
from vault_errors import emit_error, wrap_main
from pathlib import Path
from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def get_history(note_path: Path) -> List[str]:
    """Get all historical versions sorted newest first."""
    if not _history_dir().exists():
        return []
    note_name = note_path.stem
    rel_parent = str(note_path.parent.relative_to(_raiz()))
    folder_prefix = rel_parent.replace("\\", "__").replace("/", "__")
    prefix = f"{folder_prefix}__{note_name}-"
    versions = [f.name for f in _history_dir().iterdir() if f.is_file() and f.name.startswith(prefix)]
    versions.sort(reverse=True)
    return versions


def _compute_hash(path: Path) -> Dict[str, Any]:
    """Return MD5 + SHA1 for a file."""
    try:
        data = path.read_bytes()
        return {
            "ok": True,
            "path": str(path.relative_to(_raiz())).replace("\\", "/"),
            "hash_md5":   hashlib.md5(data).hexdigest(),
            "hash_sha1":  hashlib.sha1(data).hexdigest(),
            "size_bytes": len(data),
        }
    except Exception as e:
        return emit_error("vault_diff", "FILE_READ_ERROR", f"No se pudo leer para comparar: {e}", exception=e)


def _run_diff(
    lines_a: List[str],
    lines_b: List[str],
    label_a: str,
    label_b: str,
    context: int = 3,
    stat_only: bool = False,
) -> Dict[str, Any]:
    """Core diff engine shared by all modes."""
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    ratio = matcher.ratio()
    added = removed = 0
    hunks: List[Dict[str, Any]] = []

    if stat_only:
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete"):
                removed += i2 - i1
            if tag in ("replace", "insert"):
                added += j2 - j1
    else:
        for group in matcher.get_grouped_opcodes(context):
            hunk: Dict[str, Any] = {"lines": []}
            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for n, line in enumerate(lines_a[i1:i2], i1 + 1):
                        hunk["lines"].append({"op": " ", "line_a": n, "text": line})
                if tag in ("replace", "delete"):
                    for n, line in enumerate(lines_a[i1:i2], i1 + 1):
                        hunk["lines"].append({"op": "-", "line_a": n, "text": line})
                        removed += 1
                if tag in ("replace", "insert"):
                    for n, line in enumerate(lines_b[j1:j2], j1 + 1):
                        hunk["lines"].append({"op": "+", "line_b": n, "text": line})
                        added += 1
            if hunk["lines"]:
                hunks.append(hunk)

    result: Dict[str, Any] = {
        "ok": True,
        "changed": added > 0 or removed > 0,
        "similarity": round(ratio, 3),
        "lines_added": added,
        "lines_removed": removed,
        "total_lines_a": len(lines_a),
        "total_lines_b": len(lines_b),
        "compared_a": label_a,
        "compared_b": label_b,
    }
    if not stat_only:
        result["hunks"] = hunks
    return result


def _resolve_path(p: str) -> Path:
    """Resuelve ruta: absoluta > vault-relative > scripts-relative."""
    raw = Path(p)
    if raw.is_absolute():
        return raw
    candidate = _raiz() / p
    if candidate.exists():
        return candidate
    candidate2 = Path(__file__).parent / p
    return candidate2 if candidate2.exists() else candidate


def vault_diff(
    path: Optional[str] = None,
    version: Optional[str] = None,
    compare_a: Optional[str] = None,
    compare_b: Optional[str] = None,
    stat_only: bool = False,
    hash_only: bool = False,
    context: int = 3,
) -> Dict[str, Any]:
    """
    Compare note versions or two arbitrary paths.

    Modes:
      --path                       current vs most recent .history/
      --path + --version           current vs specific .history/ version
      --compare A --with B         two explicit paths (absolute or vault-relative)
      --hash PATH                  hash only, no diff
      Any mode + --stat            stats only, no hunk content
    """
    # ── Mode: arbitrary file comparison ──────────────────────────────────────
    if compare_a is not None and compare_b is not None:
        path_a = _resolve_path(compare_a)
        path_b = _resolve_path(compare_b)

        if hash_only:
            return {
                "ok": True,
                "a": _compute_hash(path_a),
                "b": _compute_hash(path_b),
            }

        for p in (path_a, path_b):
            if not p.exists():
                return emit_error("vault_diff", "FILE_NOT_FOUND", f"No existe: {p}")

        lines_a = path_a.read_text(encoding="utf-8", errors="replace").splitlines()
        lines_b = path_b.read_text(encoding="utf-8", errors="replace").splitlines()
        return _run_diff(lines_a, lines_b, str(path_a), str(path_b), context, stat_only)

    # ── Mode: note vs .history/ ───────────────────────────────────────────────
    if path is None:
        return emit_error("vault_diff", "MISSING_REQUIRED_ARG", f"Indica --path, o bien --compare y --with")

    note_path = _raiz() / path
    if not note_path.exists():
        return emit_error("vault_diff", "NOTE_NOT_FOUND", f"No existe la nota: {path}")

    if hash_only:
        return _compute_hash(note_path)

    current_lines = note_path.read_text(encoding="utf-8", errors="replace").splitlines()
    history = get_history(note_path)

    if not history:
        return {
            "ok": True,
            "path": path,
            "changed": False,
            "compared_against": None,
            "history": [],
            "message": "No historical versions found",
        }

    if version is None:
        target_name = history[0]
    elif version in history:
        target_name = version
    else:
        return emit_error("vault_diff", "VERSION_NOT_FOUND", f"Versión '{version}' inexistente. Disponibles: {history}")

    old_lines = (_history_dir() / target_name).read_text(encoding="utf-8", errors="replace").splitlines()
    result = _run_diff(old_lines, current_lines, target_name, path, context, stat_only)
    result["history"] = history
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Diff Tool — compare note versions or two files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Nota vs version mas reciente en .history/
  python vault_diff.py --path "01_Projects/ans/overview.md"

  # Nota vs version especifica
  python vault_diff.py --path "01_Projects/ans/overview.md" --version "01_Projects__ans__overview-2026-05-01.md"

  # Dos archivos arbitrarios (rutas relativas al vault o absolutas)
  python vault_diff.py --compare scripts/vault_errors.py --with /tmp/vault_errors_backup.py

  # Solo estadisticas (sin contenido de hunks -- mucho mas compacto para LLM)
  python vault_diff.py --path "01_Projects/ans/overview.md" --stat

  # Solo hash (verificar si cambio sin leer el archivo)
  python vault_diff.py --hash "01_Projects/ans/overview.md"

  # Hash de dos archivos para comparar
  python vault_diff.py --compare scripts/vault_errors.py --with /tmp/backup.py --hash
""",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--path",    help="Ruta relativa de nota (vs .history/)")
    group.add_argument("--hash",    dest="hash_path", metavar="PATH",
                       help="Solo calcular hash del archivo (sin diff)")

    parser.add_argument("--version",  help="Archivo en .history/ (default: el mas reciente)")
    parser.add_argument("--compare",  metavar="FILE_A", help="Archivo A para comparacion directa")
    parser.add_argument("--with",     dest="with_file", metavar="FILE_B",
                        help="Archivo B para comparacion directa (requiere --compare)")
    parser.add_argument("--stat",     action="store_true",
                        help="Solo estadisticas (sin hunks) -- ideal para LLM")
    parser.add_argument("--context",  type=int, default=3,
                        help="Lineas de contexto alrededor de cada cambio (default: 3)")

    args = parser.parse_args()

    if args.hash_path:
        resolved = _resolve_path(args.hash_path)
        result = _compute_hash(resolved)
    elif args.compare and args.with_file:
        result = vault_diff(
            compare_a=args.compare,
            compare_b=args.with_file,
            stat_only=args.stat,
            hash_only=False,
            context=args.context,
        )
    elif args.path:
        result = vault_diff(
            path=args.path,
            version=args.version,
            stat_only=args.stat,
            context=args.context,
        )
    else:
        parser.error("Provide --path, --hash, or --compare/--with")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_diff"))
