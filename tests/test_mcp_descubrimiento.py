"""AP-51 en el descubrimiento de vaults del servidor MCP.

Medido el 2026-10-08: `countMdFiles` se tragaba el fallo de `readdir` con
`catch (_) {}`, así que un vault con un directorio que no se podía listar
se registraba con menos notas de las que tiene y nada lo decía. Un recuento
parcial publicado como total es un dato falso sobre el vault del usuario.
"""

import json
import os

from test_backup_base64 import _ilegible
from test_mcp_runner import SesionMCP, _init_vault


def _registro(vault_por_defecto, raiz_de_busqueda):
    s = SesionMCP(vault_por_defecto, {"VAULT_SCAN_ROOTS": str(raiz_de_busqueda)})
    try:
        r = s.llamar("vault_registry", {})
    finally:
        s.cerrar()
    return json.loads(r["result"]["content"][0]["text"])


def test_un_recuento_parcial_de_notas_se_declara(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    busqueda = tmp_path / "busqueda"
    descubierto = busqueda / "vault-ajeno"
    for s in ("00_System", "99_Index", "07_Knowledge"):
        (descubierto / s).mkdir(parents=True)
    (descubierto / "07_Knowledge" / "visible.md").write_text("# V\n", encoding="utf-8")
    cerrado = descubierto / "07_Knowledge" / "cerrado"
    cerrado.mkdir()
    (cerrado / "oculta.md").write_text("# O\n", encoding="utf-8")

    with _ilegible(cerrado):
        env = _registro(por_defecto, busqueda)
    vault = next(v for v in env["vaults"] if v["name"] == "vault-ajeno")
    assert vault["notes"] == 1
    assert vault.get("notes_incomplete") == 1, vault


def test_un_recuento_completo_no_lleva_la_marca(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    descubierto = tmp_path / "busqueda" / "vault-ajeno"
    for s in ("00_System", "99_Index", "07_Knowledge"):
        (descubierto / s).mkdir(parents=True)
    env = _registro(por_defecto, tmp_path / "busqueda")
    vault = next(v for v in env["vaults"] if v["name"] == "vault-ajeno")
    assert "notes_incomplete" not in vault


def test_vault_explicito_fuera_de_convencion_cuenta_notas(tmp_path):
    vault = _init_vault(tmp_path / "vault dev codex")
    (vault / "07_Knowledge").mkdir(exist_ok=True)
    (vault / "07_Knowledge" / "one.md").write_text("# One\n", encoding="utf-8")
    (vault / "07_Knowledge" / "two.md").write_text("# Two\n", encoding="utf-8")
    (vault / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")
    env = _registro(vault, tmp_path / "empty-scan-root")
    found = next(v for v in env["vaults"] if v["name"] == "vault dev codex")
    expected = sum(1 for p in vault.rglob("*.md") if not any(x.startswith(".") for x in p.relative_to(vault).parts))
    assert found["notes"] == expected
    assert found["notes"] >= 2
    assert "notes_incomplete" not in found


def test_descubrimiento_parcial_publica_incompletitud_sin_detalles_privados(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    busqueda = tmp_path / "busqueda"
    descubierto = busqueda / "vault-visible"
    for section in ("00_System", "99_Index", "07_Knowledge"):
        (descubierto / section).mkdir(parents=True, exist_ok=True)
    (descubierto / "07_Knowledge" / "visible.md").write_text(
        "# Visible\n", encoding="utf-8")

    subtree = descubierto / "07_Knowledge" / "private-subtree-sentinel"
    subtree.mkdir()
    private_candidate = busqueda / "vault-private-candidate-sentinel"
    private_candidate.mkdir()
    injection = tmp_path / "fail-readdir.cjs"
    injection.write_text(
        "const fs = require('node:fs');\n"
        "const { syncBuiltinESMExports } = require('node:module');\n"
        f"const targets = new Set({json.dumps([str(subtree), str(private_candidate)])});\n"
        "const original = fs.readdirSync;\n"
        "fs.readdirSync = function(path, ...args) {\n"
        "  if (targets.has(String(path))) {\n"
        "    const error = new Error('private-injected-readdir-message');\n"
        "    error.code = 'EACCES';\n"
        "    throw error;\n"
        "  }\n"
        "  return original.call(this, path, ...args);\n"
        "};\n"
        "syncBuiltinESMExports();\n",
        encoding="utf-8",
    )
    missing_optional_root = tmp_path / "missing-optional-scan-root"
    s = SesionMCP(por_defecto, {
        "VAULT_SCAN_ROOTS": f"{busqueda}{os.pathsep}{missing_optional_root}",
        "NODE_OPTIONS": f'--require="{injection.as_posix()}"',
    })
    try:
        response = s.llamar("vault_registry", {})
        resource_response = s._pedir("resources/read", {"uri": "vault://registry"})
        stderr = s.stderr_tail
    finally:
        s.cerrar()

    registry = json.loads(response["result"]["content"][0]["text"])
    by_name = {vault["name"]: vault for vault in registry["vaults"]}
    assert "vault-visible" in by_name, registry
    assert by_name["vault-visible"]["notes"] >= 1
    assert "defecto" in by_name, "the explicit default registry entry must survive"
    assert registry.get("discovery_incomplete") == {
        "traversal_failures": 1,
        "candidate_failures": 1,
        "truncated": False,
    }, registry
    resource = json.loads(resource_response["result"]["contents"][0]["text"])
    assert resource["discovery_incomplete"] == registry["discovery_incomplete"]
    observed = json.dumps(response, ensure_ascii=False) + stderr
    assert str(subtree) not in observed
    assert str(private_candidate) not in observed
    assert "private-injected-readdir-message" not in observed


def test_raices_opcionales_ausentes_no_marcan_descubrimiento_incompleto(tmp_path):
    por_defecto = _init_vault(tmp_path / "defecto")
    busqueda = tmp_path / "busqueda"
    (busqueda / "vault-visible" / "00_System").mkdir(parents=True)
    (busqueda / "vault-visible" / "99_Index").mkdir()
    missing = tmp_path / "missing-optional-scan-root"
    s = SesionMCP(por_defecto, {"VAULT_SCAN_ROOTS": f"{busqueda}{os.pathsep}{missing}"})
    try:
        response = s.llamar("vault_registry", {})
    finally:
        s.cerrar()
    registry = json.loads(response["result"]["content"][0]["text"])
    assert "vault-visible" in {vault["name"] for vault in registry["vaults"]}
    assert "discovery_incomplete" not in registry
