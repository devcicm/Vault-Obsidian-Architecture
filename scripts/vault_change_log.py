#!/usr/bin/env python3

"""

Vault Change Log Tool -- Record note lifecycle events in the vault.



Tracks: created, updated, deleted, moved actions on vault notes.

Writes to two targets:

  - 00_System/change-log.md  (Markdown table, readable in Obsidian)

  - 00_System/.change-log.jsonl  (JSON Lines, append-only, queryable by agents)

  A vault from before the append-only log keeps its 00_System/.change-log.json
  (one JSON array): it is read, legacy first, and never written again.



GOVERNANCE RULE: before deleting any vault note, the agent MUST call:

  vault_change_log --action deleted --path <note> --reason <why>



Usage:

    python vault_change_log.py --action created --path "01_Projects/ans/status.md" --reason "New sprint" --agent claude

    python vault_change_log.py --action updated --path "03_Decisions/adr-001.md" --reason "Added context"

    python vault_change_log.py --action deleted --path "07_Knowledge/old.md" --reason "Duplicate of glossary/jwt.md"

    python vault_change_log.py --action moved --path "10_Migrated/old.md" --new_path "07_Knowledge/jwt.md" --reason "Promoted"

    python vault_change_log.py --query --last 20

    python vault_change_log.py --query --project "ans" --last 10

    python vault_change_log.py --query --action deleted

"""

import argparse

import json

import subprocess

import sys

from vault_errors import emit_error, emit_fallo, mensaje_de, wrap_main, proyecto_registrado
from vault_entorno import agente_por_defecto
from vault_lib import utcnow
from vault_io import (IndiceIlegible, append_line, atomic_write_text, file_lock,
                      identidad_requisito)
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional


#: `ingested` and `linted` (2026-11-16) are the two operations of the Karpathy
#: "LLM Wiki" log that are not a single note's lifecycle: an ingest pass that
#: produced notes from one source, and a lint pass over the whole vault. They
#: are appended, never inserted, so the stable order of the older five holds.
VALID_ACTIONS = ["created", "updated", "deleted", "moved", "transition", "ingested", "linted"]

VALID_PROPAGATE_STRATEGIES = ["conservative", "transitive", "critical-path"]


SCRIPTS_DIR = Path(__file__).parent


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir, proyectos as _proyectos  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _log_md() -> Path:
    return _repo().dir_sistema / "change-log.md"


def _gobernanza() -> RepositorioGobernanza:
    """La bitacora no es de Autoria: se recibe del contexto que la declara.

    `vault_fundamentals` y `vault_quality_check` (Gobernanza) leen el mismo
    registro. Que la ubicacion y el formato vengan de `RepositorioGobernanza` y
    no de una constante propia es deliberado — tres sitios decidiendo donde
    vive la bitacora es AP-05, y el dia que se moviera solo se enteraria el que
    escribe: el que lee devuelve {} sin fallar.
    """
    return RepositorioGobernanza(construir())


def _log_json() -> Path:
    """The frozen legacy log (`.change-log.json`); also the log lock's target.

    The lock keeps its historical target so every writer of the log, before
    and after the append-only format, serializes on the same lock.
    """
    return _gobernanza().bitacora_cambios


def _log_lines() -> Path:
    """The append-only log (`.change-log.jsonl`), where new entries go."""
    return _gobernanza().bitacora_cambios_lineas


def leer_bitacora():
    """One read of the whole log through its owner; `IndiceIlegible` if unreadable.

    Absent and empty are the same: no history yet. Unreadable is not: until
    2026-10-15 a broken JSON read as `[]`, the next `add` rewrote the file with
    a single entry and answered ok:true, and the non-repudiation history (F8)
    disappeared without anyone saying so (AP-51). A torn appended line is not
    unreadable history: it is left out and named in `lineas_rotas`.
    """
    repo = _gobernanza()
    try:
        return repo.leer_bitacora_cambios()
    except (OSError, ValueError, TypeError) as exc:
        ruta = repo.bitacora_cambios if repo.bitacora_cambios.exists() else repo.bitacora_cambios_lineas
        raise IndiceIlegible(ruta, exc) from exc


def _read_json_log() -> List[Dict[str, Any]]:
    """Las entradas de la bitacora; `IndiceIlegible` si existe y no se lee."""
    return leer_bitacora().entradas


def leer_historial_completo() -> List[Dict[str, Any]]:
    """Read one log snapshot without the query API's latest-20 limit."""
    entries = _read_json_log()
    if any(not isinstance(entry, dict) for entry in entries):
        raise IndiceIlegible(_log_json(), ValueError("Invalid history entry"))
    return entries


MD_HEADER = (
    "# Change Log\n\n"
    "Registro automatico de cambios en el vault.\n\n"
    "| Timestamp | Action | Path | New Path | Reason | Agent |\n"
    "|---|---|---|---|---|---|\n"
)

