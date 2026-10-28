"""El reparto en shards no pierde ni duplica tests (`tests/reparto.py`)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import reparto

RAIZ = Path(__file__).resolve().parent.parent


def test_cada_modulo_cae_en_un_solo_trozo():
    modulos = [p.stem for p in (RAIZ / "tests").glob("test_*.py")]
    for total in (1, 2, 3, 4):
        asignacion = reparto.repartir(modulos, total)
        assert set(asignacion) == set(modulos)
        assert set(asignacion.values()) <= set(range(total))


def test_el_reparto_es_determinista_y_equilibrado():
    modulos = [p.stem for p in (RAIZ / "tests").glob("test_*.py")]
    a = reparto.repartir(modulos, 2)
    assert a == reparto.repartir(list(reversed(modulos)), 2)
    pesos = reparto._pesos()
    defecto = sorted(pesos.values())[len(pesos) // 2] if pesos else 1.0
    carga = [0.0, 0.0]
    for m, k in a.items():
        carga[k] += pesos.get(m, defecto)
    assert min(carga) / max(carga) > 0.9, carga


@pytest.mark.parametrize("valor", ["0/2", "3/2", "1/0", "x/2", "2"])
def test_un_shard_mal_formado_no_se_ignora(valor):
    with pytest.raises(ValueError):
        reparto.leer_shard(valor)


def test_la_union_de_los_trozos_es_la_suite():
    """Se colecta de verdad con pytest: los dos trozos juntos dan la suite."""
    def colectar(shard):
        env = dict(__import__("os").environ)
        env.pop("VAULT_SHARD", None)
        if shard:
            env["VAULT_SHARD"] = shard
        p = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=",
             "-p", "no:cacheprovider", "tests/test_reparto.py",
             "tests/test_piso_python.py", "tests/test_ci_python_matrix.py"],
            cwd=str(RAIZ), env=env, capture_output=True, text=True, timeout=600)
        return {l for l in p.stdout.splitlines() if "::" in l}

    todo = colectar(None)
    uno, dos = colectar("1/2"), colectar("2/2")
    assert todo and uno | dos == todo and not (uno & dos)
