#!/usr/bin/env python3
"""
vault_code_sync.py — Audita y repara la trazabilidad bidireccional código ↔ vault.

Para cada nota en 11_Code/{project}/ con frontmatter source_file:
  complete       → archivo fuente existe + tiene @vault: apuntando a la nota
  missing_tag    → archivo fuente existe pero no tiene @vault:
  missing_file   → nota dice source_file: X pero X no existe en disco
  no_source_ref  → nota en 11_Code/ sin frontmatter source_file (no checkable)

Para cada archivo fuente con @vault: tag:
  orphan_vault_ref → @vault: apunta a una nota que no existe en el vault

Con --fix: inyecta @vault: en todos los archivos "missing_tag" automáticamente.

Usage:
    python vault_code_sync.py --project my-api
    python vault_code_sync.py --project my-api --fix
    python vault_code_sync.py --project my-api --fix --dry-run
    python vault_code_sync.py                         # todos los proyectos
    python vault_code_sync.py --scan-dir src/         # audita archivos fuente en dir

Con el repo enlazado (`vault_project --link`), `--project` basta: un
`source_file` relativo se resuelve contra el repo y la pasada de huérfanas lo
recorre entero. Si la trazabilidad sale limpia y no es `--dry-run`, anota el
HEAD como `repo.synced_commit` en la ficha (AP-63, P4).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_io import atomic_write_text, write_report, resolve_input_path
from vault_lib import utcnow
import vault_subproceso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.grafo.enlace_codigo import link_vault  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _code_dir() -> Path:
    return _repo().dir_codigo


def _code_index() -> Path:
    return _repo().indice_codigo


# Extensions considered source code (auditable for @vault: tags)
_CODE_EXTS = frozenset(
    {
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".py",
        ".cs",
        ".java",
        ".go",
        ".rs",
        ".cpp",
        ".c",
        ".h",
        ".kt",
        ".swift",
        ".rb",
        ".php",
        ".dart",
        ".scala",
        ".sh",
        ".bash",
        ".r",
    }
)

_VAULT_TAG_PATTERN = re.compile(
    r"^(?://|#|<!--|/\*|--)\s*@vault:\s*(\S+)\s*[—\-]+",
    re.MULTILINE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

from vault_lib import parse_frontmatter


def _vault_ref_in_file(file_path: Path) -> Optional[str]:
    """Return the @vault: note path found in a source file, or None."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        m = _VAULT_TAG_PATTERN.search(content)
        return m.group(1).strip() if m else None
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        emit_error("vault_code_sync", "FILE_READ_ERROR", str(exc))
        return None


def _collect_code_notes(project: Optional[str]) -> List[Tuple[Path, Dict[str, str]]]:
    """Collect all vault notes in 11_Code/ (optionally filtered by project)."""
    root = _code_dir() / project if project else _code_dir()
    if not root.exists():
        return []
    notes = []
    for p in root.rglob("*.md"):
        if p.name == "index.md":
            continue
        try:
            meta = parse_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
            notes.append((p, meta))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
    return notes


# ──────────────────────────────────────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────────────────────────────────────


