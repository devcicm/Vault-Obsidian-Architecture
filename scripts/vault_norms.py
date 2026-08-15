#!/usr/bin/env python3
"""
Vault Norms — la puerta de entrada al catálogo de normas del estándar.

Gestiona AP-XX (anti-patrones) y PAT-X (patrones recomendados): lista, filtra,
muestra detalles, escanea notas para detectar normas aplicables, aplica referencias
de normas a frontmatter, y reconstruye norm-registry.json.

**Este módulo era de 5.158 líneas y en v40.26 se partió en tres.** No era un
problema de clasificación —su fan-in es 26, no el del núcleo—: era catálogo,
motor y fachada a la vez, y el 60% del fichero lo ocupaba una sola constante.
Ahora:

- `vault_norms_catalog` — los datos: `NORM_CATALOG` y el vocabulario de estado.
  No lee el vault, no escribe nada, no importa ninguna tool.
- `vault_norms_engine` — el motor: `vault_norms_audit`, el drift del marco y el
  heal de AP-46.
- este módulo — la fachada de datos, la CLI, y la **reexportación** de todo lo
  que el repo consumía antes del corte.

**Por qué la reexportación es el punto del cambio y no un apaño.** La superficie
externa real son siete símbolos (`NORM_CATALOG`, `status_frontmatter_lines`,
`compute_norm_refs`, `STATUS_VOCAB`, `norma_por_codigo`, `cuerpo_sin_marcadores`,
`vault_norms_audit`), y los tests usan cinco privados más. Reexportarlos todos
hace que **ningún llamador se toque**, y eso es lo que permite leer el diff como
movimiento puro: si algo se rompe, fue el movimiento y no una corrección colada
dentro. Recortar de paso la superficie que usan los tests habría mezclado dos
cambios y hecho imposible saber cuál rompió qué; eso va aparte, si va.

El puerto declarado del contexto de gobernanza sigue siendo este módulo. Se
declaró `vault_norms:vault_norms_audit` en el commit **anterior** al corte a
propósito: la baseline de cruces se indexa por la cadena `origen -> destino`, así
que hacerlo aquí habría mezclado «este cruce siempre fue legítimo» con «este
cruce cambió de módulo», y no habría forma de saber cuál movió la cifra.

Usage:
    python vault_norms.py --list
    python vault_norms.py --list --type ap --severity critical
    python vault_norms.py --list --category linking --sort severity
    python vault_norms.py --show AP-22
    python vault_norms.py --scan --path "07_Knowledge/concepts/jwt.md"
    python vault_norms.py --apply AP-22 --path "03_Decisions/adr-001.md"
    python vault_norms.py --rebuild
"""

import argparse
import json
import re
import sys
from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_json, normalize_stem
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Reexportación: la superficie que el repo consumía antes del corte ─────────
# Lo de aquí abajo no lo usa este fichero: lo usan los llamadores. Un import
# «sin usar» que en realidad es la superficie pública se marca con `noqa: F401`
# en vez de borrarse, porque quitarlo rompería a 26 módulos sin que nada en este
# fichero lo notara.
from vault_norms_catalog import (  # noqa: F401
    _NORM_BY_CODE,
    DOMAIN_STATUS_VOCABS,
    LIFECYCLE_REGISTRY,
    NORM_CATALOG,
    STATUS_QUALIFIERS,
    STATUS_SYNONYMS,
    STATUS_TRANSITIONS,
    STATUS_VOCAB,
    _canonical_status,
    _CATEGORY_ORDER,
    _SEVERITY_ORDER,
    compute_norm_refs,
    norma_por_codigo,
    normalize_status,
    split_domain_status,
    status_frontmatter_lines,
)
from vault_norms_engine import (  # noqa: F401
    SPEC_FILENAME,
    _CONTAMINATION_DEPTH,
    _ROOT_ALLOWED,
    _VAULT_ARTIFACT_NAMES,
    _cuerpo_sin_marcadores,
    _es_instantanea,
    _norm_registry,
    _planificar_ap46,
    _raiz,
    _repo,
    cuerpo_sin_marcadores,
    framework_drift_check,
    heal_ap46,
    vault_norms_audit,
)

# ─── Funciones públicas ────────────────────────────────────────────────────────


