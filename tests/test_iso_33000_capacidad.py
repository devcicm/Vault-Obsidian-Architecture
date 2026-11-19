"""ISO/IEC 33000 (successor of ISO/IEC 15504, SPICE): capability per process.

An assessment by competent assessors (ISO/IEC 33002) is the organization's act.
What the vault keeps is its record: a note in `19_Audits/runs` written with
`vault_write`, declaring `process_capability: {<12207 process>: <0-5>}` on the
ISO/IEC 33020 scale. `vault_audit --procesos-iso` validates it and reports the
latest level per process.
"""

import json

import pytest

from apoyo import correr_tool, escribir_nota
from vault.kernel.normativa import procesos_iso as pi

CUERPO = """
## Alcance
Procesos evaluados del proyecto demo.
## Resultado
Niveles asignados por el equipo evaluador.
"""


@pytest.fixture
def vault(tmp_path):
    assert correr_tool("vault_init", vault=tmp_path).codigo == 0
    return tmp_path


def _evaluacion(vault, titulo, meta):
    r = correr_tool(
        "vault_write", "--folder", "19_Audits/runs", "--title", titulo,
        "--agent", "qa", "--tags", "evaluacion", "--content", CUERPO,
        "--meta", json.dumps(meta), vault=vault,
    )
    assert r.codigo == 0, r.stdout[-600:]
    return r.envelope["path"]


def _capacidad(vault):
    r = correr_tool("vault_audit", "--procesos-iso", vault=vault)
    assert r.codigo == 0
    filas = {f["id"]: f["capacidad"] for f in r.envelope["procesos_12207"]["entradas"]}
    return r.envelope, filas


def test_iso_33000_levels_follow_the_33020_scale():
    assert [(n, en) for n, _es, en in pi.NIVELES_CAPACIDAD] == [
        (0, "incomplete"), (1, "performed"), (2, "managed"),
        (3, "established"), (4, "predictable"), (5, "innovating"),
    ]
    assert pi.nombre_de_nivel(5) == "innovating" and pi.nombre_de_nivel(6) is None


@pytest.mark.parametrize("valor, problema", [
    ({}, "non-empty mapping"),
    ([2], "non-empty mapping"),
    ({"6.9.9": 1}, "unknown 12207 process: 6.9.9"),
    ({"6.4.3": 6}, "invalid capability level for 6.4.3: 6"),
    ({"6.4.3": True}, "invalid capability level for 6.4.3: True"),
    ({"6.4.3": "2"}, "invalid capability level for 6.4.3: '2'"),
])
def test_iso_33000_invalid_capability_values_are_named(valor, problema):
    assert any(problema in p for p in pi.validar_capacidad(valor))


def test_iso_33000_valid_capability_has_no_problems():
    assert pi.validar_capacidad({"6.4.3": 0, "6.4.14": 5}) == []


def test_iso_33000_assessment_record_reports_level_per_process(vault):
    ruta = _evaluacion(vault, "Evaluacion 2026", {
        "process_capability": {"6.4.3": 2, "6.4.9": 3},
        "assessment_method": "ISO/IEC 33020:2019", "assessor": "QA lead",
        "assessed_at": "2026-11-01",
    })
    e, filas = _capacidad(vault)
    assert filas["6.4.3"] == {
        "nivel": 2, "nombre": "managed", "fuente": ruta,
        "assessment_method": "ISO/IEC 33020:2019", "assessor": "QA lead",
        "assessed_at": "2026-11-01",
    }
    assert filas["6.4.9"]["nivel"] == 3 and filas["6.4.9"]["nombre"] == "established"
    assert filas["6.4.4"] is None
    assert e["evaluaciones"] == 1 and e["procesos_12207"]["evaluados"] == 2
    assert e["evaluaciones_invalidas"] == []


def test_iso_33000_latest_assessment_wins_and_older_is_kept(vault):
    vieja = _evaluacion(vault, "Evaluacion 2025", {
        "process_capability": {"6.4.3": 1, "6.3.4": 2}, "assessed_at": "2025-05-01"})
    nueva = _evaluacion(vault, "Evaluacion 2026", {
        "process_capability": {"6.4.3": 3}, "assessed_at": "2026-05-01"})
    e, filas = _capacidad(vault)
    assert filas["6.4.3"]["nivel"] == 3 and filas["6.4.3"]["fuente"] == nueva
    assert filas["6.3.4"]["nivel"] == 2 and filas["6.3.4"]["fuente"] == vieja
    assert (vault / vieja).is_file() and e["evaluaciones"] == 2


def test_iso_33000_invalid_record_is_listed_and_contributes_nothing(vault):
    escribir_nota(vault, "19_Audits/runs/mala.md", {
        "title": "Mala", "type": "audit", "process_capability": {"6.4.3": 9, "7.1": 1},
    }, CUERPO)
    e, filas = _capacidad(vault)
    assert filas["6.4.3"] is None and e["evaluaciones"] == 0
    assert e["evaluaciones_invalidas"] == [{
        "path": "19_Audits/runs/mala.md",
        "problemas": [
            "invalid capability level for 6.4.3: 9 (expected 0-5)",
            "unknown 12207 process: 7.1",
        ],
    }]
    assert "1 evaluaciones inválidas" in e["summary"]
