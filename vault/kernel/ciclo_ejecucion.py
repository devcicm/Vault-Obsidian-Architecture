"""Primitivas durables de ejecución, transacciones ACID/Saga y patrón Dispose/RAII (SPEC-05 Etapa 2).

Hoja pura del núcleo (`vault.kernel`, 0 dependencias externas, 0 BD, 0 embeddings)
para blindar los procesos internos del toolkit bajo Perfil A:

- **Pilar 5 (`GestorDispose`, AP-82):** gestión determinista de recursos (RAII /
  `ExitStack` con `dispose()` idempotente en orden LIFO sin enmascarar la
  excepción original y soporte de `Graceful Shutdown` ante `SIGTERM`/`SIGINT`).
- **P1 (`SagaPreSha`, AP-83):** captura `HEAD` pre-lote en el repo Git del vault
  y ejecuta compensación determinista ante fallo parcial.
- **P2 (`CheckpointLog`, AP-83):** registro append-only JSONL en `00_System/`
  con clave de idempotencia `(run_id, step_id)` y `replay()` determinista.
- **P4 (`LeaseHeartbeat`, AP-82):** concesiones temporales renovables por latido
  para detectar workers caídos y liberar bloqueos huérfanos.
"""

from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import procesos_git

__all__ = [
    "CheckpointLog",
    "GestorDispose",
    "LeaseHeartbeat",
    "SagaPreSha",
    "instalar_cierre_ordenado",
]


class GestorDispose:
    """Patrón Dispose / RAII determinista con liberación LIFO e idempotente (AP-82).

    Asegura que todo recurso registrado (locks, descriptores, temporales, timers,
    subprocesos) se libere exactamente una vez en orden inverso a la adquisición,
    incluso si ocurren excepciones, sin ocultar el error raíz (AP-51).
    """

    def __init__(self) -> None:
        self._cleanups: List[Tuple[str, Callable[[], Any]]] = []
        self._disposed: bool = False
        self._dispose_errors: List[Dict[str, str]] = []

    @property
    def disposed(self) -> bool:
        return self._disposed

    @property
    def dispose_errors(self) -> List[Dict[str, str]]:
        return list(self._dispose_errors)

    def register(self, name: str, cleanup: Callable[[], Any]) -> None:
        if self._disposed:
            raise RuntimeError(f"AP-82: no se puede registrar '{name}' en un GestorDispose ya liberado")
        self._cleanups.append((str(name), cleanup))

    def dispose(self) -> List[Dict[str, str]]:
        """Ejecuta los cleanups en orden LIFO de forma idempotente."""
        if self._disposed:
            return list(self._dispose_errors)
        self._disposed = True
        while self._cleanups:
            nombre, fn = self._cleanups.pop()
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 — AP-51: se registra sin silenciar ni ocultar causa raíz
                self._dispose_errors.append({
                    "resource": nombre,
                    "error": f"{type(exc).__name__}: {exc}",
                })
        return list(self._dispose_errors)

    def __enter__(self) -> "GestorDispose":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.dispose()
        # Nunca suprimir la excepción original del bloque `with`
        return False


def instalar_cierre_ordenado(
    gestor: GestorDispose,
    *,
    on_signal: Optional[Callable[[int], None]] = None,
) -> Dict[int, Any]:
    """Instala manejadores de `SIGINT`/`SIGTERM` que disparan `gestor.dispose()` (AP-82)."""
    previos: Dict[int, Any] = {}

    def _handler(signum: int, _frame: Any) -> None:
        gestor.dispose()
        if on_signal is not None:
            on_signal(signum)

    for nombre_sig in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, nombre_sig, None)
        if sig is None:
            continue
        try:
            previos[int(sig)] = signal.signal(sig, _handler)
        except (ValueError, OSError):
            # Hilo secundario o plataforma sin soporte para esa señal
            continue
    return previos


