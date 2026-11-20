#!/usr/bin/env python3

"""

Vault AI Decision Tool -- Log AI agent decisions (ISO/IEC 42001:2023 AIMS)



Records significant decisions made by AI agents with rationale, alternatives,

risks and human oversight status. Saves to 16_AI_Governance/decisions/.



Decision types: architectural, security, data-model, algorithm, configuration, process

Impact levels: low, medium, high, critical



Usage:

    python vault_ai_decision.py --project "mi-api" --title "Use JWT over sessions" --decision_type architectural --description "Decided to use stateless JWT tokens instead of server-side sessions" --rationale "Horizontal scaling requires stateless auth" --impact_level medium

    python vault_ai_decision.py --project "mi-api" --title "Hash algorithm: bcrypt" --decision_type security --description "Using bcrypt with cost factor 12 for password hashing" --rationale "bcrypt is resistant to GPU attacks; cost 12 balances security/performance" --alternatives '["argon2id - more secure but higher memory","sha256 - rejected: no salt by default"]' --risks '["Cost factor may need tuning under high load"]'

    python vault_ai_decision.py --project "mi-api" --title "Shard user table by region" --decision_type data-model --description "User table partitioned by geographic region" --rationale "GDPR data residency requirements" --impact_level high --human_approved

"""

import argparse

import json

import re

import sys

from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_lib import slugify_strict, utcnow
from vault_io import (
    write_report,
    atomic_write_text,
    atomic_write_json,
    indice_compartido,
    assert_within_vault,
)
from vault_registry import section_default_type
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional


DECISION_TYPES = [
    "architectural",
    "security",
    "data-model",
    "algorithm",
    "configuration",
    "process",
]

# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones

#: El registro declara la severidad de mayor a menor; aquí se lee al revés
#: porque el índice en esta lista **es** el nivel de impacto.
IMPACT_LEVELS = list(reversed(_opciones("severidad")))

# ISO/IEC 42005: the likelihood and the severity of each affected party are
# read on the scales of the risk owner (1-5 with its labels), not on a copy.
from vault_risk_save import IMPACT_LABELS, LIKELIHOOD_LABELS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.contenido import (  # noqa: E402
    estado_de_evaluacion as _estado_de_evaluacion,
    niveles_de_impacto_exigidos,
    nota_escalonada,
)
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
from vault.autoria.frontmatter import firmante as _agente  # noqa: E402

#: ISO/IEC 42005:2025 — evaluación de impacto de un sistema de IA: a quién
#: afecta la decisión, además de qué decide. Los niveles que la exigen los
#: decide el kernel sobre la escala del registro, igual que al auditar AP-65.
EVALUACION_EXIGIDA = niveles_de_impacto_exigidos(_opciones("severidad"))



from vault.kernel.frontmatter_escritura import conservar_nota_generada  # noqa: E402

from vault_encoding import sanitize_content  # noqa: E402

def estado_de_evaluacion(impact_level: str, affected: Optional[List[str]]) -> str:
    """El estado de `impact_assessment` con la escala de este módulo (AP-65)."""
    return _estado_de_evaluacion(impact_level, affected, EVALUACION_EXIGIDA)


def _en_escala(valor: Any, escala: Dict[int, str]) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor in escala


