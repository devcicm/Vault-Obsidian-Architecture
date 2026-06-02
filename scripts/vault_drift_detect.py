#!/usr/bin/env python3
"""
Vault Drift Detect — Detect undocumented file changes

Compares project file state against a baseline snapshot and cross-references
changes against vault documentation. Identifies what was worked on but not documented.

Supports both git repos (uses git diff) and non-git directories (hash-based snapshot).

Usage:
    # Start of session: take snapshot baseline
    python vault_drift_detect.py --path "src/" --project "ans" --mode snapshot

    # End of session: report undocumented changes
    python vault_drift_detect.py --path "src/" --project "ans" --mode report

    # Just list changed files without vault cross-reference
    python vault_drift_detect.py --path "src/" --project "ans" --mode status
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from vault_errors import wrap_main
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


from vault_io import VAULT_ROOT
SNAPSHOT_FILE = VAULT_ROOT / "00_System" / ".session-snapshot.json"

TRACK_EXTENSIONS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".cs", ".rb", ".php",
    ".sh", ".bash", ".ps1",
    ".html", ".css", ".vue", ".svelte",
    ".json", ".yaml", ".yml", ".toml", ".env",
    ".sql", ".graphql",
    ".md", ".mdx",
}

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", ".tox", "coverage", ".nyc_output", "target",
    "vendor", ".cache", "tmp", "temp", "logs", ".precommit_cache",
    "snapshots", "migrations", "fixtures", "__snapshots__",
}

# Extensions that never need vault documentation
SKIP_DOC_EXTENSIONS = {
    ".lock", ".log", ".map", ".min.js", ".min.css",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".whl", ".egg",
    ".pid", ".sock", ".db", ".sqlite", ".sqlite3",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".wav", ".zip", ".tar", ".gz", ".bz2",
    ".pdf", ".safetensors", ".gguf", ".onnx", ".pt", ".pth",
    ".pem", ".crt", ".key", ".pub", ".p12", ".pfx",
}

# Path fragments that indicate auto-generated or runtime files
SKIP_PATH_FRAGMENTS = {
    "archive_ca", "secrets/", ".precommit_cache", "data/run/",
    "data/models/", "data/backups/", "data/security/",
}

# Suggest which vault tool to use per file type
DOC_SUGGESTIONS = {
    "code": {"exts": {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs"}, "tool": "vault_code_module"},
    "config": {"exts": {".yaml", ".yml", ".toml", ".json", ".env"}, "tool": "vault_knowledge_save --category config"},
    "infra": {"exts": {".sh", ".bash", ".ps1"}, "tool": "vault_knowledge_save --category concept"},
    "query": {"exts": {".sql", ".graphql"}, "tool": "vault_knowledge_save --category concept"},
    "doc": {"exts": {".md", ".mdx"}, "tool": "vault_write"},
}


def slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


# ─── Git helpers ─────────────────────────────────────────────────────────────

def _has_git(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _git_head_commit(path: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _git_changed_since(path: Path, since_commit: Optional[str]) -> Dict[str, List[str]]:
    """
    Return files the agent worked on this session:
    1. Files committed since snapshot commit (git log since_commit..HEAD)
    2. Files with uncommitted changes vs HEAD (git diff HEAD — staged + unstaged)
    Untracked files are excluded: they pre-existed and were never worked on.
    """
    added, modified, deleted = [], [], []
    seen: Set[str] = set()

    try:
        # 1. Committed changes since snapshot
        if since_commit:
            log_cmd = ["git", "diff", "--name-status", f"{since_commit}...HEAD"]
            log_result = subprocess.run(log_cmd, cwd=str(path), capture_output=True, text=True, timeout=10)
            for line in log_result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) < 2:
                    continue
                status, filepath = parts[0][0], parts[1]
                if filepath in seen:
                    continue
                seen.add(filepath)
                if status == "A":
                    added.append(filepath)
                elif status == "M":
                    modified.append(filepath)
                elif status == "D":
                    deleted.append(filepath)
                elif status == "R" and "\t" in parts[1]:
                    old, new = parts[1].split("\t", 1)
                    if old not in seen:
                        deleted.append(old)
                        seen.add(old)
                    if new not in seen:
                        added.append(new)
                        seen.add(new)

        # 2. Uncommitted changes (staged + unstaged vs HEAD)
        diff_cmd = ["git", "diff", "--name-status", "HEAD"]
        diff_result = subprocess.run(diff_cmd, cwd=str(path), capture_output=True, text=True, timeout=10)
        for line in diff_result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            status, filepath = parts[0][0], parts[1]
            if filepath in seen:
                continue
            seen.add(filepath)
            if status == "A":
                added.append(filepath)
            elif status == "M":
                modified.append(filepath)
            elif status == "D":
                deleted.append(filepath)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {"added": added, "modified": modified, "deleted": deleted}


# ─── Hash-based snapshot helpers ─────────────────────────────────────────────

def _file_md5(path: Path) -> str:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _should_track(path: Path, exts: Set[str]) -> bool:
    if path.suffix not in exts:
        return False
    for part in path.parts:
        if part in IGNORE_DIRS:
            return False
    return True


def _scan_files(root: Path, exts: Set[str]) -> Dict[str, str]:
    """Return {relative_path: md5} for all trackable files under root."""
    result = {}
    try:
        for p in root.rglob("*"):
            if p.is_file() and _should_track(p.relative_to(root), exts):
                rel = str(p.relative_to(root)).replace("\\", "/")
                result[rel] = _file_md5(p)
    except (OSError, PermissionError):
        pass
    return result


def _hash_changed_since(root: Path, snapshot_files: Dict[str, str], exts: Set[str]) -> Dict[str, List[str]]:
    current = _scan_files(root, exts)
    snap_keys = set(snapshot_files.keys())
    cur_keys = set(current.keys())

    added = [f for f in cur_keys - snap_keys]
    deleted = [f for f in snap_keys - cur_keys]
    modified = [f for f in snap_keys & cur_keys if snapshot_files[f] != current[f]]

    return {"added": added, "modified": modified, "deleted": deleted}


# ─── Snapshot persistence ─────────────────────────────────────────────────────

def _load_snapshot(project: str) -> Optional[Dict[str, Any]]:
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Support per-project snapshots stored in a dict keyed by project
        if project in data:
            return data[project]
        # Legacy: single snapshot
        if data.get("project") == project:
            return data
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _save_snapshot(project: str, snapshot: Dict[str, Any]) -> None:
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Load existing multi-project file if present
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            all_snaps = json.load(f)
        if not isinstance(all_snaps, dict) or "project" in all_snaps:
            all_snaps = {}
    except (FileNotFoundError, json.JSONDecodeError):
        all_snaps = {}

    all_snaps[project] = snapshot

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_snaps, f, indent=2, ensure_ascii=False)


# ─── Vault cross-reference ────────────────────────────────────────────────────

def _load_code_index() -> List[Dict]:
    code_index_path = VAULT_ROOT / "11_Code" / ".code-index.json"
    try:
        with open(code_index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("modules", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_search_index() -> List[Dict]:
    search_index_path = VAULT_ROOT / "99_Index" / "search-index.json"
    try:
        with open(search_index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("notes", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        try:
            return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _find_coverage(
    changed_files: List[str],
    project: str,
    since_timestamp: str,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Cross-reference changed files against vault.
    Returns (documented, undocumented) lists.
    """
    modules = _load_code_index()
    notes = _load_search_index()
    since_dt = _parse_iso(since_timestamp)

    # Build lookup: file stem/path → vault entries
    # code-index: filePath field
    code_index_map: Dict[str, Dict] = {}
    for mod in modules:
        fp = mod.get("filePath", "")
        if fp:
            code_index_map[fp] = mod
            code_index_map[Path(fp).stem.lower()] = mod
            code_index_map[Path(fp).name.lower()] = mod

    # search-index: look for filename stem in note title or path
    def _note_covers_file(note: Dict, file_stem: str, file_name: str) -> bool:
        title = note.get("title", "").lower()
        path = note.get("path", "").lower()
        preview = note.get("preview", "").lower()
        return (
            file_stem in title
            or file_name in title
            or file_stem in path
            or file_stem in preview
        )

    documented = []
    undocumented = []

    for f in changed_files:
        fp = Path(f)
        stem = fp.stem.lower()
        name = fp.name.lower()

        # Skip files that don't need documentation
        if fp.suffix in SKIP_DOC_EXTENSIONS:
            continue
        if any(part in IGNORE_DIRS for part in fp.parts):
            continue
        if any(frag in f for frag in SKIP_PATH_FRAGMENTS):
            continue

        # Check code-index first (most precise)
        code_entry = code_index_map.get(f) or code_index_map.get(stem)
        if code_entry:
            entry_ts = code_entry.get("updatedAt", "")
            entry_dt = _parse_iso(entry_ts)
            is_recent = (since_dt is None or entry_dt is None or entry_dt >= since_dt)
            if is_recent:
                documented.append({
                    "file": f,
                    "vault_path": code_entry.get("relPath", "11_Code/"),
                    "source": "code-index",
                    "updatedAt": entry_ts,
                })
                continue

        # Check search-index
        matching_notes = [
            n for n in notes
            if _note_covers_file(n, stem, name)
        ]
        recent_notes = []
        if since_dt:
            recent_notes = [
                n for n in matching_notes
                if _parse_iso(n.get("updatedAt", "")) and _parse_iso(n.get("updatedAt", "")) >= since_dt
            ]
        else:
            recent_notes = matching_notes

        if recent_notes:
            best = recent_notes[0]
            documented.append({
                "file": f,
                "vault_path": best.get("path", ""),
                "source": "search-index",
                "updatedAt": best.get("updatedAt", ""),
            })
        else:
            # Determine suggestion
            suggestion = "vault_write"
            for group in DOC_SUGGESTIONS.values():
                if fp.suffix in group["exts"]:
                    suggestion = group["tool"]
                    break
            undocumented.append({
                "file": f,
                "suggestion": suggestion,
            })

    return documented, undocumented


