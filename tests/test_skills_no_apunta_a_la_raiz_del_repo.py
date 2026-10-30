"""A-12 — `docs/SKILLS.md` mandaba `export VAULT_ROOT=$(pwd)` en la raiz del repo.

La raiz del repo no es un vault (AGENTS.md, regla 1): una tool de escritura
lanzada tras ese `export` sembraria `00_System/` en el estandar.
"""
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "docs" / "SKILLS.md"


def test_skills_no_manda_vault_root_a_la_raiz_del_repo():
    for n, linea in enumerate(SKILLS.read_text(encoding="utf-8").splitlines(), 1):
        assert "VAULT_ROOT=$(pwd)" not in linea.replace("/vault-sandbox", "") or "vault-sandbox" in linea, (n, linea)
