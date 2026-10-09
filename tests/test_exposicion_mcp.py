"""La exposición en MCP se deriva de la capacidad, no de una lista a mano.

Medido en v41.2: `vault_mcp_catalog` ocultaba a MCP los grupos
`{"Normas", "meta"}` escritos a mano. «Normas» es el grupo 35, el único de la
capacidad «gobernanza del estándar»; «meta» no es un grupo de `GROUPS` —solo
aparece como `group` de seis tools `internal` del tool-spec, que ya se ocultan
por su status—, así que la cita no excluía nada y nadie lo veía. Ahora el
conjunto sale de `CAPACIDADES['gobernanza_del_estandar']`, y la cita retirada
queda anotada con su `superseded_by` (no-derogación).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for p in (str(SCRIPTS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import vault_mcp_catalog as cat  # noqa: E402
import vault_servicio as srv  # noqa: E402
from vault.meta_toolkit.capacidades import CAPACIDADES  # noqa: E402


def test_los_grupos_no_expuestos_salen_de_la_gobernanza_del_estandar():
    mapa = cat.mapa_de_grupos()
    ids = set(CAPACIDADES["gobernanza_del_estandar"]["grupos"])
    esperados = {d["name"] for d in mapa.values() if d["id"] in ids}
    assert set(cat.grupos_no_expuestos()) == esperados
    assert "Normas" in esperados


def test_todo_grupo_no_expuesto_existe_y_esta_clasificado():
    mapa = cat.mapa_de_grupos()
    clasificados = {g for d in CAPACIDADES.values() for g in d["grupos"]}
    id_por_nombre = {d["name"]: d["id"] for d in mapa.values()}
    for grupo in cat.grupos_no_expuestos():
        assert grupo in cat.GROUPS, grupo
        assert id_por_nombre[grupo] in clasificados, grupo


def test_la_cita_del_grupo_meta_queda_anotada_y_no_se_usa():
    assert "meta" not in cat.grupos_no_expuestos()
    retirada = cat.GRUPOS_NO_EXPUESTOS_RETIRADOS["meta"]
    assert retirada["superseded_by"] and retirada["why"]


def test_vault_servicio_sigue_publicando_la_misma_capacidad():
    assert srv.CAPACIDADES is CAPACIDADES


def test_los_dos_catalogos_json_exponen_lo_derivado():
    ocultos = set(cat.grupos_no_expuestos())
    for ruta in (ROOT / "mcp" / "nodejs" / "tools-catalog.json",
                 ROOT / "vault" / "meta_toolkit" / "tools-catalog.json"):
        tools = json.loads(ruta.read_text(encoding="utf-8"))["tools"]
        for nombre, t in tools.items():
            if t["group"] in ocultos:
                assert t["exposed_via_mcp"] is False, (ruta.name, nombre)
