#!/usr/bin/env python3
"""
vault_manifest.py — Genera manifiesto de tools + bootstraps/actualiza tool-spec.json.

Modos:
  normal        Escribe 00_System/tools-manifest.json desde tool-spec.json (spec-driven).
                Si tool-spec.json no existe, usa datos hardcodeados como fallback.
  --bootstrap   Genera <vault>/00_System/tool-spec.json combinando datos hardcodeados +
                introspección. Ejecutar una sola vez (o al agregar datos nuevos al spec).
                Desde v39 el contrato vive DENTRO del vault (AP-36); la ruta se resuelve
                con vault_io.tool_spec_path(), nunca desde __file__.
  --validate    Delega a vault_spec_validate.py — muestra drift entre spec e implementación.
  --check       Muestra el manifiesto sin escribir.

Flujo spec-driven:
  1. python vault_manifest.py --bootstrap     ← genera tool-spec.json inicial
  2. Editar tool-spec.json antes de cada nueva tool
  3. Implementar el script
  4. python vault_manifest.py --validate      ← verificar conformidad
  5. python vault_manifest.py                 ← actualizar tools-manifest.json

Usage:
    python vault_manifest.py                     # genera tools-manifest.json desde spec
    python vault_manifest.py --bootstrap         # (re)genera tool-spec.json
    python vault_manifest.py --validate          # muestra drift spec vs implementación
    python vault_manifest.py --check             # muestra sin escribir
    python vault_manifest.py --status active     # filtra por estado
    python vault_manifest.py --status deprecated # lista tools deprecadas
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

SCRIPTS_DIR = Path(__file__).parent

from vault_io import (  # noqa: E402
    atomic_write_json,
    get_vault_root,
    resolve_tool_spec,
    tool_spec_path,
)
from vault_errors import emit_error, wrap_main
from vault_version import CURRENT_VERSION  # generator_version de los artefactos (AP-47)
import vault_grafo_import  # noqa: E402

# AP-58 (v41.17): los datos de abajo viven en la hoja vault_spec_data;
# manifest y spec_memory compartían ambos sentidos del arco y cada uno
# importaba al otro dentro de funciones. La hoja no conoce a ninguno.
# Los nombres se reexportan aquí por no-derogación de consumidores.
from vault_spec_data import (  # noqa: E402
    DEPRECATED_TOOLS, DECLARED_RETURNS, DQ_METADATA, INTERNAL_TOOLS,
    META_TOOLS, TOOL_GROUPS, _FUND_BY_TOOL, _build_manifest,
)

# ──────────────────────────────────────────────────────────────────────────────
# Tool status registry
# ──────────────────────────────────────────────────────────────────────────────




# ──────────────────────────────────────────────────────────────────────────────
# Spec-driven helpers
# ──────────────────────────────────────────────────────────────────────────────


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault.meta_toolkit.repositorio import RepositorioMetaToolkit  # noqa: E402
from vault.kernel import construir  # noqa: E402
from vault.meta_toolkit import flags_cli  # extractor único de add_argument (v41.9)  # noqa: E402


def _raiz() -> Path:
    """La raiz del vault, resuelta al usarse."""
    return _repo().raiz


def _repo(root=None) -> RepositorioMetaToolkit:
    """Resuelve el vault al usarse, no al importarse (AP-49)."""
    return RepositorioMetaToolkit(construir(root))


def _system_dir() -> Path:
    return _repo().dir_sistema


def _manifest_file() -> Path:
    return _repo().manifiesto_tools


def _load_spec() -> Optional[Dict[str, Any]]:
    """Carga tool-spec.json si existe. Retorna None si no existe (fallback a hardcoded)."""
    spec_file = resolve_tool_spec()
    if spec_file is None:
        return None
    try:
        return json.loads(spec_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        emit_error("vault_manifest", "SPEC_PARSE_ERROR", str(exc))
        return None


def _build_manifest_from_spec(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Genera la lista de entradas del manifiesto desde tool-spec.json."""
    manifest = []
    for name, entry in sorted(spec.get("tools", {}).items()):
        m: Dict[str, Any] = {
            "name": name,
            "status": entry.get("status", "active"),
            "group": entry.get("group", "misc"),
        }
        if entry.get("status") == "deprecated":
            m["replaced_by"]      = entry.get("replaced_by", "")
            m["deprecated_since"] = entry.get("deprecated_since", "")
            m["reason"]           = entry.get("deprecation_reason", "")
        if entry.get("status") in ("internal", "meta"):
            m["note"] = "Not exposed to agent"
        dq = entry.get("dq", {})
        if dq:
            m.update(dq)
        funds = entry.get("fundamentals", [])
        if funds:
            m["data_fundamentals"] = funds
        manifest.append(m)
    return manifest


