"""A-16 — el vocabulario ESTADOS de los controles vivia copiado en tres sitios."""
import re
from pathlib import Path

from vault.gobernanza import controles as gob
from vault.kernel import controles as nuc

ROOT = Path(__file__).resolve().parent.parent


def test_gobernanza_reexporta_al_duenio_del_nucleo():
    assert gob.ESTADOS is nuc.ESTADOS


def test_el_colector_qg_no_diverge_del_duenio():
    """El colector es un script de audits/ sin acceso al paquete: conserva su copia, pero igual."""
    fuente = (ROOT / "audits" / "fase2" / "colector_qg.py").read_text(encoding="utf-8")
    m = re.search(r"^ESTADOS = \((.*?)\)", fuente, re.M)
    assert tuple(x.strip().strip('"') for x in m.group(1).split(",")) == nuc.ESTADOS


def test_no_hay_un_tercer_literal_en_vault():
    literal = '("ejecutado", "degradado", "fallido", "no_ejecutado")'
    donde = [str(p.relative_to(ROOT)) for p in (ROOT / "vault").rglob("*.py")
             if literal in p.read_text(encoding="utf-8")]
    assert donde == [str(Path("vault/kernel/controles.py"))], donde
