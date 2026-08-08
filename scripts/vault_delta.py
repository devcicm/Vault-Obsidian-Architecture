#!/usr/bin/env python3
"""
Vault Delta — Deteccion de cambios entre sesiones via hashes de contenido.

Compara hashes actuales contra el snapshot en 99_Index/hash-index.json,
luego expande el conjunto cambiado via BFS sobre el grafo de backlinks
para encontrar notas transitivamente obsoletas.

Usar al inicio de sesion: el agente sabe exactamente que re-leer y re-verificar
antes de trabajar, sin depender de git ni timestamps del sistema de archivos.

Usage:
    python vault_delta.py                        # detectar cambios + actualizar hash-index
    python vault_delta.py --dry-run              # detectar sin actualizar
    python vault_delta.py --project mi-api       # acotar a un proyecto
    python vault_delta.py --min-risk medium      # filtrar stale_deps por nivel de riesgo
    python vault_delta.py --snapshot             # solo guardar snapshot sin comparar
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vault_errors import wrap_main
from vault_lib import utcnow
from vault_io import atomic_write_json
from vault_registry import ORDERED_SECTIONS


# Derivado de `vault_registry`, no copiado: la copia literal se quedo en 18
# secciones y dejaba fuera `17_Preferences`, `18_Bugs`, `19_Audits` y
# `20_Quarantine` sin que nada fallara.
VAULT_SECTIONS = frozenset(ORDERED_SECTIONS)

# Orden canónico de severidad, de mayor a menor. Lo consume el `choices` de
# `--min-risk`, que antes era una copia literal escrita a mano: la CLI aceptaba
# un conjunto de valores y el registro declaraba otro sin que nada lo comparase.
# El vocabulario se declara una vez y se consume, no se copia. Ver
# `vault_vocabulario.py` para el registro y su contexto dueño.
from vault_vocabulario import mapa as _mapa, opciones as _opciones, rango as _rango

MIN_RISK_ORDER = _opciones("severidad")

# Los pesos son la posición en el vocabulario; los umbrales no se pueden
# derivar —son de esta tool— pero sus claves sí tienen dueño, y `_mapa` falla
# al importarse si alguna vez dejan de cubrirlo.
CIA_WEIGHT = _rango("severidad")
RISK_THRESHOLDS = _mapa(
    "severidad", {"critical": 8, "high": 4, "medium": 2, "low": 0}
)


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.autoria.repositorio import RepositorioAutoria  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioAutoria:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioAutoria(construir(root))


def _hash_index() -> Path:
    return _repo().indice_hashes


def _graph_file() -> Path:
    return _repo().grafo


def _is_vault_note(path: Path) -> bool:
    try:
        parts = path.relative_to(_raiz()).parts
    except ValueError:
        return False
    return len(parts) >= 2 and parts[0] in VAULT_SECTIONS


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_cia_integrity(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if not content.startswith("---"):
            return "medium"
        parts = content.split("---", 2)
        if len(parts) < 3:
            return "medium"
        for line in parts[1].splitlines():
            if line.startswith("cia_integrity:"):
                return line.split(":", 1)[1].strip().strip("\"'")
    except Exception:
        pass
    return "medium"


def _collect_current_hashes(project: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    hashes: Dict[str, Dict[str, Any]] = {}
    for note_path in _raiz().rglob("*.md"):
        if not _is_vault_note(note_path):
            continue
        if any(part.startswith(".") for part in note_path.parts):
            continue
        rel = str(note_path.relative_to(_raiz())).replace("\\", "/")
        if project and project not in rel:
            continue
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
            hashes[rel] = {
                "hash": _sha256(content),
                "size": len(content.encode("utf-8")),
                "cia_integrity": _read_cia_integrity(note_path),
            }
        except (PermissionError, OSError):
            continue
    return hashes


def _load_hash_index() -> Dict[str, Any]:
    if not _hash_index().exists():
        return {"snapshot_at": None, "notes": {}}
    try:
        return json.loads(_hash_index().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"snapshot_at": None, "notes": {}}


def _compute_delta(
    previous: Dict[str, Any],
    current: Dict[str, Any],
) -> Dict[str, List[str]]:
    prev_notes = previous.get("notes", {})
    changed, added, deleted = [], [], []

    for path, info in current.items():
        if path not in prev_notes:
            added.append(path)
        elif info["hash"] != prev_notes[path].get("hash"):
            changed.append(path)

    for path in prev_notes:
        if path not in current:
            deleted.append(path)

    return {
        "changed": sorted(changed),
        "added": sorted(added),
        "deleted": sorted(deleted),
    }


def _build_reverse_graph(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    reverse: Dict[str, List[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        src = edge.get("from", edge.get("source", ""))
        tgt = edge.get("to", edge.get("target", ""))
        if src and tgt:
            reverse[tgt].append(src)
    return reverse


def _bfs_impact(
    changed: List[str],
    reverse_graph: Dict[str, List[str]],
    current_hashes: Dict[str, Dict[str, Any]],
    max_hops: int = 4,
) -> List[Dict[str, Any]]:
    visited: Set[str] = set(changed)
    queue: deque = deque([(path, 0, path) for path in changed])
    results: List[Dict[str, Any]] = []

    while queue:
        node, dist, via = queue.popleft()
        if dist == 0:
            continue
        if dist > max_hops:
            continue

        info = current_hashes.get(node, {})
        cia = info.get("cia_integrity", "medium")
        weight = CIA_WEIGHT.get(cia, 2)
        stale_risk = round(weight / (dist + 1), 3)

        results.append(
            {
                "path": node,
                "distance": dist,
                "cia_integrity": cia,
                "stale_risk": stale_risk,
                "via": via,
            }
        )

        for neighbor in reverse_graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1, node))

    return sorted(results, key=lambda x: (-x["stale_risk"], x["distance"]))


def _risk_passes(stale_risk: float, cia: str, min_risk: str) -> bool:
    if min_risk not in RISK_THRESHOLDS:
        return True
    threshold_score = RISK_THRESHOLDS[min_risk]
    weight = CIA_WEIGHT.get(cia, 2)
    return (weight * stale_risk) >= threshold_score or stale_risk >= 0.4


def vault_delta(
    dry_run: bool = False,
    project: Optional[str] = None,
    min_risk: Optional[str] = None,
    snapshot_only: bool = False,
) -> Dict[str, Any]:
    current = _collect_current_hashes(project)

    if snapshot_only:
        if not dry_run:
            atomic_write_json(_hash_index(), {"snapshot_at": utcnow(), "notes": current})
        return {
            "ok": True,
            "action": "snapshot",
            "notes_hashed": len(current),
            "dry_run": dry_run,
            "hash_index": str(_hash_index().relative_to(_raiz())).replace("\\", "/"),
        }

    previous = _load_hash_index()
    delta = _compute_delta(previous, current)

    changed_set = delta["changed"] + delta["added"]
    stale_deps: List[Dict[str, Any]] = []

    if changed_set and _graph_file().exists():
        try:
            graph = json.loads(_graph_file().read_text(encoding="utf-8"))
            reverse = _build_reverse_graph(graph)
            raw_impact = _bfs_impact(changed_set, reverse, current)
            if min_risk:
                stale_deps = [
                    d
                    for d in raw_impact
                    if _risk_passes(d["stale_risk"], d["cia_integrity"], min_risk)
                ]
            else:
                stale_deps = raw_impact
        except Exception as exc:
            stale_deps = [{"error": str(exc)}]

    if not dry_run:
        atomic_write_json(_hash_index(), {"snapshot_at": utcnow(), "notes": current})

    total_changed = len(delta["changed"]) + len(delta["added"]) + len(delta["deleted"])
    parts = []
    if delta["changed"]:
        parts.append(f"{len(delta['changed'])} modificada(s)")
    if delta["added"]:
        parts.append(f"{len(delta['added'])} nueva(s)")
    if delta["deleted"]:
        parts.append(f"{len(delta['deleted'])} eliminada(s)")
    summary = (
        (
            ", ".join(parts)
            + f" · {len(stale_deps)} dependencia(s) potencialmente obsoleta(s)"
        )
        if parts
        else "Sin cambios desde el ultimo snapshot"
    )

    return {
        "ok": True,
        "changed": delta["changed"],
        "added": delta["added"],
        "deleted": delta["deleted"],
        "stale_deps": stale_deps,
        "total_changed": total_changed,
        "summary": summary,
        "dry_run": dry_run,
        "hash_index_updated": not dry_run and not snapshot_only,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault Delta — cambios entre sesiones via content hashes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_delta.py                        # detectar cambios + actualizar hash-index
  python vault_delta.py --dry-run              # detectar sin actualizar hash-index
  python vault_delta.py --snapshot             # guardar snapshot inicial (primera vez)
  python vault_delta.py --project electron-fingerprint
  python vault_delta.py --min-risk high        # solo stale_deps de riesgo high/critical

Flujo de sesion:
  python vault_delta.py --snapshot             # inicio: guardar baseline
  # ... trabajar ...
  python vault_delta.py                        # cierre: que cambio, que esta stale

Notas:
  - Hash index: 99_Index/hash-index.json
  - Expande el conjunto cambiado via BFS sobre graph.json (backlinks)
  - --min-risk acepta: critical, high, medium, low
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detectar cambios sin actualizar hash-index",
    )
    parser.add_argument(
        "--snapshot", action="store_true", help="Solo guardar snapshot sin comparar"
    )
    parser.add_argument("--project", help="Acotar deteccion a un proyecto slug")
    parser.add_argument(
        "--min-risk",
        choices=MIN_RISK_ORDER,
        help="Filtrar stale_deps por nivel minimo de riesgo",
    )

    args = parser.parse_args()
    result = vault_delta(
        dry_run=args.dry_run,
        project=args.project,
        min_risk=args.min_risk,
        snapshot_only=args.snapshot,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_delta"))
