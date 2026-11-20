"""The drift report tells a stale note from a missing one (brownfield BF-08, BF-09).

Measured on 2026-11-19 comparing two states of this repository: every changed
file whose module note already existed (`source_file:`) came out "undocumented"
with the suggestion to create a module note, so following it duplicated the
note; and 105 changed test files each got a `vault_code_module` suggestion. A
changed file with an older note is now `stale` (update that note); test files
are grouped in `tests_changed` with one suggestion for the test inventory.
"""

import pytest

from apoyo import correr_tool, entorno, escribir_nota, git_en
from test_onboard_escalonado import _commit, _escribir


@pytest.fixture()
def escenario(tmp_path):
    repo = tmp_path / "repo"
    _escribir(repo, "src/app.py", "def main():\n    return 1\n")
    _escribir(repo, "tests/test_app.py", "def test_main():\n    assert True\n")
    git_en(repo, "init", "-b", "main", check=True)
    git_en(repo, "config", "user.email", "t@example.com", check=True)
    git_en(repo, "config", "user.name", "Tester", check=True)
    _commit(repo, "feat: first version", "2026-01-10")

    v = tmp_path / "vault"
    v.mkdir()
    env = entorno(v, VAULT_TOOL_TIMEOUT="600")
    assert correr_tool("vault_init", "--no-audit", env=env, timeout=600).codigo == 0
    r = correr_tool("vault_project", "--add", "demo", "--title", "Demo", env=env)
    assert r.envelope.get("ok"), r.stdout + r.stderr
    escribir_nota(v, "11_Code/demo/app.md",
                  {"title": "app", "type": "code", "status": "draft", "project": "demo",
                   "source_file": "src/app.py", "updatedAt": "2026-01-10T10:00:00.000Z"},
                  "# app\n\nEl punto de entrada de la API de prueba del escenario.\n")
    assert correr_tool("vault_reindex", env=env).envelope.get("ok")
    snap = correr_tool("vault_drift_detect", "--project", "demo", "--path", repo,
                       "--mode", "snapshot", env=env)
    assert snap.envelope.get("ok"), snap.stdout + snap.stderr

    _escribir(repo, "src/app.py", "def main():\n    return 2\n")
    _escribir(repo, "src/nuevo.py", "VALOR = 1\n")
    _escribir(repo, "tests/test_app.py", "def test_main():\n    assert 1 == 1\n")
    _commit(repo, "feat: second version", "2026-02-10")
    r = correr_tool("vault_drift_detect", "--project", "demo", "--path", repo,
                    "--mode", "report", env=env)
    assert r.envelope.get("ok"), r.stdout + r.stderr
    return r.envelope


def test_un_fichero_con_nota_antigua_es_stale_y_apunta_a_esa_nota(escenario):
    stale = {e["file"]: e for e in escenario.get("stale", [])}
    assert stale.get("src/app.py", {}).get("vault_path") == "11_Code/demo/app.md", escenario
    assert "src/app.py" not in [e["file"] for e in escenario["undocumented"]]
    assert escenario["summary"]["stale"] == 1


def test_un_fichero_sin_nota_sigue_siendo_undocumented(escenario):
    assert "src/nuevo.py" in [e["file"] for e in escenario["undocumented"]]


def test_los_tests_se_agrupan_en_vez_de_pedir_una_nota_cada_uno(escenario):
    assert "tests/test_app.py" not in [e["file"] for e in escenario["undocumented"]]
    assert escenario["tests_changed"]["files"] == ["tests/test_app.py"]
    assert "vault_test_save" in escenario["tests_changed"]["suggestion"]
