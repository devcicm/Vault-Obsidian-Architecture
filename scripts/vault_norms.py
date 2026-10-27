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
import hashlib
import json
import re
import sys
from vault_errors import emit_error, wrap_main
from vault_version import CURRENT_VERSION  # generator_version de los artefactos (AP-47)
from vault_io import atomic_write_json, file_lock, normalize_stem
from vault_lib import cargar_bloque_tolerante, parse_frontmatter, separar_frontmatter
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.kernel.contenido import (  # noqa: E402
    es_adr,
    falta_de_evaluacion_de_impacto,
    falta_de_responsable,
    niveles_de_impacto_exigidos,
    secciones_adr_faltantes,
)
from vault_vocabulario import valores as _vocabulario  # noqa: E402
from vault_registry import regimen_de_estado  # noqa: E402
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Reexportación: la superficie que el repo consumía antes del corte ─────────
# Lo de aquí abajo no lo usa este fichero: lo usan los llamadores. Un import
# «sin usar» que en realidad es la superficie pública se marca con `noqa: F401`
# en vez de borrarse, porque quitarlo rompería a 26 módulos sin que nada en este
# fichero lo notara.
from vault_norms_catalog import (  # noqa: F401
    VINETA_VACIA,
    vinetas_de_lista,
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
    vault_norms_audit as _vault_norms_audit,
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
    bloque, cuerpo = separar_frontmatter(content)
    # AP-44 (deuda #5): los campos los lee el kernel; aquí solo se mira presencia.
    fm: Dict[str, Any] = (
        cargar_bloque_tolerante(bloque, texto=True)[0] if bloque is not None else {}
    )

    if not fm.get("agent"):
        _add("AP-16", "campo agent ausente en frontmatter")
    if not fm.get("createdAt") or not fm.get("updatedAt"):
        _add("AP-13", "timestamps createdAt/updatedAt ausentes o incompletos")
    if not fm.get("id") or not fm.get("title"):
        _add("AP-12", "campos id/title ausentes en frontmatter")

    # Content length
    body = cuerpo
    real_lines = [
        l for l in body.split("\n") if l.strip() and not l.strip().startswith("TODO")
    ]
    if len(real_lines) == 0:
        _add("AP-11", "sin contenido real — skeleton file")
    elif len(real_lines) < 3:
        _add("AP-11", f"solo {len(real_lines)} línea(s) real(es) — posible skeleton")

    # Bullet ratio (AP-20)
    bullets = vinetas_de_lista(body)
    if bullets:
        empty = [b for b in bullets if b in VINETA_VACIA]
        ratio = len(empty) / len(bullets)
        if ratio > 0.5:
            _add("AP-20", f"{int(ratio * 100)}% de bullets vacíos — deceptive skeleton")

    # Wiki-link checks
    clean = re.sub(r"```[\s\S]*?```", "", body)
    clean = re.sub(r"`[^`]+`", "", clean)
    wiki_links = re.findall(r"\[\[((?:[^\[\]]|\[(?!\[))+)\]\]", clean)

    if wiki_links:
        # Un solo índice para AP-21 y AP-14, con el criterio de Obsidian
        # (nombre de fichero, sufijo de ruta y `aliases:`; sin instantáneas).
        from vault_io import is_snapshot_path
        from vault_lib import (indice_de_nombres, inventario_de_nombres,
                               resolver_wikilink, ruta_necesaria)

        indice = indice_de_nombres(*inventario_de_nombres(_raiz(), is_snapshot_path))

        # AP-21: path-anchored — el `/` cuenta solo en el destino, no en el
        # alias. `vault_regex.RE_PATH_ANCHORED` ya lo tenía escrito y anotado
        # ("un '/' en el alias es válido"); esta copia no se enteró y medía el
        # enlace entero. Destapado por la regla 7: 0 casos en `vault-sandbox`
        # —que este repo genera— y 2 en cada uno de los dos vaults ajenos, uno
        # de ellos `[[nota|Pipeline CI/CD]]`, donde la barra está dentro de
        # "CI/CD". Un alias con una barra no es un enlace anclado a ruta.
        path_links = [l for l in wiki_links if "/" in l.split("|")[0]]
        if path_links:
            # AP-21 precisado (v40.35): la ruta que desambigua dos notas del
            # mismo nombre es legítima. Lo decide el dueño, sobre el vault.
            path_links = [
                l for l in path_links if not ruta_necesaria(l, Path(rel), indice)
            ]
        if path_links:
            _add("AP-21", f"path-anchored wiki-links: {path_links[:3]}")

        # AP-22: bracket balance
        opens = len(re.findall(r"\[\[", clean))
        closes = len(re.findall(r"\]\]", clean))
        empty_brackets = re.findall(r"\[\[\s*\]\]", clean)
        if opens != closes or empty_brackets:
            _add("AP-22", f"corchetes desbalanceados ({opens} vs {closes}) o vacíos")

        # AP-14: enlace fantasma, decidido como lo decide Obsidian (AP-44).
        # Hasta la auditoría del 2026-10-15 se comparaba `normalize_stem` del
        # enlace con el de cada fichero: el plegado quita guiones y espacios,
        # así que `[[Elegir PostgreSQL]]` «resolvía» contra
        # `elegir-postgresql.md` —Obsidian crea una nota vacía—, y un alias, un
        # sufijo de ruta o un `#sección` salían como fantasmas. El dueño es
        # `vault_lib.resolver_wikilink`; las instantáneas ya las excluye el
        # inventario, así que una copia en un backup no hace resolver nada.
        # Un enlace ambiguo (varios candidatos) no está roto: es AP-21/AP-17.
        ghost = [
            l for l in wiki_links
            if not resolver_wikilink(l, Path(rel), indice)[1]
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
    # AP-07 con el criterio del dueño (v41.3). Hasta aquí decidía por la
    # subcadena `adr` en la ruta —`07_Knowledge/padre.md` era un ADR— y exigía
    # a la vez «contexto» y «context», así que un ADR completo en castellano
    # salía siempre incompleto. Los stubs y plantillas se rigen por AP-03.
    if es_adr(rel, fm.get("type", "")) and fm.get("status", "").lower() not in ("stub", "template"):
        faltan = secciones_adr_faltantes(body)
        if faltan:
            _add("AP-07", f"ADR incompleto: faltan {', '.join(faltan)}")
    # AP-64 con el mismo dueño que la auditoría: el régimen sale del estado
    # canónico, así que un `accepted` cuenta como `approved` (cerrado).
    if es_adr(rel, fm.get("type", "")):
        canonico = normalize_status(str(fm.get("status") or ""))[0] if fm.get("status") else None
        if canonico in STATUS_TRANSITIONS:
            motivo = falta_de_responsable(fm, regimen_de_estado(canonico, STATUS_TRANSITIONS))
            if motivo:
                _add("AP-64", motivo)
    # AP-65 (ISO/IEC 42005): mismo dueño y misma escala que la auditoría.
    motivo = falta_de_evaluacion_de_impacto(
        rel, fm, niveles_de_impacto_exigidos(_vocabulario("severidad")))
    if motivo:
        _add("AP-65", motivo)

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

    bloque, cuerpo = separar_frontmatter(content)
    if bloque is None:
        return emit_error("vault_norms", "FRONTMATTER_PARSE_ERROR",
                          f"Frontmatter sin cierre `---` en {path}")

    # AP-44: `norm_refs` se lee con el parser real. El regex por líneas tomaba
    # `norm_refs:\n- AP-01` —lista en bloque, YAML válido— como el valor
    # `- AP-01` y lo reescribía como `["- AP-01", …]`.
    existing_refs = parse_frontmatter(content).get("norm_refs") or []
    if not isinstance(existing_refs, list):
        existing_refs = [existing_refs]
    if code in existing_refs:
        return {
            "ok": True,
            "path": path,
            "norm_refs": existing_refs,
            "message": f"{code} already present",
        }
    existing_refs = [*existing_refs, code]

    # AP-46: el dueño reemplaza la clave en su sitio, continuación incluida.
    new_content = (
        Frontmatter.editar(bloque).set("norm_refs", existing_refs).render()
        + "\n" + cuerpo
    )

    from vault_io import atomic_write_text

    atomic_write_text(note_path, new_content)

    return {
        "ok": True,
        "path": path,
        "norm_refs": existing_refs,
        "message": f"Added {code} to norm_refs",
    }


def vault_norms_rebuild() -> Dict[str, Any]:
    """Regenerate 00_System/norm-registry.json from the embedded catalog.

    Idempotente: si el contenido es idéntico al existente, no reescribe.
    Bajo lock para evitar race conditions con otras tools que escriban el mismo
    archivo (AP-54).
    """
    from datetime import datetime, timezone

    registry = {
        "version": "v29",
        "generator_version": CURRENT_VERSION,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "total": len(NORM_CATALOG),
        "antipatterns": len([n for n in NORM_CATALOG if n["type"] == "antipattern"]),
        "patterns": len([n for n in NORM_CATALOG if n["type"] == "pattern"]),
        "by_severity": {
            sev: len([n for n in NORM_CATALOG if n["severity"] == sev])
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

    registry_path = _norm_registry()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    # Hash de los campos estables (excluye updated_at que cambia en cada ejecución)
    contenido_estable = json.dumps(
        {k: v for k, v in registry.items() if k != "updated_at"},
        indent=2, ensure_ascii=False,
    )
    nuevo_hash = hashlib.sha256(contenido_estable.encode()).hexdigest()

    escrito = 0
    with file_lock(registry_path):
        if registry_path.exists():
            reg_existente = json.loads(registry_path.read_text(encoding="utf-8"))
            estable_existente = json.dumps(
                {k: v for k, v in reg_existente.items() if k != "updated_at"},
                indent=2, ensure_ascii=False,
            )
            if hashlib.sha256(estable_existente.encode()).hexdigest() == nuevo_hash:
                escrito = 0
            else:
                atomic_write_json(registry_path, registry)
                escrito = 1
        else:
            atomic_write_json(registry_path, registry)
            escrito = 1

    return {
        "ok": True,
        "registry": str(registry_path.relative_to(_raiz())).replace("\\", "/"),
        "total": registry["total"],
        "antipatterns": registry["antipatterns"],
        "patterns": registry["patterns"],
        "by_severity": registry["by_severity"],
        "written": escrito,
    }


# ─── CLI ───────────────────────────────────────────────────────────────────────


def _checks_estandar(flag, registrar=None) -> list:
    """Los tres controles obligatorios, por el PUERTO del nucleo (DEC-02).

    Antes esta funcion importaba a los duenos (`vault_mcp_catalog`,
    `vault_smoke`, `vault_voice`) dentro de funciones: funcionaba, pero
    gobernanza dependia de meta_toolkit y de autoria, y esos cinco simbolos
    eran los cinco sitios fuera de puerto de la puerta de arquitectura.

    Ahora el contrato es DATOS: `vault.kernel.controles.CONTROLES` dice que
    superficie responde a cada control, y aqui se lanza como PROCESO. Un
    proceso no es una arista del grafo de imports; la evidencia la sigue
    produciendo el dueno (su tool, su exit code, su envelope), y un control
    que no pudo correr vuelve como `no_ejecutado`/`fallido`, nunca como cero
    hallazgos (TD-0003, fail-closed).

    Compatibilidad publica: `vault_norms_audit()` y el envelope del audit no
    cambian; las funciones privadas `_control_ap40/42/43` se retiraron por ser
    privadas (sin contrato) y su comportamiento lo cubre el puerto con las
    superficies `--check-params`, `--baseline-check` y `--coverage`.
    """
    from vault.kernel import controles as _puerto

    checks = []
    for codigo in _puerto.CONTROLES:
        resultado = _puerto.ejecutar(codigo)
        for problema in resultado.get("problemas") or []:
            flag(codigo, problema.get("clave") or f"{codigo}#?",
                 problema.get("detalle") or "")
        checks.append({
            "control": resultado["control"],
            "estado": resultado["estado"],
            "detalle": resultado["detalle"],
            "hallazgos": resultado["hallazgos"],
        })
    if registrar is not None:
        for check in checks:
            registrar(check)
    return checks


def vault_norms_audit(root=None):
    """Auditoria publica: runtime + los tres controles del estandar (TD-0003).

    La composicion vive aqui, no en el motor, porque `vault_mcp_catalog`,
    `vault_smoke` y `vault_voice` no viajan en la wheel de producto.
    """
    resultado = _vault_norms_audit(root, insertar_checks_estandar=_checks_estandar)
    return resultado


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
        allow_abbrev=False,
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
        # `--root` ya lo acepta esta tool (es una de las que escriben, en la regla 1).
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
        if args.strict and (result.get("total_violations")
                            or result.get("completo") is False):
            # TD-0003: una auditoria INCOMPLETA no puede pasar la puerta. `ok`
            # sigue siendo True (el audit corrio); lo que cambia es el exit
            # code, para no romper a los lectores del envelope.
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
