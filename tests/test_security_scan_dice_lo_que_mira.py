"""`vault_security_scan` dice cuánto miró, no cuánto encontró.

Medido el 2026-10-17 al leer por qué el banco de AP-37 la daba «sin
escritura»: `filesScanned` era `len(results)`, y `scan_directory` solo añade a
`results` los ficheros con hallazgos. Diez ficheros limpios salían como «0
archivos escaneados — Riesgo: BAJO», igual que una ruta sin un solo fichero de
código: la tool que existe para dar confianza no distinguía «limpio» de «no
miré nada» (AP-60).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_io  # noqa: E402


@pytest.fixture
def scan(tmp_path):
    import vault_security_scan

    anterior = vault_io.get_vault_root()
    vault = tmp_path / "vault"
    vault.mkdir()
    vault_io.set_vault_root(vault)
    yield vault_security_scan, tmp_path
    vault_io.set_vault_root(anterior)


def test_cuenta_los_ficheros_limpios_que_escaneo(scan):
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    for i in range(3):
        (codigo / f"limpio_{i}.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    r = tool.vault_security_scan(str(codigo), save_findings=False)
    assert r["ok"] is True, r
    assert r["filesScanned"] == 3, r
    assert r["filesWithFindings"] == 0, r
    assert r["summary"].startswith("3 archivos escaneados"), r["summary"]


def test_separa_los_ficheros_con_hallazgos(scan):
    tool, tmp = scan
    codigo = tmp / "src"
    codigo.mkdir()
    (codigo / "limpio.py").write_text("x = 1\n", encoding="utf-8")
    (codigo / "sucio.py").write_text("import os\nos.system(input())\n", encoding="utf-8")
    r = tool.vault_security_scan(str(codigo), save_findings=False)
    assert r["filesScanned"] == 2, r
    assert r["filesWithFindings"] == (1 if r["totalFindings"] else 0), r
