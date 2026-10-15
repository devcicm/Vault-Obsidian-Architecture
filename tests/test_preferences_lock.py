"""F1/CIA-I — `vault_preferences` reescribe la nota bajo su lock.

`--set` lee `createdAt` de la versión previa y escribe la nueva; `--revoke`
lee la nota, le cambia el estado y la reescribe entera. Sin lock, un `--set`
y un `--revoke` concurrentes se pisaban: el que llegaba segundo escribía sobre
una lectura vieja, y una preferencia revocada podía volver a activa con los
dos envelopes en `ok: true`. Una preferencia es integridad alta por definición
(`cia_integrity: high` en su propio frontmatter).

Se mide la parte determinista: con la nota tomada por otro escritor, ninguna
de las dos escribe y las dos lo dicen.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import problemas_de_forma  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402


def _argv(*a):
    return [sys.executable, str(SCRIPTS / "vault_preferences.py"), *a, "--agent", "test"]


def test_con_la_nota_tomada_set_y_revoke_no_escriben(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "17_Preferences").mkdir(parents=True)
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    alta = subprocess.run(
        _argv("--set", "--category", "constraints", "--title", "tabs",
              "--statement", "usar tabs"),
        env=env, capture_output=True, text=True, encoding="utf-8", cwd=str(SCRIPTS))
    creada = json.loads(alta.stdout[alta.stdout.index("{"):])
    assert creada["ok"], creada
    nota = raiz / creada["path"]
    original = nota.read_text(encoding="utf-8")

    ocupado = nota.parent / ".locks" / f"{nota.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")

    procesos = [
        subprocess.Popen(_argv("--set", "--category", "constraints", "--title", "tabs",
                               "--statement", "usar espacios"),
                         env=env, cwd=str(SCRIPTS), stdout=subprocess.PIPE, stderr=subprocess.PIPE),
        subprocess.Popen(_argv("--revoke", creada["path"], "--reason", "cambio"),
                         env=env, cwd=str(SCRIPTS), stdout=subprocess.PIPE, stderr=subprocess.PIPE),
    ]
    for p in procesos:
        salida, error = p.communicate(timeout=120)
        texto = salida.decode("utf-8", "replace")
        assert "{" in texto, error.decode("utf-8", "replace")
        r = json.loads(texto[texto.index("{"):])
        assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
        assert problemas_de_forma(r) == [], r
    assert nota.read_text(encoding="utf-8") == original