def vault_norms_list(
    norm_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    sort_by: str = "code",
) -> Dict[str, Any]:
    """List norms with optional filters."""
    norms = list(NORM_CATALOG)

    if norm_type:
        t = norm_type.lower()
        if t in ("ap", "antipattern"):
            norms = [n for n in norms if n["type"] == "antipattern"]
        elif t in ("pat", "pattern"):
            norms = [n for n in norms if n["type"] == "pattern"]

    if category:
        norms = [n for n in norms if n["category"] == category.lower()]

    if severity:
        norms = [n for n in norms if n["severity"].lower() == severity.lower()]

    if sort_by == "severity":
        norms.sort(key=lambda n: (_SEVERITY_ORDER.get(n["severity"], 9), n["code"]))
    elif sort_by == "category":
        norms.sort(key=lambda n: (_CATEGORY_ORDER.get(n["category"], 9), n["code"]))
    elif sort_by == "enforcement":
        norms.sort(key=lambda n: (n["enforcement"], n["code"]))
    else:
        norms.sort(key=lambda n: n["code"])

    rows = []
    for n in norms:
        rows.append(
            {
                "code": n["code"],
                "name": n["name"],
                "type": n["type"],
                "category": n["category"],
                "severity": n["severity"],
                "enforcement": n["enforcement"],
            }
        )

    return {
        "ok": True,
        "total": len(rows),
        "norms": rows,
    }


def vault_norms_show(code: str) -> Dict[str, Any]:
    """Show full details of a single norm by code."""
    code = code.upper()
    norm = _NORM_BY_CODE.get(code)
    if not norm:
        return emit_error(
            "vault_norms", "INVALID_ACTION",
            f"Norma '{code}' inexistente. Códigos válidos: {sorted(_NORM_BY_CODE.keys())}",
        )
    return {"ok": True, "norm": dict(norm)}


