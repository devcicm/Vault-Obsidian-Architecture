"""AP-46: el título y el proyecto de una nota son texto, aunque parezcan fecha.

`Frontmatter.set` deja los instantes sin citar para que `createdAt` llegue al
lector como `datetime`. Los `*_save` migrados en v40.1 escribían así también
`title` y `project`: `vault_runbook_save --title 2026-10-02` devolvía al lector
un `datetime.date` como título (medido 2026-10-02). La identidad de una nota no
puede cambiar de tipo según qué texto lleve.
"""

import ast
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402

IDENTIDAD = {"title", "project"}


def _sets_sin_texto(ruta: Path) -> list:
    """`.set("title"|"project", <variable>)` sin `texto=True`.

    Un f-string con prefijo (`f"Riesgo: {title}"`) no puede leerse como fecha
    y queda fuera; una variable a secas sí puede.
    """
    malos = []
    for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "set" and len(n.args) >= 2
                and isinstance(n.args[0], ast.Constant) and n.args[0].value in IDENTIDAD
                and isinstance(n.args[1], ast.Name)
                and not any(k.arg == "texto" for k in n.keywords)):
            malos.append(f"{ruta.name}:{n.lineno}")
    return malos


def test_ap46_ningun_escritor_deja_la_identidad_a_merced_del_parser():
    rutas = sorted((ROOT / "scripts").glob("vault_*.py"))
    malos = [m for r in rutas for m in _sets_sin_texto(r)]
    assert malos == []


def test_ap46_runbook_con_titulo_de_fecha_conserva_el_texto(tmp_path):
    import vault_io
    import vault_runbook_save

    raiz = tmp_path / "v"
    for s in ("00_System", "08_Runbooks"):
        (raiz / s).mkdir(parents=True)
    vault_io.set_vault_root(raiz)
    r = vault_runbook_save.vault_runbook_save(
        "2026-10-02", "2026-10-02", "t", "maintenance", [{"action": "x"}])
    bloque, _ = separar_frontmatter((raiz / r["path"]).read_text(encoding="utf-8"))
    fm = yaml.safe_load(bloque)
    assert fm["title"] == "2026-10-02" and fm["project"] == "2026-10-02"
