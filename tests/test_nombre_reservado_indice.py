"""Nombre reservado de índice: una nota no puede llamarse como el índice generado.

Medido antes del guard: ``vault_write --title Index`` devolvía ``ok: true``; la
siguiente nota de la misma carpeta disparaba ``vault_section_index``, que
regeneraba ``index.md`` encima, y el contenido del usuario quedaba solo en un
``.backup.index.md.*`` oculto. Con otra capitalización pasa igual: en Windows y
macOS ``Index.md`` e ``index.md`` son el mismo fichero.

El dueño del criterio es ``vault.kernel.indices_structural.es_nombre_reservado``;
estos tests entran por las tools, así que fallan si cualquiera de ellas deja de
preguntarle antes de escribir.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vault.kernel.indices_structural import es_nombre_reservado

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CONTENIDO = (
    "L1 del contenido de prueba para el test.\n"
    "L2 con mas texto significativo aqui.\n"
    "L3 completa el minimo requerido.\n"
    "L4 para asegurar suficiente.\n"
    "L5 para estar seguro del todo.\n"
    "L6 y esta es la linea seis.\n"
    "L7 esta es la septima linea."
)


def _ejecutar(raiz: Path, script: str, *argv: str):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=dict(
            os.environ,
            VAULT_ROOT=str(raiz),
            PYTHONIOENCODING="utf-8",
            VAULT_AGENT="system",
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )


def _envelope(proceso) -> dict:
    lineas = [l for l in proceso.stdout.strip().splitlines() if l.strip()]
    assert lineas, proceso.stdout + proceso.stderr
    try:
        return json.loads(proceso.stdout)
    except json.JSONDecodeError:
        return json.loads(lineas[-1])


def _escribir(raiz: Path, carpeta: str, titulo: str) -> dict:
    return _envelope(_ejecutar(
        raiz, "vault_write",
        "--folder", carpeta, "--title", titulo,
        "--tags", "test", "--content", CONTENIDO,
    ))


def _ficheros(carpeta: Path) -> dict:
    """Contenido de todo lo que hay en la carpeta, backups ocultos incluidos."""
    if not carpeta.is_dir():
        return {}
    return {p.name: p.read_bytes() for p in carpeta.iterdir() if p.is_file()}


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    r = _ejecutar(raiz, "vault_init")
    assert r.returncode == 0, r.stdout + r.stderr
    return raiz


@pytest.mark.parametrize("nombre", ["index", "Index", "INDEX.md", "readme", "README.md", " index "])
def test_el_predicado_reconoce_los_nombres_reservados(nombre):
    assert es_nombre_reservado(nombre)


@pytest.mark.parametrize("nombre", ["indice", "index-de-apis", "mi-index", "readme-notas.md", ""])
def test_el_predicado_no_captura_nombres_normales(nombre):
    assert not es_nombre_reservado(nombre)


@pytest.mark.parametrize("titulo", ["Index", "index", "README", "readme"])
def test_vault_write_rechaza_el_nombre_reservado_sin_tocar_nada(vault, titulo):
    carpeta = vault / "07_Knowledge" / "concepts"
    antes = _escribir(vault, "07_Knowledge/concepts", "Nota previa")
    assert antes.get("ok") is True, antes
    estado = _ficheros(carpeta)

    resultado = _escribir(vault, "07_Knowledge/concepts", titulo)

    assert resultado.get("ok") is False, resultado
    assert resultado["error_code"] == "RESERVED_NAME"
    assert resultado["recovery"]["action"] == "fix_input"
    assert _ficheros(carpeta) == estado, "el rechazo no debe escribir ni hacer backups"


def test_la_nota_del_usuario_no_acaba_en_un_backup(vault):
    """El caso medido: tras rechazar «Index», el trabajo siguiente no pierde nada."""
    carpeta = vault / "07_Knowledge" / "concepts"
    assert _escribir(vault, "07_Knowledge/concepts", "Index").get("ok") is False
    siguiente = _escribir(vault, "07_Knowledge/concepts", "Otro concepto")
    assert siguiente.get("ok") is True, siguiente
    assert not [n for n in _ficheros(carpeta) if n.startswith(".backup.index")]
    assert "L1 del contenido" in (vault / siguiente["path"]).read_text(encoding="utf-8")


def test_un_titulo_que_solo_contiene_index_sigue_escribiendose(vault):
    resultado = _escribir(vault, "07_Knowledge/concepts", "Index de APIs")
    assert resultado.get("ok") is True, resultado


def test_vault_preferences_rechaza_el_nombre_reservado(vault):
    carpeta = vault / "17_Preferences" / "workflow"
    estado = _ficheros(carpeta)
    resultado = _envelope(_ejecutar(
        vault, "vault_preferences",
        "--set", "--category", "workflow", "--title", "Index",
        "--statement", "No commitear sin permiso", "--strength", "must",
    ))
    assert resultado.get("ok") is False, resultado
    assert resultado["error_code"] == "RESERVED_NAME"
    assert _ficheros(carpeta) == estado
