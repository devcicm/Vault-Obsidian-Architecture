"""F1/CIA-I — dos appends a la misma nota no se pisan.

Medido en v40.34 por MCP: ocho `vault_append` en paralelo sobre la misma nota
dejaron siete líneas, y los ocho envelopes decían `ok: true`. `vault_append`
leía la nota, concatenaba y la reescribía sin lock: la escritura era atómica
(`os.replace`), pero la lectura de quien llegaba segundo ya estaba vieja, así
que su `os.replace` borraba el append del primero. Atómico no es aislado.

El lock es el mismo que toma `vault_write` (`file_lock` sobre la nota), así que
un append y un write a la misma nota también se excluyen.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
N = 12


def test_appends_en_paralelo_llegan_todos(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    nota = raiz / "07_Knowledge" / "log.md"
    nota.write_text("---\ntitle: log\nstatus: draft\n---\n# log\n", encoding="utf-8")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    procesos = [
        subprocess.Popen(
            [sys.executable, str(SCRIPTS / "vault_append.py"),
             "--path", "07_Knowledge/log.md", "--content", f"MARCA{i:02d}",
             "--no-timestamp"],
            env=env, cwd=str(SCRIPTS),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for i in range(N)
    ]
    envelopes = []
    for p in procesos:
        salida, error = p.communicate(timeout=120)
        texto = salida.decode("utf-8", "replace").strip()
        assert texto, error.decode("utf-8", "replace")
        envelopes.append(json.loads(texto[texto.index("{"):]))

    contenido = nota.read_text(encoding="utf-8")
    llegadas = [i for i in range(N) if f"MARCA{i:02d}" in contenido]
    confirmadas = [e for e in envelopes if e.get("ok")]
    # Un ok:true cuyo dato no está en la nota es la mentira que se mide (F4).
    assert len(llegadas) == len(confirmadas) == N, (llegadas, envelopes)


def test_con_la_nota_bloqueada_no_escribe_y_lo_dice(tmp_path):
    """Quien no consigue el lock no escribe: `ok: false` con `NOTE_LOCKED` y
    la nota intacta. Escribir sin lock tras el timeout sería volver a abrir
    la carrera que el lock cierra."""
    sys.path.insert(0, str(ROOT))
    from vault.kernel.errores import problemas_de_forma

    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    nota = raiz / "07_Knowledge" / "log.md"
    original = "---\ntitle: log\nstatus: draft\n---\n# log\n"
    nota.write_text(original, encoding="utf-8")
    ocupado = raiz / "07_Knowledge" / ".locks" / "log.md.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps({"pid": 0, "createdAt": __import__("time").time(), "token": "otro"}),
        encoding="utf-8")
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_append.py"),
         "--path", "07_Knowledge/log.md", "--content", "NO_DEBE_LLEGAR"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", cwd=str(SCRIPTS), timeout=120,
    )
    env = json.loads(proceso.stdout[proceso.stdout.index("{"):])
    assert env["ok"] is False and env["error_code"] == "NOTE_LOCKED", env
    assert problemas_de_forma(env) == [], env
    assert nota.read_text(encoding="utf-8") == original
    assert (ocupado / "owner.json").exists()  # el lock ajeno sigue en pie