def evaluacion_por_afectado(assessment: Any) -> Dict[str, Any]:
    """Validate `--assessment` (ISO/IEC 42005, AP-78): one entry per affected party.

    Each entry is an object with `affected` (who), `likelihood` and `impact`
    (integers on the 1-5 scales of `vault_risk_save`) and `mitigation` (how
    the harm is reduced). Returns `{"entradas": [...]}` with the normalized
    entries, or `{"error": envelope}` with the first entry that is not valid.
    Nothing is written before this passes.
    """
    def _falla(codigo: str, mensaje: str) -> Dict[str, Any]:
        return {"error": emit_error("vault_ai_decision", codigo, mensaje)}

    forma = ('--assessment must be a JSON array of objects: [{"affected": "end users", '
             '"likelihood": 3, "impact": 4, "mitigation": "..."}]')
    if not isinstance(assessment, list):
        return _falla("INVALID_VALUE", forma)
    entradas: List[Dict[str, Any]] = []
    vistos = set()
    for i, item in enumerate(assessment, 1):
        if not isinstance(item, dict):
            return _falla("INVALID_VALUE", f"assessment[{i}] is not an object. {forma}")
        afectado = item.get("affected")
        afectado = afectado.strip() if isinstance(afectado, str) else ""
        if not afectado:
            return _falla("INVALID_VALUE", f"assessment[{i}].affected must name who is affected")
        if afectado in vistos:
            return _falla("INVALID_VALUE", f"assessment[{i}]: '{afectado}' is assessed twice")
        if not _en_escala(item.get("likelihood"), LIKELIHOOD_LABELS):
            return _falla("INVALID_LIKELIHOOD", (
                f"assessment[{i}].likelihood must be an integer 1-5 "
                f"({LIKELIHOOD_LABELS}), not {item.get('likelihood')!r}"))
        if not _en_escala(item.get("impact"), IMPACT_LABELS):
            return _falla("INVALID_IMPACT", (
                f"assessment[{i}].impact must be an integer 1-5 "
                f"({IMPACT_LABELS}), not {item.get('impact')!r}"))
        mitigacion = item.get("mitigation")
        mitigacion = mitigacion.strip() if isinstance(mitigacion, str) else ""
        if not mitigacion:
            return _falla("INVALID_VALUE", f"assessment[{i}].mitigation must say how the harm is reduced")
        vistos.add(afectado)
        entradas.append({"affected": afectado, "likelihood": item["likelihood"],
                         "impact": item["impact"], "mitigation": mitigacion})
    return {"entradas": entradas}


def _celda(texto: str) -> str:
    """A table cell that a pipe or a line break cannot split."""
    return " ".join(str(texto).split()).replace("|", "\\|")


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _governance_dir() -> Path:
    return _repo().seccion("16_AI_Governance")


def _decisions_dir() -> Path:
    return _repo().seccion("16_AI_Governance") / "decisions"


