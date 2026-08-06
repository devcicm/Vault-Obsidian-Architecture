#!/usr/bin/env python3
"""
vault_onboard.py v2 — Onboard completo de proyecto existente al vault.

Cubre las 12 secciones activas del vault y construye historial de desarrollo
desde git log (o mtime de archivos si no hay git).

Estrategias de sección:
  01_Projects   — overview con fechas git, contributors, versiones
  02_Observability — TODO/FIXME/HACK/BUG detectados en código fuente
  03_Decisions  — ADRs retroactivos desde commits arquitectónicos
  04_Sessions   — una nota por fase temporal del proyecto (antes/después)
  05_Patterns   — patrones inferidos por naming de archivos
  06_Diagrams   — arquitectura Mermaid desde estructura src/
  07_Knowledge  — conceptos desde README headers + dependencias clave
  08_Runbooks   — scripts npm/Makefile/CI → runbooks
  09_Infrastructure — Docker, env vars, BD schemas
  11_Code       — stubs por módulo detectado (priorizado por tipo)
  13_Flows      — GitHub Actions / CI workflows → flujos
  14_Requirements — README features/stories → reqs
  15_Tests      — inventario de test files por tipo

Idempotencia: si el archivo ya existe en vault → merge (añade secciones faltantes).
Historia: git disponible → git log + tags; sin git → mtime/ctime de archivos.

Usage:
    python vault_onboard.py --project my-api --path ../my-api
    python vault_onboard.py --project my-api --path . --lang typescript --dry-run
    python vault_onboard.py --project my-api --path . --skip 02 05 --no-git
"""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import wrap_main
from vault_lib import slugify_strict, utcnow
from vault_io import VAULT_ROOT, assert_within_vault, atomic_write_text, normalize_stem
from vault_norms import compute_norm_refs
from vault_registry import ORDERED_SECTIONS
from vault_write import _deduce_type_from_folder

#: Secciones que un onboard NO puebla, con el motivo de cada una. Se derivan
#: restándolas de `ORDERED_SECTIONS`, para que una sección nueva del registro
#: entre sola en el recorrido en vez de quedarse fuera en silencio — que es
#: como `vault_folder_registry` se quedó en 13 de 22 durante nueve secciones.
#: Las tres primeras están dirigidas por eventos: llenarlas al arrancar sería
#: inventar bugs, auditorías y cuarentenas que no han ocurrido (AP-45).
_SECCIONES_NO_POBLADAS: Dict[str, str] = {
    "00_System": "la crea y la mantiene vault_init, no el onboard",
    "10_Migrated": "la puebla vault_migrate_docs, que corre antes que esto",
    "99_Index": "la generan los índices, no se escribe a mano",
    "12_Bibliography": "se puebla con referencias externas reales",
    "18_Bugs": "se puebla cuando aparece un bug (vault_bug_save)",
    "19_Audits": "se puebla al ejecutar una auditoría (vault_tags --audit)",
    "20_Quarantine": "se puebla cuando algo entra en cuarentena",
}

# ── Language / extension maps ─────────────────────────────────────────────────

LANG_BY_EXT: Dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".kt": "kotlin",
    ".swift": "swift",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
}

SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "out",
    "bin",
    "obj",
    "__pycache__",
    ".venv",
    "venv",
    "vendor",
    "third_party",
    ".idea",
    ".vscode",
    "coverage",
    ".nyc_output",
    "vault-backups",
    "scripts",
}

SKIP_DIRS_TEST = {"test", "tests", "spec", "specs", "__tests__", "e2e", "fixtures"}

MODULE_TYPE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"service", re.I), "service"),
    (re.compile(r"controller|handler|route", re.I), "controller"),
    (re.compile(r"repository|store|dao|gateway", re.I), "repository"),
    (re.compile(r"model|entity|schema|dto", re.I), "model"),
    (re.compile(r"middleware|interceptor|guard|filter", re.I), "middleware"),
    (re.compile(r"util|helper|common|shared", re.I), "utility"),
    (re.compile(r"config|settings|constant", re.I), "config"),
    (re.compile(r"manager|coordinator|orchestrat", re.I), "manager"),
    (re.compile(r"provider|factory|builder", re.I), "factory"),
    (re.compile(r"interface|type|protocol", re.I), "interface"),
]

MODULE_PRIORITY = [
    "service",
    "controller",
    "repository",
    "manager",
    "model",
    "middleware",
    "factory",
    "interface",
    "utility",
    "config",
]

DECISION_KEYWORDS = re.compile(
    r"\b(migrat|replace|switch\s+to|adopt|refactor|rewrite|use\s+\w+|"
    r"move\s+to|upgrade|downgrade|architecture|ADR|decision|breaking)\b",
    re.I,
)

TODO_PATTERN = re.compile(
    r"(?://|#|<!--|/\*)\s*(TODO|FIXME|BUG|HACK|XXX)\s*:?\s*(.{0,120})",
    re.I,
)

TEST_PATTERNS = [
    (re.compile(r"\.test\.", re.I), "unit"),
    (re.compile(r"\.spec\.", re.I), "unit"),
    (re.compile(r"__tests__", re.I), "unit"),
    (re.compile(r"integration", re.I), "integration"),
    (re.compile(r"e2e|end.to.end", re.I), "e2e"),
    (re.compile(r"performance|load|stress", re.I), "performance"),
    (re.compile(r"security|penetr|pentest", re.I), "security"),
    (re.compile(r"acceptance|acceptance", re.I), "acceptance"),
]


# ── Utilities ─────────────────────────────────────────────────────────────────


#: Alias del slug canónico. No lleva implementación propia: la que tenía
#: (`[^a-z0-9]+`) borraba los acentos en vez de transliterarlos y producía
#: `caracter-sticas-principales` a partir de «Características principales».
_slug = slugify_strict


def _date_str(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


def _month_key(date_str: str) -> str:
    return date_str[:7]  # YYYY-MM


#: Pasos de detección que fallaron en este onboarding. Ver `_registrar_degradacion`.
_DETECCION_DEGRADADA: List[Dict[str, str]] = []


def _registrar_degradacion(paso: str, exc: BaseException) -> None:
    """Anota que un paso de detección no pudo completarse, en vez de olvidarlo.

    Once sitios hacían `except Exception: pass` sobre una lectura del proyecto —el
    `docker-compose.yml`, el `.csproj`, el README, el log de git—. Seguir sin ese
    dato es correcto: un onboarding no puede abortar porque un fichero esté
    bloqueado o venga en una codificación rara. **Lo que no es correcto es que el
    vault resultante no distinga «el proyecto no tiene infraestructura» de «no
    pude leer la que tiene»**, y hasta ahora escribía lo primero en los dos casos.
    Una nota que afirma una ausencia que nunca se comprobó es peor que un hueco:
    el hueco se ve.

    Sale en `degraded[]` del envelope, junto a `skipped_no_evidence` y
    `sections_left_empty_by_design` — las tres responden a la misma pregunta, qué
    NO está en el vault y por qué (AP-37, AP-45).
    """
    _DETECCION_DEGRADADA.append({"step": paso, "error": f"{type(exc).__name__}: {exc}"})


def _run_git(project_path: Path, args: List[str], timeout: int = 10) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_path)] + args,
            capture_output=True,
            timeout=timeout,
        )
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", errors="replace").strip()
    except Exception as exc:
        _registrar_degradacion("leer_git", exc)
        return None


def _infer_module_type(filename: str) -> str:
    stem = Path(filename).stem
    for pattern, mtype in MODULE_TYPE_PATTERNS:
        if pattern.search(stem):
            return mtype
    return "module"


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except Exception as exc:
        _registrar_degradacion("contar_commits", exc)
        return 0


# ── Git history ───────────────────────────────────────────────────────────────

SNAP_BRANCH_PATTERN = re.compile(
    r"\b(snap|snapshot|backup|archive|bk|old|fork|copy|clone|save|freeze|"
    r"preserved?|legacy|history|original|before|prior|stable)\b",
    re.I,
)


def _parse_commits(raw: str) -> List[Dict[str, Any]]:
    """Parsea `%H|%ai|%s|%an`.

    El asunto del commit es el ÚNICO campo que puede contener el separador, así
    que se acota por los dos extremos: hash y fecha por la izquierda, autor por
    la derecha, y lo de en medio es el mensaje entero venga como venga. Con un
    `split(maxsplit=3)` un commit como «fix: contain | validated responsive»
    partía por el pipe y el autor salía como `validated responsive|Carlos Ivan
    CM` — un contribuidor inventado en la lista de contribuidores del proyecto.
    """
    commits = []
    for line in raw.splitlines():
        cabeza = line.split("|", 2)
        if len(cabeza) != 3:
            continue
        hash_, fecha, resto = cabeza
        if "|" in resto:
            mensaje, autor = resto.rsplit("|", 1)
        else:
            mensaje, autor = resto, ""
        commits.append(
            {
                "hash": hash_[:8],
                "date": fecha[:10],
                "message": mensaje.strip(),
                "author": autor.strip(),
            }
        )
    return commits


def _scan_all_branches(project_path: Path) -> List[Dict[str, Any]]:
    """List all local + remote branches with their oldest commit date."""
    branches_raw = (
        _run_git(
            project_path,
            ["branch", "-a", "--format=%(refname:short)|%(objectname:short)"],
        )
        or ""
    )
    branches = []
    for line in branches_raw.splitlines():
        parts = line.strip().split("|", 1)
        if not parts[0]:
            continue
        name = parts[0].strip()
        if "HEAD" in name:
            continue
        # Get oldest commit on this branch (not reachable from others)
        oldest_raw = (
            _run_git(
                project_path,
                ["log", name, "--pretty=format:%ai|%s", "--reverse", "-n1"],
            )
            or ""
        )
        newest_raw = (
            _run_git(
                project_path,
                ["log", name, "--pretty=format:%ai", "-n1"],
            )
            or ""
        )
        count_raw = (
            _run_git(
                project_path,
                ["rev-list", "--count", name],
            )
            or "0"
        )
        oldest_date = oldest_raw.split("|")[0][:10] if oldest_raw else ""
        is_snap = bool(SNAP_BRANCH_PATTERN.search(name))
        branches.append(
            {
                "name": name,
                "oldest_date": oldest_date,
                "newest_date": newest_raw[:10],
                "commit_count": int(count_raw.strip())
                if count_raw.strip().isdigit()
                else 0,
                "is_snap_branch": is_snap,
            }
        )
    return branches


