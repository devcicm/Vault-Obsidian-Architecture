"""AP-64 — una decisión cerrada sin nadie que responda de su porqué.

Un ADR aprobado es lo que un agente consulta antes de actuar: «esto se decidió
así y por esto». Si nadie responde de ese porqué, el agente no puede distinguir
una decisión humana de una que otro agente escribió y se aprobó a sí mismo.
Medido contra /ans (regla 7, 2026-10-08): ninguno de sus ADR aceptados declara
quién responde de él, y la mayoría tampoco declara `agent`.

El criterio tiene un dueño, `vault.kernel.contenido.falta_de_responsable`, y lo
leen el scan y la auditoría. El régimen del estado lo deriva
`vault_registry.regimen_de_estado`: el núcleo no lo copia.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import vault_io  # noqa: E402

ADR = "# ADR\n\n## Contexto\nx\n\n## Decisión\ny\n\n## Consecuencias\nz\n"


@pytest.mark.parametrize("fm,regimen,marcada", [
    ({"status": "approved"}, "cerrado", True),
    ({"status": "approved", "responsable": "Carlos"}, "cerrado", False),
    ({"status": "approved", "responsable": "  "}, "cerrado", True),
    # Un agente que firma como responsable de lo que él mismo escribió.
    ({"status": "approved", "agent": "claude", "responsable": "Claude"}, "cerrado", True),
    ({"status": "approved", "agent": "human", "responsable": "human"}, "cerrado", False),
    ({"status": "draft"}, "abierto", False),        # aún se discute
    ({"status": "archived"}, "terminal", False),     # ya no se consulta como vigente
    ({"status": "template"}, "cerrado", False),      # andamiaje, no decisión
])
def test_ap64_criterio(fm, regimen, marcada):
    from vault.kernel.contenido import falta_de_responsable
    assert bool(falta_de_responsable(fm, regimen)) is marcada


@pytest.fixture
def vault(tmp_path):
    raiz = tmp_path / "v"
    for s in ("00_System", "03_Decisions", "07_Knowledge"):
        (raiz / s).mkdir(parents=True)
    previo = vault_io.get_vault_root()
    vault_io.set_vault_root(raiz)
    yield raiz
    vault_io.set_vault_root(previo)


def _escribe(raiz, rel, fm):
    (raiz / rel).write_text(f"---\n{fm}\n---\n{ADR}", encoding="utf-8")


def _ap64(scan):
    return [n for n in scan["applicable_norms"] if n["code"] == "AP-64"]


def test_ap64_scan_y_auditoria_marcan_lo_mismo(vault):
    """`accepted` es sinónimo de `approved` (cerrado); `proposed`, de `planned`
    (abierto). Los dos detectores normalizan antes de decidir."""
    import vault_norms
    from vault.gobernanza.auditoria_runtime import auditar_runtime
    base = "title: ADR\ntype: adr\n"
    _escribe(vault, "03_Decisions/adr-sin.md", base + "status: accepted")
    _escribe(vault, "03_Decisions/adr-con.md", base + "status: accepted\nresponsable: Carlos")
    _escribe(vault, "03_Decisions/adr-abierto.md", base + "status: proposed")
    _escribe(vault, "07_Knowledge/nota.md", "title: Nota\ntype: concept\nstatus: approved")
    auditoria = {v["path"] for v in auditar_runtime(vault)["violations"] if v["norm"] == "AP-64"}
    assert auditoria == {"03_Decisions/adr-sin.md"}, auditoria
    for rel in ("03_Decisions/adr-sin.md", "03_Decisions/adr-con.md",
                "03_Decisions/adr-abierto.md", "07_Knowledge/nota.md"):
        assert bool(_ap64(vault_norms.vault_norms_scan(rel))) is (rel == "03_Decisions/adr-sin.md"), rel


def test_ap64_catalogo_y_contrato():
    from vault_contrato_nota import CAMPOS
    from vault_norms_catalog import norma_por_codigo
    ap64 = norma_por_codigo("AP-64")
    assert ap64["enforcement"] == "audit" and ap64["tools_detecting"] == ["vault_norms"]
    for vecina in ("AP-07", "AP-16"):
        assert vecina in ap64["distinguido_de"]
        assert "AP-64" in norma_por_codigo(vecina)["distinguido_de"]
    assert CAMPOS["responsable"]["norma"] == "AP-64"
