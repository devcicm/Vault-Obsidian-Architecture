"""AP-36 — la traza del servidor MCP vive dentro del vault que sirve.

Medido en v40.34: `TraceLog` escribía `.mcp-trace-log.json` y `.md` junto al
`.mjs` (`join(__dirname, ...)`). En una instalación eso es el directorio del
paquete: la bitácora de todos los vaults de la máquina se mezclaba en un solo
fichero fuera de todos ellos, con parámetros de las llamadas dentro, y
`vault://traceability/mutations` devolvía a un vault las llamadas de otro.
"""

import json
from pathlib import Path

import pytest

from test_mcp_runner import SERVER, SesionMCP, _init_vault

TRAZA = ".mcp-trace-log.json"


def _huella(ruta: Path):
    return ruta.stat().st_mtime_ns if ruta.exists() else None


@pytest.fixture
def vault(tmp_path):
    return _init_vault(tmp_path / "vault")


def test_ap36_la_traza_se_escribe_en_el_vault(vault):
    junto_al_servidor = SERVER.parent / TRAZA
    antes = _huella(junto_al_servidor)
    s = SesionMCP(vault)
    try:
        s.llamar("vault_health", {})
        recurso = s._pedir("resources/read", {"uri": "vault://traceability/mutations"})
    finally:
        s.cerrar()

    traza = vault / "00_System" / TRAZA
    assert traza.is_file(), "la llamada no dejó traza dentro del vault"
    entradas = json.loads(traza.read_text(encoding="utf-8"))
    assert [e["tool"] for e in entradas] == ["vault_health"]
    assert _huella(junto_al_servidor) == antes, "se escribió traza junto al .mjs"

    publicado = json.loads(recurso["result"]["contents"][0]["text"])
    assert publicado["count"] == 1


def test_dos_vaults_no_comparten_traza(tmp_path):
    a = _init_vault(tmp_path / "a")
    b = _init_vault(tmp_path / "b")
    for raiz in (a, b):
        s = SesionMCP(raiz)
        try:
            s.llamar("vault_health", {})
        finally:
            s.cerrar()
    for raiz in (a, b):
        entradas = json.loads((raiz / "00_System" / TRAZA).read_text(encoding="utf-8"))
        assert len(entradas) == 1


def test_la_traza_no_cuenta_como_nota_del_vault(vault):
    """La tabla `.md` que también se escribía la contaba `vault_audit` como
    nota sin frontmatter: cada llamada MCP bajaba la salud del vault."""
    s = SesionMCP(vault)
    try:
        s.llamar("vault_health", {})
        auditoria = s.llamar("vault_audit", {})
    finally:
        s.cerrar()
    assert not list((vault / "00_System").glob(".mcp-trace-log*.md"))
    assert ".mcp-trace-log" not in json.dumps(auditoria)


def test_sin_00_system_no_se_siembra(tmp_path):
    """Un directorio que no es un vault no recibe `00_System/` por la traza."""
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    s = SesionMCP(vacio)
    try:
        s.llamar("vault_health", {})
    finally:
        s.cerrar()
    assert not (vacio / "00_System").exists()
