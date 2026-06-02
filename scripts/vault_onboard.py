#!/usr/bin/env python3
"""
vault_onboard.py — Onboard an existing project into the vault.

Scans a project directory, reads manifests (package.json, pyproject.toml,
Dockerfile, docker-compose.yml, README.md) and creates vault stubs for:
  - 01_Projects/<project>/overview.md
  - 11_Code/<project>/<module>.md   (one per discovered module, priority-ranked)
  - 09_Infrastructure/<project>/infra.md (if Docker / env files found)

All content is sourced only from files read on disk — never assumed.
Stubs are marked status:stub to signal they require enrichment (AP-01 guard).

Usage:
    python vault_onboard.py --project my-api --path ../my-api
    python vault_onboard.py --project my-api --path . --depth 2 --max-modules 15
    python vault_onboard.py --project my-api --path . --dry-run
    python vault_onboard.py --project my-api --path . --lang typescript
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from vault_errors import wrap_main
from vault_io import VAULT_ROOT, assert_within_vault, atomic_write_text
from vault_norms import compute_norm_refs

# ── Language detection ────────────────────────────────────────────────────────

LANG_BY_EXT: Dict[str, str] = {
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".py": "python",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".c": "c",
    ".kt": "kotlin",
    ".swift": "swift",
    ".dart": "dart",
    ".ex": "elixir", ".exs": "elixir",
}

# ── Source directory candidates ───────────────────────────────────────────────

SOURCE_DIRS = {
    "src", "lib", "app", "core", "pkg", "cmd", "internal",
    "api", "backend", "frontend", "server", "client",
    "services", "controllers", "models", "handlers", "routes",
    "domain", "application", "infrastructure", "presentation",
}

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "bin", "obj",
    "__pycache__", ".venv", "venv", ".env", "coverage", ".nyc_output",
    "vendor", "third_party", ".idea", ".vscode", "test", "tests",
    "spec", "__tests__", "e2e", "fixtures", "migrations",
}

# ── Module type inference from filename ──────────────────────────────────────

MODULE_TYPE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"service",     re.I), "service"),
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

# Priority order for limiting output (high priority first)
MODULE_PRIORITY = [
    "service", "controller", "repository", "manager",
    "model", "middleware", "factory", "interface", "utility", "config",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _infer_module_type(filename: str) -> str:
    stem = Path(filename).stem
    for pattern, mtype in MODULE_TYPE_PATTERNS:
        if pattern.search(stem):
            return mtype
    return "module"


# ── Manifest readers ──────────────────────────────────────────────────────────

def _read_package_json(project_path: Path) -> Dict[str, Any]:
    pj = project_path / "package.json"
    if not pj.exists():
        return {}
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        # Detect runtime/framework
        runtime = "Node.js"
        framework = ""
        all_deps = deps + dev_deps
        for d in all_deps:
            if d in ("electron",):       framework = "Electron"
            elif d in ("next",):         framework = "Next.js"
            elif d in ("react",):        framework = framework or "React"
            elif d in ("vue",):          framework = framework or "Vue"
            elif d in ("express", "fastify", "koa", "hapi"): framework = framework or d.capitalize()
            elif d in ("@nestjs/core",): framework = "NestJS"
        node_ver = data.get("engines", {}).get("node", "")
        return {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "version": data.get("version", ""),
            "runtime": f"{runtime} {node_ver}".strip(),
            "framework": framework,
            "scripts": list(data.get("scripts", {}).keys()),
            "key_deps": deps[:12],
            "source": "package.json",
        }
    except Exception:
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
            ver  = re.search(r'version\s*=\s*["\']([^"\']+)', text)
            return {
                "name": name.group(1) if name else "",
                "description": desc.group(1) if desc else "",
                "version": ver.group(1) if ver else "",
                "runtime": "Python",
                "framework": "",
                "source": fname,
            }
        except Exception:
            continue
    return {}


def _read_csproj(project_path: Path) -> Dict[str, Any]:
    for csproj in project_path.rglob("*.csproj"):
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
            }
        except Exception:
            continue
    return {}


def _read_readme(project_path: Path) -> str:
    for fname in ("README.md", "Readme.md", "readme.md", "README.rst"):
        fp = project_path / fname
        if fp.exists():
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                # Return first ~500 chars of meaningful content
                lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
                return " ".join(lines)[:500]
            except Exception:
                pass
    return ""


def _detect_project_meta(project_path: Path, lang_hint: Optional[str]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}

    for reader in (_read_package_json, _read_pyproject, _read_csproj):
        result = reader(project_path)
        if result:
            meta.update(result)
            break

    meta["readme_excerpt"] = _read_readme(project_path)

    # Language detection: hint > manifest-implied > extension survey
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
    project_path: Path,
    depth: int,
    language: str,
    max_modules: int,
) -> List[Dict[str, Any]]:
    """Discover source files and rank them by module type priority."""
    relevant_exts = {ext for ext, lang in LANG_BY_EXT.items() if lang == language}
    if not relevant_exts:
        # Accept all known extensions if language unknown
        relevant_exts = set(LANG_BY_EXT.keys())

    found: List[Dict[str, Any]] = []

    def _scan(dir_path: Path, current_depth: int) -> None:
        if current_depth > depth:
            return
        try:
            entries = sorted(dir_path.iterdir())
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if entry.name.lower() in SKIP_DIRS:
                    continue
                _scan(entry, current_depth + 1)
            elif entry.is_file() and entry.suffix.lower() in relevant_exts:
                rel = str(entry.relative_to(project_path)).replace("\\", "/")
                mtype = _infer_module_type(entry.name)
                found.append({
                    "name": entry.stem,
                    "file_path": rel,
                    "type": mtype,
                    "size_lines": _count_lines(entry),
                    "slug": _slug(entry.stem),
                })

    _scan(project_path, 0)

    # Sort by priority, then by file size descending (bigger = more important)
    def _priority(m: Dict) -> Tuple[int, int]:
        try:
            return (MODULE_PRIORITY.index(m["type"]), -m["size_lines"])
        except ValueError:
            return (len(MODULE_PRIORITY), -m["size_lines"])

    found.sort(key=_priority)
    return found[:max_modules]


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    except Exception:
        return 0


# ── Infrastructure scanner ────────────────────────────────────────────────────

def _detect_infra(project_path: Path) -> Dict[str, Any]:
    infra: Dict[str, Any] = {"services": [], "envs": [], "ports": [], "files": []}

    # docker-compose
    for fname in ("docker-compose.yml", "docker-compose.yaml",
                  "docker-compose.dev.yml", "compose.yml"):
        fp = project_path / fname
        if fp.exists():
            infra["files"].append(fname)
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                svcs = re.findall(r"^\s{2}(\w[\w-]+):\s*$", text, re.MULTILINE)
                infra["services"].extend(svcs)
                ports = re.findall(r'"?(\d+:\d+)"?', text)
                infra["ports"].extend(ports[:10])
            except Exception:
                pass

    # Dockerfile
    for df in ("Dockerfile", "Dockerfile.dev", "Dockerfile.prod"):
        if (project_path / df).exists():
            infra["files"].append(df)
            try:
                text = (project_path / df).read_text(encoding="utf-8", errors="replace")
                from_line = re.search(r"^FROM\s+(\S+)", text, re.MULTILINE)
                if from_line:
                    infra["base_image"] = from_line.group(1)
                expose = re.findall(r"^EXPOSE\s+(\d+)", text, re.MULTILINE)
                infra["ports"].extend(expose)
            except Exception:
                pass

    # .env.example / .env.local
    for ef in (".env.example", ".env.local", ".env.sample", ".env.template"):
        fp = project_path / ef
        if fp.exists():
            infra["files"].append(ef)
            try:
                lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
                keys = [l.split("=")[0].strip() for l in lines
                        if l.strip() and not l.startswith("#") and "=" in l]
                infra["envs"].extend(keys[:20])
            except Exception:
                pass

    # CI
    for ci_dir in (".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci"):
        if (project_path / ci_dir).exists():
            infra["files"].append(str(ci_dir))

    return infra


# ── Stub writers ──────────────────────────────────────────────────────────────

def _make_frontmatter(
    title: str,
    folder: str,
    tags: List[str],
    extra_meta: Dict[str, Any],
    content: str,
) -> str:
    now = _utcnow()
    norm_refs = compute_norm_refs(folder, content, [])
    lines = [
        "---",
        f"title: {title}",
        f"id: {uuid.uuid4()}",
        f"createdAt: {now}",
        f"updatedAt: {now}",
        f"tags: {json.dumps(tags)}",
        f"norm_refs: {json.dumps(norm_refs)}",
        f"status: stub",
        f"cia_integrity: {extra_meta.get('cia_integrity', 'medium')}",
        f"cia_availability: {extra_meta.get('cia_availability', 'medium')}",
        f"cia_sensitivity: {extra_meta.get('cia_sensitivity', 'internal')}",
        f"agent: {extra_meta.get('agent', 'claude')}",
    ]
    for k, v in extra_meta.items():
        if k in ("cia_integrity", "cia_availability", "cia_sensitivity", "agent"):
            continue
        lines.append(f"{k}: {json.dumps(v) if not isinstance(v, str) else v}")
    lines.append("---")
    return "\n".join(lines)


def _write_stub(vault_path: Path, content: str, dry_run: bool) -> None:
    if not dry_run:
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        assert_within_vault(vault_path, VAULT_ROOT)
        atomic_write_text(vault_path, content)


def _create_overview(
    project: str,
    meta: Dict[str, Any],
    agent: str,
    dry_run: bool,
) -> str:
    folder = "01_Projects"
    title = f"{project} — Overview"
    runtime = meta.get("runtime", "")
    framework = meta.get("framework", "")
    runtime_str = f"{runtime} / {framework}".strip(" /") if framework else runtime
    description = meta.get("description") or meta.get("readme_excerpt") or "Pendiente de documentar."
    language = meta.get("language", "")

    body = f"""# {title}

