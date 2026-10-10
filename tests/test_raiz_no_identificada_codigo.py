"""AP-51 — una raíz no identificada no se anuncia como un problema de permisos.

Medido como consumidor el 2026-10-10 con la wheel instalada y sin
`VAULT_ROOT`: la escritura se rechazaba (AP-36, bien), pero el sobre decía
PERMISSION_DENIED y su receta mandaba «verificar los permisos de escritura del
directorio destino». El disco no tenía nada que arreglar; faltaba decir cuál
es el vault. El catálogo ya tenía el código de esa causa, VAULT_NOT_FOUND, con
la receta de exportar VAULT_ROOT, y la excepción sigue siendo PermissionError
para quien la captura así (no-derogación).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

SONDA = """
import io, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import vault_raiz
vault_raiz.VAULT_ROOT = Path(sys.argv[1])
vault_raiz._VAULT_ROOT_ORIGIN = "repo_root_fallback"
import vault_errors, vault_io, vault_write
cuerpo = "\\n".join(["Primera línea con palabras suficientes para la norma."] * 3)
sys.argv = ["vault_write.py", "--folder", "07_Knowledge", "--title", "Nota de prueba",
            "--content", cuerpo, "--tags", "prueba"]
salida, sys.stdout = sys.stdout, io.StringIO()
try:
    rc = vault_errors.wrap_main(vault_write.main, "vault_write")
finally:
    texto, sys.stdout = sys.stdout.getvalue(), salida
r = json.loads(texto[texto.index("{"):])
try:
    vault_io._rechazar_raiz_insegura(vault_raiz.VAULT_ROOT / "x.md")
    clase = None
except PermissionError as exc:
    clase = type(exc).__name__
print(json.dumps({"write": r, "rc": rc, "clase": clase}, default=str))
"""


def _sondear(falso: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("VAULT_ROOT", "VAULT_STRICT_ROOT", "VAULT_PERMISSIVE_ROOT")}
    env["PYTHONIOENCODING"] = "utf-8"
    env["VAULT_AGENT"] = "pytest"
    p = subprocess.run([sys.executable, "-c", SONDA, str(falso), str(SCRIPTS)],
                       env=env, cwd=str(falso.parent), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert "{" in texto, p.stderr[-2000:]
    return json.loads(texto[texto.rindex('{"write"'):])


def test_raiz_no_identificada_es_vault_not_found_ap51(tmp_path):
    falso = tmp_path / "site-packages" / "vault_toolkit"
    falso.mkdir(parents=True)
    salida = _sondear(falso)
    r = salida["write"]
    assert r.get("ok") is False and salida["rc"] == 1, salida
    assert r.get("error_code") == "VAULT_NOT_FOUND", r
    assert "VAULT_ROOT" in json.dumps(r, ensure_ascii=False)
    # Sigue siendo un PermissionError para quien la captura así.
    assert salida["clase"] == "RaizNoIdentificada", salida
