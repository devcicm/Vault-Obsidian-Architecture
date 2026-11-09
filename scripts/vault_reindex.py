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

from vault_errors import presupuesto_de_vault, TOOL_TIMEOUT_SECONDS, wrap_main
from vault_fs import file_lock
from vault_lib import parse_frontmatter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.indices.coherencia import coherencia_indice  # noqa: E402
from vault.indices.enumeracion import notas_en_disco  # noqa: E402
from vault.indices.reconstruccion import ServicioReindex  # noqa: E402
from vault.indices.repositorio import RepositorioIndices  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.errores import completar_envelope  # noqa: E402


def _repo(root=None) -> RepositorioIndices:
    return RepositorioIndices(construir(root))


def notas_indexables(root=None) -> List[Path]:
    """Las notas que la reconstrucción indexaría, con SU mismo criterio.

    Nombre público desde v40.9: `vault_sanacion` la llamaba por el nombre
    privado, que es una frontera cruzada por detrás. No se llama
    `notas_en_disco` porque ese nombre ya lo ocupa la función del dominio que
    este módulo importa, y dos cosas distintas con el mismo nombre en el mismo
    fichero es la confusión que sigue. El criterio no vive aquí sino en el
    dominio.
    """
    repo = _repo(root)
    return notas_en_disco(repo.raiz, repo.ctx.secciones.ordenadas())


#: superseded_by: `notas_indexables`. Se conserva el nombre —hubo tests y tools
#: que lo importaban— con el mismo contrato (no-derogación). Hasta v41.3 el
#: cuerpo vivía aquí y el nombre público delegaba en el privado.
def _notas_en_disco(root=None) -> List[Path]:
    return notas_indexables(root)


def index_coherence(root=None) -> Dict[str, Any]:
    """Contrasta search-index.json y graph.json contra lo que hay en disco.

    Es la mitad detectora de **AP-47**: el vault es la fuente de verdad y los
    dos índices son proyecciones suyas, así que la única forma de saber que una
    proyección se quedó atrás es contrastarla contra el disco y no contra la
    escritura que la generó. La mitad aplicadora es `vault_reindex()`, que la
    regenera; separadas porque detectar el desfase y repararlo no son la misma
    operación y no siempre se piden juntas.
    """
    return coherencia_indice(_repo(root))


def _check_index(root=None) -> bool:
    """True si el índice refleja el disco. Ver `index_coherence()`."""
    return bool(index_coherence(root)["ok"])


def vault_reindex(
    dry_run: bool = False, rebuild_graph: bool = False, root=None
) -> Dict[str, Any]:
    repo = _repo(root)

    # Los índices de sección y el maestro se rehacen para que la navegación no
    # quede apuntando a lo anterior. Va en el adaptador y no en el dominio
    # porque es orquestación entre tools, no una regla del contexto.
    # Van ANTES de la búsqueda y del grafo (AP-47, medido el 2026-10-07): son
    # notas, y un `index.md` que faltaba se escribía después de construir
    # search-index.json y quedaba sin indexar hasta una segunda pasada.
    navegacion: Dict[str, Any] = {}
    if not dry_run:
        try:
            from vault_master_index import vault_master_index
            from vault_section_index import vault_section_index

            for section in repo.ctx.secciones.ordenadas():
                if section not in ("00_System", "99_Index"):
                    vault_section_index(section)
            vault_master_index()
            navegacion["indexes_rebuilt"] = True
        except Exception as e:
            navegacion["index_warning"] = str(e)

    lock_target = repo.indice_busqueda
    with file_lock(lock_target, timeout=30.0):
        result = ServicioReindex(repo, parse_frontmatter).reconstruir(dry_run=dry_run)

    if rebuild_graph and not dry_run:
        result["graph"] = _rehacer_grafo()

    # Los temporales que dejó una ejecución muerta (hallazgo 4.2 del paper de
    # la re-auditoría): el fichero destino quedó intacto —la escritura es
    # temporal→rename—, pero el temporal se quedó en su carpeta. Se recogen
    # solo los que se pueden demostrar nuestros: nombre con nuestra forma y
    # proceso muerto.
    try:
        from vault.kernel.escritura import limpiar_temporales

        result["temporales"] = limpiar_temporales(repo.raiz, dry_run=dry_run)
    except Exception as e:
        result["temporales"] = {"warning": str(e)[:160]}

    result.update(navegacion)
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

        import vault_subproceso

        proc = vault_subproceso.ejecutar(
            [sys.executable, str(graph_script)],
            capture_output=True, timeout=60,
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
        allow_abbrev=False,
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

    parser.add_argument(
        "--check-indices",
        dest="check_indices",
        action="store_true",
        help="Exit 0 si cada entrada de los índices de dominio (.bugs-index.json, "
             ".code-index.json…) apunta a una nota que existe, 1 si alguna no",
    )

    args = parser.parse_args()

    if args.check_indices:
        # Los índices de dominio son otra capa: los escribe cada `*_save` y
        # los reescribe `vault_move`/`vault_delete` (el dueño:
        # `vault_io.actualizar_indices_de_dominio`). Antes nadie los leía, así
        # que una entrada que apuntaba a una nota ya renombrada era invisible
        # (nota de causa raíz «vault_move does not update per-domain
        # indexes», 2026-10-30). La comprobación la hace el mismo dueño.
        from vault_io import verificar_indices_de_dominio

        informe = verificar_indices_de_dominio()
        informe["tool"] = "vault_reindex"
        informe["action"] = "python vault_reindex.py --check-indices"
        if not informe["ok"]:
            informe["error_code"] = "INDEX_STALE"
            informe["message"] = (
                f"{len(informe['rotas'])} entrada(s) de índices de dominio "
                f"apuntan a notas que no existen; "
                f"{len(informe['ilegibles'])} índice(s) ilegibles.")
        else:
            informe["message"] = (
                f"{informe['revisados']} entrada(s) de índices de dominio: "
                f"todas resuelven.")
        informe = completar_envelope("vault_reindex", informe)
        print(json.dumps(informe, indent=2, ensure_ascii=False))
        return 0 if informe["ok"] else 1

    if args.check:
        informe = index_coherence()
        informe["tool"] = "vault_reindex"
        if not informe["ok"]:
            informe["action"] = "python vault_reindex.py"
            # AP-52: la medida se conserva entera; el código es por lo que
            # decide el agente (`action` es texto para una persona).
            # Ausente, corrupto o desfasado: los tres los rehace la
            # reconstrucción, que es derivada del disco.
            informe["error_code"] = (
                "INDEX_NOT_FOUND" if informe["status"] == "index_missing"
                else "INDEX_STALE")
            informe["message"] = (
                f"Índice {informe['status']}: {informe['on_disk']} nota(s) en disco, "
                f"{informe['indexed']} indexada(s).")
            informe = completar_envelope("vault_reindex", informe)
        print(json.dumps(informe, indent=2, ensure_ascii=False))
        return 0 if informe["ok"] else 1

    result = vault_reindex(dry_run=args.dry_run, rebuild_graph=args.graph)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    # Recorre el vault entero: medido el 2026-10-05, 612 notas tardan ~56 s y
    # el límite por defecto (60 s) la cortaba a mitad de escritura, dejando
    # el índice a medias y un lock que no caduca hasta 120 s después. Mismo
    # criterio que vault_smoke; un VAULT_TOOL_TIMEOUT mayor sigue mandando.
    sys.exit(wrap_main(main, "vault_reindex", timeout=presupuesto_de_vault()))
