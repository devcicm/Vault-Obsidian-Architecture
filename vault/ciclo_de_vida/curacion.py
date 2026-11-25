"""Orquestador batch de curación de la Fábrica de Conocimiento (SPEC-04, SPEC-02, SP-05).

Vive en `vault/ciclo_de_vida/` y se expone mediante los subcomandos de
`vault_propagate` (`--curate-plan`, `--curate-apply`, `--resolve-flag`,
`--mark-contradicts`) bajo la Opción A (cero tools nuevas, catálogo estable).
Consume `vault.kernel.banderas` y el puerto `BitacoraCambios` (`vault.runtime`)
para anexar y registrar `curated` sin abrir cruces hacia otros contextos.
Todo en Markdown/JSON/JSONL + Git.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from vault_io import assert_within_vault, atomic_write_text, tomar_lock

from ..kernel.banderas import actualizar_estado_bandera, listar_banderas
from ..kernel.contenido import CARPETA_FUENTES
from ..kernel.frontmatter_escritura import Frontmatter
from ..kernel.frontmatter_parsing import parse_frontmatter_with_body, separar_frontmatter
from ..kernel.safety import scan_poison
from ..runtime import bitacora_de_cambios

_LOCK_TIMEOUT = 10.0


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _leer_cola_propagacion(raiz: Path, cola_propagacion: Optional[Path] = None) -> List[Dict[str, Any]]:
    cola = cola_propagacion if cola_propagacion is not None else (raiz / "00_System" / "propagation-queue.json")
    if not cola.exists():
        return []
    try:
        datos = json.loads(cola.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and isinstance(datos.get("pending"), list):
            return datos["pending"]
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return []


def _fuentes_raw_recientes(raiz: Path, limite: int = 15) -> List[str]:
    carpeta = raiz / CARPETA_FUENTES
    if not carpeta.is_dir():
        return []
    archivos = sorted(
        (p for p in carpeta.rglob("*.md") if p.name.lower() != "index.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [p.relative_to(raiz).as_posix() for p in archivos[:limite]]


def planificar_curacion(
    raiz: Path,
    cola_propagacion: Optional[Path] = None,
) -> Dict[str, Any]:
    """Genera un plan de curación batch sin efectos secundarios (`dry-run`, SP-05)."""
    res_flags = listar_banderas(raiz)
    if not res_flags.get("ok"):
        return res_flags

    banderas_activas = [
        f for f in res_flags["flags"]
        if f.get("status") in ("open", "triaged")
    ]
    pendientes_prop = _leer_cola_propagacion(raiz, cola_propagacion=cola_propagacion)
    fuentes_raw = _fuentes_raw_recientes(raiz)

    por_nota: Dict[str, Dict[str, Any]] = {}
    sin_destino: List[Dict[str, Any]] = []
    for f in banderas_activas:
        destino = str(f.get("target_note") or "").strip()
        if not destino:
            sin_destino.append(f)
            continue
        grupo = por_nota.setdefault(destino, {
            "target_note": destino,
            "exists": (raiz / destino).is_file(),
            "flags": [],
            "propagation_entries": [],
        })
        grupo["flags"].append({
            "flag_id": f["flag_id"],
            "kind": f["kind"],
            "status": f["status"],
            "observed": f["observed"],
            "proposed_fix": f.get("proposed_fix", ""),
            "trace_ref": f.get("trace_ref", ""),
            "round_id": f.get("round_id", ""),
        })

    for item in pendientes_prop:
        destino = str(item.get("path") or "").strip()
        if not destino:
            continue
        grupo = por_nota.setdefault(destino, {
            "target_note": destino,
            "exists": (raiz / destino).is_file(),
            "flags": [],
            "propagation_entries": [],
        })
        grupo["propagation_entries"].append(item)

    conflict_warnings: List[Dict[str, Any]] = []
    for destino, grupo in sorted(por_nota.items()):
        propuestas = {
            fl["proposed_fix"].strip()
            for fl in grupo["flags"]
            if fl.get("proposed_fix", "").strip()
        }
        if len(propuestas) > 1:
            conflict_warnings.append({
                "target_note": destino,
                "reason": "Múltiples banderas proponen ajustes distintos sobre la misma nota; revisar posible contradicción (PAT-7).",
                "flag_ids": [fl["flag_id"] for fl in grupo["flags"]],
            })

    return {
        "ok": True,
        "norm": "SP-05",
        "dry_run": True,
        "summary": {
            "open_or_triaged_flags": len(banderas_activas),
            "flags_without_target": len(sin_destino),
            "propagation_pending": len(pendientes_prop),
            "recent_raw_sources": len(fuentes_raw),
            "target_notes_grouped": len(por_nota),
            "conflict_warnings": len(conflict_warnings),
        },
        "groups": [por_nota[k] for k in sorted(por_nota)],
        "unassigned_flags": sin_destino,
        "recent_raw_sources": fuentes_raw,
        "conflict_warnings": conflict_warnings,
    }


def _estampar_traza_curacion(
    full_path: Path,
    flag_ids: Sequence[str],
    trace_refs: Sequence[str],
    atomic_write_text_fn,
) -> bool:
    """Estampa `source_flags` y `trace_ref` en el frontmatter de la nota curada."""
    lock = tomar_lock(full_path, _LOCK_TIMEOUT)
    if lock is None:
        return False
    with lock:
        texto = full_path.read_text(encoding="utf-8", errors="replace")
        fm_dict, _ = parse_frontmatter_with_body(texto)
        bloque, cuerpo = separar_frontmatter(texto)
        if bloque is None:
            return False
        prev_flags = fm_dict.get("source_flags") if isinstance(fm_dict, dict) else None
        combinadas: List[str] = []
        if isinstance(prev_flags, list):
            for x in prev_flags:
                s = str(x).strip()
                if s and s not in combinadas:
                    combinadas.append(s)
        for fid in flag_ids:
            if fid not in combinadas:
                combinadas.append(fid)
        editor = Frontmatter.editar(bloque).set("source_flags", combinadas)
        trazas = [t for t in trace_refs if t]
        if trazas:
            editor = editor.set("trace_ref", trazas[-1], texto=True)
        editor = editor.set("updatedAt", _ahora(), texto=True)
        atomic_write_text_fn(full_path, editor.render() + "\n" + cuerpo)
        return True


def aplicar_curacion(
    raiz: Path,
    flag_ids: Optional[Sequence[str]] = None,
    agent: str = "curator",
) -> Dict[str, Any]:
    """Aplica en lote banderas aprobadas por el puerto `BitacoraCambios` (SP-05)."""
    res_flags = listar_banderas(raiz)
    if not res_flags.get("ok"):
        return res_flags

    bitacora = bitacora_de_cambios()
    if bitacora is None:
        return {
            "ok": False,
            "error_code": "PRODUCTORES_NO_DISPONIBLES",
            "message": "SP-05: nadie atiende el puerto `bitacora_cambios`; no se aplicó curación.",
        }

    filtro_ids = {str(x).strip().upper() for x in (flag_ids or []) if str(x).strip()}
    candidatas = [
        f for f in res_flags["flags"]
        if f.get("status") in ("open", "triaged")
        and (not filtro_ids or f["flag_id"] in filtro_ids)
    ]

    aplicadas: List[Dict[str, Any]] = []
    omitidas: List[Dict[str, Any]] = []
    por_nota_trazas: Dict[str, Dict[str, List[str]]] = {}

    for flag in candidatas:
        fid = flag["flag_id"]
        target = str(flag.get("target_note") or "").strip()
        propuesta = str(flag.get("proposed_fix") or "").strip()
        if not target:
            omitidas.append({"flag_id": fid, "reason": "sin target_note asignado"})
            continue
        if not propuesta:
            omitidas.append({"flag_id": fid, "target_note": target, "reason": "sin proposed_fix para aplicar"})
            continue
        try:
            full_target = assert_within_vault(raiz / target, raiz)
        except ValueError as exc:
            omitidas.append({"flag_id": fid, "target_note": target, "reason": str(exc)})
            continue
        if not full_target.is_file():
            omitidas.append({"flag_id": fid, "target_note": target, "reason": "target_note no existe en disco"})
            continue

        # SP-05: re-verificación anti-poison obligatoria antes de curar.
        poison = [f for f in scan_poison(propuesta, f"curate:{fid}") if f.severity in ("critical", "high")]
        if poison:
            omitidas.append({
                "flag_id": fid,
                "target_note": target,
                "reason": f"POISON_DETECTED: {poison[0].code}",
            })
            continue

        bloque = (
            f"- **[{fid} · {flag['kind']}]** {propuesta}"
            + (f" _(observado: {flag['observed']})_" if flag.get("observed") else "")
            + (f" · traza: `{flag['trace_ref']}`" if flag.get("trace_ref") else "")
        )
        res_app = bitacora.anexar(
            target, bloque, "## Actualizaciones curadas (SP-05)", True,
        )
        if not isinstance(res_app, dict) or not res_app.get("ok"):
            omitidas.append({
                "flag_id": fid,
                "target_note": target,
                "reason": (res_app.get("error_code") or res_app.get("message")) if isinstance(res_app, dict) else "append_failed",
            })
            continue

        traza_nota = por_nota_trazas.setdefault(target, {"flags": [], "traces": []})
        traza_nota["flags"].append(fid)
        if flag.get("trace_ref"):
            traza_nota["traces"].append(str(flag["trace_ref"]))

        actualizar_estado_bandera(
            raiz,
            fid,
            "applied",
            resolution_note=f"Curada en lote sobre {target}",
            applied_path=target,
            agent=agent,
        )
        aplicadas.append({
            "flag_id": fid,
            "target_note": target,
            "kind": flag["kind"],
            "trace_ref": flag.get("trace_ref", ""),
        })

    for target, datos_traza in por_nota_trazas.items():
        _estampar_traza_curacion(
            raiz / target, datos_traza["flags"], datos_traza["traces"], atomic_write_text
        )

    report_rel: Optional[str] = None
    change_log_entry: Optional[Dict[str, Any]] = None
    if aplicadas:
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        corto = uuid.uuid4().hex[:6]
        report_rel = f"19_Audits/curation/curation-{fecha}-{corto}.md"
        report_path = assert_within_vault(raiz / report_rel, raiz)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        ahora = _ahora()
        # AP-46 / AP-57: frontmatter generado siempre por el escritor canónico `Frontmatter`.
        fm_rep = (
            Frontmatter()
            .set("id", str(uuid.uuid4()))
            .set("title", f"Reporte de curación {fecha} ({corto})", texto=True)
            .set("type", "audit")
            .set("status", "verified")
            .set("document_shape", "reporte")
            .set("createdAt", ahora)
            .set("updatedAt", ahora)
            .set("tags", ["audit", "curation", "sp-05"])
            .set("norm_refs", ["SP-05", "AP-74"])
            .set("cia_integrity", "high")
            .set("cia_availability", "medium")
            .set("cia_sensitivity", "internal")
            .set("agent", agent, texto=True)
        )
        cuerpo_rep = [
            f"# Reporte de curación batch ({fecha} · {corto})",
            "",
            f"- **Norma:** `SP-05` · **Curador:** `{agent}` · **Aplicadas:** {len(aplicadas)} · **Omitidas:** {len(omitidas)}",
            "",
            "## Banderas aplicadas",
            "",
        ]
        for a in aplicadas:
            cuerpo_rep.append(f"- `{a['flag_id']}` ({a['kind']}) → [[{Path(a['target_note']).stem}]] (`{a['target_note']}`)")
        if omitidas:
            cuerpo_rep += ["", "## Banderas omitidas", ""]
            for o in omitidas:
                cuerpo_rep.append(f"- `{o['flag_id']}`: {o['reason']}")
        atomic_write_text(report_path, fm_rep.render() + "\n\n" + "\n".join(cuerpo_rep) + "\n")

        res_log = bitacora.anotar(
            "curated",
            report_rel,
            f"SP-05 curación batch: {', '.join(a['flag_id'] for a in aplicadas)}",
            agent,
        )
        if isinstance(res_log, dict) and res_log.get("ok"):
            change_log_entry = res_log.get("entry")

    return {
        "ok": True,
        "norm": "SP-05",
        "dry_run": False,
        "applied_count": len(aplicadas),
        "skipped_count": len(omitidas),
        "applied": aplicadas,
        "skipped": omitidas,
        "report_path": report_rel,
        "change_log": change_log_entry,
    }


def marcar_contradiccion(
    raiz: Path,
    nota_a: str,
    nota_b: str,
    reason: str = "",
    agent: str = "curator",
) -> Dict[str, Any]:
    """Declara desacuerdo bilateral `contradicts:` (`PAT-7`) sin pisar cuerpos (SPEC-02/04)."""
    motivo_limpio = str(reason or "").strip()
    if motivo_limpio:
        poison = [f for f in scan_poison(motivo_limpio, "contradicts:reason") if f.severity in ("critical", "high")]
        if poison:
            return {
                "ok": False,
                "error_code": "POISON_DETECTED",
                "message": f"PAT-7: motivo de contradicción bloqueado por anti-poison: {poison[0].detail}",
                "findings": [f.to_dict() for f in poison],
            }
    try:
        path_a = assert_within_vault(raiz / nota_a, raiz)
        path_b = assert_within_vault(raiz / nota_b, raiz)
    except ValueError as exc:
        return {"ok": False, "error_code": "INVALID_PATH", "message": str(exc)}
    if not path_a.is_file():
        return {"ok": False, "error_code": "FILE_NOT_FOUND", "message": f"No existe {nota_a}"}
    if not path_b.is_file():
        return {"ok": False, "error_code": "FILE_NOT_FOUND", "message": f"No existe {nota_b}"}

    rel_a = path_a.resolve().relative_to(raiz.resolve()).as_posix()
    rel_b = path_b.resolve().relative_to(raiz.resolve()).as_posix()
    if rel_a == rel_b:
        return {"ok": False, "error_code": "INVALID_INPUT", "message": "Una nota no puede contradecirse a sí misma."}

    def _enlazar(target_path: Path, contraparte_stem: str) -> bool:
        lock = tomar_lock(target_path, _LOCK_TIMEOUT)
        if lock is None:
            return False
        with lock:
            texto = target_path.read_text(encoding="utf-8", errors="replace")
            fm_dict, _ = parse_frontmatter_with_body(texto)
            bloque, cuerpo = separar_frontmatter(texto)
            if bloque is None:
                return False
            enlace = f"[[{contraparte_stem}]]"
            prev = fm_dict.get("contradicts") if isinstance(fm_dict, dict) else None
            lista: List[str] = []
            if isinstance(prev, list):
                lista = [str(x).strip() for x in prev if str(x).strip()]
            elif isinstance(prev, str) and prev.strip():
                lista = [prev.strip()]
            if enlace not in lista:
                lista.append(enlace)
            editor = Frontmatter.editar(bloque).set("contradicts", lista).set("updatedAt", _ahora(), texto=True)
            atomic_write_text(target_path, editor.render() + "\n" + cuerpo)
            return True

    ok_a = _enlazar(path_a, path_b.stem)
    ok_b = _enlazar(path_b, path_a.stem)
    if not (ok_a and ok_b):
        return {
            "ok": False,
            "error_code": "NOTE_LOCKED",
            "message": "No se pudo actualizar frontmatter `contradicts:` en ambas notas.",
        }

    bitacora = bitacora_de_cambios()
    if bitacora is not None:
        bitacora.anotar(
            "curated",
            rel_a,
            f"PAT-7 contradicción declarada con {rel_b}" + (f": {reason}" if reason else ""),
            agent,
        )
    return {
        "ok": True,
        "pattern": "PAT-7",
        "note_a": rel_a,
        "note_b": rel_b,
        "reason": reason,
    }
