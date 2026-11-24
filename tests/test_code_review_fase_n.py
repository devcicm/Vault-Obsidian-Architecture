"""Tests TDD de Fase N2/N3: vault_code_review (7 ejes, diff git, RDD, PAT-10, seguridad y visor HTML)."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import vault_code_review
import vault_io


def _git(repo: Path, *args: str) -> None:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    assert r.returncode == 0


def _crear_vault_n2(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault-n2"
    for d in ("00_System", "03_Decisions", "11_Code/tienda", "14_Requirements/tienda", "15_Tests/unit", "19_Audits"):
        (raiz / d).mkdir(parents=True, exist_ok=True)

    (raiz / "14_Requirements" / "tienda" / "req-042-calculo-iva.md").write_text(
        textwrap.dedent(
            """\
            ---
            req_id: REQ-042
            title: Calculo de IVA
            project: tienda
            type: requirement
            status: approved
            related_code: src/fiscal.py
            ---
            # REQ-042 — Calculo de IVA

            ## Reglas de negocio
            - Tasa vigente: 16 % con redondeo a 2 decimales.
            """
        ),
        encoding="utf-8",
    )

    (raiz / "03_Decisions" / "adr-0001-tasa-vieja.md").write_text(
        textwrap.dedent(
            """\
            ---
            title: ADR-0001 Tasa vieja
            project: tienda
            type: adr
            status: superseded
            superseded_by: 14_Requirements/tienda/req-042-calculo-iva.md
            ---
            # ADR-0001
            """
        ),
        encoding="utf-8",
    )

    (raiz / "15_Tests" / "unit" / "test-iva.md").write_text(
        "---\ntitle: Tests IVA\nproject: tienda\ntest_type: unit\nrelated_requirement: REQ-042\n---\n# Tests IVA\n",
        encoding="utf-8",
    )
    return raiz


def _crear_repo_git(tmp_path: Path) -> Path:
    repo = tmp_path / "repo-tienda"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "Dev")
    (repo / "src" / "fiscal.py").write_text("# base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "chore: base")
    return repo


def test_code_review_pr_limpio_resuelve_reglas_vivas_rdd_y_genera_visor_html_clicable(tmp_path: Path):
    vault = _crear_vault_n2(tmp_path)
    repo = _crear_repo_git(tmp_path)

    (repo / "src" / "fiscal.py").write_text(
        textwrap.dedent(
            '''\
            """Servicio fiscal: eval('ejemplo en docstring no debe disparar alerta')."""

            class FiscalService:
                # @vault: REQ-042 — Reglas de calculo de IVA
                def calcular_iva(self, subtotal: float) -> float:
                    return round(subtotal * 0.16, 2)
            '''
        ),
        encoding="utf-8",
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_fiscal.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: calcular_iva con REQ-042")

    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_code_review.vault_code_review(
            path=str(repo),
            project="tienda",
            base="HEAD~1",
            head="HEAD",
            html_preview=True,
            save=True,
        )
        assert res["ok"] is True, res
        assert res["verdict"] == "APPROVE", res["findings"]
        assert res["summary"]["blockers"] == 0
        assert res["summary"]["warnings"] == 0
        assert len(res["applicable_rules"]) == 1
        assert "16 %" in res["applicable_rules"][0]["rules_excerpt"]
        assert res["applicable_rules"][0]["links"]["obsidian_uri"].startswith("obsidian://open?")
        assert any(s["symbol"] == "FiscalService.calcular_iva" for s in res["touched_symbols"])
        assert "14_Requirements/tienda/req-042-calculo-iva.md" in res["vault_impact"]["direct_notes"]
        assert res["rdd_traceability"]["full_coverage"] == 1

        # Visor HTML clicable y acta Markdown creados dentro del vault (AP-36)
        assert res["html_preview_path"] is not None
        html_txt = (vault / res["html_preview_path"]).read_text(encoding="utf-8")
        assert 'data-vault-ref="REQ-042"' in html_txt
        assert "code-line changed" in html_txt

        assert res["saved_report_path"] is not None
        assert (vault / res["saved_report_path"]).is_file()
    finally:
        vault_io.set_vault_root(prev)


def test_code_review_detecta_bloqueantes_ref_rota_seguridad_stale_y_pat10_sin_doc(tmp_path: Path):
    vault = _crear_vault_n2(tmp_path)
    repo = _crear_repo_git(tmp_path)

    token_falso = "ghp_" + "A" * 36
    (repo / "src" / "fiscal.py").write_text(
        textwrap.dedent(
            f"""\
            class FiscalService:
                # @vault: REQ-999 — No existe (AP-72)
                def calcular_iva(self, subtotal: float) -> float:
                    return eval(str(subtotal))

                # @vault: ADR-0001 — Decision obsoleta
                def tasa_vieja(self) -> float:
                    api_tok = "{token_falso}"
                    try:
                        return 0.15
                    except Exception:
                        pass

                def validar_regla_sin_tag(self, monto: float) -> bool:
                    return monto > 0
            """
        ),
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: cambios con defectos")

    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_code_review.vault_code_review(
            path=str(repo),
            project="tienda",
            base="HEAD~1",
            head="HEAD",
        )
        assert res["ok"] is True
        assert res["verdict"] == "REQUEST_CHANGES"
        codes = {f["code"] for f in res["findings"]}
        assert "AP-72" in codes
        assert "SEC_DYNAMIC_EXEC" in codes
        assert "SEC_SECRET" in codes
        assert "STALE_VAULT_REF" in codes
        assert "AP-51" in codes
        assert "MISSING_BUSINESS_DOC_REF" in codes
        assert "NO_TESTS_TOUCHED" in codes
    finally:
        vault_io.set_vault_root(prev)


def test_code_review_sin_repo_enlazado_devuelve_no_data_y_git_invalido_falla_cerrado(tmp_path: Path):
    vault = _crear_vault_n2(tmp_path)
    repo = _crear_repo_git(tmp_path)
    prev = vault_io.set_vault_root(vault)
    try:
        res = vault_code_review.vault_code_review(project="tienda")
        assert res["ok"] is True
        assert res["verdict"] == "NO_DATA"
        assert res["review_scope"] == "no_repo_linked"
        assert res["summary"]["files_reviewed"] == 0

        # Fallo cerrado (AP-51/AP-60): --base inexistente NO aprueba
        err = vault_code_review.vault_code_review(
            path=str(repo), project="tienda", base="rama-inexistente-xyz"
        )
        assert err["ok"] is False
    finally:
        vault_io.set_vault_root(prev)


def test_code_review_sin_falsos_positivos_en_self_scan_js_regexp_y_pat10(tmp_path: Path):
    from vault.kernel import code_review as cr_mod
    from vault.kernel import features_y_flujos as fyf

    vault = _crear_vault_n2(tmp_path)
    js_file = tmp_path / "matcher.js"
    js_file.write_text(
        "export function parsePattern(rx, txt) {\n  return rx.exec(txt);\n}\n",
        encoding="utf-8",
    )

    # PAT-10 por fronteras de token (sin substrings ingenuos)
    assert fyf.clasificar_operaciones_negocio("ui/table.py", "reorder_border", "function") == ["unclassified"]
    assert fyf.clasificar_operaciones_negocio("math/stats.py", "normal_distribution", "function", calls=("digital_filter",)) == ["unclassified"]
    assert fyf.clasificar_operaciones_negocio("io/stream.py", "close_handle", "function") == ["unclassified"]
    assert "rule" in fyf.clasificar_operaciones_negocio("src/fiscal.py", "calcular_iva", "method")
    assert "workflow" in fyf.clasificar_operaciones_negocio("src/orders.py", "create_order", "method")

    prev = vault_io.set_vault_root(vault)
    try:
        # RegExp.prototype.exec en JS NO es blocker SEC_DYNAMIC_EXEC
        r_js = vault_code_review.vault_code_review(path=str(tmp_path), files=[str(js_file)])
        assert r_js["ok"] is True
        assert not any(f["code"] == "SEC_DYNAMIC_EXEC" for f in r_js["findings"]), r_js["findings"]

        # Self-scan de vault/kernel/code_review.py y trazabilidad_codigo.py (incl. CSS user-select en f-string):
        # 0 falsos positivos de seguridad
        self_py = Path(cr_mod.__file__).resolve()
        traz_py = self_py.with_name("trazabilidad_codigo.py")
        r_self = vault_code_review.vault_code_review(
            path=str(self_py.parents[2]), files=[str(self_py), str(traz_py)], include_rdd=False
        )
        assert r_self["ok"] is True
        sec_blockers = [f for f in r_self["findings"] if f["code"].startswith("SEC_")]
        assert sec_blockers == [], sec_blockers
    finally:
        vault_io.set_vault_root(prev)
