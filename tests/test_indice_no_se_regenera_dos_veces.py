"""Siete `*_save` regeneraban el índice de sección una segunda vez, en balde.

`atomic_write_text` dispara `vault_io._auto_section_index` desde v39: ese es el
punto único por el que pasan todas las escrituras y por el que se decidió
cablear ahí el índice. Las llamadas explícitas a `update_section_index()` que
los `*_save` traían de antes quedaron, y nadie las quitó porque no rompían
nada: producían el mismo fichero con el mismo contenido.

No eran inocuas. `write_report()` cuenta escrituras, así que la segunda pasada
se contabilizaba como `unchanged` en el envelope — la tool declaraba trabajo
que no hacía falta hacer. Es la sombra de AP-37 por el otro lado: no un `ok`
sin trabajo, sino trabajo inventado dentro de un `ok`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

#: Los siete que llamaban de más, con argv mínimo para producir una nota.
CULPABLES = {
    "vault_risk_save": ["--project", "demo", "--title", "Un riesgo"],
    "vault_ncr_save": ["--project", "demo", "--title", "Una no conformidad"],
    "vault_slo_save": [
        "--project", "demo", "--service", "api",
        "--slo_type", "availability", "--target", "99.9",
    ],
    "vault_incident_save": ["--project", "demo", "--title", "Un incidente"],
    "vault_privacy_save": [
        "--project", "demo", "--title", "Un tratamiento",
        "--purpose", "Analitica interna", "--legal_basis", "consent",
    ],
    "vault_release_save": ["--project", "demo", "--version", "1.0.0"],
    "vault_knowledge_save": [
        "--category", "concept",
        "--title", "Un concepto",
        "--content", "Una linea.\nOtra linea.\nY una tercera con palabras.",
    ],
}


def _ejecutar(raiz: Path, script: str, *argv: str):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=dict(os.environ, VAULT_ROOT=str(raiz), PYTHONIOENCODING="utf-8"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )


@pytest.fixture
def vault(tmp_path):
    _ejecutar(tmp_path, "vault_init")
    return tmp_path


def test_ninguno_llama_al_indice_a_mano():
    """El refuerzo vive en el write path; repetirlo aquí es la duplicación."""
    for script in CULPABLES:
        fuente = (SCRIPTS / f"{script}.py").read_text(encoding="utf-8")
        codigo = "\n".join(
            l for l in fuente.splitlines() if not l.lstrip().startswith("#")
        )
        assert "update_section_index(" not in codigo, script


@pytest.mark.parametrize("script", sorted(CULPABLES))
def test_el_indice_de_seccion_se_escribe_igual(vault, script):
    """Quitar la llamada no deja la sección sin índice: el kernel lo hace."""
    salida = _ejecutar(vault, script, *CULPABLES[script])
    envelope = json.loads(salida.stdout.strip().splitlines()[-1])
    assert envelope["ok"] is True, salida.stdout[-400:] + salida.stderr[-400:]

    # El `path` del envelope va siempre con `/`. Cuatro `*_save` lo publicaban
    # con el separador de Windows y trece con barra: misma decisión, dos
    # respuestas. Que este test lo asuma es deliberado — si vuelve a divergir,
    # falla aquí.
    assert "\\" not in envelope["path"], envelope["path"]
    seccion = envelope["path"].split("/")[0]
    assert (vault / seccion / "index.md").exists(), seccion


def test_ningun_save_publica_el_path_con_separador_de_windows():
    """`str(Path.relative_to(...))` da `\\` en Windows y `/` en Linux.

    Trece `*_save` lo normalizaban y cuatro no, así que el mismo campo del
    mismo envelope tenía dos formatos según la tool y el sistema operativo. Un
    consumidor que parta por `/` —el propio test de arriba lo hacía— funciona
    en CI y se rompe en la máquina del usuario.
    """
    sospechosos = []
    for ruta in sorted(SCRIPTS.glob("*_save.py")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if '"path":' in linea and "relative_to" in linea and "replace(" not in linea:
                sospechosos.append(f"{ruta.name}: {linea.strip()}")
    assert not sospechosos, sospechosos


def test_el_envelope_ya_no_declara_la_escritura_fantasma(vault):
    """Lo que cambia y por qué: el índice ya no se cuenta dos veces.

    `written` no se mueve —el trabajo real es el mismo—; lo que cae a cero es
    el `unchanged` que producía la segunda pasada del generador escribiendo
    byte a byte lo mismo que la primera.
    """
    salida = _ejecutar(vault, "vault_risk_save", *CULPABLES["vault_risk_save"])
    envelope = json.loads(salida.stdout.strip().splitlines()[-1])

    assert envelope["unchanged"] == 0, envelope
    assert envelope["written"] == 5, envelope
