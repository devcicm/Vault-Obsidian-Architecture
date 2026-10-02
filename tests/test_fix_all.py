"""Tests de `vault_fix_all` — el orquestador de artefactos derivados.

Tres familias:

  1. **El plan es estable**: hay 7 pasos, en orden, y cada uno es una tool que
     existe y acepta el flag que se le pide (AP-40 aplicado a la orquestación).
  2. **Dry-run no escribe**: `--dry-run` devuelve el plan sin ejecutar nada.
  3. **La ejecución real regenera**: correr `--step N` individual no rompe, y el
     conjunto devuelve `ok` con todos los pasos reportados.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_fix_all as vfa  # noqa: E402


def _ficheros_de_la_copia(raiz):
    """Lo que la copia tiene que traer para probar el árbol de trabajo.

    AP-44: hasta aquí era `git ls-files`, el criterio de git —lo que ya está en
    el índice— y no el del árbol que se está probando. Un módulo nuevo sin
    `git add` faltaba en la copia, la recolección fallaba dentro de
    `doc_counts` y el test culpaba a la tool. `--others --exclude-standard`
    añade lo nuevo y sigue dejando fuera lo ignorado.
    """
    salida = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=raiz, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return sorted(set(filter(None, salida.split("\0"))))


def test_ap44_la_copia_trae_los_ficheros_nuevos_sin_los_ignorados(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    (tmp_path / ".gitignore").write_text("local/\n", encoding="utf-8")
    (tmp_path / "viejo.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".gitignore", "viejo.py")
    (tmp_path / "nuevo.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "dato.json").write_text("{}", encoding="utf-8")
    assert _ficheros_de_la_copia(tmp_path) == [".gitignore", "nuevo.py", "viejo.py"]


@pytest.fixture
def repo_temporal(tmp_path, monkeypatch):
    """AP-36/AP-44: regeneración real, sobre una copia con historia propia.

    Cambiar solo cwd no basta: el padre y los scripts resuelven su raíz por
    __file__. El worktree conserva el historial que leen los generadores;
    la superposición prueba los archivos actuales, incluidos cambios sin commit.
    Se copian los archivos del índice y los nuevos sin ignorar
    (`_ficheros_de_la_copia`), nunca lo que `.gitignore` deja fuera.
    """
    destino = (tmp_path / "repo").resolve()
    assert destino.is_relative_to(tmp_path.resolve())
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(destino), "HEAD"],
        cwd=ROOT, capture_output=True, check=True,
    )
    try:
        for relativa in _ficheros_de_la_copia(ROOT):
            origen = ROOT / relativa
            if origen.is_file():
                copia = destino / relativa
                copia.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origen, copia)
        monkeypatch.setattr(vfa, "REPO_ROOT", destino)
        monkeypatch.setenv("VAULT_ROOT", str(destino / "vault-sandbox"))
        monkeypatch.setenv("VAULT_STRICT_ROOT", "1")
        yield destino
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(destino)],
            cwd=ROOT, capture_output=True, check=True,
        )


def test_siete_pasos_en_el_orden_canonico():
    assert [p["nombre"] for p in vfa.PASOS] == [
        "tools_catalog",
        "env_table",
        "field_compat",
        "arquitectura",
        "blueprint",
        "doc_counts",
        "doc_sync",
    ]


def test_cada_paso_apunta_a_un_script_que_existe():
    for paso in vfa.PASOS:
        script = ROOT / "scripts" / paso["script"]
        assert script.exists(), f"{paso['script']} no existe en scripts/"


@pytest.mark.parametrize("paso", range(1, 8))
def test_cada_paso_individual_ejecuta_sin_romper(paso, repo_temporal):
    """Cada paso por separado debe poder ejecutarse (--step N)."""
    r = vfa.fix_all(solo_paso=paso)
    assert r["ok"], f"paso {paso} falló: {r['results'][0]}"
    assert r["steps_total"] == 1


def test_dry_run_no_ejecuta():
    r = vfa.fix_all(dry_run=True)
    assert r["dry_run"] is True
    assert r["ok"] is True
    assert len(r["plan"]) == len(vfa.PASOS)
    assert all("nombre" in p and "script" in p for p in r["plan"])


def test_el_conjunto_reporta_todos_los_pasos(repo_temporal):
    """El envelope del conjunto lista cada paso con su resultado."""
    r = vfa.fix_all()
    assert r["steps_total"] == 7
    assert r["steps_ok"] == 7, [x["nombre"] for x in r["results"] if not x["ok"]]
    assert r["steps_failed"] == 0
    assert r["failed"] == []
    assert len(r["results"]) == 7
