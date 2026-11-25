#!/usr/bin/env python3
"""
Vault Code Review — Revision determinista de PR / diff / archivos guiada por el vault.

Combina el enfoque dual de trazabilidad declarativa:
  1. Codigo -> Vault: lee etiquetas `@vault:` a nivel de archivo y de metodo/simbolo
     (incluidos codigos cortos como `REQ-042`, `QA-003`, `FLOW-007` y `#anclas`)
     y entrega al revisor humano o IA las reglas de negocio vigentes sin saturar el codigo.
  2. Vault -> Codigo (RDD): cruza los simbolos tocados con `14_Requirements/`, `11_Code/`,
     `15_Tests/` y operaciones de logica de negocio `PAT-10`, mas seguridad acotada al diff,
     higiene estatica (`AP-51`), impacto en backlinks y visor web HTML clicable.

Usage:
    python vault_code_review.py --project "mi-api"
    python vault_code_review.py --path . --base main --head HEAD
    python vault_code_review.py --path . --staged --report
    python vault_code_review.py --path . --files src/fiscal.py --html-preview
    python vault_code_review.py --path . --base main --head HEAD --run-linters --save
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from vault_entorno import agente_por_defecto
from vault_errors import emit_error, proyecto_registrado, wrap_main
from vault_io import (
    PoliticaInvalidaError,
    assert_within_vault,
    atomic_write_text,
    client_cwd,
    resolve_input_path,
    write_report,
    xp_level_declarado,
)
from vault_lib import slugify_strict, utcnow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.grafo.repositorio import RepositorioGrafo  # noqa: E402
from vault.kernel import code_review as _cr  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402


def _repo(root: Optional[Path] = None) -> RepositorioGrafo:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioGrafo(construir(root))


def _raiz(root: Optional[Path] = None) -> Path:
    return _repo(root).raiz


def _formatear_reporte_markdown(res: Dict[str, Any]) -> str:
    """Construye un informe legible en Markdown con hallazgos y reglas vivas aplicables."""
    s = res["summary"]
    lines: List[str] = [
        f"# Code Review — {res.get('project') or Path(res['repo']).name}",
        "",
        f"**Veredicto:** `{res['verdict']}` | **Alcance:** `{res['review_scope']}`",
        f"**Archivos revisados:** {s['files_reviewed']} | **Símbolos tocados:** {s['symbols_touched']} | "
        f"**Reglas `@vault:` activas:** {s['applicable_rules']}",
        f"**Hallazgos:** {s['blockers']} bloqueantes · {s['warnings']} advertencias · {s['infos']} informativos",
        "",
    ]

    if res.get("applicable_rules"):
        lines.append("## Reglas de negocio y documentación referenciada (`@vault:`)")
        lines.append("")
        for rule in res["applicable_rules"]:
            sym = f" (`{rule['symbol']}`)" if rule.get("symbol") else ""
            lines.append(
                f"- `{rule['file']}:{rule['line']}`{sym} → **`{rule['raw_ref']}`** "
                f"(`{rule['note_path']}`, estado: `{rule['status']}`)"
            )
            excerpt = (rule.get("rules_excerpt") or "").strip()
            if excerpt:
                preview = " ".join(excerpt.splitlines()[:3])[:220]
                lines.append(f"  > {preview}")
        lines.append("")

    if res.get("findings"):
        lines.append("## Hallazgos")
        lines.append("")
        for fnd in res["findings"]:
            loc = f"`{fnd['file']}:{fnd['line']}` " if fnd.get("file") else ""
            lines.append(
                f"- **[{fnd['severity'].upper()} / {fnd['code']}]** {loc}{fnd['message']}"
            )
            if fnd.get("suggested_command"):
                lines.append(f"  - Sugerencia: `{fnd['suggested_command']}`")
        lines.append("")
    else:
        lines.append("## Hallazgos")
        lines.append("")
        lines.append("Sin bloqueantes ni advertencias detectadas.")
        lines.append("")

    imp = res.get("vault_impact") or {}
    if imp.get("direct_notes") or imp.get("backlink_impacted_notes"):
        lines.append("## Impacto documental en el vault")
        lines.append("")
        for n in imp.get("direct_notes") or []:
            lines.append(f"- Directa: `{n}`")
        for n in (imp.get("backlink_impacted_notes") or [])[:10]:
            lines.append(f"- Backlink: `{n}`")
        lines.append("")

    rdd = res.get("rdd_traceability")
    if rdd:
        lines.append("## Matriz RDD (Requerimientos ↔ Métodos ↔ Tests)")
        lines.append("")
        lines.append(
            f"- Total requisitos: {rdd['total_requirements']} | "
            f"Con método `@vault:`: {rdd['with_code_methods']} | "
            f"Cobertura completa: {rdd['full_coverage']} | "
            f"Aprobados sin cobertura: {rdd['uncovered_approved']}"
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _guardar_reporte_vault(
    raiz: Path,
    res: Dict[str, Any],
    agent: str,
) -> str:
    """Guarda el acta de revision en `19_Audits/code-review/` respetando AP-36."""
    now = utcnow()
    fecha = now[:10]
    proj_slug = slugify_strict(res.get("project") or Path(res["repo"]).name or "repo")
    scope_slug = slugify_strict(res.get("review_scope") or "review")[:32]
    rel_path = Path("19_Audits") / "code-review" / f"{fecha}-{proj_slug}-{scope_slug}.md"
    abs_path = raiz / rel_path
    assert_within_vault(abs_path, raiz)
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    cuerpo = _formatear_reporte_markdown(res)
    tags = ["audit", "code-review", proj_slug, res["verdict"].lower().replace("_", "-")]
    titulo_acta = f"Code Review — {proj_slug} ({res['review_scope']})"
    # AP-46 / AP-57: dueño único de escritura de frontmatter en el núcleo
    fm = (
        Frontmatter()
        .set("id", str(uuid.uuid4()))
        .set("title", titulo_acta, texto=True)
        .set("type", "audit")
        .set("status", "draft")
        .set("project", proj_slug, texto=True)
        .set("agent", agent, texto=True)
        .set("tags", tags)
        .set("verdict", res["verdict"])
        .set("cia_integrity", "high")
        .set("cia_availability", "medium")
        .set("cia_sensitivity", "internal")
        .set("createdAt", now)
        .set("updatedAt", now)
    )
    atomic_write_text(abs_path, fm.render() + "\n\n" + cuerpo)
    return str(rel_path).replace("\\", "/")


def _guardar_html_vault(
    raiz: Path,
    res: Dict[str, Any],
    html_content: str,
) -> str:
    """Guarda el visor web HTML clicable en `19_Audits/previews/` respetando AP-36."""
    proj_slug = slugify_strict(res.get("project") or Path(res["repo"]).name or "repo")
    scope_slug = slugify_strict(res.get("review_scope") or "review")[:32]
    rel_path = Path("19_Audits") / "previews" / f"{proj_slug}-{scope_slug}-review.html"
    abs_path = raiz / rel_path
    assert_within_vault(abs_path, raiz)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(abs_path, html_content)
    return str(rel_path).replace("\\", "/")


def vault_code_review(
    path: Optional[str] = None,
    project: Optional[str] = None,
    base: Optional[str] = None,
    head: Optional[str] = None,
    staged: bool = False,
    files: Optional[Sequence[str]] = None,
    run_linters: bool = False,
    include_rdd: bool = True,
    html_preview: bool = False,
    save: bool = False,
    agent: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> Dict[str, Any]:
    """Orquesta el Code Review / PR Review con trazabilidad `@vault:` y matriz RDD."""
    raiz = _raiz()
    repo_path: Optional[Path] = None

    if path:
        candidato = resolve_input_path(Path(path))
        if not candidato.exists():
            return emit_error("vault_code_review", "FILE_NOT_FOUND", f"Ruta no encontrada: {candidato}")
        repo_path = candidato if candidato.is_dir() else candidato.parent
    elif project:
        vinculado = _proyectos.ruta_local(raiz, project)
        if vinculado is not None and vinculado.is_dir():
            repo_path = vinculado

    if repo_path is None:
        if files:
            primero = resolve_input_path(Path(files[0]))
            repo_path = primero.parent if primero.exists() else client_cwd()
        else:
            # Sin --path ni repo enlazado: honestidad AP-45/AP-60 (NO_DATA, nunca APPROVE)
            return {
                "ok": True,
                **write_report(),
                "verdict": "NO_DATA",
                "review_scope": "no_repo_linked",
                "repo": "",
                "project": project,
                "summary": {
                    "scope": "no_repo_linked",
                    "verdict": "NO_DATA",
                    "files_reviewed": 0,
                    "symbols_touched": 0,
                    "applicable_rules": 0,
                    "blockers": 0,
                    "warnings": 0,
                    "infos": 0,
                    "impacted_vault_notes": 0,
                },
                "files": [],
                "touched_symbols": [],
                "applicable_rules": [],
                "findings": [],
                "vault_impact": {"direct_notes": [], "backlink_impacted_notes": [], "total_impacted": 0},
                "rdd_traceability": None,
                "linters": [],
                "html_preview_path": None,
                "saved_report_path": None,
                "note": "No hay repositorio enlazado para el proyecto ni se paso --path/--files.",
            }

    try:
        nivel_xp = xp_level_declarado(raiz)
    except PoliticaInvalidaError as exc:
        return emit_error("vault_code_review", "INVALID_INPUT", str(exc))

    res = _cr.ejecutar_code_review(
        raiz,
        repo_path,
        project=project,
        base=base,
        head=head,
        staged=staged,
        files=files,
        run_linters=run_linters,
        include_rdd=include_rdd,
        generar_html=html_preview,
        xp_level=nivel_xp,
        reviewer=reviewer,
        agent=agent or agente_por_defecto(),
    )
    if not res.get("ok"):
        return emit_error(
            "vault_code_review",
            str(res.get("error_code") or "INVALID_ACTION"),
            str(res.get("message") or "No se pudo completar la revision de codigo."),
        )

    html_content = res.pop("html_content", None)
    html_rel: Optional[str] = None
    saved_note: Optional[str] = None

    if html_preview and html_content:
        html_rel = _guardar_html_vault(raiz, res, html_content)
    if save:
        saved_note = _guardar_reporte_vault(raiz, res, agent or agente_por_defecto())

    res.update(write_report())
    res["html_preview_path"] = html_rel
    res["saved_report_path"] = saved_note
    return res


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Code Review — revision de PR/diff/archivos con trazabilidad @vault:, RDD y PAT-10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--path", help="Ruta al repositorio o carpeta de codigo fuente a revisar")
    parser.add_argument(
        "--project",
        type=proyecto_registrado("vault_code_review"),
        help="Slug del proyecto (resuelve repo enlazado y desambigua IDs cortos como REQ-042)",
    )
    parser.add_argument("--base", help="Referencia git base del diff (ej: main o commit SHA)")
    parser.add_argument("--head", help="Referencia git destino del diff (default: HEAD)")
    parser.add_argument("--staged", action="store_true", help="Revisar unicamente los cambios en staging (`git diff --cached`)")
    parser.add_argument("--files", nargs="+", help="Lista explicita de archivos fuente a revisar sin exigir diff git")
    parser.add_argument("--run-linters", action="store_true", help="Ejecutar linters instalados (ruff/eslint) sobre archivos tocados")
    parser.add_argument("--no-rdd", action="store_true", help="Omitir el calculo de matriz de trazabilidad RDD")
    parser.add_argument("--html-preview", action="store_true", help="Generar visor web HTML autocontenido con @vault: clicables en 19_Audits/previews/")
    parser.add_argument("--save", action="store_true", help="Guardar acta de revision en 19_Audits/code-review/")
    parser.add_argument("--report", action="store_true", help="Emitir informe legible en Markdown en lugar de JSON")
    parser.add_argument("--strict", action="store_true", help="Retornar codigo de salida 1 si el veredicto es REQUEST_CHANGES")
    parser.add_argument("--agent", default=agente_por_defecto(), help="Agente que firma el acta cuando se usa --save")
    parser.add_argument("--reviewer", default=None, help="Revisor humano de pareja (XP Nivel 3, SP-06)")

    args = parser.parse_args()
    result = vault_code_review(
        path=args.path,
        project=args.project,
        base=args.base,
        head=args.head,
        staged=args.staged,
        files=args.files,
        run_linters=args.run_linters,
        include_rdd=not args.no_rdd,
        html_preview=args.html_preview,
        save=args.save,
        agent=args.agent,
        reviewer=args.reviewer,
    )

    if args.report and result.get("ok"):
        print(_formatear_reporte_markdown(result))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get("ok"):
        return 1
    if args.strict and result.get("verdict") == "REQUEST_CHANGES":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_code_review"))
