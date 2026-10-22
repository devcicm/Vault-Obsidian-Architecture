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
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .errores import envelope_de_fallo
from .escritura import escritura_atomica
from .fallos import FalloDeDominio
from .frontmatter_escritura import Frontmatter
from .frontmatter_parsing import parse_frontmatter_robust, separar_frontmatter
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


def pertenencia(registro: Registro, nombre: str) -> Callable[[object], bool]:
    """Predicado único «este valor es del proyecto ``nombre``» (AP-63, P3).

    Cada lector decidía a su manera si una nota, una entrada de índice o una
    etiqueta eran de un proyecto: `==` exacto en unos, `.lower() ==` en otros
    y **subcadena** en `vault_change_log`, `vault_timeline` y
    `vault_project_overview`, donde `--project api` contaba como suyo todo lo
    de `mi-api`. Tres criterios para una sola identidad es AP-57.

    El valor guardado se compara por su clave normalizada contra las claves
    del proyecto: su slug y los alias que **solo** él reclama. Así una nota
    escrita antes del registro con `project: Mi API` sigue siendo de `mi-api`,
    y un alias ambiguo no se atribuye a nadie. Si ``nombre`` no resuelve —una
    llamada directa a la función, sin la CLI que ya lo habría rechazado— se
    compara solo por su propia clave: filtrar no es el sitio donde fallar.
    """
    try:
        slug = registro.resolver(nombre)
    except FalloDeDominio:
        propias = {slugify_strict(nombre or "")} - {""}
    else:
        propias = {
            clave for clave, slugs in registro.claves().items() if slugs == {slug}
        } | {slugify_strict(slug)}

    def es_del_proyecto(valor: object) -> bool:
        if valor is None or isinstance(valor, (dict, list, tuple, set)):
            return False
        return slugify_strict(str(valor)) in propias

    return es_del_proyecto


def pertenencia_en(raiz: Path, nombre: str) -> Callable[[object], bool]:
    """`pertenencia` leyendo el registro de ``raiz``: lo que llama un lector."""
    return pertenencia(leer_registro(raiz), nombre)


#: Local de cada máquina, fuera de git: la ruta del repositorio en disco.
#: En una nota viajaría con cada copia del vault (`_sin_rutas_locales`).
DIRECTORIO_LOCAL = Path("00_System") / ".local"
RUTAS_LOCALES = DIRECTORIO_LOCAL / "project-paths.json"
#: Las rutas de los **vaults** de cada proyecto (v41.15). Vive junto a
#: `RUTAS_LOCALES` y tambien fuera de git: cada maquina puede tener el
#: vault de un proyecto en un sitio distinto.
RUTAS_DE_VAULT = Path("00_System") / ".local" / "vault-paths.json"

#: Las rutas de los **vaults** de cada proyecto (v41.15). Vive junto a
#: `RUTAS_LOCALES` y tambien fuera de git: cada maquina puede tener el
#: vault de un proyecto en un sitio distinto.
RUTAS_DE_VAULT = Path("00_System") / ".local" / "vault-paths.json"

#: Lo portable de la relación con el repositorio, en la ficha bajo `repo:`.
CAMPOS_REPO = ("remote", "default_branch", "synced_commit", "synced_at")


