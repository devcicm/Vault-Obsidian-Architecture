#!/usr/bin/env python3

"""

Vault Drift Detect — Detect undocumented file changes



Compares project file state against a baseline snapshot and cross-references

changes against vault documentation. Identifies what was worked on but not documented.



Supports both git repos (uses git diff) and non-git directories (hash-based snapshot).



Usage:

    # Start of session: take snapshot baseline

    python vault_drift_detect.py --path "src/" --project "ans" --mode snapshot



    # End of session: report undocumented changes

    python vault_drift_detect.py --path "src/" --project "ans" --mode report



    # Just list changed files without vault cross-reference

    python vault_drift_detect.py --path "src/" --project "ans" --mode status

    # Con el repo enlazado (vault_project --link), --path sobra (AP-63, P4)
    python vault_drift_detect.py --project "ans" --mode snapshot

    # AP-08: notas con `files:` cuyo código cambió después de su updatedAt
    python vault_drift_detect.py --project "ans" --mode vigencia

Un snapshot sobre git anota `repo.synced_commit` en la ficha del proyecto: es
el punto hasta el que el vault documenta el código, el que lee
`vault_project --sync-status`.
"""

import argparse

import hashlib

import json

import os

import re

import subprocess

import vault_subproceso

import sys

from vault_errors import emit_error, emit_fallo, wrap_main, proyecto_registrado
from vault_contrato_nota import es_mapa_de_versiones
from vault_lib import parse_frontmatter, slugify_strict, utcnow
from vault_norms_catalog import normalize_status
from datetime import datetime, timezone

from pathlib import Path


from typing import Any, Dict, List, Optional, Set, Tuple


from vault_io import atomic_write_json, atomic_write_text, is_snapshot_path

from vault_registry import section_documentacion

from vault_audit_catalog import es_documentacion_del_estandar


TRACK_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".cs",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    ".ps1",
    ".html",
    ".css",
    ".vue",
    ".svelte",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".env",
    ".sql",
    ".graphql",
    ".md",
    ".mdx",
}


IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "coverage",
    ".nyc_output",
    "target",
    "vendor",
    ".cache",
    "tmp",
    "temp",
    "logs",
    ".precommit_cache",
    "snapshots",
    "migrations",
    "fixtures",
    "__snapshots__",
}


# Extensions that never need vault documentation

SKIP_DOC_EXTENSIONS = {
    ".lock",
    ".log",
    ".map",
    ".min.js",
    ".min.css",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".whl",
    ".egg",
    ".pid",
    ".sock",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".mp4",
    ".mp3",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".pdf",
    ".safetensors",
    ".gguf",
    ".onnx",
    ".pt",
    ".pth",
    ".pem",
    ".crt",
    ".key",
    ".pub",
    ".p12",
    ".pfx",
}


# Path fragments that indicate auto-generated or runtime files

SKIP_PATH_FRAGMENTS = {
    "archive_ca",
    "secrets/",
    ".precommit_cache",
    "data/run/",
    "data/models/",
    "data/backups/",
    "data/security/",
}


# Suggest which vault tool to use per file type

DOC_SUGGESTIONS = {
    "code": {
        "exts": {
            ".py",
            ".js",
            ".mjs",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".cs",
        },
        "tool": "vault_code_module",
    },
    "config": {
        "exts": {".yaml", ".yml", ".toml", ".json", ".env"},
        "tool": "vault_knowledge_save --category config",
    },
    "infra": {
        "exts": {".sh", ".bash", ".ps1"},
        "tool": "vault_knowledge_save --category concept",
    },
    "query": {
        "exts": {".sql", ".graphql"},
        "tool": "vault_knowledge_save --category concept",
    },
    "doc": {"exts": {".md", ".mdx"}, "tool": "vault_write"},
}


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.enumeracion import notas_en_disco  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioGobernanza:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGobernanza(construir(root))


def _snapshot_file() -> Path:
    return _repo().instantanea_sesion


def slugify(text: str) -> str:
    # Delega en el slug canónico (`vault_lib.slugify`). La copia que había
    # aquí divergía del resto: unas borraban los acentos, otras los dejaban
    # en el nombre de fichero. Una sola fuente, un solo nombre de nota.
    return slugify_strict(text)


# ─── Git helpers ─────────────────────────────────────────────────────────────


