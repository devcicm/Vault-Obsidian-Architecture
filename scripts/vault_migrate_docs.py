#!/usr/bin/env python3

"""

Vault Migrate Docs Tool — Migrate existing documentation to vault (3-phase flow)



Phase 1 - STAGING: All files land in 10_Migrated/_staging/ as-is

Phase 2 - CLASSIFICATION: Each file classified as direct/indirect/excluded

Phase 3 - DISTRIBUTION: Files moved to definitive vault folders



NEVER migrates source code files (.js, .ts, .py, etc.) — only documentation.



Usage:

    python vault_migrate_docs.py --source_path "C:/docs" --project "ans" --keywords "Ansible MCP" --dry_run true

    python vault_migrate_docs.py --source_path "C:/old-docs" --project "mi-api" --dry_run false

"""

import argparse

import json

import re

import sys

from vault_errors import wrap_main
from vault_lib import yaml_scalar, slugify

from vault_io import (
    assert_within_vault,
    atomic_write_text,
    safe_wikilink,
    write_report,
)
import yaml
import uuid

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple


FORMATS = [".md", ".txt", ".html", ".rst", ".adoc"]


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
}

IGNORED_FILES = {".gitignore", ".env", ".DS_Store", "package-lock.json", "yarn.lock"}


CODE_EXTS = {
    ".js",
    ".mjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".cs",
    ".sh",
    ".bash",
    ".ps1",
}


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _migrated_dir() -> Path:
    return _repo().dir_migrados


def _staging_dir() -> Path:
    return _repo().dir_staging


def convert_links(content: str) -> str:
    content = re.sub(r"\[([^\]]+)\]\(([^)]+\.md)\)", r"[[\2|\1]]", content)

    content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"![[\2]]", content)

    return content


def strip_html(content: str) -> str:
    content = re.sub(
        r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
    )

    content = re.sub(
        r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
    )

    content = re.sub(r"<[^>]+>", "", content)

    content = re.sub(r"&nbsp;", " ", content)

    content = re.sub(r"&lt;", "<", content)

    content = re.sub(r"&gt;", ">", content)

    content = re.sub(r"&amp;", "&", content)

    return content


CONTENT_SIGNALS = [
    (
        1,
        [
            "decision",
            "adr",
            "architecture decision",
            "we decided",
            "options considered",
        ],
        "03_Decisions",
    ),
    (
        2,
        ["report", "reporte", "audit report", "scan result", "finding", "assessment"],
        "10_Migrated/direct",
    ),
    (3, ["readme", "overview", "introduction"], "01_Projects"),
    (
        4,
        ["api", "endpoint", "swagger", "openapi", "route", "rest", "graphql"],
        "07_Knowledge/apis",
    ),
    (
        5,
        ["framework", "react", "vue", "express", "django", "nextjs", "laravel"],
        "07_Knowledge/frameworks",
    ),
    (
        6,
        ["package", "dependency", "npm", "pip", "library", "libreria", "paquete"],
        "07_Knowledge/dependencies",
    ),
    (7, ["deploy", "install", "setup", "rollback", "how to"], "08_Runbooks/setup"),
    (
        8,
        ["architecture", "pattern", "design", "schema", "diagram"],
        "05_Patterns/architecture",
    ),
    (9, ["error", "bug", "exception", "fix", "incident"], "02_Observability/errors"),
    (
        10,
        ["config", "env", "variable", "setting", ".env", "yaml"],
        "07_Knowledge/configs",
    ),
    (11, ["glossary", "term", "definition", "glosario"], "07_Knowledge/glossary"),
    (
        12,
        ["service", "server", "infra", "host", "ip", "port"],
        "09_Infrastructure/services",
    ),
]


def detect_folder(content_lower: str, filename_lower: str) -> Tuple[str, str]:
    combined = content_lower + " " + filename_lower

    for priority, signals, folder in CONTENT_SIGNALS:
        for signal in signals:
            if signal in combined:
                return folder, "priority"

    return "10_Migrated/direct", "default"


def _frontmatter_valido(texto: str) -> bool:
    """El bloque abre, cierra y parsea como YAML de claves.

    Se valida con `yaml.safe_load`, no con un regex por líneas: es el criterio
    del consumidor (Obsidian, `vault_audit`), no el de quien escribe (AP-44).
    """
    if not texto.startswith("---\n"):
        return False
    fin = texto.find("\n---", 3)
    if fin == -1:
        return False
    try:
        datos = yaml.safe_load(texto[4:fin])
    except yaml.YAMLError:
        return False
    return isinstance(datos, dict) and bool(datos.get("type"))


