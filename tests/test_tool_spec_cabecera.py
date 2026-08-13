"""La cabecera de `tool-spec.json` llevaba tres versiones mintiendo (v40.16).

Decía `version: v37.0`, `active: 75` (eran 103), `total: 88` (eran 122) y
`active_groups: 34` (eran 37), y usaba `deprecated` cuando el vocabulario de
estado ya era `archived`. Nadie la miraba: los guards del tool-spec verifican
las **entradas**, no el encabezado, y el encabezado es lo que un consumidor lee
para saber contra qué contrato está.
"""

import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

SPEC = RAIZ / "vault-sandbox" / "00_System" / "tool-spec.json"
ESTADOS = {"active", "internal", "archived", "orphan"}


def _spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_la_version_del_spec_es_la_del_estandar():
    from vault_standard_upgrade import CURRENT_VERSION

    assert _spec()["version"] == CURRENT_VERSION


def test_los_conteos_de_la_cabecera_salen_de_las_entradas():
    d = _spec()
    tools = d["tools"]
    c = Counter(t.get("status", "active") for t in tools.values())
    counts = d["_counts"]

    assert counts["total"] == len(tools)
    assert counts["active"] == c["active"]
    assert counts["archived"] == c["archived"]
    assert counts["active_groups"] == len({
        t.get("group_id") for t in tools.values()
        if t.get("status", "active") == "active" and t.get("group_id")
    })


def test_la_cabecera_no_usa_vocabulario_retirado():
    """`deprecated` dejó de ser un estado: el contrato dice `archived`."""
    counts = _spec()["_counts"]
    assert "deprecated" not in counts
    for clave in counts:
        if clave in ("total", "active_groups", "schema_version"):
            continue
        assert clave in ESTADOS, f"conteo por un estado que no existe: {clave}"


def test_todo_required_arg_se_escribe_como_flag():
    """`vault_foreign_check` declaraba `root` y las otras 110 `--root`.

    La forma sin guiones no la reconoce `cli.safety.check_contract`, así que la
    tool que existe **para** la regla 7 era la única cuyo argumento obligatorio
    no se validaba.
    """
    malas = {
        nombre: t["required_args"]
        for nombre, t in _spec()["tools"].items()
        for a in (t.get("required_args") or [])
        if not a.startswith("--")
    }
    assert not malas, malas
