#!/usr/bin/env python3
"""
Vault MCP Context — Gestión de contexto persistido del vault.

Maneja:
- Estado del vault (versión, health score)
- Última operación realizada
- Cambios en la sesión actual
- Issues abiertos
- Próximas acciones recomendadas

El contexto se persiste en: VAULT_ROOT/00_System/vault_context.json
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


from vault_lib import utcnow
from vault_io import atomic_write_json, file_lock


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.consulta.repositorio import RepositorioConsulta  # noqa: E402
from vault.kernel import construir  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioConsulta(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _context_file() -> Path:
    """Resuelto al usarse: como constante de módulo se fijaba al importar (AP-49)."""
    return _system_dir() / "vault_context.json"


def _read_context() -> Dict[str, Any]:
    if not _context_file().exists():
        return _default_context()
    try:
        return json.loads(_context_file().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return _default_context()


def _write_context(data: Dict[str, Any]) -> None:
    _system_dir().mkdir(parents=True, exist_ok=True)
    atomic_write_json(_context_file(), data)


def _default_context() -> Dict[str, Any]:
    return {
        "version": "v34",
        "updated_at": utcnow(),
        "last_operation": None,
        "health_score": None,
        "session": {"started_at": utcnow(), "changes": []},
        "open_issues": [],
        "next_actions": [],
    }


class VaultContext:
    """Gestor de contexto del vault."""

    def __init__(self, persist: bool = True):
        self.persist = persist
        self.data = _read_context()

    def get_version(self) -> str:
        return self.data.get("version", "unknown")

    def get_health_score(self) -> Optional[int]:
        return self.data.get("health_score")

    def set_health_score(self, score: int) -> None:
        self._escribir_fusionando(
            lambda d: d.__setitem__("health_score", score))

    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        return self.data.get("last_operation")

    def record_operation(
        self, tool: str, path: str, ok: bool = True, details: Dict[str, Any] = None
    ) -> None:
        def _aplicar(d: Dict[str, Any]) -> None:
            d["last_operation"] = {
                "tool": tool,
                "path": path,
                "timestamp": utcnow(),
                "ok": ok,
                "details": details or {},
            }

        self._escribir_fusionando(_aplicar)

    def add_session_change(self, path: str, action: str) -> None:
        def _aplicar(d: Dict[str, Any]) -> None:
            sesion = d.setdefault(
                "session", {"started_at": utcnow(), "changes": []})
            sesion.setdefault("changes", []).append(
                {"path": path, "action": action, "timestamp": utcnow()}
            )

        self._escribir_fusionando(_aplicar)

    def get_session_changes(self) -> List[Dict[str, Any]]:
        return self.data.get("session", {}).get("changes", [])

    def get_open_issues(self) -> List[Dict[str, Any]]:
        return self.data.get("open_issues", [])

    def set_open_issues(self, issues: List[Dict[str, Any]]) -> None:
        self._escribir_fusionando(
            lambda d: d.__setitem__("open_issues", issues))

    def get_next_actions(self) -> List[str]:
        return self.data.get("next_actions", [])

    def set_next_actions(self, actions: List[str]) -> None:
        self._escribir_fusionando(
            lambda d: d.__setitem__("next_actions", actions))

    def get_status(self) -> Dict[str, Any]:
        return {
            "vault_root": str(_raiz()),
            "version": self.get_version(),
            "health_score": self.get_health_score(),
            "last_operation": self.get_last_operation(),
            "session_changes_count": len(self.get_session_changes()),
            "open_issues_count": len(self.get_open_issues()),
            "next_actions_count": len(self.get_next_actions()),
        }

    def reset_session(self) -> None:
        self.data["session"] = {"started_at": utcnow(), "changes": []}
        self._update()

    def _escribir_fusionando(self, mutador) -> None:
        """Aplica `mutador` al estado **recargado**, bajo el lock del fichero.

        Leer el snapshot propio y escribirlo entero **pisaba lo que otra
        instancia hubiera escrito mientras tanto**: dos instancias que
        anotaran un cambio cada una dejaban solo la ultima (perdida de
        actualizacion, reproducida el 2026-11-07 con dos instancias
        obsoletas y de nuevo el 2026-11-09 en la re-auditoria del vault).
        El lock sin recargar dentro no bastaria: habria que leer DENTRO del
        lock y fusionar, que es lo que hace esto. La escritura es atomica y
        la instancia se queda con el estado fusionado.
        """
        _system_dir().mkdir(parents=True, exist_ok=True)
        lock = file_lock(_context_file(), timeout=10.0)
        if lock is None:
            raise TimeoutError("el contexto del vault esta bloqueado")
        with lock:
            actual = _read_context()
            mutador(actual)
            actual["updated_at"] = utcnow()
            atomic_write_json(_context_file(), actual)
            self.data = actual

    def _update(self) -> None:
        self.data["updated_at"] = utcnow()
        if self.persist:
            _write_context(self.data)


def get_context(persist: bool = True) -> VaultContext:
    """Factory function para obtener el contexto."""
    return VaultContext(persist=persist)


def save_context() -> Dict[str, Any]:
    """Fuerza el guardado del contexto."""
    context = VaultContext(persist=True)
    return {"ok": True, "path": str(_context_file())}


def load_context() -> Dict[str, Any]:
    """Carga el contexto desde JSON."""
    context = VaultContext(persist=False)
    return context.get_status()


def clear_context() -> Dict[str, Any]:
    """Limpia el contexto (mantiene versión)."""
    data = _default_context()
    _write_context(data)
    return {"ok": True, "message": "Context cleared"}
