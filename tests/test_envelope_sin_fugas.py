"""AP-36 aplicado a la salida — un envelope de error no publica el disco local.

Medido antes del arreglo: todo `emit_error` con `exception=` adjuntaba el
traceback completo —rutas absolutas del intérprete, del toolkit y del usuario—
y los mensajes repetían la ruta resuelta del vault: `vault_read --path ../x`
respondía con `C:\\Users\\<usuario>\\...` dos veces. Por MCP eso llega al
agente y a sus logs. El traceback sigue disponible para quien depura, con
`VAULT_DEBUG=1`.
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


def _provocar(tool="vault_x"):
    try:
        raise OSError("fallo provocado")
    except OSError as exc:
        return vault_errors.emit_error(tool, "FILE_READ_ERROR", "no se pudo", exception=exc)


def test_sin_depuracion_no_hay_traceback(monkeypatch):
    monkeypatch.delenv("VAULT_DEBUG", raising=False)
    assert "traceback" not in _provocar()


def test_con_vault_debug_el_traceback_sigue_ahi(monkeypatch):
    monkeypatch.setenv("VAULT_DEBUG", "1")
    assert "fallo provocado" in _provocar()["traceback"]


def test_ap36_la_raiz_del_vault_sale_como_marcador(monkeypatch, tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    monkeypatch.setenv("VAULT_ROOT", str(raiz))
    nota = raiz / "07_Knowledge" / "x.md"
    env = vault_errors.emit_error("vault_x", "NOTE_NOT_FOUND", f"No existe: {nota}")
    assert str(raiz) not in env["message"]
    assert env["message"].replace("\\", "/") == "No existe: <vault>/07_Knowledge/x.md"


def test_el_directorio_del_usuario_sale_como_tilde(monkeypatch):
    monkeypatch.delenv("VAULT_ROOT", raising=False)
    fuera = Path.home() / "secreto" / "clave.txt"
    env = vault_errors.emit_error("vault_x", "FILE_NOT_FOUND", f"No existe: {fuera}")
    assert str(Path.home()) not in env["message"]
    assert env["message"].replace("\\", "/") == "No existe: ~/secreto/clave.txt"


def test_una_raiz_relativa_no_borra_palabras(monkeypatch):
    monkeypatch.setenv("VAULT_ROOT", "vault")
    env = vault_errors.emit_error("vault_x", "NOTE_NOT_FOUND", "el vault no tiene esa nota")
    assert env["message"] == "el vault no tiene esa nota"


def test_una_tool_real_no_publica_la_ruta_absoluta(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge"):
        (raiz / seccion).mkdir(parents=True)
    entorno = {k: v for k, v in os.environ.items() if k != "VAULT_DEBUG"}
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_read.py"), "--path", "../fuera.md"],
        env=dict(entorno, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    env = json.loads(salida[salida.index("{"):])
    assert env["ok"] is False, env
    texto = json.dumps(env, ensure_ascii=False)
    for ruta in (str(tmp_path), str(tmp_path.resolve()), str(Path.home())):
        assert ruta not in texto and json.dumps(ruta)[1:-1] not in texto, texto
    assert "traceback" not in env
