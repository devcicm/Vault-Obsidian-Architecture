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
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
        env={**os.environ, "VAULT_ROOT": str(tmp_path)},
        timeout=120,
    )
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "unrecognized arguments: --tit" in r.stderr
    assert list((tmp_path / "01_Projects").glob("*.md")) == []


# Medido el 2026-10-04, segunda mitad del mismo síntoma: rechazado el flag, la
# tool solo escribía el texto de uso en stderr y dejaba stdout vacío. Quien
# consume el contrato JSON (`vault run`, el servidor MCP) no tenía envelope.

def _tool(script, *argv, vault):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *argv],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
        env={**os.environ, "VAULT_ROOT": str(vault)}, timeout=120,
    )


def test_un_flag_rechazado_responde_con_envelope_invalid_args(tmp_path):
    import json

    (tmp_path / "01_Projects").mkdir()
    r = _tool("vault_write.py", "--folder", "01_Projects", "--tit", "X",
              "--content", "valor-que-no-debe-viajar", vault=tmp_path)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "usage:" in r.stderr and "unrecognized arguments: --tit" in r.stderr
    env = json.loads(r.stdout)
    assert env["ok"] is False and env["error_code"] == "INVALID_ARGS", env
    assert env["tool"] == "vault_write"
    # Los valores no viajan en `args`: pueden ser el contenido de una nota.
    assert env["args"] == {"flags": ["--folder", "--tit", "--content"]}
    assert "valor-que-no-debe-viajar" not in r.stdout


def test_un_valor_de_tipo_erroneo_responde_con_envelope(tmp_path):
    import json

    r = _tool("vault_list.py", "--limit", "diez", vault=tmp_path)
    assert r.returncode == 2
    env = json.loads(r.stdout)
    assert env["error_code"] == "INVALID_ARGS" and "--limit" in env["message"], env


def test_wrap_main_restaura_el_error_de_argparse():
    import argparse

    sys.path.insert(0, str(ROOT / "scripts"))
    import vault_errors

    original = argparse.ArgumentParser.error

    def main():
        p = argparse.ArgumentParser(allow_abbrev=False)
        p.add_argument("--uno")
        p.parse_args(["--dos", "x"])

    assert vault_errors.wrap_main(main, "probe") == 2
    assert argparse.ArgumentParser.error is original


def test_vault_secret_scan_no_ignora_argumentos_de_mas(tmp_path):
    nota = tmp_path / "n.md"
    nota.write_text("nada\n", encoding="utf-8")
    r = _tool("vault_secret_scan.py", str(nota), "--json", vault=tmp_path)
    assert r.returncode == 2 and "unrecognized arguments: --json" in r.stderr
