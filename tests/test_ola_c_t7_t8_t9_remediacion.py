"""Tests RED -> GREEN para Ola C (T-7, T-8, T-9).

- T-7 (H-12): `docs/MODO-AGENTICO-ORQUESTACION.md` refleja los 72 patrones del
  catalogo canonico `CATALOGO_PATRONES` y `vault_doc_counts` vigila la cifra (AP-47).
- T-8 (H-14): el job `lint` de `.github/workflows/vault-ci.yml` ejecuta `ruff check`
  sobre `vault/`, `scripts/` y `cli/` con las reglas bloqueantes
  `F821,F841,E722,B904,RUF034,SIM223`.
- T-9 (H-21): `.github/workflows/vault-ci.yml` declara `permissions: contents: read`
  de minimo privilegio y fija todas las GitHub Actions por SHA de 40 hex.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CI_PATH = REPO / ".github" / "workflows" / "vault-ci.yml"
SHA_REF_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def test_t7_doc_counts_vigila_patrones_y_orquestacion_sin_drift():
    import vault_doc_counts
    from vault.kernel.patrones_diseno import CATALOGO_PATRONES

    fact_ids = {f["id"] for f in vault_doc_counts.COUNTED_FACTS}
    assert "design_patterns" in fact_ids, (
        "T-7: vault_doc_counts debe registrar el conteo canonico `design_patterns`"
    )
    assert "docs/MODO-AGENTICO-ORQUESTACION.md" in vault_doc_counts.WATCHED_DOCS, (
        "T-7: docs/MODO-AGENTICO-ORQUESTACION.md debe estar en WATCHED_DOCS"
    )
    res = vault_doc_counts.scan(
        docs=["docs/MODO-AGENTICO-ORQUESTACION.md"],
        include_slow=False,
    )
    assert res["ok"] is True, f"T-7 drift detectado: {res['mismatches']}"
    assert res["values"]["design_patterns"] == len(CATALOGO_PATRONES)
    assert res["claims_checked"] >= 1


def test_t7_doc_counts_detecta_drift_de_patrones_en_doc_temporal(tmp_path, monkeypatch):
    import vault_doc_counts

    doc = tmp_path / "doc.md"
    doc.write_text("Catalogo oficial: `patrones_diseno.py` (70 patrones en 5 categorias).\n", encoding="utf-8")
    monkeypatch.setattr(vault_doc_counts, "REPO_ROOT", tmp_path)
    res = vault_doc_counts.scan(docs=["doc.md"], include_slow=False)
    assert res["ok"] is False
    assert any(m["fact"] == "design_patterns" and m["claimed"] == 70 for m in res["mismatches"])


def test_t8_ci_lint_ejecuta_ruff_con_reglas_bloqueantes():
    wf = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    lint_job = wf["jobs"]["lint"]
    runs = "\n".join(str(step.get("run") or "") for step in lint_job.get("steps", []))
    assert "ruff check" in runs, "T-8: el job lint debe ejecutar ruff check"
    for regla in ("F821", "F841", "E722", "B904", "RUF034", "SIM223"):
        assert regla in runs, f"T-8: falta la regla bloqueante {regla} en lint"
    for ruta in ("vault/", "scripts/", "cli/"):
        assert ruta in runs, f"T-8: ruff check debe cubrir {ruta}"


def test_t9_ci_declara_permissions_minimas_y_fija_actions_por_sha():
    wf = yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))
    assert wf.get("permissions") == {"contents": "read"}, (
        f"T-9: vault-ci.yml debe declarar permissions: contents: read, tiene {wf.get('permissions')!r}"
    )
    uses_list = []
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []):
            if "uses" in step:
                uses_list.append((job_name, step["uses"]))
    assert uses_list, "T-9: no se encontraron steps con uses"
    sin_sha = [(j, u) for j, u in uses_list if not SHA_REF_RE.match(u)]
    assert sin_sha == [], f"T-9: GitHub Actions sin fijar por SHA completo: {sin_sha}"
