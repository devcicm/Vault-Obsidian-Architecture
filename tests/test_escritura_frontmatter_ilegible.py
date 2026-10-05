"""Una escritura que el guard de frontmatter bloquea sale con su código.

Medido el 2026-10-05 con la wheel 40.35 contra un vault real: `vault_append`
sobre un ADR con el YAML roto se bloqueaba —bien: reescribirlo habría
publicado el bloque roto otra vez—, pero salía como `UNEXPECTED_ERROR`,
`severity: critical`, con la pista «Revisar el trace log». El consumidor leía
un fallo de la herramienta donde había una nota que corregir, y la pista no le
decía cuál ni cómo. El catálogo ya tenía el código: `FRONTMATTER_PARSE_ERROR`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _append(vault: Path, nota: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_append.py"), "--path", nota,
         "--content", "linea nueva"],
        env=env, capture_output=True, text=True, encoding="utf-8", cwd=str(SCRIPTS))
    salida = p.stdout.strip()
    return json.loads(salida[salida.index("{"):])


def test_un_frontmatter_que_no_parsea_bloquea_con_su_codigo(tmp_path):
    (tmp_path / "00_System").mkdir()
    roto = "---\nid: adr\ntitle: ADR-004 — Algoritmo: eliminar\n---\n\ncuerpo\n"
    (tmp_path / "adr.md").write_text(roto, encoding="utf-8")
    r = _append(tmp_path, "adr.md")
    assert r["ok"] is False
    assert r["error_code"] == "FRONTMATTER_PARSE_ERROR", r
    assert "trace log" not in r["recovery"]["hint"], r
    assert (tmp_path / "adr.md").read_text(encoding="utf-8") == roto, "no se escribe nada"


def test_un_frontmatter_sin_cerrar_bloquea_con_su_codigo(tmp_path):
    (tmp_path / "00_System").mkdir()
    (tmp_path / "abierta.md").write_text("---\nid: x\n\ncuerpo\n", encoding="utf-8")
    assert _append(tmp_path, "abierta.md")["error_code"] == "FRONTMATTER_PARSE_ERROR"
