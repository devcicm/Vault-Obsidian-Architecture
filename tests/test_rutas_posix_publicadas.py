"""Una ruta que una tool publica lleva `/` en todas las plataformas.

Medido en v40.34 en Windows: `vault_list --folder` y `vault_merge --action
detect` devolvían `07_Knowledge\\a\\nota.md`. Ninguna otra tool del vault la
acepta de vuelta igual —`vault_read`, el grafo y los wikilinks usan `/`—, y la
misma nota tenía dos claves según qué tool la nombrara. Es la clase que ya
rompió `vault_move` y `vault_validate --folder`: `str(Path)` donde el
consumidor espera `as_posix()`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "vault"
    for sub in ("a", "b"):
        carpeta = raiz / "07_Knowledge" / sub
        carpeta.mkdir(parents=True)
        (carpeta / "nota.md").write_text(
            f"---\ntitle: nota {sub}\nstatus: draft\n---\n# nota {sub}\n", encoding="utf-8")
    return raiz


def test_vault_list_publica_rutas_con_barra(vault):
    r = _ejecutar(vault, "vault_list.py", "--folder", "07_Knowledge")
    rutas = sorted(n["path"] for n in r["notes"])
    assert rutas == ["07_Knowledge/a/nota.md", "07_Knowledge/b/nota.md"], r


def test_vault_merge_detect_publica_rutas_con_barra(vault):
    r = _ejecutar(vault, "vault_merge.py", "--action", "detect")
    rutas = sorted(p for grupo in r["duplicates"].values() for p in grupo)
    assert rutas == ["07_Knowledge/a/nota.md", "07_Knowledge/b/nota.md"], r
