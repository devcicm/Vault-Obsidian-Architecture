#!/usr/bin/env python3

"""

Vault Requirement Save Tool -- Save software requirements (ISO/IEC/IEEE 29148)



Saves requirements to 14_Requirements/{project}/ with traceability to code.

Types: functional, non-functional, constraint, assumption

Priority: must-have, should-have, nice-to-have (MoSCoW)

Status: draft -> reviewed -> approved -> implemented -> verified -> obsolete
(validated against STATUS_TRANSITIONS, AP-41; a new requirement starts as draft or reviewed)



Usage:

    python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have

    python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'

    python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"

"""

import argparse

import json

import re

import sys

from vault_change_log import vault_change_log_add, leer_historial_completo
from vault_errors import emit_error, wrap_main, proyecto_registrado
from vault_norms_catalog import STATUS_TRANSITIONS, status_frontmatter_lines
from vault_registry import regimen_de_estado
from vault_lib import yaml_scalar, slugify_strict, utcnow
from datetime import datetime, timezone
from vault_io import (
    indice_compartido,
    write_report,
    atomic_write_text,
    atomic_write_json,
    assert_within_vault,
    identidad_requisito,
    leer_requisitos_de_dominio,
    IndiceIlegible,
)
import uuid

from pathlib import Path


from typing import Any, Dict, List, Optional


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402
from vault.kernel.contenido import nota_escalonada  # noqa: E402
from vault.kernel.frontmatter_escritura import conservar_nota_generada  # noqa: E402
from vault.autoria.frontmatter import Frontmatter, firmante  # noqa: E402


from vault_encoding import sanitize_content  # noqa: E402
from vault.kernel.normativa import calidad_iso  # noqa: E402

def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _req_dir() -> Path:
    return _repo().seccion("14_Requirements")


def _index_file() -> Path:
    return _repo().seccion("14_Requirements") / ".requirements-index.json"


REQ_TYPES = ["functional", "non-functional", "constraint", "assumption"]

PRIORITIES = ["must-have", "should-have", "nice-to-have", "wont-have"]

STATUSES = ["draft", "reviewed", "approved", "implemented", "verified", "obsolete"]

#: The states a requirement may be created in (AP-41). Not a second table: a
#: requirement enters the lifecycle in an *open* state of
#: `STATUS_TRANSITIONS` (one that can still go back to `draft`, per
#: `regimen_de_estado`). A closed state is only reachable through recorded
#: transitions; being born `verified` would skip the machine the ledger
#: replays.
ESTADOS_DE_ALTA = tuple(s for s in STATUSES
                        if regimen_de_estado(s, STATUS_TRANSITIONS) == "abierto")


def _transicion_ilegal(previo: Optional[str], destino: str) -> Optional[Dict[str, Any]]:
    """The AP-41 rejection for `previo -> destino`, or None when it is allowed.

    Same verdict and envelope shape as `vault_write`'s AP-41 guard: the table
    is `vault_norms_catalog.STATUS_TRANSITIONS`, never a copy. `previo` None is
    a new requirement, checked against `ESTADOS_DE_ALTA`. A previous state the
    machine does not know (debt older than AP-38) is let through, as
    `vault_write` does, and the audit reports it.
    """
    if previo == destino:
        return None
    if previo is None:
        permitidos = set(ESTADOS_DE_ALTA)
        origen = "(nuevo)"
    elif previo in STATUS_TRANSITIONS:
        permitidos = set(STATUS_TRANSITIONS[previo])
        origen = repr(previo)
    else:
        return None
    if destino in permitidos:
        return None
    return {
        **emit_error(
            "vault_requirement_save", "illegal_status_transition",
            f"AP-41: transición {origen} -> {destino!r} no está en "
            f"STATUS_TRANSITIONS. Desde {origen} solo se puede pasar a "
            f"{sorted(permitidos) or ['(ninguno: estado terminal)']}. "
            f"Recorre los estados intermedios con --req-id; nada se escribió."),
        "error": "illegal_status_transition",
        "norm_code": "AP-41",
        "norm_name": "Máquina de estados declarada sin verificar",
        "from_status": previo,
        "to_status": destino,
        "allowed": sorted(permitidos),
    }