def classify_relevance(
    content: str, filename: str, project: str, keywords: List[str]
) -> Tuple[str, str, str]:
    all_keywords = keywords + [project]

    content_lower = (content + " " + filename).lower()

    direct_count = sum(content_lower.count(kw.lower()) for kw in all_keywords)

    if direct_count >= 3:
        folder, method = detect_folder(content_lower, filename.lower())

        return "direct", folder, method

    tech_terms = [
        "api",
        "http",
        "json",
        "config",
        "server",
        "database",
        "deploy",
        "docker",
        "kubernetes",
        "linux",
        "framework",
        "package",
        "dependency",
    ]

    tech_count = sum(content_lower.count(t) for t in tech_terms)

    if tech_count >= 4:
        return "indirect", "10_Migrated/indirect", "tech_terms"

    return "excluded", "10_Migrated/excluded", "no_match"


def scan_directory(source_path: Path, formats: List[str]) -> List[Path]:
    files = []

    if not source_path.exists():
        return files

    for item in source_path.rglob("*"):
        if item.is_file():
            if item.suffix.lower() in CODE_EXTS:
                continue

            if item.suffix.lower() in formats:
                if not any(ignored in item.parts for ignored in IGNORED_DIRS):
                    if item.name not in IGNORED_FILES:
                        files.append(item)

    return files


