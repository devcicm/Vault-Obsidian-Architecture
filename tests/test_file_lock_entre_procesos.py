"""F1/CIA-I — `file_lock` excluye de verdad entre procesos.

Medido en v40.34: con el lock puesto, doce `vault_append` en paralelo seguían
perdiendo entre uno y tres. La causa estaba en el lock, no en el append:

- `os.mkdir(lock_dir)` y la escritura de `owner.json` son dos pasos. Quien
  miraba entre los dos no encontraba `owner.json` y daba el lock por caducado
  (`age = stale_after + 1`), así que lo robaba a un dueño vivo de milisegundos.
- Al salir, el dueño robado borraba `lock_dir` sin mirar de quién era ya, y
  con él el lock del ladrón: un tercero entraba con el ladrón todavía dentro.

Lo mide un contador leído y reescrito por N procesos, cada uno bajo el lock:
sin exclusión real, dos leen el mismo valor y el total sale corto.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
N = 12
VUELTAS = 15

HIJO = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from vault_fs import file_lock
contador = Path(sys.argv[2])

def tenaz(f):
    # En Windows un escáner puede abrir el fichero recién escrito un instante;
    # eso no es lo que se mide aquí. Sin exclusión, el total sale corto igual.
    for _ in range(200):
        try:
            return f()
        except PermissionError:
            time.sleep(0.01)
    return f()

for _ in range(int(sys.argv[3])):
    with file_lock(contador, timeout=60.0):
        valor = int(tenaz(contador.read_text))
        time.sleep(0.002)
        tenaz(lambda: contador.write_text(str(valor + 1)))
"""


def test_file_lock_no_deja_entrar_a_dos_procesos(tmp_path):
    contador = tmp_path / "contador.txt"
    contador.write_text("0")
    hijo = tmp_path / "hijo.py"
    hijo.write_text(HIJO, encoding="utf-8")
    procesos = [
        subprocess.Popen([sys.executable, str(hijo), str(SCRIPTS), str(contador), str(VUELTAS)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(N)
    ]
    errores = []
    for p in procesos:
        _, error = p.communicate(timeout=300)
        if p.returncode:
            errores.append(error.decode("utf-8", "replace"))
    assert errores == []
    assert int(contador.read_text()) == N * VUELTAS


def test_un_lock_sin_owner_recien_creado_no_se_roba(tmp_path):
    """El hueco entre `mkdir` y `owner.json` no es un lock caducado."""
    sys.path.insert(0, str(SCRIPTS))
    from vault_fs import file_lock

    objetivo = tmp_path / "nota.md"
    lock_dir = tmp_path / ".locks" / "nota.md.lock"
    lock_dir.mkdir(parents=True)  # otro proceso acaba de crearlo y aún no escribió owner.json
    try:
        with file_lock(objetivo, timeout=0.3):
            robado = True
    except TimeoutError:
        robado = False
    assert robado is False
    assert lock_dir.is_dir()
