#!/usr/bin/env python3
"""
vault_model_profile.py — Perfil de modelo LLM como contexto adaptativo.

Resuelve el problema de que vault_context_pack use un budget hardcodeado
(4000 tokens) sin conocer la ventana de contexto del modelo que conecta.

Auto-detecta el perfil desde VAULT_MODEL_PROFILE (env var propagada por el
servidor MCP) y expone el budget correcto para que vault_context_pack lo use.

Datos gobernados en 17_Preferences/:
    model_profiles.json      — registry de perfiles predefinidos
    model_profile.active     — puntero al perfil activo

Usage:
    python vault_model_profile.py --list
    python vault_model_profile.py --active
    python vault_model_profile.py --set claude
    python vault_model_profile.py --auto "claude-desktop"
    python vault_model_profile.py --budget        # solo imprime budget (consumo interno)
    python vault_model_profile.py --window        # solo imprime context_window
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vault_errors import emit_error, wrap_main
from vault_io import atomic_write_text, assert_within_vault

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.consulta.repositorio import RepositorioConsulta
from vault.kernel import construir
from vault_entorno import leer


FLOOR_BUDGET = 2000
DEFAULT_PROFILE = "claude"

MODEL_MAPPING: Dict[str, str] = {
    "claude-desktop": "claude",
    "claude": "claude",
    "cursor": "cursor",
    "openai-gpt": "gpt-4o",
    "Codex": "gpt-4o",
    "gemini-cli": "gemini",
    "deepseek-chat": "deepseek",
}


def _raiz() -> Path:
    return _repo().raiz


def _repo(root=None) -> RepositorioConsulta:
    return RepositorioConsulta(construir(root))


def _preferences_dir() -> Path:
    return _repo().dir_preferencias


def _profiles_json_path() -> Path:
    return _preferences_dir() / "model_profiles.json"


def _active_path() -> Path:
    return _preferences_dir() / "model_profile.active"


def _load_registry() -> Dict[str, Dict[str, Any]]:
    path = _profiles_json_path()
    if not path.exists():
        return _default_registry()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_registry()


def _default_registry() -> Dict[str, Dict[str, Any]]:
    return {
        "claude":   {"context_window": 200000, "budget": 15000, "supports_mcp": True},
        "cursor":   {"context_window": 200000, "budget": 15000, "supports_mcp": True},
        "gpt-4o":   {"context_window": 128000, "budget": 8000,  "supports_mcp": True},
        "gemini":   {"context_window": 32000,  "budget": 4000,  "supports_mcp": True},
        "deepseek": {"context_window": 64000,  "budget": 6000,  "supports_mcp": True},
    }


def _read_active_profile() -> str:
    path = _active_path()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return DEFAULT_PROFILE


def _write_active_profile(profile_id: str) -> None:
    path = _active_path()
    assert_within_vault(path, _raiz())
    atomic_write_text(path, profile_id.strip() + "\n")


def _resolve_profile(
    explicit: Optional[str] = None,
    from_env: Optional[str] = None,
    from_auto: Optional[str] = None,
) -> tuple[str, str]:
    """Resuelve el profile_id y la fuente.

    Prioridad: explicit > from_env > from_auto > DEFAULT

    Returns: (profile_id, source)
    source: 'active' | 'env' | 'auto' | 'default'
    """
    if explicit:
        return explicit, "active"
    if from_env:
        return from_env, "env"
    if from_auto:
        mapped = MODEL_MAPPING.get(from_auto)
        if mapped:
            return mapped, "auto"
        return DEFAULT_PROFILE, "default"
    active = _read_active_profile()
    registry = _load_registry()
    if active in registry:
        return active, "active"
    return DEFAULT_PROFILE, "default"


def vault_model_profile_resolve(
    explicit: Optional[str] = None,
    from_env: Optional[str] = None,
    from_auto: Optional[str] = None,
) -> Dict[str, Any]:
    registry = _load_registry()
    profile_id, source = _resolve_profile(explicit, from_env, from_auto)

    if profile_id not in registry:
        result = {
            "ok": True,
            "profile_id": profile_id,
            "context_window": FLOOR_BUDGET,
            "budget": FLOOR_BUDGET,
            "supports_mcp": False,
            "source": source,
            "warning": f"Perfil '{profile_id}' no encontrado. Budget ajustado a floor ({FLOOR_BUDGET}).",
        }
        return result

    profile = registry[profile_id]
    return {
        "ok": True,
        "profile_id": profile_id,
        "context_window": profile["context_window"],
        "budget": profile["budget"],
        "supports_mcp": profile.get("supports_mcp", True),
        "source": source,
    }


def vault_model_profile_list() -> Dict[str, Any]:
    registry = _load_registry()
    active = _read_active_profile()
    profiles = []
    for pid, prof in registry.items():
        profiles.append({
            "id": pid,
            "context_window": prof["context_window"],
            "budget": prof["budget"],
            "supports_mcp": prof.get("supports_mcp", True),
            "active": pid == active,
        })
    return {
        "ok": True,
        "profiles": sorted(profiles, key=lambda p: p["id"]),
        "active": active,
    }


def vault_model_profile_set(profile_id: str) -> Dict[str, Any]:
    registry = _load_registry()
    if profile_id not in registry:
        return {
            "ok": False,
            "error_code": "MODEL_PROFILE_UNKNOWN",
            "error": f"Perfil '{profile_id}' no existe. Disponibles: {sorted(registry.keys())}",
        }
    _write_active_profile(profile_id)
    return vault_model_profile_resolve(explicit=profile_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_model_profile — Perfil de modelo LLM para contexto adaptativo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_model_profile.py --list
  python vault_model_profile.py --active
  python vault_model_profile.py --set claude
  python vault_model_profile.py --auto "claude-desktop"   # auto-detecta
  python vault_model_profile.py --budget                   # solo el budget (consumo interno)
  python vault_model_profile.py --window                   # solo context_window

El servidor MCP propaga VAULT_MODEL_PROFILE automaticamente al detectar
el cliente (clientInfo.name en el handshake initialize).
""",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list",   action="store_true", help="Lista perfiles disponibles")
    mode.add_argument("--active", action="store_true", help="Devuelve el perfil activo")
    mode.add_argument("--set",    metavar="ID",       help="Activa el perfil dado")
    mode.add_argument("--auto",   metavar="NAME",     help="Auto-detecta desde nombre del cliente MCP")
    mode.add_argument("--budget", action="store_true", help="Solo imprime el budget (consumo interno)")
    mode.add_argument("--window", action="store_true", help="Solo imprime context_window")

    args = parser.parse_args()

    env_profile = leer("VAULT_MODEL_PROFILE")

    if args.list:
        result = vault_model_profile_list()
    elif args.active:
        result = vault_model_profile_resolve(from_env=env_profile)
    elif args.set:
        result = vault_model_profile_set(args.set)
    elif args.auto:
        result = vault_model_profile_resolve(from_auto=args.auto)
    elif args.budget:
        result = vault_model_profile_resolve(from_env=env_profile)
        print(result["budget"])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    elif args.window:
        result = vault_model_profile_resolve(from_env=env_profile)
        print(result["context_window"])
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_model_profile"))
