#!/usr/bin/env python3

"""
Vault Reindex — adaptador de transporte del contexto Índices.

Reconstruye `99_Index/search-index.json` (y opcionalmente `graph.json`) desde las
notas que hay en disco. Se usa cuando el índice está vacío, corrupto o ausente.

Es la tool de recuperación obligatoria para vaults gestionados por LLMs remotos
(DeepSeek, GPT, Gemini, Claude API) o cualquier harness que no llame a
`vault_write` en cada escritura. Ejecutarla al inicio de sesión siempre que
`vault_search` devuelva 0 resultados.

Desde v40.0 la reconstrucción y la comprobación de coherencia viven en
`vault/indices/`: comparten enumerador, así que `--check` no puede medir una
cosa y la reconstrucción arreglar otra (AP-44).

Usage:

    python vault_reindex.py              # rebuild search-index only
    python vault_reindex.py --graph      # also rebuild graph.json
    python vault_reindex.py --dry-run    # show what would be indexed without writing
    python vault_reindex.py --check      # exit 0 si refleja el disco, 1 si hay desfase
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from vault_errors import wrap_main
from vault_lib import parse_frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.indices.coherencia import coherencia_indice  # noqa: E402
from vault.indices.enumeracion import notas_en_disco  # noqa: E402
from vault.indices.reconstruccion import ServicioReindex  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _repo(root=None) -> RepositorioIndices:
    return RepositorioIndices(construir(root))


def _notas_en_disco(root=None) -> List[Path]:
    """Las notas que la reconstrucción indexaría, con SU mismo criterio.

    Se conserva el nombre porque hay tests y tools que lo importan
    (no-derogación); el criterio ya no vive aquí sino en el dominio.
    """
    repo = _repo(root)
    return notas_en_disco(repo.raiz, repo.ctx.secciones.ordenadas())


def notas_indexables(root=None) -> List[Path]:
    """Las notas que la reconstrucción indexaría. Nombre público desde v40.9.

    `vault_sanacion` la llamaba por el nombre privado, que es una frontera
    cruzada por detrás. No se llama `notas_en_disco` porque ese nombre ya lo
    ocupa la función del dominio que este módulo importa, y dos cosas distintas
    con el mismo nombre en el mismo fichero es la confusión que sigue.
    """
    return _notas_en_disco(root)


def index_coherence(root=None) -> Dict[str, Any]:
    """Contrasta search-index.json y graph.json contra lo que hay en disco."""
    return coherencia_indice(_repo(root))


def _check_index(root=None) -> bool:
    """True si el índice refleja el disco. Ver `index_coherence()`."""
    return bool(index_coherence(root)["ok"])


def vault_reindex(
    dry_run: bool = False, rebuild_graph: bool = False, root=None
) -> Dict[str, Any]:
    repo = _repo(root)
    result = ServicioReindex(repo, parse_frontmatter).reconstruir(dry_run=dry_run)

    if rebuild_graph and not dry_run:
        result["graph"] = _rehacer_grafo()

    # Los índices de sección y el maestro se rehacen para que la navegación no
    # quede apuntando a lo anterior. Va en el adaptador y no en el dominio
    # porque es orquestación entre tools, no una regla del contexto.
    if not dry_run:
        try:
            from vault_master_index import vault_master_index
            from vault_section_index import vault_section_index

            for section in repo.ctx.secciones.ordenadas():
                if section not in ("00_System", "99_Index"):
                    vault_section_index(section)
            vault_master_index()
            result["indexes_rebuilt"] = True
        except Exception as e:
            result["index_warning"] = str(e)

    return result


def _rehacer_grafo() -> Dict[str, Any]:
    """Delega en `vault_graph` por subproceso, tal como estaba.

    El grafo es del contexto Grafo, no de éste. Llamarlo por proceso mantiene la
    frontera mientras ese contexto no esté migrado, y el error se reporta en vez
    de tragarse.
    """
    try:
        graph_script = Path(__file__).parent / "vault_graph.py"
        if not graph_script.exists():
            return {"error": "vault_graph.py no encontrado"}

        import subprocess

        proc = subprocess.run(
            [sys.executable, str(graph_script)],
            capture_output=True, text=True, timeout=60,
        )
        datos = json.loads(proc.stdout) if proc.stdout else {}
        return datos.get("stats", {"error": proc.stderr[:200]})
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Reindex -- rebuild search-index.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_reindex.py

  python vault_reindex.py --graph

  python vault_reindex.py --dry-run

  python vault_reindex.py --check

Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Usar al inicio de sesion si vault_search retorna 0 resultados

  - --check retorna exit 0 si el indice REFLEJA el disco, exit 1 si hay desfase

""",
    )

    parser.add_argument("--graph", action="store_true", help="Also rebuild graph.json")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without writing",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 si el índice refleja el disco, 1 si hay desfase",
    )

    args = parser.parse_args()

    if args.check:
        informe = index_coherence()
        informe["tool"] = "vault_reindex"
        if not informe["ok"]:
            informe["action"] = "python vault_reindex.py"
        print(json.dumps(informe, indent=2, ensure_ascii=False))
        return 0 if informe["ok"] else 1

    result = vault_reindex(dry_run=args.dry_run, rebuild_graph=args.graph)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_reindex"))
