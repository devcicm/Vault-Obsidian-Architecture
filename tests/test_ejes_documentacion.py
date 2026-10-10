"""Ejes de trazabilidad y versionado del marco de documentación, y su correlación.

La metodología decía qué clase de documento es cada sección, pero no con qué se
traza una nota de esa clase, cómo se versiona, ni qué cambia cuando su estado
avanza o cuando sube la versión del estándar. Prometía además un campo de
traza —`relacionado_con:`— que ninguna tool escribe. Los ejes viven en
`vault_registry`, el régimen de cada estado se deriva de STATUS_TRANSITIONS y
el SDD 06 lo publica todo derivado.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_registry as reg  # noqa: E402
import vault_sdd_init  # noqa: E402
from vault_contrato_nota import HISTORIA  # noqa: E402
from vault_mcp_catalog import TOOLS_CATALOG  # noqa: E402
from vault_norms_catalog import STATUS_TRANSITIONS, STATUS_VOCAB  # noqa: E402
from vault_registry import regimen_de_estado as _regimen  # noqa: E402

import vault_grafo_import as gi  # noqa: E402


def regimen_de_estado(status):
    return _regimen(status, STATUS_TRANSITIONS)


def test_toda_clase_de_documento_declara_sus_dos_ejes():
    assert list(reg.EJES_DOCUMENTACION) == list(reg.DOCUMENTACION_CLASES)
    for clase, e in reg.EJES_DOCUMENTACION.items():
        assert e["traza"].strip(), clase
        assert e["tools"], clase
        assert e["version"] in reg.MODOS_DE_VERSION, clase


def test_todo_modo_de_version_tiene_tool_viva_y_enforcement_no_manual():
    for modo, m in reg.MODOS_DE_VERSION.items():
        assert m["enforcement"] in ("guard", "audit", "guard+audit", "recommended"), modo
        for tool in m["tools"]:
            assert tool in TOOLS_CATALOG, (modo, tool)


def test_las_tools_de_cada_eje_estan_en_el_catalogo():
    for clase, e in reg.EJES_DOCUMENTACION.items():
        for tool in e["tools"]:
            assert tool in TOOLS_CATALOG, (clase, tool)


def test_cada_campo_de_traza_lo_escribe_alguna_de_sus_tools():
    """AP-44: el campo se busca en el código que escribe, no en lo que el SDD promete."""
    for clase, e in reg.EJES_DOCUMENTACION.items():
        fuentes = "".join(
            gi.codigo_de(REPO_ROOT / "scripts" / TOOLS_CATALOG[t]["script"]).read_text(encoding="utf-8")
            for t in e["tools"])
        for campo in e["campos"]:
            assert f'"{campo}"' in fuentes, (clase, campo)


def test_ningun_eje_promete_un_campo_que_nadie_escribe():
    campos = {c for e in reg.EJES_DOCUMENTACION.values() for c in e["campos"]}
    assert "relacionado_con" not in campos
    assert "lifecycle_state" not in campos


def test_el_regimen_de_cada_estado_se_deriva_de_las_transiciones():
    assert set(STATUS_TRANSITIONS) == STATUS_VOCAB
    for status, salidas in STATUS_TRANSITIONS.items():
        r = regimen_de_estado(status)
        assert r in reg.REGIMENES_DE_ESTADO, status
        assert (r == "terminal") == (not salidas), status
        assert (r == "abierto") == (status == "draft" or "draft" in salidas), status
    assert regimen_de_estado("draft") == "abierto"
    assert regimen_de_estado("approved") == "cerrado"
    assert regimen_de_estado("archived") == "terminal"


def test_el_estado_endurece_el_modo_salvo_en_lo_anexado_y_lo_regenerado():
    for regimen in reg.REGIMENES_DE_ESTADO:
        assert reg.modo_de_version("registro", regimen) == "anexado"
        assert reg.modo_de_version("indice", regimen) == "regenerado"
    assert reg.modo_de_version("referencia", "abierto") == "historia"
    assert reg.modo_de_version("referencia", "cerrado") == "sustitucion"
    assert reg.modo_de_version("explicacion", "terminal") == "inmutable"


def test_el_sdd_publica_los_ejes_y_las_dos_correlaciones():
    texto = vault_sdd_init.generate_methodology(REPO_ROOT, {})
    assert "{EJES_DOCUMENTACION}" not in texto
    for clase, e in reg.EJES_DOCUMENTACION.items():
        assert f"| {clase} | {e['traza']} |" in texto
    for modo in reg.MODOS_DE_VERSION:
        assert f"| {modo} | {reg.MODOS_DE_VERSION[modo]['que']} |" in texto
    for status in STATUS_TRANSITIONS:
        assert f"| `{status}` | {regimen_de_estado(status)} |" in texto
    for version in HISTORIA:
        assert f"| {version} | " in texto


def test_el_sdd_ya_no_promete_relacionado_con_como_campo_vigente():
    texto = vault_sdd_init.generate_methodology(REPO_ROOT, {})
    assert "`relacionado_con:` en frontmatter cuando aplica" not in texto
