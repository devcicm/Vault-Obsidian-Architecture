"""Nadie más parte el frontmatter con `split("---")` (AP-57, 2026-10-01).

El kernel ya cierra el bloque en una línea `---` (`separar_frontmatter`), pero
catorce módulos seguían partiendo por su cuenta y cortaban dentro de un título
entre comillas. Aquí se comprueba que los sitios migrados leen la nota igual
que el dueño, y que una copia nueva hace fallar `vault_criterios`.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_criterios  # noqa: E402
import vault_frontmatter_heal  # noqa: E402
import vault_merge  # noqa: E402
import vault_quality_check  # noqa: E402
import vault_tags  # noqa: E402
from vault.indices.reconstruccion import _previo  # noqa: E402

NOTA = (
    '---\n'
    'title: "Antes --- después"\n'
    'updatedAt: 2026-10-01\n'
    '---\n'
    '\n'
    'cuerpo real de la nota\n'
)


def test_ap57_una_particion_por_split_se_detecta(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "vault_copia.py").write_text(
        'def f(t):\n    return t.split("---", 2)[1]\n', encoding="utf-8")
    dueño = tmp_path / "vault" / "kernel"
    dueño.mkdir(parents=True)
    (dueño / "frontmatter_parsing.py").write_text(
        'X = "a---b".split("---")\n', encoding="utf-8")
    archivado = tmp_path / "scripts" / "_archived"
    archivado.mkdir()
    (archivado / "viejo.py").write_text('"x".split("---", 2)\n', encoding="utf-8")
    h = vault_criterios.medir_particiones(tmp_path)
    assert [x["modulo"] for x in h] == ["scripts/vault_copia.py"]
    assert h[0]["dueño"].endswith(":separar_frontmatter")


def test_ap57_hoy_nadie_parte_por_su_cuenta():
    assert vault_criterios.medir_particiones() == []


def test_ap57_los_sitios_migrados_no_cortan_dentro_del_titulo(tmp_path):
    assert vault_tags._parse_frontmatter_title(NOTA) == "Antes --- después"
    nota = tmp_path / "n.md"
    nota.write_text(NOTA, encoding="utf-8")
    fm, cuerpo = vault_quality_check._read_frontmatter_raw(nota)
    assert fm["title"] == "Antes --- después"
    assert cuerpo.strip() == "cuerpo real de la nota"
    bloque, resto = vault_frontmatter_heal._partir(NOTA)
    assert "updatedAt" in bloque and resto.strip() == "cuerpo real de la nota"
    assert _previo(NOTA) == "cuerpo real de la nota"


def test_ap57_merge_inyecta_sin_partir_el_titulo():
    salida = vault_merge._tag_frontmatter(NOTA, "origen")
    import yaml
    bloque = salida.split("\n---\n", 1)[0][4:]
    datos = yaml.safe_load(bloque)
    assert datos["title"] == "Antes --- después"
    assert datos["mergedFrom"] == "origen"
    assert salida.endswith("---\n\ncuerpo real de la nota\n")
