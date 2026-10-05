"""Ciclo de vida mínimo, estable e instalable de un runtime consumidor.

No ejecuta scripts históricos ni intenta instalar el toolkit dentro del vault.
El seed es una proyección empaquetada y verificable del registro canónico de
secciones; el directorio creado contiene únicamente datos del consumidor.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from ..kernel.frontmatter_escritura import Frontmatter


CREATED = "INIT_CREATED"
ALREADY_INITIALIZED = "INIT_ALREADY_EXISTS"
CONFLICT = "INIT_CONFLICT"
INVALID_TARGET = "INIT_INVALID_TARGET"
FAILED = "INIT_FAILED"


@dataclass(frozen=True)
class RuntimeSeed:
    schema: int
    standard_version: str
    sections: tuple[str, ...]


def cargar_seed() -> RuntimeSeed:
    """Lee la proyección empaquetada, sin tocar el checkout."""
    raw = json.loads(
        resources.files(__package__).joinpath("runtime-seed.json").read_text(encoding="utf-8")
    )
    sections = raw.get("sections")
    version = raw.get("standard_version")
    if (
        raw.get("schema") != 1
        or not isinstance(version, str)
        or not version
        or not isinstance(sections, list)
        or not sections
        or not all(isinstance(section, str) and section for section in sections)
    ):
        raise ValueError("runtime seed empaquetado inválido")
    return RuntimeSeed(1, version, tuple(sections))


def _version_path(root: Path) -> Path:
    return root / "00_System" / "standard-version.json"


def _required_paths(root: Path, seed: RuntimeSeed) -> tuple[Path, ...]:
    return tuple(root / section for section in seed.sections) + (
        _version_path(root),
        root / "00_System" / "vault-hub.md",
    )


def _version_data(seed: RuntimeSeed) -> dict[str, Any]:
    return {
        "applied_version": seed.standard_version,
        "migrations_applied": [],
        "runtime_schema": seed.schema,
    }


def _write_seed(root: Path, seed: RuntimeSeed, con_hub: bool = True) -> None:
    for section in seed.sections:
        (root / section).mkdir(parents=True, exist_ok=False)
    _version_path(root).write_text(
        json.dumps(_version_data(seed), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if con_hub:
        _write_hub_minimo(root)


def _write_hub_minimo(root: Path) -> None:
    """El hub de respaldo: sin bootstrap, o cuando el bootstrap falló.

    Hasta v40.35 era el único hub que el `vault init` instalado escribía, y
    como `vault_section_index` solo crea el hub si falta, el completo —el que
    enlaza las secciones y la nota de comandos— no llegaba a existir nunca.
    """
    # 2026-10-01: el hub nacía sin frontmatter y `vault_validate` —la misma
    # wheel— lo daba por inválido: ningún vault recién creado validaba limpio.
    # Lleva los campos que exige el validador; `vault_section_index` ya no lo
    # reescribe porque solo crea el hub si falta.
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # AP-46: el bloque lo escribe su dueño; aquí solo se declaran los campos.
    frontmatter = (
        Frontmatter()
        .set("title", "Vault Hub")
        .set("id", "vault-hub")
        .set("createdAt", ahora)
        .set("updatedAt", ahora)
        .set("cia_integrity", "high")
        .set("cia_availability", "high")
        .set("cia_sensitivity", "internal")
        .set("agent", "system")
        .set("tags", ["nav", "hub"])
        .render()
    )
    (root / "00_System" / "vault-hub.md").write_text(
        frontmatter + "\n\n"
        "# Vault runtime\n\n"
        "Runtime documental inicializado por el toolkit instalado.\n",
        encoding="utf-8",
        newline="\n",
    )


def _target(target: str | Path) -> Path:
    path = Path(target).expanduser()
    if not path.name:
        raise ValueError("el runtime necesita una ruta de directorio concreta")
    return path.resolve()


def _initialized(root: Path, seed: RuntimeSeed) -> bool:
    return root.is_dir() and all(path.exists() for path in _required_paths(root, seed))


#: Puebla un runtime recién creado (índices, hub, nota de comandos, primers).
#: Lo inyecta quien sabe ejecutar las tools —la CLI—: este módulo no las conoce.
Bootstrap = Callable[[Path], dict]


def inicializar_runtime(
    target: str | Path, bootstrap: Bootstrap | None = None
) -> dict[str, Any]:
    """Crea un runtime nuevo de manera staging→rename y sin sobrescribir datos.

    Un directorio ya válido es idempotente. Cualquier directorio no vacío que
    no cumpla el contrato se rechaza: nunca se interpreta como permiso para
    mezclar un seed con contenido arbitrario.
    """
    try:
        root = _target(target)
        seed = cargar_seed()
    except (OSError, ValueError) as exc:
        return {"ok": False, "state": INVALID_TARGET, "detail": str(exc)}

    if root.exists() and not root.is_dir():
        return {"ok": False, "state": INVALID_TARGET, "detail": "el target no es un directorio"}
    if _initialized(root, seed):
        return {"ok": True, "state": ALREADY_INITIALIZED, "runtime": str(root)}
    if root.exists() and any(root.iterdir()):
        return {
            "ok": False,
            "state": CONFLICT,
            "detail": "el target no está vacío y no cumple el contrato de runtime",
        }
    parent = root.parent
    if not parent.exists() or not parent.is_dir():
        return {"ok": False, "state": INVALID_TARGET, "detail": "el padre del target no existe"}

    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.init-", dir=parent))
    try:
        _write_seed(staging, seed, con_hub=bootstrap is None)
        if root.exists():
            root.rmdir()
        os.replace(staging, root)
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return {"ok": False, "state": FAILED, "detail": f"no se pudo inicializar: {exc}"}
    result = {
        "ok": True,
        "state": CREATED,
        "runtime": str(root),
        "standard_version": seed.standard_version,
        "sections": list(seed.sections),
    }
    if bootstrap is not None:
        # Sobre la ruta final y no en staging: las tools registran la raíz
        # absoluta en sus trazas, y en staging quedaría la de un directorio
        # que ya no existe.
        try:
            poblado = bootstrap(root)
        except Exception as exc:  # el runtime ya existe: se informa, no se pierde
            poblado = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
        if not (root / "00_System" / "vault-hub.md").is_file():
            _write_hub_minimo(root)
        result["bootstrap"] = poblado
    return result


def _compatibility(version: str, seed: RuntimeSeed) -> str:
    if version == seed.standard_version:
        return "compatible"
    try:
        current = tuple(int(part) for part in seed.standard_version.removeprefix("v").split("."))
        observed = tuple(int(part) for part in version.removeprefix("v").split("."))
    except ValueError:
        return "invalid"
    return "unsupported_newer" if observed > current else "unsupported_older"


def diagnosticar_runtime(target: str | Path) -> dict[str, Any]:
    """Diagnóstico estructural read-only del runtime externo."""
    try:
        root = _target(target)
        seed = cargar_seed()
    except (OSError, ValueError) as exc:
        return {"ok": False, "state": "INVALID_TARGET", "detail": str(exc)}
    if not root.exists():
        return {"ok": False, "state": "RUNTIME_MISSING", "runtime": str(root)}
    if not root.is_dir():
        return {"ok": False, "state": "NOT_RUNTIME", "runtime": str(root)}
    version_path = _version_path(root)
    if not version_path.exists():
        return {"ok": False, "state": "STANDARD_VERSION_MISSING", "runtime": str(root)}
    try:
        version_data = json.loads(version_path.read_text(encoding="utf-8"))
        version = version_data["applied_version"]
        if not isinstance(version, str):
            raise ValueError("applied_version inválida")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return {"ok": False, "state": "STANDARD_VERSION_INVALID", "runtime": str(root), "detail": str(exc)}
    missing = [section for section in seed.sections if not (root / section).is_dir()]
    if missing:
        return {"ok": False, "state": "SYSTEM_FILES_MISSING", "runtime": str(root), "missing": missing}
    if not (root / "00_System" / "vault-hub.md").is_file():
        return {"ok": False, "state": "SYSTEM_FILES_MISSING", "runtime": str(root), "missing": ["00_System/vault-hub.md"]}
    compatibility = _compatibility(version, seed)
    return {
        "ok": compatibility == "compatible",
        "state": "RUNTIME_OK" if compatibility == "compatible" else "STANDARD_INCOMPATIBLE",
        "runtime": str(root),
        "standard_version": version,
        "compatibility": compatibility,
        "sections_present": len(seed.sections),
    }


def estado_runtime(target: str | Path) -> dict[str, Any]:
    """Vista breve, determinista y read-only construida desde el diagnóstico."""
    diagnosis = diagnosticar_runtime(target)
    vista = {
        "ok": diagnosis["ok"],
        "state": diagnosis["state"],
        "runtime": diagnosis.get("runtime", str(Path(target).expanduser())),
        "standard_version": diagnosis.get("standard_version"),
        "compatibility": diagnosis.get("compatibility"),
        "sections_present": diagnosis.get("sections_present", 0),
    }
    # Lo que falta es lo único accionable de un SYSTEM_FILES_MISSING: una vista
    # breve que lo omite deja al consumidor sabiendo que algo falta, no qué.
    if "missing" in diagnosis:
        vista["missing"] = diagnosis["missing"]
    return vista
