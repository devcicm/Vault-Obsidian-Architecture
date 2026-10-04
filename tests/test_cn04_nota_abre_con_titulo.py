"""CN-04 — la nota abre con su título como H1.

Medido el 2026-10-04 en la QA de producto: las notas de `vault_write`,
`vault_knowledge_save` y `vault_ai_decision` empezaban en la primera frase o
en una línea de metadatos. Se lee lo escrito en disco, como lo abriría un
editor de texto, no lo que la tool dice haber escrito.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from vault.kernel.contenido import con_titulo  # noqa: E402
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402
from vault_norms_catalog import norma_por_codigo  # noqa: E402

CONTENIDO = ("El sistema registra cada evento con su marca temporal.\n"
             "La cola reintenta tres veces antes de descartar el mensaje.\n"
             "Los errores se envían al canal de observabilidad del equipo.\n")


def _correr(raiz, script, *args):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               VAULT_AGENT="probe", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=300)
    sobre = json.loads(p.stdout)
    assert sobre.get("ok") is True, p.stdout[-600:]
    return sobre


def _primera_linea(raiz, rel):
    _, cuerpo = separar_frontmatter((raiz / rel).read_text(encoding="utf-8"))
    return next(ln for ln in cuerpo.splitlines() if ln.strip())


def test_cn04_las_tres_tools_escriben_el_h1(tmp_path):
    for seccion in ("00_System", "01_Projects", "07_Knowledge", "16_AI_Governance", "99_Index"):
        (tmp_path / seccion).mkdir()
    _correr(tmp_path, "vault_project.py", "--add", "demo")
    w = _correr(tmp_path, "vault_write.py", "--folder", "07_Knowledge",
                "--title", "Colas con reintento", "--tags", "demo", "--content", CONTENIDO)
    k = _correr(tmp_path, "vault_knowledge_save.py", "--category", "concept",
                "--title", "Concepto de cola", "--content", CONTENIDO, "--project", "demo")
    d = _correr(tmp_path, "vault_ai_decision.py", "--project", "demo", "--title", "Reintento acotado",
                "--decision_type", "process", "--description", "Colas con reintento acotado.",
                "--rationale", "No perder mensajes sin saturar al consumidor.")
    assert _primera_linea(tmp_path, w["path"]) == "# Colas con reintento"
    assert _primera_linea(tmp_path, k["path"]) == "# Concepto de cola"
    assert _primera_linea(tmp_path, d["path"]) == "# Reintento acotado"


def test_cn04_reescribir_no_duplica_el_h1(tmp_path):
    for seccion in ("00_System", "07_Knowledge", "99_Index"):
        (tmp_path / seccion).mkdir()
    args = ("vault_write.py", "--folder", "07_Knowledge", "--title", "Nota",
            "--tags", "demo", "--content")
    r = _correr(tmp_path, *args, CONTENIDO)
    _, cuerpo = separar_frontmatter((tmp_path / r["path"]).read_text(encoding="utf-8"))
    _correr(tmp_path, *args, cuerpo + "Una cuarta línea con algo más que decir sobre la cola.\n")
    texto = (tmp_path / r["path"]).read_text(encoding="utf-8")
    assert texto.count("# Nota\n") == 1


def test_cn04_el_dueno_respeta_un_h1_propio_y_no_confunde_etiquetas():
    assert con_titulo("JWT", "Token firmado.\n") == "# JWT\n\nToken firmado.\n"
    assert con_titulo("JWT", "# Mi título\n\nx") == "# Mi título\n\nx"
    assert con_titulo("JWT", "#etiqueta x").startswith("# JWT\n\n#etiqueta")
    assert con_titulo("Dos\nlíneas", "x").startswith("# Dos líneas\n")


def test_cn04_esta_catalogada_con_sus_tools():
    norma = norma_por_codigo("CN-04")
    assert norma["enforcement"] == "guard"
    assert set(norma["tools_enforcing"]) == {"vault_write", "vault_knowledge_save", "vault_ai_decision"}
