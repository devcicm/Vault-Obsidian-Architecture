"""El orden del frontmatter depende del campo, no de por dónde llegó (deuda #16).

Medido el 2026-10-07: con `--meta '{"type":"concept"}'`, `type` salía detrás de
`agent` y de los tres `cia_*`, mientras que el `type` deducido de la carpeta
salía tras `tags`. El mismo campo, dos posiciones.

Decisión del usuario (2026-10-08): el orden mínimo. La salida de una nota sin
campos del contrato en `meta` no cambia un byte; los campos de
`vault_contrato_nota.CAMPOS` que lleguen por `meta` ocupan el hueco que les da
el contrato, y lo ajeno al contrato sigue al final.
"""

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_contrato_nota  # noqa: E402
import vault_write  # noqa: E402
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402


def _claves(fm: str) -> list:
    bloque, _ = separar_frontmatter(fm + "\ncuerpo\n")
    return list(yaml.safe_load(bloque))


def test_type_por_meta_sale_donde_el_type_deducido():
    deducido = _claves(vault_write.generate_frontmatter(
        "T", tags=["a"], folder="05_Patterns"))
    por_meta = _claves(vault_write.generate_frontmatter(
        "T", tags=["a"], meta={"type": "concept"}))
    assert "type" in deducido
    assert por_meta == deducido


def test_los_campos_del_contrato_siguen_a_campos_y_los_ajenos_van_al_final():
    meta = {"owner": "infra", "revisado_en": "2026-10-08",
            "responsable": "ana", "vigente_desde": "v2", "type": "concept"}
    claves = _claves(vault_write.generate_frontmatter("T", tags=["a"], meta=meta))
    del_contrato = [c for c in claves if c in vault_contrato_nota.CAMPOS]
    opcionales = [c for c in del_contrato if c in ("vigente_desde", "responsable", "revisado_en")]
    assert opcionales == [c for c in vault_contrato_nota.CAMPOS if c in opcionales]
    assert claves[-1] == "owner"
    assert claves.index("type") == claves.index("tags") + 1


def test_sin_campos_del_contrato_en_meta_la_salida_no_cambia():
    claves = _claves(vault_write.generate_frontmatter(
        "T", tags=["a"], meta={"owner": "infra"}, folder="05_Patterns"))
    assert claves == ["title", "id", "createdAt", "updatedAt", "tags", "type", "status",
                      "cia_integrity", "cia_availability", "cia_sensitivity", "agent", "owner"]
