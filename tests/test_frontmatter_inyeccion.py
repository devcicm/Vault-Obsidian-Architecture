"""S5 — lo que un agente escribe no rompe el frontmatter ni el enlace a la nota.

Medido en v40.34 con 22 cargas (`\\n`, `---`, `: `, `#`, `&`, `*`, `!!python`,
`[..]`, `{..}`, `yes`, `null`, fechas, tabuladores...) por `vault_write`,
`vault_preferences`, `vault_ingest` y `vault_append`: el frontmatter salió
siempre válido para `yaml.safe_load`, sin claves inyectadas y con el valor
intacto. Estos tests lo fijan para que D2 (serializador único) no lo pierda.

Lo que sí rompió fue el **nombre del fichero**: `vault_write` conservaba `#`,
`^`, `[` y `]`, que Obsidian reserva dentro de `[[...]]`, así que la nota
existía pero nadie podía enlazarla (AP-14 con el criterio del consumidor,
AP-44).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

CUERPO = "\n".join(
    f"Linea {i} de una nota con cuerpo suficiente para el gate de contenido." for i in range(4)
)
CARGAS = [
    "a\nb: inyectada",
    "x\n---\ninyectada: 1",
    "clave: valor",
    "# no es comentario",
    "&ancla",
    "*alias",
    "!!python/object/apply:os.system ['echo x']",
    "{a: 1}",
    "yes",
    "null",
    "2026-01-01",
    "comillas \" y '",
]


def _ejecutar(raiz: Path, script: str, *argv: str) -> dict:
    proceso = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS),
    )
    salida = proceso.stdout.strip()
    assert salida, proceso.stderr
    return json.loads(salida[salida.index("{"):])


def _frontmatter(nota: Path) -> dict:
    texto = nota.read_text(encoding="utf-8")
    assert texto.startswith("---\n"), texto[:80]
    fm = yaml.safe_load(texto.split("\n---", 1)[0][4:])
    assert isinstance(fm, dict), fm
    return fm


@pytest.fixture
def raiz(tmp_path):
    raiz = tmp_path / "vault"
    for seccion in ("00_System", "07_Knowledge", "17_Preferences"):
        (raiz / seccion).mkdir(parents=True)
    return raiz


@pytest.mark.parametrize("carga", CARGAS)
def test_vault_write_conserva_el_valor_sin_inyectar_claves(raiz, carga):
    env = _ejecutar(
        raiz, "vault_write.py", "--folder", "07_Knowledge", "--title", carga,
        "--content", CUERPO, "--tags", "t1",
        "--meta", json.dumps({"agent": "pytest", "aliases": [carga], "extra": carga}),
    )
    assert env["ok"] is True, env
    fm = _frontmatter(raiz / env["path"])
    assert "inyectada" not in fm and "b" not in fm
    assert fm["title"] == carga
    assert fm["extra"] == carga
    assert fm["aliases"] == [carga]


@pytest.mark.parametrize("carga", CARGAS[:4])
def test_vault_preferences_conserva_el_enunciado(raiz, carga):
    sys.path.insert(0, str(SCRIPTS))
    import vault_preferences

    categoria = sorted(vault_preferences.CATEGORIES)[0]
    env = _ejecutar(
        raiz, "vault_preferences.py", "--set", "--category", categoria,
        "--title", f"Pref {carga}", "--statement", carga, "--rationale", carga,
        "--agent", "pytest",
    )
    assert env["ok"] is True, env
    notas = [p for p in (raiz / "17_Preferences").rglob("*.md") if p.name != "index.md"]
    assert len(notas) == 1, notas
    fm = _frontmatter(notas[0])
    assert "inyectada" not in fm and "b" not in fm
    assert fm["statement"] == carga


@pytest.mark.parametrize("titulo, nombre", [
    ("C# tips", "C-tips.md"),
    ("Nota [borrador]", "Nota-borrador.md"),
    ("Bloque ^ref", "Bloque-ref.md"),
    ("a | b", "a-b.md"),
])
def test_ap14_el_nombre_del_fichero_se_puede_enlazar(raiz, titulo, nombre):
    env = _ejecutar(
        raiz, "vault_write.py", "--folder", "07_Knowledge", "--title", titulo,
        "--content", CUERPO, "--tags", "t1", "--meta", json.dumps({"agent": "pytest"}),
    )
    assert env["ok"] is True, env
    ruta = raiz / env["path"]
    assert ruta.name == nombre, ruta.name
    assert not re.search(r"[#^\[\]|]", ruta.stem)
    # El título sigue intacto: lo que se limpia es el nombre, no el dato.
    assert _frontmatter(ruta)["title"] == titulo
