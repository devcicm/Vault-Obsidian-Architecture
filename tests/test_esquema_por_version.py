"""Los JSON Schema de `schemas/` son el contrato de nota, versión a versión.

El esquema es el contrato para quien no importa Python, así que tiene que
reprobar exactamente lo que `vault_validate` reprueba: ni más —rechazaría notas
que la tool aprueba— ni menos. Se mide con `jsonschema`, que es lo que usaría
ese consumidor (AP-44), contra las notas reales del sandbox.
"""

import json
from pathlib import Path

import jsonschema  # declarada en el extra dev: si falta, falla — no se salta
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

import vault_contrato_nota as contrato  # noqa: E402
import vault_esquema  # noqa: E402


def test_prepared_v42_is_selectable_without_changing_published_defaults():
    assert contrato.VERSIONES_CON_CONTRATO[-1] == "v41"
    assert contrato.VERSIONES[-1] == "v41"
    prepared = contrato.esquema_json("v42")
    for field in ("requirement_state", "solution_ref", "solved_by"):
        assert field in prepared["properties"]
        assert field not in prepared["required"]
        assert field not in contrato.esquema_json("v41")["properties"]
    assert contrato.errores_de_valor({"requirement_state": "not-a-state"}) == []
    assert contrato.errores_de_valor({"requirement_state": "not-a-state"}, "v41") == []
    assert contrato.errores_de_valor({"requirement_state": "not-a-state"}, "v42")
    assert contrato.errores_de_valor({"requirement_state": "verified"}, "v42") == []


def test_prepared_schema_does_not_rewrite_historical_schemas(tmp_path, monkeypatch):
    historical = {}
    for version in contrato.VERSIONES_CON_CONTRATO:
        name = f"vault-{version}.schema.json"
        historical[name] = (REPO_ROOT / "schemas" / name).read_bytes()
        (tmp_path / name).write_bytes(historical[name])
    monkeypatch.setattr(vault_esquema, "CARPETA", tmp_path)
    result = vault_esquema.sync()
    assert set(result["written"]) == {"schemas/vault-v42.schema.json", "schemas/README.md"}
    for name, content in historical.items():
        assert (tmp_path / name).read_bytes() == content


def test_schemas_del_repo_al_dia():
    r = vault_esquema.check()
    assert r["ok"], r["stale"] + r["unknown"]


def test_un_esquema_editado_a_mano_se_detecta(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_esquema, "CARPETA", tmp_path)
    assert vault_esquema.sync()["written_count"] == len(contrato.VERSIONES_SELECCIONABLES) + 1
    assert vault_esquema.sync()["written_count"] == 0  # AP-37: nada que escribir
    ruta = tmp_path / "vault-v37.schema.json"
    ruta.write_text(ruta.read_text(encoding="utf-8").replace('"createdAt",', ""), encoding="utf-8")
    r = vault_esquema.check()
    assert not r["ok"]
    assert r["stale"] == [{"file": "schemas/vault-v37.schema.json", "problem": "desactualizado"}]


def test_un_esquema_sin_version_no_se_borra(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_esquema, "CARPETA", tmp_path)
    vault_esquema.sync()
    (tmp_path / "vault-v99.schema.json").write_text("{}", encoding="utf-8")
    r = vault_esquema.check()
    assert r["unknown"] == ["vault-v99.schema.json"]
    vault_esquema.sync()
    assert (tmp_path / "vault-v99.schema.json").exists()


def test_cada_version_exige_lo_de_su_momento():
    # Antes del primer validador, el contrato es AP-12 del manifiesto (x-vault-origen).
    assert sorted(contrato.esquema_json("v24")["required"]) == sorted(
        ["id", "title", "type", "createdAt", "updatedAt", "tags"])
    assert contrato.esquema_json("v24")["x-vault-origen"] == "manifiesto"
    assert contrato.esquema_json("v30")["required"] == ["id", "title"]
    assert "createdAt" in contrato.esquema_json("v37")["required"]
    # Una menor se resuelve a su mayor. Una menor fija y pasada: la vigente
    # escrita a mano caduca en el bump (AP-47, test_version_coherence).
    assert contrato.esquema_json("v40.1") == contrato.esquema_json("v40")
    with pytest.raises(ValueError):
        contrato.esquema_json("v12")


def _notas_del_sandbox():
    import yaml

    raiz = REPO_ROOT / "vault-sandbox"
    from vault_registry import ORDERED_SECTIONS

    for seccion in ORDERED_SECTIONS:
        for nota in sorted((raiz / seccion).rglob("*.md")):
            if ".history" in nota.parts or nota.name.startswith("_"):
                continue
            texto = nota.read_text(encoding="utf-8", errors="ignore").lstrip("﻿")
            if not texto.startswith("---"):
                continue
            try:
                from vault.kernel.frontmatter_parsing import parse_frontmatter_with_body

                datos, _ = parse_frontmatter_with_body(texto)
            except Exception:  # noqa: BLE001 — una nota rota no es de este test
                continue
            yield nota, nota.relative_to(raiz).as_posix(), datos


def test_el_esquema_vigente_da_el_veredicto_de_vault_validate(monkeypatch):
    import vault_validate

    raiz = REPO_ROOT / "vault-sandbox"
    monkeypatch.setattr(vault_validate, "_raiz", lambda: raiz)
    esquema = contrato.esquema_json(contrato.VERSIONES[-1])
    medidas = 0
    for nota, rel, datos in _notas_del_sandbox():
        clase = contrato.clase_de_nota(rel)
        if clase == "derivada":
            continue
        sub = dict(esquema["$defs"][clase], **{"$schema": esquema["$schema"]})
        valida_esquema = jsonschema.Draft202012Validator(sub).is_valid(json.loads(json.dumps(datos, default=str)))
        assert valida_esquema == vault_validate.validate_frontmatter(nota)["valid"], rel
        medidas += 1
    assert medidas > 10, "el sandbox se quedó sin notas que medir"


def test_el_nivel_de_cada_propiedad_es_el_de_su_version():
    """Un esquema pasado no se reescribe con el nivel vigente (no-derogación)."""
    def nivel(version, campo):
        return contrato.esquema_json(version)["properties"][campo]["x-vault-nivel"]

    assert nivel("v30", "createdAt") == "opcional"
    assert nivel("v37", "createdAt") == "requerido"
    assert nivel("v20", "type") == "requerido"  # AP-12 del manifiesto
    assert nivel("v30", "type") == "opcional"
    assert nivel("v40", "type") == "recomendado"


def test_la_caja_del_valor_cia_no_cambia_el_veredicto():
    v = jsonschema.Draft202012Validator(contrato.esquema_json("v40")["properties"]["cia_integrity"])
    assert v.is_valid("HIGH") and v.is_valid("high") and not v.is_valid("higher")
