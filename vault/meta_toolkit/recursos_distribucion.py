"""Ownership técnico de recursos; clasifica rutas, no duplica su contenido."""

from __future__ import annotations

from pathlib import PurePosixPath

CLASES_RECURSO = frozenset({
    "runtime_operational", "toolkit", "bootstrap", "migration",
    "standard_maintenance", "repo_only", "test",
})


def clasificar_recurso(ruta: str) -> str:
    """Clasifica una ruta por su propietario y ciclo de vida."""
    p = PurePosixPath(ruta.replace("\\", "/"))
    partes = p.parts
    nombre = p.name
    if "tests" in partes or "vault-sandbox" in partes:
        return "test"
    if nombre == "vault_ontology.json":
        return "bootstrap"
    if nombre in {"tool-spec.json", "standard-version.json"}:
        return "runtime_operational"
    if "migrations" in partes or nombre.startswith("migration-"):
        return "migration"
    if nombre.endswith("-baseline.json"):
        return "standard_maintenance"
    if partes and partes[0] in {"docs", ".github"}:
        return "repo_only"
    if partes and partes[0] in {"vault", "cli", "vault_toolkit"}:
        return "toolkit"
    return "repo_only"


def entra_al_wheel(ruta: str) -> bool:
    return clasificar_recurso(ruta) in {"toolkit", "bootstrap", "migration"}