def _hay_historial_de_requisitos() -> bool:
    """True when the durable change log holds structured requirement events."""
    try:
        return any(isinstance(row.get("requirement"), dict) for row in leer_historial_completo())
    except (IndiceIlegible, OSError, ValueError):
        return True  # Unverifiable history: let the replay report it, never guess.


def reconstruir_indice_requisitos(adoptar_legado: bool = False) -> Dict[str, Any]:
    """Explicit mutation API; incomplete evidence never becomes a guessed history."""
    try:
        return _reconstruir_indice_requisitos(adoptar_legado=adoptar_legado)
    except (IndiceIlegible, OSError, ValueError, TypeError):
        return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                "message": "Requirement projection or durable history could not be verified"}


def _reconstruir_indice_requisitos(adoptar_legado: bool = False) -> Dict[str, Any]:
    """Replay the complete durable history into the existing derived index.

    Lock order is always projection then history; readers never hold a history
    lock while waiting for this projection. Legacy prose is not parsed as fact.
    When `adoptar_legado=True`, unmatched on-disk requirement states receive an
    explicit, auditable baseline adoption event without inventing past moves.
    """
    with indice_compartido(_index_file(), {"requirements": []}) as index:
        if (not isinstance(index, dict) or not isinstance(index.get("requirements"), list) or
                not isinstance(index.get("counters", {}), dict) or
                any(type(value) is not int or value < 0 for value in index.get("counters", {}).values())):
            return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                    "message": "Invalid requirement projection shape; restore verified data"}
        census = leer_requisitos_de_dominio(_raiz())
        if census["invalidas"] or census["ilegibles"]:
            return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                    "message": "Requirement notes could not be verified completely"}
        rows = leer_historial_completo()
        legacy = [row for row in rows if row.get("action") == "transition" and
                  str(row.get("path", "")).startswith("14_Requirements/") and
                  not isinstance(row.get("requirement"), dict)]
        if legacy and not adoptar_legado:
            return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                    "legacy_events": len(legacy),
                    "legacy_paths": sorted({str(row.get("path")) for row in legacy})[:20],
                    "message": "Legacy requirement history lacks qualified identity; restore verified history",
                    "recovery": {"action": "manual",
                                 "hint": "Review the listed change-log rows with their owner: either record "
                                         "the qualified transition (project/REQ id) through vault_requirement_save, "
                                         "run with --adopt-legacy to record an explicit baseline for disk state, "
                                         "or keep the projection and leave the rows as historical prose. "
                                         "Nothing is inferred from unqualified rows."}}
        events: Dict[str, List[Dict[str, Any]]] = {}
        seen: Dict[str, Dict[str, Any]] = {}
        counters = dict(index.get("counters") or {})
        for row in rows:
            detail = row.get("requirement")
            if not isinstance(detail, dict):
                continue
            identity = identidad_requisito(detail)
            identifier = row.get("id")
            if (identity is None or detail.get("identity") != identity or not isinstance(identifier, str) or not identifier or
                    detail.get("to") not in STATUSES or detail.get("from") not in [None, *STATUSES] or
                    not row.get("timestamp") or not row.get("agent") or not row.get("reason")):
                return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                        "message": "Invalid structured requirement history"}
            if identifier in seen:
                if seen[identifier] != row:
                    return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                            "message": "Conflicting requirement event identity"}
                continue
            seen[identifier] = row
            history = events.setdefault(identity, [])
            if detail["from"] != (history[-1]["to"] if history else None):
                return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                        "message": "Requirement event sequence is incomplete"}
            history.append({"id": identifier, "at": row["timestamp"],
                            "from": detail["from"], "to": detail["to"],
                            "agent": row["agent"], "reason": row["reason"]})
            project, req_id = identity.rsplit("/", 1)
            counters[project] = max(int(counters.get(project, 0)), int(req_id[4:]))
        previous_entries = {identidad_requisito(row): row for row in index.get("requirements", [])
                            if isinstance(row, dict) and identidad_requisito(row)}
        unmatched = [
            identity for identity, note in sorted(census["requirements"].items())
            if not events.get(identity) or
            events[identity][-1]["to"] != note.get("requirement_state", note.get("status"))
        ]
        if unmatched and not adoptar_legado:
            return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                    "unmatched_identities": unmatched,
                    "message": "Requirement note state lacks matching durable history",
                    "recovery": {"action": "manual",
                                 "hint": "Revisa las identidades en `unmatched_identities`; si su estado en "
                                         "disco es el vigente, ejecuta `vault_requirement_save --adopt-legacy` "
                                         "para registrar una linea base explicita en el change-log sin inventar "
                                         "transiciones anteriores."}}
        adopted: List[str] = []
        agente = firmante() if (adoptar_legado and unmatched) else ""
        rebuilt = []
        for identity, note in sorted(census["requirements"].items()):
            history = list(events.get(identity, []))
            estado_disco = str(note.get("requirement_state", note.get("status")) or "")
            if not history or history[-1]["to"] != estado_disco:
                if estado_disco not in STATUSES:
                    return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                            "unmatched_identities": [identity],
                            "message": f"Requirement note '{identity}' has invalid status '{estado_disco}'"}
                project, req_id = identity.rsplit("/", 1)
                previo = history[-1]["to"] if history else None
                ev_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"vault-requirement-adopt:{identity}#{len(history)}:{previo or ''}->{estado_disco}",
                ))
                reg = vault_change_log_add(
                    action="transition",
                    path=str(note.get("relPath") or ""),
                    reason=f"{req_id}: adopcion explicita de estado en disco -> {estado_disco}",
                    agent=agente,
                    event_id=ev_id,
                    requirement={"project": project, "req_id": req_id,
                                 "from": previo, "to": estado_disco},
                )
                if not reg.get("ok"):
                    return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                            "message": f"Could not record explicit adoption for '{identity}'"}
                ev = reg["entry"]
                history.append({"id": ev["id"], "at": ev["timestamp"],
                                "from": previo, "to": estado_disco,
                                "agent": ev["agent"], "reason": ev["reason"],
                                "adopted": True})
                counters[project] = max(int(counters.get(project, 0)), int(req_id[4:]))
                adopted.append(identity)
            entry = {**previous_entries.get(identity, {}), **{key: note.get(key) for key in
                     ("docId", "req_id", "project", "title", "req_type", "priority", "status", "relPath")}}
            entry.pop("pending_transition", None)
            if note.get("updatedAt") is not None:
                entry["updatedAt"] = str(note["updatedAt"])
            entry["events"] = history
            rebuilt.append(entry)
        index.update(requirements=rebuilt, counters=counters)
    salida: Dict[str, Any] = {"ok": True, "requirements": len(rebuilt), "history_incomplete": False}
    if adoptar_legado:
        salida["adopted"] = adopted
    return salida


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
        return {"requirements": []}


