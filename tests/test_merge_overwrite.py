"""CIA-A / F1 — `vault_merge --conflict overwrite` no tapa una nota sin guardarla.

Medido en v40.34: con `--conflict overwrite`, la nota del vault que coincidía
en ruta con una del origen se reescribía con `atomic_write_text` sin copiar
antes la versión que tapaba a `.history/`, y sin lock: `vault_undo` no tenía
nada que devolver y un `vault_write` concurrente sobre la misma nota podía
perderse con las dos tools respondiendo `ok: true`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import problemas_de_forma  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402


def _preparar(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "07_Knowledge"):
        (raiz / d).mkdir(parents=True)
    origen = tmp_path / "origen" / "07_Knowledge"
    origen.mkdir(parents=True)
    (origen / "nota.md").write_text("---\ntitle: nueva\n---\n\ncuerpo nuevo\n", encoding="utf-8")
    nota = raiz / "07_Knowledge" / "nota.md"
    nota.write_text("---\ntitle: vieja\n---\n\ncuerpo viejo\n", encoding="utf-8")
    (tmp_path / "cwd").mkdir()
    return raiz, origen.parent, nota


def _merge(raiz, origen, cwd, conflicto):
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_merge.py"), "--source", str(origen),
         "--action", "merge", "--conflict", conflicto],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_overwrite_guarda_la_version_tapada(tmp_path):
    raiz, origen, nota = _preparar(tmp_path)

    r = _merge(raiz, origen, tmp_path / "cwd", "overwrite")

    assert r["ok"] and r["merged"] == 1, r
    assert "cuerpo nuevo" in nota.read_text(encoding="utf-8")
    # El mismo nombre que escribe `vault_write` y lee `vault_undo`.
    historial = list(raiz.glob(".history/07_Knowledge__nota-*.md"))
    assert historial, "la versión tapada no quedó en el historial"
    assert "cuerpo viejo" in historial[0].read_text(encoding="utf-8")


def test_overwrite_con_la_nota_tomada_no_escribe_y_lo_dice(tmp_path):
    raiz, origen, nota = _preparar(tmp_path)
    antes = nota.read_text(encoding="utf-8")
    ocupado = nota.parent / ".locks" / f"{nota.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")

    r = _merge(raiz, origen, tmp_path / "cwd", "overwrite")

    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert nota.read_text(encoding="utf-8") == antes


def test_skip_sigue_sin_tocar_la_nota(tmp_path):
    raiz, origen, nota = _preparar(tmp_path)
    antes = nota.read_text(encoding="utf-8")

    r = _merge(raiz, origen, tmp_path / "cwd", "skip")

    assert r["ok"] and r["skipped"] == 1 and r["merged"] == 0, r
    assert nota.read_text(encoding="utf-8") == antes