def _has_git(path: Path) -> bool:
    try:
        result = vault_subproceso.ejecutar(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            capture_output=True,
            timeout=5,
        )

        return result.returncode == 0

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _git_head_commit(path: Path) -> Optional[str]:
    try:
        result = vault_subproceso.ejecutar(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True,
            timeout=5,
        )

        return result.stdout.strip() if result.returncode == 0 else None

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _git_changed_since(path: Path, since_commit: Optional[str]) -> Dict[str, List[str]]:
    """

    Return files the agent worked on this session:

    1. Files committed since snapshot commit (git log since_commit..HEAD)

    2. Files with uncommitted changes vs HEAD (git diff HEAD — staged + unstaged)

    Untracked files are excluded: they pre-existed and were never worked on.

    """

    added, modified, deleted = [], [], []

    seen: Set[str] = set()

    try:
        # 1. Committed changes since snapshot

        if since_commit:
            log_cmd = ["git", "diff", "--name-status", f"{since_commit}...HEAD"]

            log_result = vault_subproceso.ejecutar(
                log_cmd, cwd=str(path), capture_output=True, timeout=10
            )

            for line in log_result.stdout.splitlines():
                line = line.strip()

                if not line:
                    continue

                parts = line.split("\t", 1)

                if len(parts) < 2:
                    continue

                status, filepath = parts[0][0], parts[1]

                if filepath in seen:
                    continue

                seen.add(filepath)

                if status == "A":
                    added.append(filepath)

                elif status == "M":
                    modified.append(filepath)

                elif status == "D":
                    deleted.append(filepath)

                elif status == "R" and "\t" in parts[1]:
                    old, new = parts[1].split("\t", 1)

                    if old not in seen:
                        deleted.append(old)

                        seen.add(old)

                    if new not in seen:
                        added.append(new)

                        seen.add(new)

        # 2. Uncommitted changes (staged + unstaged vs HEAD)

        diff_cmd = ["git", "diff", "--name-status", "HEAD"]

        diff_result = vault_subproceso.ejecutar(
            diff_cmd, cwd=str(path), capture_output=True, timeout=10
        )

        for line in diff_result.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            parts = line.split("\t", 1)

            if len(parts) < 2:
                continue

            status, filepath = parts[0][0], parts[1]

            if filepath in seen:
                continue

            seen.add(filepath)

            if status == "A":
                added.append(filepath)

            elif status == "M":
                modified.append(filepath)

            elif status == "D":
                deleted.append(filepath)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {"added": added, "modified": modified, "deleted": deleted}


# ─── Hash-based snapshot helpers ─────────────────────────────────────────────


def _file_md5(path: Path) -> str:
    h = hashlib.md5()

    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)

    except OSError:
        return ""

    return h.hexdigest()


def _should_track(path: Path, exts: Set[str]) -> bool:
    if path.suffix not in exts:
        return False

    for part in path.parts:
        if part in IGNORE_DIRS:
            return False

    return True


def _scan_files(root: Path, exts: Set[str]) -> Dict[str, str]:
    """Return {relative_path: md5} for all trackable files under root."""

    result = {}

    try:
        for p in root.rglob("*"):
            if p.is_file() and _should_track(p.relative_to(root), exts):
                rel = str(p.relative_to(root)).replace("\\", "/")

                result[rel] = _file_md5(p)

    except (OSError, PermissionError):
        pass

    return result


def _hash_changed_since(
    root: Path, snapshot_files: Dict[str, str], exts: Set[str]
) -> Dict[str, List[str]]:
    current = _scan_files(root, exts)

    snap_keys = set(snapshot_files.keys())

    cur_keys = set(current.keys())

    added = [f for f in cur_keys - snap_keys]

    deleted = [f for f in snap_keys - cur_keys]

    modified = [f for f in snap_keys & cur_keys if snapshot_files[f] != current[f]]

    return {"added": added, "modified": modified, "deleted": deleted}


# ─── Snapshot persistence ─────────────────────────────────────────────────────