> Stub generado por vault_onboard. Enriquecer con vault_project_overview.

## Descripción

{description[:400]}

## Stack detectado

| Campo | Valor |
|---|---|
| Runtime | {runtime_str or "—"} |
| Lenguaje | {language or "—"} |
| Versión | {meta.get("version") or "—"} |
| Fuente detección | {meta.get("source") or "—"} |

## Scripts disponibles

{chr(10).join(f"- `{s}`" for s in meta.get("scripts", [])[:8]) or "— No detectados"}

## Próximos pasos

- Verificar descripción con el equipo
- Completar stack real (base de datos, caches, queues)
- Vincular módulos de código: [[{_slug(project)}-code-map]]
"""

    fm = _make_frontmatter(
        title, folder,
        ["project", "overview", project],
        {"agent": agent, "project": project},
        body,
    )
    full = fm + "\n\n" + body
    path = VAULT_ROOT / folder / project / "overview.md"
    _write_stub(path, full, dry_run)
    return str(path.relative_to(VAULT_ROOT)).replace("\\", "/")


def _create_module_stub(
    project: str,
    module: Dict[str, Any],
    language: str,
    agent: str,
    dry_run: bool,
) -> str:
    folder = "11_Code"
    slug = module["slug"]
    title = f"{module['name']} — {module['type'].capitalize()}"
    file_path = module["file_path"]

    body = f"""# {title}

