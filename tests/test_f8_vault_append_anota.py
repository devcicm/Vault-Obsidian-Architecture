"""F8 (no repudio): `vault_append` anota en `.change-log.json` lo que añade.

Desde m292 `vault_write` deja la constancia de lo que crea y actualiza, pero
`vault_append` cambiaba la nota sin anotar nada. Medido el 2026-10-15 al
reinstalar la wheel 41.5: tras un `vault run vault_append` la bitácora tenía
las entradas de `vault_write` y ninguna del añadido. La nota no perdía puntos
—F8 pide al menos una entrada por nota y ya tenía la de su creación—, pero
quién añadió qué y cuándo no quedaba en ninguna parte.

Mismo contrato que `vault_write`: campo `change_log` con el `id` y la `action`
de la entrada, o `change_log_error` si la bitácora falla, sin tumbar el
añadido, que ya está en disco.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _tool(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="agente-append")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads(p.stdout)


def test_vault_append_anota_el_anadido(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir()
    alta = _tool(raiz, "vault_write.py", "--folder", "07_Knowledge", "--title", "Nota F8 append",
                 "--tags", "f8", "--content",
                 "Primera línea de la nota.\n\nSegunda línea con contexto real.\n\nTercera línea.")
    anadido = _tool(raiz, "vault_append.py", "--path", alta["path"], "--content", "Añadido al final.")
    log = json.loads((raiz / "00_System" / ".change-log.json").read_text(encoding="utf-8"))
    assert [(e["action"], e["path"], e["agent"]) for e in log] == [
        ("created", alta["path"], "agente-append"),
        ("updated", alta["path"], "agente-append"),
    ]
    assert "vault_append" in log[1]["reason"]
    assert anadido["change_log"] == {"id": log[1]["id"], "action": "updated"}
