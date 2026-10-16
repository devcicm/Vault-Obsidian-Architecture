"""AP-52 — un `ok: True` que se vuelve error a mano sale del contrato.

El detector de AP-52 solo miraba literales `{"ok": False, "error": …}`. Dos
tools construían primero el resultado bueno y, al fallar, le cambiaban
`result["ok"] = False` y le colgaban `result["error"]`: un envelope sin
`error_code` ni `recovery` que el agente no puede despachar. Medido en la
auditoría del 2026-10-15: `vault_diagram_export.export_diagram` (nota sin
diagrama) y `vault_init.vault_init` (VAULT_ROOT inexistente).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def test_ap52_diagrama_ausente_sale_con_codigo(tmp_path):
    raiz = tmp_path / "v"
    for d in ("00_System", "06_Diagrams", "99_Index"):
        (raiz / d).mkdir(parents=True)
    (raiz / "06_Diagrams" / "sin.md").write_text("# sin diagrama\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_diagram_export.py"),
         "--path", "06_Diagrams/sin.md", "--json"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(raiz), timeout=120,
    )
    assert p.returncode == 1, p.stdout + p.stderr
    envelope = json.loads(p.stdout)
    assert envelope["ok"] is False
    assert envelope["error_code"] == "DIAGRAM_NOT_FOUND"
    assert envelope["recovery"]["hint"]


def test_ap52_init_sin_raiz_sale_con_codigo(tmp_path):
    import vault_io
    import vault_init

    anterior = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path / "no-existe")
    try:
        envelope = vault_init.vault_init(run_audit=False)
    finally:
        vault_io.set_vault_root(anterior)
    assert envelope["ok"] is False
    assert envelope["error_code"] == "VAULT_NOT_FOUND"
    assert not (tmp_path / "no-existe").exists()
