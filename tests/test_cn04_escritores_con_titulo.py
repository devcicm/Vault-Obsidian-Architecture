"""CN-01 y CN-04 en los escritores: la nota que crea una tool abre con H1 (deuda #13).

`vault_write`, `knowledge_save` y `ai_decision` ya pasaban el cuerpo por
`vault.kernel.contenido.con_titulo`; medido el 2026-10-08 sobre una copia del
sandbox, otros diez escritores creaban la nota sin título. El audit de solo
lectura (m128) los habría reportado en cada vault después de que la tool los
escribiera: el arreglo es en el escritor, que es donde nace la nota, y con el
criterio del dueño (`abre_con_h1`), no con uno propio del test (AP-44).

Cada escritor se ejecuta como lo haría un cliente —subproceso, con
`VAULT_ROOT` apuntando a una copia del sandbox— y se mira la nota que creó.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vault.kernel.contenido import abre_con_h1  # noqa: E402
from vault.kernel.frontmatter_parsing import separar_frontmatter  # noqa: E402
from vault_lib import slugify_strict  # noqa: E402

_P = ["--project", "mi-api"]

ESCRITORES = {
    "vault_bug_save": _P + ["--title", "Token coercionado", "--symptom",
                            "El literal llega como px", "--severity", "high"],
    "vault_code_module": _P + ["--file_path", "src/auth.py", "--description",
                               "Modulo de autenticacion", "--language", "python"],
    "vault_diagram_save": _P + ["--title", "User Flow", "--diagram_type", "mermaid",
                                "--category", "flow", "--content", "graph TD\n  A --> B"],
    "vault_flow_save": _P + ["--name", "User Registration", "--type", "workflow",
                             "--description", "Full process",
                             "--mermaid", "flowchart TD\n  A --> B"],
    "vault_test_save": _P + ["--title", "Login", "--test_type", "unit",
                             "--description", "Verifica el login"],
    "vault_requirement_save": _P + ["--title", "Auth", "--description", "Login de usuario",
                                    "--type", "functional", "--priority", "must-have"],
    "vault_infra_save": ["--name", "prod-cluster", "--type", "server", "--description",
                         "Cluster productivo", "--config", '{"region": "us-east-1"}'],
    # Reescribe la misma `infra-map.md` que `vault_infra_save`, por su cuenta.
    "vault_infra_map": [],
    "vault_pattern_save": _P + ["--name", "Repository", "--type", "architecture",
                                "--status", "planificado", "--description", "Abstraccion de acceso a datos"],
    "vault_runbook_save": _P + ["--title", "Deploy", "--trigger", "manual",
                                "--category", "deploy", "--steps", '[{"step": "Build"}, {"step": "Publicar"}]'],
}


def _foto(v: Path) -> dict:
    return {p.relative_to(v).as_posix(): p.stat().st_mtime_ns for p in v.rglob("*.md")
            if not any(s.startswith(".") for s in p.relative_to(v).parts)}


@pytest.fixture(scope="module")
def copia(tmp_path_factory):
    v = tmp_path_factory.mktemp("cn04") / "vault"
    shutil.copytree(ROOT / "vault-sandbox", v, ignore=shutil.ignore_patterns(".locks"))
    return v


def _ejecutar(v: Path, tool: str, args: list) -> subprocess.CompletedProcess:
    env = {**os.environ, "VAULT_ROOT": str(v), "VAULT_STRICT_ROOT": "1",
           "VAULT_AGENT": "test", "VAULT_VOICE": "0", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{tool}.py"), *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )


@pytest.mark.parametrize("tool", sorted(ESCRITORES))
def test_la_nota_que_crea_el_escritor_abre_con_h1(copia, tool):
    vault = copia
    if not (vault / "01_Projects" / "mi-api").exists():
        r = _ejecutar(vault, "vault_project", ["--add", "mi-api", "--title", "Mi API"])
        assert r.returncode == 0, r.stdout + r.stderr
    antes = _foto(vault)
    r = _ejecutar(vault, tool, ESCRITORES[tool])
    assert r.returncode == 0, (r.stdout + r.stderr)[-800:]
    despues = _foto(vault)
    nuevas = [k for k, t in despues.items() if antes.get(k) != t
              and not k.endswith(("index.md", "_index.md")) and "/" in k
              and not k.startswith(("00_System/", "01_Projects/"))]
    assert nuevas, f"{tool} no creó ninguna nota"
    sin_h1 = [k for k in nuevas
              if not abre_con_h1(separar_frontmatter(
                  (vault / k).read_text(encoding="utf-8"))[1] or "")]
    assert sin_h1 == [], f"{tool} crea notas que no abren con H1 (CN-04): {sin_h1}"
    # CN-01 con el criterio del audit (`slugify_strict` sobre el nombre), no
    # con el `slugify` que cada escritor use por dentro.
    no_kebab = [k for k in nuevas if slugify_strict(Path(k).stem) != Path(k).stem]
    assert no_kebab == [], f"{tool} crea notas con nombre fuera de CN-01: {no_kebab}"