def _extract_required_flags(source: str) -> List[str]:
    """Los flags con `required=True`, leídos por `flags_cli` (el extractor único)."""
    return flags_cli.obligatorios(source)


def _bootstrap_spec() -> Dict[str, Any]:
    """
    Genera tool-spec.json combinando datos hardcodeados + introspección de scripts.
    Incluye declared_returns desde vault_spec_memory.DECLARED_RETURNS.
    """
    # Import DECLARED_RETURNS (fuente actual de retornos declarados)
    _dr: Dict[str, List[str]] = {}
    try:
        from vault_spec_memory import DECLARED_RETURNS as _DR
        _dr = _DR
    except ImportError:
        pass

    # `group` y `group_id`, derivados de la fuente única del catálogo.
    #
    # Hasta v40.8 esto leía `vault_compact_contracts.GROUPS`, que es un
    # derivado **del tool-spec que esta misma función está generando**: el
    # bootstrap se alimentaba de su propia salida anterior, y de paso cruzaba
    # a otro contexto acotado por un símbolo que nadie había declarado puerto.
    # `mapa_de_grupos()` es la misma derivación que `check_contracts` usa para
    # comprobar el resultado — productor y verificador, una sola fuente.
    _group_by_tool: Dict[str, Dict] = {}
    try:
        from vault_mcp_catalog import mapa_de_grupos
        _group_by_tool = mapa_de_grupos()
    except ImportError:
        pass

    # Combinar todos los nombres de tools conocidos
    all_names: Set[str] = set(TOOL_GROUPS.keys())
    all_names.update(_group_by_tool.keys())
    # Descubrir scripts activos que puedan no estar en el registry
    for p in SCRIPTS_DIR.glob("vault_*.py"):
        stem = p.stem
        if stem not in ("vault_errors", "vault_io"):
            all_names.add(stem)

    tools: Dict[str, Any] = {}
    for name in sorted(all_names):
        # Estado
        if name in DEPRECATED_TOOLS:
            status = "deprecated"
        elif name in INTERNAL_TOOLS:
            status = "internal"
        elif name in META_TOOLS:
            status = "meta"
        else:
            status = "active"

        # Grupo
        gdata = _group_by_tool.get(name, {})
        group_name = gdata.get("name", TOOL_GROUPS.get(name, "misc"))
        group_id   = gdata.get("id", 0)

        # Args (introspección del script)
        required_args: List[str] = []
        script_path = SCRIPTS_DIR / f"{name}.py"
        if script_path.exists():
            # Deuda #12: el nombre puede ser un alias sin código; los
            # obligatorios se leen en el dueño (AP-44).
            script_path = vault_grafo_import.fuente_de(name)
            try:
                src = script_path.read_text(encoding="utf-8", errors="replace")
                required_args = _extract_required_flags(src)
            except Exception as exc:
                emit_error("vault_manifest", "INTROSPECTION_ERROR",
                          f"{name}: {exc}")

        entry: Dict[str, Any] = {
            "group":            group_name,
            "group_id":         group_id,
            "status":           status,
            "required_args":    required_args,
            "declared_returns": _dr.get(name, []),
            "dq":               DQ_METADATA.get(name, {
                "dq_dimensions":    [],
                "cia_scope":        [],
                "propagation_aware": False,
            }),
            "fundamentals": _FUND_BY_TOOL.get(name, []),
        }

        if name in DEPRECATED_TOOLS:
            dep = DEPRECATED_TOOLS[name]
            entry["replaced_by"]        = dep["replaced_by"]
            entry["deprecated_since"]   = dep["since"]
            entry["deprecation_reason"] = dep["reason"]

        tools[name] = entry

    return {
        # La versión del contrato es la corriente del estándar, no un literal:
        # era "v32", que ya no decía nada (el campo se ajustaba a mano en cada
        # release). `CURRENT_VERSION` es su dueño.
        "version":     CURRENT_VERSION,
        "generator_version": CURRENT_VERSION,
        "schema":      "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Spec-driven tool contracts. "
            "Editar este archivo ANTES de implementar una nueva tool. "
            "Validar con: python vault_spec_validate.py"
        ),
        "tools": tools,
        # La cabecera sale de las entradas, nunca de una cifra escrita a mano
        # (v40.16 la mintió tres versiones: `active: 75` eran 103). Derivarla
        # aquí hace que un nuevo bootstrap no vuelva a mentir.
        "_counts": {
            "active": sum(1 for e in tools.values() if e["status"] == "active"),
            "internal": sum(1 for e in tools.values() if e["status"] == "internal"),
            "archived": sum(1 for e in tools.values() if e["status"] == "archived"),
            "total": len(tools),
            "active_groups": len({
                e.get("group_id") for e in tools.values()
                if e["status"] == "active" and e.get("group_id")
            }),
            "schema_version": "1.0",
        },
    }




