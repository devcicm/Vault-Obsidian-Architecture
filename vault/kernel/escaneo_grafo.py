#!/usr/bin/env python3
"""El escaneo del grafo de wikilinks: contenido de notas -> notas, aristas, ambiguos, rotos.

Vivía en `vault_lib` y era la parte que se movía: nueve de los veinte commits
que `vault_kernel` (AP-59, K3) cuenta sobre `vault_lib` caían en este bloque,
y cada uno obligaba a tocar el módulo del que dependen setenta tools para
cambiar algo que consumen tres (`vault_graph`, `vault_graph_merge` y el
refresco de `vault_io`). Separarlo no es cambiar la medida: es que la próxima
evolución del grafo pese aquí y no en la biblioteca común.

La **identidad** se queda en `vault_lib`: `indice_de_nombres`,
`resolver_wikilink` y `colisiones_de_nombre` son el criterio del que también
deriva `indice_de_destinos`, y sacarlos obligaría a `vault_lib` a importar
de aquí —un ciclo—. Este módulo los importa; la dirección es una sola.
"""

from pathlib import Path
from typing import Any, Dict, List

from vault_lib import indice_de_nombres, parse_frontmatter, resolver_wikilink
from vault_regex import RE_WIKILINK  # dueño único del patrón (AP-50)


def _lista_de_cadenas(valor: Any) -> List[str]:
    """`tags:`/`aliases:` como lista de cadenas: YAML admite escalar o lista."""
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return []
    return [str(v).strip() for v in valor if isinstance(v, (str, int, float)) and str(v).strip()]


def escanear_wikilinks(notas: Dict[str, str]) -> Dict[str, Any]:
    """El único escaneo del grafo de wikilinks: `ruta relativa → contenido` → notas y aristas.

    Lo usan `vault_graph` y `vault_graph_merge`, que hasta ahora recorrían el
    vault cada uno a su manera y leían `title:`/`tags:` con un regex por
    líneas: las etiquetas en lista de bloque, en flujo sin comillas o en una
    nota CRLF salían vacías (AP-44). Aquí el frontmatter lo lee
    `parse_frontmatter` y los enlaces se resuelven con `indice_de_nombres` y
    `resolver_wikilink` —nombre de fichero, sufijo de ruta y `aliases:`,
    nunca `title:`—, así que los dos productores no pueden discrepar sobre
    qué nota es cuál (AP-17, AP-57). No hace E/S: leer el disco y qué hacer
    con un fichero ilegible es de cada productor, y cada uno proyecta su
    esquema (`type: "wiki-link"` o `predicate: "wiki_link"`).

    Devuelve `notas` (ruta → `title`, `tags`, `aliases`, `links`), `aristas`
    (`from`, `to`, una por aparición: consolidar es de `vault.grafo.aristas`),
    `ambiguos` (`from`, `link`, `candidates`) y `rotos` (`from`, `link`,
    `targetPath`).
    """
    meta = leer_notas_de_grafo(notas)
    return {"notas": meta, **resolver_enlaces(meta)}


def leer_notas_de_grafo(notas: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """La mitad de lectura de `escanear_wikilinks`: contenido → `title`, `tags`, `aliases`, `links`.

    Separada para que el refresco de una sola nota (`vault.grafo.refresco`) la
    lea con el mismo dueño que la reconstrucción entera, sin leer las demás.
    """
    meta: Dict[str, Dict[str, Any]] = {}
    for rel, contenido in notas.items():
        fm = parse_frontmatter(contenido)
        titulo = fm.get("title")
        meta[rel] = {
            "title": str(titulo).strip() if titulo not in (None, "") else Path(rel).stem,
            "tags": _lista_de_cadenas(fm.get("tags")),
            "aliases": _lista_de_cadenas(fm.get("aliases")),
            "links": RE_WIKILINK.findall(contenido),
        }
    return meta


def resolver_enlaces(meta: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """La mitad de resolución: `ruta → {aliases, links}` → `indice`, `aristas`, `ambiguos`, `rotos`.

    No necesita el contenido, solo los nombres y los enlaces ya leídos: es lo
    que permite repetir la resolución del vault entero desde los nodos de
    `graph.json` cuando cambia una nota (AP-47) sin volver a leer el disco.
    """
    indice = indice_de_nombres(list(meta), {rel: m.get("aliases") or [] for rel, m in meta.items()})
    aristas: List[Dict[str, str]] = []
    ambiguos: List[Dict[str, Any]] = []
    rotos: List[Dict[str, str]] = []
    for rel, m in meta.items():
        for link in m.get("links") or []:
            destino, candidatos = resolver_wikilink(link, Path(rel), indice)
            if destino:
                aristas.append({"from": rel, "to": destino})
            elif candidatos:
                ambiguos.append({"from": rel, "link": link, "candidates": candidatos})
            else:
                rotos.append({"from": rel, "link": link, "targetPath": link.replace("\\", "/")})
    return {"indice": indice, "aristas": aristas, "ambiguos": ambiguos, "rotos": rotos}
