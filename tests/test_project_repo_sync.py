"""AP-63, P4 — la relación de un proyecto con su repositorio.

Lo portable (remoto, rama, `synced_commit`, `synced_at`) va a `repo:` de la
ficha y viaja con el vault; la ruta del disco no, que es de cada máquina y
vive en `00_System/.local/`. `vault_drift_detect --mode snapshot` y
`vault_code_sync` limpio anotan el commit; `vault_project --sync-status` dice
cuántos commits lleva el repo por delante del vault. Con el repo enlazado,
`--project` basta: `--path` deja de ser obligatorio.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel import proyectos  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="sin git")


def _cli(vault: Path, script: str, *args: str):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=180,
    )
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(repo),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.strip()


def _commit(repo: Path, fichero: str, texto: str) -> str:
    (repo / fichero).write_text(texto, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"cambia {fichero}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def entorno(tmp_path):
    vault = tmp_path / "vault"
    (vault / "00_System").mkdir(parents=True)
    assert _cli(vault, "vault_project.py", "--add", "mi-api", "--alias", "Mi API")[1]["ok"]
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "origin", "git@example.com:org/mi-api.git")
    _commit(repo, "app.py", "# @vault: 11_Code/mi-api/app — modulo\nprint(1)\n")
    return vault, repo


def _ficha(vault: Path) -> dict:
    texto = (vault / "01_Projects" / "mi-api" / "project.md").read_text(encoding="utf-8")
    return yaml.safe_load(texto.split("---")[1])


def test_ap63_link_guarda_lo_portable_en_la_ficha_y_la_ruta_fuera(entorno):
    vault, repo = entorno
    codigo, r = _cli(vault, "vault_project.py", "--link", "Mi API", "--path", str(repo))
    assert codigo == 0 and r["ok"], r
    fm = _ficha(vault)
    assert fm["repo"] == {"remote": "git@example.com:org/mi-api.git", "default_branch": "main"}
    # La ruta del disco no viaja con la ficha: es de esta máquina.
    # `default=str`: la ficha lleva fechas desde v40.35, y YAML las carga como datetime.
    assert str(repo) not in json.dumps(fm, default=str) and repo.name not in json.dumps(fm["repo"])
    assert proyectos.ruta_local(vault, "mi-api") == repo.resolve()


def test_ap63_sin_enlace_ni_path_drift_lo_pide_y_no_escribe(entorno):
    vault, _repo = entorno
    codigo, r = _cli(vault, "vault_drift_detect.py", "--project", "mi-api", "--mode", "snapshot")
    assert codigo == 1 and r["error_code"] == "MISSING_REQUIRED_ARG", r
    assert "--link" in r["recovery"]["hint"]
    assert "repo" not in _ficha(vault)


def test_ap63_snapshot_sin_path_anota_el_commit_y_sync_status_lo_compara(entorno):
    vault, repo = entorno
    _cli(vault, "vault_project.py", "--link", "mi-api", "--path", str(repo))

    codigo, r = _cli(vault, "vault_project.py", "--sync-status", "mi-api")
    assert codigo == 0 and r["state"] == "never_synced", r

    head = _git(repo, "rev-parse", "HEAD")
    codigo, r = _cli(vault, "vault_drift_detect.py", "--project", "Mi API", "--mode", "snapshot")
    assert codigo == 0 and r["git_commit"] == head, r
    assert _ficha(vault)["repo"]["synced_commit"] == head

    codigo, r = _cli(vault, "vault_project.py", "--sync-status", "mi-api")
    assert r["state"] == "in_sync" and r["pending_commits"] == 0, r

    _commit(repo, "b.py", "x = 2\n")
    codigo, r = _cli(vault, "vault_project.py", "--sync-status", "Mi API")
    assert r["state"] == "behind" and r["pending_commits"] == 1, r
    assert r["pending"][0].endswith("cambia b.py")


def test_ap63_code_sync_limpio_anota_el_commit_y_resuelve_contra_el_repo(entorno):
    vault, repo = entorno
    _cli(vault, "vault_project.py", "--link", "mi-api", "--path", str(repo))
    nota = vault / "11_Code" / "mi-api" / "app.md"
    nota.parent.mkdir(parents=True)
    nota.write_text("---\ntitle: app\nproject: mi-api\nsource_file: app.py\n---\n\n# app\n",
                    encoding="utf-8")

    codigo, r = _cli(vault, "vault_code_sync.py", "--project", "mi-api", "--dry-run")
    assert r["status"] == "clean" and r["summary"]["complete"] == 1, r
    assert r["synced_commit_recorded"] is None and "synced_commit" not in _ficha(vault)["repo"]

    codigo, r = _cli(vault, "vault_code_sync.py", "--project", "mi-api")
    head = _git(repo, "rev-parse", "HEAD")
    assert r["synced_commit_recorded"]["commit"] == head, r
    assert _ficha(vault)["repo"]["synced_commit"] == head
    # La ficha y la cascada de índices que dispara: AP-37 ve el trabajo.
    assert r["written"] >= 1, r


def test_ap63_anotar_repo_no_funda_proyectos(tmp_path):
    assert proyectos.anotar_repo(tmp_path, "nadie", synced_commit="abc") is None
    assert not (tmp_path / "01_Projects").exists()
    with pytest.raises(ValueError):
        proyectos.anotar_repo(tmp_path, "nadie", ruta="C:/x")