def _read_version() -> str:
    try:
        sv = _system_dir() / "standard-version.json"
        if sv.exists():
            datos = json.loads(sv.read_text(encoding="utf-8"))
            # El fichero sella `applied_version` (vault_init, vault_standard_upgrade).
            # Se leía la clave `version`, que no existe en el formato actual: el
            # manifiesto decía "unknown" siempre, en silencio (medido 2026-10-18).
            # `version` numérica se acepta como formato anterior — no-derogación.
            v = datos.get("applied_version") or datos.get("version", "unknown")
            return f"v{v}" if isinstance(v, int) else str(v)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        emit_error("vault_manifest", "VERSION_READ_ERROR", str(exc))
    except Exception as exc:
        emit_error("vault_manifest", "UNEXPECTED_ERROR", str(exc))
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="vault_manifest — manifiesto de tools (spec-driven desde tool-spec.json)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python vault_manifest.py --bootstrap         # genera tool-spec.json (primera vez o al actualizar)
  python vault_manifest.py                     # genera 00_System/tools-manifest.json desde spec
  python vault_manifest.py --validate          # muestra drift entre spec e implementación
  python vault_manifest.py --check             # muestra manifiesto sin escribir
  python vault_manifest.py --status deprecated # lista solo tools deprecadas
  python vault_manifest.py --status active     # lista solo tools activas