#: Bytes read from the start of `change-log.md` to find its table header. The
#: header is written once, at the top; a file whose head does not hold it
#: takes the old whole-file path, so its behaviour is unchanged.
_MD_HEAD_BYTES = 4096


def _celda(valor: Any) -> str:
    """One Markdown table cell: a line break would end the row (and the O(1)
    append refuses multi-line lines), so CR, LF and CRLF become `<br>`.

    Independent verifier (2026-11-18): a reason with a line break made the
    append raise after the JSON row was written, leaving a half-written entry
    and, for `vault_delete`, a `deleted` row for a note still on disk.
    """
    texto = str(valor or "")
    return texto.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


def _md_row(entry: Dict[str, Any], marker: str) -> str:
    ts = _celda(entry.get("timestamp", ""))[:19]
    action = _celda(entry.get("action", ""))
    path = _celda(entry.get("path", ""))
    new_path = _celda(entry.get("new_path") or "")
    reason = _celda(entry.get("reason", "")).replace("|", "\\|")
    agent = _celda(entry.get("agent", ""))
    # The marker lives inside the last cell: an HTML block on its own line
    # ends a GFM table, and every later row would render as plain text.
    suffix = f" {marker}" if marker else ""
    return f"| {ts} | `{action}` | `{path}` | `{new_path}` | {reason} | {agent}{suffix} |"


def _md_head() -> Optional[str]:
    """The first bytes of the Markdown log, or None when it cannot be read."""
    try:
        with open(_log_md(), "rb") as fh:
            return fh.read(_MD_HEAD_BYTES).decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError:
        return None


def _append_md_log(entry: Dict[str, Any]) -> bool:
    """Append the entry's row to `change-log.md`; False when it is already there.

    O(1) on the common path: the row is appended and the header, written once,
    is only looked for in the head of the file. Two cases still read the whole
    file, as before: a requirement event, whose marker is looked for so a
    replay never writes the row twice, and a file whose head holds no header,
    which keeps the old behaviour (the table is started again).
    """
    _system_dir().mkdir(parents=True, exist_ok=True)
    marker = f"<!-- requirement-event:{entry['id']} -->" if "requirement" in entry else ""
    row = _md_row(entry, marker)

    head = _md_head()
    if marker or head is None or (head and "| Timestamp |" not in head):
        existing = ""
        if _log_md().exists():
            try:
                existing = _log_md().read_text(encoding="utf-8")
            except OSError:
                if marker:
                    raise
        if marker and marker in existing:
            return False
        if "| Timestamp |" not in existing:
            atomic_write_text(_log_md(), MD_HEADER + row + "\n")
            _refrescar_busqueda_del_log()
            return True
    elif not head:
        # A new (or empty) log: the header and the first row, once.
        atomic_write_text(_log_md(), MD_HEADER + row + "\n")
        _refrescar_busqueda_del_log()
        return True

    append_line(_log_md(), row)
    _refrescar_busqueda_del_log()
    return True


def _refrescar_busqueda_del_log() -> None:
    """The Markdown log is an indexed note: keep its search fingerprint current.

    00_System has no section hook, so without this every append left the
    search index reporting the log as modified (index_stale).
    """
    from vault_io import _regenerador_de_indices

    try:
        regenerador = _regenerador_de_indices()
        if regenerador is None:
            emit_error("vault_change_log", "AUTO_INDEX_ERROR",
                       "Search index refresh unavailable for the change log.")
            return
        regenerador.refrescar_busqueda([], existentes=[_log_md()])
    except Exception as exc:
        # AP-51: the failure is traced with its reason; the log entry itself
        # is already durable and the coherence check will report the row.
        emit_error("vault_change_log", "AUTO_INDEX_ERROR", f"{type(exc).__name__}")


def _run_propagation(path: str, strategy: str) -> Dict[str, Any]:
    """Fire vault_propagate in background — does not block the changelog response."""

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "vault_propagate.py"),
        "--changed",
        path,
        "--strategy",
        strategy,
        "--action",
        "notify,queue",
    ]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return {"ok": True, "strategy": strategy, "queued_async": True}

    except Exception as e:
        return emit_error("vault_change_log", "FILE_WRITE_ERROR", f"No se pudo registrar el cambio: {e}", exception=e)


