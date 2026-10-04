"""El índice de una sección dice de qué va cada nota, no solo cómo se llama.

Medido el 2026-10-04 en la QA de producto: la tabla listaba nota, título,
tipo y fecha. Para saber de qué iba cada nota había que abrirlas todas, que
es lo que un índice existe para evitar. La columna «Resumen» sale de lo que
la nota declara (`summary`, `description`) o de su primera afirmación.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault.indices.seccion import (  # noqa: E402
    LIMITE_DE_RESUMEN,
    RE_ALIAS_EN_TABLA,
    RenderizadorDeIndice,
    resumen_de_nota,
)

FENCE = "`" * 3


def test_lo_declarado_manda_sobre_el_cuerpo():
    assert resumen_de_nota({"summary": "Declarado."}, "Cuerpo.") == "Declarado."
    assert resumen_de_nota({"description": "Desc."}, "Cuerpo.") == "Desc."


def test_sin_declaracion_sale_la_primera_afirmacion():
    """Encabezados, marcadores de pendiente y bloques de código no son
    afirmaciones; el código en línea de una frase sí se conserva."""
    cuerpo = (f"# Título\n\n_Por definir_\n\n{FENCE}py\nprint(1)\n{FENCE}\n\n"
              "- Usa `vault_write` para crear notas.\n")
    assert resumen_de_nota({}, cuerpo) == "Usa `vault_write` para crear notas."


def test_el_resumen_cabe_en_una_celda():
    """Sin `|` sin escapar, sin enlaces nuevos, en una línea y acotado."""
    r = resumen_de_nota({}, "Ver [[nota-a|la nota A]] y [[nota-b]] | otra cosa\n")
    assert r == "Ver la nota A y nota-b \\| otra cosa"
    assert "[[" not in resumen_de_nota({}, "Texto con [[ suelto\n")
    largo = resumen_de_nota({}, "x" * 500)
    assert len(largo) == LIMITE_DE_RESUMEN and largo.endswith("…")
    assert resumen_de_nota({}, "## Solo encabezado\n") == ""


def test_la_tabla_lleva_la_columna_resumen():
    r = RenderizadorDeIndice(lambda k: "d", lambda k: "", lambda s: s)
    texto = r.render("07_Knowledge", [
        {"title": "JWT", "path": "jwt.md", "type": "concept",
         "updatedAt": "2026-10-04", "summary": "Token firmado."}], "AHORA")
    assert "| Nota | Título | Resumen | Tipo | Actualizado |" in texto
    assert "| [[jwt]] | JWT | Token firmado. | concept | 2026-10-04 |" in texto
    assert RE_ALIAS_EN_TABLA.search(texto) is None


def test_el_indice_generado_resume_cada_nota(tmp_path):
    """Criterio del consumidor: el `index.md` escrito, no el diccionario."""
    env = dict(os.environ, VAULT_ROOT=str(tmp_path), VAULT_STRICT_ROOT="1",
               VAULT_AGENT="probe", PYTHONIOENCODING="utf-8")
    (tmp_path / "07_Knowledge").mkdir()
    (tmp_path / "07_Knowledge" / "jwt.md").write_text(
        "---\ntitle: JWT\ntype: concept\n---\n\n# JWT\n\n"
        "Token firmado que viaja en cada petición.\n", encoding="utf-8")
    subprocess.run([sys.executable, str(SCRIPTS / "vault_section_index.py"),
                    "--folder", "07_Knowledge"],
                   capture_output=True, env=env, timeout=300, check=True)
    indice = (tmp_path / "07_Knowledge" / "index.md").read_text(encoding="utf-8")
    assert "| [[jwt]] | JWT | Token firmado que viaja en cada petición. | concept |" in indice
