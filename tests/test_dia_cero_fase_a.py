"""TDD Fase A: corrección de los 5 errores día cero verificados el 2026-11-23.

- DZ-01: 00_System/reglas.json o inmutable.json con UTF-8 BOM o vacíos no bloquean escrituras.
- DZ-02: vault_write traduce errores de atomic_write_text a envelopes canónicos (AP-51/AP-52).
- DZ-03: vault_security_scan escanea un archivo individual (no solo directorios) sin filtrar rutas de máquina.
- DZ-04: vault_requirement_save expone recuperación auditable (--adopt-legacy) cuando falta el índice con notas legadas.
- DZ-06: tests/test_portabilidad_terceros.py compila sin SyntaxWarning en Python 3.12+/3.14.
"""

from __future__ import annotations

import json
import warnings

import pytest

from apoyo import ROOT
from vault_base import copiar_vault


def test_dz01_politica_con_bom_y_vacia_no_bloquean_escrituras(tmp_path):
    import vault_io

    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir(parents=True)
    previa = vault_io.set_vault_root(raiz)
    try:
        # 1) UTF-8 con BOM (típico en Windows) debe leerse y aplicarse
        reglas = raiz / "00_System" / "reglas.json"
        reglas.write_bytes(b'\xef\xbb\xbf{"no_borrar": ["19_Audits"]}')
        assert vault_io.reglas_declaradas(raiz)["no_borrar"] == ["19_Audits"]

        # 2) Archivo vacío o solo espacios significa sin reglas (no bloqueo)
        reglas.write_text("   \n", encoding="utf-8")
        (raiz / "00_System" / "inmutable.json").write_text("", encoding="utf-8")
        assert vault_io.reglas_declaradas(raiz) == {"inmutable": [], "no_borrar": []}

        # 3) Corrupto sigue fallando cerrado (AP-70)
        reglas.write_text("{roto", encoding="utf-8")
        with pytest.raises(vault_io.PoliticaInvalidaError):
            vault_io.reglas_declaradas(raiz)
    finally:
        vault_io.set_vault_root(previa)


def test_dz02_vault_write_devuelve_envelope_canonico_ante_politica_invalida(tmp_path):
    import vault_io
    import vault_write

    raiz = tmp_path / "vault"
    (raiz / "00_System").mkdir(parents=True)
    (raiz / "07_Knowledge").mkdir(parents=True)
    (raiz / "00_System" / "reglas.json").write_text("{corrupto", encoding="utf-8")
    previa = vault_io.set_vault_root(raiz)
    try:
        res = vault_write.vault_write(
            folder="07_Knowledge",
            title="Nota de prueba",
            content=(
                "Primera linea con contenido real suficiente para el gate.\n\n"
                "Segunda linea con detalle de prueba para validar el envelope.\n\n"
                "Tercera linea cerrando el cuerpo de prueba.\n"
            ),
            tags=["prueba"],
            meta={"agent": "pytest"},
        )
        assert isinstance(res, dict)
        assert res["ok"] is False
        assert res["error_code"] == "INVALID_INPUT", res
    finally:
        vault_io.set_vault_root(previa)


def test_dz03_security_scan_escanea_un_solo_archivo_sin_ruta_de_maquina(tmp_path):
    import vault_io
    import vault_security_scan as sec

    vault = tmp_path / "vault"
    vault.mkdir()
    src = tmp_path / "src"
    src.mkdir()
    archivo = src / "auth_vuln.py"
    archivo.write_text(
        'password = "hunter22_secret_value"\nimport subprocess\nsubprocess.run(cmd, shell=True)\n',
        encoding="utf-8",
    )

    previa = vault_io.set_vault_root(vault)
    try:
        r = sec.vault_security_scan(str(archivo), save_findings=False)
        assert r["ok"] is True, r
        assert r["filesScanned"] == 1, r
        assert r["filesWithFindings"] == 1, r
        assert r["totalFindings"] >= 1, r
        for f in r["findings"]:
            assert f["file"] == "auth_vuln.py", f
            assert str(tmp_path) not in f["file"], f
    finally:
        vault_io.set_vault_root(previa)


def test_dz04_requirement_save_reporta_y_adopta_legado_explicitamente(tmp_path):
    import vault_io
    import vault_requirement_save as reqs

    root = copiar_vault(tmp_path / "vault", "demo")
    previa = vault_io.set_vault_root(root)
    try:
        # Nota legada válida en disco, sin índice ni fila de requisito en change-log
        carpeta = root / "14_Requirements" / "demo"
        carpeta.mkdir(parents=True, exist_ok=True)
        nota_legada = carpeta / "req-001-legado.md"
        nota_legada.write_text(
            "---\n"
            "id: 11111111-1111-4111-8111-111111111111\n"
            "title: Requisito legado\n"
            "type: requirement\n"
            "project: demo\n"
            "req_id: REQ-001\n"
            "req_type: functional\n"
            "priority: must-have\n"
            "status: draft\n"
            "requirement_state: draft\n"
            "tags: [demo, requirement]\n"
            "createdAt: '2026-01-01T00:00:00.000Z'\n"
            "updatedAt: '2026-01-01T00:00:00.000Z'\n"
            "---\n\n# Requisito legado\n\nTexto legado real suficiente.\n",
            encoding="utf-8",
        )
        indice = root / "14_Requirements" / ".requirements-index.json"
        if indice.exists():
            indice.unlink()

        # Por defecto falla cerrado e informa qué identidades faltan y la vía explícita
        bloqueado = reqs.reconstruir_indice_requisitos()
        assert bloqueado["ok"] is False
        assert bloqueado["history_incomplete"] is True
        assert "demo/REQ-001" in bloqueado.get("unmatched_identities", []), bloqueado
        assert bloqueado.get("recovery", {}).get("action") == "manual", bloqueado

        # Con adopción explícita desbloquea sin inventar transiciones intermedias
        adoptado = reqs.reconstruir_indice_requisitos(adoptar_legado=True)
        assert adoptado["ok"] is True, adoptado
        assert "demo/REQ-001" in adoptado.get("adopted", []), adoptado

        # Y ahora se puede guardar un requisito nuevo normalmente (REQ-002)
        nuevo = reqs.vault_requirement_save(
            project="demo",
            title="Nuevo requisito tras adopcion",
            description="Descripcion suficientemente clara para el requisito nuevo.",
            req_type="functional",
            priority="must-have",
            status="draft",
        )
        assert nuevo["ok"] is True, nuevo
        assert nuevo["req_id"] == "REQ-002", nuevo
    finally:
        vault_io.set_vault_root(previa)


def test_dz06_portabilidad_terceros_sin_syntax_warning():
    fuente = (ROOT / "tests" / "test_portabilidad_terceros.py").read_text(encoding="utf-8")
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", SyntaxWarning)
        compile(fuente, "tests/test_portabilidad_terceros.py", "exec")
    syntax_warnings = [w for w in avisos if issubclass(w.category, SyntaxWarning)]
    assert syntax_warnings == [], [str(w.message) for w in syntax_warnings]
