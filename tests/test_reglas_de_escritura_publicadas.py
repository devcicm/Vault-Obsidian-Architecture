"""Las reglas de escritura y el contrato de evidencia están publicados.

Propuestas `document-text-style-and-evidence-strategy` y
`progressive-documentation-and-onboarding-strategy`. El manifiesto es la
fuente normativa: si las reglas solo vivieran en una nota de auditoría, no
las leería quien escribe. Aquí se congela que estén, y que digan lo que son:

- reglas **condicionales**, no un esquema obligatorio;
- el contrato de evidencia: fuente junto a la afirmación, fecha o revisión,
  estado (observado / inferido / propuesto) y límites conocidos;
- un índice **navega**, no demuestra;
- un puntaje no certifica que el contenido sea verdadero.
"""

from __future__ import annotations

from apoyo import ROOT as REPO_ROOT  # el conftest ya pone el path

MANIFIESTO = (REPO_ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")


def test_el_manifiesto_declara_las_reglas_de_escritura():
    assert "#### Cómo se escribe una nota" in MANIFIESTO
    for pieza in ("Empieza por la respuesta",
                  "hecho observado",
                  "No se inventa",
                  "Un índice **navega**"):
        assert pieza in MANIFIESTO, pieza


def test_el_contrato_de_evidencia_esta_completo():
    assert "Contrato de evidencia" in MANIFIESTO
    for pieza in ("observado", "inferido", "propuesto", "límites conocidos"):
        assert pieza in MANIFIESTO, pieza


def test_las_reglas_son_condicionales_y_no_un_esquema():
    """Un esquema obligatorio convertiría notas cortas y verdaderas en deuda."""
    plano = " ".join(MANIFIESTO.split())
    assert "condicionales" in plano
    assert "no son un esquema obligatorio" in plano.lower()
