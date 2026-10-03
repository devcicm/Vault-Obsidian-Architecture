"""La gate de instalación limpia lee los registros del repo, no de una instalación (AP-44).

Medido 2026-10-02 en la Fase 6: `clean_install_gate` añadía `scripts/` a
`sys.path` pero no la raíz del repo, así que `import vault` lo resolvía la
instalación global que hubiera en `site-packages`. Con una 40.x vieja, la
gate caía con `ImportError: mensaje_de` —un fallo de la máquina, no del
producto—; con una que importara, habría contado las operaciones de la wheel
contra el registro de otra versión y salido verde o roja por la razón
equivocada. El script se lanza como `python tests/clean_install_gate.py`, y
entonces `sys.path[0]` es `tests/`, no la raíz.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ap44_los_registros_de_distribucion_salen_del_repo():
    sonda = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import clean_install_gate as g; g._registros_de_distribucion(); "
        "import vault, vault_servicio; "
        "print(vault.__file__); print(vault_servicio.__file__)"
    ) % (ROOT / "tests")
    r = subprocess.run(
        [sys.executable, "-c", sonda],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT / "tests",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    for origen in r.stdout.splitlines():
        assert Path(origen).resolve().is_relative_to(ROOT), origen
