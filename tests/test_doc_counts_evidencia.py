"""AP-52: si la suite no se puede contar, el error dice por qué.

`count_tests` lanzaba «no se pudo contar la suite» y descartaba lo que pytest
había escrito. Pasó en esta rama: la copia de `test_fix_all` no traía un
fichero nuevo, la recolección falló con un `ModuleNotFoundError` y el envelope
solo decía que no había cifra. La causa hubo que reproducirla a mano.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_doc_counts as DC  # noqa: E402


def _falla(monkeypatch, stdout, stderr, rc=2):
    proc = subprocess.CompletedProcess(["pytest"], rc, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(DC.vault_subproceso, "ejecutar", lambda *a, **k: proc)


def test_ap52_el_error_de_recoleccion_lleva_su_evidencia(monkeypatch):
    _falla(monkeypatch,
           "ERROR tests/test_x.py\n!!! Interrupted: 1 error during collection !!!\n",
           "E   ModuleNotFoundError: No module named 'vault.grafo.lectura'\n")
    try:
        DC.count_tests()
    except RuntimeError as exc:
        mensaje = str(exc)
    else:
        raise AssertionError("una recolección rota no puede dar cifra")
    assert "ModuleNotFoundError" in mensaje and "vault.grafo.lectura" in mensaje
    assert "salió con 2" in mensaje


def test_ap52_la_evidencia_sobrevive_al_recorte_del_informe(monkeypatch):
    _falla(monkeypatch, "x" * 2000 + "\n", "E   ImportError: rota\n")
    resultado = DC.scan(docs=[], include_slow=True)
    [error] = [e for e in resultado["errors"] if e["fact"] == "tests"]
    assert "ImportError: rota" in error["error"]
