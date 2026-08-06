"""¿Refleja el índice lo que hay en disco? (AP-47)

Se conserva palabra por palabra el criterio de v39: lo que había antes era
`len(notes) > 0`, y un índice con UNA entrada sobre un vault de 300 notas
devolvía `index_ok` — una puerta que no medía lo que decía medir, y justo en la
tool cuya única razón de existir es reconciliar.

Las dos direcciones se reportan por separado porque significan cosas distintas:
`missing_in_index` son notas invisibles para `vault_search` —el agente no sabe
que existen— y `stale_in_index` son entradas que apuntan a ficheros que ya no
están: el agente las encuentra y luego no puede abrirlas.

El grafo se compara aparte y **no** decide el veredicto: se regenera solo con
`--graph`, y contarlo como fallo convertiría el check en ruido en todo vault que
no lo pide.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .enumeracion import notas_en_disco
from .repositorio import RepositorioIndices

#: Cuántas rutas se listan en el informe. El resto se cuenta pero no se enumera:
#: un envelope con 300 rutas no lo lee nadie, y el conteo es lo accionable.
MUESTRA = 20


def coherencia_indice(repo: RepositorioIndices) -> Dict[str, Any]:
    raiz = repo.raiz
    secciones = repo.ctx.secciones.ordenadas()
    en_disco = {
        repo.relativa(p) for p in notas_en_disco(raiz, secciones)
    }

    def _degradado(estado: str, **extra: Any) -> Dict[str, Any]:
        return {
            "ok": False,
            "status": estado,
            "on_disk": len(en_disco),
            "indexed": 0,
            "missing_in_index": sorted(en_disco)[:MUESTRA],
            "stale_in_index": [],
            "graph_nodes": None,
            **extra,
        }

    fichero = repo.indice_busqueda
    if not fichero.exists():
        return _degradado("index_missing")

    try:
        datos = json.loads(fichero.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise json.JSONDecodeError("no es un objeto", "", 0)
    except (json.JSONDecodeError, OSError) as exc:
        return _degradado("index_corrupt", error=f"{type(exc).__name__}: {exc}")

    indexadas = {
        str(n.get("path", "")).replace("\\", "/")
        for n in datos.get("notes", [])
        if n.get("path")
    }
    faltan = sorted(en_disco - indexadas)
    sobran = sorted(indexadas - en_disco)

    nodos = None
    if repo.grafo.exists():
        crudo = repo.leer_json(repo.grafo)
        nodos = len(crudo.get("nodes", [])) if crudo else None

    if not en_disco and not indexadas:
        estado = "index_ok"  # vault vacío: un índice vacío lo refleja
    elif faltan or sobran:
        estado = "index_stale"
    else:
        estado = "index_ok"

    return {
        "ok": estado == "index_ok",
        "status": estado,
        "on_disk": len(en_disco),
        "indexed": len(indexadas),
        "missing_in_index": faltan[:MUESTRA],
        "missing_count": len(faltan),
        "stale_in_index": sobran[:MUESTRA],
        "stale_count": len(sobran),
        "graph_nodes": nodos,
        "graph_drift": (None if nodos is None else len(en_disco) - nodos),
    }
