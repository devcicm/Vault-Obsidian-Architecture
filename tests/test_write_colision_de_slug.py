"""AP-02 — dos títulos distintos con el mismo slug no se pisan.

Medido como consumidor el 2026-10-10: «Café con leche», «cafe-con-leche»,
«Cafe/con/leche» y «Cafe?con*leche» producen el mismo `cafe-con-leche.md`, y
cada escritura sustituía a la anterior —título incluido— con `ok: true`. La
versión previa iba a `.history`, pero nadie avisaba de que se había
reemplazado OTRA nota. Mismo título (salvo mayúsculas, espacios o forma
Unicode) es una actualización; otro título es una colisión y se rechaza.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CUERPO = "Texto propio de la nota, linea uno.\nTexto propio dos con palabras.\nTexto propio tres."


def _write(raiz: Path, titulo: str, cuerpo: str = CUERPO) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_write.py"), "--folder",
                        "07_Knowledge", "--title", titulo, "--content", cuerpo,
                        "--tags", "prueba", "--agent", "test"],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "00_System").mkdir(parents=True)
    (r / "07_Knowledge").mkdir()
    return r


@pytest.mark.parametrize("primero,otro,fichero", [
    ("Café con leche", "cafe-con-leche", "cafe-con-leche.md"),
    ("Café con leche", "Cafe con leche", "cafe-con-leche.md"),
    ("Cafe/con/leche", "Cafe?con*leche", "cafeconleche.md"),
])
def test_otro_titulo_con_el_mismo_slug_se_rechaza(raiz, primero, otro, fichero):
    # AP-02: la nota existente no se reemplaza por otra que solo comparte slug.
    assert _write(raiz, primero)["ok"] is True
    nota = raiz / "07_Knowledge" / fichero
    antes = nota.read_bytes()
    env = _write(raiz, otro, CUERPO + "\notro contenido")
    assert env["ok"] is False and env["error_code"] == "IDENTITY_CONFLICT", env
    assert nota.read_bytes() == antes


@pytest.mark.parametrize("mismo", ["Café con leche", "CAFÉ CON LECHE", "Café  con leche"])
def test_el_mismo_titulo_sigue_siendo_una_actualizacion(raiz, mismo):
    assert _write(raiz, "Café con leche")["ok"] is True
    env = _write(raiz, mismo, CUERPO + "\nsegunda version")
    assert env["ok"] is True, env
    assert "segunda version" in (raiz / "07_Knowledge" / "cafe-con-leche.md").read_text(
        encoding="utf-8")
