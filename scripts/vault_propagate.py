#!/usr/bin/env python3
"""
vault_propagate.py — Propagation strategies for graph-aware change management.

Applies one of three strategies over the impact graph returned by vault_impact,
then executes one or more actions on the affected notes.

Strategies:
  conservative   — only dist=1 (direct neighbors)
  transitive     — full BFS up to --max-hops (default 5)
  critical-path  — any distance, only cia_integrity high|critical

Actions (comma-separated, combinable):
  notify    — write propagation_pending timestamp to frontmatter
  queue     — append to 00_System/propagation-queue.json
  reindex   — call vault_section_index per affected folder

Usage:
    python vault_propagate.py --changed "overview.md" --strategy transitive --action notify
    python vault_propagate.py --changed "api.md" --strategy critical-path --action queue,reindex
    python vault_propagate.py --queue-report          # list pending notes, most urgent first
    python vault_propagate.py --clear "01_Projects/api/overview.md"  # mark as reviewed
"""

import argparse
import json
import subprocess

import vault_subproceso
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import emit_error, mensaje_de, wrap_main
from vault_lib import separar_frontmatter, utcnow
from vault_impact import vault_impact
from vault_io import (
    assert_within_vault, atomic_write_text,
    tomar_lock, write_report,
)

SCRIPTS_DIR = Path(__file__).parent


VALID_STRATEGIES = ("conservative", "transitive", "critical-path")
VALID_ACTIONS = ("notify", "queue", "reindex")


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.ciclo_de_vida.repositorio import RepositorioCicloDeVida  # noqa: E402
from vault.gobernanza.repositorio import RepositorioGobernanza  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.kernel.bloqueo import LockPerdido  # noqa: E402
from vault.kernel.frontmatter_escritura import Frontmatter  # noqa: E402
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import opciones as _opciones, rango as _rango

RISK_ORDER = _rango("severidad")


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioCicloDeVida:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioCicloDeVida(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _propagation_queue() -> Path:
    """La cola no es de Ciclo de vida: se recibe del contexto que la declara.

    `vault_audit` (Gobernanza) lee el mismo fichero —medido el 2026-10-08:
    lo lee, no lo escribe— y la escritura la hace el dueño,
    `RepositorioGobernanza.escribir_cola_propagacion`. Que la ubicacion
    venga de `RepositorioGobernanza` y no de una constante propia es
    deliberado — dos sitios decidiendo donde vive la cola es AP-05, y el dia
    que se mueva solo se enteraria uno.
    """
    return RepositorioGobernanza(construir()).cola_propagacion


def _read_propagation_queue() -> Dict[str, Any]:
    if not _propagation_queue().exists():
        return {"updated_at": utcnow(), "pending": []}
    try:
        data = json.loads(_propagation_queue().read_text(encoding="utf-8"))
        return (
            data if isinstance(data, dict) else {"updated_at": utcnow(), "pending": []}
        )
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        emit_error("vault_propagate", "QUEUE_READ_ERROR", str(exc))
        return {"updated_at": utcnow(), "pending": []}
    except Exception as exc:
        emit_error("vault_propagate", "UNEXPECTED_ERROR", str(exc))
        return {"updated_at": utcnow(), "pending": []}


def _write_propagation_queue(data: Dict[str, Any]) -> None:
    data["updated_at"] = utcnow()
    RepositorioGobernanza(construir()).escribir_cola_propagacion(data, timeout=30.0)


#: Espera máxima por el lock de una nota; la misma que vault_write y vault_append.
_LOCK_TIMEOUT = 10.0


def _fuera_del_vault(note_path: str) -> Optional[str]:
    """El motivo si *note_path* sale del vault (AP-36); None si no."""
    try:
        assert_within_vault(_raiz() / note_path, _raiz())
    except ValueError as exc:
        return str(exc)
    return None


def _action_notify(note_path: str, timestamp: str) -> bool:
    """Write propagation_pending field to frontmatter of a note."""
    full_path = _raiz() / note_path
    # La ruta sale del grafo, no del agente, pero un graph.json ajeno o
    # envenenado puede nombrar `../x.md`: se contiene igual (AP-36).
    if _fuera_del_vault(note_path) or not full_path.exists():
        return False
    lock = tomar_lock(full_path, _LOCK_TIMEOUT)
    if lock is None:
        return False
    try:
        with lock:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            bloque, cuerpo = separar_frontmatter(content)
            if bloque is not None:
                # AP-46: el dueño reemplaza la marca anterior en su sitio. Va
                # citada (`texto=True`) como siempre: el lector recibe `str`.
                fm = Frontmatter.editar(bloque).set(
                    "propagation_pending", timestamp, texto=True)
                new_content = fm.render() + "\n" + cuerpo
                atomic_write_text(full_path, new_content)
                return True
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        emit_error("vault_propagate", "NOTIFY_WRITE_ERROR", str(exc))
    except Exception as exc:
        emit_error("vault_propagate", "UNEXPECTED_ERROR", str(exc))
    return False


def _action_queue(
    note_path: str,
    triggered_by: List[str],
    distance: int,
    stale_risk: str,
) -> None:
    """Append a note to propagation-queue.json."""
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])

    # Dedup: update existing entry if already queued
    existing = next((e for e in pending if e["path"] == note_path), None)
    if existing:
        existing["queued_at"] = utcnow()
        existing["triggered_by"] = list(
            set(existing.get("triggered_by", []) + triggered_by)
        )
        existing["distance"] = min(existing.get("distance", distance), distance)
        existing["priority"] = stale_risk
    else:
        pending.append(
            {
                "path": note_path,
                "queued_at": utcnow(),
                "triggered_by": triggered_by,
                "distance": distance,
                "priority": stale_risk,
                "action_required": "review_content",
            }
        )

    queue["pending"] = pending
    _write_propagation_queue(queue)


