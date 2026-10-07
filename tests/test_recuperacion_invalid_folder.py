"""`INVALID_FOLDER` manda al agente a la tool que enseña las secciones del vault.

Medido el 2026-10-07 con una sesión MCP del perfil `agente`: `vault_write
--folder scripts` respondía `recovery.tool: vault_audit` con un `hint` que decía
`vault_section --list`. La pista de cada sitio ya se había corregido al llegar
las secciones propias (v41.2); la entrada del catálogo no, y seguía mandando a
«una carpeta de la estructura estándar». Un agente que sigue `recovery.tool`
—que es para lo que existe— ejecutaba un audit que no le dice dónde escribir.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vault.kernel.errores import ERROR_CATALOG  # noqa: E402


def test_la_recuperacion_de_invalid_folder_es_listar_las_secciones():
    recovery = ERROR_CATALOG["INVALID_FOLDER"]["recovery"]
    assert recovery["tool"] == "vault_section"
    assert recovery["args"] == ["--list"]


def test_la_pista_no_promete_solo_la_estructura_estandar():
    """Desde v41.2 un vault declara sus propias secciones (CN-02)."""
    entrada = ERROR_CATALOG["INVALID_FOLDER"]
    assert "vault_section --list" in entrada["recovery"]["hint"]
    assert "propia" in entrada["recovery"]["hint"]
