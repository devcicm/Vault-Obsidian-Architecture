#!/usr/bin/env python3
"""vault_project — registro de proyectos del vault (AP-63).

El nombre de un proyecto es identidad: resuelve a **un** slug o la tool falla.
Esta es la puerta de entrada al registro que lee `vault.kernel.proyectos`:

- `--list`: los proyectos registrados, sus alias, ambigüedades e incidencias.
- `--resolve NOMBRE`: el slug canónico, o `PROJECT_NOT_FOUND` con sugerencias
  / `PROJECT_AMBIGUOUS` con candidatos. `project_resolved_from` dice si casó
  por slug o por alias.
- `--audit`: notas cuyo `project:` no resuelve (los fantasmas) y claves no
  canónicas (`Proyecto:`, `PROJECT:`). Solo lectura.
- `--add SLUG [--title] [--alias ...] [--status]`: registra el proyecto
  creando su ficha `01_Projects/<slug>/project.md`, o le suma alias si ya
  existe. Un alias que ya es de otro proyecto se rechaza: no se elige en
  silencio.
- `--link SLUG --path RUTA`: guarda la ruta local del repositorio en
  `00_System/.local/project-paths.json`, que lleva su propio `.gitignore`.
  Una ruta de disco es de una máquina, no del proyecto: en una nota viajaría
  con cada copia del vault (y `_sin_rutas_locales` la rechaza).
- `--rebuild`: regenera el derivado `00_System/project-registry.json`.

Ejemplos:
    python vault_project.py --list
    python vault_project.py --resolve "VCloud SaaS"
    python vault_project.py --add ans --title "ANS" --alias ans-api
    python vault_project.py --link ans --path ../ans
    python vault_project.py --audit
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_audit_catalog import es_documentacion_del_estandar
from vault_errors import emit_error, emit_fallo, wrap_main
# superseded_by: vault_errors.proyecto_registrado (v40.34). Vivió aquí;
# se reexporta para quien lo importara de la tool.
from vault_errors import proyecto_registrado  # noqa: F401
from vault_io import atomic_write_json, atomic_write_text, get_vault_root, is_snapshot_path, write_report
from vault_lib import parse_frontmatter_with_body
from vault_norms_catalog import STATUS_VOCAB

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.kernel import proyectos  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402
from vault.kernel.normalizacion import slugify_strict  # noqa: E402

TOOL = "vault_project"

#: Derivado: se regenera con `--rebuild` y nunca es la fuente.
REGISTRO_DERIVADO = Path("00_System") / "project-registry.json"
#: Local de cada máquina, fuera de git.
DIRECTORIO_LOCAL = Path("00_System") / ".local"
RUTAS_LOCALES = DIRECTORIO_LOCAL / "project-paths.json"
_GITIGNORE_LOCAL = "*\n"

#: Claves que en un vault real declaran el proyecto. Solo `project` es la
#: canónica; las otras se miden para nombrarlas, no se aceptan.
_CLAVES_DE_PROYECTO = ("project", "proyecto")


def _raiz() -> Path:
    return get_vault_root()


def _registro() -> proyectos.Registro:
    return proyectos.leer_registro(_raiz())




def listar() -> Dict[str, Any]:
    return {"ok": True, "tool": TOOL, "action": "list", **_registro().como_dict()}


def resolver(nombre: str) -> Dict[str, Any]:
    registro = _registro()
    try:
        slug = registro.resolver(nombre)
    except FalloDeDominio as fallo:
        return emit_fallo(TOOL, fallo)
    origen = "slug" if slugify_strict(nombre) == slug else "alias"
    return {"ok": True, "tool": TOOL, "action": "resolve", "project": slug,
            "project_resolved_from": origen}


def auditar(raiz: Optional[Path] = None) -> Dict[str, Any]:
    """AP-63, solo lectura. `raiz` existe para el contraste de la regla 7:
    la CLI no lo expone, así que la tool no puede medir fuera del vault."""
    raiz = Path(raiz) if raiz else _raiz()
    registro = proyectos.leer_registro(raiz)
    citas: Dict[str, List[str]] = {}
    no_canonicas: List[Dict[str, str]] = []
    for p in sorted(raiz.rglob("*.md")):
        rel = p.relative_to(raiz)
        if is_snapshot_path(rel):
            continue
        try:
            crudo = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # La copia del manifiesto cita `mi-api` como ejemplo: no es un proyecto.
        if es_documentacion_del_estandar(rel.as_posix(), crudo):
            continue
        fm, _cuerpo = parse_frontmatter_with_body(crudo)
        if not isinstance(fm, dict):
            continue
        for clave, valor in fm.items():
            if str(clave).lower() not in _CLAVES_DE_PROYECTO or valor in (None, ""):
                continue
            if clave != "project":
                no_canonicas.append({"note": rel.as_posix(), "key": str(clave)})
            for nombre in (valor if isinstance(valor, list) else [valor]):
                citas.setdefault(str(nombre), []).append(rel.as_posix())
    hallazgos = proyectos.fantasmas(registro, citas)
    return {
        "ok": True, "tool": TOOL, "action": "audit", "norm": "AP-63",
        "projects_registered": len(registro.proyectos),
        "phantoms": hallazgos,
        "phantoms_total": len(hallazgos),
        "non_canonical_keys": no_canonicas,
        "ambiguous": registro.ambiguedades(),
        "issues": registro.incidencias,
    }


def _ficha_nueva(slug: str, titulo: str, alias: List[str], status: str) -> str:
    fm = (
        Frontmatter()
        .set("title", titulo, texto=True)
        .set("type", "project")
        .set("project", slug, texto=True)
        .set("aliases", alias)
        .set("status", status)
    )
    return (
        fm.render()
        + f"\n\n# {titulo}\n\n"
        + "Ficha del proyecto en el registro (AP-63). La ruta local del "
        + "repositorio no va aquí: es de cada máquina y vive en "
        + "`00_System/.local/project-paths.json`, fuera de git.\n"
    )


def registrar(slug: str, titulo: Optional[str], alias: List[str], status: str) -> Dict[str, Any]:
    """AP-63: alta o suma de alias. Nunca reasigna un nombre que ya es de otro."""
    canonico = slugify_strict(slug or "")
    if not canonico:
        return emit_error(TOOL, "INVALID_ARGS", f"{slug!r} no produce un slug válido")
    registro = _registro()
    alias = [a.strip() for a in alias if a.strip()]
    for nombre in (canonico, *alias):
        dueños = registro.claves().get(slugify_strict(nombre), set()) - {canonico}
        if dueños:
            return emit_fallo(TOOL, FalloDeDominio(
                "PROYECTO_AMBIGUO",
                f"{nombre!r} ya identifica a {', '.join(sorted(dueños))}; "
                f"añadirlo a {canonico} lo haría ambiguo.",
                project=nombre, candidatos=sorted(dueños | {canonico}),
            ))

    ficha = _raiz() / proyectos.CARPETA_PROYECTOS / canonico / proyectos.FICHA
    if ficha.is_file():
        bloque, cuerpo = separar_frontmatter(ficha.read_text(encoding="utf-8"))
        previos = list(registro.proyectos[canonico].aliases) if canonico in registro.proyectos else []
        nuevos = [a for a in alias if slugify_strict(a) not in {slugify_strict(x) for x in previos}]
        if nuevos:
            fm = Frontmatter.editar(bloque or "").set("aliases", previos + nuevos)
            # `render()` va sin salto final y `cuerpo` empieza tras la línea de
            # cierre: el salto entre los dos es el que `separar_frontmatter` quitó.
            atomic_write_text(ficha, fm.render() + "\n" + cuerpo)
        accion = "aliased"
    else:
        atomic_write_text(ficha, _ficha_nueva(canonico, titulo or canonico, alias, status))
        accion = "added"
    return {"ok": True, "tool": TOOL, "action": accion, "project": canonico,
            "ficha": ficha.relative_to(_raiz()).as_posix(), **write_report()}


def enlazar(nombre: str, ruta: str) -> Dict[str, Any]:
    """La ruta local va a `00_System/.local/`, que git ignora desde dentro."""
    try:
        slug = _registro().resolver(nombre)
    except FalloDeDominio as fallo:
        return emit_fallo(TOOL, fallo)
    destino = Path(ruta).expanduser().resolve()
    if not destino.is_dir():
        return emit_error(TOOL, "INVALID_PATH", f"{ruta!r} no es un directorio")
    local = _raiz() / DIRECTORIO_LOCAL
    gitignore = local / ".gitignore"
    if not gitignore.is_file():
        atomic_write_text(gitignore, _GITIGNORE_LOCAL, sanitize=False)
    fichero = _raiz() / RUTAS_LOCALES
    rutas: Dict[str, str] = {}
    if fichero.is_file():
        try:
            rutas = json.loads(fichero.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return emit_error(TOOL, "DATA_FILE_CORRUPT",
                              f"{RUTAS_LOCALES.as_posix()} no se puede leer ({exc}); no se reescribe")
    if rutas.get(slug) != str(destino):
        rutas[slug] = str(destino)
        atomic_write_json(fichero, dict(sorted(rutas.items())))
    return {"ok": True, "tool": TOOL, "action": "link", "project": slug,
            "file": RUTAS_LOCALES.as_posix(), **write_report()}


def reconstruir() -> Dict[str, Any]:
    datos = _registro().como_dict()
    atomic_write_json(_raiz() / REGISTRO_DERIVADO, {"derived_from": "01_Projects/*/project.md", **datos})
    return {"ok": True, "tool": TOOL, "action": "rebuild",
            "file": REGISTRO_DERIVADO.as_posix(),
            "projects_total": len(datos["projects"]), **write_report()}


def main() -> int:
    ap = argparse.ArgumentParser(description="vault_project — registro de proyectos (AP-63)")
    accion = ap.add_mutually_exclusive_group(required=True)
    accion.add_argument("--list", action="store_true", help="Lista el registro")
    accion.add_argument("--resolve", metavar="NOMBRE", help="Resuelve un nombre a su slug")
    accion.add_argument("--audit", action="store_true", help="Fantasmas y claves no canónicas")
    accion.add_argument("--add", metavar="SLUG", help="Registra un proyecto o le suma alias")
    accion.add_argument("--link", metavar="PROYECTO", help="Guarda la ruta local del repo")
    accion.add_argument("--rebuild", action="store_true", help="Regenera project-registry.json")
    ap.add_argument("--title", help="Título de la ficha (con --add)")
    ap.add_argument("--alias", nargs="*", default=[], help="Alias del proyecto (con --add)")
    ap.add_argument("--status", default="in-progress", choices=sorted(STATUS_VOCAB),
                    help="Estado de la ficha nueva (con --add)")
    ap.add_argument("--path", help="Ruta local del repositorio (con --link)")
    args = ap.parse_args()

    if args.link and not args.path:
        r = emit_error(TOOL, "MISSING_REQUIRED_ARG", "--link necesita --path")
    elif args.list:
        r = listar()
    elif args.resolve is not None:
        r = resolver(args.resolve)
    elif args.audit:
        r = auditar()
    elif args.add is not None:
        r = registrar(args.add, args.title, args.alias, args.status)
    elif args.link:
        r = enlazar(args.link, args.path)
    else:
        r = reconstruir()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))