def _action_reindex(folders: Set[str]) -> List[str]:
    """Call vault_section_index for each affected top-level folder."""
    reindexed = []
    for folder in sorted(folders):
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "vault_section_index.py"),
            "--folder",
            folder,
        ]
        try:
            result = vault_subproceso.ejecutar(cmd, capture_output=True, timeout=30)
            if result.returncode == 0:
                reindexed.append(folder)
        except Exception as exc:
            emit_error("vault_propagate", "REINDEX_ERROR", str(exc))
    return reindexed


def vault_propagate(
    changed_notes: List[str],
    strategy: str = "conservative",
    actions: List[str] = None,
    max_hops: int = 5,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply a propagation strategy and execute actions on affected notes.

    Args:
        changed_notes: Vault-relative paths of changed notes.
        strategy:      'conservative' | 'transitive' | 'critical-path'
        actions:       List of actions: ['notify', 'queue', 'reindex']
        max_hops:      Max BFS depth (only for 'transitive')
        since:         If provided, augment changed_notes from change log.

    Returns:
        {ok, strategy, actions, impacted_count, notified, queued, reindexed, timestamp}
    """
    if actions is None:
        actions = ["notify", "queue"]

    strategy = strategy.lower()
    if strategy not in VALID_STRATEGIES:
        return emit_error("vault_propagate", "INVALID_VALUE", f"Invalid strategy '{strategy}'. Must be one of: {VALID_STRATEGIES}")

    invalid_actions = [a for a in actions if a not in VALID_ACTIONS]
    if invalid_actions:
        return emit_error("vault_propagate", "INVALID_VALUE", f"Invalid actions: {invalid_actions}. Must be in: {VALID_ACTIONS}")

    # Get impact
    hops = 1 if strategy == "conservative" else max_hops
    impact = vault_impact(list(changed_notes), max_hops=hops, since=since)

    if not impact.get("ok"):
        return emit_error("vault_propagate", "UNEXPECTED_ERROR", f"vault_impact failed: {mensaje_de(impact)}")

    impacted = impact.get("impacted", [])

    # Apply strategy filter
    if strategy == "conservative":
        impacted = [n for n in impacted if n["distance"] == 1]
    elif strategy == "critical-path":
        impacted = [n for n in impacted if n["cia_integrity"] in ("critical", "high")]

    if not impacted:
        return {
            "ok": True,
            "strategy": strategy,
            "actions": actions,
            "impacted_count": 0,
            "notified": [],
            "queued": [],
            "reindexed": [],
            "timestamp": utcnow(),
            "message": "No notes require propagation with this strategy",
        }

    timestamp = utcnow()
    notified: List[str] = []
    queued: List[str] = []
    affected_folders: Set[str] = set()

    for node in impacted:
        note_path = node["path"]
        affected_folders.add(note_path.split("/")[0])

        if "notify" in actions:
            if _action_notify(note_path, timestamp):
                notified.append(note_path)

        if "queue" in actions:
            _action_queue(
                note_path=note_path,
                triggered_by=list(changed_notes),
                distance=node["distance"],
                stale_risk=node["stale_risk"],
            )
            queued.append(note_path)

    reindexed: List[str] = []
    if "reindex" in actions:
        reindexed = _action_reindex(affected_folders)

    return {
        "ok": True,
        **write_report(),
        "strategy": strategy,
        "actions": actions,
        "impacted_count": len(impacted),
        "notified": notified,
        "queued": queued,
        "reindexed": reindexed,
        "timestamp": timestamp,
    }


def vault_propagate_queue_report(min_priority: Optional[str] = None) -> Dict[str, Any]:
    """List pending propagation items, sorted by priority then queued_at."""
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])

    if min_priority:
        min_level = RISK_ORDER.get(min_priority.lower(), 1)
        pending = [
            e
            for e in pending
            if RISK_ORDER.get(e.get("priority", "low"), 1) >= min_level
        ]

    pending.sort(
        key=lambda e: (
            -RISK_ORDER.get(e.get("priority", "low"), 1),
            e.get("queued_at", ""),
        )
    )

    return {
        "ok": True,
        "total_pending": len(pending),
        "updated_at": queue.get("updated_at", ""),
        "pending": pending,
    }


def vault_propagate_clear(note_path: str) -> Dict[str, Any]:
    """Mark a note as reviewed: remove propagation_pending from frontmatter and queue."""
    cleared_fm = False
    # Medido en v40.34: `--clear ../canario.md` reescribía un fichero de fuera
    # del vault con ok: true. `Path.write_text` en crudo se saltaba el guard de
    # atomic_write_text; se contiene aquí, antes de leer nada (AP-36).
    fuera = _fuera_del_vault(note_path)
    if fuera:
        return emit_error("vault_propagate", "INVALID_PATH", fuera)
    full_path = _raiz() / note_path
    if full_path.exists():
        lock = tomar_lock(full_path, _LOCK_TIMEOUT)
        if lock is None:
            return {
                **emit_error(
                    "vault_propagate", "NOTE_LOCKED",
                    f"Otro escritor tiene {note_path}; no se limpió nada.",
                ),
                "path": note_path,
            }
        try:
            # Lectura y escritura bajo el lock de la nota (F1).
            with lock:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                # AP-46: la marca se retira del bloque por su dueño. El
                # `re.sub` sobre el contenido entero borraba también una línea
                # `propagation_pending:` del cuerpo —una nota que documenta
                # esta tool, por ejemplo— y daba la limpieza por hecha aunque
                # el frontmatter no la tuviera.
                bloque, cuerpo = separar_frontmatter(content)
                if bloque is not None:
                    antes = Frontmatter.editar(bloque)
                    despues = Frontmatter.editar(bloque).quitar("propagation_pending")
                    if despues.campos() != antes.campos():
                        atomic_write_text(full_path, despues.render() + "\n" + cuerpo)
                        cleared_fm = True
        except LockPerdido:
            # Quien perdió el lock no limpia nada, tampoco la cola: el
            # `except Exception` de abajo lo convertía en un envelope que nadie
            # devolvía y la nota salía de la cola con la marca todavía puesta
            # (auditoría del 2026-10-15). `wrap_main` lo da como NOTE_LOCKED.
            raise
        except (OSError, UnicodeDecodeError, PermissionError) as exc:
            emit_error("vault_propagate", "CLEAR_FM_ERROR", str(exc))
        except Exception as exc:
            emit_error("vault_propagate", "UNEXPECTED_ERROR", str(exc))

    cleared_queue = False
    queue = _read_propagation_queue()
    pending = queue.get("pending", [])
    new_pending = [e for e in pending if e["path"] != note_path]
    if len(new_pending) < len(pending):
        queue["pending"] = new_pending
        _write_propagation_queue(queue)
        cleared_queue = True

    return {
        "ok": True,
        "path": note_path,
        "cleared_frontmatter": cleared_fm,
        "cleared_queue": cleared_queue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_propagate — propagation strategies for graph-aware change management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Notificar vecinos directos
  python vault_propagate.py --changed "overview.md" --strategy conservative --action notify

  # Propagar completamente con queue y reindex
  python vault_propagate.py --changed "api.md" --strategy transitive --action queue,reindex

  # Solo notas criticas/high, cualquier distancia
  python vault_propagate.py --changed "core.md" --strategy critical-path --action notify,queue

  # Ver cola de propagacion pendiente
  python vault_propagate.py --queue-report

  # Ver solo items high/critical
  python vault_propagate.py --queue-report --min-priority high

  # Marcar nota como revisada
  python vault_propagate.py --clear "01_Projects/api/overview.md"

  # Propagar con --since (auto-detecta que cambio)
  python vault_propagate.py --since "2026-05-09" --strategy conservative --action queue
""",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--changed",
        nargs="+",
        metavar="PATH",
        default=[],
        help="Vault-relative paths of changed notes",
    )
    parser.add_argument(
        "--strategy",
        default="conservative",
        choices=list(VALID_STRATEGIES),
        help="Propagation strategy (default: conservative)",
    )
    parser.add_argument(
        "--action",
        default="notify,queue",
        metavar="ACTIONS",
        help="Comma-separated actions: notify,queue,reindex (default: notify,queue)",
    )
    parser.add_argument(
        "--max-hops",
        type=int,
        default=5,
        metavar="N",
        help="Max BFS depth for transitive strategy (default: 5)",
    )
    parser.add_argument(
        "--since",
        metavar="DATE",
        help="Augment --changed from change log since this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--queue-report", action="store_true", help="List pending propagation items"
    )
    parser.add_argument(
        "--min-priority",
        choices=_opciones("severidad"),
        help="Filter queue-report by minimum priority",
    )
    parser.add_argument(
        "--clear",
        metavar="PATH",
        help="Mark a note as reviewed (remove propagation_pending)",
    )

    args = parser.parse_args()

    if args.queue_report:
        result = vault_propagate_queue_report(min_priority=args.min_priority)
    elif args.clear:
        result = vault_propagate_clear(args.clear)
    else:
        if not args.changed and not args.since:
            parser.error(
                "Provide --changed PATH [PATH ...] or --since DATE (or use --queue-report / --clear)"
            )

        actions = [a.strip() for a in args.action.split(",") if a.strip()]
        result = vault_propagate(
            changed_notes=list(args.changed),
            strategy=args.strategy,
            actions=actions,
            max_hops=args.max_hops,
            since=args.since,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_propagate"))
