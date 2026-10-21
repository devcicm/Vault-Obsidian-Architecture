"""El núcleo de un vault: las notas por encima del escalón de fan-in (deuda #11).

`vault_kernel` traza el núcleo del **repo** sobre el grafo de imports. El mismo
concepto aplicado a las notas sale del grafo de **enlaces**: cuántas notas de
contenido distintas citan a cada una, resuelto como lo resuelve Obsidian
(`vault_lib.resolver_wikilink`: nombre de fichero, `aliases:`, sufijo de
carpeta; nunca `title:`). El umbral es el escalón —la mayor caída relativa con
hueco—, el mismo cálculo que usa `vault_kernel`, y tiene un solo dueño en el
núcleo: dos definiciones de «alto» serían el defecto que ese criterio cerró.

Es medida **informativa**: sale en `vaultCore` y en `stats`, sin fila en
`PENALIZACIONES`, así que no mueve `healthScore` ni `healthIndex`. Las cifras
contra vaults ajenos (regla 7) están fechadas en un solo sitio: la entrada
`el_vault_no_tiene_kernel_declarado` del plano.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import vault_audit as va  # noqa: E402

FM = "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n"


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "05_Patterns", "03_Decisions", "99_Index"):
        (root / sec).mkdir(parents=True)
    (root / "05_Patterns" / "centro.md").write_text(
        "---\nstatus: draft\ntype: reference\ntags: [x]\naliases: [El Centro]\n---\n\n# C\n",
        encoding="utf-8")
    (root / "05_Patterns" / "lateral.md").write_text(FM + "# L\n", encoding="utf-8")
    # La carpeta tiene que ser una seccion CANONICA: desde O9 una nota fuera
    # de toda seccion es material ajeno (`sin_seccion`) y no cuenta como nota
    # del vault, ni para el fan-in del nucleo.
    for i in range(6):
        # La mitad cita por alias: el criterio es el de Obsidian, no el nombre.
        destino = "[[El Centro]]" if i % 2 else "[[centro#C]]"
        (root / "03_Decisions" / f"d{i}.md").write_text(
            FM + f"# D{i}\n\n{destino} [[lateral]]\n" if i == 0 else FM + f"# D{i}\n\n{destino}\n",
            encoding="utf-8")
    # Un índice que enumera todo no hace núcleo: enumerar no es citar.
    (root / "99_Index" / "index.md").write_text(
        "# Índice\n\n" + "\n".join(f"- [[d{i}]]" for i in range(6)) + "\n- [[lateral]]\n",
        encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def test_el_escalon_tiene_un_solo_dueno_en_el_kernel():
    import vault_kernel
    from vault.kernel.escalon import escalon

    assert vault_kernel.escalon is escalon
    assert escalon([6, 1, 1, 0]) == (6, 6.0)
    assert escalon([2, 1]) == (None, None)


def test_el_nucleo_se_publica_con_umbral_y_notas(tmp_path):
    _vault(tmp_path)
    r = va.vault_audit()
    nucleo = r["vaultCore"]
    assert nucleo["threshold"] == 6 and nucleo["ratio"] == 6.0
    assert nucleo["notes"] == [{"path": "05_Patterns/centro.md", "fanIn": 6}]
    assert r["stats"]["vaultCore"] == 1


def test_sin_escalon_no_hay_nucleo_inventado(tmp_path):
    import vault_io

    root = tmp_path / "v"
    (root / "05_Patterns").mkdir(parents=True)
    (root / "00_System").mkdir()
    (root / "05_Patterns" / "a.md").write_text(FM + "# A\n\n[[b]]\n", encoding="utf-8")
    (root / "05_Patterns" / "b.md").write_text(FM + "# B\n\n[[a]]\n", encoding="utf-8")
    vault_io.set_vault_root(root)
    nucleo = va.vault_audit()["vaultCore"]
    assert nucleo["threshold"] is None and nucleo["notes"] == []


def test_el_nucleo_no_mueve_la_salud(tmp_path, monkeypatch):
    _vault(tmp_path)
    antes = va.vault_audit()
    monkeypatch.setattr(va, "_nucleo_del_vault",
                        lambda *a, **k: {"threshold": None, "ratio": None, "notes": [],
                                         "criterion": ""})
    despues = va.vault_audit()
    assert (antes["healthScore"], antes["healthIndex"]) == (despues["healthScore"], despues["healthIndex"])
    assert "vaultcore" not in repr(antes["penalties"]).lower()