# superseded_by: vault_io.indice_compartido
#
# Leia/escribia el indice fuera de todo tramo exclusivo, que es justo el
# lost update que `indice_compartido` cierra. Se conserva con su contrato
# intacto por la politica de no-derogacion: ya no lo llama el camino de
# guardado, y no debe volver a llamarlo. Si necesitas el indice, entra por
# `indice_compartido`, que cubre desde la lectura hasta la escritura.
def save_index(data: Dict[str, Any]) -> None:
    _req_dir().mkdir(parents=True, exist_ok=True)

    atomic_write_json(_index_file(), data)


def vault_requirement_save(
    project: str,
    title: str,
    description: str,
    req_type: str,
    priority: str,
    acceptance_criteria: Optional[List[str]] = None,
    source: Optional[str] = None,
    status: str = "draft",
    related_code: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    req_id: Optional[str] = None,
    quality_characteristics: Optional[List[str]] = None,
    quality_in_use: Optional[List[str]] = None,
) -> Dict[str, Any]:
    es_del = _proyectos.pertenencia_en(_raiz(), project)
    if req_type not in REQ_TYPES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"req_type '{req_type}' not valid. Use: {REQ_TYPES}")

    if priority not in PRIORITIES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"priority '{priority}' not valid. Use: {PRIORITIES}")

    if status not in STATUSES:
        return emit_error("vault_requirement_save", "INVALID_VALUE", f"status '{status}' not valid. Use: {STATUSES}")

    # ISO/IEC 25010:2023 / 25019:2023 (optional): validated before anything
    # is reserved or written; written only when given.
    calidad: Dict[str, List[str]] = {}
    for campo, modelo, valores in (("quality_characteristics", "product", quality_characteristics),
                                   ("quality_in_use", "in_use", quality_in_use)):
        terminos = calidad_iso.split_terms(valores)
        if not terminos:
            continue
        canonicos, desconocidos = calidad_iso.resolve_quality(modelo, terminos)
        if desconocidos:
            return emit_error("vault_requirement_save", "INVALID_VALUE",
                              f"{campo} {desconocidos} not valid. Use: "
                              f"{calidad_iso.characteristic_ids(modelo)}")
        calidad[campo] = canonicos

    safe_project = slugify_strict(project)

    if not _index_file().exists():
        census = leer_requisitos_de_dominio(_raiz())
        # Counters also live in the durable history: with every note deleted,
        # skipping the replay reset them and reused an identifier (REQ-001).
        if (census["requirements"] or census["invalidas"] or census["ilegibles"]
                or _hay_historial_de_requisitos()):
            recovery = reconstruir_indice_requisitos()
            if not recovery["ok"]:
                return recovery

    title_slug = slugify_strict(title)

    now = utcnow()

    # AP-16: the note and its change-log row are signed by whoever writes,
    # resolved by the owner every typed save tool uses (`firmante`).
    agente = firmante()

    # El lock abarca desde la lectura hasta la escritura, no solo la
    # escritura: este indice es tambien el contador del correlativo, y
    # reservar el numero fuera del tramo exclusivo hace que dos guardados
    # concurrentes obtengan el mismo id y el mismo nombre de fichero.
    transicion_registrada = False
    pending_transition = None

    with indice_compartido(_index_file(), {"requirements": []}) as index:

        # Count existing requirements for this project to get sequential ID

        project_reqs = [r for r in index["requirements"] if es_del(r.get("project"))]

        # Identidad del requerimiento (O4): proyecto + slug del título. Antes
        # CADA llamada reservaba el correlativo siguiente, así que re-guardar
        # el mismo requerimiento abría req-002 con el mismo título y el
        # contrato declaraba `unchanged`: el C3 lo midió al ejecutarse por fin
        # el ejemplo (el barrido anterior simulaba su rechazo). Es la misma
        # identidad que `vault_knowledge_save` ya aplica.
        # D-06: con `req_id` la identidad es el id, no el titulo. Renombrar
        # un requerimiento ya no abre otro, y un id que no existe no se crea
        # por la puerta de atras.
        if req_id:
            existente = next(
                (r for r in project_reqs if str(r.get("req_id")) == req_id), None)
            if existente is None:
                return emit_error("vault_requirement_save", "INVALID_VALUE",
                                  f"req_id '{req_id}' no existe en el proyecto '{project}'")
        else:
            existente = next(
                (r for r in project_reqs
                 if slugify_strict(str(r.get("title") or "")) == title_slug),
                None,
            )

        # AP-41 before anything is reserved or written: a rejected move leaves
        # the counter, the note, the ledger and this projection untouched
        # (`indice_compartido` only writes when the data changed). A pending
        # retry was checked when first requested and is replayed below; an
        # entry without a recorded state has no machine to walk.
        if existente is None:
            rechazo = _transicion_ilegal(None, status)
        elif existente.get("pending_transition") or not existente.get("status"):
            rechazo = None
        else:
            rechazo = _transicion_ilegal(str(existente["status"]), status)
        if rechazo is not None:
            return rechazo

        if existente is not None:
            req_id = str(existente.get("req_id") or "")
            note_id = str(existente.get("docId") or "") or str(uuid.uuid4())
            rel_previo = str(existente.get("relPath") or "")
            note_path = _raiz() / rel_previo if rel_previo else (
                _req_dir() / safe_project / f"req-{req_id[-3:]}-{title_slug}.md")
            filename = note_path.name
        else:
            # D-06: contador monotono. `len(...) + 1` reusaba el id de una
            # entrada podada; el mayor entre el contador guardado y el
            # mayor numero vivo nunca retrocede.
            contadores = index.setdefault("counters", {})
            vivos = [int(str(r.get("req_id", ""))[4:]) for r in project_reqs
                     if str(r.get("req_id", ""))[4:].isdigit()]
            req_number = max(int(contadores.get(safe_project, 0)), *vivos, 0) + 1
            contadores[safe_project] = req_number

            req_id = f"REQ-{req_number:03d}"

            note_id = str(uuid.uuid4())

            filename = f"req-{req_number:03d}-{title_slug}.md"

            note_path = _req_dir() / safe_project / filename

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

        tags_list.extend([safe_project, "requirement", req_type, priority])

        cia_integrity = "high" if priority == "must-have" else "medium"

        frontmatter = Frontmatter()

        frontmatter.set("id", note_id)

        frontmatter.set("req_id", req_id)

        frontmatter.set("title", title, texto=True)

        frontmatter.set("project", project, texto=True)

        frontmatter.set("req_type", req_type)

        frontmatter.set("priority", priority)

        frontmatter.lineas(status_frontmatter_lines("vault_requirement_save", status))

        for campo, valor in calidad.items():
            frontmatter.set(campo, valor)

        frontmatter.set("createdAt", now)

        frontmatter.set("updatedAt", now)

        if tags_list:
            frontmatter.set("tags", list(dict.fromkeys(tags_list)))

        frontmatter.set("cia_integrity", cia_integrity)

        frontmatter.set("cia_availability", "medium")

        frontmatter.set("cia_sensitivity", "internal")

        frontmatter.set("agent", agente, texto=True)


        body_sections = []

        body_sections.append(f"## Descripcion\n\n{description}")

        if acceptance_criteria:
            lines = ["## Criterios de Aceptacion\n"]

            for i, criterion in enumerate(acceptance_criteria, 1):
                lines.append(f"{i}. {criterion}")

            body_sections.append("\n".join(lines))

        if related_code:
            rows = ["## Trazabilidad\n", "| Archivo | Rol |", "|---|---|"]

            for code_file in related_code:
                rows.append(f"| `{code_file}` | implementacion |")

            body_sections.append("\n".join(rows))

        if source:
            body_sections.append(f"## Fuente\n\n{source}")

        # Status badge

        status_line = " | ".join(f"**{s}**" if s == status else s for s in STATUSES)

        body_sections.append(f"## Estado\n\n**Estado:** {status_line}")

        # nota-escalonada S4: the lead says what the requirement is from its arguments.
        lead = (f"{title} es un requisito de tipo {req_type} y prioridad {priority} "
                f"del proyecto {project}, en estado {status}.")
        if acceptance_criteria:
            lead += f" Tiene {len(acceptance_criteria)} criterios de aceptación."
        lead += (" Esta nota se generó con `vault_requirement_save` y vive en la "
                 "sección de requisitos del vault.")
        falta = None if acceptance_criteria else (
            "faltan sus criterios de aceptación (`--acceptance_criteria`)")
        final_content = (frontmatter.render() + "\n\n" + nota_escalonada(title, lead, falta=falta)
                         + "\n" + "\n\n".join(body_sections))

        previo = ""
        if note_path.exists():
            try:
                previo = note_path.read_text(encoding="utf-8")
            except OSError:
                previo = ""

        # Mismo cuerpo ⇒ misma nota: id, `req_id` y sellos no son el
        # requerimiento. Re-guardar lo idéntico no toca la nota (ni dispara la
        # cascada de índices y grafo).
        final_content = conservar_nota_generada(
            note_path, sanitize_content(final_content, dry_run=False)[0])

        sin_cambio = bool(previo) and final_content == previo

        previous_pending = existente.get("pending_transition") if existente else None
        if previous_pending and previous_pending["to"] != status:
            return {"ok": False, "error_code": "INDEX_STALE", "history_incomplete": True,
                    "message": "Retry the pending requirement state before requesting another transition"}
        if not sin_cambio:
            note_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(note_path, final_content)

        previous_state = str(existente.get("status") or "") if existente else ""
        eventos = list(existente.get("events") or []) if existente else []
        state_changed = previous_state != status
        if previous_pending or state_changed:
            # The event identity is derived from the history position, not
            # drawn at random: when the ledger commit succeeded but the index
            # write did not, the retry reproduces the same id and the change
            # log deduplicates it instead of appending a second transition.
            sequence = f"{safe_project}/{req_id}#{len(eventos)}:{previous_state or ''}->{status}"
            pending_transition = previous_pending or {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "vault-requirement-event:" + sequence)),
                "from": previous_state or None, "to": status,
                "reason": f"{req_id}: {previous_state or '(nuevo)'} -> {status}",
            }
            rel_note = note_path.relative_to(_raiz()).as_posix()
            try:
                registro = vault_change_log_add(
                    action="transition", path=rel_note, reason=pending_transition["reason"],
                    agent=agente, event_id=pending_transition["id"],
                    requirement={"project": safe_project, "req_id": req_id,
                                 "from": pending_transition["from"], "to": status})
            except Exception:
                # The note may already be durable. Retain a retry identity and
                # report partial work, never claim a committed history event.
                registro = {"ok": False}
            transicion_registrada = bool(registro.get("ok"))
            if transicion_registrada:
                event = registro["entry"]
                if not any(item.get("id") == event["id"] for item in eventos):
                    eventos.append({"id": event["id"], "at": event["timestamp"],
                                    "from": event["requirement"]["from"], "to": status,
                                    "agent": event["agent"], "reason": event["reason"]})
                pending_transition = None
        # An unchanged note whose projected state differs is a retry after a
        # failed index write: the projection must be rewritten, not skipped.
        if not sin_cambio or previous_pending or state_changed:
            entry = {
                "docId": note_id, "req_id": req_id, "project": project, "title": title,
                "req_type": req_type, "priority": priority, "status": status,
                "relPath": note_path.relative_to(_raiz()).as_posix(),
                "related_code": related_code or [],
                "updatedAt": existente.get("updatedAt", now) if sin_cambio and existente else now,
                "events": eventos,
            }
            if pending_transition is not None:
                entry["pending_transition"] = pending_transition
            if existente is not None:
                index["requirements"][index["requirements"].index(existente)] = entry
            else:
                index["requirements"].append(entry)



    if sin_cambio:
        accion = "unchanged"
    elif existente is not None:
        accion = "updated"
    else:
        accion = "created"

    if pending_transition is not None:
        return {"ok": False, "error_code": "FILE_WRITE_ERROR", "partial": True,
                "message": "Requirement note saved, but transition history is pending; retry the same request",
                "transition_logged": False, "req_id": req_id,
                "path": str(note_path.relative_to(_raiz())).replace("\\", "/"), **write_report()}

    return {
        "ok": True,
        **write_report(),
        "path": str(note_path.relative_to(_raiz())).replace("\\", "/"),
        "req_id": req_id,
        "action": accion,
        "transition_logged": transicion_registrada,
    }