> Stub generado por vault_onboard. Enriquecer con vault_code_module.

**Archivo:** `{file_path}`
**Lenguaje:** {language}
**Tipo inferido:** {module["type"]}
**Líneas:** {module["size_lines"]}

## Propósito

_Pendiente. Leer el archivo y documentar con vault_code_module._

## Para documentar este módulo

```bash
python scripts/vault_code_module.py \\
  --project {project} \\
  --file_path "{file_path}" \\
  --description "..." \\
  --language {language} \\
  --iso_type {module["type"]}
```
"""

    fm = _make_frontmatter(
        title, folder,
        ["stub", "code", project, module["type"]],
        {"agent": agent, "project": project, "source_file": file_path, "language": language},
        body,
    )
    full = fm + "\n\n" + body
    path = VAULT_ROOT / folder / project / f"{slug}.md"
    _write_stub(path, full, dry_run)
    return str(path.relative_to(VAULT_ROOT)).replace("\\", "/")


def _create_infra_stub(
    project: str,
    infra: Dict[str, Any],
    agent: str,
    dry_run: bool,
) -> str:
    folder = "09_Infrastructure"
    title = f"{project} — Infraestructura"

    services_md = "\n".join(f"- `{s}`" for s in infra.get("services", [])) or "— No detectados"
    ports_md = "\n".join(f"- `{p}`" for p in set(infra.get("ports", []))) or "— No detectados"
    envs_md = "\n".join(f"- `{e}`" for e in infra.get("envs", [])) or "— No detectadas"
    files_md = "\n".join(f"- `{f}`" for f in infra.get("files", [])) or "— Ninguno"

    body = f"""# {title}

> Stub generado por vault_onboard desde archivos de configuración detectados.

## Archivos detectados

{files_md}

## Servicios (docker-compose)

{services_md}

## Puertos expuestos

{ports_md}

## Variables de entorno (.env)

{envs_md}

## Imagen base

{infra.get("base_image") or "— No detectada"}

## Próximos pasos

