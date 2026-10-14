"""`vault_quality_check` puntuaba como nota lo que una tool regenera (AP-57).

`00_System/change-log.md` lo escribe `vault_change_log` como tabla, sin
frontmatter, y `vault_registry.DERIVED_ARTIFACTS` lo declara derivado. La
calidad no consultaba a nadie: lo puntuaba como nota, con integridad 0 y los
cuatro campos del contrato «faltantes», y un vault recién creado con
`vault init` arrancaba con una nota bajo 0.7 que ningún agente puede arreglar
sin pelearse con la tool que la regenera. `vault_audit` ya decidía la clase con
el dueño, `vault_contrato_nota.clase_de_nota`; la calidad pasa a hacer lo mismo.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_io  # noqa: E402
import vault_quality_check as q  # noqa: E402
from vault_registry import DERIVED_ARTIFACTS  # noqa: E402


def test_ap57_un_artefacto_derivado_no_se_puntua_como_nota(tmp_path):
    vault = tmp_path / "vault"
    for d in ("00_System", "99_Index", "07_Knowledge"):
        (vault / d).mkdir(parents=True)
    for rel in DERIVED_ARTIFACTS:
        (vault / rel).write_text("# Derivado\n\n| a | b |\n|---|---|\n", encoding="utf-8")
    # Una nota de contenido sin frontmatter sí se puntúa: la exención es de la
    # clase, no de la falta de frontmatter.
    (vault / "07_Knowledge" / "suelta.md").write_text("# Suelta\n\ntexto\n", encoding="utf-8")
    vault_io.set_vault_root(vault)

    r = q.vault_quality_check(check_only=True)
    assert r["ok"], r
    assert not set(DERIVED_ARTIFACTS) & set(r["notes"]), sorted(r["notes"])
    assert "07_Knowledge/suelta.md" in r["notes"]