def vault_norms_scan(path: str) -> Dict[str, Any]:
    """Detect which norms are applicable to a vault note based on content analysis."""
    note_path = _raiz() / path
    if not note_path.exists():
        return emit_error("vault_norms", "NOTE_NOT_FOUND", f"No existe la nota: {path}")

    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return emit_error("vault_norms", "FILE_READ_ERROR", f"No se pudo leer {path}: {e}", exception=e)

    rel = path.replace("\\", "/")
    folder = rel.split("/")[0] if "/" in rel else ""

    applicable: List[Dict[str, Any]] = []

    def _add(code: str, reason: str) -> None:
        norm = _NORM_BY_CODE.get(code)
        if norm:
            applicable.append({"code": code, "name": norm["name"], "reason": reason})

    # Frontmatter checks
    has_frontmatter = content.startswith("---")
    fm: Dict[str, str] = {}
    if has_frontmatter:
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip("\"'")

    if not fm.get("agent"):
        _add("AP-16", "campo agent ausente en frontmatter")
    if not fm.get("createdAt") or not fm.get("updatedAt"):
        _add("AP-13", "timestamps createdAt/updatedAt ausentes o incompletos")
    if not fm.get("id") or not fm.get("title"):
        _add("AP-12", "campos id/title ausentes en frontmatter")

    # Content length
    body = content.split("---", 2)[-1] if has_frontmatter else content
    real_lines = [
        l for l in body.split("\n") if l.strip() and not l.strip().startswith("TODO")
    ]
    if len(real_lines) == 0:
        _add("AP-11", "sin contenido real — skeleton file")
    elif len(real_lines) < 3:
        _add("AP-11", f"solo {len(real_lines)} línea(s) real(es) — posible skeleton")

    # Bullet ratio (AP-20)
    bullets = re.findall(r"^\s*[-*]\s*(.*)", body, re.MULTILINE)
    if bullets:
        empty = [
            b
            for b in bullets
            if not b.strip() or b.strip() in ("[]", "[[]]", "-", "[ ]")
        ]
        ratio = len(empty) / len(bullets)
        if ratio > 0.5:
            _add("AP-20", f"{int(ratio * 100)}% de bullets vacíos — deceptive skeleton")

    # Wiki-link checks
    clean = re.sub(r"```[\s\S]*?```", "", body)
    clean = re.sub(r"`[^`]+`", "", clean)
    wiki_links = re.findall(r"\[\[([^\]]+)\]\]", clean)

    if wiki_links:
        # AP-21: path-anchored — el `/` cuenta solo en el destino, no en el
        # alias. `vault_regex.RE_PATH_ANCHORED` ya lo tenía escrito y anotado
        # ("un '/' en el alias es válido"); esta copia no se enteró y medía el
        # enlace entero. Destapado por la regla 7: 0 casos en `vault-sandbox`
        # —que este repo genera— y 2 en cada uno de los dos vaults ajenos, uno
        # de ellos `[[nota|Pipeline CI/CD]]`, donde la barra está dentro de
        # "CI/CD". Un alias con una barra no es un enlace anclado a ruta.
        path_links = [l for l in wiki_links if "/" in l.split("|")[0]]
        if path_links:
            _add("AP-21", f"path-anchored wiki-links: {path_links[:3]}")

        # AP-22: bracket balance
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        empty_brackets = re.findall(r"\[\[\s*\]\]", clean)
        if opens != closes or empty_brackets:
            _add("AP-22", f"corchetes desbalanceados ({opens} vs {closes}) o vacíos")

        # AP-14: check for ghost links (note doesn't exist)
        all_stems = {
            p.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
            for p in _raiz().rglob("*.md")
            # El hueco simétrico al del barrido principal, y en la direccion
            # contraria: si los stems de las instantaneas cuentan, un enlace
            # fantasma "resuelve" porque existe una COPIA en un backup. La nota
            # viva ya no está y AP-14 no lo ve.
            if not _es_instantanea(str(p.relative_to(_raiz())))
        }
        ghost = [
            l
            for l in wiki_links
            if l.split("|")[0]
            .strip()
            .lower()
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
            not in all_stems
        ]
        if ghost:
            _add("AP-14", f"wiki-links posiblemente rotos: {ghost[:3]}")
    else:
        # AP-22: check even without wiki-links (unmatched brackets in text)
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        if opens != closes:
            _add("AP-22", f"corchetes desbalanceados ({opens} vs {closes})")

    # Folder-specific checks
    if "03_Decisions" in rel or "adr" in rel.lower():
        sections = re.findall(r"^#{1,3}\s+(.+)", body, re.MULTILINE)
        section_names = [s.lower() for s in sections]
        missing = [
            s
            for s in (
                "contexto",
                "context",
                "opciones",
                "options",
                "consecuencias",
                "consequences",
            )
            if not any(s in n for n in section_names)
        ]
        if missing:
            _add(
                "AP-07", f"ADR posiblemente incompleto (secciones faltantes detectadas)"
            )

    # La sección es `08_Runbooks`; aquí se comparaba contra `06_Runbooks`, que
    # no existe. La condición era por tanto siempre cierta: un runbook guardado
    # correctamente en `08_Runbooks/` se reportaba como fuera de sitio, y uno
    # realmente extraviado se reportaba igual. El guard no distinguía nada.
    if "08_Runbooks" not in rel and any(
        kw in note_path.stem.lower() for kw in ("runbook", "procedure", "playbook")
    ):
        _add("AP-09", "runbook fuera de 08_Runbooks/")

    # Always recommend PAT-5 (provenance chain)
    if not all(fm.get(f) for f in ("id", "createdAt", "updatedAt", "agent")):
        _add("PAT-5", "cadena de provenance incompleta (id/createdAt/updatedAt/agent)")

    return {
        "ok": True,
        "path": rel,
        "applicable_norms": applicable,
        "total": len(applicable),
    }


