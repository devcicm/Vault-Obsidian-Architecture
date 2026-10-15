"""Un salto del reloj de pared le roba el lock a un dueño vivo.

`vault.kernel.bloqueo.adquirir` da un lock por huérfano cuando
`time.time() - createdAt` supera `CADUCA_TRAS` (120 s). La edad sale del
reloj de pared, que puede saltar: NTP corrigiendo, una VM que despierta, la
resincronización de WSL. Medido el 2026-10-15 al ejecutar la suite en un
contenedor python:3.9-slim sobre Docker Desktop: el reloj del contenedor iba
3458 s por detrás del host, saltó en mitad de
`test_append_concurrente::test_con_la_nota_bloqueada_no_escribe_y_lo_dice`, el
lock de un dueño de 1,2 s pasó a tener 3460 y `vault_append` escribió con
ok:true sobre una nota bloqueada.

No es una regresión: el criterio es el de siempre. Está declarado como deuda
(`lock_caduca_por_reloj_de_pared`) y este test fija el límite: falla el día
que un dueño vivo deje de perder el lock por un salto del reloj, y entonces
la deuda se salda.
"""

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_blueprint as bp  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402


def test_limite_declarado_lock_caduca_por_reloj_de_pared(tmp_path):
    deuda = {d["id"]: d for d in bp.DEUDA_DECLARADA}.get("lock_caduca_por_reloj_de_pared")
    assert deuda and deuda["estado"] == "pendiente"

    nota = tmp_path / "nota.md"
    nota.write_text("x\n", encoding="utf-8")
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    lock_dir.mkdir(parents=True)
    # Un dueño vivo —este mismo proceso— cuyo `createdAt` quedó atrás porque
    # el reloj saltó hacia delante más que `CADUCA_TRAS`.
    (lock_dir / "owner.json").write_text(json.dumps({
        "pid": os.getpid(),
        "createdAt": time.time() - bloqueo.CADUCA_TRAS - 1,
        "token": "dueno-vivo",
    }), encoding="utf-8")

    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        assert dueno["token"] == token != "dueno-vivo", (
            "el dueño vivo conserva el lock tras un salto del reloj: salda "
            "`lock_caduca_por_reloj_de_pared` en vault_blueprint.DEUDA_DECLARADA")
    finally:
        bloqueo.soltar(nota, token)
