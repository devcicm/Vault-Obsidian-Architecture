"""A-16 — el vocabulario ESTADOS de los controles tenía tres copias; hoy tiene un dueño.

La nota de causa raíz «A canonical vocabulary has three owners» (2026-10-30)
declaraba tres declaraciones de `ESTADOS`. Al medirlo en `1db90da` el cuadro
era otro: dos eran **código muerto** (una constante que nadie leía) y la
tercera era un vocabulario **distinto** (`("cubierta", "descubierta")` y
`("PASS", "FAIL", "BLOCKED")` no son estados de control). La copia viva era la
de `CONTROLES_OBLIGATORIOS`, y el colector de Quality Gates tenía su propio
`ESTADOS` sin comparar con nadie.

Hoy: un dueño (`vault.kernel.controles`), los consumidores lo importan, y el
guard que lo vigila es `tests/test_vocabulario_de_controles.py`.
"""

import ast
from pathlib import Path

from vault.gobernanza import controles as gob
from vault.kernel import controles as nuc

ROOT = Path(__file__).resolve().parent.parent
COLECTOR = ROOT / "audits" / "fase2" / "colector_qg.py"


def test_gobernanza_reexporta_al_dueno_del_nucleo():
    assert gob.ESTADOS is nuc.ESTADOS
    assert gob.CONTROLES_OBLIGATORIOS is nuc.CONTROLES_OBLIGATORIOS


def test_el_colector_qg_importa_al_dueno_y_no_lo_copia():
    """Antes conservaba su copia «pero igual»: tres declaraciones que
    coincidían por casualidad. Ahora la pide al dueño."""
    fuente = COLECTOR.read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    importa = any(
        isinstance(n, ast.ImportFrom)
        and n.module == "vault.kernel.controles"
        and any(a.name == "ESTADOS" for a in n.names)
        for n in ast.walk(arbol))
    assert importa, "el colector debe leer el vocabulario de su dueño"
    # Y no lo reescribe: ninguna asignación de los cuatro estados.
    literales = [
        n.lineno for n in ast.walk(arbol)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "ESTADOS" for t in n.targets)
    ]
    assert not literales, f"el colector vuelve a declarar ESTADOS en {literales}"


def test_no_hay_un_tercer_literal_en_vault():
    literal = '("ejecutado", "degradado", "fallido", "no_ejecutado")'
    donde = [str(p.relative_to(ROOT)) for p in (ROOT / "vault").rglob("*.py")
             if literal in p.read_text(encoding="utf-8")]
    assert donde == [str(Path("vault/kernel/controles.py"))], donde
