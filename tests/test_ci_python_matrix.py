"""Toda matriz de Python de la CI arranca en el piso publicado.

`tests/test_piso_python.py` exige el piso en los jobs que ejecutan pytest. Esto
cubre el resto: el job `product-gates` instala la wheel y es el que ejerce la
promesa de instalación, así que una matriz que subiera allí el mínimo dejaría
el piso sin instalar nunca aunque la suite sí lo corriera.

La matriz se lee con `yaml.safe_load`, no con un regex sobre el texto (AP-44).
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


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


# ---------------------------------------------------------------------------
# Lo que los classifiers prometen, la matriz lo ejerce.
#
# Medido en la auditoría del 2026-10-15: `pyproject.toml` declaraba Python
# 3.9–3.12 y `Operating System :: OS Independent`, y la CI ejecutaba 3.9 y 3.11
# en ubuntu y windows. 3.10 y 3.12 no los corría nadie; macOS, tampoco, y «OS
# Independent» promete además cualquier sistema que exista. El ejecutor de
# `vault_produccion` (`_ci_cubre_los_sistemas`) lo daba por cubierto porque el
# texto del YAML contenía las subcadenas «ubuntu» y «windows».

def _classifiers() -> list:
    texto = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bloque = re.search(r"^classifiers\s*=\s*\[(.*?)^\]", texto, re.S | re.M)
    assert bloque, "classifiers no encontrado en pyproject.toml"
    return re.findall(r'"([^"]+)"', bloque.group(1))


def _ejes(job: str) -> dict:
    datos = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "vault-ci.yml").read_text(encoding="utf-8"))
    return (datos["jobs"][job].get("strategy") or {}).get("matrix") or {}


JOBS_QUE_EJERCEN = ("validate", "product-gates")


def test_toda_version_prometida_corre_en_cada_job():
    prometidas = {c.rsplit("::", 1)[1].strip() for c in _classifiers()
                  if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c)}
    assert prometidas
    for job in JOBS_QUE_EJERCEN:
        corre = {str(v) for v in _ejes(job).get("python-version", [])}
        assert prometidas <= corre, f"{job}: prometidas sin ejecutar {sorted(prometidas - corre)}"


def test_ningun_classifier_promete_cualquier_sistema():
    assert "Operating System :: OS Independent" not in _classifiers()


def test_todo_sistema_prometido_tiene_runner_en_cada_job():
    import vault_produccion as vp

    prometidos = vp.sistemas_prometidos()
    assert prometidos, "pyproject.toml no promete ningún sistema"
    for job in JOBS_QUE_EJERCEN:
        runners = {str(r).split("-")[0] for r in _ejes(job).get("os", [])}
        faltan = {s for s in prometidos if vp.RUNNER_DE_SISTEMA[s] not in runners}
        assert not faltan, f"{job}: sistemas prometidos sin runner {sorted(faltan)}"


def test_el_ejecutor_de_produccion_lee_la_matriz_y_no_el_texto(tmp_path, monkeypatch):
    """Una subcadena en un comentario no es un runner (AP-44)."""
    import vault_produccion as vp

    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        'classifiers = [\n    "Operating System :: Microsoft :: Windows",\n'
        '    "Operating System :: POSIX :: Linux",\n]\n', encoding="utf-8")
    ci = tmp_path / ".github" / "workflows" / "vault-ci.yml"
    ci.write_text(
        "# ubuntu algún día\njobs:\n  validate:\n    strategy:\n      matrix:\n"
        "        os: [windows-latest]\n  product-gates:\n    strategy:\n"
        "      matrix:\n        os: [windows-latest]\n", encoding="utf-8")
    monkeypatch.setattr(vp, "RAIZ", tmp_path)
    assert vp._ci_cubre_los_sistemas() is False
    ci.write_text(ci.read_text(encoding="utf-8").replace(
        "[windows-latest]", "[windows-latest, ubuntu-latest]"), encoding="utf-8")
    assert vp._ci_cubre_los_sistemas() is True
    (tmp_path / "pyproject.toml").write_text(
        'classifiers = [\n    "Operating System :: OS Independent",\n]\n', encoding="utf-8")
    assert vp._ci_cubre_los_sistemas() is False
