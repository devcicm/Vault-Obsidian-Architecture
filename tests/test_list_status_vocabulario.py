"""CN-03 — `vault_list --status` filtra por el vocabulario canónico.

Medido como consumidor el 2026-10-10: `--status inventado` devolvía `ok: true`
con cero notas, indistinguible de «no hay ninguna en ese estado», y `--status
implementado` —el ejemplo que da el propio `--help`— no veía las notas con
`status: implemented`. El filtro comparaba el texto crudo sin pasar por
`normalize_status`, cuyo contrato dice que un estado que no se puede decidir
se rechaza, no se adivina.

Un estado fuera del vocabulario que sí aparece literal en alguna nota (un
vault ajeno, regla 7) se sigue pudiendo listar, marcado como tal: sanar un
vault empieza por encontrar esas notas.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(raiz: Path, *args: str) -> dict:
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run([sys.executable, str(SCRIPTS / "vault_list.py"), *args],
                       env=env, cwd=str(SCRIPTS), capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    texto = p.stdout.strip()
    assert texto, p.stderr
    return json.loads(texto[texto.index("{"):])


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "vault"
    (r / "07_Knowledge").mkdir(parents=True)
    for nombre, estado in (("a", "implemented"), ("b", "implementado"),
                           ("c", "draft"), ("d", "borrador")):
        (r / "07_Knowledge" / f"{nombre}.md").write_text(
            f"---\ntitle: {nombre}\nstatus: {estado}\n---\n# {nombre}\n", encoding="utf-8")
    return r


def _rutas(env):
    return sorted(n["path"].rsplit("/", 1)[-1] for n in env["notes"])


def test_un_estado_que_no_existe_se_rechaza(raiz):
    env = _run(raiz, "--folder", "07_Knowledge", "--status", "inventado")
    assert env["ok"] is False and env["error_code"] == "INVALID_INPUT", env
    assert "implemented" in env["message"]


@pytest.mark.parametrize("pedido", ["implemented", "implementado", "Implemented"])
def test_el_filtro_compara_estados_canonicos(raiz, pedido):
    env = _run(raiz, "--folder", "07_Knowledge", "--status", pedido)
    assert env["ok"] is True, env
    assert _rutas(env) == ["a.md", "b.md"]
    assert env["status"] == "implemented"


def test_un_estado_fuera_del_vocabulario_presente_se_lista_marcado(raiz):
    env = _run(raiz, "--folder", "07_Knowledge", "--status", "borrador")
    assert env["ok"] is True, env
    assert _rutas(env) == ["d.md"]
    assert env["status_fuera_de_vocabulario"] is True
