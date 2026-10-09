"""CN-01 y CN-04 se miden también en las notas ya escritas (deuda #13).

Hasta v41.2 solo las cumplía el write path —`slugify` y `con_titulo`—, y una
nota que llegaba por otro camino no la medía nadie. Regla 7, 2026-10-08, solo
lectura sobre copias: /ans (vault-ans) 530 notas, 110 nombres fuera de CN-01 y
253 sin H1; /vcloud 109 notas, 19 y 0.

La medida es **informativa**: sale en `issues` y en `stats`, sin fila en
`PENALIZACIONES`, así que no mueve `healthScore` ni `healthIndex`. Si penaliza
lo decide el usuario. Los primers de `vault_init` quedan fuera: su nombre lo
fija el propio estándar (`00-01_projects-primer`) y renombrarlos rompería los
enlaces de los consumidores.

El criterio es el del write path, no uno nuevo: CN-01 es `slugify_strict` del
nombre y CN-04 es `abre_con_h1`, el mismo que usa `con_titulo` (AP-57).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import vault_audit as va  # noqa: E402
from vault.kernel.contenido import abre_con_h1, con_titulo  # noqa: E402

FM = "---\nstatus: draft\ntype: reference\ntags: [x]\n---\n\n"


def _vault(tmp_path: Path) -> Path:
    import vault_io

    root = tmp_path / "v"
    for sec in ("00_System", "05_Patterns", "99_Index"):
        (root / sec).mkdir(parents=True)
    notas = {
        "05_Patterns/bien-nombrada.md": FM + "# Bien\n\ntexto\n",
        "05_Patterns/Mal_Nombrada.md": FM + "# Mal\n\ntexto\n",
        "05_Patterns/sin-titulo.md": FM + "texto sin encabezado\n",
        "05_Patterns/con-bom.md": "﻿" + FM + "# Con BOM\n",
        "05_Patterns/00-05_patterns-primer.md": "---\ntype: primer\n---\n\ntexto\n",
    }
    for rel, txt in notas.items():
        (root / rel).write_text(txt, encoding="utf-8")
    vault_io.set_vault_root(root)
    return root


def test_cn04_el_criterio_es_el_de_con_titulo():
    assert abre_con_h1("\n\n# T\n")
    assert abre_con_h1("﻿# T\n")
    assert not abre_con_h1("#etiqueta\n# T\n")
    assert not abre_con_h1("texto\n# T\n")
    assert con_titulo("T", "# Otro\n") == "# Otro\n"


def test_cn01_cn04_se_publican_sin_peso(tmp_path):
    _vault(tmp_path)
    r = va.vault_audit()
    cn01 = {e["path"] for e in r["issues"]["cn01NotKebab"]}
    cn04 = {e["path"] for e in r["issues"]["cn04NoTitle"]}
    assert cn01 == {"05_Patterns/Mal_Nombrada.md"}
    assert cn04 == {"05_Patterns/sin-titulo.md"}
    assert all(e["norm_code"] == "CN-01" for e in r["issues"]["cn01NotKebab"])
    assert all(e["norm_code"] == "CN-04" for e in r["issues"]["cn04NoTitle"])
    assert r["stats"]["cn01NotKebab"] == 1 and r["stats"]["cn04NoTitle"] == 1
    assert "cn0" not in repr(r["penalties"]).lower()


def test_cn01_cn04_no_mueven_la_salud(tmp_path):
    root = _vault(tmp_path)
    antes = va.vault_audit()
    (root / "05_Patterns" / "Mal_Nombrada.md").rename(root / "05_Patterns" / "mal-nombrada.md")
    (root / "05_Patterns" / "sin-titulo.md").write_text(FM + "# T\n\ntexto sin encabezado\n",
                                                        encoding="utf-8")
    despues = va.vault_audit()
    assert despues["issues"]["cn01NotKebab"] == [] and despues["issues"]["cn04NoTitle"] == []
    assert (antes["healthScore"], antes["healthIndex"]) == (despues["healthScore"], despues["healthIndex"])
