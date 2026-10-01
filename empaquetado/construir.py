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


class BuildPy(_build_py):
    def find_package_modules(self, package, package_dir):
        modulos = super().find_package_modules(package, package_dir)
        paquete, fuera = fuera_de_la_wheel()
        if package != paquete:
            return modulos
        return [m for m in modulos if m[1] not in fuera]
