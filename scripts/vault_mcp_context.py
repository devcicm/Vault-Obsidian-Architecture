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
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_io import VAULT_ROOT
from vault_lib import utcnow


SYSTEM_DIR = VAULT_ROOT / "00_System"
CONTEXT_FILE = SYSTEM_DIR / "vault_context.json"


def _read_context() -> Dict[str, Any]:
    if not CONTEXT_FILE.exists():
        return _default_context()
    try:
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return _default_context()


def _write_context(data: Dict[str, Any]) -> None:
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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
        self.data["health_score"] = score
        self._update()

    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        return self.data.get("last_operation")

    def record_operation(
        self, tool: str, path: str, ok: bool = True, details: Dict[str, Any] = None
    ) -> None:
        self.data["last_operation"] = {
            "tool": tool,
            "path": path,
            "timestamp": utcnow(),
            "ok": ok,
            "details": details or {},
        }
        self._update()

    def add_session_change(self, path: str, action: str) -> None:
        if "session" not in self.data:
            self.data["session"] = {"started_at": utcnow(), "changes": []}
        self.data["session"]["changes"].append(
            {"path": path, "action": action, "timestamp": utcnow()}
        )
        self._update()

    def get_session_changes(self) -> List[Dict[str, Any]]:
        return self.data.get("session", {}).get("changes", [])

    def get_open_issues(self) -> List[Dict[str, Any]]:
        return self.data.get("open_issues", [])

    def set_open_issues(self, issues: List[Dict[str, Any]]) -> None:
        self.data["open_issues"] = issues
        self._update()

    def get_next_actions(self) -> List[str]:
        return self.data.get("next_actions", [])

    def set_next_actions(self, actions: List[str]) -> None:
        self.data["next_actions"] = actions
        self._update()

    def get_status(self) -> Dict[str, Any]:
        return {
            "vault_root": str(VAULT_ROOT),
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
    return {"ok": True, "path": str(CONTEXT_FILE)}


def load_context() -> Dict[str, Any]:
    """Carga el contexto desde JSON."""
    context = VaultContext(persist=False)
    return context.get_status()


def clear_context() -> Dict[str, Any]:
    """Limpia el contexto (mantiene versión)."""
    data = _default_context()
    _write_context(data)
    return {"ok": True, "message": "Context cleared"}
