"""Secciones propias: las que un vault declara en `00_System/secciones.json` (CN-02).

Hasta v41.1 una carpeta de raíz fuera del registro del estándar era CN-02 sin
remedio. Medido en un vault ajeno: `/ans` guarda `scripts/` en la raíz y sus
`.md` salían como notas sin sección. Ahora el vault puede declarar la sección;
lo que no declara sigue siendo CN-02. Aquí se prueba solo la lectura y la
validación, que vive en `vault_registry` sin importar `vault_io`.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_registry as reg  # noqa: E402


def _declarar(raiz: Path, secciones) -> None:
    destino = raiz / reg.SECCIONES_PROPIAS_RUTA
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"schema": 1, "secciones": secciones}), encoding="utf-8")


def _s(folder, documentacion="referencia", **extra):
    return {"folder": folder, "documentacion": documentacion, **extra}


def test_el_rango_libre_se_deriva_del_registro_del_estandar():
    assert reg.NUMEROS_PROPIOS == (22, 98)


@pytest.mark.parametrize("nombre", ["22_Scripts", "45_Clientes", "98_Archivo_2025"])
def test_nombres_validos(nombre):
    assert reg.motivo_de_nombre_invalido(nombre) is None


@pytest.mark.parametrize("nombre,parte", [
    ("scripts", "NN_Nombre"),
    ("22-Scripts", "NN_Nombre"),
    ("22_", "NN_Nombre"),
    ("07_Otra", "no está libre"),
    ("99_Mas", "no está libre"),
    ("21_QA", "no está libre"),
])
def test_nombres_invalidos_dicen_por_que(nombre, parte):
    assert parte in reg.motivo_de_nombre_invalido(nombre)


def test_sin_fichero_no_hay_secciones_propias(tmp_path):
    assert reg.leer_secciones_propias(tmp_path) == []
    assert reg.secciones_del_vault(tmp_path) == sorted(reg.ORDERED_SECTIONS)


def test_las_declaradas_se_suman_en_orden(tmp_path):
    _declarar(tmp_path, [_s("30_Clientes", "explicacion"), _s("22_Scripts")])
    assert [s["folder"] for s in reg.leer_secciones_propias(tmp_path)] == ["22_Scripts", "30_Clientes"]
    vault = reg.secciones_del_vault(tmp_path)
    assert vault.index("21_QA") < vault.index("22_Scripts") < vault.index("30_Clientes") \
        < vault.index("99_Index")


def test_una_retirada_sigue_siendo_seccion(tmp_path):
    _declarar(tmp_path, [_s("22_Viejo", status="retirada", superseded_by="23_Nuevo"),
                         _s("23_Nuevo")])
    assert "22_Viejo" in reg.secciones_del_vault(tmp_path)


@pytest.mark.parametrize("contenido,parte", [
    ("{no es json", "no se puede leer"),
    (json.dumps({"otra": []}), "falta la lista"),
    (json.dumps({"secciones": [_s("scripts")]}), "NN_Nombre"),
    (json.dumps({"secciones": [_s("22_A"), _s("22_B")]}), "repite"),
    (json.dumps({"secciones": [_s("22_A", "manual")]}), "documentacion"),
    (json.dumps({"secciones": [_s("22_A", status="borrada")]}), "status"),
])
def test_un_registro_roto_falla_en_voz_alta(tmp_path, contenido, parte):
    """AP-51: un `[]` aquí haría violar CN-02 a todas las notas de la sección."""
    destino = tmp_path / reg.SECCIONES_PROPIAS_RUTA
    destino.parent.mkdir(parents=True)
    destino.write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError, match=parte):
        reg.leer_secciones_propias(tmp_path)


def test_es_de_seccion_con_raiz_ve_las_propias_y_sin_raiz_no(tmp_path):
    _declarar(tmp_path, [_s("22_Scripts")])
    assert reg.es_de_seccion("22_Scripts/deploy.md", tmp_path)
    assert not reg.es_de_seccion("22_Scripts/deploy.md")
    assert not reg.es_de_seccion("23_Otra/x.md", tmp_path)
    assert not reg.es_de_seccion("22_Scripts.md", tmp_path)
    assert reg.es_de_seccion("07_Knowledge/x.md", tmp_path)


def test_la_cache_se_invalida_cuando_el_vault_declara_otra_seccion(tmp_path):
    """El contrato pregunta por cada nota; la caché no puede esconder un `--add`."""
    _declarar(tmp_path, [_s("22_Scripts")])
    assert "30_Clientes" not in reg.secciones_del_vault(tmp_path)
    _declarar(tmp_path, [_s("22_Scripts"), _s("30_Clientes", "explicacion")])
    assert "30_Clientes" in reg.secciones_del_vault(tmp_path)
    # La lista devuelta es nueva: mutarla no envenena la siguiente lectura.
    reg.secciones_del_vault(tmp_path).clear()
    assert "22_Scripts" in reg.secciones_del_vault(tmp_path)
