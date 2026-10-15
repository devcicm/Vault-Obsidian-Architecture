"""Un salto del reloj de pared le robaba el lock a un dueño vivo.

`vault.kernel.bloqueo.adquirir` daba un lock por huérfano cuando
`time.time() - createdAt` superaba `CADUCA_TRAS` (120 s). La edad salía del
reloj de pared, que puede saltar: NTP corrigiendo, una VM que despierta, la
resincronización de WSL. Medido el 2026-10-15 al ejecutar la suite en un
contenedor python:3.9-slim sobre Docker Desktop: el reloj del contenedor iba
3458 s por detrás del host, saltó en mitad de
`test_append_concurrente::test_con_la_nota_bloqueada_no_escribe_y_lo_dice`, el
lock de un dueño de 1,2 s pasó a tener 3460 y `vault_append` escribió con
ok:true sobre una nota bloqueada.

Se declaró como deuda (`lock_caduca_por_reloj_de_pared`) y este test fijaba el
límite. Saldada el 2026-10-15: `owner.json` guarda la máquina y el inicio del
proceso, y en la misma máquina el lock solo se rompe si el dueño murió
(`tests/test_lock_dueno_vivo.py`, que la sostiene). El límite se conserva
invertido —no-derogación—: ahora vigila que el cierre no se deshaga.
"""

import json
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import vault_blueprint as bp  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402


def test_limite_declarado_lock_caduca_por_reloj_de_pared(tmp_path):
    deuda = {d["id"]: d for d in bp.DEUDA_DECLARADA}.get("lock_caduca_por_reloj_de_pared")
    assert deuda and deuda["estado"] == "saldada" and deuda.get("sostenida_por")

    nota = tmp_path / "nota.md"
    nota.write_text("x\n", encoding="utf-8")
    _, lock_dir = bloqueo.rutas_de_lock(nota)
    token = bloqueo.adquirir(nota, timeout=1.0)
    try:
        # El dueño vivo —este mismo proceso— ve su `createdAt` atrás porque el
        # reloj saltó hacia delante más que `CADUCA_TRAS`.
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        dueno["createdAt"] = time.time() - bloqueo.CADUCA_TRAS - 3458
        (lock_dir / "owner.json").write_text(json.dumps(dueno), encoding="utf-8")
        with pytest.raises(TimeoutError):
            bloqueo.adquirir(nota, timeout=0.5)
        dueno = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        assert dueno["token"] == token, (
            "un salto del reloj volvió a robarle el lock a un dueño vivo: "
            "`lock_caduca_por_reloj_de_pared` se ha reabierto")
    finally:
        bloqueo.soltar(nota, token)
