"""Entry module instalado para ``vault_knowledge_get``."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional, Sequence
from vault.kernel.proyectos import proyecto_registrado
from .conocimiento import recuperar_conocimiento

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="vault_knowledge_get", allow_abbrev=False)
    # `--project` resuelve contra el registro del vault de `--root`, que
    # puede venir detrás en el argv: se lee antes, sin consumir nada.
    previo = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    previo.add_argument("--root")
    raiz = previo.parse_known_args(argv)[0].root
    parser.add_argument("--root", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--category")
    parser.add_argument("--project", type=proyecto_registrado("vault_knowledge_get", lambda: Path(raiz)))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    result = recuperar_conocimiento(args.root, args.query, args.category, args.project, args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
