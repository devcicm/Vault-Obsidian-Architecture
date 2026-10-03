"""Registro de proyectos: qué nombres de proyecto existen y a qué slug resuelven.

El nombre de un proyecto es **identidad**, no texto libre. Hasta aquí cada tool
aceptaba `--project` como cadena y la escribía tal cual en `project:` o en la
ruta `01_Projects/<valor>/`, así que un typo, una mayúscula o un ejemplo del
manifiesto (`mi-api`, `demo`) fundaban un proyecto nuevo sin que nadie lo
decidiera. Medido en un vault ajeno de 647 notas: cuatro proyectos fantasma y
la misma entidad escrita con dos claves (`Proyecto:` y `PROJECT:`).

**De dónde sale el registro.** La carpeta `01_Projects/<slug>/` registra el
slug: es la identidad que un vault real ya usa sin frontmatter ninguno (así lo
lleva /vcloud). La ficha `01_Projects/<slug>/project.md` es opcional y aporta
`aliases:`, `title` y `status`. **No** es `index.md`: ese nombre está reservado
(`indices_structural.RESERVED_INDEX_NAMES`) y `vault_section_index` lo regenera
encima, así que lo que el registro guardara allí se perdería en la siguiente
pasada. Se midió en los dos vaults ajenos antes de escribir esto: sus
`<slug>/index.md` son índices generados sin frontmatter.

**Qué no hace.** No escribe nada, no sabe del catálogo de errores y no conoce
rutas locales de repositorio. Nombra lo que pasó con `FalloDeDominio`; la tool
lo traduce con `vault_errors.emit_fallo`.

**Por qué en el núcleo (v40.34).** Nació en `vault/autoria/`, y en cuanto las
tools de grafo, gobernanza o ciclo de vida empezaron a resolver su `--project`
cada una sumaba un cruce de contexto hacia Autoría. El nombre de un proyecto no
es vocabulario de un contexto: es identidad que leen todos, como la raíz del
vault. Ya dependía solo del núcleo, así que moverlo no le cambia ni una
importación. `vault.autoria.proyectos` queda como reexportación.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .fallos import FalloDeDominio
from .frontmatter_parsing import parse_frontmatter_robust
from .normalizacion import slugify_strict

CARPETA_PROYECTOS = "01_Projects"

#: La ficha del proyecto. Nombre fijo y no reservado: ver el docstring del módulo.
FICHA = "project.md"


@dataclass(frozen=True)
class Proyecto:
    slug: str
    titulo: Optional[str] = None
    status: Optional[str] = None
    aliases: Tuple[str, ...] = ()
    #: Ruta de la ficha relativa al vault, en POSIX; ``None`` si la carpeta no
    #: la tiene, que es un registro válido: la carpeta ya dice el slug.
    ficha: Optional[str] = None


@dataclass
class Registro:
    proyectos: Dict[str, Proyecto] = field(default_factory=dict)
    #: Lo que impide confiar en el registro tal como está: carpetas con nombre
    #: no canónico, fichas ilegibles o con `project:` distinto de su carpeta.
    #: Se publica en vez de corregirse porque leer no escribe.
    incidencias: List[Dict[str, str]] = field(default_factory=list)

    def claves(self) -> Dict[str, Set[str]]:
        """Clave normalizada -> slugs que la reclaman (slug y alias)."""
        indice: Dict[str, Set[str]] = {}
        for p in self.proyectos.values():
            for nombre in (p.slug, *p.aliases):
                clave = slugify_strict(nombre)
                if clave:
                    indice.setdefault(clave, set()).add(p.slug)
        return indice

    def ambiguedades(self) -> Dict[str, List[str]]:
        """Claves que reclaman dos o más proyectos. Un registro con alguna no
        resuelve esa clave: elegir uno en silencio sería inventar la identidad."""
        return {
            clave: sorted(slugs)
            for clave, slugs in sorted(self.claves().items())
            if len(slugs) > 1
        }

    def resolver(self, nombre: str) -> str:
        """Slug canónico de ``nombre``, o `FalloDeDominio` si no hay uno solo."""
        clave = slugify_strict(nombre or "")
        indice = self.claves()
        candidatos = indice.get(clave, set())
        if len(candidatos) == 1:
            return next(iter(candidatos))
        if candidatos:
            raise FalloDeDominio(
                "PROYECTO_AMBIGUO",
                f"El nombre de proyecto {nombre!r} lo reclaman varios proyectos: "
                f"{', '.join(sorted(candidatos))}.",
                project=nombre,
                candidatos=sorted(candidatos),
            )
        raise FalloDeDominio(
            "PROYECTO_NO_REGISTRADO",
            f"El proyecto {nombre!r} no está registrado en {CARPETA_PROYECTOS}/.",
            project=nombre,
            sugerencias=difflib.get_close_matches(clave, sorted(indice), n=3),
            registrados=sorted(self.proyectos),
        )

    def como_dict(self) -> Dict[str, object]:
        return {
            "projects": [
                {
                    "slug": p.slug,
                    "title": p.titulo,
                    "status": p.status,
                    "aliases": list(p.aliases),
                    "ficha": p.ficha,
                }
                for p in sorted(self.proyectos.values(), key=lambda p: p.slug)
            ],
            "ambiguous": self.ambiguedades(),
            "issues": list(self.incidencias),
        }


def _aliases(valor: object) -> Tuple[str, ...]:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, (list, tuple)):
        return ()
    return tuple(str(a).strip() for a in valor if str(a).strip())


def _texto(valor: object) -> Optional[str]:
    if valor is None:
        return None
    return str(valor).strip() or None


def _carpetas(raiz: Path) -> Iterable[Path]:
    base = raiz / CARPETA_PROYECTOS
    if not base.is_dir():
        return []
    # `.locks`, `.history` y similares son de la maquinaria, no proyectos.
    return sorted(
        d for d in base.iterdir()
        if d.is_dir() and not d.name.startswith((".", "_"))
    )


def leer_registro(raiz: Path) -> Registro:
    """Lee el registro de ``raiz``. Solo lectura: nunca crea ni corrige nada."""
    registro = Registro()
    for carpeta in _carpetas(Path(raiz)):
        slug = carpeta.name
        canonico = slugify_strict(slug)
        if canonico != slug:
            registro.incidencias.append({
                "kind": "carpeta_no_canonica",
                "folder": f"{CARPETA_PROYECTOS}/{slug}",
                "expected": canonico,
            })
        ficha = carpeta / FICHA
        if not ficha.is_file():
            registro.proyectos[slug] = Proyecto(slug=slug)
            continue
        rel = f"{CARPETA_PROYECTOS}/{slug}/{FICHA}"
        try:
            texto = ficha.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            registro.incidencias.append({"kind": "ficha_ilegible", "file": rel, "error": str(exc)})
            registro.proyectos[slug] = Proyecto(slug=slug, ficha=rel)
            continue
        fm, _cuerpo, ok, error = parse_frontmatter_robust(texto)
        if not ok:
            registro.incidencias.append({"kind": "ficha_ilegible", "file": rel, "error": error or ""})
        declarado = _texto(fm.get("project"))
        if declarado is not None and slugify_strict(declarado) != canonico:
            registro.incidencias.append({
                "kind": "ficha_contradice_carpeta",
                "file": rel,
                "declared": declarado,
                "expected": slug,
            })
        registro.proyectos[slug] = Proyecto(
            slug=slug,
            titulo=_texto(fm.get("title")),
            status=_texto(fm.get("status")),
            aliases=_aliases(fm.get("aliases")),
            ficha=rel,
        )
    return registro


def fantasmas(registro: Registro, valores: Mapping[str, Iterable[str]]) -> List[Dict[str, object]]:
    """De ``valores`` (nombre de proyecto -> notas que lo citan), los que no
    resuelven a un único proyecto registrado. Es la medida del audit de AP-63."""
    indice = registro.claves()
    hallazgos: List[Dict[str, object]] = []
    for nombre, notas in sorted(valores.items()):
        candidatos = indice.get(slugify_strict(nombre), set())
        if len(candidatos) == 1:
            continue
        hallazgos.append({
            "project": nombre,
            "kind": "ambiguo" if candidatos else "no_registrado",
            "candidates": sorted(candidatos),
            "notes": sorted(notas),
        })
    return hallazgos
