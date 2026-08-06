#!/usr/bin/env python3
"""vault_quarantine — adaptador de transporte del contexto Durabilidad.

Retener sin borrar (`20_Quarantine/`). Este fichero ya no decide nada: las tres
propiedades que hacen segura la cuarentena —la nota se mueve y no se copia, el
origen se guarda siempre, la razón es obligatoria— son invariantes de
`vault/durabilidad/cuarentena.py`, donde se prueban sin CLI.

Medido sobre 17 vaults reales, lo que pasa cuando no hay cuarentena es que las
notas sin destino se quedan donde cayeron: 855 sin frontmatter, y carpetas
inventadas sobre la marcha (`docs/`, `scripts/`) para lo que no encajaba.

Usage:
    python vault_quarantine.py --add "07_Knowledge/nota-rara.md" \\
        --reason "Sin frontmatter y origen desconocido" --category unclassified

    python vault_quarantine.py --list
    python vault_quarantine.py --restore "20_Quarantine/unclassified/nota-rara.md"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from vault_errors import wrap_main
from vault_io import write_report
from vault_lib import parse_frontmatter_with_body

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.durabilidad.cuarentena import CATEGORIAS, ServicioCuarentena  # noqa: E402
from vault.kernel import construir  # noqa: E402

#: Se reexporta con el nombre viejo: estaba publicado y hay quien lo importa.
CATEGORIES = CATEGORIAS


def _servicio(root=None) -> ServicioCuarentena:
    """El parser de frontmatter se inyecta: es del kernel, no del dominio."""
    return ServicioCuarentena(construir(root), parse_frontmatter_with_body)


def vault_quarantine_add(
    path: str,
    reason: str,
    category: str = "unclassified",
    agent: Optional[str] = None,
    root=None,
) -> Dict[str, Any]:
    agent = agent or os.environ.get("VAULT_AGENT", "")
    resultado = _servicio(root).retener(path, reason, category, agent)
    if "ok" in resultado:
        return resultado
    return {"ok": True, **write_report(), **resultado}


def vault_quarantine_restore(
    path: str, agent: Optional[str] = None, root=None
) -> Dict[str, Any]:
    agent = agent or os.environ.get("VAULT_AGENT", "")
    resultado = _servicio(root).devolver(path, agent)
    if "ok" in resultado:
        return resultado
    return {"ok": True, **write_report(), **resultado}


def vault_quarantine_list(
    category: Optional[str] = None, root=None
) -> Dict[str, Any]:
    return _servicio(root).listar(category)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_quarantine — retener notas sin destino seguro, sin borrarlas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python vault_quarantine.py --add "07_Knowledge/rara.md" \\
      --reason "Sin frontmatter y origen desconocido" --category unclassified

  python vault_quarantine.py --list --category suspicious
  python vault_quarantine.py --restore "20_Quarantine/unclassified/rara.md"

Notas:
  - category: unclassified | suspicious | duplicates
  - la nota se MUEVE (no se copia): dos copias de una nota dudosa es peor que una
  - el origen viaja dentro de la nota y en el ledger append-only
""",
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--add", metavar="PATH", help="Retener esta nota")
    grupo.add_argument("--restore", metavar="PATH", help="Devolver la nota a su origen")
    grupo.add_argument("--list", action="store_true", help="Listar lo retenido")

    parser.add_argument("--reason", help="Por qué se retiene (obligatorio con --add)")
    # Sin default: con uno, `--list` filtraría siempre por esa categoría y
    # ocultaría el resto de la cuarentena sin que nadie lo pidiera.
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--agent", help="Agente que actúa (AP-16)")

    args = parser.parse_args()

    if args.add:
        result = vault_quarantine_add(
            args.add, args.reason or "", args.category or "unclassified", args.agent
        )
    elif args.restore:
        result = vault_quarantine_restore(args.restore, args.agent)
    else:
        result = vault_quarantine_list(args.category)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_quarantine"))
