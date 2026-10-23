"""El bump único de versión es reproducible y se niega a divergir (O1a).

`vault_release.py` es el dueño del movimiento de release: siete sitios
que antes se tocaban a mano (el manifiesto a tres: banner, fila y
changelog; badge, cli/README, pyproject, `version.py` y la spec por su
dueño). El guard es real: corre la tool de verdad sobre un repo temporal
(AP-42, el criterio del consumidor) y las dos direcciones:

- sube de verdad los siete sitios y los deja coherentes para los tests
  heredados de versión;
- se niega a romper: segunda corrida = no-op, downgrade = rechazo,
  ficheros protegidos sucios = rechazo, fila de la tabla ausente =
  rechazo con el motivo escrito.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("PYTHONIOENCODING", "utf-8")  # stderr de los hijos: acentos

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

REPRODUCE = ["vault-obsidian-architecture.md", "README.md", "pyproject.toml",
             "cli/README.md", Path("vault/kernel/version.py"),
             "vault-sandbox/00_System/tool-spec.json"]


@pytest.fixture()
def repo_bump(tmp_path):
    """Un mini-repo con los siete ficheros de versión, tal como están hoy."""
    repo = tmp_path / "repo"
    for rel in REPRODUCE:
        destino = repo / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, destino)
    return repo


#: Decodificación estable para los hijos: stderr con acentos del envelope.
ENCODING = {"PYTHONIOENCODING": "utf-8"}


# Versión vieja del repo real en el momento del test: se lee, no se copia.
def _vieja():
    sys.path.insert(0, str(ROOT))
    from vault.kernel.version import CURRENT_VERSION
    return CURRENT_VERSION


def _salida(r) -> dict:
    """El envelope de una corrida: a stdout en la vía feliz; un rechazo con
    SystemExit imprime el JSON completo (multilínea) a stderr."""
    dec = json.JSONDecoder()
    for texto in ((r.stdout or "").strip(), (r.stderr or "").strip()):
        i = texto.find("{")
        if i == -1:
            continue
        try:
            obj, _ = dec.raw_decode(texto[i:])
            return obj
        except json.JSONDecodeError:
            continue
    return {}


def test_sube_los_siete_sitios(repo_bump, tmp_path):  # noqa: F811
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) + 1
    nueva = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "release de prueba",
         "--fecha", "2030-01-31", "--raiz", str(repo_bump),
          # el gate de contraste (P3) es otra puerta; estos tests miden el bump
          "--declarar-contraste-pendiente"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    env = json.loads(r.stdout)
    assert env["ok"] and env["escrito"] and env["version"] == nueva, env

    manifiesto = (repo_bump / "vault-obsidian-architecture.md").read_text(
        encoding="utf-8")
    assert f"**Versión:** {nueva} - 2030-01-31" in manifiesto, "banner"
    assert f"| {nueva} | 2030-01-31 | release de prueba |" in manifiesto,\
        "fila de tabla"
    assert f"### {nueva} — 2030-01-31 `git: pending`" in manifiesto, "changelog"
    # El ancla de la fila: queda DESPUÉS de la fila del release anterior.
    assert manifiesto.find(f"| {vieja} |") < manifiesto.find(f"| {nueva} |"), (
        "la fila nueva no quedó a continuación de la anterior")

    assert f'version = "{nueva.lstrip("v")}"' in (
        repo_bump / "pyproject.toml").read_text(encoding="utf-8")
    assert f"version-{nueva}-blue" in (
        repo_bump / "README.md").read_text(encoding="utf-8")
    assert f"**{nueva} · " in (
        repo_bump / "cli" / "README.md").read_text(encoding="utf-8")
    assert f'CURRENT_VERSION = "{nueva}"' in (
        repo_bump / "vault" / "kernel" / "version.py").read_text(
            encoding="utf-8")
    if (repo_bump / "vault-sandbox" / "00_System" / "tool-spec.json").exists():
        spec = json.loads(
            (repo_bump / "vault-sandbox" / "00_System" / "tool-spec.json")
            .read_text(encoding="utf-8"))
        assert spec["version"] == nueva, "la spec no la subió su dueño"


def test_la_segunda_corrida_es_no_op(repo_bump):
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) + 1
    nueva = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    r1 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "release de prueba",
         "--raiz", str(repo_bump),
         # el gate de contraste (P3) es otra puerta, probada en sus dos tests
         "--declarar-contraste-pendiente"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    assert _salida(r1).get("ok"), r1.stdout
    version_py = repo_bump / "vault" / "kernel" / "version.py"
    manifiesto = repo_bump / "vault-obsidian-architecture.md"
    antes = [(version_py.read_bytes(), manifiesto.read_bytes())]
    r2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "release de prueba",
         "--raiz", str(repo_bump),
         "--declarar-contraste-pendiente"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    d = _salida(r2)
    assert d["ok"] and d.get("escrito") is False, d
    despues = [(version_py.read_bytes(), manifiesto.read_bytes())]
    assert antes == despues, "el no-op reescribió ficheros"


def test_se_niega_a_regress(repo_bump):
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) - 1
    vieja_menor = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", vieja_menor, "--nota", "regresión",
         "--declarar-contraste-pendiente",
         "--raiz", str(repo_bump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    d = _salida(r)
    assert r.returncode == 1 and d.get("ok") is False, d


def test_se_niega_con_trabajo_sucio(repo_bump):
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) + 1
    nueva = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    subprocess.run(["git", "init", "-q", str(repo_bump)], capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_bump), "add", "-A"], capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_bump), "-c", "user.name=br",
         "-c", "user.email=b@r", "commit", "-q", "-m", "base"],
        capture_output=True)
    (repo_bump / "README.md").write_text("trabajo en curso\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "nada",
         "--declarar-contraste-pendiente",
         "--raiz", str(repo_bump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    d = _salida(r)
    assert r.returncode == 1 and "README.md" in d.get("detalle", ""), d


def test_se_niega_sin_ancala_de_fila(repo_bump):
    vieja = _vieja()
    nueva = f"v{int(vieja.lstrip('v').split('.')[0]) + 1}.0"
    manifiesto = repo_bump / "vault-obsidian-architecture.md"
    texto = manifiesto.read_text(encoding="utf-8")
    linea_vieja = [l for l in texto.splitlines() if f"| {vieja} |" in l][0]
    # `open(newline=)` y no `write_text(newline=)`: el argumento es 3.10+ en
    # pathlib y el piso declarado es 3.9 (test_piso_python).
    with manifiesto.open("w", encoding="utf-8", newline="") as f:
        f.write(texto.replace(linea_vieja, ""))
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "nada",
         "--declarar-contraste-pendiente",
         "--raiz", str(repo_bump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    d = _salida(r)
    assert r.returncode == 1 and "no está en el manifiesto" in d.get(
        "detalle", ""), d


# ── P3 · el bump exige contraste de vault ajeno, o el hueco declarado ─────────


def test_el_bump_se_niega_sin_contraste_y_dice_salida_de_regla_7(repo_bump):  # noqa
    """Sin recibo de contraste, el bump para y explica por qué y cómo resolverlo.

    El sandbox de este repo lo genera él mismo, así que contrastar contra él no
    contrasta nada (regla 7): la única salida honesta sin un vault ajeno a mano
    es declarar el hueco, y eso es lo que dice el mensaje.
    """
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) + 1
    nueva = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "sin contraste",
         "--fecha", "2030-01-31", "--raiz", str(repo_bump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    env = _salida(r)
    assert not env.get("ok") and not env.get("escrito"), env
    detalle = env.get("detalle", "")
    assert "regla 7" in detalle, detalle
    # el mensaje ofrece las dos salidas: medir o declarar
    assert "registrar-contraste" in detalle, detalle
    assert "declarar-contraste-pendiente" in detalle, detalle


def test_el_bump_pasa_con_contraste_vigente(repo_bump, tmp_path):  # noqa
    """Con un recibo fechado dentro del plazo, el bump no se frena por la regla 7."""
    d = repo_bump / "docs" / "contrastes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "ultimo-contraste.json").write_text(json.dumps(
        {"ok": True, "kind": "recibo_de_contraste",
         "fecha": "2030-01-01", "vault_medido": "notas-personales"}),
        encoding="utf-8")
    vieja = _vieja()
    numero = int(vieja.lstrip("v").split(".")[1]) + 1
    nueva = f"v{vieja.lstrip('v').split('.')[0]}.{numero}"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_release.py"),
         "--nueva-version", nueva, "--nota", "con contraste",
         "--fecha", "2030-01-31", "--raiz", str(repo_bump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, cwd=str(repo_bump))
    env = _salida(r)
    assert env.get("ok") and env.get("escrito"), env