def vault_norms_apply(code: str, path: str) -> Dict[str, Any]:
    """Add a norm_refs entry to a note's frontmatter."""
    code = code.upper()
    if code not in _NORM_BY_CODE:
        return emit_error("vault_norms", "INVALID_ACTION",
                          f"Norma '{code}' inexistente; consulta `--list` para los códigos válidos")

    note_path = _raiz() / path
    if not note_path.exists():
        return emit_error("vault_norms", "NOTE_NOT_FOUND", f"No existe la nota: {path}")

    try:
        content = note_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return emit_error("vault_norms", "FILE_READ_ERROR", f"No se pudo leer {path}: {e}", exception=e)

    if not content.startswith("---"):
        return emit_error(
            "vault_norms", "FRONTMATTER_MISSING",
            "La nota no tiene frontmatter YAML; créala con `vault_write`.",
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        return emit_error("vault_norms", "FRONTMATTER_PARSE_ERROR",
                          f"Frontmatter sin cierre `---` en {path}")

    fm_block = parts[1]
    body = parts[2]

    # Parse existing norm_refs
    norm_refs_match = re.search(r"^norm_refs:\s*(.+)$", fm_block, re.MULTILINE)
    if norm_refs_match:
        existing_raw = norm_refs_match.group(1).strip()
        try:
            existing_refs = json.loads(existing_raw)
        except json.JSONDecodeError:
            existing_refs = [
                r.strip().strip('"')
                for r in existing_raw.strip("[]").split(",")
                if r.strip()
            ]
        if code in existing_refs:
            return {
                "ok": True,
                "path": path,
                "norm_refs": existing_refs,
                "message": f"{code} already present",
            }
        existing_refs.append(code)
        new_refs_line = f"norm_refs: {json.dumps(existing_refs)}"
        fm_block = re.sub(
            r"^norm_refs:\s*.+$", new_refs_line, fm_block, flags=re.MULTILINE
        )
    else:
        # Insert norm_refs after last field in frontmatter
        new_refs_line = f"norm_refs: {json.dumps([code])}"
        fm_block = fm_block.rstrip("\n") + f"\n{new_refs_line}\n"

    new_content = f"---{fm_block}---{body}"

    from vault_io import atomic_write_text

    atomic_write_text(note_path, new_content)

    # Read back to return final norm_refs
    norm_refs_match2 = re.search(r"^norm_refs:\s*(.+)$", fm_block, re.MULTILINE)
    final_refs = (
        json.loads(norm_refs_match2.group(1).strip()) if norm_refs_match2 else [code]
    )

    return {
        "ok": True,
        "path": path,
        "norm_refs": final_refs,
        "message": f"Added {code} to norm_refs",
    }


def vault_norms_rebuild() -> Dict[str, Any]:
    """Regenerate 00_System/norm-registry.json from the embedded catalog."""
    from datetime import datetime, timezone

    registry = {
        "version": "v29",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "total": len(NORM_CATALOG),
        "antipatterns": len([n for n in NORM_CATALOG if n["type"] == "antipattern"]),
        "patterns": len([n for n in NORM_CATALOG if n["type"] == "pattern"]),
        "by_severity": {
            sev: len([n for n in NORM_CATALOG if n["severity"] == sev])
            # Derivado del catálogo, no reescrito. Hasta v40.26 este literal
            # estaba exento de AP-49 porque `vault_norms` era el módulo fuente
            # del vocabulario; al mudarse el dato a `vault_norms_catalog` dejó
            # de serlo, y el guard vio lo que siempre había sido: una copia.
            for sev in _SEVERITY_ORDER
        },
        "by_category": {
            cat: len([n for n in NORM_CATALOG if n["category"] == cat])
            for cat in (
                "content-quality",
                "structure",
                "frontmatter",
                "linking",
                "process",
            )
        },
        "by_enforcement": {
            enf: len([n for n in NORM_CATALOG if n["enforcement"] == enf])
            for enf in ("guard", "audit", "guard+audit", "manual", "recommended")
        },
        "norms": NORM_CATALOG,
    }

    _norm_registry().parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_norm_registry(), registry)

    return {
        "ok": True,
        "registry": str(_norm_registry().relative_to(_raiz())).replace("\\", "/"),
        "total": registry["total"],
        "antipatterns": registry["antipatterns"],
        "patterns": registry["patterns"],
        "by_severity": registry["by_severity"],
    }


# ─── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Norms — catálogo de normas AP-XX y PAT-X",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Listar todas las normas
  python vault_norms.py --list

  # Filtrar por tipo, severidad o categoría
  python vault_norms.py --list --type ap --severity critical
  python vault_norms.py --list --category linking --sort severity
  python vault_norms.py --list --type pat

  # Detalle de una norma
  python vault_norms.py --show AP-22

  # Escanear una nota para detectar normas aplicables
  python vault_norms.py --scan --path "07_Knowledge/concepts/jwt.md"

  # Agregar referencia de norma al frontmatter
  python vault_norms.py --apply AP-22 --path "03_Decisions/adr-001.md"

  # Reconstruir norm-registry.json
  python vault_norms.py --rebuild
