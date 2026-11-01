"""`build_py` de la wheel de producto: deja fuera la gobernanza del estándar.

La lista no se escribe aquí. Es `fuera-de-la-wheel.json`, que deriva
`python scripts/vault_servicio.py --wheel-sync` de la capacidad
`gobernanza_del_estandar` y que `vault_servicio --check` (puerta) vigila.

Solo stdlib y setuptools: el build aislado no tiene PyYAML ni este repo en
`sys.path`, así que importar `vault_servicio` desde aquí fallaría justo en la
máquina del tercero.
"""

from __future__ import annotations

import json
from pathlib import Path

from setuptools.command.build_py import build_py as _build_py

LISTA = Path(__file__).resolve().parent / "fuera-de-la-wheel.json"


def fuera_de_la_wheel() -> tuple[str, frozenset[str]]:
    """`(paquete, módulos)`. Sin el fichero, el build falla en vez de llevarlo todo."""
    datos = json.loads(LISTA.read_text(encoding="utf-8"))
    return datos["paquete"], frozenset(datos["modulos"])


def excluidos() -> tuple[dict[str, frozenset[str]], tuple[str, ...]]:
    """`({paquete: módulos}, subpaquetes)`: los módulos de las tools, sus alias y
    los subpaquetes enteros (B-3). Una clave que falta hace fallar el build, igual
    que el fichero: leerla como vacía metería la gobernanza en la wheel."""
    datos = json.loads(LISTA.read_text(encoding="utf-8"))
    por_paquete = {datos["paquete"]: set(datos["modulos"])}
    for paquete, modulos in datos["alias"].items():
        por_paquete.setdefault(paquete, set()).update(modulos)
    return ({k: frozenset(v) for k, v in por_paquete.items()},
            tuple(datos["subpaquetes"]))


class BuildPy(_build_py):
    def find_package_modules(self, package, package_dir):
        modulos = super().find_package_modules(package, package_dir)
        por_paquete, subpaquetes = excluidos()
        # El subpaquete tampoco está en `packages` de pyproject.toml; esto es lo
        # que lo deja fuera aunque alguien lo añada ahí.
        if any(package == s or package.startswith(s + ".") for s in subpaquetes):
            return []
        fuera = por_paquete.get(package)
        if not fuera:
            return modulos
        return [m for m in modulos if m[1] not in fuera]
