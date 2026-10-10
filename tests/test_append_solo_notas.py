"""AP-46 — `vault_append` solo escribe en notas, nunca en un artefacto con dueño.

Medido como consumidor (wheel limpia, `vault run`) el 2026-10-10:
`vault_append --path 00_System/standard-version.json` respondía `ok: true` y
dejaba el JSON con datos de más; desde ese momento `vault status` y
`vault doctor` daban el runtime por inválido. Igual con `99_Index/graph.json`
y con el `index.md` de una sección, que regenera su propio escritor. La tool
solo comprobaba que la ruta estuviera dentro del vault, no que fuera una nota.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from vault_version import CURRENT_VERSION  # noqa: E402

VERSION_JSON = json.dumps({"version": CURRENT_VERSION})


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "00_System").mkdir()
    (raiz / "99_Index").mkdir()
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: nota\nstatus: draft\n---\n# nota\n", encoding="utf-8")
    (raiz / "07_Knowledge" / "index.md").write_text("# indice\n", encoding="utf-8")
    (raiz / "00_System" / "standard-version.json").write_text(
        VERSION_JSON + '\n', encoding="utf-8")
    (raiz / "99_Index" / "graph.json").write_text('{"nodes": {}}\n', encoding="utf-8")
    (raiz / "07_Knowledge" / "datos.txt").write_text("texto\n", encoding="utf-8")
    return raiz


def _append(raiz: Path, ruta: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_append.py"), "--path", ruta,
         "--content", "TEXTO AÑADIDO", "--no-timestamp"],
        env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", timeout=120)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


@pytest.mark.parametrize("ruta", [
    "00_System/standard-version.json",
    "99_Index/graph.json",
    "07_Knowledge/index.md",
    "07_Knowledge/datos.txt",
    "07_Knowledge/../99_Index/graph.json",
])
def test_append_rechaza_lo_que_no_es_una_nota(tmp_path, ruta):
    # AP-46: el artefacto derivado tiene su propio escritor.
    raiz = _vault(tmp_path)
    antes = (raiz / ruta).read_bytes()
    env = _append(raiz, ruta)
    assert env["ok"] is False, env
    assert env["error_code"] == "INVALID_PATH", env
    assert (raiz / ruta).read_bytes() == antes, "el rechazo modificó el fichero"


def test_append_a_una_nota_sigue_funcionando(tmp_path):
    raiz = _vault(tmp_path)
    env = _append(raiz, "07_Knowledge/nota.md")
    assert env["ok"] is True, env
    assert "TEXTO AÑADIDO" in (raiz / "07_Knowledge" / "nota.md").read_text(encoding="utf-8")