class CheckpointLog:
    """Bitácora append-only de checkpoints con idempotencia y replay determinista (AP-83).

    Persiste en JSONL estrictamente dentro del vault (AP-36). Un `run_id`
    interrumpido consulta `completed_steps(run_id)` para omitir pasos ya
    confirmados sin duplicar efectos secundarios.
    """

    def __init__(self, vault_root: Path, rel_path: str = "00_System/.checkpoints.jsonl") -> None:
        self._root = Path(vault_root).resolve()
        destino = (self._root / rel_path).resolve()
        if not destino.is_relative_to(self._root):
            raise ValueError(f"AP-36: checkpoint fuera del vault: {destino}")
        self._path = destino

    @property
    def path(self) -> Path:
        return self._path

    def save_checkpoint(
        self,
        run_id: str,
        step_id: str,
        *,
        status: str = "completed",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": str(run_id),
            "step_id": str(step_id),
            "status": str(status),
            "payload": payload or {},
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def load_checkpoints(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out: List[Dict[str, Any]] = []
        for linea in self._path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                fila = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if run_id is None or fila.get("run_id") == run_id:
                out.append(fila)
        return out

    def completed_steps(self, run_id: str) -> List[str]:
        """Devuelve en orden los `step_id` ya confirmados para replay idempotente."""
        vistos: List[str] = []
        for fila in self.load_checkpoints(run_id):
            sid = str(fila.get("step_id", ""))
            if fila.get("status") == "completed" and sid and sid not in vistos:
                vistos.append(sid)
        return vistos

    def replay_pending(self, run_id: str, planned_steps: List[str]) -> List[str]:
        """Filtra los pasos pendientes omitiendo los ya confirmados en checkpoint."""
        hechos = set(self.completed_steps(run_id))
        return [s for s in planned_steps if s not in hechos]


class SagaPreSha:
    """Compensación determinista para mutaciones en lote sin pérdida de datos (AP-83, H-04).

    Antes de iniciar un lote multi-nota sobre un vault:
    1. Captura `HEAD` (`pre_sha`) si el vault tiene Git.
    2. Registra el inventario de archivos existentes antes del lote y toma una
       instantánea en bytes de cualquier archivo que ya tuviera modificaciones
       sin commit, para **nunca destruir trabajo previo del usuario**.
    3. Al compensar (`compensate()`), restaura archivos previamente sucios a su
       instantánea exacta en bytes, restaura archivos limpios desde `pre_sha` en
       bytes (sin corromper binarios) y retira archivos nuevos creados durante el
       lote hacia `.history/saga-rolled-back/<run_id>/` (sin borrado destructivo).
    """

    _OMITIR_ESCANEO = frozenset({".git", ".locks", ".history", "__pycache__"})

    def __init__(self, vault_root: Path, run_id: str = "batch") -> None:
        self._root = Path(vault_root).resolve()
        self._run_id = str(run_id)
        self._pre_sha: Optional[str] = None
        self._archivos_previos: Set[str] = set()
        self._snapshots_sucios: Dict[str, bytes] = {}
        self._iniciada = False

    @property
    def pre_sha(self) -> Optional[str]:
        return self._pre_sha

    def _listar_archivos(self) -> Set[str]:
        encontrados: Set[str] = set()
        for actual, dirs, archivos in os.walk(self._root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in self._OMITIR_ESCANEO]
            base = Path(actual)
            for nombre in archivos:
                ruta = base / nombre
                if ruta.is_symlink():
                    continue
                encontrados.add(ruta.relative_to(self._root).as_posix())
        return encontrados

    def begin(self) -> Optional[str]:
        """Captura `HEAD`, inventario previo y bytes exactos de archivos ya modificados."""
        self._archivos_previos = self._listar_archivos()
        self._snapshots_sucios = {}
        r = procesos_git.ejecutar_git(
            self._root, ["rev-parse", "HEAD"], capture_output=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            self._pre_sha = r.stdout.strip()
            r_dirty = procesos_git.ejecutar_git(
                self._root, ["diff", "--name-only", self._pre_sha],
                capture_output=True, timeout=15,
            )
            if r_dirty.returncode == 0:
                for rel in (ln.strip() for ln in r_dirty.stdout.splitlines() if ln.strip()):
                    ruta = (self._root / rel).resolve()
                    if ruta.is_relative_to(self._root) and ruta.is_file():
                        self._snapshots_sucios[rel] = ruta.read_bytes()
        self._iniciada = True
        return self._pre_sha

    def compensate(
        self,
        files: Optional[List[str]] = None,
        *,
        checkpoints: Optional[CheckpointLog] = None,
    ) -> Dict[str, Any]:
        """Revierte únicamente los efectos del lote sin destruir trabajo previo ni binarios (AP-68, H-04)."""
        if not self._iniciada or not self._pre_sha:
            return {"ok": False, "compensated": False, "reason": "no_pre_sha"}

        # 1. Determinar archivos modificados en Git + archivos nuevos creados durante el lote.
        actuales = self._listar_archivos()
        nuevos_en_lote = sorted(actuales - self._archivos_previos)

        objetivos_mod = list(files or [])
        if not objetivos_mod:
            r_diff = procesos_git.ejecutar_git(
                self._root, ["diff", "--name-only", self._pre_sha],
                capture_output=True, timeout=15,
            )
            if r_diff.returncode == 0:
                objetivos_mod = [ln.strip() for ln in r_diff.stdout.splitlines() if ln.strip()]

        restaurados: List[str] = []
        preservados_sucios: List[str] = []
        retirados_nuevos: List[str] = []
        errores: List[str] = []

        for rel in objetivos_mod:
            destino = (self._root / rel).resolve()
            if not destino.is_relative_to(self._root):
                raise ValueError(f"AP-36: ruta fuera del vault en compensacion: {rel}")
            if rel in self._snapshots_sucios:
                destino.parent.mkdir(parents=True, exist_ok=True)
                tmp = destino.with_name(f".{destino.name}.saga.tmp")
                tmp.write_bytes(self._snapshots_sucios[rel])
                tmp.replace(destino)
                restaurados.append(rel)
                preservados_sucios.append(rel)
                continue
            r_show = procesos_git.ejecutar_git(
                self._root, ["show", f"{self._pre_sha}:{rel}"],
                capture_output=True, binario=True, timeout=15,
            )
            if r_show.returncode != 0:
                errores.append(rel)
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            tmp = destino.with_name(f".{destino.name}.saga.tmp")
            datos = r_show.stdout if isinstance(r_show.stdout, (bytes, bytearray)) else str(r_show.stdout).encode("utf-8")
            tmp.write_bytes(datos)
            tmp.replace(destino)
            restaurados.append(rel)

        # 2. Retirar a cuarentena reversible archivos nuevos creados durante el lote
        cuarentena = self._root / ".history" / "saga-rolled-back" / self._run_id
        candidatos_nuevos = (
            [f for f in files if f in nuevos_en_lote] if files is not None else nuevos_en_lote
        )
        for rel in candidatos_nuevos:
            origen = (self._root / rel).resolve()
            if not origen.is_relative_to(self._root) or not origen.is_file():
                continue
            destino_q = cuarentena / rel
            destino_q.parent.mkdir(parents=True, exist_ok=True)
            origen.replace(destino_q)
            retirados_nuevos.append(rel)

        ok = not errores
        if checkpoints is not None:
            checkpoints.save_checkpoint(
                self._run_id,
                "saga_compensate",
                status="completed" if ok else "failed",
                payload={
                    "pre_sha": self._pre_sha,
                    "restored": restaurados,
                    "preserved_preexisting_dirty": preservados_sucios,
                    "quarantined_new": retirados_nuevos,
                    "errors": errores,
                },
            )
        return {
            "ok": ok,
            "compensated": ok,
            "pre_sha": self._pre_sha,
            "restored": restaurados,
            "preserved_preexisting_dirty": preservados_sucios,
            "quarantined_new": retirados_nuevos,
            "errors": errores,
        }


class LeaseHeartbeat:
    """Concesión temporal renovable por latido para operaciones largas (AP-82)."""

    def __init__(
        self,
        owner: str,
        *,
        ttl_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds debe ser > 0")
        self._owner = str(owner)
        self._ttl = float(ttl_seconds)
        self._clock = clock
        self._expires_at: Optional[float] = None
        self._heartbeats: int = 0

    def acquire_lease(self) -> float:
        self._expires_at = self._clock() + self._ttl
        self._heartbeats = 1
        return self._expires_at

    def renew_lease(self) -> float:
        if self._expires_at is None:
            raise RuntimeError("No se puede renovar un lease no adquirido")
        self._expires_at = self._clock() + self._ttl
        self._heartbeats += 1
        return self._expires_at

    def release_lease(self) -> None:
        self._expires_at = None

    def is_expired(self) -> bool:
        if self._expires_at is None:
            return True
        return self._clock() > self._expires_at

    def snapshot(self) -> Dict[str, Any]:
        rem = 0.0 if self._expires_at is None else max(0.0, self._expires_at - self._clock())
        return {
            "owner": self._owner,
            "ttl_seconds": self._ttl,
            "heartbeats": self._heartbeats,
            "expired": self.is_expired(),
            "remaining_seconds": round(rem, 3),
        }
