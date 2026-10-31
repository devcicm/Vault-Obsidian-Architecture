"""A-21 y A-14 — dos cifras escritas a mano que envejecieron sin guard.

El manifiesto decía «83 normas (44 AP + 6 PAT + 3 SP + 3 CN), AP-01 a AP-44»
cuando el catálogo ya tenía 68 AP, 4 SP y 5 CN; y `cli/COMMANDS.md` ilustraba
`groups` con total 76 / 35 grupos frente a 127 / 37. Se contrastan con los
registros, no con números copiados aquí.
"""

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from vault_norms_catalog import NORM_CATALOG  # noqa: E402


def _codigos():
    return [n["id"] if "id" in n else n["code"] for n in NORM_CATALOG] \
        if not isinstance(NORM_CATALOG, dict) else list(NORM_CATALOG)


def test_el_manifiesto_cuenta_las_normas_como_el_catalogo():
    texto = (ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")
    m = re.search(r"Catálogo embebido de las \*\*(\d+) normas\*\* del estándar "
                  r"\((\d+) AP \+ (\d+) PAT \+ (\d+) SP \+ (\d+) CN\).*?`AP-01` a `AP-(\d+)`", texto)
    assert m, "no se encuentra la frase de recuento de normas"
    codigos = _codigos()
    por_tipo = Counter(c.split("-")[0] for c in codigos)
    esperado = (len(codigos), por_tipo["AP"], por_tipo["PAT"], por_tipo["SP"], por_tipo["CN"])
    assert tuple(int(x) for x in m.groups()[:5]) == esperado
    maximo = max(int(c[3:]) for c in codigos if c.startswith("AP-"))
    assert int(m.group(6)) == maximo == por_tipo["AP"], "numeración AP contigua"


def test_el_ejemplo_de_cli_groups_coincide_con_la_salida_real():
    real = json.loads(subprocess.run(
        [sys.executable, "-m", "cli", "groups"], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", timeout=120).stdout)
    doc = (ROOT / "cli" / "COMMANDS.md").read_text(encoding="utf-8")
    m = re.search(r'"total": (\d+), "read": (\d+), "write": (\d+), "groups": (\d+)', doc)
    assert m
    assert tuple(map(int, m.groups())) == (real["total"], real["read"], real["write"], real["groups"])
