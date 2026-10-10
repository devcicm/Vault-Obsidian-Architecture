"""AP-36 — con una raíz adivinada no se escribe nada, tampoco por la puerta de atrás.

`vault_io._rechazar_raiz_insegura` (v40.30) protegía `atomic_write_text` y se
declaraba «el único sitio por el que toda escritura pasa». Medido como
consumidor el 2026-10-10 con la wheel instalada y sin `VAULT_ROOT`: la raíz cae
a `repo_root_fallback` —el propio `site-packages/vault_toolkit`— y, aunque la
nota se rechazaba, dentro del paquete quedaban `00_System/.tool-trace.json`,
`00_System/.voice-counter` y la carpeta `07_Knowledge/` vacía. Tres escritores
que no pasan por `atomic_write_text`: la traza, el contador de voz y el `mkdir`
de la carpeta destino. La decisión «¿se puede escribir aquí?» tiene un dueño,
`vault_raiz.escritura_admitida`, y la consultan todos.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

SONDA = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import vault_raiz
falso = Path(sys.argv[1])
vault_raiz.VAULT_ROOT = falso
vault_raiz._VAULT_ROOT_ORIGIN = "repo_root_fallback"
import vault_write, vault_errors_trace
from vault.autoria import voz
cuerpo = "Contenido de prueba con cuerpo suficiente para pasar la puerta. " * 4
r = vault_write.vault_write("07_Knowledge", "Nota de prueba", cuerpo, tags=["prueba"])
vault_errors_trace.log_trace({"tool": "sonda", "ok": False})
voz.rotacion(voz._root_runtime())
print(json.dumps({"write": r}, default=str))
"""


def _sondear(falso: Path, permisivo: bool = False) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("VAULT_ROOT", "VAULT_STRICT_ROOT", "VAULT_PERMISSIVE_ROOT")}
    env["PYTHONIOENCODING"] = "utf-8"
    if permisivo:
        env["VAULT_PERMISSIVE_ROOT"] = "1"
    p = subprocess.run([sys.executable, "-c", SONDA, str(falso), str(SCRIPTS)],
                       env=env, cwd=str(falso.parent), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert "{" in texto, p.stderr[-2000:]
    return json.loads(texto[texto.rindex('{"write"'):])


def test_raiz_adivinada_no_deja_ningun_fichero(tmp_path):
    # AP-36: rechazada la escritura, el directorio adivinado queda como estaba.
    falso = tmp_path / "site-packages" / "vault_toolkit"
    falso.mkdir(parents=True)
    salida = _sondear(falso)
    assert salida["write"].get("ok") is False, salida
    dejado = sorted(p.relative_to(falso).as_posix() for p in falso.rglob("*"))
    assert dejado == [], f"la raíz adivinada recibió escrituras: {dejado}"


def test_la_bandera_permisiva_sigue_escribiendo(tmp_path):
    # No-derogación: VAULT_PERMISSIVE_ROOT=1 conserva el comportamiento anterior.
    falso = tmp_path / "site-packages" / "vault_toolkit"
    falso.mkdir(parents=True)
    salida = _sondear(falso, permisivo=True)
    assert (falso / "00_System" / ".tool-trace.json").exists(), salida
