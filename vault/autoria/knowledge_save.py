"""Entry module instalado para ``vault_knowledge_save``."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional, Sequence
from vault.kernel.proyectos import proyecto_registrado
from .conocimiento import CATEGORIES, guardar_conocimiento

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="vault_knowledge_save")
    # `--project` resuelve contra el registro del vault de `--root`, que
    # puede venir detrás en el argv: se lee antes, sin consumir nada.
    previo = argparse.ArgumentParser(add_help=False)
    previo.add_argument("--root")
    raiz = previo.parse_known_args(argv)[0].root
    parser.add_argument("--root", required=True)
    parser.add_argument("--category", required=True, choices=CATEGORIES)
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--project", type=proyecto_registrado("vault_knowledge_save", lambda: Path(raiz)))
    parser.add_argument("--tags", nargs="*")
    parser.add_argument("--related", nargs="*")
    args = parser.parse_args(argv)
    result = guardar_conocimiento(args.root, args.category, args.title, args.content,
                                  args.project, args.tags, args.related)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
