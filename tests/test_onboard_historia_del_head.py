"""The onboarding describes the checked-out commit, not every branch (brownfield BF-02).

Measured on 2026-11-19: onboarding this repository checked out at `main` produced
5 retroactive ADRs, 3 of them from commits of an unmerged branch, all signed
`provenance: ... (a2e70827)`, and reported 1568 commits for a HEAD with 1508. The
log across all refs stays for what it is good at (hidden history: an older first
date elsewhere), but the content that asserts the project's state at HEAD
(decisions, phases, contributors, last commit, total) comes from HEAD's history.
"""

import pytest

from apoyo import correr_tool, entorno, git_en
from test_onboard_escalonado import _commit, _escribir

SUJETO_LATERAL = "refactor: migrate the order storage to postgres in a side experiment"


@pytest.fixture(scope="module")
def repo_con_rama(tmp_path_factory):
    p = tmp_path_factory.mktemp("repo-rama-lateral")
    _escribir(p, "README.md", "# demo-rama\n\nAPI de prueba con una rama lateral sin integrar.\n")
    _escribir(p, "src/app.py", "def main():\n    return 1\n")
    git_en(p, "init", "-b", "main", check=True)
    git_en(p, "config", "user.email", "t@example.com", check=True)
    git_en(p, "config", "user.name", "Tester", check=True)
    _commit(p, "feat: first version of the api", "2026-01-10")
    git_en(p, "checkout", "-b", "lado", check=True)
    _escribir(p, "src/storage.py", "STORE = 'postgres'\n")
    _commit(p, SUJETO_LATERAL, "2026-02-01")
    lateral = git_en(p, "rev-parse", "--short", "HEAD", check=True).strip()
    git_en(p, "checkout", "main", check=True)
    _escribir(p, "src/app.py", "def main():\n    return 2\n")
    _commit(p, "refactor: switch to the repository layer for orders", "2026-03-01")
    return p, lateral


@pytest.fixture(scope="module")
def onboarding(tmp_path_factory, repo_con_rama):
    repo, lateral = repo_con_rama
    v = tmp_path_factory.mktemp("vault-rama")
    assert correr_tool("vault_init", env=entorno(v, VAULT_TOOL_TIMEOUT="600"), timeout=600).codigo == 0
    r = correr_tool("vault_onboard", "--project", "demo-rama", "--path", repo,
                    env=entorno(v, VAULT_TOOL_TIMEOUT="600"), timeout=600)
    assert r.codigo == 0 and r.envelope.get("ok"), r.stdout[-1500:] + r.stderr[-1500:]
    return v, r.envelope, lateral


def test_ninguna_decision_sale_de_una_rama_que_head_no_contiene(onboarding):
    v, _, lateral = onboarding
    adrs = "\n".join(n.read_text(encoding="utf-8") for n in (v / "03_Decisions").glob("adr-*.md"))
    assert lateral not in adrs and "postgres" not in adrs.lower(), adrs[:1500]
    assert "repository layer" in adrs.lower(), "the decision on HEAD must still be found"


def test_el_total_es_el_de_head_y_las_demas_refs_se_cuentan_aparte(onboarding):
    _, env, _ = onboarding
    historia = env["git_history"]
    assert historia["total_commits"] == 2, historia
    assert historia["total_commits_all_refs"] == 3, historia
