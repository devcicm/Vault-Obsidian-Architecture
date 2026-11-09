"""Los objetivos del propietario son una nota, y su contrato está declarado.

El contrato vive en el manifiesto del estándar (fuente normativa) y en la
nota `17_Preferences/objetivos.md` de cada vault. Aquí se congela lo que
no puede cambiar por descuido:

- el manifiesto **declara** dónde viven los objetivos, quién los escribe y
  con qué vocabulario;
- el `status` que usa el contrato está en el vocabulario del registro
  (`vault_norms.STATUS_VOCAB`): un contrato con un status inventado es un
  contrato que nadie puede cumplir;
- la `strength` es la misma de `vault_preferences` (`must` / `should` /
  `may`): dos vocabularios de fuerza en el mismo vault obligarían a adivinar
  cuál manda.
"""

from __future__ import annotations

from pathlib import Path

from apoyo import ROOT as REPO_ROOT

MANIFIESTO = (REPO_ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")


def test_el_manifiesto_declara_el_contrato():
    assert "#### Los objetivos del propietario, como nota" in MANIFIESTO
    assert "17_Preferences/objetivos.md" in MANIFIESTO
    # Quién escribe y con qué vocabulario, en el propio manifiesto.
    assert "Quién escribe:" in MANIFIESTO
    assert "strength" in MANIFIESTO


def test_el_status_del_contrato_esta_en_el_vocabulario_del_registro():
    from vault_norms import STATUS_VOCAB

    for valor in ("planned", "implemented", "archived"):
        assert valor in STATUS_VOCAB, (
            f"el contrato usa status '{valor}', que no está en el registro")


def test_la_fuerza_es_la_misma_que_la_de_las_preferencias():
    """Dos vocabularios de fuerza en el mismo vault obligarían a adivinar."""
    import vault_preferences

    fuentes = []
    for nombre in ("vault_preferences.py",):
        p = REPO_ROOT / "scripts" / nombre
        if p.is_file():
            fuentes.append(p.read_text(encoding="utf-8"))
    if not fuentes:
        return  # el registro de preferencias no está en el checkout
    texto = "\n".join(fuentes)
    for valor in ("must", "should", "may"):
        assert valor in texto, f"el contrato usa '{valor}' y las preferencias no"