def ruta_local(raiz: Path, slug: str) -> Optional[Path]:
    """La ruta del repo enlazada con `vault_project --link`, o ``None``.

    Un fichero ilegible es ``None`` y no un fallo: quien lo necesita pide
    `--path`, como antes de P4. Lo reescribe `--link`, que sí lo rechaza."""
    fichero = Path(raiz) / RUTAS_LOCALES
    try:
        rutas = json.loads(fichero.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    valor = rutas.get(slug) if isinstance(rutas, dict) else None
    return Path(valor) if isinstance(valor, str) and valor else None


def _ficha(raiz: Path, slug: str) -> Path:
    return Path(raiz) / CARPETA_PROYECTOS / slug / FICHA


def repo_de(raiz: Path, slug: str) -> Dict[str, str]:
    """El bloque `repo:` de la ficha, solo con los campos de `CAMPOS_REPO`."""
    try:
        texto = _ficha(raiz, slug).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    fm, _cuerpo, _ok, _error = parse_frontmatter_robust(texto)
    repo = fm.get("repo") if isinstance(fm, dict) else None
    if not isinstance(repo, dict):
        return {}
    return {k: str(repo[k]) for k in CAMPOS_REPO if repo.get(k) not in (None, "")}


def ruta_de_vault(raiz: Path, slug: str) -> Optional[Path]:
    """La ruta del vault de ese proyecto en esta maquina, o `None`.

    La escribe `vault_project --link --vault <ruta>`, o el puntero
    `.vault-path` que el repositorio declara (v41.15): son las dos formas de
    decir donde vive el vault de un proyecto, y la segunda la escribe la
    persona porque una tool que escribiera fuera del vault romperia la
    contencion de AP-36.
    """
    fichero = Path(raiz) / RUTAS_DE_VAULT
    try:
        rutas = json.loads(fichero.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    valor = rutas.get(slug) if isinstance(rutas, dict) else None
    return Path(valor) if isinstance(valor, str) and valor else None


def anotar_vault(raiz: Path, slug: str, ruta: "str | Path") -> Optional[str]:
    """Guarda la ruta del vault del proyecto en el registro local.

    Devuelve la ruta guardada, o `None` si no se pudo escribir. No crea el
    vault: esto declara donde esta, no lo hace.
    """
    destino = Path(ruta).expanduser()
    fichero = Path(raiz) / RUTAS_DE_VAULT
    rutas: Dict[str, str] = {}
    if fichero.is_file():
        try:
            rutas = json.loads(fichero.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rutas = {}
    if not isinstance(rutas, dict):
        rutas = {}
    rutas[slug] = str(destino)
    try:
        escritura_atomica(fichero, json.dumps(dict(sorted(rutas.items())),
                                               ensure_ascii=False, indent=1))
    except OSError:
        return None
    return str(destino)


def ruta_de_vault(raiz: Path, slug: str) -> Optional[Path]:
    """La ruta del vault de ese proyecto en esta maquina, o `None`.

    La escribe `vault_project --link --vault <ruta>`, o el puntero
    `.vault-path` que el repositorio declara (v41.15): son las dos formas de
    decir donde vive el vault de un proyecto, y la segunda la escribe la
    persona porque una tool que escribiera fuera del vault romperia la
    contencion de AP-36.
    """
    fichero = Path(raiz) / RUTAS_DE_VAULT
    try:
        rutas = json.loads(fichero.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    valor = rutas.get(slug) if isinstance(rutas, dict) else None
    return Path(valor) if isinstance(valor, str) and valor else None


def anotar_vault(raiz: Path, slug: str, ruta: "str | Path") -> Optional[str]:
    """Guarda la ruta del vault del proyecto en el registro local.

    Devuelve la ruta guardada, o `None` si no se pudo escribir. No crea el
    vault: esto declara donde esta, no lo hace.
    """
    destino = Path(ruta).expanduser()
    fichero = Path(raiz) / RUTAS_DE_VAULT
    rutas: Dict[str, str] = {}
    if fichero.is_file():
        try:
            rutas = json.loads(fichero.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rutas = {}
    if not isinstance(rutas, dict):
        rutas = {}
    rutas[slug] = str(destino)
    try:
        escritura_atomica(fichero, json.dumps(dict(sorted(rutas.items())),
                                               ensure_ascii=False, indent=1))
    except OSError:
        return None
    return str(destino)


def anotar_repo(
    raiz: Path,
    slug: str,
    escribir: Callable[[Path, str], object] = escritura_atomica,
    **campos: Optional[str],
) -> Optional[str]:
    """Mezcla ``campos`` en `repo:` de la ficha; la ruta relativa, o ``None``.

    Sin ficha no se crea ninguna: el registro lo funda `vault_project --add`,
    y anotar el commit no es la forma de dar de alta un proyecto. Si nada
    cambia, no se escribe. `escribir` es el transporte: las tools pasan
    `vault_io.atomic_write_text`, que cuenta la escritura (AP-37) y aplica
    sus guardas; el núcleo no conoce el ledger."""
    desconocidos = set(campos) - set(CAMPOS_REPO)
    if desconocidos:
        raise ValueError(f"campos de repo desconocidos: {sorted(desconocidos)}")
    ficha = _ficha(raiz, slug)
    if not ficha.is_file():
        return None
    actual = repo_de(raiz, slug)
    nuevo = dict(actual)
    nuevo.update({k: v for k, v in campos.items() if v})
    rel = f"{CARPETA_PROYECTOS}/{slug}/{FICHA}"
    if nuevo == actual:
        return rel
    bloque, cuerpo = separar_frontmatter(ficha.read_text(encoding="utf-8"))
    ordenado = {k: nuevo[k] for k in CAMPOS_REPO if k in nuevo}
    fm = Frontmatter.editar(bloque or "").set("repo", ordenado)
    escribir(ficha, fm.render() + "\n" + cuerpo)
    return rel


def resuelto_desde(nombre: str, slug: str) -> str:
    """`project_resolved_from`: `slug` si el nombre ya era la clave, si no `alias`.

    Campo estable del envelope (`field-compat-baseline.json`). Lo emiten
    `vault_project --resolve` y `vault mcp-path --project`; el criterio vive
    aquí para que no haya dos.
    """
    return "slug" if slugify_strict(nombre or "") == slug else "alias"


#: AP-63, P5 — proyecto por sesión. Declaradas en `vault_entorno.VARIABLES`;
#: se leen aquí directamente porque el núcleo no importa `scripts/`.
ENTORNO_PROYECTO = "VAULT_PROJECT"
ENTORNO_CANDADO = "VAULT_PROJECT_LOCK"


def proyecto_de_sesion(registro: Registro,
                       entorno: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """El slug al que está atada la sesión, o `None` si no hay candado.

    Sin `VAULT_PROJECT_LOCK=1`, `VAULT_PROJECT` no restringe nada. Con el
    candado, el proyecto se resuelve contra el registro como cualquier
    `--project`: un alias vale y un nombre que no resuelve falla. Candado sin
    proyecto falla también —cerrado por defecto—: la alternativa sería que una
    variable olvidada abriese la sesión entera.
    """
    entorno = os.environ if entorno is None else entorno
    if entorno.get(ENTORNO_CANDADO) != "1":
        return None
    nombre = (entorno.get(ENTORNO_PROYECTO) or "").strip()
    if not nombre:
        raise FalloDeDominio(
            "PROYECTO_FUERA_DE_SESION",
            f"{ENTORNO_CANDADO}=1 sin {ENTORNO_PROYECTO}: la sesión no tiene "
            "proyecto y el candado no deja trabajar en ninguno.",
            session_project=None,
        )
    return registro.resolver(nombre)


def comprobar_sesion(registro: Registro, slug: str,
                     entorno: Optional[Mapping[str, str]] = None) -> None:
    """`FalloDeDominio` si la sesión está atada a un proyecto que no es `slug`."""
    sesion = proyecto_de_sesion(registro, entorno)
    if sesion is not None and slug != sesion:
        raise FalloDeDominio(
            "PROYECTO_FUERA_DE_SESION",
            f"La sesión está atada a {sesion!r} y se pidió {slug!r}.",
            session_project=sesion,
            project=slug,
        )


def comprobar_ruta_en_sesion(raiz: Path, ruta: object,
                             entorno: Optional[Mapping[str, str]] = None) -> None:
    """El candado de P5 para las tools que reciben ruta y no `--project`.

    `vault_write`, `vault_append`, `vault_move` y `vault_delete` escriben donde
    se les señala, así que la fábrica de `--project` no las ve. El proyecto de
    una ruta es el segundo segmento —`<carpeta>/<slug>/...`, la forma de
    `01_Projects/`, `11_Code/` y las de cada tipo de nota— cuando su clave
    pertenece a un proyecto registrado. Un segmento que reclaman varios cuenta
    como de otro salvo que el de la sesión esté entre ellos: el candado se
    equivoca hacia cerrar. Fuera de esa forma no hay proyecto que comprobar; la
    contención en el vault es de `assert_within_vault`, no de aquí.
    """
    entorno = os.environ if entorno is None else entorno
    if entorno.get(ENTORNO_CANDADO) != "1":
        return
    registro = leer_registro(Path(raiz))
    sesion = proyecto_de_sesion(registro, entorno)
    try:
        partes = Path(str(ruta)).resolve().relative_to(Path(raiz).resolve()).parts
    except ValueError:
        return
    # `<carpeta>/<slug>` a secas es la carpeta del proyecto (un `vault_move`
    # de carpeta); `<carpeta>/nota.md` no tiene proyecto en la ruta.
    if len(partes) < 2 or (len(partes) == 2 and Path(partes[1]).suffix):
        return
    duenos = registro.claves().get(slugify_strict(partes[1]), set())
    if duenos and sesion not in duenos:
        raise FalloDeDominio(
            "PROYECTO_FUERA_DE_SESION",
            f"La sesión está atada a {sesion!r} y la ruta "
            f"{'/'.join(partes)!r} es de {', '.join(sorted(duenos))}.",
            session_project=sesion,
            project=sorted(duenos)[0] if len(duenos) == 1 else sorted(duenos),
            path="/".join(partes),
        )


def proyecto_registrado(
    tool: str,
    raiz: Callable[[], Path],
    emitir: Callable[[str, FalloDeDominio], Dict[str, object]] = envelope_de_fallo,
) -> Callable[[str], str]:
    """`type=` de argparse para el `--project` de toda tool (AP-63).

    Lo que llega a la tool ya es el slug canónico. Un nombre que no resuelve
    no llega: se imprime el envelope con el nombre de **la tool que llama**
    —por eso es una fábrica— y se sale con 1 antes de que la tool cree nada.
    No se usa `ArgumentTypeError`: argparse lo volvería texto por stderr con
    código 2, fuera del contrato que leen la CLI y el MCP. La cadena vacía
    pasa tal cual: es el «sin proyecto» de las opcionales.

    `raiz` se llama al resolver, no al construir el parser: la raíz puede
    salir del propio argv (`--root` de los entry modules) o del entorno.
    `emitir` es el transporte: `vault_errors` pasa `emit_fallo`, que además
    deja traza; el código instalado usa el envelope sin I/O del núcleo.

    Con `VAULT_PROJECT_LOCK=1` (P5), un nombre que resuelve a otro proyecto
    que el de la sesión sale con `PROJECT_LOCKED`. Es el único punto por el
    que pasan los `--project` de las 43 tools, así que el candado no depende
    de que cada una se acuerde de mirarlo.
    """

    def _resolver(valor: str) -> str:
        if valor == "":
            return valor
        try:
            registro = leer_registro(Path(raiz()))
            slug = registro.resolver(valor)
            comprobar_sesion(registro, slug)
            return slug
        except FalloDeDominio as fallo:
            print(json.dumps(emitir(tool, fallo), ensure_ascii=False))
            raise SystemExit(1)

    _resolver.__name__ = "proyecto_registrado"
    return _resolver