def listar_requisitos(project: Optional[str] = None) -> Dict[str, Any]:
    """D-05 -- los requisitos del indice, sin escribir nada.

    Lee el indice compartido en solo lectura; `project` filtra por slug.
    """
    try:
        datos = json.loads(_index_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        datos = {"requirements": []}
    es_del = _proyectos.pertenencia_en(_raiz(), project) if project is not None else None
    filas = [
        {k: r.get(k) for k in ("req_id", "project", "title", "req_type", "priority", "status", "relPath")}
        for r in datos.get("requirements", [])
        if es_del is None or es_del(r.get("project"))
    ]
    return {"ok": True, "tool": "vault_requirement_save", "count": len(filas), "requirements": filas}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Requirement Save Tool -- ISO/IEC/IEEE 29148 requirement documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:

  python vault_requirement_save.py --project "mi-api" --title "User Authentication" --description "The system must authenticate users via JWT" --type functional --priority must-have



  python vault_requirement_save.py --project "mi-api" --title "Response Time" --description "API must respond in < 200ms at p99" --type non-functional --priority must-have --acceptance_criteria '["p99 latency < 200ms in load tests","No degradation under 1000 concurrent users"]'



  python vault_requirement_save.py --project "mi-api" --title "GDPR Compliance" --description "User data must be deletable on request" --type constraint --priority must-have --related_code "src/user.py,src/gdpr.py"



Notes:

  - req_type: functional | non-functional | constraint | assumption  (ISO/IEC/IEEE 29148)

  - priority: must-have | should-have | nice-to-have | wont-have    (MoSCoW)

  - status: draft | reviewed | approved | implemented | verified | obsolete
    Changes follow STATUS_TRANSITIONS (AP-41): draft -> reviewed -> approved ->
    implemented -> verified -> obsolete, one step at a time with --req-id. A new
    requirement starts as draft or reviewed. An illegal move is rejected with
    illegal_status_transition and writes nothing.

  - --related_code accepts comma-separated file paths

  - req_id is auto-generated as REQ-001, REQ-002, etc. per project

  - --quality_characteristics (optional, comma-separated): ISO/IEC 25010:2023
    characteristics (functional_suitability, performance_efficiency,
    compatibility, interaction_capability, reliability, security,
    maintainability, flexibility, safety) or characteristic.subcharacteristic;
    the 2011 names (usability, portability) resolve to their 2023 successor

  - --quality_in_use (optional, comma-separated): ISO/IEC 25019:2023
    (effectiveness, efficiency, satisfaction, freedom_from_risk, context_coverage)

  - Coverage per characteristic: vault_quality_check --iso-quality

""",
        allow_abbrev=False,
    )

    parser.add_argument("--list", action="store_true", help="Lista los requisitos del indice (solo lectura); --project filtra")

    parser.add_argument("--project", type=proyecto_registrado("vault_requirement_save"), help="Project slug")

    parser.add_argument("--title", help="Short requirement title")

    parser.add_argument("--req-id", dest="req_id", help="REQ-NNN existente: actualiza ese requisito aunque cambie el titulo")

    parser.add_argument(
        "--description", help="Full requirement description"
    )

    parser.add_argument(
        "--type", choices=REQ_TYPES, dest="req_type", help=f"Requirement type: {REQ_TYPES}"
    )

    parser.add_argument(
        "--priority", choices=PRIORITIES, help=f"MoSCoW priority: {PRIORITIES}"
    )

    parser.add_argument(
        "--acceptance_criteria", help="JSON array of acceptance criteria strings"
    )

    parser.add_argument(
        "--source", help="Origin of the requirement (stakeholder, document, etc.)"
    )

    parser.add_argument(
        "--status", choices=STATUSES,
        default="draft",
        help=f"Requirement status (default: draft): {STATUSES}",
    )

    parser.add_argument(
        "--related_code", help="Comma-separated list of related source files"
    )

    parser.add_argument("--tags", nargs="*", help="Additional tags")

    parser.add_argument("--quality_characteristics", help="Comma-separated ISO/IEC 25010:2023 characteristics or characteristic.subcharacteristic")

    parser.add_argument("--quality_in_use", help="Comma-separated ISO/IEC 25019:2023 quality-in-use characteristics")

    parser.add_argument("--adopt-legacy", action="store_true", dest="adopt_legacy",
                        help="Reconstruye el indice registrando una adopcion explicita para notas legadas sin historia")

    args = parser.parse_args()

    if args.list:
        print(json.dumps(listar_requisitos(args.project), indent=2, ensure_ascii=False))
        return 0

    if args.adopt_legacy and not args.title:
        r = reconstruir_indice_requisitos(adoptar_legado=True)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0 if r.get("ok") else 1

    if not (args.project and args.title and args.description and args.req_type and args.priority):
        parser.error("--project, --title, --description, --type y --priority son obligatorios salvo con --list o --adopt-legacy")

    def parse_json_arg(val: Optional[str], name: str) -> Optional[Any]:
        if not val:
            return None

        try:
            return json.loads(val)

        except json.JSONDecodeError as e:
            print(json.dumps(emit_error("vault_requirement_save", "ARG_JSON_INVALID", f"Invalid JSON in --{name}: {e}"), ensure_ascii=False))

            sys.exit(1)

    related_code_list: Optional[List[str]] = None

    if args.related_code:
        related_code_list = [
            f.strip() for f in args.related_code.split(",") if f.strip()
        ]

    acceptance_criteria = parse_json_arg(
        args.acceptance_criteria, "acceptance_criteria"
    )

    result = vault_requirement_save(
        project=args.project,
        title=args.title,
        description=args.description,
        req_type=args.req_type,
        priority=args.priority,
        acceptance_criteria=acceptance_criteria,
        source=args.source,
        status=args.status,
        related_code=related_code_list,
        tags=args.tags,
        req_id=args.req_id,
        quality_characteristics=args.quality_characteristics,
        quality_in_use=args.quality_in_use,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_requirement_save"))
