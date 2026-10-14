"""AP-37 — `vault_diagram_export` sin argumentos decía que había guardado.

Sin `--config`, `--path` ni `--project` la tool solo lee la configuración
vigente (`load_config`), pero en modo texto imprimía «Configuración guardada:
<fichero>» —el mismo mensaje que `--config`— aunque no escribiera nada y el
fichero ni existiera. Un agente lo leía como trabajo hecho. Lo encontró el
barrido de tools instaladas sin argumentos el 2026-10-14.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _texto(raiz: Path, *argv: str) -> str:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_diagram_export.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(raiz), timeout=120,
    )
    assert p.returncode == 0, p.stderr
    return p.stdout


def _vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "v"
    for d in ("00_System", "06_Diagrams", "99_Index"):
        (raiz / d).mkdir(parents=True)
    return raiz


def test_ap37_sin_argumentos_lee_y_no_dice_que_guardo(tmp_path):
    raiz = _vault(tmp_path)
    antes = sorted(p.relative_to(raiz) for p in raiz.rglob("*"))
    salida = _texto(raiz)
    assert "guardada" not in salida.lower(), salida
    assert sorted(p.relative_to(raiz) for p in raiz.rglob("*")) == antes


def test_ap37_con_config_si_guarda_y_lo_dice(tmp_path):
    raiz = _vault(tmp_path)
    salida = _texto(raiz, "--config", "--zoom", "1.5")
    assert "guardada" in salida.lower(), salida
