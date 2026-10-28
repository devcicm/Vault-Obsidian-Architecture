"""La capa de trazabilidad es ADITIVA y se deriva de una fuente INMUTABLE.

Este test es su propio guard: si el inventario o el grafo se desactualizan
respecto a sus fuentes, o si una ficha afirma mas de lo que su fuente dice, el
test falla. No se desactiva para obtener verde.
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


def _generar(destino: Path, extra=()):
    p = subprocess.run([sys.executable, str(BASE / "generar_inventario.py"),
                        "--salida-dir", str(destino), *extra],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=3600)
    assert p.returncode == 0, p.stdout[-500:] + p.stderr[-500:]
    return destino


def test_el_inventario_esta_generado_y_no_es_una_copia_a_mano():
    datos = _yaml("inventario-maestro.yaml")
    assert datos.get("recursos"), "el inventario no tiene recursos"
    assert datos.get("generado_por", "").endswith("generar_inventario.py")
    assert datos.get("source"), "el inventario debe declarar su fuente"
    assert datos.get("source_sha"), "el inventario debe declarar el SHA que leyo"


def test_la_fuente_es_el_arbol_y_no_el_workspace(tmp_path):
    """La fuente de verdad es el commit: el workspace mutable no cuenta."""
    destino = _generar(tmp_path / "gen")
    datos = _yaml_en(destino / "inventario-maestro.yaml")
    assert datos["source"] == "arbol git (inmutable)"
    assert datos["source_sha"], datos


def _yaml_en(ruta):
    import yaml

    return yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}


def test_toda_relacion_apunta_a_recursos_existentes():
    grafo = _json("grafo-trazabilidad.json")
    ids = {r["id"] for r in _yaml("inventario-maestro.yaml").get("recursos", [])}
    for arista in grafo.get("relaciones", []):
        assert arista["from"] in ids, arista
        assert arista["to"] in ids, arista
    assert grafo["conteo"]["aristas_huerfanas"] == 0, grafo.get("aristas_huerfanas")


def test_las_relaciones_estan_tipadas():
    grafo = _json("grafo-trazabilidad.json")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generador_trazabilidad", BASE / "generar_inventario.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for arista in grafo.get("relaciones", []):
        assert arista["relation"] in mod.RELACIONES, arista
        assert arista["basis"] in mod.FUNDAMENTO, arista


def test_no_hay_autorrelaciones_vacias():
    """Una relacion de un recurso consigo mismo no dice nada."""
    grafo = _json("grafo-trazabilidad.json")
    for arista in grafo.get("relaciones", []):
        if arista["from"] == arista["to"]:
            assert arista["relation"] != "APPLIES_TO", arista


def test_ninguna_relacion_se_presenta_como_observada_sin_fundamento():
    grafo = _json("grafo-trazabilidad.json")
    for arista in grafo.get("relaciones", []):
        if arista["basis"] == "observada":
            assert arista.get("detail"), f"relacion observada sin detalle: {arista}"


def test_los_niveles_de_verificacion_significan_algo():
    """Descubrir un fichero NO es certificarlo (QA-ARC-02)."""
    datos = _yaml("inventario-maestro.yaml")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generador_trazabilidad_niveles", BASE / "generar_inventario.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for r in datos.get("recursos", []):
        assert r["verification_level"] in mod.NIVELES, r["id"]
        if r["verification_level"] != "ratificado_propietario":
            assert r.get("next_level_requires"), (
                f"{r['id']} dice su nivel pero no que falta para el siguiente")
    niveles = {n: sum(1 for r in datos.get("recursos", [])
                       if r["verification_level"] == n) for n in mod.NIVELES}
    assert niveles["verificado"] + niveles["evidencia_acreditada"] < niveles["descubierto"] + niveles["declarado"] + niveles["implementado"], (
        "presentar descubrimiento como certificacion")


def test_los_recursos_no_verificados_lo_declaran():
    for r in _yaml("inventario-maestro.yaml").get("recursos", []):
        assert r["status"] in ("VERIFICADO", "NO_VERIFICADO"), r["id"]


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


def test_la_lista_de_aceptaciones_no_silencia_nada_sin_ratificar():
    import yaml

    ruta = BASE / "divergencias-aceptadas.yaml"
    assert ruta.is_file()
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    for entrada in datos.get("divergencias") or []:
        if entrada.get("ratificado"):
            pytest.skip("existe una aceptacion ratificada: revisar a mano")
        assert entrada.get("evidencia"), entrada


def test_el_reconciliador_sigue_listando_las_diez_sin_ratificacion():
    p = subprocess.run([sys.executable, str(ROOT / "audits" / "fase2" /
                                            "reconciliar_archify.py"), "--check"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=3600)
    salida = p.stdout + p.stderr
    assert "divergencia(s) no aceptada(s)" in salida, salida[-400:]


def test_la_generacion_es_determinista_sobre_el_mismo_arbol(tmp_path):
    """Dos generaciones desde el MISMO commit dan el MISMO resultado."""
    uno = _generar(tmp_path / "a")
    dos = _generar(tmp_path / "b")
    primero = (uno / "inventario-maestro.yaml").read_text(encoding="utf-8")
    segundo = (dos / "inventario-maestro.yaml").read_text(encoding="utf-8")
    assert primero == segundo, "la generacion no es reproducible"


def test_la_generacion_detecta_un_arbol_modificado(tmp_path):
    """Si el commit no existe, el generador FALLA: no inventa un inventario."""
    p = subprocess.run([sys.executable, str(BASE / "generar_inventario.py"),
                        "--salida-dir", str(tmp_path / "x"),
                        "--sha", "f" * 40],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    assert p.returncode != 0, "un sha inexistente no puede generar inventario"
    assert "SHA_INEXISTENTE" in p.stdout, p.stdout[-300:]


def test_la_constitucion_declara_su_ratificacion_y_su_acto():
    """DEC-01 (2026-10-28): ratificada tal cual. El estado tiene que citar el
    acto que la ratifica; un «RATIFICADA» sin acta seria autoatribucion."""
    texto = (ROOT / "docs" / "architecture" /
             "CONSTITUCION-ARQUITECTONICA.md").read_text(encoding="utf-8")
    assert "ESTADO: RATIFICADA" in texto
    assert "PENDIENTE DE RATIFICACIÓN" not in texto
    acta = "ACTA-DECISIONES-PROPIETARIO-2026-10-28.md#DEC-01"
    assert acta in texto
    assert (ROOT / "audits" / "handoff" / acta.split("#")[0]).is_file()
