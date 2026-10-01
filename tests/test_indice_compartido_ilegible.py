"""CIA-I — un índice compartido ilegible no se cede vacío.

`vault_io.indice_compartido` es la entrada de nueve `*_save` a su índice, y
tres de ellos son además el contador del correlativo. Hasta v40.34 trataba un
JSON que no se podía parsear igual que uno ausente: cedía el índice vacío y el
guardado lo reescribía con una sola entrada. Medido: una coma de más en
`.bugs-index.json` y el bug siguiente salía como `BUG-001` —el id de otra nota
que seguía en disco—, el índice perdía las dos entradas anteriores y la tool
respondía `ok: true`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from vault.kernel import fallos  # noqa: E402
from vault.kernel.errores import problemas_de_forma  # noqa: E402
import vault_errors  # noqa: E402
import vault_io  # noqa: E402


def test_un_indice_ilegible_levanta_y_no_se_reescribe(tmp_path):
    indice = tmp_path / ".x-index.json"
    roto = '{"bugs": [{"id": "BUG-001"},]}'
    indice.write_text(roto, encoding="utf-8")
    with pytest.raises(vault_io.IndiceIlegible) as info:
        with vault_io.indice_compartido(indice, {"bugs": []}) as datos:
            datos["bugs"].append({"id": "BUG-001"})
    assert indice.read_text(encoding="utf-8") == roto
    assert info.value.causa in fallos.CAUSAS
    assert vault_errors.MAPA_DE_FALLOS[info.value.causa] == "DATA_FILE_CORRUPT"


def test_un_indice_ausente_sigue_siendo_vacio(tmp_path):
    indice = tmp_path / ".x-index.json"
    with vault_io.indice_compartido(indice, {"bugs": []}) as datos:
        assert datos == {"bugs": []}
        datos["bugs"].append({"id": "BUG-001"})
    assert json.loads(indice.read_text(encoding="utf-8")) == {"bugs": [{"id": "BUG-001"}]}


def _bug(raiz: Path, cwd: Path, titulo: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_bug_save.py"), "--project", "p",
         "--title", titulo, "--symptom", f"sintoma observable de {titulo}"],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=120,
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def test_bug_save_con_el_indice_roto_no_reutiliza_ids(tmp_path):
    raiz = tmp_path / "vault"
    for d in ("00_System", "18_Bugs"):
        (raiz / d).mkdir(parents=True)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    assert _bug(raiz, cwd, "fallo uno")["bug_id"] == "BUG-001"
    assert _bug(raiz, cwd, "fallo dos")["bug_id"] == "BUG-002"
    indice = raiz / "18_Bugs" / ".bugs-index.json"
    roto = indice.read_text(encoding="utf-8").rstrip()[:-1] + ",}"
    indice.write_text(roto, encoding="utf-8")
    notas_antes = sorted(p.name for p in (raiz / "18_Bugs").rglob("*.md"))

    r = _bug(raiz, cwd, "fallo tres")

    assert r["ok"] is False and r["error_code"] == "DATA_FILE_CORRUPT", r
    assert problemas_de_forma(r) == [], r
    assert indice.read_text(encoding="utf-8") == roto
    assert sorted(p.name for p in (raiz / "18_Bugs").rglob("*.md")) == notas_antes
