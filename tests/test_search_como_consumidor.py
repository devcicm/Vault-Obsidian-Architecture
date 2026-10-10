"""AP-44 / AP-37 — `vault_search` encuentra lo que el agente escribió y dice lo que calla.

Medido como consumidor el 2026-10-10 sobre una nota «Canción» con la tag
«Música» (que `vault_write` guarda normalizada como `musica`), todo `ok: true`:

- `--query cancion` y `--query CONFIGURACION` daban 0: el texto se comparaba
  con `.lower()` y sin plegar acentos.
- `--tag Música` daba 0 —la tag guardada es `musica`—: el filtro no usaba la
  normalización con que se guardó, el criterio del propio escritor (AP-44).
- `--folder 07_K` casaba con `07_Knowledge` (prefijo de texto), `--folder
  NoExiste` y `--folder ../` respondían 0 resultados como si buscaran.
- `--query ""` devolvía todo el vault.
- Más de 20 coincidencias se recortaban sin decirlo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _nota(titulo: str, tags: str, cuerpo: str) -> str:
    return (f"---\ntitle: {titulo}\nstatus: draft\ntype: knowledge\ntags: [{tags}]\n---\n"
            f"# {titulo}\n\n{cuerpo}\n")


def _cli(raiz: Path, script: str, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    return json.loads(texto[texto.index("{"):]) if "{" in texto else {"raw": p.stderr}


@pytest.fixture(scope="module")
def raiz(tmp_path_factory):
    r = tmp_path_factory.mktemp("srch") / "vault"
    (r / "00_System").mkdir(parents=True)
    k = r / "07_Knowledge"
    k.mkdir()
    (k / "cancion.md").write_text(_nota("Canción", "musica", "La configuración del verano."),
                                  encoding="utf-8")
    for i in range(25):
        (k / f"lote-{i}.md").write_text(_nota(f"Lote {i}", "lote", "palabra repetida"),
                                        encoding="utf-8")
    _cli(r, "vault_reindex.py")
    return r


def _paths(env: dict) -> list:
    return [x["path"] for x in env.get("results", [])]


@pytest.mark.parametrize("consulta", ["cancion", "CANCIÓN", "CONFIGURACION", "configuración"])
def test_la_consulta_pliega_acentos_y_mayusculas(raiz, consulta):
    env = _cli(raiz, "vault_search.py", "--query", consulta)
    assert "07_Knowledge/cancion.md" in _paths(env), env


@pytest.mark.parametrize("tag", ["musica", "Música", "#música", "MUSICA"])
def test_el_filtro_de_tag_usa_la_forma_guardada(raiz, tag):
    # AP-44: se compara con el mismo criterio con que `vault_write` la guardó.
    env = _cli(raiz, "vault_search.py", "--query", "verano", "--tag", tag)
    assert _paths(env) == ["07_Knowledge/cancion.md"], env


def test_la_carpeta_es_un_componente_no_un_prefijo(raiz):
    env = _cli(raiz, "vault_search.py", "--query", "verano", "--folder", "07_K")
    assert env["ok"] is False and env["error_code"] == "FOLDER_NOT_FOUND", env
    env = _cli(raiz, "vault_search.py", "--query", "verano", "--folder", "07_Knowledge/")
    assert _paths(env) == ["07_Knowledge/cancion.md"], env


def test_una_carpeta_fuera_del_vault_se_rechaza(raiz):
    env = _cli(raiz, "vault_search.py", "--query", "verano", "--folder", "../")
    assert env["ok"] is False and env["error_code"] == "INVALID_PATH", env


@pytest.mark.parametrize("consulta", ["", "   "])
def test_la_consulta_vacia_se_rechaza(raiz, consulta):
    env = _cli(raiz, "vault_search.py", "--query", consulta)
    assert env["ok"] is False and env["error_code"] == "INVALID_INPUT", env


def test_el_recorte_se_declara(raiz):
    # AP-37: 25 coincidencias, 20 devueltas, y el sobre lo dice.
    env = _cli(raiz, "vault_search.py", "--query", "palabra repetida")
    assert env["total"] == 20 and env["matched"] == 25 and env["truncated"] is True, env
    env = _cli(raiz, "vault_search.py", "--query", "verano")
    assert env["matched"] == env["total"] and env["truncated"] is False, env
