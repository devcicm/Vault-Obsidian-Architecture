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
from .seccion import con_marca_de


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

        # El previo del maestro se lee ANTES de la cascada (v41.12): su propia
        # indexación de la sección `99_Index` reescribe este MISMO fichero en
        # formato de sección, y leerlo después compararía contra el destrozo,
        # no contra el maestro que ya había — el sello se movería en cada
        # corrida sin que nada semántico cambiara (el C3 lo medía por hash).
        previo: Optional[str] = None
        try:
            previo = repo.indice_maestro.read_text(encoding="utf-8",
                                                    errors="replace")
        except OSError:
            previo = None

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
        # Mismo cuerpo ⇒ mismo documento: el sello de la marca se conserva;
        # a cuerpo nuevo le toca sello nuevo. La comparación corre sobre la
        # FORMA DE DISCO: escribir sanea (NFC, em-dash→`--`), y contrastar el
        # texto crudo contra el fichero saneado reescribe en cada corrida.
        texto_nuevo = repo.ctx.escritor.sanear("\n".join(lineas))
        texto = con_marca_de(previo, texto_nuevo)
        repo.ctx.escritor.escribir(repo.indice_maestro, texto)
        repo.ctx.escritor.escribir(repo.indice_maestro, texto)

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
            # Recién escrito por `_indexar`: el enlace resuelve. La ruta entera
            # es la que fija cuál de los `index` es (AP-21 precisado). El alias
            # `|índice` dentro de la celda "Índice" de la tabla rompía la fila:
            # la `|` actúa como separador de columna (medido 2026-10-18 en
            # 99_Index/index.md de SMART POS CR — 23 filas afectadas). Mismo
            # arreglo que `vault/indices/seccion.py`: wikilink SIN alias en
            # celdas de tabla. El destino se muestra como el stem.
            if r["ok"]:
                enlace = f"[[{seccion}/index.md]]"
            else:
                enlace = "_(vacía)_"
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
