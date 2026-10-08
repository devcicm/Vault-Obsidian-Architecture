"""`--meta` no puede pisar la identidad ni colar erratas (CN-01, CN-02, CN-03, AP-13).

Medido el 2026-10-04 contra `vault_write`:
`--meta '{"id":"fijo","createdAt":"ayer","statsu":"activ","cia_sensitivity":"top-secret"}'`
respondía `ok: true` con un `id` que no era el de la nota en disco, dejaba
`createdAt: ayer` y escribía `statsu` como propiedad. Un `status` fuera de
vocabulario salía como UNEXPECTED_ERROR crítico en vez de como entrada inválida.
"""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402
import vault_write  # noqa: E402

CONTENIDO = "Línea uno real.\nLínea dos con contenido.\nLínea tres con contenido.\nLínea cuatro."


@pytest.fixture
def vault_vacio(tmp_path):
    previo = vault_io.get_vault_root()
    (tmp_path / "01_Projects").mkdir()
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previo)


def _escribir(meta, titulo="Nota Meta"):
    return vault_write.vault_write(
        folder="01_Projects", title=titulo, content=CONTENIDO,
        tags=["demo"], meta=meta,
    )


def _notas(vault):
    return [p.name for p in (vault / "01_Projects").glob("*.md") if p.name != "index.md"]


@pytest.mark.parametrize("clave", sorted(vault_write.CAMPOS_DEL_WRITE_PATH))
def test_meta_no_fija_los_campos_del_write_path(vault_vacio, clave):
    r = _escribir({"agent": "probe", clave: "x"})
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert clave in r["message"]
    assert _notas(vault_vacio) == []


@pytest.mark.parametrize("meta,pista", [
    ({"statsu": "draft"}, "status"),
    ({"tag": "a"}, "tags"),
    ({"agente": "x"}, "agent"),
    ({"Status": "draft"}, "status"),
    ({"ID": "x"}, "id"),
    ({"cia_sensitivity": "top-secret"}, "cia_sensitivity"),
    ({"cia_availability": "critical"}, "cia_availability"),
    ({"status": "inventado"}, "CN-03"),
    ({"type": "adr"}, "03_Decisions"),
    ({"type": ""}, "type"),
])
def test_meta_rechaza_erratas_y_valores_fuera_de_vocabulario(vault_vacio, meta, pista):
    r = _escribir({"agent": "probe", **meta})
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r
    assert pista in r["message"]
    assert _notas(vault_vacio) == []


@pytest.mark.parametrize("meta", [[1, 2], "texto", 7])
def test_meta_que_no_es_objeto_es_entrada_invalida(vault_vacio, meta):
    r = _escribir(meta)
    assert r["ok"] is False and r["error_code"] == "INVALID_INPUT", r


def test_propiedades_propias_siguen_permitidas_y_el_id_es_el_de_la_nota(vault_vacio):
    """El vocabulario de claves es abierto: lo que no imita un campo pasa."""
    r = _escribir({"agent": "probe", "owner": "#infra", "status": "active",
                   "cia_sensitivity": "restricted", "type": "project-overview"})
    assert r["ok"] is True, r
    nota = vault_vacio / r["path"]
    datos = yaml.safe_load(nota.read_text(encoding="utf-8").split("---")[1])
    assert datos["id"] == r["id"]
    assert datos["owner"] == "#infra"
    assert datos["title"] == "Nota Meta"


def test_el_autor_del_bloque_no_deja_que_meta_lo_pise():
    with pytest.raises(ValueError, match="CN-01"):
        vault_write.generate_frontmatter(title="Demo", meta={"id": "fijo"})


def test_la_pista_de_missing_agent_nombra_un_flag_que_vault_write_acepta(tmp_path):
    """Medido el 2026-10-04 desde la wheel: la pista decía `--agent`, que
    `vault_write` no declara; seguirla daba INVALID_ARGS (AP-16).

    Desde 77818b8 (2026-10-07) `vault_write` declara `--agent` y la pista lo
    nombra. Lo que este test protege no es qué flag, sino que el nombrado
    exista: se comprueba contra el argparse del script, criterio del
    consumidor, y no contra un literal."""
    import json
    import os
    import re
    import subprocess

    (tmp_path / "01_Projects").mkdir()
    env = {k: v for k, v in os.environ.items() if k != "VAULT_AGENT"}
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_write.py"), "--folder", "01_Projects",
         "--title", "Sin Agente", "--content", CONTENIDO, "--tags", "demo"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
        env={**env, "VAULT_ROOT": str(tmp_path)}, timeout=120,
    )
    sobre = json.loads(r.stdout)
    assert sobre["error_code"] == "missing_agent", sobre
    pista = sobre["recovery"]["hint"]
    from vault_mcp_catalog import argparse_params
    citados = re.findall(r"--([a-z][\w-]*)", pista)
    assert citados, pista
    assert set(citados) <= set(argparse_params("vault_write.py")), pista
    assert sobre["recovery"]["action"] == "fix_input"


def test_ap13_las_fechas_salen_del_reloj_en_iso_completo(vault_vacio):
    """AP-13: `createdAt` y `updatedAt` los pone el write path, con fecha,
    hora y zona; `--meta` no puede colar `ayer` (ver el parametrizado de
    arriba). Se lee el frontmatter escrito con `yaml.safe_load`."""
    from datetime import datetime

    r = _escribir({"agent": "probe"})
    assert r["ok"] is True, r
    texto = (vault_vacio / r["path"]).read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---")[1])
    for campo in ("createdAt", "updatedAt"):
        # Como lo lee el consumidor: un instante con zona, no una cadena suelta.
        assert isinstance(fm[campo], datetime) and fm[campo].tzinfo is not None, (
            "AP-13", campo, fm[campo])
    rechazo = _escribir({"agent": "probe", "createdAt": "ayer"}, titulo="Otra")
    assert rechazo["ok"] is False and "AP-13" in rechazo["message"], rechazo
