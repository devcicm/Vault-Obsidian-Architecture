"""El audit no puede auditar sus propias copias de seguridad.

Encontrado sanando BuilderX: `vault_norms --audit` devolvía 216 violaciones, de
las que **194 (el 90%) vivían dentro de `vault-backups/`**. Es una contradicción
entre dos normas del propio estándar: AP-36 obliga a que todo side-effect
(backups, papelera, historial) viva DENTRO del vault, y el barrido de notas
excluía `.history/` y los dotfiles pero no `vault-backups/`.

No es ruido de métrica. Tiene tres costes concretos:

  * Toda medida de salud queda dominada por instantáneas congeladas, así que
    sanar el vault no mueve el número y el agente no sabe si avanza.
  * El audit manda a "corregir" una copia de seguridad — que es exactamente lo
    que destruye su valor: un backup corregido ya no registra qué había.
  * Cada violación se contaba tantas veces como backups hubiera. Con dos
    snapshots, una nota mala aparecía tres veces.

Y el hueco simétrico, en la dirección contraria: la lista de stems con la que
AP-14 detecta enlaces fantasma SÍ incluía los backups, así que un enlace a una
nota borrada "resolvía" porque quedaba una copia en `vault-backups/`. Un falso
negativo permanente en el detector de enlaces rotos.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_norms as vn  # noqa: E402


NOTA_MALA = """---
title: Nota con status inválido
status: en_desarrollo
type: reference
---

# Nota

Cuerpo.
"""


@pytest.mark.parametrize(
    "rel,esperado",
    [
        ("vault-backups/vault-2026-07-31/01_Projects/a.md", True),
        ("vault-backups/x.md", True),
        ("00_System/.trash/a-20260731.md.bak", True),
        ("03_Decisions/.history/adr-1-20260731.md", True),
        ("01_Projects/builderx/status.md", False),
        ("03_Decisions/adr-uno.md", False),
        # No basta con un `in`: una nota legítima puede nombrar el directorio.
        ("07_Knowledge/concepts/como-usar-vault-backups.md", False),
    ],
)
def test_reconoce_que_es_una_instantanea(rel, esperado):
    assert vn._es_instantanea(rel) is esperado


def test_acepta_separador_de_windows():
    assert vn._es_instantanea("vault-backups\\snap\\01_Projects\\a.md") is True


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "v"
    for sec in ("00_System", "01_Projects", "99_Index"):
        (root / sec).mkdir(parents=True)
        (root / sec / "index.md").write_text("# index\n", encoding="utf-8")
    return root


def test_una_violacion_solo_en_backups_no_se_reporta(tmp_path):
    """El caso de BuilderX: 194 hallazgos, todos en copias congeladas."""
    root = _vault(tmp_path)
    snap = root / "vault-backups" / "vault-2026-07-31" / "01_Projects"
    snap.mkdir(parents=True)
    (snap / "status.md").write_text(NOTA_MALA, encoding="utf-8")

    r = vn.vault_norms_audit(root)
    rutas = [v.get("path", "") for v in r.get("violations", [])]
    assert not any("vault-backups" in p for p in rutas), (
        f"el audit está auditando sus propias copias: {rutas}"
    )


def test_la_misma_violacion_en_una_nota_viva_si_se_reporta(tmp_path):
    """Excluir instantáneas no puede volverse una excusa para no ver nada."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "status.md").write_text(NOTA_MALA, encoding="utf-8")

    r = vn.vault_norms_audit(root)
    rutas = [v.get("path", "") for v in r.get("violations", [])]
    assert any("01_Projects/status.md" in p.replace("\\", "/") for p in rutas), (
        f"la nota viva con status inválido debe seguir reportándose: {rutas}"
    )


def test_los_backups_no_multiplican_el_recuento(tmp_path):
    """Con N snapshots, una nota mala se contaba N+1 veces."""
    root = _vault(tmp_path)
    (root / "01_Projects" / "status.md").write_text(NOTA_MALA, encoding="utf-8")
    sin_backups = len(vn.vault_norms_audit(root).get("violations", []))

    for n in ("snap-a", "snap-b", "snap-c"):
        d = root / "vault-backups" / n / "01_Projects"
        d.mkdir(parents=True)
        (d / "status.md").write_text(NOTA_MALA, encoding="utf-8")

    con_backups = len(vn.vault_norms_audit(root).get("violations", []))
    assert con_backups == sin_backups, (
        f"{sin_backups} sin backups vs {con_backups} con 3 backups: hacer una "
        f"copia de seguridad no puede empeorar la salud del vault"
    )


def test_una_copia_en_backups_no_salva_a_un_enlace_fantasma(tmp_path):
    """El hueco simétrico: AP-14 resolvía enlaces contra los backups.

    Se borra la nota destino y queda su copia en `vault-backups/`. El enlace
    está roto para cualquier lector, pero el detector lo daba por bueno.
    """
    root = _vault(tmp_path)
    snap = root / "vault-backups" / "snap" / "01_Projects"
    snap.mkdir(parents=True)
    (snap / "nota-borrada.md").write_text("# borrada\n", encoding="utf-8")

    stems = {
        p.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
        for p in root.rglob("*.md")
        if not vn._es_instantanea(str(p.relative_to(root)))
    }
    assert "notaborrada" not in stems, (
        "el stem de una nota que solo existe en un backup no puede contar como "
        "destino válido de un wikilink"
    )
