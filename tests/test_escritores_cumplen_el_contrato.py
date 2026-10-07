"""Lo que escribe una tool lo aprueba `vault_validate` (AP-12).

Medido el 2026-10-07 ejecutando el ejemplo del catálogo de cada tool sobre una
copia del sandbox: cuatro escritores dejaban notas de contenido que el contrato
vigente reprueba — `vault_bibliography_save` omitía `tags` vacío,
`vault_project` no acuñaba `id`, `vault_quality_dashboard` no llevaba ni CIA
ni `agent`, y con v41 a los dos últimos y a `vault_log_error` les faltaba
`status`. Ningún test lo veía porque cada uno miraba el campo que arreglaba,
no el contrato entero.

Se mide con el ejemplo del catálogo y con `faltantes` del dueño del contrato:
el mismo criterio que aplica `vault_validate`, no una lista propia (AP-57).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_smoke  # noqa: E402
from vault_contrato_nota import clase_de_nota, faltantes  # noqa: E402
from vault_lib import parse_frontmatter  # noqa: E402
from vault_registry import ORDERED_SECTIONS  # noqa: E402

ESCRITORES = (
    "vault_write",
    "vault_preferences",
    "vault_bibliography_save",
    "vault_project",
)


#: El ejemplo del catálogo de `vault_write` es demasiado corto y AP-11 lo
#: rechaza, que es lo correcto; aquí se le da un cuerpo que pase.
_CUERPO = "# Overview\n\n" + "API REST que expone el inventario y su historia de cambios.\n" * 3


def _invocacion(tool: str) -> list:
    argv = vault_smoke.invocation(tool)
    if tool == "vault_write":
        argv[argv.index("--content") + 1] = _CUERPO
    return argv


def _foto(raiz: Path) -> dict:
    return {p.relative_to(raiz).as_posix(): p.read_bytes() for p in raiz.rglob("*.md")}


@pytest.mark.parametrize("tool", ESCRITORES)
def test_la_nota_que_escribe_cumple_el_contrato_vigente(tool, tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "vault-sandbox", vault, ignore=shutil.ignore_patterns(".locks"))
    antes = _foto(vault)
    argv = _invocacion(tool)
    assert argv and argv[-1] != "--help", f"{tool} sin ejemplo ejecutable en el catálogo"
    proceso = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 VAULT_AGENT="test", PYTHONIOENCODING="utf-8"),
        cwd=str(tmp_path), timeout=120,
    )
    assert proceso.returncode == 0, proceso.stdout[-2000:] + proceso.stderr[-2000:]

    escritas = [rel for rel, datos in _foto(vault).items()
                if antes.get(rel) != datos
                and rel.split("/", 1)[0] in ORDERED_SECTIONS
                and clase_de_nota(rel) != "derivada"]
    assert escritas, f"{tool}: el ejemplo no escribió ninguna nota"
    incumplen = {}
    for rel in escritas:
        datos = parse_frontmatter((vault / rel).read_text(encoding="utf-8"))
        falta = faltantes(datos, rel)
        if falta:
            incumplen[rel] = falta
    assert incumplen == {}, incumplen
