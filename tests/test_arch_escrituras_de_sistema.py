"""Quién escribe cada subruta de `00_System/` (deuda #3, decisión 2026-10-08).

`00_System/` lo escribían seis contextos y ningún guard decía cuál podía
escribir qué. La decisión del usuario fue un registro de subrutas: cada una
declara su contexto dueño, un contexto que escribe la de otro falla la puerta y
los cruces que ya existían arrancan en una baseline que solo encoge.

El dueño no se copia en una tabla nueva: lo declaran los `FICHERO_*` de cada
`vault/<ctx>/repositorio.py`, que `rutas_duplicadas` ya protege contra
duplicados. Solo lo que ningún repositorio declara se registra a mano, con
motivo, en `vault_arch.SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO`.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_arch  # noqa: E402


def _subrutas(fuente: str) -> set[str]:
    arbol = ast.parse(fuente)
    return {s for _, _, s in vault_arch.escrituras_de_sistema_en(arbol)}


def test_el_analizador_ve_las_formas_de_ruta_que_usa_el_repo():
    fuente = '''
from pathlib import Path
def _system_dir():
    return root / "00_System"
def a(root):
    (root / "00_System" / "norm-registry.json").write_text("x")
def b():
    atomic_write_json(_system_dir() / "tag-registry.json", {})
def c(repo):
    repo.ctx.ruta("00_System", "move-log.json").write_text("x")
def d():
    destino = _system_dir() / ".voice-counter"
    destino.write_text("1")
def e():
    "a-b".replace("-", "_")
'''
    assert _subrutas(fuente) == {
        "norm-registry.json", "tag-registry.json", "move-log.json", ".voice-counter",
    }


def test_los_duenos_salen_de_los_repositorios_y_no_se_duplican():
    duenos = vault_arch.duenos_de_sistema()
    # Derivados de `FICHERO_*`, no escritos en ninguna tabla nueva.
    assert duenos["norm-registry.json"] == "gobernanza"
    assert duenos["tag-registry.json"] == "indices"
    assert duenos["move-log.json"] == "grafo"
    # Lo que ningún repositorio declara, declarado a mano y con motivo.
    for subruta, entrada in vault_arch.SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO.items():
        assert entrada["dueno"] in vault_arch.CONTEXTS, subruta
        assert entrada["por_que"].strip(), subruta
    # AP-05: una subruta declarada a mano que ya tiene repositorio sería una copia.
    derivados = vault_arch._duenos_por_repositorio()
    assert not set(derivados) & set(vault_arch.SUBRUTAS_DE_SISTEMA_SIN_REPOSITORIO)


def test_un_contexto_que_escribe_la_subruta_de_otro_es_un_cruce():
    escrituras = [
        {"module": "vault_x", "context": "autoria", "path": "norm-registry.json", "line": 3},
        {"module": "vault_y", "context": "gobernanza", "path": "norm-registry.json", "line": 4},
        {"module": "vault_z", "context": "consulta", "path": "inventada.json", "line": 5},
    ]
    ajenas = vault_arch.escrituras_de_sistema_ajenas(escrituras)
    assert [(a["module"], a["owner"]) for a in ajenas] == [
        ("vault_x", "gobernanza"), ("vault_z", None),
    ]


def test_la_puerta_frena_un_cruce_nuevo_y_no_los_congelados(monkeypatch):
    r = vault_arch.check()
    assert r["new_system_writes"] == []
    assert r["system_writes_baseline"] >= r["system_writes_total"] > 0

    real = vault_arch.escrituras_de_sistema
    monkeypatch.setattr(vault_arch, "escrituras_de_sistema", lambda: real() + [
        {"module": "vault_intruso", "context": "consulta",
         "path": "norm-registry.json", "line": 1},
    ])
    r = vault_arch.check()
    assert r["ok"] is False
    assert r["new_system_writes"] == ["norm-registry.json <- vault_intruso"]
