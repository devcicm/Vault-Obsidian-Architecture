"""El producto no arrastra a la gobernanza del estándar (grupo 35).

Medido en v40.34: `vault/kernel/adaptadores.NormasDelCatalogo` leía
`NORM_CATALOG` entrando por la fachada `vault_norms`, que importa el motor y,
con él, `vault_smoke`, `vault_voice` y el resto del meta-toolkit. Era la arista
que hacía imposible sacar el grupo 35 de la wheel sin romper `vault`: el dato
vive en la hoja `vault_norms_catalog` desde v40.27 (AP-62).
"""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _en_proceso_limpio(codigo: str) -> dict:
    salida = subprocess.run(
        [sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout
    return json.loads(salida.strip().splitlines()[-1])


def test_ap62_las_normas_del_producto_salen_de_la_hoja():
    r = _en_proceso_limpio(
        "import json, sys\n"
        "from vault.kernel.adaptadores import NormasDelCatalogo\n"
        "n = NormasDelCatalogo()\n"
        "v = n.vigentes(); c = n.por_codigo(v[0]['code']) is not None\n"
        "print(json.dumps({'vigentes': len(v), 'por_codigo': c, 'cargados': sorted("
        "m for m in sys.modules if m.split('.')[-1] in "
        "('vault_norms', 'vault_norms_engine', 'vault_smoke', 'vault_voice'))}))\n"
    )
    assert r["vigentes"] > 0 and r["por_codigo"]
    assert r["cargados"] == [], f"el producto cargó la gobernanza: {r['cargados']}"


def test_la_hoja_y_la_fachada_dan_el_mismo_catalogo():
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        import vault_norms
        import vault_norms_catalog
    finally:
        sys.path.remove(str(RAIZ / "scripts"))
    assert vault_norms.NORM_CATALOG is vault_norms_catalog.NORM_CATALOG


# ── La wheel de producto (P1, v40.34) ────────────────────────────────────────

def _servicio():
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        import vault_servicio
    finally:
        sys.path.remove(str(RAIZ / "scripts"))
    return vault_servicio


def test_la_lista_de_la_wheel_es_la_capacidad_de_gobernanza():
    vs = _servicio()
    volcado = json.loads(vs.FUERA_DE_LA_WHEEL.read_text(encoding="utf-8"))
    assert volcado["modulos"] == vs.modulos_fuera_de_la_wheel()
    assert "vault_gate" in volcado["modulos"]
    assert "vault_write" not in volcado["modulos"]


def test_una_lista_desfasada_rompe_la_puerta(tmp_path, monkeypatch):
    vs = _servicio()
    falso = tmp_path / "fuera.json"
    falso.write_text(json.dumps({"modulos": ["vault_gate"]}), encoding="utf-8")
    monkeypatch.setattr(vs, "FUERA_DE_LA_WHEEL", falso)
    r = vs.check()
    assert not r["ok"]
    assert r["wheel"]["exclusion_drift"]


def test_importar_un_excluido_sin_protegerlo_se_detecta():
    vs = _servicio()
    fuera = {"vault_gate"}
    assert vs.importaciones_sin_proteger("import vault_gate\n", fuera)
    assert vs.importaciones_sin_proteger(
        "def f():\n    return import_toolkit_module('vault_gate')\n", fuera)
    assert vs.importaciones_sin_proteger(
        "from vault_toolkit._impl import vault_gate\n", fuera)
    protegido = "try:\n    import vault_gate\nexcept (ImportError, OSError):\n    pass\n"
    assert vs.importaciones_sin_proteger(protegido, fuera) == []


def test_hoy_nada_de_lo_que_viaja_necesita_a_la_gobernanza():
    r = _servicio().check_de_la_wheel()
    assert r["shipped_imports_of_excluded"] == []


def test_el_hook_de_build_deja_fuera_la_gobernanza():
    """Se ejerce el `build_py` real que declara pyproject.toml."""
    pytest = __import__("pytest")
    pytest.importorskip("setuptools")
    proyecto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert 'build_py = "empaquetado.construir.BuildPy"' in proyecto

    sys.path.insert(0, str(RAIZ))
    try:
        from empaquetado.construir import BuildPy, fuera_de_la_wheel
    finally:
        sys.path.remove(str(RAIZ))
    from setuptools.dist import Distribution

    dist = Distribution({"name": "x"})
    dist.script_name = "setup.py"  # distutils lo compara al listar módulos
    cmd = BuildPy(dist)
    cmd.initialize_options()
    viajan = {m[1] for m in cmd.find_package_modules("vault_toolkit._impl", str(RAIZ / "scripts"))}
    paquete, fuera = fuera_de_la_wheel()
    assert paquete == "vault_toolkit._impl"
    assert fuera and not (viajan & fuera), sorted(viajan & fuera)
    assert {"vault_write", "vault_io", "vault_norms_catalog"} <= viajan
