"""El índice de una sección: qué notas hay y cómo se renderiza la tabla.

Estaba dentro de `scripts/vault_section_index.py`, un adaptador de 598 líneas
que hacía las cuatro cosas a la vez: parsear argv, recorrer el disco, decidir el
formato del índice y escribirlo. Aquí vive solo la tercera —y el recorrido que
la alimenta—, que es la única parte con reglas propias del dominio y la única
que se puede probar sin tocar un vault.

Lo que **no** está aquí, deliberadamente: la escritura, el `file_lock`, el
`assert_within_vault` y el guard CN-02 de sección canónica. Todo eso es
contención (AP-36) y pertenece al write path del kernel; bajarlo al dominio
sería tener dos sitios donde se decide qué es una ruta legal.

Las dependencias entran por el constructor, no por import: describir una sección
y sugerir su tool son datos del registro, y `enlace_seguro` es del kernel.
Inyectadas, el renderizado se prueba con dobles y sin disco.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .enumeracion import notas_en_disco

# Alias-wikilink dentro de celda de tabla — formato prohibido en índices:
# combina identidad y título en una celda, confunde a agentes (crean notas en
# blanco a partir del alias) y dispara falsos positivos de sintaxis.
RE_ALIAS_EN_TABLA = re.compile(r"^\|\s*\[\[[^\]|]+\|[^\]]+\]\]", re.MULTILINE)


def recolectar_notas(
    raiz: Path,
    ruta_seccion: Path,
    secciones: Iterable[str],
    incluir_subcarpetas: bool,
    leer_frontmatter: Callable[[str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Metadatos de las notas reales de una carpeta (index.md queda fuera).

    **No enumera por su cuenta.** Qué cuenta como nota indexable lo decide
    `enumeracion.notas_en_disco`, que es el único sitio del contexto que hace
    `rglob`. Si esto tuviera su propio filtro serían dos definiciones de "nota",
    y el índice mostraría un conjunto distinto del que `vault_reindex` indexa:
    exactamente el desfase que AP-47 describe, pero silencioso.

    Lo que sí decide aquí es un recorte propio y declarado: **el `index.md` de la
    propia carpeta**. Es artefacto derivado y listarse a sí mismo añadiría una
    fila en cada regeneración. `readme.md` sí entra, porque es contenido — por
    eso no vale `incluir_indices=False`, que se llevaría los dos por delante.

    Heredaba además el defecto que `enumeracion` ya corrigió: descartaba las
    notas mirando los tramos ocultos de la ruta **absoluta**, así que un vault
    colgado de `~/.claude/…` salía entero como sección vacía. Al consumir el
    enumerador el criterio pasa a ser el relativo, y el defecto desaparece sin
    arreglarse dos veces.
    """
    candidatas = [
        p
        for p in notas_en_disco(raiz, secciones, incluir_indices=True)
        if p.is_relative_to(ruta_seccion)
        and (incluir_subcarpetas or p.parent == ruta_seccion)
    ]
    notas: List[Dict[str, Any]] = []
    for ruta in sorted(candidatas):
        if ruta.name == "index.md":
            continue
        try:
            contenido = ruta.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        meta = leer_frontmatter(contenido)
        rel = str(ruta.relative_to(ruta_seccion)).replace("\\", "/")
        notas.append(
            {
                "title": meta.get("title") or ruta.stem,
                "path": rel,
                "type": meta.get("type") or "",
                "updatedAt": meta.get("updatedAt") or meta.get("createdAt") or "",
            }
        )
    return notas


def migaja(clave_carpeta: str) -> str:
    """Navegación de cabecera para un índice de sección o subsección.

    AP-21: nunca un wikilink anclado a ruta (`[[carpeta/index]]`). Obsidian
    resuelve por stem, e `index` es un stem que comparten todas las secciones:
    el enlace apuntaría a cualquiera de ellas. Se navega en texto plano y con un
    único enlace al hub, que sí es un nombre único.
    """
    partes = clave_carpeta.split("/")
    if len(partes) == 1:
        return "> **←** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]  ·  _99_Index/index.md_"
    padre = partes[0]
    return (
        f"> **←** [[vault-hub|Hub]]  ·  [[vault-commands|Comandos]]  "
        f"·  _99_Index/index.md_  ·  _{padre}/"
    )


