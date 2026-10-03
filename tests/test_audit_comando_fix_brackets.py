"""El comando que vault_audit sugiere para AP-22/AP-24 se puede ejecutar (AP-44).

Medido 2026-10-02: la acción sugerida era
`python scripts/vault_fix_brackets.py --apply <ruta>`, con la ruta como
posicional y sin comillas. vault_fix_brackets no tiene posicional: argparse
respondía «unrecognized arguments» y el agente que seguía la receta no
arreglaba nada. Se mide ejecutando el comando tal como sale del informe.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402


def test_ap22_el_comando_sugerido_arregla_la_nota(tmp_path):
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "07_Knowledge", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    nota = root / "07_Knowledge" / "con espacio.md"
    nota.write_text("---\ntitle: n\ntype: knowledge\n---\n\nver [[]] aquí\n", encoding="utf-8")
    vault_io.set_vault_root(root)

    acciones = [a for a in va.vault_audit().get("nextActions", [])
                if a.get("category") == "malformed_wikilink"]
    assert acciones, "el audit no sugirió nada para [[]]"
    argv = shlex.split(acciones[0]["command"])
    assert argv[:2] == ["python", "scripts/vault_fix_brackets.py"]
    argv = [sys.executable, str(ROOT / argv[1]), *argv[2:]]

    env = dict(os.environ, VAULT_ROOT=str(root), PYTHONIOENCODING="utf-8")
    p = subprocess.run(argv, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert p.returncode == 0, p.stderr[-300:]
    r = json.loads(p.stdout)
    assert r["files_modified"] == ["07_Knowledge/con espacio.md"]
    assert "[[]]" not in nota.read_text(encoding="utf-8")