def vault_change_log_add(
    action: str,
    path: str,
    reason: str,
    agent: str = "claude",
    new_path: Optional[str] = None,
    propagate: Optional[str] = None,
    requirement: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """El registro que **SP-01** exige antes de eliminar una nota.

    El protocolo pide llamar aquí con `action=deleted` ANTES de borrar, y el
    orden no es ceremonia: después del borrado ya no queda de dónde sacar el
    motivo ni la ruta, así que un registro posterior sería una reconstrucción
    de memoria. Esta función no borra nada — deja la constancia; quien borra es
    otra tool, y es esa separación la que permite que la constancia sobreviva
    aunque el borrado falle.
    """
    # SP-01: la constancia del borrado se deja antes de borrar.
    action = action.lower()

    if action not in VALID_ACTIONS:
        return emit_error(
            "vault_change_log", "INVALID_ACTION",
            f"Acción '{action}' inválida. Válidas: {VALID_ACTIONS}",
        )

    if not reason or not reason.strip():
        return emit_error("vault_change_log", "MISSING_REQUIRED_ARG", f"`reason` es obligatorio y no puede ir vacío")

    if action == "moved" and not new_path:
        return emit_error("vault_change_log", "MISSING_REQUIRED_ARG", f"`new_path` es obligatorio para la acción 'moved'")

    if propagate and propagate not in VALID_PROPAGATE_STRATEGIES:
        return emit_error(
            "vault_change_log", "INVALID_ACTION",
            f"Estrategia de propagación '{propagate}' inválida. "
            f"Válidas: {VALID_PROPAGATE_STRATEGIES}",
        )

    if requirement is not None:
        from vault_norms_catalog import LIFECYCLE_REGISTRY

        states = next(row["states"] for row in LIFECYCLE_REGISTRY
                      if row["tool"] == "vault_requirement_save")
        identity = identidad_requisito(requirement)
        if (action != "transition" or identity is None or
                requirement.get("to") not in states or
                requirement.get("from") not in [None, *states]):
            return emit_error("vault_change_log", "INVALID_VALUE", "Invalid requirement transition")
        requirement = {"identity": identity, "project": identity.rsplit("/", 1)[0],
                       "req_id": requirement["req_id"], "from": requirement.get("from"),
                       "to": requirement["to"]}
        if event_id is not None:
            try:
                event_id = str(uuid.UUID(event_id))
            except (ValueError, TypeError, AttributeError):
                return emit_error("vault_change_log", "INVALID_VALUE", "Invalid event identity")
    elif event_id is not None:
        return emit_error("vault_change_log", "INVALID_VALUE", "Event identity requires a structured transition")

    entry: Dict[str, Any] = {
        "id": event_id or str(uuid.uuid4()),
        "action": action,
        "path": path,
        "new_path": new_path,
        "reason": reason.strip(),
        "agent": agent,
        "timestamp": utcnow(),
    }
    if requirement is not None:
        entry["requirement"] = requirement

    # Serialize the appends against concurrent writers: one line each, in lock
    # order, and the JSON and Markdown rows of one entry together. The log is
    # append-only (bigo-inmutabilidad, S3): an ordinary row reads nothing and
    # rewrites nothing. Two cases read the history first. A requirement event,
    # whose identity is looked up so a replay never records it twice. And the
    # first append of a vault that only has the legacy array: it is checked
    # once, so an unreadable history is reported before the new file starts,
    # as before (AP-51) — afterwards the legacy file is never written again,
    # so an append cannot destroy it.
    with file_lock(_log_json()):
        repo = _gobernanza()
        if requirement is not None or (
                repo.bitacora_cambios.exists() and not repo.bitacora_cambios_lineas.exists()):
            try:
                entries = leer_historial_completo()
            except IndiceIlegible as exc:
                # No se escribe nada: el fichero queda como estaba para repararlo.
                return emit_fallo("vault_change_log", exc)
        else:
            entries = []

        if requirement is not None:
            previous = next((row for row in entries if row.get("id") == entry["id"]), None)
            if previous is not None:
                if any(previous.get(key) != entry.get(key)
                       for key in ("action", "path", "requirement")):
                    return emit_error("vault_change_log", "INVALID_VALUE", "Event identity conflict")
                repaired = _append_md_log(previous)
                return {"ok": True, "id": previous["id"], "action": action,
                        "path": path, "written": int(repaired), "entry": previous}

        repo.anexar_bitacora_cambios(entry)

        _append_md_log(entry)

    response: Dict[str, Any] = {
        "ok": True,
        "id": entry["id"],
        "action": action,
        "path": path,
        # Indicador de trabajo (AP-37, O3): la entrada queda en los DOS
        # registros del changelog — el .md legible y el .json del que lee el
        # índice. Sin este contador, "anoté la entrada" y "no hice nada"
        # devolvían la misma forma de envelope.
        "written": 2,
        "log_md": str(_log_md().relative_to(_raiz())).replace("\\", "/"),
        "log_json": str(_log_lines().relative_to(_raiz())).replace("\\", "/"),
    }
    if requirement is not None:
        response["entry"] = entry

    if propagate:
        prop_result = _run_propagation(path, propagate)

        response["propagation_triggered"] = prop_result.get("ok", False)

        response["propagation_strategy"] = propagate

        response["impacted_count"] = prop_result.get("impacted_count", 0)

        if not prop_result.get("ok"):
            response["propagation_error"] = mensaje_de(prop_result)

    return response


def vault_change_log_query(
    project: Optional[str] = None,
    action_filter: Optional[str] = None,
    last: int = 20,
) -> Dict[str, Any]:
    try:
        lectura = leer_bitacora()
    except IndiceIlegible as exc:
        # `total: 0` diria que nunca hubo cambios.
        return emit_fallo("vault_change_log", exc)
    entries = lectura.entradas

    if action_filter:
        entries = [e for e in entries if e.get("action") == action_filter.lower()]

    if project:
        # Por segmento de ruta, no por subcadena: `ans` contaba como suyo todo
        # `transferencias.md`, y `api` todo lo de `mi-api` (AP-63).
        es_del = _proyectos.pertenencia_en(_raiz(), project)
        entries = [
            e for e in entries
            if any(es_del(seg) for seg in str(e.get("path", "")).replace("\\", "/").split("/"))
        ]

    entries_sorted = sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True)

    page = entries_sorted[:last]

    response: Dict[str, Any] = {
        "ok": True,
        "total": len(entries),
        "returned": len(page),
        "entries": page,
    }
    if lectura.lineas_rotas:
        # A torn append (crash mid-line) is left out, never merged: say so.
        response["torn_lines"] = list(lectura.lineas_rotas)
        response["torn_log"] = str(_log_lines().relative_to(_raiz())).replace("\\", "/")
    return response


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Change Log -- record and query note lifecycle events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

