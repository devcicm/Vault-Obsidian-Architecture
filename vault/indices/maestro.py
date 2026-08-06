"""El índice maestro: `99_Index/index.md`, una fila por sección.

La tabla enlaza en texto plano y **no** con wikilinks anclados a ruta: eso es
AP-21, y la razón es que un `[[07_Knowledge/index]]` deja de resolver en cuanto
la nota se mueve, que es precisamente lo que un vault vivo hace todo el rato.

Generar cada índice de sección es trabajo del otro servicio; aquí se recibe ya
hecho. Que el maestro no sepa indexar una sección es intencionado: si supiera,
habría dos implementaciones de lo mismo (AP-48).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence

from .repositorio import RepositorioIndices


class ServicioIndiceMaestro:
    def __init__(
        self,
        repo: RepositorioIndices,
        indexar_seccion: Callable[[str], dict],
        describir_seccion: Callable[[str], str],
    ) -> None:
        self._repo = repo
        self._indexar = indexar_seccion
        self._describir = describir_seccion

    def generar(self) -> Dict[str, Any]:
        repo = self._repo
        secciones: Sequence[str] = repo.ctx.secciones.ordenadas()
        resultados: List[Dict[str, Any]] = []
        total = 0

        for seccion in secciones:
            if not (repo.raiz / seccion).exists():
                resultados.append({"section": seccion, "noteCount": 0, "ok": False})
                continue
            r = self._indexar(seccion)
            n = r.get("noteCount", 0)
            total += n
            resultados.append(
                {"section": seccion, "noteCount": n, "ok": r.get("ok", False)}
            )

        lineas = self._componer(resultados, total, len(secciones))
        repo.dir_indices.mkdir(parents=True, exist_ok=True)
        repo.ctx.escritor.escribir(repo.indice_maestro, "\n".join(lineas))

        return {
            "path": repo.relativa(repo.indice_maestro),
            "sectionsTotal": len(secciones),
            "notesTotal": total,
        }

    def _componer(
        self, resultados: List[Dict[str, Any]], total: int, n_secciones: int
    ) -> List[str]:
        ahora = self._repo.ctx.reloj.marca()
        lineas = [
            "# Vault — Índice Maestro",
            "",
            f"> Generado automáticamente · {ahora} · {total} nota(s) en "
            f"{n_secciones} secciones",
            "",
            "| Sección | Descripción | Notas | Índice |",
            "|---|---|---|---|",
        ]
        for r in resultados:
            seccion = r["section"]
            enlace = f"`{seccion}/index.md`" if r["ok"] else "_(vacía)_"
            lineas.append(
                f"| `{seccion}` | {self._describir(seccion)} | {r['noteCount']} "
                f"| {enlace} |"
            )
        lineas += [
            "",
            "---",
            "",
            "> **Navegación:** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]",
            "",
            "## Índices técnicos",
            "",
            "| Archivo | Descripción |",
            "|---|---|",
            "| `99_Index/search-index.json` | Índice de búsqueda full-text "
            "(auto-generado por vault_write) |",
            "| `99_Index/graph.json` | Grafo de wiki-links, orphans y broken links "
            "(vault_graph) |",
            "| `99_Index/hash-index.json` | Hash + size + CIA por nota "
            "(auto-generado por vault_reindex) |",
            "",
        ]
        return lineas
