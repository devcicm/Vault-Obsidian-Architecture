"""Toda matriz de Python de la CI arranca en el piso publicado.

`tests/test_piso_python.py` exige el piso en los jobs que ejecutan pytest. Esto
cubre el resto: el job `product-gates` instala la wheel y es el que ejerce la
promesa de instalación, así que una matriz que subiera allí el mínimo dejaría
el piso sin instalar nunca aunque la suite sí lo corriera.

La matriz se lee con `yaml.safe_load`, no con un regex sobre el texto (AP-44).
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _piso() -> tuple:
    texto = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python\s*=\s*"[><=~^]*\s*(\d+)\.(\d+)', texto)
    assert m, "requires-python no encontrado en pyproject.toml"
    return int(m.group(1)), int(m.group(2))


def _matrices() -> dict:
    datos = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8")
    )
    salida = {}
    for nombre, job in datos["jobs"].items():
        versiones = ((job.get("strategy") or {}).get("matrix") or {}).get("python-version")
        if versiones:
            salida[nombre] = [tuple(int(x) for x in str(v).split(".")[:2]) for v in versiones]
    return salida


def test_toda_matriz_de_python_arranca_en_el_piso():
    piso = _piso()
    matrices = _matrices()
    assert matrices, "la CI no declara ninguna matriz de Python"
    for job, versiones in matrices.items():
        assert min(versiones) == piso, (
            f"el job '{job}' prueba desde {min(versiones)} y pyproject.toml "
            f"promete {piso}: o la matriz baja, o la promesa sube"
        )


def test_el_job_de_la_wheel_declara_matriz():
    """Sin matriz, `product-gates` correría con el Python por defecto del runner."""
    assert "product-gates" in _matrices()