def _extract_git_history(project_path: Path, max_commits: int = 500) -> Dict[str, Any]:
    check = _run_git(project_path, ["rev-parse", "--is-inside-work-tree"])
    if check != "true":
        return {"is_git": False}

    # Current branch name
    current_branch = _run_git(project_path, ["branch", "--show-current"]) or "HEAD"

    # ── Full log across ALL branches (--all) ──────────────────────────────────
    log_raw = (
        _run_git(
            project_path,
            ["log", "--all", f"--pretty=format:%H|%ai|%s|%an", f"-n{max_commits}"],
        )
        or ""
    )
    commits_all = _parse_commits(log_raw)

    # Current branch log (for apparent age)
    log_current = (
        _run_git(
            project_path,
            ["log", f"--pretty=format:%H|%ai|%s|%an", f"-n{max_commits}"],
        )
        or ""
    )
    commits_current = _parse_commits(log_current)

    # ── Reflog (catches orphan / pre-rebase / detached HEAD history) ──────────
    reflog_raw = (
        _run_git(
            project_path,
            ["reflog", "--pretty=format:%H|%ai|%gs|%an", f"-n{min(max_commits, 300)}"],
        )
        or ""
    )
    reflog_commits = []
    known_hashes = {c["hash"] for c in commits_all}
    for line in reflog_raw.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4 and parts[0][:8] not in known_hashes:
            reflog_commits.append(
                {
                    "hash": parts[0][:8],
                    "date": parts[1][:10],
                    "message": f"[reflog] {parts[2].strip()}",
                    "author": parts[3].strip(),
                    "source": "reflog",
                }
            )

    # ── Stash list ────────────────────────────────────────────────────────────
    stash_raw = (
        _run_git(
            project_path,
            ["stash", "list", "--pretty=format:%gd|%ai|%s"],
        )
        or ""
    )
    stashes = []
    for line in stash_raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            stashes.append(
                {"ref": parts[0], "date": parts[1][:10], "message": parts[2].strip()}
            )

    # ── All branches with dates ───────────────────────────────────────────────
    branches = _scan_all_branches(project_path)
    snap_branches = [b for b in branches if b["is_snap_branch"]]

    # ── Tags ─────────────────────────────────────────────────────────────────
    tags_raw = (
        _run_git(
            project_path,
            [
                "tag",
                "-l",
                "--sort=version:refname",
                "--format=%(refname:short)|%(creatordate:short)",
            ],
        )
        or ""
    )
    tags = []
    for line in tags_raw.splitlines():
        parts = line.split("|", 1)
        if len(parts) == 2 and parts[1].strip():
            tags.append({"name": parts[0], "date": parts[1].strip()[:10]})

    # ── True vs apparent age ──────────────────────────────────────────────────
    # Merge all known commit dates (all branches + reflog)
    all_dates = [c["date"] for c in commits_all + reflog_commits if c.get("date")]
    for b in branches:
        if b.get("oldest_date"):
            all_dates.append(b["oldest_date"])

    true_first_date = min(all_dates) if all_dates else ""
    apparent_first_date = (
        commits_current[-1]["date"] if commits_current else true_first_date
    )

    hidden_history = False
    hidden_months = 0
    if (
        true_first_date
        and apparent_first_date
        and true_first_date < apparent_first_date
    ):
        try:
            t = datetime.fromisoformat(true_first_date)
            a = datetime.fromisoformat(apparent_first_date)
            hidden_months = max(0, (a.year - t.year) * 12 + (a.month - t.month))
            hidden_history = hidden_months > 1
        except Exception as exc:
            _registrar_degradacion("fechar_historia_oculta", exc)
            pass

    contributors = list(
        dict.fromkeys(c["author"] for c in commits_all if c.get("author"))
    )
    key_commits = [
        c for c in commits_all if DECISION_KEYWORDS.search(c.get("message", ""))
    ][:10]

    # Build unified commit list: all_branches + reflog for phase detection
    all_commits_unified = commits_all + reflog_commits
    all_commits_unified.sort(key=lambda c: c.get("date", ""), reverse=True)

    # Tope declarado, no silencioso. `git log -n500` sobre un repo de 2.000
    # commits devuelve 500 y ningún aviso: la tool informaba `total_commits:
    # 500` con `warnings: []` y detectaba UNA fase sobre cinco meses de
    # historia, porque los commits antiguos —los que separan las fases— eran
    # justo los cortados. La cifra parecía un hecho del proyecto y era un
    # parámetro de la invocación.
    ventana_truncada = len(commits_all) >= max_commits
    avisos: List[str] = []
    if ventana_truncada:
        avisos.append(
            f"La historia se leyó con --max-commits={max_commits} y se alcanzó el "
            f"tope: hay commits anteriores sin mirar, así que `total_commits` es "
            "el tope y no el total, y las fases detectadas cubren solo esa "
            "ventana. Repite con --max-commits mayor para la historia completa."
        )

    return {
        "is_git": True,
        "current_branch": current_branch,
        "window_truncated": ventana_truncada,
        "max_commits": max_commits,
        "warnings": avisos,
        "first_commit": {"date": true_first_date, "message": "", "author": ""},
        "last_commit": commits_all[0] if commits_all else None,
        "apparent_first_date": apparent_first_date,
        "true_first_date": true_first_date,
        "hidden_history": hidden_history,
        "hidden_months": hidden_months,
        "total_commits": len(commits_all),
        "total_commits_with_reflog": len(all_commits_unified),
        "contributors": contributors[:8],
        "tags": tags,
        "commits": all_commits_unified,  # unified for phase detection
        "commits_current": commits_current,  # current branch only
        "key_commits": key_commits,
        "branches": branches,
        "snap_branches": snap_branches,
        "stashes": stashes,
        "reflog_extra_commits": len(reflog_commits),
    }


def _extract_file_history(project_path: Path) -> Dict[str, Any]:
    relevant_exts = set(LANG_BY_EXT.keys())
    files = []
    for f in project_path.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in relevant_exts:
            continue
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        try:
            stat = f.stat()
            files.append(
                {
                    "path": str(f.relative_to(project_path)).replace("\\", "/"),
                    "ctime": stat.st_ctime,
                    "mtime": stat.st_mtime,
                    "date": _date_str(stat.st_mtime)[:10],
                }
            )
        except Exception as exc:
            _registrar_degradacion("datar_ficheros", exc)
            pass

    files.sort(key=lambda x: x["ctime"])
    return {
        "is_git": False,
        "first_file": {
            "path": files[0]["path"],
            "date": _date_str(files[0]["ctime"])[:10],
        }
        if files
        else None,
        "last_modified": {
            "path": files[-1]["path"],
            "date": _date_str(files[-1]["mtime"])[:10],
        }
        if files
        else None,
        "files": files,
        "commits": [],
        "tags": [],
        "contributors": [],
        "key_commits": [],
    }


def _detect_phases(
    history: Dict[str, Any], max_phases: int = 8
) -> List[Dict[str, Any]]:
    """Cluster git commits (or file mtimes) into phases by month."""
    if history["is_git"]:
        items = [
            {"date": c["date"], "message": c["message"], "author": c.get("author", "")}
            for c in history.get("commits", [])
        ]
    else:
        items = [
            {"date": f["date"][:10], "message": f["path"], "author": ""}
            for f in history.get("files", [])
        ]

    if not items:
        return []

    # Group by month
    by_month: Dict[str, List] = defaultdict(list)
    for item in items:
        key = item["date"][:7]
        by_month[key].append(item)

    months = sorted(by_month.keys())

    # Un tag es el proyecto declarando «aquí pasó algo». Es la mejor evidencia
    # de frontera que existe, y mejor que el calendario: el hueco de meses solo
    # detecta el abandono, así que un proyecto en desarrollo continuo salía
    # SIEMPRE como una sola fase —626 commits y seis meses comprimidos en una
    # nota de sesión, con cinco tags que marcaban los hitos siendo ignorados
    # para partir y usados solo para etiquetar—.
    meses_con_tag = {t["date"][:7] for t in history.get("tags", []) if t.get("date")}

    # Merge close months — if gap ≤ 1 month, keep as same phase
    phases = []
    current: List[str] = []
    for i, month in enumerate(months):
        if i == 0:
            current = [month]
        else:
            prev_year, prev_mon = int(months[i - 1][:4]), int(months[i - 1][5:7])
            cur_year, cur_mon = int(month[:4]), int(month[5:7])
            gap = (cur_year - prev_year) * 12 + (cur_mon - prev_mon)
            if gap <= 1 and month not in meses_con_tag:
                current.append(month)
            else:
                phases.append(current)
                current = [month]
    if current:
        phases.append(current)

    # Limit
    phases = phases[-max_phases:]

    # Build phase descriptors
    result = []
    tag_dates = {t["date"][:7]: t["name"] for t in history.get("tags", [])}

    for idx, group in enumerate(phases):
        all_items = []
        for m in group:
            all_items.extend(by_month[m])

        first_date = group[0] + "-01"
        last_date = group[-1] + "-28"

        # Find tag in this period
        tag_label = next((tag_dates[m] for m in group if m in tag_dates), None)

        if idx == 0:
            label = tag_label or "Fase inicial"
        elif tag_label:
            label = tag_label
        else:
            label = f"Fase {idx + 1}"

        # Top messages
        highlights = list(
            dict.fromkeys(i["message"] for i in all_items if i["message"])
        )[:5]

        # Most active authors
        authors = list(
            dict.fromkeys(i["author"] for i in all_items if i.get("author"))
        )[:3]

        result.append(
            {
                "label": label,
                "label_slug": _slug(label),
                "month_start": group[0],
                "month_end": group[-1],
                "first_date": first_date,
                "last_date": last_date,
                "item_count": len(all_items),
                "highlights": highlights,
                "authors": authors,
                "tag": tag_label,
                "is_first": idx == 0,
                "is_last": idx == len(phases) - 1,
            }
        )

    return result


# ── Project meta ──────────────────────────────────────────────────────────────


def _read_package_json(project_path: Path) -> Dict[str, Any]:
    pj = project_path / "package.json"
    if not pj.exists():
        return {}
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        all_deps = deps + dev_deps
        framework = ""
        for d in all_deps:
            if d == "electron":
                framework = "Electron"
            elif d == "next":
                framework = "Next.js"
            elif d == "react":
                framework = framework or "React"
            elif d == "vue":
                framework = framework or "Vue"
            elif d == "@nestjs/core":
                framework = "NestJS"
            elif d in ("express", "fastify", "koa"):
                framework = framework or d.capitalize()
        node_ver = data.get("engines", {}).get("node", "")
        return {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "version": data.get("version", ""),
            "runtime": f"Node.js {node_ver}".strip(),
            "framework": framework,
            "scripts": data.get("scripts", {}),
            "key_deps": deps[:15],
            "all_deps": all_deps,
            "source": "package.json",
        }
    except Exception as exc:
        _registrar_degradacion("leer_manifiesto_de_dependencias", exc)
        return {}