def _load_snapshot(project: str) -> Optional[Dict[str, Any]]:
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    try:
        with open(_snapshot_file(), "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support per-project snapshots stored in a dict keyed by project

        if project in data:
            return data[project]

        # Legacy: single snapshot

        if es_del(data.get("project")):
            return data

        return None

    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _save_snapshot(project: str, snapshot: Dict[str, Any]) -> None:
    _snapshot_file().parent.mkdir(parents=True, exist_ok=True)

    # Load existing multi-project file if present

    try:
        with open(_snapshot_file(), "r", encoding="utf-8") as f:
            all_snaps = json.load(f)

        if not isinstance(all_snaps, dict) or "project" in all_snaps:
            all_snaps = {}

    except (FileNotFoundError, json.JSONDecodeError):
        all_snaps = {}

    all_snaps[project] = snapshot

    # atomic_write_* y no `open(..., "w")`: el escaneo de secretos, el
    # saneado de encoding y el temp+replace viven ahí. Escribir en crudo los
    # esquivaba los tres (AP-36) y dejaba la nota a medias si el proceso moría.
    atomic_write_json(_snapshot_file(), all_snaps)


# ─── Vault cross-reference ────────────────────────────────────────────────────


def _load_code_index() -> List[Dict]:
    code_index_path = _raiz() / "11_Code" / ".code-index.json"

    try:
        with open(code_index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("modules", [])

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_search_index() -> List[Dict]:
    search_index_path = _raiz() / "99_Index" / "search-index.json"

    try:
        with open(search_index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("notes", [])

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None

    ts = ts.replace("Z", "+00:00")

    try:
        # Con zona siempre: un vault ajeno escribe `updatedAt: 2026-01-01`, y
        # compararla con el `since` del snapshot lanzaba TypeError (regla 7).
        return _en_utc(datetime.fromisoformat(ts))

    except ValueError:
        try:
            return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            return None


def _find_coverage(
    changed_files: List[str],
    project: str,
    since_timestamp: str,
) -> Tuple[List[Dict], List[Dict]]:
    """

    Cross-reference changed files against vault.

    Returns (documented, undocumented) lists.

    """

    modules = _load_code_index()

    notes = _load_search_index()

    since_dt = _parse_iso(since_timestamp)

    # Build lookup: file stem/path → vault entries

    # code-index: filePath field

    code_index_map: Dict[str, Dict] = {}

    for mod in modules:
        fp = mod.get("filePath", "")

        if fp:
            code_index_map[fp] = mod

            code_index_map[Path(fp).stem.lower()] = mod

            code_index_map[Path(fp).name.lower()] = mod

    # search-index: look for filename stem in note title or path

    def _note_covers_file(note: Dict, file_stem: str, file_name: str) -> bool:
        title = note.get("title", "").lower()

        path = note.get("path", "").lower()

        preview = note.get("preview", "").lower()

        return (
            file_stem in title
            or file_name in title
            or file_stem in path
            or file_stem in preview
        )

    documented = []

    undocumented = []

    for f in changed_files:
        fp = Path(f)

        stem = fp.stem.lower()

        name = fp.name.lower()

        # Skip files that don't need documentation

        if fp.suffix in SKIP_DOC_EXTENSIONS:
            continue

        if any(part in IGNORE_DIRS for part in fp.parts):
            continue

        if any(frag in f for frag in SKIP_PATH_FRAGMENTS):
            continue

        # Check code-index first (most precise)

        code_entry = code_index_map.get(f) or code_index_map.get(stem)

        if code_entry:
            entry_ts = code_entry.get("updatedAt", "")

            entry_dt = _parse_iso(entry_ts)

            is_recent = since_dt is None or entry_dt is None or entry_dt >= since_dt

            if is_recent:
                documented.append(
                    {
                        "file": f,
                        "vault_path": code_entry.get("relPath", "11_Code/"),
                        "source": "code-index",
                        "updatedAt": entry_ts,
                    }
                )

                continue

        # Check search-index

        matching_notes = [n for n in notes if _note_covers_file(n, stem, name)]

        recent_notes = []

        if since_dt:
            recent_notes = [
                n
                for n in matching_notes
                if _parse_iso(n.get("updatedAt", ""))
                and _parse_iso(n.get("updatedAt", "")) >= since_dt
            ]

        else:
            recent_notes = matching_notes

        if recent_notes:
            best = recent_notes[0]

            documented.append(
                {
                    "file": f,
                    "vault_path": best.get("path", ""),
                    "source": "search-index",
                    "updatedAt": best.get("updatedAt", ""),
                }
            )

        else:
            # Determine suggestion

            suggestion = "vault_write"

            for group in DOC_SUGGESTIONS.values():
                if fp.suffix in group["exts"]:
                    suggestion = group["tool"]

                    break

            undocumented.append(
                {
                    "file": f,
                    "suggestion": suggestion,
                }
            )

    return documented, undocumented


# ─── AP-08: notas que no acompañaron al cambio ───────────────────────────────

#: Estados canónicos (`STATUS_VOCAB`) cuyo contenido ya no se afirma vigente:
#: que su código cambie después es lo esperado, no un desfase. Una nota
#: reemplazada se reconoce por `superseded_by:`, que no es un `status`.
_ESTADOS_SIN_VIGENCIA = frozenset({"deprecated", "obsolete", "archived", "stub", "template"})


def _en_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Una fecha sin zona (`updatedAt: 2026-01-01`) se lee en UTC: comparar
    una ingenua con una con zona lanza TypeError."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _ultimo_cambio(repo: Path, ficheros: List[str]) -> Optional[Dict[str, str]]:
    """El commit más reciente que tocó alguno de `ficheros` en `repo`."""
    try:
        r = vault_subproceso.ejecutar(
            ["git", "log", "-1", "--format=%H%x09%cI", "--", *ficheros],
            cwd=str(repo), capture_output=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    linea = (r.stdout or "").strip() if r.returncode == 0 else ""
    if not linea:
        return None
    commit, fecha = linea.split("\t", 1)
    return {"commit": commit, "fecha": fecha}


def _codigo_inexistente(repo: Path, ficheros: List[str]) -> List[str]:
    """AP-01, la parte decidible: los `files:` que no existen en el repo.

    Una nota que declara documentar un fichero ausente describe código que no
    existe. Se mira el disco y no git: un fichero sin commit existe aunque
    `_ultimo_cambio` no lo encuentre, y uno borrado del disco ya no es código
    del repo aunque su historia siga ahí. Lo que la nota afirme en prosa no se
    mide —eso no es decidible sin interpretarla.
    """
    ausentes = []
    for f in ficheros:
        destino = (repo / f).resolve()
        try:
            destino.relative_to(repo)
        except ValueError:
            # Fuera del repo no es una afirmación sobre su código.
            continue
        if not destino.exists():
            ausentes.append(f)
    return ausentes


#: Una ruta de código citada entre backticks en el cuerpo: al menos una
#: carpeta y una extensión de código. Sin carpeta (`pago.py`) no se mide: el
#: nombre suelto no dice desde dónde resolverlo.
_RE_RUTA_EN_PROSA = re.compile(
    r"`((?:\./)?[\w.@-]+(?:/[\w.@-]+)+\."
    r"(?:py|pyi|ts|tsx|js|jsx|mjs|cjs|go|rs|java|kt|cs|swift|rb|php|c|h|cpp"
    r"|vue|svelte|sh|ps1|sql|ya?ml|toml))(?::\d+)?`"
)
_RE_BLOQUE_DE_CODIGO = re.compile(r"```[\s\S]*?```")
#: Clases de documento (`vault_registry.SECTION_DOCUMENTACION`) que cuentan lo
#: que había en su fecha o navegan: no afirman que el código siga ahí.
_CLASES_SIN_AFIRMACION = frozenset({"registro", "indice"})
#: Carpetas que no son código del repo al buscar un nombre de fichero.
_PODAR_AL_BUSCAR = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__"})


def _nombres_de_fichero(repo: Path) -> Set[str]:
    """Los nombres de fichero del repo, para separar «otra base» de «no existe»."""
    nombres: Set[str] = set()
    for _dir, carpetas, ficheros in os.walk(repo):
        carpetas[:] = [c for c in carpetas if c not in _PODAR_AL_BUSCAR]
        nombres.update(ficheros)
    return nombres


def _prosa_inexistente(
    repo: Path, raiz: Path, texto: str, nombres: Set[str]
) -> Tuple[List[str], int]:
    """AP-01 en prosa: (rutas citadas que no existen, rutas de base ambigua).

    Lo que va en un bloque de código muestra, no afirma, y se quita antes.
    Una ruta ausente cuyo nombre de fichero sí está en otro sitio del repo
    se cuenta como base ambigua y no se nombra: con la base equivocada todo
    sale ausente, que es lo que la regla 7 midió en `files:` y la `pista`
    ya advierte.
    """
    inexistentes: List[str] = []
    ambiguas = 0
    vistas: Set[str] = set()
    for m in _RE_RUTA_EN_PROSA.finditer(_RE_BLOQUE_DE_CODIGO.sub("", texto)):
        ruta = m.group(1)
        if ruta in vistas:
            continue
        vistas.add(ruta)
        if _codigo_inexistente(repo, [ruta]) == [] or (raiz / ruta).exists():
            continue
        if Path(ruta).name in nombres:
            ambiguas += 1
        else:
            inexistentes.append(ruta)
    return inexistentes, ambiguas


# ─── AP-08 en el cuerpo: `version_pinned` frente al manifiesto ──────────────

_REQUISITO = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")
_NUMERO_DE_VERSION = re.compile(r"\d+(?:\.\d+)*")


def _clave_de_paquete(nombre: str) -> str:
    """El nombre normalizado como lo compara PEP 503: `FastAPI` y `fast_api`
    son el mismo paquete. Los nombres de npm ya van en minúsculas y sin `_`,
    así que la misma normalización no los confunde."""
    return re.sub(r"[-_.]+", "-", str(nombre).strip()).lower()


def _requisito(linea: str) -> Optional[Tuple[str, str]]:
    """`FastAPI[all]>=0.110 ; python_version>'3.8'` → `("FastAPI", ">=0.110")`."""
    linea = linea.split("#", 1)[0].split(";", 1)[0].strip()
    if not linea or linea.startswith("-"):
        return None
    m = _REQUISITO.match(linea)
    return (m.group(1), m.group(2).strip()) if m else None


def versiones_del_manifiesto(repo: Path) -> Dict[str, Any]:
    """Las versiones que declaran los manifiestos de la **raíz** del repo.

    `package.json` (la versión del propio paquete y sus cuatro tablas de
    dependencias), `pyproject.toml` (`[project]` y `[tool.poetry]`) y
    `requirements*.txt`. Gana el primero que nombra un paquete, en ese orden.
    Un manifiesto en una subcarpeta no se busca: el repo declarado es la raíz,
    como para `files:`. `vault_onboard` lee los mismos ficheros para nombres y
    framework, no versiones; no es el mismo criterio.
    """
    versiones: Dict[str, Dict[str, str]] = {}
    leidos: List[str] = []
    no_leidos: List[Dict[str, str]] = []

    def anotar(nombre: Any, spec: Any, fuente: str) -> None:
        if nombre and isinstance(spec, (str, int, float)):
            versiones.setdefault(_clave_de_paquete(str(nombre)),
                                 {"manifiesto": str(spec).strip(), "fuente": fuente})

    pj = repo / "package.json"
    if pj.is_file():
        try:
            datos = json.loads(pj.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            no_leidos.append({"fuente": "package.json", "motivo": type(exc).__name__})
        else:
            leidos.append("package.json")
            anotar(datos.get("name"), datos.get("version"), "package.json")
            for tabla in ("dependencies", "devDependencies", "peerDependencies",
                          "optionalDependencies"):
                for nombre, spec in (datos.get(tabla) or {}).items():
                    anotar(nombre, spec, "package.json")
    pp = repo / "pyproject.toml"
    if pp.is_file():
        try:
            import tomllib  # 3.11+: con >=3.9 el fichero se declara no leído
        except ImportError:
            tomllib = None
        if tomllib is None:
            no_leidos.append({"fuente": "pyproject.toml",
                              "motivo": "tomllib no está en este Python (<3.11)"})
        else:
            try:
                datos = tomllib.loads(pp.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                no_leidos.append({"fuente": "pyproject.toml", "motivo": type(exc).__name__})
            else:
                leidos.append("pyproject.toml")
                proyecto = datos.get("project") or {}
                anotar(proyecto.get("name"), proyecto.get("version"), "pyproject.toml")
                reqs = list(proyecto.get("dependencies") or [])
                for grupo in (proyecto.get("optional-dependencies") or {}).values():
                    reqs.extend(grupo or [])
                for linea in reqs:
                    r = _requisito(str(linea))
                    if r:
                        anotar(r[0], r[1], "pyproject.toml")
                poetry = (datos.get("tool") or {}).get("poetry") or {}
                anotar(poetry.get("name"), poetry.get("version"), "pyproject.toml")
                for nombre, spec in (poetry.get("dependencies") or {}).items():
                    if isinstance(spec, dict):
                        spec = spec.get("version")
                    anotar(nombre, spec, "pyproject.toml")
    for req in sorted(repo.glob("requirements*.txt")):
        try:
            lineas = req.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            no_leidos.append({"fuente": req.name, "motivo": type(exc).__name__})
            continue
        leidos.append(req.name)
        for linea in lineas:
            r = _requisito(linea)
            if r:
                anotar(r[0], r[1], req.name)
    return {"versiones": versiones, "leidos": leidos, "no_leidos": no_leidos}


def _numeros(version: Any) -> Optional[Tuple[int, ...]]:
    m = _NUMERO_DE_VERSION.search(str(version))
    return tuple(int(x) for x in m.group(0).split(".")) if m else None


def _pin_anclado(fijada: Any, manifiesto: str) -> Optional[bool]:
    """True si la versión fijada ya no es la del manifiesto; None si no se compara.

    Se compara la primera versión numérica de cada lado hasta la precisión del
    más corto: `react: 18` sigue al día con `^18.2.0`, y `17.0.2` no. El
    operador del manifiesto (`^`, `>=`, `~=`) no se interpreta: la versión
    que escribe es la que el repo usa como referencia, y adivinar qué resuelve
    un rango sería instalarlo.
    """
    a, b = _numeros(fijada), _numeros(manifiesto)
    if a is None or b is None:
        return None
    k = min(len(a), len(b))
    return a[:k] != b[:k]


def vault_drift_vigencia(path: str, project: str) -> Dict[str, Any]:
    """AP-08: notas del proyecto cuyo código cambió después de su `updatedAt`.

    La señal es la que el manifiesto escribe desde v19 —«el `updatedAt` de la
    nota es muy anterior al de los archivos de código relacionados»— y que
    ninguna tool medía. La relación nota → código no se adivina por el nombre
    del fichero, como hace `report`: la declara la nota en `files:`, el mismo
    campo que lee `vault_arquitectura_en`. Una nota sin `files:` no se juzga;
    se cuenta, para que el silencio no pase por vigencia.

    AP-01 en prosa (v41.3): las rutas de código citadas entre backticks en el
    cuerpo que no existen salen en `prosa_inexistente`, fuera de
    `action_required` —informa, no exige: la regla 7 dio ausencias reales
    junto a rutas de otro repo indistinguibles—. Las notas de clase
    `registro`/`indice` y la documentación del estándar no se miden.

    Solo lectura: ni el vault ni el repo se tocan.
    """
    repo = Path(path).resolve()
    if not _has_git(repo):
        return emit_error(
            "vault_drift_detect", "GIT_UNAVAILABLE",
            f"--mode vigencia necesita un repo git: {repo.name} no lo es",
            pista="La fecha del último cambio de un fichero la da su historia; "
                  "sin git no hay de dónde leerla.",
        )
    from vault.kernel.fallos import FalloDeDominio

    try:
        secciones = _repo().ctx.secciones.ordenadas()
    except FalloDeDominio as fallo:
        return emit_fallo("vault_drift_detect", fallo)
    raiz = _raiz()
    # El predicado único de pertenencia (AP-63, P3), no un `==` propio.
    es_del = _proyectos.pertenencia_en(raiz, project)
    desfasadas: List[Dict[str, Any]] = []
    vigentes = 0
    sin_files: List[str] = []
    sin_historia: List[Dict[str, Any]] = []
    codigo_inexistente: List[Dict[str, Any]] = []
    prosa_inexistente: List[Dict[str, Any]] = []
    prosa_base_ambigua = 0
    nombres: Optional[Set[str]] = None
    resueltos = 0
    # AP-08 en el cuerpo: el universo se publica entero, también vacío (AP-60).
    manifiesto: Optional[Dict[str, Any]] = None
    pin_declaran = 0
    pin_comparadas = 0
    pin_ancladas: List[Dict[str, Any]] = []
    pin_sin_comparar: List[Dict[str, Any]] = []
    pin_ilegibles: List[str] = []
    for nota in sorted(notas_en_disco(raiz, secciones, incluir_indices=False)):
        rel = nota.relative_to(raiz).as_posix()
        if is_snapshot_path(rel):
            continue
        try:
            texto = nota.read_text(encoding="utf-8-sig")
            fm = parse_frontmatter(texto)
        except (OSError, UnicodeDecodeError):
            continue
        if not es_del(fm.get("project")):
            continue
        if fm.get("superseded_by"):
            continue
        if normalize_status(str(fm.get("status") or ""))[0] in _ESTADOS_SIN_VIGENCIA:
            continue
        if (section_documentacion(rel) not in _CLASES_SIN_AFIRMACION
                and not es_documentacion_del_estandar(rel, texto)):
            if nombres is None:
                nombres = _nombres_de_fichero(repo)
            ausentes_prosa, ambiguas = _prosa_inexistente(repo, raiz, texto, nombres)
            prosa_base_ambigua += ambiguas
            if ausentes_prosa:
                prosa_inexistente.append({"path": rel, "norm": "AP-01",
                                          "inexistentes": ausentes_prosa})
        if "version_pinned" in fm:
            pin_declaran += 1
            pins = fm.get("version_pinned")
            if not es_mapa_de_versiones(pins):
                pin_ilegibles.append(rel)
            else:
                if manifiesto is None:
                    manifiesto = versiones_del_manifiesto(repo)
                anclados: List[Dict[str, Any]] = []
                sin_comparar: List[str] = []
                comparada = False
                for paquete, fijada in pins.items():
                    dato = manifiesto["versiones"].get(_clave_de_paquete(str(paquete)))
                    veredicto = None if dato is None else _pin_anclado(fijada, dato["manifiesto"])
                    if veredicto is None:
                        sin_comparar.append(str(paquete))
                        continue
                    comparada = True
                    if veredicto:
                        anclados.append({"paquete": str(paquete), "fijada": str(fijada),
                                         "manifiesto": dato["manifiesto"],
                                         "fuente": dato["fuente"]})
                pin_comparadas += comparada
                if anclados:
                    pin_ancladas.append({"path": rel, "norm": "AP-08", "paquetes": anclados})
                if sin_comparar:
                    pin_sin_comparar.append({"path": rel, "paquetes": sin_comparar})
        files = fm.get("files")
        if isinstance(files, str):
            files = [files]
        files = [str(f).strip() for f in (files or []) if str(f).strip()]
        if not files:
            sin_files.append(rel)
            continue
        # La nota acompaña a su código desde la última vez que alguien la tocó
        # o comprobó que seguía siendo cierta: `revisado_en` (contrato v41)
        # deja rastro de una revisión que no cambió el texto.
        escrita = _en_utc(_parse_iso(str(fm.get("updatedAt") or fm.get("createdAt") or "")))
        revisada = _en_utc(_parse_iso(str(fm.get("revisado_en") or "")))
        nota_dt = max((f for f in (escrita, revisada) if f is not None), default=None)
        ausentes = _codigo_inexistente(repo, files)
        resueltos += len(files) - len(ausentes)
        if ausentes:
            codigo_inexistente.append({"path": rel, "norm": "AP-01",
                                       "inexistentes": ausentes})
        cambio = _ultimo_cambio(repo, files)
        if cambio is None:
            # Un `files:` que git no conoce —renombrado, borrado o mal
            # escrito— no es una nota vigente: es una relación rota.
            sin_historia.append({"path": rel, "files": files})
            continue
        cambio_dt = _en_utc(_parse_iso(cambio["fecha"]))
        if nota_dt is None or (cambio_dt is not None and cambio_dt > nota_dt):
            desfasadas.append({
                "path": rel,
                "updatedAt": fm.get("updatedAt"),
                "revisado_en": fm.get("revisado_en"),
                "files": files,
                "ultimo_cambio": cambio["fecha"],
                "commit": cambio["commit"],
            })
        else:
            vigentes += 1
    resultado: Dict[str, Any] = {
        "ok": True,
        "mode": "vigencia",
        "norm": "AP-08",
        "project": project,
        "desfasadas": desfasadas,
        "summary": {
            "desfasadas": len(desfasadas),
            "vigentes": vigentes,
            "sin_files": len(sin_files),
            "sin_historia": len(sin_historia),
            "codigo_inexistente": len(codigo_inexistente),
            "prosa_inexistente": len(prosa_inexistente),
            "prosa_base_ambigua": prosa_base_ambigua,
        },
        "sin_files": sin_files,
        "sin_historia": sin_historia,
        "codigo_inexistente": codigo_inexistente,
        "prosa_inexistente": prosa_inexistente,
        "version_pinned": {
            "norm": "AP-08",
            "declaran": pin_declaran,
            "comparadas": pin_comparadas,
            "ancladas": pin_ancladas,
            "sin_comparar": pin_sin_comparar,
            "ilegibles": pin_ilegibles,
            "manifiestos": (manifiesto or {}).get("leidos", []),
            "manifiestos_no_leidos": (manifiesto or {}).get("no_leidos", []),
            "universo": (
                f"{pin_declaran} notas declaran `version_pinned`; "
                f"{pin_comparadas} se compararon con el manifiesto." if pin_declaran else
                "ninguna nota declara `version_pinned`: cero ancladas no dice que el "
                "cuerpo esté al día, dice que no hay nada que comparar (AP-60)."
            ),
            "criterio": (
                "Cada `paquete: versión` de `version_pinned` se compara con la versión "
                "que declara el manifiesto de la raíz del repo, hasta la precisión del "
                "más corto; distinta, la nota está anclada a una versión que ya pasó. "
                "Un paquete fuera de todo manifiesto, o sin número de versión, se lista "
                "en `sin_comparar` y no se juzga."
            ),
        },
        "action_required": bool(desfasadas or sin_historia or codigo_inexistente
                                or pin_ancladas),
        "criterio": (
            "Una nota con `files:` está desfasada si algún fichero cambió en git "
            "después de su `updatedAt`. Sin `files:` no se juzga; un `files:` "
            "sin historia en git se lista aparte. Un `files:` que no existe en "
            "el disco del repo es AP-01: la nota describe código "
            "inexistente."
        ),
    }
    if codigo_inexistente and resueltos == 0:
        # Medido en la regla 7: con la base equivocada, todo `files:` sale
        # ausente. La lista se publica igual; la pista dice qué mirar antes.
        resultado["pista"] = (
            "Ningún `files:` existe bajo la ruta medida: comprueba que `--path` "
            "es la carpeta desde la que la nota escribe sus rutas antes de dar "
            "por inexistente el código."
        )
    return resultado


# ─── Main tool function ───────────────────────────────────────────────────────


def vault_drift_detect(
    path: str,
    project: str,
    mode: str = "report",
    extensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    scan_path = Path(path).resolve()

    if not scan_path.exists():
        return emit_error("vault_drift_detect", "FILE_NOT_FOUND", f"Path not found: {path}")

    if mode == "vigencia":
        return vault_drift_vigencia(str(scan_path), project)

    exts = set(extensions) if extensions else TRACK_EXTENSIONS

    use_git = _has_git(scan_path)

    # ── SNAPSHOT mode ─────────────────────────────────────────────────────────

    if mode == "snapshot":
        now = utcnow()

        snapshot: Dict[str, Any] = {
            "project": project,
            "path": str(scan_path),
            "timestamp": now,
            "git": use_git,
        }

        if use_git:
            commit = _git_head_commit(scan_path)

            snapshot["git_commit"] = commit

            snapshot["files"] = {}  # git tracks changes — no hash needed

        else:
            files = _scan_files(scan_path, exts)

            snapshot["git_commit"] = None

            snapshot["files"] = files

        _save_snapshot(project, snapshot)

        # La ficha guarda el punto, no la ruta: sin ficha no se anota nada.
        ficha = None
        if snapshot.get("git_commit"):
            ficha = _proyectos.anotar_repo(
                _raiz(), project, atomic_write_text,
                synced_commit=snapshot["git_commit"], synced_at=now[:10])

        return {
            "ok": True,
            "mode": "snapshot",
            "project": project,
            "path": str(scan_path),
            "timestamp": now,
            "backend": "git" if use_git else "hash",
            "git_commit": snapshot.get("git_commit"),
            "synced_commit_recorded_in": ficha,
            "files_tracked": len(snapshot.get("files", {}))
            if not use_git
            else "git-managed",
            "message": "Snapshot saved. Run with --mode report at end of session.",
        }

    # ── STATUS / REPORT mode ──────────────────────────────────────────────────

    snap = _load_snapshot(project)

    if snap is None and not use_git:
        return {
            **emit_error("vault_drift_detect", "DRIFT_SNAPSHOT_MISSING",
                         "No snapshot found and repo has no git. Run --mode snapshot first."),
            # Sin la ruta del repo (S4): con el proyecto enlazado no hace falta,
            # y sin enlazar la pide MISSING_REQUIRED_ARG con su propia pista.
            "hint": f'python vault_drift_detect.py --project "{project}" --mode snapshot',
        }

    since_timestamp = snap["timestamp"] if snap else utcnow()

    if use_git:
        since_commit = snap.get("git_commit") if snap else None

        changes = _git_changed_since(scan_path, since_commit)

        backend = "git"

    else:
        changes = _hash_changed_since(scan_path, snap.get("files", {}), exts)

        backend = "hash"

    all_changed = changes["added"] + changes["modified"]

    total_changed = len(all_changed) + len(changes["deleted"])

    if mode == "status":
        return {
            "ok": True,
            "mode": "status",
            "project": project,
            "backend": backend,
            "since": since_timestamp,
            "added": changes["added"],
            "modified": changes["modified"],
            "deleted": changes["deleted"],
            "total_changed": total_changed,
        }

    # mode == "report"

    documented, undocumented = _find_coverage(all_changed, project, since_timestamp)

    coverage_pct = (
        round(len(documented) / len(all_changed) * 100) if all_changed else 100
    )

    result: Dict[str, Any] = {
        "ok": True,
        "mode": "report",
        "project": project,
        "backend": backend,
        "since": since_timestamp,
        "summary": {
            "total_changed": total_changed,
            "added": len(changes["added"]),
            "modified": len(changes["modified"]),
            "deleted": len(changes["deleted"]),
            "documented": len(documented),
            "undocumented": len(undocumented),
            "coverage_pct": coverage_pct,
        },
        "documented": documented,
        "undocumented": undocumented,
        "deleted": changes["deleted"],
    }

    if undocumented:
        result["action_required"] = True

        result["message"] = (
            f"{len(undocumented)} file(s) changed without vault documentation. "
            f"Coverage: {coverage_pct}%."
        )

    else:
        result["action_required"] = False

        result["message"] = (
            f"All {len(documented)} changed file(s) are documented. Coverage: 100%."
        )

    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Vault Drift Detect Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_drift_detect.py --path "src/" --project "ans" --mode snapshot

  python vault_drift_detect.py --path "src/" --project "ans" --mode report

  python vault_drift_detect.py --path "src/" --project "ans" --mode status

  python vault_drift_detect.py --path "C:/repos/mi-api" --project "mi-api" --mode snapshot --extensions .py .js .ts



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Flujo: tomar snapshot al inicio -> report al final de sesion

  - Soporta repos git (usa git diff) y directorios sin git (hash-based)

  - mode=report cruza cambios con el vault para detectar que no fue documentado

""",
        allow_abbrev=False,
    )

    parser.add_argument("--path", help="Project root path to scan (por defecto, el enlazado con vault_project --link)")

    parser.add_argument("--project", type=proyecto_registrado("vault_drift_detect"), required=True, help="Project slug")

    parser.add_argument(
        "--mode",
        choices=["snapshot", "status", "report", "vigencia"],
        default="report",
        help="snapshot: save baseline | status: list changes | report: changes + vault coverage"
        " | vigencia: notas con `files:` cuyo codigo cambio despues de su updatedAt (AP-08)",
    )

    parser.add_argument(
        "--extensions",
        nargs="*",
        help="File extensions to track (e.g. .py .js .ts). Default: all code/config extensions.",
    )

    args = parser.parse_args()

    ruta = args.path
    if not ruta:
        enlazada = _proyectos.ruta_local(_raiz(), args.project)
        if enlazada is None:
            print(json.dumps(emit_error(
                "vault_drift_detect", "MISSING_REQUIRED_ARG",
                f"--path no se dio y {args.project} no tiene repo enlazado",
                pista=f"python vault_project.py --link {args.project} --path <repo>",
            ), indent=2, ensure_ascii=False))
            return 1
        ruta = str(enlazada)

    result = vault_drift_detect(ruta, args.project, args.mode, args.extensions)

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_drift_detect"))
