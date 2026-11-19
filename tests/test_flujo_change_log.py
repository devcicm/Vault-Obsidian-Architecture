"""The change log is born with the vault (bigo-inmutabilidad, S8 a).

Until 2026-11-19 the first logged operation created `00_System/change-log.md`.
On a freshly indexed vault that left `vault_reindex --check` at `index_stale`
(`missing_in_index: [00_System/change-log.md]`): an append only refreshes the
search rows that already exist. `vault_init` now writes the log's initial state
through its owner before the first reindex: the Markdown header and an empty
`.change-log.jsonl`. Nothing is recorded — the history starts empty — and a
vault that already holds a log is left as it is.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from apoyo import correr_tool, filas_de_bitacora, git_en
from vault_change_log import MD_HEADER


@pytest.fixture(scope="module")
def _vault_nuevo(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("nacido") / "vault"
    raiz.mkdir()
    r = correr_tool("vault_init", "--no-audit", vault=raiz)
    assert r.codigo == 0, r.stdout + r.stderr
    return raiz, r.envelope


@pytest.fixture
def vault(_vault_nuevo, tmp_path) -> Path:
    copia = tmp_path / "vault"
    shutil.copytree(_vault_nuevo[0], copia)
    return copia


def _estado(vault: Path) -> dict:
    r = correr_tool("vault_reindex", "--check", vault=vault)
    return {"codigo": r.codigo, **r.envelope}


def test_el_vault_nace_con_su_change_log(_vault_nuevo):
    raiz, envelope = _vault_nuevo
    md = raiz / "00_System" / "change-log.md"
    lineas = raiz / "00_System" / ".change-log.jsonl"
    assert md.read_text(encoding="utf-8") == MD_HEADER
    assert lineas.read_bytes() == b""
    assert not (raiz / "00_System" / ".change-log.json").exists()
    assert filas_de_bitacora(raiz) == []
    paso = [s for s in envelope["steps"] if s["step"] == "change_log"]
    assert paso == [{"step": "change_log", "ok": True,
                     "created": ["00_System/change-log.md", "00_System/.change-log.jsonl"]}]
    # Born before the first index: indexed, and versioned from the first
    # commit (rule 5 of `vault.kernel.vcs` keeps the line file in git).
    versionados = git_en(raiz, "ls-files").splitlines()
    assert "00_System/change-log.md" in versionados
    assert "00_System/.change-log.jsonl" in versionados
    assert git_en(raiz, "status", "--porcelain") == ""


def test_la_primera_operacion_anotada_no_deja_el_indice_desfasado(vault):
    antes = _estado(vault)
    assert antes["codigo"] == 0 and antes["status"] == "index_ok", antes

    r = correr_tool("vault_change_log", "--action", "created", "--path",
                    "07_Knowledge/una-nota.md", "--reason", "primera", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert r.envelope["written"] == 2

    despues = _estado(vault)
    assert despues["codigo"] == 0 and despues["status"] == "index_ok", despues
    assert despues["missing_in_index"] == [] and despues["modified_in_index"] == []
    # The row was appended after the header the vault was born with.
    texto = (vault / "00_System" / "change-log.md").read_text(encoding="utf-8")
    assert texto.startswith(MD_HEADER)
    assert texto[len(MD_HEADER):].count("\n") == 1
    assert "| `created` | `07_Knowledge/una-nota.md` |" in texto
    filas = filas_de_bitacora(vault)
    assert [(f["action"], f["path"]) for f in filas] == [("created", "07_Knowledge/una-nota.md")]


def test_un_vault_con_log_no_se_toca_al_reinicializarlo(vault):
    """Previous behaviour holds: an existing log is never rewritten, and a
    legacy array without the line file keeps its one-time check on append."""
    sistema = vault / "00_System"
    (sistema / ".change-log.jsonl").unlink(missing_ok=True)
    legado = sistema / ".change-log.json"
    legado.write_bytes(json.dumps([{
        "id": "a", "action": "created", "path": "07_Knowledge/vieja.md", "new_path": None,
        "reason": "antes", "agent": "pytest", "timestamp": "2026-01-01T00:00:00.000Z",
    }]).encode("utf-8"))
    md = sistema / "change-log.md"
    md.write_bytes(MD_HEADER.encode("utf-8") + b"| fila previa |\n")
    bytes_legado, bytes_md = legado.read_bytes(), md.read_bytes()

    r = correr_tool("vault_init", "--no-audit", vault=vault)
    assert r.codigo == 0, r.stdout + r.stderr
    assert [s.get("created") for s in r.envelope["steps"]
            if s["step"] == "change_log"] in ([], [[]])
    assert legado.read_bytes() == bytes_legado
    assert md.read_bytes() == bytes_md
    assert not (sistema / ".change-log.jsonl").exists()
    assert [f["id"] for f in filas_de_bitacora(vault)] == ["a"]


def test_init_del_log_no_reescribe_un_log_que_existe(vault):
    """`vault_change_log --init` writes only what is missing, and records nothing."""
    sistema = vault / "00_System"
    r = correr_tool("vault_change_log", "--action", "created", "--path",
                    "07_Knowledge/una-nota.md", "--reason", "primera", vault=vault)
    assert r.envelope["ok"], r.envelope
    antes = {n: (sistema / n).read_bytes() for n in ("change-log.md", ".change-log.jsonl")}

    r = correr_tool("vault_change_log", "--init", vault=vault)
    assert r.codigo == 0 and r.envelope["ok"], r.envelope
    assert r.envelope["seeded"] == [] and r.envelope["written"] == 0
    assert {n: (sistema / n).read_bytes() for n in antes} == antes

    (sistema / "change-log.md").unlink()
    r = correr_tool("vault_change_log", "--init", vault=vault)
    assert r.envelope["seeded"] == ["00_System/change-log.md"], r.envelope
    assert (sistema / "change-log.md").read_text(encoding="utf-8") == MD_HEADER
    assert (sistema / ".change-log.jsonl").read_bytes() == antes[".change-log.jsonl"]
    assert len(filas_de_bitacora(vault)) == 1


@pytest.mark.parametrize("extra", [
    ("--action", "created", "--path", "07_Knowledge/z.md", "--reason", "deberia registrarse"),
    ("--query",),
    ("--propagate", "conservative"),
])
def test_init_no_se_combina_con_otras_opciones(vault, extra):
    """Independent verifier (2026-11-19, B1): `--init --action ... --reason ...`
    answered ok and recorded nothing; `--init --query` answered the init and
    skipped the query. An option the tool ignores with success is a silent
    lie (AP-37): the combination is refused before anything is written."""
    antes = filas_de_bitacora(vault)
    r = correr_tool("vault_change_log", "--init", *extra, vault=vault)
    assert r.codigo == 2, r.stdout + r.stderr
    assert "--init" in (r.stdout + r.stderr)
    assert filas_de_bitacora(vault) == antes
