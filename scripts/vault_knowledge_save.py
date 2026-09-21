#!/usr/bin/env python3
"""Adaptador histórico de ``vault_knowledge_save``.

La semántica de conocimiento vive en ``vault.autoria.conocimiento``. Este
archivo conserva detección de raíz, ledger e índices del modo checkout; no es
una dependencia de la operación instalada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vault.autoria.conocimiento import CATEGORIES, guardar_conocimiento
from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_text, get_vault_root, write_report


def vault_knowledge_save(category: str, title: str, content: str,
                         project: Optional[str] = None, tags: Optional[List[str]] = None,
                         related: Optional[List[str]] = None) -> Dict[str, Any]:
    return guardar_conocimiento(
        get_vault_root(), category, title, content, project, tags, related,
        writer=atomic_write_text, report=write_report,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault Knowledge Save Tool")
    parser.add_argument("--category", required=True, choices=CATEGORIES)
    parser.add_argument("--title")
    parser.add_argument("--content")
    parser.add_argument("--project")
    parser.add_argument("--tags", nargs="*")
    parser.add_argument("--related", nargs="*")
    parser.add_argument("--scan-path")
    args = parser.parse_args()
    if args.scan_path:
        source = Path(args.scan_path)
        if not source.exists():
            print(json.dumps(
                emit_error("vault_knowledge_save", "FOLDER_NOT_FOUND", f"scan-path not found: {args.scan_path}"),
                ensure_ascii=False,
            ))
            return 1
        saved, skipped = [], []
        for path in list(source.rglob("*.md")) + list(source.rglob("*.txt")):
            try:
                result = vault_knowledge_save(args.category, path.stem.replace("-", " ").title(),
                                               path.read_text(encoding="utf-8"), args.project,
                                               args.tags, args.related)
            except OSError as exc:
                skipped.append({"file": str(path), "reason": str(exc)})
                continue
            if result.get("ok"):
                saved.append(result["path"])
            else:
                skipped.append({"file": str(path), "reason": result.get("message", "unknown")})
        print(json.dumps({"ok": True, "scanned": len(saved) + len(skipped), "saved": saved,
                          "skipped": skipped}, ensure_ascii=False))
        return 0
    if not args.title or not args.content:
        parser.error("--title y --content son requeridos sin --scan-path")
    result = vault_knowledge_save(args.category, args.title, args.content, args.project,
                                  args.tags, args.related)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(wrap_main(main, "vault_knowledge_save"))
