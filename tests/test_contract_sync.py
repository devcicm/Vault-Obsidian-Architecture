"""Tests de `vault_mcp_catalog --check-contracts` — guard catálogo ↔ tool-spec.json.

Mismas dos familias que en `test_doc_sync.py`:

  1. **El guard funciona**: ante un tool-spec manipulado, detecta lo que debe.
  2. **El repo está alineado**: hoy, aquí, `--check-contracts` sale limpio.

La manipulación siempre se hace sobre una copia en `tmp_path`, nunca sobre
`vault-sandbox/00_System/tool-spec.json`.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_mcp_catalog as vmc  # noqa: E402

SPEC_REAL = ROOT / "vault-sandbox/00_System/tool-spec.json"


@pytest.fixture
def spec_temporal(tmp_path):
    """Devuelve (ruta, cargar, guardar) sobre una copia del tool-spec real."""
    copia = tmp_path / "tool-spec.json"
    copia.write_text(SPEC_REAL.read_text(encoding="utf-8"), encoding="utf-8")

    def cargar():
        return json.loads(copia.read_text(encoding="utf-8"))

    def guardar(data):
        copia.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return copia, cargar, guardar


# ── 1. El guard funciona ───────────────────────────────────────────────────


def test_detecta_una_tool_del_catalogo_sin_contrato(spec_temporal):
    ruta, cargar, guardar = spec_temporal
    data = cargar()
    del data["tools"]["vault_move"]
    guardar(data)
    problemas = vmc.check_contracts(str(ruta))["problems"]
    assert {"kind": "tool_sin_contrato", "detail": "vault_move"} in problemas


def test_detecta_una_entrada_fuera_del_catalogo_sin_estado(spec_temporal):
    """No-derogación no es lo mismo que abandono: si sigue ahí, dice por qué."""
    ruta, cargar, guardar = spec_temporal
    data = cargar()
    data["tools"]["vault_create"]["status"] = "active"
    guardar(data)
    tipos = {p["kind"] for p in vmc.check_contracts(str(ruta))["problems"]}
    assert "entrada_sin_catalogo_ni_estado" in tipos


def test_detecta_un_group_divergente(spec_temporal):
    ruta, cargar, guardar = spec_temporal
    data = cargar()
    data["tools"]["vault_norms"]["group"] = "Normas y Etiquetas"
    guardar(data)
    tipos = {p["kind"] for p in vmc.check_contracts(str(ruta))["problems"]}
    assert "group_divergente" in tipos


def test_detecta_un_group_id_que_no_sigue_la_numeracion_del_readme(spec_temporal):
    """La regresión concreta: `vault_env_matrix` tenía group_id 30 en el grupo 8."""
    ruta, cargar, guardar = spec_temporal
    data = cargar()
    data["tools"]["vault_env_matrix"]["group_id"] = 30
    guardar(data)
    problemas = vmc.check_contracts(str(ruta))["problems"]
    assert any(
        p["kind"] == "group_id_divergente" and p["detail"].startswith("vault_env_matrix")
        for p in problemas
    )


# ── 2. El repo está alineado ───────────────────────────────────────────────


def test_el_tool_spec_del_repo_esta_alineado():
    resultado = vmc.check_contracts()
    assert resultado["ok"], "\n".join(
        f"{p['kind']}: {p['detail']}" for p in resultado["problems"]
    )


def test_toda_tool_del_catalogo_tiene_contrato():
    data = json.loads(SPEC_REAL.read_text(encoding="utf-8"))
    sin_contrato = sorted(set(vmc.TOOLS_CATALOG) - set(data["tools"]))
    assert not sin_contrato, f"tools sin entrada en tool-spec.json: {sin_contrato}"


def test_group_id_se_deriva_de_la_numeracion_del_readme():
    """No es un cuarto sistema de nombres: es la numeración del README leída.

    Antes había cuatro numeraciones distintas para lo mismo. Esta es la única
    que cubre los 35 grupos y la única que otro guard (`vault_doc_sync`)
    mantiene viva.
    """
    readme = (ROOT / "scripts/README.md").read_text(encoding="utf-8")
    gid = {
        etiqueta: int(numero)
        for numero, etiqueta in re.findall(r"^## Grupo (\d+) — (.+?)\s*$", readme, re.M)
    }
    assert set(gid) >= set(vmc.GROUPS), (
        f"grupos sin sección en scripts/README.md: {sorted(set(vmc.GROUPS) - set(gid))}"
    )

    data = json.loads(SPEC_REAL.read_text(encoding="utf-8"))["tools"]
    pertenencia = {t: g for g, tools in vmc.GROUPS.items() for t in tools}
    desalineadas = sorted(
        (nombre, data[nombre].get("group_id"), gid[grupo])
        for nombre, grupo in pertenencia.items()
        if nombre in data and data[nombre].get("group_id") != gid[grupo]
    )
    assert not desalineadas, f"group_id fuera de la numeración del README: {desalineadas}"


def test_las_entradas_archivadas_conservan_su_sustituta():
    """No-derogación: lo reemplazado apunta a lo que lo reemplaza."""
    data = json.loads(SPEC_REAL.read_text(encoding="utf-8"))["tools"]
    archivadas = {n: s for n, s in data.items() if s.get("status") == "archived"}
    assert archivadas, "se esperaban entradas archivadas anotadas"
    for nombre, spec in archivadas.items():
        assert spec.get("archived_in"), f"{nombre} sin archived_in"
    # `vault_tools` se disolvió en scripts individuales: no tiene una sustituta
    # única, así que es la excepción documentada en la tabla de scripts/README.md.
    for nombre, spec in archivadas.items():
        if nombre != "vault_tools":
            assert spec.get("superseded_by"), f"{nombre} sin superseded_by"
