"""Cifras escritas a mano que `vault_doc_counts` no vigila (AP-47).

Auditoría del 2026-10-15. Dos cifras se quedaron atrás sin que ninguna puerta
lo viera, porque sus patrones son deliberadamente estrechos:

- El `fix` de la puerta `produccion` decía «las otras veinte puertas» cuando
  ya eran veinticuatro. Ese texto se copia, derivado, al bloque de AGENTS.md.
- `README.md` decía «— 75 scripts adicionales» en el árbol: la cifra de v34.1,
  con 162 scripts en `scripts/`.

Una cifra que nadie vigila envejece; la salida no es vigilarla con un patrón
laxo —`vault_doc_counts` explica por qué eso acaba desactivado— sino no
escribirla.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

#: Un número en cifra o en palabra delante de «puertas».
_PUERTAS_CONTADAS = re.compile(
    r"\b(?:\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|"
    r"trece|catorce|quince|dieciséis|diecisiete|dieciocho|diecinueve|veinte|"
    r"veinti\w+|treinta)\s+puertas\b", re.IGNORECASE)


def test_ninguna_puerta_cuenta_a_las_demas_a_mano():
    import vault_gate

    for puerta in vault_gate.PUERTAS:
        for campo in ("mide", "fix"):
            texto = puerta.get(campo) or ""
            assert not _PUERTAS_CONTADAS.search(texto), (puerta["id"], campo, texto)


def test_el_arbol_del_readme_no_cuenta_los_scripts_que_no_lista():
    texto = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"\d+\s+scripts adicionales", texto)