# ─── Main tool function ───────────────────────────────────────────────────────

def vault_drift_detect(
    path: str,
    project: str,
    mode: str = "report",
    extensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    scan_path = Path(path).resolve()
    if not scan_path.exists():
        return {"ok": False, "error": f"Path not found: {path}"}

    exts = set(extensions) if extensions else TRACK_EXTENSIONS
    use_git = _has_git(scan_path)

    # ── SNAPSHOT mode ─────────────────────────────────────────────────────────
    if mode == "snapshot":
        now = _utcnow()
        snapshot: Dict[str, Any] = {
            "project": project,
            "path": str(scan_path),
            "timestamp": now,
            "git": use_git,
        }

        if use_git:
            commit = _git_head_commit(scan_path)
            snapshot["git_commit"] = commit
            snapshot["files"] = {}  # git tracks changes — no hash needed
        else:
            files = _scan_files(scan_path, exts)
            snapshot["git_commit"] = None
            snapshot["files"] = files

        _save_snapshot(project, snapshot)

        return {
            "ok": True,
            "mode": "snapshot",
            "project": project,
            "path": str(scan_path),
            "timestamp": now,
            "backend": "git" if use_git else "hash",
            "git_commit": snapshot.get("git_commit"),
            "files_tracked": len(snapshot.get("files", {})) if not use_git else "git-managed",
            "message": "Snapshot saved. Run with --mode report at end of session.",
        }

    # ── STATUS / REPORT mode ──────────────────────────────────────────────────
    snap = _load_snapshot(project)

    if snap is None and not use_git:
        return {
            "ok": False,
            "error": "No snapshot found and repo has no git. Run --mode snapshot first.",
            "hint": f"python vault_drift_detect.py --path \"{path}\" --project \"{project}\" --mode snapshot",
        }

    since_timestamp = snap["timestamp"] if snap else _utcnow()

    if use_git:
        since_commit = snap.get("git_commit") if snap else None
        changes = _git_changed_since(scan_path, since_commit)
        backend = "git"
    else:
        changes = _hash_changed_since(scan_path, snap.get("files", {}), exts)
        backend = "hash"

    all_changed = changes["added"] + changes["modified"]
    total_changed = len(all_changed) + len(changes["deleted"])

    if mode == "status":
        return {
            "ok": True,
            "mode": "status",
            "project": project,
            "backend": backend,
            "since": since_timestamp,
            "added": changes["added"],
            "modified": changes["modified"],
            "deleted": changes["deleted"],
            "total_changed": total_changed,
        }

    # mode == "report"
    documented, undocumented = _find_coverage(all_changed, project, since_timestamp)

    coverage_pct = (
        round(len(documented) / len(all_changed) * 100)
        if all_changed else 100
    )

    result: Dict[str, Any] = {
        "ok": True,
        "mode": "report",
        "project": project,
        "backend": backend,
        "since": since_timestamp,
        "summary": {
            "total_changed": total_changed,
            "added": len(changes["added"]),
            "modified": len(changes["modified"]),
            "deleted": len(changes["deleted"]),
            "documented": len(documented),
            "undocumented": len(undocumented),
            "coverage_pct": coverage_pct,
        },
        "documented": documented,
        "undocumented": undocumented,
        "deleted": changes["deleted"],
    }

    if undocumented:
        result["action_required"] = True
        result["message"] = (
            f"{len(undocumented)} file(s) changed without vault documentation. "
            f"Coverage: {coverage_pct}%."
        )
    else:
        result["action_required"] = False
        result["message"] = f"All {len(documented)} changed file(s) are documented. Coverage: 100%."

    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Vault Drift Detect Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_drift_detect.py --path "src/" --project "ans" --mode snapshot
  python vault_drift_detect.py --path "src/" --project "ans" --mode report
  python vault_drift_detect.py --path "src/" --project "ans" --mode status
  python vault_drift_detect.py --path "C:/repos/mi-api" --project "mi-api" --mode snapshot --extensions .py .js .ts

Notas:
  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script
  - Flujo: tomar snapshot al inicio -> report al final de sesion
  - Soporta repos git (usa git diff) y directorios sin git (hash-based)
  - mode=report cruza cambios con el vault para detectar que no fue documentado
""",
    )
    parser.add_argument("--path", required=True, help="Project root path to scan")
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument(
        "--mode",
        choices=["snapshot", "status", "report"],
        default="report",
        help="snapshot: save baseline | status: list changes | report: changes + vault coverage",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        help="File extensions to track (e.g. .py .js .ts). Default: all code/config extensions.",
    )

    args = parser.parse_args()
    result = vault_drift_detect(args.path, args.project, args.mode, args.extensions)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_drift_detect"))
