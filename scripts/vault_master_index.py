#!/usr/bin/env python3

"""
Vault Master Index — adaptador de transporte del contexto Índices.

Genera `99_Index/index.md`, el índice maestro del vault: una fila por sección
con su conteo de notas y el enlace a su índice. Desde v40.0 la composición vive
en `vault/indices/maestro.py`; aquí solo se parsea argv y se imprime el envelope.

La indexación de cada sección se **inyecta** (`vault_section_index`) en vez de
importarse dentro del dominio: el maestro no sabe indexar una sección, y eso es
intencionado — si supiera, habría dos implementaciones de lo mismo (AP-48).

Usage:
    python vault_master_index.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from vault_errors import wrap_main
from vault_io import write_report
from vault_registry import section_description

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.indices.maestro import ServicioIndiceMaestro  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402


def vault_master_index(root=None) -> Dict[str, Any]:
    """Genera `99_Index/index.md` como índice maestro del vault.

    Returns:
        {"ok": True, "path": "99_Index/index.md", "sectionsTotal": 22, "notesTotal": 108}
    """
    from vault_section_index import vault_section_index

    servicio = ServicioIndiceMaestro(
        RepositorioIndices(construir(root)),
        indexar_seccion=lambda s: vault_section_index(s, include_subdirs=True),
        describir_seccion=section_description,
    )
    return {"ok": True, **write_report(), **servicio.generar()}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Vault Master Index -- Generate 99_Index/index.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  python vault_master_index.py

Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Llama a vault_section_index para cada seccion declarada en vault_registry

  - Genera 99_Index/index.md con tabla resumen de todo el vault

""",
    )

    parser.parse_args()

    result = vault_master_index()

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_master_index"))