def _index_file() -> Path:
    return _repo().seccion("16_AI_Governance") / ".decisions-log.json"


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def load_index() -> Dict[str, Any]:
    try:
        with open(_index_file(), "r", encoding="utf-8") as f:
            return json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        return {"decisions": []}


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def save_index(data: Dict[str, Any]) -> None:
    _governance_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_ai_decision(
    project: str,
    title: str,
    decision_type: str,
    description: str,
    rationale: str,
    alternatives: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    impact_level: str = "medium",
    reversible: bool = True,
    human_approved: bool = False,
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    affected: Optional[List[str]] = None,
    assessment: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    if decision_type not in DECISION_TYPES:
        return emit_error("vault_ai_decision", "INVALID_VALUE", f"decision_type '{decision_type}' not valid. Use: {DECISION_TYPES}")

    if impact_level not in IMPACT_LEVELS:
        return emit_error("vault_ai_decision", "INVALID_VALUE", f"impact_level '{impact_level}' not valid. Use: {IMPACT_LEVELS}")

    # ISO/IEC 42005 (AP-78): the per-party assessment is optional. Absent or
    # empty, the decision is written exactly as before this option existed.
    evaluados: List[Dict[str, Any]] = []
    if assessment not in (None, []):
        validada = evaluacion_por_afectado(assessment)
        if "error" in validada:
            return validada["error"]
        evaluados = validada["entradas"]

    safe_project = slugify_strict(project)

    affected = [str(a).strip() for a in (affected or []) if str(a).strip()]
    # A party assessed is a party affected: named once, in the order given.
    affected = list(dict.fromkeys(affected + [e["affected"] for e in evaluados]))
    nombres_evaluados = {e["affected"] for e in evaluados}
    sin_evaluar = [a for a in affected if a not in nombres_evaluados]
    por_afectado = (("parcial" if sin_evaluar else "completa") if evaluados else None)
    evaluacion = estado_de_evaluacion(impact_level, affected)

    title_slug = slugify_strict(title)

    now = utcnow()

    # El tramo exclusivo abarca desde la lectura hasta la escritura: sin el,
    # dos ejecuciones concurrentes leen el mismo indice, cada una anade su
    # entrada, gana la segunda y la primera desaparece con las dos tools
    # devolviendo `ok: true` (AP-37 por la puerta de atras).
    with indice_compartido(_index_file(), {"decisions": []}) as index:

        # Count existing decisions for this project to get sequential ID

        project_decisions = [d for d in index["decisions"] if es_del(d.get("project"))]

        # O4: identidad por ruta (proyecto+título). Antes cada llamada anexaba
        # una entrada y el correlativo se recalculaba desde la longitud del
        # registro: re-guardar la misma decisión dejaba AID-002 apuntando a la
        # nota de AID-001 (medido: .decisions-log.json 1 → 2).
        filename = f"{safe_project}-{title_slug}.md"

        note_path = _decisions_dir() / filename

        rel_previsto = str(note_path.relative_to(_raiz())).replace("\\", "/")

        existente = next((d for d in index["decisions"]
                          if d.get("relPath") == rel_previsto), None)

        if existente is not None:
            decision_id = str(existente.get("decision_id") or "")
            note_id = str(existente.get("docId") or "") or str(uuid.uuid4())
        else:
            decision_number = len(project_decisions) + 1

            decision_id = f"AID-{decision_number:03d}"

            note_id = str(uuid.uuid4())

        try:
            assert_within_vault(note_path, _raiz())

        except ValueError as exc:
            return {
                "ok": False,
                "error_code": "INVALID_PATH",
                "error": "INVALID_PATH",
                "message": str(exc),
            }

        tags_list = list(tags or [])

        tags_list.extend([safe_project, "ai-decision", decision_type, impact_level])

        cia_integrity = "high" if impact_level in ("high", "critical") else "medium"

        # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
        bloque = (
            Frontmatter()
            .set("id", note_id)
            .set("decision_id", decision_id)
            .set("title", title, texto=True)
            .set("project", project, texto=True)
            .set("type", section_default_type("16_AI_Governance"))
            .set("status", "approved" if human_approved else "draft")
            .set("decision_type", decision_type)
            .set("impact_level", impact_level)
            .set("human_approved", bool(human_approved))
            .set("reversible", bool(reversible))
            .set("impact_assessment", evaluacion)
        )
        if por_afectado:
            # AP-78: only a decision that uses `--assessment` declares it.
            bloque.set("evaluacion_por_afectado", por_afectado)
        frontmatter = [
            bloque
            .set("createdAt", now)
            .set("updatedAt", now)
            .set("tags", list(dict.fromkeys(tags_list)), omitir_vacio=True)
            .set("cia_integrity", cia_integrity)
            .set("cia_availability", "medium")
            .set("cia_sensitivity", "internal")
            .set("agent", _agente())
            .render()
        ]

        body_sections = []

        # Informative header

        approved_str = "Si" if human_approved else "No"

        reversible_str = "Si" if reversible else "No"

        header_info = (
            f"**Proyecto:** {project}  |  **Tipo:** {decision_type}  |  "
            f"**Impacto:** {impact_level}  |  **Reversible:** {reversible_str}  |  "
            f"**Aprobado por humano:** {approved_str}"
        )

        body_sections.append(header_info + "\n")

        body_sections.append(f"## Descripcion\n\n{description}")

        body_sections.append(f"## Justificacion\n\n{rationale}")

        if alternatives:
            lines = ["## Alternativas Consideradas\n"]

            for alt in alternatives:
                lines.append(f"- {alt}")

            body_sections.append("\n".join(lines))

        if risks:
            lines = ["## Riesgos Identificados\n"]

            for risk in risks:
                lines.append(f"- {risk}")

            body_sections.append("\n".join(lines))

        if evaluados:
            lines = ["## Evaluacion de Impacto\n"]
            if sin_evaluar:
                lines.append("A quién afecta, sin evaluar todavía (ISO/IEC 42005, AP-78):\n")
                lines.extend(f"- {a}" for a in sin_evaluar)
                lines.append("")
            lines.append("Evaluación por afectado (ISO/IEC 42005), en las escalas de "
                         "`vault_risk_save`:\n")
            lines.append("| Afectado | Probabilidad | Severidad | Mitigación |")
            lines.append("|---|---|---|---|")
            for e in evaluados:
                lines.append(
                    f"| {_celda(e['affected'])} "
                    f"| {e['likelihood']}/5 {LIKELIHOOD_LABELS[e['likelihood']]} "
                    f"| {e['impact']}/5 {IMPACT_LABELS[e['impact']]} "
                    f"| {_celda(e['mitigation'])} |")
            body_sections.append("\n".join(lines))
        elif evaluacion != "no_exigida":
            lines = ["## Evaluacion de Impacto\n"]
            if affected:
                lines.append("A quién afecta:\n")
                lines.extend(f"- {a}" for a in affected)
            else:
                lines.append(
                    f"Impacto `{impact_level}` sin afectados declarados: la decisión "
                    "dice qué y por qué, no a quién le cuesta (ISO/IEC 42005, AP-65)."
                )
            body_sections.append("\n".join(lines))

        if related_code:
            lines = ["## Codigo Relacionado\n"]

            for code_file in related_code:
                lines.append(f"- `{code_file}`")

            body_sections.append("\n".join(lines))

        body_sections.append(
            "> *Registrado bajo ISO/IEC 42001:2023 — AI Management System*"
        )

        # CN-04: la decisión abre con su título, antes de la línea de metadatos.
        # nota-escalonada S4: an AI decision is an event record; it names its
        # parent, the project card, before its metadata line.
        lead = (f"Decisión de IA de tipo {decision_type} e impacto {impact_level} "
                f"del proyecto {_proyectos.enlace_a_ficha(project)}.")
        final_content = ("\n".join(frontmatter) + "\n\n" + nota_escalonada(title, lead)
                         + "\n" + "\n\n".join(body_sections))

        note_path.parent.mkdir(parents=True, exist_ok=True)

        contenido = conservar_nota_generada(
            note_path,
            sanitize_content(final_content, dry_run=False)[0],
            campos=("decision_id",),
        )
        previo = ""
        if note_path.exists():
            try:
                previo = note_path.read_text(encoding="utf-8")
            except OSError:
                previo = ""
        sin_cambio = bool(previo) and contenido == previo
        atomic_write_text(note_path, contenido)

        entry = {
            "docId": note_id,
            "decision_id": decision_id,
            "project": project,
            "title": title,
            "decision_type": decision_type,
            "impact_level": impact_level,
            "human_approved": human_approved,
            "reversible": reversible,
            "impact_assessment": evaluacion,
            "relPath": str(note_path.relative_to(_raiz())).replace("\\", "/"),
            "updatedAt": now,
        }
        if por_afectado:
            entry["evaluacion_por_afectado"] = por_afectado

        if existente is not None:
            if not sin_cambio:
                index["decisions"][index["decisions"].index(existente)] = entry
        else:
            index["decisions"].append(entry)


    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "decision_id": decision_id,
        "impact_level": impact_level,
        "impact_assessment": evaluacion,
        **({"hint": (
            f"Impacto {impact_level} sin --affected: la evaluación de impacto "
            "queda pendiente (ISO/IEC 42005, AP-65). Añade a quién afecta."
        )} if evaluacion == "pendiente" else {}),
        **({"evaluacion_por_afectado": por_afectado} if por_afectado else {}),
        **({"hint": (
            f"Sin probabilidad, severidad ni mitigación para: {', '.join(sin_evaluar)}. "
            "Añádelos a --assessment para completar la evaluación (ISO/IEC 42005, AP-78)."
        )} if por_afectado == "parcial" else {}),
        "action": ("unchanged" if existente is not None and sin_cambio else
                   ("updated" if existente is not None else "created")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault AI Decision Tool -- ISO/IEC 42001:2023 AI decision logging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_ai_decision.py --project "mi-api" --title "Use JWT over sessions" --decision_type architectural --description "Decided to use stateless JWT tokens instead of server-side sessions" --rationale "Horizontal scaling requires stateless auth" --impact_level medium



  python vault_ai_decision.py --project "mi-api" --title "Hash algorithm: bcrypt" --decision_type security --description "Using bcrypt with cost factor 12 for password hashing" --rationale "bcrypt is resistant to GPU attacks; cost 12 balances security/performance" --alternatives '["argon2id - more secure but higher memory","sha256 - rejected: no salt by default"]' --risks '["Cost factor may need tuning under high load"]'



  python vault_ai_decision.py --project "mi-api" --title "Shard user table by region" --decision_type data-model --description "User table partitioned by geographic region" --rationale "GDPR data residency requirements" --impact_level high --human_approved



  python vault_ai_decision.py --project "mi-api" --title "Rotate tokens hourly" --decision_type security --description "Access tokens expire after one hour" --rationale "Limits the window of a leaked token" --impact_level high --affected '["end users - re-authenticate every hour"]'



Notes:

  - decision_type: architectural | security | data-model | algorithm | configuration | process

  - impact_level: low | medium | high | critical

  - --human_approved is a flag (no value needed), default is false

  - --reversible defaults to true; use --no-reversible to mark as irreversible

  - decision_id is auto-generated as AID-001, AID-002, etc. per project

  - --related_code accepts comma-separated file paths

  - --affected (ISO/IEC 42005): impact high/critical without it writes impact_assessment: pendiente (AP-65)

  - --assessment (ISO/IEC 42005): per affected party, likelihood and impact 1-5 (the scales of

    vault_risk_save) and a mitigation; writes evaluacion_por_afectado: completa | parcial (AP-78)



  python vault_ai_decision.py --project "mi-api" --title "Rotate tokens hourly" --decision_type security --description "Access tokens expire after one hour" --rationale "Limits the window of a leaked token" --impact_level high --assessment '[{"affected": "end users", "likelihood": 4, "impact": 2, "mitigation": "Silent refresh before expiry"}]'

""",
        allow_abbrev=False,
    )

    parser.add_argument("--project", type=proyecto_registrado("vault_ai_decision"), required=True, help="Project slug")

    parser.add_argument("--title", required=True, help="Short decision title")

    parser.add_argument(
        "--decision_type", choices=DECISION_TYPES, required=True, help=f"Decision type: {DECISION_TYPES}"
    )

    parser.add_argument("--description", required=True, help="What decision was made")

    parser.add_argument("--rationale", required=True, help="Why this decision was made")

    parser.add_argument(
        "--alternatives",
        help='JSON array of alternatives considered: ["option A - reason","option B - reason"]',
    )

    parser.add_argument(
        "--risks", help='JSON array of identified risks: ["risk description"]'
    )

    parser.add_argument(
        "--impact_level", choices=IMPACT_LEVELS,
        default="medium",
        help=f"Impact level (default: medium): {IMPACT_LEVELS}",
    )

    parser.add_argument(
        "--reversible",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Whether the decision can be reversed (default: true)",
    )

    parser.add_argument(
        "--human_approved",
        action="store_true",
        help="Flag: decision was reviewed and approved by a human",
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    parser.add_argument(
        "--affected",
        # Literal y no f-string: `vault_mcp_catalog` lee el help sin ejecutar
        # el módulo, y uno calculado llegaba al schema MCP como "".
        help=(
            'JSON array of who the decision affects (ISO/IEC 42005): '
            '["end users - lose session on deploy"]. Without it, a decision '
            "of the two highest impact levels is written with "
            "impact_assessment: pendiente (AP-65)"
        ),
    )

    parser.add_argument(
        "--assessment",
        # Literal, like --affected: the MCP catalog reads it without running.
        help=(
            'JSON array, one object per affected party (ISO/IEC 42005): '
            '[{"affected": "end users", "likelihood": 3, "impact": 4, '
            '"mitigation": "silent token refresh"}]. likelihood and impact '
            "are integers 1-5 on the scales of vault_risk_save. Writes "
            "evaluacion_por_afectado: completa, or parcial when an affected "
            "party has no entry (AP-78)"
        ),
    )

    args = parser.parse_args()

    def parse_json_arg(val: Optional[str], name: str) -> Optional[Any]:
        if not val:
            return None

        try:
            return json.loads(val)

        except json.JSONDecodeError as e:
            print(json.dumps(emit_error("vault_ai_decision", "ARG_JSON_INVALID", f"Invalid JSON in --{name}: {e}"), ensure_ascii=False))

            sys.exit(1)

    related_code_list: Optional[List[str]] = None

    if args.related_code:
        related_code_list = [
            f.strip() for f in args.related_code.split(",") if f.strip()
        ]

    alternatives = parse_json_arg(args.alternatives, "alternatives")

    risks = parse_json_arg(args.risks, "risks")

    affected = parse_json_arg(args.affected, "affected")

    assessment = parse_json_arg(args.assessment, "assessment")

    result = vault_ai_decision(
        project=args.project,
        title=args.title,
        decision_type=args.decision_type,
        description=args.description,
        rationale=args.rationale,
        alternatives=alternatives,
        risks=risks,
        impact_level=args.impact_level,
        reversible=args.reversible,
        human_approved=args.human_approved,
        related_code=related_code_list,
        tags=args.tags,
        affected=affected,
        assessment=assessment,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_ai_decision"))