def _head(repo: Path) -> Optional[str]:
    try:
        r = vault_subproceso.ejecutar(["git", "rev-parse", "HEAD"], cwd=str(repo),
                                      capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def vault_code_sync(
    project: Optional[str] = None,
    scan_dir: Optional[str] = None,
    fix: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Audit bidirectional traceability between vault notes and source files.

    Returns:
      {
        "ok": true,
        "summary": { complete, missing_tag, missing_file, no_source_ref, orphan_vault_refs },
        "complete":       [ {note, source_file} ],
        "missing_tag":    [ {note, source_file, fix_applied} ],
        "missing_file":   [ {note, source_file_declared} ],
        "no_source_ref":  [ {note} ],
        "orphan_vault_refs": [ {source_file, vault_ref_declared} ],
        "fixed":          int,
        "dry_run":        bool,
      }
    """
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    repo = _proyectos.ruta_local(_raiz(), project) if project else None
    if repo is not None and not repo.is_dir():
        repo = None
    complete: List[Dict] = []
    missing_tag: List[Dict] = []
    missing_file: List[Dict] = []
    no_source_ref: List[Dict] = []
    orphan_vault_refs: List[Dict] = []
    fixed = 0

    # ── Pass 1: vault notes → source files ───────────────────────────────────
    notes = _collect_code_notes(project)
    for note_path, meta in notes:
        note_rel = str(note_path.relative_to(_raiz())).replace("\\", "/")
        note_ref = note_rel.removesuffix(".md")

        source_file_str = meta.get("file_path") or meta.get("source_file") or ""
        if not source_file_str:
            no_source_ref.append({"note": note_rel})
            continue

        source_path = resolve_input_path(source_file_str)
        if repo is not None and not Path(source_file_str).is_absolute():
            en_repo = repo / source_file_str
            if en_repo.exists() or not source_path.exists():
                source_path = en_repo

        if not source_path.exists():
            missing_file.append(
                {
                    "note": note_rel,
                    "source_file_declared": source_file_str,
                }
            )
            continue

        existing_ref = _vault_ref_in_file(source_path)

        if existing_ref and existing_ref == note_ref:
            complete.append({"note": note_rel, "source_file": source_file_str})
            continue

        # Missing or mismatched @vault: tag
        fix_applied = False
        if fix and not dry_run:
            try:
                title = meta.get("title", note_path.stem)
                iso_type = meta.get("iso_type", "module")
                tag_title = f"{Path(source_file_str).name} ({iso_type})"
                tag_result = link_vault(
                    note_ref, str(source_path), tag_title, report=write_report
                )
                fix_applied = tag_result.get("ok", False)
                if fix_applied:
                    fixed += 1
            except Exception as exc:
                emit_error("vault_code_sync", "TAG_FIX_ERROR",
                          f"{note_rel}: {exc}")

        missing_tag.append(
            {
                "note": note_rel,
                "source_file": source_file_str,
                "existing_vault_ref": existing_ref,
                "fix_applied": fix_applied,
            }
        )

    # ── Pass 2: scan source files for orphan @vault: refs ────────────────────
    scan_roots: List[Path] = []
    if scan_dir:
        d = Path(scan_dir)
        if d.exists():
            scan_roots.append(d)
    elif repo is not None:
        scan_roots.append(repo)
    else:
        # Derive likely project source root from code index
        try:
            if _code_index().exists():
                index = json.loads(_code_index().read_text(encoding="utf-8"))
                for mod in index.get("modules", []):
                    if project and not es_del(mod.get("project")):
                        continue
                    fp = Path(mod.get("filePath", ""))
                    if fp.is_absolute() and fp.parent.exists():
                        root = fp.parent
                        while root.parent != root and root not in scan_roots:
                            if any(
                                r.is_relative_to(root) or root.is_relative_to(r)
                                for r in scan_roots
                            ):
                                break
                            scan_roots.append(root)
                            break
        except Exception as exc:
            emit_error("vault_code_sync", "SCAN_ROOT_ERROR", str(exc))

    all_note_refs = {
        str(p.relative_to(_raiz())).replace("\\", "/").removesuffix(".md")
        for p, _ in notes
    }

    for scan_root in scan_roots:
        for src_file in scan_root.rglob("*"):
            if src_file.suffix.lower() not in _CODE_EXTS:
                continue
            ref = _vault_ref_in_file(src_file)
            if ref and ref not in all_note_refs:
                orphan_vault_refs.append(
                    {
                        "source_file": str(src_file),
                        "vault_ref_declared": ref,
                        "note": f"Vault note {ref}.md not found in {_code_dir().name}/",
                    }
                )

    summary = {
        "total_notes_checked": len(notes),
        "complete": len(complete),
        "missing_tag": len(missing_tag),
        "missing_file": len(missing_file),
        "no_source_ref": len(no_source_ref),
        "orphan_vault_refs": len(orphan_vault_refs),
        "fix_applied": fixed,
    }

    status = (
        "clean"
        if not missing_tag and not missing_file and not orphan_vault_refs
        else "gaps_found"
    )

    synced = None
    if status == "clean" and complete and repo is not None and not dry_run:
        head = _head(repo)
        if head:
            ficha = _proyectos.anotar_repo(_raiz(), project, atomic_write_text, synced_commit=head,
                                           synced_at=utcnow()[:10])
            synced = {"commit": head, "ficha": ficha} if ficha else None

    return {
        "ok": True,
        **write_report(),
        "status": status,
        "project": project or "all",
        "repo_linked": repo is not None,
        "synced_commit_recorded": synced,
        "dry_run": dry_run,
        "summary": summary,
        "complete": complete,
        "missing_tag": missing_tag,
        "missing_file": missing_file,
        "no_source_ref": no_source_ref,
        "orphan_vault_refs": orphan_vault_refs,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Human-readable report
# ──────────────────────────────────────────────────────────────────────────────


def _print_report(result: Dict[str, Any]) -> None:
    s = result["summary"]
    proj = result["project"]
    prefix = "[DRY-RUN] " if result.get("dry_run") else ""

    print(f"\n{prefix}=== vault_code_sync — proyecto: {proj} ===")
    print(
        f"  Notas revisadas : {s['total_notes_checked']}\n"
        f"  Completo        : {s['complete']}  (nota + @vault: alineados)\n"
        f"  Sin @vault:     : {s['missing_tag']}  (archivo fuente sin tag)\n"
        f"  Archivo ausente : {s['missing_file']}  (source_file no existe en disco)\n"
        f"  Sin source_file : {s['no_source_ref']}  (nota sin frontmatter source_file)\n"
        f"  Refs huérfanas  : {s['orphan_vault_refs']}  (@vault: apunta a nota inexistente)\n"
        f"  Fixes aplicados : {s['fix_applied']}"
    )

    if result["missing_tag"]:
        print("\n  Sin @vault: (pendiente de linkar):")
        for e in result["missing_tag"]:
            tick = "✓ fixed" if e.get("fix_applied") else "✗"
            print(f"    {tick}  {e['source_file']}")
            print(f"         → vault: {e['note']}")

    if result["missing_file"]:
        print("\n  Archivos fuente no encontrados:")
        for e in result["missing_file"]:
            print(f"    ✗  {e['source_file_declared']}")
            print(f"       declarado en: {e['note']}")

    if result["orphan_vault_refs"]:
        print("\n  Referencias @vault: huérfanas (nota ya no existe):")
        for e in result["orphan_vault_refs"]:
            print(f"    ✗  {e['source_file']}")
            print(f"       @vault: {e['vault_ref_declared']}")

    status_label = "CLEAN" if result["status"] == "clean" else "GAPS FOUND"
    print(f"\n  Estado: {status_label}\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_code_sync — audita trazabilidad bidireccional código ↔ vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Estados posibles por nota:
  complete       → archivo fuente existe y tiene @vault: correcto
  missing_tag    → archivo fuente existe pero le falta el @vault:
  missing_file   → la nota declara source_file pero el archivo no está en disco
  no_source_ref  → nota sin frontmatter source_file (no auditada)
  orphan_vault   → archivo fuente tiene @vault: a nota que ya no existe

Ejemplos:
  python vault_code_sync.py --project my-api
  python vault_code_sync.py --project my-api --report
  python vault_code_sync.py --project my-api --fix --dry-run
  python vault_code_sync.py --project my-api --fix
  python vault_code_sync.py --scan-dir src/
""",
        allow_abbrev=False,
    )
    parser.add_argument("--project", type=proyecto_registrado("vault_code_sync"), help="Slug del proyecto (omitir = todos)")
    parser.add_argument(
        "--scan-dir", help="Directorio de código fuente a escanear para refs huérfanas"
    )
    parser.add_argument(
        "--fix", action="store_true", help="Inyectar @vault: en archivos sin tag"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué se haría sin modificar archivos",
    )
    parser.add_argument(
        "--report", action="store_true", help="Salida human-readable en lugar de JSON"
    )

    args = parser.parse_args()

    result = vault_code_sync(
        project=args.project,
        scan_dir=args.scan_dir,
        fix=args.fix,
        dry_run=args.dry_run,
    )

    if args.report:
        _print_report(result)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_sync"))
