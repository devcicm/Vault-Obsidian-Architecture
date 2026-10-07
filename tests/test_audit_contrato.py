"""El audit cuenta los campos ausentes con el contrato, no con una lista propia.

`_detect_missing_metadata` decide con criterios suyos qué es derivado, qué es de
sistema y qué falta. Una nota con `type:` y sin `id:` la rechaza `vault_validate`
y el audit no la contaba en ningún sitio, así que la fase 4 de `vault_sanacion`,
que lee el audit, la daba por sanada. `missingContract` es la lectura del dueño
(`vault_contrato_nota`), con el mismo parser que `vault_validate` (AP-44).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_audit  # noqa: E402
import vault_io  # noqa: E402
import vault_validate  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    for seccion in ("00_System", "07_Knowledge"):
        (tmp_path / seccion).mkdir()
    previa = vault_io.get_vault_root()
    vault_io.set_vault_root(tmp_path)
    yield tmp_path
    vault_io.set_vault_root(previa)


def _contrato(vault):
    notas = sorted(vault.rglob("*.md"))
    return {e["path"]: e for e in vault_audit._detect_missing_metadata(notas)["missing_contract"]}


def test_una_nota_con_type_y_sin_id_falta_al_contrato(vault):
    nota = vault / "07_Knowledge" / "jwt.md"
    nota.write_bytes(b"---\ntype: knowledge\n---\n\n# JWT\n")
    assert vault_validate.validate_frontmatter(nota)["valid"] is False

    entrada = _contrato(vault)["07_Knowledge/jwt.md"]
    assert "id" in entrada["missing"]


def test_una_nota_de_sistema_no_debe_lo_que_su_clase_no_exige(vault):
    (vault / "00_System" / "primer.md").write_bytes(
        b"---\ntitle: P\nid: a\ncreatedAt: x\nupdatedAt: y\n---\n")
    assert "00_System/primer.md" not in _contrato(vault)


def test_un_derivado_no_tiene_contrato(vault):
    (vault / "07_Knowledge" / "index.md").write_bytes(b"# Indice\n")
    assert "07_Knowledge/index.md" not in _contrato(vault)


def test_sin_bloque_falta_todo_y_un_bloque_ilegible_se_dice(vault):
    (vault / "07_Knowledge" / "suelta.md").write_bytes(b"# Suelta\n")
    (vault / "07_Knowledge" / "rota.md").write_bytes(b"---\ntitle: a: b\n---\n")
    por_ruta = _contrato(vault)
    assert "id" in por_ruta["07_Knowledge/suelta.md"]["missing"]
    assert por_ruta["07_Knowledge/rota.md"]["illegible"] is True


def test_una_nota_completa_no_aparece(vault):
    nota = vault / "07_Knowledge" / "ok.md"
    nota.write_bytes(b"---\ntitle: Ok\nid: a1\ncreatedAt: 2026-01-01T00:00:00.000Z\n"
                     b"updatedAt: 2026-01-01T00:00:00.000Z\ntype: knowledge\nstatus: draft\n"
                     b"tags: [x]\nagent: system\ncia_integrity: medium\n"
                     b"cia_availability: medium\ncia_sensitivity: internal\n---\n\n# Ok\n")
    assert vault_validate.validate_frontmatter(nota)["valid"] is True
    assert "07_Knowledge/ok.md" not in _contrato(vault)


# ── Las listas viejas deciden con el mismo criterio que el contrato (AP-57) ───


def _listas(vault):
    return vault_audit._detect_missing_metadata(sorted(vault.rglob("*.md")))


def _rutas(lista):
    return [e["path"] for e in lista]


def test_un_bom_no_esconde_el_frontmatter_a_las_listas_viejas(vault):
    """`adr-001-mcp-transport.md` del sandbox —BOM y CRLF— salía «sin frontmatter»
    en `missing_frontmatter` mientras `missing_contract`, con el parser del
    kernel, le leía todos los campos menos `id`."""
    (vault / "07_Knowledge" / "bom.md").write_bytes(
        "﻿---\r\ntitle: B\r\ntags: [a]\r\n---\r\n\r\n# B\r\n".encode("utf-8"))
    listas = _listas(vault)
    assert "07_Knowledge/bom.md" not in _rutas(listas["missing_frontmatter"])
    assert "07_Knowledge/bom.md" not in _rutas(listas["missing_tags"])


def test_un_derivado_declarado_no_entra_en_las_listas_viejas(vault):
    """`00_System/tool-contracts.md` lo escribe `vault_compact_contracts` sin
    frontmatter; el audit lo contaba como nota sin metadatos."""
    (vault / "00_System" / "tool-contracts.md").write_bytes(b"# Tool Contracts\n")
    listas = _listas(vault)
    assert all("00_System/tool-contracts.md" not in _rutas(v) for v in listas.values())


def test_agent_no_se_exige_a_una_nota_de_sistema(vault):
    """El contrato exige `agent` solo a las notas de contenido (v37)."""
    (vault / "00_System" / "reglas.md").write_bytes(
        b"---\ntitle: R\nupdatedAt: 2026-01-01T00:00:00Z\n---\n\n# R\n")
    assert "00_System/reglas.md" not in _rutas(_listas(vault)["missing_agent"])
