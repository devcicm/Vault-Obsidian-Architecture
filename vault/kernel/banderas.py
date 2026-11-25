"""Cola append-only de banderas de la Fábrica de Conocimiento (SPEC-04, SP-05).

Vive en `vault/kernel/` porque la escribe `vault_ronda` (contexto `autoria`,
perfil `ejecutor`) y la consume `vault_propagate` / `curacion` (contexto
`ciclo_de_vida`, perfil `operador`): así ambos contextos operan sobre la cola
`00_System/.flags.jsonl` sin abrir cruces entre contextos. Todo el estado
persiste en texto plano versionado en Git — cero bases de datos y cero terceros.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .escritura import escritura_atomica
from .fs import tomar_lock
from .safety import scan_poison

FICHERO_FLAGS = ".flags.jsonl"
TIPOS_BANDERA: Tuple[str, ...] = ("gap", "stale", "schema_drift", "format_feedback")
ESTADOS_BANDERA: Tuple[str, ...] = ("open", "triaged", "applied", "dismissed")
_ESTADOS_ABIERTOS = frozenset({"open", "triaged"})
_TRANSICIONES_BANDERA: Dict[str, frozenset[str]] = {
    "open": frozenset({"triaged", "applied", "dismissed"}),
    "triaged": frozenset({"applied", "dismissed"}),
    "applied": frozenset(),
    "dismissed": frozenset(),
}
_RE_FLAG_ID = re.compile(r"^FLAG-(\d+)$")
_LOCK_TIMEOUT = 10.0


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _resolver_raiz_y_cola(repo_o_raiz: Union[Path, Any]) -> Tuple[Path, Path]:
    if hasattr(repo_o_raiz, "raiz") and hasattr(repo_o_raiz, "cola_banderas"):
        return Path(repo_o_raiz.raiz), Path(repo_o_raiz.cola_banderas)
    raiz = Path(repo_o_raiz.raiz) if hasattr(repo_o_raiz, "raiz") else Path(repo_o_raiz)
    return raiz, raiz / "00_System" / FICHERO_FLAGS


def _contener_en_vault(ruta: Path, raiz: Path) -> Path:
    raiz_res = raiz.resolve()
    ruta_res = ruta.resolve()
    try:
        ruta_res.relative_to(raiz_res)
    except ValueError as exc:
        raise ValueError(f"Ruta fuera del vault (AP-36): {ruta}") from exc
    return ruta_res


def _anexar_linea_atomica(ruta: Path, linea: str) -> None:
    prev = ruta.read_text(encoding="utf-8", errors="replace") if ruta.exists() else ""
    if prev and not prev.endswith("\n"):
        prev += "\n"
    escritura_atomica(ruta, prev + linea + "\n")


def _leer_round_id_activo(raiz: Path) -> str:
    fichero = raiz / "00_System" / "ronda-activa.json"
    if not fichero.is_file():
        return ""
    try:
        datos = json.loads(fichero.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return ""
    if isinstance(datos, dict) and datos.get("round_id"):
        return str(datos["round_id"]).strip()
    return ""


def _leer_eventos(ruta: Path) -> Tuple[List[Dict[str, Any]], int]:
    """Lee el JSONL append-only devolviendo `(eventos, lineas_rotas)` (AP-51)."""
    if not ruta.exists():
        return [], 0
    eventos: List[Dict[str, Any]] = []
    rotas = 0
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        txt = linea.strip()
        if not txt:
            continue
        try:
            obj = json.loads(txt)
        except json.JSONDecodeError:
            rotas += 1
            continue
        if isinstance(obj, dict) and obj.get("flag_id"):
            eventos.append(obj)
        else:
            rotas += 1
    return eventos, rotas


def _estado_actual_banderas(ruta: Path) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """Reconstruye la vista consolidada de cada `FLAG-NNN` desde el log append-only."""
    eventos, rotas = _leer_eventos(ruta)
    por_id: Dict[str, Dict[str, Any]] = {}
    for ev in eventos:
        fid = str(ev["flag_id"])
        if fid not in por_id:
            por_id[fid] = dict(ev)
            por_id[fid].setdefault("history", [])
        else:
            prev = por_id[fid]
            prev.setdefault("history", []).append({
                "status": ev.get("status"),
                "updated_at": ev.get("updated_at") or ev.get("timestamp"),
                "agent": ev.get("agent"),
                "resolution_note": ev.get("resolution_note", ""),
                "applied_path": ev.get("applied_path", ""),
            })
            if ev.get("status"):
                prev["status"] = ev["status"]
            if ev.get("updated_at") or ev.get("timestamp"):
                prev["updated_at"] = ev.get("updated_at") or ev.get("timestamp")
            if ev.get("resolution_note"):
                prev["resolution_note"] = ev["resolution_note"]
            if ev.get("applied_path"):
                prev["applied_path"] = ev["applied_path"]
            if ev.get("curated_by"):
                prev["curated_by"] = ev["curated_by"]
    return por_id, rotas


def _siguiente_flag_id(por_id: Dict[str, Dict[str, Any]]) -> str:
    mayor = 0
    for fid in por_id:
        m = _RE_FLAG_ID.match(fid)
        if m:
            mayor = max(mayor, int(m.group(1)))
    return f"FLAG-{mayor + 1:03d}"


def levantar_bandera(
    repo: Union[Path, Any],
    kind: str,
    observed: str,
    proposed_fix: str = "",
    target_note: str = "",
    trace_ref: str = "",
    round_id: str = "",
    agent: str = "",
) -> Dict[str, Any]:
    """Registra una bandera no bloqueante `FLAG-NNN` bajo SP-05 y pre-vuelo anti-poison."""
    raiz, ruta_cola = _resolver_raiz_y_cola(repo)
    tipo = str(kind or "").strip().lower()
    if tipo not in TIPOS_BANDERA:
        return {
            "ok": False,
            "error_code": "INVALID_VALUE",
            "message": f"SP-05: tipo de bandera inválido {kind!r}. Válidos: {list(TIPOS_BANDERA)}",
        }
    obs = str(observed or "").strip()
    if not obs:
        return {
            "ok": False,
            "error_code": "INVALID_INPUT",
            "message": "SP-05: --observed es obligatorio y no puede estar vacío.",
        }
    prop = str(proposed_fix or "").strip()
    target = str(target_note or "").strip().replace("\\", "/")

    # SP-05 + Fase H: pre-vuelo anti-poison NO desactivable sobre la señal hacia el curador.
    hallazgos = (
        scan_poison(obs, "flag:observed")
        + scan_poison(prop, "flag:proposed_fix")
        + scan_poison(target, "flag:target_note")
    )
    bloqueantes = [f for f in hallazgos if f.severity in ("critical", "high")]
    if bloqueantes:
        return {
            "ok": False,
            "error_code": "POISON_DETECTED",
            "message": f"SP-05: bandera bloqueada por pre-vuelo anti-poison: {bloqueantes[0].detail}",
            "findings": [f.to_dict() for f in bloqueantes],
        }

    # AP-36: si nombra una nota objetivo, debe contenerse dentro del vault.
    if target:
        try:
            resuelta = _contener_en_vault(raiz / target, raiz)
            target = resuelta.relative_to(raiz.resolve()).as_posix()
        except ValueError as exc:
            return {"ok": False, "error_code": "INVALID_PATH", "message": str(exc)}

    r_id = str(round_id or "").strip() or _leer_round_id_activo(raiz)

    ruta_cola.parent.mkdir(parents=True, exist_ok=True)
    lock = tomar_lock(ruta_cola, _LOCK_TIMEOUT)
    if lock is None:
        return {
            "ok": False,
            "error_code": "NOTE_LOCKED",
            "message": "No se pudo adquirir lock sobre 00_System/.flags.jsonl.",
        }
    with lock:
        existentes, rotas = _estado_actual_banderas(ruta_cola)
        flag_id = _siguiente_flag_id(existentes)
        ahora = _ahora()
        registro: Dict[str, Any] = {
            "flag_id": flag_id,
            "kind": tipo,
            "status": "open",
            "target_note": target,
            "observed": obs,
            "proposed_fix": prop,
            "trace_ref": str(trace_ref or "").strip(),
            "round_id": r_id,
            "agent": str(agent or "").strip() or "unknown",
            "created_at": ahora,
            "updated_at": ahora,
        }
        _anexar_linea_atomica(ruta_cola, json.dumps(registro, ensure_ascii=False))
    return {
        "ok": True,
        "flag": registro,
        "queue_path": "00_System/.flags.jsonl",
        "corrupt_lines_skipped": rotas,
    }


def listar_banderas(
    repo: Union[Path, Any],
    status: Optional[str] = None,
    kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Lista banderas consolidadas (solo lectura) con conteo por estado."""
    _raiz, ruta_cola = _resolver_raiz_y_cola(repo)
    if status and str(status).strip().lower() not in ESTADOS_BANDERA:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"Estado de bandera inválido {status!r}. Válidos: {list(ESTADOS_BANDERA)}",
        }
    if kind and str(kind).strip().lower() not in TIPOS_BANDERA:
        return {
            "ok": False,
            "error_code": "INVALID_VALUE",
            "message": f"Tipo de bandera inválido {kind!r}. Válidos: {list(TIPOS_BANDERA)}",
        }
    por_id, rotas = _estado_actual_banderas(ruta_cola)
    todas = sorted(por_id.values(), key=lambda x: x["flag_id"])
    resumen = {st: sum(1 for f in todas if f.get("status") == st) for st in ESTADOS_BANDERA}
    filtradas = [
        f for f in todas
        if (not status or f.get("status") == status.strip().lower())
        and (not kind or f.get("kind") == kind.strip().lower())
    ]
    return {
        "ok": True,
        "total": len(todas),
        "count": len(filtradas),
        "by_status": resumen,
        "flags": filtradas,
        "corrupt_lines_skipped": rotas,
    }


