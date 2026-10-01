"""F1 — `vault_relation_add` añade la relación bajo el lock del JSON del proyecto.

Medido en v40.34: la tool leía `<proyecto>-relations.json`, añadía la relación
y reescribía el fichero entero, sin lock. Ocho altas en paralelo respondían
las ocho `ok: true` y en disco quedaban seis: la que escribía segunda lo hacía
sobre su lectura vieja y la relación de la otra desaparecía.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import problemas_de_forma  # noqa: E402


def _vault(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "06_Diagrams", "99_Index"):
        (raiz / d).mkdir(parents=True)
    (tmp_path / "cwd").mkdir()
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    return raiz, env


def _lanzar(env, cwd, origen):
    return subprocess.Popen(
        [sys.executable, str(SCRIPTS / "vault_relation_add.py"), "--project", "p",
         "--from", origen, "--to", "B", "--relation_type", "uses"],
        env=env, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _leer(p):
    salida, error = p.communicate(timeout=180)
    texto = salida.decode("utf-8", "replace")
    assert "{" in texto, error.decode("utf-8", "replace")
    return json.loads(texto[texto.index("{"):])


def _relaciones(raiz):
    fichero = next(raiz.rglob("p-relations.json"))
    return fichero, json.loads(fichero.read_text(encoding="utf-8"))["relations"]


def test_altas_en_paralelo_llegan_todas(tmp_path):
    raiz, env = _vault(tmp_path)
    n = 12
    procesos = [_lanzar(env, tmp_path / "cwd", f"A{i}") for i in range(n)]
    resultados = [_leer(p) for p in procesos]
    assert all(r["ok"] for r in resultados), resultados
    _, relaciones = _relaciones(raiz)
    perdidas = sorted({f"A{i}" for i in range(n)} - {r["fromEntity"] for r in relaciones})
    assert perdidas == [], f"relaciones perdidas con ok: true: {perdidas}"
    erd = next(raiz.rglob("p-erd.md")).read_text(encoding="utf-8")
    # Mermaid recibe los ids en minúsculas: `A3` sale como `a3 --> b`.
    assert all(f"a{i} --> b" in erd for i in range(n)), "el ERD no refleja la lista escrita"


def test_con_el_json_tomado_no_escribe_y_lo_dice(tmp_path):
    raiz, env = _vault(tmp_path)
    assert _leer(_lanzar(env, tmp_path / "cwd", "A0"))["ok"]
    fichero, _ = _relaciones(raiz)
    antes = fichero.read_text(encoding="utf-8")
    ocupado = fichero.parent / ".locks" / f"{fichero.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps({"pid": 0, "createdAt": time.time(), "token": "otro"}), encoding="utf-8")

    r = _leer(_lanzar(env, tmp_path / "cwd", "A1"))

    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert fichero.read_text(encoding="utf-8") == antes