class RenderizadorDeIndice:
    """Convierte una lista de notas en el markdown de `index.md`.

    No lee ni escribe nada: recibe las notas ya recolectadas y devuelve texto.
    Esa es la razón de separarlo — el formato del índice tiene reglas (AP-21 en
    los enlaces, el título en su propia columna, cero comandos embebidos) que
    hasta ahora solo se podían comprobar escribiendo en un vault de verdad.
    """

    def __init__(
        self,
        describir_seccion: Callable[[str], str],
        pista_de_tool: Callable[[str], str],
        enlace_seguro: Callable[[str], str],
    ) -> None:
        self._describir = describir_seccion
        self._pista = pista_de_tool
        self._enlace = enlace_seguro

    def render(
        self,
        carpeta: str,
        notas: List[Dict[str, Any]],
        ahora: str,
        subcarpetas: Optional[List[str]] = None,
    ) -> str:
        clave = carpeta.replace("\\", "/")

        descripcion = self._describir(clave)
        pista = self._pista(clave)
        pista_tool = pista if pista else f"vault_write --folder {clave} --title <titulo>"

        lineas = [
            f"# {clave} — Índice",
            "",
            migaja(clave),
            f"> **Propósito:** {descripcion}",
            f"> Generado automáticamente · {ahora} · {len(notas)} nota(s)",
            "",
        ]

        # Subcarpetas antes que notas: se descubre primero la estructura.
        # AP-21: nada de [[02_Observability/errors/index]] — ruta en texto plano
        # y una sola fila que remite al hub para navegar.
        if subcarpetas:
            lineas += ["## Subcarpetas", ""]
            lineas += ["| Carpeta | Propósito |", "|---|---|"]
            for sub in sorted(subcarpetas):
                sub_clave = sub.replace("\\", "/")
                lineas.append(f"| `{sub_clave}/` | {self._describir(sub_clave)} |")
            lineas.append("")
            lineas.append(
                "> Para navegar a una subcarpeta, abre `{folder}/{subcarpeta}/index.md` desde tu editor, o usa el [[vault-hub|Hub]]."
            )
            lineas.append("")

        if notas:
            lineas += [
                "## Notas" if subcarpetas else "",
                "",
                "| Nota | Título | Tipo | Actualizado |",
                "|---|---|---|---|",
            ]
            for n in notas:
                ruta = n["path"].replace("\\", "/")
                # AP-21: enlace por stem, sin prefijo de carpeta. Y sin alias: un
                # alias largo dentro de la celda ([[stem|Título — largo/etc]])
                # parece celda combinada, dispara falsos positivos de sintaxis y
                # provoca notas en blanco creadas a partir del alias. El título
                # va en su propia columna.
                stem = self._enlace(Path(ruta).stem)
                titulo = (
                    str(n["title"]).replace("|", "\\|").replace("[", "").replace("]", "")
                )
                lineas.append(
                    f"| [[{stem}]] | {titulo} | {n['type']} | {n['updatedAt']} |"
                )
        else:
            # Sección vacía — stub mínimo, SIN bloque bash embebido. Los comandos
            # viven en `00_System/vault-commands.md` y en ningún otro sitio:
            # repetirlos en 16 índices es la fuente única duplicada de AP-05.
            lineas += [
                "## Notas",
                "",
                "_Sección sin notas._",
                "",
                f"> **Propósito:** {descripcion}",
                "",
                f"Para poblar esta sección consulta la **referencia unificada de comandos** en [[vault-commands|vault-commands]] "
                f"(entrada _{clave}_).",
                "",
                f"> **Comando sugerido:** `{pista_tool}`",
                "",
                "Una vez creada la primera nota, este índice se regenera automáticamente.",
            ]

        lineas.append("")
        return "\n".join(lineas)