def actualizar_estado_bandera(
    repo: Union[Path, Any],
    flag_id: str,
    nuevo_estado: str,
    resolution_note: str = "",
    applied_path: str = "",
    agent: str = "",
) -> Dict[str, Any]:
    """Transiciona append-only una bandera `FLAG-NNN` (uso exclusivo del curador, SP-05)."""
    _raiz, ruta_cola = _resolver_raiz_y_cola(repo)
    fid = str(flag_id or "").strip().upper()
    est = str(nuevo_estado or "").strip().lower()
    nota_res = str(resolution_note or "").strip()
    ruta_ap = str(applied_path or "").strip().replace("\\", "/")
    hallazgos = scan_poison(nota_res, "flag:resolution_note") + scan_poison(ruta_ap, "flag:applied_path")
    bloqueantes = [f for f in hallazgos if f.severity in ("critical", "high")]
    if bloqueantes:
        return {
            "ok": False,
            "error_code": "POISON_DETECTED",
            "message": f"SP-05: resolución bloqueada por pre-vuelo anti-poison: {bloqueantes[0].detail}",
            "findings": [f.to_dict() for f in bloqueantes],
        }
    if est not in ESTADOS_BANDERA:
        return {
            "ok": False,
            "error_code": "INVALID_STATUS",
            "message": f"Estado de bandera inválido {nuevo_estado!r}. Válidos: {list(ESTADOS_BANDERA)}",
        }
    if not ruta_cola.exists():
        return {"ok": False, "error_code": "FILE_NOT_FOUND", "message": f"No existe bandera {fid} (cola vacía)."}
    lock = tomar_lock(ruta_cola, _LOCK_TIMEOUT)
    if lock is None:
        return {"ok": False, "error_code": "NOTE_LOCKED", "message": "Lock ocupado sobre .flags.jsonl."}
    with lock:
        por_id, _ = _estado_actual_banderas(ruta_cola)
        actual = por_id.get(fid)
        if not actual:
            return {"ok": False, "error_code": "FILE_NOT_FOUND", "message": f"Bandera no encontrada: {fid}"}
        prev_status = str(actual.get("status") or "open")
        permitidos = _TRANSICIONES_BANDERA.get(prev_status, frozenset())
        if est not in permitidos:
            return {
                "ok": False,
                "error_code": "INVALID_STATUS",
                "message": (
                    f"SP-05: transición ilegal {prev_status!r} -> {est!r} para {fid}. "
                    f"Permitidos: {sorted(permitidos) or ['ninguno (terminal)']}"
                ),
            }
        ahora = _ahora()
        evento = {
            "flag_id": fid,
            "event": "status_change",
            "previous_status": prev_status,
            "status": est,
            "resolution_note": str(resolution_note or "").strip(),
            "applied_path": str(applied_path or "").strip().replace("\\", "/"),
            "curated_by": str(agent or "").strip() or "curator",
            "updated_at": ahora,
        }
        _anexar_linea_atomica(ruta_cola, json.dumps(evento, ensure_ascii=False))
    return {"ok": True, "flag_id": fid, "previous_status": prev_status, "status": est, "event": evento}
