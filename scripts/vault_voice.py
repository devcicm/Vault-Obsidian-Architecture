#!/usr/bin/env python3
"""Fachada legacy de la voz del vault y auditoría AP-43.

La composición de ``vault_says`` vive en :mod:`vault.autoria.voz`. Este
adaptador conserva la CLI, los nombres importables históricos y la cobertura
del catálogo del estándar.
"""

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


# Ejecutar este fichero directamente sigue siendo compatible con checkout.
# El servicio estable no depende de esta regla ni de ``scripts/``.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vault.autoria.voz import (  # noqa: E402
    menciona as _menciona_estable,
    norms_for_tool as _norms_for_tool_estable,
    rotacion as _rotacion_estable,
    speak as _speak_estable,
)
from vault_entorno import leer as _env  # noqa: E402
from vault_io import get_vault_root  # noqa: E402
from vault_vocabulario import rango as _rango  # noqa: E402


@lru_cache(maxsize=1)
def _catalog() -> List[Dict[str, Any]]:
    """Lee el catálogo canónico sin convertir su ausencia en un fallo de tool."""
    try:
        from vault_norms_catalog import NORM_CATALOG

        return list(NORM_CATALOG)
    except Exception:
        return []


def _menciona(entrada: Any, tool: str) -> bool:
    """Compatibilidad histórica del helper de selección de normas."""
    return _menciona_estable(entrada, tool)


@lru_cache(maxsize=256)
def norms_for_tool(tool: str) -> List[Dict[str, Any]]:
    """Compatibilidad cacheada; la selección la posee el servicio estable."""
    return _norms_for_tool_estable(
        tool,
        _catalog(),
        _rango("severidad", base=0, mayor_primero=False),
    )


def _runtime_root() -> Optional[Path]:
    try:
        return get_vault_root()
    except (OSError, TypeError):
        return None


def _rotacion() -> int:
    """Seam público histórico para tests y consumidores que lo parchean."""
    return _rotacion_estable(_runtime_root())


def speak(
    tool: str,
    payload: Optional[Dict[str, Any]] = None,
    writes: Optional[Dict[str, int]] = None,
) -> Optional[Dict[str, Any]]:
    """Fachada compatible que delega la composición al servicio estable."""
    return _speak_estable(
        tool,
        payload,
        writes,
        catalog=_catalog(),
        severity_order=_rango("severidad", base=0, mayor_primero=False),
        runtime_root=_runtime_root(),
        voice_mode=_env("VAULT_VOICE"),
        rotation=_rotacion,
    )


def coverage() -> Dict[str, Any]:
    """AP-43: cobertura del catálogo del estándar, no del runtime."""
    try:
        from vault_mcp_catalog import TOOLS_CATALOG

        tools = sorted(TOOLS_CATALOG)
    except Exception:
        tools = []
    dichas = {norma["code"] for tool in tools for norma in norms_for_tool(tool)}
    todas = {norma["code"] for norma in _catalog()}
    descubiertas = sorted(
        norma["code"]
        for norma in _catalog()
        if (norma.get("cobertura_descubierta") or "").strip()
    )
    mudas = sorted(todas - dichas - set(descubiertas))
    return {
        "ok": not mudas,
        "tool": "vault_voice",
        "action": "coverage",
        "norms_total": len(todas),
        "norms_spoken": len(dichas),
        "silent": mudas,
        "uncovered_declared": descubiertas,
        "hint": (
            "Una norma que ninguna tool nombra no llega nunca al agente: "
            "declara tools_enforcing, tools_detecting o tools_del_patron; "
            "si no tiene cobertura, declara el motivo."
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="vault_voice — refuerzo de normas por interacción")
    parser.add_argument("--tool", help="Normas que gobiernan una tool")
    parser.add_argument("--coverage", action="store_true", help="Normas que ninguna tool pronuncia")
    args = parser.parse_args()
    if args.coverage:
        print(json.dumps(coverage(), ensure_ascii=False, indent=2))
        return 0
    if args.tool:
        normas = norms_for_tool(args.tool)
        print(
            json.dumps(
                {
                    "ok": True,
                    "tool": "vault_voice",
                    "target": args.tool,
                    "count": len(normas),
                    "norms": [
                        {
                            "code": norma["code"],
                            "name": norma["name"],
                            "severity": norma.get("severity"),
                            "enforcement": norma.get("enforcement"),
                            "prevention": norma.get("prevention"),
                        }
                        for norma in normas
                    ],
                    "says": speak(args.tool),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    from vault_errors import wrap_main

    sys.exit(wrap_main(main, "vault_voice"))
