"""`vault_project_status`: el proyecto es un nombre, no una ruta ni YAML crudo.

Medido el 2026-10-01 en un vault del scratchpad, con el criterio del
consumidor (en otro proceso, como lo llama la CLI o el MCP).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ejecutar(vault: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_project_status.py"), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", cwd=str(vault.parent),
        timeout=120)
    salida = p.stdout + p.stderr
    return json.loads(salida[salida.index("{"):])


def _runtime(tmp_path: Path) -> Path:
    from vault.ciclo_de_vida import producto

    vault = tmp_path / "vault"
    assert producto.inicializar_runtime(vault)["ok"]
    return vault


def _alta(vault: Path, *args: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vault_project.py"), "--add", *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8"),
        capture_output=True, text=True, encoding="utf-8", cwd=str(vault.parent),
        timeout=120)
    r = json.loads(p.stdout[p.stdout.index("{"):])
    assert r["ok"], r
    return r


def test_ap36_un_proyecto_con_traversal_no_crea_nada_fuera_del_vault(tmp_path):
    """`--project ../../fuera` lo rechazaba la escritura atómica, pero el
    `mkdir` previo ya había creado `fuera/` junto al vault: un side effect
    fuera de él (AP-36) en la rama que se declaraba fallida.

    Desde AP-63 el traversal no llega a la tool: el nombre se resuelve contra
    el registro antes. Sin proyecto registrado es PROJECT_NOT_FOUND (ya no
    INVALID_PATH, que lo daba la tool); con `fuera` registrado, el nombre
    resuelve al slug y la nota cae **dentro** del vault. En ninguno de los
    dos casos existe ya una ruta que salga de él."""
    vault = _runtime(tmp_path)
    env = _ejecutar(vault, "--project", "../../fuera", "--status", "en_desarrollo",
                    "--summary", "prueba")
    assert env["ok"] is False
    assert env["error_code"] == "PROJECT_NOT_FOUND", env
    assert not (tmp_path / "fuera").exists(), "creó un directorio fuera del vault"

    _alta(vault, "fuera")
    env = _ejecutar(vault, "--project", "../../fuera", "--status", "en_desarrollo",
                    "--summary", "prueba")
    assert env["ok"] is True, env
    assert (vault / "01_Projects" / "fuera" / "status.md").exists()
    assert not (tmp_path / "fuera").exists(), "creó un directorio fuera del vault"


def test_ap46_el_proyecto_con_almohadilla_no_se_trunca_en_el_frontmatter(tmp_path):
    """`--project "Alfa #1"` escribía `title: Alfa #1 — Status` y
    `project: Alfa #1` sin escapar: ` #` abre un comentario YAML, y la nota
    quedaba con `project: Alfa` — atribuida en silencio a otro proyecto. Se
    lee con `yaml.safe_load`, que es como la lee el consumidor (AP-44).

    Desde AP-63 el texto hostil ya no llega a la nota: es un alias declarado
    en la ficha y la nota recibe el slug. El escapado sigue medido donde ahora
    vive el texto, en `aliases:` de `project.md`."""
    import yaml

    vault = _runtime(tmp_path)
    proyecto = "Alfa #1 l'beta"
    _alta(vault, "alfa", "--alias", proyecto)
    ficha = (vault / "01_Projects" / "alfa" / "project.md").read_text(encoding="utf-8")
    assert yaml.safe_load(ficha.split("---\n", 2)[1])["aliases"] == [proyecto]

    env = _ejecutar(vault, "--project", proyecto, "--status", "en_desarrollo",
                    "--summary", "prueba")
    assert env["ok"] is True, env
    texto = (vault / "01_Projects" / "alfa" / "status.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(texto.split("---\n", 2)[1])
    assert fm["project"] == "alfa"
    # El guion largo lo normaliza la capa de escritura (`vault_encoding`), en
    # todo el fichero y desde antes: no es parte de este defecto.
    assert fm["title"].startswith("alfa") and fm["title"].endswith("Status")
    assert fm["tags"] == ["status", "alfa"]
    assert not (vault / "01_Projects" / proyecto).exists()
