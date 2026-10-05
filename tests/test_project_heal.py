"""AP-63, P6 — `vault_project --heal`: el `project:` canónico, sin inventar.

Repara lo mecánico —`Proyecto:`/`PROJECT:` y el valor que resuelve por alias
o variante— al slug del registro. Dry-run por defecto; `--apply` deja la
versión anterior en `.history/` con el nombre que lee `vault_undo`. Un
fantasma o un conflicto se listan y no se tocan, y la copia del manifiesto no
cuenta como nota.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _cli(vault: Path, script: str, *args: str):
    p = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env=dict(os.environ, VAULT_ROOT=str(vault), VAULT_STRICT_ROOT="1",
                 PYTHONIOENCODING="utf-8", VAULT_AGENT="pytest"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(SCRIPTS), timeout=180,
    )
    return p.returncode, json.loads(p.stdout[p.stdout.index("{"):])


def _nota(vault: Path, rel: str, cabecera: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {p.stem}\n{cabecera}tags: [demo]\n---\n\n# {p.stem}\n\ncuerpo\n",
                 encoding="utf-8")
    return p


def _fm(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1])


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    (v / "00_System").mkdir(parents=True)
    assert _cli(v, "vault_project.py", "--add", "mi-api", "--alias", "Pasarela")[1]["ok"]
    assert _cli(v, "vault_project.py", "--add", "otra")[1]["ok"]
    return v


@pytest.fixture
def notas(vault):
    return {
        "clave": _nota(vault, "07_Knowledge/a.md", "Proyecto: Pasarela\n"),
        "alias": _nota(vault, "07_Knowledge/b.md", "project: Mi_API\n"),
        "bien": _nota(vault, "07_Knowledge/c.md", "project: mi-api\n"),
        "fantasma": _nota(vault, "07_Knowledge/d.md", "project: nadie\n"),
        "conflicto": _nota(vault, "07_Knowledge/e.md", "project: mi-api\nPROJECT: otra\n"),
    }


def test_ap63_heal_en_dry_run_no_escribe(vault, notas):
    antes = {k: p.read_bytes() for k, p in notas.items()}
    codigo, r = _cli(vault, "vault_project.py", "--heal")
    assert codigo == 0 and r["mode"] == "dry-run" and r["healed"] == 0, r
    assert sorted(x["note"] for x in r["repairable"]) == ["07_Knowledge/a.md", "07_Knowledge/b.md"]
    assert {x["note"]: x["cause"] for x in r["unrepaired"]} == {
        "07_Knowledge/d.md": "no_registrado", "07_Knowledge/e.md": "conflicto"}
    assert {k: p.read_bytes() for k, p in notas.items()} == antes
    assert not (vault / ".history").exists()


def test_ap63_heal_apply_canoniza_y_deja_copia_que_undo_lee(vault, notas):
    fantasma, conflicto = notas["fantasma"].read_bytes(), notas["conflicto"].read_bytes()
    codigo, r = _cli(vault, "vault_project.py", "--heal", "--apply")
    assert codigo == 0 and r["healed"] == 2, r

    fm = _fm(notas["clave"])
    assert fm["project"] == "mi-api" and "Proyecto" not in fm
    assert fm["title"] == "a" and fm["tags"] == ["demo"]
    assert _fm(notas["alias"])["project"] == "mi-api"
    # Lo que no resuelve a un único proyecto no se adivina.
    assert notas["fantasma"].read_bytes() == fantasma
    assert notas["conflicto"].read_bytes() == conflicto

    copia = r["repairable"][0]["backup"]
    assert (vault / copia).is_file() and "Proyecto: Pasarela" in (vault / copia).read_text(encoding="utf-8")
    codigo, v = _cli(vault, "vault_undo.py", "--list", "07_Knowledge/a.md")
    assert any(x["filename"] == Path(copia).name for x in v.get("versions", [])), v

    # Idempotente: una segunda pasada no encuentra nada.
    codigo, r = _cli(vault, "vault_project.py", "--heal", "--apply")
    assert r["healed"] == 0 and r["repairable_count"] == 0, r


def test_ap63_heal_no_toca_la_copia_del_manifiesto(vault):
    copia = vault / "99_Archive" / "vault-obsidian-architecture-v39.md"
    copia.parent.mkdir(parents=True)
    copia.write_text((ROOT / "vault-obsidian-architecture.md").read_text(encoding="utf-8")[:20000],
                     encoding="utf-8")
    antes = copia.read_bytes()
    codigo, r = _cli(vault, "vault_project.py", "--heal", "--apply")
    assert codigo == 0 and all("99_Archive" not in x["note"] for x in r["repairable"] + r["unrepaired"]), r
    assert copia.read_bytes() == antes


def test_ap63_una_nota_ilegible_se_declara_en_vez_de_saltarse(vault, notas):
    """Regla 7 contra /ans (2026-10-04): una nota con `title: ADR-004 — … (Musk): …`
    sin comillas no parsea, y el audit la saltaba sin decirlo. Si esa nota
    citaba un proyecto fantasma, el audit salía limpio sin haberla leído."""
    rota = vault / "03_Decisions" / "adr.md"
    rota.parent.mkdir(parents=True)
    rota.write_text("---\ntitle: ADR-004 — Algoritmo (Musk): eliminar\nproject: nadie\n---\n\n# ADR\n",
                    encoding="utf-8")
    antes = rota.read_bytes()
    codigo, r = _cli(vault, "vault_project.py", "--audit")
    assert r["notes_unreadable_total"] == 1, r
    assert r["notes_unreadable"][0]["note"] == "03_Decisions/adr.md"
    codigo, r = _cli(vault, "vault_project.py", "--heal", "--apply")
    assert {"note": "03_Decisions/adr.md", "cause": "frontmatter_ilegible"} in r["unrepaired"], r
    assert rota.read_bytes() == antes
