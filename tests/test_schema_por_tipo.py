"""El schema por tipo del SDD 06 sale de lo que los escritores escriben.

La tabla «Schema canónico por tipo (regla dura)» estaba escrita a mano y no
tenía registro detrás. Medido en v41.2 con `yaml.safe_load` sobre la nota que
deja cada escritor (AP-44: el criterio del consumidor): ocho de sus campos
obligatorios no los escribe nadie —`lifecycle_state` en Pattern, `coverage` en
Test, `last_run` en Runbook, `date` en ADR y Session, `duration` en Session,
`sli_type` y `status` en SLO—. Se conservan como prometidos (no-derogación) y
el SDD los publica marcados como «prometido sin escritor».

Lo que escribe cada `*_save` se contrasta contra sus dorados
(`tests/dorados/saves/`), que la caracterización comprueba byte a byte en cada
corrida. ADR y Session no tienen escritor propio: los escribe `vault_write`, y
se ejecuta aquí.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vault_registry as reg  # noqa: E402
import vault_sdd_init  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402

DORADOS = Path(__file__).parent / "dorados" / "saves"
CUERPO = ("Contexto de la decision con palabras reales.\n"
          "Segunda linea con varias palabras reales.\n"
          "Tercera linea con mas palabras reales.\n")


def _frontmatter(nota: str) -> dict:
    return yaml.safe_load(nota.split("---", 2)[1])


@pytest.fixture(scope="module")
def vault(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("schema")
    env = dict(os.environ, VAULT_ROOT=str(raiz), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "vault_init.py")], env=env,
                       capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    assert r.returncode == 0, r.stdout + r.stderr
    return raiz, env


def test_todo_tipo_declara_escritor_vivo_y_lo_prometido():
    assert list(reg.SCHEMA_POR_TIPO) == ["Pattern", "Requirement", "Test", "Runbook", "ADR",
                                         "Incident", "Session", "SLO", "NCR", "Risk"]
    for tipo, s in reg.SCHEMA_POR_TIPO.items():
        assert s["escritor"] in TOOLS_CATALOG, tipo
        assert s["prometido"] and s["escribe"], tipo


@pytest.mark.parametrize("tipo", [t for t, s in reg.SCHEMA_POR_TIPO.items()
                                  if s["escritor"] != "vault_write"])
def test_lo_que_escribe_un_save_es_su_dorado(tipo):
    escritor = reg.SCHEMA_POR_TIPO[tipo]["escritor"]
    dorado = json.loads((DORADOS / f"{escritor}.json").read_text(encoding="utf-8"))
    assert tuple(sorted(_frontmatter(dorado["nota"]))) == reg.SCHEMA_POR_TIPO[tipo]["escribe"]


@pytest.mark.parametrize("tipo, carpeta", [("ADR", "03_Decisions"), ("Session", "04_Sessions")])
def test_lo_que_escribe_vault_write_se_mide_ejecutandolo(vault, tipo, carpeta):
    raiz, env = vault
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_write.py"), "--folder", carpeta,
         "--title", f"Medida {tipo}", "--content", CUERPO, "--tags", "medida",
         "--agent", "medida"],
        env=env, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    ruta = json.loads(r.stdout.strip().splitlines()[-1])["path"]
    nota = (raiz / ruta).read_text(encoding="utf-8")
    assert tuple(sorted(_frontmatter(nota))) == reg.SCHEMA_POR_TIPO[tipo]["escribe"]


def test_lo_prometido_sin_escritor_se_deriva_y_no_se_borra():
    sin = {t: reg.prometido_sin_escritor(t) for t in reg.SCHEMA_POR_TIPO}
    assert sin["Pattern"] == ("lifecycle_state",)
    assert sin["SLO"] == ("sli_type", "status")
    assert sin["Requirement"] == ()
    for tipo, s in reg.SCHEMA_POR_TIPO.items():
        assert set(sin[tipo]) == set(s["prometido"]) - set(s["escribe"]), tipo


def test_el_sdd_publica_la_tabla_derivada():
    texto = vault_sdd_init.generate_methodology(REPO_ROOT, {})
    assert "{SCHEMA_POR_TIPO}" not in texto
    assert "Fuente: `vault_registry.SCHEMA_POR_TIPO`" in texto
    for tipo, s in reg.SCHEMA_POR_TIPO.items():
        fila = [linea for linea in texto.splitlines() if linea.startswith(f"| {tipo} |")]
        assert len(fila) == 1, tipo
        assert s["escritor"] in fila[0], tipo
        for campo in reg.prometido_sin_escritor(tipo):
            assert f"`{campo}`" in fila[0].rsplit("|", 2)[-2], (tipo, campo)
