"""F1/CIA-I — `vault_runbook_log` registra la ejecución bajo el lock de la nota.

Medido en v40.34: la tool leía el runbook, añadía la entrada al historial,
subía `executions` y reescribía la nota entera, sin lock. Dos ejecuciones
registradas a la vez se pisaban: la que llegaba segunda escribía sobre su
lectura vieja, la entrada de la otra desaparecía y el contador se quedaba
corto. Los dos envelopes en `ok: true`, con el mismo `executionNumber`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from vault.kernel.errores import problemas_de_forma  # noqa: E402
from vault_lib import parse_frontmatter  # noqa: E402
from vault.kernel import bloqueo  # noqa: E402

RUNBOOK = (
    "---\ntitle: deploy\nexecutions: 0\n---\n# deploy\n\n"
    "## Historial de Ejecuciones\n\nSin ejecuciones registradas.\n"
)


def _argv(*a):
    return [sys.executable, str(SCRIPTS / "vault_runbook_log.py"), *a]


def _vault(tmp_path):
    raiz = tmp_path / "vault"
    (raiz / "08_Runbooks").mkdir(parents=True)
    (raiz / "00_System").mkdir()
    nota = raiz / "08_Runbooks" / "deploy.md"
    nota.write_text(RUNBOOK, encoding="utf-8")
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8")
    return raiz, nota, env


def _leer(p):
    salida, error = p.communicate(timeout=180)
    texto = salida.decode("utf-8", "replace")
    assert "{" in texto, error.decode("utf-8", "replace")
    return json.loads(texto[texto.index("{"):])


def test_ejecuciones_en_paralelo_llegan_todas(tmp_path):
    raiz, nota, env = _vault(tmp_path)
    n = 8
    procesos = [
        subprocess.Popen(_argv("--path", "08_Runbooks/deploy.md", "--outcome", "success",
                               "--notes", f"ejecucion-{i}"),
                         env=env, cwd=str(SCRIPTS), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(n)
    ]
    resultados = [_leer(p) for p in procesos]
    assert all(r["ok"] for r in resultados), resultados
    texto = nota.read_text(encoding="utf-8")
    perdidas = [i for i in range(n) if f"ejecucion-{i}" not in texto]
    assert perdidas == [], f"entradas perdidas: {perdidas}"
    assert int(parse_frontmatter(texto)["executions"]) == n
    assert sorted(r["executionNumber"] for r in resultados) == list(range(1, n + 1))


def test_con_la_nota_tomada_no_escribe_y_lo_dice(tmp_path):
    raiz, nota, env = _vault(tmp_path)
    ocupado = nota.parent / ".locks" / f"{nota.name}.lock"
    ocupado.mkdir(parents=True)
    (ocupado / "owner.json").write_text(
        json.dumps(bloqueo.ficha_del_dueno("otro")), encoding="utf-8")
    r = _leer(subprocess.Popen(
        _argv("--path", "08_Runbooks/deploy.md", "--outcome", "failed"),
        env=env, cwd=str(SCRIPTS), stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    assert r["ok"] is False and r["error_code"] == "NOTE_LOCKED", r
    assert problemas_de_forma(r) == [], r
    assert nota.read_text(encoding="utf-8") == RUNBOOK
