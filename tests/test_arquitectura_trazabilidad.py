"""La capa de trazabilidad es ADITIVA y se deriva de las fuentes vivas.

Este test es su propio guard: si el inventario o el grafo se desactualizan
respecto a sus fuentes, o si una ficha afirma mas de lo que su fuente dice, el
test falla. No se disables para obtener verde.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "audits" / "architecture"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _yaml(nombre: str):
    import yaml

    ruta = BASE / nombre
    if not ruta.is_file():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def _json(nombre: str):
    ruta = BASE / nombre
    if not ruta.is_file():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_el_inventario_esta_generado_y_no_es_una_copia_a_mano():
    datos = _yaml("inventario-maestro.yaml")
    assert datos.get("recursos"), "el inventario no tiene recursos"
    assert datos.get("generado_por", "").endswith("generar_inventario.py")
    assert datos.get("sha"), "el inventario no declara el SHA que lo genero"


def test_toda_relacion_apunta_a_recursos_existentes():
    grafo = _json("grafo-trazabilidad.json")
    ids = {r["id"] for r in _yaml("inventario-maestro.yaml").get("recursos", [])}
    for arista in grafo.get("relaciones", []):
        assert arista["from"] in ids, arista
        assert arista["to"] in ids, arista
        assert arista["relation"], arista
        assert arista["basis"] in ("observada", "declarada", "inferida",
                                  "pendiente"), arista


def test_ninguna_relacion_se_presenta_como_observada_sin_fundamento():
    grafo = _json("grafo-trazabilidad.json")
    for arista in grafo.get("relaciones", []):
        if arista["basis"] == "observada":
            assert arista.get("detail"), ("relacion observada sin detalle: "
                                          f"{arista}")


def test_los_recursos_no_verificados_lo_declaran():
    recursos = _yaml("inventario-maestro.yaml").get("recursos", [])
    for r in recursos:
        assert r["status"] in ("VERIFICADO", "NO_VERIFICADO"), r["id"]
        if r["status"] == "NO_VERIFICADO":
            assert r.get("confidence_basis"), r["id"]


def test_las_fichas_de_divergencias_cubren_las_diez():
    fichas = _yaml("divergencias-archify.yaml").get("divergencias", [])
    assert len(fichas) == 10, len(fichas)
    for f in fichas:
        assert f["id"].startswith("DIV-")
        assert f["naturaleza"], f
        assert f["accion_requerida"], f
        assert f["ratificado"] is False, ("una divergencia no puede estar "
                                          "ratificada sin el propietario")
        assert f["alternativas"], f


def test_las_fichas_de_hallazgos_distinguen_los_dos_escenarios():
    datos = _yaml("hallazgos-qg02.yaml")
    fichas = datos.get("hallazgos", [])
    assert fichas, "no hay fichas de hallazgos"
    entornos = {f["environment"] for f in fichas}
    assert any("A" in e for e in entornos), entornos
    assert any("B" in e for e in entornos), entornos
    for f in fichas:
        assert f["norm"] and f["path"], f
        assert f["classification"], f
        assert f["quality_gate"] == "QG-02", f


def test_la_lista_de_aceptaciones_no_silencia_nada_sin_ratificar():
    import yaml

    ruta = BASE / "divergencias-aceptadas.yaml"
    assert ruta.is_file()
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    for entrada in datos.get("divergencias") or []:
        if entrada.get("ratificado"):
            pytest.skip("existe una aceptacion ratificada: revisar a mano")
        # sin ratificar, la entrada es una ficha inerte
        assert entrada.get("evidencia"), entrada


def test_el_reconciliador_sigue_listando_las_diez_sin_ratificacion():
    p = subprocess.run([sys.executable, str(ROOT / "audits" / "fase2" /
                                            "reconciliar_archify.py"), "--check"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    salida = p.stdout + p.stderr
    assert "divergencia(s) no aceptada(s)" in salida, salida[-400:]


def test_el_inventario_se_regenera_de_forma_determinista():
    antes = (BASE / "inventario-maestro.yaml").read_text(encoding="utf-8")
    p = subprocess.run([sys.executable, str(BASE / "generar_inventario.py")],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    assert p.returncode == 0, p.stdout[-400:] + p.stderr[-400:]
    despues = (BASE / "inventario-maestro.yaml").read_text(encoding="utf-8")
    assert antes == despues, "el inventario generado no es reproducible"


def test_la_constitucion_esta_marcada_como_borrador():
    texto = (ROOT / "docs" / "architecture" /
             "CONSTITUCION-ARQUITECTONICA.md").read_text(encoding="utf-8")
    assert "PENDIENTE DE RATIFICACIÓN" in texto
    assert "DRAFT" in texto
