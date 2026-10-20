"""Tests de `vault_fix_all` — el orquestador de artefactos derivados.

Tres familias:

  1. **El plan es estable**: los pasos de `PASOS`, en orden, y cada uno es una tool que
     existe y acepta el flag que se le pide (AP-40 aplicado a la orquestación).
  2. **Dry-run no escribe**: `--dry-run` devuelve el plan sin ejecutar nada.
  3. **La ejecución real regenera**: correr `--step N` individual no rompe, y el
     conjunto devuelve `ok` con todos los pasos reportados.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_fix_all as vfa  # noqa: E402
pytestmark = pytest.mark.slow  # carril rápido (-m "not slow"): el perfil de la suite del 2026-10-20 midió aquí llamadas > 25 s



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


def _quitar_worktree(destino: Path) -> None:
    """Teardown que no convierte un trabajo bien hecho en ERROR.

    `git worktree remove --force` falla con exit 255 en Windows cuando el
    árbol tiene handles recién cerrados (Defender u otro lector escaneando):
    medido 2026-10-18 con `-n auto`, dos tests verdes morían en el `finally`.
    Reintenta, y si el registro sigue atascado poda y borra el directorio —
    un worktree colgado en `.git/worktrees` apuntando a un tmp que ya no
    existe ensuciaría la lista de worktrees del repo.
    """
    def quitar():
        return subprocess.run(
            ["git", "worktree", "remove", "--force", str(destino)],
            cwd=ROOT, capture_output=True, check=False,
        )

    intento = quitar()
    if intento.returncode != 0:
        time.sleep(1.0)
        intento = quitar()
    if intento.returncode != 0:
        shutil.rmtree(destino, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True, check=False)


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
        _quitar_worktree(destino)


def test_los_pasos_en_el_orden_canonico():
    """La lista se escribe aquí a propósito: un paso nuevo tiene que entrar en
    el orden que se decida, no colarse. Lo que no se escribe es su número —el
    «siete» de este test caducó en cuanto entró `esquemas` (AP-47)."""
    assert [p["nombre"] for p in vfa.PASOS] == [
        "tools_catalog",
        "env_table",
        "field_compat",
        "esquemas",
        "metricas",
        "arquitectura",
        "blueprint",
        "doc_counts",
        "doc_sync",
    ]


def test_cada_paso_apunta_a_un_script_que_existe():
    for paso in vfa.PASOS:
        script = ROOT / "scripts" / paso["script"]
        assert script.exists(), f"{paso['script']} no existe en scripts/"


@pytest.mark.parametrize("paso", range(1, len(vfa.PASOS) + 1))
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
    total = len(vfa.PASOS)
    assert r["steps_total"] == total
    assert r["steps_ok"] == total, [x["nombre"] for x in r["results"] if not x["ok"]]
    assert r["steps_failed"] == 0
    assert r["failed"] == []
    assert len(r["results"]) == total
