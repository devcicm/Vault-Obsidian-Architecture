#!/usr/bin/env python3
"""Adaptador histórico de ``vault_knowledge_get`` hacia Autoría estable."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vault.autoria.conocimiento import recuperar_conocimiento
from vault_errors import wrap_main
from vault_io import get_vault_root


def vault_knowledge_get(query: str, category: Optional[str] = None,
                        project: Optional[str] = None) -> Dict[str, Any]:
    return recuperar_conocimiento(get_vault_root(), query, category, project)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault Knowledge Get Tool")
    parser.add_argument("--query", required=True)
    parser.add_argument("--category")
    parser.add_argument("--project")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    result = recuperar_conocimiento(get_vault_root(), args.query, args.category,
                                    args.project, args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(wrap_main(main, "vault_knowledge_get"))