""",
        allow_abbrev=False,
    )
    parser.add_argument("--bootstrap", action="store_true",
                        help="Genera tool-spec.json desde datos hardcodeados + introspección. "
                             "Se niega a sobrescribir una spec existente salvo --force (v41.17): "
                             "el bootstrap reescribe el contrato entero y las ediciones a mano "
                             "se pierden — para el bump de versión está --sync-version.")
    parser.add_argument("--sync-version", action="store_true",
                        help="Sube SOLO el campo version de tool-spec.json a CURRENT_VERSION, "
                             "sin regenerar los contratos. Es lo que un release necesita.")
    parser.add_argument("--campo-version", dest="campo_version",
                        help="Con --sync-version: la versión a escribir, en vez de "
                             "CURRENT_VERSION. Es para la fábrica de release, que "
                             "sube el número ANTES de que el registro lo muestre")
    parser.add_argument("--force", action="store_true",
                        help="Con --bootstrap: aceptar sobrescribir la spec existente.")
    parser.add_argument("--validate", action="store_true",
                        help="Valida conformidad implementación vs spec (delega a vault_spec_validate)")
    parser.add_argument("--check",  action="store_true", help="Mostrar manifiesto sin escribir")
    parser.add_argument("--status", choices=["active", "deprecated", "internal", "meta"],
                        help="Filtrar por estado")

    args = parser.parse_args()

    # ── Modo bootstrap ──────────────────────────────────────────────────────
    if args.bootstrap:
        # v41.17: el bootstrap regenera el contratco entero a partir del
        # catálogo + introspección — cualquier declared_returns / guard /
        # nota escrita a mano en la spec se pierde. Sobre una spec que ya
        # existe, la regla es la del manifiesto: no se sobrescribe salvo
        # que quien lo invoca lo pida explícito (--force). Corollario del
        # incidente del 2026-10-21: --bootstrap sin --force había borrado
        # las required_args a mano y Creating un fantasma aplicable.
        spec_file = tool_spec_path()
        if spec_file.exists() and not args.force:
            print(json.dumps(emit_error(
                "vault_manifest", "INVALID_ARGS",
                "tool-spec.json ya existe y --bootstrap lo reescribe entero; usa "
                "--sync-version para subir la version, o --force si de verdad "
                "regeneras el contrato desde cero",
            ), ensure_ascii=False))
            return 1
        spec = _bootstrap_spec()
        # v39/AP-36: el contrato vive en <vault>/00_System/ y se escribe de forma
        # atómica. Antes: scripts/tool-spec.json con write_text() directo.
        atomic_write_json(spec_file, spec)
        tool_count = len(spec["tools"])
        active = sum(1 for e in spec["tools"].values() if e["status"] == "active")
        print(json.dumps({
            "ok": True,
            "action": "bootstrap",
            "spec_file": str(spec_file.relative_to(get_vault_root())).replace("\\", "/"),
            "tools_total": tool_count,
            "tools_active": active,
            "version": spec["version"],
            "next_step": "Commit tool-spec.json. Desde ahora editar spec ANTES de implementar.",
        }, indent=2, ensure_ascii=False))
        return 0

    # ── Modo sync-version (v41.17) ─────────────────────────────────────────
    # Lo que un release necesita del spec: SOLO el campo version y el
    # generated_at, sin regenerar los contratos que la mano del contract-
    # owner sostiene. El round-trip del escritor es byte-estable (verificado
    # 2026-10-22), así que el diff de este modo es exactamente el campo.
    if args.sync_version:
        spec_file = tool_spec_path()
        if not spec_file.exists():
            print(json.dumps(emit_error(
                "vault_manifest", "INVALID_ARGS",
                "no hay tool-spec.json en el vault activo; --sync-version sube "
                "el campo de una spec existente, no la crea. Se construye con "
                "--bootstrap)",
            ), ensure_ascii=False))
            return 1
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        objetivo = args.campo_version or CURRENT_VERSION
        if not re.fullmatch(r"v\d+\.\d+", objetivo or ""):
            print(json.dumps(emit_error(
                "vault_manifest", "INVALID_ARGS",
                f"--campo-version debe ser vX.Y; llega {objetivo!r}",
            ), ensure_ascii=False))
            return 1
        antes = str(spec.get("version"))
        if antes == objetivo:
            # Idempotencia: si ya manda la versión corriente, no se toca el
            # fichero (ni el generated_at) — una re-corrida no es un diff.
            print(json.dumps({
                "ok": True, "tool": "vault_manifest", "action": "sync-version",
                "version": objetivo, "written": False,
                "spec_file": str(
                    spec_file.relative_to(get_vault_root())).replace("\\", "/"),
            }, indent=2, ensure_ascii=False))
            return 0
        spec["version"] = objetivo
        spec["generated_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        atomic_write_json(spec_file, spec)
        print(json.dumps({
            "ok": True, "tool": "vault_manifest", "action": "sync-version",
            "version": {"antes": antes, "despues": objetivo},
            "spec_file": str(
                spec_file.relative_to(get_vault_root())).replace("\\", "/"),
        }, indent=2, ensure_ascii=False))
        return 0

    # ── Modo validate ──────────────────────────────────────────────────────
    if args.validate:
        try:
            from vault_spec_validate import load_spec, run_validation, _print_report
            spec = load_spec()
            validation = run_validation(spec)
            _print_report(validation)
            return 0 if validation["ok"] else 1
        except ImportError:
            print(json.dumps(emit_error("vault_manifest", "FILE_NOT_FOUND", "vault_spec_validate.py no encontrado"), ensure_ascii=False))
            return 1

    # ── Modo normal (genera manifiesto) ────────────────────────────────────
    spec = _load_spec()
    if spec is not None:
        manifest = _build_manifest_from_spec(spec)
        source_label = "tool-spec.json"
    else:
        # Fallback hardcodeado — advertir
        import sys as _sys
        print(
            '{"warning": "tool-spec.json no encontrado — usando datos hardcodeados. '
            'Ejecutar: python vault_manifest.py --bootstrap"}',
            file=_sys.stderr,
        )
        manifest = _build_manifest()
        source_label = "hardcoded (fallback)"

    if args.status:
        manifest = [e for e in manifest if e["status"] == args.status]

    result: Dict[str, Any] = {
        "ok": True,
        "standard_version": _read_version(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source_label,
        "total":      len(manifest),
        "active":     sum(1 for e in manifest if e["status"] == "active"),
        "deprecated": sum(1 for e in manifest if e["status"] == "deprecated"),
        "internal":   sum(1 for e in manifest if e["status"] == "internal"),
        "meta":       sum(1 for e in manifest if e["status"] == "meta"),
        "tools": manifest,
    }

    if args.check:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    _system_dir().mkdir(parents=True, exist_ok=True)
    _manifest_file().write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "source": source_label,
        "total":      result["total"],
        "active":     result["active"],
        "deprecated": result["deprecated"],
        "path": str(_manifest_file().relative_to(_raiz())).replace("\\", "/"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(wrap_main(main, "vault_manifest"))
