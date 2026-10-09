"""K3 avisa del commit en curso sin cambiar la cifra canónica (deuda #15).

`vault_kernel` cuenta el churn con `git log`, así que la puerta que corre antes
de commitear no ve el commit que se está haciendo: el que cruza el umbral pasa
en verde y el siguiente hereda el rojo. Decidido el 2026-10-08: la cifra
canónica sigue siendo la de `git log` —la que mide la CI, después del commit—
y el índice solo sirve para **avisar** en el pre-commit.

Los tests montan un repo git de verdad en `tmp_path`: lo que se prueba es que
el índice se lee con el mismo criterio de comportamiento que la historia, no
una función con los datos ya masticados.
"""
from __future__ import annotations

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
    for m in ("nucleo", "otro"):
        (tmp_path / "scripts" / f"{m}.py").write_text(
            '"""doc."""\n\ndef f():\n    return 1\n', encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.setattr(vault_kernel, "RAIZ_REPO", tmp_path)
    return tmp_path


def _medida(churn: int, umbral: float):
    return lambda: {"kernel": ["nucleo"], "churn": {"nucleo": churn},
                    "umbral_churn": umbral, "churn_mediana_dominio": 1}


def _escribe(repo: Path, modulo: str, fuente: str) -> None:
    (repo / "scripts" / f"{modulo}.py").write_text(fuente, encoding="utf-8")
    _git(repo, "add", f"scripts/{modulo}.py")


def test_el_commit_que_cruza_el_umbral_se_avisa_antes_de_hacerse(repo, monkeypatch):
    monkeypatch.setattr(vault_kernel, "medir", _medida(churn=2, umbral=3))
    _escribe(repo, "nucleo", '"""doc."""\n\ndef f():\n    return 2\n')
    r = vault_kernel.aviso_del_indice()
    assert r["ok"] is True
    assert [a["module"] for a in r["avisos"]] == ["nucleo"]
    aviso = r["avisos"][0]
    assert (aviso["churn"], aviso["churn_tras_el_commit"], aviso["umbral_churn"]) == (2, 3, 3)


def test_un_cambio_solo_de_docstring_no_avisa(repo, monkeypatch):
    monkeypatch.setattr(vault_kernel, "medir", _medida(churn=2, umbral=3))
    _escribe(repo, "nucleo", '"""otra doc."""\n\ndef f():\n    return 1\n')
    assert vault_kernel.aviso_del_indice()["avisos"] == []


def test_un_modulo_fuera_del_kernel_no_avisa(repo, monkeypatch):
    monkeypatch.setattr(vault_kernel, "medir", _medida(churn=2, umbral=3))
    _escribe(repo, "otro", '"""doc."""\n\ndef f():\n    return 2\n')
    assert vault_kernel.aviso_del_indice()["avisos"] == []


def test_lejos_del_umbral_no_avisa(repo, monkeypatch):
    monkeypatch.setattr(vault_kernel, "medir", _medida(churn=1, umbral=3))
    _escribe(repo, "nucleo", '"""doc."""\n\ndef f():\n    return 2\n')
    assert vault_kernel.aviso_del_indice()["avisos"] == []


def test_la_cifra_canonica_no_cuenta_el_indice(repo):
    """`churn()` sigue siendo `git log`: lo stageado no entra en la medida."""
    _escribe(repo, "nucleo", '"""doc."""\n\ndef f():\n    return 2\n')
    vault_kernel._CHURN = None
    try:
        assert vault_kernel.churn("nucleo") == 1
    finally:
        vault_kernel._CHURN = None


def test_el_pre_commit_pide_el_aviso_y_no_bloquea():
    hook = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    linea = next(l for l in hook.splitlines() if "--aviso-indice" in l)
    assert "|| true" in linea, "el aviso nunca puede bloquear el commit"
