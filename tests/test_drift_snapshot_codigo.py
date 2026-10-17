"""AP-52 — `vault_drift_detect` sin snapshot previo lleva la pista que lo crea.

Medido el 2026-10-07 siguiendo el paso de cierre del protocolo de sesión: con
el proyecto registrado y enlazado a un repo sin git, `--mode report` devolvía
`INDEX_NOT_FOUND`, cuya recuperación es `vault_reindex --graph`. Seguirla al pie
de la letra reconstruía la búsqueda y el grafo y dejaba el drift igual: lo que
faltaba era el snapshot del repo, que solo crea `--mode snapshot`. Además el
campo `hint` llevaba la ruta absoluta del repo, que el envelope no debe sacar
(S4).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


def _tool(raiz: Path, script: str, *argv: str):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return p.returncode, json.loads(salida[salida.index("{"):]), salida


def _proyecto_enlazado(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    raiz.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    assert _tool(raiz, "vault_project", "--add", "demo")[1]["ok"] is True
    assert _tool(raiz, "vault_project", "--link", "demo", "--path", str(repo))[1]["ok"] is True
    return raiz


def test_ap52_sin_snapshot_la_recuperacion_lo_crea(tmp_path):
    raiz = _proyecto_enlazado(tmp_path)
    rc, r, _ = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "report")
    assert rc == 1 and r["ok"] is False
    assert r["error_code"] == "DRIFT_SNAPSHOT_MISSING", r

    rec = r["recovery"]
    catalogo = ERROR_CATALOG["DRIFT_SNAPSHOT_MISSING"]["recovery"]
    assert (rec["action"], rec["tool"]) == (catalogo["action"], catalogo["tool"]), rec
    args = [a.replace("<project>", "demo") for a in rec["args"]]
    assert _tool(raiz, rec["tool"], *args)[1]["ok"] is True

    rc, r, _ = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "report")
    assert rc == 0 and r["ok"] is True, r


def test_s4_el_envelope_no_saca_la_ruta_del_repo(tmp_path):
    raiz = _proyecto_enlazado(tmp_path)
    _, r, salida = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "report")
    assert r["ok"] is False
    repo = str(tmp_path / "repo")
    assert repo not in salida and json.dumps(repo)[1:-1] not in salida, r["hint"]
    assert "--mode snapshot" in r["hint"], "el campo estable se conserva"


def test_ap37_el_snapshot_dice_que_escribio(tmp_path):
    """AP-37, medido por `vault_noop_audit --ejecutado` (2026-10-17): el
    snapshot escribe `00_System/.session-snapshot.json` y el envelope no
    llevaba ningún indicador de trabajo, igual que uno que no hubiera escrito."""
    raiz = _proyecto_enlazado(tmp_path)
    rc, r, _ = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "snapshot")
    assert rc == 0 and r["ok"] is True, r
    assert r["written"] is True, r
    assert (raiz / "00_System" / ".session-snapshot.json").is_file()
