"""`vault_validate` medía con su criterio, no con el del consumidor (AP-44).

Ejecutada contra `vault-sandbox/` reprobaba 33 de 124 notas. Ninguna de las 33
estaba mal: eran tres defectos de la propia comprobación.

1. Barría el vault entero con `rglob` desde la raíz, así que metía en el informe
   los trece markdown de `docs/sdd/` —que conviven con el vault pero no son
   notas suyas— y los reprobaba por no llevar frontmatter.
2. Un BOM delante del `---` hacía falso el `startswith("---")`, y once notas con
   frontmatter completo y legible salían como «No frontmatter block». El kernel
   tiene `strip_bom` desde hace versiones.
3. Dos artefactos derivados —`change-log.md` y `tool-contracts.md`, escritos por
   tools de este mismo estándar— se exigían con las reglas de una nota.

Los tres son la misma forma: la comprobación decidía por su cuenta algo que ya
estaba declarado en un registro.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import vault_validate  # noqa: E402
from vault_fundamentals import CIA_TRIAD, cia_valores  # noqa: E402
from vault_registry import (  # noqa: E402
    DERIVED_ARTIFACTS,
    ORDERED_SECTIONS,
    es_artefacto_derivado,
)

FRONTMATTER = """---
id: n1
title: Nota
createdAt: 2026-08-06T00:00:00Z
updatedAt: 2026-08-06T00:00:00Z
tags: ["x"]
agent: claude
cia_integrity: high
cia_availability: high
cia_sensitivity: internal
---

Cuerpo de la nota.
"""


@pytest.fixture
def vault(tmp_path, monkeypatch):
    for seccion in ORDERED_SECTIONS:
        (tmp_path / seccion).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vault_validate, "_raiz", lambda: tmp_path)
    return tmp_path


def test_un_bom_delante_del_frontmatter_no_lo_esconde(vault):
    """Once notas del vault de pruebas se perdían por tres bytes invisibles."""
    nota = vault / "07_Knowledge" / "con-bom.md"
    nota.write_text("﻿" + FRONTMATTER, encoding="utf-8")

    resultado = vault_validate.validate_frontmatter(nota)

    assert resultado["valid"], resultado.get("error")
    assert resultado["data"]["id"] == "n1"


def test_no_se_reprueba_markdown_que_solo_convive_con_el_vault(vault):
    """`docs/` no es una sección: lo que hay dentro no son notas del vault."""
    ajeno = vault / "docs" / "sdd"
    ajeno.mkdir(parents=True)
    (ajeno / "00-principles.md").write_text("# Principios\n", encoding="utf-8")
    (vault / "07_Knowledge" / "real.md").write_text(FRONTMATTER, encoding="utf-8")

    informe = vault_validate.check_frontmatter(None, None)

    rutas = [x["path"] for x in informe["invalid"]]
    assert rutas == [], rutas
    assert len(informe["valid"]) == 1


@pytest.mark.parametrize("relativa", sorted(DERIVED_ARTIFACTS))
def test_un_artefacto_derivado_no_se_juzga_como_nota(vault, relativa):
    """Lo escribe una tool sin frontmatter; exigírselo es reprobarse a sí mismo."""
    destino = vault / relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("# Generado\n\nSin frontmatter, a propósito.\n", encoding="utf-8")

    assert vault_validate.validate_frontmatter(destino)["valid"]


def test_el_indice_entra_por_nombre_y_no_por_lista():
    """Hay veintidós `index.md` y ninguno está declarado: el criterio es el stem."""
    assert es_artefacto_derivado("07_Knowledge/index.md")
    assert es_artefacto_derivado("07_Knowledge\\subcarpeta\\index.md")
    assert not es_artefacto_derivado("07_Knowledge/indexado.md")


def test_las_secciones_exigidas_salen_del_registro():
    """Se congelaron en diez en v33: un vault a medias pasaba como completo."""
    assert vault_validate.REQUIRED_FOLDERS == list(ORDERED_SECTIONS)


def test_el_vocabulario_cia_no_se_escribe_dos_veces():
    """Una copia que se quede atrás reprueba notas válidas y nadie lo nota."""
    for campo, esperado in [
        ("cia_integrity", vault_validate.CIA_INTEGRITY_VALUES),
        ("cia_availability", vault_validate.CIA_AVAILABILITY_VALUES),
        ("cia_sensitivity", vault_validate.CIA_SENSITIVITY_VALUES),
    ]:
        assert cia_valores(campo) == esperado, campo
        assert esperado, f"{campo} no está en CIA_TRIAD"


def test_la_asimetria_de_disponibilidad_es_del_registro():
    """DISPONIBILIDAD no admite `critical` e INTEGRIDAD sí. Es deliberado y hay
    que poder verlo: sin este test parece un olvido y alguien lo «arregla»."""
    campos = {c["frontmatter_field"]: set(c["values"]) for c in CIA_TRIAD}
    assert "critical" in campos["cia_integrity"]
    assert "critical" not in campos["cia_availability"]