REGLA DE GOBERNANZA: antes de eliminar cualquier nota del vault, llamar:

  vault_change_log --action deleted --path <ruta> --reason <motivo>



Ejemplos:

  # Registrar creacion

  python vault_change_log.py --action created --path "01_Projects/ans/status.md" --reason "New sprint tracking" --agent claude



  # Registrar actualizacion

  python vault_change_log.py --action updated --path "03_Decisions/adr-001.md" --reason "Updated rationale section"



  # Registrar eliminacion (REQUERIDO antes de borrar)

  python vault_change_log.py --action deleted --path "07_Knowledge/old-note.md" --reason "Duplicate of glossary/jwt.md"



  # Registrar movimiento

  python vault_change_log.py --action moved --path "10_Migrated/draft.md" --new_path "07_Knowledge/jwt.md" --reason "Promoted from migrated"



  # Consultar ultimas 20 entradas

  python vault_change_log.py --query --last 20



  # Consultar por proyecto

  python vault_change_log.py --query --project "ans" --last 10



  # Consultar solo eliminaciones

  python vault_change_log.py --query --action deleted



Notas:

  - VAULT_ROOT se detecta automaticamente desde la ubicacion del script

  - Guarda en 00_System/change-log.md y 00_System/.change-log.jsonl (append-only);
    un vault anterior conserva 00_System/.change-log.json, que se lee y no se reescribe

  - --query retorna JSON ordenado por timestamp desc

""",
        allow_abbrev=False,
    )

    parser.add_argument("--action", choices=VALID_ACTIONS, help=f"Action to record: {VALID_ACTIONS}")

    parser.add_argument("--path", help="Vault-relative path of the affected note")

    parser.add_argument("--new_path", help="New path (required for action 'moved')")

    parser.add_argument("--reason", help="Why this change was made (required)")

    parser.add_argument(
        "--summary", help="Alias for --reason (accepted for compatibility)"
    )

    parser.add_argument(
        "--agent", default=agente_por_defecto(), help="Agent name (default: VAULT_AGENT o claude)"
    )

    parser.add_argument(
        "--propagate",
        choices=VALID_PROPAGATE_STRATEGIES,
        metavar="STRATEGY",
        help="After recording, trigger propagation: conservative|transitive|critical-path",
    )

    parser.add_argument(
        "--query", action="store_true", help="Query mode: return recent log entries"
    )

    parser.add_argument(
        "--project", type=proyecto_registrado("vault_change_log"), help="Filter query by project name (substring match on path)"
    )

    parser.add_argument(
        "--last",
        type=int,
        default=20,
        help="Number of entries to return in query (default: 20)",
    )

    args = parser.parse_args()

    # --summary is a documented alias for --reason

    reason = args.reason or args.summary

    if args.query:
        result = vault_change_log_query(
            project=args.project,
            action_filter=args.action,
            last=args.last,
        )

    else:
        if not args.action:
            parser.error("--action is required (or use --query mode)")

        if not args.path:
            parser.error("--path is required")

        if not reason:
            parser.error("--reason (or --summary) is required")

        result = vault_change_log_add(
            action=args.action,
            path=args.path,
            reason=reason,
            agent=args.agent,
            new_path=args.new_path,
            propagate=args.propagate,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_change_log"))
