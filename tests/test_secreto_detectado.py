"""AP-52 — un secreto bloqueado sale como `SECRET_DETECTED`, y antes que la forma.

Medido en la comparativa v34/v40 (2026-10-01): el bloqueo funcionaba —la clave
no llegaba al disco— pero el envelope decía `PERMISSION_DENIED`, cuya pista
manda revisar los permisos del directorio, y el mensaje enseñaba la variable
que desactiva el escáner. Además el escaneo solo ocurría al escribir: una nota
con secreto y sin tags volvía AP-26, y el agente añadía tags y reintentaba con
la clave dentro.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_errors  # noqa: E402
import vault_fs  # noqa: E402
from vault.kernel.errores import ERROR_CATALOG  # noqa: E402

CLAVE = "AKIAIOSFODNN7EXAMPLE"
CONTENIDO = (
    "configuracion de prueba con varias palabras para el validador\n"
    f"aws_access_key_id = {CLAVE}\n"
    "fin de la nota de prueba con texto suficiente\n"
)


def _write(raiz: Path, *argv: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="system")
    env.pop("VAULT_SKIP_SECRET_SCAN", None)
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_write.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(SCRIPTS))
    salida = p.stdout.strip()
    assert salida, p.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / seccion).mkdir(parents=True)
    return raiz


def test_ap52_el_bloqueo_es_un_fallo_con_causa_y_sin_receta_de_bypass(monkeypatch):
    monkeypatch.delenv("VAULT_SKIP_SECRET_SCAN", raising=False)
    with pytest.raises(PermissionError) as info:
        vault_fs.guarda_secretos(Path("x.md"), CONTENIDO)
    exc = info.value
    assert isinstance(exc, vault_fs.SecretoDetectado)
    assert "VAULT_SKIP_SECRET_SCAN" not in str(exc)
    assert CLAVE not in json.dumps(exc.datos)
    env = vault_errors.emit_fallo("vault_write", exc)
    assert env["error_code"] == "SECRET_DETECTED"
    assert env["secrets"] and env["secrets"][0]["line"]
    assert ERROR_CATALOG["SECRET_DETECTED"]["category"] == "governance"


def test_ap52_secreto_sin_tags_dice_secreto_no_ap26(vault):
    r = _write(vault, "--folder", "07_Knowledge", "--title", "credenciales",
               "--content", CONTENIDO)
    assert r["ok"] is False
    assert r["error_code"] == "SECRET_DETECTED", r
    assert CLAVE not in json.dumps(r)
    assert not any(CLAVE in p.read_text(encoding="utf-8", errors="replace")
                   for p in vault.rglob("*") if p.is_file())


def test_ap52_secreto_en_el_titulo_tambien(vault):
    r = _write(vault, "--folder", "07_Knowledge", "--title", f"clave {CLAVE}",
               "--tags", "demo", "--content",
               "texto normal de la nota con palabras suficientes para el validador\n"
               "segunda linea del cuerpo de la nota de prueba\n")
    assert r["error_code"] == "SECRET_DETECTED", r