def _read_pyproject(project_path: Path) -> Dict[str, Any]:
    for fname in ("pyproject.toml", "setup.cfg", "setup.py"):
        fp = project_path / fname
        if not fp.exists():
            continue
        try:
            text = fp.read_text(encoding="utf-8")
            name = re.search(r'name\s*=\s*["\']([^"\']+)', text)
            desc = re.search(r'description\s*=\s*["\']([^"\']+)', text)
            ver = re.search(r'version\s*=\s*["\']([^"\']+)', text)
            return {
                "name": name.group(1) if name else "",
                "description": desc.group(1) if desc else "",
                "version": ver.group(1) if ver else "",
                "runtime": "Python",
                "framework": "",
                "source": fname,
                "scripts": {},
                "key_deps": [],
                "all_deps": [],
            }
        except Exception as exc:
            _registrar_degradacion("leer_manifiesto_python", exc)
            continue
    return {}


def _read_csproj(project_path: Path) -> Dict[str, Any]:
    for csproj in list(project_path.rglob("*.csproj"))[:3]:
        try:
            text = csproj.read_text(encoding="utf-8", errors="replace")
            framework = re.search(r"<TargetFramework>([^<]+)", text)
            return {
                "name": csproj.stem,
                "description": "",
                "version": "",
                "runtime": "dotnet",
                "framework": framework.group(1) if framework else "",
                "source": csproj.name,
                "scripts": {},
                "key_deps": [],
                "all_deps": [],
            }
        except Exception as exc:
            _registrar_degradacion("leer_csproj", exc)
            continue
    return {}


#: Título H1 del README leído. Se guarda para poder contrastarlo con el nombre
#: del proyecto: el README es la fuente de la descripción y de las notas de
#: conocimiento, así que si describe otra cosa, TODO lo derivado describe otra
#: cosa. Es el caso real de BuilderX, cuyo repositorio contiene en la raíz una
#: copia del README del estándar: 8 conceptos correctos sobre el proyecto
#: equivocado, que es la clase de error que nadie revisa porque parece contenido.
_README_H1: List[str] = []


def _read_readme(project_path: Path) -> Tuple[str, List[str]]:
    """Returns (excerpt, list_of_H2_headers).

    El README se lee del proyecto escaneado y de ningún otro sitio: se resuelve
    la ruta y se comprueba que cuelga de `project_path` antes de leerla, porque
    un enlace simbólico o un `--path` relativo mal resuelto metía la descripción
    de otro proyecto en la nota de overview —y una descripción equivocada es
    peor que ninguna: nadie la revisa, porque parece contenido—.

    `utf-8-sig` en vez de `utf-8`: el BOM que Windows antepone se colaba como
    primer carácter de `description:` y viajaba al frontmatter.
    """
    project_path = project_path.resolve()
    for fname in ("README.md", "Readme.md", "readme.md"):
        fp = project_path / fname
        if not fp.exists():
            continue
        try:
            if fp.resolve().parent != project_path:
                continue  # symlink fuera del proyecto: no es su README
            text = fp.read_text(encoding="utf-8-sig", errors="replace")
            _README_H1.clear()
            h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if h1:
                _README_H1.append(h1.group(1).strip())
            headers = re.findall(r"^## (.+)$", text, re.MULTILINE)
            lines = [
                l for l in text.splitlines() if l.strip() and not l.startswith("#")
            ]
            return " ".join(lines)[:500], headers
        except Exception as exc:
            _registrar_degradacion("leer_readme", exc)
            pass
    return "", []


def _detect_project_meta(
    project_path: Path, lang_hint: Optional[str]
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    for reader in (_read_package_json, _read_pyproject, _read_csproj):
        result = reader(project_path)
        if result:
            meta.update(result)
            break

    meta["readme_excerpt"], meta["readme_headers"] = _read_readme(project_path)

    if lang_hint:
        meta["language"] = lang_hint
    elif not meta.get("language"):
        ext_counts: Dict[str, int] = {}
        for f in project_path.rglob("*"):
            if f.is_file() and not any(p in SKIP_DIRS for p in f.parts):
                lang = LANG_BY_EXT.get(f.suffix.lower())
                if lang:
                    ext_counts[lang] = ext_counts.get(lang, 0) + 1
        if ext_counts:
            meta["language"] = max(ext_counts, key=ext_counts.get)

    return meta


# ── Module scanner ────────────────────────────────────────────────────────────


def _scan_modules(
    project_path: Path, depth: int, language: str, max_modules: int
) -> List[Dict]:
    relevant_exts = {
        ext for ext, lang in LANG_BY_EXT.items() if lang == language
    } or set(LANG_BY_EXT.keys())
    found = []

    def _scan(dir_path: Path, d: int) -> None:
        if d > depth:
            return
        try:
            entries = sorted(dir_path.iterdir())
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if entry.name.lower() in SKIP_DIRS | SKIP_DIRS_TEST:
                    continue
                _scan(entry, d + 1)
            elif entry.is_file() and entry.suffix.lower() in relevant_exts:
                rel = str(entry.relative_to(project_path)).replace("\\", "/")
                found.append(
                    {
                        "name": entry.stem,
                        "file_path": rel,
                        "type": _infer_module_type(entry.name),
                        "size_lines": _count_lines(entry),
                        "slug": _slug(entry.stem),
                    }
                )

    _scan(project_path, 0)

    def _priority(m: Dict) -> Tuple[int, int]:
        try:
            return (MODULE_PRIORITY.index(m["type"]), -m["size_lines"])
        except ValueError:
            return (len(MODULE_PRIORITY), -m["size_lines"])

    found.sort(key=_priority)

    # Deduplicar con el criterio del vault, no con el del sistema de ficheros.
    # `BrowserManager.ts` y `browser-manager.ts` son dos ficheros distintos para
    # el disco y la MISMA nota para Obsidian —`normalize_stem` es lo que ya usa
    # el resto del estándar para decidirlo—. Sin esto el onboard escribía
    # `11_Code/x/browsermanager.md` y `browser-manager.md`: dos notas para un
    # módulo, cada una con la mitad de los enlaces entrantes.
    #
    # Se queda la de mayor prioridad, que es la primera tras el sort: el orden
    # ya expresa cuál de las dos describe mejor el módulo.
    unicos: List[Dict] = []
    vistos: set = set()
    for m in found:
        clave = normalize_stem(m["slug"])
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(m)

    return unicos[:max_modules]


# ── Infrastructure scanner ────────────────────────────────────────────────────


def _detect_infra(project_path: Path) -> Dict[str, Any]:
    infra: Dict[str, Any] = {
        "services": [],
        "envs": [],
        "ports": [],
        "files": [],
        "base_image": "",
    }
    for fname in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        fp = project_path / fname
        if not fp.exists():
            continue
        infra["files"].append(fname)
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            infra["services"].extend(
                re.findall(r"^\s{2}(\w[\w-]+):\s*$", text, re.MULTILINE)
            )
            infra["ports"].extend(re.findall(r'"?(\d+:\d+)"?', text)[:10])
        except Exception as exc:
            _registrar_degradacion("leer_docker_compose", exc)
            pass
    for df in ("Dockerfile", "Dockerfile.dev", "Dockerfile.prod"):
        if (project_path / df).exists():
            infra["files"].append(df)
            try:
                text = (project_path / df).read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^FROM\s+(\S+)", text, re.MULTILINE)
                if m:
                    infra["base_image"] = m.group(1)
                infra["ports"].extend(
                    re.findall(r"^EXPOSE\s+(\d+)", text, re.MULTILINE)
                )
            except Exception as exc:
                _registrar_degradacion("leer_dockerfile", exc)
                pass
    for ef in (".env.example", ".env.local", ".env.sample", ".env.template"):
        fp = project_path / ef
        if fp.exists():
            infra["files"].append(ef)
            try:
                keys = [
                    l.split("=")[0].strip()
                    for l in fp.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    if l.strip() and not l.startswith("#") and "=" in l
                ]
                infra["envs"].extend(keys[:20])
            except Exception as exc:
                _registrar_degradacion("leer_env_example", exc)
                pass
    for ci_dir in (".github/workflows", ".circleci", "Jenkinsfile", ".gitlab-ci.yml"):
        if (project_path / ci_dir).exists():
            infra["files"].append(str(ci_dir))
    return infra


# ── Merge helper ──────────────────────────────────────────────────────────────


def _existing_h2_sections(text: str) -> set:
    return set(re.findall(r"^## (.+)$", text, re.MULTILINE))


def _verificar_releyendo(vault_path: Path) -> None:
    """Relee del disco y valida el frontmatter con el criterio del consumidor.

    Corolario de AP-44 aplicado al generador: esta tool construye el
    frontmatter a mano, concatenando líneas. Verificar que la concatenación
    salió bien mirando las líneas que acaba de concatenar no verifica nada —el
    error estaría en los dos lados—. Lo que decide es si `yaml.safe_load` lo
    lee, que es lo que hacen Obsidian y el resto del estándar, y si trae los
    campos que `vault_audit` exige.

    Falla ruidosamente: una nota con frontmatter ilegible es peor que ninguna
    nota, porque el siguiente write path le antepone un segundo bloque.
    """
    import yaml

    texto = vault_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", texto, re.DOTALL)
    if not m:
        raise ValueError(f"{vault_path.name}: se escribió sin frontmatter delimitado")
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"{vault_path.name}: frontmatter ilegible para YAML: {exc}")
    if not isinstance(fm, dict):
        raise ValueError(f"{vault_path.name}: el frontmatter no es un mapa YAML")
    faltan = [c for c in ("title", "type", "status", "tags", "updatedAt") if not fm.get(c)]
    if faltan:
        raise ValueError(f"{vault_path.name}: frontmatter sin {faltan}")


