"""The tutorial is executed, not just written (producto-usable S2).

`docs/TUTORIAL.md` is the first-use walk for a third party. Every ```bash
block runs here, in order, in an empty folder, with `vault` meaning the
product CLI (`python -m vault`): the commands a reader copies are the commands
this test runs. Then each promise the text makes is checked against the vault
the walk left behind. A tutorial that drifts from the product fails here, not
in the reader's terminal.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apoyo import correr_tool

ROOT = Path(__file__).resolve().parent.parent
TUTORIAL = ROOT / "docs" / "TUTORIAL.md"
def _resolver_bash():
    """Resuelve bash usable con Python nativo; en Windows prioriza Git Bash sobre WSL."""
    if os.name == "nt":
        git = shutil.which("git")
        candidatos = []
        if git:
            raiz_git = Path(git).resolve().parent.parent
            candidatos.extend([
                raiz_git / "bin" / "bash.exe",
                raiz_git / "usr" / "bin" / "bash.exe",
            ])
        candidatos.extend([
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ])
        for cand in candidatos:
            if cand.is_file():
                return str(cand)
        hallado = shutil.which("bash")
        if hallado and "system32" in Path(hallado).as_posix().lower():
            return None
        return hallado
    return shutil.which("bash")


BASH = _resolver_bash()


def _bloques() -> list:
    return re.findall(r"```bash\n(.*?)```", TUTORIAL.read_text(encoding="utf-8"), re.S)


def test_el_tutorial_es_solo_producto_instalado():
    """A third party has the installed CLI, not the repository checkout."""
    for bloque in _bloques():
        assert "scripts/" not in bloque and "python " not in bloque, bloque
        for linea in bloque.splitlines():
            linea = linea.strip()
            if linea and not linea.startswith(("#", "'", "--", "export ")):
                assert linea.startswith("vault "), linea


@pytest.fixture(scope="module")
def recorrido(tmp_path_factory):
    if not BASH:
        pytest.skip("bash no disponible: el tutorial está escrito para bash")
    carpeta = tmp_path_factory.mktemp("tutorial")
    python = Path(sys.executable).as_posix()
    guion = ["set -euo pipefail",
             f'vault() {{ "{python}" -m vault "$@"; }}',
             'paso() { echo "@@paso $1" >&2; }']
    for i, bloque in enumerate(_bloques(), 1):
        guion += [f"paso {i}", bloque]
    guion.append('echo "@@vault=$VAULT_ROOT" >&2')
    entorno = {k: v for k, v in os.environ.items()
               if not k.startswith("VAULT_") and k not in ("PYTHONHOME",)}
    entorno.update(PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    corrida = subprocess.run([BASH, "-c", "\n".join(guion)], cwd=str(carpeta), env=entorno,
                             capture_output=True, text=True, encoding="utf-8", timeout=1800)
    pasos = re.findall(r"@@paso (\d+)", corrida.stderr)
    assert corrida.returncode == 0, (
        f"el tutorial se rompe en el bloque {pasos[-1] if pasos else '?'}:\n"
        f"{corrida.stdout[-2000:]}\n{corrida.stderr[-2000:]}")
    return carpeta / "vault-tutorial"


def test_cada_bloque_del_tutorial_funciona(recorrido):
    assert (recorrido / "07_Knowledge").is_dir()


def test_la_nota_guardada_es_markdown_con_autor(recorrido):
    texto = (recorrido / "07_Knowledge" / "cola-de-eventos-con-redis.md").read_text(encoding="utf-8")
    assert texto.startswith("---\n") and "\n# " in texto
    assert re.search(r"^agent: ['\"]?yo['\"]?$", texto, re.M), texto[:400]


def test_la_sustituida_sigue_en_disco_y_apunta_a_la_vigente(recorrido):
    texto = (recorrido / "07_Knowledge" / "cola-de-eventos-con-redis.md").read_text(encoding="utf-8")
    assert "superseded_by:" in texto and "cola-de-eventos-con-nats" in texto


def test_la_busqueda_responde_lo_vigente_y_cuenta_lo_apartado(recorrido):
    env = correr_tool("vault_search", "--query", "cola de eventos", vault=recorrido).envelope
    assert env["results"][0]["path"] == "07_Knowledge/cola-de-eventos-con-nats.md"
    assert "07_Knowledge/cola-de-eventos-con-redis.md" not in [r["path"] for r in env["results"]]
    by_reason = env["history_excluded"]["by_reason"]
    assert by_reason.get("superseded") == 1, by_reason
    assert set(by_reason) <= {"superseded", "system_log"}, by_reason
    todo = correr_tool("vault_search", "--query", "cola de eventos", "--incluir-historico",
                       vault=recorrido).envelope
    assert "07_Knowledge/cola-de-eventos-con-redis.md" in [r["path"] for r in todo["results"]]


def test_el_paquete_de_contexto_deja_fuera_la_sustituida(recorrido):
    env = correr_tool("vault_context_pack", "cola de eventos", vault=recorrido).envelope
    incluidas = json.dumps(env.get("items") or env.get("included") or env, ensure_ascii=False)
    assert "cola-de-eventos-con-nats" in incluidas
    assert "07_Knowledge/cola-de-eventos-con-redis.md" not in [
        i.get("path") for i in (env.get("items") or env.get("included") or [])]


def test_la_historia_registra_las_notas_y_guarda_versiones(recorrido):
    log = correr_tool("vault_change_log", "--query", vault=recorrido).envelope
    creadas = {e["path"] for e in log["entries"] if e["action"] == "created"}
    assert {"07_Knowledge/cola-de-eventos-con-redis.md",
            "07_Knowledge/cola-de-eventos-con-nats.md"} <= creadas
    sustitucion = [e for e in log["entries"] if e["action"] == "updated"
                   and e["path"] == "07_Knowledge/cola-de-eventos-con-redis.md"]
    assert sustitucion and sustitucion[0]["agent"] == "yo", log["entries"]
    versiones = correr_tool("vault_undo", "--list", "07_Knowledge/cola-de-eventos-con-redis.md",
                            vault=recorrido).envelope
    assert versiones.get("ok") is True and (versiones.get("versions") or versiones.get("total")), versiones
