"""K3 no paga la historia entera en cada ejecución.

Auditoría del 2026-10-15: `_churn_de_comportamiento` parseaba las ~2.400
versiones históricas de `scripts/` en cada `vault_kernel --check` —12,7 s de
13,8—, y el coste crecía con cada commit aunque el trabajo nuevo fuese uno.
La huella de un blob no cambia nunca: el blob es inmutable y la huella pura.
Se guarda en el directorio de git, que no se versiona, por id de blob, con la
clave del algoritmo y de la versión de Python —`ast.dump` cambia entre
versiones—.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_kernel  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "scripts").mkdir()
    for i in range(4):
        (tmp_path / "scripts" / "m.py").write_text(f"def f():\n    return {i}\n",
                                                   encoding="utf-8")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-q", "-m", f"c{i}")
    monkeypatch.setattr(vault_kernel, "RAIZ_REPO", tmp_path)
    return tmp_path


@pytest.fixture
def contador(monkeypatch):
    """Cuenta huellas calculadas, en serie para que el espía se vea."""
    llamadas = []
    real = vault_kernel.huella_de_comportamiento
    def espia(fuente):
        llamadas.append(1)
        return real(fuente)
    monkeypatch.setattr(vault_kernel, "huella_de_comportamiento", espia)
    import concurrent.futures
    def sin_pool(*a, **k):
        raise OSError("en serie para el test")
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", sin_pool)
    return llamadas


def test_la_segunda_medida_no_recalcula_ninguna_huella(repo, contador):
    primera = vault_kernel._churn_de_comportamiento()
    n = len(contador)
    assert n >= 4
    segunda = vault_kernel._churn_de_comportamiento()
    assert segunda == primera == {"m": 4}
    assert len(contador) == n, "la segunda medida recalculó huellas ya conocidas"


def test_un_commit_nuevo_solo_calcula_lo_nuevo(repo, contador):
    vault_kernel._churn_de_comportamiento()
    n = len(contador)
    (repo / "scripts" / "m.py").write_text("def f():\n    return 99\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "nuevo")
    assert vault_kernel._churn_de_comportamiento() == {"m": 5}
    assert len(contador) - n == 1


def test_una_cache_de_otro_algoritmo_no_se_usa(repo, contador):
    """Si cambia la huella o el intérprete, lo guardado no vale: se recalcula."""
    vault_kernel._churn_de_comportamiento()
    ruta = vault_kernel._ruta_huellas()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["clave"] = "otra"
    datos["huellas"] = {b: "falsa" for b in datos["huellas"]}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    n = len(contador)
    assert vault_kernel._churn_de_comportamiento() == {"m": 4}
    assert len(contador) > n


def test_una_cache_ilegible_se_recalcula_sin_cambiar_la_cifra(repo, contador):
    vault_kernel._churn_de_comportamiento()
    vault_kernel._ruta_huellas().write_text("{roto", encoding="utf-8")
    assert vault_kernel._churn_de_comportamiento() == {"m": 4}


def test_la_cache_no_vive_en_el_arbol_versionado(repo):
    ruta = vault_kernel._ruta_huellas()
    assert ruta is not None
    git_dir = (repo / ".git").resolve()
    assert git_dir in ruta.resolve().parents
