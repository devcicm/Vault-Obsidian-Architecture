"""La ficha que escribe `vault_project --add` pasa el audit como cualquier nota.

Medido el 2026-10-04 en la QA de producto: registrar un proyecto —el paso que
el Quick Start pide antes de documentarlo— dejaba `01_Projects/<slug>/project.md`
sin `agent`, `tags`, CIA ni fechas, y el audit la apuntaba en `missingAgent`
(AP-16), `missingTags`, `missingCIA` y `missingUpdated` en cuanto existía.

Se mide con `vault_audit`, el consumidor, no releyendo los campos escritos.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault_fundamentals_catalog import CIA_TRIAD, cia_por_defecto  # noqa: E402
from vault_lib import parse_frontmatter  # noqa: E402

FICHA = "01_Projects/demo/project.md"


def _correr(raiz, script, *args, **entorno):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", **entorno)
    if "VAULT_AGENT" not in entorno:
        env.pop("VAULT_AGENT", None)
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=300)
    return json.loads(p.stdout)


def _vault(tmp_path):
    for seccion in ("00_System", "01_Projects", "99_Index"):
        (tmp_path / seccion).mkdir()
    return tmp_path


def test_la_ficha_nueva_no_aparece_en_ningun_hallazgo_del_audit(tmp_path):
    raiz = _vault(tmp_path)
    assert _correr(raiz, "vault_project.py", "--add", "demo", VAULT_AGENT="claude")["ok"]
    issues = _correr(raiz, "vault_audit.py")["issues"]
    for clave in ("missingAgent", "missingTags", "missingCIA", "missingUpdated"):
        rutas = [i.get("path") for i in issues.get(clave, [])]
        assert FICHA not in rutas, (clave, rutas)
    fm = parse_frontmatter((raiz / FICHA).read_text(encoding="utf-8"))
    assert fm["agent"] == "claude"
    assert {k: fm[k] for k in cia_por_defecto()} == cia_por_defecto()


def test_sin_vault_agent_firma_system_como_las_tools_tipadas(tmp_path):
    raiz = _vault(tmp_path)
    assert _correr(raiz, "vault_project.py", "--add", "demo")["ok"]
    fm = parse_frontmatter((raiz / FICHA).read_text(encoding="utf-8"))
    assert fm["agent"] == "system"


def test_sumar_un_alias_refresca_updated_at(tmp_path):
    raiz = _vault(tmp_path)
    _correr(raiz, "vault_project.py", "--add", "demo")
    ruta = raiz / FICHA
    texto = re.sub(r"^(createdAt|updatedAt): .*$", r"\1: 2020-01-01T00:00:00.000Z",
                   ruta.read_text(encoding="utf-8"), flags=re.M)
    ruta.write_text(texto, encoding="utf-8")
    assert _correr(raiz, "vault_project.py", "--add", "demo", "--alias", "demo-api")["ok"]
    fm = parse_frontmatter(ruta.read_text(encoding="utf-8"))
    assert fm["aliases"] == ["demo-api"]
    assert not str(fm["updatedAt"]).startswith("2020")
    # createdAt y updatedAt nacieron iguales y los dos pasaron a 2020: solo
    # updatedAt se mueve al editar.
    assert str(fm["createdAt"]).startswith("2020")


def test_los_defaults_cia_salen_del_registro():
    assert cia_por_defecto() == {c["frontmatter_field"]: c["default"] for c in CIA_TRIAD}
