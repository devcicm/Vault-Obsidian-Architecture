"""F8: una bitácora ilegible no se pisa con una entrada nueva.

Medido en la auditoría del 2026-10-15: `_read_json_log` devolvía `[]` ante un
`.change-log.json` que no se leía como JSON, y `vault_change_log_add` lo
reescribía con una sola entrada y respondía ok:true. Todo el historial de no
repudio desaparecía sin que nadie lo dijera —lo contrario de lo que F8 promete—,
y `--query` contestaba `total: 0` como si nunca hubiera habido cambios (AP-51).

Ahora una bitácora que existe y no se lee —JSON roto o algo que no es una
lista— es `DATA_FILE_CORRUPT` (causa INDICE_ILEGIBLE, la misma que los índices
compartidos): no se escribe nada, el fichero queda como estaba para repararlo a
mano, y quien anota por debajo (`vault_write`, `vault_append`) lo publica en
`change_log_error` sin tumbar la nota, que ya está en disco.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

ROTA = '[{"id": "a", "action": "created", "path": "07_Knowledge/x.md"'
NO_LISTA = '{"entries": []}'


def _tool(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="agente-f8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    return json.loads(p.stdout[p.stdout.index("{"):])


def _vault(tmp_path: Path, contenido: str) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    (raiz / "00_System" / ".change-log.json").write_text(contenido, encoding="utf-8")
    return raiz


@pytest.mark.parametrize("contenido", [ROTA, NO_LISTA], ids=["json_roto", "no_lista"])
def test_anotar_sobre_una_bitacora_ilegible_no_la_pisa(tmp_path, contenido):
    raiz = _vault(tmp_path, contenido)
    env = _tool(raiz, "vault_change_log.py", "--action", "deleted",
                "--path", "07_Knowledge/x.md", "--reason", "prueba F8")
    assert env["ok"] is False and env["error_code"] == "DATA_FILE_CORRUPT", env
    assert env.get("causa") == "INDICE_ILEGIBLE", env
    bitacora = raiz / "00_System" / ".change-log.json"
    assert bitacora.read_text(encoding="utf-8") == contenido


def test_consultar_una_bitacora_ilegible_no_dice_cero(tmp_path):
    raiz = _vault(tmp_path, ROTA)
    env = _tool(raiz, "vault_change_log.py", "--query")
    assert env["ok"] is False and env["error_code"] == "DATA_FILE_CORRUPT", env


def test_vault_write_publica_el_fallo_y_conserva_la_bitacora(tmp_path):
    raiz = _vault(tmp_path, ROTA)
    env = _tool(raiz, "vault_write.py", "--folder", "07_Knowledge", "--title", "Nota F8 rota",
                "--tags", "f8", "--content",
                "Primera línea de la nota.\n\nSegunda línea con contexto real.\n\nTercera línea.")
    assert env["ok"] is True, env
    assert "change_log" not in env and env.get("change_log_error"), env
    assert (raiz / env["path"]).exists()
    assert (raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8") == ROTA