def _merge_stub(vault_path: Path, new_content: str, dry_run: bool) -> str:
    """
    Create the file if missing. If it exists, append only missing ## sections.
    Returns: 'created' | 'merged' | 'skipped' | 'dry_run'
    """
    if dry_run:
        return "dry_run"

    vault_path.parent.mkdir(parents=True, exist_ok=True)
    assert_within_vault(vault_path, VAULT_ROOT)

    if not vault_path.exists():
        atomic_write_text(vault_path, new_content)
        _verificar_releyendo(vault_path)
        return "created"

    existing = vault_path.read_text(encoding="utf-8", errors="replace")
    existing_sections = _existing_h2_sections(existing)

    # Extract ## sections from new_content
    section_pattern = re.compile(r"^(## .+?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    new_sections = section_pattern.findall(new_content)

    to_add = []
    for section in new_sections:
        header = re.match(r"^## (.+)", section)
        if header and header.group(1) not in existing_sections:
            to_add.append(section.strip())

    if not to_add:
        return "skipped"

    merged = existing.rstrip() + "\n\n" + "\n\n".join(to_add) + "\n"
    atomic_write_text(vault_path, merged)
    _verificar_releyendo(vault_path)
    return "merged"


# ── Frontmatter ───────────────────────────────────────────────────────────────


def _make_frontmatter(
    title: str,
    folder: str,
    tags: List[str],
    extra: Dict[str, Any],
    content: str,
) -> str:
    now = utcnow()
    norm_refs = compute_norm_refs(folder, content, [])
    # `type:` lo exige `vault_audit._detect_missing_metadata`, y sin él las 54
    # notas de un onboard nacían en `missingType`: el estándar reprobaba lo que
    # su propia tool acababa de escribir. No se declara aquí una tabla nueva
    # —eso sería una segunda verdad— sino que se deriva del mismo mapa
    # sección→tipo que usa el write path canónico.
    tipo = extra.get("type") or _deduce_type_from_folder(folder)
    lines = [
        "---",
        f"title: {title}",
        f"id: {uuid.uuid4()}",
        f"type: {tipo}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(tags)}",
        f"norm_refs: {json.dumps(norm_refs)}",
        "status: stub",
        f"cia_integrity: {extra.get('cia_integrity', 'medium')}",
        f"cia_availability: {extra.get('cia_availability', 'medium')}",
        f"cia_sensitivity: {extra.get('cia_sensitivity', 'internal')}",
        f"agent: {extra.get('agent', 'claude')}",
    ]
    skip = {"cia_integrity", "cia_availability", "cia_sensitivity", "agent", "type"}
    for k, v in extra.items():
        if k not in skip:
            lines.append(f"{k}: {json.dumps(v) if not isinstance(v, str) else v}")
    lines.append("---")
    return "\n".join(lines)


#: Notas que el onboard no escribió por falta de evidencia (AP-45). Se vacía al
#: principio de cada `vault_onboard()` y sale en `warnings` y `next_steps`: el
#: hueco declarado es información; el stub que lo tapa es desinformación.
_SIN_EVIDENCIA: List[Dict[str, str]] = []


def _tiene_evidencia(body: str) -> bool:
    """¿El cuerpo afirma algo, o es andamiaje anunciando lo que no hay?

    Mismo criterio exacto que aplica AP-45 en `vault_norms --audit`, importado
    en vez de reimplementado: si el generador midiera con un criterio propio y
    el audit con otro, la tool volvería a certificarse a sí misma (AP-44) y el
    vault recién creado saldría reprobado por el estándar que lo creó.
    """
    from vault_lib import extract_wikilinks
    from vault_norms import _cuerpo_sin_marcadores

    return bool(extract_wikilinks(body) or _cuerpo_sin_marcadores(body))


#: Prefijo de commit convencional: `feat(scope):`, `fix:`, `chore:`… Es
#: metadato de proceso, no nombre de decisión.
_PREFIJO_CONVENCIONAL = re.compile(
    r"^\s*(?:feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)"
    r"(?:\([^)]*\))?!?\s*:\s*",
    re.IGNORECASE,
)


def _asunto_util(mensaje: str) -> str:
    """El asunto del commit si nombra algo; cadena vacía si no.

    Quita el prefijo convencional y descarta los asuntos que no distinguen un
    commit de otro (`wip`, `fix`, `update`, `cambios`). Sin esto, cinco ADRs
    salían como `adr-002-retroactivo` … `adr-006-retroactivo`: numerados,
    indistinguibles y sin decir qué se decidió — AP-07.
    """
    asunto = _PREFIJO_CONVENCIONAL.sub("", (mensaje or "").splitlines()[0] if mensaje else "")
    asunto = asunto.strip().strip(".").strip()
    vacios = {
        "wip", "fix", "fixes", "update", "updates", "cambios", "cambio", "misc",
        "minor", "cleanup", "tweaks", "stuff", "varios", "ajustes", "test",
    }
    if len(asunto) < 12 or asunto.lower() in vacios:
        return ""
    return asunto


def _errores_mermaid(diagrama: str) -> List[str]:
    """Errores de sintaxis según `vault_mermaid_check`, la gramática real.

    Se consulta al validador del estándar en vez de confiar en que el generador
    escribió bien —es AP-44: el generador y su comprobación serían el mismo
    criterio, ciego al mismo fallo—.
    """
    try:
        from vault_mermaid_check import validate_mermaid
    except ImportError:
        return []
    return [
        str(e.get("message") or e)
        for e in validate_mermaid(diagrama)
        if str(e.get("severity", "error")).lower() == "error"
    ]


def _write(
    folder: str,
    filename: str,
    title: str,
    tags: List[str],
    extra: Dict[str, Any],
    body: str,
    dry_run: bool,
) -> Tuple[str, str]:
    path = VAULT_ROOT / folder / filename
    rel = str(path.relative_to(VAULT_ROOT)).replace("\\", "/")

    # AP-45: no hay nota sin algo que afirmar. Un onboard sobre un proyecto real
    # emitía 8 conceptos cuyo cuerpo entero era `_Pendiente. Leer la sección del
    # README._`; para el conteo eran cobertura y para quien las abría eran nada.
    # No escribirlas no pierde información: la pierde escribirlas, porque una
    # sección vacía invita a llenarla y una llena de stubs declara que ya está.
    if not _tiene_evidencia(body):
        _SIN_EVIDENCIA.append({"path": rel, "title": title})
        return rel, "skipped_no_evidence"

    content = body
    fm = _make_frontmatter(title, folder, tags, extra, content)
    full = fm + "\n\n" + body
    action = _merge_stub(path, full, dry_run)
    return rel, action


# ── Section strategies ────────────────────────────────────────────────────────


def _onboard_01_projects(
    project: str,
    meta: Dict,
    history: Dict,
    phases: List[Dict],
    agent: str,
    dry_run: bool,
) -> List[Tuple[str, str]]:
    first = history.get("first_commit") or history.get("first_file")
    last = history.get("last_commit") or history.get("last_modified")
    tags = history.get("tags", [])
    contributors = history.get("contributors", [])
    is_git = history.get("is_git", False)
    history_source = "git log" if is_git else "mtime de archivos"

    runtime = meta.get("runtime", "")
    framework = meta.get("framework", "")
    runtime_str = f"{runtime} / {framework}".strip(" /") if framework else runtime
    description = (
        meta.get("description")
        or meta.get("readme_excerpt")
        or "_Pendiente de documentar._"
    )[:400]

    versions_md = (
        "\n".join(f"- `{t['name']}` — {t['date']}" for t in tags[:8])
        or "— Sin tags detectados"
    )
    contributors_md = (
        "\n".join(f"- {c}" for c in contributors) or "— Desconocidos (sin git)"
    )
    scripts_md = (
        "\n".join(
            f"- `{k}`: `{v}`" for k, v in list((meta.get("scripts") or {}).items())[:8]
        )
        or "— No detectados"
    )

    timeline_md = ""
    if phases:
        timeline_md = "\n## Línea de tiempo\n\n"
        for p in phases:
            marker = f" ({p['tag']})" if p.get("tag") else ""
            timeline_md += f"- **{p['month_start']}** — {p['label']}{marker}: {p['item_count']} commits\n"

    # Branch info
    hidden_history = history.get("hidden_history", False)
    true_first = history.get("true_first_date", "")
    apparent_first = history.get("apparent_first_date", "")
    snap_branches = history.get("snap_branches", [])
    branch_count = len(history.get("branches", []))
    stash_count = len(history.get("stashes", []))

    hidden_md = ""
    if hidden_history:
        hidden_md = f"""
## Advertencia: historia oculta detectada

| | |
|---|---|
| Antigüedad aparente | {apparent_first} |
| Antigüedad real (cross-branch) | {true_first} |
| Historia oculta | **{history.get("hidden_months", 0)} meses** |
| Ramas snap/backup | {len(snap_branches)} detectadas |

Ver ADR de arqueologia: [[adr-001-historia-oculta-branch-archaeology]]
"""

    branches_md = ""
    if branch_count > 1:
        snap_names = ", ".join(f"`{b['name']}`" for b in snap_branches[:4])
        branches_md = f"\n**Ramas totales:** {branch_count} | Snap/backup: {len(snap_branches)} ({snap_names or 'ninguna'})"

    body = f"""# {project} — Overview

> Stub generado por vault_onboard v2 — enriquecer con vault_project_overview.

## Descripción

{description}

## Stack detectado

| Campo | Valor |
|---|---|
| Runtime | {runtime_str or "—"} |
| Lenguaje | {meta.get("language") or "—"} |
| Framework | {meta.get("framework") or "—"} |
| Versión actual | {meta.get("version") or "—"} |
| Fuente | {meta.get("source") or "—"} |
| Historia desde | {history_source} |
{hidden_md}
## Historial del proyecto

| | |
|---|---|
| Primer commit/archivo (real) | {true_first or (first["date"] if first else "—")} |
| Primer commit (rama actual) | {apparent_first or "—"} |
| Último commit/archivo | {last["date"] if last else "—"} |
| Total commits (todas las ramas) | {history.get("total_commits", "—")} |
| Fases detectadas | {len(phases)} |
| Stashes pendientes | {stash_count} |
{branches_md}
{timeline_md}
## Versiones detectadas

{versions_md}

## Contribuidores

{contributors_md}

## Scripts disponibles

{scripts_md}

## Próximos pasos

- Verificar descripción y stack con el equipo
- {"Revisar historia oculta en [[adr-001-historia-oculta-branch-archaeology]]" if hidden_history else "Completar base de datos, caches, queues"}
- Revisar ADRs en [[03_Decisions/index]]
- Ver módulos en [[11_Code/index]]
"""
    return [
        _write(
            f"01_Projects/{project}",
            "overview.md",
            f"{project} — Overview",
            ["project", "overview", project],
            {
                "agent": agent,
                "project": project,
                # El fichero se llama `overview.md` —igual que el overview de
                # cualquier otro proyecto—, así que el resto de notas lo enlazan
                # como `[[<proyecto>-overview]]`, que es el nombre que lo
                # identifica. Obsidian resuelve por nombre de fichero y por
                # `aliases:`, nunca por `title:`: sin este alias los 8 enlaces
                # entrantes quedaban rotos para quien lee el vault y resueltos
                # para las tools, que es justo el fallo que castiga AP-44.
                "aliases": [f"{_slug(project)}-overview"],
            },
            body,
            dry_run,
        )
    ]


def _onboard_02_observability(
    project: str, project_path: Path, modules: List[Dict], agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    issues: Dict[str, List[Dict]] = {"high": [], "medium": [], "low": []}
    severity_map = {
        "FIXME": "high",
        "BUG": "high",
        "HACK": "medium",
        "TODO": "low",
        "XXX": "low",
    }

    for mod in modules[:30]:
        fp = project_path / mod["file_path"]
        if not fp.exists():
            continue
        try:
            for lineno, line in enumerate(
                fp.open(encoding="utf-8", errors="replace"), 1
            ):
                m = TODO_PATTERN.search(line)
                if m:
                    keyword = m.group(1).upper()
                    sev = severity_map.get(keyword, "low")
                    issues[sev].append(
                        {
                            "file": mod["file_path"],
                            "line": lineno,
                            "keyword": keyword,
                            "text": m.group(2).strip()[:100],
                        }
                    )
        except Exception:
            pass

    total = sum(len(v) for v in issues.values())
    if total == 0:
        return []

    def _issue_md(items: List[Dict]) -> str:
        return "\n".join(
            f"- `{i['file']}:{i['line']}` — **{i['keyword']}**: {i['text']}"
            for i in items[:15]
        )

    body = f"""# {project} — Deuda técnica detectada

> Generado por vault_onboard desde análisis estático de comentarios. Verificar manualmente.

**Total:** {total} items | High: {len(issues["high"])} | Medium: {len(issues["medium"])} | Low: {len(issues["low"])}

## Alta prioridad (FIXME / BUG)

{_issue_md(issues["high"]) or "— Ninguno detectado"}

## Media prioridad (HACK)

{_issue_md(issues["medium"]) or "— Ninguno detectado"}

## Baja prioridad (TODO / XXX)

{_issue_md(issues["low"]) or "— Ninguno detectado"}

## Siguiente acción

Revisar cada item y crear issue o registrar con vault_log_error.
"""
    return [
        _write(
            "02_Observability/issues",
            f"{_slug(project)}-debt.md",
            f"{project} — Deuda técnica detectada",
            ["observability", "debt", project],
            {"agent": agent, "project": project, "cia_integrity": "high"},
            body,
            dry_run,
        )
    ]


def _onboard_03_decisions(
    project: str, history: Dict, project_path: Path, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    adr_counter = [1]

    # ── Branch archaeology — historia oculta detectada ────────────────────────
    if history.get("hidden_history"):
        apparent = history.get("apparent_first_date", "—")
        true_start = history.get("true_first_date", "—")
        hidden_months = history.get("hidden_months", 0)
        snap_branches = history.get("snap_branches", [])
        all_branches = history.get("branches", [])
        current_branch = history.get("current_branch", "HEAD")
        reflog_extra = history.get("reflog_extra_commits", 0)

        snap_md = (
            "\n".join(
                f"- `{b['name']}` — oldest: {b['oldest_date']} | commits: {b['commit_count']}"
                for b in snap_branches
            )
            or "— No detectadas (historia encontrada via reflog o commits huérfanos)"
        )

        all_branches_md = (
            "\n".join(
                f"- `{b['name']}` — {b['oldest_date']} → {b['newest_date']} ({b['commit_count']} commits)"
                for b in sorted(all_branches, key=lambda x: x.get("oldest_date", ""))[
                    :12
                ]
            )
            or "— No detectadas"
        )

        body = f"""# ADR-{adr_counter[0]:03d} — Historia oculta detectada (branch archaeology)

> Generado por vault_onboard al detectar historia anterior a la rama actual.
> Esto indica que el proyecto existia antes del estado actual de la rama `{current_branch}`.

**Status:** critical-finding

## Hallazgo

| | |
|---|---|
| Antigüedad aparente (rama {current_branch}) | desde {apparent} |
| Antigüedad real (cross-branch) | desde {true_start} |
| Historia oculta | **{hidden_months} meses** no visibles en rama actual |
| Commits extra en reflog | {reflog_extra} |

## Ramas con historia antigua detectadas

{snap_md}

## Todas las ramas del repositorio

{all_branches_md}

## Qué pudo haber pasado

- Se creó un "snap" o backup de la rama main y se trabajó en una nueva rama desde ese punto
- La rama actual fue creada a partir de una exportacion / fork de la rama original
- Se hizo `git checkout --orphan` perdiendo la conexion con el historial anterior
- Los commits antiguos estan en ramas `snap-*`, `backup-*`, `archive-*` o similares

## Accion recomendada

1. Revisar cada rama snap/backup listada arriba con: `git log <rama> --oneline | head -20`
2. Si contiene historia util, documentar en 04_Sessions con las fechas reales
3. Considerar `git merge --allow-unrelated-histories <rama-antigua>` si corresponde
4. Actualizar overview del proyecto con la fecha real de inicio: {true_start}

## Para enriquecer

```bash
# Ver historial de una rama snap
git log <nombre-rama-snap> --oneline --graph | head -30

# Comparar ramas
git log {current_branch}...<nombre-rama-snap> --oneline
```
"""
        results.append(
            _write(
                "03_Decisions",
                f"{_slug(f'adr-{adr_counter[0]:03d}-historia-oculta-branch-archaeology')}.md",
                f"ADR-{adr_counter[0]:03d} — Historia oculta detectada (branch archaeology)",
                ["adr", "branch-archaeology", "historia-oculta", project],
                {"agent": agent, "project": project, "cia_integrity": "high"},
                body,
                dry_run,
            )
        )
        adr_counter[0] += 1

    # From key commits (decision keywords)
    for commit in history.get("key_commits", [])[:5]:
        # Un ADR se llama por lo que decidió. `adr-002-retroactivo` no nombra
        # nada: es AP-07, y en cuanto hay dos el nombre deja de distinguirlos.
        # El nombre sale del asunto del commit, que es lo único que se sabe.
        asunto = _asunto_util(commit.get("message", ""))
        if not asunto:
            _SIN_EVIDENCIA.append(
                {
                    "path": f"03_Decisions/adr-{adr_counter[0]:03d}",
                    "title": commit.get("message", "")[:60],
                    "reason": (
                        "el asunto del commit no describe una decisión "
                        "nombrable; queda en el historial, no como ADR"
                    ),
                }
            )
            continue

        title = f"ADR-{adr_counter[0]:03d} — {asunto[:60]} (retroactivo)"
        body = f"""# {title}

**Fecha detectada:** {commit["date"]} (commit `{commit.get("hash", "?")}`)
**Autor:** {commit.get("author", "—")}

## Contexto detectado

Commit: "{commit["message"]}"
Fuente: historial git del proyecto

## Decisión

Reconstruida del asunto del commit: {asunto}

El commit registra el cambio; la decisión que lo motivó no está escrita en
ningún sitio del proyecto. Esta nota nace `stub` a propósito: afirmar
`implemented` declararía una revisión que nadie hizo.

## Consecuencias

Sin verificar. Lo que consta es el cambio, no su efecto.

## Para enriquecer

```bash
python scripts/vault_write.py --folder 03_Decisions --title "{title}"
```
"""
        results.append(
            _write(
                "03_Decisions",
                f"{_slug(f'adr-{adr_counter[0]:03d}-{asunto[:48]}')}.md",
                title,
                ["adr", "retroactivo", project],
                {"agent": agent, "project": project},
                body,
                dry_run,
            )
        )
        adr_counter[0] += 1

    # From CHANGELOG.md / DECISIONS.md / ARCHITECTURE.md
    for fname in ("CHANGELOG.md", "DECISIONS.md", "ARCHITECTURE.md"):
        fp = project_path / fname
        if not fp.exists():
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            title = f"ADR-{adr_counter[0]:03d} — {fname} (retroactivo)"
            excerpt = text[:800].replace("---", "")
            body = f"""# {title}

**Fuente:** `{fname}` encontrado en el proyecto
**Status:** implemented

## Contenido detectado

```
{excerpt}
```

## Para enriquecer

Revisar el archivo y extraer ADRs individuales con vault_write.
"""
            results.append(
                _write(
                    "03_Decisions",
                    f"{_slug(f'adr-{adr_counter[0]:03d}-{fname}')}.md",
                    title,
                    ["adr", "retroactivo", project],
                    {"agent": agent, "project": project},
                    body,
                    dry_run,
                )
            )
            adr_counter[0] += 1
        except Exception:
            pass

    return results


def _onboard_04_sessions(
    project: str, phases: List[Dict], history: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    is_git = history.get("is_git", False)

    for phase in phases:
        month = phase["month_start"]
        label = phase["label"]
        slug_label = phase["label_slug"]
        highlights_md = (
            "\n".join(f"- {h}" for h in phase["highlights"][:5]) or "— Sin datos"
        )
        authors_md = (
            ", ".join(phase["authors"]) if phase["authors"] else "— Desconocidos"
        )
        tag_md = (
            f"\nVersión: **{phase['tag']}** (tag detectado)" if phase.get("tag") else ""
        )
        source_note = "git log" if is_git else "mtime de archivos"
        item_label = "Commits" if is_git else "Archivos modificados"

        status_notes = []
        if phase["is_first"]:
            status_notes.append("Inicio del proyecto")
        if phase["is_last"]:
            status_notes.append("Estado actual del proyecto")
        if phase.get("tag"):
            status_notes.append(f"Release: {phase['tag']}")
        status_str = " | ".join(status_notes) if status_notes else "Fase intermedia"

        body = f"""# {month} — {label}

> Fase del proyecto reconstruida desde {source_note}.

**Período:** {phase["first_date"]} → {phase["last_date"]}
**{item_label}:** {phase["item_count"]} | **Contribuidores:** {authors_md}
**Estado:** {status_str}{tag_md}

## Cambios destacados

{highlights_md}

## Notas

_Enriquecer con decisiones, incidentes o hitos relevantes de este período._

## Para documentar sesiones reales

```bash
python scripts/vault_write.py --folder 04_Sessions --title "{month} sesion de trabajo"
```
"""
        results.append(
            _write(
                "04_Sessions",
                f"{month}-{slug_label}.md",
                f"{month} — {label}",
                ["session", "historial", project, month[:4]],
                {"agent": agent, "project": project, "period": month},
                body,
                dry_run,
            )
        )

    return results


def _onboard_05_patterns(
    project: str, modules: List[Dict], agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    pattern_counts: Dict[str, int] = defaultdict(int)
    for mod in modules:
        pattern_counts[mod["type"]] += 1

    PATTERN_RULES = [
        (
            "service",
            2,
            "Service Layer",
            "architecture",
            "Separación de lógica de negocio en servicios",
        ),
        (
            "controller",
            1,
            "MVC / Layered",
            "architecture",
            "Separación de responsabilidades en capas",
        ),
        ("repository", 1, "Repository", "design", "Abstracción del acceso a datos"),
        ("factory", 1, "Factory", "design", "Creación de objetos encapsulada"),
        (
            "middleware",
            1,
            "Middleware Chain",
            "architecture",
            "Procesamiento encadenado de requests",
        ),
        (
            "manager",
            1,
            "Manager / Coordinator",
            "design",
            "Coordinación de múltiples servicios",
        ),
    ]

    results = []
    for mtype, min_count, pname, pcat, pdesc in PATTERN_RULES:
        if pattern_counts.get(mtype, 0) >= min_count:
            evidence = [m["file_path"] for m in modules if m["type"] == mtype][:5]
            evidence_md = "\n".join(f"- `{f}`" for f in evidence)
            body = f"""# {pname}

> Patrón detectado automáticamente por vault_onboard. Verificar implementación real.

**Categoría:** {pcat}
**Evidencia:** {pattern_counts[mtype]} archivos de tipo `{mtype}`

## Descripción

{pdesc}

## Archivos detectados

{evidence_md}

## Para enriquecer

```bash
python scripts/vault_pattern_save.py --project {project} --name "{_slug(pname)}" \\
  --pattern_type {pcat} --status implementado
```
"""
            results.append(
                _write(
                    f"05_Patterns/{pcat}",
                    f"{_slug(project)}-{_slug(pname)}.md",
                    pname,
                    ["pattern", pcat, project, mtype],
                    {"agent": agent, "project": project, "pattern_type": pcat},
                    body,
                    dry_run,
                )
            )

    return results


def _onboard_06_diagrams(
    project: str,
    project_path: Path,
    meta: Dict,
    modules: List[Dict],
    agent: str,
    dry_run: bool,
) -> List[Tuple[str, str]]:
    # Build Mermaid graph from module type groups
    groups: Dict[str, List[str]] = defaultdict(list)
    for mod in modules[:20]:
        groups[mod["type"]].append(mod["name"])

    # Identificador seguro + etiqueta legible. El nombre de un módulo real trae
    # puntos, guiones y mayúsculas (`BrowserManager.impl`), y ponerlo crudo como
    # id de nodo produce un diagrama que Mermaid no dibuja. El id se sanea; el
    # nombre de verdad va en la etiqueta, donde no rompe nada y sí se lee.
    def _nodo(texto: str) -> str:
        ident = re.sub(r"[^A-Za-z0-9_]", "_", texto).strip("_") or "n"
        if ident[0].isdigit():
            ident = f"n_{ident}"
        return f'{ident}["{texto}"]'

    mermaid_lines = ["graph TD"]
    for gtype, names in sorted(groups.items()):
        for name in names[:4]:
            mermaid_lines.append(f"  {_nodo(gtype)} --> {_nodo(name)}")
    mermaid = "\n".join(mermaid_lines)

    # AP-44: validar con la gramática real de Mermaid, no con la confianza de
    # quien generó el texto. El diagrama que no valida NO se escribe: una nota
    # de `06_Diagrams` cuyo bloque no dibuja es peor que su ausencia, porque el
    # índice la cuenta como diagrama y quien la abre ve un error de sintaxis.
    errores = _errores_mermaid(mermaid)
    if errores:
        _SIN_EVIDENCIA.append(
            {
                "path": f"06_Diagrams/component/{_slug(project)}-architecture.md",
                "title": f"{project} — Arquitectura de componentes",
                "reason": f"el diagrama generado no valida contra Mermaid: {errores[0]}",
            }
        )
        return []

    body = f"""# {project} — Arquitectura de componentes

> Diagrama generado por vault_onboard desde estructura de archivos. Verificar y ajustar.

**Lenguaje:** {meta.get("language", "—")}
**Framework:** {meta.get("framework", "—")}

## Diagrama

```mermaid
{mermaid}
```

## Para enriquecer

```bash
python scripts/vault_diagram_save.py --project {project} \\
  --title "Arquitectura {project}" --type mermaid --category component \\
  --content "..."
```
"""
    return [
        _write(
            "06_Diagrams/component",
            f"{_slug(project)}-architecture.md",
            f"{project} — Arquitectura de componentes",
            ["diagram", "architecture", project],
            {
                "agent": agent,
                "project": project,
                "diagramType": "mermaid",
                "category": "component",
            },
            body,
            dry_run,
        )
    ]


def _onboard_07_knowledge(
    project: str, meta: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    all_deps = meta.get("all_deps", [])

    # README headers → concepts
    SKIP_HEADERS = {
        "installation",
        "install",
        "usage",
        "license",
        "contributing",
        "changelog",
        "table of contents",
        "prerequisites",
        "getting started",
    }
    headers = [
        h for h in meta.get("readme_headers", []) if h.lower() not in SKIP_HEADERS
    ][:8]

    for header in headers:
        slug = _slug(header)
        body = f"""# {header}

> Concepto detectado en README del proyecto {project}. Pendiente de documentar.

**Proyecto:** {project}
**Fuente:** README.md — sección `## {header}`

## Descripción

_Pendiente. Leer la sección del README y documentar aquí._

## Referencias

- [[{_slug(project)}-overview]]
"""
        results.append(
            _write(
                "07_Knowledge/concepts",
                f"{slug}.md",
                header,
                ["concept", project, "readme"],
                {"agent": agent, "project": project, "category": "concept"},
                body,
                dry_run,
            )
        )

    # Key framework deps → framework entries
    KNOWN_FRAMEWORKS = {
        "electron",
        "react",
        "vue",
        "next",
        "express",
        "fastify",
        "koa",
        "@nestjs/core",
        "django",
        "flask",
        "fastapi",
        "spring",
        "rails",
    }
    frameworks_found = [d for d in all_deps if d.lower() in KNOWN_FRAMEWORKS][:4]
    for dep in frameworks_found:
        slug = _slug(dep.replace("@", "").replace("/", "-"))
        body = f"""# {dep}

> Dependencia clave detectada en {meta.get("source", "package.json")} del proyecto {project}.

**Tipo:** framework
**Proyecto que lo usa:** [[{_slug(project)}-overview]]

## Para documentar

```bash
python scripts/vault_knowledge_save.py --category framework \\
  --title "{dep}" --content "..." --project {project}
```
"""
        results.append(
            _write(
                "07_Knowledge/frameworks",
                f"{slug}.md",
                dep,
                ["framework", project, slug],
                {"agent": agent, "project": project, "category": "framework"},
                body,
                dry_run,
            )
        )

    return results[:15]


def _onboard_08_runbooks(
    project: str, meta: Dict, project_path: Path, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    scripts = meta.get("scripts", {})

    RUNBOOK_CATEGORY = {
        "dev": "setup",
        "start": "setup",
        "serve": "setup",
        "build": "pipeline",
        "compile": "pipeline",
        "bundle": "pipeline",
        "test": "debug",
        "lint": "debug",
        "typecheck": "debug",
        "deploy": "deploy",
        "release": "deploy",
        "migrate": "maintenance",
        "seed": "maintenance",
        "clean": "maintenance",
    }

    for script_name, script_cmd in list(scripts.items())[:8]:
        category = next(
            (
                cat
                for key, cat in RUNBOOK_CATEGORY.items()
                if key in script_name.lower()
            ),
            "maintenance",
        )
        body = f"""# npm run {script_name}

> Runbook generado por vault_onboard desde package.json. Verificar pasos reales.

**Trigger:** Ejecutar `{script_name}` del proyecto
**Categoría:** {category}
**Comando:** `{script_cmd[:200]}`

## Prerrequisitos

- [ ] Node.js instalado
- [ ] Dependencias instaladas: `npm install`

## Pasos

1. Abrir terminal en el directorio del proyecto
2. Ejecutar: `npm run {script_name}`

## Para enriquecer

```bash
python scripts/vault_runbook_save.py --project {project} \\
  --title "npm run {script_name}" --trigger "..." \\
  --category {category} --steps '[{{"step":"npm run {script_name}"}}]'
```
"""
        results.append(
            _write(
                f"08_Runbooks/{category}",
                f"{_slug(project)}-npm-{_slug(script_name)}.md",
                f"npm run {script_name}",
                ["runbook", category, project, "npm"],
                {
                    "agent": agent,
                    "project": project,
                    "category": category,
                    "cia_availability": "high",
                },
                body,
                dry_run,
            )
        )

    # Makefile targets
    makefile = project_path / "Makefile"
    if makefile.exists():
        try:
            text = makefile.read_text(encoding="utf-8", errors="replace")
            targets = re.findall(r"^([a-z][\w-]+)\s*:", text, re.MULTILINE)
            phony = (
                set(re.findall(r"^\.PHONY\s*:(.*)", text, re.MULTILINE)[0].split())
                if re.findall(r"^\.PHONY", text, re.MULTILINE)
                else set()
            )
            for target in [t for t in targets if t not in phony][:4]:
                body = f"""# make {target}

> Runbook generado por vault_onboard desde Makefile.

**Trigger:** `make {target}`
**Categoría:** pipeline

## Pasos

1. `make {target}`
"""
                results.append(
                    _write(
                        "08_Runbooks/pipeline",
                        f"{_slug(project)}-make-{_slug(target)}.md",
                        f"make {target}",
                        ["runbook", "make", project],
                        {"agent": agent, "project": project, "category": "pipeline"},
                        body,
                        dry_run,
                    )
                )
        except Exception:
            pass

    return results[:8]


def _onboard_09_infrastructure(
    project: str, infra: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    if not infra.get("files"):
        return []
    services_md = (
        "\n".join(f"- `{s}`" for s in infra.get("services", [])) or "— No detectados"
    )
    ports_md = (
        "\n".join(f"- `{p}`" for p in set(infra.get("ports", []))) or "— No detectados"
    )
    envs_md = "\n".join(f"- `{e}`" for e in infra.get("envs", [])) or "— No detectadas"
    files_md = "\n".join(f"- `{f}`" for f in infra.get("files", []))
    body = f"""# {project} — Infraestructura

> Stub generado por vault_onboard desde archivos de configuración.

## Archivos detectados

{files_md}

## Servicios (docker-compose)

{services_md}

## Puertos expuestos

{ports_md}

## Variables de entorno (.env)

{envs_md}

## Imagen base Docker

{infra.get("base_image") or "— No detectada"}

## Para enriquecer

```bash
python scripts/vault_infra_save.py --project {project} --component "..."
python scripts/vault_env_save.py --project {project} --env_file ".env"
```
"""
    return [
        _write(
            f"09_Infrastructure/{project}",
            "infra.md",
            f"{project} — Infraestructura",
            ["infrastructure", project],
            {"agent": agent, "project": project, "cia_availability": "high"},
            body,
            dry_run,
        )
    ]


def _onboard_11_code(
    project: str, modules: List[Dict], language: str, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    for mod in modules:
        body = f"""# {mod["name"]} — {mod["type"].capitalize()}

> Stub generado por vault_onboard. Enriquecer con vault_code_module.

**Archivo:** `{mod["file_path"]}`
**Lenguaje:** {language}
**Tipo inferido:** {mod["type"]}
**Líneas:** {mod["size_lines"]}

## Propósito

_Pendiente. Leer el archivo y documentar con vault_code_module._

## Para enriquecer

```bash
python scripts/vault_code_module.py \\
  --project {project} \\
  --file_path "{mod["file_path"]}" \\
  --description "..." \\
  --language {language} \\
  --iso_type {mod["type"]}
```
"""
        results.append(
            _write(
                f"11_Code/{project}",
                f"{mod['slug']}.md",
                f"{mod['name']} — {mod['type'].capitalize()}",
                ["stub", "code", project, mod["type"]],
                {
                    "agent": agent,
                    "project": project,
                    "source_file": mod["file_path"],
                    "language": language,
                },
                body,
                dry_run,
            )
        )
    return results


def _onboard_13_flows(
    project: str, project_path: Path, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    workflows_dir = project_path / ".github" / "workflows"
    if not workflows_dir.exists():
        return []
    for wf_file in sorted(workflows_dir.glob("*.yml"))[:5]:
        try:
            text = wf_file.read_text(encoding="utf-8", errors="replace")
            triggers = re.findall(
                r"^\s+(push|pull_request|workflow_dispatch|schedule|release):",
                text,
                re.MULTILINE,
            )
            jobs = re.findall(r"^\s{2}([\w-]+):\s*$", text, re.MULTILINE)
            jobs_md = "\n".join(f"- `{j}`" for j in jobs[:8]) or "— No detectados"
            triggers_md = ", ".join(set(triggers)) or "— No detectados"
            wf_name = wf_file.stem
            body = f"""# CI: {wf_name}

> Flujo detectado desde `.github/workflows/{wf_file.name}`.

**Trigger:** {triggers_md}
**Tipo:** pipeline

## Jobs detectados

{jobs_md}

## Para enriquecer

```bash
python scripts/vault_flow_save.py --project {project} \\
  --name "{wf_name}" --flow_type pipeline --description "..."
```
"""
            results.append(
                _write(
                    "13_Flows/pipeline",
                    f"{_slug(project)}-{_slug(wf_name)}.md",
                    f"CI: {wf_name}",
                    ["flow", "pipeline", "ci", project],
                    {"agent": agent, "project": project, "flow_type": "pipeline"},
                    body,
                    dry_run,
                )
            )
        except Exception:
            pass
    return results


def _onboard_14_requirements(
    project: str, meta: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    results = []
    readme_text, _ = _read_readme(
        VAULT_ROOT.parent
        if not VAULT_ROOT.name.startswith("vault-")
        else VAULT_ROOT.parent
    )
    # Find bullet points under ## Features or ## Requirements
    headers = meta.get("readme_headers", [])
    feature_headers = [
        h
        for h in headers
        if re.search(r"feature|requirement|funcionalidad|funciones", h, re.I)
    ]
    if not feature_headers:
        return []

    # Re-read README to extract bullets
    for project_path_candidate in [
        VAULT_ROOT.parent,
        VAULT_ROOT.parent.parent,
    ]:
        readme = project_path_candidate / "README.md"
        if readme.exists():
            try:
                full_text = readme.read_text(encoding="utf-8", errors="replace")
                for fh in feature_headers[:2]:
                    section_match = re.search(
                        rf"^## {re.escape(fh)}\s*\n(.*?)(?=^## |\Z)",
                        full_text,
                        re.MULTILINE | re.DOTALL,
                    )
                    if not section_match:
                        continue
                    bullets = re.findall(
                        r"^[-*]\s+(.+)$", section_match.group(1), re.MULTILINE
                    )
                    for i, bullet in enumerate(bullets[:10], 1):
                        req_id = f"REQ-{i:03d}"
                        body = f"""# {req_id} — {bullet[:80]}

> Requerimiento detectado desde README. Verificar implementación.

**ID:** {req_id}
**Tipo:** functional
**Prioridad:** must-have
**Status:** implemented
**Fuente:** README.md — sección `## {fh}`

## Descripción

{bullet}

## Criterios de aceptación

_Pendiente de definir._

## Para enriquecer

```bash
python scripts/vault_requirement_save.py --project {project} \\
  --title "{req_id} — ..." --req_type functional --priority must-have
```
"""
                        results.append(
                            _write(
                                f"14_Requirements/{project}",
                                f"{_slug(req_id)}.md",
                                f"{req_id} — {bullet[:60]}",
                                ["requirement", "functional", project],
                                {
                                    "agent": agent,
                                    "project": project,
                                    "req_type": "functional",
                                    "priority": "must-have",
                                },
                                body,
                                dry_run,
                            )
                        )
            except Exception:
                pass
            break

    return results[:10]


def _onboard_15_tests(
    project: str, project_path: Path, meta: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    relevant_exts = {
        ext for ext, lang in LANG_BY_EXT.items() if lang == meta.get("language", "")
    } or set(LANG_BY_EXT.keys())

    by_type: Dict[str, List[str]] = defaultdict(list)
    for f in project_path.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in relevant_exts:
            continue
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        rel = str(f.relative_to(project_path)).replace("\\", "/")
        matched = False
        for pattern, ttype in TEST_PATTERNS:
            if pattern.search(rel):
                by_type[ttype].append(rel)
                matched = True
                break
        if not matched and any(p in SKIP_DIRS_TEST for p in f.parts):
            by_type["unit"].append(rel)

    if not by_type:
        return []

    results = []
    for ttype, files in by_type.items():
        files_md = "\n".join(f"- `{f}`" for f in files[:20])
        body = f"""# {project} — Tests {ttype}

> Inventario generado por vault_onboard desde archivos de test detectados.

**Tipo:** {ttype}
**Archivos encontrados:** {len(files)}

## Archivos

{files_md}

## Para enriquecer

```bash
python scripts/vault_test_save.py --project {project} \\
  --title "Test suite {ttype}" --test_type {ttype} --description "..."
```
"""
        results.append(
            _write(
                f"15_Tests/{ttype}",
                # El tipo va en el NOMBRE, no solo en la carpeta. Obsidian
                # resuelve `[[builderx-inventory]]` por nombre de fichero, así
                # que tres inventarios homónimos en `unit/`, `security/` y
                # `performance/` son tres notas que se hacen sombra: el enlace
                # cae en una cualquiera de las tres (AP-17).
                f"{_slug(project)}-{_slug(ttype)}-inventory.md",
                f"{project} — Tests {ttype}",
                ["test", ttype, project],
                {"agent": agent, "project": project, "test_type": ttype},
                body,
                dry_run,
            )
        )

    return results


def _onboard_16_governance(
    project: str, meta: Dict, infra: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    """Baseline de gobernanza: lo que el repo revela, no lo que debería tener.

    La nota afirma hechos comprobables —si hay CI, si hay secretos declarados en
    infra, qué dependencias entran— y nombra explícitamente lo que NO se sabe.
    Decir "no consta quién revisa esto" es información; rellenarlo con un
    `_Pendiente_` no lo es, y por eso lo segundo no se escribe (AP-45).
    """
    hechos = []
    if infra.get("files"):
        hechos.append(
            f"- Infraestructura declarada en el repo: {', '.join(sorted(infra['files'])[:6])}"
        )
    if infra.get("env_vars"):
        hechos.append(
            f"- {len(infra['env_vars'])} variables de entorno referenciadas por el código"
        )
    if meta.get("all_deps"):
        hechos.append(
            f"- {len(meta['all_deps'])} dependencias de terceros entran en el producto"
        )
    if meta.get("license"):
        hechos.append(f"- Licencia declarada: {meta['license']}")
    if not hechos:
        return []

    body = f"""# {project} — Baseline de gobernanza

> Levantado por vault_onboard leyendo el repositorio. Son hechos observados,
> no una evaluación: nadie ha revisado este proyecto todavía.

## Lo que consta en el repositorio

{chr(10).join(hechos)}

## Lo que no consta

Ninguna de estas cosas está escrita en el proyecto, y por eso no hay nota que
las afirme: quién es responsable del sistema, qué datos personales trata, con
qué criterio se aceptan dependencias nuevas, y qué decisiones toma un modelo
sin revisión humana.

Son las cuatro preguntas que un baseline ISO/IEC 42001 abre. Responderlas es
trabajo de una persona, no de un escáner.

## Para enriquecer

```bash
python scripts/vault_ai_decision.py --project {project} \\
  --title "<decisión>" --decision_type architecture
python scripts/vault_privacy_save.py --project {project} --title "<tratamiento>"
```
"""
    return [
        _write(
            "16_AI_Governance",
            f"{_slug(project)}-baseline.md",
            f"{project} — Baseline de gobernanza",
            ["governance", "baseline", project],
            {"agent": agent, "project": project, "cia_integrity": "high"},
            body,
            dry_run,
        )
    ]


def _onboard_17_preferences(
    project: str, meta: Dict, agent: str, dry_run: bool
) -> List[Tuple[str, str]]:
    """Contexto estable del proyecto: lo que un agente debe saber sin preguntar.

    Solo se escriben las preferencias que el repositorio DEMUESTRA —el lenguaje
    que domina, el gestor de paquetes que hay— porque una preferencia inventada
    dirige el trabajo futuro hacia donde nadie decidió que fuera.
    """
    lineas = []
    if meta.get("language"):
        lineas.append(
            f"- El código de este proyecto se escribe en **{meta['language']}**. "
            "Se deduce de la extensión mayoritaria de los ficheros fuente."
        )
    if meta.get("framework"):
        lineas.append(f"- El framework en uso es **{meta['framework']}**.")
    if meta.get("package_manager"):
        lineas.append(
            f"- El gestor de paquetes es **{meta['package_manager']}**, "
            "declarado por el lockfile presente en el repositorio."
        )
    if meta.get("runtime"):
        lineas.append(f"- El runtime declarado es **{meta['runtime']}**.")
    if not lineas:
        return []

    body = f"""# {project} — Contexto estable

> Preferencias deducidas del repositorio por vault_onboard. Cada una tiene una
> evidencia detrás; lo que el repo no demuestra, no está aquí.

## Qué asumir al trabajar en este proyecto

{chr(10).join(lineas)}

## Cómo cambiarlas

Estas notas las lee `vault_context_pack` al armar el contexto de una sesión, así
que una preferencia equivocada se propaga a todo lo que venga después.

```bash
python scripts/vault_preferences.py --set --title "<preferencia>" \\
  --statement "..." --strength should
```
"""
    return [
        _write(
            "17_Preferences",
            f"{_slug(project)}-contexto.md",
            f"{project} — Contexto estable",
            ["preference", "context", project],
            {"agent": agent, "project": project, "strength": "should"},
            body,
            dry_run,
        )
    ]


# ── Index update ──────────────────────────────────────────────────────────────


def _update_indexes(sections: List[str], dry_run: bool) -> List[str]:
    if dry_run:
        return [f"{s}/index.md" for s in sections]
    try:
        from vault_section_index import vault_section_index

        updated = []
        for folder in sections:
            if (VAULT_ROOT / folder).exists():
                r = vault_section_index(folder)
                if r.get("ok"):
                    updated.append(r["path"])
        return updated
    except Exception:
        return []


# ── Main ──────────────────────────────────────────────────────────────────────


def vault_onboard(
    project: str,
    path: str,
    depth: int = 3,
    max_modules: int = 20,
    lang_hint: Optional[str] = None,
    dry_run: bool = False,
    agent: str = "claude",
    skip: Optional[List[str]] = None,
    git_phases: int = 8,
    max_commits: int = 500,
    no_git: bool = False,
) -> Dict[str, Any]:
    project_path = Path(path).resolve()
    if not project_path.exists():
        return {
            "ok": False,
            "error": "project_path_not_found",
            "path": str(project_path),
        }

    skip = set(skip or [])
    warnings: List[str] = []
    _SIN_EVIDENCIA.clear()
    _DETECCION_DEGRADADA.clear()  # por onboarding, no por proceso
    created: Dict[str, Any] = {}
    merge_stats = {"created": 0, "merged": 0, "skipped": 0, "dry_run": 0}

    def _record(pairs: List[Tuple[str, str]], key: str) -> None:
        paths = []
        for rel, action in pairs:
            merge_stats[action] = merge_stats.get(action, 0) + 1
            paths.append(rel)
        if paths:
            if key in created and isinstance(created[key], list):
                created[key].extend(paths)
            elif key in created:
                created[key] = [created[key]] + paths
            else:
                created[key] = paths if len(paths) > 1 else paths[0]

    # 1. Discover meta
    meta = _detect_project_meta(project_path, lang_hint)
    language = meta.get("language", "")
    if not language:
        warnings.append("Lenguaje no detectado — usa --lang para indicarlo")

    # ¿El README habla de este proyecto? No siempre: un repo puede llevar en la
    # raíz el README de otra cosa (una copia propagada, una plantilla sin
    # renombrar). No se puede decidir automáticamente cuál es el bueno, pero sí
    # se puede decir que no cuadran — y eso basta, porque de ese fichero salen
    # la descripción del overview y las notas de 07_Knowledge.
    if _README_H1:
        h1 = _README_H1[0]
        if normalize_stem(project) not in normalize_stem(h1) and normalize_stem(
            h1
        ) not in normalize_stem(project):
            warnings.append(
                f"El README de la raíz se titula «{h1}», que no se parece a "
                f"«{project}». La descripción y las notas de 07_Knowledge salen "
                "de ese fichero: si describe otro proyecto, revísalas antes de "
                "darlas por buenas."
            )

    # 2. History
    if no_git:
        history = _extract_file_history(project_path)
    else:
        history = _extract_git_history(project_path, max_commits)
        if not history.get("is_git"):
            history = _extract_file_history(project_path)
            warnings.append(
                "No es un repo git — usando mtime de archivos para el historial"
            )

    # El tope de lectura de historia deja de ser silencioso: si la ventana se
    # truncó, `phases_detected` describe la ventana y no el proyecto, y eso hay
    # que decirlo donde el usuario lo lee.
    warnings.extend(history.get("warnings", []))

    phases = _detect_phases(history, max_phases=git_phases)

    # 3. Scan modules
    modules = _scan_modules(project_path, depth, language, max_modules)
    infra = _detect_infra(project_path)

    # 4. Apply section strategies
    if "01" not in skip:
        _record(
            _onboard_01_projects(project, meta, history, phases, agent, dry_run),
            "overview",
        )
    if "04" not in skip:
        _record(
            _onboard_04_sessions(project, phases, history, agent, dry_run), "sessions"
        )
    if "03" not in skip:
        _record(
            _onboard_03_decisions(project, history, project_path, agent, dry_run),
            "decisions",
        )
    if "02" not in skip:
        _record(
            _onboard_02_observability(project, project_path, modules, agent, dry_run),
            "observability",
        )
    if "05" not in skip:
        _record(_onboard_05_patterns(project, modules, agent, dry_run), "patterns")
    if "06" not in skip:
        _record(
            _onboard_06_diagrams(project, project_path, meta, modules, agent, dry_run),
            "diagrams",
        )
    if "07" not in skip:
        _record(_onboard_07_knowledge(project, meta, agent, dry_run), "knowledge")
    if "08" not in skip:
        _record(
            _onboard_08_runbooks(project, meta, project_path, agent, dry_run),
            "runbooks",
        )
    if "09" not in skip:
        _record(_onboard_09_infrastructure(project, infra, agent, dry_run), "infra")
    if "11" not in skip:
        _record(_onboard_11_code(project, modules, language, agent, dry_run), "modules")
    if "13" not in skip:
        _record(_onboard_13_flows(project, project_path, agent, dry_run), "flows")
    if "14" not in skip:
        _record(_onboard_14_requirements(project, meta, agent, dry_run), "requirements")
    if "15" not in skip:
        _record(_onboard_15_tests(project, project_path, meta, agent, dry_run), "tests")
    if "16" not in skip:
        _record(
            _onboard_16_governance(project, meta, infra, agent, dry_run), "governance"
        )
    if "17" not in skip:
        _record(_onboard_17_preferences(project, meta, agent, dry_run), "preferences")

    # 5. Update indexes
    sections_to_index = [
        s
        for s in ORDERED_SECTIONS
        if s not in _SECCIONES_NO_POBLADAS and not skip.intersection({s[:2]})
    ]
    created["indexes_updated"] = _update_indexes(sections_to_index, dry_run)

    # 5b. Reconstruir el buscador (AP-47). Los `index.md` de sección son
    # navegación; `99_Index/search-index.json` es lo que responde a
    # `vault_search`, y ninguna de las ~40 tools `*_save` que este onboard invoca
    # lo actualiza. Medido antes de añadir esto: 67 notas en disco y 41 indexadas
    # al terminar — un tercio del vault recién creado era invisible desde el
    # primer minuto, y el agente que no encontrara una nota la habría vuelto a
    # escribir. Es el mismo criterio que `sections_left_empty_by_design`: el
    # onboard no puede dejar deuda que él mismo sabe cerrar.
    if not dry_run:
        try:
            from vault_reindex import vault_reindex

            created["search_index"] = vault_reindex()
        except Exception as exc:  # noqa: BLE001 — no tumbar el onboard por esto
            warnings.append(
                f"search-index no reconstruido ({type(exc).__name__}: {exc}); "
                f"ejecuta `vault_reindex` antes de buscar en el vault (AP-47)"
            )

    # 6. Anotar el vocabulario introducido (AP-39). Un onboard mete de golpe
    # decenas de términos nuevos —el lenguaje, el framework, los tipos de
    # módulo, el nombre del proyecto— y sin bitácora quedan como vocabulario
    # aparecido de la nada: nadie sabe quién los metió ni cuándo, y el siguiente
    # que dude no tiene a qué agarrarse. Es la tool que los introduce la que
    # tiene el contexto para anotarlos, y este es el único momento en que lo
    # tiene.
    if not dry_run:
        try:
            from vault_tags import vault_tags_backfill_ledger

            r = vault_tags_backfill_ledger()
            created["vocabulary_recorded"] = r.get("recorded", 0)
        except (ImportError, TypeError, OSError) as exc:
            warnings.append(
                f"No se pudo anotar el vocabulario nuevo en la bitácora ({exc}): "
                "correr `vault_tags --backfill-ledger` a mano (AP-39)."
            )

    return {
        "ok": True,
        "project": project,
        "path_scanned": str(project_path),
        "dry_run": dry_run,
        "git_history": {
            "is_git": history.get("is_git", False),
            "current_branch": history.get("current_branch", ""),
            "apparent_first_date": history.get("apparent_first_date", ""),
            "true_first_date": history.get("true_first_date", ""),
            "hidden_history": history.get("hidden_history", False),
            "hidden_months": history.get("hidden_months", 0),
            "last": (
                history.get("last_commit") or history.get("last_modified") or {}
            ).get("date"),
            "total_commits": history.get("total_commits", 0),
            "total_commits_with_reflog": history.get("total_commits_with_reflog", 0),
            "contributors": history.get("contributors", []),
            "tags": [t["name"] for t in history.get("tags", [])],
            "branches": len(history.get("branches", [])),
            "snap_branches": [b["name"] for b in history.get("snap_branches", [])],
            "stashes": len(history.get("stashes", [])),
            "reflog_extra_commits": history.get("reflog_extra_commits", 0),
            "phases_detected": len(phases),
        },
        "discovered": {
            "runtime": meta.get("runtime", ""),
            "language": language,
            "framework": meta.get("framework", ""),
            "description": (
                meta.get("description") or meta.get("readme_excerpt") or ""
            )[:120],
            "module_count": len(modules),
            "has_infra": bool(infra.get("files")),
        },
        "created": created,
        "merge_stats": merge_stats,
        # AP-45: lo que NO se escribió, y por qué. Es la mitad útil del informe.
        # Un hueco nombrado dirige el siguiente trabajo; un stub que lo tapa
        # hace creer que ya está hecho.
        "skipped_no_evidence": list(_SIN_EVIDENCIA),
        # Vacías a propósito, y por eso se declaran: son secciones dirigidas por
        # eventos. Poblarlas en el arranque sería inventar bugs, auditorías y
        # cuarentenas que no han ocurrido — exactamente AP-45.
        "sections_left_empty_by_design": dict(_SECCIONES_NO_POBLADAS),
        # Pasos de detección que fallaron: la diferencia entre «el proyecto no
        # tiene esto» y «no pude leerlo». Ver `_registrar_degradacion`.
        "degraded": list(_DETECCION_DEGRADADA),
        "warnings": warnings,
        "next_steps": [
            f"vault_project_overview --project {project}  # enriquecer overview",
            "vault_code_module --project ... --file_path ...  # enriquecer módulos",
            "vault_audit  # verificar health score",
        ]
        + (
            [
                f"Escribir a mano las {len(_SIN_EVIDENCIA)} notas que se omitieron "
                "por falta de evidencia (ver skipped_no_evidence)"
            ]
            if _SIN_EVIDENCIA
            else []
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_onboard v2 — Onboard completo de proyecto existente al vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_onboard.py --project my-api --path ../my-api
  python vault_onboard.py --project my-api --path . --lang typescript --dry-run
  python vault_onboard.py --project my-api --path . --skip 02 05 13
  python vault_onboard.py --project my-api --path . --no-git --git-phases 6
""",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--max-modules", dest="max_modules", type=int, default=20)
    parser.add_argument("--lang", dest="lang_hint")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent", default="claude")
    parser.add_argument(
        "--skip",
        nargs="+",
        default=[],
        help=(
            "Secciones a omitir: 01 02 03 04 05 06 07 08 09 11 13 14 15 16 17. "
            "18/19/20 no aparecen porque no se pueblan nunca: son secciones "
            "dirigidas por eventos y llenarlas al arrancar sería AP-45."
        ),
    )
    parser.add_argument("--git-phases", dest="git_phases", type=int, default=8)
    parser.add_argument("--max-commits", dest="max_commits", type=int, default=500)
    parser.add_argument("--no-git", action="store_true")

    args = parser.parse_args()
    result = vault_onboard(
        project=args.project,
        path=args.path,
        depth=args.depth,
        max_modules=args.max_modules,
        lang_hint=args.lang_hint,
        dry_run=args.dry_run,
        agent=args.agent,
        skip=args.skip,
        git_phases=args.git_phases,
        max_commits=args.max_commits,
        no_git=args.no_git,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_onboard"))