def process_file_staging(file_path: Path, project: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

    except (UnicodeDecodeError, PermissionError, FileNotFoundError):
        return None

    if not content.strip():
        return None

    original_content = content

    content_stripped = strip_html(content)

    content_converted = convert_links(content_stripped)

    safe_name = slugify(file_path.stem)

    filename = f"{safe_name}.md"

    timestamp = datetime.now(timezone.utc).isoformat()

    from vault_lib import utcnow
    now = utcnow()
    tags = [project, "migrated"]

    frontmatter = ["---"]

    frontmatter.append(f"title: {yaml_scalar(file_path.stem)}")

    frontmatter.append(f"id: {str(uuid.uuid4())}")

    frontmatter.append(f"migratedFrom: {str(file_path)}")

    frontmatter.append(f"type: migrated")

    frontmatter.append(f"createdAt: {now}")

    frontmatter.append(f"updatedAt: {now}")

    frontmatter.append(f"tags: {json.dumps(tags)}")

    frontmatter.append(f"migratedAt: {timestamp}")

    frontmatter.append(f"stagedAt: {timestamp}")

    frontmatter.append(f"distributedTo: ''")

    frontmatter.append(f"project: {yaml_scalar(project)}")

    frontmatter.append("cia_integrity: low")

    frontmatter.append("cia_availability: low")

    frontmatter.append("cia_sensitivity: internal")

    frontmatter.append("status: migrated")

    frontmatter.append("agent: vault_migrate_docs")

    frontmatter.append("---")

    frontmatter.append(f"\n{content_converted.strip()}\n")

    return {
        "originalPath": str(file_path),
        "originalName": file_path.name,
        "stagedName": filename,
        "content": "\n".join(frontmatter),
        "preview": content_converted.strip()[:300],
        "wordCount": len(content_converted.split()),
    }


def vault_migrate_docs(
    source_path: str,
    project: str,
    keywords: Optional[List[str]] = None,
    formats: Optional[List[str]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    source = Path(source_path)

    if not source.exists():
        return {"ok": False, "error": f"Source path not found: {source_path}"}

    keywords = keywords or []

    formats = formats or FORMATS

    files = scan_directory(source, formats)

    staged_results: List[Dict[str, Any]] = []

    errors: List[Dict[str, Any]] = []

    for file_path in files:
        result = process_file_staging(file_path, project)

        if result:
            staged_results.append(result)

        else:
            errors.append({"path": str(file_path), "reason": "Could not read file"})

    phase1_report = {
        "phase": "STAGING",
        "total": len(staged_results),
        "staged": [r["stagedName"] for r in staged_results[:5]],
    }

    if dry_run:
        classified = []

        for staged in staged_results:
            content_for_class = staged["preview"]

            relevance, dest_folder, method = classify_relevance(
                content_for_class, staged["originalName"], project, keywords
            )

            dest_name = f"{slugify(Path(staged['originalName']).stem)}.md"

            classified.append(
                {
                    "originalName": staged["originalName"],
                    "stagedName": staged["stagedName"],
                    "relevance": relevance,
                    "destination": dest_folder,
                    "destFile": dest_name,
                    "method": method,
                }
            )

        return {
            "ok": True,
            "dryRun": True,
            "project": project,
            "totalScanned": len(files),
            "totalStaged": len(staged_results),
            "phase1": phase1_report,
            "classified": classified[:20],
            "errors": len(errors),
            "message": f"Dry run: {len(staged_results)} files ready for staging. Run with dry_run=false to execute migration.",
        }

    _staging_dir().mkdir(parents=True, exist_ok=True)

    _migrated_dir().mkdir(parents=True, exist_ok=True)

    for staged in staged_results:
        staged_path = _staging_dir() / staged["stagedName"]

        atomic_write_text(staged_path, staged["content"])

    classified: List[Dict[str, Any]] = []

    subfolders_created: List[str] = []

    distributed: List[Dict[str, Any]] = []

    stubs_created: List[Dict[str, Any]] = []

    for staged in staged_results:
        content_for_class = staged["preview"]

        relevance, dest_folder, method = classify_relevance(
            content_for_class, staged["originalName"], project, keywords
        )

        dest_name = f"{slugify(Path(staged['originalName']).stem)}.md"

        # `dest_folder` ya viene relativo a la RAÍZ del vault ("03_Decisions",
        # "10_Migrated/indirect"): componerlo bajo MIGRATED_DIR duplicaba el
        # segmento y el fichero acababa en `10_Migrated/10_Migrated/indirect/`.
        # Peor, los destinos que no son de 10_Migrated (03_Decisions,
        # 07_Knowledge/apis) quedaban enterrados dentro de la carpeta de
        # migración, que es justo de donde la distribución tiene que sacarlos.
        dest_path = _raiz() / dest_folder / dest_name

        assert_within_vault(dest_path, _raiz())

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        relative_parent = str(dest_path.parent.relative_to(_raiz()))

        if relative_parent not in subfolders_created:
            subfolders_created.append(relative_parent)

        dest_path_rels = dest_path.relative_to(_raiz())

        distributed.append(
            {
                "originalName": staged["originalName"],
                "stagedName": staged["stagedName"],
                "destFolder": dest_folder,
                "destPath": str(dest_path_rels),
                "relevance": relevance,
            }
        )

        # Solo se reescribe la línea `distributedTo:`; el resto del documento
        # viaja intacto. La versión anterior cortaba por `split("\n", 8)` y se
        # quedaba con `[:7]`: escribía siete líneas de frontmatter SIN el `---`
        # de cierre y tiraba el cuerpo entero. De ahí que la nota migrada fuese
        # la única `missingFrontmatter` del vault — el bloque nunca cerraba.
        staged_content = "\n".join(
            f"distributedTo: '{dest_folder}/{dest_name}'"
            if line.startswith("distributedTo:")
            else line
            for line in staged["content"].split("\n")
        )

        atomic_write_text(dest_path, staged_content)

        # Releer del disco y comprobar que el frontmatter parsea: el generador
        # no puede certificarse con su propio criterio (AP-44). Este defecto
        # sobrevivió porque nadie volvió a abrir lo que la tool escribió.
        escrito = dest_path.read_text(encoding="utf-8")
        if not _frontmatter_valido(escrito):
            raise ValueError(
                f"frontmatter ilegible tras escribir {dest_path.relative_to(_raiz())}"
            )

        stub_content = f"""# {Path(staged["originalName"]).stem}


> Este archivo fue migrado a: [[{safe_wikilink(str(dest_path_rels))}|{safe_wikilink(dest_folder)}/{safe_wikilink(dest_name)}]]


**Origen:** `{staged["originalPath"]}`

**Relevancia:** {relevance}

**Migrado:** {datetime.now(timezone.utc).strftime("%Y-%m-%d")}


---


_{staged["preview"][:200]}..._

"""

        # El stub queda junto al destino real, no bajo `10_Migrated/` otra vez.
        stub_path = _raiz() / dest_folder / f"_stub-{dest_name}"

        atomic_write_text(stub_path, stub_content)

        stubs_created.append(
            {
                "originalName": staged["originalName"],
                "stub": str(stub_path.relative_to(_raiz())),
            }
        )

    for staged_file in _staging_dir().glob("*.md"):
        staged_file.unlink()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    report_path = _migrated_dir() / f"_report-{slugify(project)}-{timestamp}.md"

    direct_count = sum(1 for d in distributed if d["relevance"] == "direct")

    indirect_count = sum(1 for d in distributed if d["relevance"] == "indirect")

    excluded_count = sum(1 for d in distributed if d["relevance"] == "excluded")

    report_lines = ["---"]

    report_lines.append(f"title: Migration Report - {project}")

    report_lines.append(f"project: {yaml_scalar(project)}")

    report_lines.append(f"date: {timestamp}")

    report_lines.append(f"type: migration-report")

    report_lines.append("---")

    report_lines.append(f"\n# Migration Report: {project}\n")

    report_lines.append(f"**Fecha:** {timestamp}")

    report_lines.append(f"**Total archivos procesados:** {len(staged_results)}")

    report_lines.append(f"**Directos:** {direct_count}")

    report_lines.append(f"**Indirectos:** {indirect_count}")

    report_lines.append(f"**Excluidos:** {excluded_count}")

    report_lines.append(f"**Errores:** {len(errors)}")

    report_lines.append(f"**Subcarpetas creadas:** {len(subfolders_created)}\n")

    if distributed:
        report_lines.append(
            "## Archivos Distribuidos\n\n| Archivo Original | Destino | Relevancia |"
        )

        report_lines.append("|---|---|---|")

        for d in distributed:
            report_lines.append(
                f"| `{d['originalName']}` | [[{safe_wikilink(d['destPath'])}]] | {d['relevance']} |"
            )

        report_lines.append("")

    if stubs_created:
        report_lines.append("## Stubs Creados\n\n")

        for s in stubs_created:
            report_lines.append(
                f"- `{s['originalName']}` → [[{safe_wikilink(s['stub'])}]]"
            )

        report_lines.append("")

    if subfolders_created:
        report_lines.append("## Subcarpetas Creadas\n\n")

        for sf in sorted(subfolders_created):
            report_lines.append(f"- {sf}")

        report_lines.append("")

    if errors:
        report_lines.append("## Errores\n\n| Archivo | Razón |")

        report_lines.append("|---|---|")

        for e in errors:
            report_lines.append(f"| `{e['path']}` | {e['reason']} |")

        report_lines.append("")

    atomic_write_text(report_path, "\n".join(report_lines))

    return {
        "ok": True,
        **write_report(),
        "dryRun": False,
        "project": project,
        "totalScanned": len(files),
        "totalStaged": len(staged_results),
        "distributed": {
            "direct": direct_count,
            "indirect": indirect_count,
            "excluded": excluded_count,
        },
        # `distributed` son conteos y se conserva tal cual (no-derogación). Pero
        # con solo conteos no se puede comprobar DÓNDE aterrizó cada fichero, y
        # por eso el destino duplicado (`10_Migrated/10_Migrated/…`) sobrevivió:
        # la salida decía "1 indirect" y eso era cierto. La ruta, aparte.
        "distributedFiles": [
            {
                "originalName": d["originalName"],
                "destPath": str(Path(d["destPath"]).as_posix()),
                "relevance": d["relevance"],
            }
            for d in distributed
        ],
        "subfoldersCreated": subfolders_created,
        "stubsCreated": len(stubs_created),
        "reportFile": str(report_path.relative_to(_raiz())),
        "message": f"Migration complete: {direct_count} direct, {indirect_count} indirect, {excluded_count} excluded. {len(subfolders_created)} subfolders created.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Vault Migrate Docs Tool (3-phase)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Ejemplos:

  python vault_migrate_docs.py --source_path "C:/docs" --project "ans" --keywords "Ansible MCP" --dry_run true

  python vault_migrate_docs.py --source_path "C:/old-docs" --project "mi-api" --dry_run false

  python vault_migrate_docs.py --source_path "docs/" --project "ans" --formats ".md" ".txt" --dry_run true

  python vault_migrate_docs.py --source_path "/repos/backend/docs" --project "backend" --keywords "API REST" --dry_run false



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Flujo de 3 fases: STAGING -> CLASSIFICATION -> DISTRIBUTION

  - Nunca migra archivos de codigo fuente (.py, .js, .ts, etc.)

  - dry_run=true (default) solo muestra lo que se haria

""",
    )

    parser.add_argument("--source_path", required=True, help="Source directory")

    parser.add_argument("--project", required=True, help="Project slug")

    parser.add_argument("--keywords", nargs="*", help="Additional keywords")

    parser.add_argument(
        "--formats", nargs="*", default=[".md"], help="Formats to process"
    )

    parser.add_argument(
        "--dry_run",
        type=lambda x: x.lower() == "true",
        default=True,
        help="Dry run mode",
    )

    args = parser.parse_args()

    result = vault_migrate_docs(
        args.source_path,
        args.project,
        args.keywords,
        args.formats,
        args.dry_run,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_migrate_docs"))
