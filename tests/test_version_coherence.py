"""La versión del estándar se declara en cinco sitios. Deben decir lo mismo.

El plan de consolidación pedía `vault_version --check` para esto. Esa tool no
existe y nunca existió: la referencia venía de una verificación escrita a mano.
No se crea una tool nueva — no hay nada que ejecutar contra un vault, es un
invariante del propio repo, y su sitio es la suite.

`CURRENT_VERSION` manda: es lo que lee `vault_standard_upgrade` para decidir si
un vault necesita migración. Los otros cuatro son su reflejo, y cuando uno se
queda atrás el vault migra a una versión que la documentación no describe.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_standard_upgrade as vsu  # noqa: E402

VERSION = vsu.CURRENT_VERSION  # "v39.0"
NUMERO = VERSION.lstrip("v")  # "39.0"


def test_el_formato_de_current_version_es_canonico():
    assert re.fullmatch(r"v\d+\.\d+", VERSION), VERSION


def test_el_banner_del_manifiesto_coincide():
    cabecera = (ROOT / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8"
    )[:2000]
    m = re.search(r"^\*\*Versión:\*\* (v[\d.]+)", cabecera, re.M)
    assert m, "no se encontró el banner de versión en el manifiesto"
    assert m.group(1) == VERSION


def test_el_badge_del_readme_coincide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"img\.shields\.io/badge/version-(v[\d.]+)-", readme)
    assert m, "no se encontró el badge de versión en README.md"
    assert m.group(1) == VERSION


def test_pyproject_coincide():
    m = re.search(
        r'^version = "([\d.]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert m, "no se encontró version en pyproject.toml"
    assert m.group(1) == NUMERO


def test_el_vault_de_pruebas_esta_migrado_a_la_version_actual():
    """Si el sandbox se queda atrás, los guards corren contra un vault viejo."""
    estado = json.loads(
        (ROOT / "vault-sandbox/00_System/standard-version.json").read_text(
            encoding="utf-8"
        )
    )
    assert estado["applied_version"] == VERSION


def test_la_version_tiene_entrada_de_migracion_registrada():
    mayor = VERSION.split(".")[0]  # "v39"
    assert mayor in vsu.MIGRATIONS, f"{mayor} sin entrada en MIGRATIONS"
    assert mayor in vsu.VERSION_ORDER, f"{mayor} fuera de VERSION_ORDER"
    assert vsu.VERSION_ORDER[-1] == mayor, (
        f"VERSION_ORDER termina en {vsu.VERSION_ORDER[-1]!r} y CURRENT_VERSION "
        f"es {VERSION!r}: una migración posterior quedaría sin aplicar"
    )
