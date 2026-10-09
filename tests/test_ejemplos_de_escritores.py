"""El ejemplo del catálogo de un escritor crea la nota, no un error bien formado.

`vault_smoke` (AP-42) da por buena una salida `ok: false` con forma de JSON,
porque el sandbox no tiene las rutas de muchos ejemplos. Eso dejaba pasar lo
que salió al medir CN-04 (2026-10-08): siete escritores cuyo ejemplo
documentado lo rechaza la propia tool —un `--type` fuera de sus `choices`, un
`--steps` que no es el array JSON que pide—. Quien copia el ejemplo no tiene
otra cosa que copiar.

El argv es el que construye `vault_smoke.invocation`, el mismo que el smoke, y
se contrasta con lo que haría una shell POSIX con esa línea (AP-44: el
consumidor del ejemplo es una persona en su terminal).
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vault_smoke  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

ESCRITORES = [
    "vault_ai_decision", "vault_env_save", "vault_infra_save", "vault_pattern_save",
    "vault_requirement_save", "vault_runbook_save",
]


def _env(v: Path) -> dict:
    return {**os.environ, "VAULT_ROOT": str(v), "VAULT_STRICT_ROOT": "1",
            "VAULT_AGENT": "test", "VAULT_VOICE": "0", "PYTHONIOENCODING": "utf-8"}


@pytest.fixture(scope="module")
def copia_con_proyecto(tmp_path_factory):
    v = tmp_path_factory.mktemp("ejemplos") / "vault"
    shutil.copytree(ROOT / "vault-sandbox", v, ignore=shutil.ignore_patterns(".locks"))
    if not (v / "01_Projects" / "mi-api").exists():
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "vault_project.py"),
             "--add", "mi-api", "--title", "Mi API"],
            cwd=ROOT, env=_env(v), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        assert r.returncode == 0, r.stdout + r.stderr
    return v


@pytest.mark.parametrize("tool", ESCRITORES)
def test_el_ejemplo_documentado_del_escritor_tiene_exito(copia_con_proyecto, tool):
    argv = vault_smoke.invocation(tool)
    linea = TOOLS_CATALOG[tool]["example"].splitlines()[0]
    # Lo que la shell le pasaría a la tool es lo mismo que le pasa el smoke.
    assert [a for a in argv[2:] if a != "--json"] == shlex.split(linea)[2:]
    r = subprocess.run(argv, cwd=ROOT / "scripts", env=_env(copia_con_proyecto),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    salida = r.stdout.strip()
    try:
        datos = json.loads(salida)
    except ValueError:
        datos = json.loads(salida.splitlines()[-1])
    assert datos.get("ok") is True, (linea, datos)


def test_el_efecto_declarado_de_ai_decision_es_donde_escribe():
    efectos = " ".join(TOOLS_CATALOG["vault_ai_decision"].get("side_effects", []))
    assert "16_AI_Governance" in efectos
    assert "03_Decisions" not in efectos


def test_el_filtro_documentado_de_pattern_list_es_un_tipo_que_existe():
    """Un `--type` que no existe no falla: filtra a cero patrones en silencio."""
    from vault_pattern_save import PATTERN_TYPES

    for linea in TOOLS_CATALOG["vault_pattern_list"]["example"].splitlines():
        partes = shlex.split(linea)
        if "--type" in partes:
            assert partes[partes.index("--type") + 1] in PATTERN_TYPES, linea
