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
  Lo portable —remoto y rama por defecto— va a `repo:` de la ficha.
- `--sync-status PROYECTO`: compara `repo.synced_commit` con el HEAD del repo
  enlazado y da los commits pendientes de volcar al vault. Solo lectura.
  `vault_drift_detect --mode snapshot` y `vault_code_sync` (con trazabilidad
  completa) son quienes anotan `synced_commit`.
- `--heal [--apply]`: canoniza `project:` al slug del registro —clave no
  canónica y valor por alias o variante—. Dry-run salvo `--apply`, que deja
  la versión anterior en `.history/` (la lee `vault_undo`). Los fantasmas y
  los conflictos se listan; no se tocan.
- `--rebuild`: regenera el derivado `00_System/project-registry.json`.

Ejemplos:
    python vault_project.py --list
    python vault_project.py --resolve "VCloud SaaS"
    python vault_project.py --add ans --title "ANS" --alias ans-api
    python vault_project.py --link ans --path ../ans
    python vault_project.py --sync-status ans
    python vault_project.py --audit
    python vault_project.py --heal            # dry-run
    python vault_project.py --heal --apply
"""

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_audit_catalog import es_documentacion_del_estandar
from vault_fundamentals_catalog import cia_por_defecto
from vault_errors import emit_error, emit_fallo, wrap_main
# superseded_by: vault_errors.proyecto_registrado (v40.34). Vivió aquí;
# se reexporta para quien lo importara de la tool.
from vault_errors import proyecto_registrado  # noqa: F401
from vault_io import atomic_write_json, atomic_write_text, file_lock, get_vault_root, is_snapshot_path, write_report
from vault_lib import parse_frontmatter_with_body, utcnow
from vault_norms_catalog import STATUS_VOCAB
from vault_undo import _guardar_version_actual
import vault_subproceso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.frontmatter import firmante  # noqa: E402
from vault.kernel import proyectos  # noqa: E402
from vault.kernel.fallos import FalloDeDominio  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.frontmatter_parsing import parse_frontmatter_robust, separar_frontmatter  # noqa: E402
from vault.kernel.normalizacion import slugify_strict  # noqa: E402

TOOL = "vault_project"

#: Derivado: se regenera con `--rebuild` y nunca es la fuente.
REGISTRO_DERIVADO = Path("00_System") / "project-registry.json"
#: Local de cada máquina, fuera de git. superseded_by: vault.kernel.proyectos
#: (v40.34) — `code_sync` y `drift_detect` también la leen, y desde otro
#: contexto; se conservan los nombres.
DIRECTORIO_LOCAL = proyectos.DIRECTORIO_LOCAL
RUTAS_LOCALES = proyectos.RUTAS_LOCALES
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
    return {"ok": True, "tool": TOOL, "action": "resolve", "project": slug,
            "project_resolved_from": proyectos.resuelto_desde(nombre, slug)}


def auditar(raiz: Optional[Path] = None) -> Dict[str, Any]:
    """AP-63, solo lectura. `raiz` existe para el contraste de la regla 7:
    la CLI no lo expone, así que la tool no puede medir fuera del vault."""
    raiz = Path(raiz) if raiz else _raiz()
    registro = proyectos.leer_registro(raiz)
    citas: Dict[str, List[str]] = {}
    no_canonicas: List[Dict[str, str]] = []
    ilegibles: List[Dict[str, str]] = []
    for _p, rel, crudo in _notas_de_proyecto(raiz):
        # AP-51: un frontmatter que no parsea no es una nota sin proyecto. Hasta
        # v40.35 se saltaba en silencio y el audit salía limpio sin haberla
        # leído; la regla 7 lo destapó con un título sin comillas en /ans.
        fm, _cuerpo, legible, causa = parse_frontmatter_robust(crudo)
        if not legible:
            ilegibles.append({"note": rel.as_posix(), "cause": str(causa)})
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
        "notes_unreadable": ilegibles,
        "notes_unreadable_total": len(ilegibles),
        "ambiguous": registro.ambiguedades(),
        "issues": registro.incidencias,
    }

def _notas_de_proyecto(raiz: Path):
    """`(ruta, rel, crudo)` de las notas que mide el audit: sin snapshots ni la
    documentación del estándar. Un solo recorrido para `auditar` y `sanar`."""
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
        yield p, rel, crudo


def _plan_de_nota(registro: proyectos.Registro, fm: Dict[str, Any]):
    """AP-63: qué cambiaría en el `project:` de una nota, o por qué no.

    Devuelve `(slug, claves_a_retirar, motivo)`. Solo se repara lo que resuelve
    a **un** proyecto registrado: un nombre sin dueño o con dos no se adivina.
    """
    claves = [c for c in fm if str(c).lower() in _CLAVES_DE_PROYECTO and fm[c] not in (None, "")]
    if not claves:
        return None, [], None
    indice = registro.claves()
    destinos = set()
    for clave in claves:
        valor = fm[clave]
        if isinstance(valor, (list, dict)):
            return None, [], "valor_no_escalar"
        candidatos = indice.get(slugify_strict(str(valor)), set())
        if len(candidatos) != 1:
            return None, [], "ambiguo" if candidatos else "no_registrado"
        destinos |= candidatos
    if len(destinos) != 1:
        return None, [], "conflicto"
    slug = destinos.pop()
    retirar = [c for c in claves if c != "project"]
    if not retirar and fm.get("project") == slug:
        return None, [], None
    return slug, retirar, None


def _valores_de_proyecto(fm: Dict[str, Any]) -> Dict[str, Any]:
    return {str(c): fm[c] for c in fm if str(c).lower() in _CLAVES_DE_PROYECTO}


def sanar(apply: bool = False) -> Dict[str, Any]:
    """AP-63, heal: `project:` canónico con el slug del registro.

    Dry-run salvo `apply`. Repara solo lo mecánico —clave no canónica
    (`Proyecto:`, `PROJECT:`) y valor que resuelve por alias o variante—; los
    fantasmas y los conflictos se listan y no se tocan: inventar el dueño de
    un nombre es peor que el hueco. Antes de escribir, la versión anterior va
    a `.history/` con el nombre que lee `vault_undo`, y la nota se relee con el
    criterio del consumidor (`parse_frontmatter_with_body`): el resto de las
    claves tiene que leerse igual o no se escribe.
    """
    raiz = _raiz()
    registro = proyectos.leer_registro(raiz)
    reparadas: List[Dict[str, Any]] = []
    sin_reparar: List[Dict[str, Any]] = []
    for p, rel, crudo in _notas_de_proyecto(raiz):
        fm, _cuerpo, legible, _causa = parse_frontmatter_robust(crudo)
        if not legible:
            # AP-51: se declara; reparar el YAML no es cosa de AP-63.
            sin_reparar.append({"note": rel.as_posix(), "cause": "frontmatter_ilegible"})
            continue
        slug, retirar, motivo = _plan_de_nota(registro, fm)
        if motivo:
            sin_reparar.append({"note": rel.as_posix(), "cause": motivo,
                                "values": _valores_de_proyecto(fm)})
            continue
        if slug is None:
            continue
        bloque, cuerpo = separar_frontmatter(crudo)
        editado = Frontmatter.editar(bloque or "")
        for clave in retirar:
            editado.quitar(str(clave))
        nuevo = editado.set("project", slug, texto=True).render() + "\n" + cuerpo
        despues, _ = parse_frontmatter_with_body(nuevo)
        esperado = {k: v for k, v in fm.items() if k not in retirar}
        esperado["project"] = slug
        if despues != esperado:
            sin_reparar.append({"note": rel.as_posix(), "cause": "lectura_distinta",
                                "values": _valores_de_proyecto(fm)})
            continue
        entrada: Dict[str, Any] = {"note": rel.as_posix(), "project": slug,
                                   "from": _valores_de_proyecto(fm)}
        if apply:
            # AP-54: diagnóstico y escritura sobre el mismo texto.
            with file_lock(p):
                if p.read_text(encoding="utf-8") != crudo:
                    sin_reparar.append({"note": rel.as_posix(), "cause": "cambio_concurrente"})
                    continue
                entrada["backup"] = ".history/" + _guardar_version_actual(p)
                atomic_write_text(p, nuevo)
            entrada["written"] = True
        reparadas.append(entrada)
    return {
        "ok": True, "tool": TOOL, "action": "heal", "norm": "AP-63",
        "mode": "apply" if apply else "dry-run",
        # AP-37: lo escrito en disco, que en dry-run es cero.
        "healed": sum(1 for r in reparadas if r.get("written")),
        "repairable": reparadas,
        "repairable_count": len(reparadas),
        "unrepaired": sin_reparar,
        "unrepaired_count": len(sin_reparar),
        "hint": ("Lo que no resuelve a un proyecto registrado no se adivina: "
                 "regístralo con --add (o súmale el alias) y vuelve a pasar --heal."),
        **(write_report() if apply else {}),
    }


def _ficha_nueva(slug: str, titulo: str, alias: List[str], status: str) -> str:
    # La ficha es una nota de contenido como cualquier otra: hasta v40.34 salía
    # sin autor, tags, CIA ni fechas, y el audit la penalizaba en cuanto se
    # registraba un proyecto (AP-16, AP-26, AP-30, missing_updated). Hasta
    # v40.36, además, sin `id`, que el contrato exige a toda nota (AP-12).
    ahora = utcnow()
    fm = (
        Frontmatter()
        .set("title", titulo, texto=True)
        .set("id", str(uuid.uuid4()))
        .set("type", "project")
        .set("project", slug, texto=True)
        .set("aliases", alias)
        .set("status", status)
        .set("tags", [slug, "project"])
        .set("createdAt", ahora)
        .set("updatedAt", ahora)
    )
    for campo, valor in cia_por_defecto().items():
        fm.set(campo, valor, texto=True)
    fm.set("agent", firmante(), texto=True)
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
            fm = (Frontmatter.editar(bloque or "").set("aliases", previos + nuevos)
                  .set("updatedAt", utcnow()))
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
    # Lo portable va a la ficha; la ruta, nunca. Un repo sin remoto o sin git
    # se enlaza igual: la ruta basta para `drift_detect` por hash.
    remoto = _git(destino, "config", "--get", "remote.origin.url")
    rama = _git(destino, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    rama = rama.split("/", 1)[1] if rama and "/" in rama else _git(destino, "branch", "--show-current")
    ficha = proyectos.anotar_repo(_raiz(), slug, atomic_write_text,
                                  remote=remoto, default_branch=rama)
    return {"ok": True, "tool": TOOL, "action": "link", "project": slug,
            "file": RUTAS_LOCALES.as_posix(), "ficha": ficha,
            "repo": proyectos.repo_de(_raiz(), slug), **write_report()}


def _git(ruta: Path, *args: str) -> Optional[str]:
    """Salida de `git <args>` en ``ruta``, o ``None`` si no hay git o falla."""
    try:
        r = vault_subproceso.ejecutar(["git", *args], cwd=str(ruta),
                                      capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    salida = (r.stdout or "").strip()
    return salida if r.returncode == 0 and salida else None


def _git_ok(ruta: Path, *args: str) -> bool:
    """`git <args>` terminó con 0 (para los que no imprimen nada)."""
    try:
        return vault_subproceso.ejecutar(["git", *args], cwd=str(ruta),
                                         capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def estado_sync(nombre: str, limite: int = 20) -> Dict[str, Any]:
    """AP-63, P4. Solo lectura: cuánto va el repo por delante del vault."""
    try:
        slug = _registro().resolver(nombre)
    except FalloDeDominio as fallo:
        return emit_fallo(TOOL, fallo)
    repo = proyectos.repo_de(_raiz(), slug)
    ruta = proyectos.ruta_local(_raiz(), slug)
    base = {"ok": True, "tool": TOOL, "action": "sync-status", "project": slug,
            "repo": repo, "linked": ruta is not None,
            "synced_commit": repo.get("synced_commit")}
    if ruta is None:
        return {**base, "state": "unlinked",
                "hint": f"python vault_project.py --link {slug} --path <repo>"}
    if not ruta.is_dir():
        return emit_error(TOOL, "INVALID_PATH",
                          f"la ruta enlazada de {slug} ya no es un directorio; vuelve a --link")
    head = _git(ruta, "rev-parse", "HEAD")
    if head is None:
        return {**base, "state": "no_git", "head": None}
    sincronizado = repo.get("synced_commit")
    if not sincronizado:
        return {**base, "state": "never_synced", "head": head,
                "hint": f"python vault_drift_detect.py --project {slug} --mode snapshot"}
    if not _git_ok(ruta, "cat-file", "-e", f"{sincronizado}^{{commit}}"):
        return {**base, "state": "unknown_commit", "head": head,
                "hint": "synced_commit no existe en este clon: fetch, o vuelve a sincronizar"}
    cuenta = _git(ruta, "rev-list", "--count", f"{sincronizado}..HEAD")
    pendientes = int(cuenta) if cuenta and cuenta.isdigit() else 0
    lista = _git(ruta, "log", "--format=%h %s", f"-{limite}", f"{sincronizado}..HEAD")
    return {**base, "state": "in_sync" if pendientes == 0 else "behind", "head": head,
            "pending_commits": pendientes,
            "pending": lista.splitlines() if lista else []}


def reconstruir() -> Dict[str, Any]:
    datos = _registro().como_dict()
    atomic_write_json(_raiz() / REGISTRO_DERIVADO, {"derived_from": "01_Projects/*/project.md", **datos})
    return {"ok": True, "tool": TOOL, "action": "rebuild",
            "file": REGISTRO_DERIVADO.as_posix(),
            "projects_total": len(datos["projects"]), **write_report()}


def main() -> int:
    ap = argparse.ArgumentParser(description="vault_project — registro de proyectos (AP-63)", allow_abbrev=False)
    accion = ap.add_mutually_exclusive_group(required=True)
    accion.add_argument("--list", action="store_true", help="Lista el registro")
    accion.add_argument("--resolve", metavar="NOMBRE", help="Resuelve un nombre a su slug")
    accion.add_argument("--audit", action="store_true", help="Fantasmas y claves no canónicas")
    accion.add_argument("--add", metavar="SLUG", help="Registra un proyecto o le suma alias")
    accion.add_argument("--link", metavar="PROYECTO", help="Guarda la ruta local del repo")
    accion.add_argument("--sync-status", metavar="PROYECTO",
                        help="Commits del repo enlazado pendientes de volcar al vault")
    accion.add_argument("--rebuild", action="store_true", help="Regenera project-registry.json")
    accion.add_argument("--heal", action="store_true",
                        help="Canoniza project: al slug registrado (dry-run salvo --apply)")
    ap.add_argument("--apply", action="store_true", help="Con --heal: escribe (copia previa en .history/)")
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
    elif args.sync_status:
        r = estado_sync(args.sync_status)
    elif args.heal:
        r = sanar(apply=args.apply)
    else:
        r = reconstruir()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, TOOL))
