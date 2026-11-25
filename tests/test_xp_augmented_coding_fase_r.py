"""Tests Fase R (C17-C20) — Protocolo XP / Augmented Coding (SPEC-03, SP-06)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vault_io
import vault_preferences
import vault_requirement_save
from vault.kernel.code_review import ejecutar_code_review


def _preparar_vault(tmp_path: Path, reglas: dict | None = None) -> Path:
    vault = tmp_path / "vault"
    for carpeta in (
        "00_System",
        "01_Projects",
        "03_Decisions",
        "14_Requirements",
        "15_Tests",
        "17_Preferences",
    ):
        (vault / carpeta).mkdir(parents=True, exist_ok=True)
    if reglas is not None:
        (vault / "00_System" / "reglas.json").write_text(
            json.dumps(reglas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return vault


def test_r_escalera_xp_niveles_1_a_4_y_retrocompatibilidad(tmp_path: Path, monkeypatch):
    # Sin xp_level declarado: retrocompatible (None)
    vault_sin_xp = _preparar_vault(tmp_path / "v0", {"no_borrar": ["12_Bibliography"]})
    assert vault_io.xp_level_declarado(vault_sin_xp) is None

    # Nivel 1, 2, 3 válidos
    for nivel in (1, 2, 3):
        v = _preparar_vault(tmp_path / f"v{nivel}", {"xp_level": nivel})
        assert vault_io.xp_level_declarado(v) == nivel

    # Nivel inválido falla cerrado (AP-70 / SP-06)
    v_bad = _preparar_vault(tmp_path / "v_bad", {"xp_level": 9})
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.xp_level_declarado(v_bad)

    v_bool = _preparar_vault(tmp_path / "v_bool", {"xp_level": True})
    with pytest.raises(vault_io.PoliticaInvalidaError):
        vault_io.xp_level_declarado(v_bool)

    # Nivel 4 sin prerequisitos falla cerrado
    v4_fail = _preparar_vault(tmp_path / "v4_fail", {"xp_level": 4})
    with pytest.raises(vault_io.PoliticaInvalidaError) as exc_info:
        vault_io.xp_level_declarado(v4_fail)
    assert "xp_prerequisites" in str(exc_info.value)

    # Nivel 4 con ambos prerequisitos verificados pasa
    v4_ok = _preparar_vault(
        tmp_path / "v4_ok",
        {
            "xp_level": 4,
            "xp_prerequisites": {"tdd_pass": True, "human_pair_review": True},
        },
    )
    assert vault_io.xp_level_declarado(v4_ok) == 4


def test_r_requirement_buffer_y_compuerta_tdd_nivel_2(tmp_path: Path):
    vault = _preparar_vault(tmp_path, {"xp_level": 2})
    vault_io.set_vault_root(vault)
    try:
        # Crear requisito con buffer=critical siguiendo el ciclo de vida: draft -> approved
        res_ok = vault_requirement_save.vault_requirement_save(
            title="Login con sesion corta",
            req_type="functional",
            priority="must-have",
            project="demo",
            status="draft",
            description="El usuario autentica con token de vida corta.",
            acceptance_criteria=["Emite token", "Expira en 15m"],
            buffer="critical",
        )
        assert res_ok["ok"] is True, res_ok
        assert res_ok["buffer"] == "critical"
        req_id = res_ok["req_id"]
        contenido = (vault / res_ok["path"]).read_text(encoding="utf-8")
        assert "buffer: critical" in contenido

        res_rev = vault_requirement_save.vault_requirement_save(
            title="Login con sesion corta",
            req_id=req_id,
            req_type="functional",
            priority="must-have",
            project="demo",
            status="reviewed",
            description="El usuario autentica con token de vida corta.",
            acceptance_criteria=["Emite token", "Expira en 15m"],
            buffer="critical",
        )
        assert res_rev["ok"] is True, res_rev

        res_app = vault_requirement_save.vault_requirement_save(
            title="Login con sesion corta",
            req_id=req_id,
            req_type="functional",
            priority="must-have",
            project="demo",
            status="approved",
            description="El usuario autentica con token de vida corta.",
            acceptance_criteria=["Emite token", "Expira en 15m"],
            buffer="critical",
        )
        assert res_app["ok"] is True, res_app

        # Pasar a implemented SIN evidencia TDD en 15_Tests/: bloqueado por SP-06
        res_block = vault_requirement_save.vault_requirement_save(
            title="Login con sesion corta",
            req_id=req_id,
            req_type="functional",
            priority="must-have",
            project="demo",
            status="implemented",
            description="Implementado pero sin nota de test en verde.",
            acceptance_criteria=["Emite token", "Expira en 15m"],
        )
        assert res_block["ok"] is False
        assert res_block["error_code"] == "VALIDATION_FAILED"
        assert "SP-06" in res_block["message"]

        # Registrar evidencia de test en verde en 15_Tests/ vinculada al requisito
        (vault / "15_Tests" / "test-login-sesion.md").write_text(
            "---\n"
            "title: Test Login Sesion\n"
            "type: test\n"
            "status: verified\n"
            "test_result: pass\n"
            f"links:\n  - '[[{req_id}]]'\n"
            "---\n\n"
            f"Prueba unitaria en verde para {req_id}.\n",
            encoding="utf-8",
        )

        # Ahora implemented pasa con éxito
        res_pass = vault_requirement_save.vault_requirement_save(
            title="Login con sesion corta",
            req_id=req_id,
            req_type="functional",
            priority="must-have",
            project="demo",
            status="implemented",
            description="Implementado con prueba unitaria en verde.",
            acceptance_criteria=["Emite token", "Expira en 15m"],
        )
        assert res_pass["ok"] is True, res_pass
        assert res_pass["action"] == "updated"
        assert "status: implemented" in (vault / res_pass["path"]).read_text(encoding="utf-8")
    finally:
        vault_io.reset_vault_root()


def test_r_requirement_retrocompat_sin_buffer_ni_xp(tmp_path: Path):
    vault = _preparar_vault(tmp_path)
    vault_io.set_vault_root(vault)
    try:
        res_draft = vault_requirement_save.vault_requirement_save(
            title="Requisito clasico sin XP",
            req_type="functional",
            priority="should-have",
            project="demo",
            status="draft",
            description="Sin xp_level no bloquea y sin --buffer no emite clave buffer.",
        )
        assert res_draft["ok"] is True, res_draft
        req_id = res_draft["req_id"]
        for estado in ("reviewed", "approved", "implemented"):
            res = vault_requirement_save.vault_requirement_save(
                title="Requisito clasico sin XP",
                req_id=req_id,
                req_type="functional",
                priority="should-have",
                project="demo",
                status=estado,
                description="Sin xp_level no bloquea y sin --buffer no emite clave buffer.",
            )
            assert res["ok"] is True, res
        assert "buffer" not in res
        texto = (vault / res["path"]).read_text(encoding="utf-8")
        assert "buffer:" not in texto
    finally:
        vault_io.reset_vault_root()


def test_r_code_review_xp_nivel_2_y_3(tmp_path: Path):
    vault = _preparar_vault(tmp_path / "v_rev")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    # Fichero largo (>400 líneas) para disparar XP_MONOLITHIC_DIFF en Nivel 3
    lineas_codigo = [f"def fn_{i}(x):\n    return x + {i}\n" for i in range(220)]
    (repo / "src" / "motor.py").write_text("\n".join(lineas_codigo), encoding="utf-8")

    # Nivel 2: NO_TESTS_TOUCHED escala a blocker con norma SP-06
    res_l2 = ejecutar_code_review(
        vault_root=vault,
        repo_root=repo,
        files=["src/motor.py"],
        xp_level=2,
    )
    assert res_l2["ok"] is True
    assert res_l2["xp_level"] == 2
    tdd = [f for f in res_l2["findings"] if f["code"] == "NO_TESTS_TOUCHED"]
    assert len(tdd) == 1
    assert tdd[0]["severity"] == "blocker"
    assert tdd[0]["norm"] == "SP-06"
    assert res_l2["verdict"] == "REQUEST_CHANGES"

    # Nivel 3 sin --reviewer avisa XP_REVIEWER_MISSING; con revisor IA bloquea XP_REVIEWER_INVALID
    res_l3_missing = ejecutar_code_review(
        vault_root=vault,
        repo_root=repo,
        files=["src/motor.py"],
        xp_level=3,
    )
    assert any(f["code"] == "XP_REVIEWER_MISSING" for f in res_l3_missing["findings"])

    res_l3_ai = ejecutar_code_review(
        vault_root=vault,
        repo_root=repo,
        files=["src/motor.py"],
        xp_level=3,
        reviewer="claude",
    )
    codigos = {f["code"]: f for f in res_l3_ai["findings"]}
    assert "XP_MONOLITHIC_DIFF" in codigos
    assert codigos["XP_MONOLITHIC_DIFF"]["severity"] == "warning"
    assert "XP_REVIEWER_INVALID" in codigos
    assert codigos["XP_REVIEWER_INVALID"]["severity"] == "blocker"

    # Nivel 3 con test acompañado y revisor humano: no dispara TDD ni REVIEWER_INVALID
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_motor.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    res_l3_ok = ejecutar_code_review(
        vault_root=vault,
        repo_root=repo,
        files=["src/motor.py", "tests/test_motor.py"],
        xp_level=3,
        reviewer="Carlos Ivan",
    )
    codigos_ok = {f["code"] for f in res_l3_ok["findings"]}
    assert "NO_TESTS_TOUCHED" not in codigos_ok
    assert "XP_REVIEWER_INVALID" not in codigos_ok
    assert "XP_REVIEWER_MISSING" not in codigos_ok
    assert res_l3_ok["verdict"] != "REQUEST_CHANGES"


def test_r_adapters_clausula_xp_compacta_y_pat9(tmp_path: Path):
    vault = _preparar_vault(tmp_path, {"xp_level": 2})
    proyecto = tmp_path / "mi-app"
    proyecto.mkdir()
    vault_io.set_vault_root(vault)
    try:
        res = vault_preferences.vault_preferences_adapters(str(proyecto), force=True)
        assert res["ok"] is True
        assert len(res["adapters"]) >= 1
        for fila in res["adapters"]:
            texto = (proyecto / fila["adapter"]).read_text(encoding="utf-8")
            assert "## Augmented Coding (SP-06)" in texto
            assert "Nivel XP activo: `2`" in texto
            # PAT-9: techo estricto de 120 líneas por adaptador
            assert len(texto.splitlines()) <= 120
    finally:
        vault_io.reset_vault_root()
