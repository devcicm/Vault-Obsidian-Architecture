"""Ningún paso de la CI convierte un fallo en verde por su cuenta.

Medido en la auditoría del 2026-10-15: tres pasos del job `validate` acababan
en `|| echo "... not yet implemented"`, y los tres fallaban:

- `vault_validate` sobre `vault-sandbox/`, que lleva a propósito veinte notas
  defectuosas (`health_fixture` de `tests/fixtures/sandbox-seed.json`) para
  los tests de salud. Validarlo no puede salir verde nunca, así que el paso
  no medía nada.
- `vault_audit --dry-run`: el flag no existe, argparse salía con rc 2.
- `vault_spec_validate`: 90 tools en «drift», casi todas porque el detector
  solo ve claves escritas como literal en un `return {...}`.

Un `|| echo` es un `continue-on-error` que no se ve en la interfaz y que
miente sobre el motivo. Ahora `vault_validate` y `vault_audit` miden un vault
recién creado con `vault_init` —lo que el estándar genera tiene que cumplir su
propio contrato— y el paso que todavía no puede ser puerta lo dice en el YAML
(`continue-on-error`) y cita la deuda que lo sostiene.

La CI se lee con `yaml.safe_load` (AP-44).
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import vault_blueprint as bp  # noqa: E402

CI = ROOT / ".github" / "workflows" / "vault-ci.yml"
ENMASCARA = re.compile(r"\|\|\s*(echo|true|:|exit\s+0)\b")


def _pasos():
    datos = yaml.safe_load(CI.read_text(encoding="utf-8"))
    for nombre, job in datos["jobs"].items():
        for paso in job.get("steps", []):
            yield nombre, paso


def test_ningun_paso_enmascara_su_rc():
    culpables = [(job, p.get("name"), linea.strip())
                 for job, p in _pasos()
                 for linea in str(p.get("run") or "").splitlines()
                 if ENMASCARA.search(linea)]
    assert culpables == [], culpables


def test_todo_paso_que_puede_fallar_cita_su_deuda_pendiente():
    pendientes = {d["id"] for d in bp.DEUDA_DECLARADA if d["estado"] == "pendiente"}
    for job, p in _pasos():
        if p.get("continue-on-error"):
            citadas = {i for i in pendientes if i in str(p.get("name"))}
            assert citadas, (
                f"{job}/{p.get('name')}: continue-on-error sin citar en el nombre "
                f"una deuda pendiente de vault_blueprint.DEUDA_DECLARADA")


def test_validate_y_audit_miden_un_vault_recien_creado():
    """Los pasos existen y el vault que miden lo crea `vault_init` antes."""
    runs = [str(p.get("run") or "") for _, p in _pasos()]
    texto = "\n".join(runs)
    i_init = texto.find("vault_init.py")
    assert i_init != -1, "la CI no crea ningún vault limpio con vault_init"
    for tool in ("vault_validate.py", "vault_audit.py"):
        i = texto.find(tool)
        assert i > i_init, f"{tool} no corre sobre el vault de vault_init"
    assert "--dry-run" not in texto


def test_un_vault_recien_creado_valida_y_audita_limpio(tmp_path):
    """Lo que el paso de la CI ejerce, ejercido aquí: si falla, la CI también."""
    raiz = tmp_path / "limpio"
    raiz.mkdir()
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    for script in ("vault_init.py", "vault_validate.py", "vault_audit.py"):
        p = subprocess.run([sys.executable, str(SCRIPTS / script)], env=env,
                           cwd=str(tmp_path), capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        assert p.returncode == 0, f"{script} rc {p.returncode}: {p.stdout[-1500:]}"


def test_limite_declarado_spec_validate_returns_ciego(monkeypatch):
    """`returns_match` no ve una clave que se añade al dict fuera del literal.

    Fija el límite de la deuda `spec_validate_returns_ciego`: el día que el
    detector la vea, este test falla y la deuda se salda.
    """
    import vault_spec_validate as sv

    fuente = (
        "def tool():\n"
        "    r = {'ok': True}\n"
        "    r['written'] = 1\n"
        "    r.update(indicador())\n"
        "    return r\n"
    )
    monkeypatch.setattr(sv, "_read_source", lambda name: fuente)
    res = sv.validate_tool("vault_x", {"declared_returns": ["ok", "written"]})
    assert res["status"] == "drift", res
    assert ast.parse(fuente)  # la fuente es Python válido: el fallo es del detector


def test_la_deuda_spec_validate_returns_ciego_esta_declarada():
    d = next((d for d in bp.DEUDA_DECLARADA if d["id"] == "spec_validate_returns_ciego"), None)
    assert d is not None and d["estado"] == "pendiente"
    assert "test_limite_declarado_spec_validate_returns_ciego" in d["por_que_no_ahora"]
