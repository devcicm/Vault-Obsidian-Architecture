"""AP-08 — una nota que no acompañó al cambio de su código sale nombrada.

El manifiesto da la señal de AP-08 desde v19: «el `updatedAt` de la nota es muy
anterior al de los archivos de código relacionados». Hasta v41.3 ninguna tool
la medía y el catálogo declaraba la norma `cobertura_descubierta`. Ahora
`vault_drift_detect --mode vigencia` compara el `updatedAt` de cada nota del
proyecto con el último commit que tocó los ficheros que la nota declara en
`files:`. La relación nota → código la declara la nota; no se adivina por el
nombre del fichero.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _tool(raiz: Path, script: str, *argv: str):
    env = dict(os.environ, VAULT_ROOT=str(raiz), VAULT_STRICT_ROOT="1",
               PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest")
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *argv],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(raiz.parent), timeout=300)
    salida = p.stdout.strip()
    assert salida, p.stderr[-1000:]
    return p.returncode, json.loads(salida[salida.index("{"):])


def _git(repo: Path, *argv: str, fecha: str = "2026-01-01T00:00:00+00:00"):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_AUTHOR_DATE=fecha, GIT_COMMITTER_DATE=fecha)
    subprocess.run(["git", *argv], cwd=str(repo), env=env, check=True,
                   capture_output=True)


def _commit(repo: Path, fichero: str, fecha: str):
    (repo / fichero).write_text(f"# {fecha}\n", encoding="utf-8")
    _git(repo, "add", fichero)
    _git(repo, "commit", "-q", "-m", fichero, fecha=fecha)


def _nota(raiz: Path, nombre: str, fm: str):
    (raiz / "07_Knowledge" / f"{nombre}.md").write_text(
        f"---\ntitle: {nombre}\n{fm}\n---\n# {nombre}\n", encoding="utf-8")


def _proyecto(tmp_path: Path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "viejo.py", "2025-06-01T00:00:00+00:00")
    _commit(repo, "nuevo.py", "2026-03-01T00:00:00+00:00")
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    assert _tool(raiz, "vault_project", "--add", "demo")[1]["ok"] is True
    assert _tool(raiz, "vault_project", "--link", "demo", "--path", str(repo))[1]["ok"] is True
    return raiz, repo


def test_ap08_vigencia_nombra_la_nota_que_no_acompano_al_cambio(tmp_path):
    raiz, _ = _proyecto(tmp_path)
    base = "project: demo\nstatus: active\nupdatedAt: 2026-01-01T00:00:00Z"
    _nota(raiz, "desfasada", base + "\nfiles:\n  - nuevo.py")
    _nota(raiz, "vigente", base + "\nfiles:\n  - viejo.py")
    _nota(raiz, "sin-files", base)
    _nota(raiz, "rota", base + "\nfiles:\n  - no-existe.py")
    _nota(raiz, "retirada", "project: demo\nstatus: deprecated\n"
          "updatedAt: 2026-01-01T00:00:00Z\nfiles:\n  - nuevo.py")
    _nota(raiz, "reemplazada", base + '\nsuperseded_by: "[[desfasada]]"\n'
          "files:\n  - nuevo.py")
    _nota(raiz, "ajena", "project: otro\nstatus: active\n"
          "updatedAt: 2026-01-01T00:00:00Z\nfiles:\n  - nuevo.py")

    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["ok"] is True, r
    assert r["norm"] == "AP-08"
    assert [d["path"] for d in r["desfasadas"]] == ["07_Knowledge/desfasada.md"]
    assert r["desfasadas"][0]["files"] == ["nuevo.py"]
    # La ficha del proyecto tampoco declara `files:`: se cuenta, no se oculta.
    assert r["sin_files"] == ["01_Projects/demo/project.md", "07_Knowledge/sin-files.md"]
    assert [d["path"] for d in r["sin_historia"]] == ["07_Knowledge/rota.md"]
    assert r["summary"] == {"desfasadas": 1, "vigentes": 1, "sin_files": 2,
                            "sin_historia": 1, "codigo_inexistente": 1,
                            # AP-01 en prosa (v41.3): estas notas no citan rutas.
                            "prosa_inexistente": 0, "prosa_base_ambigua": 0}
    # `rota.md` apunta a un fichero que no existe: además es AP-01.
    assert [d["path"] for d in r["codigo_inexistente"]] == ["07_Knowledge/rota.md"]
    assert r["action_required"] is True


def test_ap08_vigencia_actualizar_la_nota_la_devuelve_a_vigente(tmp_path):
    raiz, _ = _proyecto(tmp_path)
    _nota(raiz, "al-dia", "project: demo\nstatus: active\n"
          "updatedAt: 2026-04-01\nfiles:\n  - nuevo.py")
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0 and r["desfasadas"] == [] and r["summary"]["vigentes"] == 1, r
    assert r["action_required"] is False


def test_ap08_vigencia_sin_git_no_finge_vigencia(tmp_path):
    raiz = tmp_path / "vault"
    raiz.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _tool(raiz, "vault_init")[1]["ok"] is True
    assert _tool(raiz, "vault_project", "--add", "demo")[1]["ok"] is True
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--path", str(repo),
                  "--mode", "vigencia")
    assert rc == 1 and r["ok"] is False and r["error_code"] == "GIT_UNAVAILABLE", r


def test_ap08_los_estados_sin_vigencia_son_del_vocabulario():
    """Un estado que no está en `STATUS_VOCAB` nunca coincidiría: el filtro
    quedaría escrito y sin efecto, que es lo que tenía su primer borrador."""
    sys.path.insert(0, str(SCRIPTS))
    import vault_drift_detect
    from vault_norms_catalog import STATUS_VOCAB
    assert vault_drift_detect._ESTADOS_SIN_VIGENCIA <= set(STATUS_VOCAB)


def test_ap08_revisar_una_nota_sin_cambiarla_la_devuelve_a_vigente(tmp_path):
    """`updatedAt` solo se mueve si el texto cambia. Quien comprueba que la
    nota sigue siendo cierta lo deja en `revisado_en` (contrato v41), y esa
    revisión cuenta como acompañar al cambio del código."""
    raiz, _ = _proyecto(tmp_path)
    base = "project: demo\nstatus: active\nupdatedAt: 2026-01-01T00:00:00Z\nfiles:\n  - nuevo.py"
    _nota(raiz, "revisada", base + "\nrevisado_en: 2026-04-01")
    _nota(raiz, "revisada-antes", base + "\nrevisado_en: 2026-02-01")
    rc, r = _tool(raiz, "vault_drift_detect", "--project", "demo", "--mode", "vigencia")
    assert rc == 0, r
    assert [d["path"] for d in r["desfasadas"]] == ["07_Knowledge/revisada-antes.md"], r
    assert r["summary"]["vigentes"] == 1
