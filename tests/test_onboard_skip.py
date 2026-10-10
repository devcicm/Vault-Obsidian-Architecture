"""`vault_onboard --skip` rechaza un valor que no omite nada.

Medido el 2026-10-05: la skill `vault-onboard` enseñaba `--skip 07_Knowledge`,
y el script compara con el código de dos cifras (`"07" not in skip`). El valor
se aceptaba, no omitía nada y el envelope no lo decía: el agente creía haber
dejado la sección para escribirla a mano y la encontraba poblada (AP-37).
"""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_onboard  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def test_un_valor_que_no_omite_nada_se_rechaza():
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_onboard.py"), "--project", "p",
         "--path", ".", "--skip", "07_Knowledge", "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert p.returncode == 2, p.stdout[-400:]
    assert "07_Knowledge" in p.stderr


def test_las_secciones_omitibles_son_las_que_el_onboard_comprueba():
    """La lista de `choices` y los `if "NN" not in skip` no pueden divergir."""
    arbol = ast.parse(gi.codigo_de(SCRIPTS / "vault_onboard.py").read_text(encoding="utf-8"))
    comprobadas = {
        n.left.value for n in ast.walk(arbol)
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Constant)
        and isinstance(n.ops[0], ast.NotIn)
        and isinstance(n.comparators[0], ast.Name) and n.comparators[0].id == "skip"
    }
    assert set(vault_onboard.SECCIONES_OMITIBLES) == comprobadas
