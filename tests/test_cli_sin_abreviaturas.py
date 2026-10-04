"""Ningún parser acepta un flag abreviado (AP-44: el criterio es el del consumidor).

Medido el 2026-10-04: argparse resuelve prefijos por defecto, así que
`vault_write --tit X --cont Y --tag a` escribía la nota como si fueran
`--title`, `--content` y `--tags`, y `vault run vault_list --lim 1` filtraba.
Un flag que no está en la programación de la tool pasaba sin error, y bastaba
con que una tool ganara un flag nuevo con el mismo prefijo para que la misma
receta cambiara de significado o empezara a fallar por ambigüedad.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZONAS = ("scripts", "vault", "cli", "vault_toolkit", "empaquetado")


def _parsers_sin_allow_abbrev():
    faltan = []
    for zona in ZONAS:
        for f in (ROOT / zona).rglob("*.py"):
            if "_archived" in f.parts or "__pycache__" in f.parts:
                continue
            arbol = ast.parse(f.read_text(encoding="utf-8"))
            for n in ast.walk(arbol):
                if not isinstance(n, ast.Call):
                    continue
                nombre = getattr(n.func, "attr", getattr(n.func, "id", ""))
                if nombre not in ("ArgumentParser", "add_parser"):
                    continue
                kw = {k.arg: k.value for k in n.keywords}
                if None in kw:  # **kwargs: lo decide quien los construye
                    continue
                valor = kw.get("allow_abbrev")
                if not (isinstance(valor, ast.Constant) and valor.value is False):
                    faltan.append(f"{f.relative_to(ROOT).as_posix()}:{n.lineno}")
    return faltan


def test_todo_parser_declara_allow_abbrev_false():
    faltan = _parsers_sin_allow_abbrev()
    assert faltan == [], f"parsers que aceptan abreviaturas: {faltan}"


def test_un_flag_abreviado_se_rechaza_sin_escribir(tmp_path):
    (tmp_path / "01_Projects").mkdir()
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_write.py"),
         "--folder", "01_Projects", "--tit", "Abreviada", "--content", "x"],
        capture_output=True, text=True, cwd=str(ROOT),
        env={**os.environ, "VAULT_ROOT": str(tmp_path)},
        timeout=120,
    )
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "unrecognized arguments: --tit" in r.stderr
    assert list((tmp_path / "01_Projects").glob("*.md")) == []