""",
    )

    parser.add_argument("--list", action="store_true", help="Listar normas")
    parser.add_argument(
        "--show", metavar="CODE", help="Mostrar detalle de una norma (ej: AP-22)"
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Escanear nota para detectar normas aplicables",
    )
    parser.add_argument(
        "--apply", metavar="CODE", help="Agregar referencia de norma al frontmatter"
    )
    parser.add_argument(
        "--rebuild", action="store_true", help="Regenerar norm-registry.json"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Auditar el vault contra las normas automatizables (AP-06/07/09/10/15/19, CN-02/03, SP-01)",
    )
    parser.add_argument(
        "--root", help="Vault root para --audit (default: VAULT_ROOT auto-detect)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Con --audit: salir con código 1 si hay violaciones (gate de CI). "
             "Sin este flag el audit informa pero siempre sale 0.",
    )
    parser.add_argument(
        "--check-framework",
        action="store_true",
        help="Verificar que el manifiesto documente todos los ids del marco de datos (CIA/F/FAIR/V/ISO)",
    )
    parser.add_argument(
        "--spec", help="Ruta del manifiesto para --check-framework (default: raíz del repo)"
    )
    parser.add_argument(
        "--path", help="Ruta relativa de la nota (para --scan y --apply)"
    )
    parser.add_argument(
        "--type",
        choices=["ap", "pat", "antipattern", "pattern"],
        help="Filtrar por tipo",
    )
    parser.add_argument(
        "--category",
        choices=["content-quality", "structure", "frontmatter", "linking", "process", "session-protocol", "convention"],
        help="Filtrar por categoria",
    )
    parser.add_argument(
        "--severity",
        # Mismo caso que el recuento por severidad: sale del catálogo. Se
        # excluye "N/A", que es la severidad de los PAT-X y no una opción de
        # filtrado útil.
        choices=[s for s in _SEVERITY_ORDER if s != "N/A"],
        help="Filtrar por severidad",
    )
    parser.add_argument(
        "--sort",
        choices=["code", "severity", "category", "enforcement"],
        default="code",
        help="Ordenar por (default: code)",
    )

    parser.add_argument(
        "--heal-ap46", action="store_true",
        help="Repara frontmatter roto (AP-46). Informe en seco salvo --apply-heal",
    )
    parser.add_argument(
        "--apply-heal", action="store_true",
        help="Con --heal-ap46: escribe de verdad, con backup en .history/",
    )

    args = parser.parse_args()

    if args.heal_ap46:
        # `--root` ya lo acepta esta tool (es una de las cuatro de la regla 1).
        # El heal escribe, así que el default es el informe: `--apply-heal` es
        # una segunda afirmación explícita, no un matiz de la primera.
        result = heal_ap46(Path(args.root) if args.root else None,
                           apply=args.apply_heal)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.audit:
        if args.root:
            from vault_io import set_vault_root
            set_vault_root(Path(args.root))  # AP-36: traces al vault objetivo
        result = vault_norms_audit(Path(args.root) if args.root else None)
        if args.strict and result.get("total_violations"):
            # `ok` sigue siendo True (el audit corrió bien); lo que cambia es el
            # exit code, para poder usarlo como gate sin romper a los lectores
            # que ya interpretan el envelope.
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1
    elif args.check_framework:
        result = framework_drift_check(Path(args.spec) if args.spec else None)
    elif args.rebuild:
        result = vault_norms_rebuild()
    elif args.show:
        result = vault_norms_show(args.show)
    elif args.scan:
        if not args.path:
            parser.error("--scan requiere --path")
        result = vault_norms_scan(args.path)
    elif args.apply:
        if not args.path:
            parser.error("--apply requiere --path")
        result = vault_norms_apply(args.apply, args.path)
    elif args.list:
        result = vault_norms_list(
            norm_type=args.type,
            category=args.category,
            severity=args.severity,
            sort_by=args.sort,
        )
    else:
        parser.print_help()
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_norms"))
