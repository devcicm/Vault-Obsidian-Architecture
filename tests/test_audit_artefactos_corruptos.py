"""AP-37 — `vault_audit` no da por sano un vault con sus artefactos JSON rotos.

Medido como consumidor el 2026-10-10: con `00_System/standard-version.json` y
`99_Index/graph.json` corruptos (texto añadido tras el JSON), `vault_audit`
respondía `ok: true, healthIndex: 95` y `degraded: []`, mientras `vault status`
daba el runtime por inválido. Cada lectura de artefacto hacía
`except ...: pass`/`return None`, así que el fallo contaba como éxito.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from vault_version import CURRENT_VERSION  # noqa: E402

VERSION_JSON = json.dumps({"version": CURRENT_VERSION})


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge", "99_Index"):
        (raiz / s).mkdir(parents=True)
    (raiz / "07_Knowledge" / "nota.md").write_text(
        "---\ntitle: nota\nstatus: draft\ntype: knowledge\n---\n# nota\n\ntexto\n",
        encoding="utf-8")
    return raiz


def _audit(raiz: Path) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_audit.py")],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):])


def test_audit_declara_los_artefactos_json_corruptos(tmp_path):
    # AP-37: el artefacto ilegible va a `degraded`, no se cuenta como sano.
    raiz = _vault(tmp_path)
    (raiz / "00_System" / "standard-version.json").write_text(
        VERSION_JSON + '\nTEXTO AÑADIDO\n', encoding="utf-8")
    (raiz / "99_Index" / "graph.json").write_text(
        '{"nodes": {}}\nTEXTO AÑADIDO\n', encoding="utf-8")
    env = _audit(raiz)
    rotos = {d["path"] for d in env["degraded"]}
    assert "00_System/standard-version.json" in rotos, env["degraded"]
    assert "99_Index/graph.json" in rotos, env["degraded"]


def test_audit_sin_artefactos_o_con_artefactos_validos_no_degrada(tmp_path):
    raiz = _vault(tmp_path)
    assert _audit(raiz)["degraded"] == []
    (raiz / "00_System" / "standard-version.json").write_text(
        VERSION_JSON + '\n', encoding="utf-8")
    (raiz / "99_Index" / "graph.json").write_text('{"nodes": {}}\n', encoding="utf-8")
    assert _audit(raiz)["degraded"] == []