- Verificar servicios y puertos reales
- Documentar con vault_infra_save para cada componente
- Agregar variables con vault_env_save
"""

    fm = _make_frontmatter(
        title, folder,
        ["stub", "infrastructure", project],
        {"agent": agent, "project": project},
        body,
    )
    full = fm + "\n\n" + body
    path = VAULT_ROOT / folder / project / "infra.md"
    _write_stub(path, full, dry_run)
    return str(path.relative_to(VAULT_ROOT)).replace("\\", "/")


def _update_indexes(folders: List[str], dry_run: bool) -> List[str]:
    if dry_run:
        return [f"{f}/index.md" for f in folders]
    try:
        from vault_section_index import vault_section_index
        updated = []
        for folder in folders:
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
) -> Dict[str, Any]:
    project_path = Path(path).resolve()
    if not project_path.exists():
        return {"ok": False, "error": "project_path_not_found", "path": str(project_path)}

    warnings: List[str] = []

    # 1. Discover project metadata
    meta = _detect_project_meta(project_path, lang_hint)
    language = meta.get("language", "")
    if not language:
        warnings.append("Lenguaje no detectado — usa --lang para indicarlo")

    # 2. Scan modules
    modules = _scan_modules(project_path, depth, language, max_modules)
    total_files = sum(
        1 for f in project_path.rglob("*")
        if f.is_file()
        and f.suffix.lower() in LANG_BY_EXT
        and not any(p in SKIP_DIRS for p in f.parts)
    )
    if total_files > max_modules:
        warnings.append(
            f"{total_files} archivos fuente encontrados, {len(modules)} seleccionados "
            f"por prioridad. Aumenta --max-modules o documenta el resto con vault_code_module."
        )

    # 3. Detect infrastructure
    infra = _detect_infra(project_path)
    has_infra = bool(infra.get("files"))

    # 4. Write stubs
    created: Dict[str, Any] = {}

    overview_path = _create_overview(project, meta, agent, dry_run)
    created["overview"] = overview_path

    module_paths = []
    for mod in modules:
        mp = _create_module_stub(project, mod, language, agent, dry_run)
        module_paths.append(mp)
    created["modules"] = module_paths

    if has_infra:
        infra_path = _create_infra_stub(project, infra, agent, dry_run)
        created["infra"] = infra_path
    else:
        warnings.append("No se detectó Docker / .env — omitido 09_Infrastructure")

    # 5. Update section indexes
    sections_to_index = ["01_Projects", "11_Code"]
    if has_infra:
        sections_to_index.append("09_Infrastructure")
    created["indexes_updated"] = _update_indexes(sections_to_index, dry_run)

    return {
        "ok": True,
        "project": project,
        "path_scanned": str(project_path),
        "dry_run": dry_run,
        "discovered": {
            "runtime": meta.get("runtime", ""),
            "language": language,
            "framework": meta.get("framework", ""),
            "description": (meta.get("description") or meta.get("readme_excerpt") or "")[:120],
            "config_files": [meta.get("source", "")] + infra.get("files", []),
            "module_count": len(modules),
            "has_infra": has_infra,
        },
        "created": created,
        "warnings": warnings,
        "next_steps": [
            f"Enriquecer overview: vault_project_overview --project {project}",
            "Completar cada stub: vault_code_module --project ... --file_path ...",
            "Actualizar infra: vault_infra_save + vault_env_save",
            "Auditar el vault: vault_audit",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_onboard — Onboard an existing project into the vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Onboard desde directorio adyacente
  python vault_onboard.py --project my-api --path ../my-api

  # Vista previa sin escribir nada
  python vault_onboard.py --project my-api --path . --dry-run

  # Forzar lenguaje y limitar módulos
  python vault_onboard.py --project my-api --path . --lang typescript --max-modules 10

  # Profundidad de escaneo (default 3)
  python vault_onboard.py --project my-api --path . --depth 2
""",
    )
    parser.add_argument("--project", required=True, help="Slug del proyecto (kebab-case)")
    parser.add_argument("--path",    required=True, help="Ruta al directorio del proyecto existente")
    parser.add_argument("--depth",   type=int, default=3, help="Profundidad de escaneo de directorios (default 3)")
    parser.add_argument("--max-modules", dest="max_modules", type=int, default=20,
                        help="Máximo de stubs de módulos a crear (default 20)")
    parser.add_argument("--lang",    dest="lang_hint", help="Forzar lenguaje (typescript, python, csharp, go...)")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar qué se crearía sin escribir nada")
    parser.add_argument("--agent",   default="claude", help="Agente que ejecuta (default claude)")

    args = parser.parse_args()
    result = vault_onboard(
        project=args.project,
        path=args.path,
        depth=args.depth,
        max_modules=args.max_modules,
        lang_hint=args.lang_hint,
        dry_run=args.dry_run,
        agent=args.agent,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_onboard"))
