"""Exercise the workflow gate with deterministic local certification evidence."""

import hashlib
import os
import sys

import pytest
import yaml

from apoyo import ROOT, correr_python

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="workflow uses tomllib"
)

SHA = "a" * 40


def _gate():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    )
    step = next(
        s
        for s in workflow["jobs"]["publish"]["steps"]
        if s.get("name") == "El tag es el candidato autorizado"
    )
    return step["run"].split("python - <<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0]


def _run_gate(tmp_path, owner, qa, product_sha=SHA):
    """Run the real workflow gate body; `owner` is text, bytes, a directory marker or None."""
    audits = tmp_path / "audits"
    (audits / "fase2").mkdir(parents=True)
    owner_ref = "audits/owner.md"
    if owner == "<directory>":
        owner_ref = "audits/ownerdir"
        (audits / "ownerdir").mkdir()
    elif isinstance(owner, bytes):
        (audits / "owner.md").write_bytes(owner)
    elif owner is not None:
        (audits / "owner.md").write_text(
            f"Certified product: `{owner}`\n", encoding="utf-8"
        )
    qa_ref = qa
    if qa not in ("PENDIENTE", "OMITIDO_POR_PROPIETARIO"):
        (audits / "qa.md").write_text(f"Tested product: `{qa}`\n", encoding="utf-8")
        qa_ref = "audits/qa.md"
    manifest = {
        "release_candidate": {
            "version": "1.0",
            "product_sha": product_sha,
            "product_tree_sha": "tree",
        },
        "verification": {"ci": {"run_sha": product_sha, "conclusion": "success"}},
        "governance": {
            "release_authorized": True,
            "qg_statuses": {f"QG-0{i}": "PASS" for i in range(8)},
            "owner_decision_ref": owner_ref,
            "qa_verdict_ref": qa_ref,
        },
    }
    (audits / "fase2/CANDIDATO-RELEASE.yaml").write_text(
        yaml.safe_dump(manifest), encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "1.0"\n', encoding="utf-8"
    )
    # Only the unrelated git certification checks are stubbed. Execute the
    # actual workflow Python body, including exit/output and evidence reads.
    bootstrap = (
        "import subprocess\n"
        "def git_result(args, **kwargs):\n"
        " assert args[0] == 'git'\n"
        " return subprocess.CompletedProcess(args, 0, stdout='tree\\n', stderr='')\n"
        "subprocess.run = git_result\n"
    )

    def snapshot():
        return {
            p.relative_to(tmp_path).as_posix(): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in tmp_path.rglob("*")
            if p.is_file()
        }

    before = snapshot()
    result = correr_python(
        "-c", bootstrap + _gate(), cwd=tmp_path,
        env={**os.environ, "GITHUB_REF_NAME": "v1.0"},
        modo="text", timeout=30,
    )
    assert result.stderr == ""
    assert snapshot() == before
    return result


@pytest.mark.parametrize(
    "owner,qa,accepted",
    [
        (SHA, SHA, True),
        (SHA, "PENDIENTE", True),
        (SHA, "OMITIDO_POR_PROPIETARIO", True),
        ("b" * 40, SHA, False),
        (SHA, "b" * 40, False),
        (SHA[:7], SHA, False),
        ("0" + SHA + "0", SHA, False),
        (None, SHA, False),
    ],
)
def test_release_requires_candidate_bound_evidence(tmp_path, owner, qa, accepted):
    result = _run_gate(tmp_path, owner, qa)
    assert result.returncode == (0 if accepted else 1), result.stdout + result.stderr
    assert ("OK: v1.0" if accepted else "NO SE PUBLICA:") in result.stdout


@pytest.mark.parametrize(
    "case,owner,product_sha,fragment",
    [
        ("abbreviated_product_sha", SHA[:7], SHA[:7], "product_sha"),
        ("invalid_utf8_evidence", b"\xff\xfe" + SHA.encode(), SHA, "owner_decision_ref"),
        ("directory_evidence", "<directory>", SHA, "owner_decision_ref"),
    ],
)
def test_release_fails_closed_on_unverifiable_identity_or_evidence(tmp_path, case, owner,
                                                                    product_sha, fragment):
    result = _run_gate(tmp_path, owner, "PENDIENTE", product_sha=product_sha)
    assert result.returncode == 1, case + result.stdout
    assert "NO SE PUBLICA:" in result.stdout and fragment in result.stdout
